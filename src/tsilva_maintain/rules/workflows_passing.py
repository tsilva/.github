"""WORKFLOWS_PASSING — all workflow runs on default branch must pass."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tsilva_maintain.github import get_workflow_conclusions, gh_authenticated
from tsilva_maintain.rules import Category, CheckResult, Rule, Status

if TYPE_CHECKING:
    from tsilva_maintain.repo import Repo


class WorkflowsPassingRule(Rule):
    id = "WORKFLOWS_PASSING"
    name = "All workflow runs on default branch must pass"
    category = Category.CICD

    def applies_to(self, repo: Repo) -> bool:
        return repo.has_workflows and repo.github_repo is not None

    def check(self, repo: Repo) -> CheckResult:
        if not gh_authenticated():
            return CheckResult(Status.SKIP, "gh not authenticated")
        conclusions = repo._prefetch.get("workflow_conclusions")
        if conclusions is None:
            conclusions = get_workflow_conclusions(repo.github_repo)  # type: ignore[arg-type]
        if not conclusions:
            return CheckResult(Status.SKIP, "No completed workflow runs found")
        failed = {name: c for name, c in conclusions.items() if c != "success"}
        if not failed:
            return CheckResult(Status.PASS)
        details = ", ".join(f"{name}: {c}" for name, c in sorted(failed.items()))
        return CheckResult(Status.FAIL, details)
