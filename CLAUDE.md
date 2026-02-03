# CLAUDE.md

## Repository Purpose

Shared GitHub Actions reusable workflows for the `tsilva` GitHub organization. Caller repositories reference workflows from this repo to standardize CI/CD across projects.

## Architecture

Modular reusable workflows triggered via `workflow_call`. Each workflow handles a single concern and can be called independently. A composed `release.yml` chains them together for the common release flow.

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

- **Inputs:** `python-version` (string, default `"3.12"`)
- **Timeout:** 10 minutes
- Gracefully skips when no tests are found (pytest exit code 5)

### `release.yml` (composer)

Chains the above workflows together. Maintains the same interface as before.

#### Inputs

- `publish_to_pypi` (boolean, default: `true`) — controls whether to build/publish to PyPI or create a release without artifacts

#### Secrets

- `GITHUB_TOKEN` — used for creating GitHub releases (provided automatically)

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

Run PII scanning on PRs:

```yaml
on:
  pull_request:

jobs:
  pii-scan:
    uses: tsilva/.github/.github/workflows/pii-scan.yml@main
```

Run CI checks on PRs:

```yaml
on:
  pull_request:

jobs:
  test:
    uses: tsilva/.github/.github/workflows/test.yml@main
```

### Dependabot

Caller repos can add `.github/dependabot.yml` to keep GitHub Actions up to date:

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

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
