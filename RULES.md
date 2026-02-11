# Rules

Canonical specification of compliance rules for the `tsilva` GitHub organization. Every repository in the org must satisfy applicable rules. Each rule documents its automation status — whether an audit check detects violations and whether a fix exists.

**Legend:** `check:` audit check ID from `audit-repos.sh` | `fix:` sync script or skill that remediates

---

## 1. Repository Structure

### 1.1 README must exist

- **Applies to:** all repos
- **Check:** `README_EXISTS` — automated
- **Fix:** `fix-readme` skill (delegates to `project-readme-author`) — automated
- **Details:** Every repo must have a `README.md` at the root.

### 1.2 README must be current

- **Applies to:** all repos
- **Check:** `README_CURRENT` — automated
- **Fix:** `fix-readme` skill (delegates to `project-readme-author`) — automated
- **Details:** README must not contain placeholders (TODO, FIXME, Coming soon, Work in progress, Under construction, Lorem ipsum), must be longer than 100 characters, and must include installation or usage sections.

### 1.3 README must reference license

- **Applies to:** all repos
- **Check:** `README_LICENSE` — automated
- **Fix:** `fix-readme` skill — automated
- **Details:** README must contain a license heading or mention "MIT" license. A `## License` section with "MIT" is the standard format.

### 1.4 README must have CI badge

- **Applies to:** repos with CI workflows
- **Check:** not implemented
- **Fix:** not implemented
- **Details:** Repos that have a GitHub Actions CI workflow must display a CI status badge in the README.

### 1.5 Logo must exist

- **Applies to:** all repos
- **Check:** `LOGO_EXISTS` — automated
- **Fix:** `fix-logo` skill (delegates to `project-logo-author`) — automated
- **Details:** A logo must exist in a standard location (`logo.png`, `logo.svg`, `logo.jpg`, or under `assets/`, `images/`, `.github/`). Logo should be a square icon with transparent background, 512x512 or similar.

### 1.6 LICENSE must exist

- **Applies to:** all repos
- **Check:** `LICENSE_EXISTS` — automated
- **Fix:** `sync-license.sh` — automated
- **Details:** A `LICENSE`, `LICENSE.md`, or `LICENSE.txt` file must exist. All tsilva repos use MIT license. The sync script creates from template with current year and author.

### 1.7 .gitignore must exist

- **Applies to:** all repos
- **Check:** `GITIGNORE_EXISTS` — automated
- **Fix:** `sync-gitignore.sh` — automated
- **Details:** Every repo must have a `.gitignore` file.

### 1.8 .gitignore must include essential patterns

- **Applies to:** all repos
- **Check:** `GITIGNORE_COMPLETE` — automated
- **Fix:** `sync-gitignore.sh` — automated
- **Details:** `.gitignore` must include these patterns: `.env`, `.DS_Store`, `node_modules/`, `__pycache__/`, `*.pyc`, `.venv/`. The sync script appends missing rules from `gitignore.global`.

### 1.9 No tracked files matching gitignore

- **Applies to:** all repos
- **Check:** `TRACKED_IGNORED` — automated
- **Fix:** manual (`git rm --cached`)
- **Details:** Files that match `.gitignore` patterns must not be tracked by git. Detected via `git ls-files -i --exclude-standard`. Requires manual review before removal since untracking may affect collaborators.

### 1.10 GitHub description must match README tagline

- **Applies to:** all repos
- **Check:** not implemented
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
- **Check:** not implemented
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
- **Check:** not implemented
- **Fix:** not implemented
- **Details:** Python repos must have a GitHub Actions workflow that runs tests on push. Should reference the reusable `test.yml` workflow from this repo.

### 4.2 Release workflow for versioned projects

- **Applies to:** repos with version in `pyproject.toml`
- **Check:** not implemented
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
- **Check:** not implemented
- **Fix:** implicit via `release.yml` (chains `pii-scan.yml`)
- **Details:** Repositories must run gitleaks for secret/credential scanning as part of CI. Repos using the `release.yml` reusable workflow get this automatically. Repos with custom CI should add `pii-scan.yml` explicitly.

### 6.2 Pre-commit hooks for secret scanning

- **Applies to:** all repos
- **Check:** not implemented
- **Fix:** not implemented
- **Details:** Repos should configure pre-commit with gitleaks for local secret scanning before push. Requires a `.pre-commit-config.yaml` referencing `tsilva/.github` with the `gitleaks` hook ID.

---

## Automation Coverage

| Metric | Count | Rules |
|--------|-------|-------|
| **Audit checks** | 14 of 24 | 1.1-1.3, 1.5-1.9, 2.1, 3.1, 5.1-5.4 |
| **Automated fixes** (sync scripts) | 7 scripts covering 8 rules | 1.6-1.8, 1.10, 2.1, 5.1, 5.2, 5.4 |
| **AI-dependent fixes** (skills) | 3 skills covering 4 rules | 1.1-1.3, 1.5 |
| **Manual fix only** | 2 rules | 1.9, 5.3 |
| **No automation** | 10 rules | 1.4, 1.10 (check only), 3.2-3.5, 4.1-4.2, 6.1-6.2 |

## Implementation Backlog

Unimplemented rules, ordered by implementation complexity (simplest first):

| Priority | Check ID | Rule | Complexity |
|----------|----------|------|------------|
| 1 | `PYTHON_MIN_VERSION` | 3.3 — requires-python field | Simple pyproject.toml field check |
| 2 | `README_CI_BADGE` | 1.4 — CI badge in README | Regex for badge URL + workflow existence check |
| 3 | `PYTHON_CI_WORKFLOW` | 4.1 — CI workflow exists | Check for workflow YAML referencing reusable workflows |
| 4 | `REPO_DESCRIPTION` | 1.10 — description matches tagline | Compare GitHub API description vs README tagline |
| 5 | `PYTHON_UV_INSTALL` | 3.2 — UV installable | Validate pyproject.toml structure for PEP 621 |
| 6 | `PYTHON_CLI_PYPI` | 3.4 — CLI on PyPI | Detect `[project.scripts]`, verify release workflow |
| 7 | `RELEASE_WORKFLOW` | 4.2 — release workflow exists | Check versioned projects reference release.yml |
| 8 | `PII_SCAN_ENABLED` | 6.1 — gitleaks in CI | Implicit if using release.yml, explicit check otherwise |
| 9 | `PRECOMMIT_GITLEAKS` | 6.2 — pre-commit with gitleaks | Check .pre-commit-config.yaml for gitleaks hook |
| 10 | `PYTHON_CLI_HOMEBREW` | 3.5 — CLI on Homebrew | Needs Homebrew tap strategy decided first |
