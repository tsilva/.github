"""Rule 7.3: Default branch must be 'main'."""

import subprocess

from gitguard.git import has_branch, run_git
from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status


class DefaultBranchRule(Rule):
    id = "DEFAULT_BRANCH"
    name = "Default branch must be 'main'"
    category = Category.GIT_HYGIENE

    def check(self, repo):
        if has_branch(repo.path, "main"):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "No 'main' branch found")

    def fix(self, repo, *, dry_run=False):
        if has_branch(repo.path, "main"):
            return FixOutcome(FixOutcome.ALREADY_OK)
        if not has_branch(repo.path, "master"):
            return FixOutcome(FixOutcome.SKIPPED, "No 'master' branch to rename")

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would rename master → main and update GitHub default branch")

        try:
            # Rename local branch master → main
            r = run_git(repo.path, "branch", "-m", "master", "main")
            if r.returncode != 0:
                return FixOutcome(FixOutcome.FAILED, f"Could not rename branch: {r.stderr.strip()}")

            # Push new main branch and set upstream
            r = run_git(repo.path, "push", "--set-upstream", "origin", "main", timeout=30)
            if r.returncode != 0:
                return FixOutcome(FixOutcome.FAILED, f"Could not push main: {r.stderr.strip()}")

            # Update GitHub default branch
            gh_repo = repo.github_repo
            if gh_repo:
                subprocess.run(
                    ["gh", "repo", "edit", gh_repo, "--default-branch", "main"],
                    capture_output=True, text=True, timeout=15,
                )
                # Delete remote master branch
                run_git(repo.path, "push", "origin", "--delete", "master", timeout=30)

            return FixOutcome(FixOutcome.FIXED, "Renamed master → main and updated GitHub default branch")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
