"""Claude Code settings rules (dangerous patterns, cleanliness)."""

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
