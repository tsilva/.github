"""Thin subprocess wrappers for common git operations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Union


def run_git(repo_path: Path, *args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def status_porcelain(repo_path: Path) -> str:
    r = run_git(repo_path, "status", "--porcelain")
    return r.stdout.strip() if r.returncode == 0 else ""


def unpushed_commits(repo_path: Path) -> str:
    r = run_git(repo_path, "log", "@{u}..", "--oneline")
    return r.stdout.strip() if r.returncode == 0 else ""


def has_branch(repo_path: Path, branch: str) -> bool:
    r = run_git(repo_path, "rev-parse", "--verify", branch)
    return r.returncode == 0


def tracked_ignored_files(repo_path: Path) -> list[str]:
    r = run_git(repo_path, "ls-files", "-i", "-c", "--exclude-standard")
    if r.returncode != 0 or not r.stdout.strip():
        return []
    return r.stdout.strip().splitlines()


def merged_branches(repo_path: Path) -> list[str]:
    r = run_git(repo_path, "branch", "--merged", "main")
    if r.returncode != 0 or not r.stdout.strip():
        return []
    return [
        b.strip().lstrip("* ")
        for b in r.stdout.strip().splitlines()
        if b.strip().lstrip("* ") not in ("main", "master")
    ]


def branch_ages(repo_path: Path) -> list[tuple[str, int]]:
    """Return (branch_name, unix_epoch) for all local branches."""
    r = run_git(
        repo_path,
        "for-each-ref",
        "--format=%(refname:short) %(committerdate:unix)",
        "refs/heads/",
    )
    if r.returncode != 0 or not r.stdout.strip():
        return []
    result = []
    for line in r.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            result.append((parts[0], int(parts[1])))
    return result


def add_all(repo_path: Path) -> bool:
    return run_git(repo_path, "add", "-A").returncode == 0


def commit(repo_path: Path, message: str) -> bool:
    return run_git(repo_path, "commit", "-m", message).returncode == 0


def push(repo_path: Path) -> bool:
    return run_git(repo_path, "push", timeout=30).returncode == 0


def has_remote(repo_path: Path) -> bool:
    r = run_git(repo_path, "remote", "get-url", "origin")
    return r.returncode == 0


def diff_head(repo_path: Path, max_lines: int = 200, color: bool = False) -> str:
    args = ["diff", "HEAD"]
    if color:
        args.insert(1, "--color=always")
    r = run_git(repo_path, *args)
    if r.returncode != 0:
        return ""
    lines = r.stdout.splitlines()[:max_lines]
    return "\n".join(lines)


def untracked_files(repo_path: Path) -> str:
    r = run_git(repo_path, "ls-files", "--others", "--exclude-standard")
    return r.stdout.strip() if r.returncode == 0 else ""


def fetch_all(repo_path: Path) -> subprocess.CompletedProcess:
    return run_git(repo_path, "fetch", "--all", timeout=60)


def clone_repo(nwo: str, target_dir: Union[str, Path]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", "repo", "clone", nwo, str(target_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
