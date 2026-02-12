"""Claude Code settings rules (dangerous patterns, cleanliness)."""

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status
from tsilva_maintain.settings_optimizer import SettingsOptimizer


class SettingsDangerousRule(Rule):
    id = "SETTINGS_DANGEROUS"
    name = "No dangerous permission patterns"
    category = Category.CLAUDE
    rule_number = "5.3"
    fix_type = FixType.MANUAL

    def check(self, repo):
        settings_file = repo.path / ".claude" / "settings.local.json"
        if not settings_file.is_file():
            return CheckResult(Status.SKIP)

        optimizer = SettingsOptimizer(project_path=settings_file)
        if not optimizer.load_settings():
            return CheckResult(Status.SKIP)

        grouped = optimizer.analyze()
        if optimizer.check("dangerous", grouped):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Dangerous permission patterns detected")


class SettingsCleanRule(Rule):
    id = "SETTINGS_CLEAN"
    name = "Settings must be clean"
    category = Category.CLAUDE
    rule_number = "5.4"
    fix_type = FixType.AUTO

    def check(self, repo):
        settings_file = repo.path / ".claude" / "settings.local.json"
        if not settings_file.is_file():
            return CheckResult(Status.SKIP)

        optimizer = SettingsOptimizer(project_path=settings_file)
        if not optimizer.load_settings():
            return CheckResult(Status.SKIP)

        grouped = optimizer.analyze()
        if optimizer.check("clean", grouped):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Redundant permissions or unmigrated WebFetch domains")

    def fix(self, repo, *, dry_run=False):
        settings_file = repo.path / ".claude" / "settings.local.json"
        if not settings_file.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No settings.local.json")

        optimizer = SettingsOptimizer(project_path=settings_file)
        if not optimizer.load_settings():
            return FixOutcome(FixOutcome.SKIPPED, "No permissions found")

        grouped = optimizer.analyze()
        if optimizer.check("clean", grouped):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would optimize settings")

        if optimizer.auto_fix(grouped):
            return FixOutcome(FixOutcome.FIXED, "Optimized settings")
        return FixOutcome(FixOutcome.FAILED, "Failed to optimize settings")
