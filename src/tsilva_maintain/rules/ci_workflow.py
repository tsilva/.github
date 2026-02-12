"""Rule 4.1: Python repos must have a CI workflow."""

import re

from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class CiWorkflowRule(Rule):
    id = "CI_WORKFLOW"
    name = "Python repos must have a CI workflow"
    category = Category.CICD
    rule_number = "4.1"
    fix_type = FixType.NONE

    def applies_to(self, repo):
        return repo.is_python

    def check(self, repo):
        if not repo.is_python:
            return CheckResult(Status.SKIP)

        wf_dir = repo.path / ".github" / "workflows"
        if not wf_dir.is_dir():
            return CheckResult(Status.FAIL, "No CI workflow referencing test.yml/release.yml/pytest")

        for wf_file in wf_dir.iterdir():
            if wf_file.suffix not in (".yml", ".yaml"):
                continue
            try:
                content = wf_file.read_text(encoding="utf-8", errors="replace")
                if re.search(r"tsilva/\.github/.*/(test|release|ci)\.yml|pytest", content):
                    return CheckResult(Status.PASS)
            except Exception:
                continue

        return CheckResult(Status.FAIL, "No CI workflow referencing test.yml/release.yml/pytest")
