#!/usr/bin/env bash
# Generates a tabular report of repo names and their README.md taglines
# Usage: ./scripts/report-taglines.sh [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Generates a tabular report of repository names and their README.md taglines.

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -f, --filter    Only process repos matching pattern
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") ..
EOF
    exit "${1:-0}"
}

parse_args "$@"
require_command python3

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

# Collect data first to calculate column widths
declare -a repos=()
declare -a taglines=()
max_repo_width=4  # minimum "Repo" header width

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    repos+=("$repo_name")

    if [[ -f "$dir/README.md" ]]; then
        tagline=$(extract_tagline "$dir/README.md" 2>/dev/null || true)
        if [[ -z "$tagline" ]]; then
            tagline="(no tagline)"
        fi
    else
        tagline="(no README)"
    fi
    taglines+=("$tagline")

    if [[ ${#repo_name} -gt $max_repo_width ]]; then
        max_repo_width=${#repo_name}
    fi
done

if [[ ${#repos[@]} -eq 0 ]]; then
    echo "No git repositories found in: $REPOS_DIR"
    exit 0
fi

# Print header
printf "${BLUE}%-${max_repo_width}s${NC}   ${BLUE}%s${NC}\n" "Repo" "Tagline"
printf '%0.s─' $(seq 1 $((max_repo_width + 3 + 60))); echo ""

# Counters
with_tagline=0
without_tagline=0

# Print rows
for i in "${!repos[@]}"; do
    repo="${repos[$i]}"
    tagline="${taglines[$i]}"

    if [[ "$tagline" == "(no tagline)" || "$tagline" == "(no README)" ]]; then
        printf "%-${max_repo_width}s   ${DIM}%s${NC}\n" "$repo" "$tagline"
        ((without_tagline++))
    else
        printf "${GREEN}%-${max_repo_width}s${NC}   %s\n" "$repo" "$tagline"
        ((with_tagline++))
    fi
done

echo ""
echo "Summary: $with_tagline with tagline, $without_tagline without"
