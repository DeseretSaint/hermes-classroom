# H-178 · Field Stop — evidence

Status: implemented; review-round-1 code defects fixed and unit-proven on
`wt/h178-field-stop` (base `5cc8cca`). **Live Desktop frames are not captured yet** — the rigs are
built, running and bound; §5 lists exactly what remains. Not pushed.

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

## 5. Remaining work (blocking the card's evidence list)

The run hit its iteration budget immediately after the binding was established, so these are **not**
done:

1. Drive the after rig (9385): wrong answer → `I used a hint` → pending `hinted` → retry `好きです`
   → pass → completion → `Return to the trail`, capturing each state.
2. Capture the frame matrix for step / written check / wrong feedback / hinted attempt / completion /
   returned trail at 1049 / 900 / 460 × light / dark, plus 200% text.
3. Capture the before rig (9384) for the same surfaces on an open check (v4 after step 1 closes v3),
   since the H-177 player has the textarea + grey evidence line and no chip.
4. `python3 scripts/m4v-audit.py` to re-pin the module hash, then the full desktop discovery.
5. Write the measurements JSON and the frame README, and replace §4 of this document with results.

A live **choice** check does not exist for an authored lesson in this backend: every generated
check for the demonstration pack is `format: "text"`. The radiogroup is therefore proven by the
shipped-component tests and will be shown in renderer frames, not claimed as live — per the card's
"if the authored check has no choice/checklist, the written check remains the lesson".
