#!/usr/bin/env bash
# VQ-002 — build the owner-facing contact sheet for the field_atlas kit.
#
# The sheet is evidence, not decoration: it must show the hero, both cover aspects for every real
# Home course, the fox and object references, the lesson scene, and a side-by-side against
# docs/concept-parity/refs/home.png. Labels are drawn by ImageMagick as separate `caption:` images
# and appended, because `montage -label` silently drops labels once the tiles are resized.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIT="$ROOT/assets/visual-kits/field_atlas"
OUT="$KIT/specimens/contact-sheet.png"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

W=1400
BG='#f7f1e4'
INK='#1a1713'
MUTED='#5b4a3f'
FONT='Liberation-Sans'
FONT_B='Liberation-Sans-Bold'

cap() { # cap <width> <pointsize> <font> <fill> <text> <out>
  magick -background "$BG" -fill "$4" -font "$3" -pointsize "$2" -size "${1}x" \
    caption:"$5" "$6"
}

center() { # center a row image inside the sheet width
  local f="$1" h
  h="$(identify -format %h "$f")"
  magick "$f" -background "$BG" -gravity center -extent "${W}x${h}" "$f.c"
  mv "$f.c" "$f"
}

# ---- header ------------------------------------------------------------------------------
magick -background "$BG" -fill "$INK" -font "$FONT_B" -pointsize 40 -size ${W}x \
  label:"field_atlas@2 - curated visual kit specimens" "$TMP/title.png"

cap $W 19 "$FONT" "$MUTED" \
  "VQ-002 owner rework. Sources at 2x the rendered size: hero 1344x768 from a 2688x1536 provider frame (shipped beside it as home-hero@2x.png), covers 640x800 and 1200x800 for a 320x400 and 600x400 render, lesson scene 1344x768 with a 2688x1536 sibling. Every plate was generated with the reference mockup attached (reference_image_urls) and passes the recorded textless rule." \
  "$TMP/sub1.png"
cap $W 19 "$FONT" "$MUTED" \
  "Real Home shelf, read from the seeded library at ~/.hermes/coursebook-test-vq006: three courses, so three display covers and no invented fourth. No Press Plate is used or referenced. No product source is touched by this card." \
  "$TMP/sub2.png"

# ---- hero --------------------------------------------------------------------------------
magick "$KIT/hero/home-hero.png" -resize ${W}x "$TMP/hero.png"
cap $W 20 "$FONT_B" "$INK" "hero/home-hero.png - 1344x768 - 2x source 2688x1536 - textless" "$TMP/hero-c.png"

# ---- covers 4:5 --------------------------------------------------------------------------
cap $W 20 "$FONT_B" "$INK" "Display covers 4:5 - 640x800, 2x of the 320x400 render" "$TMP/covers45-c.png"
magick "$KIT/cover/japanese-4x5-640x800.png" -resize 320x400 "$TMP/c1.png"
magick "$KIT/cover/parent-4x5-640x800.png" -resize 320x400 "$TMP/c2.png"
magick "$KIT/cover/technical-4x5-640x800.png" -resize 320x400 "$TMP/c3.png"
cap 320 16 "$FONT" "$INK" "Japanese register: affection and closeness" "$TMP/c1x.png"
cap 320 16 "$FONT" "$INK" "Measuring together: a kitchen lesson" "$TMP/c2x.png"
cap 320 16 "$FONT" "$INK" "Reading a pack before you install it" "$TMP/c3x.png"
for i in 1 2 3; do
  magick "$TMP/c$i.png" "$TMP/c${i}x.png" -background "$BG" -gravity center -append "$TMP/cc$i.png"
done
magick "$TMP/cc1.png" "$TMP/cc2.png" "$TMP/cc3.png" -background "$BG" -gravity north +append "$TMP/row45.png"

# ---- covers 3:2 --------------------------------------------------------------------------
cap $W 20 "$FONT_B" "$INK" "Display covers 3:2 - 1200x800, 2x of the 600x400 render" "$TMP/covers32-c.png"
magick "$KIT/cover/japanese-3x2-1200x800.png" -resize 440x293 "$TMP/d1.png"
magick "$KIT/cover/parent-3x2-1200x800.png" -resize 440x293 "$TMP/d2.png"
magick "$KIT/cover/technical-3x2-1200x800.png" -resize 440x293 "$TMP/d3.png"
for i in 1 2 3; do
  magick "$TMP/d$i.png" "$TMP/c${i}x.png" -background "$BG" -gravity center -append "$TMP/dd$i.png"
done
magick "$TMP/dd1.png" "$TMP/dd2.png" "$TMP/dd3.png" -background "$BG" -gravity north +append "$TMP/row32.png"

# ---- fox and objects ---------------------------------------------------------------------
cap $W 20 "$FONT_B" "$INK" "fox/ - the seven approved A1 poses at 128 and the model sheet, carried as references from assets/art/fox" "$TMP/fox-c.png"
magick "$KIT"/fox/fox-cheer-256.png "$KIT"/fox/fox-clock-256.png "$KIT"/fox/fox-point-256.png \
  "$KIT"/fox/fox-read-256.png "$KIT"/fox/fox-sleep-256.png "$KIT"/fox/fox-think-256.png \
  "$KIT"/fox/fox-wave-256.png "$KIT"/fox/fox-model-sheet-512.png -resize 128x +append "$TMP/fox.png"

cap $W 20 "$FONT_B" "$INK" "objects/ - the approved A5 blank kit, seven 256 px cutouts carried as references from assets/art/objects" "$TMP/obj-c.png"
magick "$KIT"/objects/clock.png "$KIT"/objects/medallion-rim.png "$KIT"/objects/passport-tray.png \
  "$KIT"/objects/shelf-plank.png "$KIT"/objects/stamp-rim.png "$KIT"/objects/tag.png \
  "$KIT"/objects/ticket.png -resize 128x +append "$TMP/obj.png"

# ---- lesson scene ------------------------------------------------------------------------
cap $W 20 "$FONT_B" "$INK" "lesson-scene/lesson-room.png - 1344x768 - 2x source 2688x1536 - reused by Classroom when no per-course scene exists" "$TMP/lesson-c.png"
magick "$KIT/lesson-scene/lesson-room.png" -resize ${W}x "$TMP/lesson.png"

# ---- side by side with the references ----------------------------------------------------
cap $W 22 "$FONT_B" "$INK" "Against the references" "$TMP/pair-c.png"

magick "$KIT/hero/home-hero.png" -resize 680x "$TMP/ref-hero.png"
magick "$ROOT/docs/concept-parity/refs/home.png" -resize 680x "$TMP/ref-home.png"
cap 680 16 "$FONT" "$MUTED" "kit v2 hero" "$TMP/ref-hero-c.png"
cap 680 16 "$FONT" "$MUTED" "docs/concept-parity/refs/home.png (mockup, not a title source)" "$TMP/ref-home-c.png"
magick "$TMP/ref-hero.png" "$TMP/ref-hero-c.png" -background "$BG" -gravity center -append "$TMP/ref-a.png"
magick "$TMP/ref-home.png" "$TMP/ref-home-c.png" -background "$BG" -gravity center -append "$TMP/ref-b.png"
magick "$TMP/ref-a.png" "$TMP/ref-b.png" -background "$BG" -gravity north +append "$TMP/pair1.png"

magick "$KIT/lesson-scene/lesson-room.png" -resize 680x "$TMP/ref-lesson.png"
magick "$ROOT/docs/concept-parity/refs/classroom.png" -resize 680x "$TMP/ref-class.png"
cap 680 16 "$FONT" "$MUTED" "kit v2 lesson scene" "$TMP/ref-lesson-c.png"
cap 680 16 "$FONT" "$MUTED" "docs/concept-parity/refs/classroom.png (mockup)" "$TMP/ref-class-c.png"
magick "$TMP/ref-lesson.png" "$TMP/ref-lesson-c.png" -background "$BG" -gravity center -append "$TMP/ref-c.png"
magick "$TMP/ref-class.png" "$TMP/ref-class-c.png" -background "$BG" -gravity center -append "$TMP/ref-d.png"
magick "$TMP/ref-c.png" "$TMP/ref-d.png" -background "$BG" -gravity north +append "$TMP/pair2.png"

for row in row45 row32 fox obj pair1 pair2; do center "$TMP/$row.png"; done

# ---- assemble ----------------------------------------------------------------------------
magick \
  "$TMP/title.png" "$TMP/sub1.png" "$TMP/sub2.png" \
  "$TMP/hero-c.png" "$TMP/hero.png" \
  "$TMP/covers45-c.png" "$TMP/row45.png" \
  "$TMP/covers32-c.png" "$TMP/row32.png" \
  "$TMP/fox-c.png" "$TMP/fox.png" \
  "$TMP/obj-c.png" "$TMP/obj.png" \
  "$TMP/lesson-c.png" "$TMP/lesson.png" \
  "$TMP/pair-c.png" "$TMP/pair1.png" "$TMP/pair2.png" \
  -background "$BG" -gravity west -append \
  -bordercolor "$BG" -border 20 "$OUT"

identify "$OUT"
