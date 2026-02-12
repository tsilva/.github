"""Rule 3.3: Python projects must specify minimum Python version."""

from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class PythonMinVersionRule(Rule):
    id = "PYTHON_MIN_VERSION"
    name = "Must specify minimum Python version"
    category = Category.PYTHON
    rule_number = "3.3"
    fix_type = FixType.NONE

    def applies_to(self, repo):
        return repo.has_pyproject

    def check(self, repo):
        if not repo.has_pyproject:
            return CheckResult(Status.SKIP)

        try:
            import tomllib
            with open(repo.path / "pyproject.toml", "rb") as f:
                data = tomllib.load(f)
            rp = data.get("project", {}).get("requires-python", "")
            if rp:
                return CheckResult(Status.PASS)
            return CheckResult(Status.FAIL, "pyproject.toml missing requires-python")
        except Exception:
            return CheckResult(Status.FAIL, "pyproject.toml missing requires-python")
