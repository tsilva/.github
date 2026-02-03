#!/usr/bin/env bash
# Syncs repo description to GitHub from README.md tagline or pyproject.toml
# Priority: README.md tagline → pyproject.toml description
# Usage: ./scripts/sync-repo-descriptions.sh <repos-dir>

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

Syncs GitHub repo descriptions from README.md tagline or pyproject.toml
for all git repos in the specified directory.

Priority: README.md tagline → pyproject.toml description

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

# Check Python 3.11+ is available (required for tomllib)
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH" >&2
    exit 1
fi

# Verify tomllib is available (Python 3.11+)
if ! python3 -c "import tomllib" 2>/dev/null; then
    echo "Error: Python 3.11+ required (tomllib not available)" >&2
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

# Extract description from pyproject.toml using Python's tomllib
extract_description() {
    local pyproject="$1"
    python3 -c "
import tomllib
with open('$pyproject', 'rb') as f:
    data = tomllib.load(f)
desc = data.get('project', {}).get('description', '')
print(desc)
"
}

# Extract tagline from README.md (first qualifying paragraph line)
# Skips: frontmatter, headers, badges, blockquotes, HTML, links-only, horizontal rules
extract_tagline() {
    local readme="$1"
    python3 - "$readme" << 'PYEOF'
import re
import sys

def extract_tagline(readme_path):
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return ""

    lines = content.split('\n')
    in_frontmatter = False
    frontmatter_count = 0

    for line in lines:
        stripped = line.strip()

        # Handle YAML frontmatter
        if stripped == '---':
            frontmatter_count += 1
            if frontmatter_count == 1:
                in_frontmatter = True
                continue
            elif frontmatter_count == 2:
                in_frontmatter = False
                continue

        if in_frontmatter:
            continue

        # Skip empty lines
        if not stripped:
            continue

        # Skip headers (# ...)
        if stripped.startswith('#'):
            continue

        # Skip badges (![...] or [![...)
        if stripped.startswith('![') or stripped.startswith('[!['):
            continue

        # Skip blockquotes (> ...)
        if stripped.startswith('>'):
            continue

        # Skip HTML tags (<div>, </div>, <img, etc.)
        if stripped.startswith('<') or stripped.startswith('</'):
            continue

        # Skip horizontal rules (---, ***, ___)
        if re.match(r'^[-*_]{3,}$', stripped):
            continue

        # Skip link-only lines [text](url) or just URLs
        if re.match(r'^\[.+\]\(.+\)$', stripped):
            continue
        if re.match(r'^https?://', stripped):
            continue

        # Skip lines that are just navigation links like [Link1] · [Link2]
        nav_pattern = r'^\[.+\](?:\(.+\))?\s*(?:[·|]\s*\[.+\](?:\(.+\))?)+$'
        if re.match(nav_pattern, stripped):
            continue

        # Must have at least 10 characters to be a tagline
        if len(stripped) < 10:
            continue

        # Found a qualifying line - clean it up
        tagline = stripped

        # Strip leading emoji (common pattern)
        tagline = re.sub(r'^[\U0001F300-\U0001F9FF\U00002600-\U000027BF]\s*', '', tagline)

        # Strip markdown formatting
        tagline = re.sub(r'\*\*(.+?)\*\*', r'\1', tagline)  # bold
        tagline = re.sub(r'\*(.+?)\*', r'\1', tagline)      # italic
        tagline = re.sub(r'_(.+?)_', r'\1', tagline)        # italic
        tagline = re.sub(r'`(.+?)`', r'\1', tagline)        # code
        tagline = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', tagline)  # links
        tagline = re.sub(r'<[^>]+>', '', tagline)           # HTML tags

        # Truncate to 350 chars (GitHub limit) if needed
        if len(tagline) > 350:
            tagline = tagline[:347] + '...'

        return tagline.strip()

    return ""

print(extract_tagline(sys.argv[1]))
PYEOF
}

# Get current GitHub repo description
get_github_description() {
    local repo="$1"
    gh repo view "$repo" --json description -q '.description // ""' 2>/dev/null || echo ""
}

# Counters
updated=0
failed=0
skipped=0
in_sync=0

echo "Syncing repo descriptions (README.md → pyproject.toml) in: $REPOS_DIR"
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

    # Try README.md first, then pyproject.toml
    local_desc=""
    desc_source=""

    if [[ -f "$dir/README.md" ]]; then
        local_desc=$(extract_tagline "$dir/README.md" 2>/dev/null || true)
        if [[ -n "$local_desc" ]]; then
            desc_source="README.md"
        fi
    fi

    if [[ -z "$local_desc" && -f "$dir/pyproject.toml" ]]; then
        local_desc=$(extract_description "$dir/pyproject.toml" 2>/dev/null || true)
        if [[ -n "$local_desc" ]]; then
            desc_source="pyproject.toml"
        fi
    fi

    if [[ -z "$local_desc" ]]; then
        log_skip "$repo_name (no description in README.md or pyproject.toml)"
        ((skipped++))
        continue
    fi

    # Get current GitHub description
    github_desc=$(get_github_description "$github_repo")

    # Compare descriptions
    if [[ "$local_desc" == "$github_desc" ]]; then
        log_success "$repo_name (already in sync)"
        ((in_sync++))
        continue
    fi

    # Update description
    if $DRY_RUN; then
        log_update "$repo_name → $github_repo"
        log_info "Current: \"$github_desc\""
        log_info "New:     \"$local_desc\""
        ((updated++))
    else
        if gh repo edit "$github_repo" --description "$local_desc" 2>/dev/null; then
            log_update "$repo_name → $github_repo"
            log_info "Updated ($desc_source): \"$local_desc\""
            ((updated++))
        else
            log_error "$repo_name → $github_repo (failed to update)"
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
