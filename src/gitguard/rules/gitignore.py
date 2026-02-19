"""Gitignore rules (existence and completeness)."""

from pathlib import Path

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status
from gitguard.rules._helpers import ESSENTIAL_GITIGNORE

MANAGED_START = "# >>> MANAGED BY GITGUARD - DO NOT EDIT THIS SECTION <<<"
MANAGED_END = "# >>> END MANAGED <<<"

# Load full rules from gitignore.global if available
_GITIGNORE_GLOBAL: list[str] | None = None


def _load_gitignore_global() -> list[str]:
    global _GITIGNORE_GLOBAL
    if _GITIGNORE_GLOBAL is not None:
        return _GITIGNORE_GLOBAL

    candidates = [
        Path(__file__).resolve().parents[3] / "gitignore.global",
    ]
    for p in candidates:
        if p.is_file():
            rules = []
            for line in p.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    rules.append(stripped)
            _GITIGNORE_GLOBAL = rules
            return rules

    _GITIGNORE_GLOBAL = []
    return []


def _parse_rules(content: str) -> list[str]:
    """Extract non-comment, non-blank rules from content."""
    rules = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            rules.append(stripped)
    return rules


def _build_content(rules: list[str]) -> str:
    """Build clean gitignore content: deduped, preserving order, no comments, no blank lines."""
    seen = set()
    unique = []
    for rule in rules:
        if rule not in seen:
            seen.add(rule)
            unique.append(rule)
    return "\n".join(unique) + "\n"


def _parse_sectioned(content: str) -> tuple[list[str] | None, list[str]]:
    """
    Parse a .gitignore file into managed and repo-specific sections.

    Returns (managed_rules, repo_lines) where:
    - managed_rules: None if no markers found (legacy format), else list of
      non-comment non-blank rules extracted from the managed section
    - repo_lines: raw lines after MANAGED_END (leading blank lines stripped),
      or all lines if no markers found
    """
    lines = content.splitlines()

    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == MANAGED_START:
            start_idx = i
        elif line.strip() == MANAGED_END:
            end_idx = i

    if start_idx is None or end_idx is None:
        return None, lines

    managed_rules = []
    for line in lines[start_idx + 1 : end_idx]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            managed_rules.append(stripped)

    # Lines after MANAGED_END, stripped of leading blank lines
    repo_lines = lines[end_idx + 1 :]
    first_nonblank = next(
        (i for i, l in enumerate(repo_lines) if l.strip()), len(repo_lines)
    )
    repo_lines = repo_lines[first_nonblank:]

    return managed_rules, repo_lines


def _build_sectioned_content(global_rules: list[str], repo_lines: list[str]) -> str:
    """
    Build .gitignore with a managed section at the top and repo-specific rules below.

    The managed section is delimited by MANAGED_START / MANAGED_END markers.
    repo_lines are appended as-is after a blank separator, with any lines that
    duplicate a managed rule silently dropped.
    """
    # Deduplicate global rules preserving order
    seen: set[str] = set()
    unique_global: list[str] = []
    for r in global_rules:
        if r not in seen:
            seen.add(r)
            unique_global.append(r)

    parts = [MANAGED_START, *unique_global, MANAGED_END]

    # Filter repo_lines: drop rule lines that duplicate managed rules; keep
    # comments and blank lines as-is so negation ordering is preserved.
    filtered: list[str] = []
    for line in repo_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            if stripped not in seen:
                filtered.append(line)
        else:
            filtered.append(line)

    if any(l.strip() for l in filtered):
        parts.append("")  # blank separator between sections
        parts.extend(filtered)

    return "\n".join(parts) + "\n"


class GitignoreRule(Rule):
    id = "GITIGNORE"
    name = ".gitignore must exist with essential patterns"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        gitignore = repo.path / ".gitignore"
        if not gitignore.is_file():
            return CheckResult(Status.FAIL, ".gitignore not found")

        content = gitignore.read_text(encoding="utf-8", errors="replace")
        global_rules = _load_gitignore_global()

        if not global_rules:
            # Fallback: check essential patterns are present
            content_lower = content.lower()
            missing = [
                p
                for p in ESSENTIAL_GITIGNORE
                if p.rstrip("/").lower() not in content_lower
            ]
            if missing:
                return CheckResult(
                    Status.FAIL, f"Missing {len(missing)} patterns: {' '.join(missing)}"
                )
            return CheckResult(Status.PASS)

        managed_rules, _ = _parse_sectioned(content)

        if managed_rules is None:
            # Legacy format: fail with migration needed message
            existing = set(_parse_rules(content))
            expected = set(global_rules)
            missing = sorted(expected - existing)
            parts = ["migration needed (no managed section)"]
            if missing:
                parts.append(f"also missing: {' '.join(missing)}")
            return CheckResult(Status.FAIL, "; ".join(parts))

        # Verify managed section matches global rules exactly (order and content)
        if managed_rules != global_rules:
            stale = sorted(set(managed_rules) - set(global_rules))
            added = sorted(set(global_rules) - set(managed_rules))
            parts = []
            if stale:
                parts.append(f"stale: {' '.join(stale)}")
            if added:
                parts.append(f"missing: {' '.join(added)}")
            if not stale and not added:
                parts.append("order mismatch")
            return CheckResult(
                Status.FAIL, f"Managed section out of sync ({'; '.join(parts)})"
            )

        return CheckResult(Status.PASS)

    def fix(self, repo, *, dry_run=False):
        gitignore = repo.path / ".gitignore"
        all_rules = _load_gitignore_global() or ESSENTIAL_GITIGNORE

        if not gitignore.is_file():
            if dry_run:
                return FixOutcome(
                    FixOutcome.FIXED, "Would create .gitignore with managed section"
                )
            try:
                new_content = _build_sectioned_content(all_rules, [])
                gitignore.write_text(new_content, encoding="utf-8")
                return FixOutcome(
                    FixOutcome.FIXED,
                    f"Created .gitignore ({len(all_rules)} managed patterns)",
                )
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))

        content = gitignore.read_text(encoding="utf-8", errors="replace")
        managed_rules, repo_lines = _parse_sectioned(content)

        if managed_rules is not None:
            # File already has markers: check if managed section is correct
            if managed_rules == all_rules:
                return FixOutcome(FixOutcome.ALREADY_OK)

            if dry_run:
                stale = set(managed_rules) - set(all_rules)
                new = set(all_rules) - set(managed_rules)
                parts = []
                if stale:
                    parts.append(f"remove {len(stale)} stale")
                if new:
                    parts.append(f"add {len(new)} new")
                label = ", ".join(parts) or "reorder"
                return FixOutcome(
                    FixOutcome.FIXED, f"Would update managed section ({label})"
                )

            new_content = _build_sectioned_content(all_rules, repo_lines)
            gitignore.write_text(new_content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Updated managed section")

        else:
            # Legacy format: migrate to sectioned format
            existing_rules = _parse_rules(content)
            all_rules_set = set(all_rules)
            repo_specific = [r for r in existing_rules if r not in all_rules_set]

            if dry_run:
                return FixOutcome(
                    FixOutcome.FIXED,
                    f"Would migrate to sectioned format ({len(repo_specific)} repo-specific rules preserved)",
                )

            new_repo_lines: list[str] = []
            if repo_specific:
                new_repo_lines = ["# Project-specific rules"] + repo_specific

            new_content = _build_sectioned_content(all_rules, new_repo_lines)
            gitignore.write_text(new_content, encoding="utf-8")
            return FixOutcome(
                FixOutcome.FIXED,
                f"Migrated to sectioned format ({len(repo_specific)} repo-specific rules preserved)",
            )
