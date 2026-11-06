# Coursebook review packet — visual bar, accessibility, performance and the 19-row proof suite

**Task:** `t_110d10a4` (Atlas, integration marshal)
**Tree measured:** `wt/t_110d10a4` at **1b623dd** (master; D1 merge `e3d6770` is an ancestor)
**Wire contract:** `cb.rpc` **v6**, **51** methods
**Date:** 2026-11-06
**Companion task:** release gate `t_de9a872d` (must stay gated until the residuals below close)

---

## 0. Verdict at a glance

| Acceptance criterion | Verdict | Basis |
|---|---|---|
| No raw colours, ad-hoc shadows, card-in-card, primitive overrides | **PASS** | 13-rule hygiene gate 0/13; source counts 0; 11-view live DOM audit clean for plugin-authored chrome |
| No focus theft, keyboard traps, colour-only status | **PASS for measured states; 2 states not proven** | 49 gated captures, 45–576-stop keyboard walks, 0 unnamed / 0 colour-only / 0 small targets; delete-dialog and grader-unavailable states unreachable by the DOM rig |
| Native Hermes feel | **PASS (with scope)** | SDK primitives and tokens only; 0 host-chrome overrides; both installed presentations measured; alternate theme did not exist on the rig |
| Performance for long content and 50+ objectives | **PASS (with printed limits)** | 60-objective / 3,565-word legal fixture: 83 ms worst lesson render, 0 dropped frames; D1 closed |
| Proof suite **19/19 with evidence** | **FAIL — 9/19 fully evidenced** | 6 partial, 2 boundary-only, 2 open; see §5 |
| **Overall release gate** | **FAIL / NOT READY** | The visual bar passes; the proof-suite criterion does not. Release cards stay gated. |

This packet does **not** infer a pass from a branch label. Every row below names the artifact and
states the half of the loop that the artifact does not contain. Where an earlier document called a
row `live@other`, the cited artifact is re-read here and the row is downgraded if the cited run does
not show the user-visible loop.

---

## 1. Evidence inventory

| Artifact | What it proves | Run detail |
|---|---|---|
| `audit/A11Y_UX_AUDIT.md` + `audit/ux/results.json` | 49 route-gated captures, 7 states × 7 presentations, plus 3 lesson frames | CDP 9351, isolated profile `~/.hermes/sentinel-ux-audit`, backend 44231 |
| `audit/ux/attempt-dialog.json`, `audit/ux/dialog-focus.json` | attempt lock within 120 ms; 200 % text on the section; delete-dialog non-reachability | same rig |
| `audit/ux/f01-*.json`, `docs/REVIEW_F01.md` | F-01 contrast before/after; plugin half 0 failures; host token 66 % → 0 failures | own isolated F-01 window |
| `docs/sentinel-perf/PERF-REPORT.md`, `docs/sentinel-perf/results/*` | independent 60-objective and over-cap performance run; D1 defect | own backend 44241, window CDP 9371, 175 Hz |
| `docs/REVIEW_D1-section-cap.md`, `docs/sentinel-perf/results/lesson-readability.json` | D1 closure: over-cap 55/55 and legal 60/60 readable; pre-fix 53/55 | merged as `e3d6770` |
| `docs/REVIEW_CB015.md` + `docs/REVIEW_CB015-*.json` | live fault states, keyboard, perf, gallery, delete paths, loops | isolated home `~/.hermes/cb015-test`, backend 44220, CDP 9338 |
| `docs/REVIEW_CB049.md`, `docs/cb049-shots/audit.json` | visual polish and 11-view DOM audit | isolated window CDP 9341, real backend |
| `docs/assets/` (9 files), `docs/README-SHOTS.md`, `docs/README-SHOTS-STATUS.md` | README/demo image set with provenance | README rig CDP 9382; two frames reuse CB-009/CB-015 evidence |
| `docs/REVIEW_CB009-pane-chat.json`, `docs/REVIEW_CB011.md`, `docs/REVIEW_CB013-run52.md` | sibling-worktree evidence for pane, Parent Studio and restart rows | cited per row, with the gap named |

Reproduction of the gates in this packet:

```console
$ cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_110d10a4
$ python3 -m unittest discover -s tests -t .     → Ran 664 tests ... OK
$ node --check desktop/plugin.js                 → OK
$ node scripts/cb015-hygiene.mjs                 → TOTAL 0 (13 rules, 7908 lines)
```

---

## 2. Screenshot gallery (README/demo set)

Nine committed frames. Dimensions and hashes are of the files in this tree; provenance names the
merged evidence set the frame came from, so a reviewer can replay it.

| # | File | Use | Bytes | SHA-256 (16) | Provenance |
|---|---|---|---:|---|---|
| 1 | `docs/assets/readme-overview-dark.png` | landing / course overview, dark | 56,243 | `1a5601a1df7b12dd` | `docs/cb049-shots/030-overview-dark.png` |
| 2 | `docs/assets/readme-overview-light.png` | landing / course overview, light | 53,982 | `55e864a32e643085` | `docs/cb049-shots/040-overview-light.png` |
| 3 | `docs/assets/readme-library-dark.png` | library and imported pack | 60,078 | `7cc761124f925616` | `docs/cb049-shots/036-library-dark.png` |
| 4 | `docs/assets/readme-textbook-dark.png` | textbook surface | 64,083 | `570da18e90d852c7` | `docs/cb049-shots/031-textbook-dark.png` |
| 5 | `docs/assets/readme-notebook-dark.png` | notebook surface | 66,648 | `0de7217e8998279f` | `docs/cb049-shots/033-notebook-dark.png` |
| 6 | `docs/assets/readme-parent-studio-dark.png` | Parent Studio | 51,204 | `e00bba36b348d483` | `docs/cb049-shots/037-studio-dark.png` |
| 7 | `docs/assets/readme-lesson-pane-dark.png` | lesson pane beside a bound chat | 127,122 | `2922ccbe3c5e466a` | `docs/cb009-shots/pane-02-bound-chat-pane.png` |
| 8 | `docs/assets/readme-quiz-in-progress.png` | quiz in progress, answer typed | 76,199 | `f494a8da15eb311b` | `docs/cb-loops-shots/21-quiz-answer-typed.png` |
| 9 | `docs/assets/readme-quiz-results.png` | quiz results and attempt history | 82,468 | `4aeaecb618960a20` | `docs/cb-loops-shots/23-quiz-graded.png` |

Frames 1–6 are direct README-rig captures from the CB-049 polish build. Frames 7–9 deliberately
reuse merged CB-009/CB-015 live captures: in the README seed the section's chat binding arrives
detached, `Reattach` returns to the course list, and `Start a fresh run` leaves the route, so a clean
in-progress lesson/quiz frame cannot be produced from that seed without deciding a product question.
This is recorded in `docs/README-SHOTS-STATUS.md` as a **rig limitation, not a product defect**.

Supporting galleries (not duplicated here):

- `docs/cb049-shots/` — 39 dark/light/narrow/200 %/first-run/pane stills + `audit.json`
- `docs/cb015-shots/` — 40 live loop, fault-state, delete-path and perf stills
- `docs/cb-loops-shots/` — 18 notebook/textbook/quiz stills
- `docs/a11y-shots/` — 52 gated frames (49 variant captures + 3 lesson-section frames)

---

## 3. Consolidated a11y / UX report

Source: `audit/A11Y_UX_AUDIT.md` (Sentinel, audit only; no product code changed), measured on base
`b476738`, then re-measured for F-01 on the fixed plugin and host token.

### 3.1 Scope — the card's "23" vs the spec's 26

`UX_SPEC.md` §13 is the only state enumeration in the repository and it contains **26 states**. The
task's "23-state audit" matches no enumeration; the audit used all 26 and marked each row
individually. Consolidated coverage:

| Group | Count | States |
|---|---:|---|
| Captured with the full 7-variant matrix | 8 | first run, no courses, no search results, backend off, unsupported backend, lesson ready, demo fixture mode; plus attempt-submitting and 200 %-section driven outside the matrix |
| Captured partial | 1 | detached chat (banner/recovery visible inside lesson-ready, not isolated) |
| Attempted, blocked by rig topology | 2 | grader unavailable / needs_retry; course-delete dialog |
| Not attempted | 15 | reconnecting, plan generating, generation failed, plan awaiting approval, offline (in this audit pass), TTS/image unavailable, source stale/dead, pack invalid, incompatible pack update, grant revoked, export awaiting review, export complete, download failed/cancelled, course archived, job interrupted |

**Coverage claim:** 9 of 26 states have live evidence in this audit; 15 are unproven, 2 are blocked.
No uncaptured state is claimed to pass.

### 3.2 What measured clean (49/49 captures)

- **0 clipped text nodes** and **0 horizontal overflow** at 1281 px, 460 px, split 639 px and hidden-pane 1045 px.
- **0 unnamed controls**, **0 colour-only status chips**, **0 targets under 20×20 px**.
- **45-stop tab walk**: no trap. Route stops all named.
- **Attempt lock**: `Submit answer` disabled within **120 ms**; duplicate click recorded nothing.
- **200 % text on the lesson section**: root 32 px, body 26 px, 0 clipped, 0 overflow.
- **Reduced motion** (CB-015 harness): max computed transition/animation **0.00001 s**.
- **Submit via Enter** after a real keyboard walk (CB-015, 576 stops; 62 visible controls, 0 unnamed).
- **Escape focus return** in the notebook dialog: `document.activeElement` is the `Save to notebook`
  trigger after close (`docs/REVIEW_CB015-a11y2.json`, `61-after-escape-focus.png`).
- **View picker name** carries the selected view: `Course view: Textbook` → `Course view: Notebook`
  after a real keyboard change.

### 3.3 F-01 — the one release-relevant defect, now closed with a host dependency

| Stage | Evidence | Result |
|---|---|---|
| Original audit | `audit/ux/results.json` | Light theme: **184 nodes / 52 strings** at 3.47–3.53:1 vs 4.5 AA. Foreground is the 54 % tertiary token; every captured light state affected. |
| Plugin half fixed | `audit/ux/f01-light-after.json`, `docs/REVIEW_F01.md` | 88 `text-(--ui-text-tertiary)` call sites moved to the secondary token; **0 plugin-authored failing nodes**; 86 residual nodes are host SDK primitives (`Badge`, `SegmentedControl`, `Button text`, `ListRow` caption, `EmptyState`). |
| Host half fixed | `audit/ux/f01-host66.json` | Light-only `--ui-text-tertiary` raised 54 % → **66 %** in the host fork (`apps/desktop/src/styles.css`, `:root:not(.dark)`); **0 failures across the seven states**. Dark stays 54 %, `f01-dark-after.json` 0 failures. |
| Negative control | `audit/ux/f01-light-token61.json` | 61 % still fails with the same 86 nodes; the fix is the measured token change, not a measurement artefact. |

**Release condition:** the host change lives in `~/Projects/hermes-fork/apps/desktop/src/styles.css`
and the rebuilt host, not in this plugin repository. The shipped Desktop build must carry it; a
plugin-only install into a 54 % host still fails AA. This is an integration dependency, not an open
plugin defect.

### 3.4 Unproven a11y states (do not read as pass)

| State | Why unproven | Evidence of the block |
|---|---|---|
| `grader unavailable / needs_retry` | the audit window's primary gateway is 44219; the 44232 fault proxy received **zero** traffic, so the injected fault never reached the window | `audit/ux/rpc-log.jsonl`, §7.3 |
| `course deleted` dialog focus/Escape | the row `Actions for …` control opens no DOM menu; `[role=menuitem]` and `[role=menu] button` are empty after a synthetic click; the dialog was never opened (no course deleted) | `audit/ux/dialog-focus.json`, §7.4 |
| Alternate colour theme | no second theme existed on the rig; `forced-colors` is the third presentation and passes | §5 |
| Network offline in this audit pass | not induced here; CB-015 drove it separately (`docs/REVIEW_CB015-fault-offline.json`, four verdicts true) | §4 row 14 |

P3 observations retained, not blockers: host-owned 200 ms input transitions, 9.6 px tag captions,
host sidebar truncation at 200 %, and host tile-memory blank frames (each needs a host change, not a
plugin change).

---

## 4. Performance report — long content and 50+ objectives

Source: `docs/sentinel-perf/PERF-REPORT.md` (independent rig, no product code changed) and
`docs/REVIEW_CB015-perf.json` (55-objective run). The perf run measured candidate `b476738`; D1 was
found in that run and fixed later at `e3d6770`. The fix touches import/repair only; the perf numbers
were **not re-run on the fixed tree** (Supervisor instruction), and this packet does not pretend
otherwise.

### 4.1 Measurement limits (printed, not hidden)

175 Hz display (idle rAF cadence 5.7 ms), `--disable-gpu`, synthetic but real-contract fixtures,
single window, one machine. A dropped frame is > 2 × idle cadence (11.4 ms) because the display is
175 Hz. Long tasks are `PerformanceObserver` > 50 ms.

### 4.2 Legal maximum-content fixture — 60 objectives, 3,565-word lessons

| Metric | Baseline (3 objectives) | Long (60 objectives) |
|---|---:|---:|
| Cold mount: first contentful paint | 1,172 ms | 1,220 ms |
| Cold mount: route + course rows | 1,904 ms | 1,981 ms |
| Course detail render | 12 ms | 13 ms |
| Textbook index | 3 rows / 65 nodes | **60 rows / 578 nodes** |
| Long lesson full render | 28 ms | **83 ms** (22,098 chars, 371 nodes) |
| Last objective render | 216 ms | 162 ms |
| Rapid pane switch p95 / worst | 11 / 11 ms | **14 / 15 ms**, 0/315 frames > 32 ms |
| Long-lesson scroll worst frame | 6 ms | **6 ms** |
| 200 % text: overflow / clipped | 0 px / 0 | **0 px / 0** |
| 460 px: horizontal overflow | 0 px | **0 px** |
| Long tasks opening the largest lesson | — | **1 × 69 ms** (honest note; all other steps 0) |
| Leak test (10 × open lesson, forced GC) | — | **−0.03 MB total**, flat |

55-objective run (`docs/REVIEW_CB015-perf.json`): Textbook index **157 ms / 533 nodes**, Plan view
**12 ms**, 55th CJK section **161 ms**, index scroll worst frame **6 ms / 0 frames > 32 ms**, 200 %
and 460 px **0 overflow / 0 clipped**.

**Verdict: PASS with limits.** Course size does not move cold mount; the largest legal lesson costs
one 69 ms long task and 83 ms render. That is usable, and it is the number a reviewer should quote.

### 4.3 D1 — a real P1 found by this run, closed at `e3d6770`

A section file over 8,000 characters imported successfully and then its lesson was permanently
unreadable: `lesson.page` returned `INTERNAL_ERROR` at `segments/0/text`, `retryable: false`,
because `pack_flow._write_lesson_page` stored a whole section as one `lesson_segments.text` value
while `cb.rpc` v6 caps `segments[].text` at 8,000.

| Check | Pre-fix | Fixed (`e3d6770`) |
|---|---|---|
| over-cap 55-objective fixture | 53/55 readable, 2 × `INTERNAL_ERROR` (ordinals 1, 55) | **55/55 readable**, max segment 7,939 |
| legal 60-objective fixture | 60/60 | 60/60, max segment 7,789 |
| over-cap course imported by the pre-fix build, then served by the fix (same DB, no re-import) | 53/55 | **55/55 readable**, repaired in place, 7 pieces per long section |
| boundary tests 7,999 / 8,001 chars; 500-segment refusal; marker-once | — | `tests/test_segment_cap.py`, 12 new tests |

The 8,000/500 caps are unchanged and read from the contract. `desktop/plugin.js` untouched.

**Architecture review of the D1 seam (Supervisor's flag):** the repair is content-preserving
(`"".join(pieces) == source`), order-preserving, fenced in `BEGIN IMMEDIATE`, idempotent, and skips
on lock contention without failing the command. `PRAGMA user_version = 1` is a data-repair marker,
not a schema version (`schema_migrations` remains the schema authority). **Accepted for the gate**
with one documentation condition: `ARCHITECTURE.md` must name the marker and the one-time
`lesson_segments` rewrite, because it is the first lifecycle path that mutates learner content and
must not be discovered later as an undocumented exception to CB-014-R1. Tracked as `t_9444d202`
(Harbor); it is not a behaviour blocker.

---

## 5. UX_SPEC §16 proof matrix — 19 rows

Status vocabulary used here (stricter than `REVIEW_CB015.md` §7):

- **FULL** — the user-visible loop was driven in a live Desktop window and the artifact shows the
  decisive step(s).
- **PARTIAL** — the artifact proves a subset (backend/seam or one half of the loop); the row's
  decisive user action is absent.
- **BOUNDARY** — only an RPC/unit/adversarial-seam result exists; no UI path was driven.
- **OPEN** — no executable evidence.

| # | Proof (UX_SPEC §16) | Status | Evidence in this tree | What is missing / why it is not FULL |
|---|---|---|---|---|
| 1 | fresh profile → sidebar → bundled preview → import → lesson | **PARTIAL** | `docs/README-SHOTS-STATUS.md`: disposable install, real `pack.grant/preview/import`, course + lesson mounted; `docs/assets/readme-overview-dark.png` | The import **dialog** needs the native folder picker; the UI grant/preview/import path was not driven. Owned by `t_36679b90`. |
| 2 | backend disabled → enable → brief kept | **FULL** | `docs/REVIEW_CB015-fault-backend-off.json` (`offStateNamed`, `enableInstructionsInText`, `recoveryActionPresent`, `noFakeContentWhileDown`, `dataKeptAcrossCycle`, `recoveredByItsOwnAction` all true); `70`, `71` | — |
| 3 | new goal → cancel generation → reattach → approve edited plan | **PARTIAL** | `docs/REVIEW_CB011.md`: plan job completed, `parent.plan.edit` live, `plan.approve` live, `docs/cb011-shots/04-studio-plan.png` | **Cancel generation and reattach were not driven.** `jobs.cancel` is kernel-only (`docs/REVIEW_CB011-EXECUTOR.md`); the UI cancel/reattach half is absent. `REVIEW_CB015.md` labels this `live@other`; that label overstates the artifact. |
| 4 | chat answer and pane answer race → one attempt/transition | **OPEN** | none | No run drives two submissions for one open check. Owned by `t_36679b90`. |
| 5 | wrong answer → alternate representation → clarification not a retry | **PARTIAL** | `docs/REVIEW_CB015-loops.json`: wrong answer graded `Not yet / Hinted`; `docs/REVIEW_CB015.md` §3 | The **hint-is-not-a-retry accounting** is CB-009/CB-013 evidence, not this worktree; no attempt-count delta is recorded here. Owned by `t_36679b90`. |
| 6 | grader timeout → needs_retry → explicit override | **FULL** | `docs/REVIEW_CB015-needs-retry.json` (`honestNeedsRetryCopy`, `retryDidNotAdvance`, `overrideRecorded`, `dialogExplainedFence`, `dialogClosed`, `immediatePanelSeen` all true); `72`–`75` | — |
| 7 | hide/reopen/split pane during attempt → no lost/duplicate submit | **PARTIAL** | `docs/REVIEW_CB009-pane-chat.json` (pane typed, verdict returned, narrow and 200 % variants); `docs/cb009-shots/pane-*.png` | The artifact does **not** hide/reopen/split the pane *during* an attempt, nor assert a duplicate-submit count. CB-009 proves the pane works, not this loop's decisive action. |
| 8 | restart at every attempt state → same visible objective/pending | **PARTIAL** | `docs/REVIEW_CB013-run52.md` §Restart-resume: isolated backend cycled, same enrollment/revision/attempt rows served | One post-attempt state, and only the backend was cycled. "At **every** attempt state" was not exercised; `docs/ACCEPTANCE.md` row 8 still says pending beyond the open-check state. |
| 9 | parent edit after approval → reapproval required before export | **PARTIAL** | `docs/REVIEW_CB011.md`: approved plans refuse direct edit, `parent.export` blocked with `no_final_approval`; two clearly labelled gates in `04-studio-plan.png` | The document itself says "Editing after approval blocks export until reapproval — **wired; needs a complete lesson set to demonstrate**". The reapproval half was never shown. |
| 10 | invalid/malicious pack → precise error, no residue, no network render | **BOUNDARY** | `tests/adversarial/evidence/attack-packs.json`: 21/21 hostile packs rejected, zero residue; P01–P16 in `docs/ACCEPTANCE.md` | No rendered refusal was driven; the UI folder grant needs the native picker. Owned by `t_36679b90`. |
| 11 | offline lesson → cached content; research explains pause | **FULL** | `docs/REVIEW_CB015-fault-offline.json` (`offlineSpaceNamed`, `createActionsAbsentOffline`, `cachedContentRendered`, `noticeClearedOnline` all true); `64`–`66` | — |
| 12 | source stale → impact banner; old evidence retained | **OPEN** | `docs/REVIEW_CB015.md` §7/§11: the only writer is `sources.apply_run` from `generation.py:1862`; **0 of 51** contract methods mutate a source | Unreachable through the contract without a hand-written DB row. Owned by `t_8863beb4` (decide the contract surface). |
| 13 | reimport same pack → resume vs fresh | **BOUNDARY** | `pack.import` modes exercised by `scripts/seed-demo-course.py --mode fresh/resume`; `docs/ACCEPTANCE.md` P20 `resumed_same=True`, `fresh_new=True` | Not clicked through the UI. Owned by `t_36679b90`. |
| 14 | course/chat/pack deletion distinct and recoverable | **FULL** | `docs/REVIEW_CB015-delete-paths.json` (six verdicts true, `verdictBasis` names the step behind each field); `76`–`81` | Chat deletion is host-owned and was not probed; the row's course/pack halves are live. |
| 15 | keyboard-only, text-only, reduced motion, 200 %, narrow | **FULL for plugin surfaces** | `docs/REVIEW_CB015-keyboard.json` (576 stops, 62 controls, 0 unnamed, reduced motion 0.00001 s); `docs/REVIEW_CB015-a11y2.json` (Escape focus return, view-picker name); `audit/A11Y_UX_AUDIT.md` (45-stop, no trap, 49 captures) | Delete-dialog focus/Escape and the grader-unavailable state remain unproven; host tab-order cost (~500 host stops) is host-owned. |
| 16 | 50+ objectives / long JP-EN / many sources stay usable | **FULL** | `docs/sentinel-perf/PERF-REPORT.md` (60 objectives, 3,565-word lessons); `docs/REVIEW_CB015-perf.json` (55 objectives) | — (D1 fixed; perf not re-run after the fix, stated above) |
| 17 | save teaching moment → tag/search → exact section → new run | **FULL** | `docs/REVIEW_CB015-loops.json` steps `notebook-*`, `notebook-section-identity`; `45`, `46`, `14`–`19` | — |
| 18 | past quiz unchanged → new version → both inspectable | **FULL** | `docs/REVIEW_CB015-loops.json` steps `quizzes-list`, `quiz-review`, `quiz-new-version`; `47`, `48`, `20`–`22`; `docs/cb-loops-quiz.json` (26 → 27 rows, reload-persistent) | New version was honestly refused (`VALIDATION_FAILED: no unused, audited variant`); both attempts remained inspectable. That is the product's correct no-op, not a missing run. |
| 19 | jump early/late → separate runs, later evidence intact | **FULL** | `docs/REVIEW_CB015-loops.json` steps `late-section-detached`, `late-run-armed`, `early-section-after-late-run`; `23`, `24` | — |

### 5.1 Tally

| Status | Count | Rows |
|---|---:|---|
| FULL | **9** | 2, 6, 11, 14, 15, 16, 17, 18, 19 |
| PARTIAL | **6** | 1, 3, 5, 7, 8, 9 |
| BOUNDARY | **2** | 10, 13 |
| OPEN | **2** | 4, 12 |

### 5.2 Rejections — items that may not be claimed as passing

The six rows the Supervisor already named as open by design (1, 4, 5, 10, 12, 13) are confirmed
below. This packet additionally rejects **rows 3, 7, 8 and 9**: `REVIEW_CB015.md` labels them
`live@other`, but the cited artifacts do not contain the user-visible half of each loop. The exact
gaps are in the table above (cancel/reattach; hide/split during an attempt; every attempt state;
edit-after-approval reapproval). A branch citation is not a substitute for the decisive step.

Rejected as evidence of a passed row:

1. **Row 1** — import driven by RPC, not the UI dialog.
2. **Row 3** — plan edit/approve driven; cancel and reattach absent.
3. **Row 4** — no run at all.
4. **Row 5** — wrong answer driven; retry accounting not measured in this worktree.
5. **Row 7** — pane works; hide/reopen/split mid-attempt not driven.
6. **Row 8** — one backend cycle, not every attempt state.
7. **Row 9** — export gate refusal present; reapproval after an approved-plan edit not demonstrated.
8. **Row 10** — adversarial seam only; no rendered refusal.
9. **Row 12** — unreachable through cb.rpc.
10. **Row 13** — import modes at the script seam; no UI click-through.

No row was promoted by inference. No missing run was manufactured.

---

## 6. Visual-bar verification (mechanical, not adjectives)

| Check | Command / artifact | Result |
|---|---|---|
| Design-system hygiene | `node scripts/cb015-hygiene.mjs` | **0 findings / 13 rules** (7908-line plugin) |
| Raw colour literals in plugin | `grep -cE '#[0-9a-fA-F]{3,8}\\b|rgba?\\(|hsla?\\(' desktop/plugin.js` | **0** |
| Ad-hoc shadows | `grep -c shadow desktop/plugin.js` | **0** |
| Inline style objects | `grep -c 'style: {' desktop/plugin.js` | **0** |
| 2 px width overrides (`border-l-2`/`border-s-2`/`border-e-2`) | grep | **0** |
| Tertiary token off the approved scale | `grep -c ui-text-tertiary desktop/plugin.js` | **0** (F-01 move) |
| Host chrome utility in plugin | `grep -c text-muted-foreground desktop/plugin.js` | **0** |
| Live 11-view DOM audit | `docs/cb049-shots/audit.json` | `markdownResidue` **0** in all 11 views; 4 `nested` hits and 4 `heavy` hits inspected below |
| Parse | `node --check desktop/plugin.js` | **OK** |

**The 4 `nested` hits** (`notebook-dark` only) are a host-rendered `aui-md-table` inside a notebook
list row that carries a bottom hairline, plus a table cell inside that table. They are content
tables painted by `MessageTextContent`, not plugin-authored cards, and the detector's "bordered
child inside bordered parent" rule cannot distinguish content chrome from a card. **The 4 `heavy`
hits** (`section-dark`, `section-light`) are the host Markdown blockquote's `border-s-2` — the
plugin source contains **0** width overrides. Recorded as detector false positives, not as "0 nested
borders" in the raw JSON.

**Native feel:** the plugin imports SDK primitives (Button, PanelSectionLabel, EmptyState, Markdown
renderer) and uses host tokens for colour, elevation and spacing; the route publishes
`data-cb-route`/`data-cb-destination`; both installed presentations (dark, light) were measured.
Scope note: no alternate colour theme existed on the rig, so `forced-colors` is the third
presentation, and "theme parity" beyond dark/light/forced is unproven.

---

## 7. Release blockers and next actions

| Blocker | Owner | Card | Gate effect |
|---|---|---|---|
| Proof rows 1, 4, 5, 10, 13 | Vellum | `t_36679b90` | release cards stay gated |
| Proof row 12 (stale-source contract surface) | Cinder | `t_8863beb4` | release cards stay gated |
| Proof rows 3, 7, 8, 9 must either be re-driven or the matrix must be formally re-scoped | Vellum | `t_7fffb4e9` (linked as a parent of `t_de9a872d`) | do not mark 19/19 |
| Host light tertiary 66 % must ship in the Desktop build | Host design-system owner | applied in `~/Projects/hermes-fork`; build/pack provenance to be confirmed at release | light theme AA depends on it |
| `ARCHITECTURE.md` must document the D1 repair marker and `lesson_segments` rewrite | Harbor | `t_9444d202` | documentation condition, not a behaviour blocker |

**Overall verdict: FAIL — release not ready.** The visual bar, the measured accessibility surface
and the performance envelope pass on the evidence above. The acceptance criterion that the proof
suite is 19/19 with evidence is not met: 9 rows are fully evidenced, 6 are partial, 2 are
boundary-only and 2 are open. Ten rows are rejected above. `t_de9a872d` must not complete while any
of these is unresolved.

---

## 8. Reproduce this packet

```console
$ cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_110d10a4
$ git rev-parse --short HEAD                 # 1b623dd
$ python3 -m unittest discover -s tests -t . # Ran 664 tests ... OK
$ node --check desktop/plugin.js             # OK
$ node scripts/cb015-hygiene.mjs             # TOTAL 0
$ jq -c '{audits:(.audits|length),residue:([.audits[].markdownResidue[]]|length)}' \
      docs/cb049-shots/audit.json            # {"audits":11,"residue":0}
$ jq -c '.verdict' docs/REVIEW_CB015-fault-offline.json \
      docs/REVIEW_CB015-needs-retry.json \
      docs/REVIEW_CB015-fault-backend-off.json \
      docs/REVIEW_CB015-delete-paths.json
$ jq -c '.totalFailures' audit/ux/f01-host66.json   # 0
$ cat docs/sentinel-perf/results/lesson-readability.json
```
