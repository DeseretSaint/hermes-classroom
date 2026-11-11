#!/usr/bin/env bash
# VQ-006 — one command that produces installed-plugin captures and a manifest.
#
# This is the capture path every screen card uses (VISUAL-QUALITY-PROGRAM.md Gate 5). It:
#   1. builds a disposable rig: a private HERMES_HOME/userdata, the current checkout installed into
#      it, an isolated backend on that home, and one Desktop window the capture drives;
#   2. seeds a real library — the bundled packs through the product's own grant/preview/import path
#      — and requires one user-created Game course with an approved world (or --allow-no-game, which
#      reports the gap instead of photographing Textbook as Game);
#   3. captures Home, Discover, Classroom, Course home, World Studio and the Design System at
#      1344x768, 1049, 900 and 460 route widths;
#   4. writes one PNG and one JSON cell per destination/width, a contact sheet, and a manifest;
#   5. judges the frames with scripts/vq-manifest.py — missing required image, below 2x rendered,
#      data URI standing in for a kit asset, proof-only page — and exits non-zero on any failure.
#
#   scripts/vq-capture.sh                       # fresh rig, seed, capture everything
#   scripts/vq-capture.sh --widths 1344 460     # subset of widths
#   scripts/vq-capture.sh --destinations home discover
#   scripts/vq-capture.sh --state ~/.hermes/coursebook-test-cp040 --reuse   # point at a pumped rig
#   scripts/vq-capture.sh --game-course crs_… --allow-no-game
#
# Everything this script writes stays under the state directory and the output directory. It never
# touches the operator's main window, profile or gateway, and it stops its own window and backend
# when it finishes unless --keep-window is passed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STATE="${COURSEBOOK_TEST_STATE:-$HOME/.hermes/coursebook-test-vq006}"
OUT="${VQ_OUT:-$ROOT/docs/visual-review/vq-006}"
BACKEND_PORT="${VQ_BACKEND_PORT:-44396}"
CDP_PORT="${VQ_CDP_PORT:-9396}"
TOKEN="${VQ_TOKEN:-vq006-test-token}"
WIDTHS="${VQ_WIDTHS:-1344 1049 900 460}"
DESTINATIONS="${VQ_DESTINATIONS:-home discover course-home classroom world-studio design-system}"
GAME_COURSE=""
REUSE=0
ALLOW_NO_GAME=0
KEEP_WINDOW=0
SEED=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state) STATE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --backend-port) BACKEND_PORT="$2"; shift 2 ;;
    --cdp-port) CDP_PORT="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --widths) WIDTHS="$2"; shift 2 ;;
    --destinations) DESTINATIONS="$2"; shift 2 ;;
    --game-course) GAME_COURSE="$2"; shift 2 ;;
    --reuse) REUSE=1; shift ;;
    --allow-no-game) ALLOW_NO_GAME=1; shift ;;
    --no-seed) SEED=0; shift ;;
    --keep-window) KEEP_WINDOW=1; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

HOME_DIR="$STATE/home"
USERDATA="$STATE/userdata"
OUT="$(mkdir -p "$OUT" && cd "$OUT" && pwd)"
mkdir -p "$STATE" "$HOME_DIR" "$USERDATA"

export COURSEBOOK_TEST_STATE="$STATE"
export COURSEBOOK_TEST_HOME="$HOME_DIR"
export CB013_CDP_PORT="$CDP_PORT"
export CB013_PORT="$BACKEND_PORT"
export CB013_TOKEN="$TOKEN"
export CB015_CDP_PORT="$CDP_PORT"

cleanup() {
  if [[ "$KEEP_WINDOW" == "1" ]]; then
    echo "rig kept: state=$STATE backend=:$BACKEND_PORT cdp=:$CDP_PORT"
    return
  fi
  scripts/cb013-live-window.sh --stop >/dev/null 2>&1 || true
  scripts/cb013-live-backend.sh --stop >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ "$REUSE" == "0" ]]; then
  echo "== 1/5 install the checkout into the disposable rig"
  scripts/install-local.sh --home "$HOME_DIR" | tail -6

  echo "== 2/5 write the remote connection for $BACKEND_PORT"
  python3 scripts/vq-rig.py connection "$USERDATA/connections.json" "$BACKEND_PORT" "$TOKEN"

  echo "== 3/5 start the isolated backend on :$BACKEND_PORT"
  scripts/cb013-live-backend.sh | tail -2
  # The backend reports READY a moment before the plugin routes are mounted, and a seed that runs
  # in that window gets a connection refusal. Wait for the route itself, not the log line.
  ready=0
  for _ in $(seq 1 120); do
    code="$(curl -s -m 2 -o /dev/null -w '%{http_code}' \
      -H "Authorization: Bearer $TOKEN" \
      "http://127.0.0.1:$BACKEND_PORT/api/plugins/coursebook/runtime" || true)"
    if [[ "$code" == "200" ]]; then ready=1; break; fi
    sleep 0.5
  done
  [[ "$ready" == "1" ]] || { echo "backend never answered /api/plugins/coursebook/runtime on :$BACKEND_PORT" >&2; exit 1; }
  echo "backend: /api/plugins/coursebook/runtime 200"

  if [[ "$SEED" == "1" ]]; then
    echo "== 4/5 seed the bundled packs through the product's import path"
    seed_args=(--base-url "http://127.0.0.1:$BACKEND_PORT" --token "$TOKEN" --json "$STATE/library.json")
    [[ -n "$GAME_COURSE" ]] && seed_args+=(--game-course "$GAME_COURSE")
    [[ "$ALLOW_NO_GAME" == "1" ]] && seed_args+=(--allow-no-game)
    set +e
    python3 scripts/vq-library.py "${seed_args[@]}"
    seed_status=$?
    set -e
    if [[ $seed_status -ne 0 && $seed_status -ne 3 ]]; then
      echo "library seed failed (exit $seed_status)" >&2
      exit $seed_status
    fi
    if [[ $seed_status -eq 3 ]]; then
      echo "library: no user-created Game course — Classroom and World Studio cells are recorded as" >&2
      echo "         missing, not photographed from a Textbook course." >&2
    fi
  fi

  echo "== 5/5 launch the disposable Desktop window (CDP :$CDP_PORT)"
  scripts/cb013-live-window.sh | tail -2
else
  echo "reuse : $STATE (backend :$BACKEND_PORT, cdp :$CDP_PORT)"
  curl -s -m 4 "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null || {
    echo "no CDP window on :$CDP_PORT for $STATE" >&2; exit 1; }
fi

# A Game course is required for the two Game surfaces; without one those cells are skipped and the
# manifest records them as missing rather than substituting a different course.
GAME=""
if [[ -f "$STATE/library.json" ]]; then
  GAME="$(python3 scripts/vq-rig.py game-course "$STATE/library.json" 2>/dev/null || true)"
fi
[[ -n "$GAME_COURSE" && -z "$GAME" ]] && GAME="$GAME_COURSE"

echo "== capture"
captured=0
for width in $WIDTHS; do
  for destination in $DESTINATIONS; do
    if [[ -z "$GAME" && ( "$destination" == "classroom" || "$destination" == "world-studio" ) ]]; then
      echo "skip  $destination @ $width (no approved Game course in this library)"
      continue
    fi
    cell="$destination--$width"
    echo "-- $cell"
    set +e
    node scripts/vq-capture.mjs \
      --destination "$destination" --width "$width" \
      --out "$OUT" --name "$cell" --cdp-port "$CDP_PORT" \
      --plugin "$ROOT/desktop/plugin.js" \
      ${GAME:+--course "$GAME"}
    status=$?
    set -e
    if [[ $status -eq 3 ]]; then
      echo "   recorded: the installed plugin has no $destination surface"
    elif [[ $status -ne 0 ]]; then
      echo "   recorded with a capture problem (exit $status)"
    fi
    captured=$((captured + 1))
  done
done

echo "== manifest"
commit="$(git rev-parse HEAD 2>/dev/null || echo unrecorded)"
set +e
python3 scripts/vq-manifest.py --dir "$OUT" --commit "$commit"
verdict=$?
set -e

echo
echo "output directory: $OUT"
echo "captured cells : $captured"
echo "manifest       : $OUT/manifest.json"
echo "contact sheet  : $OUT/contact-sheet.png"
exit $verdict
