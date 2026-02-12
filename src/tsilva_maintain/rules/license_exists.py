"""Rule 1.8: LICENSE must exist."""

import subprocess
from datetime import datetime

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status
from tsilva_maintain.templates import load_template


def _has_license_file(repo_path) -> bool:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (repo_path / name).is_file():
            return True
    return False


class LicenseExistsRule(Rule):
    id = "LICENSE_EXISTS"
    name = "LICENSE must exist"
    category = Category.REPO_STRUCTURE
    rule_number = "1.8"
    fix_type = FixType.AUTO

    def check(self, repo):
        if _has_license_file(repo.path):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No LICENSE file found")

    def fix(self, repo, *, dry_run=False):
        if _has_license_file(repo.path):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would create LICENSE")

        try:
            template = load_template("LICENSE")
            # Get author from git config
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
