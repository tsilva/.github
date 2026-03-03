"""Logo generation command — delegates to repologogen CLI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def run_logo(repo_path: Path, dry_run: bool = False) -> int:
    """Generate a logo by delegating to the repologogen CLI.

    Args:
        repo_path: Path to the repository
        dry_run: If True, only show what would be generated

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if not repo_path.is_dir():
        print(f"Error: Not a directory: {repo_path}", file=sys.stderr)
        return 1

    if not shutil.which("repologogen"):
        print("Error: repologogen is not installed.", file=sys.stderr)
        print(
            "\nInstall it with:  uv tool install repologogen --from /path/to/repologogen",
            file=sys.stderr,
        )
        return 1

    cmd = ["repologogen", str(repo_path)]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd)
    return result.returncode
