<div align="center">
  <img src="logo.png" alt=".github" width="512"/>

  # .github

  Shared reusable GitHub Actions workflows and org-wide maintenance tooling for the `tsilva` organization

  [Workflows](#-workflows) · [CLI](#-cli-tsilva-maintain) · [Usage](#-usage) · [Pre-commit Hook](#-pre-commit-hook)
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

## CLI (`tsilva-maintain`)

A Python CLI that replaces the legacy bash scripts. Each compliance rule is a self-contained class with `check()` and `fix()` methods, auto-discovered at runtime.

### Installation

```bash
uv pip install -e .           # development
uv tool install tsilva-maintain  # global CLI
```

### Commands

```bash
# Audit — run all 25 compliance checks
tsilva-maintain audit ~/repos/tsilva
tsilva-maintain audit --json ~/repos/tsilva
tsilva-maintain audit --filter myrepo ~/repos/tsilva
tsilva-maintain audit --rule README_EXISTS ~/repos/tsilva

# Fix — auto-fix failing checks (11 rules have auto-fixes)
tsilva-maintain fix ~/repos/tsilva
tsilva-maintain fix --dry-run ~/repos/tsilva

# Maintain — full audit → fix → verify cycle
tsilva-maintain maintain ~/repos/tsilva

# Commit — AI-assisted commit & push for dirty repos
tsilva-maintain commit ~/repos/tsilva

# Report — generate reports
tsilva-maintain report taglines ~/repos/tsilva
tsilva-maintain report tracked-ignored ~/repos/tsilva
```

### Adding a New Rule

Create one Python file in `src/tsilva_maintain/rules/`:

```python
from tsilva_maintain.rules import Category, CheckResult, Rule, Status

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

### Compliance Checks (25)

| Check | What it detects |
|-------|----------------|
| `DEFAULT_BRANCH` | Repo has a "main" branch |
| `README_EXISTS` | README.md file exists |
| `README_CURRENT` | No placeholders, adequate length, has install/usage |
| `README_LICENSE` | README mentions license |
| `README_LOGO` | README references the project logo |
| `LOGO_EXISTS` | Logo in standard locations |
| `LICENSE_EXISTS` | LICENSE/LICENSE.md/LICENSE.txt exists |
| `GITIGNORE_EXISTS` | .gitignore exists |
| `GITIGNORE_COMPLETE` | Essential patterns present |
| `CLAUDE_MD_EXISTS` | CLAUDE.md exists |
| `CLAUDE_SANDBOX` | Sandbox enabled in .claude/settings*.json |
| `DEPENDABOT_EXISTS` | .github/dependabot.yml exists |
| `PRECOMMIT_GITLEAKS` | .pre-commit-config.yaml has gitleaks hook |
| `TRACKED_IGNORED` | No tracked files matching gitignore |
| `PENDING_COMMITS` | No uncommitted changes or unpushed commits |
| `STALE_BRANCHES` | No merged or inactive (>90d) branches |
| `PYTHON_PYPROJECT` | pyproject.toml exists (Python projects only) |
| `PYTHON_MIN_VERSION` | requires-python field in pyproject.toml |
| `SETTINGS_DANGEROUS` | No dangerous permission patterns |
| `SETTINGS_CLEAN` | No redundant permissions or unmigrated WebFetch domains |
| `README_CI_BADGE` | README has CI status badge |
| `CI_WORKFLOW` | Python repos reference test.yml/release.yml/pytest |
| `RELEASE_WORKFLOW` | Versioned projects reference release.yml |
| `PII_SCAN` | CI workflows include PII scanning |
| `REPO_DESCRIPTION` | GitHub description matches README tagline |

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
