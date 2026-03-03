---
name: bootstrap-repo
description: Bootstrap a new tsilva org repo from a template. Creates GitHub repo, clones, replaces placeholders, generates logo+README, runs gitguard.
argument-hint: "<repo-name> <template-type> [description]"
---

# Bootstrap Repo

Bootstraps a new `tsilva` org repository from a GitHub template repo to full compliance in a single invocation.

## Prerequisites

**Required tools:** git, gh CLI, python3, gitguard

Install the CLI from the `.github` repo:

```bash
uv tool install gitguard --from /path/to/.github
```

**Required tools:**
- `project-readme-author` skill — README generation
- `repologogen` CLI — logo generation

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `REPO_NAME` | yes | Repo name — lowercase, hyphens/numbers only |
| `TEMPLATE_TYPE` | yes (or auto-detected) | `python-cli`, `python-sandbox`, `generic`, or `react-native` |
| `DESCRIPTION` | no (prompted if missing) | One-line project description |

**Auto-detection:** Names matching `sandbox-*` default to `python-sandbox`. Otherwise ask the user if not specified.

**Derived:** `PACKAGE_NAME` = `REPO_NAME` with hyphens replaced by underscores.

## Execution Steps

### Step 1: Parse Arguments

- Parse `REPO_NAME`, `TEMPLATE_TYPE`, and `DESCRIPTION` from arguments
- If `TEMPLATE_TYPE` is missing: auto-detect from name (`sandbox-*` → `python-sandbox`) or ask user
- If `DESCRIPTION` is missing: ask user for a one-line description

### Step 2: Create Repo via CLI

Run `gitguard create` to handle all deterministic steps (validation, GitHub creation, clone, placeholder replacement, package dir rename, commit & push):

```bash
gitguard create REPO_NAME TEMPLATE_TYPE -d "DESCRIPTION" REPOS_DIR
```

`REPOS_DIR` is the current working directory. All `gh` commands require `dangerouslyDisableSandbox: true`.

If this fails, stop and report the error.

### Step 3: Generate Logo

`cd` into the repo directory, then generate the logo:

```bash
repologogen .
```

The logo must exist at `logo.png` in the repo root before proceeding.

### Step 4: Generate README

From within the repo directory, delegate to the README generation skill:

Use `/project-readme-author create` to generate the README.

The skill detects `logo.png` from Step 3 and includes it in the README.

### Step 5: Set GitHub Description

Set the GitHub repo description explicitly from the DESCRIPTION argument:

```bash
gh repo edit tsilva/REPO_NAME --description "DESCRIPTION"
```

This avoids relying on gitguard's tagline extraction, which can mismatch when the README tagline uses bookend emojis or other formatting.

### Step 6: Run gitguard

```bash
gitguard --filter REPO_NAME REPOS_DIR
```

This catches remaining auto-fixable issues (e.g., `REPO_DESCRIPTION` sets GitHub description from README tagline).

### Step 7: Commit & Push

From within the repo directory:

```bash
git add -A
git commit -m "Add logo and README

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### Step 8: Final Verification

```bash
gitguard --dry-run --filter REPO_NAME REPOS_DIR
```

Report results to user. Expected transient warnings for freshly bootstrapped repos:
- `WORKFLOWS_PASSING` — CI hasn't run yet on the newly pushed commit
- `README_CURRENT` — placeholder text like "Coming soon" is normal for repos with no code yet
- `CI_WORKFLOW` — expected for `python-sandbox` and `generic` templates (no CI needed)
- `PENDING_COMMITS` — `.vscode/` or other IDE artifacts may appear as untracked; ignore if in `.gitignore`

## Usage Examples

```
/bootstrap-repo my-new-tool python-cli "A CLI tool that does X"
/bootstrap-repo sandbox-ml python-sandbox "Experimenting with ML algorithms"
/bootstrap-repo my-app generic "A web application"
/bootstrap-repo my-mobile-app react-native "A habit tracking app"
/bootstrap-repo my-thing
```
