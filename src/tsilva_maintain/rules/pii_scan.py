"""Rule 6.1: PII scanning in CI."""

import re

from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class PiiScanRule(Rule):
    id = "PII_SCAN"
    name = "PII scanning in CI"
    category = Category.SECURITY
    rule_number = "6.1"
    fix_type = FixType.NONE

    def applies_to(self, repo):
        return repo.has_workflows

    def check(self, repo):
        if not repo.has_workflows:
            return CheckResult(Status.SKIP)

        wf_dir = repo.path / ".github" / "workflows"
        for wf_file in wf_dir.iterdir():
            if wf_file.suffix not in (".yml", ".yaml"):
                continue
            try:
                content = wf_file.read_text(encoding="utf-8", errors="replace")
                if re.search(r"pii-scan\.yml|release\.yml|gitleaks-action", content):
                    return CheckResult(Status.PASS)
            except Exception:
                continue

        return CheckResult(Status.FAIL, "No PII scanning in CI workflows")
