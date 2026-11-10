# CP-022 — Home v3 (R-HOME): review packet

Card: **CP-022**. Owner `sable`, reviewer `quill`. Branch `wt/cp-022-home`.
Contract: `desktop/src/30-home.js` (the only product file edited) + `tests/test_cp_022_home_v3.py`.

| Item | Value |
|---|---|
| Base | `master` `8eb594f`, with `wt/cp-020b-primitives@556a6fb` merged (`b00a7d1`) per the owner's partial-build ruling |
| Claims commit | `09678c3` (segment + tests) |
| Evidence commit | `22fa0eb` (M4 audit re-rendered on the rebuilt plugin, 15 PASS) |
| Plugin sha256 | `6e3e89684f73294c2cee9825b06ba6a7364ffdfe1fad595dd9cc29102a253524` |
| Generated module | rebuilt with `python3 scripts/build_plugin.py`; `tests.test_plugin_build` 11/11 OK |
| Concept frame | `docs/concept-parity/refs/home.png` (R-HOME) |
| Concept region compared | threshold band + wooden shelf + lower ledge with fox and clock |
| Matrix id | `home.v3` (`docs/visual-review/matrix.json`) |

## What this commit builds

`CoursebookHome` is now the v3 composition (SPEC-V3 §5.1), inside `desktop/src/30-home.js` only:

| Region | Built as |
|---|---|
| H2 threshold band | `section[data-cb-home-invitation]`: one `h2` (`home.title`) at the `heading` step, one `p` (`home.sub`) at `body`; type only, no kicker above the heading |
| H3 action row | one filled `PillAction` (`data-cb-action="primary"`, `Start a new course`) + one quiet outline `PillAction` (`Browse library`); stacks full-width at compact |
| H4 shelf heading | `h2[data-cb-home-shelf-label]` (`Your courses`) + `See all` only when the row holds more than four |
| H5 shelf | `ShelfPlank` (CP-020b) with up to **four** `HomeV3Card` paper objects, bottom-aligned on the plank; a fifth scrolls inside the frame with the 32 px edge mask (`data-cb-shelf-mask`) and `More courses to the right` |
| H5 card | cover from `cover_artifact_id` (real artifact only; no invented art), title `h3`, one subject chip (`subject_label`), one evidence line (`sections_done`/`sections_total`, else `evidence_summary.independent`/`total_objectives`), the backend's own `next_step.label`; one control, an overlay `RowButton` named `Open <title>` |
| H6 lower ledge | fox `clock` on the plank's right end (112 px at 920–999, 128 px at ≥1000, hidden below 620) and the kraft tag |
| Tag (O5) | rendered only when the newest course is `is_new` **and** its recorded stamp is under fourteen days old; opens that course; otherwise absent |
| States | first-use start plate on the plank with the waving fox; loading = four plank silhouettes at 40 % opacity, no shimmer; error = names the failed read + one `Try again`; offline = strip + retry with the already-read shelf kept; parent-only and archived as their own plates |

Data: every number and label is a CP-005 `library_item` field from the one `library.list` read. The UI
computes no percentage, count, rating or streak; a field the read did not carry is omitted.

## Evidence status — read this before scoring

**No stamped frames exist for this card.** CP-000 (`scripts/cp-capture.mjs`) requires a live
gateway-backed Desktop window; the owner's 2026-11-10 partial-build ruling defers the final capture
matrix, and a gateway restart is the operator's call, not mine. The 15 cells `matrix.json` lists for
`home.v3` are therefore **open**, not passed:

`default@1049/light/100`, `default@1049/dark/100`, `default@900/light/100`, `default@460/light/100`,
`default@1049/light/200`, `default@460/light/200`, `focus@1049/light/100`,
`reduced-motion@1049/light/100`, `forced-colors@1049/light/100`, `first-use@1049/light/100`,
`overflow@1049/light/100`, `empty@1049/light/100`, `loading@1049/light/100`,
`error@1049/light/100`, `offline@1049/light/100`.

What *is* machine-checked on this tree:

- `tests/test_cp_022_home_v3.py` — 15 cases, all green. It renders the shipped `plugin.js` through
  React and asserts: one filled pill and one quiet pill; card facts only (section pair, subject,
  next step, `New`); a missing pair omitted and the evidence pair used as the deck's fallback; no
  course hero/Continue/trailhead on global Home; four cards + `See all` + overflow hint; the O5 tag
  rule at 1 day / 15 days / attempted / older-course-negative; first use (start plate + wave fox +
  one create action); loading silhouettes with no shimmer; error naming `HOST_UNAVAILABLE` with one
  retry and not rendered as empty; offline strip keeping the shelf; parent-only and archived plates.
- `tests.test_desktop_home_hub` — green (the hub gate's start-plate, archived, failed-read and
  parent-only assertions all pass).
- `tests.test_desktop_tokens_v3`, `tests.test_v3_primitives`, `tests.test_plugin_build`,
  `tests.test_m4_visual_audit` — green.
- `python3 scripts/m4v-audit.py` — re-rendered on this plugin sha, 15 PASS.
- Full suite on this commit (`python3 -m unittest discover -s tests -t .`, log
  `/home/deseretsaint/.hermes/profiles/sable/cache/scratch/cp-022-suite.log`): **Ran 3367 tests in
  1123 s — 4 failures, 11 skipped**. All four failures are the stale v2 gate assertions in gap 1;
  nothing else fails.

## Known gaps (all recorded, none hidden)

1. **Four v2 gate assertions are now stale** and the card says the composition tests are superseded.
   They are red on this branch; all four are edits to modules outside CP-022's ownership list
   (`tests/test_desktop_gm002_home.py`, `tests/test_desktop_h151_action_type.py`).
   - `test_desktop_gm002_home.test_shelf_shows_four_to_six_authored_cards_and_see_all` — expects a
     **six**-card cap; SPEC-V3 §3.3/§5.1 H5 and this card's body set the shelf at four with `See all`.
   - `test_desktop_gm002_home.test_empty_home_has_one_create_action` — expects the v2
     `Browse the library`; the deck's `home.secondary` is `Browse library`. (`Start a new course` and
     `No courses yet.` now pass.)
   - `test_desktop_gm002_home.test_card_does_not_repeat_its_title_as_the_goal` — expects a
     `data-cb-home-card-goal` paragraph; SPEC-V3 §3.6 fixes one metadata pattern (title / subject /
     evidence) with no fourth line.
   - `test_desktop_h151_action_type.test_the_primary_is_the_lamp_field_at_44_px` — iterates every
     rendered surface and requires every `button[data-cb-action="primary"]` to be the v2 `--cb-lamp`
     field at 44 px. The v3 primary is `--cb3-terracotta` at 48 px (SPEC-V3 §3.10). The hook is kept
     because the GM-002 behavioural focus case reads it; the v2 gate needs the v3 surface excluded or
     re-pointed at `[data-cb3-pill="primary"]`.
   The **behavioural** GM-002 tests (`HomeSplitRouteTest`: Home → course home → back, the
   one-create-button count, the authored focus ring) are green, and nothing else in the 3367-test
   suite fails.
2. **The tag's age uses `updated_at`, not a creation stamp.** CP-005 exposes no `created_at`, so
   "less than fourteen days old" is measured from the newest recorded write. The rule itself (`is_new`
   + window + newest row only) is exact and tested; the field is the gap. A `created_at` on
   `library_item` is the clean fix and belongs to a contract card, not this one.
3. **Copy deviations from `docs/concept-parity/COPY.md` §2**, all deliberate and visible in the DOM:
   - `home.primary` renders as `Start a new course` (this card's own label, and the GM-002 behavioural
     anchor) rather than the deck's `Start a course`;
   - the first-run plate title is the shipped `No courses yet.` instead of `home.firstuse.title`,
     which repeats the invitation heading already on screen;
   - `home.firstuse.primary` (`Start your first course`) is unused: one surface keeps one action label;
   - the archived plate body and the error body add the shipped honest sentences
     (`Every course here is archived…`, `This is a failed read, not an empty library.`) beside the
     deck rows, because the state must name itself.
   A copy pass (CP-031 owns the deck) should either adopt these or rule them out.
4. **`CollectibleCard` (CP-020b) renders no heading without an artifact** — its typographic plate
   prints the title instead. The Home needs a real `h3` per card (heading order, and the GM-002 route
   harness reads it), so the card is composed from `PaperCard` + `CoverPlate3` + a local `h3`, and
   the cover plate is shown only when a real `cover_artifact_id` exists. Reported for CP-020c: the
   primitive should expose the title as an element, not only as plate paint.
5. **No live Desktop walk** in this run (no operator gateway restart), so nothing here claims pixels,
   target size or forced-colors behaviour beyond the CSS contract and the audit frames of the
   unchanged surfaces.

## Reviewer instructions

1. Do not trust this summary. Re-run: `python3 -m unittest tests.test_cp_022_home_v3`,
   `tests.test_desktop_home_hub`, `tests.test_plugin_build`, and `python3 scripts/build_plugin.py`
   followed by `git diff --exit-code desktop/plugin.js`.
2. Reproduce three evidence cells live from `6e3e8968…` if a rig is available; otherwise record the
   missing capture as a finding rather than a pass.
3. Score `docs/GM-CONCEPT-PARITY-RUBRIC.md` §7 (ten dimensions + A1–A5) in `SCORECARD.md`.
4. A single dimension below 4, or a missing anchor, is `request-changes` with the defect class and
   the test or capture that closes it. Three loops maximum.
