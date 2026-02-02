# CLAUDE.md

## Repository Purpose

Shared GitHub Actions reusable workflows for the `tsilva` GitHub organization. Caller repositories reference workflows from this repo to standardize CI/CD across projects.

## Architecture

Modular reusable workflows triggered via `workflow_call`. Each workflow handles a single concern and can be called independently. A composed `release.yml` chains them together for the common release flow.

## Workflows

### `sync-repo-description.yml`

Reads `description` from `pyproject.toml` and updates the GitHub repo description.

- **Secrets:** `PAT_TOKEN`

### `publish-pypi.yml`

Extracts version from `pyproject.toml`, checks if tag exists, builds with `uv`, creates a GitHub release with artifacts, and publishes to PyPI via trusted publishing.

- **Permissions:** `contents: write`, `id-token: write`
- **Environment:** `pypi`

### `create-release.yml`

Extracts version from `pyproject.toml`, checks if tag exists, and creates a GitHub release without artifacts.

- **Permissions:** `contents: write`

### `pii-scan.yml`

Scans repository files for credentials and sensitive data (PII). Embeds a pure-Python scanner inline — no external dependencies.

- **Inputs:**
  - `severity_threshold` (string, default: `"high"`) — minimum severity to fail (`critical`, `high`, `medium`)
  - `respect_gitignore` (boolean, default: `true`)
- **Detected patterns:** AWS keys, GitHub tokens, private keys, database URLs, Stripe keys, Slack webhooks, JWTs, hardcoded passwords/secrets
- **Exit behavior:** Fails the workflow if findings meet or exceed the severity threshold
- **Output:** JSON results to stdout + formatted table in GitHub Step Summary

### `release.yml` (composer)

Chains the above workflows together. Maintains the same interface as before.

#### Inputs

- `publish_to_pypi` (boolean, default: `true`) — controls whether to build/publish to PyPI or create a release without artifacts

#### Secrets

- `PAT_TOKEN` — used to update the caller repo's GitHub description via `gh repo edit`
- `GITHUB_TOKEN` — used for creating GitHub releases (provided automatically)

#### Flow

1. Calls `pii-scan.yml` to scan for credentials and secrets
2. Calls `sync-repo-description.yml` to update repo description
3. If `publish_to_pypi`: calls `publish-pypi.yml`
4. If not `publish_to_pypi`: calls `create-release.yml`

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

Individual workflows can also be called directly:

```yaml
jobs:
  sync:
    uses: tsilva/.github/.github/workflows/sync-repo-description.yml@main
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

With custom threshold:

```yaml
  pii-scan:
    uses: tsilva/.github/.github/workflows/pii-scan.yml@main
    with:
      severity_threshold: critical
```

## Maintenance

README.md must be kept up to date with any significant project changes.
