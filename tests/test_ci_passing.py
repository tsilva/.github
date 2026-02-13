"""Tests for the CI_PASSING rule."""

from __future__ import annotations

from unittest.mock import patch

from tsilva_maintain.repo import Repo
from tsilva_maintain.rules import Status
from tsilva_maintain.rules.ci_passing import CiPassingRule


def _make_repo(tmp_path, *, has_ci_workflow=True, github_repo="tsilva/test"):
    """Create a minimal Repo with controllable cached properties."""
    repo = Repo(path=tmp_path)
    repo._cache["has_ci_workflow"] = has_ci_workflow
    repo._cache["github_repo"] = github_repo
    return repo


def test_pass_when_success(tmp_path):
    repo = _make_repo(tmp_path)
    rule = CiPassingRule()
    with patch("tsilva_maintain.rules.ci_passing.gh_authenticated", return_value=True), \
         patch("tsilva_maintain.rules.ci_passing.get_last_run_conclusion", return_value="success"):
        result = rule.check(repo)
    assert result.status == Status.PASS


def test_fail_when_failure(tmp_path):
    repo = _make_repo(tmp_path)
    rule = CiPassingRule()
    with patch("tsilva_maintain.rules.ci_passing.gh_authenticated", return_value=True), \
         patch("tsilva_maintain.rules.ci_passing.get_last_run_conclusion", return_value="failure"):
        result = rule.check(repo)
    assert result.status == Status.FAIL
    assert "failure" in result.message


def test_skip_when_gh_not_authenticated(tmp_path):
    repo = _make_repo(tmp_path)
    rule = CiPassingRule()
    with patch("tsilva_maintain.rules.ci_passing.gh_authenticated", return_value=False):
        result = rule.check(repo)
    assert result.status == Status.SKIP


def test_skip_when_no_completed_runs(tmp_path):
    repo = _make_repo(tmp_path)
    rule = CiPassingRule()
    with patch("tsilva_maintain.rules.ci_passing.gh_authenticated", return_value=True), \
         patch("tsilva_maintain.rules.ci_passing.get_last_run_conclusion", return_value=None):
        result = rule.check(repo)
    assert result.status == Status.SKIP
    assert "No completed CI runs" in result.message


def test_skip_when_no_ci_workflow(tmp_path):
    repo = _make_repo(tmp_path, has_ci_workflow=False)
    rule = CiPassingRule()
    assert not rule.applies_to(repo)


def test_skip_when_no_github_repo(tmp_path):
    repo = _make_repo(tmp_path, github_repo=None)
    rule = CiPassingRule()
    assert not rule.applies_to(repo)
