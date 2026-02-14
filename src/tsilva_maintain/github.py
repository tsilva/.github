"""GitHub CLI (gh) helpers."""

from __future__ import annotations

import json
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


def list_org_repos(org: str) -> list[str]:
    """Return sorted list of non-archived repo names for the given GitHub org."""
    try:
        r = subprocess.run(
            ["gh", "repo", "list", org, "--no-archived", "--json", "name", "--limit", "1000"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return []
        repos = json.loads(r.stdout)
        return sorted(repo["name"] for repo in repos)
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, KeyError):
        return []


def fetch_org_repo_metadata(org: str) -> dict[str, str]:
    """Return {repo_name: description} for non-archived repos via a single GraphQL call.

    Uses repositoryOwner to work for both user and organization accounts.
    """
    query = """
query($owner: String!, $cursor: String) {
  repositoryOwner(login: $owner) {
    repositories(first: 100, after: $cursor, ownerAffiliations: [OWNER], orderBy: {field: NAME, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes { name description isArchived }
    }
  }
}"""
    result: dict[str, str] = {}
    cursor = None
    try:
        while True:
            cmd = [
                "gh", "api", "graphql",
                "-f", f"query={query}",
                "-f", f"owner={org}",
            ]
            if cursor:
                cmd.extend(["-f", f"cursor={cursor}"])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return result or {}
            data = json.loads(r.stdout)
            repos_data = data["data"]["repositoryOwner"]["repositories"]
            for node in repos_data["nodes"]:
                if node.get("isArchived"):
                    continue
                result[node["name"]] = node.get("description") or ""
            page_info = repos_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, KeyError):
        pass
    return result


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
