#!/usr/bin/env bash
# DEPRECATED: Use 'tsilva-maintain fix' instead
# Syncs global gitignore rules to all repos from gitignore.global template
# Usage: ./scripts/sync-gitignore.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Syncs global gitignore rules to all git repos in the specified directory.
Rules are loaded from gitignore.global in this repo.

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

# Find template file
TEMPLATE_FILE="$REPO_ROOT/gitignore.global"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Error: Template file not found: $TEMPLATE_FILE" >&2
    exit 1
fi

# Load rules from template (skip comments and empty lines)
RULES=()
while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    RULES+=("$line")
done < "$TEMPLATE_FILE"

if [[ ${#RULES[@]} -eq 0 ]]; then
    echo "Error: No rules found in template file" >&2
    exit 1
fi

# Header to add when appending rules
MANAGED_HEADER="# Managed by tsilva/.github
# Do not remove - synced automatically"

# Counters
updated=0
failed=0
skipped=0
in_sync=0

info "Syncing gitignore rules to repos in: $REPOS_DIR"
dim "Template: $TEMPLATE_FILE (${#RULES[@]} rules)"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"
    gitignore_file="$dir/.gitignore"
    existing_content=""

    if [[ -f "$gitignore_file" ]]; then
        existing_content=$(cat "$gitignore_file")
    fi

    # Find missing rules
    missing_rules=()
    for rule in "${RULES[@]}"; do
        if ! grep -qxF "$rule" "$gitignore_file" 2>/dev/null; then
            missing_rules+=("$rule")
        fi
    done

    if [[ ${#missing_rules[@]} -eq 0 ]]; then
        success "$repo_name (all rules present)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name (${#missing_rules[@]} rules missing)"
        for rule in "${missing_rules[@]}"; do
            detail "+ $rule"
        done
        ((updated++))
    else
        append_content=""

        if [[ -n "$existing_content" && "${existing_content: -1}" != $'\n' ]]; then
            append_content=$'\n'
        fi
        if [[ -n "$existing_content" ]]; then
            append_content+=$'\n'
        fi

        append_content+="$MANAGED_HEADER"$'\n'
        for rule in "${missing_rules[@]}"; do
            append_content+="$rule"$'\n'
        done

        if echo -n "$append_content" >> "$gitignore_file"; then
            step "$repo_name (added ${#missing_rules[@]} rules)"
            for rule in "${missing_rules[@]}"; do
                detail "+ $rule"
            done
            ((updated++))
        else
            error "$repo_name (failed to update .gitignore)"
            ((failed++))
        fi
    fi
done

print_summary "Updated" "$updated" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
