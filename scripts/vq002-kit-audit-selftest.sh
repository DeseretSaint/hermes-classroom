#!/usr/bin/env bash
# VQ-002 — mutation self-test for scripts/vq002-kit-audit.py.
#
# A green `--check` proves nothing on its own: a judge that asserts nothing also exits 0. Each case
# below breaks one claim in a throwaway copy of `kit.json`, runs the real judge against it, and
# requires exit 1. The manifest is restored before the next case, and the last case requires the
# restored manifest to pass. No plate bytes are touched.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIT="$ROOT/assets/visual-kits/field_atlas/kit.json"
TMP="$(mktemp -d)"
cp "$KIT" "$TMP/original.json"

restore() { cp "$TMP/original.json" "$KIT"; }
trap 'restore; rm -rf "$TMP"' EXIT

failures=0

case_check() { # case_check <name> <jq filter>
  local name="$1" filter="$2" out
  restore
  jq "$filter" "$TMP/original.json" >"$KIT" || { echo "skip  $name (jq)"; failures=$((failures+1)); return; }
  out="$(python3 "$ROOT/scripts/vq002-kit-audit.py" --check 2>&1)"
  if [ $? -eq 0 ]; then
    echo "MISS  $name — the judge accepted a broken manifest"
    failures=$((failures+1))
  else
    echo "caught $name -> $(printf '%s\n' "$out" | grep '^FAIL' | head -1)"
  fi
}

case_check "cover fallback names a Press Plate" \
  '.fallbacks.cover = ["course-master","pack-cover"]'
case_check "cover fallback dodges the fixed list" \
  '.fallbacks.cover = ["course-master","Packet_Thumb"]'
case_check "cover chain does not lead with course-master" \
  '.fallbacks.cover = ["background","course-master"]'
case_check "accepted row loses the raw hash it consumed" \
  '(.generation_log[] | select(.kit == 2 and .verdict == "accepted" and .asset == "cover/japanese-3x2-1200x800.png")) |= del(.raw_sha256)'
case_check "accepted row produces nothing" \
  '(.generation_log[] | select(.kit == 2 and .verdict == "accepted" and .asset == "hero/home-hero.png")) |= (.produces = [])'
case_check "fictional proof title injected" \
  '.label = "Sourdough starter kit"'
case_check "budget ceiling raised in the manifest" \
  '.generation_budget.attempts_allowed = 40'
case_check "budget ceiling lowered in the manifest" \
  '.generation_budget.attempts_allowed = 10'
case_check "one asset over four attempts" \
  '(.generation_log += [
     {"kit":2,"asset":"lesson-scene/lesson-room.png","attempt":2,"verdict":"rejected","media_url":"u2","reason":"r"},
     {"kit":2,"asset":"lesson-scene/lesson-room.png","attempt":3,"verdict":"rejected","media_url":"u3","reason":"r"},
     {"kit":2,"asset":"lesson-scene/lesson-room.png","attempt":4,"verdict":"rejected","media_url":"u4","reason":"r"},
     {"kit":2,"asset":"lesson-scene/lesson-room.png","attempt":5,"verdict":"rejected","media_url":"u5","reason":"r"}])
   | .generation_budget.attempts_used = (.generation_log | length)
   | .generation_budget.rejected = ([.generation_log[] | select(.verdict == "rejected")] | length)'
case_check "hero size claim changed" \
  '.roles.hero[0].size = [1600,900]'
case_check "recorded OCR text does not match the bytes" \
  '.roles.cover[0].provenance.ocr.raw = "HELLO WORLD"'
case_check "hero 2x source hash wrong" \
  '.resolution.hero.source.sha256 = "deadbeef"'
case_check "a derived cover traces to nothing" \
  '(.generation_log[] | select(.kit == 2 and .verdict == "accepted" and .asset == "cover/parent-3x2-1200x800.png")) |= (.produces = ["cover/parent-3x2-1200x800.png"])'
case_check "v1 art sneaks back into the consumer path" \
  '.roles.hero[0].provenance.media_url = "https://v3b.fal.media/files/b/0ab204ca/E9XJ8ljMOyKzoG7oHhW3A_cy9P4jrv.png"'
case_check "v1 recorded as something other than rejected" \
  '.supersedes.status = "approved"'
case_check "3:2 note names the wrong referent again" \
  '.roles.cover |= map(if .path == "cover/japanese-3x2-1200x800.png"
     then .provenance.source_frame.note = "2400x1600 would be an exact 2x of the 600x400 render"
     else . end)'
case_check "3:2 source_frame scale states the crop-to-plate ratio" \
  '.roles.cover |= map(if .path == "cover/parent-3x2-1200x800.png"
     then .provenance.source_frame.scale = 1.92
     else . end)'
case_check "3:2 cover ratios dropped from the manifest" \
  '.roles.cover |= map(if .path == "cover/technical-3x2-1200x800.png"
     then .provenance.source_frame |= del(.ratios)
     else . end)'
case_check "3:2 natural crop dropped from resolution" \
  '.resolution.cover["3x2"] |= del(.natural)'
case_check "superseded accepted row reclaims a shipped plate" \
  '.generation_log |= map(if (.kit == 1 and .verdict == "accepted"
                             and .asset == "hero/home-hero.png")
     then .produces = ["hero/home-hero.png"]
     else . end)'
case_check "superseded accepted row loses its superseded_by" \
  '.generation_log |= map(if (.kit == 1 and .verdict == "accepted"
                             and .asset == "lesson-scene/lesson-room.png")
     then del(.superseded_by)
     else . end)'

restore
if python3 "$ROOT/scripts/vq002-kit-audit.py" --check >/dev/null 2>&1; then
  echo "restored manifest passes --check"
else
  echo "MISS  restored manifest does not pass --check"
  failures=$((failures+1))
fi

echo
if [ "$failures" -ne 0 ]; then
  echo "$failures self-test failure(s)"
  exit 1
fi
echo "all mutation cases caught; judge is not vacuous"
