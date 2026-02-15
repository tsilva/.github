"""Rule 1.2: README must be current."""

import re

from gitguard.rules import Category, CheckResult, Rule, Status

_PLACEHOLDERS = ["TODO", "FIXME", "Coming soon", "Work in progress", "Under construction", "[Insert", "Lorem ipsum"]


class ReadmeCurrentRule(Rule):
    id = "README_CURRENT"
    name = "README must be current"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        readme = repo.path / "README.md"
        if not readme.is_file():
            return CheckResult(Status.FAIL, "README.md does not exist")

        content = readme.read_text(encoding="utf-8", errors="replace")
        issues = []

        for placeholder in _PLACEHOLDERS:
            if re.search(re.escape(placeholder), content, re.IGNORECASE):
                issues.append(f"Contains placeholder: '{placeholder}'")

        if len(content) < 100:
            issues.append("README is very short (<100 chars)")

        content_lower = content.lower()
        has_install = bool(re.search(r"install|setup|getting started", content_lower))
        has_usage = bool(re.search(r"usage|example|how to", content_lower))

        if not has_install and not has_usage:
            issues.append("Missing installation/usage sections")

        if not issues:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "; ".join(issues))
