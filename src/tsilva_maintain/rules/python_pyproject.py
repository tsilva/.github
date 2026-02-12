"""Rule 3.1: Python projects must use pyproject.toml."""

from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class PythonPyprojectRule(Rule):
    id = "PYTHON_PYPROJECT"
    name = "Python projects must use pyproject.toml"
    category = Category.PYTHON
    rule_number = "3.1"
    fix_type = FixType.MANUAL

    def applies_to(self, repo):
        return repo.is_python

    def check(self, repo):
        if not repo.is_python:
            return CheckResult(Status.SKIP)
        if repo.has_pyproject:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Python project missing pyproject.toml")
