#!/usr/bin/env bash
# Run all tests for the Open Testimony project.
#
# Usage:
#   ./scripts/run-tests.sh          # run all tests
#   ./scripts/run-tests.sh api      # run only API server tests
#   ./scripts/run-tests.sh bridge   # run only bridge tests
#
# Prerequisites:
#   - Postgres running on localhost:5432 (docker compose up db)
#   - bridge/.venv exists with bridge dependencies installed
#   - bcrypt==4.1.2 installed in system python (or api-server venv)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_URL="${TEST_DATABASE_URL:-postgresql://user:pass@localhost:5432/opentestimony_test}"
FAILED=0

red()   { printf '\033[1;31m%s\033[0m\n' "$*"; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

run_api_tests() {
    bold "--- API Server Tests ---"
    cd "$ROOT/api-server"
    if TEST_DATABASE_URL="$DB_URL" python -m pytest tests/ -v --tb=short "$@"; then
        green "API server: ALL PASSED"
    else
        red "API server: SOME FAILURES"
        FAILED=1
    fi
    echo
}

run_bridge_tests() {
    bold "--- Bridge Tests ---"
    cd "$ROOT/bridge"
    if [ ! -d .venv ]; then
        red "Bridge .venv not found. Run: cd bridge && python -m venv .venv && pip install -r requirements.txt"
        FAILED=1
        return
    fi
    if source .venv/bin/activate && TEST_DATABASE_URL="$DB_URL" python -m pytest tests/ -v --tb=short "$@"; then
        green "Bridge: ALL PASSED"
    else
        red "Bridge: SOME FAILURES"
        FAILED=1
    fi
    deactivate 2>/dev/null || true
    echo
}

# Parse arguments
SUITE="${1:-all}"
shift 2>/dev/null || true

case "$SUITE" in
    api)    run_api_tests "$@" ;;
    bridge) run_bridge_tests "$@" ;;
    all)
        run_api_tests "$@"
        run_bridge_tests "$@"
        ;;
    *)
        echo "Usage: $0 [all|api|bridge] [pytest args...]"
        exit 1
        ;;
esac

if [ "$FAILED" -eq 0 ]; then
    echo
    green "========== ALL SUITES PASSED =========="
else
    echo
    red  "========== SOME SUITES HAD FAILURES =========="
    exit 1
fi
