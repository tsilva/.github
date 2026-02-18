"""Report commands: taglines, tracked-ignored, and branches."""

from __future__ import annotations

import sys
from pathlib import Path

from gitguard import git, output
from gitguard.repo import Repo
from gitguard.tagline import extract_tagline


def run_report(report_type: str, repos_dir: Path, filter_pattern: str) -> int:
    if report_type == "taglines":
        return _report_taglines(repos_dir, filter_pattern)
    elif report_type == "tracked-ignored":
        return _report_tracked_ignored(repos_dir, filter_pattern)
    elif report_type == "branches":
        return _report_branches(repos_dir, filter_pattern)
    return 1


def _report_taglines(repos_dir: Path, filter_pattern: str) -> int:
    repos = Repo.discover(repos_dir, filter_pattern)
    if not repos:
        print("No git repositories found.", file=sys.stderr)
        return 0

    data = []
    max_name_width = 4  # "Repo"

    for repo in repos:
        readme = repo.path / "README.md"
        if readme.is_file():
            tagline = extract_tagline(str(readme))
            if not tagline:
                tagline = "(no tagline)"
        else:
            tagline = "(no README)"
        data.append((repo.name, tagline))
        max_name_width = max(max_name_width, len(repo.name))

    # Print header
    print(f"{output.BLUE}{'Repo':<{max_name_width}}{output.NC}   {output.BLUE}Tagline{output.NC}", file=sys.stderr)
    print("\u2500" * (max_name_width + 3 + 60), file=sys.stderr)

    with_tagline = 0
    without_tagline = 0

    for name, tagline in data:
        if tagline in ("(no tagline)", "(no README)"):
            print(f"{name:<{max_name_width}}   {output.DIM}{tagline}{output.NC}", file=sys.stderr)
            without_tagline += 1
        else:
            print(f"{output.GREEN}{name:<{max_name_width}}{output.NC}   {tagline}", file=sys.stderr)
            with_tagline += 1

    print("", file=sys.stderr)
    print(f"Summary: {with_tagline} with tagline, {without_tagline} without", file=sys.stderr)
    return 0


def _report_branches(repos_dir: Path, filter_pattern: str) -> int:
    repos = Repo.discover(repos_dir, filter_pattern)
    if not repos:
        print("No git repositories found.", file=sys.stderr)
        return 0

    output.info(f"Fetching {len(repos)} repos...")
    for repo in repos:
        git.fetch_all(repo.path)

    multi = 0
    single = 0

    for repo in repos:
        branches = git.local_branches(repo.path)
        if len(branches) < 2:
            single += 1
            continue
        multi += 1
        output.warn(f"{repo.name}: {len(branches)} branches")
        for b in branches:
            output.detail(f"  {b}")

    print("", file=sys.stderr)
    print(f"Summary: {multi} repos with multiple branches, {single} with single branch", file=sys.stderr)
    return 0


def _report_tracked_ignored(repos_dir: Path, filter_pattern: str) -> int:
    repos = Repo.discover(repos_dir, filter_pattern)
    if not repos:
        print("No git repositories found.", file=sys.stderr)
        return 0

    output.info(f"Checking for tracked files that should be ignored in: {repos_dir}")
    print("", file=sys.stderr)

    clean = 0
    warnings = 0

    for repo in repos:
        files = git.tracked_ignored_files(repo.path)
        if not files:
            output.success(f"{repo.name} (clean)")
            clean += 1
            continue

        output.warn(f"{repo.name}: {len(files)} tracked file(s) should be ignored")
        for f in files:
            output.detail(f"  {f}")
        warnings += 1

    print("", file=sys.stderr)
    print(f"Summary:", file=sys.stderr)
    print(f"  Clean:    {clean}", file=sys.stderr)
    print(f"  Warnings: {warnings}", file=sys.stderr)

    if warnings > 0:
        print("", file=sys.stderr)
        print("To fix tracked files that should be ignored, run in each repo:", file=sys.stderr)
        print('  git rm --cached <file>', file=sys.stderr)
        print('  git commit -m "Stop tracking ignored file"', file=sys.stderr)
        return 1
    return 0
