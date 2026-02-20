"""Rule 7.2: No stale branches."""

import time

from gitguard.git import branch_ages, delete_branch, merged_branches
from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status

_90_DAYS = 90 * 86400


class StaleBranchesRule(Rule):
    id = "STALE_BRANCHES"
    name = "No stale branches"
    category = Category.GIT_HYGIENE

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

    def fix(self, repo, *, dry_run=False):
        merged = merged_branches(repo.path)
        if not merged:
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            names = ", ".join(merged)
            return FixOutcome(FixOutcome.FIXED, f"Would delete {len(merged)} merged branch(es): {names}")

        deleted = []
        failed = []
        for branch in merged:
            if delete_branch(repo.path, branch):
                deleted.append(branch)
            else:
                failed.append(branch)

        if failed:
            names = ", ".join(failed)
            return FixOutcome(FixOutcome.FAILED, f"Could not delete: {names}")

        names = ", ".join(deleted)
        return FixOutcome(FixOutcome.FIXED, f"Deleted {len(deleted)} merged branch(es): {names}")
