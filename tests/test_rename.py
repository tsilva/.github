"""Unit tests for gitguard rename command."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gitguard.commands.rename import (
    _apply_targeted_replacements,
    _find_targeted_replacements,
    _grep_remaining_references,
    _new_remote_url,
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
# _find_targeted_replacements
# ---------------------------------------------------------------------------

class TestFindTargetedReplacements:
    def test_finds_claude_md(self, tmp_path):
        repo = tmp_path / "my-repo"
        repo.mkdir()
        (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Project: my-repo\n")
        results = dict(_find_targeted_replacements(repo, "my-repo", "new-repo"))
        assert "CLAUDE.md" in results
        assert results["CLAUDE.md"] == 1

    def test_finds_readme(self, tmp_path):
        repo = tmp_path / "my-repo"
        repo.mkdir()
        content = (
            '[![badge](https://img.shields.io/badge/tsilva%2Fmy-repo-blue)]()\n'
            '[![CI](https://github.com/tsilva/my-repo/actions)]()\n'
            '![alt="my-repo"]()\n'
        )
        (repo / "README.md").write_text(content)
        results = dict(_find_targeted_replacements(repo, "my-repo", "new-repo"))
        assert "README.md" in results
        assert results["README.md"] >= 1

    def test_finds_pyproject_hyphen(self, tmp_path):
        repo = tmp_path / "my-repo"
        repo.mkdir()
        (repo / "pyproject.toml").write_text('[project]\nname = "my-repo"\nversion = "1.0"\n')
        results = dict(_find_targeted_replacements(repo, "my-repo", "new-repo"))
        assert "pyproject.toml" in results

    def test_finds_pyproject_underscore(self, tmp_path):
        repo = tmp_path / "my-repo"
        repo.mkdir()
        (repo / "pyproject.toml").write_text('[project]\nname = "my_repo"\nversion = "1.0"\n')
        results = dict(_find_targeted_replacements(repo, "my-repo", "new-repo"))
        assert "pyproject.toml" in results

    def test_skips_pyproject_different_name(self, tmp_path):
        repo = tmp_path / "my-repo"
        repo.mkdir()
        (repo / "pyproject.toml").write_text('[project]\nname = "completely-different"\nversion = "1.0"\n')
        results = dict(_find_targeted_replacements(repo, "my-repo", "new-repo"))
        assert "pyproject.toml" not in results

    def test_empty_repo(self, tmp_path):
        repo = tmp_path / "my-repo"
        repo.mkdir()
        results = _find_targeted_replacements(repo, "my-repo", "new-repo")
        assert results == []


# ---------------------------------------------------------------------------
# _apply_targeted_replacements
# ---------------------------------------------------------------------------

class TestApplyTargetedReplacements:
    def test_updates_claude_md(self, tmp_path):
        f = tmp_path / "CLAUDE.md"
        f.write_text("## Project: my-repo\n\nSome content.\n")
        _apply_targeted_replacements(f, "my-repo", "new-name")
        assert "## Project: new-name" in f.read_text()
        assert "my-repo" not in f.read_text()

    def test_updates_readme_github_url(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("See https://github.com/tsilva/my-repo for details.\n")
        _apply_targeted_replacements(f, "my-repo", "new-name")
        assert "tsilva/new-name" in f.read_text()
        assert "tsilva/my-repo" not in f.read_text()

    def test_updates_readme_percent_encoded(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("[![badge](https://codecov.io/gh/tsilva%2Fmy-repo)]()\n")
        _apply_targeted_replacements(f, "my-repo", "new-name")
        assert "tsilva%2Fnew-name" in f.read_text()

    def test_updates_readme_alt_text(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text('![logo](logo.png) alt="my-repo"\n')
        _apply_targeted_replacements(f, "my-repo", "new-name")
        assert 'alt="new-name"' in f.read_text()

    def test_updates_pyproject_name(self, tmp_path):
        f = tmp_path / "pyproject.toml"
        f.write_text('[project]\nname = "my-repo"\nversion = "1.0"\n')
        _apply_targeted_replacements(f, "my-repo", "new-name")
        content = f.read_text()
        assert 'name = "new-name"' in content

    def test_updates_pyproject_underscore_name(self, tmp_path):
        f = tmp_path / "pyproject.toml"
        f.write_text('[project]\nname = "my_repo"\nversion = "1.0"\n')
        _apply_targeted_replacements(f, "my-repo", "new-name")
        content = f.read_text()
        assert 'name = "new-name"' in content

    def test_nonexistent_file_no_error(self, tmp_path):
        # Should not raise
        _apply_targeted_replacements(tmp_path / "nonexistent.md", "old", "new")


# ---------------------------------------------------------------------------
# _grep_remaining_references
# ---------------------------------------------------------------------------

class TestGrepRemainingReferences:
    def test_finds_references_in_committed_files(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        # Add a file with a reference and commit it
        (repo / "docs.txt").write_text("See my-repo for more details.\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "add docs"], capture_output=True)
        results = _grep_remaining_references(repo, "my-repo")
        file_names = [f for f, _ in results]
        assert any("docs.txt" in f for f in file_names)

    def test_returns_empty_when_no_references(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        results = _grep_remaining_references(repo, "completely-unique-string-xyz-123")
        assert results == []

    def test_counts_occurrences(self, tmp_path):
        repo = _make_repo(tmp_path, "my-repo")
        (repo / "multi.txt").write_text("my-repo is great. Use my-repo now. my-repo!\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "multi"], capture_output=True)
        results = dict(_grep_remaining_references(repo, "my-repo"))
        assert results.get("multi.txt", 0) == 3


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
