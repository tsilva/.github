#!/usr/bin/env bash
# Terminal styling library for .github scripts
# Usage: source "$(dirname "${BASH_SOURCE[0]}")/lib/style.sh"
# Respects NO_COLOR (https://no-color.org/)

# Guard against double-sourcing
[[ -n "${_STYLE_SH_LOADED:-}" ]] && return 0
_STYLE_SH_LOADED=1

# Colors — disabled when NO_COLOR is set or stdout is not a terminal
if [[ -z "${NO_COLOR:-}" && -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' MAGENTA='' CYAN=''
    BOLD='' DIM='' NC=''
fi

# --- Log functions ---
success() { echo -e "${GREEN}✓${NC} $1"; }
error()   { echo -e "${RED}✗${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
info()    { echo -e "${BLUE}ℹ${NC} $1"; }
step()    { echo -e "${BLUE}↻${NC} $1"; }
skip()    { echo -e "${YELLOW}→${NC} $1"; }
dim()     { echo -e "${DIM}$1${NC}"; }
detail()  { echo -e "  $1"; }

# --- Structural output ---
header() {
    echo ""
    echo -e "${BOLD}$1${NC}"
    printf '%0.s─' $(seq 1 "${2:-${#1}}"); echo ""
}

section() {
    echo ""
    echo -e "${CYAN}$1${NC}"
}

banner() {
    local width="${2:-60}"
    echo ""
    printf '%0.s═' $(seq 1 "$width"); echo ""
    echo -e "${BOLD}  $1${NC}"
    printf '%0.s═' $(seq 1 "$width"); echo ""
}

# --- Summary ---
# Usage: print_summary "Label1" value1 "Label2" value2 ...
print_summary() {
    echo ""
    echo "Summary:"
    while [[ $# -ge 2 ]]; do
        printf "  %-10s %s\n" "$1:" "$2"
        shift 2
    done
}

# --- Dry-run banner ---
dry_run_banner() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        echo -e "${YELLOW}DRY RUN MODE - no changes will be made${NC}"
    fi
}
