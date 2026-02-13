"""Auto-discovery and canonical ordering of Rule subclasses."""

from __future__ import annotations

import importlib
import pkgutil
from tsilva_maintain.rules import Rule

# Dependency-aware ordering: foundational rules first so later rules see fixed state.
_CANONICAL_ORDER = [
    # Foundation: git basics
    "DEFAULT_BRANCH",
    # Foundation: key files that other rules depend on
    "LICENSE_EXISTS",
    "LOGO_EXISTS",
    "GITIGNORE",
    "CLAUDE_MD_EXISTS",
    "PYTHON_PYPROJECT",
    # Dependent rules: README (depends on README_EXISTS, LICENSE_EXISTS, LOGO_EXISTS)
    "README_EXISTS",
    "README_CURRENT",
    "README_LICENSE",
    "README_LOGO",
    "README_CI_BADGE",
    # Dependent rules: gitignore/claude/python
    "TRACKED_IGNORED",
    "CLAUDE_SANDBOX",
    "SETTINGS_DANGEROUS",
    "SETTINGS_CLEAN",
    "PYTHON_MIN_VERSION",
    # CLI project rules
    "CLI_BUILD_BACKEND",
    "CLI_VERSION",
    "CLI_RELEASE_WORKFLOW",
    "CLI_PYPI_READY",
    # Independent rules
    "DEPENDABOT_EXISTS",
    "PRECOMMIT_GITLEAKS",
    "PENDING_COMMITS",
    "STALE_BRANCHES",
    "CI_WORKFLOW",
    "WORKFLOWS_PASSING",
    "RELEASE_WORKFLOW",
    "PII_SCAN",
    "REPO_DESCRIPTION",
]


def discover_rules() -> list[Rule]:
    """Import all rule modules and return instances in canonical order."""
    # Import all modules in the rules package
    package = importlib.import_module("tsilva_maintain.rules")
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        if modname.startswith("_"):
            continue
        importlib.import_module(f"tsilva_maintain.rules.{modname}")

    # Collect all concrete subclasses
    instances: dict[str, Rule] = {}
    for cls in _all_subclasses(Rule):
        if not getattr(cls, "id", None):
            continue
        instances[cls.id] = cls()

    # Return in canonical order, then any extras at the end
    ordered = []
    for rule_id in _CANONICAL_ORDER:
        if rule_id in instances:
            ordered.append(instances.pop(rule_id))
    # Append any rules not in the canonical list
    for rule in sorted(instances.values(), key=lambda r: r.id):
        ordered.append(rule)

    return ordered


def _all_subclasses(cls):
    result = set()
    work = [cls]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in result:
                result.add(child)
                work.append(child)
    return result
