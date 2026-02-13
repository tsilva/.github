"""Tests for RuleRunner engine."""

from tsilva_maintain.engine import RuleRunner


def test_run_dry_run_audit(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir)
    exit_code = runner.run(dry_run=True)
    assert exit_code in (0, 1)


def test_run_json(repos_dir, capsys):
    runner = RuleRunner(repos_dir=repos_dir)
    runner.run(dry_run=True, json_output=True)
    import json
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert "repos" in report
    assert "summary" in report
    assert report["repos_count"] == 1
    assert report["repos"][0]["repo"] == "test-repo"


def test_run_rule_filter(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir, rule_filter="README_EXISTS")
    exit_code = runner.run(dry_run=True)
    assert exit_code == 0


def test_run_no_repos(tmp_path):
    runner = RuleRunner(repos_dir=tmp_path)
    exit_code = runner.run(dry_run=True)
    assert exit_code == 0


def test_run_dry_run(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir)
    exit_code = runner.run(dry_run=True)
    assert exit_code in (0, 1)


def test_run_maintain(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir)
    exit_code = runner.run()
    assert exit_code in (0, 1)


def test_dependency_ordering():
    """Rules that depend on others should come after their dependencies."""
    from tsilva_maintain.rules._registry import _CANONICAL_ORDER

    order = {rule_id: i for i, rule_id in enumerate(_CANONICAL_ORDER)}

    # GITIGNORE before TRACKED_IGNORED
    assert order["GITIGNORE"] < order["TRACKED_IGNORED"]
    # README_EXISTS before README_CURRENT, README_LICENSE, README_LOGO, README_CI_BADGE
    assert order["README_EXISTS"] < order["README_CURRENT"]
    assert order["README_EXISTS"] < order["README_LICENSE"]
    assert order["README_EXISTS"] < order["README_LOGO"]
    assert order["README_EXISTS"] < order["README_CI_BADGE"]
    # LICENSE_EXISTS before README_LICENSE
    assert order["LICENSE_EXISTS"] < order["README_LICENSE"]
    # LOGO_EXISTS before README_LOGO
    assert order["LOGO_EXISTS"] < order["README_LOGO"]
    # CLAUDE_MD_EXISTS before CLAUDE_SANDBOX
    assert order["CLAUDE_MD_EXISTS"] < order["CLAUDE_SANDBOX"]
    # SETTINGS_DANGEROUS before SETTINGS_CLEAN
    assert order["SETTINGS_DANGEROUS"] < order["SETTINGS_CLEAN"]
    # PYTHON_PYPROJECT before PYTHON_MIN_VERSION
    assert order["PYTHON_PYPROJECT"] < order["PYTHON_MIN_VERSION"]
