"""Rule 5.1: CLAUDE.md must exist."""

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status
from tsilva_maintain.templates import load_template


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
