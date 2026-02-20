"""Rule 1.1: README must exist."""

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status


class ReadmeExistsRule(Rule):
    id = "README_EXISTS"
    name = "README must exist"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        if (repo.path / "README.md").is_file():
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "README.md not found")

    def fix(self, repo, *, dry_run=False):
        readme = repo.path / "README.md"
        if readme.is_file():
            return FixOutcome(FixOutcome.ALREADY_OK)
        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would create README.md")
        try:
            readme.write_text(f"# {repo.name}\n\nTODO: Add description.\n", encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Created README.md scaffold")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
