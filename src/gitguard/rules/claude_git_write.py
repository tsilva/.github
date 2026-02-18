"""Rule: no unattended git commit/push permissions in Claude settings."""

import json

from gitguard.rules import Category, CheckResult, FixOutcome, Rule, Status

_FLAGGED = {
    "Bash(git commit:*)",
    "Bash(git push:*)",
    "Bash(git:*)",
}


class ClaudeGitWriteRule(Rule):
    id = "CLAUDE_GIT_WRITE"
    name = "No unattended git commit/push"
    category = Category.CLAUDE

    def check(self, repo):
        settings_file = repo.path / ".claude" / "settings.local.json"
        if not settings_file.is_file():
            return CheckResult(Status.SKIP)

        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
        except Exception:
            return CheckResult(Status.SKIP)

        allow = data.get("permissions", {}).get("allow", [])
        offending = [p for p in allow if p in _FLAGGED]
        if not offending:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, f"Git write patterns allowed: {', '.join(sorted(offending))}")

    def fix(self, repo, *, dry_run=False):
        settings_file = repo.path / ".claude" / "settings.local.json"
        if not settings_file.is_file():
            return FixOutcome(FixOutcome.SKIPPED, "No settings.local.json")

        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
        except Exception:
            return FixOutcome(FixOutcome.SKIPPED, "Cannot parse settings.local.json")

        allow = data.get("permissions", {}).get("allow", [])
        cleaned = [p for p in allow if p not in _FLAGGED]

        if len(cleaned) == len(allow):
            return FixOutcome(FixOutcome.ALREADY_OK)

        if dry_run:
            removed = set(allow) - set(cleaned)
            return FixOutcome(FixOutcome.FIXED, f"Would remove: {', '.join(sorted(removed))}")

        data.setdefault("permissions", {})["allow"] = cleaned
        settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return FixOutcome(FixOutcome.FIXED, "Removed git write patterns")
