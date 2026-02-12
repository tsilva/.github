#!/usr/bin/env bash
# Runs all sync scripts in sequence
# Usage: ./scripts/sync-all.sh [--dry-run] [--filter PATTERN] [--online] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

ONLINE=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Runs all sync scripts in sequence to enforce org-wide standards.

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -n, --dry-run   Pass --dry-run to all sub-scripts
    -f, --filter    Only process repos matching pattern
    -o, --online    Also run online sync scripts (e.g. sync-repo-descriptions.sh)
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") --dry-run ~/repos
    $(basename "$0") --online ~/repos
EOF
    exit "${1:-0}"
}

# Custom parse_args to handle --online
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
        -o|--online)
            ONLINE=true
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

# Build common args
COMMON_ARGS=()
[[ "$DRY_RUN" == "true" ]] && COMMON_ARGS+=("--dry-run")
[[ -n "$FILTER" ]] && COMMON_ARGS+=("--filter" "$FILTER")
COMMON_ARGS+=("$REPOS_DIR")

# Local sync scripts (safe, no network)
LOCAL_SCRIPTS=(
    "sync-license.sh"
    "sync-claude-md.sh"
    "sync-sandbox.sh"
    "sync-settings.sh"
    "sync-dependabot.sh"
    "sync-gitignore.sh"
    "sync-precommit.sh"
    "sync-readme-license.sh"
    "sync-readme-logo.sh"
)

# Online sync scripts (require gh auth, modify GitHub API)
ONLINE_SCRIPTS=(
    "sync-repo-descriptions.sh"
)

banner "Sync All"
info "Directory: $REPOS_DIR"
dry_run_banner
echo ""

failed_scripts=()
passed_scripts=()

run_script() {
    local script="$1"
    local script_path="$SCRIPT_DIR/$script"

    if [[ ! -x "$script_path" ]]; then
        error "$script (not found or not executable)"
        failed_scripts+=("$script")
        return
    fi

    header "$script"
    if "$script_path" "${COMMON_ARGS[@]}"; then
        passed_scripts+=("$script")
    else
        error "$script exited with errors"
        failed_scripts+=("$script")
    fi
}

for script in "${LOCAL_SCRIPTS[@]}"; do
    run_script "$script"
done

if $ONLINE; then
    section "Online scripts"
    for script in "${ONLINE_SCRIPTS[@]}"; do
        run_script "$script"
    done
fi

# Summary
total=${#passed_scripts[@]}
failed=${#failed_scripts[@]}
((total += failed))

echo ""
banner "Sync Complete"
echo -e "  Scripts run: ${total}"
echo -e "  Passed:      ${GREEN}${#passed_scripts[@]}${NC}"
if [[ $failed -gt 0 ]]; then
    echo -e "  Failed:      ${RED}${failed}${NC}"
    for s in "${failed_scripts[@]}"; do
        detail "${RED}$s${NC}"
    done
fi

[[ $failed -gt 0 ]] && exit 1
exit 0
