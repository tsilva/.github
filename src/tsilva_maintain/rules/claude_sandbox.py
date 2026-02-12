"""Rule 5.2: Sandbox must be enabled."""

import json

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, FixType, Rule, Status


def _has_sandbox_enabled(repo_path) -> bool:
    for name in ("settings.json", "settings.local.json"):
        settings_file = repo_path / ".claude" / name
        if settings_file.is_file():
            try:
                data = json.loads(settings_file.read_text(encoding="utf-8"))
                sandbox = data.get("sandbox", {})
                if isinstance(sandbox, dict) and sandbox.get("enabled") is True:
                    return True
            except Exception:
                continue
    return False


class ClaudeSandboxRule(Rule):
    id = "CLAUDE_SANDBOX"
    name = "Sandbox must be enabled"
    category = Category.CLAUDE
    rule_number = "5.2"
    fix_type = FixType.AUTO

    def check(self, repo):
        if _has_sandbox_enabled(repo.path):
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Sandbox not enabled")

    def fix(self, repo, *, dry_run=False):
        if _has_sandbox_enabled(repo.path):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would enable sandbox")

        try:
            claude_dir = repo.path / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            settings_file = claude_dir / "settings.json"

            if settings_file.is_file():
                try:
                    data = json.loads(settings_file.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
                if "sandbox" not in data:
                    data["sandbox"] = {}
                data["sandbox"]["enabled"] = True
            else:
                data = {"sandbox": {"enabled": True}}

            settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Enabled sandbox")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))
