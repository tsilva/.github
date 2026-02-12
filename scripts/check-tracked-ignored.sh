#!/usr/bin/env bash
# DEPRECATED: Use 'tsilva-maintain report tracked-ignored' instead
# Warns about files that are tracked in git but match gitignore patterns
# Usage: ./scripts/check-tracked-ignored.sh [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Checks all git repos for files that are tracked but match gitignore patterns.
These files should typically be untracked (removed from git with git rm --cached).

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -n, --dry-run   Same as normal mode (this is a read-only operation)
    -f, --filter    Only process repos matching pattern
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
EOF
    exit "${1:-0}"
}

parse_args "$@"

# Counters
clean=0
warnings=0
failed=0
skipped=0

info "Checking for tracked files that should be ignored in: $REPOS_DIR"
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    tracked_ignored=$(git -C "$dir" ls-files -i --exclude-standard 2>/dev/null || true)

    if [[ -z "$tracked_ignored" ]]; then
        success "$repo_name (clean)"
        ((clean++))
        continue
    fi

    file_count=$(echo "$tracked_ignored" | wc -l | tr -d ' ')
    warn "$repo_name: $file_count tracked file(s) should be ignored"

    while IFS= read -r file; do
        detail "  $file"
    done <<< "$tracked_ignored"

    ((warnings++))
done

print_summary "Clean" "$clean" "Warnings" "$warnings" "Failed" "$failed" "Skipped" "$skipped"

if [[ $warnings -gt 0 ]]; then
    echo ""
    echo "To fix tracked files that should be ignored, run in each repo:"
    echo "  git rm --cached <file>"
    echo "  git commit -m \"Stop tracking ignored file\""
    exit 1
fi
