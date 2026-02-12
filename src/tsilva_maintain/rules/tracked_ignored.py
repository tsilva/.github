"""Rule 1.11: No tracked files matching gitignore."""

from tsilva_maintain.git import tracked_ignored_files
from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class TrackedIgnoredRule(Rule):
    id = "TRACKED_IGNORED"
    name = "No tracked files matching gitignore"
    category = Category.REPO_STRUCTURE
    rule_number = "1.11"
    fix_type = FixType.MANUAL

    def check(self, repo):
        files = tracked_ignored_files(repo.path)
        if not files:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, f"{len(files)} tracked file(s) match gitignore")
