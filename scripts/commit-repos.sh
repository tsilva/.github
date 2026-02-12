#!/usr/bin/env bash
# DEPRECATED: Use 'tsilva-maintain commit' instead
# Interactive AI-assisted commit & push for repos with uncommitted changes
# Usage: ./scripts/commit-repos.sh [--dry-run] [--filter PATTERN] <repos-dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/style.sh"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <repos-dir>

Scans repos for uncommitted changes, generates AI commit messages via Claude CLI,
and interactively commits and pushes approved changes.

Arguments:
    repos-dir       Directory containing git repositories

Options:
    -n, --dry-run   Show dirty repos and changes without committing or calling AI
    -f, --filter    Only process repos matching pattern
    -h, --help      Show this help message

Examples:
    $(basename "$0") ~/repos
    $(basename "$0") --dry-run ~/repos
    $(basename "$0") --filter my-project ~/repos
EOF
    exit "${1:-0}"
}

parse_args "$@"

# Counters
committed=0
pushed=0
no_changes=0
skipped=0
failed=0

info "Scanning repos for uncommitted changes in: $REPOS_DIR"
dry_run_banner
echo ""

discover_repos "$REPOS_DIR"

# --- Phase 1: Scan for dirty repos ---
DIRTY_REPOS=()
DIRTY_NAMES=()
DIRTY_STATUS=()

for i in "${!REPOS[@]}"; do
    dir="${REPOS[$i]}"
    repo_name="${REPO_NAMES[$i]}"

    status_output=$(git -C "$dir" status --short 2>/dev/null || true)

    if [[ -z "$status_output" ]]; then
        success "$repo_name (no changes)"
        ((no_changes++))
        continue
    fi

    DIRTY_REPOS+=("$dir")
    DIRTY_NAMES+=("$repo_name")
    DIRTY_STATUS+=("$status_output")
done

if [[ ${#DIRTY_REPOS[@]} -eq 0 ]]; then
    echo ""
    info "No repos with uncommitted changes found."
    print_summary "Committed" "$committed" "Pushed" "$pushed" \
        "No changes" "$no_changes" "Skipped" "$skipped" "Failed" "$failed"
    exit 0
fi

echo ""
info "Found ${#DIRTY_REPOS[@]} repo(s) with uncommitted changes"

# --- Phase 2: Generate AI commit messages ---
MESSAGES=()
HAS_CLAUDE=false

if command -v claude &> /dev/null; then
    HAS_CLAUDE=true
fi

for i in "${!DIRTY_REPOS[@]}"; do
    dir="${DIRTY_REPOS[$i]}"
    repo_name="${DIRTY_NAMES[$i]}"

    if $DRY_RUN; then
        MESSAGES+=("")
        continue
    fi

    if ! $HAS_CLAUDE; then
        MESSAGES+=("")
        continue
    fi

    # Build context: diff + untracked files
    diff_output=$(git -C "$dir" diff HEAD 2>/dev/null | head -200 || true)
    untracked=$(git -C "$dir" ls-files --others --exclude-standard 2>/dev/null || true)

    context="Changes:\n${diff_output}"
    if [[ -n "$untracked" ]]; then
        context="${context}\n\nNew untracked files:\n${untracked}"
    fi

    msg=$(echo -e "$context" | claude -p \
        --model haiku \
        --max-budget-usd 0.01 \
        --no-session-persistence \
        "Generate a concise git commit message (one line, no quotes, no prefix like 'feat:') for these changes. Only output the message, nothing else." \
        2>/dev/null || true)

    # Trim whitespace
    msg=$(echo "$msg" | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    MESSAGES+=("$msg")
done

# --- Phase 3: Interactive approval ---
APPROVED_INDICES=()
APPROVED_MESSAGES=()

if $DRY_RUN; then
    for i in "${!DIRTY_REPOS[@]}"; do
        repo_name="${DIRTY_NAMES[$i]}"
        status_output="${DIRTY_STATUS[$i]}"

        header "$repo_name"
        echo "$status_output"
        echo ""
        dim "(would generate AI message and prompt for approval)"
    done
else
    for i in "${!DIRTY_REPOS[@]}"; do
        repo_name="${DIRTY_NAMES[$i]}"
        status_output="${DIRTY_STATUS[$i]}"
        msg="${MESSAGES[$i]}"

        header "$repo_name"
        echo "$status_output"
        echo ""

        if [[ -n "$msg" ]]; then
            echo -e "  Suggested: ${BOLD}${msg}${NC}"
            echo ""
            echo -n "  [a]pprove / [e]dit / [s]kip? "
            read -r choice </dev/tty

            case "$choice" in
                a|A)
                    APPROVED_INDICES+=("$i")
                    APPROVED_MESSAGES+=("$msg")
                    ;;
                e|E)
                    echo -n "  Enter commit message: "
                    read -r custom_msg </dev/tty
                    if [[ -n "$custom_msg" ]]; then
                        APPROVED_INDICES+=("$i")
                        APPROVED_MESSAGES+=("$custom_msg")
                    else
                        skip "$repo_name (empty message, skipping)"
                        ((skipped++))
                    fi
                    ;;
                *)
                    skip "$repo_name (skipped)"
                    ((skipped++))
                    ;;
            esac
        else
            echo -e "  ${DIM}(no AI message available)${NC}"
            echo ""
            echo -n "  [e]nter message / [s]kip? "
            read -r choice </dev/tty

            case "$choice" in
                e|E)
                    echo -n "  Enter commit message: "
                    read -r custom_msg </dev/tty
                    if [[ -n "$custom_msg" ]]; then
                        APPROVED_INDICES+=("$i")
                        APPROVED_MESSAGES+=("$custom_msg")
                    else
                        skip "$repo_name (empty message, skipping)"
                        ((skipped++))
                    fi
                    ;;
                *)
                    skip "$repo_name (skipped)"
                    ((skipped++))
                    ;;
            esac
        fi
    done
fi

if [[ ${#APPROVED_INDICES[@]} -eq 0 ]]; then
    echo ""
    info "No repos approved for commit."
    print_summary "Committed" "$committed" "Pushed" "$pushed" \
        "No changes" "$no_changes" "Skipped" "$skipped" "Failed" "$failed"
    exit 0
fi

# --- Phase 4: Bulk commit & push ---
echo ""
section "Committing approved repos..."

COMMITTED_INDICES=()

for j in "${!APPROVED_INDICES[@]}"; do
    idx="${APPROVED_INDICES[$j]}"
    dir="${DIRTY_REPOS[$idx]}"
    repo_name="${DIRTY_NAMES[$idx]}"
    msg="${APPROVED_MESSAGES[$j]}"

    if git -C "$dir" add -A && git -C "$dir" commit -m "$msg" > /dev/null 2>&1; then
        step "$repo_name (committed)"
        ((committed++))
        COMMITTED_INDICES+=("$idx")
    else
        error "$repo_name (commit failed)"
        ((failed++))
    fi
done

echo ""
section "Pushing committed repos..."

for idx in "${COMMITTED_INDICES[@]}"; do
    dir="${DIRTY_REPOS[$idx]}"
    repo_name="${DIRTY_NAMES[$idx]}"

    if ! git -C "$dir" remote get-url origin > /dev/null 2>&1; then
        warn "$repo_name (no remote, skipping push)"
        continue
    fi

    if git -C "$dir" push > /dev/null 2>&1; then
        success "$repo_name (pushed)"
        ((pushed++))
    else
        error "$repo_name (push failed)"
        ((failed++))
    fi
done

print_summary "Committed" "$committed" "Pushed" "$pushed" \
    "No changes" "$no_changes" "Skipped" "$skipped" "Failed" "$failed"

[[ $failed -gt 0 ]] && exit 1
exit 0
