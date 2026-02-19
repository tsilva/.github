"""Configuration loading for logo generation with 3-level hierarchy."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in strings."""
    if isinstance(value, str):

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))

        pattern = r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
        return re.sub(pattern, replace_var, value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries. Override takes precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_json_file(path: Path) -> dict[str, Any] | None:
    """Load JSON file, returning None if not found or invalid."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, PermissionError):
        return None


def load_logo_config(repo_path: Path) -> dict[str, Any]:
    """Load logo configuration with 3-level hierarchy.

    Hierarchy (highest precedence first):
    1. Project config: {repo}/.gitguard/logo.json
    2. User config: ~/.config/gitguard/logo-config.json
    3. Bundled defaults: src/gitguard/templates/logo-config.json

    Args:
        repo_path: Path to the repository

    Returns:
        Merged configuration dictionary
    """
    # Load bundled defaults
    defaults_path = Path(__file__).parent / "templates" / "logo-config.json"
    config = load_json_file(defaults_path) or {}
    sources = ["defaults"]

    # Load user config
    user_config_path = Path.home() / ".config" / "gitguard" / "logo-config.json"
    user_config = load_json_file(user_config_path)
    if user_config:
        config = deep_merge(config, user_config)
        sources.append("user")

    # Load project config
    project_config_path = repo_path / ".gitguard" / "logo.json"
    project_config = load_json_file(project_config_path)
    if project_config:
        config = deep_merge(config, project_config)
        sources.append("project")

    # Expand environment variables
    config = expand_env_vars(config)

    # Add metadata
    config["_meta"] = {"sources": sources}

    return config


def resolve_api_key(repo_path: Path) -> str:
    """Resolve OpenRouter API key from environment or .env file.

    Resolution order (highest priority first):
    1. GITGUARD_OPENROUTER_API_KEY environment variable
    2. OPENROUTER_API_KEY from .env file in repo root

    Args:
        repo_path: Path to the repository

    Returns:
        API key string

    Raises:
        RuntimeError: If no API key is found
    """
    # Check environment variable first
    api_key = os.environ.get("GITGUARD_OPENROUTER_API_KEY")
    if api_key:
        return api_key

    # Try to load from .env file
    env_path = repo_path / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip("\"'")
                        if key == "OPENROUTER_API_KEY" and value:
                            return value
        except (PermissionError, UnicodeDecodeError):
            pass

    raise RuntimeError(
        "OpenRouter API key not found. Set GITGUARD_OPENROUTER_API_KEY environment variable "
        "or add OPENROUTER_API_KEY=your_key to .env file in the repository."
    )
