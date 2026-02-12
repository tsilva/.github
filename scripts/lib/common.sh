#!/usr/bin/env bash
# Shared repo-iteration boilerplate for .github scripts
# Usage: source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
# Requires: lib/style.sh sourced first

# Guard against double-sourcing
[[ -n "${_COMMON_SH_LOADED:-}" ]] && return 0
_COMMON_SH_LOADED=1

# Script directory (of the sourcing script, not this file)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)}"
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$LIB_DIR/../.." && pwd)"

# --- Argument parsing ---
# Sets: DRY_RUN, FILTER, REPOS_DIR
# Accepts additional options via EXTRA_OPTS associative array
# Usage:
#   declare -A EXTRA_OPTS=(["-f|--format"]="FORMAT")
#   parse_args "$@"
DRY_RUN=false
FILTER=""
REPOS_DIR=""

parse_args() {
    local usage_fn="${USAGE_FN:-usage}"

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
            -h|--help)
                "$usage_fn" 0
                ;;
            -*)
                echo "Unknown option: $1" >&2
                "$usage_fn" 1
                ;;
            *)
                break
                ;;
        esac
    done

    if [[ $# -lt 1 ]]; then
        echo "Error: Missing required argument: repos-dir" >&2
        "$usage_fn" 1
    fi

    REPOS_DIR="$1"
    shift

    if [[ ! -d "$REPOS_DIR" ]]; then
        echo "Error: Directory does not exist: $REPOS_DIR" >&2
        exit 1
    fi

    # Return remaining args
    REMAINING_ARGS=("$@")
}

# --- Repo discovery ---
# Finds git repos in a directory, optionally filtered
# Sets: REPOS (array of full paths), REPO_NAMES (array of basenames)
discover_repos() {
    local dir="$1"
    local filter="${2:-$FILTER}"
    REPOS=()
    REPO_NAMES=()

    for repo_dir in "$dir"/*/; do
        [[ ! -d "$repo_dir/.git" ]] && continue
        repo_dir="${repo_dir%/}"
        local name
        name="$(basename "$repo_dir")"

        # Apply filter if set
        if [[ -n "$filter" ]] && [[ "$name" != *"$filter"* ]]; then
            continue
        fi

        REPOS+=("$repo_dir")
        REPO_NAMES+=("$name")
    done
}

# --- GitHub remote extraction ---
# Parses owner/repo from git remote URL (HTTPS or SSH)
extract_github_remote() {
    local url="$1"
    local repo

    # SSH format: git@github.com:owner/repo.git
    if [[ "$url" =~ git@github\.com:([^/]+/[^/]+)(\.git)?$ ]]; then
        repo="${BASH_REMATCH[1]}"
    # HTTPS format: https://github.com/owner/repo.git
    elif [[ "$url" =~ github\.com/([^/]+/[^/]+)(\.git)?$ ]]; then
        repo="${BASH_REMATCH[1]}"
    else
        return 1
    fi

    echo "${repo%.git}"
}

# --- Dependency checks ---
require_gh_auth() {
    if ! command -v gh &> /dev/null; then
        echo "Error: GitHub CLI (gh) is not installed or not in PATH" >&2
        exit 1
    fi
    if ! gh auth status &> /dev/null; then
        echo "Error: Not authenticated with GitHub CLI. Run 'gh auth login' first." >&2
        exit 1
    fi
}

require_command() {
    local cmd="$1"
    local install_hint="${2:-}"
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: $cmd is not installed or not in PATH" >&2
        [[ -n "$install_hint" ]] && echo "Install: $install_hint" >&2
        exit 1
    fi
}

# --- Shared constants ---

LOGO_LOCATIONS=(
    "logo.png" "logo.svg" "logo.jpg"
    "assets/logo.png" "assets/logo.svg"
    "images/logo.png" "images/logo.svg"
    ".github/logo.png" ".github/logo.svg"
)

# --- Shared check helpers ---

has_license_file() {
    for n in LICENSE LICENSE.md LICENSE.txt; do
        [[ -f "$1/$n" ]] && return 0
    done
    return 1
}

readme_has_license_ref() {
    tr '[:upper:]' '[:lower:]' < "$1" | grep -qE '## license|# license|mit license|\[mit\]'
}

has_sandbox_enabled() {
    local dir="$1"
    for settings_file in "$dir/.claude/settings.json" "$dir/.claude/settings.local.json"; do
        [[ -f "$settings_file" ]] && python3 -c "
import json, sys
try:
    data = json.load(open('$settings_file'))
    sys.exit(0 if isinstance(data.get('sandbox'), dict) and data['sandbox'].get('enabled') is True else 1)
except: sys.exit(1)
" 2>/dev/null && return 0
    done
    return 1
}
