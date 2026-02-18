---
name: rename-repo
description: Use when renaming a tsilva org repository — orchestrates all deterministic steps (gitguard rename) plus logo and README regeneration so the rename needs zero manual planning.
argument-hint: "<old-name> <new-name> [repos-dir]"
---

# Rename Repo

Full rename orchestration for `tsilva` org repos. Runs `gitguard rename` for all deterministic operations, then handles AI-dependent steps (logo, README).

## Prerequisites

**Required tools:** git, gh CLI, gitguard, uv

**Required skills:**
- `project-logo-author` — logo regeneration
- `project-readme-author` — README regeneration

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `OLD_NAME` | yes | Current repo name |
| `NEW_NAME` | yes | New repo name (lowercase, hyphens/numbers) |
| `REPOS_DIR` | no | Parent directory of repos (default: current working directory) |

## Execution Steps

### Step 1: Parse Arguments

- Parse `OLD_NAME`, `NEW_NAME`, and optional `REPOS_DIR` from arguments
- Default `REPOS_DIR` to the current working directory if not provided

### Step 2: Run `gitguard rename`

```bash
gitguard rename OLD_NAME NEW_NAME [REPOS_DIR]
```

This handles all deterministic operations:
1. Validation (local dir, git repo, GitHub auth, no conflicts, clean working tree)
2. GitHub repo rename (`gh api`)
3. Local folder rename
4. Git remote URL update
5. Python package dir rename (if `src/old_pkg/` or `old_pkg/` exists)
6. `.code-workspace` file rename (if present)
7. Global search-replace across all tracked text files (skips `uv.lock` and binaries)
8. `uv.lock` regeneration (if `pyproject.toml` present)
9. Cross-repo reference scan (warnings only)

Capture the cross-repo warning output from step 9 — you'll remind the user in Step 7.

### Step 3: Run Tests

From within the renamed repo directory (`REPOS_DIR/NEW_NAME`):

```bash
uv run pytest tests/ -q
```

If a `tests/` directory exists, run tests. A failure is a **warning only** — do not stop the rename. Report the failure to the user at the end.

### Step 4: Regenerate Logo

`cd` into the renamed repo directory, then invoke the logo generation skill:

Use `/project-logo-author` to regenerate the logo for the project under its new name.

The logo must exist at `logo.png` in the repo root before proceeding to Step 5.

**Why before README:** Calling `project-logo-author` directly ensures the logo is generated with user config from `~/.claude/project-logo-author.json`. When `readme-author` runs in Step 5, it detects `logo.png` already exists and skips its own logo generation — sidestepping any settings passthrough issues.

### Step 5: Regenerate README

From within the renamed repo directory, invoke the README skill:

Use `/project-readme-author create` to regenerate the README.

The skill detects `logo.png` from Step 4 and includes it. Since the repo is already set up, `create` mode generates a fresh README reflecting the new name.

### Step 6: Commit & Push

From within the renamed repo directory:

```bash
git add -A
git commit -m "Rename from OLD_NAME to NEW_NAME

Update all in-repo references, regenerate logo and README.

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### Step 7: Remind About Cross-Repo References

Show the user the cross-repo warnings captured from Step 2 (sibling repos with references to `OLD_NAME`). Remind them these require manual updates.

If there were no cross-repo references, confirm that no sibling repos reference the old name.

## Usage Examples

```
/rename-repo archive-extractor archex
/rename-repo claude-skills claude-skillz ~/repos/tsilva
/rename-repo my-old-tool my-new-tool
```
