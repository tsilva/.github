#!/usr/bin/env bash
# Ensures LICENSE file exists in all repos (MIT template)
# Usage: ./scripts/sync-license.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Ensures all git repos have a LICENSE file. Creates MIT LICENSE from template
with year and git author substitution for repos that are missing one.

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

TEMPLATE_FILE="$SCRIPT_DIR/templates/LICENSE"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Error: Template file not found: $TEMPLATE_FILE" >&2
    exit 1
fi

# Counters
created=0
in_sync=0
failed=0
skipped=0

info "Syncing LICENSE to repos in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    # Check if any license variant exists
    has_license=false
    for name in LICENSE LICENSE.md LICENSE.txt; do
        if [[ -f "$dir/$name" ]]; then
            has_license=true
            break
        fi
    done

    if $has_license; then
        success "$repo_name (license exists)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name (would create LICENSE)"
        ((created++))
        continue
    fi

    # Get author from git config
    author=$(git -C "$dir" config user.name 2>/dev/null || echo "Author")
    year=$(date +%Y)

    # Copy template with substitutions
    content=$(<"$TEMPLATE_FILE")
    content="${content//\[year\]/$year}"
    content="${content//\[fullname\]/$author}"

    if echo "$content" > "$dir/LICENSE"; then
        step "$repo_name (created LICENSE — MIT, $year, $author)"
        ((created++))
    else
        error "$repo_name (failed to create LICENSE)"
        ((failed++))
    fi
done

print_summary "Created" "$created" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
