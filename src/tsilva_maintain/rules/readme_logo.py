"""Rule 1.6: README must reference logo."""

import re

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, Rule, Status
from tsilva_maintain.rules.logo_exists import LOGO_LOCATIONS

_LOGO_PATTERN_MD = re.compile(r'!\[.*\]\(\.?/?((assets|images|\.github)/)?logo\.', re.IGNORECASE)
_LOGO_PATTERN_HTML = re.compile(r'<img[^>]+src=.\.?/?((assets|images|\.github)/)?logo\.', re.IGNORECASE)


def _readme_has_logo_ref(content: str) -> bool:
    return bool(_LOGO_PATTERN_MD.search(content) or _LOGO_PATTERN_HTML.search(content))


class ReadmeLogoRule(Rule):
    id = "README_LOGO"
    name = "README must reference logo"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        readme = repo.path / "README.md"
        if not readme.is_file():
            return CheckResult(Status.FAIL, "README.md does not exist")
        content = readme.read_text(encoding="utf-8", errors="replace")
        if _readme_has_logo_ref(content):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "README does not reference logo")

    def fix(self, repo, *, dry_run=False):
        readme = repo.path / "README.md"
        if not readme.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No README.md")

        # Find logo file
        logo_path = None
        for loc in LOGO_LOCATIONS:
            if (repo.path / loc).is_file():
                logo_path = loc
                break
        if not logo_path:
            return FixOutcome(FixOutcome.SKIPPED, "No logo file found")

        content = readme.read_text(encoding="utf-8", errors="replace")
        if _readme_has_logo_ref(content):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, f"Would insert logo reference -> {logo_path}")

        logo_block = f'\n<p align="center">\n  <img src="{logo_path}" alt="{repo.name} logo" width="200">\n</p>\n'

        lines = content.splitlines(keepends=True)
        # Find first heading and insert after it
        for i, line in enumerate(lines):
            if line.startswith("# "):
                lines.insert(i + 1, logo_block)
                break
        else:
            # No heading — prepend
            lines.insert(0, logo_block + "\n")

        try:
            readme.write_text("".join(lines), encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, f"Inserted logo reference -> {logo_path}")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
