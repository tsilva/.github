"""Config-driven workflow search rules (CI, Release, PII scan)."""

import re

from tsilva_maintain.rules import Category, CheckResult, Rule, Status


class _WorkflowSearchBase(Rule):
    """Search .github/workflows/*.yml for a regex pattern. No id — skipped by registry."""

    _pattern: str
    _fail_message: str

    def applies_to(self, repo):
        check = getattr(self, "_applies_check", None)
        if check:
            return check(repo)
        return True

    def check(self, repo):
        wf_dir = repo.path / ".github" / "workflows"
        if not wf_dir.is_dir():
            return CheckResult(Status.FAIL, self._fail_message)

        for wf_file in wf_dir.iterdir():
            if wf_file.suffix not in (".yml", ".yaml"):
                continue
            try:
                content = wf_file.read_text(encoding="utf-8", errors="replace")
                if re.search(self._pattern, content):
                    return CheckResult(Status.PASS)
            except Exception:
                continue

        return CheckResult(Status.FAIL, self._fail_message)


def _make(*, id, name, category, pattern, fail_message, applies_check=None):
    attrs = {
        "id": id,
        "name": name,
        "category": category,
        "_pattern": pattern,
        "_fail_message": fail_message,
    }
    if applies_check:
        attrs["_applies_check"] = staticmethod(applies_check)
    return type(id.title().replace("_", "") + "Rule", (_WorkflowSearchBase,), attrs)


CiWorkflowRule = _make(
    id="CI_WORKFLOW",
    name="Python repos must have a CI workflow",
    category=Category.CICD,
    pattern=r"tsilva/\.github/.*/(test|release|ci)\.yml|pytest",
    fail_message="No CI workflow referencing test.yml/release.yml/pytest",
    applies_check=lambda r: r.is_python,
)

ReleaseWorkflowRule = _make(
    id="RELEASE_WORKFLOW",
    name="Release workflow for versioned projects",
    category=Category.CICD,
    pattern=r"tsilva/\.github/.*/(release|publish-pypi)\.yml",
    fail_message="Versioned project missing release workflow",
    applies_check=lambda r: r.has_pyproject and r.has_version,
)

PiiScanRule = _make(
    id="PII_SCAN",
    name="PII scanning in CI",
    category=Category.SECURITY,
    pattern=r"pii-scan\.yml|release\.yml|gitleaks-action",
    fail_message="No PII scanning in CI workflows",
    applies_check=lambda r: r.has_workflows,
)
