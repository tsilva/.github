"""Rule 6.2: Pre-commit hooks for secret scanning."""

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status
from tsilva_maintain.templates import load_template


class PrecommitGitleaksRule(Rule):
    id = "PRECOMMIT_GITLEAKS"
    name = "Pre-commit hooks for secret scanning"
    category = Category.SECURITY
    rule_number = "6.2"
    fix_type = FixType.AUTO

    def applies_to(self, repo):
        return repo.name != ".github"

    def check(self, repo):
        if repo.name == ".github":
            return CheckResult(Status.SKIP)

        config = repo.path / ".pre-commit-config.yaml"
        if not config.is_file():
            return CheckResult(Status.FAIL, ".pre-commit-config.yaml not found")

        content = config.read_text(encoding="utf-8", errors="replace")
        if "tsilva/.github" in content:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, ".pre-commit-config.yaml missing gitleaks hook")

    def fix(self, repo, *, dry_run=False):
        if repo.name == ".github":
            return FixOutcome(FixOutcome.SKIPPED, "Defines the hook")

        config = repo.path / ".pre-commit-config.yaml"

        if config.is_file():
            content = config.read_text(encoding="utf-8", errors="replace")
            if "tsilva/.github" in content:
                return FixOutcome(FixOutcome.ALREADY_OK)

            if dry_run:
                return FixOutcome(FixOutcome.FIXED, "Would append gitleaks hook")

            # Append the repo entry
            try:
                append = ""
                if content and not content.endswith("\n"):
                    append += "\n"
                append += "\n"
                append += (
                    "  - repo: https://github.com/tsilva/.github\n"
                    "    rev: main\n"
                    "    hooks:\n"
                    "      - id: gitleaks\n"
                )
                with open(config, "a", encoding="utf-8") as f:
                    f.write(append)
                return FixOutcome(FixOutcome.FIXED, "Appended gitleaks hook")
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))
        else:
            if dry_run:
                return FixOutcome(FixOutcome.FIXED, "Would create .pre-commit-config.yaml")

            try:
                template = load_template("pre-commit-config.yaml")
                config.write_text(template, encoding="utf-8")
                return FixOutcome(FixOutcome.FIXED, "Created .pre-commit-config.yaml")
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))
