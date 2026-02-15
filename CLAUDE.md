# CLAUDE.md

## Repository Purpose

Shared GitHub Actions reusable workflows and org-wide maintenance tooling for the `tsilva` GitHub organization. Caller repositories reference workflows from this repo to standardize CI/CD across projects. The Python CLI (`gitguard`) audits and enforces repo compliance standards.

## Architecture

### Workflows

Modular reusable workflows triggered via `workflow_call`. Each workflow handles a single concern and can be called independently. A composed `release.yml` chains them together for the common release flow.

### Python CLI (`gitguard`)

The primary maintenance tool. A Python package in `src/gitguard/` installable via `uv tool install` or `uv pip install -e .`. Each compliance rule is a self-contained class in `src/gitguard/rules/` with `check()` and `fix()` methods, auto-discovered via `pkgutil`.

Commands: `gitguard [repos-dir]` (clone missing repos, fetch updates, check+fix), `gitguard --dry-run` (preview), `gitguard commit` (AI-assisted commit+push), `gitguard report`

### Scripts

Only `scripts/set-secret-all-repos.sh` remains (no Python replacement). It depends on `scripts/lib/style.sh` and `scripts/lib/common.sh`.

### Skills

Skills in `.claude/skills/` provide AI-dependent maintenance operations:

- `maintain-repos` — orchestrator: uses `gitguard` CLI for audit/fix, delegates to AI skills for remaining issues

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

## Python CLI (`gitguard`)

### Installation

```bash
uv pip install -e .           # development
uv tool install gitguard  # global CLI
```

### Commands

```
gitguard [repos-dir] [-f PAT] [-j|--json] [-n|--dry-run] [--rule ID] [--category CAT]
gitguard commit [repos-dir] [-f PAT] [-n|--dry-run]
gitguard report taglines|tracked-ignored [repos-dir] [-f PAT]
```

Running with no flags clones missing repos, fetches updates for clean repos, then performs a single-pass check+fix cycle: each rule is checked, and if it fails, auto-fixed and re-verified. Dirty repos skip fetch but still have rules applied. Use `--dry-run` to preview what would be cloned/fixed without modifying anything. The `commit` subcommand finds dirty repos, generates AI commit messages, and prompts for interactive approval before committing and pushing.

### Package Structure

- `src/gitguard/cli.py` — argparse entry point
- `src/gitguard/engine.py` — RuleRunner: single-pass check → fix → verify per rule
- `src/gitguard/commands/commit.py` — interactive AI-assisted commit & push
- `src/gitguard/repo.py` — Repo dataclass with lazy-cached properties
- `src/gitguard/rules/` — one file per compliance rule (24 total), auto-discovered via `pkgutil`
- `src/gitguard/rules/__init__.py` — Rule ABC, Status, Category, CheckResult, FixOutcome
- `src/gitguard/rules/_registry.py` — auto-discovery + dependency-aware ordering
- `src/gitguard/settings_optimizer.py` — Claude Code settings analyzer (from `scripts/settings_optimizer.py`)
- `src/gitguard/tagline.py` — README tagline extractor (from `scripts/lib/extract_tagline.py`)
- `src/gitguard/templates/` — LICENSE, CLAUDE.md, dependabot.yml, pre-commit-config.yaml

### Adding a New Rule

Create `src/gitguard/rules/my_rule.py`:

```python
from gitguard.rules import Category, CheckResult, Rule, Status

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

## Repository Templates

Three GitHub template repos provide pre-compliant starting points for new projects. Use `gh repo create` with `--template` to bootstrap:

```bash
# Python CLI tool (published to PyPI)
gh repo create tsilva/my-new-tool --template tsilva/template-python-cli --clone

# Python sandbox/learning repo
gh repo create tsilva/sandbox-whatever --template tsilva/template-python-sandbox --clone

# Non-Python project
gh repo create tsilva/my-app --template tsilva/template-generic --clone
```

| Template | Use case | Key files |
|----------|----------|-----------|
| `template-python-cli` | CLI tools published to PyPI | pyproject.toml (hatchling), src layout, release workflow, tests |
| `template-python-sandbox` | Learning/experimentation | Minimal pyproject.toml, no src layout, no release workflow |
| `template-generic` | Non-Python repos | No Python files, dependabot for github-actions only |

All templates include: LICENSE (MIT), CLAUDE.md, .gitignore, .github/dependabot.yml, .pre-commit-config.yaml (gitleaks), .claude/settings.local.json (sandbox enabled).

## Maintenance

README.md must be kept up to date with any significant project changes.
