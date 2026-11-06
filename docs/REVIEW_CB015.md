# CB-015 — visual polish, performance and the UX proof suite

Owner: Vellum. Branch `wt/cb-015-vellum`, source commit `64ea355` plus this evidence pack.
Rig: isolated home `~/.hermes/cb015-test/home`, backend `127.0.0.1:44220` (wire `cb.rpc` v6),
isolated Electron window on CDP `9338` (`COURSEBOOK_TEST_STATE=~/.hermes/cb015-test
scripts/cb013-live-window.sh`). The operator's window, profile and gateway were not touched.
Proof 12 was re-driven later on the CB-015 residual branch (`wt/cb015-proof12`, base `9f4b387`):
isolated rig `~/.hermes/coursebook-test` (its own home and userdata), backend `127.0.0.1:44219`
wire **`cb.rpc` v7 / cb.db v4 (52 methods)**, window CDP `9337`. Proof 12 (§3b) and the residual
rows 3/7/8/9 (§12) were driven later on the v7 backend; everything else in this packet is the
v6 pass described above.

Status in one line: **the design-system polish is machine-clean; the notebook, quiz and
textbook loops are live-proven on this branch; the 55-objective performance run is measured;
the 19-proof matrix stands at 10 live / 6 partial / 2 boundary-only / 1 open, with every
missing half named — no row is claimed green on prose alone.**

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

Measured on the merged master tree, not on the branch this packet was written on.

| gate | command | result |
|---|---|---|
| unit/integration | `python3 -m unittest discover -s tests -t .` | **674 tests OK** at `459b99f` (this packet's own measurement at `64ea355` was 636; master grew with CB-014/CB-049 and the rows 3/7/8/9 pass) |
| ESM parse | `node --check desktop/plugin.js` | OK at `459b99f` |
| design hygiene | `node scripts/cb015-hygiene.mjs` | 0 findings / 13 rules |
| release gate | `bash scripts/validate-plugin.sh` | 3/3 on `459b99f` (787 files) — clean `git archive` export, admission + security scan `safe` |
| canonical gate | `scripts/validate.sh` | 31/31 mounted expectations, recorded when the packet was assembled; not re-run in the final gate pass |

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
`Retry grading` exists in `AttemptControls`; the explicit override that follows it was driven
end to end in the later pass — `Retry grading` keeps the same nonce and stays `needs_retry`,
then `Move on… → Record override` advances the check and tags the attempt
`Override — not independent evidence` (§11(4), `docs/REVIEW_CB015-needs-retry.json`).

## 3b. Proof 12 — a real source revalidation, its banner, and the evidence that survives

The v7 backend adds `source.revalidate` (52nd method). `scripts/cb015-proof12-stale.py` drives it
through the same `cb.rpc` endpoint the Desktop calls; `scripts/cb015-proof12-ui.mjs` reads the
rendered result from the live window on CDP `9337`. No UI control was added: Atlas ruled that a
Sources-tab "Check for changes" button must not ship while `source.revalidate` is detection-only,
so the transition is driven through the proof harness and the plugin only renders the state.

Course: pack-imported `japanese-affection-context-l0` on the v7 rig, enrollment
`enr_36266a77f6024e4da1130d6bd2404bbf`, source `src_f4da58f3e9fe4635b0d03bf3ba879d4f`.

| stage | observed |
|---|---|
| pre-transition attempt | `attempt.submit` on `chk_e5d74106de12466faa2389efebf0671d` answered `B` → `verdict: pass`, `evidence_class: cold`; attempt `att_774c1a97d154437b9ec4918418493756` and two evidence rows (attempt + independent_evidence) committed; DB counts **attempts 32 / transitions 63 / evidence 45** |
| baseline revalidation | `source.revalidate` with captured content → `changed: false`, `previous_hash: null` (a pack source has no baseline yet), status `authoritative_documentation`; the baseline hash is now recorded |
| changed revalidation | different content → `changed: true`, `review_required: true`, `support_status: "stale"`, `previous_hash` = the baseline, new `content_hash`; envelope `revision: 0` (not an enrollment revision) |
| library row | `library.list` for the same enrollment returns `warning: "stale_source"` |
| retained evidence | after the transition the same attempt is `Passed · Cold attempt · just now · B` in Quizzes; the same two evidence rows are present; no retained attempt changed verdict or class; DB counts are **still 32 / 63 / 45** |

Rendered proof (`docs/cb015-shots/row12-01`–`04`): the library row carries the `Source stale`
badge and *"A source behind this course changed. Existing evidence is kept; the source needs
review."*; the course Overview shows the banner *"A source behind this course changed. Old
evidence is kept; the source needs review."* with `Passed · just now` and `1 independent` beneath
it; Quizzes lists the pre-transition attempt; Sources renders the revalidated row as `stale`
(`fetched just now`). The Sources controls are `New course / Courses / Library / Parent Studio /
All courses / Resume lesson / Overview / Textbook / Notebook / Quizzes / Plan / Evidence /
Sources` — there is no revalidate control, and the probe fails if one appears.

**Honest limit, not hidden:** on this pack-imported course the returned `impact` lists are empty
(`objective_ids`, `check_ids`, `lesson_ids`, `artifact_ids`). The impact query reads
`gen_plan_sections.source_ids_json`, and pack import writes no `gen_plan_sections` rows — those
belong to the research/generation pipeline. So the banner states the affected *course* and the
review need, but cannot name an objective/check on this course shape, and `CHECK_STALE` cannot
fire. The citation-backed impact ids and the `CHECK_STALE` refusal (with zero attempt/evidence
writes) are proven at the same seam by `scripts/proof_contract_v7.py` (4/4 OK) using a seeded
section that does cite the source. This is recorded as a backend follow-up on t_8863beb4 rather
than papered over.

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
  `escape` record). Focus used to land on `<body>`; that is **fixed and re-proved** in §11 —
  `docs/REVIEW_CB015-a11y2.json` now shows `document.activeElement` is the `Save to notebook`
  trigger after the dialog closes (`61-after-escape-focus.png`).
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
| 2 | backend disabled → enable → brief kept | **live@015** | `docs/REVIEW_CB015-fault-backend-off.json`: the isolated gateway on 44220 was stopped (pid recorded), the page rendered `Backend off` + the enable instructions + `Open Capabilities` / `Check again` with **zero rows and no New course**, then the gateway was started again and the page's own `Check again` returned both enrollments with their revisions. While the whole gateway is down the host paints its own CONNECTING view over the workspace (host-owned), so `70-plugin-half-disabled-dark.png` isolates the plugin half: surface stays mounted, names `VALIDATION_FAILED`, no fake rows, `Try again` recovers. |
| 3 | new goal → cancel → reattach → approve edited plan | partial | **cancel + reattach driven, approve-edited-plan not.** The Desktop had no cancel affordance at all (`jobs.cancel` was never called), so this branch adds one to the job line — `Cancel generation` while queued/running, a named `cancelled` state, and `Run this stage again` re-queuing the job's own stored brief. Driven on the disposable `~/.hermes/cb015-residual` rig: `docs/REVIEW_CB015-row3a.json` + `docs/cb015-residual/row3-0{3,4,5,6}.png` show the plan job `job_27f922c7…` queued → **cancelled** by the button, the course reopened as `cancelled` with its brief preserved, then `Run this stage again` producing `job_40849e53…`. That second job completed (`plan authored (needs_review)`, 5 objectives), but the **edit-then-approve half was not finished**: `scripts/cb015r-row3b.mjs` could not open the Plan editor (`Edit plan` never rendered after the view switch), so no approved-plan artifact exists. |
| 4 | chat and pane answers race → one attempt | open | not driven this pass |
| 5 | wrong answer → alternate representation → clarification not a retry | partial | wrong answer live (`Not yet / Hinted`, §3); the "hint is not a retry" accounting is CB-009/CB-013 evidence |
| 6 | grader timeout → needs_retry → override recorded | **live@015** | `docs/REVIEW_CB015-needs-retry.json`: the open-response check on the JP course's 4th section fails closed (`I couldn’t grade this attempt`, `Retry grading` / `Edit answer` / `Move on…`), Retry re-sent the same nonce and stayed `needs_retry` (check still v2, no second attempt row), and `Move on… → Record override` recorded the override — durable attempt row `Override — not independent evidence` plus the objective badge `Overridden`, with the check advanced v2 → v3. |
| 7 | hide/reopen/split pane mid-attempt → no lost answer | partial (hide + reopen driven; split not) | `docs/REVIEW_CB015-row7.json`: in the bound chat's pane (Check v15), a real answer was typed into `#cb-attempt-answer`, `Submit answer` clicked, and the host's right sidebar hidden **immediately** (`Hide right sidebar`, leaving `Show right sidebar` as the only toggle). While hidden the pane painted nothing; reopening it showed the committed verdict **Not yet** (`Cold attempt / does not match an accepted answer`), so the submission landed once and nothing was lost on hide. **What this artifact does not prove:** the before/after attempt *count* and the attempt id. The harness's attempts-block regex in `scripts/cb015r-row7.mjs` is double-escaped, so `attemptsBlock` is `null` in every step, and the `att_8ff275dc…` id that earlier prose quoted is not present in `docs/REVIEW_CB015-row7.json` — it is withdrawn here rather than repeated. Stills `row7-01..03`. **Split was not driven** — the layout editor did not expose a split at this width, so that half of the row is still unproven. |
| 8 | restart at every attempt state | partial | `docs/REVIEW_CB015-row8.json`: the isolated gateway (44219, same `data.db`) was **cycled** and the window hard-reloaded at three states, each read before and after on the same section: **awaiting input** (ordinal 2, Check v2, open check), **graded** (ordinal 1, Check v15, `Not yet`), **overridden** (ordinal 4, `Override — not independent evidence`). Every cycle returned the same objective title, the same check version, the same verdict/override copy and a byte-identical `ATTEMPTS ON THIS SECTION` block (`sameAttemptsBlock: true` in all three). **Not restarted:** `submitting` (mid-flight), a standalone `needs_retry`, and `detached`. The row stays partial on those three states. Caveat on the labels: the cycle recorded as **awaiting input** actually captured a body showing `Passed` with a *detached* banner, so that label is approximate even though its before/after comparison is real. |
| 9 | parent edit after approval → reapproval before export | partial | **refusal half driven, restoration half blocked by a backend gap.** On `crs_3ea89…` (active final approval, `export.ready=true`), `docs/REVIEW_CB015-row9-rpc.json` shows `plan.replan` then `parent.plan.edit` turning the approval `superseded` (`course_edited`) and the export gate `ready:false` with `parent.export` refusing `POLICY_VIOLATION / plan_not_approved`; `direct parent.plan.edit on an approved plan` is refused `plan_not_draft` ("use plan.replan"). In the UI, `docs/REVIEW_CB015-row9-ui.json` records the Export screen after that edit: badge **Changes need review**, `Lesson set approval — Changes need review`, the blocked sentence, and `Export the approved files` **disabled**; after `Approve plan` it is still blocked with export disabled. The **reapproval → export** step could not be completed: the replanned plan has no `gen_plan_documents` row, so `Generate lessons` fails `INTERNAL_ERROR: plan 'pln_4a4e0887…' has no authored document` (`docs/REVIEW_CB015-row9-ui2.json`, job `job_5779b460…`) and there is no lesson set to re-approve. That is a product gap, not a UI proof; carded as `t_fc758da8`, and Atlas must rule on it at `t_c9baab37`. |
| 10 | invalid/malicious pack → precise error, no residue | boundary | adversarial suite 21/21 hostile packs rejected with zero residue (`tests/adversarial/evidence/attack-packs.json`, CB-014). The UI folder grant needs a native dialog. |
| 11 | offline → cached lesson, research paused | **live@015** | `docs/REVIEW_CB015-fault-offline.json`: `Network.emulateNetworkConditions(offline)` → `navigator.onLine=false`, the header renders `Offline` + a sentence naming what still works and what is paused, `New course` is absent while offline, a course opens from what the profile already has, and the notice clears when the connection returns (`64`–`66`). |
| 12 | source stale → impact banner, old evidence kept | **live@015** | `docs/REVIEW_CB015-row12-rpc.json` + `docs/REVIEW_CB015-row12-ui.json` (+ `cb015-shots/row12-01`–`04`): on the v7 rig, `source.revalidate` records a baseline (`changed=false`), then a changed fetch returns `changed=true`, `support_status="stale"`, `review_required=true`; `library.list` returns `warning: "stale_source"`; the rendered library row and Overview banner say "A source behind this course changed. Old evidence is kept; the source needs review."; Sources renders the revalidated row as `stale`; the pre-transition `Passed · Cold` attempt and its two evidence rows are unchanged and attempt/evidence row counts are identical before and after (32/63/45). The impact **ids** are empty on a pack-imported course because pack import writes no `gen_plan_sections` citations; the citation-backed impact list and `CHECK_STALE` are proven at the kernel seam in `scripts/proof_contract_v7.py` (§3b). |
| 13 | reimport same pack → resume vs fresh | boundary | `pack.import` modes exercised by `seed-demo-course.py --mode fresh/resume`; not clicked through the UI |
| 14 | course/chat/pack deletion distinct and recoverable | **live@015** | `docs/REVIEW_CB015-delete-paths.json` (all six verdicts true, stills `76`–`81`): archive through the row's own menu hides it from the default list (2→1 rows); the `Archived` filter shows it; `Unarchive course` returns both titles to `All`; `Delete enrollment…` opens a scoped confirm (attempts/notes/runs/jobs + `Course and plan kept` / `Hermes transcripts kept`) and removes the row; `Remove pack…` previews `Evidence kept` and freezes the pack. Driving this exposed a real defect — the delete preview sent no `idempotency_key`, so the confirm could never open — fixed in `desktop/plugin.js`. Chat deletion stays host-owned. |
| 15 | keyboard / text-only / reduced motion / 200 % / narrow | **live@015** | §5 (`docs/REVIEW_CB015-keyboard.json`); both recorded defects (Escape focus return, view-strip name) fixed and re-proved — `docs/REVIEW_CB015-a11y2.json`, §11(1)/(2) |
| 16 | 50+ objectives, long names, long JP/EN, many sources | **live@015** | §4 (`docs/REVIEW_CB015-perf.json`) |
| 17 | teaching moment → tag/search → exact section → new run | **live@015** | §3 (`docs/REVIEW_CB015-loops.json`, steps `notebook-*`, `notebook-section-identity`) |
| 18 | past quiz unchanged → new version → both inspectable | **live@015** | §3; new version refused honestly (`VALIDATION_FAILED`), both attempts remain inspectable (`20`, `21`, `22`, `47`, `48`) |
| 19 | jump early/late → separate runs, later evidence intact | **live@015** | §3 steps `late-run-*`, `early-evidence-intact`, `23`, `24` |

Result: **10 rows live in this worktree (2, 6, 11, 12, 14, 15, 16, 17, 18, 19), 6 partial (1, 3, 5,
7, 8, 9), 2 boundary-only (10, 13), 1 open (4).** Row 7 is counted partial because the split half
was not driven even though the hide/reopen outcome is proven. Row 12 moved to live when its own
`source.revalidate` pass landed; the four rows the packet downgraded were either re-driven here or
re-scoped in §12 with the missing half named. 10 + 6 + 2 + 1 = 19. I did not manufacture the missing
runs to turn this into 19 green rows.

## 8. State matrix (UX_SPEC §13, 26 states)

Same legend; `not driven` means the implementation exists and was reviewed, but this pass did
not exercise it in the live window.

| state | status | note / evidence |
|---|---|---|
| first run | live@015 (pass 1) | real Create/Import actions, zero courses and no fake progress; pass-1 capture not shipped (overlay present) |
| no courses | live@015 (pass 1) | same state, zero rows, no fake progress |
| no search results | **live@015** | quiz filter exclusion: "No attempt matches … Clear filters"; notebook equivalent in CB-009 |
| backend off | **live@015** | fault-injected by stopping the isolated gateway: `Backend off` + enable instructions + `Open Capabilities` / `Check again`, zero rows and no `New course`, and the page's own `Check again` recovers both enrollments once the gateway returns (`REVIEW_CB015-fault-backend-off.json`, §11(5)); the plugin-half-off variant shows the surface staying mounted with a scoped `VALIDATION_FAILED` (`-fault-plugin-off.json`) |
| reconnecting | not driven | stale-read-only branch not exercised |
| unsupported backend | not driven | `implemented` gate reviewed; not fault-injected |
| plan generating | live@other | CB-011 plan job (2m01s, real stages) |
| generation failed | live@other | CB-011 lessons job failed `GRADER_UNAVAILABLE` |
| plan awaiting approval | live@other | CB-011 editable preview + explicit approve |
| lesson ready | **live@015** | section pages across both courses |
| attempt submitting | **live@015** | Submit disabled after submit; `ATTEMPTS ON THIS SECTION` updated once |
| grader unavailable / needs_retry | **live@015** | `Grading failed / Grader unavailable` row in review; full `needs_retry` loop driven — fail closed, `Retry grading` keeps the same nonce, `Move on… → Record override` advances the check and writes `Override — not independent evidence` (`REVIEW_CB015-needs-retry.json`, §11(4)) |
| detached chat | **live@015** | banner, `Reattach`, `Start a fresh run`, Submit disabled with reason (`44`) |
| offline | **live@015** | CDP `Network.emulateNetworkConditions(offline)`: `Offline` badge + one sentence naming what keeps working and what is paused, `New course` absent, a cached course opens, notice clears on reconnect (`REVIEW_CB015-fault-offline.json`, §11(3)) |
| TTS/image unavailable | n/a this pack | both packs declare no audio; lesson shows text and no media control |
| source stale/dead | **live@015** | `source.revalidate` flips the source `stale`; library row + Overview banner name the course and keep old evidence; Sources reads `stale`; impact ids need `gen_plan_sections` citations, proven at the kernel seam (`REVIEW_CB015-row12-rpc.json`, `-ui.json`, §3b) |
| pack invalid | boundary | hostile-pack suite 21/21; native folder grant blocks UI path |
| incompatible pack update | boundary | version gate unit-tested; not UI-driven |
| grant revoked | boundary | staging/grant refusal unit-tested; not UI-driven |
| export awaiting review | live@other (also rendered live in §12) | CB-011 export gate refusal `no_final_approval`; the same blocked screen renders on the live rig after an edit supersedes approval — `Changes need review`, disabled export (`REVIEW_CB015-row9-ui.json`). The exit from this state (reapprove → export) is unproven: §12 row 9 |
| export complete | open | CB-011 never reached final approval/export |
| download failed/cancelled | not driven | saved-on-backend vs local copy not exercised |
| course archived | **live@015** | archive from the row's own menu hides it from the default list (2 → 1 rows), the `Archived` filter shows it, `Unarchive course` restores both (`REVIEW_CB015-delete-paths.json`, §11(6)) |
| course deleted | **live@015** | `Delete enrollment…` renders the scoped confirm (attempts / notebook / lesson runs / jobs, `Course and plan kept`, `Hermes transcripts kept`) and removes the row on confirm (`REVIEW_CB015-delete-paths.json`, §11(6)); chat deletion stays host-owned |
| job interrupted | live@other | CB-011/CB-013 lease + resume evidence |
| demo fixture mode | **live@015** | every row reads "From a local pack · v1.0.0"; perf pack licence `local_only` |

## 9. Defects and limits found this pass

1. **Escape does not return focus to the trigger** (minor a11y). The dialog closes on one
   Escape; `document.activeElement` was `<body>` afterwards. **Fixed in §11(1) and re-proved.**
2. **The view strip is a combobox, not a tablist.** `#cb-view-picker` is a single Tab stop;
   ArrowRight switches views. Keyboard-operable, but its accessible name was only
   "Course view" — the selected view was not in the name. **Fixed in §11(2) and re-proved.**
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
- `docs/REVIEW_CB015-a11y2.json` — Escape focus return + view-picker name, re-proved
- `docs/REVIEW_CB015-fault-offline.json` — emulated offline, rendered state
- `docs/REVIEW_CB015-fault-backend-off.json` — whole gateway stopped and restarted
- `docs/REVIEW_CB015-fault-plugin-off.json` — only the Python half disabled
- `docs/REVIEW_CB015-needs-retry.json` — needs_retry → retry → override, end to end
- `docs/REVIEW_CB015-delete-paths.json` — archive / unarchive / delete / pack freeze
- `docs/REVIEW_CB015-row12-rpc.json` — proof 12 on `cb.rpc` v7: baseline, changed→stale, library warning, retained evidence
- `docs/REVIEW_CB015-row12-ui.json` — proof 12 rendered: library badge, Overview banner, Quizzes attempt, Sources `stale`
- `docs/cb015-shots/row12-01`–`04` — proof 12 stills
- `docs/REVIEW_CB015-gallery.json` — gallery manifest
- `docs/REVIEW_CB015-row3a.json` — cancel generation → reattach → re-queue (§12)
- `docs/REVIEW_CB015-row7.json` — pane hidden mid-attempt, committed verdict read back (§12)
- `docs/REVIEW_CB015-row8.json` — backend cycled at three attempt states (§12)
- `docs/REVIEW_CB015-row9-rpc.json`, `-row9-ui.json`, `-row9-ui2.json` — edit-after-approval gate (§12)
- `docs/cb015-residual/row3-*`, `row7-*`, `row8-*`, `row9-*` — stills for §12
- `docs/cb015-shots/10`–`24`, `40`–`54`, `60`–`81` — stills
- `scripts/cb015-hygiene.mjs`, `cb015-lib.mjs`, `cb015-loops-*.mjs`, `cb015-perf.mjs`,
  `cb015-perf-pack.py`, `cb015-keyboard.mjs`, `cb015-gallery2.mjs`, `cb015-a11y2.mjs`,
  `cb015-fault-offline.mjs`, `cb015-fault-backend-off.mjs`, `cb015-fault-plugin-off.mjs`,
  `cb015-needs-retry.mjs`, `cb015-delete-paths.mjs`, `cb015-delete-verdict.mjs`,
  `cb015-proof12-stale.py`, `cb015-proof12-ui.mjs`

## 11. Re-run after the supervisor unblock (the rows that moved)

Five items were dispatched after the first packet was accepted as a partial. This section says
exactly what changed and what did not.

**(1) Escape now returns focus to the trigger — fixed and re-proved.** `desktop/plugin.js`
gained `useReturnFocus(open)`, used by `NotebookSaveDialog`: it records the element that had
focus when the dialog opened and, one frame after the host's own cleanup, focuses it again if it
is still connected. `docs/REVIEW_CB015-a11y2.json` (`escapeFocusReturn`): dialog opens, one real
Escape closes it, `document.activeElement` is the `Save to notebook` button — not `<body>`
(`61-after-escape-focus.png`).

**(2) The view picker's name carries the selected view — fixed and re-proved.** The narrow-layout
combobox now reads `aria-label="Course view: Textbook"` and, after a real Enter/ArrowDown/Enter
keyboard change, `Course view: Notebook` (`viewPickerName` in the same JSON, `62`/`63`).

**(3) Offline — implemented and fault-injected.** The route had no offline state at all, so the
header now listens to the browser's own `online`/`offline` events (`useOnline()`): an `Offline`
badge plus one sentence naming what keeps working and what is paused, with `New course` and
`New lesson brief` absent while offline. Driven with CDP `Network.emulateNetworkConditions` —
`docs/REVIEW_CB015-fault-offline.json` (all four verdicts true, stills `64`–`66`).

**(4) needs_retry → override — driven end to end.** `docs/REVIEW_CB015-needs-retry.json`: the
open-response check fails closed, Retry grading keeps `needs_retry` (same nonce, no second
attempt), and `Move on… → Record override` produces `Access granted — not independent evidence`
before the section reloads; the durable attempt row and the objective badge keep the override.
Stills `72`–`75`.

**(5) Backend off — driven both ways.** `REVIEW_CB015-fault-backend-off.json` (whole gateway
stopped and restarted: `Backend off`, enable instructions, `Check again`, no fake rows, both
enrollments back) and `REVIEW_CB015-fault-plugin-off.json` (only the Python half disabled: the
surface stays mounted and names a scoped `VALIDATION_FAILED` instead of showing an empty list).
Still `70`, `71`.

**(1b) Driving the deletion path exposed a real defect, now fixed.** `enrollment.delete`'s preview
call — the dry run behind `Delete enrollment…` — sent no `idempotency_key`, so `cb.rpc` refused it
(`VALIDATION_FAILED: 'idempotency_key' is a required property`) and `setPendingDelete` never ran.
The destructive path was **unreachable from the UI**: the row menu opened, the item was clickable,
and nothing happened except a warning toast. `pack.delete`'s preview had always passed
`{expectedRevision, idempotencyKey}`, so the asymmetry was the bug. Both `onDelete` call sites
(course list and course detail) now pass a row-derived key plus the row revision; the detail
surface had also copied the pack's key namespace (`cb-pack-delete-…`) and now uses `cb-delete-…`.
Verified live: the confirm renders the real scope (`55 lesson run(s)`, `Course and plan kept: yes`).

**(6) Deletion paths — driven end to end (proof 14).** `docs/REVIEW_CB015-delete-paths.json`,
six verdicts true, stills `76`–`81`:
archive from the row's own menu hides the course from the default list (2 rows → 1); the
`Archived` filter shows it; `Unarchive course` puts both titles back in `All`; `Delete
enrollment…` shows the scoped counts + kept rows and removes the row on confirm; `Remove pack…`
previews `Evidence kept` and freezes the pack without cascading.

Two harness corrections are recorded rather than hidden: the row menu opens only through the
pointer pipeline (a synthetic `el.click()` leaves it closed — that is what stopped the earlier
pass), and the probe's own `archiveRecoverable` predicate tested the row text for the word
"Unarchive", which is a menu item and never appears in the row. The verdict in the JSON was
recomputed from that run's recorded steps by `scripts/cb015-delete-verdict.mjs`, which writes
`verdictBasis` naming the step each field comes from; no step was re-driven or invented.

**Still not proven — and why (no manufacture):**

- **source stale — impact ids and `CHECK_STALE` on a pack-imported course (proof 12 limit).**
  The v7 `source.revalidate` path is live on the rig (§3b): the source flips to `stale`, the
  library row and Overview banner render, and the old attempt/evidence rows are untouched. What a
  pack-imported course cannot show is the *impact list*: `sources.impact()` reads
  `gen_plan_sections.source_ids_json`, and pack import writes no `gen_plan_sections` rows (those
  are written by the research/generation pipeline). So `objective_ids`/`check_ids` come back empty
  and `CHECK_STALE` cannot fire on this course shape. The citation-backed impact ids and the
  `CHECK_STALE` refusal with zero writes are proven by `scripts/proof_contract_v7.py` on a seeded
  citing section. Follow-up recorded on t_8863beb4 (backend), not faked in the UI.
- **pack UI states (proofs 1/10/13).** `pack.preview` / `pack.import` require
  `pluginContext.files.requestFolder()`, a native folder picker this headless rig cannot drive.
  Proven at the RPC boundary, not through the dialog.
- **chat deletion.** Host-owned transcript action; the plugin does not own or simulate it.
- Rig state after this pass: the JP enrollment is active again; the perf pack is **frozen** by the
  pack-delete step (`pack.delete` = freeze, evidence kept), so it is no longer re-importable —
  future runs must regenerate it with `cb015-perf-pack.py`.

**Gates re-run after these changes (on `fd124b1`):** `node --check desktop/plugin.js` OK,
`node scripts/cb015-hygiene.mjs` **0 findings / 13 rules**, `python3 -m unittest
tests.test_desktop_contracts` **7/7 OK**, full suite **652 tests OK**, and both a11y checks
re-proved after the plugin edit (`REVIEW_CB015-a11y2.json`). That 652 was this branch's count;
the merged master tree is measured in §2 at **674**.

## 12. Residual pass on rows 3, 7, 8, 9 (answers `REVIEW_PACKET.md` §5)

The packet downgraded these four rows from `live@other` after re-reading the artifacts they cited;
this pass either re-drove the decisive half or re-scoped the row with the exact gap. Nothing here
is inferred from the earlier worktrees.

| Row | Driven this pass | Missing half, named |
|---|---|---|
| 3 | `Cancel generation` → job `cancelled`; leave/reopen the course and the cancelled job and its brief are still shown; `Run this stage again` re-queues the job's own brief (`job_40849e53…`, completed, 5 objectives). `docs/REVIEW_CB015-row3a.json`, stills `row3-03..06` | `Edit plan` never rendered for the requeued draft (`scripts/cb015r-row3b.mjs` timed out at 20 s on the Plan view), so no edited-plan approval was recorded |
| 7 | Answer typed in the pane, submitted, right sidebar hidden in the same tick, committed `Not yet` verdict read back after reopening. `docs/REVIEW_CB015-row7.json`, stills `row7-01..03` | **Split** pane during the attempt was not driven (the layout editor exposed no split at this width), and the attempt count/id before and after is **not** in the artifact — the harness regex is double-escaped so `attemptsBlock` is `null`; the `att_8ff275dc…` id quoted in earlier prose is withdrawn |
| 8 | Backend cycled at **awaiting input**, **graded** and **overridden**; each returned the same objective, check version, verdict/override copy and an identical attempts block. `docs/REVIEW_CB015-row8.json`, stills `row8-*` | **submitting** (mid-flight), standalone **needs_retry**, and **detached** were not restarted in this pass |
| 9 | After an active approval, replan + edit supersede it; the Export screen shows `Changes need review`, the blocked sentence and a **disabled** export; the RPC refuses `plan_not_approved`. `docs/REVIEW_CB015-row9-rpc.json`, `docs/REVIEW_CB015-row9-ui.json`, stills `row9-01..03` | Reapproval → export could not run: the replanned plan has no authored document, so `Generate lessons` fails `INTERNAL_ERROR` and no lesson set exists to re-approve (`docs/REVIEW_CB015-row9-ui2.json`) |

**Defect this pass found (backend authoring, for Atlas).** `plan.replan` writes a new `plans` row but
no `gen_plan_documents` row, so the lesson job fails closed with
`plan '<id>' has no authored document` and an authored course can never reach final approval or
export after a replan. The UI is honest about it (the job line shows `Failed (INTERNAL_ERROR)`), but
the authoring loop is incomplete. `parent.plan.edit` on an approved plan is refused `plan_not_draft`
by design ("use plan.replan"), so replan is the only edit path and the gap is on the kernel side.
I did not hand-write a plan document to make row 9 green.

**UI change carried by this branch (row 3).** `desktop/plugin.js` gained a job-line affordance that
did not exist: `Cancel generation` for a queued/running job (`jobs.cancel`), an explicit `cancelled`
sentence, and `Run this stage again` (re-`jobs.create` from the job's stored brief, then re-read the
parent so the line shows the new job id instead of pretending the old one resumed). It is exercised
by `docs/REVIEW_CB015-row3a.json`; nothing else in the plugin changed.

**Rig used.** The writes were made against the disposable `~/.hermes/coursebook-test` home (gateway
44219, window CDP 9337) and, for the cancel/reattach run, the disposable `~/.hermes/cb015-residual`
home (gateway 44225, window CDP 9341). The operator profile was not used.
