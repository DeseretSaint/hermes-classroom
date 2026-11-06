#!/usr/bin/env bash
# Shared helpers for the Coursebook runtime probes.
set -euo pipefail

W="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${QA_PROFILE:-cbqa}"
H="${QA_HOME:-$HOME/.hermes/profiles/$PROFILE}"
BIN="${QA_PROFILE_BIN:-$HOME/.local/bin/$PROFILE}"
TEST_ROOT="$H/test-root"
RAW="$W/raw"
PY="${QA_PYTHON:-$(ls -d "$HOME"/.hermes/tools/python-3.14.9*/bin/python3 2>/dev/null | head -1)}"

probe_log="$TEST_ROOT/logs/probe.jsonl"

reset_log() { : > "$probe_log"; }

control() { printf '%s\n' "$1" > "$TEST_ROOT/control.json"; }

chat() {
  ( cd "$HOME" && "$BIN" chat "$@" )
}

run_py() {
  ( cd "$HOME/.hermes/hermes-agent" && "$PY" "$@" )
}

verdict() { # name status detail
  printf 'RESULT probe=%s %s %s\n' "$1" "$2" "${3:-}"
}
