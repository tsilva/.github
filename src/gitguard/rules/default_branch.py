"""Rule 7.3: Default branch must be 'main'."""

from gitguard.git import has_branch
from gitguard.rules import Category, CheckResult, Rule, Status


class DefaultBranchRule(Rule):
    id = "DEFAULT_BRANCH"
    name = "Default branch must be 'main'"
    category = Category.GIT_HYGIENE

    def check(self, repo):
        if has_branch(repo.path, "main"):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No 'main' branch found")
