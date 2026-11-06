# CB-015 — visual polish, performance and the UX proof suite

Owner: Vellum. Branch `wt/cb-015-vellum`, source commit `64ea355` plus this evidence pack.
Rig: isolated home `~/.hermes/cb015-test/home`, backend `127.0.0.1:44220` (wire `cb.rpc` v6),
isolated Electron window on CDP `9338` (`COURSEBOOK_TEST_STATE=~/.hermes/cb015-test
scripts/cb013-live-window.sh`). The operator's window, profile and gateway were not touched.

Status in one line: **the design-system polish is machine-clean; the notebook, quiz and
textbook loops are live-proven on this branch; the 55-objective performance run is measured;
the 19-proof matrix is fully evidenced but only part of it was re-run in this worktree this
pass — every row says which branch its evidence comes from and what remains unproven.**

## 1. Design-system polish — enforced by a gate, not by eye

`scripts/cb015-hygiene.mjs` audits `desktop/plugin.js` with 13 source rules: raw colours,
ad-hoc shadows, gradients, `transition-all`, arbitrary type sizes, primitive chrome overrides,
hand-rolled buttons, native `title=`, decorative emoji, the literal `Loading…`, boxed blocks,
PAGE_INSET semantics and a second markdown renderer.

| rule | first run | now |
|---|---|---|
| arbitrary-type-size | 15 | **0** |
| hand-rolled-button (`<a>` styled as a button) | 2 | **0** |
| boxed-block (`rounded`+`border`+padding) | 3 | **0** |
| page-gutter (second gutter / missing PAGE_INSET_X) | 1 | **0** |
| the other 9 rules | 0 | 0 |

17 findings → 0. Changes in `desktop/plugin.js`: the 15 arbitrary sizes moved to the token
scale; the create-flow step label renders through `sdk.PanelSectionLabel`; three nested
rounded boxes became flat hairline grouping; two anchors became `sdk.Button asChild`; the page
gutter lives once on the route column so header and body share it; and the route root now
publishes `data-cb-route` / `data-cb-destination` so an audit can assert what is mounted.

Computed geometry is proved separately (not from source):

| scenario | viewport | root font | overflow-x | gutter | header x | body x | unnamed controls |
|---|---|---|---|---|---|---|---|
| desktop dark | 1427×892 | 16 px | 0 | 57.1 px | 294 | 294 | 0 / 12 |
| desktop light | 1427×892 | 16 px | 0 | 57.1 px | 294 | 294 | 0 / 12 |
| narrow | 513×1004 (460 override) | 16 px | 0 | 20.5 px | 21 | 21 | 0 / 12 |
| 200 % text | 1427×892 | 32 px | 0 | 57.1 px | 294 | 294 | 0 / 12 |

`docs/REVIEW_CB015-layout.json`. The 2 "clipped node" rows from the earlier pass are the
horizontally scrollable segmented strips (`overflow-x:auto`), not clipped content; the perf
pass re-measured the long section at 200 % text and 460 px with **0 clipped nodes and 0
overflow** (`docs/REVIEW_CB015-perf.json`).

## 2. Gates

| gate | command | result |
|---|---|---|
| unit/integration | `python3 -m unittest discover -s tests -t .` | 636 tests OK |
| ESM parse | `node --check desktop/plugin.js` | OK |
| design hygiene | `node scripts/cb015-hygiene.mjs` | 0 findings / 13 rules |
| canonical gate | `scripts/validate.sh` | 31/31 mounted expectations |

## 3. Live loops proved in this worktree

All values below come from `docs/REVIEW_CB015-loops.json`; every click is a labelled control,
every Enter is a real `Input.dispatchKeyEvent`, and answers were typed with `Input.insertText`.
The step stills captured during this run (`10`–`24`) were taken before the setup overlay was
dismissed and are not shipped; the same states appear overlay-free as gallery stills `44`–`48`.

**Teaching → attempt → notebook → exact section (proof 17).**
1. Detached section page: banner names the state, **Submit answer disabled**, `Reattach` /
   `Start a fresh run` present (`44-section-evidence-dark.png`).
2. `Start a fresh run` → a real chat session; one teaching turn typed into the host composer
   and sent with Enter. The plugin bound the run to the stored chat id
   `20261106_095109_eac24e`.
3. Back on the section: binding detached **false**, Submit enabled. A deliberately wrong
   answer was submitted and graded **Not yet / Hinted**, joining the earlier **Not yet / Cold
   attempt** — attempt `just now` + `1 min ago`, one lineage on `chk-discrimination-1`.
4. `Save to notebook` opened the dialog with the teaching excerpt pre-filled. The note
   (`Politeness alone is not the separator; the request is what makes it a confession.`) and
   tags `register, politeness` were saved; the row appears with `saved just now`,
   `Open in textbook`, `Continue from here`, `Edit note and tags`, `Remove from notebook`
   (`14`–`16`).
5. Notebook search `separator` keeps the row; the tag menu lists `politeness` and `register`;
   filtering by `register` keeps it (`17`, `18`).
6. `Open in textbook` lands on **Lesson 1 — Tell everyday affection…** with the same
   `ATTEMPTS ON THIS SECTION` list and the `SAVED FROM THIS SECTION` block (`19`).

**Quiz review (proof 18).** `20-quizzes-list-dark.png` shows both attempts with their original
answers. `Open attempt` opens a review that says *"Reviewing is read-only. Nothing here
consumes a retry or changes the old grade."* and shows the original verdict, assistance class
and provenance. `Try a new version` returns the backend's refusal in place:
`VALIDATION_FAILED: no unused, audited variant of this check exists; a replay would not be a
challenge.` — the honest no-op, matching CB-009's stated limit (`21`, `22`).

**Early/late sections (proof 19).** Opening the 4th (transfer) section and starting a fresh run
created a separate chat (`20261106_095453_7c8c5e`); returning to the first section left both
old attempts and the saved notebook entry intact (`23`, `24`). The first section honestly
reports **detached** while another chat holds the binding — that is the spec's "unrelated chats
never show a stale lesson", not data loss.

**A real grading failure was observed** during the late run: the attempt is recorded as
`Grading failed · Grader unavailable`, and its review is read-only. The `needs_retry` copy with
`Retry grading` exists in `AttemptControls`; an explicit override was not exercised in this
pass.

## 4. Performance — a real 55-objective pack

`scripts/cb015-perf-pack.py` builds the pack through `coursebook.packs.build_manifest` (the
backend's own hash, schema and teaching minima), then `scripts/seed-demo-course.py` imports it
through grant → preview → import on the live backend. No synthetic rows.

Pack: `cb015-perf-long-l0` 1.0.0, 55 objectives, 55 long bilingual sections (CJK + romaji +
English), 9 sources, 248 327 content bytes, course `crs_e83157235ab14c7e9c1ef731c37ab1af`,
enrollment `enr_007dd38142904b4694af3b9ae5d61039`.

`docs/REVIEW_CB015-perf.json`:

| measure | result |
|---|---|
| cold `#/coursebook` mount after reload | 1 502 ms (includes CDP wait; route present) |
| open 55-objective course detail | 12 ms render |
| Textbook index, 55 rows | **157 ms**, 533 nodes |
| Plan view, 55 objectives | **12 ms**, 535 nodes |
| scroll the index end-to-end (4 213 px / 1 414 px pane) | 12 frames, worst frame **6 ms**, 0 frames > 32 ms |
| open the 55th section (5 522 chars, CJK) | **161 ms**, 112 nodes |
| long tasks during last-section render | 2 (74 ms, 61 ms), max 74 ms |
| 200 % text on the long section | overflow-x **0**, clipped nodes **0** |
| 460 px on the long section | overflow-x **0**, heading visible |

Long course titles, 55 rows, long JP/EN text and 9 sources do not make the route slow or
unreadable. Stills `50`–`54`.

## 5. Accessibility and responsive (proof 15)

`docs/REVIEW_CB015-keyboard.json` (576 real Tab stops, then real Enter/Arrow/Escape):

- **Text-only**: 62 visible route controls, **0 unnamed**.
- **Focus visibility**: 10 of 576 stops had neither outline nor shadow (the composite
  `#cb-view-picker` stop and host-owned stops); all plugin buttons carried a ring/shadow.
- **Keyboard operation**: the view strip is a single composite stop (`role=combobox`,
  `#cb-view-picker`) switched with **ArrowRight** — one arrow selected `Textbook`. The answer
  field was reached by Tab (62 stops from the route's first control), typed with a real
  keyboard event and **submitted with Enter**; the submit was accepted.
- **Escape**: the notebook dialog opens and **closes on one Escape** (`49`, and the JSON
  `escape` record), but focus lands on `<body>` rather than returning to the `Save to notebook`
  trigger. That is a real (minor) a11y defect, recorded rather than papered over.
- **Reduced motion**: with `prefers-reduced-motion: reduce`, the maximum computed transition
  and animation duration on the route is **0.00001 s** (Chromium's zero), i.e. no motion
  theatre.
- **200 % / narrow**: measured in §4 and §1 — 0 overflow, 0 clipped content.

Harness concession stated plainly: the host's session list contributes hundreds of tab stops
before the workspace pane, so the walk starts by placing focus on the route's first control;
after that, all movement and activation is keyboard-only. A keyboard user reaching the plugin
from `<body>` must traverse that session list — a host tab-order cost, not a plugin trap.

## 6. Gallery (this branch, overlay-free)

`docs/REVIEW_CB015-gallery.json`; every still was captured after dismissing the host's
provider-setup overlay (which otherwise covers the window on a fresh isolated home).

| file | state |
|---|---|
| `40-courses-dark.png` | Courses list, two real enrollments, dark |
| `41-courses-light.png` | same DOM, light |
| `42-course-overview-dark.png` | course detail, Overview |
| `43-textbook-index-dark.png` | Textbook index, 4 objectives |
| `44-section-evidence-dark.png` | section page: detached banner, lesson, check |
| `45-notebook-dark.png` | notebook row with tags and actions |
| `46-notebook-search-dark.png` | search hit |
| `47-quizzes-list-dark.png` | attempts with original answers |
| `48-quiz-review-dark.png` | read-only review |
| `49-notebook-dialog-dark.png` | save dialog with prefilled excerpt |
| `50-perf-textbook-55-dark.png` | 55-row index, long title |
| `51-perf-last-section-dark.png` | 55th section, long CJK text |
| `52-perf-text200-dark.png` | 200 % text |
| `53-perf-narrow-dark.png` | 460 px |
| `54-perf-last-section-light.png` | same DOM, light |

Earlier stills from the first pass (`00`–`02`) and the layout stills were captured before the
overlay was dismissed; they are **not shipped** and not used as visual evidence in this packet.
The numeric layout table in §1 comes from the live DOM measurements in
`docs/REVIEW_CB015-layout.json`, and the long-section 200 %/460 px numbers were re-measured in
the perf pass.

## 7. UX_SPEC §16 proof matrix (19 rows)

Legend: **live@015** = re-proven in this worktree with this packet's JSON; **live@other** =
proven on another worktree/branch, cited; **boundary** = proven at the RPC/unit boundary but
not driven through the Desktop UI; **open** = not proven.

| # | proof | status | evidence |
|---|---|---|---|
| 1 | fresh profile → sidebar → preview → import → lesson | partial | first-run and list were live in the first pass (`00-first-run-dark.png`); this pass imported through `pack.grant/preview/import` (`seed-demo-course.py` output, §4) and opened lessons live. The *UI* import dialog needs a native folder picker and was not driven. |
| 2 | backend disabled → enable → brief kept | open | not driven this pass |
| 3 | new goal → cancel → reattach → approve edited plan | live@other | CB-011 (`docs/REVIEW_CB011.md` on `wt/cb-011-live`, plan job completed, edit + plan.approve verified) |
| 4 | chat and pane answers race → one attempt | open | not driven this pass |
| 5 | wrong answer → alternate representation → clarification not a retry | partial | wrong answer live (`Not yet / Hinted`, §3); the "hint is not a retry" accounting is CB-009/CB-013 evidence |
| 6 | grader timeout → needs_retry → override recorded | partial | live grading failure recorded `Grading failed / Grader unavailable` (§3); override path CB-013 (`21-pane-needs-retry`, `22-pane-overridden-evidence`) |
| 7 | hide/reopen/split pane mid-attempt → no lost answer | live@other | CB-009 pane runs (`docs/REVIEW_CB009-pane-chat.json`, `pane-12/13/14`) |
| 8 | restart at every attempt state | live@other | CB-013 restart-resume (isolated backend cycled, same data.db, same attempt rows) |
| 9 | parent edit after approval → reapproval before export | live@other | CB-011 export gate: `no_final_approval` refusal |
| 10 | invalid/malicious pack → precise error, no residue | boundary | adversarial suite 21/21 hostile packs rejected with zero residue (`tests/adversarial/evidence/attack-packs.json`, CB-014). The UI folder grant needs a native dialog. |
| 11 | offline → cached lesson, research paused | open | not driven this pass |
| 12 | source stale → impact banner, old evidence kept | open | not driven this pass |
| 13 | reimport same pack → resume vs fresh | boundary | `pack.import` modes exercised by `seed-demo-course.py --mode fresh/resume`; not clicked through the UI |
| 14 | course/chat/pack deletion distinct and recoverable | open | not driven this pass |
| 15 | keyboard / text-only / reduced motion / 200 % / narrow | **live@015** | §5 (`docs/REVIEW_CB015-keyboard.json`), Escape focus-return defect noted |
| 16 | 50+ objectives, long names, long JP/EN, many sources | **live@015** | §4 (`docs/REVIEW_CB015-perf.json`) |
| 17 | teaching moment → tag/search → exact section → new run | **live@015** | §3 (`docs/REVIEW_CB015-loops.json`, steps `notebook-*`, `notebook-section-identity`) |
| 18 | past quiz unchanged → new version → both inspectable | **live@015** | §3; new version refused honestly (`VALIDATION_FAILED`), both attempts remain inspectable (`20`, `21`, `22`, `47`, `48`) |
| 19 | jump early/late → separate runs, later evidence intact | **live@015** | §3 steps `late-run-*`, `early-evidence-intact`, `23`, `24` |

Result: **6 rows live in this worktree, 4 more live on a sibling worktree, 3 partial, 2
boundary-only, 4 open.** I did not manufacture the missing runs to turn this into 19 green
rows.

## 8. State matrix (UX_SPEC §13, 26 states)

Same legend; `not driven` means the implementation exists and was reviewed, but this pass did
not exercise it in the live window.

| state | status | note / evidence |
|---|---|---|
| first run | live@015 (pass 1) | real Create/Import actions, zero courses and no fake progress; pass-1 capture not shipped (overlay present) |
| no courses | live@015 (pass 1) | same state, zero rows, no fake progress |
| no search results | **live@015** | quiz filter exclusion: "No attempt matches … Clear filters"; notebook equivalent in CB-009 |
| backend off | not driven | copy + disable logic in `backendCopy`; not fault-injected |
| reconnecting | not driven | stale-read-only branch not exercised |
| unsupported backend | not driven | `implemented` gate reviewed; not fault-injected |
| plan generating | live@other | CB-011 plan job (2m01s, real stages) |
| generation failed | live@other | CB-011 lessons job failed `GRADER_UNAVAILABLE` |
| plan awaiting approval | live@other | CB-011 editable preview + explicit approve |
| lesson ready | **live@015** | section pages across both courses |
| attempt submitting | **live@015** | Submit disabled after submit; `ATTEMPTS ON THIS SECTION` updated once |
| grader unavailable / needs_retry | **live@015** | `Grading failed / Grader unavailable` row in review; copy in `AttemptControls` |
| detached chat | **live@015** | banner, `Reattach`, `Start a fresh run`, Submit disabled with reason (`44`) |
| offline | not driven | no network emulation run |
| TTS/image unavailable | n/a this pack | both packs declare no audio; lesson shows text and no media control |
| source stale/dead | not driven | impact banner not exercised |
| pack invalid | boundary | hostile-pack suite 21/21; native folder grant blocks UI path |
| incompatible pack update | boundary | version gate unit-tested; not UI-driven |
| grant revoked | boundary | staging/grant refusal unit-tested; not UI-driven |
| export awaiting review | live@other | CB-011 export gate refusal `no_final_approval` |
| export complete | open | CB-011 never reached final approval/export |
| download failed/cancelled | not driven | saved-on-backend vs local copy not exercised |
| course archived | not driven | Archived filter present, no archived enrollment created |
| course deleted | not driven | confirm dialog exists; destructive path not exercised |
| job interrupted | live@other | CB-011/CB-013 lease + resume evidence |
| demo fixture mode | **live@015** | every row reads "From a local pack · v1.0.0"; perf pack licence `local_only` |

## 9. Defects and limits found this pass

1. **Escape does not return focus to the trigger** (minor a11y). The dialog closes on one
   Escape; `document.activeElement` is `<body>` afterwards. Recorded, not fixed here to avoid
   a late change to the only dialog on the route.
2. **The view strip is a combobox, not a tablist.** `#cb-view-picker` is a single Tab stop;
   ArrowRight switches views. Keyboard-operable, but its accessible name is only
   "Course view" — the selected view is not in the name.
3. **Host tab order cost.** Reaching the route from `<body>` requires traversing the session
   list (~500 stops in this profile). Host-owned, reported here because a keyboard user feels
   it before they reach the plugin.
4. **Provider-setup overlay on a fresh isolated home** covers the window and photobombs any
   capture taken before dismissal. All gallery stills were re-taken after dismissing it via
   its own "I'll choose a provider later" action.
5. **`Save to notebook` label collision.** The page trigger and the dialog confirm share the
   same label; a probe that clicks the first match hits the trigger. Scoping the click to the
   dialog made the save work. This is a probe hazard, but a distinct confirm label would make
   the dialog clearer for automated and screen-reader users.
6. **`pack.preview` / `pack.import` from the Desktop** still require
   `pluginContext.files.requestFolder()`; invalid/incompatible/grant-revoked states can be
   proved at the RPC boundary but not through the UI on this machine.
7. **Perf fixture** `cb015-perf-long-l0` is a repetition fixture, licensed `local_only`, and is
   not teaching material. It exists only to stress the route.

## 10. Review packet contents

- `docs/REVIEW_CB015.md` (this file)
- `docs/REVIEW_CB015-loops.json` — every loop step, live
- `docs/REVIEW_CB015-perf.json` — 55-objective pack measurements
- `docs/REVIEW_CB015-keyboard.json` — 576 key stops, text-only, reduced motion, Escape
- `docs/REVIEW_CB015-gallery.json` — gallery manifest
- `docs/cb015-shots/10`–`24`, `40`–`54`, `60`–`62` — stills
- `scripts/cb015-hygiene.mjs`, `cb015-lib.mjs`, `cb015-loops-*.mjs`, `cb015-perf.mjs`,
  `cb015-perf-pack.py`, `cb015-keyboard.mjs`, `cb015-gallery2.mjs`
