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
    python3 "$LIB_DIR/extract_tagline.py" "$1"
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
