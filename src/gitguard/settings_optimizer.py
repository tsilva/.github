"""Claude Code Settings Optimizer (library version, no CLI)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class IssueType(Enum):
    DANGEROUS = "dangerous"
    SPECIFIC = "specific"
    REDUNDANT = "redundant"
    MIGRATE_TO_SANDBOX = "migrate_to_sandbox"
    GOOD = "good"


@dataclass
class Permission:
    pattern: str
    location: str  # "Global" or "Project"

    def __hash__(self):
        return hash((self.pattern, self.location))

    def __eq__(self, other):
        return self.pattern == other.pattern and self.location == other.location


@dataclass
class Issue:
    permission: Permission
    issue_type: IssueType
    reason: str
    suggestion: Optional[str] = None
    covered_by: Optional[Permission] = None
    migrate_domain: Optional[str] = None


class SettingsOptimizer:
    """Analyzes and optimizes Claude Code permission settings."""

    DANGEROUS_PATTERNS = {
        "Bash(*:*)",
        "Read(/*)",
        "Write(/*)",
        "Edit(/*)",
        "Bash(rm:*)",
        "Bash(sudo:*)",
        "Skill(*)",
    }

    def __init__(self, global_path: Optional[Path] = None, project_path: Optional[Path] = None):
        self.global_path = global_path or Path.home() / ".claude" / "settings.json"
        self.project_path = project_path
        if self.project_path is None:
            self.project_path = Path.cwd() / ".claude" / "settings.local.json"

        self.global_permissions: Set[str] = set()
        self.project_permissions: Set[str] = set()
        self.project_sandbox_network_allow: Set[str] = set()
        self.issues: List[Issue] = []

    def load_settings(self) -> bool:
        try:
            if self.global_path.exists():
                with open(self.global_path, "r") as f:
                    global_data = json.load(f)
                    self.global_permissions = set(
                        global_data.get("permissions", {}).get("allow", [])
                    )

            if self.project_path.exists():
                with open(self.project_path, "r") as f:
                    project_data = json.load(f)
                    self.project_permissions = set(
                        project_data.get("permissions", {}).get("allow", [])
                    )
                    sandbox = project_data.get("sandbox", {})
                    network_perms = sandbox.get("permissions", {}).get("network", {})
                    self.project_sandbox_network_allow = set(network_perms.get("allow", []))

            return bool(self.global_permissions or self.project_permissions)

        except Exception:
            return False

    def is_dangerous(self, pattern: str) -> bool:
        return pattern in self.DANGEROUS_PATTERNS

    def is_overly_specific(self, pattern: str) -> Tuple[bool, Optional[str]]:
        if not pattern.startswith("Bash(") or not pattern.endswith(")"):
            return False, None
        args = pattern[5:-1]
        if ":*" in args or args == "*:*":
            return False, None
        if " " in args:
            base_cmd = args.split()[0]
            return True, f"Bash({base_cmd}:*)"
        return False, None

    def extract_webfetch_domain(self, pattern: str) -> Optional[str]:
        match = re.match(r"^WebFetch\(domain:([^)]+)\)$", pattern)
        return match.group(1) if match else None

    def is_pattern_subset(self, specific: str, general: str) -> bool:
        spec_tool = specific.split("(")[0] if "(" in specific else specific
        gen_tool = general.split("(")[0] if "(" in general else general

        if spec_tool != gen_tool:
            return False
        if "(" not in general:
            return True
        if "(" not in specific:
            return False

        spec_args = specific[specific.index("(") + 1 : -1] if specific.endswith(")") else ""
        gen_args = general[general.index("(") + 1 : -1] if general.endswith(")") else ""

        if spec_args == gen_args:
            return True
        if gen_args == "*:*":
            return True
        if gen_args == "domain:*" and spec_args.startswith("domain:"):
            return True
        if gen_args.endswith(":*"):
            base_cmd = gen_args[:-2]
            if spec_args == base_cmd or spec_args.startswith(base_cmd + " ") or spec_args.startswith(base_cmd + ":"):
                return True
        if spec_tool in ["Read", "Write", "Edit"]:
            if gen_args == "/*":
                return True
            if gen_args.endswith("*") and spec_args.startswith(gen_args[:-1]):
                return True

        return False

    def is_redundant(self, perm: Permission) -> Optional[Permission]:
        if perm.location != "Project":
            return None
        for global_perm in self.global_permissions:
            if self.is_pattern_subset(perm.pattern, global_perm):
                return Permission(global_perm, "Global")
        return None

    def should_migrate_to_sandbox(self, perm: Permission) -> Optional[str]:
        if perm.location != "Project":
            return None
        domain = self.extract_webfetch_domain(perm.pattern)
        if not domain:
            return None
        covered = any(
            self.is_pattern_subset(perm.pattern, gp) for gp in self.global_permissions
        )
        if not covered:
            return None
        if domain in self.project_sandbox_network_allow:
            return None
        return domain

    def analyze(self) -> Dict[IssueType, List[Issue]]:
        self.issues = []

        for pattern in self.global_permissions:
            perm = Permission(pattern, "Global")
            if self.is_dangerous(pattern):
                self.issues.append(Issue(perm, IssueType.DANGEROUS, "Allows unrestricted access"))
            else:
                is_specific, suggestion = self.is_overly_specific(pattern)
                if is_specific:
                    self.issues.append(Issue(perm, IssueType.SPECIFIC, "Hardcoded arguments should be generalized", suggestion=suggestion))
                else:
                    self.issues.append(Issue(perm, IssueType.GOOD, ""))

        for pattern in self.project_permissions:
            perm = Permission(pattern, "Project")
            if self.is_dangerous(pattern):
                self.issues.append(Issue(perm, IssueType.DANGEROUS, "Allows unrestricted access"))
                continue
            migrate_domain = self.should_migrate_to_sandbox(perm)
            if migrate_domain:
                covered_by = self.is_redundant(perm)
                self.issues.append(Issue(perm, IssueType.MIGRATE_TO_SANDBOX, "Redundant for WebFetch but needed for Bash network access", covered_by=covered_by, migrate_domain=migrate_domain))
                continue
            covered_by = self.is_redundant(perm)
            if covered_by:
                self.issues.append(Issue(perm, IssueType.REDUNDANT, "Covered by global permission", covered_by=covered_by))
                continue
            is_specific, suggestion = self.is_overly_specific(pattern)
            if is_specific:
                self.issues.append(Issue(perm, IssueType.SPECIFIC, "Hardcoded arguments should be generalized", suggestion=suggestion))
            else:
                self.issues.append(Issue(perm, IssueType.GOOD, ""))

        grouped: Dict[IssueType, List[Issue]] = {t: [] for t in IssueType}
        for issue in self.issues:
            grouped[issue.issue_type].append(issue)
        return grouped

    def check(self, mode: str, grouped: Dict[IssueType, List[Issue]]) -> bool:
        """Return True if check passes, False if issues found."""
        if mode == "dangerous":
            return not grouped[IssueType.DANGEROUS]
        elif mode == "clean":
            return not grouped[IssueType.REDUNDANT] and not grouped[IssueType.MIGRATE_TO_SANDBOX]
        return True

    def auto_fix(self, grouped: Dict[IssueType, List[Issue]]) -> bool:
        redundant = grouped[IssueType.REDUNDANT]
        migrate = grouped[IssueType.MIGRATE_TO_SANDBOX]

        if not redundant and not migrate:
            return True

        project_perms = self.project_permissions.copy()
        sandbox_network = self.project_sandbox_network_allow.copy()

        for issue in migrate:
            project_perms.discard(issue.permission.pattern)
            if issue.migrate_domain:
                sandbox_network.add(issue.migrate_domain)

        for issue in redundant:
            project_perms.discard(issue.permission.pattern)

        # Create backup
        if self.project_path.exists():
            backup_path = self.project_path.with_suffix(self.project_path.suffix + ".bak")
            try:
                shutil.copy2(self.project_path, backup_path)
            except Exception:
                pass

        sandbox_arg = sandbox_network if migrate else None
        return self._save_settings(project_perms, sandbox_arg)

    def _save_settings(self, project_perms: Set[str],
                       sandbox_network_allow: Optional[Set[str]] = None) -> bool:
        try:
            if self.project_path.exists():
                with open(self.project_path, "r") as f:
                    project_data = json.load(f)
                if "permissions" not in project_data:
                    project_data["permissions"] = {}
                project_data["permissions"]["allow"] = sorted(list(project_perms))
                if sandbox_network_allow is not None:
                    if "sandbox" not in project_data:
                        project_data["sandbox"] = {}
                    if "permissions" not in project_data["sandbox"]:
                        project_data["sandbox"]["permissions"] = {}
                    if "network" not in project_data["sandbox"]["permissions"]:
                        project_data["sandbox"]["permissions"]["network"] = {}
                    project_data["sandbox"]["permissions"]["network"]["allow"] = sorted(list(sandbox_network_allow))
                with open(self.project_path, "w") as f:
                    json.dump(project_data, f, indent=2)
                    f.write("\n")
            return True
        except Exception:
            return False
