"""Repo dataclass — represents a git repository on disk."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Repo:
    """A git repository on disk with lazy-cached properties."""

    path: Path
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_python(self) -> bool:
        if "is_python" not in self._cache:
            self._cache["is_python"] = self._detect_python()
        return self._cache["is_python"]

    @property
    def github_repo(self) -> Optional[str]:
        if "github_repo" not in self._cache:
            self._cache["github_repo"] = self._extract_github_repo()
        return self._cache["github_repo"]

    @property
    def has_workflows(self) -> bool:
        if "has_workflows" not in self._cache:
            wf_dir = self.path / ".github" / "workflows"
            self._cache["has_workflows"] = wf_dir.is_dir() and any(
                f.suffix in (".yml", ".yaml") for f in wf_dir.iterdir()
            )
        return self._cache["has_workflows"]

    @property
    def has_ci_workflow(self) -> bool:
        if "has_ci_workflow" not in self._cache:
            self._cache["has_ci_workflow"] = self._detect_ci_workflow()
        return self._cache["has_ci_workflow"]

    @property
    def has_pyproject(self) -> bool:
        return (self.path / "pyproject.toml").is_file()

    @property
    def has_version(self) -> bool:
        """Check if pyproject.toml has a project version."""
        if "has_version" not in self._cache:
            self._cache["has_version"] = self._check_pyproject_field("version")
        return self._cache["has_version"]

    def _detect_ci_workflow(self) -> bool:
        wf_dir = self.path / ".github" / "workflows"
        if not wf_dir.is_dir():
            return False
        for wf_file in wf_dir.iterdir():
            if wf_file.suffix not in (".yml", ".yaml"):
                continue
            try:
                content = wf_file.read_text(encoding="utf-8", errors="replace")
                if re.search(r"tsilva/\.github/.*/(test|release|ci)\.yml|pytest", content):
                    return True
            except Exception:
                continue
        return False

    def _detect_python(self) -> bool:
        indicators = ["setup.py", "requirements.txt", "setup.cfg", "Pipfile"]
        for f in indicators:
            if (self.path / f).is_file():
                return True
        if self.has_pyproject:
            return True
        py_files = [
            p
            for p in self.path.rglob("*.py")
            if not p.name.startswith("test_")
            and ".venv" not in p.parts
            and "node_modules" not in p.parts
        ]
        return len(py_files) > 2

    def _extract_github_repo(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.path), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            return parse_github_remote(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _check_pyproject_field(self, field_name: str) -> bool:
        pyproject = self.path / "pyproject.toml"
        if not pyproject.is_file():
            return False
        try:
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return bool(data.get("project", {}).get(field_name, ""))
        except Exception:
            return False

    @staticmethod
    def discover(repos_dir: Path, filter_pattern: str = "") -> list[Repo]:
        repos = []
        if not repos_dir.is_dir():
            return repos
        for child in sorted(repos_dir.iterdir()):
            if not child.is_dir():
                continue
            if not (child / ".git").is_dir():
                continue
            if filter_pattern and filter_pattern not in child.name:
                continue
            repos.append(Repo(path=child))
        return repos


def parse_github_remote(url: str) -> Optional[str]:
    """Parse owner/repo from a git remote URL (HTTPS or SSH)."""
    # SSH: git@github.com:owner/repo.git
    m = re.match(r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    # HTTPS: https://github.com/owner/repo.git
    m = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    return None
