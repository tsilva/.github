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

**Required skills:**
- `project-readme-author` — README generation
- `project-logo-author` — logo generation

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `REPO_NAME` | yes | Repo name — lowercase, hyphens/numbers only |
| `TEMPLATE_TYPE` | yes (or auto-detected) | `python-cli`, `python-sandbox`, or `generic` |
| `DESCRIPTION` | no (prompted if missing) | One-line project description |

**Auto-detection:** Names matching `sandbox-*` default to `python-sandbox`. Otherwise ask the user if not specified.

**Derived:** `PACKAGE_NAME` = `REPO_NAME` with hyphens replaced by underscores.

## Execution Steps

### Step 1: Parse & Validate Arguments

- Parse `REPO_NAME`, `TEMPLATE_TYPE`, and `DESCRIPTION` from arguments
- Validate `REPO_NAME`: must be lowercase, only letters/hyphens/numbers
- If `TEMPLATE_TYPE` is missing: auto-detect from name (`sandbox-*` → `python-sandbox`) or ask user
- If `DESCRIPTION` is missing: ask user for a one-line description
- Derive `PACKAGE_NAME` = `REPO_NAME` with `-` → `_`

### Step 2: Pre-flight Checks

Run these checks before making any changes:

```bash
gh api user --jq .login
```
Must return a username. This tests actual API access, resilient to keyring errors.

```bash
gh repo view tsilva/REPO_NAME 2>&1
```
Must NOT exist (expect error).

Check that `REPOS_DIR/REPO_NAME` does not exist locally. `REPOS_DIR` is the current working directory.

### Step 3: Create Repo from Template & Clone

Two-step create + clone for explicit control over clone destination:

```bash
gh repo create tsilva/REPO_NAME --template tsilva/template-TEMPLATE_TYPE --public
```

Wait a few seconds for GitHub to finish template copying, then:

```bash
gh repo clone tsilva/REPO_NAME REPOS_DIR/REPO_NAME
```

### Step 4: Replace Placeholders

In `REPOS_DIR/REPO_NAME`, replace across all text files (excluding `.git/`):

| Pattern | Replacement | Templates |
|---------|-------------|-----------|
| `my-project` | `REPO_NAME` | All |
| `my_project` | `PACKAGE_NAME` | python-cli |
| `Short description of what this tool does.` | `DESCRIPTION` | python-cli |
| `Short description of what this project explores.` | `DESCRIPTION` | python-sandbox |
| `Short description of what this project does.` | `DESCRIPTION` | generic |

Use `find` to locate text files, excluding `.git/`:

```bash
find REPOS_DIR/REPO_NAME -type f -not -path '*/.git/*' -print0 | xargs -0 sed -i '' 's/my-project/REPO_NAME/g'
```

For python-cli, also replace `my_project` → `PACKAGE_NAME`:

```bash
find REPOS_DIR/REPO_NAME -type f -not -path '*/.git/*' -print0 | xargs -0 sed -i '' 's/my_project/PACKAGE_NAME/g'
```

Replace the template description placeholder with the actual description (use exact template-specific text).

### Step 5: Rename Package Directory (python-cli only)

Only for `python-cli` template:

```bash
mv REPOS_DIR/REPO_NAME/src/my_project REPOS_DIR/REPO_NAME/src/PACKAGE_NAME
```

This must happen AFTER placeholder replacement in Step 4 so `sed` finds files at their original paths.

### Step 6: Generate Logo

`cd` into the repo directory, then delegate to the logo generation skill:

Use `/project-logo-author` to generate a logo for the project.

The logo must exist at `logo.png` in the repo root before proceeding.

### Step 7: Generate README

From within the repo directory, delegate to the README generation skill:

Use `/project-readme-author create` to generate the README.

The skill detects `logo.png` from Step 6 and includes it in the README.

### Step 7.5: Set GitHub Description

Set the GitHub repo description explicitly from the DESCRIPTION argument:

```bash
gh repo edit tsilva/REPO_NAME --description "DESCRIPTION"
```

This avoids relying on gitguard's tagline extraction, which can mismatch when the README tagline uses bookend emojis or other formatting.

### Step 8: Run gitguard

```bash
gitguard --filter REPO_NAME REPOS_DIR
```

This catches remaining auto-fixable issues (e.g., `REPO_DESCRIPTION` sets GitHub description from README tagline).

### Step 9: Commit & Push

From within the repo directory:

```bash
git add -A
git commit -m "Bootstrap from template-TEMPLATE_TYPE

Initialize REPO_NAME from template-TEMPLATE_TYPE template with
placeholder replacement, logo, and README generation.

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### Step 10: Final Verification

```bash
gitguard --dry-run --filter REPO_NAME REPOS_DIR
```

Report results to user. Expected transient warnings for freshly bootstrapped repos:
- `WORKFLOWS_PASSING` — CI hasn't run yet on the newly pushed commit
- `README_CURRENT` — placeholder text like "Coming soon" is normal for repos with no code yet

## Usage Examples

```
/bootstrap-repo my-new-tool python-cli "A CLI tool that does X"
/bootstrap-repo sandbox-ml python-sandbox "Experimenting with ML algorithms"
/bootstrap-repo my-app generic "A web application"
/bootstrap-repo my-thing
```
