#!/usr/bin/env bash
# DEPRECATED: Use 'tsilva-maintain fix' instead
# Optimizes Claude Code settings across all repos (removes redundant permissions, migrates WebFetch domains)
# Usage: ./scripts/sync-settings.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Optimizes Claude Code settings in all git repos by removing redundant
permissions and migrating WebFetch domains to sandbox network allowlists.

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -n, --dry-run   Print what would be done without executing
    -f, --filter    Only process repos matching pattern
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") --dry-run ~/repos
EOF
    exit "${1:-0}"
}

parse_args "$@"

# Counters
fixed=0
in_sync=0
failed=0
skipped=0

info "Syncing Claude Code settings in repos: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    settings_file="$dir/.claude/settings.local.json"

    if [[ ! -f "$settings_file" ]]; then
        skip "$repo_name (no settings.local.json)"
        ((skipped++))
        continue
    fi

    # Check if settings need fixing
    if python3 "$SCRIPT_DIR/settings_optimizer.py" --check clean --project-dir "$dir" 2>/dev/null; then
        success "$repo_name (settings clean)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name (would optimize settings)"
        ((fixed++))
        continue
    fi

    if python3 "$SCRIPT_DIR/settings_optimizer.py" auto-fix --project-dir "$dir" 2>/dev/null; then
        step "$repo_name (optimized settings)"
        ((fixed++))
    else
        error "$repo_name (failed to optimize settings)"
        ((failed++))
    fi
done

print_summary "Fixed" "$fixed" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
