"""Rule enforcing CLAUDE.md should be a symlink to AGENTS.md."""

import os
from pathlib import Path

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status


class ClaudeMdSymlinkRule(Rule):
    id = "CLAUDE_MD_SYMLINK"
    name = "CLAUDE.md must be a symlink to AGENTS.md"
    category = Category.CLAUDE

    def check(self, repo):
        claude_path = repo.path / "CLAUDE.md"
        agents_path = repo.path / "AGENTS.md"

        claude_exists = claude_path.exists()
        agents_exists = agents_path.exists()

        # Neither exists - let CLAUDE_MD_EXISTS rule handle this
        if not claude_exists and not agents_exists:
            return CheckResult(Status.SKIP, "Neither CLAUDE.md nor AGENTS.md exists")

        # Both exist - check if CLAUDE.md is a symlink to AGENTS.md
        if claude_exists and agents_exists:
            if claude_path.is_symlink():
                try:
                    target = os.readlink(claude_path)
                    # Resolve relative to CLAUDE.md's directory
                    target_path = (claude_path.parent / target).resolve()
                    expected_path = agents_path.resolve()
                    if target_path == expected_path:
                        return CheckResult(Status.PASS)
                    else:
                        return CheckResult(
                            Status.FAIL,
                            f"CLAUDE.md is a symlink but points to {target}, not AGENTS.md",
                        )
                except OSError:
                    return CheckResult(
                        Status.FAIL, "CLAUDE.md is a symlink but target cannot be read"
                    )
            else:
                # Both exist as regular files - manual intervention needed
                return CheckResult(
                    Status.FAIL,
                    "Both CLAUDE.md and AGENTS.md exist as regular files. Manual merge required.",
                )

        # Only CLAUDE.md exists - needs migration
        if claude_exists and not agents_exists:
            if claude_path.is_symlink():
                return CheckResult(
                    Status.FAIL, "CLAUDE.md is a symlink but AGENTS.md does not exist"
                )
            return CheckResult(
                Status.FAIL,
                "CLAUDE.md exists but AGENTS.md does not. CLAUDE.md should be moved to AGENTS.md and symlinked.",
            )

        # Only AGENTS.md exists - needs symlink
        if not claude_exists and agents_exists:
            return CheckResult(
                Status.FAIL,
                "AGENTS.md exists but CLAUDE.md does not. CLAUDE.md should be a symlink to AGENTS.md.",
            )

        return CheckResult(Status.FAIL, "Unexpected state")

    def fix(self, repo, *, dry_run=False):
        claude_path = repo.path / "CLAUDE.md"
        agents_path = repo.path / "AGENTS.md"

        claude_exists = claude_path.exists()
        agents_exists = agents_path.exists()

        # Both exist as regular files - manual intervention needed
        if claude_exists and agents_exists and not claude_path.is_symlink():
            return FixOutcome(
                FixOutcome.MANUAL,
                "Both CLAUDE.md and AGENTS.md exist as regular files. Please manually merge them, keeping the content in AGENTS.md and making CLAUDE.md a symlink.",
            )

        # Only CLAUDE.md exists - move to AGENTS.md and create symlink
        if claude_exists and not agents_exists:
            if dry_run:
                return FixOutcome(
                    FixOutcome.FIXED,
                    "Would move CLAUDE.md to AGENTS.md and create CLAUDE.md as symlink",
                )

            try:
                # Read content before moving
                content = claude_path.read_text(encoding="utf-8")
                # Remove CLAUDE.md
                claude_path.unlink()
                # Create AGENTS.md with the content
                agents_path.write_text(content, encoding="utf-8")
                # Create CLAUDE.md as symlink to AGENTS.md
                claude_path.symlink_to("AGENTS.md")
                return FixOutcome(
                    FixOutcome.FIXED,
                    "Moved CLAUDE.md to AGENTS.md and created CLAUDE.md as symlink",
                )
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))

        # Only AGENTS.md exists - create symlink
        if not claude_exists and agents_exists:
            if dry_run:
                return FixOutcome(
                    FixOutcome.FIXED, "Would create CLAUDE.md as symlink to AGENTS.md"
                )

            try:
                claude_path.symlink_to("AGENTS.md")
                return FixOutcome(
                    FixOutcome.FIXED, "Created CLAUDE.md as symlink to AGENTS.md"
                )
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))

        # CLAUDE.md is symlink but AGENTS.md doesn't exist
        if claude_exists and claude_path.is_symlink() and not agents_exists:
            if dry_run:
                return FixOutcome(
                    FixOutcome.FIXED,
                    "Would remove broken CLAUDE.md symlink (AGENTS.md missing)",
                )

            try:
                claude_path.unlink()
                return FixOutcome(
                    FixOutcome.FIXED,
                    "Removed broken CLAUDE.md symlink (AGENTS.md was missing)",
                )
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))

        return FixOutcome(FixOutcome.MANUAL, "Unexpected state - manual review needed")
