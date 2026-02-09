#!/usr/bin/env bash
# Ensures CLAUDE.md exists in all repos
# Usage: ./scripts/sync-claude-md.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Ensures all git repos have a CLAUDE.md file. Creates a minimal template with
project name and README maintenance instruction for repos that are missing one.

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

TEMPLATE_FILE="$SCRIPT_DIR/templates/CLAUDE.md"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Error: Template file not found: $TEMPLATE_FILE" >&2
    exit 1
fi

# Counters
created=0
in_sync=0
failed=0
skipped=0

info "Syncing CLAUDE.md to repos in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    if [[ -f "$dir/CLAUDE.md" ]]; then
        success "$repo_name (CLAUDE.md exists)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name (would create CLAUDE.md)"
        ((created++))
        continue
    fi

    # Copy template with project name substitution
    content=$(<"$TEMPLATE_FILE")
    content="${content//\[project-name\]/$repo_name}"

    if echo "$content" > "$dir/CLAUDE.md"; then
        step "$repo_name (created CLAUDE.md)"
        ((created++))
    else
        error "$repo_name (failed to create CLAUDE.md)"
        ((failed++))
    fi
done

print_summary "Created" "$created" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
