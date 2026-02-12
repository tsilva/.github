# CLAUDE.md

## Repository Purpose

Shared GitHub Actions reusable workflows and org-wide maintenance tooling for the `tsilva` GitHub organization. Caller repositories reference workflows from this repo to standardize CI/CD across projects. The Python CLI (`tsilva-maintain`) audits and enforces repo compliance standards.

## Architecture

### Workflows

Modular reusable workflows triggered via `workflow_call`. Each workflow handles a single concern and can be called independently. A composed `release.yml` chains them together for the common release flow.

### Python CLI (`tsilva-maintain`)

The primary maintenance tool. A Python package in `src/tsilva_maintain/` installable via `uv tool install` or `uv pip install -e .`. Each compliance rule is a self-contained class in `src/tsilva_maintain/rules/` with `check()` and `fix()` methods, auto-discovered via `pkgutil`.

Commands: `tsilva-maintain audit|fix|maintain|commit|report`

### Scripts

Only `scripts/set-secret-all-repos.sh` remains (no Python replacement). It depends on `scripts/lib/style.sh` and `scripts/lib/common.sh`.

### Skills

Skills in `.claude/skills/` provide AI-dependent maintenance operations:

- `maintain-repos` — orchestrator: uses `tsilva-maintain` CLI for audit/fix, delegates to AI skills for remaining issues

## Workflows

### `publish-pypi.yml`

Extracts version from `pyproject.toml`, checks if tag exists, builds with `uv`, creates a GitHub release with artifacts, and publishes to PyPI via trusted publishing.

- **Permissions:** `contents: write`, `id-token: write`
- **Environment:** `pypi`

### `create-release.yml`

Extracts version from `pyproject.toml`, checks if tag exists, and creates a GitHub release without artifacts.

- **Permissions:** `contents: write`

### `pii-scan.yml`

Scans repository for credentials and secrets using [gitleaks-action v2](https://github.com/gitleaks/gitleaks-action).

- Uses `fetch-depth: 0` to scan full git history
- Produces GitHub Step Summary output natively
- Configured via `.gitleaks.toml` in caller repos (optional)

### `test.yml`

Runs tests with [pytest](https://docs.pytest.org/).

- **Inputs:** `python-version` (string, default `"3.12"`), `pytest-args` (string, default `""`)
- **Timeout:** 10 minutes
- Gracefully skips when no tests are found (pytest exit code 5)

### `ci.yml`

Composes `test.yml` + `pii-scan.yml` in parallel for PR-time checks. Caller repos use a single `uses:` line instead of composing manually.

- **Inputs:** `python-version` (string, default `"3.12"`), `pytest-args` (string, default `""`)

### `audit.yml`

Scheduled compliance audit of all org repos. Runs weekly (Monday 08:00 UTC) + on-demand via `workflow_dispatch`. Clones all non-archived repos, runs `tsilva-maintain audit --json`, posts results to GitHub Step Summary, uploads JSON artifact.

### `release.yml` (composer)

Chains the above workflows together.

#### Inputs

- `publish_to_pypi` (boolean, default: `true`) — controls whether to build/publish to PyPI or create a release without artifacts

#### Flow

1. Runs `test.yml` and `pii-scan.yml` in parallel
2. If `publish_to_pypi`: calls `publish-pypi.yml`
3. If not `publish_to_pypi`: calls `create-release.yml`

### Caller Usage

```yaml
on:
  push:
    branches: [main]

jobs:
  release:
    uses: tsilva/.github/.github/workflows/release.yml@main
    secrets: inherit
```

Set `publish_to_pypi: false` for non-Python repos:

```yaml
    uses: tsilva/.github/.github/workflows/release.yml@main
    with:
      publish_to_pypi: false
    secrets: inherit
```

## Python CLI (`tsilva-maintain`)

### Installation

```bash
uv pip install -e .           # development
uv tool install tsilva-maintain  # global CLI
```

### Commands

```
tsilva-maintain audit <repos-dir> [--filter PAT] [--json] [--rule ID] [--category CAT]
tsilva-maintain fix <repos-dir> [--filter PAT] [--dry-run] [--rule ID]
tsilva-maintain maintain <repos-dir> [--filter PAT] [--dry-run]
tsilva-maintain commit <repos-dir> [--filter PAT] [--dry-run]
tsilva-maintain report taglines|tracked-ignored <repos-dir> [--filter PAT]
```

### Package Structure

- `src/tsilva_maintain/cli.py` — argparse entry point
- `src/tsilva_maintain/engine.py` — RuleRunner: discover → check → fix → report
- `src/tsilva_maintain/repo.py` — Repo dataclass with lazy-cached properties
- `src/tsilva_maintain/rules/` — one file per compliance rule (24 total), auto-discovered via `pkgutil`
- `src/tsilva_maintain/rules/__init__.py` — Rule ABC, Status, Category, CheckResult, FixOutcome
- `src/tsilva_maintain/rules/_registry.py` — auto-discovery + canonical ordering
- `src/tsilva_maintain/settings_optimizer.py` — Claude Code settings analyzer (from `scripts/settings_optimizer.py`)
- `src/tsilva_maintain/tagline.py` — README tagline extractor (from `scripts/lib/extract_tagline.py`)
- `src/tsilva_maintain/templates/` — LICENSE, CLAUDE.md, dependabot.yml, pre-commit-config.yaml

### Adding a New Rule

Create `src/tsilva_maintain/rules/my_rule.py`:

```python
from tsilva_maintain.rules import Category, CheckResult, Rule, Status

class MyRule(Rule):
    id = "MY_RULE"
    name = "Description of the rule"
    category = Category.REPO_STRUCTURE

    def check(self, repo):
        if condition:
            return CheckResult(Status.PASS)
        return CheckResult(Status.FAIL, "Failure message")
```

The rule is auto-discovered. Add its ID to `_CANONICAL_ORDER` in `rules/_registry.py` if ordering matters.

### Tests

```bash
pytest tests/
```

## Scripts

- `set-secret-all-repos.sh` — set GitHub secret across all repos (no CLI replacement)

## Pre-commit Hook

This repo provides a [pre-commit](https://pre-commit.com/) hook for running gitleaks locally.

### Caller repo setup

Add to `.pre-commit-config.yaml`:

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

## Maintenance

README.md must be kept up to date with any significant project changes.
