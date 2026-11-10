# CP-033 — script and beat sheet

Shot list for the 75-second cut. Times are the animatic's own: 120 BPM, `0.5 s` per beat, so every
boundary is an integer beat and every cut is a hard cut on that beat. Nothing here is rounded by
eye.

The picture column names the **surface**, not a drawing. Where the animatic uses a reference plate,
the final take substitutes a real capture of the same surface through `scripts/cp-capture.mjs`.

## 1. Picture | words | hand-off

| # | In → out (s) | Picture — surface and what changes | Words on screen (caption) | Words spoken (VO) | Hand-off |
|---|---|---|---|---|---|
| S0 | 0.0 → 3.0 | Word card, paper ground, display type. No product pixels. | A chat can answer this. | "A chat can answer this." | Hard cut on beat 6 |
| S1 | 3.0 → 9.0 | Word card, same ground, one line. | It cannot make the answer change what happens next. | "What it cannot do is make the answer change what happens next." | Hard cut on beat 18; the reveal lands on the first hit |
| S2 | 9.0 → 15.0 | **Reveal.** `Home` composition. The wordmark lands on the hit, then the shelf settles in. | Coursebook. / A lesson is governed state, not chat. | "Coursebook. A learning workspace inside Hermes Desktop." | Hold to beat 30, then the shelf gets its own beat |
| S3 | 15.0 → 27.0 | **Proof 1 — the shelf.** `Home`, wide (1049 route). Camera drifts 4% across the card row so the evidence lines are read, not skimmed. | Your shelf is what you have done. / Every card carries its own evidence line and one next step. | "Every card tells you what you have finished and the one thing to do next." | Cut on beat 54 into the lesson |
| S4a | 27.0 → 33.0 | **Proof 2 — the answer.** `Classroom`, wide. The section's real line, then the check card; the answer is entered and submitted. | You answer the check. / It is graded against the section's objective. | "You answer the check, and it is graded against the objective." | Same surface, no cut — the state changes |
| S4b | 33.0 → 39.0 | **Proof 2 — the row.** Same frame: the verdict line appears, the evidence chip stops being a preview — `data-cb-evidence-pending` goes `true` → `false`, compared in the take — and the primary becomes `Next section`. | One row is written. / The chip is a record now. | "One answer. One row. The chip on the screen stops being a preview." | Hard cut on beat 78, labelled as a close |
| S5a | 39.0 → 45.0 | Word card, labelled cut: `window closed`. | Close it. Open it. / A labelled cut in the final take; the reopen is real. | "Close it." | Cut on the reopen (beat 90) |
| S5b | 45.0 → 51.0 | **Proof 3 — resume.** `Classroom` after reopen: the `Now` stamp is on the same section and the same check block is on screen — its block id is compared against the one act one closed on. The evidence chip is present; its class is *not* compared across the reopen. | Same objective. Same check. / A new window on the same place. | "Open it. Same objective, the same check, in a window that is genuinely new." | Hard cut on beat 102 |
| S6 | 51.0 → 57.0 | Word card, the mechanism, largest type in the film. | One answer. One transition. One row. | "One answer, one transition, one row." | Hard cut on beat 114 |
| S7a | 57.0 → 63.0 | Word card with three struck rows: stars, XP on a lesson, a leaderboard — the concept-art elements the build refuses. | No stars. No XP on the shelf. No leaderboard. / Each of these is in the concept art and is refused by the build. | "The concept art had stars, XP and a leaderboard. None of them shipped." | Hard cut on beat 126 |
| S7b | 63.0 → 69.0 | Word card, the rule. | If the backend did not record it, it is not on the screen. | "If the backend did not record it, it is not on the screen." | Hard cut on beat 138 |
| S8 | 69.0 → 75.0 | **End card.** Name, one line, repository, licence. | Coursebook / A Hermes Desktop plugin. MIT licence. / github.com/DeseretSaint/hermes-classroom | "Coursebook. MIT. The repository is on screen." | End of film |

**Sum:** 3 + 6 + 6 + 12 + 6 + 6 + 6 + 6 + 6 + 6 + 6 + 6 = **75.00 s**.

### Where each product string comes from

No product sentence is authored for the film. The strings inside product frames are rows of
`docs/concept-parity/COPY.md`; the film's own captions are editorial and never rendered inside a
product frame.

| Beat | Visible product string | COPY.md id |
|---|---|---|
| S2, S3 | Your field library / Pick a course, or start a new one. / Start a course / Browse library / Your courses | `home.title`, `home.sub`, `home.primary`, `home.secondary`, `home.shelf.label` |
| S3 | `{done} of {total} sections done` · `New` · `{next step}` | `home.card.meta`, `home.card.new`, `home.card.next` |
| S4a | `{check prompt}` · `{choice text}` · Check answer | `classroom.check.question`, `classroom.check.option`, `classroom.check.primary` |
| S4b | That is right. `{why}` · `{evidence class label}` · Next section | `classroom.check.correct`, `classroom.check.next`; the chip label is `EVIDENCE_CHIP_LABEL[class]`, `desktop/plugin.js:11268` |
| S5b | Now · Done · Next · `{section title}` | `classroom.step.current`, `classroom.step.done`, `classroom.step.next`, `classroom.section` |

The v3 deck also defines `classroom.evidence.count` (`{n} of {total} checks recorded`, `COPY.md:157`).
This branch's `desktop/plugin.js` renders no such string — the classroom surface's evidence statement
is the `EvidenceChip` (`desktop/plugin.js:11280`, `data-cb-evidence-chip`) — so the take measures the
chip and the picture does not claim a count. A branch that renders the caption can add it to this
table and to `beats.json`; the film does not name a number the build did not produce.

`{braces}` stay visible in the caption because the value is live state. The caption in the final
take is a fixed sentence, and the number it points at is whatever the real course holds at capture
time; the film never names a number the build did not produce.

## 2. Beat sheet

Bars are 4/4 at 120 BPM: one bar = 4 beats = 2.00 s. Beat 0 is the first frame.

| Beat | Bar.beat | Time (s) | Frame id | Duration (beats) | Event |
|---|---|---|---|---|---|
| 0 | 1.1 | 0.00 | `S0-hook` | 6 | open on the problem |
| 6 | 2.3 | 3.00 | `S1-problem` | 12 | the problem stated |
| 18 | 5.3 | 9.00 | `S2-reveal` | 12 | **reveal on the first hit** |
| 30 | 8.3 | 15.00 | `S3-proof1-shelf` | 24 | proof 1 |
| 54 | 14.3 | 27.00 | `S4a-proof2-answer` | 12 | proof 2, answer |
| 66 | 17.3 | 33.00 | `S4b-proof2-row` | 12 | proof 2, row |
| 78 | 20.3 | 39.00 | `S5a-proof3-close` | 12 | labelled close |
| 90 | 23.3 | 45.00 | `S5b-proof3-resume` | 12 | proof 3 |
| 102 | 26.3 | 51.00 | `S6-mechanism` | 12 | the claim, plainly |
| 114 | 29.3 | 57.00 | `S7a-truth` | 12 | what is refused |
| 126 | 32.3 | 63.00 | `S7b-truth` | 12 | the rule |
| 138 | 35.3 | 69.00 | `S8-end` | 12 | end card |
| 150 | 38.3 | 75.00 | — | — | out |

Machine-readable form: `docs/launch/animatic/beats.json` (the same file the animatic renderer and
the demo driver read). Durations in `docs/launch/animatic/manifest.json` are the measured ones.

## 3. Sound plan (final take, not the animatic)

The animatic is silent on purpose: a flat animatic is judged on whether the beats read without
motion or audio.

| Layer | Rule |
|---|---|
| Bed | one licensed track at 120 BPM, or a generated bed cut to 120 BPM. Keep it model-independent so a provider change never re-times the film. |
| Cuts | every shot change lands on a beat; no transition sound on a word card |
| UI effects | one click on the check submit, one dry tick on the evidence row, one paper "settle" on the shelf drift. Crisp, short, never louder than the caption |
| Voice | only if the script above is recorded first; ducked under nothing, the bed ducks under it by about 8 dB |
| Loudness | normalise the export to −14 LUFS integrated, true peak ≤ −1 dBTP |

## 4. What the driver must produce for each beat

`scripts/cp-demo.mjs` drives the window over CDP and writes a timestamped marker log. Each beat
below has a marker id equal to the frame id, so the editor places a cut at the marker.

| Marker | Driver action |
|---|---|
| `S2-reveal` | navigate to `#/coursebook`, wait for `[data-cb-route]`, wait for the shelf, hold |
| `S3-proof1-shelf` | slow pointer travel across the card row, no click |
| `S4a-proof2-answer` | click the course card, wait for the check, click the first served choice, assert `[data-cb-answer-kind="selection"]`, pause on the filled primary |
| `S4b-proof2-row` | click `Check answer`, wait for the verdict, compare the evidence chip against the value read before the submit (it must have changed), hold |
| `S5a-proof3-close` | marker only; the close is a cut in the edit. Act one ends here |
| `S5b-proof3-resume` | re-attach to the reopened window's **new page target**, navigate to the same route, wait for the section, assert the check block id equals the one act one closed on, hold |
| `S8-end` | no window; the card is composited in the edit |

**The answer must be the selection format.** The module renders three answer kinds — selection,
checklist and text (`desktop/plugin.js:13446`). A click into the text area only focuses it, types
nothing, and the primary stays disabled while the text is empty (`desktop/plugin.js:13628`), so a
text-format check cannot produce S4a's filled primary. The step list therefore clicks
`[data-cb-choice="1"]` and the next step asserts `[data-cb-answer-kind="selection"]`; on a text or
checklist check the take stops instead of stamping an unreachable frame. The demo course is authored
with `classroom.check.option` (see §1), so this is the same check the script is written around.

**The close is a real window transition, not a marker.** The take is split into two acts. Act one
ends at `S5a-proof3-close`; act two opens with a `reconnect` step that closes the take's own CDP
socket and refuses to attach to the page id it just left, so `S5b-proof3-resume` can only be stamped
on a window that was actually reopened. Either run the whole list in one command — the driver
announces the close and waits for the new target — or run `--act 1`, close and reopen the window,
then `--act 2`. Act two's log records the target ids it moved between.

**A mark that says a value changed has to have measured it.** `assert` and `wait for` are presence
checks — they ask whether an element exists, not what it says — so on their own they cannot support a
claim about a value changing. Two steps close that gap. `snapshot { id, selector, attribute? }`
reads an element's `textContent` (or one named attribute) and keeps it; `assert { selector, snapshot,
changed | equals }` reads the same element the same way and stops the take if the value did not move
(`changed`) or did move (`equals`). The evidence chip is snapshotted before the submit and compared
after the verdict: `data-cb-evidence-pending` must go `true` → `false`, so S4b cannot be stamped on a
chip that never became a record. The check block's id (`data-cb-block-check`) is snapshotted before
the close and compared after the reopen, so S5b cannot be stamped on a different block. Where a value
is *not* compared, the document says so: S5b asserts the evidence chip's presence only, and does not
claim its class survived the reopen.

Snapshots are written to `docs/launch/animatic/takes/cp033-take-01.snapshots.json` beside the act
logs, because act two may run as its own invocation. Act one (or a full run) starts a fresh store, so
nothing carries over from an earlier take; act two reads what act one wrote, and a standalone
`--act 2` with no store stops at the S5b comparison and says why rather than skipping the proof.

**The test home is reset between takes.** The driven check must be *unanswered*: the module draws the
answer form only while the check is awaiting input or stale (`desktop/plugin.js:13271`) and the verdict
branch once it has been graded (`desktop/plugin.js:13670`), so on the take after the first,
`[data-cb-choice="1"]` is gone and the answer click stops the take. Reset the test home (or the
section's attempts) to an unanswered check before running act one again; the step list's `setup` says
so, and nothing in the step list performs the reset itself.
