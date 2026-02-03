#!/usr/bin/env bash
# Syncs global gitignore rules to all repos from gitignore.global template
# Usage: ./scripts/sync-gitignore.sh <repos-dir>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Syncs global gitignore rules to all git repos in the specified directory.
Rules are loaded from gitignore.global in this repo.

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -n, --dry-run   Print what would be done without executing
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") --dry-run ~/repos
EOF
    exit "${1:-0}"
}

log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_skip() { echo -e "${YELLOW}→${NC} $1"; }
log_update() { echo -e "${BLUE}↻${NC} $1"; }
log_info() { echo -e "  $1"; }

# Parse options
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run)
            DRY_RUN=true
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

# Find the script's directory and the template file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/../gitignore.global"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Error: Template file not found: $TEMPLATE_FILE" >&2
    exit 1
fi

# Load rules from template (skip comments and empty lines)
RULES=()
while IFS= read -r line; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    RULES+=("$line")
done < "$TEMPLATE_FILE"

if [[ ${#RULES[@]} -eq 0 ]]; then
    echo "Error: No rules found in template file" >&2
    exit 1
fi

# Header to add when appending rules
HEADER="# Managed by tsilva/.github
# Do not remove - synced automatically"

# Counters
updated=0
failed=0
skipped=0
in_sync=0

echo "Syncing gitignore rules to repos in: $REPOS_DIR"
echo "Template: $TEMPLATE_FILE (${#RULES[@]} rules)"
if $DRY_RUN; then
    echo -e "${YELLOW}DRY RUN MODE - no changes will be made${NC}"
fi
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

    gitignore_file="$dir/.gitignore"
    existing_content=""

    # Read existing .gitignore if it exists
    if [[ -f "$gitignore_file" ]]; then
        existing_content=$(cat "$gitignore_file")
    fi

    # Find missing rules
    missing_rules=()
    for rule in "${RULES[@]}"; do
        # Check if rule exists in the file (exact line match)
        if ! grep -qxF "$rule" "$gitignore_file" 2>/dev/null; then
            missing_rules+=("$rule")
        fi
    done

    # If no missing rules, repo is in sync
    if [[ ${#missing_rules[@]} -eq 0 ]]; then
        log_success "$repo_name (all rules present)"
        ((in_sync++))
        continue
    fi

    # Report and optionally update
    if $DRY_RUN; then
        log_update "$repo_name (${#missing_rules[@]} rules missing)"
        for rule in "${missing_rules[@]}"; do
            log_info "+ $rule"
        done
        ((updated++))
    else
        # Build the content to append
        append_content=""

        # Add newline if file exists and doesn't end with newline
        if [[ -n "$existing_content" && "${existing_content: -1}" != $'\n' ]]; then
            append_content=$'\n'
        fi

        # Add blank line separator if file has content
        if [[ -n "$existing_content" ]]; then
            append_content+=$'\n'
        fi

        # Add header and rules
        append_content+="$HEADER"$'\n'
        for rule in "${missing_rules[@]}"; do
            append_content+="$rule"$'\n'
        done

        # Append to file
        if echo -n "$append_content" >> "$gitignore_file"; then
            log_update "$repo_name (added ${#missing_rules[@]} rules)"
            for rule in "${missing_rules[@]}"; do
                log_info "+ $rule"
            done
            ((updated++))
        else
            log_error "$repo_name (failed to update .gitignore)"
            ((failed++))
        fi
    fi
done

# Summary
echo ""
echo "Summary:"
echo "  Updated:  $updated"
echo "  In sync:  $in_sync"
echo "  Failed:   $failed"
echo "  Skipped:  $skipped"

# Exit with error if any failed
if [[ $failed -gt 0 ]]; then
    exit 1
fi
