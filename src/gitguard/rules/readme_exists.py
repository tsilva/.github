"""Rule 1.1: README must exist."""

from gitguard.rules import Category, CheckResult, Rule, Status


class ReadmeExistsRule(Rule):
    id = "README_EXISTS"
    name = "README must exist"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        if (repo.path / "README.md").is_file():
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "README.md not found")
