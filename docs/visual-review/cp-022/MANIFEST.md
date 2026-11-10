# CP-022 — Home v3 (R-HOME): review packet (round 3)

Card: **CP-022**. Owner `sable`, reviewer `quill`. Branch `wt/cp-022-home`.
Contract: `desktop/src/30-home.js` (the only product file edited) + the two `tests/test_cp_022_*`
modules.

| Item | Value |
|---|---|
| Base | `master` `8eb594f`, with `wt/cp-020b-primitives@556a6fb` merged (`b00a7d1`) per the owner's partial-build ruling |
| Round-1 review commit | `14c4116` (plugin `6e3e8968…`) |
| Round-2 commit | `31233e5` — geometry, ledge, mask, copy; generated module rebuilt in the same commit |
| Plugin sha256 | `8c304d341c06eb07aafd455117f0986d01938b049d654593c8706b5b77fe476d` |
| Generated module | `python3 scripts/build_plugin.py`; re-running it is a no-op; `tests.test_plugin_build` 11/11 OK |
| Concept frame | `docs/concept-parity/refs/home.png` (R-HOME) |
| Concept region compared | threshold band + wooden shelf + lower ledge with fox and clock |
| Matrix id | `home.v3` (`docs/visual-review/matrix.json`) |

## Round-2 changes (what the review asked for)

1. **Shelf geometry (blocking defect closed).** Card width is now derived from the content box the
   shipped `.cb3-gutter` actually draws, and the **fox and kraft tag move off the card row onto the
   H6 lower ledge** (`data-cb-home-ledge`), which is what SPEC §2 measured (cards 272–1038, fox
   1155–1294 on the lower ledge) and what H5/H6 describe. The card row therefore owns the shelf's
   full width, so the arithmetic closes at every shell:

   | Route | Gutter (`.cb3-gutter`) | Content | Columns | Card | Row need | Lane |
   |---|---|---|---|---|---|---|
   | 1049 | 32.0 | 985.0 | 4 | 234 | 984 | 985 |
   | 900 | 27.45 | 845.1 | 3 | 271 | 845 | 845.1 |
   | 460 | 11.2 | 437.6 | 1 (stacked) | 437 | 437 | 437.6 |

   The old build sized a card from the whole route with no lane for the 128 px fox and returned
   **one** column below 920 while staying horizontal to 620 — 868 px clipped cards at 900 and a cut
   fourth card at 1049. Both are gone: `homeShelfLayout()` returns `{compact, columns, capacity}`,
   `capacity` is 4 wide / 3 mid / 4 stacked, and `overflow` is `hub.total > capacity` (SPEC §5.1:
   5+ wide, 4+ mid) rather than `> 4`.
2. **Overflow hint is wide and mid only** (COPY `home.overflow.hint`): it is not rendered at 460,
   where the row is a stacked column with `overflow-x: visible`. Asserted at 460 with five courses
   (`test_home_v3_shelf_fits_its_route`).
3. **The edge mask re-measures.** The effect now depends on the measured route width and observes
   the row with a `ResizeObserver`; a narrowed route (chat rail opens) recomputes `data-cb-shelf-mask`
   instead of leaving a clipped shelf unfaded (`test_home_v3_mask_remeasures_on_a_route_change`).
4. **Copy record completed** — see gap 3 below; every visible string is now enumerated and ruled.

## Round-3 changes (the non-discriminating closing tests)

The round-2 product geometry was accepted; round 3 fixes three oracles that passed regardless of the
code, and proves each one bites:

1. **`test_home_v3_copy_has_an_id` is no longer vacuous.** `_deck_patterns()` no longer maps text
   placeholders (`{subject label}`, `{next step}`) to `. +`: a text placeholder is a field value, so
   the oracle matches it against the payload's **own state string**, and only numeric placeholders
   keep a shape (`\d+`). Additions: a compositional acceptor (the error state concatenates the
   backend read, the failed-read word and the deck body into one paragraph, so every character must
   be consumable from a frozen unit), an overflowing payload so `See all` is actually rendered, an
   assertion that each frozen pending really appears, and negative controls that assert an invented
   sentence is rejected by both the exact and the compositional path. `Start a new course` and
   `See all` are enumerated in the frozen CP-031 pendings.
   *Negative control reproduced:* removing `Start a new course` from the pendings makes the test
   fail with `Home rendered a string with no COPY.md id or state source: 'Start a new course'`.
2. **The fox assertion runs.** `MEASURE` queried `[data-cb-fox]` while the primitive renders
   `data-cb3-fox`, so `foxOnShelfRow` was always false. It now queries `[data-cb3-fox]` and asserts
   the fox **exists** and is contained by `[data-cb-home-ledge]` at 1049/900, and is absent at 460.
   *Negative control reproduced:* restoring the old selector reports `fox: None`, so the new
   existence assertion fails.
3. **The mask probe exercises the `ResizeObserver`.** jsdom has no `ResizeObserver`, so the round-2
   test only re-exercised the pre-existing window `'resize'` listener. `MASK` now installs a
   `ResizeObserver` stub **before** importing the plugin, changes the stubbed row geometry, fires
   the observer callback with **no** window resize, and asserts the mask goes `none → right → none`.
   The window-resize/route-width path stays as a second assertion.
   *Negative control reproduced:* disabling the component's observer branch yields `observers: 0`,
   `afterObserver: none`; the shipped module yields `observers: 1`, `none → right → none → right`.


## What this commit builds

`CoursebookHome` is the v3 composition (SPEC-V3 §5.1), inside `desktop/src/30-home.js` only:

| Region | Built as |
|---|---|
| H2 threshold band | `section[data-cb-home-invitation]`: one `h2` (`home.title`) at `heading`, one `p` (`home.sub`) at `body`; type only, no kicker |
| H3 action row | one filled `PillAction` (`data-cb-action="primary"`, `Start a new course`) + one quiet outline `PillAction` (`Browse library`); stacks full-width at compact |
| H4 shelf heading | `h2[data-cb-home-shelf-label]` (`Your courses`) + `See all` only when the row holds more than four |
| H5 shelf | `ShelfPlank` (CP-020b) holding up to **four** `HomeV3Card` paper objects bottom-aligned on the plank; the row scrolls inside its frame and carries the 32 px edge mask (`data-cb-shelf-mask`) + `More courses to the right` when `hub.total > capacity` |
| H5 card | cover from `cover_artifact_id` (real artifact only), title `h3`, one subject chip (`subject_label`), one evidence line (`sections_done`/`sections_total`, else the evidence pair), the backend's own `next_step.label`; exactly one control, an overlay `RowButton` named `Open <title>`; `box-sizing: border-box` so the measured box is the box |
| H6 lower ledge | `div[data-cb-home-ledge]` under the plank: the kraft tag and the fox `clock` (128 px at ≥900, 112 px at 620–899, hidden below 620). The ledge is never inside the card row |
| Tag (O5) | only when the newest course is `is_new` **and** its recorded stamp is under fourteen days old **and** it has no attempt; opens that course; otherwise absent |
| States | first-use start plate on the plank with the waving fox on the ledge; loading = plank silhouettes at 40 % opacity, no shimmer; error = names the failed read + one `Try again`; offline strip + retry keeping the already-read shelf; parent-only and archived plates |

Data: every number and label is a CP-005 `library_item` field from the one `library.list` read. The
UI computes no percentage, count, rating, XP or streak; a field the read did not carry is omitted.

## Evidence status — read this before scoring

**No stamped frames exist for this card.** CP-000 (`scripts/cp-capture.mjs`) requires a live
gateway-backed Desktop window; the owner's 2026-11-10 partial-build ruling defers the final capture
matrix, and a gateway restart is the operator's call. The 15 cells `matrix.json` lists for
`home.v3` are therefore **open**, not passed:

`default@1049/light/100`, `default@1049/dark/100`, `default@900/light/100`, `default@460/light/100`,
`default@1049/light/200`, `default@460/light/200`, `focus@1049/light/100`,
`reduced-motion@1049/light/100`, `forced-colors@1049/light/100`, `first-use@1049/light/100`,
`overflow@1049/light/100`, `empty@1049/light/100`, `loading@1049/light/100`,
`error@1049/light/100`, `offline@1049/light/100`.

What *is* machine-checked on this tree:

- `tests/test_cp_022_home_v3.py` — 16 cases, all green: one filled + one quiet pill; card facts only;
  a missing pair omitted and the evidence pair used as the deck fallback; no course hero/Continue/
  trailhead on global Home; four cards + `See all` + capacity overflow; the O5 tag rule at 1 / 15
  days / attempted / older-negative; first use; loading; error; offline; parent-only; archived;
  **every visible string is a `home.*` deck row, a backend value, or one of the enumerated CP-031
  pendings** (`test_home_v3_copy_has_an_id`).
- `tests/test_cp_022_geometry.py` — 3 cases, all green:
  - `test_home_v3_shelf_fits_its_route` — renderer arithmetic at 1049 / 900 / 460 (`n·card + gap`
    against the shipped gutter), the fox/ledge placement, the hint's wide+mid placement and the
    capacity overflow marker;
  - `test_home_v3_shelf_cards_sit_inside_the_row` — the shipped markup painted in **headless
    Chromium** at 1049 / 900 / 460: every `[data-cb-home-card]` border box lies inside
    `[data-cb-home-shelf-row]`'s clip box, 4 / 3 / 1 cards show, the row direction is row/column as
    specified, page overflow is 0, and the fox is not a child of the card row;
  - `test_home_v3_mask_remeasures_on_a_route_change` — a jsdom mount with stubbed row geometry:
    a fitting row paints `none`, and narrowing the route (four cards no longer fitting three
    columns) makes the mask `right`.
- `tests.test_desktop_home_hub`, `tests.test_desktop_tokens_v3`, `tests.test_v3_primitives`,
  `tests.test_plugin_build`, `tests.test_m4_visual_audit` — green.
- `python3 scripts/m4v-audit.py` — re-rendered on `8c304d34…`, 15 PASS.
- Full suite on the round-2 tree (`python3 -m unittest discover -s tests -t .`, log
  `/home/deseretsaint/.hermes/profiles/sable/cache/scratch/cp-022-r2-suite.log`): **Ran 3371 tests
  in 850 s — 5 failures, 11 skipped**. All five are the stale v2 gate assertions in gap 1; nothing
  in CP-022's own modules fails.

## Known gaps (all recorded, none hidden)

1. **Five v2 gate assertions are now stale** and this card says the composition tests are
   superseded. They are outside CP-022's ownership list (`tests/test_desktop_gm002_home.py`,
   `tests/test_desktop_h151_action_type.py`) and tracked on follow-up card `t_847e5b1b`. The
   follow-up card also records that CP-003's `GATE-MIGRATION.md` never covered
   `test_desktop_gm002_home` — the packet's earlier "superseded per CP-003's table" was imprecise.
   The fifth arrived in round 2: `test_offline_says_so_without_inventing_courses` asserts the v2
   literal `"Offline"`; the v3 banner now speaks the deck's own `home.offline.title`
   ("You are offline"). Full-suite log: `…/cache/scratch/cp-022-r2-suite.log`
   (`Ran 3371 tests in 850 s — 5 failures, 11 skipped`; the four round-1 failures plus this one).
2. **No stamped frames and no live walk** (no operator gateway restart), so A3 (material surface) and
   A4 (subject mark) stay **unverified**, and paint/type/contrast scores are provisional. This is an
   environment capability gap, not a maker dodge.
3. **Copy record — every visible Home string, ruled.** SPEC §4: a screen may not render a string
   with no id. This card owns no deck file, so a no-id string may only be *reduced* or *routed*.

   Reduced in round 2 (were no-id, now deck rows or omissions):
   - the offline banner word `Offline` → `home.offline.title` ("You are offline");
   - the stale strip `Reconnecting. Showing the courses that were last read.` / `Retry now` →
     `home.error.body` / `home.error.action`;
   - `No next step recorded` → the line is **omitted** when `next_step.label` is absent (honest
     omission, the same rule as the evidence pair);
   - `2 more courses behind See all.` → **removed**; `See all` + `home.overflow.hint` are the
     affordances, and no count is invented;
   - `This backend does not report course mode yet.` → the whole notice is **removed**; with no
     `world.read` the card simply omits the mode chip, which is the honest omission.

   **Still no `COPY.md` §2 id — frozen by `test_home_v3_copy_has_an_id`, routed to CP-031 (nine):**

   | String | Where | Why it is not a deck row yet |
   |---|---|---|
   | `Start a new course` | primary action label (`CB_HOME_V3_COPY.primary`) | the card body's own label; the deck ships `home.primary` = `Start a course` and `home.firstuse.primary` = `Start your first course`. Also the GM-002 behavioural anchor — routed to CP-031 with the primary |
   | `See all` | H4 shelf action (`seeAll`) | COPY.md §2 has no see-all / overflow-action row at all |
   | `Parent Studio holds your lesson plans.` | parent-only plate title | COPY has no parent-profile state copy at all |
   | `This profile has parent-led lesson plans, not a learner course. Start a learner course here, or open Parent Studio.` | parent-only plate body | same |
   | `Open Parent Studio` | parent-only plate action | same; only `nav.parent` names the destination |
   | `No courses yet.` | first-use plate title (`emptyShippedTitle`) | deck's `home.firstuse.title` repeats the invitation heading already on screen; the shipped line is the plate's own |
   | `Every course here is archived. Unarchive one in Courses to continue it.` | archived plate body (`emptyArchivedBody`) | deck has `home.empty.*` for "no matches", not for the all-archived reason |
   | `This is a failed read, not an empty library.` | error body (`failedReadWord`) | deck's `home.error.body` says "Nothing you saved is lost"; the invariant sentence is additionally pinned by the existing behavioural `tests.test_desktop_home_hub`, which this card does not own |
   | `Untitled course` | card title fallback | defensive fallback for a contract-violating row (CP-005 `title` is required); normally never visible |

   Deck-vs-card-body conflicts, disclosed rather than silently resolved (SPEC §4: the deck wins when
   it has an id; the card-body sentence has none, so it is not rendered):
   - **Subline.** Card body says "Choose a course or start a new expedition."; the build renders
     `home.sub` = **"Pick a course, or start a new one."** (the deck row).
   - **Primary.** Card body says `Start a new course`; the build renders that, while the deck's
     `home.primary` is `Start a course`. `Start a new course` is this card's own label, the GM-002
     behavioural anchor, and carries no deck id — routed to CP-031 with the primary.
   - **Kraft tag.** Card body says the tag shows `New: <title>`; the build renders the deck's
     `home.card.new`/`home.tag.firstuse` label **"New course"** with the course title beneath it.
     `New: <title>` has no id, so it was not adopted.
   - `home.firstuse.primary` (`Start your first course`) stays unused: one surface keeps one action
     label, and two create labels on one screen is the failure the deck exists to prevent.
4. **`CollectibleCard` (CP-020b) renders no heading without an artifact** — its typographic plate
   prints the title instead. The Home needs a real `h3` per card, so the card is composed from
   `PaperCard` + `CoverPlate3` + a local `h3`, with the plate only when `cover_artifact_id` exists.
   Reported for CP-020c.
5. **SPEC §3.3's shell table assumes an 80 px rail inside the route; the shipped route renders a
   tab-strip nav and no rail.** Consequence: at route 1049 the content box is 985 (not 905), so H5's
   `4 × 214` becomes `4 × 234`, and the mid gutter is `.cb3-gutter`'s `3.05cqi` = 27.45 (not 24), so
   H5's `3 × 273` becomes `3 × 271`. Cards fit either way; the *exact* H5 numbers need a ruled
   decision (rail lands, or H5's mid gutter is recorded as 3.05cqi) — a CP-014/CP-020c item, not a
   CP-022 edit.
6. **The tag's age uses `updated_at`**, not a creation stamp: CP-005 exposes no `created_at`, so
   "less than fourteen days" is measured from the newest recorded write. The rule itself (`is_new` +
   window + newest row only) is exact and tested; the field is the gap.

## Reviewer instructions

1. Do not trust this summary. Re-run:
   `python3 -m unittest tests.test_cp_022_home_v3 tests.test_cp_022_geometry`,
   `tests.test_desktop_home_hub`, `tests.test_plugin_build`, then `python3 scripts/build_plugin.py`
   followed by `git diff --exit-code desktop/plugin.js`.
2. Reproduce the blocking defect class directly: render at 1049 / 900 / 460 and paint in Chromium;
   a card outside the row's clip box, a clipped fourth card, or an 868 px card at 900 is the same
   defect returning. The geometry module does exactly this and prints the measured boxes on failure.
3. Reproduce three evidence cells live from `8c304d34…` if a rig is available; otherwise record the
   missing capture as a finding rather than a pass.
4. Score `docs/GM-CONCEPT-PARITY-RUBRIC.md` §7 (ten dimensions + A1–A5) in `SCORECARD.md`.
5. A single dimension below 4, a missing anchor, or a card outside its row clip box is
   `request-changes` with the defect class and the test that closes it. Three loops maximum.
