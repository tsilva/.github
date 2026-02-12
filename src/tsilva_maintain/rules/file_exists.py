"""File existence rules (LICENSE, CLAUDE.md)."""

import subprocess
from datetime import datetime

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status
from tsilva_maintain.rules._helpers import has_license_file
from tsilva_maintain.templates import load_template


class LicenseExistsRule(Rule):
    id = "LICENSE_EXISTS"
    name = "LICENSE must exist"
    category = Category.REPO_STRUCTURE
    rule_number = "1.8"
    fix_type = FixType.AUTO

    def check(self, repo):
        if has_license_file(repo.path):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No LICENSE file found")

    def fix(self, repo, *, dry_run=False):
        if has_license_file(repo.path):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would create LICENSE")

        try:
            template = load_template("LICENSE")
            try:
                r = subprocess.run(
                    ["git", "-C", str(repo.path), "config", "user.name"],
                    capture_output=True, text=True, timeout=5,
                )
                author = r.stdout.strip() or "Author"
            except Exception:
                author = "Author"

            year = str(datetime.now().year)
            content = template.replace("[year]", year).replace("[fullname]", author)
            (repo.path / "LICENSE").write_text(content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, f"Created LICENSE (MIT, {year}, {author})")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))


class ClaudeMdExistsRule(Rule):
    id = "CLAUDE_MD_EXISTS"
    name = "CLAUDE.md must exist"
    category = Category.CLAUDE
    rule_number = "5.1"
    fix_type = FixType.AUTO

    def check(self, repo):
        if (repo.path / "CLAUDE.md").is_file():
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "CLAUDE.md not found")

    def fix(self, repo, *, dry_run=False):
        if (repo.path / "CLAUDE.md").is_file():
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would create CLAUDE.md")

        try:
            template = load_template("CLAUDE.md")
            content = template.replace("[project-name]", repo.name)
            (repo.path / "CLAUDE.md").write_text(content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Created CLAUDE.md")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
