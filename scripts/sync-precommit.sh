#!/usr/bin/env bash
# DEPRECATED: Use 'tsilva-maintain fix' instead
# Ensures .pre-commit-config.yaml has gitleaks hook in all repos
# Usage: ./scripts/sync-precommit.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Ensures all git repos have a .pre-commit-config.yaml with the gitleaks hook
from tsilva/.github. Creates file from template if missing, or appends the
repo block if the file exists but lacks the hook.

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

TEMPLATE_FILE="$SCRIPT_DIR/templates/pre-commit-config.yaml"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Error: Template file not found: $TEMPLATE_FILE" >&2
    exit 1
fi

# Counters
created=0
updated=0
in_sync=0
failed=0
skipped=0

info "Syncing pre-commit gitleaks hook to repos in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"
    config_file="$dir/.pre-commit-config.yaml"

    # Skip .github repo itself (it defines the hook, doesn't consume it)
    if [[ "$repo_name" == ".github" ]]; then
        skip "$repo_name (defines the hook)"
        ((skipped++))
        continue
    fi

    if [[ -f "$config_file" ]]; then
        # File exists — check if it already references tsilva/.github
        if grep -q "tsilva/\.github" "$config_file" 2>/dev/null; then
            success "$repo_name (gitleaks hook present)"
            ((in_sync++))
            continue
        fi

        # File exists but missing the hook — append
        if $DRY_RUN; then
            step "$repo_name (would append gitleaks hook)"
            ((updated++))
        else
            existing_content=$(<"$config_file")
            append_content=""

            # Ensure trailing newline before appending
            if [[ -n "$existing_content" && "${existing_content: -1}" != $'\n' ]]; then
                append_content=$'\n'
            fi
            if [[ -n "$existing_content" ]]; then
                append_content+=$'\n'
            fi

            # Append just the repo entry (skip the "repos:" key since file already has it)
            append_content+="  - repo: https://github.com/tsilva/.github
    rev: main
    hooks:
      - id: gitleaks"
            append_content+=$'\n'

            if echo -n "$append_content" >> "$config_file"; then
                step "$repo_name (appended gitleaks hook)"
                ((updated++))
            else
                error "$repo_name (failed to update .pre-commit-config.yaml)"
                ((failed++))
            fi
        fi
    else
        # File doesn't exist — create from template
        if $DRY_RUN; then
            step "$repo_name (would create .pre-commit-config.yaml)"
            ((created++))
        else
            if cp "$TEMPLATE_FILE" "$config_file"; then
                step "$repo_name (created .pre-commit-config.yaml)"
                ((created++))
            else
                error "$repo_name (failed to create .pre-commit-config.yaml)"
                ((failed++))
            fi
        fi
    fi
done

print_summary "Created" "$created" "Updated" "$updated" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
