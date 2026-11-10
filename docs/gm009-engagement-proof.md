# GM-009 evidence — game engagement store and XP rules

Backend-only card; there is no screen in this slice. The proof is the executed test set, the wire
contract delta and the database invariants the tests assert against a real SQLite store.

## Commands and observed results

| Command | Result |
|---|---|
| `python3 -m unittest tests.test_game_engagement -v` | 11 tests, `OK` — the seven card-named tests plus level/point/contract checks |
| `python3 -m unittest tests.test_contracts` | 171 tests, `OK` — `cb.rpc` v21 is additive over the byte-identical v20 snapshot |
| `python3 -m unittest tests.test_gm_contract tests.test_kernel_schema tests.test_platform_config tests.test_desktop_contracts tests.test_desktop_h194_fine_tune_ui` | 99 tests, `OK` |
| `python3 -m unittest tests.test_harness_e2e` | 26 tests, `OK` — the H-40 packet was regenerated for the v21 echo |
| `python3 -m unittest discover -s tests -t .` | full suite, `OK` (see the commit message for the exact run) |
| `node --check desktop/plugin.js` | not touched by this card; no desktop file changed |

## What the tests prove

- `test_game_xp_awarded_once_per_real_action` — one ledger row per
  `(enrollment_id, action_kind, action_id)`, `awarded: false` on a second award, identical replay
  for the same `idempotency_key`, `IDEMPOTENCY_CONFLICT` for a different payload under it.
- `test_game_xp_ignores_clicks_and_timers` — `page_open`/`timer` are not wire values; an invented
  `lesson_step`/`check_submitted` id is refused because no durable row backs it; a brand-new run
  is not a `returned` action. The ledger stays empty.
- `test_game_xp_not_in_evidence_or_export` — `evidence.inspect` and `course.export.read` carry no
  XP key, and `packs.export_allowlist()` has no engagement field.
- `test_textbook_has_no_engagement_surface` — `engagement.read` is refused
  (`VALIDATION_FAILED`, `reason: engagement_is_game_only`) for `textbook` and legacy `NULL`; the
  rows survive the switch and the same total returns when the course is switched back.
- `test_core_lesson_not_gated_by_xp` — with zero XP, `lesson.begin`, `check.open` and
  `attempt.submit` still work; `coursebook/domain.py` never reads `game_engagement`.
- `test_game_feedback_toggle_hides_without_deleting` — with the `game_feedback` setting off the
  read reports `feedback_visible: false` and no recent events, while the XP total and every ledger
  row are unchanged; turning it back on restores the same total.
- `test_parent_read_does_not_return_xp` — `parent.blueprint.read` carries no XP, and
  `evidence.inspect` still serves the real attempts.

## Contract and storage

- `contracts/rpc.v21.json` appends `engagement.read` and `engagement.award`; `rpc.v20.json` is
  byte-identical history (`sha256:81cf882f…`). No existing method or payload moved.
- Storage is the GM-001 `game_engagement` table (`cb.db` v13, migration 0013), whose unique key is
  the idempotency fence. No migration or schema change is made by this card.
- `game_feedback` is a declared plugin setting (`plugin.yaml`), read only by
  `coursebook/engagement.py`.
