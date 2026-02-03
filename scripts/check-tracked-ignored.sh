#!/usr/bin/env bash
# Warns about files that are tracked in git but match gitignore patterns
# Usage: ./scripts/check-tracked-ignored.sh <repos-dir>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Checks all git repos for files that are tracked but match gitignore patterns.
These files should typically be untracked (removed from git with git rm --cached).

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -n, --dry-run   Same as normal mode (this is a read-only operation)
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
EOF
    exit "${1:-0}"
}

log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_skip() { echo -e "${YELLOW}→${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_info() { echo -e "    $1"; }

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run)
            # No-op for this read-only script, but accept for consistency
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

# Validate arguments
if [[ $# -lt 1 ]]; then
    echo "Error: Missing required argument: repos-dir" >&2
    usage 1
fi

REPOS_DIR="$1"

# Validate repos directory
if [[ ! -d "$REPOS_DIR" ]]; then
    echo "Error: Directory does not exist: $REPOS_DIR" >&2
    exit 1
fi

# Counters
clean=0
warnings=0
failed=0
skipped=0

echo "Checking for tracked files that should be ignored in: $REPOS_DIR"
echo ""

# Iterate over subdirectories
for dir in "$REPOS_DIR"/*/; do
    # Remove trailing slash for cleaner output
    dir="${dir%/}"
    repo_name="$(basename "$dir")"

    # Skip if not a git repository
    if [[ ! -d "$dir/.git" ]]; then
        log_skip "$repo_name (not a git repo)"
        ((skipped++))
        continue
    fi

    # Check for tracked files that match gitignore patterns
    # git ls-files -i --exclude-standard lists tracked files that match .gitignore
    tracked_ignored=$(git -C "$dir" ls-files -i --exclude-standard 2>/dev/null || true)

    if [[ -z "$tracked_ignored" ]]; then
        log_success "$repo_name (clean)"
        ((clean++))
        continue
    fi

    # Count files
    file_count=$(echo "$tracked_ignored" | wc -l | tr -d ' ')

    log_warning "$repo_name: $file_count tracked file(s) should be ignored"

    # Print each file
    while IFS= read -r file; do
        log_info "$file"
    done <<< "$tracked_ignored"

    ((warnings++))
done

# Summary
echo ""
echo "Summary:"
echo "  Clean:    $clean"
echo "  Warnings: $warnings"
echo "  Failed:   $failed"
echo "  Skipped:  $skipped"

# Exit with warning code if any issues found
if [[ $warnings -gt 0 ]]; then
    echo ""
    echo "To fix tracked files that should be ignored, run in each repo:"
    echo "  git rm --cached <file>"
    echo "  git commit -m \"Stop tracking ignored file\""
    exit 1
fi
