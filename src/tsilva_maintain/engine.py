"""RuleRunner: single-pass check-and-fix engine."""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tsilva_maintain import git, output
from tsilva_maintain.github import fetch_org_repo_metadata, get_workflow_conclusions
from tsilva_maintain.progress import ProgressBar
from tsilva_maintain.repo import Repo
from tsilva_maintain.rules import CheckResult, FixOutcome, Rule, Status
from tsilva_maintain.rules._registry import discover_rules


@dataclass
class RuleResult:
    """Outcome for a single rule on a single repo."""

    rule_id: str
    status: str  # "pass", "skip", "fixed", "fix_failed", "manual", "failed"
    message: str = ""


@dataclass
class RepoResult:
    """Aggregated results for a single repo."""

    name: str
    path: str
    results: list[RuleResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status in ("pass", "skip"))

    @property
    def fixed(self) -> int:
        return sum(1 for r in self.results if r.status == "fixed")

    @property
    def manual(self) -> list[RuleResult]:
        return [r for r in self.results if r.status in ("manual", "failed", "fix_failed")]

    @property
    def all_ok(self) -> bool:
        return len(self.manual) == 0


class RuleRunner:
    """Single-pass engine: check each rule, fix if needed, verify."""

    def __init__(
        self,
        repos_dir: Path,
        filter_pattern: str = "",
        rule_filter: str | None = None,
        category_filter: str | None = None,
    ):
        self.repos_dir = repos_dir
        self.filter_pattern = filter_pattern
        self.rule_filter = rule_filter
        self.category_filter = category_filter
        self.rules = discover_rules()

    def _filter_rules(self) -> list[Rule]:
        rules = self.rules
        if self.rule_filter:
            rules = [r for r in rules if r.id == self.rule_filter]
        if self.category_filter:
            cat_upper = self.category_filter.upper().replace(" ", "_")
            rules = [r for r in rules if r.category.name == cat_upper]
        return rules

    def run(
        self,
        *,
        dry_run: bool = False,
        json_output: bool = False,
    ) -> int:
        """Single-pass: for each repo, check each rule and optionally fix."""
        if not json_output:
            output.step("Discovering repositories\u2026")
        org_metadata = fetch_org_repo_metadata("tsilva")
        non_archived = set(org_metadata)
        if non_archived:
            all_local = {
                child.name
                for child in self.repos_dir.iterdir()
                if child.is_dir() and (child / ".git").is_dir()
            }
            archived_names = all_local - non_archived
        else:
            archived_names = None

        # Clone missing repos before discovery
        cloned: list[str] = []
        clone_errors: list[str] = []
        if non_archived:
            to_clone = sorted(non_archived - all_local)
            if self.filter_pattern:
                to_clone = [n for n in to_clone if self.filter_pattern in n]
            if to_clone:
                if not json_output:
                    output.step(f"Cloning {len(to_clone)} missing repo(s)\u2026")
                if dry_run:
                    for name in to_clone:
                        if not json_output:
                            output.skip(f"{name} (would clone)")
                        cloned.append(name)
                else:
                    errors_lock = threading.Lock()

                    def _clone_one(name: str) -> None:
                        target = self.repos_dir / name
                        try:
                            r = git.clone_repo(f"tsilva/{name}", target)
                            if r.returncode == 0:
                                if not json_output:
                                    output.success(f"{name} (cloned)")
                                cloned.append(name)
                            else:
                                if not json_output:
                                    output.error(f"{name} (clone failed: {r.stderr.strip()})")
                                with errors_lock:
                                    clone_errors.append(name)
                        except Exception as e:
                            if not json_output:
                                output.error(f"{name} (clone failed: {e})")
                            with errors_lock:
                                clone_errors.append(name)

                    with ThreadPoolExecutor(max_workers=min(8, len(to_clone))) as pool:
                        list(pool.map(_clone_one, to_clone))

        repos = Repo.discover(self.repos_dir, self.filter_pattern, archived_names=archived_names)
        rules = self._filter_rules()

        if not repos:
            if not json_output:
                output.info("No git repositories found.")
            return 0

        # Inject prefetched descriptions and github_repo from metadata
        for repo in repos:
            if repo.name in org_metadata:
                repo._prefetch["description"] = org_metadata[repo.name]
            repo._prefetch["github_repo"] = f"tsilva/{repo.name}"

        # Prefetch workflow conclusions in parallel
        if not json_output:
            output.step("Prefetching workflow status\u2026")
        wf_repos = [r for r in repos if r.has_workflows and r.github_repo]

        def _fetch_wf(repo: Repo) -> None:
            repo._prefetch["workflow_conclusions"] = get_workflow_conclusions(repo.github_repo)  # type: ignore[arg-type]

        with ThreadPoolExecutor(max_workers=8) as pool:
            pool.map(_fetch_wf, wf_repos)

        progress = ProgressBar(len(repos) * len(rules)) if not json_output else None

        def _process_repo(repo: Repo) -> RepoResult:
            rr = RepoResult(name=repo.name, path=str(repo.path))
            if not dry_run and not repo.is_dirty:
                try:
                    git.fetch_all(repo.path)
                except Exception:
                    pass
            try:
                for rule in rules:
                    if progress:
                        progress.update(repo.name, rule.id, "Checking")

                    if not rule.applies_to(repo):
                        rr.results.append(RuleResult(rule.id, "skip"))
                        continue

                    result = rule.check(repo)

                    if result.status == Status.PASS:
                        rr.results.append(RuleResult(rule.id, "pass"))
                        continue

                    if result.status == Status.SKIP:
                        rr.results.append(RuleResult(rule.id, "skip"))
                        continue

                    # Rule failed — attempt fix
                    if progress:
                        progress.set_phase(repo.name, rule.id, "Fixing")
                    outcome = rule.fix(repo, dry_run=dry_run)

                    if outcome.status == FixOutcome.FIXED:
                        if dry_run:
                            rr.results.append(RuleResult(rule.id, "fixed", outcome.message))
                        else:
                            if progress:
                                progress.set_phase(repo.name, rule.id, "Verifying")
                            verify = rule.check(repo)
                            if verify.status == Status.PASS:
                                rr.results.append(RuleResult(rule.id, "fixed", outcome.message))
                            else:
                                rr.results.append(RuleResult(rule.id, "fix_failed", verify.message))
                    elif outcome.status == FixOutcome.ALREADY_OK:
                        rr.results.append(RuleResult(rule.id, "pass"))
                    elif outcome.status == FixOutcome.MANUAL:
                        rr.results.append(RuleResult(rule.id, "manual", result.message))
                    elif outcome.status == FixOutcome.SKIPPED:
                        rr.results.append(RuleResult(rule.id, "manual", outcome.message))
                    else:
                        rr.results.append(RuleResult(rule.id, "failed", outcome.message))
            except Exception as exc:
                rr.results.append(RuleResult("INTERNAL", "failed", str(exc)))
            return rr

        max_workers = min(8, len(repos))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            repo_results = list(pool.map(_process_repo, repos))

        if progress:
            progress.clear()

        sync_info = {"cloned": cloned, "clone_errors": clone_errors}

        if json_output:
            return self._output_json(repos, repo_results, sync=sync_info)

        return self._output_summary(repo_results, dry_run=dry_run)

    def _output_summary(
        self,
        repo_results: list[RepoResult],
        *,
        dry_run: bool,
    ) -> int:
        """Print compact per-repo summary with expanded details for failures."""
        mode = "Maintain (dry run)" if dry_run else "Maintain"
        output.banner(mode)
        output.info(f"Directory: {self.repos_dir}")
        output.info(f"Repositories: {len(repo_results)}")
        print("", file=sys.stderr)

        all_passing = 0
        needed_fixes = 0
        needs_work = 0

        for rr in repo_results:
            fixed = rr.fixed
            manual = rr.manual
            passed = rr.passed
            total = rr.total

            if manual:
                needs_work += 1
                parts = [f"{passed}/{total} passed"]
                if fixed:
                    parts.append(f"{fixed} fixed")
                parts.append(f"{len(manual)} manual")
                print(f"{output.BG_DARK}{output.RED}\u2717 {output.NC}{output.BG_DARK}{rr.name:<28} {', '.join(parts)}{output.NC}", file=sys.stderr)
                for i, m in enumerate(manual):
                    connector = "└" if i == len(manual) - 1 else "├"
                    output.detail(f"{output.DIM}{connector}{output.NC} {output.RED}{m.rule_id}{output.NC}: {m.message}")
            elif fixed:
                needed_fixes += 1
                print(f"{output.BG_DARK}{output.GREEN}\u2713 {output.NC}{output.BG_DARK}{rr.name:<28} {passed}/{total} passed ({fixed} fixed){output.NC}", file=sys.stderr)
            else:
                all_passing += 1
                print(f"{output.BG_DARK}{output.GREEN}\u2713 {output.NC}{output.BG_DARK}{rr.name:<28} {total}/{total} passed{output.NC}", file=sys.stderr)

        # Summary footer
        output.header("Results")
        print(f"  Repos:        {len(repo_results)}", file=sys.stderr)
        print(f"  All passing:  {output.GREEN}{all_passing}{output.NC}", file=sys.stderr)
        if needed_fixes:
            print(f"  Needed fixes: {output.YELLOW}{needed_fixes}{output.NC} (all auto-fixed)", file=sys.stderr)
        if needs_work:
            print(f"  Needs work:   {output.RED}{needs_work}{output.NC} (have remaining manual issues)", file=sys.stderr)

        return 1 if needs_work > 0 else 0

    def _output_json(self, repos: list[Repo], repo_results: list[RepoResult], *, sync: dict | None = None) -> int:
        """Output JSON report to stdout."""
        github_user = ""
        if repos and repos[0].github_repo:
            github_user = repos[0].github_repo.split("/")[0]

        total_checks = 0
        total_passed = 0
        total_failed = 0
        json_repos = []

        for rr in repo_results:
            checks = []
            for r in rr.results:
                if r.status in ("pass", "skip", "fixed"):
                    status_str = "passed" if r.status != "fixed" else "fixed"
                    total_passed += 1
                else:
                    status_str = "failed"
                    total_failed += 1
                total_checks += 1
                checks.append({
                    "check": r.rule_id,
                    "status": status_str,
                    "message": r.message,
                })

            json_repos.append({
                "repo": rr.name,
                "path": rr.path,
                "checks": checks,
                "summary": {
                    "passed": rr.passed + rr.fixed,
                    "failed": len(rr.manual),
                },
            })

        pass_rate = round(total_passed * 100 / total_checks) if total_checks > 0 else 0

        report = {
            "audit_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "repos_dir": str(self.repos_dir),
            "github_user": github_user,
            "repos_count": len(repo_results),
            "repos": json_repos,
            "summary": {
                "total_checks": total_checks,
                "passed": total_passed,
                "failed": total_failed,
                "pass_rate": pass_rate,
            },
        }
        if sync and (sync["cloned"] or sync["clone_errors"]):
            report["sync"] = sync
        print(json.dumps(report, indent=2))

        return 1 if total_failed > 0 else 0
