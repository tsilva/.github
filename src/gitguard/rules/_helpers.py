"""Shared helpers used by multiple rule modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

ESSENTIAL_GITIGNORE = [".env", ".DS_Store", "node_modules/", "__pycache__/", "*.pyc", ".venv/"]


def has_license_file(repo_path: Path) -> bool:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (repo_path / name).is_file():
            return True
    return False
