<div align="center">
  <img src="logo.png" alt=".github" width="512"/>

  # .github

  Shared reusable GitHub Actions workflows and org-wide maintenance tooling for the `tsilva` organization

  [Workflows](#workflows) · [CLI](#cli-gitguard) · [Usage](#usage) · [Pre-commit Hook](#pre-commit-hook)
</div>

## Features

- Modular workflows — each handles a single concern, composable together
- PyPI publishing — build, release, and publish via trusted publishing
- Auto-tagging — version extracted from `pyproject.toml`, skips existing tags
- Secret scanning — detect credentials and secrets using [gitleaks](https://github.com/gitleaks/gitleaks)
- Pre-commit hook — run gitleaks locally before pushing
- Testing — pytest via reusable workflow
- Repo compliance — audit and enforce org standards across all repos via Python CLI
- One-line integration — `uses: tsilva/.github/...@main` and `secrets: inherit`
- Repo templates — pre-compliant starting points for new projects

## Workflows

| Workflow | Purpose | Key Details |
|----------|---------|-------------|
| `release.yml` | Composed release flow | Chains test + scan + publish/release |
| `publish-pypi.yml` | Build, tag, release, publish | Uses `uv build` + trusted publishing |
| `create-release.yml` | Tag + GitHub release (no PyPI) | For non-Python repos |
| `test.yml` | Run tests | Uses pytest via uv |
| `pii-scan.yml` | Scan for credentials/secrets | Uses gitleaks-action v2 |
| `ci.yml` | PR-time checks | Composes test + pii-scan in parallel |
| `audit.yml` | Scheduled compliance audit | Weekly + on-demand, all org repos |

### `release.yml` (Composer)

The main entry point for most repos. Chains individual workflows together.

**Inputs:**
- `publish_to_pypi` (boolean, default: `true`) — set `false` for non-Python repos

**Flow:**
1. Runs tests and PII scan in parallel
2. If `publish_to_pypi`: builds with `uv`, creates release with artifacts, publishes to PyPI
3. If not: creates a GitHub release without artifacts

### `pii-scan.yml`

Scans repository for credentials and secrets using [gitleaks-action v2](https://github.com/gitleaks/gitleaks-action). Scans full git history and produces GitHub Step Summary output natively.

Caller repos can customize detection rules via a `.gitleaks.toml` config file.

## CLI (`gitguard`)

A Python CLI that replaces the legacy bash scripts. Each compliance rule is a self-contained class with `check()` and `fix()` methods, auto-discovered at runtime.

### Installation

```bash
uv pip install -e .           # development
uv tool install gitguard  # global CLI
```

### Commands

```bash
# Default — single-pass check + fix cycle
gitguard ~/repos/tsilva
gitguard ~/repos/tsilva --filter myrepo   # only repos matching pattern
gitguard ~/repos/tsilva --rule README_EXISTS

# Dry run — preview what would be fixed without modifying files
gitguard ~/repos/tsilva --dry-run
gitguard ~/repos/tsilva --dry-run --json  # JSON output for CI

# Commit — AI-assisted commit & push for dirty repos
gitguard commit ~/repos/tsilva
gitguard commit ~/repos/tsilva --filter myrepo
gitguard commit ~/repos/tsilva --dry-run   # show dirty repos only

# Report — generate reports
gitguard report taglines ~/repos/tsilva
gitguard report tracked-ignored ~/repos/tsilva
```

### Adding a New Rule

Create one Python file in `src/gitguard/rules/`:

```python
from gitguard.rules import Category, CheckResult, Rule, Status

class MyRule(Rule):
    id = "MY_RULE"
    name = "Description of the rule"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        if (repo.path / "expected_file").is_file():
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "expected_file not found")
```

The rule is auto-discovered — no registration needed.

### Compliance Rules

**Repository Structure**

| ID | Rule |
|----|------|
| `README_EXISTS` | README.md must exist |
| `README_CURRENT` | README must have no placeholders, be >100 chars, and include install/usage sections |
| `README_LICENSE` | README must reference the license |
| `README_CI_BADGE` | README must have a CI badge (repos with workflows) |
| `README_LOGO` | README must reference the project logo |
| `LOGO_EXISTS` | A logo file must exist in a standard location |
| `LICENSE_EXISTS` | LICENSE file must exist |
| `GITIGNORE_EXISTS` | .gitignore must exist |
| `GITIGNORE_COMPLETE` | .gitignore must include essential patterns (.env, .DS_Store, node_modules/, __pycache__/, *.pyc, .venv/) |
| `TRACKED_IGNORED` | No tracked files should match .gitignore patterns |
| `REPO_DESCRIPTION` | GitHub repo description must match README tagline |

**Dependency Management**

| ID | Rule |
|----|------|
| `DEPENDABOT_EXISTS` | .github/dependabot.yml must exist |

**Python Projects**

| ID | Rule |
|----|------|
| `PYTHON_PYPROJECT` | Python projects must use pyproject.toml |
| `PYTHON_MIN_VERSION` | pyproject.toml must specify requires-python |

**CI/CD**

| ID | Rule |
|----|------|
| `CI_WORKFLOW` | Python repos must have a CI workflow |
| `RELEASE_WORKFLOW` | Versioned projects must have a release workflow |

**Claude Code Configuration**

| ID | Rule |
|----|------|
| `CLAUDE_MD_EXISTS` | CLAUDE.md must exist |
| `CLAUDE_SANDBOX` | Claude Code sandbox must be enabled |
| `SETTINGS_DANGEROUS` | No dangerous permission patterns in Claude settings |
| `SETTINGS_CLEAN` | No redundant permissions or unmigrated WebFetch domains |

**Security**

| ID | Rule |
|----|------|
| `PII_SCAN` | CI must include gitleaks secret scanning |
| `PRECOMMIT_GITLEAKS` | Pre-commit must include gitleaks hook |

**Git Hygiene**

| ID | Rule |
|----|------|
| `DEFAULT_BRANCH` | Default branch must be `main` |
| `PENDING_COMMITS` | No uncommitted changes or unpushed commits |
| `STALE_BRANCHES` | No merged or inactive (>90 days) branches |

## Repository Templates

Bootstrap new repos that are pre-compliant with org standards:

```bash
# Python CLI tool (published to PyPI)
gh repo create tsilva/my-new-tool --template tsilva/template-python-cli --clone

# Python sandbox/learning repo
gh repo create tsilva/sandbox-whatever --template tsilva/template-python-sandbox --clone

# Non-Python project
gh repo create tsilva/my-app --template tsilva/template-generic --clone
```

| Template | Use case | Includes |
|----------|----------|----------|
| `template-python-cli` | CLI tools published to PyPI | src layout, hatchling build, release workflow, tests |
| `template-python-sandbox` | Learning/experimentation | Minimal pyproject.toml, no workflows |
| `template-generic` | Non-Python repos | No Python files |

All templates include: LICENSE (MIT), CLAUDE.md, .gitignore, dependabot, pre-commit (gitleaks), Claude sandbox config.

## Usage

### Full release (Python projects)

```yaml
on:
  push:
    branches: [main]

jobs:
  release:
    uses: tsilva/.github/.github/workflows/release.yml@main
    secrets: inherit
```

### Release without PyPI

```yaml
on:
  push:
    branches: [main]

jobs:
  release:
    uses: tsilva/.github/.github/workflows/release.yml@main
    with:
      publish_to_pypi: false
    secrets: inherit
```

### CI checks on PRs

```yaml
on:
  pull_request:

jobs:
  ci:
    uses: tsilva/.github/.github/workflows/ci.yml@main
```

## Pre-commit Hook

This repo provides a [pre-commit](https://pre-commit.com/) hook for running gitleaks locally.

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/tsilva/.github
    rev: main
    hooks:
      - id: gitleaks
```

Then:

```bash
pre-commit install
pre-commit run gitleaks --all-files
```

Requires [gitleaks](https://github.com/gitleaks/gitleaks#installing) installed locally.

## Requirements

Caller repos need:
- `pyproject.toml` with `version` field (for release workflows)
- `pypi` environment configured (for PyPI publishing with trusted publishing)

CLI requires:
- Python 3.11+ — zero external dependencies (stdlib only)
- [GitHub CLI](https://cli.github.com/) (`gh`) — for repo description sync
- git — for repository operations

## License

MIT
