#!/usr/bin/env bash
# Sets a GitHub secret for all repos in a directory
# Usage: ./scripts/set-secret-all-repos.sh <repos-dir> <secret-name> <secret-value>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

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
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos MY_SECRET "secret-value"
    $(basename "$0") --dry-run ~/repos PAT_TOKEN "\$PAT"
EOF
    exit "${1:-0}"
}

log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_skip() { echo -e "${YELLOW}→${NC} $1"; }
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
if [[ $# -lt 3 ]]; then
    echo "Error: Missing required arguments" >&2
    usage 1
fi

REPOS_DIR="$1"
SECRET_NAME="$2"
SECRET_VALUE="$3"

# Validate repos directory
if [[ ! -d "$REPOS_DIR" ]]; then
    echo "Error: Directory does not exist: $REPOS_DIR" >&2
    exit 1
fi

# Validate secret name (GitHub secret names must be alphanumeric or underscore, not start with GITHUB_)
if [[ ! "$SECRET_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "Error: Invalid secret name. Must be alphanumeric with underscores, starting with a letter or underscore." >&2
    exit 1
fi

if [[ "$SECRET_NAME" =~ ^GITHUB_ ]]; then
    echo "Error: Secret names cannot start with 'GITHUB_'" >&2
    exit 1
fi

# Check gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed or not in PATH" >&2
    exit 1
fi

# Check gh is authenticated
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub CLI. Run 'gh auth login' first." >&2
    exit 1
fi

# Extract GitHub repo from remote URL
# Handles both HTTPS and SSH formats:
#   https://github.com/owner/repo.git
#   git@github.com:owner/repo.git
extract_repo() {
    local url="$1"
    local repo

    # SSH format: git@github.com:owner/repo.git
    if [[ "$url" =~ git@github\.com:([^/]+/[^/]+)(\.git)?$ ]]; then
        repo="${BASH_REMATCH[1]}"
    # HTTPS format: https://github.com/owner/repo.git
    elif [[ "$url" =~ github\.com/([^/]+/[^/]+)(\.git)?$ ]]; then
        repo="${BASH_REMATCH[1]}"
    else
        return 1
    fi

    # Remove .git suffix if present
    echo "${repo%.git}"
}

# Counters
succeeded=0
failed=0
skipped=0

echo "Setting secret '$SECRET_NAME' for repos in: $REPOS_DIR"
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

    # Get the remote URL
    remote_url=$(git -C "$dir" remote get-url origin 2>/dev/null || true)

    if [[ -z "$remote_url" ]]; then
        log_skip "$repo_name (no origin remote)"
        ((skipped++))
        continue
    fi

    # Extract GitHub repo identifier
    github_repo=$(extract_repo "$remote_url" || true)

    if [[ -z "$github_repo" ]]; then
        log_skip "$repo_name (not a GitHub repo: $remote_url)"
        ((skipped++))
        continue
    fi

    # Set the secret
    if $DRY_RUN; then
        log_success "$repo_name → $github_repo (would set secret)"
        ((succeeded++))
    else
        if echo "$SECRET_VALUE" | gh secret set "$SECRET_NAME" --repo "$github_repo" 2>/dev/null; then
            log_success "$repo_name → $github_repo"
            ((succeeded++))
        else
            log_error "$repo_name → $github_repo (failed to set secret)"
            ((failed++))
        fi
    fi
done

# Summary
echo ""
echo "Summary:"
echo "  Succeeded: $succeeded"
echo "  Failed:    $failed"
echo "  Skipped:   $skipped"

# Exit with error if any failed
if [[ $failed -gt 0 ]]; then
    exit 1
fi
