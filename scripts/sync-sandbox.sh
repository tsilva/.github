#!/usr/bin/env bash
# Ensures Claude sandbox is enabled in all repos
# Usage: ./scripts/sync-sandbox.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Ensures all git repos have Claude sandbox enabled via
.claude/settings.json with {"sandbox": {"enabled": true}}.

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

# Counters
created=0
in_sync=0
failed=0
skipped=0

info "Syncing Claude sandbox settings to repos in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    if has_sandbox_enabled "$dir"; then
        success "$repo_name (sandbox enabled)"
        ((in_sync++))
        continue
    fi

    if $DRY_RUN; then
        step "$repo_name (would enable sandbox)"
        ((created++))
        continue
    fi

    claude_dir="$dir/.claude"
    settings_file="$claude_dir/settings.json"

    mkdir -p "$claude_dir"

    # Merge into existing settings if present
    if [[ -f "$settings_file" ]]; then
        if python3 -c "
import json
f = '$settings_file'
try:
    data = json.load(open(f))
except: data = {}
if 'sandbox' not in data: data['sandbox'] = {}
data['sandbox']['enabled'] = True
with open(f, 'w') as fh:
    json.dump(data, fh, indent=2)
    fh.write('\n')
" 2>/dev/null; then
            step "$repo_name (updated settings.json — sandbox enabled)"
            ((created++))
        else
            error "$repo_name (failed to update settings.json)"
            ((failed++))
        fi
    else
        # Create new settings file
        if printf '{\n  "sandbox": {\n    "enabled": true\n  }\n}\n' > "$settings_file"; then
            step "$repo_name (created settings.json — sandbox enabled)"
            ((created++))
        else
            error "$repo_name (failed to create settings.json)"
            ((failed++))
        fi
    fi
done

print_summary "Created" "$created" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
