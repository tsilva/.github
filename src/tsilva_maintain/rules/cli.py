"""CLI project rules (build backend, versioning, release workflow, PyPI metadata)."""

import re

from tsilva_maintain.rules import Category, CheckResult, FixOutcome, Rule, Status
from tsilva_maintain.templates import load_template


class CliBuildBackendRule(Rule):
    id = "CLI_BUILD_BACKEND"
    name = "CLI projects must use hatchling"
    category = Category.PYTHON

    def applies_to(self, repo):
        return repo.is_cli

    def check(self, repo):
        try:
            import tomllib

            with open(repo.path / "pyproject.toml", "rb") as f:
                data = tomllib.load(f)
            backend = data.get("build-system", {}).get("build-backend", "")
            if backend == "hatchling.build":
                return CheckResult(Status.PASS)
            return CheckResult(
                Status.FAIL,
                f"Build backend is {backend!r}, expected 'hatchling.build'",
            )
        except Exception as e:
            return CheckResult(Status.FAIL, f"Cannot read build-system: {e}")


class CliVersionRule(Rule):
    id = "CLI_VERSION"
    name = "CLI projects must define a version"
    category = Category.PYTHON

    def applies_to(self, repo):
        return repo.is_cli

    def check(self, repo):
        if repo.has_version:
            return CheckResult(Status.PASS)
        return CheckResult(
            Status.FAIL,
            "CLI project missing version (static or dynamic)",
        )


class CliReleaseWorkflowRule(Rule):
    id = "CLI_RELEASE_WORKFLOW"
    name = "CLI projects must have a release workflow with PyPI publishing"
    category = Category.CICD

    def applies_to(self, repo):
        return repo.is_cli and repo.has_version

    def check(self, repo):
        wf_dir = repo.path / ".github" / "workflows"
        if not wf_dir.is_dir():
            return CheckResult(Status.FAIL, "No .github/workflows directory")

        for wf_file in wf_dir.iterdir():
            if wf_file.suffix not in (".yml", ".yaml"):
                continue
            try:
                content = wf_file.read_text(encoding="utf-8", errors="replace")
                if re.search(r"publish-pypi\.yml|release\.yml@main", content):
                    return CheckResult(Status.PASS)
            except Exception:
                continue

        return CheckResult(
            Status.FAIL,
            "No release workflow with PyPI publishing found",
        )

    def fix(self, repo, *, dry_run=False):
        wf_dir = repo.path / ".github" / "workflows"

        # Re-check in case already present
        if wf_dir.is_dir():
            for wf_file in wf_dir.iterdir():
                if wf_file.suffix not in (".yml", ".yaml"):
                    continue
                try:
                    content = wf_file.read_text(encoding="utf-8", errors="replace")
                    if re.search(r"publish-pypi\.yml|release\.yml@main", content):
                        return FixOutcome(FixOutcome.ALREADY_OK)
                except Exception:
                    continue

        if dry_run:
            return FixOutcome(FixOutcome.FIXED, "Would create .github/workflows/release.yml")

        try:
            wf_dir.mkdir(parents=True, exist_ok=True)
            template = load_template("release.yml")
            (wf_dir / "release.yml").write_text(template, encoding="utf-8")
            return FixOutcome(FixOutcome.FIXED, "Created .github/workflows/release.yml")
        except Exception as e:
            return FixOutcome(FixOutcome.FAILED, str(e))


class CliPypiReadyRule(Rule):
    id = "CLI_PYPI_READY"
    name = "CLI projects should have PyPI metadata"
    category = Category.PYTHON

    _REQUIRED_FIELDS = ("description", "license", "requires-python")

    def applies_to(self, repo):
        return repo.is_cli

    def check(self, repo):
        try:
            import tomllib

            with open(repo.path / "pyproject.toml", "rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})

            missing = []
            for field in self._REQUIRED_FIELDS:
                if not project.get(field):
                    missing.append(field)
            if not project.get("urls"):
                missing.append("[project.urls]")

            if not missing:
                return CheckResult(Status.PASS)
            return CheckResult(
                Status.FAIL,
                f"Missing PyPI metadata: {', '.join(missing)}",
            )
        except Exception as e:
            return CheckResult(Status.FAIL, f"Cannot read pyproject.toml: {e}")
