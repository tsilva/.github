#!/usr/bin/env bash
# Sets a GitHub secret for all repos in a directory
# Usage: ./scripts/set-secret-all-repos.sh [--dry-run] [--filter PATTERN] <repos-dir> <secret-name> <secret-value>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir> <secret-name> <secret-value>

Sets a GitHub repository secret for all git repos in the specified directory.

Arguments:
    repos-dir       Directory containing git repositories
    secret-name     Name of the secret to set
    secret-value    Value of the secret

Options:
    -n, --dry-run   Print what would be done without executing
    -f, --filter    Only process repos matching pattern
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos MY_SECRET "secret-value"
    $(basename "$0") --dry-run ~/repos PAT_TOKEN "\$PAT"
EOF
    exit "${1:-0}"
}

parse_args "$@"

# Need two more positional args after repos-dir
if [[ ${#REMAINING_ARGS[@]} -lt 2 ]]; then
    echo "Error: Missing required arguments: secret-name and secret-value" >&2
    usage 1
fi

SECRET_NAME="${REMAINING_ARGS[0]}"
SECRET_VALUE="${REMAINING_ARGS[1]}"

# Validate secret name
if [[ ! "$SECRET_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "Error: Invalid secret name. Must be alphanumeric with underscores, starting with a letter or underscore." >&2
    exit 1
fi

if [[ "$SECRET_NAME" =~ ^GITHUB_ ]]; then
    echo "Error: Secret names cannot start with 'GITHUB_'" >&2
    exit 1
fi

require_gh_auth

# Counters
succeeded=0
failed=0
skipped=0

info "Setting secret '$SECRET_NAME' for repos in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    remote_url=$(git -C "$dir" remote get-url origin 2>/dev/null || true)

    if [[ -z "$remote_url" ]]; then
        skip "$repo_name (no origin remote)"
        ((skipped++))
        continue
    fi

    github_repo=$(extract_github_remote "$remote_url" || true)

    if [[ -z "$github_repo" ]]; then
        skip "$repo_name (not a GitHub repo: $remote_url)"
        ((skipped++))
        continue
    fi

    if $DRY_RUN; then
        success "$repo_name → $github_repo (would set secret)"
        ((succeeded++))
    else
        if echo "$SECRET_VALUE" | gh secret set "$SECRET_NAME" --repo "$github_repo" 2>/dev/null; then
            success "$repo_name → $github_repo"
            ((succeeded++))
        else
            error "$repo_name → $github_repo (failed to set secret)"
            ((failed++))
        fi
    fi
done

print_summary "Succeeded" "$succeeded" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
