"""Logo generation command for gitguard CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gitguard.config_loader import load_logo_config, resolve_api_key
from gitguard.logo_generator import generate_logo


def run_logo(repo_path: Path, dry_run: bool = False, show_config: bool = False) -> int:
    """Generate a logo for the given repository.

    Args:
        repo_path: Path to the repository
        dry_run: If True, only show what would be generated
        show_config: If True, display merged configuration and exit

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if not repo_path.is_dir():
        print(f"Error: Not a directory: {repo_path}", file=sys.stderr)
        return 1

    # Load configuration
    try:
        config = load_logo_config(repo_path)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    if show_config:
        import json

        print(json.dumps(config, indent=2))
        return 0

    # Resolve API key
    try:
        api_key = resolve_api_key(repo_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nSet GITGUARD_OPENROUTER_API_KEY environment variable", file=sys.stderr)
        print(
            "or create a .env file in the repo with OPENROUTER_API_KEY=your_key",
            file=sys.stderr,
        )
        return 1

    if dry_run:
        from gitguard.logo_generator import build_prompt, detect_project_type

        project_name = repo_path.name
        project_type = detect_project_type(repo_path)
        prompt = build_prompt(project_name, project_type, config)
        print(f"Project: {project_name}")
        print(f"Type: {project_type}")
        print(f"Output: {config.get('outputPath', 'logo.png')}")
        print(f"\nPrompt:\n{prompt}")
        return 0

    # Generate logo
    try:
        output_path = generate_logo(repo_path, config, api_key)
        print(f"Logo generated: {output_path}")
        return 0
    except Exception as e:
        print(f"Error generating logo: {e}", file=sys.stderr)
        return 1
