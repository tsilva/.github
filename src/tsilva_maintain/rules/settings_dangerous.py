"""Rule 5.3: No dangerous permission patterns."""

from pathlib import Path

from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status
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
