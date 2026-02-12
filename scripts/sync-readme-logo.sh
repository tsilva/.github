#!/usr/bin/env bash
# Ensures README.md references the project logo (inserts img tag after title if missing)
# Usage: ./scripts/sync-readme-logo.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Ensures all git repos with a README.md and a logo file have a logo reference
in the README. Inserts an <img> tag after the title line for READMEs that
are missing a logo reference.

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

# Standard logo locations (same as audit-repos.sh check_logo_exists)
LOGO_LOCATIONS=(
    "logo.png" "logo.svg" "logo.jpg"
    "assets/logo.png" "assets/logo.svg"
    "images/logo.png" "images/logo.svg"
    ".github/logo.png" ".github/logo.svg"
)

# Counters
updated=0
in_sync=0
skipped=0
failed=0

info "Syncing README logo references in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    # Skip if no README.md
    if [[ ! -f "$dir/README.md" ]]; then
        skip "$repo_name (no README.md)"
        ((skipped++))
        continue
    fi

    # Find logo file
    logo_path=""
    for loc in "${LOGO_LOCATIONS[@]}"; do
        if [[ -f "$dir/$loc" ]]; then
            logo_path="$loc"
            break
        fi
    done

    if [[ -z "$logo_path" ]]; then
        skip "$repo_name (no logo file)"
        ((skipped++))
        continue
    fi

    # Check if README already references the logo (same patterns as audit)
    if grep -qiE '!\[.*\]\(\.?/?((assets|images|\.github)/)?logo\.' "$dir/README.md" 2>/dev/null; then
        success "$repo_name (logo referenced)"
        ((in_sync++))
        continue
    fi
    if grep -qiE '<img[^>]+src=.\.?/?((assets|images|\.github)/)?logo\.' "$dir/README.md" 2>/dev/null; then
        success "$repo_name (logo referenced)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name (would insert logo reference → $logo_path)"
        ((updated++))
        continue
    fi

    # Insert logo img tag after the first title line (# Title)
    # Build the logo block
    logo_block="<p align=\"center\">\n  <img src=\"$logo_path\" alt=\"$repo_name logo\" width=\"200\">\n</p>"

    # Find the first heading line and insert after it
    if head -5 "$dir/README.md" | grep -qE '^# '; then
        # Insert after the first # heading line
        local_tmp=$(mktemp)
        awk -v block="$logo_block" '
            /^# / && !done { print; printf "\n%s\n", block; done=1; next }
            { print }
        ' "$dir/README.md" > "$local_tmp"

        if mv "$local_tmp" "$dir/README.md"; then
            step "$repo_name (inserted logo reference → $logo_path)"
            ((updated++))
        else
            error "$repo_name (failed to insert logo reference)"
            rm -f "$local_tmp"
            ((failed++))
        fi
    else
        # No heading found — prepend logo block
        local_tmp=$(mktemp)
        { printf '%b\n\n' "$logo_block"; cat "$dir/README.md"; } > "$local_tmp"

        if mv "$local_tmp" "$dir/README.md"; then
            step "$repo_name (prepended logo reference → $logo_path)"
            ((updated++))
        else
            error "$repo_name (failed to prepend logo reference)"
            rm -f "$local_tmp"
            ((failed++))
        fi
    fi
done

print_summary "Updated" "$updated" "In sync" "$in_sync" "Skipped" "$skipped" "Failed" "$failed"

[[ $failed -gt 0 ]] && exit 1
exit 0
