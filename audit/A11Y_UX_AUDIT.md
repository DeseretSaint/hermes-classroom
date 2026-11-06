# A11Y / UX state audit — Coursebook Desktop

**Auditor:** Sentinel (adversarial QA, audit only — no product code changed)
**Candidate:** `wt/t_7145b91e`, base `b476738` (merge of CB-049), `desktop/plugin.js` @ `69a87b5`
**Date of measured run:** 2026-11-06, 19:23–19:27 UTC
**Evidence root:** `audit/ux/`, screenshots `docs/a11y-shots/`
**Verdict:** **CONDITIONAL FAIL** — 1 reproducible AA contrast defect in the light theme across all seven captured states; 18 of 26 documented states not captured; keyboard Escape/focus-return unproven. No P0/P1 layout, clipping or keyboard-trap defect was found in the states that were measured.

---

## 1. What was measured, and on which window

Nothing below is inferred from source. Every number comes from a live renderer measured over CDP on a pinned port.

| Item | Value | How it was verified |
|---|---|---|
| CDP port | **9351** (pinned; never the default `9351` fallback of a different worker) | `GET /json/version` → `Chrome/152.0.7977.167`, `Electron/44.9.3`; page target `AE7750420D224ED28B98B4975EE23DCE`, url `http://127.0.0.1:5174/#/coursebook` |
| Plugin root | `/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_7145b91e` | `audit/ux/runtime.json` (`plugin_root`) |
| Wire contract | `cb.rpc` **v6**, **51** methods, `contract_problems: []` | `audit/ux/runtime.json` |
| Backend | isolated audit backend on **44231** (`hermes`, pid pinned at run time) | `ss -ltnp`; `audit/ux/rpc-log.jsonl` shows served calls |
| Fault/provenance proxy | **44232** (`node scripts/audit-ux-proxy.mjs`) → 44231; injects from `audit/ux/fault.json`; logs every call | proxy source + `rpc-log.jsonl` (505 entries at attempt 1; appended by this run) |
| Audit profile | `~/.hermes/sentinel-ux-audit` (`db_path` in `runtime.json`) — not the operator's real courses | `runtime.json` |
| Text scaling | `document.documentElement.style.fontSize = 32px` (root 16px → 32px); measured body text 13px → **26px**, h2 14px → **28px** | live probe: `html=32px`, `p fs=26px`, `h2 fs=28px` |
| Viewport | 1281×901 CSS px (device metrics scaled by host zoom); narrow 460×901; split 639px route; hidden 1045px route | `results.json` per variant |

Capture gate: each snapshot is refused unless `[data-cb-route]` is present, its text is non-empty, **no host overlay** (`CONNECTING` / `Hermes couldn't start`) is in `document.body.innerText`, and the PNG is larger than 12 KB. This gate is the fix for the evidence defect in §2; all 49 captures in `docs/a11y-shots/` passed it.

Measurement definitions (`scripts/audit-ux-lib.mjs`): contrast is WCAG 2.1 relative luminance on the element's own composited foreground over the nearest opaque background (4.5:1 normal, 3:1 large); clipping is text whose own box overflows (`scrollWidth/Height` beyond client) or is cut by an ancestor with `overflow: hidden/clip`, or text off the horizontal viewport; `colorOnly` is an icon-only control with no accessible name and a status chip with no words; `smallTargets` is a control <20×20 CSS px.

## 2. Evidence-integrity defect found in attempt 1 (audit tooling, not product)

Attempt 1 (run 93) left 54 PNGs in `docs/a11y-shots/`. I inspected every one before reusing them: **all 54 were invalid** — host chrome frames, not the Coursebook route. 52 were the host `CONNECTING` / `Hermes couldn't start` overlay on an otherwise empty background (`lesson-ready-light.png` is literally the single word `CONNECTING`), and `attempt-section-narrow.png` was a 19×36 px capture. DOM metrics in the old `results.json` were internally consistent with a live route, so the numbers were usable, but **any claim illustrated by those images would have been false**. Originals are preserved at `audit/ux/shots-attempt1/`; the report above uses only the re-captured set.

Severity **P2 process**: a rig whose screenshot path is not gated on route/overlay state can silently publish photobombed evidence. Fixed here with `scripts/audit-ux-recapture.mjs` (route + overlay + size gate, 10 s screenshot timeout). The Supervisor's warning about CDP 9351 being taken over mid-run matches this exactly.

## 3. Scope: 23 vs 26 states

The card says "23 documented UX states". The only enumeration in the repo is `UX_SPEC.md` §13, **26 states** (also quoted as 26 in `docs/REVIEW_CB015.md` §8). I audited against all 26 rather than guess which three the card dropped; rows are individually marked captured/not captured below, so the "23" can be derived by whoever owns that number.

## 4. Per-state matrix (UX_SPEC §13)

Legend: **PASS** = all measured a11y/layout checks clean in the captured variants; **FAIL(n)** = n contrast nodes below AA; **not captured** = no live evidence in this pass (reason given).

| # | State | Status | Evidence |
|---|---|---|---|
| 1 | first run | PASS (welcome half) | `no-courses` scenario: zero rows, real `Create a course` / `Import a pack`, no fake progress; `no-courses-*.png` |
| 2 | no courses | PASS | same capture, `no-courses-*.png`, route text has no course rows |
| 3 | no search results | PASS | `zzzz-no-such-course` typed into the route search; `No courses match` + `Clear search`; `no-search-results-*.png` |
| 4 | backend off | PASS | proxy `{down:true}` → `Backend off` / `Coursebook needs its agent plugin` / `Open Capabilities` / `Check again`, zero rows, no `New course`; `backend-off-*.png` |
| 5 | reconnecting | **not captured** | needs a stale-read-only transition (backend up, then dropped mid-read); not induced this pass |
| 6 | unsupported backend | PASS | two branches captured: `unsupported-backend` (runtime v1, 3 methods) and `degraded-db` (`db.ready=false`); scoped copy, no course actions; `*-{dark..hidden}.png` |
| 7 | plan generating | **not captured** | needs a live Parent Studio generation job; not re-run this pass (CB-011 evidence only) |
| 8 | generation failed | **not captured** | same; CB-011 recorded `GRADER_UNAVAILABLE` failure but not the UI state in this window |
| 9 | plan awaiting approval | **not captured** | CB-011 evidence only |
| 10 | lesson ready | PASS (with detached-chat banner present) | `lesson-ready-*.png`; objective + `Resume lesson` / `Open this section` |
| 11 | attempt submitting | PASS | Submit disabled within 120 ms; duplicate click ignored while disabled; §7.1 |
| 12 | grader unavailable / needs_retry | **blocked** | fault proxy receives no traffic from this window (primary is 44219); §7.3 |
| 13 | detached chat | PARTIAL | banner, `Reattach` / `Start a fresh run`, Submit disabled with reason are visible in `lesson-ready-*`; not isolated into its own matrix because the JP course was already detached |
| 14 | offline | **not captured** | needs `Network.emulateNetworkConditions(offline)` |
| 15 | TTS/image unavailable | **not captured** (n/a for this pack) | both shipped packs declare no audio/media; no media control rendered, so the state cannot be exercised without a media-bearing pack |
| 16 | source stale/dead | **not captured** | unreachable through the 51 contract methods (documented limit in `REVIEW_CB015.md` §11) |
| 17 | pack invalid | **not captured** (boundary only) | hostile-pack suite 21/21 in CB-014; folder-grant dialog blocks the UI path |
| 18 | incompatible pack update | **not captured** (boundary only) | version gate unit-tested, not UI-driven |
| 19 | grant revoked | **not captured** (boundary only) | staging/grant refusal unit-tested, not UI-driven |
| 20 | export awaiting review | **not captured** | needs Parent Studio final-approval gate |
| 21 | export complete | **not captured** | CB-011 never reached final approval/export |
| 22 | download failed/cancelled | **not captured** | not exercised |
| 23 | course archived | **not captured** | Archived filter rendered; no archived enrollment created this pass |
| 24 | course deleted | **blocked** | row `Actions for …` opens no DOM menu, so the confirm cannot be reached by DOM click; §7.4 |
| 25 | job interrupted | **not captured** | CB-011/CB-013 lease-resume evidence only |
| 26 | demo fixture mode | PASS | every row reads `From a local pack · v1.0.0`; no simulated live research; `demo-fixture-mode-*.png` |

Captured with full 7-variant matrices: **7 scenarios covering 8 spec rows** (first run + no courses are the same zero-row screen; unsupported backend covered twice). Two more rows were driven outside the matrix (**11 attempt submitting — PASS**, **13 detached chat — PARTIAL**). Two rows were attempted and are **blocked by rig topology** (**12 grader unavailable**, **24 course deleted**). **15 rows were not attempted**, each for the stated reason.

## 5. Variant matrix for captured states

Columns are the presentations the card asked for. `forced` is Chromium `forced-colors: active` (the third presentation available — see §6 on "alternate theme").

| state | dark | light | forced | narrow 460 | split 639 | hidden pane | 200% text |
|---|---|---|---|---|---|---|---|
| lesson ready | PASS | **FAIL(40)** | PASS | PASS | PASS | PASS | PASS |
| first run / no courses | PASS | **FAIL(15)** | PASS | PASS | PASS | PASS | PASS |
| no search results | PASS | **FAIL(7)** | PASS | PASS | PASS | PASS | PASS |
| backend off | PASS | **FAIL(15)** | PASS | PASS | PASS | PASS | PASS |
| degraded DB (unsupported) | PASS | **FAIL(33)** | PASS | PASS | PASS | PASS | PASS |
| unsupported backend | PASS | **FAIL(34)** | PASS | PASS | PASS | PASS | PASS |
| demo fixture mode | PASS | **FAIL(40)** | PASS | PASS | PASS | PASS | PASS |

Totals across all 49 captures: `overflowX = 0` everywhere; **0 clipped text nodes**; **0 unnamed controls**; **0 colour-only status**; **0 controls under 20×20 px**; route width 461 at 460 px viewport (1 px, no horizontal scroll), 639 in split, 1045 in full/hidden.

Keyboard (measured separately per state, `results.json → keyboard`): 45 real Tab presses, **no trap** (`trap: null`); route stops are all named, e.g. `lesson-ready`: `New course, Courses, Library, Parent Studio, All courses, Resume lesson, Course view, Resume lesson, Open this section`. The Escape probe is **vacuous**: focus was outside the route before and after in every scenario, so "Escape closes a route dialog and returns focus" is **not** proven by this data — see §7.

## 6. Failures

### F-01 — Light-theme tertiary text is below AA contrast (P2)

- **Where:** all seven captured states, light theme only; 184 failing text nodes, 52 distinct strings.
- **Measured:** 153 nodes at **3.53:1** (12 px / 11 px), 31 nodes at **3.47:1** (9.6 px) against a required **4.5:1**. Foreground is the tertiary token at 54 % alpha: `color(srgb 0.121569 0.137255 0.156863 / 0.54)` over `rgb(254,254,254)` / `rgb(246,246,246)`. Example strings: `Open` ×16, `Parent preparation` ×14, `fetched 19 hr ago` ×12, `model_assessed` ×8, `Library`, `Parent Studio`, `Casual`, section metadata, empty-state explanations.
- **Why it matters:** WCAG 1.4.3 AA for normal-size text. This is the plugin's pervasive secondary/meta voice — provenance, status and empty-state copy all become hard to read in light mode, which is the theme a parent is most likely to use in daylight.
- **Reproduction:**
  1. Pin CDP `9351`; open `http://127.0.0.1:5174/#/coursebook` with the audit profile.
  2. `document.documentElement.dataset.hermesMode = 'light'` (what `setMode(cdp,'light')` does).
  3. `measure(cdp)` from `scripts/audit-ux-lib.mjs`; read `contrast[]`.
  4. Every state returns 7–40 nodes at 3.47–3.53.
- **Screenshots:** `docs/a11y-shots/<state>-light.png` for all seven states (e.g. `lesson-ready-light.png`, `demo-fixture-mode-light.png`).
- **Owner:** Vellum (plugin token choice) with the host design-system owner for the token value. The plugin uses `text-(--ui-text-tertiary)` 88× and `text-(--ui-text-secondary)` 81× (`desktop/plugin.js`); no raw hex is used, so the fix is either the host token or moving 12 px body/meta copy to a stronger token in light mode. Not fixed here (audit only).

### F-02 — Attempt-1 screenshot set was invalid (P2, audit tooling; corrected)

See §2. 54/54 images were host overlay/blank frames. Corrected by re-capture; invalid originals preserved in `audit/ux/shots-attempt1/`. Any earlier document that cites them as visual proof is unsupported.

### F-03 — 200 ms transitions on inputs (P3)

`desktop-input-chrome` elements carry `transition-duration: 0.2s` (measured in every dark capture; up to two nodes per page). DESIGN guidance is ~100 ms functional transitions; `prefers-reduced-motion: reduce` was **not** measured this pass (harness supports it via `setReducedMotion`, but no variant used it). Minor: no layout or usability impact observed.

### F-04 — 9.6 px captions (P3, folded into F-01)

Chips/tags (`Casual`, `Parent preparation`, `Cold attempt`) compute to **9.6 px** at 100 % text. They are legible in dark, fail contrast in light, and remain 19.2 px at 200 %. No WCAG minimum font size exists, but 9.6 px is below comfortable reading size; report only.

### F-05 — Host session sidebar truncates at 200 % (P3, host-owned)

At root 32 px the host's own left rail truncates labels (`Capabil…`, `Messa…`, `Schedul…`, `Course…`, `Search ses`). Outside `[data-cb-route]`; recorded because a keyboard/screen-reader user meets it before reaching Coursebook. Owner: Hermes Desktop host, not Coursebook.

### F-06 — Two UX states are unreachable by the DOM rig (P3, testability)

`GRADER_UNAVAILABLE` cannot be injected into the window in this configuration (primary gateway 44219; proxy 44232 receives nothing, §7.3), and the course-row `Actions for …` control opens no DOM menu, so `Delete enrollment…` cannot be selected (§7.4). Both states need a dedicated window whose primary connection is the fault proxy, and either pointer events or a restart after `audit-ux-connection.py` rebinds the profile. Until then those two rows are **unproven**, not passed.

### F-07 — Rendering fails under tile-memory pressure (P3, host-owned)

The audit window logs `cc/tiles/tile_manager.cc: tile memory limits exceeded, some content may not draw` and crashed its renderer once mid-run; screenshots then come back blank while the DOM stays correct. This is why every capture here is gated on route + overlay + byte size, and why the gap pass ran DOM-only. Owner: Hermes Desktop host (Electron/`--disable-gpu` on Wayland); it also explains attempt-1's 54 corrupt frames.

Adding: attempt-submitting lock (**PASS**), 200 % text on the lesson section (**PASS**). Still blocked: grader-unavailable copy and the delete-confirmation dialog — both by rig topology, not by product behaviour (§7.3, §7.4). Raw data: `audit/ux/attempt-dialog.json`, `audit/ux/dialog-focus.json`.

**7.1 Attempt submitting — PASS.** On the live lesson section (`CURRENT CHECK`, bound chat), `Submit answer` became `disabled` **within 120 ms** of the click (measured twice), and a second click while disabled was dispatched but recorded nothing new. The attempts view advanced after the graded submit, so the row count alone cannot prove exactly-once; the lock + disabled duplicate is the direct evidence for "no duplicate submit". Evidence: DOM measurements in `audit/ux/attempt-dialog.json`. The two frames taken at that moment came back as 218×153 partial surfaces (tile-memory pressure) and were **deleted rather than published as if they were full-window captures**.

**7.2 200 % text on the lesson section — PASS.** Root 32 px, body text 26 px, `overflowX = 0`, `clipped = []`, no unnamed controls, no colour-only status, no control under 20×20 px. Evidence: `-section-text200` measurement in `audit/ux/attempt-dialog.json`, screenshot `attempt-section-text200.png` (135 KB, valid frame).

**7.3 Grader unavailable — BLOCKED (rig topology).** The window's primary gateway is `127.0.0.1:44219`, not the fault-injection proxy on `44232`: `audit/ux/rpc-log.jsonl` received **zero** new entries after pointing the profile's primary connection at 44232 and reloading the window. A submit under the injected `GRADER_UNAVAILABLE` fault therefore graded normally instead of failing, and no `needs_retry` copy was produced. This says nothing about the product's grader-unavailable state; it says the injection path was not wired to this window. Repro of the block: `python3 scripts/audit-ux-connection.py 44232` → primary changes in `~/.hermes/sentinel-ux-audit/userdata/connections.json`, but the running app keeps dialing 44219 until it is restarted, and no restart was performed (shared window, another session's work in it).

**7.4 Delete-confirmation dialog — BLOCKED (entry point is not a DOM menu).** The course-row control `Actions for <course>` is reachable by keyboard (it appears as a Tab stop) and clicking it in the renderer leaves `document.querySelectorAll('[role="menuitem"], [role="menu"] button')` **empty** — no DOM menu opens, so `Delete enrollment…` cannot be selected by a DOM click. A 14-stop Tab walk after the click stayed on the list's `Open` / `Actions for …` pairs (no trap), and Escape left focus on the same row action. The dialog's focus/Escape behaviour is therefore **still unproven**; it needs a pointer-event or native-menu path, or a dedicated window where the menu is known to render. No destructive action was confirmed; the dialog was never opened, so no course was deleted. Evidence: `audit/ux/dialog-focus.json`.

**Unchanged gaps:** alternate colour theme (no second theme present; `forced-colors` used instead), reduced motion, screen-reader announcement text, and the 18 uncaptured §13 rows listed in §4.


## 8. Verdict

- Layout, clipping at 200 %, horizontal overflow, narrow, split and hidden-pane: **PASS** in all seven captured states (49/49 captures, 0 clipped nodes, 0 overflow).
- Colour-only communication / unnamed controls / small targets: **PASS** (0 instances in 49 captures).
- Keyboard trap: **PASS** over 45 Tab stops per state and 14 stops inside the course list; **Escape/focus-return in a dialog unproven** (dialog not reachable, §7.4).
- Attempt submit lock: **PASS** (disabled within 120 ms, duplicate ignored). 200 % text on the lesson section: **PASS**.
- Contrast: **FAIL** in light theme (F-01, P2, 184 nodes) — the one release-relevant defect.
- Coverage: **9 of 26** documented states captured (8 with the full 7-variant matrix, 1 partial), 2 attempted and blocked by the rig, 15 not attempted. This report does not claim the uncaptured states pass.

**Release recommendation: conditional no-go on the light theme until F-01 is fixed or explicitly accepted; the matrix is otherwise green for the measured states.**
