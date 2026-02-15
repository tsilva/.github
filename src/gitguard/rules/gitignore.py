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
            if repo_content:
                new_content = repo_content + "\n" + managed_block
            else:
                new_content = managed_block
            gitignore.write_text(new_content, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Synced managed gitignore block")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
