"""Auto-discovery and canonical ordering of Rule subclasses."""

from __future__ import annotations

import importlib
import pkgutil
from typing import List

from tsilva_maintain.rules import Rule

# Canonical order matching ALL_CHECKS in audit-repos.sh
_CANONICAL_ORDER = [
    "DEFAULT_BRANCH",
    "README_EXISTS",
    "README_CURRENT",
    "README_LICENSE",
    "README_LOGO",
    "LOGO_EXISTS",
    "LICENSE_EXISTS",
    "GITIGNORE_EXISTS",
    "GITIGNORE_COMPLETE",
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
    "RELEASE_WORKFLOW",
    "PII_SCAN",
    "REPO_DESCRIPTION",
]


def discover_rules() -> List[Rule]:
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
