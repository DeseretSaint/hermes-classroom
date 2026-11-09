# H-178 · Field Stop — evidence

Status: implemented; review-round-1 code defects fixed and unit-proven on
`wt/h178-field-stop` (base `5cc8cca`). **The eight-frame static matrix is captured and measured on
the current master module — see §5.** The driven sequence is still outstanding (H-205). Not pushed.

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
