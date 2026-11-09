#!/usr/bin/env bash
# Probe 1b — compression ids: does /compress compact in place and keep the session ids?
# The stock p1 transcript (8 messages) refuses compression because protect_last_n=20 leaves no
# compressible middle. This builds a 38-message session, requests /compress, records the
# post_compaction hook, then resumes once to check that session_id/task_id survived.
set -uo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p1/compress_long"; mkdir -p "$OUT"

FILL=""
for i in $(seq 1 30); do
  FILL+="Line $i: the learner repeats one short Japanese phrase, the tutor records one observation and asks for the next repetition. "
done

control '{}'
reset_log
FIRST=$(chat -q "Reply with START only." --in "$TEST_ROOT/isolated_course" -Q 2>&1)
SID=$(printf '%s\n' "$FIRST" | grep '^session_id:' | awk '{print $2}')
printf '%s\n' "$FIRST" > "$OUT/turn0.txt"
if [[ -z "${SID:-}" ]]; then verdict p1-compaction FAIL "no session id"; exit 3; fi

for n in $(seq 1 16); do
  R=$(chat -q "Turn $n. $FILL Reply with the single word ACK$n." --resume "$SID" -Q 2>&1)
  printf '%s\n' "$R" > "$OUT/turn$n.txt"
done

reset_log
COMP=$(chat -q "/compress" --resume "$SID" -Q 2>&1 || true)
printf '%s\n' "$COMP" > "$OUT/compress_long.txt"
cp "$probe_log" "$OUT/events_compress_long.jsonl"

# One more turn after compaction: ids must be unchanged (session_id/task_id) with a new turn_id.
reset_log
chat -q "Reply POSTCOMPACT." --resume "$SID" -Q > "$OUT/turn_after_compact.txt" 2>&1 || true
cp "$probe_log" "$OUT/events_after_compact.jsonl"

python3 "$W/scripts/assert_compress.py" "$OUT" "$SID" | tee "$OUT/assert.json"; RC=${PIPESTATUS[0]}
if [[ $RC -eq 0 ]]; then
  verdict p1-compaction PASS "in-place /compress summarised 38 messages to 12, post_compaction fired once and the session/task ids survived"
else
  verdict p1-compaction BLOCKED "compression did not compact or ids changed; see probes/raw/p1/compress_long/"
fi
