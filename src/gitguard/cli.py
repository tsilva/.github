"""CLI entry point: argparse-based command dispatch."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPOS_DIR_ENV = "GITGUARD_REPOS_DIR"
_REPOS_DIR_HELP = (
    "Directory containing git repositories "
    f"(default: ${_REPOS_DIR_ENV} env var)"
)

_SUBCOMMANDS = {"commit", "report"}


def _resolve_repos_dir(args: argparse.Namespace) -> None:
    """Fill args.repos_dir from env var when not given on the command line."""
    if args.repos_dir is not None:
        return
    env = os.environ.get(_REPOS_DIR_ENV)
    if env:
        args.repos_dir = Path(env)
    else:
        print(
            f"Error: repos_dir not provided and ${_REPOS_DIR_ENV} is not set",
            file=sys.stderr,
        )
        sys.exit(1)


def _build_maintain_parser() -> argparse.ArgumentParser:
    """Build parser for the default maintain command."""
    parser = argparse.ArgumentParser(
        prog="gitguard",
        description="Compliance audit and maintenance CLI for the tsilva GitHub organization",
    )
    parser.add_argument("repos_dir", nargs="?", default=None, type=Path, help=_REPOS_DIR_HELP)
    parser.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")
    parser.add_argument("-j", "--json", dest="json_output", action="store_true", help="Output JSON report to stdout")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", help="Check and show what would be fixed without modifying files")
    parser.add_argument("--rule", dest="rule_filter", default=None, help="Run only this rule ID")
    parser.add_argument("--category", dest="category_filter", default=None, help="Run only rules in this category")
    return parser


def _build_commit_parser() -> argparse.ArgumentParser:
    """Build parser for the commit subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitguard commit",
        description="Interactive AI-assisted commit & push for dirty repos",
    )
    parser.add_argument("repos_dir", nargs="?", default=None, type=Path, help=_REPOS_DIR_HELP)
    parser.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true", help="Show dirty repos without committing")
    return parser


def _build_report_parser() -> argparse.ArgumentParser:
    """Build parser for the report subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitguard report",
        description="Generate reports",
    )
    parser.add_argument("report_type", choices=["taglines", "tracked-ignored"], help="Report type")
    parser.add_argument("repos_dir", nargs="?", default=None, type=Path, help=_REPOS_DIR_HELP)
    parser.add_argument("-f", "--filter", dest="filter_pattern", default="", help="Only process repos matching pattern")
    return parser


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    # Route to subcommand if first arg matches
    if argv and argv[0] in _SUBCOMMANDS:
        command = argv[0]
        rest = argv[1:]

        if command == "commit":
            parser = _build_commit_parser()
            args = parser.parse_args(rest)
            _resolve_repos_dir(args)

            if not args.repos_dir.is_dir():
                print(f"Error: Directory does not exist: {args.repos_dir}", file=sys.stderr)
                sys.exit(1)

            from gitguard.commands.commit import run_commit

            sys.exit(run_commit(args.repos_dir, args.filter_pattern, args.dry_run))

        elif command == "report":
            parser = _build_report_parser()
            args = parser.parse_args(rest)
            _resolve_repos_dir(args)

            if not args.repos_dir.is_dir():
                print(f"Error: Directory does not exist: {args.repos_dir}", file=sys.stderr)
                sys.exit(1)

            from gitguard.commands.report import run_report

            sys.exit(run_report(args.report_type, args.repos_dir, args.filter_pattern))

    else:
        # Default: maintain (single-pass check+fix)
        parser = _build_maintain_parser()
        args = parser.parse_args(argv)
        _resolve_repos_dir(args)

        if not args.repos_dir.is_dir():
            print(f"Error: Directory does not exist: {args.repos_dir}", file=sys.stderr)
            sys.exit(1)

        from gitguard.engine import RuleRunner

        runner = RuleRunner(
            repos_dir=args.repos_dir,
            filter_pattern=args.filter_pattern,
            rule_filter=args.rule_filter,
            category_filter=args.category_filter,
        )
        sys.exit(runner.run(
            dry_run=args.dry_run,
            json_output=args.json_output,
        ))
