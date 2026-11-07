# Adversarial UX review — Coursebook 0.1.0-rc

Date: 2026-11-07. Reviewer: Hermes (integrator). Baseline: `master` at `54087de`
(`H-02` learner flow merged; `H-03` design merged; `H-01`/`H-14`/`H-12` already on master).
Scope: the learner and Parent Studio surfaces, not host chrome. This review is deliberately
adversarial: the question is not "does it work?" but "would a real person choose to use it, and
does the interface make the harness's honesty feel like care rather than a compliance notice?"

Method: source review of `desktop/plugin.js` on `54087de`, plus the repository's own captured
frames (`docs/assets/*.png`, `docs/a11y-shots/*.png`, `docs/cb015-shots/*.png`). The frames predate
`H-02`'s create-flow rewrite; every finding that depends on the rewritten flow is anchored to code,
not to a stale frame. No new Desktop window was launched during this review, because the operator
has an active Desktop and test rigs must stay on the secondary monitor.

## Verdict

**Functionally coherent; not yet humanified.** The visual system is disciplined and the honesty
copy is unusually good, but the product reads as a governance dashboard for a learning model rather
than a place a person wants to learn. The biggest gaps are language, emotional pacing, and the
absence of a visible path. A first-time learner can read every screen and still not know whether
they are making a one-off lesson, a short course, or a full course, or what will happen after they
press Create.

This is a **GO for a UX pass before release**, not a rewrite. Preserve the honesty and the
accessibility gate; replace the system vocabulary and the flat information density with a warmer
first-run, a clearer scope choice, and one obvious next action per screen.

## Evidence table

| id | surface | observed | severity | card |
|---|---|---|---|---|
| UX-01 | First run / Courses empty state | Text-only; "governed learning workspace", "real evidence", "honest next steps"; "Import a pack" undefined; filter pills visible with zero courses; duplicate "New course" and "Create a course" actions | High | H-28 |
| UX-02 | Create flow | "Recipe" is the most prominent choice; placeholder goal/title are Japanese-only; "Your level", "Subject domain", "Locale" are unexplained system fields; scope exists but the difference between One lesson / Short course / Full course is only a time sentence | High | H-28 |
| UX-03 | Create result / plan review | Honest job and recovery states, but the screen is a status ledger (ids, revision, job id) before it is a promise ("here is what you will be able to do"); no visual progress, no “what happens next” summary | Medium | H-28 |
| UX-04 | Lesson index / Textbook | Four rows of title + two tags + timestamp + repeated "Open section"; no visible overall progress, grouping, or completed/next marker; the tags compete with the title | High | H-29 |
| UX-05 | Check result | "Cold attempt", "discrimination", "matches an accepted answer", "Grading failed"; success is a green check plus a dry sentence; the copy does not distinguish “first try without hints” from a penalty | High | H-29 |
| UX-06 | Library / Import | "No marketplace ranking and no verified badge" reads as a warning about the product; no statement of what a pack is, what file to choose, or what happens after import; only the community-pack path is visible | High | H-28/H-27 |
| UX-07 | Parent Studio | "Parent Studio", "brief", "authored courses" are builder vocabulary; list rows do not explain why near-identical lessons exist; a parent is asked to understand the architecture before teaching | Medium | H-28 |
| UX-08 | Cross-surface visual language | Dark palette, text-only surfaces, no illustrations/thumbnails, almost no differentiated status color; the "Ink & Field Notes" intent is present in tokens but not in the felt experience; the host footer exposes "Backend ready" and version numbers | Medium | H-29 / host |
| UX-09 | Scope and expectation | `H-02` adds One lesson / Short course / Full course and honest time copy; the screen still does not say what the learner will receive, how many sessions, or how approval changes the plan | High | H-28 |
| UX-10 | Status and error tone | `needs_retry` is "Grading failed"; "Nothing advances on its own" is framed as a warning; no encouragement after a pass, no explanation of what was learned | Medium | H-29 |

## Detailed findings

### UX-01 — The first run explains the system, not the invitation

`FirstRun` (`desktop/plugin.js`, current `54087de`) renders the heading "Build a course around
what you want to do." then a paragraph about profile-local progress, two actions, and three
orientation lines. The captured first-run frames show the same screen with visible search/filter
pills and no illustration. The resulting impression is a settings page, not a welcome.

Concrete fixes:
- Lead with one promise and one example: "Learn something specific. Coursebook researches it,
  builds the lessons, and checks your work." Then one primary button, "Start with a goal".
- Keep "Import a pack" as a secondary path with a plain explanation: "Use a course someone already
  made. You will review its sources and integrity before anything is added."
- Hide empty-state search and filter controls until there is at least one course.
- Remove the duplicate top-right "New course" when the empty-state primary action is present.
- Replace "governed learning workspace", "real evidence", and "nothing advances on its own" with
  plain language: "Your progress stays on this profile. Coursebook will not mark something complete
  without a check you can see."

### UX-02 — "Recipe" is the wrong first question, and the examples are Japanese-only

`CreateCourseFlow` currently asks for the goal and title before the scope; the most visually
prominent control in step one is the recipe list (`one_off`/`casual`/`committed`/`companion`).
"Recipe" is product-internal. The goal and title placeholders are both Japanese
(`"Explain the register difference between a friend and a manager."`,
`"Japanese register with friends and managers"`), which makes a generic harness look like a
Japanese demo at the exact moment a new user is deciding whether to trust it.

Concrete fixes:
- Ask scope first, in user language: "What do you want to make?" — "A single lesson", "A short
  course (a few sessions)", "A full course (weeks or months)".
- Explain the consequence of each choice in one sentence, including roughly how many lessons and
  whether a plan will be reviewed. Use the honest time copy already added by `H-02`; do not invent
  minutes.
- Rename "Recipe" to "How you will use it" or derive it from the scope; do not ask a learner to
  choose an internal enum. `one_off` should be visibly tied to "a task I need to do now", not a
  quiz-shaped mini-course.
- Use neutral, topic-diverse placeholders: "Replace the tube on my road bike", "Hold a six-week
  conversation course in Spanish", "Understand the first month of a statistics class". A
  Japanese-specific example belongs in the demo, not the default form.
- Put "Your level", "Subject domain", and "Locale" behind "Help me tune it" or explain them with
  examples. "Locale" must say it is only for language/content conventions, not for the subject.

### UX-03 — The create result is a receipt, not a beginning

The post-create screen lists `courseId`, draft plan id, enrollment id, and plan job id. This is
excellent forensic honesty and poor product reassurance. A learner needs the first sentence to be
"Your plan is being researched; this usually takes several minutes, and you can leave this page."
The ids can live under a disclosure line. The plan review should lead with the learner outcome,
then units/objectives, then the approval action; the job state should be a quiet status, not the
headline.

### UX-04 — The lesson index is a metadata table with a lesson hiding inside it

The Textbook index rows carry a title, two status/construct tags, a "last opened" timestamp, and a
repeated "Open section" button. There is no overall progress marker, no unit/group heading in the
current frame, and no visual distinction between "this is next" and "this is review." A learner has
to read every tag to answer "where am I?"

Concrete fixes:
- Make the row itself the action; keep one visible chevron, not a repeated button.
- Add a compact progress line: "3 of 4 objectives have independent evidence" with a bar or dots,
  and a "Next: ..." marker.
- Use a small number of semantic status treatments (not color alone): a filled dot for complete,
  a ring for next, a quiet dash for not started. Keep the text label for accessibility.
- Group by unit when the blueprint lands; the current flat list will become unreadable at full
  scope.
- Retire "discrimination" from the learner surface. It is a rubric construct, not a learner-facing
  label. Use "tell the difference" or keep it in a details tooltip.

### UX-05 — The result screen is accurate and unkind

"Cold attempt" is internal evidence vocabulary. A learner reads it as "I failed before I started."
"Grading failed" is worse: it describes the system's state as the learner's outcome. "Matches an
accepted answer" is audit language, not feedback.

Keep the honesty: a pass is not mastery, and an open answer that cannot be graded must not advance.
Change the voice:
- "First try, no hints" for `cold`; explain in one line that independent evidence is worth more.
- "We could not grade this answer" for `needs_retry`; the existing "saved, not graded" copy is
  right and should lead.
- "This one is done. Here is what you can do now" instead of "This objective is complete."
- After a pass, show one concrete takeaway and one next action; do not add confetti or a fake
  streak. Warmth without a false mastery claim.

### UX-06 — The Library warns before it welcomes

The Library subtitle says "Packs you can teach from, with the provenance the backend recorded."
The explanatory line says "No marketplace ranking and no verified badge." Both are true and both
read as "this product cannot vouch for anything." A first-time learner does not know what a pack
is or what file to choose.

Concrete fixes:
- Lead with "Courses made by other people" and "You will see the author, sources, and integrity
  before you add one."
- State the accepted input in the import action ("Choose a .zip course pack" or the host-granted
  folder). If the host picker is absent, say that plainly; do not show a button that cannot work.
- Keep the trust labels, but move "no ranking / no verified badge" into a "What we check / what we
  do not check" disclosure. Do not lead with the absence.
- This is also where the second import path belongs: "Have a college syllabus? Start a Student
  companion course" should be visible once H-25/H-27 exist, not buried behind a pack.

### UX-07 — Parent Studio speaks to an architect

"Parent Studio", "brief", and "authored courses" are builder words. The page subtitle explains the
workflow, which helps, but the list rows do not explain why two similar lesson packs exist or what
the parent should do next. The parent is the operator and should not need to understand the
contract.

Use "Lesson plans you prepared for your child", "New lesson plan", "Open plan". Explain the
difference between a parent-authored pack and an imported learner course in one sentence. Keep the
parent-only design and the no-child-chat rule; humanize the frame around them.

### UX-08 — The visual language is coherent but emotionally flat

The "Ink & Field Notes" token layer is real: the M4 gate measured 0 authored contrast failures and
no clipping across 62 frames (`docs/M4-VISUAL-MEDIA-AUDIT.md`). This review is not re-litigating
accessibility. The problem is expressive: text-only surfaces, no illustrations or thumbnails, no
visual rhythm between "read", "practice", and "review", and an almost monochrome status language.
The result feels like a well-built internal tool.

The fix is not a new theme or a gradient. It is composition:
- one illustrated or typographic "lesson cover" per course, even if it is a deterministic
  Field Notes pattern rather than generated art;
- a visible path (units → lessons → checks) with a current marker;
- a small palette of semantic states carried by icon + text, not color alone;
- a calmer empty state with one clear action, not three explanatory paragraphs.

### UX-09 — Scope is present but not understood

`H-02` correctly adds `COURSE_SCOPES` and `planTimingCopy`. The labels are a good start. The screen
still does not say what the learner receives: a single verifiable lesson, a short sequence of a few
sessions, or a multi-unit course that continues past the first generation. The user's own request
was explicitly "depending on the user intention of if it is a one-off short lesson or meant to be a
whole course"; the UI must make that intention a first-class choice and explain the consequence
before the model call, not only after the plan exists.

### UX-10 — Status copy is system copy

`EVIDENCE_CLASS_COPY`, `VERDICT_COPY`, and `NEXT_ACTION_COPY` are accurate and cold. "Grading
failed" should be "We could not grade this answer"; "Cold attempt" should be "First try, no hints";
"Nothing due" is good and should stay. `H-22` already carries the frozen construct-breadth copy;
this card should not rewrite those strings. It should rewrite the learner-voice strings around
them and keep the distinction between "not graded" and "not passed."

## What is working (do not lose it)

- The honesty is real: the UI says when a control is unavailable instead of faking it.
- The empty states explain why they are empty; "the review queue stays quiet until evidence is
  scheduled" is the right instinct, even if the vocabulary is too clinical.
- `H-02`'s plan job state, cancel, retry, and honest "several minutes" copy are the right
  foundation.
- The M4 accessibility gate is strong; contrast, keyboard reachability, text equivalents, and
  forced-colors all have measured evidence.
- The scope enum, level, subject domain, and locale now travel through the product path.

## Host-owned findings

The captured frames show host chrome that the plugin does not own: "Backend ready", "Backend
inference unavailable", `client v0.23.0`, raw gateway addresses, and the session sidebar. These
make the product feel like a development build. They are **not** plugin defects and must not be
"fixed" by patching host chrome. The product answer is a host-level presentation mode (or a
dedicated Desktop environment) that hides infrastructure status from the learner. Record this as a
host integration request; do not put it in a plugin card.

## Card mapping

| finding | card | owner | dependency |
|---|---|---|---|
| UX-01, UX-02, UX-03, UX-06, UX-07, UX-09 | H-28 first-run/create/import humanization | vellum | H-02, H-22 |
| UX-04, UX-05, UX-08, UX-10 | H-29 learning-surface and result-voice pass | vellum | H-28 |
| second import path / student mode | H-25 design, H-26 backend, H-27 UI | atlas/cinder/vellum | H-03, H-02 |
| host chrome | host integration note | operator | not a plugin card |

## Acceptance for the UX cards

- A new learner can answer, from the first screen alone, "what is this, what do I press, and what
  happens next?" — verified by a five-person first-run script, not by the author's opinion.
- A one-off task, a short course, and a full course produce visibly different expectations before
  Create, and the difference is explained in plain language.
- No learner-facing string uses `recipe`, `evidence class`, `cold`, `discrimination`, `provenance`,
  `L0`, or a raw enum unless it is inside an explicitly opened details panel.
- The lesson index shows a current/next marker and an overall progress statement without requiring
  the learner to decode tags.
- A graded pass, a saved-not-graded answer, and a failed grading attempt have distinct, humane
  copy; none implies mastery, and none calls the learner's attempt "cold."
- Screenshots at 1280 px and 460 px, light and dark, plus a keyboard walk, are attached to the card;
  `node --check` and the full suite pass.
- The M4 contrast and a11y claims stay green; this pass does not regress measured accessibility.

## Limits

This review did not run a live Desktop session, did not use a provider, and did not test the
rewritten `H-02` flow visually. The visual judgments are based on captured frames from the
repository plus source anchors; the cards require fresh frames. No publication, tag, or catalog
action was taken.
