# Rules

Canonical specification of compliance rules for the `tsilva` GitHub organization. Every repository in the org must satisfy applicable rules. Each rule documents its automation status — whether an audit check detects violations and whether a fix exists.

**Legend:** `check:` audit check ID from `audit-repos.sh` | `fix:` sync script or skill that remediates

---

## 1. Repository Structure

### 1.1 README must exist

- **Applies to:** all repos
- **Check:** `README_EXISTS` — automated
- **Fix:** `maintain-repos` skill (delegates to `project-readme-author`) — automated
- **Details:** Every repo must have a `README.md` at the root.

### 1.2 README must be current

- **Applies to:** all repos
- **Check:** `README_CURRENT` — automated
- **Fix:** `maintain-repos` skill (delegates to `project-readme-author`) — automated
- **Details:** README must not contain placeholders (TODO, FIXME, Coming soon, Work in progress, Under construction, Lorem ipsum), must be longer than 100 characters, and must include installation or usage sections.

### 1.3 README must reference license

- **Applies to:** all repos
- **Check:** `README_LICENSE` — automated
- **Fix:** `sync-readme-license.sh` / `maintain-repos` skill — automated
- **Details:** README must contain a license heading or mention "MIT" license. A `## License` section with "MIT" is the standard format.

### 1.4 README must have CI badge

- **Applies to:** repos with CI workflows
- **Check:** `README_CI_BADGE` — automated
- **Fix:** not implemented
- **Details:** Repos that have a GitHub Actions CI workflow must display a CI status badge in the README.

### 1.5 Logo must exist

- **Applies to:** all repos
- **Check:** `LOGO_EXISTS` — automated
- **Fix:** `maintain-repos` skill (delegates to `project-logo-author`) — automated
- **Details:** A logo must exist in a standard location (`logo.png`, `logo.svg`, `logo.jpg`, or under `assets/`, `images/`, `.github/`). Logo should be a square icon with transparent background, 512x512 or similar.

### 1.6 README must reference logo

- **Applies to:** all repos
- **Check:** `README_LOGO` — automated
- **Fix:** `sync-readme-logo.sh` / `maintain-repos` skill — automated
- **Details:** README.md must contain an image reference to the project logo (markdown `![...](logo.png)` or HTML `<img>`). Logo may be at root or under `assets/`, `images/`, or `.github/`.

### 1.7 Logo must contain repo name

- **Applies to:** all repos
- **Check:** not implemented (requires visual inspection)
- **Fix:** `maintain-repos` skill (delegates to `project-logo-author`) — AI-dependent
- **Details:** The project logo must visually include the repository name as text alongside the icon. Verified during AI-assisted maintenance via visual inspection.

### 1.8 LICENSE must exist

- **Applies to:** all repos
- **Check:** `LICENSE_EXISTS` — automated
- **Fix:** `sync-license.sh` — automated
- **Details:** A `LICENSE`, `LICENSE.md`, or `LICENSE.txt` file must exist. All tsilva repos use MIT license. The sync script creates from template with current year and author.

### 1.9 .gitignore must exist

- **Applies to:** all repos
- **Check:** `GITIGNORE_EXISTS` — automated
- **Fix:** `sync-gitignore.sh` — automated
- **Details:** Every repo must have a `.gitignore` file.

### 1.10 .gitignore must include essential patterns

- **Applies to:** all repos
- **Check:** `GITIGNORE_COMPLETE` — automated
- **Fix:** `sync-gitignore.sh` — automated
- **Details:** `.gitignore` must include these patterns: `.env`, `.DS_Store`, `node_modules/`, `__pycache__/`, `*.pyc`, `.venv/`. The sync script appends missing rules from `gitignore.global`.

### 1.11 No tracked files matching gitignore

- **Applies to:** all repos
- **Check:** `TRACKED_IGNORED` — automated
- **Fix:** manual (`git rm --cached`)
- **Details:** Files that match `.gitignore` patterns must not be tracked by git. Detected via `git ls-files -i --exclude-standard`. Requires manual review before removal since untracking may affect collaborators.

### 1.12 GitHub description must match README tagline

- **Applies to:** all repos
- **Check:** `REPO_DESCRIPTION` — automated
- **Fix:** `sync-repo-descriptions.sh` — automated
- **Details:** The GitHub repository description must match the README tagline (or `pyproject.toml` description as fallback). The sync script extracts the tagline and updates the GitHub description via `gh api`.

---

## 2. Dependency Management

### 2.1 Dependabot must be configured

- **Applies to:** all repos
- **Check:** `DEPENDABOT_EXISTS` — automated
- **Fix:** `sync-dependabot.sh` — automated
- **Details:** `.github/dependabot.yml` must exist with auto-detected ecosystems (pip, npm, GitHub Actions, etc.). The sync script generates the config from a base template by detecting which package managers are present.

---

## 3. Python Projects

### 3.1 Must use pyproject.toml

- **Applies to:** Python repos (detected by presence of `setup.py`, `requirements.txt`, `setup.cfg`, `Pipfile`, or 3+ non-test `.py` files)
- **Check:** `PYTHON_PYPROJECT` — automated
- **Fix:** manual
- **Details:** Python projects must use `pyproject.toml` as the single project configuration file. Legacy `setup.py`/`setup.cfg` should be migrated.

### 3.2 Must be installable with UV

- **Applies to:** Python repos
- **Check:** not implemented
- **Fix:** not implemented
- **Details:** Python projects must be installable via `uv pip install .` or `uv sync`. The `pyproject.toml` must follow standards that UV supports (PEP 621).

### 3.3 Must specify minimum Python version

- **Applies to:** Python repos
- **Check:** `PYTHON_MIN_VERSION` — automated
- **Fix:** not implemented
- **Details:** `pyproject.toml` must include a `requires-python` field specifying the minimum Python version the project supports (e.g., `requires-python = ">=3.10"`).

### 3.4 CLI projects must be deployed to PyPI

- **Applies to:** Python CLI projects (repos with `[project.scripts]` in `pyproject.toml`)
- **Check:** not implemented
- **Fix:** not implemented
- **Details:** CLI tools must be published to PyPI so users can install via `uv tool install <package>`. The repo should use the `release.yml` reusable workflow with `publish_to_pypi: true`.

### 3.5 CLI projects must be deployed to Homebrew

- **Applies to:** Python CLI projects
- **Check:** not implemented
- **Fix:** not implemented
- **Details:** CLI tools must be available via Homebrew for macOS users. Requires a Homebrew tap strategy to be decided first.

---

## 4. CI/CD

### 4.1 Python repos must have a CI workflow

- **Applies to:** Python repos
- **Check:** `CI_WORKFLOW` — automated
- **Fix:** not implemented
- **Details:** Python repos must have a GitHub Actions workflow that runs tests on push. Should reference the reusable `test.yml` workflow from this repo.

### 4.2 Release workflow for versioned projects

- **Applies to:** repos with version in `pyproject.toml`
- **Check:** `RELEASE_WORKFLOW` — automated
- **Fix:** not implemented
- **Details:** Projects that define a version must use the reusable `release.yml` workflow to automate release creation. Python projects use `publish_to_pypi: true`; non-Python use `publish_to_pypi: false`.

---

## 5. Claude Code Configuration

### 5.1 CLAUDE.md must exist

- **Applies to:** all repos
- **Check:** `CLAUDE_MD_EXISTS` — automated
- **Fix:** `sync-claude-md.sh` — automated
- **Details:** Every repo must have a `CLAUDE.md` at the root providing project context for Claude Code. The sync script creates a minimal file from template if missing.

### 5.2 Sandbox must be enabled

- **Applies to:** all repos
- **Check:** `CLAUDE_SANDBOX` — automated
- **Fix:** `sync-sandbox.sh` — automated
- **Details:** `.claude/settings.json` or `.claude/settings.local.json` must have `"sandbox": {"enabled": true}`. This restricts Claude Code's filesystem and network access.

### 5.3 No dangerous permission patterns

- **Applies to:** repos with `.claude/settings.local.json`
- **Check:** `SETTINGS_DANGEROUS` — automated
- **Fix:** manual (requires human review)
- **Details:** Claude Code settings must not contain dangerous permission patterns (e.g., `Bash(*:*)`). Detected by `settings_optimizer.py --check dangerous`. Dangerous patterns are never auto-removed — they require human review to determine if they are intentional.

### 5.4 Settings must be clean

- **Applies to:** repos with `.claude/settings.local.json`
- **Check:** `SETTINGS_CLEAN` — automated
- **Fix:** `sync-settings.sh` — automated
- **Details:** Claude Code settings must not contain redundant permissions or unmigrated WebFetch domains. The sync script removes redundant permissions and migrates WebFetch domain allowlists to sandbox network configuration.

---

## 6. Security

### 6.1 PII scanning in CI

- **Applies to:** all repos with CI
- **Check:** `PII_SCAN` — automated
- **Fix:** implicit via `release.yml` (chains `pii-scan.yml`)
- **Details:** Repositories must run gitleaks for secret/credential scanning as part of CI. Repos using the `release.yml` reusable workflow get this automatically. Repos with custom CI should add `pii-scan.yml` explicitly.

### 6.2 Pre-commit hooks for secret scanning

- **Applies to:** all repos (except `.github` which defines the hook)
- **Check:** `PRECOMMIT_GITLEAKS` — automated
- **Fix:** `sync-precommit.sh` — automated
- **Details:** Repos should configure pre-commit with gitleaks for local secret scanning before push. Requires a `.pre-commit-config.yaml` referencing `tsilva/.github` with the `gitleaks` hook ID. The sync script creates the file from template if missing, or appends the hook if the file exists but lacks it.

---

## 7. Git Hygiene

### 7.1 No pending commits

- **Applies to:** all repos
- **Check:** `PENDING_COMMITS` — automated
- **Fix:** manual (review and commit/push)
- **Details:** Repos must not have uncommitted changes or unpushed commits. Detected via `git status --porcelain` and `git log @{u}..`. Requires human review before committing or pushing.

### 7.2 No stale branches

- **Applies to:** all repos
- **Check:** `STALE_BRANCHES` — automated
- **Fix:** manual (`git branch -d`)
- **Details:** Repos must not have branches that are already merged into main or inactive for more than 90 days. Merged branches should be deleted with `git branch -d`. Stale branches require human review before deletion.

### 7.3 Default branch must be "main"

- **Applies to:** all repos
- **Check:** `DEFAULT_BRANCH` — automated
- **Fix:** manual (`git branch -m master main` + `gh repo edit --default-branch main`)
- **Details:** Every repo must have a `main` branch. Repos still using `master` as default should be migrated. Requires coordination to avoid breaking CI/CD and collaborator workflows.

---

## Automation Coverage

| Metric | Count | Rules |
|--------|-------|-------|
| **Audit checks** | 25 of 29 | 1.1-1.6, 1.8-1.12, 2.1, 3.1, 3.3, 4.1-4.2, 5.1-5.4, 6.1-6.2, 7.1-7.3 |
| **Automated fixes** (sync scripts) | 10 scripts covering 11 rules | 1.3, 1.6, 1.8-1.10, 1.12, 2.1, 5.1, 5.2, 5.4, 6.2 |
| **AI-dependent fixes** (skills) | 1 skill covering 5 rules | 1.1-1.2, 1.5, 1.7 (via `maintain-repos`) |
| **Manual fix only** | 5 rules | 1.11, 5.3, 7.1-7.3 |
| **No automation** | 4 rules | 1.7 (check only), 3.2, 3.4-3.5 |

## Implementation Backlog

Unimplemented checks, ordered by implementation complexity (simplest first):

| Priority | Check ID | Rule | Complexity |
|----------|----------|------|------------|
| 1 | `PYTHON_UV_INSTALL` | 3.2 — UV installable | Validate pyproject.toml structure for PEP 621 |
| 2 | `PYTHON_CLI_PYPI` | 3.4 — CLI on PyPI | Detect `[project.scripts]`, verify release workflow |
| 3 | `PYTHON_CLI_HOMEBREW` | 3.5 — CLI on Homebrew | Needs Homebrew tap strategy decided first |
