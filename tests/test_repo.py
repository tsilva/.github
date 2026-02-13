"""Tests for Repo dataclass."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from tsilva_maintain.repo import Repo, parse_github_remote


def test_discover_finds_repos(repos_dir):
    repos = Repo.discover(repos_dir)
    assert len(repos) == 1
    assert repos[0].name == "test-repo"


def test_discover_filter(repos_dir):
    assert len(Repo.discover(repos_dir, "test")) == 1
    assert len(Repo.discover(repos_dir, "nonexistent")) == 0


def test_discover_skips_non_git(tmp_path):
    (tmp_path / "not-a-repo").mkdir()
    assert len(Repo.discover(tmp_path)) == 0


def test_repo_name(tmp_repo):
    repo = Repo(path=tmp_repo)
    assert repo.name == "test-repo"


def test_repo_is_python_false(tmp_repo):
    repo = Repo(path=tmp_repo)
    assert repo.is_python is False


def test_repo_is_python_with_pyproject(tmp_repo):
    (tmp_repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
    repo = Repo(path=tmp_repo)
    assert repo.is_python is True


def test_repo_has_workflows_false(tmp_repo):
    repo = Repo(path=tmp_repo)
    # Our fixture creates .github/dependabot.yml but no workflows dir
    assert repo.has_workflows is False


def test_repo_has_workflows_true(tmp_repo):
    wf_dir = tmp_repo / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "ci.yml").write_text("on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n")
    repo = Repo(path=tmp_repo)
    assert repo.has_workflows is True


def test_parse_github_remote_https():
    assert parse_github_remote("https://github.com/tsilva/.github.git") == "tsilva/.github"
    assert parse_github_remote("https://github.com/owner/repo") == "owner/repo"


def test_parse_github_remote_ssh():
    assert parse_github_remote("git@github.com:tsilva/.github.git") == "tsilva/.github"
    assert parse_github_remote("git@github.com:owner/repo") == "owner/repo"


def test_parse_github_remote_invalid():
    assert parse_github_remote("not-a-url") is None
    assert parse_github_remote("https://gitlab.com/owner/repo") is None


def test_is_archived_no_remote(tmp_repo):
    repo = Repo(path=tmp_repo)
    assert repo.is_archived is False


def test_is_archived_gh_fails(tmp_repo):
    repo = Repo(path=tmp_repo)
    repo._cache["github_repo"] = "owner/repo"
    with patch("tsilva_maintain.repo.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        assert repo.is_archived is False


def test_is_archived_true(tmp_repo):
    repo = Repo(path=tmp_repo)
    repo._cache["github_repo"] = "owner/repo"
    with patch("tsilva_maintain.repo.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr="")
        assert repo.is_archived is True


def test_is_archived_gh_not_found(tmp_repo):
    repo = Repo(path=tmp_repo)
    repo._cache["github_repo"] = "owner/repo"
    with patch("tsilva_maintain.repo.subprocess.run", side_effect=FileNotFoundError):
        assert repo.is_archived is False


def test_discover_skip_archived(repos_dir):
    with patch.object(Repo, "is_archived", new_callable=lambda: property(lambda self: True)):
        assert len(Repo.discover(repos_dir)) == 0


def test_discover_skip_archived_false(repos_dir):
    with patch.object(Repo, "is_archived", new_callable=lambda: property(lambda self: True)):
        repos = Repo.discover(repos_dir, skip_archived=False)
        assert len(repos) == 1
