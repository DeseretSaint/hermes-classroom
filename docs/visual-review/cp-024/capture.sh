#!/usr/bin/env bash
# CP-024 — the course-home (R-MAP) capture matrix, from the module this branch builds.
#
# Every frame goes through `scripts/cp-capture.mjs` and writes its `<name>.stamp.json` beside it.
# The screen is a course home, which is shell state rather than a URL, so each cell passes the
# card's own real-click driver (`--after-reload`) and the capture runs on the live window
# (`--no-reload`; the stamp records `capture.reloaded: false` and the module sha the window reads).
#
# Prerequisites (the review round-2 rig — the packet names these exact values):
#   * an isolated rig on this checkout: scripts/install-local.sh,
#     scripts/cb013-live-backend.sh (CB013_PORT=44427, token cp024-test-token),
#     scripts/cb013-live-window.sh (CB013_CDP_PORT=9361), state
#     ~/.hermes/coursebook-test-cp024-r2 (override with COURSEBOOK_TEST_STATE);
#   * the window has been restarted after the last `install-local.sh` so the evaluated module is
#     the installed one;
#   * `world` state fixtures are the rig's own DB rows (a real `course_worlds` row, valid brief),
#     switched per cell below; they are removed at the end.
#
# Cells (15):
#   eight baseline  1049/900/460 × light/dark, 1349 wide, forced colors
#   named states    plan-in-review, world-running, world-rejected, course-end, read-error, loading
#   text scale      460 at 200 % root text
#
# `no-world` used to be its own cell, but the rig's demonstration course has no `course_worlds`
# row at all, so that cell and the `default` cell were the same state and byte-identical — coverage
# that looked separate without being it. The `default` cells carry the no-world state; `read-error`
# and `loading` are the two states that need their own machinery (below).
#
#   docs/visual-review/cp-024/capture.sh [cell ...]      # no arguments = every cell
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
OUT="docs/visual-review/cp-024"
STATE="${COURSEBOOK_TEST_STATE:-$HOME/.hermes/coursebook-test-cp024-r2}"
HOME_DIR="${COURSEBOOK_TEST_HOME:-$STATE/home}"
DB="$HOME_DIR/plugin-data/coursebook/data.db"
COURSE="crs_650052975ca7406aaddda22122c89bad"
PLAN="pln_0e8776a5f5c541b5be19aea043ab0360"
# The completed-course fixture uses a course with no evidence rows at all, so the review
# scheduler has nothing to demote: moving its objectives to independent evidence is stable.
END_COURSE="crs_9fa51c20bfbc4028bc7c55c700f60c09"
END_PLAN="pln_12fbd05585454d818db48ae0394d7405"
PORT="${CB013_CDP_PORT:-9361}"
BACKEND="${CB013_BACKEND_URL:-http://127.0.0.1:44427}"
BACKEND_PORT="${CB013_PORT:-44427}"
TOKEN="${CB013_TOKEN:-cp024-test-token}"

BASE=(--out "$OUT" --cdp-port "$PORT" --state "$STATE" --plugin desktop/plugin.js
      --backend-url "$BACKEND" --token "$TOKEN" --require-v3 --no-reload --root-font 16px
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

# read-error: a stored world row whose brief does not satisfy the contract makes `world.read`
# answer INTERNAL_ERROR (the same refusal the manifest reproduces). One read fails; the backend
# and every other read stay healthy, so the frame is the surface's real error state.
broken_world() {
  sqlite3 "$DB" "INSERT OR REPLACE INTO course_worlds
    (id, course_id, revision, state, brief_json, concepts_json, selected_concept_id, style_hash,
     kit_hash, approved_hash, approved_at, error_json, created_at, updated_at)
    VALUES ('wld_cp024_broken', '$COURSE', 90, 'approved', '{\"course_id\":\"$COURSE\"}',
      '[]', NULL, NULL, NULL, NULL, NULL, NULL,
      '2026-11-10T23:00:00+00:00', '2026-11-10T23:00:00+00:00');"
}

# course-end: every section of the demonstration course carries independent state, which is what
# the shelf read counts as done. This is a FIXTURE in a disposable rig — it proves the completed
# state renders, not that a learner finished a course; the previous states are restored after the
# frame. No attempt, check or evidence row is fabricated: only the recorded objective state is
# moved to a state the product itself can reach.
SNAP="$(mktemp)"
SNAP_ENR="$(mktemp)"
end_state() {
  sqlite3 "$DB" "SELECT id || '|' || state FROM objectives WHERE plan_id='$END_PLAN';" > "$SNAP"
  sqlite3 "$DB" "SELECT id || '|' || updated_at FROM enrollments WHERE course_id='$END_COURSE';" > "$SNAP_ENR"
  sqlite3 "$DB" "UPDATE objectives SET state='independent_evidence' WHERE plan_id='$END_PLAN';"
  # The shelf lists the most recently updated enrollments first; this is bookkeeping only, so the
  # completed course is reachable through the same real click every other cell uses.
  sqlite3 "$DB" "UPDATE enrollments SET updated_at=strftime('%Y-%m-%dT%H:%M:%f+00:00','now') WHERE course_id='$END_COURSE';"
}

restore_end() {
  while IFS='|' read -r id state; do
    [[ -z "${id:-}" ]] && continue
    sqlite3 "$DB" "UPDATE objectives SET state='$state' WHERE id='$id';"
  done < "$SNAP"
  # The timestamp is restored too: a bumped enrollment reorders the shelf, and the later cells
  # drive the L0 demonstration course by clicking its row.
  while IFS='|' read -r id updated; do
    [[ -z "${id:-}" ]] && continue
    sqlite3 "$DB" "UPDATE enrollments SET updated_at='$updated' WHERE id='$id';"
  done < "$SNAP_ENR"
  rm -f "$SNAP" "$SNAP_ENR"
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
  appearance light
  node scripts/cp-capture.mjs --name course-home--1049--light--100--plan-in-review \
    --out "$OUT" --cdp-port "$PORT" --state "$STATE" --plugin desktop/plugin.js \
    --backend-url "$BACKEND" --token "$TOKEN" --require-v3 --no-reload \
    --after-reload "$OUT/drive-course-plan.js" \
    --after-reload-wait '[data-cb-course-home-v3]' --route-width 1049
fi
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
if want read-error; then
  appearance light
  broken_world
  cell course-home--1049--light--100--read-error --route-width 1049
  clear_world
fi
if want course-end; then
  appearance light
  end_state
  trap restore_end EXIT
  node scripts/cp-capture.mjs --name course-home--1049--light--100--course-end \
    --out "$OUT" --cdp-port "$PORT" --state "$STATE" --plugin desktop/plugin.js \
    --backend-url "$BACKEND" --token "$TOKEN" --require-v3 --no-reload \
    --after-reload "$OUT/drive-course-end.js" \
    --after-reload-wait '[data-cb-course-home-v3]' --route-width 1049
  restore_end
  trap - EXIT
fi
if want text-200; then cell course-home--460--light--200--text-200 --route-width 460 --root-font 32px; fi

# ── loading: a read that has not answered yet ──────────────────────────────────────────────────
# The course's `course.outline` read is held open by a forwarding proxy on the port the window is
# already connected to; every other request passes through to the same backend unchanged. Run this
# cell last: it moves the backend one port up and restores it afterwards.
if want loading; then
  echo "== loading: backend $BACKEND_PORT -> $((BACKEND_PORT + 1)), proxy on $BACKEND_PORT holds course.outline"
  COURSEBOOK_TEST_HOME="$HOME_DIR" CB013_PORT="$BACKEND_PORT" CB013_TOKEN="$TOKEN" scripts/cb013-live-backend.sh --stop >/dev/null 2>&1 || true
  COURSEBOOK_TEST_HOME="$HOME_DIR" CB013_PORT="$((BACKEND_PORT + 1))" CB013_TOKEN="$TOKEN" scripts/cb013-live-backend.sh
  CP024_PROXY_PORT="$BACKEND_PORT" CP024_PROXY_TARGET="http://127.0.0.1:$((BACKEND_PORT + 1))" \
    CP024_STALL_METHODS=course.outline \
    node docs/visual-review/cp-024/forward-proxy.mjs >"$OUT/forward-proxy.log" 2>&1 &
  PROXY_PID=$!
  trap 'kill "$PROXY_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do
    curl -s -m 1 -o /dev/null -H "Authorization: Bearer $TOKEN" \
      "http://127.0.0.1:$BACKEND_PORT/api/plugins/coursebook/runtime" && break
    sleep 0.25
  done
  # The window is restarted *after* the proxy is listening: main caches a connection's health, so
  # swapping the backend under a running window made the next reads fail with 502 before they ever
  # reached the proxy. A fresh boot sees one healthy connection on the same URL.
  COURSEBOOK_TEST_STATE="$STATE" CB013_CDP_PORT="$PORT" scripts/cb013-live-window.sh --restart
  sleep 4
  appearance light
  cell course-home--1049--light--100--loading --route-width 1049
  kill "$PROXY_PID" 2>/dev/null || true
  trap - EXIT
  COURSEBOOK_TEST_HOME="$HOME_DIR" CB013_PORT="$((BACKEND_PORT + 1))" CB013_TOKEN="$TOKEN" scripts/cb013-live-backend.sh --stop >/dev/null 2>&1 || true
  COURSEBOOK_TEST_HOME="$HOME_DIR" CB013_PORT="$BACKEND_PORT" CB013_TOKEN="$TOKEN" scripts/cb013-live-backend.sh
  # The held read's request died with the proxy; restart the window so the next cell starts clean.
  COURSEBOOK_TEST_STATE="$STATE" CB013_CDP_PORT="$PORT" scripts/cb013-live-window.sh --restart
  sleep 3
fi

clear_world
echo "done"
