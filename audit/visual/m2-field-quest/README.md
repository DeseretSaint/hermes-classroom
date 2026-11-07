# M2-U2 — Field Quest

Evidence for the gamified presentation of the same lesson document. Product-line card: nothing
here changes the 0.1.0 release evidence, and nothing here claims Coursebook is installable.

## What was built

Field Quest is the third lens over one validated `LessonDocument` (`docs/VISUAL_MEDIA_PLAN.md` §2,
§5). It is not a second lesson, a second check or a second renderer:

- **Missions** — every block of the document becomes one numbered mission, in authored order,
  printing the authored `short` prose plus its media and source chips. The mission list is a
  `<ol>`; each mission keeps `data-cb-mission="<block id>"`.
- **Checkpoints** — the block that already carries the document's `check_id` is labelled
  `Checkpoint` and holds the *same* single `AttemptControls` node Textbook and Guided use. No
  mission is locked, and the checkpoint says so in words: “Finishing it is not required to read
  anything here.”
- **Progress is descriptive** — `2 independent · 1 due`, read from `library.list`'s
  `evidence_summary`. There is no XP, no streak, no badge standing in for evidence and no mastery
  claim; a course with nothing recorded says “No objectives recorded yet”, and a missing summary
  says “Progress not recorded” rather than rendering a zero.
- **View handoff** — each mission offers “Read in Textbook”, which switches the lens and moves
  focus to that exact block id (`data-cb-block`, `tabindex="-1"`), never to an offset.
- **Availability** — the switcher is built from `document.views` (`lessonViewOptions`). A document
  without authored `short` offers Textbook alone; Field Quest is never a broken toggle.
- **States** — reduced motion is read (`useCbMotion` → `data-cb-motion`) and the view adds no
  transition or animation; media keeps its text equivalent; a failed check keeps every mission
  readable; a checkpoint with no attachable check says it stays “readable and ungated”.

## Files

| File | What it proves |
|---|---|
| `01-quest-light-wide.png` … `05-quest-light-460-200pct.png` | The view at 1280 and 460 px, light and dark, 100 % and 200 % text. |
| `06-quest-keyboard-focus-460.png` | One `Tab` lands on the first mission's “Read mission 1, Start here, in Textbook” button. |
| `06b-quest-checkpoint-focus-460.png` | Three `Tab`s reach the checkpoint's answer field — the real form, not a mock. |
| `07-quest-reduced-motion.png` | `data-cb-motion="reduced"` and **zero** elements with a transition or animation. |
| `08-quest-media-light.png` | A media child renders once, inside its field-note frame, with its text equivalent. |
| `09-quest-check-error-light.png` | A failed check node: the error is shown and all four missions stay readable. |
| `10-quest-ungated-light.png` | A checkpoint with no attachable check says it stays readable and ungated. |
| `11-parity-textbook-light.png` / `12-parity-guided-light.png` | The same document in the other two lenses, for the parity comparison. |
| `13-quest-no-objectives-light.png` | A course with no recorded objectives: “No objectives recorded yet”, no fake zero. |
| `evidence.json` | Per-frame DOM measurements: tokens painted, mission ids/roles/state words, checkpoint id, progress string, overlap count, disabled controls outside the checkpoint, animated elements, banned words, overflow, active element. |
| `live-01-section-availability.png` | **Live** isolated Desktop capture on a real backend: a real section whose document has no authored `short` shows `data-cb-view-switcher="textbook-only"`, `data-cb-view-options="textbook"` and the server's own `view_note`. |
| `live-availability.json` | The same measurements read from the live window, with the plugin sha256 that was loaded. |

## Honest limits

- `01`–`13` are static renders of the shipped module in Chromium: no backend, no chat, no RPC. The
  document is contract-shaped input and the assertions are about what the view does with it.
- **No live Field Quest frame was captured.** The isolated homes hold stored lessons that predate
  authored `short`, so `views.field_quest` is false on every section the Desktop walk reached; the
  HTTP probe of `~/.hermes/coursebook-m1-guided-211852` does contain four `state=complete`
  sections with `views.field_quest=true`, but the window walk inside this card's runtime reached
  only `textbook_only` sections of a different enrollment in that home. The Quest surface is
  therefore proved by the shipped-module render, the 56-test render/parity suite and the static
  frames; the live capture proves the availability rule and the honest server note.
- The static frames carry no host button/badge CSS (the stubs render bare `<button>`/`<span>`), so
  “Read in Textbook” looks like a bordered field in the PNGs. The real control is a text button;
  the live frame shows the styled switcher.
- The checkpoint form in the frames is the real `AttemptControls` with a contract-shaped `check.get`
  stimulus; no attempt was submitted in any frame.
- Screenshots are single frames. Focus rings come from the host/browser, not from the plugin.
