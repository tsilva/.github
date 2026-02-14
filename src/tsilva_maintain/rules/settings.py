"""Claude Code settings rules (dangerous patterns, cleanliness)."""

import json

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, Rule, Status
from tsilva_maintain.settings_optimizer import SettingsOptimizer


def _check_settings(repo, mode, fail_message):
    settings_file = repo.path / ".claude" / "settings.local.json"
    if not settings_file.is_file():
        return CheckResult(Status.SKIP), None

    optimizer = SettingsOptimizer(project_path=settings_file)
    if not optimizer.load_settings():
        return CheckResult(Status.SKIP), None

    grouped = optimizer.analyze()
    if optimizer.check(mode, grouped):
        return CheckResult(Status.PASS), None
    return CheckResult(Status.FAIL, fail_message), (optimizer, grouped)


class SettingsDangerousRule(Rule):
    id = "SETTINGS_DANGEROUS"
    name = "No dangerous permission patterns"
    category = Category.CLAUDE

    def check(self, repo):
        result, _ = _check_settings(repo, "dangerous", "Dangerous permission patterns detected")
        return result

    def fix(self, repo, *, dry_run=False):
        settings_file = repo.path / ".claude" / "settings.local.json"
        if not settings_file.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No settings.local.json")

        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
        except Exception:
            return FixOutcome(FixOutcome.SKIPPED, "Cannot parse settings.local.json")

        allow = data.get("permissions", {}).get("allow", [])
        cleaned = [p for p in allow if p not in SettingsOptimizer.DANGEROUS_PATTERNS]

        if len(cleaned) == len(allow):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            removed = set(allow) - set(cleaned)
            return FixOutcome(FixOutcome.FIXED, f"Would remove: {', '.join(sorted(removed))}")

        data.setdefault("permissions", {})["allow"] = cleaned
        settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return FixOutcome(FixOutcome.FIXED, "Removed dangerous patterns")


class SettingsCleanRule(Rule):
    id = "SETTINGS_CLEAN"
    name = "Settings must be clean"
    category = Category.CLAUDE

    def check(self, repo):
        result, _ = _check_settings(repo, "clean", "Redundant permissions or unmigrated WebFetch domains")
        return result

    def fix(self, repo, *, dry_run=False):
        result, context = _check_settings(repo, "clean", "")
        if result.status == Status.SKIP:
            return FixOutcome(FixOutcome.SKIPPED, "No settings.local.json or no permissions")
        if result.status == Status.PASS:
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would optimize settings")

        optimizer, grouped = context
        if optimizer.auto_fix(grouped):
            return FixOutcome(FixOutcome.FIXED, "Optimized settings")
        return FixOutcome(FixOutcome.FAILED, "Failed to optimize settings")
