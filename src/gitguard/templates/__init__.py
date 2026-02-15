"""Template loading via importlib.resources."""

from __future__ import annotations

from importlib import resources


def load_template(name: str) -> str:
    """Load a template file by name (e.g. 'LICENSE', 'CLAUDE.md')."""
    return resources.files("gitguard.templates").joinpath(name).read_text(encoding="utf-8")
