#!/usr/bin/env bash
# Copy audit: OCR the encoded mp4 and assert every plan §4 string appears in the
# beat the plan puts it in. Reads the *render*, not the source, so a beat that
# silently lost its caption fails here.
#
# Usage: ./scripts/check-copy.sh out/scaffold-75s.mp4   (from video/)
set -euo pipefail

cd "$(dirname "$0")/.."
MP4="${1:-out/scaffold-75s.mp4}"
[ -f "$MP4" ] || { echo "no such file: $MP4"; exit 1; }

OUT="${TMPDIR:-/tmp}/cb-copy-audit"
rm -rf "$OUT"; mkdir -p "$OUT"

norm() { tr '[:upper:]' '[:lower:]' | tr '\n' ' ' | sed 's/[^a-z0-9]//g'; }

# beat | frame | substring that must be on screen at that frame (§3 + §4)
CHECKS=(
  "B01|40|you dont need another course"
  "B02|150|a textbook"
  "B02|200|a flashcard app"
  "B02|215|a tutor you cant afford"
  "B03|260|one course finished"
  "B04|340|coursebook"
  "B04|400|your field library"
  "B05|480|any topic becomes a real course"
  "B05|480|placeholder beat 05 create topic"
  "B05|700|placeholder beat 05 plan sections"
  "B06|780|read it hear it answer it"
  "B06|780|placeholder beat 06 classroom line"
  "B06|950|placeholder beat 06 classroom check"
  "B06|1100|placeholder beat 06 classroom feedback"
  "B07|1200|ask the lesson get the page"
  "B07|1200|placeholder beat 07 tutor cited"
  "B08|1480|practice that remembers where you are"
  "B08|1480|placeholder beat 08 game challenge"
  "B08|1650|placeholder beat 08 game complete"
  "B09|1720|and a parent sees the work not the screen time"
  "B09|1720|placeholder beat 09 parent observation"
  "B10|1950|your next world is already on the shelf"
  "B10|1950|placeholder beat 10 discover grid"
  "B11|2160|coursebook"
  "B11|2160|githubcomdeseretsainthermesclassroom"
  "B11|2160|mit"
  "B11|2160|built with hermes"
)

fail=0
for check in "${CHECKS[@]}"; do
  beat="${check%%|*}"
  rest="${check#*|}"
  frm="${rest%%|*}"
  want="${rest#*|}"
  img="$OUT/${beat}-${frm}.png"
  [ -f "$img" ] || ffmpeg -y -loglevel error -i "$MP4" \
    -vf "select=eq(n\,$frm)" -frames:v 1 "$img"
  got=$(tesseract "$img" stdout 2>/dev/null | norm)
  if printf '%s' "$got" | grep -qF "$(printf '%s' "$want" | norm)"; then
    echo "ok   $beat @$frm  \"$want\""
  else
    echo "FAIL $beat @$frm  \"$want\" missing"
    echo "     ocr: $(printf '%s' "$got" | head -c 160)"
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "copy audit FAILED"
  exit 1
fi
echo "copy audit passed ($(printf '%s\n' "${CHECKS[@]}" | wc -l) assertions, evidence: $OUT)"
