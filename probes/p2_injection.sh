#!/usr/bin/env bash
# Probe 2 — is a pre_llm_call injected sentinel persisted and replayed after restart?
set -euo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p2"; mkdir -p "$OUT"

NONCE="SENT2-$(date +%s)"
control "{\"inject_sentinel\": \"$NONCE\"}"
reset_log
FIRST=$(chat -q "Reply with the single word OK." --in "$TEST_ROOT/isolated_course" -Q 2>&1)
SID=$(printf '%s\n' "$FIRST" | grep '^session_id:' | awk '{print $2}')
printf '%s\n' "$FIRST" > "$OUT/turn1.txt"
printf '%s\n' "$NONCE" > "$OUT/nonce.txt"
cp "$probe_log" "$OUT/events_turn1.jsonl"

set +e
python3 "$W/scripts/assert_probe.py" p2 "$H/state.db" "$SID" "$NONCE" > "$OUT/assert_storage.json"
RC1=$?
set -e
cat "$OUT/assert_storage.json"

# Second process: injection disabled. Does the stored sidecar replay into the wire?
control '{}'
reset_log
SECOND=$(chat -q "Does the text CB_INJECTED_SENTINEL appear anywhere in this conversation? Answer PRESENT or ABSENT only." --resume "$SID" -Q 2>&1)
printf '%s\n' "$SECOND" > "$OUT/turn2.txt"
cp "$probe_log" "$OUT/events_turn2.jsonl"

if printf '%s\n' "$SECOND" | grep -q 'PRESENT'; then
  verdict p2-replay FAIL "model saw the sentinel on a resumed turn where injection was disabled"
else
  verdict p2-replay PASS "sentinel not replayed to the model"
fi
if [[ $RC1 -eq 0 ]]; then
  verdict p2 PASS "injection not persisted in api_content"
else
  verdict p2 FAIL "pre_llm_call injection persisted in api_content and replayed; docs claim ephemerality"
fi
