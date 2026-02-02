# CLAUDE.md

## Repository Purpose

Shared GitHub Actions reusable workflows for the `tsilva` GitHub organization. Caller repositories reference workflows from this repo to standardize CI/CD across projects.

## Architecture

Single reusable workflow (`release.yml`) triggered via `workflow_call`. No standalone workflows — everything is designed to be called from other repos.

## Release Workflow (`.github/workflows/release.yml`)

### Inputs

- `publish_to_pypi` (boolean, default: `true`) — controls whether to build/publish to PyPI or create a release without artifacts

### Secrets

- `PAT_TOKEN` — used to update the caller repo's GitHub description via `gh repo edit`
- `GITHUB_TOKEN` — used for creating GitHub releases (provided automatically)

### Environment

- Conditionally sets the `pypi` environment when `publish_to_pypi` is true (for trusted publishing)

### Flow

1. Reads version from `pyproject.toml`
2. Updates repo description from `pyproject.toml`
3. Checks if the version tag already exists (skips release if so)
4. If `publish_to_pypi`: builds with `uv build`, creates release with dist artifacts, publishes to PyPI via trusted publishing
5. If not `publish_to_pypi`: creates release without artifacts

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

## Maintenance

README.md must be kept up to date with any significant project changes.
