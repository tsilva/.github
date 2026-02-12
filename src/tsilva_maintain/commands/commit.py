"""Interactive AI-assisted commit & push for repos with uncommitted changes."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from tsilva_maintain import git, output
from tsilva_maintain.repo import Repo


def run_commit(repos_dir: Path, filter_pattern: str, dry_run: bool) -> int:
    repos = Repo.discover(repos_dir, filter_pattern)

    if not repos:
        output.info("No git repositories found.")
        return 0

    output.info(f"Scanning repos for uncommitted changes in: {repos_dir}")
    if dry_run:
        print(f"{output.YELLOW}DRY RUN MODE - no changes will be made{output.NC}", file=sys.stderr)
    print("", file=sys.stderr)

    # Phase 1: Find dirty repos
    dirty_repos = []
    no_changes = 0

    for repo in repos:
        status = git.status_porcelain(repo.path)
        if not status:
            output.success(f"{repo.name} (no changes)")
            no_changes += 1
            continue
        dirty_repos.append((repo, status))

    if not dirty_repos:
        output.info("No repos with uncommitted changes found.")
        return 0

    print("", file=sys.stderr)
    output.info(f"Found {len(dirty_repos)} repo(s) with uncommitted changes")

    # Phase 2: Generate AI commit messages
    has_claude = shutil.which("claude") is not None
    messages = []

    for repo, status in dirty_repos:
        if dry_run or not has_claude:
            messages.append("")
            continue

        diff = git.diff_head(repo.path, max_lines=200)
        untracked = git.untracked_files(repo.path)

        context = f"Changes:\n{diff}"
        if untracked:
            context += f"\n\nNew untracked files:\n{untracked}"

        try:
            r = subprocess.run(
                [
                    "claude", "-p",
                    "--model", "haiku",
                    "--max-budget-usd", "0.01",
                    "--no-session-persistence",
                    "Generate a concise git commit message (one line, no quotes, no prefix like 'feat:') for these changes. Only output the message, nothing else.",
                ],
                input=context,
                capture_output=True,
                text=True,
                timeout=30,
            )
            msg = r.stdout.strip().replace("\n", " ").strip()
        except Exception:
            msg = ""
        messages.append(msg)

    # Phase 3: Interactive approval
    approved = []
    skipped = 0

    if dry_run:
        for (repo, status), _ in zip(dirty_repos, messages):
            output.header(repo.name)
            print(status, file=sys.stderr)
            print("", file=sys.stderr)
            print(f"{output.DIM}(would generate AI message and prompt for approval){output.NC}", file=sys.stderr)
    else:
        for (repo, status), msg in zip(dirty_repos, messages):
            output.header(repo.name)
            print(status, file=sys.stderr)
            print("", file=sys.stderr)

            if msg:
                print(f"  Suggested: {output.BOLD}{msg}{output.NC}", file=sys.stderr)
                print("", file=sys.stderr)
                print("  [a]pprove / [e]dit / [s]kip? ", end="", file=sys.stderr, flush=True)
                try:
                    choice = input().strip().lower()
                except EOFError:
                    choice = "s"

                if choice == "a":
                    approved.append((repo, msg))
                elif choice == "e":
                    print("  Enter commit message: ", end="", file=sys.stderr, flush=True)
                    try:
                        custom = input().strip()
                    except EOFError:
                        custom = ""
                    if custom:
                        approved.append((repo, custom))
                    else:
                        output.skip(f"{repo.name} (empty message, skipping)")
                        skipped += 1
                else:
                    output.skip(f"{repo.name} (skipped)")
                    skipped += 1
            else:
                print(f"  {output.DIM}(no AI message available){output.NC}", file=sys.stderr)
                print("", file=sys.stderr)
                print("  [e]nter message / [s]kip? ", end="", file=sys.stderr, flush=True)
                try:
                    choice = input().strip().lower()
                except EOFError:
                    choice = "s"

                if choice == "e":
                    print("  Enter commit message: ", end="", file=sys.stderr, flush=True)
                    try:
                        custom = input().strip()
                    except EOFError:
                        custom = ""
                    if custom:
                        approved.append((repo, custom))
                    else:
                        output.skip(f"{repo.name} (empty message, skipping)")
                        skipped += 1
                else:
                    output.skip(f"{repo.name} (skipped)")
                    skipped += 1

    if not approved:
        print("", file=sys.stderr)
        output.info("No repos approved for commit.")
        return 0

    # Phase 4: Commit & push
    committed = 0
    pushed = 0
    failed = 0
    committed_repos = []

    print("", file=sys.stderr)
    output.header("Committing approved repos...")

    for repo, msg in approved:
        if git.add_all(repo.path) and git.commit(repo.path, msg):
            output.step(f"{repo.name} (committed)")
            committed += 1
            committed_repos.append(repo)
        else:
            output.error(f"{repo.name} (commit failed)")
            failed += 1

    print("", file=sys.stderr)
    output.header("Pushing committed repos...")

    for repo in committed_repos:
        if not git.has_remote(repo.path):
            output.warn(f"{repo.name} (no remote, skipping push)")
            continue

        if git.push(repo.path):
            output.success(f"{repo.name} (pushed)")
            pushed += 1
        else:
            output.error(f"{repo.name} (push failed)")
            failed += 1

    print("", file=sys.stderr)
    print(f"Summary:", file=sys.stderr)
    print(f"  Committed: {committed}", file=sys.stderr)
    print(f"  Pushed:    {pushed}", file=sys.stderr)
    print(f"  Skipped:   {skipped}", file=sys.stderr)
    print(f"  Failed:    {failed}", file=sys.stderr)

    return 1 if failed > 0 else 0
