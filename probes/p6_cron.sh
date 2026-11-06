#!/usr/bin/env bash
# Probe 6 — cron delivery targets: explicit vs omitted; no external send.
set -euo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p6"; mkdir -p "$OUT"

# Clean any leftovers from an earlier run.
if [[ -f "$H/cron/jobs.json" ]]; then
  for j in $(grep -o '"id": "[0-9a-f]*"' "$H/cron/jobs.json" | cut -d'"' -f4); do
    "$BIN" cron remove "$j" >/dev/null 2>&1 || true
  done
fi

"$BIN" cron create "0 0 1 1 *" "QA probe omitted delivery. Do nothing." --name qa-omit --paused >/dev/null
"$BIN" cron create "0 0 1 1 *" "QA probe local delivery. Do nothing." --name qa-local --deliver local --paused >/dev/null
"$BIN" cron create "0 0 1 1 *" "QA probe telegram delivery. Do nothing." --name qa-tele --deliver telegram:999999999 --paused >/dev/null
"$BIN" cron create "0 0 1 1 *" "QA probe duplicate name. Do nothing." --name qa-omit --paused >/dev/null

cp "$H/cron/jobs.json" "$OUT/jobs.json"

set +e
python3 "$W/scripts/assert_probe.py" p6 "$OUT/jobs.json" | tee "$OUT/assert.json"
RC=$?
set -e

for j in $(grep -o '"id": "[0-9a-f]*"' "$H/cron/jobs.json" | cut -d'"' -f4); do
  "$BIN" cron remove "$j" >/dev/null 2>&1 || true
done

if [[ $RC -eq 0 ]]; then
  verdict p6 PASS "omitted=local, explicit target stored verbatim, duplicate names create duplicates (plugin must dedupe)"
else
  verdict p6 FAIL "cron delivery semantics differ; see probes/raw/p6/assert.json"
fi
