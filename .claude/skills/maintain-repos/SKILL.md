---
name: maintain-repos
description: Audit and remediate repos for tsilva org standardization. Run from repos parent directory.
argument-hint: "[audit|fix|status] [--filter PATTERN] <repos-dir>"
---

# Maintain Repos

Orchestrates repo compliance auditing and remediation for the tsilva organization.

## Prerequisites

**Required tools:** git, gh CLI, python3

**Required skills (for fix operation):**
- `project-readme-author` — README creation/optimization
- `project-logo-author` — logo generation
- `mcp__image-tools__get_image_metadata` — logo verification

## Operations

| Operation | Triggers | Purpose |
|-----------|----------|---------|
| `audit` | "audit", "check", "scan", default | Run all checks, show report |
| `fix` | "fix", "remediate", "repair" | Apply fixes for failures |
| `status` | "status", "progress" | Show existing audit results |

### Operation Detection

1. Check arguments for explicit keyword (audit/fix/status)
2. If no keyword: default to `audit`

## Audit

Run the audit script from the `.github` repository:

```bash
{SKILL_DIR}/../../scripts/audit-repos.sh <repos-dir>
```

Or for machine-readable output:

```bash
{SKILL_DIR}/../../scripts/audit-repos.sh --json <repos-dir>
```

### Checks (14 per repo)

| Check | What it detects |
|-------|----------------|
| README_EXISTS | README.md file exists |
| README_CURRENT | No placeholders, adequate length, has install/usage |
| README_LICENSE | README mentions license |
| LOGO_EXISTS | Logo in standard locations |
| LICENSE_EXISTS | LICENSE/LICENSE.md/LICENSE.txt exists |
| GITIGNORE_EXISTS | .gitignore exists |
| GITIGNORE_COMPLETE | Essential patterns present |
| CLAUDE_MD_EXISTS | CLAUDE.md exists |
| CLAUDE_SANDBOX | sandbox.enabled: true in .claude/settings*.json |
| DEPENDABOT_EXISTS | .github/dependabot.yml exists |
| TRACKED_IGNORED | No tracked files matching gitignore |
| PYTHON_PYPROJECT | pyproject.toml exists (Python projects only) |
| SETTINGS_DANGEROUS | No dangerous permission patterns (e.g. `Bash(*:*)`) |
| SETTINGS_CLEAN | No redundant permissions or unmigrated WebFetch domains |

## Fix

### Step 1: Apply Safe Fixes (automatic, no AI needed)

Run sync scripts for deterministic fixes. These are safe to run without review:

```bash
SCRIPTS="{SKILL_DIR}/../../scripts"
REPOS_DIR="<repos-dir>"

# Run all safe sync scripts
"$SCRIPTS/sync-license.sh" "$REPOS_DIR"
"$SCRIPTS/sync-claude-md.sh" "$REPOS_DIR"
"$SCRIPTS/sync-sandbox.sh" "$REPOS_DIR"
"$SCRIPTS/sync-settings.sh" "$REPOS_DIR"
"$SCRIPTS/sync-dependabot.sh" "$REPOS_DIR"
"$SCRIPTS/sync-gitignore.sh" "$REPOS_DIR"
```

Each script only creates files that are missing — existing files are never overwritten.

### Step 2: Re-audit to Find Remaining Failures

```bash
"$SCRIPTS/audit-repos.sh" --json "$REPOS_DIR"
```

### Step 3: Fix Remaining Issues (AI-dependent)

Process remaining failures per repo. For each repo with failures:

1. `cd` into the repo directory
2. For **README** failures (README_EXISTS, README_CURRENT, README_LICENSE):
   - Use the `fix-readme` skill: delegate to `.claude/skills/fix-readme/SKILL.md`
3. For **LOGO** failures (LOGO_EXISTS):
   - Use the `fix-logo` skill: delegate to `.claude/skills/fix-logo/SKILL.md`
4. For **GITIGNORE_COMPLETE**: append missing patterns to .gitignore
5. For **TRACKED_IGNORED**: list the files and suggest `git rm --cached` commands
6. For **PYTHON_PYPROJECT**: generate a minimal pyproject.toml
7. For **SETTINGS_DANGEROUS**: list the dangerous patterns and require human review — do NOT auto-remove

### Step 4: Final Audit

Run audit again to confirm all fixes applied:

```bash
"$SCRIPTS/audit-repos.sh" "$REPOS_DIR"
```

## Status

Display the results of the most recent audit:

```bash
"$SCRIPTS/audit-repos.sh" "$REPOS_DIR"
```

Show pass rate, failed checks grouped by type, and list of fully-compliant repos.

## Filter

All operations support `--filter PATTERN` to limit to repos matching a name pattern:

```bash
"$SCRIPTS/audit-repos.sh" --filter my-project "$REPOS_DIR"
```

## Usage Examples

```
/maintain-repos audit ~/repos/tsilva
/maintain-repos fix ~/repos/tsilva
/maintain-repos fix --filter my-project ~/repos/tsilva
/maintain-repos status ~/repos/tsilva
```
