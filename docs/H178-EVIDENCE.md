# H-178 · Field Stop — evidence

Status: implemented and unit-proven on `wt/h178-field-stop` (base `5cc8cca`, includes merged H-177
and H-176). **Live Desktop captures were not produced in this run**; see §5. Not pushed.

## 1. What changed (`desktop/plugin.js`)

**Header.** `LessonPlayer` now opens with `STOP n OF m` (n = section ordinal, m =
`evidence_summary.total_objectives`), the section title as an `h2`, and one objective sentence
composed from the recorded `evidence_target` (`By the end of this stop you can show: <learner
target>.`). The course metadata strip, the `Check 1 of n` count strip and the shell's duplicate
title block are gone while the player is on screen; the breadcrumb and the view switcher move to
one slim navigation row above the reading column (`data-cb-workspace-actions`).

**Answer surface.** The authored stimulus decides the surface. `format: "selection"` with declared
choices renders a `role="radiogroup"` of large option rows:

- keys `1`–`8` select by number, arrows move and select, Home/End jump; roving `tabIndex`;
- selected state is words (`Selected` on the row, `Selected: 2. <choice>` in a live line);
- the answer travels as `choiceAnswer(choice)` = `{kind:'selection', selection:[choice], text}` —
  both fields the `attempt.submit` answer schema declares, so an `exact` reference (grade on
  `text`) and a `selection` reference (grade on `selection`) both read the same pick;
- written checks keep the textarea (rows 5 in the player), the same one-primary footer, and a
  clear submit label. No check format is invented: a `text`/`short_answer` stimulus never becomes a
  choice.

**Integrity chip (P0).** `EvidenceChip` renders the backend's `evidence_class` with one sentence:

| backend field | value | chip label | sentence |
| --- | --- | --- | --- |
| `attempt.submit.evidence_class` | `cold` | First try, no hints | No hint and no shown answer went into this answer, so it can count as independent evidence for the objective. |
| `attempt.submit.evidence_class` | `hinted` | Hinted | A hint was recorded before this answer. The attempt is still recorded, but it cannot count as independent evidence. |
| `attempt.submit.evidence_class` | `answer_shown` | Answer shown — this attempt is no longer independent | The answer was shown before this attempt. It records what you did after seeing the answer, not what you can do unaided. |
| `attempt.submit.evidence_class` | `self_reported` | Self-reported — you told us | It cannot count as independent evidence. |
| `attempt.submit.evidence_class` | `override` | Override — not independent evidence | You moved on without a grade. Access advanced; the objective is not counted as independent evidence. |

The chip is shown **at the result** (`PlayerVerdict`, `AttemptVerdict`) and **at the next attempt**
(a pending chip above the answer form, `data-cb-evidence-pending="true"`). The pending class is
read, never guessed:

- `evidence.inspect {enrollment_id, objective_id}` → the newest `l1.events` row with
  `attempt_id = null` and `kind ∈ {hint_request, answer_shown}` names the class the next committed
  attempt inherits (`evidence_class`); this is the same predicate `coursebook/domain.py::_classify_evidence`
  uses;
- else `check.get.attempt_count > 0` → `hinted` (a second answer to the same check follows feedback —
  `_classify_evidence` / `docs/CONTRACTS.md` §lesson.assist);
- else `cold`.

Because both facts come back from the backend on every mount, the chip survives reload.

**Help controls.** `lesson.assist` is now actually called from the pane for the first time: `I used
a hint` (`hint_request`) and `I saw the answer` (`answer_shown`), only while a check is open and the
chat binding is active. The control records the learner's own statement — it does not invent hint
text, because `check.get` withholds the reference and the assist response carries no answer. The
response's `evidence_class` drives the pending chip immediately and the revision bump makes an
in-flight submit lose its fence instead of committing as cold.

**Close.** `PlayerClose` now renders, in order: the learner's pet through the existing
`useStudyCompanion` seam (absent → nothing, no placeholder), `You finished Section n`, the evidence
chip of the recorded result, the recorded counts, and one action pair — primary `Return to the
trail` (`onExit`, lands on the path), secondary `Read the section` (same document in Textbook
without leaving the page). Exactly one primary; no confetti, no score, no mastery.

**Media.** The text equivalent is now visible, not collapsed: a caption plus `Text equivalent`
block under every artifact, marked `data-cb-media-transcript="true"` for audio. An unavailable
artifact still prints the backend's own message and the text equivalent, which remains the lesson.

## 2. Tests

`node --check desktop/plugin.js` → OK.

Required suite:

```
python3 -m unittest tests.test_desktop_h149_lesson_player tests.test_desktop_h97_check_stimulus \
  tests.test_desktop_breadth_copy tests.test_desktop_lesson_views tests.test_desktop_h152_motion \
  tests.test_desktop_h105_validator_truth
Ran 99 tests — OK
```

Full desktop discovery:

```
python3 -m unittest discover -s tests -p 'test_desktop*.py'
Ran 756 tests — OK
```

(739 before this card; the 17 new cases are `tests/test_desktop_h178_field_stop.py`.)

New coverage: chip mapping for every class, chip render/pending marker, no-class = no chip,
unconsumed hint event → pending `hinted`, prior attempt → `hinted`, first attempt → `cold` then
`hinted` after the real `lesson.assist` response, radiogroup markup and absence of textarea,
keyboard `2` selects and the submitted payload is
`{kind:'selection', selection:['少々お待ちください'], text:'少々お待ちください'}`, reference fields never
printed, close actions/rates/no companion, and source invariants (no timer/streak/score, assist
before answer, no reference leak).

Changed existing tests: `test_desktop_h149_lesson_player` now asserts the Field Stop header
(`STOP 2 OF 4`, title, objective, no check-count strip) and `Return to the trail`, per §5 of
`docs/FINAL-POLISH-SPEC.md`.

## 3. Honest read of the demo sequence

The backend classifies an answer by **how it was produced**, not by whether it was right
(`_classify_evidence`). Therefore the provable sequence on one check is:

1. first answer, deliberately wrong → verdict `not_yet`, chip **First try, no hints** (a failed
   first answer is still cold);
2. `I used a hint` → pending chip **Hinted** (backend response);
3. retry → verdict carries `evidence_class: hinted`, chip **Hinted**.

A *cold* retry on the same check is not possible: `_classify_evidence` treats any second committed
answer to the same check as at least `hinted`, and `check.open` reuses the open check. A cold chip is
proved on the next stop's first attempt (or a fresh check). This card does not change that rule; the
demo narration must say "same check, now hinted" and show cold again at the next stop.

## 4. Files

- `desktop/plugin.js` — `EVIDENCE_CHIP_*`, `EvidenceChip`, `usePendingEvidence`, `choiceAnswer`,
  `AttemptControls`, `PlayerVerdict`, `AttemptVerdict`, `PlayerClose`, `LessonPlayer`,
  `MediaFrame`, `WorkspaceShell`, `SectionPage`.
- `tests/test_desktop_h178_field_stop.py` (new, 17 cases).
- `tests/test_desktop_h149_lesson_player.py` (header + close copy updated to the spec).

## 5. Not done in this run (blocking the card's evidence list)

The isolated Desktop window was **not** re-pointed at this branch, so there are no live before/after
frames at 1049/900/460, light/dark, 200% text, and no live driven sequence (wrong answer → hint →
retry → close → return to trail). What exists on this machine to finish it:

- backend: `http://127.0.0.1:44219` (cb.rpc contract v14, token `cb013-test-token`), Japanese demo
  enrollment `enr_544f0aba033e4fc0a2f50fb61aceda25`, revision 51, 4 objectives, 3 review due;
- window rig: `~/.hermes/coursebook-test-h176a`, CDP `9376`, currently running the H-176 plugin;
- H-149/H-177 capture harnesses (`scripts/h149-capture.mjs`, `scripts/h177-live-check.mjs`).

The remaining work is: copy this `desktop/plugin.js` to
`~/.hermes/coursebook-test-h176a/home/desktop-plugins/coursebook/plugin.js`, repoint
`home/plugins/coursebook` at this worktree, `--stop`/`--restart` (never a page reload), then run the
H-149-style capture for the Field Stop states and re-pin M4 (`python3 scripts/m4v-audit.py`) because
the module hash changed.

**M4 note:** the plugin hash changed, so `tests.test_m4_visual_audit` was not re-pinned in this run.
That pin must be regenerated with the live frames before the card can be called done.
