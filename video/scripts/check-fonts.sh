#!/usr/bin/env bash
# Font regression check for the launch film.
#
# Renders the FontProbe composition and proves, by pixel comparison, that the
# bundled Fraunces and Source Sans 3 faces are actually the faces being used —
# not the browser's Times fallback. This exists because a wrong font-family
# declaration fails silently: the frame looks fine at a glance and is wrong.
#
# Usage: ./scripts/check-fonts.sh   (from video/)
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="${TMPDIR:-/tmp}/cb-font-probe"
BROWSER="/usr/bin/chromium"
[ -x "$BROWSER" ] || BROWSER=""

rm -rf "$OUT"
mkdir -p "$OUT"

npx remotion still src/index.ts FontProbe "$OUT/probe.png" \
  --frame=0 --bundle-cache=false ${BROWSER:+--browser-executable="$BROWSER"} >/dev/null

# Rows are 170 px tall starting at y=0 (see src/FontProbe.tsx).
row() { # $1 = row index, $2 = output name
  local y=$(( $1 * 170 ))
  ffmpeg -y -loglevel error -i "$OUT/probe.png" -vf "crop=1840:150:40:$((y + 20))" "$OUT/$2.png"
}

row 0 ss3_600
row 1 ss3_400
row 2 fraunces
row 3 fraunces_italic
row 4 serif
row 5 sans

fail=0
assert_differs() { # $1 label, $2 file a, $3 file b
  local psnr
  psnr=$(ffmpeg -loglevel info -i "$OUT/$2.png" -i "$OUT/$3.png" \
    -lavfi psnr -f null - 2>&1 | grep -o 'average:[^ ]*' | head -1 || true)
  if [ -z "$psnr" ] || [ "$psnr" = "average:inf" ]; then
    echo "FAIL $1: rows are pixel-identical — the bundled face is not being used"
    fail=1
  else
    echo "ok   $1 ($psnr)"
  fi
}

assert_differs "Source Sans 3 600 is not the serif fallback" ss3_600 serif
assert_differs "Source Sans 3 400 is not the serif fallback" ss3_400 serif
assert_differs "Source Sans 3 600 is not the generic sans"    ss3_600 sans
assert_differs "Fraunces 600 is not the serif fallback"       fraunces serif
assert_differs "Fraunces 600 italic differs from upright"     fraunces fraunces_italic

if [ "$fail" -ne 0 ]; then
  echo "font check FAILED"
  exit 1
fi
echo "font check passed (evidence: $OUT)"
