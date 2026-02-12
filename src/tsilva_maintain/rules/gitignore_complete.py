"""Rule 1.10: .gitignore must include essential patterns."""

from pathlib import Path

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status

ESSENTIAL_GITIGNORE = [".env", ".DS_Store", "node_modules/", "__pycache__/", "*.pyc", ".venv/"]

# Load full rules from gitignore.global if available
_GITIGNORE_GLOBAL: list[str] | None = None


def _load_gitignore_global() -> list[str]:
    global _GITIGNORE_GLOBAL
    if _GITIGNORE_GLOBAL is not None:
        return _GITIGNORE_GLOBAL

    # Try to find gitignore.global relative to package
    candidates = [
        Path(__file__).resolve().parents[3] / "gitignore.global",  # src/tsilva_maintain/rules -> repo root
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


class GitignoreCompleteRule(Rule):
    id = "GITIGNORE_COMPLETE"
    name = ".gitignore must include essential patterns"
    category = Category.REPO_STRUCTURE
    rule_number = "1.10"
    fix_type = FixType.AUTO

    def check(self, repo):
        gitignore = repo.path / ".gitignore"
        if not gitignore.is_file():
            return CheckResult(Status.FAIL, ".gitignore does not exist")

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

        # Use the full gitignore.global rules if available, otherwise essential
        all_rules = _load_gitignore_global() or ESSENTIAL_GITIGNORE

        if not gitignore.is_file():
            # Delegate to gitignore_exists rule for creation
            return FixOutcome(FixOutcome.SKIPPED, ".gitignore does not exist")

        content = gitignore.read_text(encoding="utf-8", errors="replace")
        missing = []
        for rule in all_rules:
            # Check if rule is already present (exact line match)
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
