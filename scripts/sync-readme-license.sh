#!/usr/bin/env bash
# Ensures README.md has a license section (appends ## License / MIT if missing)
# Usage: ./scripts/sync-readme-license.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Ensures all git repos with a README.md have a license section. Appends
"## License\n\nMIT" to READMEs that are missing a license reference.
Only acts when a LICENSE file also exists in the repo.

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
updated=0
in_sync=0
skipped=0
failed=0

info "Syncing README license sections in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    # Skip if no README.md
    if [[ ! -f "$dir/README.md" ]]; then
        skip "$repo_name (no README.md)"
        ((skipped++))
        continue
    fi

    # Skip if no LICENSE file
    has_license=false
    for name in LICENSE LICENSE.md LICENSE.txt; do
        if [[ -f "$dir/$name" ]]; then
            has_license=true
            break
        fi
    done

    if ! $has_license; then
        skip "$repo_name (no LICENSE file)"
        ((skipped++))
        continue
    fi

    # Check if README already mentions license
    content_lower=$(tr '[:upper:]' '[:lower:]' < "$dir/README.md")
    if echo "$content_lower" | grep -qE '## license|# license|mit license|\[mit\]'; then
        success "$repo_name (license section exists)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name (would append license section)"
        ((updated++))
        continue
    fi

    # Append license section
    if printf '\n## License\n\nMIT\n' >> "$dir/README.md"; then
        step "$repo_name (appended license section)"
        ((updated++))
    else
        error "$repo_name (failed to append license section)"
        ((failed++))
    fi
done

print_summary "Updated" "$updated" "In sync" "$in_sync" "Skipped" "$skipped" "Failed" "$failed"

[[ $failed -gt 0 ]] && exit 1
exit 0
