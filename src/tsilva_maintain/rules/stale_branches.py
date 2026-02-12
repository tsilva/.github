"""Rule 7.2: No stale branches."""

import time

from tsilva_maintain.git import branch_ages, merged_branches
from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status

_90_DAYS = 90 * 86400


class StaleBranchesRule(Rule):
    id = "STALE_BRANCHES"
    name = "No stale branches"
    category = Category.GIT_HYGIENE
    rule_number = "7.2"
    fix_type = FixType.MANUAL

    def check(self, repo):
        issues = []

        merged = merged_branches(repo.path)
        if merged:
            names = ", ".join(merged)
            issues.append(f"{len(merged)} merged branch(es): {names}")

        cutoff = int(time.time()) - _90_DAYS
        stale = []
        for branch, epoch in branch_ages(repo.path):
            if branch in ("main", "master"):
                continue
            if epoch < cutoff:
                stale.append(branch)

        if stale:
            names = ", ".join(stale)
            issues.append(f"{len(stale)} stale branch(es) (>90d): {names}")

        if not issues:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "; ".join(issues))
