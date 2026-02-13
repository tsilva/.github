"""CI_PASSING — last CI run on default branch must pass."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tsilva_maintain.github import get_last_run_conclusion, gh_authenticated
from tsilva_maintain.rules import Category, CheckResult, Rule, Status

if TYPE_CHECKING:
    from tsilva_maintain.repo import Repo


class CiPassingRule(Rule):
    id = "CI_PASSING"
    name = "Last CI run on default branch must pass"
    category = Category.CICD

    def applies_to(self, repo: Repo) -> bool:
        return repo.has_ci_workflow and repo.github_repo is not None

    def check(self, repo: Repo) -> CheckResult:
        if not gh_authenticated():
            return CheckResult(Status.SKIP, "gh not authenticated")
        conclusion = get_last_run_conclusion(repo.github_repo)  # type: ignore[arg-type]
        if conclusion is None:
            return CheckResult(Status.SKIP, "No completed CI runs found")
        if conclusion == "success":
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, f"Last CI run: {conclusion}")
