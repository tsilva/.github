"""Rule 7.1: No pending commits."""

from tsilva_maintain.git import status_porcelain, unpushed_commits
from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class PendingCommitsRule(Rule):
    id = "PENDING_COMMITS"
    name = "No pending commits"
    category = Category.GIT_HYGIENE
    rule_number = "7.1"
    fix_type = FixType.MANUAL

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
