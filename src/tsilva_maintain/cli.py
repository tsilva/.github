"""CLI entry point: argparse-based command dispatch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="tsilva-maintain",
        description="Compliance audit and maintenance CLI for the tsilva GitHub organization",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- audit ---
    p_audit = sub.add_parser("audit", help="Run compliance audit on repos")
    p_audit.add_argument("repos_dir", type=Path, help="Directory containing git repositories")
    p_audit.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")
    p_audit.add_argument("-j", "--json", dest="json_output", action="store_true", help="Output JSON report to stdout")
    p_audit.add_argument("--rule", dest="rule_filter", default=None, help="Run only this rule ID")
    p_audit.add_argument("--category", dest="category_filter", default=None, help="Run only rules in this category")

    # --- fix ---
    p_fix = sub.add_parser("fix", help="Auto-fix failing compliance checks")
    p_fix.add_argument("repos_dir", type=Path, help="Directory containing git repositories")
    p_fix.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")
    p_fix.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", help="Show what would be done without executing")
    p_fix.add_argument("--rule", dest="rule_filter", default=None, help="Fix only this rule ID")

    # --- maintain ---
    p_maintain = sub.add_parser("maintain", help="Full audit -> fix -> verify cycle")
    p_maintain.add_argument("repos_dir", type=Path, help="Directory containing git repositories")
    p_maintain.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")
    p_maintain.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", help="Show what would be done without executing")

    # --- commit ---
    p_commit = sub.add_parser("commit", help="AI-assisted commit & push for dirty repos")
    p_commit.add_argument("repos_dir", type=Path, help="Directory containing git repositories")
    p_commit.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")
    p_commit.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", help="Show dirty repos without committing")

    # --- report ---
    p_report = sub.add_parser("report", help="Generate reports")
    p_report.add_argument("report_type", choices=["taglines", "tracked-ignored"], help="Report type")
    p_report.add_argument("repos_dir", type=Path, help="Directory containing git repositories")
    p_report.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")

    args = parser.parse_args(argv)

    if not args.repos_dir.is_dir():
        print(f"Error: Directory does not exist: {args.repos_dir}", file=sys.stderr)
        sys.exit(1)

    if args.command in ("audit", "fix", "maintain"):
        from tsilva_maintain.engine import RuleRunner

        runner = RuleRunner(
            repos_dir=args.repos_dir,
            filter_pattern=args.filter_pattern,
            rule_filter=getattr(args, "rule_filter", None),
            category_filter=getattr(args, "category_filter", None),
        )

        if args.command == "audit":
            sys.exit(runner.audit(json_output=args.json_output))
        elif args.command == "fix":
            sys.exit(runner.fix(dry_run=args.dry_run))
        elif args.command == "maintain":
            sys.exit(runner.maintain(dry_run=args.dry_run))

    elif args.command == "commit":
        from tsilva_maintain.commands.commit import run_commit

        sys.exit(run_commit(args.repos_dir, args.filter_pattern, args.dry_run))

    elif args.command == "report":
        from tsilva_maintain.commands.report import run_report

        sys.exit(run_report(args.report_type, args.repos_dir, args.filter_pattern))
