<div align="center">
  <img src="logo.png" alt=".github" width="512"/>

  # .github

  Private GitHub Actions building blocks and fleet maintenance tooling for the `tsilva` repositories

  [Workflows](#workflows) · [CLI](#cli-gitguard) · [Usage](#usage)
</div>

## Features

[![CI](https://github.com/tsilva/.github/actions/workflows/ci.yml/badge.svg)](https://github.com/tsilva/.github/actions/workflows/ci.yml)

- Modular internal workflows — same-repository calls use commit-bound relative references
- PyPI publishing — build, release, and publish via trusted publishing
- Auto-tagging — version extracted from `pyproject.toml`, skips existing tags
- Testing — pytest via a reusable workflow within this repository
- Repo compliance — audit and enforce repository standards via Python CLI
- Supply-chain controls — generated workflows use full-SHA action pins and least-privilege jobs
- Repo templates — pre-compliant starting points for new projects
- Repo bootstrapping — automate new repo setup from template to full compliance in one command

## Workflows

| Workflow | Purpose | Key Details |
|----------|---------|-------------|
| `release.yml` | Repository release flow | Calls local test and publish workflows |
| `publish-pypi.yml` | Build, tag, release, publish | Uses `uv build` + trusted publishing |
| `create-release.yml` | Tag + GitHub release (no PyPI) | For non-Python repos |
| `test.yml` | Validate Python | Frozen sync, lock/audit, focused Ruff, pytest, and package build |
| `ci.yml` | PR-time checks | Wraps test workflow |
| `dependency-review.yml` | Review dependency changes | Portable lock, registry-source, and frozen audit gate |

### `release.yml`

The release entry point for this repository. Other repositories receive a self-contained, SHA-pinned release workflow from `gitguard` rather than calling this private repository.

**Flow:**
1. Runs tests
2. Builds once in a read-only job and stores the artifacts
3. Creates the GitHub release and publishes to PyPI in separate least-privilege jobs

## CLI (`gitguard`)

A Python CLI that replaces the legacy bash scripts. Each compliance rule is a self-contained class with `check()` and `fix()` methods, auto-discovered at runtime.

### Installation

```bash
uv pip install -e .           # development
uv tool install gitguard  # global CLI
```

### Commands

```bash
# Default — single-pass check + fix cycle
gitguard ~/repos/tsilva
gitguard ~/repos/tsilva --filter myrepo   # only repos matching pattern
gitguard ~/repos/tsilva --rule README_EXISTS

# Dry run — preview what would be fixed without modifying files
gitguard ~/repos/tsilva --dry-run
gitguard ~/repos/tsilva --dry-run --json  # JSON output for CI

# Commit — AI-assisted commit & push for dirty repos
gitguard commit ~/repos/tsilva
gitguard commit ~/repos/tsilva --filter myrepo
gitguard commit ~/repos/tsilva --dry-run   # show dirty repos only

# Report — generate reports
gitguard report taglines ~/repos/tsilva
gitguard report tracked-ignored ~/repos/tsilva

# Rename — rename a repo on GitHub + local + remote + file references
gitguard rename old-name new-name ~/repos/tsilva
gitguard rename old-name new-name ~/repos/tsilva --dry-run
```

### Adding a New Rule

Create one Python file in `src/gitguard/rules/`:

```python
from gitguard.rules import Category, CheckResult, Rule, Status

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

### Compliance Rules

**Repository Structure**

| ID | Rule |
|----|------|
| `README_EXISTS` | README.md must exist |
| `README_CURRENT` | README must have no placeholders, be >100 chars, and include install/usage sections |
| `README_LICENSE` | README must reference the license |
| `README_CI_BADGE` | README must have a CI badge (repos with workflows) |
| `README_LOGO` | README must reference the project logo |
| `LOGO_EXISTS` | A logo file must exist in a standard location |
| `LICENSE_EXISTS` | LICENSE file must exist |
| `GITIGNORE_EXISTS` | .gitignore must exist |
| `GITIGNORE_COMPLETE` | .gitignore must include essential patterns (.env, .DS_Store, node_modules/, __pycache__/, *.pyc, .venv/) |
| `TRACKED_IGNORED` | No tracked files should match .gitignore patterns |
| `REPO_DESCRIPTION` | GitHub repo description must match README tagline |

**Python Projects**

| ID | Rule |
|----|------|
| `PYTHON_PYPROJECT` | Python projects must use pyproject.toml |
| `PYTHON_MIN_VERSION` | pyproject.toml must specify requires-python |

**CI/CD**

| ID | Rule |
|----|------|
| `CI_WORKFLOW` | Python repos must have a CI workflow |
| `RELEASE_WORKFLOW` | Versioned projects must have a release workflow |

**Claude Code Configuration**

| ID | Rule |
|----|------|
| `CLAUDE_MD_EXISTS` | CLAUDE.md must exist |
| `CLAUDE_SANDBOX` | Claude Code sandbox must be enabled |
| `SETTINGS_DANGEROUS` | No dangerous permission patterns in Claude settings |
| `SETTINGS_CLEAN` | No redundant permissions or unmigrated WebFetch domains |

**Git Hygiene**

| ID | Rule |
|----|------|
| `DEFAULT_BRANCH` | Default branch must be `main` |
| `PENDING_COMMITS` | No uncommitted changes or unpushed commits |
| `STALE_BRANCHES` | No merged or inactive (>90 days) branches |

## Repository Templates

Bootstrap new repos that are pre-compliant with org standards:

```bash
# Python CLI tool (published to PyPI)
gh repo create tsilva/my-new-tool --template tsilva/template-python-cli --clone

# Python sandbox/learning repo
gh repo create tsilva/sandbox-whatever --template tsilva/template-python-sandbox --clone

# Non-Python project
gh repo create tsilva/my-app --template tsilva/template-generic --clone

# React Native (Expo) app
gh repo create tsilva/my-app --template tsilva/template-react-native --clone
```

| Template | Use case | Includes |
|----------|----------|----------|
| `template-python-cli` | CLI tools published to PyPI | src layout, hatchling build, release workflow, tests |
| `template-python-sandbox` | Learning/experimentation | Minimal pyproject.toml, no workflows |
| `template-generic` | Non-Python repos | No Python files |
| `template-react-native` | React Native (Expo) apps | Expo Router, EAS Build workflow, TypeScript |

All templates include: LICENSE (MIT), CLAUDE.md, .gitignore, Claude sandbox config.

### Automated Bootstrapping

Use the `bootstrap-repo` skill to go from zero to fully compliant in a single invocation — creates the GitHub repo from a template, clones it, replaces placeholders, generates a logo and README, runs gitguard, and commits:

```
/bootstrap-repo my-new-tool python-cli "A CLI tool that does X"
/bootstrap-repo sandbox-ml python-sandbox "Experimenting with ML algorithms"
/bootstrap-repo my-app generic "A web application"
/bootstrap-repo my-mobile-app react-native "A habit tracking app"
```

## Usage

### Install or repair a Python release workflow

```bash
gitguard /path/to/repos --rule CLI_RELEASE_WORKFLOW
```

The generated `.github/workflows/release.yml` is self-contained, pins every remote action to a full commit SHA, and separates build, GitHub release, and PyPI publishing permissions.

### Internal reusable workflows

```yaml
jobs:
  test:
    uses: ./.github/workflows/test.yml
```

Relative calls execute the workflow from the same commit. Cross-repository use is intentionally disabled while this repository remains private.

## Requirements

Generated release workflows need:
- `pyproject.toml` with `version` field (for release workflows)
- `pypi` environment configured (for PyPI publishing with trusted publishing)

CLI requires:
- Python 3.11+ — zero external dependencies (stdlib only)
- [GitHub CLI](https://cli.github.com/) (`gh`) — for repo description sync
- git — for repository operations

## License

MIT
