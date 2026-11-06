#!/usr/bin/env bash
# Probe 7 — backend submit_attempt stays authoritative when the chat hook fails/times out.
set -euo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p7"; mkdir -p "$OUT"

export CB_PROBE_DB="$TEST_ROOT/probe.db"
rm -f "$TEST_ROOT/probe.db" "$TEST_ROOT/probe.db-wal" "$TEST_ROOT/probe.db-shm"

"$BIN" cbprobe submit --key k1 --answer 42 --revision 1 > "$OUT/p7_submit_first.json" 2>&1
"$BIN" cbprobe submit --key k1 --answer 42 --revision 1 > "$OUT/p7_submit_duplicate.json" 2>&1
"$BIN" cbprobe submit --key k1 --answer 41 --revision 1 > "$OUT/p7_submit_conflict.json" 2>&1
"$BIN" cbprobe submit --key k2 --answer 42 --revision 9 > "$OUT/p7_submit_stale.json" 2>&1

# Hook exception: does the turn still proceed (fail-open)?
control '{"pre_llm_raise": true}'
reset_log
RAISE_TURN=$(chat -q "Reply RAISEOK." --in "$TEST_ROOT/isolated_course" -Q 2>&1 || true)
printf '%s\n' "$RAISE_TURN" > "$OUT/raise_turn.txt"
cp "$probe_log" "$OUT/events_raise.jsonl"
RAISE_OK=false
printf '%s\n' "$RAISE_TURN" | grep -q 'RAISEOK' && RAISE_OK=true

# Hook timeout: restart plugin with a 1s callback budget, then sleep past it.
"$BIN" config set plugins.hook_callback_timeout 1 >/dev/null
"$BIN" plugins disable cb-probe >/dev/null 2>&1 || true
"$BIN" plugins enable cb-probe >/dev/null 2>&1 || true
control '{"pre_llm_sleep": 32}'
reset_log
START=$(date +%s)
SLEEP_TURN=$(chat -q "Reply SLEEPDONE." --in "$TEST_ROOT/isolated_course" -Q 2>&1 || true)
WALL=$(( $(date +%s) - START ))
printf '%s\n' "$SLEEP_TURN" > "$OUT/timeout_turn.txt"
cp "$probe_log" "$OUT/events_timeout.jsonl"
TIMEOUT_OK=false
printf '%s\n' "$SLEEP_TURN" | grep -q 'SLEEPDONE' && TIMEOUT_OK=true

# After the timeout, does pre_llm_call fire again?
control '{}'
reset_log
chat -q "Reply AFTER." --in "$TEST_ROOT/isolated_course" -Q >/dev/null 2>&1 || true
cp "$probe_log" "$OUT/events_after_timeout.jsonl"
if grep -q '"event": "pre_llm_call"' "$OUT/events_after_timeout.jsonl"; then AFTER=false; else AFTER=true; fi

# Backend command still commits with the hook effectively gone.
"$BIN" cbprobe submit --key k9 --answer 42 --revision 1 > "$OUT/p7_submit_after_bypass.json" 2>&1
AFTER_STATUS=$(python3 "$W/scripts/json_field.py" status "$OUT/p7_submit_after_bypass.json")

python3 - "$OUT" "$RAISE_OK" "$TIMEOUT_OK" "$WALL" "$AFTER" "$AFTER_STATUS" <<'PY'
import json, sys
out, raise_ok, timeout_ok, wall, after, after_status = sys.argv[1:]
data = {
    "raise_turn_proceeded": raise_ok == "true",
    "timeout_turn_proceeded": timeout_ok == "true",
    "timeout_wall_s": int(wall),
    "pre_llm_after_timeout": after != "true",
    "submit_after_bypass": after_status,
}
open(f"{out}/p7_hook_bypass.json", "w").write(json.dumps(data, indent=2) + "\n")
PY

"$BIN" config unset plugins.hook_callback_timeout >/dev/null 2>&1 || true
control '{}'

set +e
python3 "$W/scripts/assert_probe.py" p7 "$OUT" | tee "$OUT/assert.json"
RC=$?
set -e
if [[ $RC -eq 0 ]]; then
  verdict p7 PASS "submit_attempt idempotent/durable with no hook; hook fails open and a timed-out hook stops firing"
else
  verdict p7 FAIL "authority or fail-open behaviour differs; see probes/raw/p7/assert.json"
fi
