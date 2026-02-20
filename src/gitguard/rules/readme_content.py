"""README content rules (license reference, CI badge)."""

import re

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status
from gitguard.rules._helpers import has_license_file


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


def _find_ci_workflow_filename(repo_path) -> str | None:
    """Return the filename of the CI workflow (ci.yml, release.yml, etc.), or None."""
    wf_dir = repo_path / ".github" / "workflows"
    if not wf_dir.is_dir():
        return None
    # Preferred names in priority order
    for preferred in ("ci.yml", "release.yml", "test.yml", "ci.yaml", "release.yaml"):
        if (wf_dir / preferred).exists():
            return preferred
    # Fall back to first workflow containing pytest/CI pattern
    for wf_file in sorted(wf_dir.iterdir()):
        if wf_file.suffix not in (".yml", ".yaml"):
            continue
        try:
            content = wf_file.read_text(encoding="utf-8", errors="replace")
            if re.search(r"tsilva/\.github/.*/(test|release|ci)\.yml|pytest", content):
                return wf_file.name
        except Exception:
            continue
    return None


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

    def fix(self, repo, *, dry_run=False):
        readme = repo.path / "README.md"
        if not readme.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No README.md")

        content = readme.read_text(encoding="utf-8", errors="replace")
        if re.search(r"actions/workflows/.*badge|shields\.io.*workflow|!\[.*\]\(.*actions/workflows", content):
            return FixOutcome(FixOutcome.ALREADY_OK)

        gh_repo = repo.github_repo
        if not gh_repo:
            return FixOutcome(FixOutcome.SKIPPED, "Cannot determine GitHub repo name")

        wf_name = _find_ci_workflow_filename(repo.path)
        if not wf_name:
            return FixOutcome(FixOutcome.SKIPPED, "Cannot determine CI workflow filename")

        badge_url = f"https://github.com/{gh_repo}/actions/workflows/{wf_name}/badge.svg"
        wf_url = f"https://github.com/{gh_repo}/actions/workflows/{wf_name}"
        badge_line = f"[![CI]({badge_url})]({wf_url})\n"

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, f"Would insert CI badge for {wf_name}")

        try:
            # Insert badge after first `#` heading line
            lines = content.splitlines(keepends=True)
            insert_at = None
            for i, line in enumerate(lines):
                if line.startswith("#"):
                    insert_at = i + 1
                    break

            if insert_at is None:
                # No heading found — prepend badge at top
                new_content = badge_line + "\n" + content
            else:
                # Insert after heading, with blank line separator
                lines.insert(insert_at, "\n")
                lines.insert(insert_at + 1, badge_line)
                new_content = "".join(lines)

            readme.write_text(new_content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, f"Inserted CI badge for {wf_name}")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
