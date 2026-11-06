#!/usr/bin/env bash
# Probe 3 — which AGENTS policies reach the system prompt for isolated / in-repo / outside cwds?
set -euo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p3"; mkdir -p "$OUT"

run_case() {
  local name="$1"; shift
  reset_log
  chat -q "Reply OK." --in "$TEST_ROOT/$1" "${@:2}" -Q >/dev/null 2>&1 || true
  cp "$probe_log" "$OUT/$name.jsonl"
  printf '%s: ' "$name"
  grep -o '"markers": \[[^]]*\]' "$OUT/$name.jsonl" | sort -u | tr '\n' ' '; echo
}

run_case isolated isolated_course
run_case repo_course repo/course
run_case repo_root repo
run_case outside outside
run_case ignore_rules isolated_course --ignore-rules

set +e
python3 "$W/scripts/assert_probe.py" p3 "$OUT" | tee "$OUT/assert.json"
RC=$?
set -e
if [[ $RC -eq 0 ]]; then
  verdict p3 PASS "isolated/outside/ignore-rules load only the intended policy; in-repo parent policy leaks (documented constraint)"
else
  verdict p3 FAIL "unexpected AGENTS discovery result; see probes/raw/p3/assert.json"
fi
