<div align="center">
  <img src="logo.png" alt=".github" width="512"/>

  # .github

  ⚙️ Shared reusable GitHub Actions workflows for the `tsilva` organization — standardized CI/CD across every repo

  [Workflows](#-workflows) · [Usage](#-usage) · [Pre-commit Hook](#-pre-commit-hook)
</div>

## ✨ Features

- 🔄 **Modular workflows** — each handles a single concern, composable together
- 📦 **PyPI publishing** — build, release, and publish via trusted publishing
- 🏷️ **Auto-tagging** — version extracted from `pyproject.toml`, skips existing tags
- 🛡️ **Secret scanning** — detect credentials and secrets using [gitleaks](https://github.com/gitleaks/gitleaks)
- 🔒 **Pre-commit hook** — run gitleaks locally before pushing
- 🧪 **Testing** — pytest via reusable workflow
- 🎯 **One-line integration** — `uses: tsilva/.github/...@main` and `secrets: inherit`

## 📋 Workflows

| Workflow | Purpose | Key Details |
|----------|---------|-------------|
| `release.yml` | Composed release flow | Chains test + scan + publish/release |
| `publish-pypi.yml` | Build, tag, release, publish | Uses `uv build` + trusted publishing |
| `create-release.yml` | Tag + GitHub release (no PyPI) | For non-Python repos |
| `test.yml` | Run tests | Uses pytest via uv |
| `pii-scan.yml` | Scan for credentials/secrets | Uses gitleaks-action v2 |

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

## 🚀 Usage

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
  test:
    uses: tsilva/.github/.github/workflows/test.yml@main
  pii-scan:
    uses: tsilva/.github/.github/workflows/pii-scan.yml@main
```

## 🔒 Pre-commit Hook

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

Requires Go installed locally (gitleaks is built from source by pre-commit).

## 🛠️ Scripts

All scripts should be run from the `.github` repo directory, using `..` to reference sibling repos.

### `set-secret-all-repos.sh`

Sets a GitHub repository secret for all git repos in a specified directory.

```bash
# Run from the .github repo directory
./scripts/set-secret-all-repos.sh .. PAT_TOKEN "$MY_PAT"

# Dry run (preview without making changes)
./scripts/set-secret-all-repos.sh --dry-run .. PAT_TOKEN "$MY_PAT"
```

**Features:**
- Validates inputs before proceeding
- Skips non-git directories
- Handles both HTTPS and SSH remote URL formats
- Provides summary at the end (X succeeded, Y failed, Z skipped)

Requires [GitHub CLI](https://cli.github.com/) (`gh`) to be installed and authenticated.

### `sync-repo-descriptions.sh`

Syncs GitHub repo descriptions from README.md tagline or `pyproject.toml` for all repos.

**Priority:** README.md tagline (first paragraph line) → `pyproject.toml` description

```bash
# Run from the .github repo directory
./scripts/sync-repo-descriptions.sh ..

# Dry run (preview without making changes)
./scripts/sync-repo-descriptions.sh --dry-run ..
```

**Features:**
- Extracts tagline from README.md (skips headers, badges, frontmatter, HTML)
- Falls back to `pyproject.toml` description if no README tagline found
- Only updates if description differs (shows "already in sync" otherwise)
- Requires Python 3.11+ (uses `tomllib`)
- Provides summary at the end (X updated, Y in sync, Z failed, W skipped)

Requires [GitHub CLI](https://cli.github.com/) (`gh`) to be installed and authenticated.

## ⚙️ Requirements

Caller repos need:
- `pyproject.toml` with `version` field (and `description` for script-based sync)
- `pypi` environment configured (for PyPI publishing with trusted publishing)

## 📄 License

MIT
