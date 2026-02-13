"""Interactive AI-assisted commit & push for repos with uncommitted changes."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from tsilva_maintain import git, output
from tsilva_maintain.repo import Repo

OPENROUTER_BASE_URL = "http://127.0.0.1:8082/api"
OPENROUTER_MODEL = "anthropic/claude-opus-4.5"


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

    # Phase 2: Process each dirty repo one at a time
    committed = 0
    pushed = 0
    skipped = 0
    failed = 0

    for i, (repo, status) in enumerate(dirty_repos, 1):
        output.header(f"[{i}/{len(dirty_repos)}] {repo.name}")

        # Show the actual diff (colorized) and untracked file contents
        diff_colored = git.diff_head(repo.path, max_lines=200, color=True)
        diff_plain = git.diff_head(repo.path, max_lines=200)
        untracked = git.untracked_files(repo.path)

        if diff_colored:
            print(diff_colored, file=sys.stderr)
        if untracked:
            print(f"\n{output.BOLD}New untracked files:{output.NC}", file=sys.stderr)
            for uf in untracked.splitlines():
                print(f"  {output.GREEN}+ {uf}{output.NC}", file=sys.stderr)
        print("", file=sys.stderr)

        if dry_run:
            print(f"{output.DIM}(would generate AI message and prompt for approval){output.NC}", file=sys.stderr)
            continue

        # Generate AI commit message
        context = f"Changes:\n{diff_plain}"
        if untracked:
            context += f"\n\nNew untracked files:\n{untracked}"

        try:
            body = json.dumps({
                "model": OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Generate a concise git commit message (one line, no quotes, no prefix like 'feat:') for these changes. Only output the message, nothing else.",
                    },
                    {"role": "user", "content": context},
                ],
                "max_tokens": 100,
            }).encode()
            req = urllib.request.Request(
                f"{OPENROUTER_BASE_URL}/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            msg = data["choices"][0]["message"]["content"].strip().replace("\n", " ")
        except Exception:
            msg = ""

        # Prompt for approval
        if msg:
            print(f"  {output.CYAN}{repo.name}{output.NC} → {output.BOLD}{msg}{output.NC}", file=sys.stderr)
            print("", file=sys.stderr)
            print("  [a]pprove / [e]dit / [s]kip / [q]uit? ", end="", file=sys.stderr, flush=True)
        else:
            print(f"  {output.DIM}(no AI message available){output.NC}", file=sys.stderr)
            print("", file=sys.stderr)
            print("  [e]nter message / [s]kip / [q]uit? ", end="", file=sys.stderr, flush=True)

        try:
            choice = input().strip().lower()
        except EOFError:
            choice = "s"

        if choice == "q":
            output.info("Quitting early.")
            break

        final_msg = None
        if choice == "a" and msg:
            final_msg = msg
        elif choice == "e":
            print("  Enter commit message: ", end="", file=sys.stderr, flush=True)
            try:
                custom = input().strip()
            except EOFError:
                custom = ""
            if custom:
                final_msg = custom

        if final_msg is None:
            output.skip(f"{repo.name} (skipped)")
            skipped += 1
            continue

        # Commit & push immediately
        if git.add_all(repo.path) and git.commit(repo.path, final_msg):
            output.success(f"{repo.name} (committed)")
            committed += 1

            if git.has_remote(repo.path):
                if git.push(repo.path):
                    output.success(f"{repo.name} (pushed)")
                    pushed += 1
                else:
                    output.error(f"{repo.name} (push failed)")
                    failed += 1
            else:
                output.warn(f"{repo.name} (no remote, skipping push)")
        else:
            output.error(f"{repo.name} (commit failed)")
            failed += 1

    print("", file=sys.stderr)
    print(f"Summary:", file=sys.stderr)
    print(f"  Committed: {committed}", file=sys.stderr)
    print(f"  Pushed:    {pushed}", file=sys.stderr)
    print(f"  Skipped:   {skipped}", file=sys.stderr)
    print(f"  Failed:    {failed}", file=sys.stderr)

    return 1 if failed > 0 else 0
