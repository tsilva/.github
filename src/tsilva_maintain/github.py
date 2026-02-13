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


def get_workflow_conclusions(github_repo: str, branch: str = "main") -> dict[str, str]:
    """Return {workflow_name: conclusion} for latest completed run of each workflow."""
    try:
        r = subprocess.run(
            [
                "gh", "run", "list",
                "--repo", github_repo,
                "--branch", branch,
                "--limit", "50",
                "--json", "workflowName,conclusion,status",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return {}
        import json
        runs = json.loads(r.stdout)
        conclusions: dict[str, str] = {}
        for run in runs:
            name = run.get("workflowName")
            if not name or name in conclusions:
                continue
            if run.get("status") != "completed":
                continue
            conclusion = run.get("conclusion")
            if conclusion:
                conclusions[name] = conclusion
        return conclusions
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, KeyError):
        return {}


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
