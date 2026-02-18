"""Rule: archived repos must have a .archived.md marker file."""

from gitguard.rules import Category, CheckResult, Rule, Status


class ArchivedMarkerRule(Rule):
    id = "ARCHIVED_MARKER"
    name = "Archived repos must have .archived.md"
    category = Category.REPO_STRUCTURE
    archived_only = True

    def check(self, repo) -> CheckResult:
        marker = repo.path / ".archived.md"
        if marker.is_file():
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Missing .archived.md file")
