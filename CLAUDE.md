# CLAUDE.md

## Repository Purpose

Shared GitHub Actions reusable workflows and org-wide maintenance tooling for the `tsilva` GitHub organization. Caller repositories reference workflows from this repo to standardize CI/CD across projects. Maintenance scripts audit and enforce repo compliance standards.

## Architecture

### Workflows

Modular reusable workflows triggered via `workflow_call`. Each workflow handles a single concern and can be called independently. A composed `release.yml` chains them together for the common release flow.

### Scripts

Scripts in `scripts/` operate on a directory of repos. They share common infrastructure:

- `scripts/lib/style.sh` — terminal styling (colors, log functions, NO_COLOR support)
- `scripts/lib/common.sh` — argument parsing (`--dry-run`, `--filter`, `<repos-dir>`), repo discovery, GitHub remote extraction

All scripts follow the pattern: `./scripts/<name>.sh [--dry-run] [--filter PATTERN] <repos-dir>`

### Skills

Skills in `.claude/skills/` provide AI-dependent maintenance operations:

- `maintain-repos` — orchestrator: audit → sync scripts → AI fixes
- `fix-readme` — README remediation (delegates to `project-readme-author`)
- `fix-logo` — logo remediation (delegates to `project-logo-author`)

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

## Scripts

### Audit

- `audit-repos.sh` — comprehensive compliance audit (12 checks per repo, `--json` for machine output)

### Sync (safe, idempotent)

- `sync-gitignore.sh` — append missing rules from `gitignore.global`
- `sync-license.sh` — create MIT LICENSE from template
- `sync-claude-md.sh` — create minimal CLAUDE.md from template
- `sync-sandbox.sh` — enable Claude sandbox in `.claude/settings.json`
- `sync-dependabot.sh` — create `dependabot.yml` with auto-detected ecosystems
- `sync-repo-descriptions.sh` — sync GitHub descriptions from README tagline

### Reports

- `report-taglines.sh` — tabular report of repo taglines
- `check-tracked-ignored.sh` — find tracked files matching gitignore

### Utilities

- `set-secret-all-repos.sh` — set GitHub secret across all repos

### Templates

Templates used by sync scripts:

- `scripts/templates/LICENSE` — MIT license (`[year]`/`[fullname]` placeholders)
- `scripts/templates/CLAUDE.md` — minimal CLAUDE.md (`[project-name]` placeholder)
- `scripts/templates/dependabot.yml` — base dependabot config

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
