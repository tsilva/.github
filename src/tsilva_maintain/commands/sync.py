"""Sync local clones with all non-archived repos in the tsilva GitHub org."""

from __future__ import annotations

import sys
from pathlib import Path

from tsilva_maintain import git, output
from tsilva_maintain.github import gh_authenticated, gh_available, list_org_repos


def run_sync(repos_dir: Path, filter_pattern: str, dry_run: bool) -> int:
    # Pre-flight: check gh available + authenticated
    if not gh_available():
        output.error("GitHub CLI (gh) is not installed.")
        return 1
    if not gh_authenticated():
        output.error("GitHub CLI is not authenticated. Run: gh auth login")
        return 1

    output.info(f"Syncing repos in: {repos_dir}")
    if dry_run:
        print(f"{output.YELLOW}DRY RUN MODE - no changes will be made{output.NC}", file=sys.stderr)
    print("", file=sys.stderr)

    # List all non-archived repos from GitHub
    output.step("Fetching repo list from GitHub...")
    all_repos = list_org_repos("tsilva")
    if not all_repos:
        output.error("Failed to list repos from GitHub (empty result).")
        return 1

    # Apply filter
    if filter_pattern:
        all_repos = [r for r in all_repos if filter_pattern in r]

    output.info(f"Found {len(all_repos)} repo(s) on GitHub")
    print("", file=sys.stderr)

    # Classify each repo
    to_clone: list[str] = []
    to_fetch: list[str] = []
    skipped: list[str] = []

    for name in all_repos:
        local = repos_dir / name
        if not local.exists():
            to_clone.append(name)
        elif (local / ".git").is_dir():
            to_fetch.append(name)
        else:
            skipped.append(name)

    output.info(f"To clone: {len(to_clone)}  |  To fetch: {len(to_fetch)}  |  Skipped: {len(skipped)}")
    print("", file=sys.stderr)

    errors = 0

    # Clone missing repos
    if to_clone:
        output.header(f"Cloning {len(to_clone)} repo(s)")
        for name in to_clone:
            target = repos_dir / name
            if dry_run:
                output.skip(f"{name} (would clone)")
                continue
            try:
                r = git.clone_repo(f"tsilva/{name}", target)
                if r.returncode == 0:
                    output.success(f"{name} (cloned)")
                else:
                    output.error(f"{name} (clone failed: {r.stderr.strip()})")
                    errors += 1
            except Exception as e:
                output.error(f"{name} (clone failed: {e})")
                errors += 1

    # Fetch existing repos
    if to_fetch:
        output.header(f"Fetching {len(to_fetch)} repo(s)")
        for name in to_fetch:
            repo_path = repos_dir / name
            if dry_run:
                output.skip(f"{name} (would fetch)")
                continue
            try:
                r = git.fetch_all(repo_path)
                if r.returncode == 0:
                    output.success(f"{name} (fetched)")
                else:
                    output.error(f"{name} (fetch failed: {r.stderr.strip()})")
                    errors += 1
            except Exception as e:
                output.error(f"{name} (fetch failed: {e})")
                errors += 1

    # Skipped dirs
    if skipped:
        print("", file=sys.stderr)
        for name in skipped:
            output.warn(f"{name} (exists but not a git repo, skipped)")

    # Summary
    print("", file=sys.stderr)
    print("Summary:", file=sys.stderr)
    print(f"  Cloned:  {len(to_clone)}", file=sys.stderr)
    print(f"  Fetched: {len(to_fetch)}", file=sys.stderr)
    print(f"  Skipped: {len(skipped)}", file=sys.stderr)
    print(f"  Errors:  {errors}", file=sys.stderr)

    return 1 if errors > 0 else 0
