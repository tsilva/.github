"""CLI entry point: argparse-based command dispatch."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPOS_DIR_ENV = "GITGUARD_REPOS_DIR"
_REPOS_DIR_HELP = (
    f"Directory containing git repositories (default: ${_REPOS_DIR_ENV} env var)"
)

_SUBCOMMANDS = {"commit", "report", "rename", "logo", "create"}


def _resolve_target(args: argparse.Namespace) -> tuple[Path, bool]:
    """
    Resolve the target path and determine mode.

    Returns:
        tuple of (target_path, is_single_repo_mode)
    """
    # If a path is provided, use it as a single repo target
    if args.target is not None:
        target = Path(args.target).resolve()
        if not target.exists():
            print(f"Error: Path does not exist: {target}", file=sys.stderr)
            sys.exit(1)
        if not (target / ".git").is_dir():
            print(f"Error: Not a git repository: {target}", file=sys.stderr)
            sys.exit(1)
        return target, True

    # No path provided - use env var as repos directory (multi-repo mode)
    env = os.environ.get(_REPOS_DIR_ENV)
    if env:
        repos_dir = Path(env)
        if not repos_dir.is_dir():
            print(
                f"Error: Repos directory does not exist: {repos_dir}", file=sys.stderr
            )
            sys.exit(1)
        return repos_dir, False
    else:
        print(
            f"Error: No target provided and ${_REPOS_DIR_ENV} is not set",
            file=sys.stderr,
        )
        sys.exit(1)


def _build_maintain_parser() -> argparse.ArgumentParser:
    """Build parser for the default maintain command."""
    parser = argparse.ArgumentParser(
        prog="gitguard",
        description="Compliance audit and maintenance CLI for the tsilva GitHub organization",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        type=Path,
        help="Path to a git repository (runs single-repo mode). If omitted, uses GITGUARD_REPOS_DIR env var for multi-repo mode.",
    )
    parser.add_argument(
        "-f",
        "--filter",
        dest="filter_pattern",
        default="",
        help="Only process repos matching pattern (multi-repo mode only)",
    )
    parser.add_argument(
        "-j",
        "--json",
        dest="json_output",
        action="store_true",
        help="Output JSON report to stdout",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Check and show what would be fixed without modifying files",
    )
    parser.add_argument(
        "--rule", dest="rule_filter", default=None, help="Run only this rule ID"
    )
    parser.add_argument(
        "--category",
        dest="category_filter",
        default=None,
        help="Run only rules in this category",
    )
    return parser


def _build_commit_parser() -> argparse.ArgumentParser:
    """Build parser for the commit subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitguard commit",
        description="Interactive AI-assisted commit & push for dirty repos",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        type=Path,
        help="Path to a git repository (runs single-repo mode). If omitted, uses GITGUARD_REPOS_DIR env var for multi-repo mode.",
    )
    parser.add_argument(
        "-f",
        "--filter",
        dest="filter_pattern",
        default="",
        help="Only process repos matching pattern (multi-repo mode only)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Show dirty repos without committing",
    )
    return parser


def _build_report_parser() -> argparse.ArgumentParser:
    """Build parser for the report subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitguard report",
        description="Generate reports",
    )
    parser.add_argument(
        "report_type",
        choices=["taglines", "tracked-ignored", "branches"],
        help="Report type",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        type=Path,
        help="Path to a git repository (runs single-repo mode). If omitted, uses GITGUARD_REPOS_DIR env var for multi-repo mode.",
    )
    parser.add_argument(
        "-f",
        "--filter",
        dest="filter_pattern",
        default="",
        help="Only process repos matching pattern (multi-repo mode only)",
    )
    return parser


def _build_rename_parser() -> argparse.ArgumentParser:
    """Build parser for the rename subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitguard rename",
        description="Rename a repo: GitHub, local folder, git remote, and in-repo file references",
    )
    parser.add_argument("old_name", help="Current repository name")
    parser.add_argument("new_name", help="New repository name")
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        type=Path,
        help="Path to repos directory (uses GITGUARD_REPOS_DIR env var if omitted)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Show what would change without modifying anything",
    )
    return parser


def _build_logo_parser() -> argparse.ArgumentParser:
    """Build parser for the logo subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitguard logo",
        description="Generate a logo for a repository using AI image generation",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        type=Path,
        help="Path to a git repository (uses GITGUARD_REPOS_DIR env var if omitted)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Show prompt without generating image",
    )
    return parser


def _build_create_parser() -> argparse.ArgumentParser:
    """Build parser for the create subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitguard create",
        description="Create a new repo from a GitHub template",
    )
    parser.add_argument("repo_name", help="Repository name (lowercase, letters/hyphens/numbers)")
    parser.add_argument(
        "template_type",
        nargs="?",
        default=None,
        choices=["python-cli", "python-sandbox", "generic", "react-native"],
        help="Template type (auto-detected for sandbox-* names)",
    )
    parser.add_argument(
        "-d",
        "--description",
        dest="description",
        default="",
        help="One-line project description",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        type=Path,
        help="Path to repos directory (uses GITGUARD_REPOS_DIR env var if omitted)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Show what would happen without making changes",
    )
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
            target, single_repo = _resolve_target(args)

            from gitguard.commands.commit import run_commit

            if single_repo:
                sys.exit(run_commit(target, None, args.dry_run, single_repo=True))
            else:
                sys.exit(
                    run_commit(
                        target, args.filter_pattern, args.dry_run, single_repo=False
                    )
                )

        elif command == "report":
            parser = _build_report_parser()
            args = parser.parse_args(rest)
            target, single_repo = _resolve_target(args)

            from gitguard.commands.report import run_report

            if single_repo:
                sys.exit(run_report(args.report_type, target, None, single_repo=True))
            else:
                sys.exit(
                    run_report(
                        args.report_type, target, args.filter_pattern, single_repo=False
                    )
                )

        elif command == "rename":
            parser = _build_rename_parser()
            args = parser.parse_args(rest)

            # For rename, target is always the repos directory (not a single repo)
            if args.target is not None:
                repos_dir = Path(args.target).resolve()
                if not repos_dir.is_dir():
                    print(
                        f"Error: Directory does not exist: {repos_dir}", file=sys.stderr
                    )
                    sys.exit(1)
            else:
                env = os.environ.get(_REPOS_DIR_ENV)
                if env:
                    repos_dir = Path(env)
                    if not repos_dir.is_dir():
                        print(
                            f"Error: Repos directory does not exist: {repos_dir}",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                else:
                    print(
                        f"Error: No target provided and {_REPOS_DIR_ENV} is not set",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            from gitguard.commands.rename import run_rename

            sys.exit(run_rename(args.old_name, args.new_name, repos_dir, args.dry_run))

        elif command == "logo":
            parser = _build_logo_parser()
            args = parser.parse_args(rest)

            # For logo, target is always a single repo
            if args.target is not None:
                repo_path = Path(args.target).resolve()
                if not repo_path.exists():
                    print(f"Error: Path does not exist: {repo_path}", file=sys.stderr)
                    sys.exit(1)
                if not (repo_path / ".git").is_dir():
                    print(f"Error: Not a git repository: {repo_path}", file=sys.stderr)
                    sys.exit(1)
            else:
                env = os.environ.get(_REPOS_DIR_ENV)
                if env:
                    repos_dir = Path(env)
                    if not repos_dir.is_dir():
                        print(
                            f"Error: Repos directory does not exist: {repos_dir}",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    # Use current directory name as repo name
                    repo_path = repos_dir / Path.cwd().name
                    if not (repo_path / ".git").is_dir():
                        print(
                            f"Error: Not a git repository: {repo_path}", file=sys.stderr
                        )
                        sys.exit(1)
                else:
                    print(
                        f"Error: No target provided and {_REPOS_DIR_ENV} is not set",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            from gitguard.commands.logo import run_logo

            sys.exit(run_logo(repo_path, args.dry_run))

        elif command == "create":
            parser = _build_create_parser()
            args = parser.parse_args(rest)

            # Auto-detect template type for sandbox-* names
            template_type = args.template_type
            if template_type is None:
                if args.repo_name.startswith("sandbox-"):
                    template_type = "python-sandbox"
                else:
                    print(
                        "Error: template_type is required (python-cli, python-sandbox, generic, or react-native)",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            # Resolve repos directory
            if args.target is not None:
                repos_dir = Path(args.target).resolve()
                if not repos_dir.is_dir():
                    print(
                        f"Error: Directory does not exist: {repos_dir}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            else:
                env = os.environ.get(_REPOS_DIR_ENV)
                if env:
                    repos_dir = Path(env)
                    if not repos_dir.is_dir():
                        print(
                            f"Error: Repos directory does not exist: {repos_dir}",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                else:
                    print(
                        f"Error: No target provided and {_REPOS_DIR_ENV} is not set",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            from gitguard.commands.create import run_create

            sys.exit(
                run_create(
                    args.repo_name, template_type, args.description, repos_dir, args.dry_run
                )
            )

    else:
        # Default: maintain (single-pass check+fix)
        parser = _build_maintain_parser()
        args = parser.parse_args(argv)
        target, single_repo = _resolve_target(args)

        from gitguard.engine import RuleRunner

        runner = RuleRunner(
            target=target,
            filter_pattern=args.filter_pattern if not single_repo else "",
            rule_filter=args.rule_filter,
            category_filter=args.category_filter,
            single_repo=single_repo,
        )
        sys.exit(
            runner.run(
                dry_run=args.dry_run,
                json_output=args.json_output,
            )
        )
