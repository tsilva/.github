"""Rule: Python repos should have ruff configured."""

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status

_RUFF_DEFAULTS = """
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]
"""


def _has_ruff_config(repo_path) -> bool:
    # Check ruff.toml or .ruff.toml
    if (repo_path / "ruff.toml").is_file() or (repo_path / ".ruff.toml").is_file():
        return True
    # Check pyproject.toml for [tool.ruff]
    pyproject = repo_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            return "[tool.ruff]" in content
        except Exception:
            pass
    return False


class RuffConfigRule(Rule):
    id = "RUFF_CONFIG"
    name = "Python repos should have ruff configured"
    category = Category.PYTHON

    def applies_to(self, repo):
        return repo.is_python

    def check(self, repo):
        if _has_ruff_config(repo.path):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No ruff configuration found")

    def fix(self, repo, *, dry_run=False):
        if _has_ruff_config(repo.path):
            return FixOutcome(FixOutcome.ALREADY_OK)

        pyproject = repo.path / "pyproject.toml"
        if not pyproject.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No pyproject.toml to inject ruff config into")

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would inject [tool.ruff] section into pyproject.toml")

        try:
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            content = content.rstrip() + "\n" + _RUFF_DEFAULTS
            pyproject.write_text(content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Injected [tool.ruff] section into pyproject.toml")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
