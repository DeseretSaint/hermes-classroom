#!/usr/bin/env bash
# CP-024 — the course-home (R-MAP) capture matrix, from the module this branch builds.
#
# Every frame goes through `scripts/cp-capture.mjs` and writes its `<name>.stamp.json` beside it.
# The screen is a course home, which is shell state rather than a URL, so each cell passes the
# card's own real-click driver (`--after-reload`) and the capture runs on the live window
# (`--no-reload`; the stamp records `capture.reloaded: false` and the module sha the window reads).
#
# Prerequisites:
#   * an isolated rig on this checkout: scripts/install-local.sh, scripts/cb013-live-backend.sh,
#     scripts/cb013-live-window.sh (CB013_CDP_PORT=9357, CB013_PORT=44417, token cp024-test-token);
#   * the window has been restarted after the last `install-local.sh` so the evaluated module is
#     the installed one;
#   * `world` state fixtures are the rig's own DB rows (a real `course_worlds` row, valid brief),
#     switched per cell below; they are removed at the end.
#
#   docs/visual-review/cp-024/capture.sh [cell ...]      # no arguments = every cell
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
OUT="docs/visual-review/cp-024"
STATE="${COURSEBOOK_TEST_STATE:-$HOME/.hermes/coursebook-test-cp024}"
DB="$STATE/home/plugin-data/coursebook/data.db"
COURSE="crs_650052975ca7406aaddda22122c89bad"
PORT="${CB013_CDP_PORT:-9357}"
BACKEND="${CB013_BACKEND_URL:-http://127.0.0.1:44417}"
TOKEN="${CB013_TOKEN:-cp024-test-token}"

BASE=(--out "$OUT" --cdp-port "$PORT" --state "$STATE" --plugin desktop/plugin.js
      --backend-url "$BACKEND" --token "$TOKEN" --require-v3 --no-reload
      --after-reload "$OUT/drive-course-home.js"
      --after-reload-wait '[data-cb-course-home-v3]')

cell() {
  local name="$1"; shift
  echo "== $name"
  node scripts/cp-capture.mjs --name "$name" "${BASE[@]}" "$@"
}

# The v3 route follows the host's own appearance attribute, not `prefers-color-scheme`, so a mode
# cell sets the host through the app's settings control first (idempotent; it returns to Home).
appearance() {
  node docs/visual-review/cp-024/set-appearance.mjs "$1" --cdp-port "$PORT"
}

world_state() {
  local state="$1" rev="$2" error_json="${3:-NULL}" err="NULL"
  local style="sha256:$(printf 'a%.0s' {1..64})" kit="sha256:$(printf 'b%.0s' {1..64})"
  if [[ -n "${3:-}" ]]; then err="'$error_json'"; fi
  sqlite3 "$DB" "INSERT OR REPLACE INTO course_worlds
    (id, course_id, revision, state, brief_json, concepts_json, selected_concept_id, style_hash,
     kit_hash, approved_hash, approved_at, error_json, created_at, updated_at)
    VALUES ('wld_cp024_state_$rev', '$COURSE', $rev, '$state',
      '{\"course_id\":\"$COURSE\",\"title\":\"Japanese affection and register\",\"subject_domain\":\"language\",\"end_capability\":\"\",\"audience\":\"adult learner\",\"level\":\"novice\",\"locale\":\"en-US\",\"tone\":\"practical, calm, competent\",\"safety_class\":\"none\",\"motifs\":[],\"forbidden\":[],\"sections\":[]}',
      '[]', NULL, '$style', '$kit', NULL, NULL,
      $err, '2026-11-10T22:00:00+00:00', '2026-11-10T22:00:00+00:00');"
}

clear_world() {
  sqlite3 "$DB" "DELETE FROM course_worlds WHERE course_id='$COURSE';"
}

want() {
  if [[ ${#CELLS[@]} -eq 0 ]]; then return 0; fi
  [[ " ${CELLS[*]} " == *" $1 "* ]]
}

CELLS=("$@")
clear_world

# ── eight baseline cells: 1049/900/460 × light/dark, the 1349 wide cell, forced colors ──────────
if want default-1049-light; then appearance light; cell course-home--1049--light--100--default --route-width 1049; fi
if want default-1049-dark; then appearance dark; cell course-home--1049--dark--100--default --route-width 1049; fi
if want default-900-light; then appearance light; cell course-home--900--light--100--default --route-width 900; fi
if want default-900-dark; then appearance dark; cell course-home--900--dark--100--default --route-width 900; fi
if want default-460-light; then appearance light; cell course-home--460--light--100--default --route-width 460; fi
if want default-460-dark; then appearance dark; cell course-home--460--dark--100--default --route-width 460; fi
if want default-1349-light; then appearance light; cell course-home--1349--light--100--default --route-width 1349; fi
if want forced-colors; then appearance light; cell course-home--1049--light--100--forced-colors --route-width 1049 --forced-colors; fi

# ── named states ────────────────────────────────────────────────────────────────────────────────
if want plan-in-review; then
  node scripts/cp-capture.mjs --name course-home--1049--light--100--plan-in-review \
    --out "$OUT" --cdp-port "$PORT" --state "$STATE" --plugin desktop/plugin.js \
    --backend-url "$BACKEND" --token "$TOKEN" --require-v3 --no-reload \
    --after-reload "$OUT/drive-course-plan.js" \
    --after-reload-wait '[data-cb-course-home-v3]' --route-width 1049
fi
if want no-world; then cell course-home--1049--light--100--no-world --route-width 1049; fi
if want world-running; then
  world_state kit_generating 1
  cell course-home--1049--light--100--world-running --route-width 1049
  clear_world
fi
if want world-rejected; then
  world_state failed 2 '{"missing_roles":["hero"]}'
  cell course-home--1049--light--100--world-rejected --route-width 1049
  clear_world
fi
if want text-200; then cell course-home--460--light--200--text-200 --route-width 460 --root-font 32px; fi

clear_world
echo "done"
