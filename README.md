<div align="center">
  <img src="logo.png" alt=".github" width="512"/>

  # .github

  Shared reusable GitHub Actions workflows and org-wide maintenance tooling for the `tsilva` organization

  [Workflows](#-workflows) · [Scripts](#-scripts) · [Skills](#-skills) · [Usage](#-usage) · [Pre-commit Hook](#-pre-commit-hook)
</div>

## Features

- Modular workflows — each handles a single concern, composable together
- PyPI publishing — build, release, and publish via trusted publishing
- Auto-tagging — version extracted from `pyproject.toml`, skips existing tags
- Secret scanning — detect credentials and secrets using [gitleaks](https://github.com/gitleaks/gitleaks)
- Pre-commit hook — run gitleaks locally before pushing
- Testing — pytest via reusable workflow
- Repo compliance — audit and enforce org standards across all repos
- One-line integration — `uses: tsilva/.github/...@main` and `secrets: inherit`

## Workflows

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

## Scripts

All scripts operate on a directory of git repos. Run from the `.github` repo directory, using `..` as the repos directory.

Common options: `--dry-run` (preview without changes), `--filter PATTERN` (substring match on repo name), `--help`.

### Audit

#### `audit-repos.sh`

Comprehensive compliance audit — 14 checks per repo covering README, logo, LICENSE, .gitignore, CLAUDE.md, sandbox settings, dependabot, tracked-ignored files, Python config, and Claude settings optimization.

```bash
./scripts/audit-repos.sh ..
./scripts/audit-repos.sh --json ..         # Machine-readable output
./scripts/audit-repos.sh --filter myrepo ..
```

### Sync

Idempotent scripts that ensure standard files exist. Only create missing files — never overwrite existing ones.

| Script | Purpose |
|--------|---------|
| `sync-gitignore.sh` | Append missing rules from `gitignore.global` |
| `sync-license.sh` | Create MIT LICENSE from template |
| `sync-claude-md.sh` | Create minimal CLAUDE.md from template |
| `sync-sandbox.sh` | Enable Claude sandbox in `.claude/settings.json` |
| `sync-settings.sh` | Remove redundant permissions, migrate WebFetch domains to sandbox |
| `sync-dependabot.sh` | Create `dependabot.yml` with auto-detected ecosystems |
| `sync-repo-descriptions.sh` | Sync GitHub descriptions from README tagline |

```bash
# Dry run any sync script
./scripts/sync-license.sh --dry-run ..
./scripts/sync-dependabot.sh --dry-run ..
```

### Reports

| Script | Purpose |
|--------|---------|
| `report-taglines.sh` | Tabular report of repo names and README taglines |
| `check-tracked-ignored.sh` | Find tracked files that match gitignore patterns |

### Utilities

| Script | Purpose |
|--------|---------|
| `set-secret-all-repos.sh` | Set a GitHub secret across all repos |

```bash
./scripts/set-secret-all-repos.sh .. MY_SECRET "value"
```

### Shared Libraries

Scripts share common infrastructure via `scripts/lib/`:

- `style.sh` — terminal colors, log functions (`success`, `error`, `warn`, `info`, `step`, `skip`), `NO_COLOR` support
- `common.sh` — `parse_args()`, `discover_repos()`, `extract_github_remote()`, `require_gh_auth()`

### Templates

Templates used by sync scripts live in `scripts/templates/`:

- `LICENSE` — MIT license with `[year]`/`[fullname]` placeholders
- `CLAUDE.md` — minimal CLAUDE.md with `[project-name]` placeholder
- `dependabot.yml` — base dependabot config

## Skills

Claude Code skills for AI-dependent maintenance operations (in `.claude/skills/`):

| Skill | Purpose |
|-------|---------|
| `maintain-repos` | Orchestrator: audit → sync scripts → AI fixes |
| `fix-readme` | README remediation (delegates to `project-readme-author`) |
| `fix-logo` | Logo remediation (delegates to `project-logo-author`) |

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
  test:
    uses: tsilva/.github/.github/workflows/test.yml@main
  pii-scan:
    uses: tsilva/.github/.github/workflows/pii-scan.yml@main
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

Scripts require:
- [GitHub CLI](https://cli.github.com/) (`gh`) — installed and authenticated
- Python 3.11+ — for tagline extraction and settings manipulation
- bash 4+ — for associative arrays and modern shell features

## License

MIT
