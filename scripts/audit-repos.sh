#!/usr/bin/env bash
# DEPRECATED: Use 'tsilva-maintain audit' instead
# Comprehensive repo compliance audit
# Usage: ./scripts/audit-repos.sh [--dry-run] [--filter PATTERN] [--json] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

JSON_OUTPUT=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Audits all git repos for compliance with tsilva org standards.

Checks: default branch, README (exists, current, license, logo, CI badge),
logo, LICENSE, .gitignore, CLAUDE.md, sandbox settings, dependabot config,
pre-commit gitleaks hook, tracked-ignored files, pending commits, stale branches,
Python config (pyproject.toml, min version), CI/release workflows, PII scanning,
repo description, Claude settings (dangerous patterns, redundant permissions).

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -n, --dry-run   Same as normal mode (this is a read-only operation)
    -f, --filter    Only process repos matching pattern
    -j, --json      Output JSON report to stdout
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") --json ~/repos
    $(basename "$0") --filter my-project ~/repos
EOF
    exit "${1:-0}"
}

# Override parse_args to add --json
parse_args_audit() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -f|--filter)
                FILTER="${2:?Error: --filter requires a value}"
                shift 2
                ;;
            -j|--json)
                JSON_OUTPUT=true
                shift
                ;;
            -h|--help)
                usage 0
                ;;
            -*)
                echo "Unknown option: $1" >&2
                usage 1
                ;;
            *)
                break
                ;;
        esac
    done

    if [[ $# -lt 1 ]]; then
        echo "Error: Missing required argument: repos-dir" >&2
        usage 1
    fi

    REPOS_DIR="$1"

    if [[ ! -d "$REPOS_DIR" ]]; then
        echo "Error: Directory does not exist: $REPOS_DIR" >&2
        exit 1
    fi
}

parse_args_audit "$@"

# --- Gitignore essential patterns ---
ESSENTIAL_GITIGNORE=(
    ".env"
    ".DS_Store"
    "node_modules/"
    "__pycache__/"
    "*.pyc"
    ".venv/"
)

# --- Check functions ---
# Each outputs "PASS" or "FAIL<tab>message"

check_readme_exists() {
    [[ -f "$1/README.md" ]] && echo "PASS" || echo "FAIL	README.md not found"
}

check_readme_current() {
    local dir="$1"
    local readme="$dir/README.md"

    [[ ! -f "$readme" ]] && { echo "FAIL	README.md does not exist"; return; }

    local content
    content=$(<"$readme")
    local issues=()

    # Check for placeholder content
    for placeholder in "TODO" "FIXME" "Coming soon" "Work in progress" "Under construction" "[Insert" "Lorem ipsum"; do
        if echo "$content" | grep -qi "$placeholder" 2>/dev/null; then
            issues+=("Contains placeholder: '$placeholder'")
        fi
    done

    # Check for very short README
    local char_count=${#content}
    if [[ $char_count -lt 100 ]]; then
        issues+=("README is very short (<100 chars)")
    fi

    # Check for missing sections
    local content_lower
    content_lower=$(echo "$content" | tr '[:upper:]' '[:lower:]')
    local has_install=false has_usage=false
    echo "$content_lower" | grep -qE "install|setup|getting started" && has_install=true
    echo "$content_lower" | grep -qE "usage|example|how to" && has_usage=true

    if ! $has_install && ! $has_usage; then
        issues+=("Missing installation/usage sections")
    fi

    if [[ ${#issues[@]} -eq 0 ]]; then
        echo "PASS"
    else
        local msg
        msg=$(IFS='; '; echo "${issues[*]}")
        echo "FAIL	$msg"
    fi
}

check_readme_has_license() {
    local readme="$1/README.md"
    [[ ! -f "$readme" ]] && { echo "FAIL	README.md does not exist"; return; }

    if readme_has_license_ref "$readme"; then
        echo "PASS"
    else
        echo "FAIL	README missing license reference"
    fi
}

check_logo_exists() {
    local dir="$1"
    for pattern in "${LOGO_LOCATIONS[@]}"; do
        if [[ -f "$dir/$pattern" ]]; then
            echo "PASS"
            return
        fi
    done
    echo "FAIL	No logo found in standard locations"
}

check_license_exists() {
    local dir="$1"
    has_license_file "$dir" && { echo "PASS"; return; }
    echo "FAIL	No LICENSE file found"
}

check_gitignore_exists() {
    [[ -f "$1/.gitignore" ]] && echo "PASS" || echo "FAIL	.gitignore not found"
}

check_gitignore_complete() {
    local gitignore="$1/.gitignore"
    [[ ! -f "$gitignore" ]] && { echo "FAIL	.gitignore does not exist"; return; }

    local content_lower
    content_lower=$(tr '[:upper:]' '[:lower:]' < "$gitignore")
    local missing=()

    for pattern in "${ESSENTIAL_GITIGNORE[@]}"; do
        local pattern_base
        pattern_base=$(echo "${pattern%%/}" | tr '[:upper:]' '[:lower:]')
        if ! echo "$content_lower" | grep -q "$pattern_base"; then
            missing+=("$pattern")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        echo "PASS"
    else
        echo "FAIL	Missing ${#missing[@]} patterns: ${missing[*]}"
    fi
}

check_claude_md_exists() {
    [[ -f "$1/CLAUDE.md" ]] && echo "PASS" || echo "FAIL	CLAUDE.md not found"
}

check_claude_sandbox() {
    local dir="$1"
    if has_sandbox_enabled "$dir"; then
        echo "PASS"
    else
        echo "FAIL	Sandbox not enabled"
    fi
}

check_dependabot_exists() {
    local dir="$1"
    if [[ -f "$dir/.github/dependabot.yml" || -f "$dir/.github/dependabot.yaml" ]]; then
        echo "PASS"
    else
        echo "FAIL	No .github/dependabot.yml"
    fi
}

check_precommit_gitleaks() {
    local dir="$1"
    local repo_name
    repo_name=$(basename "$dir")

    # Skip .github repo (it defines the hook, doesn't consume it)
    if [[ "$repo_name" == ".github" ]]; then
        echo "SKIP"
        return
    fi

    local config="$dir/.pre-commit-config.yaml"
    if [[ ! -f "$config" ]]; then
        echo "FAIL	.pre-commit-config.yaml not found"
        return
    fi

    if grep -q "tsilva/\.github" "$config" 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL	.pre-commit-config.yaml missing gitleaks hook"
    fi
}

check_tracked_ignored() {
    local dir="$1"
    local tracked_ignored
    tracked_ignored=$(git -C "$dir" ls-files -i --exclude-standard 2>/dev/null || true)
    if [[ -z "$tracked_ignored" ]]; then
        echo "PASS"
    else
        local count
        count=$(echo "$tracked_ignored" | wc -l | tr -d ' ')
        echo "FAIL	$count tracked file(s) match gitignore"
    fi
}

check_python_pyproject() {
    local dir="$1"

    # Detect if it's a Python project
    local is_python=false
    for indicator in setup.py requirements.txt setup.cfg Pipfile; do
        [[ -f "$dir/$indicator" ]] && { is_python=true; break; }
    done

    if ! $is_python; then
        # Check for .py files (more than 2 non-test files)
        local py_count
        py_count=$(find "$dir" -name "*.py" -not -name "test_*" -not -path "*/.venv/*" -not -path "*/node_modules/*" 2>/dev/null | head -3 | wc -l | tr -d ' ')
        [[ "$py_count" -gt 2 ]] && is_python=true
    fi

    if ! $is_python; then
        echo "SKIP"
        return
    fi

    [[ -f "$dir/pyproject.toml" ]] && echo "PASS" || echo "FAIL	Python project missing pyproject.toml"
}

check_settings_dangerous() {
    local dir="$1"
    local settings_file="$dir/.claude/settings.local.json"
    [[ ! -f "$settings_file" ]] && { echo "SKIP"; return; }

    if python3 "$SCRIPT_DIR/settings_optimizer.py" --check dangerous --project-dir "$dir" 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL	Dangerous permission patterns detected"
    fi
}

check_settings_clean() {
    local dir="$1"
    local settings_file="$dir/.claude/settings.local.json"
    [[ ! -f "$settings_file" ]] && { echo "SKIP"; return; }

    if python3 "$SCRIPT_DIR/settings_optimizer.py" --check clean --project-dir "$dir" 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL	Redundant permissions or unmigrated WebFetch domains"
    fi
}

check_python_min_version() {
    local dir="$1"
    [[ ! -f "$dir/pyproject.toml" ]] && { echo "SKIP"; return; }

    if python3 -c "
import tomllib, sys
with open('$dir/pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
rp = data.get('project', {}).get('requires-python', '')
sys.exit(0 if rp else 1)
" 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL	pyproject.toml missing requires-python"
    fi
}

check_readme_ci_badge() {
    local dir="$1"
    local readme="$dir/README.md"

    # Skip if no workflows exist
    if ! ls "$dir/.github/workflows/"*.yml &>/dev/null && \
       ! ls "$dir/.github/workflows/"*.yaml &>/dev/null; then
        echo "SKIP"
        return
    fi

    [[ ! -f "$readme" ]] && { echo "FAIL	README.md does not exist"; return; }

    if grep -qE 'actions/workflows/.*badge|shields\.io.*workflow|!\[.*\]\(.*actions/workflows' "$readme" 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL	README missing CI badge"
    fi
}

check_ci_workflow() {
    local dir="$1"

    # Skip if not a Python project
    local is_python=false
    [[ -f "$dir/pyproject.toml" || -f "$dir/setup.py" || -f "$dir/requirements.txt" ]] && is_python=true
    if ! $is_python; then
        echo "SKIP"
        return
    fi

    if ls "$dir/.github/workflows/"*.yml "$dir/.github/workflows/"*.yaml 2>/dev/null | \
       xargs grep -lE 'tsilva/\.github/.*/(test|release|ci)\.yml|pytest' 2>/dev/null | \
       head -1 | grep -q .; then
        echo "PASS"
    else
        echo "FAIL	No CI workflow referencing test.yml/release.yml/pytest"
    fi
}

check_release_workflow() {
    local dir="$1"
    [[ ! -f "$dir/pyproject.toml" ]] && { echo "SKIP"; return; }

    # Skip if no version in pyproject.toml
    if ! python3 -c "
import tomllib, sys
with open('$dir/pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
v = data.get('project', {}).get('version', '')
sys.exit(0 if v else 1)
" 2>/dev/null; then
        echo "SKIP"
        return
    fi

    if ls "$dir/.github/workflows/"*.yml "$dir/.github/workflows/"*.yaml 2>/dev/null | \
       xargs grep -lE 'tsilva/\.github/.*/(release|publish-pypi)\.yml' 2>/dev/null | \
       head -1 | grep -q .; then
        echo "PASS"
    else
        echo "FAIL	Versioned project missing release workflow"
    fi
}

check_pii_scan() {
    local dir="$1"

    # Skip if no workflows exist
    if ! ls "$dir/.github/workflows/"*.yml &>/dev/null && \
       ! ls "$dir/.github/workflows/"*.yaml &>/dev/null; then
        echo "SKIP"
        return
    fi

    if ls "$dir/.github/workflows/"*.yml "$dir/.github/workflows/"*.yaml 2>/dev/null | \
       xargs grep -lE 'pii-scan\.yml|release\.yml|gitleaks-action' 2>/dev/null | \
       head -1 | grep -q .; then
        echo "PASS"
    else
        echo "FAIL	No PII scanning in CI workflows"
    fi
}

check_repo_description() {
    local dir="$1"

    # Skip if gh not available or not authenticated
    if ! command -v gh &>/dev/null || ! gh auth status &>/dev/null 2>&1; then
        echo "SKIP"
        return
    fi

    local remote_url
    remote_url=$(git -C "$dir" remote get-url origin 2>/dev/null || true)
    [[ -z "$remote_url" ]] && { echo "SKIP"; return; }

    local github_repo
    github_repo=$(extract_github_remote "$remote_url" 2>/dev/null || true)
    [[ -z "$github_repo" ]] && { echo "SKIP"; return; }

    # Extract local tagline
    local tagline=""
    if [[ -f "$dir/README.md" ]]; then
        tagline=$(python3 "$SCRIPT_DIR/lib/extract_tagline.py" "$dir/README.md" 2>/dev/null || true)
    fi
    [[ -z "$tagline" ]] && { echo "SKIP"; return; }

    local github_desc
    github_desc=$(gh repo view "$github_repo" --json description -q '.description // ""' 2>/dev/null || true)

    if [[ "$tagline" == "$github_desc" ]]; then
        echo "PASS"
    else
        echo "FAIL	Description mismatch (GitHub vs README tagline)"
    fi
}

check_default_branch() {
    local dir="$1"
    if git -C "$dir" rev-parse --verify main &>/dev/null; then
        echo "PASS"
    else
        echo "FAIL	No 'main' branch found"
    fi
}

check_readme_logo() {
    local dir="$1"
    local readme="$dir/README.md"
    [[ ! -f "$readme" ]] && { echo "FAIL	README.md does not exist"; return; }
    if grep -qiE '!\[.*\]\(\.?/?((assets|images|\.github)/)?logo\.' "$readme" 2>/dev/null || \
       grep -qiE '<img[^>]+src=.\.?/?((assets|images|\.github)/)?logo\.' "$readme" 2>/dev/null; then
        echo "PASS"; return
    fi
    echo "FAIL	README does not reference logo"
}

check_pending_commits() {
    local dir="$1"
    local issues=()
    local porcelain
    porcelain=$(git -C "$dir" status --porcelain 2>/dev/null || true)
    if [[ -n "$porcelain" ]]; then
        local count
        count=$(echo "$porcelain" | wc -l | tr -d ' ')
        issues+=("$count uncommitted change(s)")
    fi
    local unpushed
    unpushed=$(git -C "$dir" log '@{u}..' --oneline 2>/dev/null || true)
    if [[ -n "$unpushed" ]]; then
        local count
        count=$(echo "$unpushed" | wc -l | tr -d ' ')
        issues+=("$count unpushed commit(s)")
    fi
    if [[ ${#issues[@]} -eq 0 ]]; then
        echo "PASS"
    else
        local msg
        msg=$(IFS='; '; echo "${issues[*]}")
        echo "FAIL	$msg"
    fi
}

check_stale_branches() {
    local dir="$1"
    local issues=()
    # Merged into main (excluding main/master)
    local merged
    merged=$(git -C "$dir" branch --merged main 2>/dev/null \
        | sed 's/^[* ] //' \
        | grep -vE '^(main|master)$' \
        || true)
    if [[ -n "$merged" ]]; then
        local count
        count=$(echo "$merged" | wc -l | tr -d ' ')
        local names
        names=$(echo "$merged" | paste -sd ',' - | sed 's/,/, /g')
        issues+=("$count merged branch(es): $names")
    fi
    # Inactive >90 days (exclude main/master)
    local cutoff
    cutoff=$(( $(date +%s) - 90 * 86400 ))
    local stale_names=()
    while IFS=' ' read -r branch epoch; do
        [[ -z "$branch" ]] && continue
        [[ "$branch" == "main" || "$branch" == "master" ]] && continue
        if [[ "$epoch" -lt "$cutoff" ]]; then
            stale_names+=("$branch")
        fi
    done < <(git -C "$dir" for-each-ref --format='%(refname:short) %(committerdate:unix)' refs/heads/ 2>/dev/null)
    if [[ ${#stale_names[@]} -gt 0 ]]; then
        local names
        names=$(IFS=', '; echo "${stale_names[*]}")
        issues+=("${#stale_names[@]} stale branch(es) (>90d): $names")
    fi
    if [[ ${#issues[@]} -eq 0 ]]; then
        echo "PASS"
    else
        local msg
        msg=$(IFS='; '; echo "${issues[*]}")
        echo "FAIL	$msg"
    fi
}

# --- All checks in order ---
ALL_CHECKS=(
    "DEFAULT_BRANCH:check_default_branch"
    "README_EXISTS:check_readme_exists"
    "README_CURRENT:check_readme_current"
    "README_LICENSE:check_readme_has_license"
    "README_LOGO:check_readme_logo"
    "LOGO_EXISTS:check_logo_exists"
    "LICENSE_EXISTS:check_license_exists"
    "GITIGNORE_EXISTS:check_gitignore_exists"
    "GITIGNORE_COMPLETE:check_gitignore_complete"
    "CLAUDE_MD_EXISTS:check_claude_md_exists"
    "CLAUDE_SANDBOX:check_claude_sandbox"
    "DEPENDABOT_EXISTS:check_dependabot_exists"
    "PRECOMMIT_GITLEAKS:check_precommit_gitleaks"
    "TRACKED_IGNORED:check_tracked_ignored"
    "PENDING_COMMITS:check_pending_commits"
    "STALE_BRANCHES:check_stale_branches"
    "PYTHON_PYPROJECT:check_python_pyproject"
    "PYTHON_MIN_VERSION:check_python_min_version"
    "SETTINGS_DANGEROUS:check_settings_dangerous"
    "SETTINGS_CLEAN:check_settings_clean"
    "README_CI_BADGE:check_readme_ci_badge"
    "CI_WORKFLOW:check_ci_workflow"
    "RELEASE_WORKFLOW:check_release_workflow"
    "PII_SCAN:check_pii_scan"
    "REPO_DESCRIPTION:check_repo_description"
)

# --- Run audit ---
discover_repos "$REPOS_DIR"

if [[ ${#REPOS[@]} -eq 0 ]]; then
    echo "No git repositories found in: $REPOS_DIR"
    exit 0
fi

# JSON accumulator
json_repos="["
json_first_repo=true

# Totals
total_passed=0
total_failed=0
total_skipped=0

if ! $JSON_OUTPUT; then
    banner "Repo Audit"
    info "Directory: $REPOS_DIR"
    info "Repositories: ${#REPOS[@]}"
    echo ""
fi

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    repo_passed=0
    repo_failed=0
    repo_skipped=0
    failed_checks=()
    failed_messages=()

    # JSON per-check accumulator
    json_checks="["
    json_first_check=true

    for check_entry in "${ALL_CHECKS[@]}"; do
        check_name="${check_entry%%:*}"
        check_fn="${check_entry##*:}"

        result=$("$check_fn" "$dir")

        if [[ "$result" == "PASS" ]]; then
            ((repo_passed++))
            status="passed"
            message=""
        elif [[ "$result" == "SKIP" ]]; then
            ((repo_skipped++))
            ((repo_passed++))  # Skips count as passed
            status="skipped"
            message=""
        else
            ((repo_failed++))
            message="${result#FAIL	}"
            status="failed"
            failed_checks+=("$check_name")
            failed_messages+=("$message")
        fi

        # Build JSON check entry
        if $JSON_OUTPUT; then
            $json_first_check || json_checks+=","
            json_first_check=false
            # Escape message for JSON
            escaped_msg=$(echo "$message" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g')
            json_checks+="{\"check\":\"$check_name\",\"status\":\"$status\",\"message\":\"$escaped_msg\"}"
        fi
    done

    json_checks+="]"

    ((total_passed += repo_passed))
    ((total_failed += repo_failed))
    ((total_skipped += repo_skipped))

    # Human-readable output
    if ! $JSON_OUTPUT; then
        if [[ $repo_failed -eq 0 ]]; then
            success "$repo_name (${repo_passed}/${repo_passed} passed)"
        else
            error "$repo_name (${repo_failed} failed)"
            for j in "${!failed_checks[@]}"; do
                detail "${RED}${failed_checks[$j]}${NC}: ${failed_messages[$j]}"
            done
        fi
    fi

    # Build JSON repo entry
    if $JSON_OUTPUT; then
        $json_first_repo || json_repos+=","
        json_first_repo=false
        json_repos+="{\"repo\":\"$repo_name\",\"path\":\"$dir\",\"checks\":$json_checks,\"summary\":{\"passed\":$repo_passed,\"failed\":$repo_failed,\"skipped\":$repo_skipped}}"
    fi
done

json_repos+="]"

# Overall summary
total_checks=$((total_passed + total_failed))
pass_rate=0
if [[ $total_checks -gt 0 ]]; then
    pass_rate=$(( (total_passed * 1000 / total_checks + 5) / 10 ))
fi

if $JSON_OUTPUT; then
    # Detect GitHub user from first repo
    github_user=""
    if [[ ${#REPOS[@]} -gt 0 ]]; then
        remote_url=$(git -C "${REPOS[0]}" remote get-url origin 2>/dev/null || true)
        if [[ -n "$remote_url" ]]; then
            github_user=$(extract_github_remote "$remote_url" 2>/dev/null | cut -d/ -f1 || true)
        fi
    fi

    cat <<ENDJSON
{
  "audit_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "repos_dir": "$REPOS_DIR",
  "github_user": "$github_user",
  "repos_count": ${#REPOS[@]},
  "repos": $json_repos,
  "summary": {
    "total_checks": $total_checks,
    "passed": $total_passed,
    "failed": $total_failed,
    "pass_rate": $pass_rate
  }
}
ENDJSON
else
    echo ""
    header "Results"
    echo -e "  Checks:    ${total_passed}/${total_checks} passed (${pass_rate}%)"
    echo -e "  Passed:    ${GREEN}${total_passed}${NC}"
    echo -e "  Failed:    ${RED}${total_failed}${NC}"
    [[ $total_skipped -gt 0 ]] && echo -e "  Skipped:   ${DIM}${total_skipped}${NC}"
fi

[[ $total_failed -gt 0 ]] && exit 1
exit 0
