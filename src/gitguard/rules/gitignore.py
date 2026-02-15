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


class GitignoreRule(Rule):
    id = "GITIGNORE"
    name = ".gitignore must exist with essential patterns"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        gitignore = repo.path / ".gitignore"
        if not gitignore.is_file():
            return CheckResult(Status.FAIL, ".gitignore not found")

        content_lower = gitignore.read_text(encoding="utf-8", errors="replace").lower()
        missing = []
        for pattern in ESSENTIAL_GITIGNORE:
            pattern_base = pattern.rstrip("/").lower()
            if pattern_base not in content_lower:
                missing.append(pattern)

        if not missing:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, f"Missing {len(missing)} patterns: {' '.join(missing)}")

    def fix(self, repo, *, dry_run=False):
        gitignore = repo.path / ".gitignore"
        all_rules = _load_gitignore_global() or ESSENTIAL_GITIGNORE

        if not gitignore.is_file():
            if dry_run:
                return FixOutcome(FixOutcome.FIXED, "Would create .gitignore with essential patterns")
            try:
                content = "# Managed by tsilva/.github\n# Do not remove - synced automatically\n"
                content += "\n".join(all_rules) + "\n"
                gitignore.write_text(content, encoding="utf-8")
                return FixOutcome(FixOutcome.FIXED, f"Created .gitignore ({len(all_rules)} patterns)")
            except Exception as e:
                return FixOutcome(FixOutcome.FAILED, str(e))

        content = gitignore.read_text(encoding="utf-8", errors="replace")
        missing = []
        for rule in all_rules:
            if rule not in content.splitlines():
                missing.append(rule)

        if not missing:
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, f"Would add {len(missing)} missing rules")

        try:
            append = ""
            if content and not content.endswith("\n"):
                append += "\n"
            append += "\n# Managed by tsilva/.github\n# Do not remove - synced automatically\n"
            for rule in missing:
                append += rule + "\n"

            with open(gitignore, "a", encoding="utf-8") as f:
                f.write(append)
            return FixOutcome(FixOutcome.FIXED, f"Added {len(missing)} rules")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
