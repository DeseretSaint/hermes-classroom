#!/usr/bin/env bash
# Probe 4 — owned aux structured grading: latency, invalid JSON, timeout, provider outage.
set -euo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p4"; mkdir -p "$OUT"

# The outage slot: an auxiliary task pinned to a model that does not exist.
"$BIN" config set auxiliary.cb_grader_bad.provider nous >/dev/null
"$BIN" config set auxiliary.cb_grader_bad.model definitely-not-a-model-xyz >/dev/null

grade() { # name extra-args...
  local name="$1"; shift
  "$BIN" cbprobe grade --scenario "$name" "$@" > "$OUT/p4_$name.json" 2>&1 || true
}

for i in 1 2 3 4 5; do
  "$BIN" cbprobe grade --scenario realistic > "$OUT/p4_realistic_$i.json" 2>&1 || true
done
grade schema_ok
grade invalid_json
grade timeout --timeout 0.001
grade outage

run_py "$W/scripts/check_runtime.py" > "$OUT/p4_runtime_seam.json" 2>/dev/null || true

set +e
python3 "$W/scripts/assert_probe.py" p4 "$OUT" | tee "$OUT/assert.json"
RC=$?
set -e
if [[ $RC -eq 0 ]]; then
  verdict p4 PASS "normal grading is fast and fail-closed; see p4/assert.json for outage/model-substitution caveat"
else
  verdict p4 FAIL "grading contract violation; see probes/raw/p4/assert.json"
fi
