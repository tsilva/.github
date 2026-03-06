"""Rule: archived repos must be stored under .archived/ folder."""

import shutil
from pathlib import Path

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status


class ArchivedLocationRule(Rule):
    id = "ARCHIVED_LOCATION"
    name = "Archived repos must be in .archived/ folder"
    category = Category.REPO_STRUCTURE
    archived_only = True

    def check(self, repo) -> CheckResult:
        parent = repo.path.parent.name
        if parent == ".archived":
            return CheckResult(Status.PASS)
        return CheckResult(
            Status.FAIL,
            f"Archived repo not in .archived/ folder (currently in: {repo.path.parent.name}/)",
        )

    def fix(self, repo, *, dry_run=False) -> FixOutcome:
        repos_dir = repo.path.parent
        archived_dir = repos_dir / ".archived"
        dest = archived_dir / repo.name

        if repo.path.parent.name == ".archived":
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, f"Would move {repo.name} to .archived/")

        try:
            archived_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(repo.path), str(dest))
            return FixOutcome(FixOutcome.FIXED, f"Moved {repo.name} to .archived/")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
