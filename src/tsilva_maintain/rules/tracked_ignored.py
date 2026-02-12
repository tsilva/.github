"""Rule 1.11: No tracked files matching gitignore."""

from tsilva_maintain.git import run_git, tracked_ignored_files
from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status


class TrackedIgnoredRule(Rule):
    id = "TRACKED_IGNORED"
    name = "No tracked files matching gitignore"
    category = Category.REPO_STRUCTURE
    rule_number = "1.11"
    fix_type = FixType.AUTO

    def check(self, repo):
        files = tracked_ignored_files(repo.path)
        if not files:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, f"{len(files)} tracked file(s) match gitignore")

    def fix(self, repo, *, dry_run=False):
        files = tracked_ignored_files(repo.path)
        if not files:
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, f"Would untrack {len(files)} file(s)")

        r = run_git(repo.path, "rm", "--cached", "--", *files)
        if r.returncode != 0:
            return FixOutcome(FixOutcome.FAILED, r.stderr.strip())
        return FixOutcome(FixOutcome.FIXED, f"Untracked {len(files)} file(s)")
