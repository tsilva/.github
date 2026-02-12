"""Tests for Repo dataclass."""

from pathlib import Path

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
