"""Tests for individual rules."""

import json
import subprocess
from pathlib import Path

from tsilva_maintain.repo import Repo
from tsilva_maintain.rules import Status
from tsilva_maintain.rules._registry import discover_rules


def test_all_rules_discovered():
    rules = discover_rules()
    rule_ids = {r.id for r in rules}
    expected = {
        "DEFAULT_BRANCH", "README_EXISTS", "README_CURRENT", "README_LICENSE",
        "README_LOGO", "LOGO_EXISTS", "LICENSE_EXISTS", "GITIGNORE",
        "CLAUDE_MD_EXISTS", "CLAUDE_SANDBOX",
        "DEPENDABOT_EXISTS", "PRECOMMIT_GITLEAKS", "TRACKED_IGNORED",
        "PENDING_COMMITS", "STALE_BRANCHES", "PYTHON_PYPROJECT",
        "PYTHON_MIN_VERSION", "SETTINGS_DANGEROUS", "SETTINGS_CLEAN",
        "README_CI_BADGE", "CI_WORKFLOW", "WORKFLOWS_PASSING", "RELEASE_WORKFLOW",
        "PII_SCAN", "REPO_DESCRIPTION",
        "CLI_VERSION", "CLI_PYPI_READY", "CLI_RELEASE_WORKFLOW", "CLI_BUILD_BACKEND",
        "CLI_EDITABLE_INSTALL",
    }
    assert rule_ids == expected


def test_canonical_order():
    rules = discover_rules()
    assert rules[0].id == "DEFAULT_BRANCH"
    assert rules[1].id == "LICENSE_EXISTS"
    assert rules[-1].id == "REPO_DESCRIPTION"


def test_all_pass_on_complete_repo(tmp_repo):
    """A well-configured repo should pass most checks."""
    repo = Repo(path=tmp_repo)
    rules = discover_rules()

    passing_ids = set()
    for rule in rules:
        if not rule.applies_to(repo):
            continue
        result = rule.check(repo)
        if result.status in (Status.PASS, Status.SKIP):
            passing_ids.add(rule.id)

    # The fixture repo should pass all these
    assert "DEFAULT_BRANCH" in passing_ids
    assert "README_EXISTS" in passing_ids
    assert "README_CURRENT" in passing_ids
    assert "README_LICENSE" in passing_ids
    assert "LICENSE_EXISTS" in passing_ids
    assert "GITIGNORE" in passing_ids
    assert "CLAUDE_MD_EXISTS" in passing_ids
    assert "CLAUDE_SANDBOX" in passing_ids
    assert "DEPENDABOT_EXISTS" in passing_ids
    assert "TRACKED_IGNORED" in passing_ids
    assert "LOGO_EXISTS" in passing_ids
    assert "README_LOGO" not in passing_ids  # README doesn't reference logo


def test_readme_exists_fail(bare_repo):
    repo = Repo(path=bare_repo)
    from tsilva_maintain.rules.readme_exists import ReadmeExistsRule
    result = ReadmeExistsRule().check(repo)
    assert result.status == Status.FAIL


def test_readme_current_placeholders(tmp_repo):
    (tmp_repo / "README.md").write_text("# Test\n\nTODO: finish this\n\n## Usage\n\nExample here.\n")
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.readme_current import ReadmeCurrentRule
    result = ReadmeCurrentRule().check(repo)
    assert result.status == Status.FAIL
    assert "TODO" in result.message


def test_readme_current_short(tmp_repo):
    (tmp_repo / "README.md").write_text("# Hi\n")
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.readme_current import ReadmeCurrentRule
    result = ReadmeCurrentRule().check(repo)
    assert result.status == Status.FAIL


def test_license_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from tsilva_maintain.rules.file_exists import LicenseExistsRule
    rule = LicenseExistsRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    assert (bare_repo / "LICENSE").is_file()
    assert "MIT License" in (bare_repo / "LICENSE").read_text()

    # Re-check should pass
    assert rule.check(repo).status == Status.PASS


def test_claude_md_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from tsilva_maintain.rules.file_exists import ClaudeMdExistsRule
    rule = ClaudeMdExistsRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    assert (bare_repo / "CLAUDE.md").is_file()
    content = (bare_repo / "CLAUDE.md").read_text()
    assert "bare-repo" in content


def test_gitignore_fix_incomplete(tmp_repo):
    # Remove some patterns
    (tmp_repo / ".gitignore").write_text("*.pyc\n")
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.gitignore import GitignoreRule
    rule = GitignoreRule()
    result = rule.check(repo)
    assert result.status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"


def test_gitignore_fix_missing(bare_repo):
    repo = Repo(path=bare_repo)
    from tsilva_maintain.rules.gitignore import GitignoreRule
    rule = GitignoreRule()
    result = rule.check(repo)
    assert result.status == Status.FAIL
    assert "not found" in result.message

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    assert (bare_repo / ".gitignore").is_file()
    content = (bare_repo / ".gitignore").read_text()
    assert ".env" in content


def test_sandbox_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from tsilva_maintain.rules.claude_sandbox import ClaudeSandboxRule
    rule = ClaudeSandboxRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"

    settings = json.loads((bare_repo / ".claude" / "settings.local.json").read_text())
    assert settings["sandbox"]["enabled"] is True
    assert settings["permissions"] == {"allow": [], "deny": []}


def test_dependabot_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from tsilva_maintain.rules.dependabot_exists import DependabotExistsRule
    rule = DependabotExistsRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    assert (bare_repo / ".github" / "dependabot.yml").is_file()


def test_precommit_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from tsilva_maintain.rules.precommit_gitleaks import PrecommitGitleaksRule
    rule = PrecommitGitleaksRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    config = (bare_repo / ".pre-commit-config.yaml").read_text()
    assert "tsilva/.github" in config


def test_pending_commits_clean(tmp_repo):
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.pending_commits import PendingCommitsRule
    result = PendingCommitsRule().check(repo)
    assert result.status == Status.PASS


def test_pending_commits_dirty(tmp_repo):
    (tmp_repo / "new-file.txt").write_text("hello")
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.pending_commits import PendingCommitsRule
    result = PendingCommitsRule().check(repo)
    assert result.status == Status.FAIL
    assert "uncommitted" in result.message


def test_stale_branches_clean(tmp_repo):
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.stale_branches import StaleBranchesRule
    result = StaleBranchesRule().check(repo)
    assert result.status == Status.PASS


def test_python_pyproject_skip(tmp_repo):
    """Non-Python repos should skip."""
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.python import PythonPyprojectRule
    rule = PythonPyprojectRule()
    assert not rule.applies_to(repo)


def test_python_pyproject_pass(tmp_repo):
    (tmp_repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.python import PythonPyprojectRule
    result = PythonPyprojectRule().check(repo)
    assert result.status == Status.PASS


def test_tracked_ignored_fix(tmp_repo):
    # Create and commit a .env file (which is in .gitignore)
    (tmp_repo / ".env").write_text("SECRET=abc")
    subprocess.run(["git", "-C", str(tmp_repo), "add", "-f", ".env"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp_repo), "commit", "-m", "add env"], capture_output=True, check=True)

    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.tracked_ignored import TrackedIgnoredRule
    rule = TrackedIgnoredRule()
    result = rule.check(repo)
    assert result.status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"

    # File should still exist on disk
    assert (tmp_repo / ".env").is_file()

    # But should no longer be tracked
    result = rule.check(repo)
    assert result.status == Status.PASS


def test_readme_license_fix(tmp_repo):
    # Remove license reference from README
    (tmp_repo / "README.md").write_text("# test-repo\n\nA test repo.\n\n## Installation\n\npip install test-repo\n")
    repo = Repo(path=tmp_repo)
    from tsilva_maintain.rules.readme_content import ReadmeLicenseRule
    rule = ReadmeLicenseRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    content = (tmp_repo / "README.md").read_text()
    assert "## License" in content
