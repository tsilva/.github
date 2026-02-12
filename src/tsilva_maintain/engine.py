"""RuleRunner: discover -> check -> fix -> report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tsilva_maintain import output
from tsilva_maintain.repo import Repo
from tsilva_maintain.rules import CheckResult, FixOutcome, Rule, Status
from tsilva_maintain.rules._registry import discover_rules


class RuleRunner:
    """Orchestrates rule discovery, audit, fix, and maintain flows."""

    def __init__(
        self,
        repos_dir: Path,
        filter_pattern: str = "",
        rule_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
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

    def audit(self, *, json_output: bool = False) -> int:
        repos = Repo.discover(self.repos_dir, self.filter_pattern)
        rules = self._filter_rules()

        if not repos:
            output.info("No git repositories found.")
            return 0

        total_passed = 0
        total_failed = 0
        total_skipped = 0

        json_repos = []

        if not json_output:
            output.banner("Repo Audit")
            output.info(f"Directory: {self.repos_dir}")
            output.info(f"Repositories: {len(repos)}")
            print("", file=__import__("sys").stderr)

        for repo in repos:
            repo_passed = 0
            repo_failed = 0
            repo_skipped = 0
            failed_checks = []
            json_checks = []

            for rule in rules:
                if not rule.applies_to(repo):
                    result = CheckResult(Status.SKIP)
                else:
                    result = rule.check(repo)

                if result.status == Status.PASS:
                    repo_passed += 1
                    status_str = "passed"
                elif result.status == Status.SKIP:
                    repo_skipped += 1
                    repo_passed += 1  # Skips count as passed
                    status_str = "skipped"
                else:
                    repo_failed += 1
                    status_str = "failed"
                    failed_checks.append((rule.id, result.message))

                if json_output:
                    json_checks.append({
                        "check": rule.id,
                        "status": status_str,
                        "message": result.message,
                    })

            total_passed += repo_passed
            total_failed += repo_failed
            total_skipped += repo_skipped

            if not json_output:
                if repo_failed == 0:
                    output.success(f"{repo.name} ({repo_passed}/{repo_passed} passed)")
                else:
                    output.error(f"{repo.name} ({repo_failed} failed)")
                    for check_id, msg in failed_checks:
                        output.detail(f"{output.RED}{check_id}{output.NC}: {msg}")

            if json_output:
                json_repos.append({
                    "repo": repo.name,
                    "path": str(repo.path),
                    "checks": json_checks,
                    "summary": {
                        "passed": repo_passed,
                        "failed": repo_failed,
                        "skipped": repo_skipped,
                    },
                })

        total_checks = total_passed + total_failed
        pass_rate = round(total_passed * 100 / total_checks) if total_checks > 0 else 0

        if json_output:
            # Detect GitHub user from first repo
            github_user = ""
            if repos and repos[0].github_repo:
                github_user = repos[0].github_repo.split("/")[0]

            report = {
                "audit_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "repos_dir": str(self.repos_dir),
                "github_user": github_user,
                "repos_count": len(repos),
                "repos": json_repos,
                "summary": {
                    "total_checks": total_checks,
                    "passed": total_passed,
                    "failed": total_failed,
                    "pass_rate": pass_rate,
                },
            }
            print(json.dumps(report, indent=2))
        else:
            output.header("Results")
            import sys
            print(f"  Checks:    {total_passed}/{total_checks} passed ({pass_rate}%)", file=sys.stderr)
            print(f"  Passed:    {output.GREEN}{total_passed}{output.NC}", file=sys.stderr)
            print(f"  Failed:    {output.RED}{total_failed}{output.NC}", file=sys.stderr)
            if total_skipped > 0:
                print(f"  Skipped:   {output.DIM}{total_skipped}{output.NC}", file=sys.stderr)

        return 1 if total_failed > 0 else 0

    def fix(self, *, dry_run: bool = False) -> int:
        repos = Repo.discover(self.repos_dir, self.filter_pattern)
        rules = self._filter_rules()

        if not repos:
            output.info("No git repositories found.")
            return 0

        total_fixed = 0
        total_already_ok = 0
        total_skipped = 0
        total_failed = 0

        output.banner("Fix Mode" + (" (dry run)" if dry_run else ""))
        output.info(f"Directory: {self.repos_dir}")
        output.info(f"Repositories: {len(repos)}")
        print("", file=__import__("sys").stderr)

        for repo in repos:
            repo_actions = []

            for rule in rules:
                if not rule.applies_to(repo):
                    continue

                result = rule.check(repo)
                if result.status != Status.FAIL:
                    continue

                outcome = rule.fix(repo, dry_run=dry_run)

                if outcome.status == FixOutcome.FIXED:
                    total_fixed += 1
                    repo_actions.append((rule.id, "fixed", outcome.message))
                elif outcome.status == FixOutcome.ALREADY_OK:
                    total_already_ok += 1
                elif outcome.status == FixOutcome.SKIPPED:
                    total_skipped += 1
                    repo_actions.append((rule.id, "skipped", outcome.message))
                elif outcome.status == FixOutcome.MANUAL:
                    total_skipped += 1
                    repo_actions.append((rule.id, "manual", outcome.message))
                else:
                    total_failed += 1
                    repo_actions.append((rule.id, "failed", outcome.message))

            if repo_actions:
                for rule_id, status, msg in repo_actions:
                    if status == "fixed":
                        output.step(f"{repo.name}: {rule_id} - {msg}")
                    elif status == "failed":
                        output.error(f"{repo.name}: {rule_id} - {msg}")
                    else:
                        output.skip(f"{repo.name}: {rule_id} - {msg}")

        import sys
        output.header("Fix Results")
        print(f"  Fixed:     {output.GREEN}{total_fixed}{output.NC}", file=sys.stderr)
        print(f"  Skipped:   {output.DIM}{total_skipped}{output.NC}", file=sys.stderr)
        print(f"  Failed:    {output.RED}{total_failed}{output.NC}", file=sys.stderr)

        return 1 if total_failed > 0 else 0

    def maintain(self, *, dry_run: bool = False) -> int:
        """Full audit -> fix -> verify cycle."""
        import sys

        output.banner("Maintain (audit -> fix -> verify)")

        # Phase 1: Audit
        output.header("Phase 1: Audit")
        print("", file=sys.stderr)
        self.audit()

        # Phase 2: Fix
        output.header("Phase 2: Fix")
        print("", file=sys.stderr)
        self.fix(dry_run=dry_run)

        # Phase 3: Verify
        output.header("Phase 3: Verify")
        print("", file=sys.stderr)
        return self.audit()
