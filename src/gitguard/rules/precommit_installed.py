"""Rule: pre-commit hooks actually installed in the local repo."""

import subprocess

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status


class PrecommitInstalledRule(Rule):
    id = "PRECOMMIT_INSTALLED"
    name = "Pre-commit hooks installed locally"
    category = Category.SECURITY

    def applies_to(self, repo):
        return repo.name != ".github"

    def check(self, repo):
        config = repo.path / ".pre-commit-config.yaml"
        if not config.is_file():
            return CheckResult(Status.SKIP, "No .pre-commit-config.yaml")

        hook = repo.path / ".git" / "hooks" / "pre-commit"
        if hook.is_file() and "pre-commit" in hook.read_text(encoding="utf-8", errors="replace"):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "pre-commit hooks not installed")

    def fix(self, repo, *, dry_run=False):
        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would run pre-commit install")

        try:
            subprocess.run(
                ["pre-commit", "install"],
                cwd=repo.path,
                capture_output=True,
                timeout=30,
                check=True,
            )
            return FixOutcome(FixOutcome.FIXED, "Ran pre-commit install")
        except FileNotFoundError:
            return FixOutcome(FixOutcome.FAILED, "pre-commit not installed on this system")
        except subprocess.TimeoutExpired:
            return FixOutcome(FixOutcome.FAILED, "pre-commit install timed out")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
