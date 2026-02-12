"""Rule 4.2: Release workflow for versioned projects."""

import re

from tsilva_maintain.rules import Category, CheckResult, FixType, Rule, Status


class ReleaseWorkflowRule(Rule):
    id = "RELEASE_WORKFLOW"
    name = "Release workflow for versioned projects"
    category = Category.CICD
    rule_number = "4.2"
    fix_type = FixType.NONE

    def applies_to(self, repo):
        return repo.has_pyproject and repo.has_version

    def check(self, repo):
        if not repo.has_pyproject:
            return CheckResult(Status.SKIP)
        if not repo.has_version:
            return CheckResult(Status.SKIP)

        wf_dir = repo.path / ".github" / "workflows"
        if not wf_dir.is_dir():
            return CheckResult(Status.FAIL, "Versioned project missing release workflow")

        for wf_file in wf_dir.iterdir():
            if wf_file.suffix not in (".yml", ".yaml"):
                continue
            try:
                content = wf_file.read_text(encoding="utf-8", errors="replace")
                if re.search(r"tsilva/\.github/.*/(release|publish-pypi)\.yml", content):
                    return CheckResult(Status.PASS)
            except Exception:
                continue

        return CheckResult(Status.FAIL, "Versioned project missing release workflow")
