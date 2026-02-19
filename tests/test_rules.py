"""Tests for individual rules."""

import json
import subprocess
from pathlib import Path

from gitguard.repo import Repo
from gitguard.rules import Status
from gitguard.rules._registry import discover_rules


def test_all_rules_discovered():
    rules = discover_rules()
    rule_ids = {r.id for r in rules}
    expected = {
        "ARCHIVED_MARKER",
        "DEFAULT_BRANCH",
        "README_EXISTS",
        "README_CURRENT",
        "README_LICENSE",
        "README_LOGO",
        "LOGO_EXISTS",
        "LICENSE_EXISTS",
        "GITIGNORE",
        "CLAUDE_MD_EXISTS",
        "CLAUDE_SANDBOX",
        "DEPENDABOT_EXISTS",
        "PRECOMMIT_GITLEAKS",
        "TRACKED_IGNORED",
        "PENDING_COMMITS",
        "STALE_BRANCHES",
        "PYTHON_PYPROJECT",
        "PYTHON_MIN_VERSION",
        "SETTINGS_DANGEROUS",
        "SETTINGS_CLEAN",
        "README_CI_BADGE",
        "CI_WORKFLOW",
        "WORKFLOWS_PASSING",
        "RELEASE_WORKFLOW",
        "PII_SCAN",
        "REPO_DESCRIPTION",
        "CLI_VERSION",
        "CLI_PYPI_READY",
        "CLI_RELEASE_WORKFLOW",
        "CLI_BUILD_BACKEND",
        "CLI_EDITABLE_INSTALL",
        "CLAUDE_GIT_WRITE",
        "CLAUDE_MD_SYMLINK",
    }
    assert rule_ids == expected


def test_canonical_order():
    rules = discover_rules()
    assert rules[0].id == "ARCHIVED_MARKER"
    assert rules[1].id == "DEFAULT_BRANCH"
    assert rules[2].id == "LICENSE_EXISTS"
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
    from gitguard.rules.readme_exists import ReadmeExistsRule

    result = ReadmeExistsRule().check(repo)
    assert result.status == Status.FAIL


def test_readme_current_placeholders(tmp_repo):
    (tmp_repo / "README.md").write_text(
        "# Test\n\nTODO: finish this\n\n## Usage\n\nExample here.\n"
    )
    repo = Repo(path=tmp_repo)
    from gitguard.rules.readme_current import ReadmeCurrentRule

    result = ReadmeCurrentRule().check(repo)
    assert result.status == Status.FAIL
    assert "TODO" in result.message


def test_readme_current_short(tmp_repo):
    (tmp_repo / "README.md").write_text("# Hi\n")
    repo = Repo(path=tmp_repo)
    from gitguard.rules.readme_current import ReadmeCurrentRule

    result = ReadmeCurrentRule().check(repo)
    assert result.status == Status.FAIL


def test_license_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from gitguard.rules.file_exists import LicenseExistsRule

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
    from gitguard.rules.file_exists import ClaudeMdExistsRule

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
    from gitguard.rules.gitignore import GitignoreRule

    rule = GitignoreRule()
    result = rule.check(repo)
    assert result.status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"


def test_gitignore_fix_missing(bare_repo):
    repo = Repo(path=bare_repo)
    from gitguard.rules.gitignore import GitignoreRule, MANAGED_START, MANAGED_END

    rule = GitignoreRule()
    result = rule.check(repo)
    assert result.status == Status.FAIL
    assert "not found" in result.message

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    assert (bare_repo / ".gitignore").is_file()
    content = (bare_repo / ".gitignore").read_text()
    assert ".env" in content
    assert MANAGED_START in content
    assert MANAGED_END in content


def test_sandbox_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from gitguard.rules.claude_sandbox import ClaudeSandboxRule

    rule = ClaudeSandboxRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"

    settings = json.loads((bare_repo / ".claude" / "settings.local.json").read_text())
    assert settings["sandbox"]["enabled"] is True
    assert settings["permissions"] == {"allow": [], "deny": []}


def test_dependabot_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from gitguard.rules.dependabot_exists import DependabotExistsRule

    rule = DependabotExistsRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    assert (bare_repo / ".github" / "dependabot.yml").is_file()


def test_precommit_fix(bare_repo):
    repo = Repo(path=bare_repo)
    from gitguard.rules.precommit_gitleaks import PrecommitGitleaksRule

    rule = PrecommitGitleaksRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    config = (bare_repo / ".pre-commit-config.yaml").read_text()
    assert "tsilva/.github" in config


def test_pending_commits_clean(tmp_repo):
    repo = Repo(path=tmp_repo)
    from gitguard.rules.pending_commits import PendingCommitsRule

    result = PendingCommitsRule().check(repo)
    assert result.status == Status.PASS


def test_pending_commits_dirty(tmp_repo):
    (tmp_repo / "new-file.txt").write_text("hello")
    repo = Repo(path=tmp_repo)
    from gitguard.rules.pending_commits import PendingCommitsRule

    result = PendingCommitsRule().check(repo)
    assert result.status == Status.FAIL
    assert "uncommitted" in result.message


def test_stale_branches_clean(tmp_repo):
    repo = Repo(path=tmp_repo)
    from gitguard.rules.stale_branches import StaleBranchesRule

    result = StaleBranchesRule().check(repo)
    assert result.status == Status.PASS


def test_python_pyproject_skip(tmp_repo):
    """Non-Python repos should skip."""
    repo = Repo(path=tmp_repo)
    from gitguard.rules.python import PythonPyprojectRule

    rule = PythonPyprojectRule()
    assert not rule.applies_to(repo)


def test_python_pyproject_pass(tmp_repo):
    (tmp_repo / "pyproject.toml").write_text('[project]\nname = "test"\n')
    repo = Repo(path=tmp_repo)
    from gitguard.rules.python import PythonPyprojectRule

    result = PythonPyprojectRule().check(repo)
    assert result.status == Status.PASS


def test_tracked_ignored_fix(tmp_repo):
    # Create and commit a .env file (which is in .gitignore)
    (tmp_repo / ".env").write_text("SECRET=abc")
    subprocess.run(
        ["git", "-C", str(tmp_repo), "add", "-f", ".env"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_repo), "commit", "-m", "add env"],
        capture_output=True,
        check=True,
    )

    repo = Repo(path=tmp_repo)
    from gitguard.rules.tracked_ignored import TrackedIgnoredRule

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


def test_gitignore_fix_deduplicates_user_rules(tmp_repo):
    """User rules that duplicate managed rules should be removed by fix()."""
    from gitguard.rules.gitignore import (
        GitignoreRule,
        _load_gitignore_global,
        _parse_sectioned,
        MANAGED_START,
        MANAGED_END,
    )

    global_rules = _load_gitignore_global()
    assert global_rules, "gitignore.global must be loadable for this test"

    # Write a legacy .gitignore with user rules that overlap with managed rules
    user_section = "# My custom rules\n.env\n.DS_Store\n__pycache__/\n*.pyc\n\n# Custom project rule\nmy-custom-dir/\n"
    (tmp_repo / ".gitignore").write_text(user_section)

    repo = Repo(path=tmp_repo)
    rule = GitignoreRule()

    # fix() should migrate to sectioned format and deduplicate
    outcome = rule.fix(repo)
    assert outcome.status == "fixed"

    content = (tmp_repo / ".gitignore").read_text()
    lines = content.splitlines()

    # Managed section markers present
    assert MANAGED_START in content
    assert MANAGED_END in content

    # All global rules present in managed section
    managed_rules, repo_lines = _parse_sectioned(content)
    assert ".env" in managed_rules
    assert "__pycache__/" in managed_rules

    # Count occurrences of duplicated rules — each should appear exactly once
    env_count = sum(1 for l in lines if l.strip() == ".env")
    assert env_count == 1, f".env appears {env_count} times, expected 1"

    ds_count = sum(1 for l in lines if l.strip() == ".DS_Store")
    assert ds_count == 1, f".DS_Store appears {ds_count} times, expected 1"

    pycache_count = sum(1 for l in lines if l.strip() == "__pycache__/")
    assert pycache_count == 1, f"__pycache__/ appears {pycache_count} times, expected 1"

    # Custom rule that is NOT in managed block should be preserved
    assert "my-custom-dir/" in content
    assert "my-custom-dir/" in repo_lines


def test_readme_license_fix(tmp_repo):
    # Remove license reference from README
    (tmp_repo / "README.md").write_text(
        "# test-repo\n\nA test repo.\n\n## Installation\n\npip install test-repo\n"
    )
    repo = Repo(path=tmp_repo)
    from gitguard.rules.readme_content import ReadmeLicenseRule

    rule = ReadmeLicenseRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"
    content = (tmp_repo / "README.md").read_text()
    assert "## License" in content


def _write_settings(repo_path, allow):
    settings_dir = repo_path / ".claude"
    settings_dir.mkdir(exist_ok=True)
    data = {"permissions": {"allow": allow}, "sandbox": {"enabled": True}}
    (settings_dir / "settings.local.json").write_text(json.dumps(data, indent=2) + "\n")


def test_claude_git_write_skip_no_settings(bare_repo):
    repo = Repo(path=bare_repo)
    from gitguard.rules.claude_git_write import ClaudeGitWriteRule

    result = ClaudeGitWriteRule().check(repo)
    assert result.status == Status.SKIP


def test_claude_git_write_pass_clean_settings(tmp_repo):
    _write_settings(tmp_repo, ["Bash(git add:*)", "Bash(echo:*)"])
    repo = Repo(path=tmp_repo)
    from gitguard.rules.claude_git_write import ClaudeGitWriteRule

    result = ClaudeGitWriteRule().check(repo)
    assert result.status == Status.PASS


def test_claude_git_write_fail_commit_pattern(tmp_repo):
    _write_settings(tmp_repo, ["Bash(git add:*)", "Bash(git commit:*)"])
    repo = Repo(path=tmp_repo)
    from gitguard.rules.claude_git_write import ClaudeGitWriteRule

    result = ClaudeGitWriteRule().check(repo)
    assert result.status == Status.FAIL
    assert "Bash(git commit:*)" in result.message


def test_claude_git_write_fail_push_pattern(tmp_repo):
    _write_settings(tmp_repo, ["Bash(git push:*)"])
    repo = Repo(path=tmp_repo)
    from gitguard.rules.claude_git_write import ClaudeGitWriteRule

    result = ClaudeGitWriteRule().check(repo)
    assert result.status == Status.FAIL
    assert "Bash(git push:*)" in result.message


def test_claude_git_write_fail_broad_git_pattern(tmp_repo):
    _write_settings(tmp_repo, ["Bash(git:*)"])
    repo = Repo(path=tmp_repo)
    from gitguard.rules.claude_git_write import ClaudeGitWriteRule

    result = ClaudeGitWriteRule().check(repo)
    assert result.status == Status.FAIL
    assert "Bash(git:*)" in result.message


def test_claude_git_write_fix_removes_flagged_preserves_others(tmp_repo):
    _write_settings(
        tmp_repo,
        ["Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)", "Bash(echo:*)"],
    )
    repo = Repo(path=tmp_repo)
    from gitguard.rules.claude_git_write import ClaudeGitWriteRule

    rule = ClaudeGitWriteRule()
    assert rule.check(repo).status == Status.FAIL

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"

    data = json.loads((tmp_repo / ".claude" / "settings.local.json").read_text())
    allow = data["permissions"]["allow"]
    assert "Bash(git commit:*)" not in allow
    assert "Bash(git push:*)" not in allow
    assert "Bash(git add:*)" in allow
    assert "Bash(echo:*)" in allow

    assert rule.check(repo).status == Status.PASS


def test_archived_marker_fail(bare_repo):
    repo = Repo(path=bare_repo)
    from gitguard.rules.archived_marker import ArchivedMarkerRule

    result = ArchivedMarkerRule().check(repo)
    assert result.status == Status.FAIL
    assert ".archived.md" in result.message


def test_archived_marker_pass(bare_repo):
    (bare_repo / ".archived.md").write_text("Archived: superseded by new-repo.\n")
    repo = Repo(path=bare_repo)
    from gitguard.rules.archived_marker import ArchivedMarkerRule

    result = ArchivedMarkerRule().check(repo)
    assert result.status == Status.PASS


def test_archived_marker_is_archived_only():
    from gitguard.rules.archived_marker import ArchivedMarkerRule

    assert ArchivedMarkerRule.archived_only is True


def test_gitignore_check_allows_repo_specific_rules(tmp_repo):
    """Rules below the managed section don't cause check() to fail."""
    from gitguard.rules.gitignore import (
        GitignoreRule,
        _build_sectioned_content,
        _load_gitignore_global,
    )

    global_rules = _load_gitignore_global()
    assert global_rules, "gitignore.global must be loadable for this test"

    # Build a .gitignore with repo-specific rules in the repo section
    content = _build_sectioned_content(global_rules, ["wheels/*", "!wheels/stable.whl"])
    (tmp_repo / ".gitignore").write_text(content)

    repo = Repo(path=tmp_repo)
    result = GitignoreRule().check(repo)
    assert result.status == Status.PASS


def test_gitignore_fix_preserves_negation_order(tmp_repo):
    """Repo-specific negation patterns stay in original order after fix()."""
    from gitguard.rules.gitignore import (
        GitignoreRule,
        _build_sectioned_content,
        _load_gitignore_global,
        _parse_sectioned,
    )

    global_rules = _load_gitignore_global()
    assert global_rules, "gitignore.global must be loadable for this test"

    repo_lines = ["# Wheels", "wheels/*", "!wheels/stable.whl"]

    # Write a .gitignore with a stale managed section (only one rule) so fix()
    # actually rewrites the managed section while preserving repo_lines
    stale_content = _build_sectioned_content(["*.pyc"], repo_lines)
    (tmp_repo / ".gitignore").write_text(stale_content)

    repo = Repo(path=tmp_repo)
    rule = GitignoreRule()

    outcome = rule.fix(repo)
    assert outcome.status == "fixed"

    result_content = (tmp_repo / ".gitignore").read_text()
    _, result_repo_lines = _parse_sectioned(result_content)

    # Negation order must be preserved
    wheel_idx = next(
        i for i, l in enumerate(result_repo_lines) if l.strip() == "wheels/*"
    )
    negation_idx = next(
        i for i, l in enumerate(result_repo_lines) if l.strip() == "!wheels/stable.whl"
    )
    assert wheel_idx < negation_idx, "wheels/* must come before !wheels/stable.whl"


def test_gitignore_fix_legacy_migration(tmp_repo):
    """A flat .gitignore (no markers) gets migrated to sectioned format."""
    from gitguard.rules.gitignore import (
        GitignoreRule,
        _load_gitignore_global,
        _parse_sectioned,
        MANAGED_START,
        MANAGED_END,
    )

    global_rules = _load_gitignore_global()
    assert global_rules, "gitignore.global must be loadable for this test"

    # Write legacy format: all global rules + a custom repo rule
    legacy_content = "\n".join(global_rules) + "\ncustom-dir/\n"
    (tmp_repo / ".gitignore").write_text(legacy_content)

    repo = Repo(path=tmp_repo)
    rule = GitignoreRule()

    # check() should fail with migration message
    result = rule.check(repo)
    assert result.status == Status.FAIL
    assert "migration" in result.message

    # fix() should migrate
    outcome = rule.fix(repo)
    assert outcome.status == "fixed"

    content = (tmp_repo / ".gitignore").read_text()
    assert MANAGED_START in content
    assert MANAGED_END in content

    # custom-dir/ preserved in repo section
    assert "custom-dir/" in content
    managed_rules, repo_lines = _parse_sectioned(content)
    assert managed_rules == global_rules
    assert "custom-dir/" in repo_lines

    # check() should now pass
    result = rule.check(repo)
    assert result.status == Status.PASS


def test_tracked_ignored_respects_negation(tmp_repo):
    """.env.example is NOT untracked when !.env.example negation is in .gitignore."""
    from gitguard.rules.tracked_ignored import TrackedIgnoredRule

    # The tmp_repo fixture builds .gitignore from gitignore.global which includes
    # `.env.*` AND `!.env.example`, so .env.example should NOT be truly ignored.
    # Create and commit .env.example to the repo
    (tmp_repo / ".env.example").write_text("DB_URL=postgresql://localhost/mydb\n")
    subprocess.run(
        ["git", "-C", str(tmp_repo), "add", ".env.example"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_repo), "commit", "-m", "add env example"],
        capture_output=True,
        check=True,
    )

    repo = Repo(path=tmp_repo)
    rule = TrackedIgnoredRule()

    # Run fix() — even if check() detects a spurious hit from git ls-files -i,
    # fix() must not untrack .env.example because git check-ignore will say it's not ignored.
    rule.fix(repo)

    # .env.example must still be tracked
    tracked = subprocess.run(
        ["git", "-C", str(tmp_repo), "ls-files", ".env.example"],
        capture_output=True,
        text=True,
    )
    assert ".env.example" in tracked.stdout, (
        ".env.example should remain tracked after fix()"
    )
