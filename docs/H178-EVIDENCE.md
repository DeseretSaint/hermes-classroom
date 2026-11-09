# H-178 · Field Stop — evidence

Status: implemented; review-round-1 code defects fixed and unit-proven on
`wt/h178-field-stop` (base `5cc8cca`). The driven live Desktop sequence (wrong → hint → hinted retry
→ completion → return) is captured on base `2d7282a` at plugin sha `3500117…`; §5 has the frames,
the backend rows and the defects it found. The static frame matrix remains H-204's. Not pushed.

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

## 5. Driven sequence — wrong → hint → hinted retry → completion → return (H-205)

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
| 04 | `04-retry-surface.png` | answer field back after `Try again` | pending `hinted` — "Hinted if you submit now" | `4b3d315ab9bc` |
| 05 | `05-hint-recorded.png` | same screen after "I used a hint" | pending `hinted` (**pixel-identical to 04**) | `4b3d315ab9bc` |
| 06 | `06-hinted-pass.png` | graded `pass`, `Finish` | recorded `hinted` | `5bed2f88d675` |
| 07 | `07-completion.png` | "You finished Section 2", counts, `Return to the trail` | recorded `hinted` | `8f78357f3e97` |
| 08 | `08-returned-trail.png` | section page + trail, "Resume the lesson" | none (player gone) | `6b1e229e7554` |

All frames: viewport `1049 × 1338`, root font size `16px`, theme `dark` (H-204 owns the frame matrix
across widths/themes; this card only drives the sequence).

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

1. **No visible acknowledgement of a recorded hint.** Frame 04 and frame 05 are byte-identical
   (`4b3d315ab9bc…`, 242,999 B). `lesson.assist` *did* record the event (row above), but the pane
   changes nothing on screen: the pending chip was already `hinted` (driven by `attempt_count > 0`,
   not by the hint), the assist buttons stay enabled, and no line says "hint recorded". A learner
   cannot tell a click from a miss, and nothing stops repeat clicks. Owning specialist should add a
   recorded-state confirmation (and consider disabling the control once recorded).
2. **Completion copy disagrees with the trail.** Frame 07 says "0 of 4 with evidence · 3 to review"
   while the section header/trail say "0 of 4 **With independent evidence**" — two different
   denominators/labels for the same section on adjacent surfaces. Copy only; no state is wrong.
3. Not this card's scope, seen while reviewing the completion frame: low-contrast secondary
   controls ("Review due", "Open Coursebook") and a clipped saved-note body at the 1049 viewport.
   H-204's frame matrix should judge these.

### What this run did not do

- No light-theme sequence, no narrow (900/460) sequence, no 200% text sequence — the card assigned
  the frame matrix to H-204 and asked this card for the driven sequence only.
- No before-rig (9384) capture; the comparison frames remain H-204's.
- No changes to `desktop/plugin.js`, no M4 re-pin, no merge, no push. The only writes are the eight
  frames, `sequence.json`, the driver `scripts/h205-drive.mjs`, and this section.

