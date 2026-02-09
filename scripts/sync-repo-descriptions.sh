#!/usr/bin/env bash
# Syncs repo description to GitHub from README.md tagline or pyproject.toml
# Priority: README.md tagline → pyproject.toml description
# Usage: ./scripts/sync-repo-descriptions.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

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
    -f, --filter    Only process repos matching pattern
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") --dry-run ~/repos
EOF
    exit "${1:-0}"
}

parse_args "$@"
require_gh_auth
require_command python3
if ! python3 -c "import tomllib" 2>/dev/null; then
    echo "Error: Python 3.11+ required (tomllib not available)" >&2
    exit 1
fi

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

        if not stripped:
            continue
        if stripped.startswith('#'):
            continue
        if stripped.startswith('![') or stripped.startswith('[!['):
            continue
        if stripped.startswith('>'):
            continue
        if stripped.startswith('<') or stripped.startswith('</'):
            continue
        if re.match(r'^[-*_]{3,}$', stripped):
            continue
        if re.match(r'^\[.+\]\(.+\)$', stripped):
            continue
        if re.match(r'^https?://', stripped):
            continue

        nav_pattern = r'^\[.+\](?:\(.+\))?\s*(?:[·|]\s*\[.+\](?:\(.+\))?)+$'
        if re.match(nav_pattern, stripped):
            continue

        if len(stripped) < 10:
            continue

        tagline = stripped
        tagline = re.sub(r'^[\U0001F300-\U0001F9FF\U00002600-\U000027BF]\s*', '', tagline)
        tagline = re.sub(r'\*\*(.+?)\*\*', r'\1', tagline)
        tagline = re.sub(r'\*(.+?)\*', r'\1', tagline)
        tagline = re.sub(r'_(.+?)_', r'\1', tagline)
        tagline = re.sub(r'`(.+?)`', r'\1', tagline)
        tagline = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', tagline)
        tagline = re.sub(r'<[^>]+>', '', tagline)

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

info "Syncing repo descriptions (README.md → pyproject.toml) in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    # Get the remote URL
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
        skip "$repo_name (no description in README.md or pyproject.toml)"
        ((skipped++))
        continue
    fi

    github_desc=$(get_github_description "$github_repo")

    if [[ "$local_desc" == "$github_desc" ]]; then
        success "$repo_name (already in sync)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name → $github_repo"
        detail "Current: \"$github_desc\""
        detail "New:     \"$local_desc\""
        ((updated++))
    else
        if gh repo edit "$github_repo" --description "$local_desc" 2>/dev/null; then
            step "$repo_name → $github_repo"
            detail "Updated ($desc_source): \"$local_desc\""
            ((updated++))
        else
            error "$repo_name → $github_repo (failed to update)"
            ((failed++))
        fi
    fi
done

print_summary "Updated" "$updated" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
