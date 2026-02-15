"""Rule 1.5: Logo must exist."""

from gitguard.rules import Category, CheckResult, Rule, Status

LOGO_LOCATIONS = [
    "logo.png", "logo.svg", "logo.jpg",
    "assets/logo.png", "assets/logo.svg",
    "images/logo.png", "images/logo.svg",
    ".github/logo.png", ".github/logo.svg",
]


class LogoExistsRule(Rule):
    id = "LOGO_EXISTS"
    name = "Logo must exist"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        for loc in LOGO_LOCATIONS:
            if (repo.path / loc).is_file():
                return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No logo found in standard locations")
