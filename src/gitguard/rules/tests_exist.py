"""Rule: CLI/library projects should have tests."""

from gitguard.rules import Category, CheckResult, Rule, Status


class TestsExistRule(Rule):
    id = "TESTS_EXIST"
    name = "CLI projects should have tests"
    category = Category.PYTHON

    def applies_to(self, repo):
        return repo.is_cli

    def check(self, repo):
        for pattern in ("test_*.py", "*_test.py"):
            if any(repo.path.rglob(pattern)):
                return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No test files found (test_*.py or *_test.py)")
