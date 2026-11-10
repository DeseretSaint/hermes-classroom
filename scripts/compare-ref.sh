#!/usr/bin/env bash
# Compare a rendered frame with its approved reference, and produce a review sheet.
#
#   scripts/compare-ref.sh visual/frames/home.png docs/concept-parity/refs/home.png visual/compare
#
# Output:
#   <out>/<label>-sheet.png     render | approved reference, labelled, at equal height
#   <out>/<label>-diff.png      absolute difference, autocontrasted
#   <out>/<label>.txt           RMSE and normalized similarity (1 - RMSE), plus image sizes
#
# The sheet is the deliverable a reviewer scores against the rubric; the numbers are advisory,
# because a render and a reference rarely share the exact crop. A similarity under 0.50 with a
# visibly different composition is a redesign, not a fidelity gap.
set -euo pipefail

render="${1:?render png}"
ref="${2:?reference png}"
out="${3:-visual/compare}"
label="${4:-$(basename "${render%.png}")}"

mkdir -p "$out"
H=900

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

magick "$render" -resize "x${H}" "$work/render.png"
magick "$ref"    -resize "x${H}" "$work/ref.png"

magick montage \
  -label 'render' "$work/render.png" \
  -label 'approved reference' "$work/ref.png" \
  -tile 2x1 -geometry +16+16 -background '#f4ecd9' -fill '#1a1713' -font Adwaita-Sans -pointsize 22 \
  "$out/${label}-sheet.png"

# Equal canvas for the difference: pad the smaller to the larger, anchored top-left.
rw=$(magick identify -format '%w' "$work/render.png"); rh=$(magick identify -format '%h' "$work/render.png")
fw=$(magick identify -format '%w' "$work/ref.png");    fh=$(magick identify -format '%h' "$work/ref.png")
W=$(( rw > fw ? rw : fw )); Hh=$(( rh > fh ? rh : fh ))
magick "$work/render.png" -background '#f4ecd9' -gravity northwest -extent "${W}x${Hh}" "$work/r2.png"
magick "$work/ref.png"    -background '#f4ecd9' -gravity northwest -extent "${W}x${Hh}" "$work/f2.png"

metric=$(compare -metric RMSE "$work/r2.png" "$work/f2.png" "$out/${label}-diff.png" 2>&1 || true)
rmse=$(printf '%s' "$metric" | sed -E 's/.*\(([0-9.]+)\).*/\1/')
sim=$(awk -v r="$rmse" 'BEGIN { printf "%.4f", 1 - r }')

{
  echo "render:   $render (${rw}x${rh})"
  echo "reference: $ref (${fw}x${fh})"
  echo "rmse:     $rmse"
  echo "similarity: $sim"
  echo "sheet:    $out/${label}-sheet.png"
  echo "diff:     $out/${label}-diff.png"
} | tee "$out/${label}.txt"
