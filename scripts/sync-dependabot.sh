#!/usr/bin/env bash
# DEPRECATED: Use 'tsilva-maintain fix' instead
# Ensures .github/dependabot.yml exists in all repos
# Usage: ./scripts/sync-dependabot.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Ensures all git repos have a .github/dependabot.yml for automated dependency
updates. Auto-detects relevant ecosystems (npm, pip, cargo, etc.) and generates
config with weekly schedule.

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

info "Syncing dependabot.yml to repos in: $REPOS_DIR"
dry_run_banner
echo ""

# Detect ecosystems for a repo and write dependabot.yml content
generate_dependabot() {
    local dir="$1"
    local ecosystems=()

    # GitHub Actions
    if [[ -d "$dir/.github/workflows" ]]; then
        local yml_count
        yml_count=$(ls -1 "$dir/.github/workflows/"*.yml 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$yml_count" -gt 0 ]]; then
            ecosystems+=("github-actions")
        fi
    fi

    # Package managers
    [[ -f "$dir/package.json" ]]    && ecosystems+=("npm")
    [[ -f "$dir/pyproject.toml" || -f "$dir/requirements.txt" ]] && ecosystems+=("pip")
    [[ -f "$dir/Cargo.toml" ]]      && ecosystems+=("cargo")
    [[ -f "$dir/go.mod" ]]          && ecosystems+=("gomod")
    [[ -f "$dir/Gemfile" ]]         && ecosystems+=("bundler")
    [[ -f "$dir/composer.json" ]]   && ecosystems+=("composer")

    # Default to github-actions if nothing detected
    if [[ ${#ecosystems[@]} -eq 0 ]]; then
        ecosystems+=("github-actions")
    fi

    # Build YAML
    local content
    content="# Dependabot configuration for automated dependency updates
# https://docs.github.com/en/code-security/dependabot/dependabot-version-updates
version: 2
updates:"

    for eco in "${ecosystems[@]}"; do
        content+="
  - package-ecosystem: \"$eco\"
    directory: \"/\"
    schedule:
      interval: \"weekly\""
    done

    echo "$content"
    # Return ecosystem list for logging
    DETECTED_ECOSYSTEMS="${ecosystems[*]}"
}

discover_repos "$REPOS_DIR"

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    # Check if dependabot config already exists
    if [[ -f "$dir/.github/dependabot.yml" || -f "$dir/.github/dependabot.yaml" ]]; then
        success "$repo_name (dependabot config exists)"
        ((in_sync++))
        continue
    fi

    DETECTED_ECOSYSTEMS=""
    content=$(generate_dependabot "$dir")

    if $DRY_RUN; then
        step "$repo_name (would create dependabot.yml — $DETECTED_ECOSYSTEMS)"
        ((created++))
        continue
    fi

    # Create .github directory if needed
    mkdir -p "$dir/.github"

    if echo "$content" > "$dir/.github/dependabot.yml"; then
        step "$repo_name (created dependabot.yml — $DETECTED_ECOSYSTEMS)"
        ((created++))
    else
        error "$repo_name (failed to create dependabot.yml)"
        ((failed++))
    fi
done

print_summary "Created" "$created" "In sync" "$in_sync" "Failed" "$failed" "Skipped" "$skipped"

[[ $failed -gt 0 ]] && exit 1
exit 0
