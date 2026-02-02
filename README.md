<div align="center">
  <img src="logo.png" alt=".github" width="512"/>

  # .github

  ⚙️ Shared reusable GitHub Actions workflows for the `tsilva` organization — standardized CI/CD across every repo

  [Workflows](#-workflows) · [Usage](#-usage) · [PII Scanning](#pii-scanyml)
</div>

## ✨ Features

- 🔄 **Modular workflows** — each handles a single concern, composable together
- 📦 **PyPI publishing** — build, release, and publish via trusted publishing
- 🏷️ **Auto-tagging** — version extracted from `pyproject.toml`, skips existing tags
- 📝 **Repo description sync** — keeps GitHub description in sync with `pyproject.toml`
- 🛡️ **PII scanning** — detect credentials and secrets with zero dependencies
- 🎯 **One-line integration** — `uses: tsilva/.github/...@main` and `secrets: inherit`

## 📋 Workflows

| Workflow | Purpose | Key Details |
|----------|---------|-------------|
| `release.yml` | Composed release flow | Chains sync + publish/release |
| `sync-repo-description.yml` | Sync repo description | Reads from `pyproject.toml` |
| `publish-pypi.yml` | Build, tag, release, publish | Uses `uv build` + trusted publishing |
| `create-release.yml` | Tag + GitHub release (no PyPI) | For non-Python repos |
| `pii-scan.yml` | Scan for credentials/secrets | Pure-Python, configurable severity |

### `release.yml` (Composer)

The main entry point for most repos. Chains individual workflows together.

**Inputs:**
- `publish_to_pypi` (boolean, default: `true`) — set `false` for non-Python repos

**Required secrets:**
- `PAT_TOKEN` — for updating repo description

**Flow:**
1. Runs PII scan for credentials and secrets
2. Syncs repo description from `pyproject.toml`
3. If `publish_to_pypi`: builds with `uv`, creates release with artifacts, publishes to PyPI
4. If not: creates a GitHub release without artifacts

### `pii-scan.yml`

Scans repository files for credentials and sensitive data. Embeds a pure-Python scanner inline — no external dependencies.

**Inputs:**
- `severity_threshold` (string, default: `"high"`) — minimum severity to fail (`critical`, `high`, `medium`)
- `respect_gitignore` (boolean, default: `true`)

**Detected patterns:** AWS keys, GitHub tokens, private keys, database URLs, Stripe keys, Slack webhooks, JWTs, hardcoded passwords/secrets

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

### Individual workflows

```yaml
jobs:
  sync:
    uses: tsilva/.github/.github/workflows/sync-repo-description.yml@main
    secrets: inherit
```

### PII scanning on PRs

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

## ⚙️ Requirements

Caller repos need:
- `pyproject.toml` with `version` and `description` fields
- `PAT_TOKEN` secret (for repo description updates)
- `pypi` environment configured (for PyPI publishing with trusted publishing)

## 📄 License

MIT
