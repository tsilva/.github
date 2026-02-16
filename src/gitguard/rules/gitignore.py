"""Gitignore rules (existence and completeness)."""

from pathlib import Path

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status
from gitguard.rules._helpers import ESSENTIAL_GITIGNORE

_MANAGED_HEADER = "# Managed by tsilva/.github"
_MANAGED_SUBHEADER = "# Do not remove - synced automatically"

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


def _parse_managed_rules(content: str) -> list[str]:
    """Extract non-comment, non-blank rules from managed block(s)."""
    rules = []
    in_managed = False
    for line in content.splitlines():
        if line.strip() == _MANAGED_HEADER:
            in_managed = True
            continue
        if not in_managed:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rules.append(stripped)
    return rules


def _strip_managed_blocks(content: str) -> str:
    """Return content with all managed block(s) removed, trailing blank lines stripped."""
    lines = []
    in_managed = False
    for line in content.splitlines():
        if line.strip() == _MANAGED_HEADER:
            in_managed = True
            continue
        if in_managed:
            continue
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


def _build_managed_block(rules: list[str]) -> str:
    """Build a managed block string from rules."""
    return f"{_MANAGED_HEADER}\n{_MANAGED_SUBHEADER}\n" + "\n".join(rules) + "\n"


def _dedup_user_rules(user_content: str, managed_rules: list[str]) -> str:
    """Remove lines from user content that exactly match a managed rule.

    Keeps comments, blank lines, and rules not in the managed set.
    Collapses runs of 3+ consecutive blank lines down to 2.
    Strips trailing blank lines.
    """
    managed_set = {r.strip() for r in managed_rules}
    kept: list[str] = []
    for line in user_content.splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#") or stripped not in managed_set:
            kept.append(line)

    # Collapse runs of 3+ consecutive blank lines down to 2
    result: list[str] = []
    blank_count = 0
    for line in kept:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)

    # Strip trailing blank lines
    while result and not result[-1].strip():
        result.pop()

    return "\n".join(result) + "\n" if result else ""


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
            return CheckResult(Status.FAIL, f"Missing {len(missing)} patterns: {' '.join(missing)}")

        # Check managed block matches gitignore.global
        global_rules = _load_gitignore_global()
        if global_rules:
            managed = set(_parse_managed_rules(content))
            expected = set(global_rules)
            if managed != expected:
                stale = sorted(managed - expected)
                added = sorted(expected - managed)
                parts = []
                if stale:
                    parts.append(f"stale: {' '.join(stale)}")
                if added:
                    parts.append(f"missing: {' '.join(added)}")
                return CheckResult(Status.FAIL, f"Managed block out of sync ({'; '.join(parts)})")

        return CheckResult(Status.PASS)

    def fix(self, repo, *, dry_run=False):
        gitignore = repo.path / ".gitignore"
        all_rules = _load_gitignore_global() or ESSENTIAL_GITIGNORE
        managed_block = _build_managed_block(all_rules)

        if not gitignore.is_file():
            if dry_run:
                return FixOutcome(FixOutcome.FIXED, "Would create .gitignore with managed patterns")
            try:
                gitignore.write_text(managed_block, encoding="utf-8")
                return FixOutcome(FixOutcome.FIXED, f"Created .gitignore ({len(all_rules)} patterns)")
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))

        content = gitignore.read_text(encoding="utf-8", errors="replace")
        managed_rules = _parse_managed_rules(content)

        if set(managed_rules) == set(all_rules) and managed_rules:
            # Check if user section has duplicates that need cleaning
            repo_content = _strip_managed_blocks(content)
            deduped = _dedup_user_rules(repo_content, all_rules)
            if deduped == repo_content:
                return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            stale = set(managed_rules) - set(all_rules)
            new = set(all_rules) - set(managed_rules)
            parts = []
            if stale:
                parts.append(f"remove {len(stale)} stale")
            if new:
                parts.append(f"add {len(new)} new")
            if not managed_rules:
                parts.append(f"add {len(all_rules)} rules")
            return FixOutcome(FixOutcome.FIXED, f"Would sync managed block ({', '.join(parts)})")

        try:
            repo_content = _strip_managed_blocks(content)
            repo_content = _dedup_user_rules(repo_content, all_rules)
            if repo_content:
                new_content = repo_content + "\n" + managed_block
            else:
                new_content = managed_block
            gitignore.write_text(new_content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Synced managed gitignore block")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
