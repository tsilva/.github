"""Rule 1.9: .gitignore must exist."""

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status

ESSENTIAL_GITIGNORE = [".env", ".DS_Store", "node_modules/", "__pycache__/", "*.pyc", ".venv/"]


class GitignoreExistsRule(Rule):
    id = "GITIGNORE_EXISTS"
    name = ".gitignore must exist"
    category = Category.REPO_STRUCTURE
    rule_number = "1.9"
    fix_type = FixType.AUTO

    def check(self, repo):
        if (repo.path / ".gitignore").is_file():
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, ".gitignore not found")

    def fix(self, repo, *, dry_run=False):
        gitignore = repo.path / ".gitignore"
        if gitignore.is_file():
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would create .gitignore with essential patterns")

        try:
            content = "# Managed by tsilva/.github\n# Do not remove - synced automatically\n"
            content += "\n".join(ESSENTIAL_GITIGNORE) + "\n"
            gitignore.write_text(content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, f"Created .gitignore ({len(ESSENTIAL_GITIGNORE)} patterns)")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
