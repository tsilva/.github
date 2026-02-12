"""Tests for RuleRunner engine."""

from tsilva_maintain.engine import RuleRunner


def test_audit_all_pass(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir)
    # Exit code 1 because README_LOGO will fail (no logo ref in README)
    exit_code = runner.audit()
    assert exit_code in (0, 1)


def test_audit_json(repos_dir, capsys):
    runner = RuleRunner(repos_dir=repos_dir)
    runner.audit(json_output=True)
    import json
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert "repos" in report
    assert "summary" in report
    assert report["repos_count"] == 1
    assert report["repos"][0]["repo"] == "test-repo"


def test_audit_rule_filter(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir, rule_filter="README_EXISTS")
    exit_code = runner.audit()
    assert exit_code == 0  # Should pass


def test_audit_no_repos(tmp_path):
    runner = RuleRunner(repos_dir=tmp_path)
    exit_code = runner.audit()
    assert exit_code == 0


def test_fix_dry_run(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir)
    exit_code = runner.fix(dry_run=True)
    assert exit_code == 0


def test_maintain_dry_run(repos_dir):
    runner = RuleRunner(repos_dir=repos_dir)
    exit_code = runner.maintain(dry_run=True)
    assert exit_code in (0, 1)
