"""Tests for the WORKFLOWS_PASSING rule."""

from __future__ import annotations

from unittest.mock import patch

from gitguard.repo import Repo
from gitguard.rules import Status
from gitguard.rules.workflows_passing import WorkflowsPassingRule


def _make_repo(tmp_path, *, has_workflows=True, github_repo="tsilva/test"):
    """Create a minimal Repo with controllable cached properties."""
    repo = Repo(path=tmp_path)
    repo._cache["has_workflows"] = has_workflows
    repo._cache["github_repo"] = github_repo
    return repo


def test_pass_when_all_success(tmp_path):
    repo = _make_repo(tmp_path)
    rule = WorkflowsPassingRule()
    with patch("gitguard.rules.workflows_passing.gh_authenticated", return_value=True), \
         patch("gitguard.rules.workflows_passing.get_workflow_conclusions", return_value={"CI": "success", "Release": "success"}):
        result = rule.check(repo)
    assert result.status == Status.PASS


def test_fail_when_any_failure(tmp_path):
    repo = _make_repo(tmp_path)
    rule = WorkflowsPassingRule()
    with patch("gitguard.rules.workflows_passing.gh_authenticated", return_value=True), \
         patch("gitguard.rules.workflows_passing.get_workflow_conclusions", return_value={"CI": "failure"}):
        result = rule.check(repo)
    assert result.status == Status.FAIL
    assert "CI: failure" in result.message


def test_partial_failure(tmp_path):
    repo = _make_repo(tmp_path)
    rule = WorkflowsPassingRule()
    with patch("gitguard.rules.workflows_passing.gh_authenticated", return_value=True), \
         patch("gitguard.rules.workflows_passing.get_workflow_conclusions", return_value={"CI": "success", "PII Scan": "failure"}):
        result = rule.check(repo)
    assert result.status == Status.FAIL
    assert "PII Scan: failure" in result.message
    assert "CI" not in result.message


def test_skip_when_gh_not_authenticated(tmp_path):
    repo = _make_repo(tmp_path)
    rule = WorkflowsPassingRule()
    with patch("gitguard.rules.workflows_passing.gh_authenticated", return_value=False):
        result = rule.check(repo)
    assert result.status == Status.SKIP


def test_skip_when_no_completed_runs(tmp_path):
    repo = _make_repo(tmp_path)
    rule = WorkflowsPassingRule()
    with patch("gitguard.rules.workflows_passing.gh_authenticated", return_value=True), \
         patch("gitguard.rules.workflows_passing.get_workflow_conclusions", return_value={}):
        result = rule.check(repo)
    assert result.status == Status.SKIP
    assert "No completed workflow runs" in result.message


def test_skip_when_no_workflows(tmp_path):
    repo = _make_repo(tmp_path, has_workflows=False)
    rule = WorkflowsPassingRule()
    assert not rule.applies_to(repo)


def test_skip_when_no_github_repo(tmp_path):
    repo = _make_repo(tmp_path, github_repo=None)
    rule = WorkflowsPassingRule()
    assert not rule.applies_to(repo)
