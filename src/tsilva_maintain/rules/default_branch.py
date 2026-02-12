"""Rule 7.3: Default branch must be 'main'."""

from tsilva_maintain.git import has_branch
from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class DefaultBranchRule(Rule):
    id = "DEFAULT_BRANCH"
    name = "Default branch must be 'main'"
    category = Category.GIT_HYGIENE
    rule_number = "7.3"
    fix_type = FixType.MANUAL

    def check(self, repo):
        if has_branch(repo.path, "main"):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No 'main' branch found")
