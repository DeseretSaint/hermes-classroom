#!/usr/bin/env bash
# Probe 1 — runtime/stored ids across create, first turn, resume, tool context.
set -euo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p1"; mkdir -p "$OUT"

reset_log
FIRST=$(chat -q "Call cb_probe_ids exactly once, then reply DONE." --in "$TEST_ROOT/isolated_course" -Q 2>&1)
SID=$(printf '%s\n' "$FIRST" | grep '^session_id:' | awk '{print $2}')
printf '%s\n' "$FIRST" > "$OUT/turn1.txt"
if [[ -z "${SID:-}" ]]; then verdict p1 FAIL "no session id"; exit 3; fi

RESUMED=$(chat -q "Reply RESUMED." --resume "$SID" -Q 2>&1)
printf '%s\n' "$RESUMED" > "$OUT/turn2.txt"
cp "$probe_log" "$OUT/events.jsonl"

set +e
python3 "$W/scripts/assert_probe.py" p1 "$probe_log" "$SID" > "$OUT/assert.json"
RC=$?
set -e
cat "$OUT/assert.json"

# Compression segment: report what this topology actually does.
COMP=$(chat -q "/compress" --resume "$SID" -Q 2>&1 || true)
printf '%s\n' "$COMP" > "$OUT/compress.txt"
if printf '%s\n' "$COMP" | grep -q 'session rotation did not occur'; then
  verdict p1-compaction BLOCKED "gateway /compress cannot rotate or compact in place (issue #44794 warning recorded)"
elif printf '%s\n' "$COMP" | grep -Eq 'Compression refused|No changes from compression'; then
  verdict p1-compaction BLOCKED "compressor no-op/refusal on the available transcript; post_compaction never fired"
else
  verdict p1-compaction PARTIAL "compression output recorded; inspect $OUT/compress.txt"
fi
[[ $RC -eq 0 ]] && verdict p1 PASS "session id stable, turn id per-turn, gateway cwd not session cwd" || verdict p1 FAIL "see assert.json"
