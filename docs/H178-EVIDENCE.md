# H-178 · Field Stop — evidence

Status: implemented; review-round-1 code defects fixed and unit-proven on
`wt/h178-field-stop` (base `5cc8cca`). **Both evidence halves are now captured on the current
module: the eight-frame static matrix (§5, H-204) and the driven wrong → hint → hinted retry →
completion → return sequence (§6, H-205), each pinned to plugin sha `3500117…`.** Merged to master on top of `d84cfc5`.

Capture provenance: both halves were captured on module `3500117…` (`desktop/plugin.js` at `2d7282a`)
and merged onto master `d84cfc5`, whose module is `6f444dcb…` after H-179. H-179's diff touches no
`LessonPlayer` / `FieldStop` / `AttemptControls` / `useOpenCheck` line (`git diff 98aedde 09b942a -- desktop/plugin.js`,
zero matches), so the surfaces these frames show are unchanged; each record still pins the sha it was
captured against. Re-shooting on the final module belongs to the final evidence pass (H-203 / H-182).

## 0. Review round 1 — what changed in this run

1. **`attempt_count` now reaches the chip.** `useOpenCheck` merges the facts `check.get` already
   returns (`attempt_count`, `state`) alongside `stimulus` (`desktop/plugin.js` `useOpenCheck`).
   Before this, the pending chip's `attemptCount > 0 ⇒ hinted` branch was dead in the shipped path,
   so a retry printed "First try, no hints" while the backend committed `hinted`.
   New tests mount the real hook (`mode: "open"` in `tests/test_desktop_h178_field_stop.py`) against
   contract-shaped `check.open` + `check.get`, and assert `attempt_count` is present on the object
   `AttemptControls` receives — no hand-built `check_payload(attempt_count=...)`.
2. **`lesson.assist`'s revision is adopted.** `AttemptControls` keeps `assistRevision` from the
   response and submits against `fenceRevision = max(page.revision, assistRevision)` for the assist
   itself, `attempt.submit` and the retry submit. A hint followed immediately by Check can no longer
   be refused as `STALE_REVISION`. Test asserts the post-assist submit carries revision 4, not 3.
3. **Chip comment corrected**: it now states that `self_reported` is also an authored override
   (learner voice), not only `answer_shown`.
4. **Close can no longer claim an unearned class.** `LessonPlayer` passes
   `state.evidenceClass` (recorded) only; a stop with no check closes without a chip. Test added.
5. Harness scripts for the live run: `scripts/h178-nav.mjs` (route → course → Learn → stop → Game →
   check step), `scripts/h178-send.mjs` (one real chat turn, which is what binds the armed lesson
   run), `scripts/h178-eval.mjs` (single CDP eval with a hard timeout; `h149-cdp.mjs`'s evaluate has
   none and hung once on a dead context).

## 1. What the Field Stop is (`desktop/plugin.js`)

**Header.** `STOP n OF m` (section ordinal / `progress.total_objectives`), section title, one
objective sentence from the recorded `evidence_target`. No metadata strip, no check-count strip;
the shell's duplicate title block stands down while the player is on screen.

**Answer surface.** The authored stimulus decides: `format: "selection"` with declared choices is a
`role="radiogroup"` of large option rows (keys 1–8, arrows, Home/End, roving tabIndex, selected
state in words, `{kind:'selection',selection:[choice],text}` so `exact` and `selection` references
both grade the pick). A written check keeps the textarea as a first-class surface. No check format
is invented.

**Integrity chip (P0).** `EvidenceChip` renders the backend's `evidence_class` with one sentence:

| backend field | value | chip label | sentence |
| --- | --- | --- | --- |
| `attempt.submit.evidence_class` | `cold` | First try, no hints | No hint and no shown answer went into this answer, so it can count as independent evidence for the objective. |
| `attempt.submit.evidence_class` | `hinted` | Hinted | A hint was recorded before this answer. The attempt is still recorded, but it cannot count as independent evidence. |
| `attempt.submit.evidence_class` | `answer_shown` | Answer shown — this attempt is no longer independent | The answer was shown before this attempt. It records what you did after seeing the answer, not what you can do unaided. |
| `attempt.submit.evidence_class` | `self_reported` | Self-reported — you told us | It cannot count as independent evidence. |
| `attempt.submit.evidence_class` | `override` | Override — not independent evidence | You moved on without a grade. Access advanced; the objective is not counted as independent evidence. |

Pending class (before submit) is read, never guessed: newest unconsumed `evidence.inspect` event
(`hint_request` / `answer_shown`), else `check.get.attempt_count > 0` ⇒ `hinted`, else `cold`.

**Help controls.** `lesson.assist` is called from the pane (`I used a hint` / `I saw the answer`),
only with a live check and an active binding; it records the learner's own statement (the backend
withholds hint text and the answer).

**Close.** Companion (existing seam, absent ⇒ nothing), `You finished Section n`, the recorded
evidence chip, recorded counts, one action pair: primary `Return to the trail`, secondary
`Read the section`. No confetti, score, streak or mastery.

## 2. Tests (this run)

```
node --check desktop/plugin.js                                  → OK
required suite (h149, h97, breadth-copy, lesson-views, h152, h105) → 99 tests OK
tests.test_desktop_h178_field_stop                              → 20 tests OK
```

`tests.test_m4_visual_audit` is still red by design until the frames are regenerated (§5).

## 3. Honest read of the demo sequence

The backend classifies an answer by **how it was produced**, not whether it was right. On one check
the provable sequence is: first answer (wrong) → chip `cold`; `I used a hint` → pending `hinted`;
retry → verdict `hinted`. A *cold retry on the same check is impossible* (`_classify_evidence`
treats any second committed answer as at least `hinted`; `check.open` reuses the open check). Cold is
proved on the next check version's first attempt — which is the state prepared below.

## 4. Live state prepared on the demo backend (127.0.0.1:44219)

- Enrollment `enr_544f0aba033e4fc0a2f50fb61aceda25`, section 2
  (`obj_2d909e4f37014c14bb216f1b35cc3753`, "Choose the polite expression for a first confession") —
  the one section whose served document has teaching blocks.
- Open check is now **`chk_be7f41759dad406d91b89a482c4d1aa1` v3, `attempt_count: 0`** — a genuine
  first try, because the previous v2 was taken to a pass (`好きです`, accepted answer) which closed it.
- `check.get` returns `attempt_count: 0` for v3, so the pending chip renders **cold** live (verified
  in the window: `chip: "cold"`, `chipPending: "false"`).
- The section's run `run_397b2fb57f93445d873f5e1da0fcbcfb` is now **bound**: one real chat turn in
  the isolated window wrote
  `bind_ec912fd15f164df983d11e36875756ac` (status `active`, stored session
  `20261108_112415_bfc421`). Before that the player was `detached` and `Check` was off — that is why
  the first attempt at this capture could not be driven.
- Rigs (launched from this worktree's `scripts/cb013-live-window.sh`, never reloaded):
  - **before**: `~/.hermes/coursebook-test-h178-b`, CDP **9384**, plugin sha `6aeca221` (H-177/base)
  - **after**: `~/.hermes/coursebook-test-h178-a`, CDP **9385**, plugin sha `a19a344b` (this branch)
- Read-only live state reached on the after rig: player mounted on section 2, `STOP 2 OF 4`, step
  2 of 2, written check, pending chip `cold`, `I used a hint` / `I saw the answer` present, `Check`
  enabled (binding active).

## 5. Field Stop frame matrix (H-204) — captured

Rig: `~/.hermes/coursebook-test-h178-a` (after plugin), CDP **9385**, window restarted so the
loaded bytes are the installed bytes. Installed `desktop-plugins/coursebook/plugin.js` sha256
`350011775b97a055e887d624bc2df11025a3129a2a41207b20acc2dc53f89ad4` — byte-identical to `desktop/plugin.js` at base `2d7282a` (H-196 + H-197).
State: the existing open check on section 2 (STOP 2 OF 4, step 2 of 2, written check `Check v4`,
binding active), pending integrity chip **cold** — no answer was submitted for these frames.
No course was re-authored and no backend state was advanced.

Theme was set through the plugin's own Appearance control (Settings sheet, real click), never by
forcing a class. Every row is read from the painted DOM of the live window; the PNG is the same
window's `Page.captureScreenshot`.

| frame | viewport (CSS px) | root font | theme | state | horizontal overflow | PNG px | sha256 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `field-stop-stop2-dark-460.png` | 460×1561 | 16px | dark | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 413×1400 | `bceb31b24b21b8a2c6232faaf08cc0eabe8258cee403cae6451f0f8c04d785ba` |
| `field-stop-stop2-dark-900.png` | 900×1561 | 16px | dark | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 807×1400 | `ad4f766e5bdf89fa721b43a1ab34b9b1455026686b595af48eea145bafd8cccf` |
| `field-stop-stop2-dark-1049.png` | 1049×1561 | 16px | dark | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 941×1400 | `3be5723113f2a140a23ec464ee8c7386995a81f8232838acfd2ac29aa06ac47c` |
| `field-stop-stop2-dark-1049-text200.png` | 1049×1561 | 32px | dark | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 941×1400 | `234839dbe4734485559d9985a258eaac13e5d5d1226f2a27bcb1e2d181bc1061` |
| `field-stop-stop2-light-460.png` | 460×1561 | 16px | light | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 413×1400 | `aa07f199e8394c9b9c7aaba6d4233e30447fc562ae06c2553771f1b8500e9b70` |
| `field-stop-stop2-light-900.png` | 900×1561 | 16px | light | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 807×1400 | `5b3001f8733dc888c577608da1c1cf58bfbeee0b98416be8dce01ac27503e4f9` |
| `field-stop-stop2-light-1049.png` | 1049×1561 | 16px | light | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 941×1400 | `6e33b36851539db624abfb9913740ab72b0083434414938512de7b90d3bd609a` |
| `field-stop-stop2-light-1049-text200.png` | 1049×1561 | 32px | light | header `STOP 2 OF 4`; chip `cold` (pending) | 0 | 941×1400 | `43823cc8d822c50781a35e7309cdc4ff267472f2fecf2cf7aeb39573c35fdd56` |

The PNG is narrower than the CSS viewport because this desktop window carries the display scale
(`devicePixelRatio` 0.896): 1049 CSS px paints onto 941 device px. The layout width is the
measured `innerWidth`; the file's pixel width is recorded separately so neither number is implied.
The 200% rows are a 32px root font on a 1049 CSS px viewport, not a browser zoom.

Not painted, and stated rather than synthesized:

- **Before rig** (`~/.hermes/coursebook-test-h178-b`, CDP 9384): not running — `curl` to 9384
  returns connection refused, and its installed plugin is the H-177 sha `6aeca221`. No before
  frames are part of this card, so no rig was started for it.
- **Driven sequence** (wrong answer → hint → hinted retry → pass → completion → trail) belongs to
  H-205. These frames show one state only: the untouched cold check.
- **M4 re-pin** deliberately not run (card forbids it); `tests.test_m4_visual_audit` stays red
  until that separate step.

Measurements: `audit/visual/h178-field-stop/measurements.json`; capture: `scripts/h202-capture.mjs`.
## 6. Driven sequence — wrong → hint → hinted retry → completion → return (H-205, rechecked by H-206)

Captured 2026-11-08 17:07–17:08 MST on the **after** rig, CDP **9385**, after re-pointing the rig at
the card's base: worktree `t_9659a217` @ `2d7282a` (H-196 + H-197 merge), installed desktop plugin
sha256 `350011775b97a055e887d624bc2df11025a3129a2a41207b20acc2dc53f89ad4`
(`~/.hermes/coursebook-test-h178-a/home/desktop-plugins/coursebook/plugin.js`; the marker's source is
the worktree's `desktop/` via `home/plugins/coursebook`). The window was restarted once to publish
that copy; the H-196 Workshop destination (`data-cb-nav-item="workshop"`) is present in the loaded
build, which the previous copy (sha `7a56a7d`, `a8b36be`) did not have.

Surface: `enr_544f0aba033e4fc0a2f50fb61aceda25`, section 2 /
`obj_2d909e4f37014c14bb216f1b35cc3753`, check `chk_be7f41759dad406d91b89a482c4d1aa1` **v3**,
`attempt_count: 0`, state `open`, binding `bind_ec912fd15f164df983d11e36875756ac` `active`.
Driven through the real UI only: typed into `#cb-attempt-answer`, clicked the footer `Check`,
clicked `[data-cb-assist] button` "I used a hint", `Try again`, then the completion actions.
Driver: `scripts/h205-drive.mjs` (`nav` / `sequence` / `finish`); every frame carries viewport,
root font size, theme, sha256 and the step label in `audit/visual/h205-field-sequence/sequence.json`.

| # | frame | state on screen | chip | sha256 (12) |
| --- | --- | --- | --- | --- |
| 01 | `01-answer-cold.png` | STOP 2 OF 4, step 2 of 2, answer field empty | pending `cold` — "First try, no hints if you submit now" | `0d0c0c91ef2d` |
| 02 | `02-answer-typed.png` | wrong text typed, `Check` enabled | pending `cold` | `94cf987d876e` |
| 03 | `03-wrong-verdict.png` | "Not quite", recorded answer, `Try again` | recorded `cold`, pending false | `bf37c2d53fd6` |
| 04 | `h206-recheck/04-retry-surface.png` | answer field back after `Try again` | pending `hinted` — "Hinted if you submit now" | `a53e31052661` (H-205 before: `4b3d315ab9bc`) |
| 05 | `h206-recheck/05-hint-recorded.png` | after "I used a hint": `Hint recorded` used-state chip replaces the button; only `I saw the answer` remains | pending `hinted` (before H-206 this was **pixel-identical to 04**) | `ee0d46c87209` (before: `4b3d315ab9bc`) |
| 06 | `06-hinted-pass.png` | graded `pass`, `Finish` | recorded `hinted` | `5bed2f88d675` |
| 07 | `h206-recheck/07-completion.png` | "You finished Section 2"; `0 of 4 with independent evidence · 3 to review` | recorded `hinted` | `babd14361a18` (before: `8f78357f3e97`) |
| 08 | `08-returned-trail.png` | section page + trail, "Resume the lesson" | none (player gone) | `6b1e229e7554` |

All frames: viewport `1049 × 1338`, root font size `16px`, theme `dark` (H-204 owns the frame matrix
across widths/themes; this card only drives the sequence).

**H-206 recheck.** Rows 04/05/07 were re-shot after the fix on the same rig (window restarted;
installed plugin sha `47e04fd55a61a50d7159eb96a27fee29d70d93d6afa1ee34351ffb848474419b`,
byte-identical to `desktop/plugin.js` on `wt/h206-field-followups`), same viewport `1049 × 1338`,
root font `16px`, theme `dark`, DPR 0.896. The recheck drove the next version of the same check
through one cold wrong attempt and one hinted pass; its five frames and their per-frame geometry
live in `audit/visual/h206-recheck/` (`scripts/h206-recheck.mjs`). The H-205 before-shas are kept in
parentheses above so the comparison survives without re-running the old module.

Read from the painted DOM of the after frames: `[data-cb-assist]` contains no `I used a hint` button
(`[data-cb-assist-used="hint_request"]`, role `status`, reads "Hint recorded"), the note becomes
"Recorded for this attempt. This answer cannot count as independent evidence.", and the completion
line and the section header now use one phrase — `with independent evidence`.

**Backend record (`evidence.inspect`, layer 1, ordered).** Exactly one evidence-class transition on
the check, and it is the one the chip names:

```
2026-11-09T00:07:33.430Z  attempt       cold    att_9c770b858e884da2816d70178ab65e7c  verdict not_yet
2026-11-09T00:08:01.941Z  hint_request  hinted  (is_action true, attached to the next attempt)
2026-11-09T00:08:04.699Z  attempt       hinted  att_2ab4009add4a4217adfe5e7d58cf9a1b  verdict pass
```

Two committed attempts on v3, `cold` then `hinted`; the `hint_request` row sits between them. The
completion surface's own count line agrees ("7 attempts recorded on this section · last just now"),
and `check.get` now returns `attempt_count: 2` for v3.

### Defects found by this run

1. **Fixed in H-206 — no visible acknowledgement of a recorded hint.** Frame 04 and frame 05 were
   byte-identical (`4b3d315ab9bc…`, 242,999 B) when this run was captured. `lesson.assist` *did*
   record the event (row above), but the pane changed nothing on screen: the pending chip was already
   `hinted` (driven by `attempt_count > 0`, not by the hint), the assist buttons stayed enabled, and
   nothing said "hint recorded". H-206 replaces the pressed control with a `role="status"`
   "Hint recorded" chip, changes the note to "Recorded for this attempt…", keeps focus in the group
   that replaced the button, and refuses a second hint event. The after rows above are the proof.
2. **Fixed in H-206 — completion copy disagrees with the trail.** Frame 07 said "0 of 4 with
   evidence · 3 to review" while the section header/trail said "0 of 4 **With independent
   evidence**". The completion fact now reads `0 of 4 with independent evidence · 3 to review`, one
   phrase in both places; no state changed.
3. Not this card's scope, seen while reviewing the completion frame: low-contrast secondary
   controls ("Review due", "Open Coursebook") and a clipped saved-note body at the 1049 viewport.
   H-204's frame matrix should judge these.

### What this run did not do

- No light-theme sequence, no narrow (900/460) sequence, no 200% text sequence — the card assigned
  the frame matrix to H-204 and asked this card for the driven sequence only.
- No before-rig (9384) capture; the comparison frames remain H-204's.
- No changes to `desktop/plugin.js`, no M4 re-pin, no merge, no push. The only writes are the eight
  frames, `sequence.json`, the driver `scripts/h205-drive.mjs`, and this section. (The H-206 recheck
  above is a later run on the next check version; it re-shot 04/05/07 and changed `plugin.js`.)

