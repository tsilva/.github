"""Python project rules (pyproject.toml, minimum version)."""

from tsilva_maintain.rules import Category, CheckResult, Rule, Status


class PythonPyprojectRule(Rule):
    id = "PYTHON_PYPROJECT"
    name = "Python projects must use pyproject.toml"
    category = Category.PYTHON

    def applies_to(self, repo):
        return repo.is_python

    def check(self, repo):
        if repo.has_pyproject:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Python project missing pyproject.toml")


class PythonMinVersionRule(Rule):
    id = "PYTHON_MIN_VERSION"
    name = "Must specify minimum Python version"
    category = Category.PYTHON

    def applies_to(self, repo):
        return repo.has_pyproject

    def check(self, repo):
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
