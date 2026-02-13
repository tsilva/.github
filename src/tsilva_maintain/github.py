"""GitHub CLI (gh) helpers."""

from __future__ import annotations

import shutil
import subprocess


def gh_available() -> bool:
    return shutil.which("gh") is not None


def gh_authenticated() -> bool:
    if not gh_available():
        return False
    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_repo_description(github_repo: str) -> str:
    try:
        r = subprocess.run(
            ["gh", "repo", "view", github_repo, "--json", "description", "-q", '.description // ""'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_last_run_conclusion(github_repo: str, branch: str = "main") -> str | None:
    """Return the conclusion of the latest workflow run on *branch*.

    Returns ``None`` if no completed runs exist, the run is still in
    progress, or the ``gh`` call fails.
    """
    try:
        r = subprocess.run(
            [
                "gh", "run", "list",
                "--repo", github_repo,
                "--branch", branch,
                "--limit", "1",
                "--json", "conclusion,status",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return None
        import json
        runs = json.loads(r.stdout)
        if not runs:
            return None
        run = runs[0]
        if run.get("status") != "completed":
            return None
        return run.get("conclusion") or None
    except (subprocess.TimeoutExpired, FileNotFoundError, (ValueError, KeyError)):
        return None


def set_repo_description(github_repo: str, description: str) -> bool:
    try:
        r = subprocess.run(
            ["gh", "repo", "edit", github_repo, "--description", description],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
