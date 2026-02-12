"""Rule 1.4: README must have CI badge."""

import re

from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class ReadmeCiBadgeRule(Rule):
    id = "README_CI_BADGE"
    name = "README must have CI badge"
    category = Category.REPO_STRUCTURE
    rule_number = "1.4"
    fix_type = FixType.NONE

    def applies_to(self, repo):
        return repo.has_workflows

    def check(self, repo):
        if not repo.has_workflows:
            return CheckResult(Status.SKIP)

        readme = repo.path / "README.md"
        if not readme.is_file():
            return CheckResult(Status.FAIL, "README.md does not exist")

        content = readme.read_text(encoding="utf-8", errors="replace")
        if re.search(r"actions/workflows/.*badge|shields\.io.*workflow|!\[.*\]\(.*actions/workflows", content):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "README missing CI badge")
