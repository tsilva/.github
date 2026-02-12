---
name: maintain-repos
description: Audit and remediate repos for tsilva org standardization. Run from repos parent directory.
argument-hint: "[audit|fix|maintain|commit|report] [--filter PATTERN] <repos-dir>"
---

# Maintain Repos

Orchestrates repo compliance auditing and remediation for the tsilva organization using the `tsilva-maintain` Python CLI.

## Prerequisites

**Required tools:** git, gh CLI, python3, tsilva-maintain

Install the CLI from the `.github` repo:

```bash
uv tool install tsilva-maintain --from /path/to/.github
```

**Required skills (for AI-dependent fixes):**
- `project-readme-author` — README creation/optimization
- `project-logo-author` — logo generation
- `mcp__image-tools__get_image_metadata` — logo verification

## Operations

| Operation | Triggers | Purpose |
|-----------|----------|---------|
| `audit` | "audit", "check", "scan", default | Run all 25 checks, show report |
| `fix` | "fix", "remediate", "repair" | Apply auto-fixes for failures |
| `maintain` | "maintain", "full" | Audit -> fix -> verify cycle |
| `commit` | "commit", "push" | AI-assisted commit & push for dirty repos |
| `report` | "report", "taglines" | Generate reports |

### Operation Detection

1. Check arguments for explicit keyword
2. If no keyword: default to `audit`

## Audit

```bash
tsilva-maintain audit <repos-dir>
tsilva-maintain audit --json <repos-dir>
tsilva-maintain audit --filter my-project <repos-dir>
tsilva-maintain audit --rule README_EXISTS <repos-dir>
```

### Checks (25 per repo)

| Check | What it detects |
|-------|----------------|
| DEFAULT_BRANCH | Repo has a "main" branch |
| README_EXISTS | README.md file exists |
| README_CURRENT | No placeholders, adequate length, has install/usage |
| README_LICENSE | README mentions license |
| README_LOGO | README references the project logo |
| LOGO_EXISTS | Logo in standard locations |
| LICENSE_EXISTS | LICENSE/LICENSE.md/LICENSE.txt exists |
| GITIGNORE_EXISTS | .gitignore exists |
| GITIGNORE_COMPLETE | Essential patterns present |
| CLAUDE_MD_EXISTS | CLAUDE.md exists |
| CLAUDE_SANDBOX | sandbox.enabled: true in .claude/settings*.json |
| DEPENDABOT_EXISTS | .github/dependabot.yml exists |
| PRECOMMIT_GITLEAKS | .pre-commit-config.yaml has gitleaks hook (skips .github) |
| TRACKED_IGNORED | No tracked files matching gitignore |
| PENDING_COMMITS | No uncommitted changes or unpushed commits |
| STALE_BRANCHES | No merged or inactive (>90d) branches |
| PYTHON_PYPROJECT | pyproject.toml exists (Python projects only) |
| PYTHON_MIN_VERSION | requires-python field in pyproject.toml |
| SETTINGS_DANGEROUS | No dangerous permission patterns (e.g. `Bash(*:*)`) |
| SETTINGS_CLEAN | No redundant permissions or unmigrated WebFetch domains |
| README_CI_BADGE | README has CI status badge (skips if no workflows) |
| CI_WORKFLOW | Python repos reference test.yml/release.yml/pytest |
| RELEASE_WORKFLOW | Versioned projects reference release.yml |
| PII_SCAN | CI workflows include PII scanning (skips if no workflows) |
| REPO_DESCRIPTION | GitHub description matches README tagline |

## Fix

### Step 1: Apply Auto-Fixes

```bash
tsilva-maintain fix <repos-dir>
tsilva-maintain fix --dry-run <repos-dir>
```

Auto-fixes cover 11 rules: LICENSE, CLAUDE.md, sandbox, dependabot, gitignore, pre-commit, README license/logo sections, settings cleanup, repo descriptions.

### Step 2: Re-audit to Find Remaining Failures

```bash
tsilva-maintain audit --json <repos-dir>
```

### Step 3: Fix Remaining Issues (AI-dependent)

Process remaining failures per repo. For each repo with failures:

1. `cd` into the repo directory
2. For **README** failures (README_EXISTS, README_CURRENT):
   - If README.md is missing: use `/project-readme-author create` to generate one
   - If README exists but is stale/placeholder: use `/project-readme-author optimize` to update it
3. For **LOGO** failures (LOGO_EXISTS):
   - Use `/project-logo-author` to generate a logo
   - Verify the result: must be at `logo.png` in repo root, transparent background, includes project name as text
   - Check with `mcp__image-tools__get_image_metadata` and visual inspection
   - If verification fails, regenerate with specific corrections
4. For **TRACKED_IGNORED**: list the files and suggest `git rm --cached` commands
5. For **PYTHON_PYPROJECT**: generate a minimal pyproject.toml
6. For **SETTINGS_DANGEROUS**: list the dangerous patterns and require human review — do NOT auto-remove
7. For **DEFAULT_BRANCH**: suggest `git branch -m master main` + `gh repo edit --default-branch main` — do NOT auto-rename
8. For **PENDING_COMMITS**: list the uncommitted changes and unpushed commits, suggest user review and commit/push — do NOT auto-commit
9. For **STALE_BRANCHES**: list branches, suggest `git branch -d <branch>` for merged branches — do NOT auto-delete

### Step 4: Final Audit

```bash
tsilva-maintain audit <repos-dir>
```

## Maintain (One-Command Flow)

Full audit -> fix -> verify cycle:

```bash
tsilva-maintain maintain <repos-dir>
tsilva-maintain maintain --dry-run <repos-dir>
```

## Commit

AI-assisted commit & push for repos with uncommitted changes:

```bash
tsilva-maintain commit <repos-dir>
tsilva-maintain commit --dry-run <repos-dir>
```

## Report

```bash
tsilva-maintain report taglines <repos-dir>
tsilva-maintain report tracked-ignored <repos-dir>
```

## Filter

All operations support `--filter PATTERN` to limit to repos matching a name pattern:

```bash
tsilva-maintain audit --filter my-project <repos-dir>
```

## Usage Examples

```
/maintain-repos audit ~/repos/tsilva
/maintain-repos fix ~/repos/tsilva
/maintain-repos fix --filter my-project ~/repos/tsilva
/maintain-repos maintain ~/repos/tsilva
/maintain-repos commit ~/repos/tsilva
/maintain-repos report taglines ~/repos/tsilva
```
