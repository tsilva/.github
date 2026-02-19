"""Gitignore rules (existence and completeness)."""

from pathlib import Path

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status
from gitguard.rules._helpers import ESSENTIAL_GITIGNORE

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
    """Build clean gitignore content: deduped, sorted, no comments, no blank lines."""
    # Deduplicate while preserving order for consistent output
    seen = set()
    unique = []
    for rule in rules:
        if rule not in seen:
            seen.add(rule)
            unique.append(rule)
    # Sort alphabetically for consistency
    unique.sort(key=lambda x: x.lower())
    return "\n".join(unique) + "\n"


class GitignoreRule(Rule):
    id = "GITIGNORE"
    name = ".gitignore must exist with essential patterns"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        gitignore = repo.path / ".gitignore"
        if not gitignore.is_file():
            return CheckResult(Status.FAIL, ".gitignore not found")

        content = gitignore.read_text(encoding="utf-8", errors="replace")
        content_lower = content.lower()

        # Check essential patterns are present
        missing = []
        for pattern in ESSENTIAL_GITIGNORE:
            if pattern.rstrip("/").lower() not in content_lower:
                missing.append(pattern)
        if missing:
            return CheckResult(
                Status.FAIL, f"Missing {len(missing)} patterns: {' '.join(missing)}"
            )

        # Check all expected rules are present (from gitignore.global)
        global_rules = _load_gitignore_global()
        if global_rules:
            existing = set(_parse_rules(content))
            expected = set(global_rules)
            if existing != expected:
                stale = sorted(existing - expected)
                added = sorted(expected - existing)
                parts = []
                if stale:
                    parts.append(f"stale: {' '.join(stale)}")
                if added:
                    parts.append(f"missing: {' '.join(added)}")
                return CheckResult(
                    Status.FAIL, f"Rules out of sync ({'; '.join(parts)})"
                )

        return CheckResult(Status.PASS)

    def fix(self, repo, *, dry_run=False):
        gitignore = repo.path / ".gitignore"
        all_rules = _load_gitignore_global() or ESSENTIAL_GITIGNORE

        if not gitignore.is_file():
            if dry_run:
                return FixOutcome(
                    FixOutcome.FIXED, "Would create .gitignore with managed patterns"
                )
            try:
                new_content = _build_content(all_rules)
                gitignore.write_text(new_content, encoding="utf-8")
                return FixOutcome(
                    FixOutcome.FIXED, f"Created .gitignore ({len(all_rules)} patterns)"
                )
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))

        content = gitignore.read_text(encoding="utf-8", errors="replace")
        existing_rules = _parse_rules(content)

        # Combine existing and expected rules, then dedupe and sort
        combined = existing_rules + [r for r in all_rules if r not in existing_rules]
        new_content = _build_content(combined)

        # Check if content would change
        if _build_content(existing_rules) == new_content and set(existing_rules) == set(
            all_rules
        ):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            stale = set(existing_rules) - set(all_rules)
            new = set(all_rules) - set(existing_rules)
            parts = []
            if stale:
                parts.append(f"remove {len(stale)} stale")
            if new:
                parts.append(f"add {len(new)} new")
            return FixOutcome(
                FixOutcome.FIXED, f"Would sync gitignore ({', '.join(parts)})"
            )

        try:
            gitignore.write_text(new_content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Synced gitignore (deduped, sorted)")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
