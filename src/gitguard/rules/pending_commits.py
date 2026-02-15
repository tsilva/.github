"""Rule 7.1: No pending commits."""

from gitguard.git import status_porcelain, unpushed_commits
from gitguard.rules import Category, CheckResult, Rule, Status


class PendingCommitsRule(Rule):
    id = "PENDING_COMMITS"
    name = "No pending commits"
    category = Category.GIT_HYGIENE

    def check(self, repo):
        issues = []

        porcelain = status_porcelain(repo.path)
        if porcelain:
            count = len(porcelain.splitlines())
            issues.append(f"{count} uncommitted change(s)")

        unpushed = unpushed_commits(repo.path)
        if unpushed:
            count = len(unpushed.splitlines())
            issues.append(f"{count} unpushed commit(s)")

        if not issues:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "; ".join(issues))
