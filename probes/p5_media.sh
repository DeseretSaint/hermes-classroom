#!/usr/bin/env bash
# Probe 5 — Coursebook-owned tool → artifact → MEDIA: → renderer / delivery seam.
set -euo pipefail
source "$(dirname "$0")/scripts/lib.sh"
OUT="$RAW/p5"; mkdir -p "$OUT"

control "{\"artifact_dir\": \"$TEST_ROOT/artifacts\"}"
"$BIN" cbprobe media --stem cli_p5 > "$OUT/p5_tool_result.json" 2>&1
run_py "$W/scripts/check_media.py" "$OUT/p5_tool_result.json" > "$OUT/p5_media_seam.json" 2>/dev/null || true

set +e
python3 "$W/scripts/assert_probe.py" p5 "$OUT" | tee "$OUT/assert.json"
RC=$?
set -e
if [[ $RC -eq 0 ]]; then
  verdict p5 PASS "artifact+text fallback exist and MEDIA tag parses on plain text; Desktop renderer is provenance-scoped"
else
  verdict p5 FAIL "media seam broken; see probes/raw/p5/assert.json"
fi
verdict p5-render BLOCKED "no renderer contribution in the skeleton and no Electron session driven in this pass; host contract verified only"
