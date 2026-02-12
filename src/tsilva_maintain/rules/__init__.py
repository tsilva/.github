"""Rule base class and types for compliance checks."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tsilva_maintain.repo import Repo


class Status(Enum):
    PASS = "passed"
    FAIL = "failed"
    SKIP = "skipped"


class Category(Enum):
    REPO_STRUCTURE = "Repository Structure"
    DEPENDENCY_MANAGEMENT = "Dependency Management"
    PYTHON = "Python Projects"
    CICD = "CI/CD"
    CLAUDE = "Claude Code Configuration"
    SECURITY = "Security"
    GIT_HYGIENE = "Git Hygiene"


class FixType(Enum):
    AUTO = "auto"
    MANUAL = "manual"
    AI = "ai"
    NONE = "none"


@dataclass
class CheckResult:
    status: Status
    message: str = ""


@dataclass
class FixOutcome:
    status: str  # "fixed", "already_ok", "skipped", "manual", "failed"
    message: str = ""

    FIXED = "fixed"
    ALREADY_OK = "already_ok"
    SKIPPED = "skipped"
    MANUAL = "manual"
    FAILED = "failed"


class Rule(abc.ABC):
    """Base class for all compliance rules."""

    id: str
    name: str
    category: Category
    rule_number: str = ""
    fix_type: FixType = FixType.NONE

    def applies_to(self, repo: Repo) -> bool:
        """Whether this rule applies to the given repo. Default: True."""
        return True

    @abc.abstractmethod
    def check(self, repo: Repo) -> CheckResult:
        """Run the compliance check. Must return PASS, FAIL, or SKIP."""
        ...

    def fix(self, repo: Repo, *, dry_run: bool = False) -> FixOutcome:
        """Attempt to fix the issue. Override in subclasses with auto-fixable rules."""
        return FixOutcome(FixOutcome.MANUAL, f"No auto-fix for {self.id}")
