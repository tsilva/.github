#!/usr/bin/env python3
"""
Claude Code Settings Optimizer

Analyzes and auto-fixes Claude Code permission settings.
Detects dangerous patterns, redundant permissions, and unmigrated WebFetch domains.

Usage:
    python3 settings_optimizer.py analyze [--project-dir DIR] [--json]
    python3 settings_optimizer.py auto-fix [--project-dir DIR]
    python3 settings_optimizer.py --check dangerous [--project-dir DIR]
    python3 settings_optimizer.py --check clean [--project-dir DIR]
"""

import json
import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# --- ANSI colors (zero external deps) ---

def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_COLOR = _use_color()

RED = "\033[0;31m" if _COLOR else ""
GREEN = "\033[0;32m" if _COLOR else ""
YELLOW = "\033[0;33m" if _COLOR else ""
BLUE = "\033[0;34m" if _COLOR else ""
MAGENTA = "\033[0;35m" if _COLOR else ""
CYAN = "\033[0;36m" if _COLOR else ""
BOLD = "\033[1m" if _COLOR else ""
NC = "\033[0m" if _COLOR else ""


# --- Domain model ---

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


# --- Analyzer ---

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

            if not self.global_permissions and not self.project_permissions:
                print(f"{YELLOW}No permissions found in settings files.{NC}", file=sys.stderr)
                return False

            return True

        except json.JSONDecodeError as e:
            print(f"{RED}Error: Invalid JSON in settings file: {e}{NC}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"{RED}Error loading settings: {e}{NC}", file=sys.stderr)
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

    # --- Reports ---

    def print_report(self, grouped: Dict[IssueType, List[Issue]]):
        print(f"\n{BOLD}=== Claude Code Settings Analysis ==={NC}\n")
        self._print_context()

        dangerous = grouped[IssueType.DANGEROUS]
        if dangerous:
            print(f"{RED}{BOLD}DANGEROUS ({len(dangerous)} found):{NC}")
            for issue in dangerous:
                print(f"  - {issue.permission.pattern} [{issue.permission.location}]")
                print(f"    Risk: {issue.reason}")
            print()

        migrate = grouped[IssueType.MIGRATE_TO_SANDBOX]
        if migrate:
            print(f"{MAGENTA}{BOLD}MIGRATE_TO_SANDBOX ({len(migrate)} found):{NC}")
            for issue in migrate:
                print(f"  - {issue.permission.pattern} [{issue.permission.location}]")
                if issue.covered_by:
                    print(f"    Covered by: {issue.covered_by.pattern} [{issue.covered_by.location}]")
                print(f"    -> Migrate '{issue.migrate_domain}' to sandbox.permissions.network.allow")
            print()

        specific = grouped[IssueType.SPECIFIC]
        if specific:
            print(f"{YELLOW}{BOLD}OVERLY SPECIFIC ({len(specific)} found):{NC}")
            for issue in specific:
                print(f"  - {issue.permission.pattern} [{issue.permission.location}]")
                if issue.suggestion:
                    print(f"    -> Suggest: {issue.suggestion}")
            print()

        redundant = grouped[IssueType.REDUNDANT]
        if redundant:
            print(f"{BLUE}{BOLD}REDUNDANT ({len(redundant)} found):{NC}")
            for issue in redundant:
                print(f"  - {issue.permission.pattern} [{issue.permission.location}]")
                if issue.covered_by:
                    print(f"    Covered by: {issue.covered_by.pattern} [{issue.covered_by.location}]")
            print()

        good = grouped[IssueType.GOOD]
        if good:
            print(f"{GREEN}{BOLD}GOOD ({len(good)} permissions){NC}")
            print()

        total_issues = len(dangerous) + len(specific) + len(redundant) + len(migrate)
        if total_issues == 0:
            print(f"{GREEN}No issues found! Your permissions are well-configured.{NC}\n")
        else:
            print(f"{BOLD}Total issues: {total_issues}{NC}\n")

    def print_json_report(self, grouped: Dict[IssueType, List[Issue]]):
        result = {
            "global_settings": str(self.global_path),
            "project_settings": str(self.project_path),
            "issues": {},
            "summary": {},
        }
        for issue_type in IssueType:
            issues = grouped[issue_type]
            result["issues"][issue_type.value] = []
            for issue in issues:
                entry = {
                    "pattern": issue.permission.pattern,
                    "location": issue.permission.location,
                    "reason": issue.reason,
                }
                if issue.suggestion:
                    entry["suggestion"] = issue.suggestion
                if issue.covered_by:
                    entry["covered_by"] = issue.covered_by.pattern
                if issue.migrate_domain:
                    entry["migrate_domain"] = issue.migrate_domain
                result["issues"][issue_type.value].append(entry)
            result["summary"][issue_type.value] = len(issues)
        print(json.dumps(result, indent=2))

    def _print_context(self):
        print(f"{CYAN}{BOLD}CONTEXT:{NC}")
        print(f"  Global settings: {self.global_path}")
        print(f"  Project settings: {self.project_path}")
        if self.project_sandbox_network_allow:
            print(f"  Sandbox network allowlist: {sorted(self.project_sandbox_network_allow)}")
        print()

    # --- Fixes ---

    def create_backup(self, filepath: Path) -> bool:
        if not filepath.exists():
            return True
        backup_path = filepath.with_suffix(filepath.suffix + ".bak")
        try:
            shutil.copy2(filepath, backup_path)
            print(f"{CYAN}Creating backup: {backup_path}{NC}")
            return True
        except Exception as e:
            print(f"{RED}Error creating backup: {e}{NC}", file=sys.stderr)
            return False

    def save_settings(self, global_perms: Set[str], project_perms: Set[str],
                      sandbox_network_allow: Optional[Set[str]] = None) -> bool:
        try:
            if self.global_path.exists():
                with open(self.global_path, "r") as f:
                    global_data = json.load(f)
                if "permissions" not in global_data:
                    global_data["permissions"] = {}
                global_data["permissions"]["allow"] = sorted(list(global_perms))
                with open(self.global_path, "w") as f:
                    json.dump(global_data, f, indent=2)
                    f.write("\n")

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

        except Exception as e:
            print(f"{RED}Error saving settings: {e}{NC}", file=sys.stderr)
            return False

    def auto_fix(self, grouped: Dict[IssueType, List[Issue]]):
        redundant = grouped[IssueType.REDUNDANT]
        migrate = grouped[IssueType.MIGRATE_TO_SANDBOX]

        if not redundant and not migrate:
            print(f"\n{GREEN}No redundant permissions or migrations needed.{NC}")
            return

        project_perms = self.project_permissions.copy()
        sandbox_network = self.project_sandbox_network_allow.copy()

        if migrate:
            print(f"\n{MAGENTA}{BOLD}Migrating {len(migrate)} domain(s) to sandbox...{NC}\n")
            for issue in migrate:
                print(f"  - Migrating: {issue.permission.pattern}")
                print(f"    -> sandbox.permissions.network.allow: {issue.migrate_domain}")
                project_perms.discard(issue.permission.pattern)
                sandbox_network.add(issue.migrate_domain)

        if redundant:
            print(f"\n{BLUE}{BOLD}Removing {len(redundant)} redundant permission(s)...{NC}\n")
            for issue in redundant:
                print(f"  - Removing: {issue.permission.pattern}")
                print(f"    (Covered by: {issue.covered_by.pattern} [{issue.covered_by.location}])")
                project_perms.discard(issue.permission.pattern)

        print(f"\n{BOLD}Creating backup...{NC}")
        self.create_backup(self.project_path)

        sandbox_arg = sandbox_network if migrate else None
        if self.save_settings(self.global_permissions, project_perms, sandbox_arg):
            total = len(redundant) + len(migrate)
            print(f"\n{GREEN}{BOLD}Fixed {total} issue(s):{NC}")
            if migrate:
                print(f"  - Migrated {len(migrate)} domain(s) to sandbox")
            if redundant:
                print(f"  - Removed {len(redundant)} redundant permission(s)")
            print()
        else:
            print(f"\n{RED}Failed to save changes.{NC}", file=sys.stderr)

    # --- Check mode (exit-code only) ---

    def check(self, mode: str, grouped: Dict[IssueType, List[Issue]]) -> int:
        """Return 0 if check passes, 1 if issues found."""
        if mode == "dangerous":
            return 1 if grouped[IssueType.DANGEROUS] else 0
        elif mode == "clean":
            has_redundant = bool(grouped[IssueType.REDUNDANT])
            has_migrate = bool(grouped[IssueType.MIGRATE_TO_SANDBOX])
            return 1 if (has_redundant or has_migrate) else 0
        else:
            print(f"{RED}Unknown check mode: {mode}{NC}", file=sys.stderr)
            return 2


def main():
    parser = argparse.ArgumentParser(
        description="Optimize Claude Code permission settings"
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["analyze", "auto-fix"],
        help="Command to execute (required unless --check is used)",
    )
    parser.add_argument(
        "--global-settings",
        type=Path,
        help="Path to global settings file (default: ~/.claude/settings.json)",
    )
    parser.add_argument(
        "--project-settings",
        type=Path,
        help="Path to project settings file",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        help="Project directory (resolves DIR/.claude/settings.local.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON report (analyze only)",
    )
    parser.add_argument(
        "--check",
        choices=["dangerous", "clean"],
        help="Lightweight check mode — exit 0 (pass) or 1 (fail)",
    )

    args = parser.parse_args()

    # Validate: need either command or --check
    if not args.command and not args.check:
        parser.error("either command (analyze/auto-fix) or --check is required")

    # Resolve project settings path
    project_path = args.project_settings
    if args.project_dir:
        project_path = args.project_dir / ".claude" / "settings.local.json"

    optimizer = SettingsOptimizer(args.global_settings, project_path)

    if not optimizer.load_settings():
        # No permissions = nothing to flag
        if args.check:
            return 0
        return 1

    grouped = optimizer.analyze()

    if args.check:
        return optimizer.check(args.check, grouped)

    if args.command == "analyze":
        if args.json_output:
            optimizer.print_json_report(grouped)
        else:
            optimizer.print_report(grouped)
    elif args.command == "auto-fix":
        optimizer.auto_fix(grouped)

    return 0


if __name__ == "__main__":
    sys.exit(main())
