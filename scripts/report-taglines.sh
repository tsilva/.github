#!/usr/bin/env bash
# Generates a tabular report of repo names and their README.md taglines
# Usage: ./scripts/report-taglines.sh <repos-dir>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
NC='\033[0m' # No Color

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Generates a tabular report of repository names and their README.md taglines.

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") ..
EOF
    exit "${1:-0}"
}

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
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

# Check Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH" >&2
    exit 1
fi

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

# Collect data first to calculate column widths
declare -a repos=()
declare -a taglines=()
max_repo_width=4  # minimum "Repo" header width

for dir in "$REPOS_DIR"/*/; do
    dir="${dir%/}"
    repo_name="$(basename "$dir")"

    # Skip if not a git repository
    if [[ ! -d "$dir/.git" ]]; then
        continue
    fi

    repos+=("$repo_name")

    # Extract tagline
    if [[ -f "$dir/README.md" ]]; then
        tagline=$(extract_tagline "$dir/README.md" 2>/dev/null || true)
        if [[ -z "$tagline" ]]; then
            tagline="(no tagline)"
        fi
    else
        tagline="(no README)"
    fi
    taglines+=("$tagline")

    # Update max width
    if [[ ${#repo_name} -gt $max_repo_width ]]; then
        max_repo_width=${#repo_name}
    fi
done

# Check if any repos found
if [[ ${#repos[@]} -eq 0 ]]; then
    echo "No git repositories found in: $REPOS_DIR"
    exit 0
fi

# Print header
printf "${BLUE}%-${max_repo_width}s${NC}   ${BLUE}%s${NC}\n" "Repo" "Tagline"
printf "%s\n" "$(printf '─%.0s' $(seq 1 $((max_repo_width + 3 + 60))))"

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

# Summary
echo ""
echo "Summary: $with_tagline with tagline, $without_tagline without"
