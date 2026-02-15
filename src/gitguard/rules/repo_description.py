"""Rule 1.12: GitHub description must match README tagline."""

from gitguard.github import get_repo_description, gh_authenticated, set_repo_description
from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status
from gitguard.tagline import extract_tagline


class RepoDescriptionRule(Rule):
    id = "REPO_DESCRIPTION"
    name = "GitHub description must match README tagline"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        if not gh_authenticated():
            return CheckResult(Status.SKIP)

        github_repo = repo.github_repo
        if not github_repo:
            return CheckResult(Status.SKIP)

        readme = repo.path / "README.md"
        if not readme.is_file():
            return CheckResult(Status.SKIP)

        tagline = extract_tagline(str(readme))
        if not tagline:
            return CheckResult(Status.SKIP)

        github_desc = repo._prefetch.get("description")
        if github_desc is None:
            github_desc = get_repo_description(github_repo)
        if tagline == github_desc:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Description mismatch (GitHub vs README tagline)")

    def fix(self, repo, *, dry_run=False):
        if not gh_authenticated():
            return FixOutcome(FixOutcome.SKIPPED, "gh not authenticated")

        github_repo = repo.github_repo
        if not github_repo:
            return FixOutcome(FixOutcome.SKIPPED, "No GitHub remote")

        readme = repo.path / "README.md"
        if not readme.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No README.md")

        tagline = extract_tagline(str(readme))
        if not tagline:
            return FixOutcome(FixOutcome.SKIPPED, "No tagline found")

        github_desc = repo._prefetch.get("description")
        if github_desc is None:
            github_desc = get_repo_description(github_repo)
        if tagline == github_desc:
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, f"Would update description to: {tagline}")

        if set_repo_description(github_repo, tagline):
            return FixOutcome(FixOutcome.FIXED, f"Updated description: {tagline}")
        return FixOutcome(FixOutcome.FAILED, "gh repo edit failed")
