"""RuleRunner: single-pass check-and-fix engine."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tsilva_maintain import output
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
        check_only: bool = False,
        dry_run: bool = False,
        json_output: bool = False,
    ) -> int:
        """Single-pass: for each repo, check each rule and optionally fix."""
        repos = Repo.discover(self.repos_dir, self.filter_pattern)
        rules = self._filter_rules()

        if not repos:
            if not json_output:
                output.info("No git repositories found.")
            return 0

        repo_results: list[RepoResult] = []

        for repo in repos:
            rr = RepoResult(name=repo.name, path=str(repo.path))

            for rule in rules:
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

                # Rule failed
                if check_only:
                    rr.results.append(RuleResult(rule.id, "failed", result.message))
                    continue

                # Attempt fix
                outcome = rule.fix(repo, dry_run=dry_run)

                if outcome.status == FixOutcome.FIXED:
                    # Re-check to verify the fix worked
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

            repo_results.append(rr)

        if json_output:
            return self._output_json(repos, repo_results)

        return self._output_summary(repo_results, check_only=check_only, dry_run=dry_run)

    def _output_summary(
        self,
        repo_results: list[RepoResult],
        *,
        check_only: bool,
        dry_run: bool,
    ) -> int:
        """Print compact per-repo summary with expanded details for failures."""
        mode = "Check" if check_only else ("Maintain (dry run)" if dry_run else "Maintain")
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
                output.error(f"{rr.name:<28} {', '.join(parts)}")
                for m in manual:
                    output.detail(f"{output.RED}{m.rule_id}{output.NC}: {m.message}")
            elif fixed:
                needed_fixes += 1
                output.success(f"{rr.name:<28} {passed}/{total} passed ({fixed} fixed)")
            else:
                all_passing += 1
                output.success(f"{rr.name:<28} {total}/{total} passed")

        # Summary footer
        output.header("Results")
        print(f"  Repos:        {len(repo_results)}", file=sys.stderr)
        print(f"  All passing:  {output.GREEN}{all_passing}{output.NC}", file=sys.stderr)
        if needed_fixes:
            print(f"  Needed fixes: {output.YELLOW}{needed_fixes}{output.NC} (all auto-fixed)", file=sys.stderr)
        if needs_work:
            print(f"  Needs work:   {output.RED}{needs_work}{output.NC} (have remaining manual issues)", file=sys.stderr)

        return 1 if needs_work > 0 else 0

    def _output_json(self, repos: list[Repo], repo_results: list[RepoResult]) -> int:
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
        print(json.dumps(report, indent=2))

        return 1 if total_failed > 0 else 0
