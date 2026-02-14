"""Shared fixtures for tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with common files for testing."""
    repo = tmp_path / "test-repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test.com"], capture_output=True, check=True)

    # Create basic files
    (repo / "README.md").write_text(
        "# test-repo\n\nA test repository for unit testing.\n\n## Installation\n\nRun `pip install test-repo`.\n\n## Usage\n\nJust use it.\n\n## License\n\nMIT\n"
    )
    (repo / ".gitignore").write_text(".env\n.DS_Store\nnode_modules/\n__pycache__/\n*.pyc\n.venv/\n")
    (repo / "LICENSE").write_text("MIT License\n\nCopyright (c) 2024 Test\n")
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Project: test-repo\n")
    (repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header

    # Create .claude/settings.local.json with sandbox
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.local.json").write_text('{\n  "sandbox": {\n    "enabled": true\n  },\n  "permissions": {\n    "allow": [],\n    "deny": []\n  }\n}\n')

    # Create .github/dependabot.yml
    gh_dir = repo / ".github"
    gh_dir.mkdir()
    (gh_dir / "dependabot.yml").write_text("version: 2\nupdates:\n  - package-ecosystem: github-actions\n    directory: /\n    schedule:\n      interval: weekly\n")

    # Create pre-commit config
    (repo / ".pre-commit-config.yaml").write_text("repos:\n  - repo: https://github.com/tsilva/.github\n    rev: main\n    hooks:\n      - id: gitleaks\n")

    # Commit everything
    subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], capture_output=True, check=True)

    return repo


@pytest.fixture
def repos_dir(tmp_repo: Path) -> Path:
    """Return the parent directory containing the test repo."""
    return tmp_repo.parent


@pytest.fixture
def bare_repo(tmp_path: Path) -> Path:
    """Create a bare-minimum git repo (no files except .git)."""
    repo = tmp_path / "bare-repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test.com"], capture_output=True, check=True)
    # Need at least one commit for 'main' branch to exist
    (repo / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], capture_output=True, check=True)
    return repo
