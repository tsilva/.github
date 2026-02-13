"""README content rules (license reference, CI badge)."""

import re

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, Rule, Status
from tsilva_maintain.rules._helpers import has_license_file


def _readme_has_license_ref(readme_path) -> bool:
    try:
        content = readme_path.read_text(encoding="utf-8", errors="replace").lower()
        return bool(re.search(r"## license|# license|mit license|\[mit\]", content))
    except Exception:
        return False


class ReadmeLicenseRule(Rule):
    id = "README_LICENSE"
    name = "README must reference license"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        readme = repo.path / "README.md"
        if not readme.is_file():
            return CheckResult(Status.FAIL, "README.md does not exist")
        if _readme_has_license_ref(readme):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "README missing license reference")

    def fix(self, repo, *, dry_run=False):
        readme = repo.path / "README.md"
        if not readme.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No README.md")
        if not has_license_file(repo.path):
            return FixOutcome(FixOutcome.SKIPPED, "No LICENSE file")
        if _readme_has_license_ref(readme):
            return FixOutcome(FixOutcome.ALREADY_OK)
        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would append license section")
        try:
            with open(readme, "a", encoding="utf-8") as f:
                f.write("\n## License\n\nMIT\n")
            return FixOutcome(FixOutcome.FIXED, "Appended license section")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))


class ReadmeCiBadgeRule(Rule):
    id = "README_CI_BADGE"
    name = "README must have CI badge"
    category = Category.REPO_STRUCTURE

    def applies_to(self, repo):
        return repo.has_ci_workflow

    def check(self, repo):
        readme = repo.path / "README.md"
        if not readme.is_file():
            return CheckResult(Status.FAIL, "README.md does not exist")

        content = readme.read_text(encoding="utf-8", errors="replace")
        if re.search(r"actions/workflows/.*badge|shields\.io.*workflow|!\[.*\]\(.*actions/workflows", content):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "README missing CI badge")
