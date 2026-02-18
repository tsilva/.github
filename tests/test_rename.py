"""Unit tests for gitguard rename command."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gitguard.commands.rename import (
    _global_search_replace,
    _is_binary_file,
    _new_remote_url,
    _python_package_name,
    _regenerate_lockfile,
    _rename_package_dir,
    _rename_workspace_file,
    _scan_cross_references,
    _validate,
    run_rename,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(parent: Path, name: str, remote: str | None = None) -> Path:
    """Create a minimal git repo with committed files."""
    repo = parent / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test.com"], capture_output=True, check=True)
    (repo / "README.md").write_text(
        f"# {name}\n"
        f'![{name}](https://img.shields.io/badge/{name}-blue)\n'
        f'[![CI](https://github.com/tsilva/{name}/actions/workflows/ci.yml/badge.svg)](https://github.com/tsilva/{name}/actions)\n'
        f'[![codecov](https://codecov.io/gh/tsilva%2F{name}/graph/badge.svg)](https://codecov.io/gh/tsilva/{name})\n'
    )
    (repo / "CLAUDE.md").write_text(f"# CLAUDE.md\n\n## Project: {name}\n\nSome content.\n")
    (repo / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], capture_output=True, check=True)
    if remote:
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], capture_output=True, check=True)
    return repo


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_same_name_fails(self, tmp_path):
        result = _validate("my-repo", "my-repo", tmp_path)
        assert result is not None
        assert "same" in result

    def test_missing_local_folder(self, tmp_path):
        result = _validate("old-repo", "new-repo", tmp_path)
        assert result is not None
        assert "not found" in result

    def test_non_git_dir_fails(self, tmp_path):
        (tmp_path / "old-repo").mkdir()
        result = _validate("old-repo", "new-repo", tmp_path)
        assert result is not None
        assert "git repository" in result

    def test_new_name_conflict(self, tmp_path):
        _make_repo(tmp_path, "old-repo")
        (tmp_path / "new-repo").mkdir()
        with patch("gitguard.github.gh_authenticated", return_value=True), \
             patch("gitguard.github.repo_exists", return_value=False):
            result = _validate("old-repo", "new-repo", tmp_path)
        assert result is not None
        assert "already exists" in result

    def test_gh_not_authenticated(self, tmp_path):
        _make_repo(tmp_path, "old-repo")
        with patch("gitguard.github.gh_authenticated", return_value=False):
            result = _validate("old-repo", "new-repo", tmp_path)
        assert result is not None
        assert "authenticated" in result

    def test_github_repo_not_found(self, tmp_path):
        _make_repo(tmp_path, "old-repo")
        with patch("gitguard.github.gh_authenticated", return_value=True), \
             patch("gitguard.github.repo_exists", side_effect=lambda nwo: False):
            result = _validate("old-repo", "new-repo", tmp_path)
        assert result is not None
        assert "GitHub repo not found" in result

    def test_new_github_repo_exists(self, tmp_path):
        _make_repo(tmp_path, "old-repo")
        def repo_exists(nwo):
            return nwo == "tsilva/old-repo" or nwo == "tsilva/new-repo"
        with patch("gitguard.github.gh_authenticated", return_value=True), \
             patch("gitguard.github.repo_exists", side_effect=repo_exists):
            result = _validate("old-repo", "new-repo", tmp_path)
        assert result is not None
        assert "already exists" in result

    def test_dirty_repo_fails(self, tmp_path):
        repo = _make_repo(tmp_path, "old-repo")
        (repo / "dirty.txt").write_text("uncommitted")
        def repo_exists(nwo):
            return nwo == "tsilva/old-repo"
        with patch("gitguard.github.gh_authenticated", return_value=True), \
             patch("gitguard.github.repo_exists", side_effect=repo_exists):
            result = _validate("old-repo", "new-repo", tmp_path)
        assert result is not None
        assert "uncommitted" in result

    def test_valid_passes(self, tmp_path):
        _make_repo(tmp_path, "old-repo")
        def repo_exists(nwo):
            return nwo == "tsilva/old-repo"
        with patch("gitguard.github.gh_authenticated", return_value=True), \
             patch("gitguard.github.repo_exists", side_effect=repo_exists):
            result = _validate("old-repo", "new-repo", tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# _new_remote_url
# ---------------------------------------------------------------------------

class TestNewRemoteUrl:
    def test_ssh_url(self):
        url = "git@github.com:tsilva/old-repo.git"
        result = _new_remote_url(url, "old-repo", "new-repo")
        assert result == "git@github.com:tsilva/new-repo.git"

    def test_https_url(self):
        url = "https://github.com/tsilva/old-repo"
        result = _new_remote_url(url, "old-repo", "new-repo")
        assert result == "https://github.com/tsilva/new-repo"

    def test_https_url_with_git_suffix(self):
        url = "https://github.com/tsilva/old-repo.git"
        result = _new_remote_url(url, "old-repo", "new-repo")
        assert result == "https://github.com/tsilva/new-repo"

    def test_unrecognized_url_unchanged(self):
        url = "https://gitlab.com/someone/old-repo.git"
        result = _new_remote_url(url, "old-repo", "new-repo")
        assert result == url  # no substitution


# ---------------------------------------------------------------------------
# _python_package_name
# ---------------------------------------------------------------------------

class TestPythonPackageName:
    def test_hyphenated(self):
        assert _python_package_name("my-repo") == "my_repo"

    def test_no_hyphens(self):
        assert _python_package_name("myrepo") == "myrepo"

    def test_multiple_hyphens(self):
        assert _python_package_name("my-long-repo-name") == "my_long_repo_name"


# ---------------------------------------------------------------------------
# _is_binary_file
# ---------------------------------------------------------------------------

class TestIsBinaryFile:
    def test_text_file(self, tmp_path):
        f = tmp_path / "text.txt"
        f.write_text("Hello, world!\n")
        assert _is_binary_file(f) is False

    def test_binary_file(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"hello\x00world")
        assert _is_binary_file(f) is True

    def test_missing_file(self, tmp_path):
        f = tmp_path / "nonexistent.txt"
        assert _is_binary_file(f) is True


# ---------------------------------------------------------------------------
# _rename_package_dir
# ---------------------------------------------------------------------------

class TestRenamePackageDir:
    def test_root_dir(self, tmp_path):
        pkg = tmp_path / "my_repo"
        pkg.mkdir()
        result = _rename_package_dir(tmp_path, "my-repo", "new-name", dry_run=False)
        assert result is True
        assert (tmp_path / "new_name").is_dir()
        assert not pkg.exists()

    def test_src_layout(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        pkg = src / "my_repo"
        pkg.mkdir()
        result = _rename_package_dir(tmp_path, "my-repo", "new-name", dry_run=False)
        assert result is True
        assert (src / "new_name").is_dir()
        assert not pkg.exists()

    def test_missing_dir(self, tmp_path):
        result = _rename_package_dir(tmp_path, "my-repo", "new-name", dry_run=False)
        assert result is False

    def test_same_package_name(self, tmp_path):
        # When hyphens are the only difference and both map to same pkg name
        pkg = tmp_path / "myrepo"
        pkg.mkdir()
        # old_name "myrepo" and new_name "myrepo" same pkg name → skip
        result = _rename_package_dir(tmp_path, "myrepo", "myrepo", dry_run=False)
        assert result is False

    def test_dry_run(self, tmp_path):
        pkg = tmp_path / "my_repo"
        pkg.mkdir()
        result = _rename_package_dir(tmp_path, "my-repo", "new-name", dry_run=True)
        assert result is True
        # Directory should NOT be renamed in dry-run
        assert pkg.exists()
        assert not (tmp_path / "new_name").exists()


# ---------------------------------------------------------------------------
# _rename_workspace_file
# ---------------------------------------------------------------------------

class TestRenameWorkspaceFile:
    def test_found(self, tmp_path):
        ws = tmp_path / "my-repo.code-workspace"
        ws.write_text("{}")
        result = _rename_workspace_file(tmp_path, "my-repo", "new-name", dry_run=False)
        assert result is True
        assert (tmp_path / "new-name.code-workspace").is_file()
        assert not ws.exists()

    def test_missing(self, tmp_path):
        result = _rename_workspace_file(tmp_path, "my-repo", "new-name", dry_run=False)
        assert result is False

    def test_dry_run(self, tmp_path):
        ws = tmp_path / "my-repo.code-workspace"
        ws.write_text("{}")
        result = _rename_workspace_file(tmp_path, "my-repo", "new-name", dry_run=True)
        assert result is True
        # File should NOT be renamed in dry-run
        assert ws.exists()
        assert not (tmp_path / "new-name.code-workspace").exists()


# ---------------------------------------------------------------------------
# _global_search_replace
# ---------------------------------------------------------------------------

class TestGlobalSearchReplace:
    def test_replaces_both_patterns(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        # Add a file with both hyphenated and underscore forms
        f = repo / "config.txt"
        f.write_text("Repo: my-repo, pkg: my_repo\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "add config"], capture_output=True)

        modified = _global_search_replace(repo, "my-repo", "new-name", dry_run=False)
        file_names = [r for r, _ in modified]
        assert "config.txt" in file_names
        assert "new-name" in f.read_text()
        assert "new_name" in f.read_text()

    def test_skips_uv_lock(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        lockfile = repo / "uv.lock"
        lockfile.write_text("# my-repo reference\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "add lock"], capture_output=True)

        modified = _global_search_replace(repo, "my-repo", "new-name", dry_run=False)
        file_names = [r for r, _ in modified]
        assert "uv.lock" not in file_names
        # Lock file content should be unchanged
        assert "my-repo" in lockfile.read_text()

    def test_skips_binary(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        binfile = repo / "logo.png"
        binfile.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00my-repo\x00")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "add binary"], capture_output=True)

        modified = _global_search_replace(repo, "my-repo", "new-name", dry_run=False)
        file_names = [r for r, _ in modified]
        assert "logo.png" not in file_names

    def test_dry_run(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        f = repo / "info.txt"
        f.write_text("my-repo is great\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "add info"], capture_output=True)

        modified = _global_search_replace(repo, "my-repo", "new-name", dry_run=True)
        file_names = [r for r, _ in modified]
        assert "info.txt" in file_names
        # File should NOT be modified in dry-run
        assert "my-repo" in f.read_text()

    def test_no_references(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        modified = _global_search_replace(repo, "completely-unique-xyz-999", "new-name", dry_run=False)
        assert modified == []


# ---------------------------------------------------------------------------
# _regenerate_lockfile
# ---------------------------------------------------------------------------

class TestRegenerateLockfile:
    def test_no_pyproject(self, tmp_path):
        result = _regenerate_lockfile(tmp_path, dry_run=False)
        assert result is False

    def test_dry_run_with_lockfile(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = _regenerate_lockfile(tmp_path, dry_run=True)
        assert result is True
        # Lock file should still exist (dry-run)
        assert (tmp_path / "uv.lock").is_file()

    def test_mock_uv_lock(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        old_lock = tmp_path / "uv.lock"
        old_lock.write_text("# old lock\n")

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = _regenerate_lockfile(tmp_path, dry_run=False)

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["uv", "lock"]
        # Old lock file should have been deleted before calling uv lock
        # (can't check this directly, but we verify the call happened)


# ---------------------------------------------------------------------------
# _scan_cross_references
# ---------------------------------------------------------------------------

class TestScanCrossReferences:
    def test_finds_sibling_references(self, tmp_path):
        _make_repo(tmp_path, "my-repo")
        sibling = _make_repo(tmp_path, "other-repo")
        # Add a reference in sibling
        (sibling / "ref.txt").write_text("We depend on my-repo.\n")
        subprocess.run(["git", "-C", str(sibling), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(sibling), "commit", "-m", "add ref"], capture_output=True)

        results = _scan_cross_references(tmp_path, "my-repo", skip_repo="my-repo")
        assert "other-repo" in results
        assert any("ref.txt" in f for f in results["other-repo"])

    def test_skips_renamed_repo(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        # Repo references itself — but we skip it
        (repo / "self.txt").write_text("my-repo self reference\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "self"], capture_output=True)

        results = _scan_cross_references(tmp_path, "my-repo", skip_repo="my-repo")
        assert "my-repo" not in results

    def test_returns_empty_when_no_references(self, tmp_path):
        _make_repo(tmp_path, "my-repo")
        _make_repo(tmp_path, "other-repo")
        results = _scan_cross_references(tmp_path, "completely-unique-xyz-999", skip_repo="my-repo")
        assert results == {}


# ---------------------------------------------------------------------------
# run_rename (dry-run integration)
# ---------------------------------------------------------------------------

class TestRunRenameDryRun:
    def test_dry_run_validates_and_exits_cleanly(self, tmp_path):
        _make_repo(tmp_path, "old-repo")

        def repo_exists(nwo):
            return nwo == "tsilva/old-repo"

        with patch("gitguard.github.gh_authenticated", return_value=True), \
             patch("gitguard.github.repo_exists", side_effect=repo_exists), \
             patch("gitguard.github.rename_repo", return_value=True), \
             patch("gitguard.git.get_remote_url", return_value="git@github.com:tsilva/old-repo.git"):
            result = run_rename("old-repo", "new-repo", tmp_path, dry_run=True)

        assert result == 0

    def test_dry_run_does_not_rename_folder(self, tmp_path):
        _make_repo(tmp_path, "old-repo")

        def repo_exists(nwo):
            return nwo == "tsilva/old-repo"

        with patch("gitguard.github.gh_authenticated", return_value=True), \
             patch("gitguard.github.repo_exists", side_effect=repo_exists), \
             patch("gitguard.github.rename_repo", return_value=True), \
             patch("gitguard.git.get_remote_url", return_value="git@github.com:tsilva/old-repo.git"):
            run_rename("old-repo", "new-repo", tmp_path, dry_run=True)

        assert (tmp_path / "old-repo").exists()
        assert not (tmp_path / "new-repo").exists()

    def test_validation_failure_returns_1(self, tmp_path):
        result = run_rename("nonexistent", "new-repo", tmp_path, dry_run=True)
        assert result == 1
