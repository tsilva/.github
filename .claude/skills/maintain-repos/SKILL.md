---
name: maintain-repos
description: Audit and remediate repos for tsilva org standardization. Run from repos parent directory.
argument-hint: "[--dry-run] [--filter PATTERN] <repos-dir>"
---

# Maintain Repos

Orchestrates repo compliance auditing and remediation for the tsilva organization using the `gitguard` Python CLI.

## Prerequisites

**Required tools:** git, gh CLI, python3, gitguard

Install the CLI from the `.github` repo:

```bash
uv tool install gitguard --from /path/to/.github
```

**Required skills (for AI-dependent fixes):**
- `project-readme-author` — README creation/optimization
- `project-logo-author` — logo generation
- `mcp__image-tools__get_image_metadata` — logo verification

## Operations

| Operation | Triggers | Purpose |
|-----------|----------|---------|
| default (maintain) | no keyword, "maintain", "fix" | Single-pass check + fix cycle |
| `--dry-run` | "audit", "check", "scan", "dry run" | Preview what would be fixed without modifying files |
| `commit` | "commit", "push", "dirty" | AI-assisted commit & push for dirty repos |
| `report` | "report", "taglines" | Generate reports |

### Operation Detection

1. Check arguments for explicit keyword
2. If no keyword: default to maintain (check + fix)

## Maintain (Default)

Single-pass check+fix: each rule is checked, and if it fails, auto-fixed and re-verified. Rules run in dependency order so later rules see the fixed state of earlier rules.

```bash
gitguard <repos-dir>
gitguard --dry-run <repos-dir>
gitguard --filter my-project <repos-dir>
```

### Post-Fix: Handle Remaining Failures

After running `gitguard`, check output for remaining manual issues. For each repo with failures:

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

### Final Verification

```bash
gitguard --dry-run <repos-dir>
```

## Commit

Interactive AI-assisted commit & push. Finds repos with uncommitted changes, generates commit messages via AI, prompts for approval, then commits and pushes.

```bash
gitguard commit <repos-dir>
gitguard commit --dry-run <repos-dir>
gitguard commit --filter my-project <repos-dir>
```

## Dry Run (Audit)

```bash
gitguard --dry-run <repos-dir>
gitguard --dry-run --json <repos-dir>
gitguard --dry-run --filter my-project <repos-dir>
gitguard --dry-run --rule README_EXISTS <repos-dir>
```

### Checks (24 per repo)

| Check | What it detects |
|-------|----------------|
| DEFAULT_BRANCH | Repo has a "main" branch |
| LICENSE_EXISTS | LICENSE/LICENSE.md/LICENSE.txt exists |
| LOGO_EXISTS | Logo in standard locations |
| GITIGNORE | .gitignore exists with essential patterns |
| CLAUDE_MD_EXISTS | CLAUDE.md exists |
| PYTHON_PYPROJECT | pyproject.toml exists (Python projects only) |
| README_EXISTS | README.md file exists |
| README_CURRENT | No placeholders, adequate length, has install/usage |
| README_LICENSE | README mentions license |
| README_LOGO | README references the project logo |
| README_CI_BADGE | README has CI status badge (skips if no workflows) |
| TRACKED_IGNORED | No tracked files matching gitignore |
| CLAUDE_SANDBOX | sandbox.enabled: true in .claude/settings*.json |
| SETTINGS_DANGEROUS | No dangerous permission patterns (e.g. `Bash(*:*)`) |
| SETTINGS_CLEAN | No redundant permissions or unmigrated WebFetch domains |
| PYTHON_MIN_VERSION | requires-python field in pyproject.toml |
| DEPENDABOT_EXISTS | .github/dependabot.yml exists |
| PRECOMMIT_GITLEAKS | .pre-commit-config.yaml has gitleaks hook (skips .github) |
| PENDING_COMMITS | No uncommitted changes or unpushed commits |
| STALE_BRANCHES | No merged or inactive (>90d) branches |
| CI_WORKFLOW | Python repos reference test.yml/release.yml/pytest |
| RELEASE_WORKFLOW | Versioned projects reference release.yml |
| PII_SCAN | CI workflows include PII scanning (skips if no workflows) |
| REPO_DESCRIPTION | GitHub description matches README tagline |

## Report

```bash
gitguard report taglines <repos-dir>
gitguard report tracked-ignored <repos-dir>
```

## Filter

All operations support `--filter PATTERN` to limit to repos matching a name pattern:

```bash
gitguard --filter my-project <repos-dir>
```

## Usage Examples

```
/maintain-repos ~/repos/tsilva
/maintain-repos --dry-run ~/repos/tsilva
/maintain-repos --filter my-project ~/repos/tsilva
/maintain-repos commit ~/repos/tsilva
/maintain-repos report taglines ~/repos/tsilva
```
