# Coursebook: generic home, course worlds, and the tutor rail

Status: plan for owner approval. No implementation has started.
Date: 2026-11-09.
Base: `b9f4a19` on the operator checkout.
Supersedes the relevant home and presentation assumptions in `docs/HOME-HUB-ARCHITECTURE.md`
and `docs/FINAL-POLISH-SPEC.md` only after owner approval. The evidence contract, grading
kernel, and `docs/VISUAL_MEDIA_PLAN.md` media rules remain in force.

## 0. Locked decisions

1. **Home is generic.** The first Coursebook screen is a launcher: choose a course or create a
   new one. It is not a course-bound Continue plate and it does not assume a Japanese course.
2. **The course page is course-bound.** The existing Atlas Lamp trailhead, Continue card, and
   chapter path become the course's own home after a course is chosen. The first Japanese
   concept frame is the reference for that classroom, not for global Home.
3. **Game mode is the default for new courses.** Textbook mode is an explicit alternative.
   Game mode owns a generated course world; Textbook mode does not generate a world.
4. **A course world is subject-specific, not a skin.** Japanese gets a lantern district. A head
   gasket course gets a service-bay and workshop-manual world. Astronomy gets an observatory.
   The same page composition and Coursebook type system stay; the art direction and motifs
   change with the subject.
5. **Production art is textless.** Generated images are art plates, not screenshots of a UI.
   All headings, labels, card names, buttons, progress and citations are real DOM text. This
   fixes the garbled placeholder text in the concept frames and keeps generated images from
   pretending to be authoritative UI.
6. **Game world art is orientation, not evidence.** It may establish place, subject and mood.
   It may never carry a torque value, clearance, sequence, measurement, safety instruction, or
   answer. Those remain deterministic schematics, sourced references, or authored prose.
7. **The right rail is a lesson-bound tutor, not a general Hermes agent.** It is scoped to the
   active course, objective and block. It has no shell, browser, file, or authoring tools.
8. **Textbook mode generates no artwork.** It may still render deterministic schematics or
   sourced figures that an existing lesson already requires; those are instructional media,
   not a generated world. If "textbook" must mean literally no graphics at all, that is a
   separate `text_only` setting, not a silent removal of a head-gasket diagram.

## 1. What changes in the product

The current product has four ideas in the wrong places:

| Current surface | Current job | Problem | New job |
|---|---|---|---|
| `Home` / `FieldDeskHome` | Continue plate for one selected course | The first screen belongs to a course before the learner has chosen one | Global Coursebook launcher: course shelf plus create |
| Course page | Atlas trailhead and path | This is the right course-bound experience, but it is being used as the global Home | Keep it as the course's own home |
| Coursebook pane | Context facts for the focused chat | It says "Not a Coursebook lesson" and is not the learner's help surface | Lesson-bound tutor rail |
| Game / Guided / Textbook | Three lesson rendering views | Game is a view name, not a generated environment; Textbook still has no clear relationship to the world | Game and Textbook become course-level modes; Guided remains a lesson view |

The rest of the harness does not change. A course still has one validated document. It still has
typed checks, evidence, attempts, sources, and transitions. The visual layer never creates a
second learning state.

## 2. Global Home: the field library

### 2.1 Purpose

The learner opens Coursebook and answers one question: **what do I want to learn now?**

The home is a library and a threshold, not a dashboard and not a course page.

### 2.2 Composition

Wide layout, top to bottom:

1. **Header**: Coursebook mark; navigation `Home`, `Courses`, `Workshop`, `Parent Studio`;
   settings in the header. No second primary button.
2. **Invitation**: display-serif headline `What will you learn next?` and one short line:
   `Pick a course, or chart a new one.`
3. **Primary action**: one filled `Start a new course`.
4. **Secondary path**: one text link `Browse the library`.
5. **Your courses**: a horizontal shelf of course cards, each with:
   - subject-specific cover or paper cover;
   - course title;
   - last touched / next section;
   - mode badge (`Game` or `Textbook`);
   - one `Open` action. The whole card is the target; it is not a row of admin controls.
6. **No courses**: an honest empty state: `No courses yet. Start with a goal, or browse a
   ready-made course.` The same two actions remain.
7. **Loading, error, offline**: preserve the shelf geometry; name the failed read; never show
   an empty library in place of a failed read.

The shelf is capped and scrolls; it is not a grid of equal admin cards. Four to six cards is the
first viewport. A `See all` link opens `Courses`.

### 2.3 What Home does not show

- No `Continue` hero for a course the learner has not selected.
- No Japanese lesson scene, Japanese vocabulary, or Japanese-specific illustration.
- No fake "recently played", invented learner, streak, XP, level, or mastery percentage.
- No unlabeled generated cards. Every card's image is either a course cover with provenance or
  a paper cover with type and a subject mark.
- No second "Create" control on the shelf. The top primary is the only create action.

### 2.4 Course page, not Home

Selecting a course opens its **course home**:

- the existing trailhead: course title, what the learner can now do, one Continue;
- the route and current/next checkpoint;
- the course world hero;
- the mode badge and a quiet `Course settings` action.

This is where the Japanese concept frame belongs. It is a course-bound screen. The global Home
never borrows it.

## 3. Modes and switching

### 3.1 Mode model

There are two **course modes**:

| Mode | New course behavior | Lesson rendering | Art behavior |
|---|---|---|---|
| **Game** (default) | Plan plus a generated course world | Field Quest by default; Guided and Textbook remain available as lesson views | One approved world kit, plus only instructional media the lesson policy permits |
| **Textbook** | Plan only | Textbook by default; Guided remains available | No generated world art; existing deterministic/sourced instructional media may render |

`Guided` remains a **lesson view**, not a third course world. It is the low-distraction,
one-block-at-a-time reading view. A learner can choose it from the lesson without converting the
course or generating art.

### 3.2 Where mode lives

The current `defaultMode` in `desktop/plugin.js` is device preference, not course identity. The
new course mode must be durable on the course because a world is attached to that course.

- Add nullable `courses.presentation_mode` with values `game` / `textbook`.
- Existing courses read as `textbook` until a world is approved. There is no backfill that
  pretends an old course has a world.
- New courses created by the UI send `presentation_mode: "game"` unless the learner picks
  Textbook.
- Keep the existing local `defaultMode` for "what a new course starts as" and for per-classroom
  view overrides. Do not confuse it with the course's durable mode.

### 3.3 Switching from Textbook to Game

The learner may ask to switch at any time after the plan exists.

1. The mode control opens a dialog:
   `Game mode needs a course world. This course was built in Textbook mode. Generate a world
   for it now?`
2. Actions: `Generate a game world` (primary), `Keep Textbook` (secondary), `Cancel` (tertiary).
3. If the course already has an approved world, the dialog becomes:
   `This course already has a world. Switch to Game mode?` with `Switch` and `Keep Textbook`.
4. If there is an unapproved world, the dialog says so and opens the World Studio; the course
   remains Textbook until final visual approval.
5. If the image provider is unavailable, the dialog says:
   `Game mode is not available right now because the image provider is not configured. The
   course stays in Textbook mode and your lessons are unchanged.` No fake world is created.
6. Switching never rewrites objectives, checks, attempts, evidence, or lesson text. It only
   changes presentation and, when needed, starts a world-generation job.

### 3.4 Switching from Game to Textbook

This is immediate. The course keeps its world and assets; the UI hides them and renders the
Textbook view. Switching back to Game reuses the approved world if it is still valid. No
deletion and no regeneration happen silently.

### 3.5 World freshness

If the plan is re-approved with new objectives after a world exists, mark the world `stale` only
when the subject or section set changed. Keep the existing approved art visible; show a quiet
`This world was built for the previous plan` line and offer `Review the world` or `Generate new
section cards`. Never block the learner from reading the existing lessons because art is stale.
A new course with no approved world is the only case that cannot enter Game mode.

## 4. The course world

### 4.1 What a world is

A world is a small, governed visual kit attached to a course:

- `world_hero`: the course home image;
- `world_cover`: the library card image;
- `world_section`: one image per section, up to six, used as section-card art;
- optional `lesson_scene`: one image for a lesson that genuinely benefits from place, never a
  replacement for instructional media.

A world is not a full UI screenshot and not a course document. It is a set of textless plates
plus a style specification. The renderer composes them with real type and real controls.

### 4.2 World brief

The backend builds a typed `world_brief` from the approved plan, not from a single keyword:

```
{
  "course_id": "...",
  "title": "...",
  "subject_domain": "technical_procedure",   // advisory, normalized
  "end_capability": "Replace a head gasket ...",
  "audience": "adult learner",
  "level": "novice",
  "locale": "en-US",
  "tone": "practical, calm, competent",
  "safety_class": "workshop",                 // drives the technical rules
  "motifs": ["service bay", "torque wrench", "head gasket", "shop manual"],
  "forbidden": ["brand logos", "invented torque values", "text", "UI chrome"],
  "candidate_styles": ["service_manual", "workshop_bench", "cutaway_atlas"]
}
```

`motifs` come from the plan's objectives, section titles, and fetched sources. `forbidden` is
always at least: no text, no logos, no UI, no watermark, no invented measurements.

### 4.3 Subject visual grammars

The policy chooses a **visual grammar**, not a generic fantasy skin. The user may edit the
choice before approval.

| Grammar | Best fit | Motifs | Cannot do |
|---|---|---|---|
| `field_atlas` | languages, humanities, general learning | maps, lanterns, travel desk, field notebook | pretend a map is a real geography lesson |
| `workshop_manual` | auto repair, trades, engineering procedures | service bay, tool wall, blueprints, exploded parts | show a torque value, clearance or sequence as art |
| `observatory` | astronomy, physics, natural science | star charts, instruments, night sky, observation log | use an AI sky image as a measurement |
| `kitchen_table` | cooking, home skills, food | recipe cards, ingredients, work surface | imply a generated dish is a tested recipe |
| `archive_desk` | history, law, business, research | documents, stamps, maps, index cards | invent a source or a quotation |
| `studio_bench` | art, music, design | materials, swatches, instrument, sketchbook | present a generated artwork as a technique authority |
| `lab_bench` | biology, chemistry, lab safety | glassware, lab notebook, labeled stations | use art as a safety or measurement reference |
| `instrument_board` | mathematics, logic, symbolic work | instruments, graph paper, blackboard | generate an AI illustration for a symbolic concept |

The default for an unknown subject is `field_atlas`, because it is the Coursebook house style.
That default is a starting point, not permission to use lanterns for a head gasket.

The policy is deterministic and testable:

- `subject_domain`, evidence target, recipe and safety class narrow the candidate grammars;
- the plan text supplies motifs;
- a teacher or learner can choose another grammar in World Studio;
- a technical-procedure course cannot select a grammar whose only output is decorative fantasy;
- a symbolic course cannot make an AI illustration a required lesson visual.

### 4.4 Art direction quality rules

Every generated world plate is reviewed against these rules before it can be approved:

1. **Textless.** No letters, words, labels, numbers, logos, watermarks, or UI. Real text is DOM.
2. **Subject-specific.** At least two motifs come from the course's own plan or sources. A
   subject-swap test must fail: if the same plate could serve a cooking course and a car-repair
   course, reject it.
3. **Consistent.** One palette, medium, line weight and light direction across hero, cover and
   section cards. The selected concept is the reference for the kit.
4. **Legible underneath type.** The plate leaves a quiet field for the headline and controls;
   no essential information is only in the image.
5. **Safe.** No depicted procedure, torque, measurement, wiring, medication or hazard as
   authority. Technical instruction remains text, deterministic SVG, or a sourced reference.
6. **Honest.** The image has a provenance row: provider, model, prompt hash, style hash,
   generation time, and `role = orientation`. It is never labeled "verified", "accurate", or
   "manual".
7. **Accessible.** Every plate has alt text and a text equivalent. The page works at 460 px,
   200% text, keyboard only, reduced motion and with images disabled.
8. **Useful.** The world encodes the subject and the course's shape. Decoration that could be
   removed without changing orientation is rejected.

### 4.5 World asset budget

The first release allows at most:

- three low-resolution concept boards per generation attempt;
- one hero, one cover, and one card per section, capped at six sections;
- at most two optional lesson scenes for a course;
- no image per block, per paragraph, or per check;
- no image generated merely because a section exists if the section card already carries its
  identity.

The cap is enforced by the backend, not by UI discipline. A retry reuses cached concepts and
assets; it never pays twice for the same `style_hash + course_hash + role + section_id`.

### 4.6 Concept generation and final approval

Game-mode creation uses two visual checkpoints:

**Style check**

- Generate three textless concept boards from the same world brief, each with a different
  visual grammar or palette path.
- Each board shows a hero crop, a section-card crop, and a palette strip, all as art only.
- The learner chooses one, edits the brief, or asks for another set.
- This is not final approval. The course is still in Textbook fallback.

**World check**

- From the selected style, generate the actual hero, cover and section cards, using the selected
  board as a reference.
- Show the assembled course home and shelf card with real UI text over the art.
- The learner presses `Use this world` (final visual approval) or `Edit direction` / `Try
  another`.
- Only after this approval does the game-mode lessons job run.
- If the provider fails after the style approval, keep the approved style and report exactly
  which assets are missing; do not approve a partial world or fabricate files.

The plan approval and the world approval are separate facts. A game course needs both before
lesson generation. The UI may present them as two panels of one review screen, but neither
silently approves the other.

### 4.7 Prompt construction

The prompt builder is code, not prose invented per call:

```
world_brief + selected visual grammar + palette + medium
+ required motifs from the course
+ composition and negative-space needs
+ hard negatives: no text, no letters, no UI, no logo, no watermark,
  no invented measurements, no depicted safety procedure
+ output role (hero / cover / section / scene) and aspect ratio
```

The model never sees the answer key, checks, rubric, or learner attempts. The generator receives
the course title, subject, end capability, section titles and approved source motifs only.

### 4.8 Technical courses: the head-gasket rule

A head-gasket course is the acceptance test for general-purpose quality, not a Japanese variant.

- The world is a service bay / workshop manual: car on a lift, tool wall, clean bench, manual
  pages, component trays.
- The **procedure** renders as numbered steps, tool and part lists, hazards and a stop
  condition.
- The **torque sequence and part orientation** are deterministic SVG from structured facts, or a
  sourced manual figure with permission. They are never an AI illustration.
- Generated art may sit beside the procedure for orientation. It cannot show a torque pattern
  as authority, cannot invent a clearance, and cannot replace a hazard callout.
- The tutor can explain a concept, but it cannot invent a procedure or certify physical work.
- A completion check is a verification checklist, not a quiz; the UI labels self-reported
  physical completion honestly.
- Textbook mode still shows the deterministic/sourced diagrams needed for the procedure; it
  generates no world art.

## 5. World Studio

### 5.1 Entry

World Studio is reached from:

- a new Game-mode course after its draft plan is ready;
- `Course settings → Generate a game world` on a Textbook course;
- `Course settings → Review world` on an existing Game course.

It is not a separate top-level destination. It is a step in the course's setup and a settings
surface afterward.

### 5.2 Screen

1. **Header**: `Choose the world for this course`; course title; `Game mode` label.
2. **What the course is**: one short subject line and the end capability, taken from the plan.
3. **Three concepts**: each a textless art board with a name, a one-line description, palette
   chips, and `Use this direction`. The primary is the recommended grammar; the others are real
   alternatives, not random noise.
4. **Edit direction**: setting, mood, palette, art medium, motifs to include, motifs to avoid.
   These fields update the next concept generation; they do not edit the lesson.
5. **Textbook fallback**: `Use Textbook mode` remains available and creates no art.
6. **Final world**: once the kit exists, the same screen becomes a preview with the real course
   home and shelf card, `Use this world`, `Try another`, and `Edit direction`.

### 5.3 State matrix

| State | What the learner sees | Action |
|---|---|---|
| No plan | `The plan is being written; the world comes after it.` | Review the plan when ready |
| Concepts generating | Three art placeholders with a real job stage | Cancel / wait |
| Concepts ready | Three boards | Choose, edit, try another, use Textbook |
| Style selected, kit generating | Selected board plus per-asset progress | Cancel / wait |
| Kit ready | Real course home and shelf card | Use this world / edit / try another |
| Approved | `This world is approved.` and `Change world` | Change / switch to Textbook |
| Provider unavailable | `Game mode is unavailable because image generation is not configured.` | Keep Textbook / retry |
| Partial failure | Missing roles named; no fake images | Retry missing / use Textbook |
| Stale plan | Existing art stays; `Built for the previous plan` | Review / generate new section cards |

Every state has one primary action. The learner is never trapped in a spinner with no exit.

## 6. Creation flow

### 6.1 Game mode (default)

1. **Goal.** Existing stage 1. The learner says what they want to be able to do.
2. **Shape.** Existing stage 2: one lesson / short course / full course, plus recipe and dials.
   Add one mode control:
   - `Game` (default): `Build a visual world around this course.`
   - `Textbook`: `Text-first. No generated world.`
   The mode control is one choice, not a second primary action.
3. **Review.** Existing stage 3 preview. It now names the mode, the plan size, and the first
   stop. `Create course` remains the only mutation.
4. **Plan.** Course and draft plan are created as today. The plan job runs.
5. **Plan review.** The learner approves or edits the plan. No lesson is written before this.
6. **World Studio.** Triggered automatically when a Game course has a draft plan; three
   concepts generate. The learner chooses a style, edits it, and finally approves the world kit.
7. **Build.** After plan approval and world approval, one `Build the course` action queues the
   lessons job. It shows real stages; no fake percentage.
8. **Course home.** The course opens on its world hero, Continue, and route.

If the learner exits before world approval, the course stays in Textbook fallback and says
`World not approved yet`; reading the plan is still possible. No lesson is fabricated.

### 6.2 Textbook mode

1. Goal.
2. Shape plus `Textbook` mode.
3. Review; `Create course`.
4. Plan job and plan approval.
5. Lessons job; no world job, no image generation, no world art.
6. Course home and Textbook lesson view. Guided remains available as a lesson view.

### 6.3 Existing Textbook course

See §3.3. The course's current plan, lessons, attempts and evidence are untouched. If the
learner approves a world, the course can switch to Game presentation using the existing
content; no lesson regeneration is required.

### 6.4 Pack and imported courses

A pack may have no world. It opens in Textbook mode. A learner may request a world for it after
the plan is available, using the same World Studio. Pack contents and evidence are unchanged.
World art is local to the profile in the first release and is not exported in packs or course
exports.

## 7. Tutor rail

### 7.1 What it is

The right rail is a **lesson tutor**, not a general chat and not the authoring agent.

- It is bound to the active `course_id`, `enrollment_id`, `objective_id` and lesson run.
- It knows the current section, the current block, the check state and the selected excerpt.
- It answers about this lesson; if it goes outside the lesson, it labels that as general
  background.
- It cannot grade, advance, unlock, rewrite, export or call tools.

The existing right-side Coursebook pane becomes the rail. The old `CoursebookPane` reads the
focused chat's binding; that is the wrong identity for a learner tutor. The rail reads the
active lesson run instead. When no lesson is active it shows:

`Open a lesson to ask the tutor.` with `Open Coursebook`.

It never says "Not a Coursebook lesson" to a learner.

### 7.2 Chat architecture

The rail is a Coursebook-owned chat surface backed by a `tutor.ask` backend command. It is not a
second Hermes agent chat.

Why this direction:

- The host has no embedded chat component in the plugin SDK. A text box that secretly submits to
  the focused host chat would create two chats and the wrong binding.
- A lesson tutor needs a narrow context envelope, no tools, and durable per-run turns. Those are
  Coursebook responsibilities.
- The existing authoring chat remains the builder's chat. The learner's tutor is a different
  product surface with a different policy.

First slice:

- non-streaming answer with a visible `Thinking` state and cancellation;
- one thread per lesson run;
- persisted turns in the plugin database;
- no web, shell, browser, file or authoring tools;
- citations to the lesson block and source ids;
- a clear `Tutor` header with the current objective;
- the conversation remains readable after reload.

If the host later exposes a dockable chat surface, the renderer can be swapped without changing
the context or persistence contract.

### 7.3 Selection to ask

This is the deliberate interaction that replaces copy and paste.

- **Select a phrase in lesson text.** After a completed selection, a small `Ask tutor` pill
  appears near the selection. It does not appear on a single click or a hover.
- **Press `Ask tutor`.** The rail opens with the excerpt attached as a quote chip in the
  composer. It does not send automatically.
- **Type the question and press Ask.** The selected text and its block id travel with the
  question.
- **Quote chip.** It can be removed; clicking it highlights the source block. The learner can
  select a word, a sentence or a whole passage.
- **Keyboard.** `Ctrl+J` / `Cmd+J` focuses the tutor. With a selection, `Ctrl+Shift+E` opens the
  quote in the rail. `Escape` dismisses the pill.
- **No clipboard.** The selected text is passed in context; the learner never has to copy it.
- **No auto-send.** The extra press is the protection against misclicks.

### 7.4 Word-level help

Not every word is a chat trigger.

- Authored vocabulary and glossary terms carry a dotted underline and a real button target.
- Clicking one opens a compact inline card: reading, gloss, pronunciation where the lesson
  supplies it, and `Ask more`.
- `Ask more` moves the term into the rail with the quote chip.
- For non-language courses, the same treatment applies to named concepts the lesson authors as
  glossary items; headings and paragraphs also carry a quiet `Explain this` control.
- No hover-only card, no click on arbitrary prose, no tooltip that covers the next paragraph.

### 7.5 What the tutor may do

- define a word or term in the lesson's context;
- translate or explain a phrase, with the lesson's scaffold level;
- explain grammar, a concept, a mechanism or a step;
- give another example or a different representation;
- ask a checking question or offer a hint ladder;
- rephrase the lesson's explanation;
- point to the source or block that supports an answer.

On an open check:

- a hint request is explicit and is recorded through the existing assist/evidence path;
- the tutor does not reveal the final answer while the check is open;
- after an attempt, it can explain the result and the misconception;
- it never says "you passed" or writes a verdict;
- the grader continues to read learner attempts, never tutor prose.

For a procedure lesson, the tutor uses the authored steps and sources; it does not invent a
torque, clearance, sequence or safety step. For a question outside the lesson, it may answer as
general background, clearly labeled, but it does not pretend the lesson supports it.

### 7.6 Rail layout

- 340-380 px wide at desktop; resizable within a bounded range; collapsible.
- Header: `Tutor`, fox mark, course/objective line, and a context chip.
- Body: quiet reading width, no giant chat bubbles; citations are inline links.
- Composer: `Ask about this lesson...`; quote chip above the field; `Ask` primary; no `Ask
  anything` placeholder.
- Suggested prompts are lesson-specific: `Explain this grammar`, `Give another example`,
  `Why is this wrong?`.
- At 460 px the rail becomes a bottom sheet; the lesson never shrinks below a readable measure.
- The fox is a quiet companion in the header or empty state; it never replaces a control or a
  progress marker.

### 7.7 Practice is a mode of the rail

A conversation-practice check is not a second chat. When the open check declares practice, the
rail header gains one `Practice` mode beside `Ask`:

- `practice.start` opens the authored scene and the tutor's opening turn in the rail;
- learner turns are sent through the existing `practice.*` commands;
- the tutor's in-character reply appears in the same thread;
- `practice.end` hands only the learner turns to the existing grader;
- the tutor's prose is never graded and cannot produce a pass;
- if no practice backend is available, the rail says `Practice is not available in this
  build` and keeps Ask usable;
- the learner can leave Practice and return to Ask without losing the lesson.

Learner mode does not keep a second host lesson chat beside the rail. The authoring chat remains
the builder's chat in Studio; the learner's practice and questions both live in the rail.

### 7.9 Tutor states

| State | Surface | Action |
|---|---|---|
| No lesson | `Open a lesson to ask the tutor.` | Open Coursebook |
| Loading context | `Reading this lesson...` | Cancel / wait |
| Ready | Composer and recent turns | Ask |
| Offline/unavailable | `The tutor is unavailable. The lesson is still readable.` | Retry |
| Provider failure | `The tutor could not answer. Nothing was graded.` | Retry |
| Lesson changed | `This thread belongs to the previous section.` | Start a new thread / read old |
| Check open | Hint policy notice | Ask for a hint |
| Completed lesson | `Review this lesson with the tutor.` | Ask |

No failure may look like an empty thread or a fabricated assistant answer.

## 8. Fit with the existing Coursebook architecture

### 8.1 Preserved

- One validated lesson document shared by Game, Guided and Textbook.
- Typed checks, attempts, evidence classes, grading lanes and transitions.
- Source ledger and provenance.
- `LessonCapabilityPolicy` for instructional media.
- Deterministic schematics for technical procedures.
- Existing artifact store, content-addressed cache, MIME policy and text fallback.
- Existing plan approval and lesson-generation gate.
- Parent Studio as the parent's authoring space; no child-facing tutor.

### 8.2 New separation

- **Instructional media** remains a child of a lesson block and is judged by
  `LessonCapabilityPolicy` and the evidence target.
- **World art** is a course-level orientation asset and is judged by `WorldPolicy`; it is not a
  lesson block and cannot carry evidence.
- **Tutor chat** is a lesson-bound conversation; it is not an attempt, grade or transition.
- **Global Home** is a library read model; **course home** is the existing trailhead.

### 8.3 Code surfaces

Backend:

- `coursebook/world.py`: `WorldBrief`, `WorldGrammar`, `WorldPolicy`, prompt builder, quality
  checks, cache key.
- `coursebook/tutor.py`: context envelope, tutor prompt, turn persistence, citation extraction.
- `coursebook/domain.py`: handlers for mode, world and tutor commands.
- `coursebook/artifacts.py` and `coursebook/media.py`: reuse the artifact store and host media
  adapter; no second media path.
- `coursebook/generation.py`: the game-mode lessons gate; no lesson media is promoted to world
  art.

Desktop:

- `CoursebookHome`: global library launcher.
- `FieldDeskHome`: course-bound trailhead (existing, with a world hero).
- `WorldStudio`: concepts, edit, kit preview, approval.
- `CourseModeDialog`: Textbook-to-Game prompt and Game-to-Textbook switch.
- `TutorRail`: chat surface, quote chip, context header.
- `SelectionAsk`: deliberate selection pill.
- `GlossaryMark`: authored terms and inline definition card.
- `WorldHero`, `WorldCover`, `WorldSectionCard`.

Host:

- existing `HostMedia` / `image_generate` path for art;
- `ctx.llm` for the tutor;
- no provider keys in the plugin;
- no new host chat requirement for the first slice.

## 9. Data and contract plan

### 9.1 Migration 0013: course worlds

```
ALTER TABLE courses ADD COLUMN presentation_mode TEXT; -- NULL reads as textbook
CREATE TABLE course_visual_worlds (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  state TEXT NOT NULL,
  brief_json TEXT NOT NULL,
  concepts_json TEXT NOT NULL,
  selected_concept_id TEXT,
  style_hash TEXT,
  kit_hash TEXT,
  final_approved_hash TEXT,
  final_approved_at TEXT,
  error_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(course_id, revision)
);
CREATE TABLE course_visual_assets (
  id TEXT PRIMARY KEY,
  world_id TEXT NOT NULL,
  role TEXT NOT NULL,
  section_id TEXT,
  artifact_id TEXT NOT NULL,
  style_hash TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  textless INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(world_id, role, section_id)
);
```

`state`: `not_requested`, `concepts_generating`, `concepts_ready`, `style_selected`,
`kit_generating`, `kit_ready`, `approved`, `failed`, `stale`, `unavailable`.

The world is course-level, not enrollment-level. Two enrollments on one course share the
course's visual identity; they do not share attempts or progress.

### 9.2 Migration 0014: tutor threads

```
CREATE TABLE tutor_threads (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  enrollment_id TEXT NOT NULL,
  objective_id TEXT NOT NULL,
  lesson_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE tutor_turns (
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  role TEXT NOT NULL,          -- learner | tutor
  text TEXT NOT NULL,
  block_id TEXT,
  selected_text TEXT,
  source_refs_json TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(thread_id, ordinal)
);
```

Tutor turns are learner-owned and are excluded from pack and course exports. They are not
attempts and never enter evidence.

### 9.3 Contract additions

Use `cb.rpc` v21 for the world/mode surface and v22 for the tutor surface, or one additive v21
if the build is shipped together. Keep `cb.jobs` unchanged by using the existing `media` job
family with explicit `stage` values:

- `visual.world.read`
  - request: `course_id`
  - response: `course_id`, `presentation_mode`, `world` or null, `fallback`, `revision`
- `visual.world.generate`
  - request: `course_id`, `stage` (`concepts` / `kit`), optional `style_id`, optional
    `brief_patch`, `expected_revision`
  - response: `job_id`, `state`, `world_id`
  - queues `kind=media`, `brief.stage=world_concepts` or `world_kit`; no new job kind
- `visual.world.approve`
  - request: `course_id`, `world_id`, `stage` (`style` / `final`), `expected_revision`,
    idempotency key
  - response: `world` state, `style_hash`, `kit_hash`, `assets`
  - style approval records the selected concept; final approval accepts the actual kit and
    freezes `final_approved_hash`
- `course.mode.set`
  - request: `course_id`, `mode` (`game` / `textbook`), `expected_revision`, idempotency key
  - response: `mode`, `world` state, `requires_world` boolean
  - `game` without an approved world returns `requires_world=true` and a reason; it never
    silently changes the mode
- `tutor.ask`
  - request: `course_id`, `enrollment_id`, `objective_id`, `lesson_run_id`, `question`,
    optional `block_id`, optional `selected_text`, `expected_revision`
  - response: `turn`, `thread_id`, `citations`, `assist` (nullable), `state`
- `tutor.history`
  - request: `course_id`, `enrollment_id`, `objective_id`, `lesson_run_id`
  - response: `thread_id`, `turns`, `context`

All mutating methods carry `expected_revision` and idempotency where they can spend provider
money. Reads are GET-shaped and never generate art.

### 9.4 Jobs and approvals

- Game mode, plan approved, world not approved: no lessons job.
- `visual.world.generate` is a `media` job. It writes artifact bytes before DB rows; retry uses
  the cache key and never double-spends.
- Plan approval stays the content gate; final world approval is the visual gate.
- `Build the course` requires both for Game mode.
- A Textbook course has no world gate.
- A failed world job leaves the course in Textbook fallback; no fake world and no silent lesson
  build.

### 9.5 Pack and export

First release: world art is local to the profile and is **not** included in `cb.pack` or
`course.export`. Packs carry teaching content, checks and sources. A future pack version may
carry world art with explicit provenance and licences; that is a separate contract decision.
Tutor turns are never exported.

Take-home packs are a separate print artifact, not `cb.pack`. They may use the source lesson's
approved world plates as **captioned orientation** when the pack's visual proof approves them and
the provenance is recorded. They never use generated art as a procedure, answer or safety
authority, and they never include tutor turns or private history.

## 10. General-purpose acceptance matrix

The generator is accepted only if all rows preserve quality. The Japanese row is one row, not
the template.

| Course | World grammar | Required instructional visual | Must not do | Acceptance |
|---|---|---|---|---|
| Japanese L0 cafe lesson | `field_atlas` / lantern district | pronunciation/reference audio if the objective needs it; vocabulary gloss | turn the page into a Japanese-only skin; garble labels; auto-generate narration because locale is set | Course home uses the Japanese concept reference; word glossary and quote-to-tutor work; no images with fake text |
| Head gasket replacement | `workshop_manual` / service bay | deterministic torque/sequence schematic or sourced manual figure; tool and hazard list | show a torque value or sequence as AI art; omit safety stop; imply physical work was independently verified | Procedure renders with steps, hazards, tools, sourced reference; AI art only orientation; checklist is verification, not a quiz |
| General auto repair | `workshop_manual` or `archive_desk` for history/service records | diagrams/tables from structured facts | generic fantasy map; invented part numbers; brand marks | World reads as a workshop; source cards; no decorative map |
| Astronomy | `observatory` | star chart/data diagram from facts | AI sky image as measurement; constellations without source | Night-sky world; deterministic diagrams; citations |
| Sourdough | `kitchen_table` | timeline/process diagram if needed | generated dish as tested recipe; fake temperatures | Warm kitchen world; process steps and safety notes; no fabricated values |
| Mathematics | `instrument_board` | deterministic graph/worked example | AI illustration for a symbolic concept; decorative "magic" | No AI visual authority; graph/worked example; world art is quiet and optional |
| History source analysis | `archive_desk` | document/source image with provenance if permitted | invent a quotation or document | Archive world; source cards; no fabricated evidence |
| Parent lesson | parent's authoring surface; optional `field_atlas`/subject grammar | parent guide and activity props, not child chat | child-facing tutor; generated image presented as child-safe | Parent approves sources and world; child does not chat |

The **anti-generic test** is mandatory: take the generated world brief and swap the subject to
an unrelated field. If the same art and motifs still pass, the world is rejected. The visual
grammar and at least two motifs must change.

## 10A. Parent Studio, take-home packs, and homework

### 10A.1 Product job

The Parent Studio is the adult's preparation and take-home surface. It must be usable in two
ways:

1. **Author a new parent-led lesson** through the existing `recipe=parent` brief.
2. **Open a lesson that already exists** in a Game or Textbook course, inspect its validated
   content, and turn it into a high-quality take-home pack or activity plan.

The parent is always the operator. There is no child account, child chat or child-facing tutor
surface in this flow. Adult learners also get the same take-home task generator from their own
lesson; this is not a parent-only capability.

### 10A.2 Parent Studio source picker

Add a second entrance, not a second studio:

- `My lesson plans` keeps the existing Parent Studio authoring list.
- `Take-home from a lesson` opens a picker over `library.list` rows, including Game and Textbook
  courses and imported packs.
- Select a course, then a section and its validated lesson. Show a read-only preview:
  objective, lesson blocks, sources, existing diagrams, and the current world art if the course
  has one.
- Choose:
  - `Print a take-home pack` for a parent to teach from;
  - `Prepare an activity plan` for a short parent-led activity;
  - `Send with homework` for one real-world practice task.
- The source course is not cloned, rewritten, re-approved or enrolled. The pack binds to
  `source_course_id`, `source_objective_id`, `source_lesson_version` and `content_hash`.

### 10A.3 Take-home pack

A take-home pack is a rendered artifact, not a second course:

| Part | Content | Rule |
|---|---|---|
| Parent guide | objective, materials, preparation, script, questions, what to notice | written for the adult; no child persona |
| Learner page | one activity, one target, one success criterion | no answer key, no grading, no fake score |
| Answer guide | expected responses, common errors, next step | separate file/page; parent-only |
| Visuals | optional world art and existing instructional diagrams | captioned; generated art is orientation, not authority |
| Sources | title, URL, access date, support label | only recorded sources |
| Homework | one real-world task with a small completion record | self/parent-reported, never a grade |

Pack rules:

- The pack uses the source lesson's exact text and check content; it does not regenerate the
  lesson merely to print it.
- Parent edits are allowed in the pack draft and invalidate the pack approval, not the source
  course.
- Export requires an explicit preview and final approval of the actual pages.
- PDF and print CSS must use selectable text, low-ink layout, real margins, page breaks, alt
  text, and no color-only answers. A proof page is part of acceptance.
- World art in a print pack is textless and captioned; any technical diagram is deterministic
  or sourced, never an AI illustration.
- The pack never contains attempts, learner notes, tutor turns, private observations or child
  data that was not deliberately authored into the pack.

### 10A.4 Homework and away-from-screen practice

Homework is a first-class, small object, not a hidden chat request.

```
homework_task
  id
  course_id
  enrollment_id
  objective_id
  source_lesson_version
  audience          learner | parent
  task_kind         real_world_use | observe | label | practice | make | teach_back
  title
  target            the exact word, phrase, concept or action
  context           where/when the learner will use it
  steps[]           at most three short steps
  success_criterion one observable sentence
  estimated_minutes 3 to 10
  state             proposed | assigned | self_reported_done | parent_reported_done | skipped | expired
  created_at
  completed_at
```

Rules:

- The generator proposes homework only when the objective's evidence target or lesson intent
  supports transfer, production, procedure or observation. It does not attach a generic task to
  every lesson.
- One task, one target, one context. "Practise for ten minutes" is not a task.
- The task can be printed, saved to the notebook, or exported as a one-page take-home sheet.
- There is no external send without an explicit channel and confirmation. Printing and
  downloading are local actions.
- Completion is `self_reported` or `parent_reported`, never independent evidence and never a
  mastery claim. It may be followed by a retrieval check in the course.
- A parent can record an observation; an adult learner can record their own completion. Neither
  is graded.
- No surveillance, photo requirement, geolocation, streak guilt or penalty.
- Game mode may award engagement XP for completing an assigned task, but the completion record
  remains self-reported and the XP is never shown as learning evidence.

### 10A.5 Japanese examples for the demo

The Japanese L0 course should ship a small, source-checked set of away-from-screen tasks:

- Before a meal, use the customary pre-meal greeting; after a meal, use the post-meal greeting.
  The lesson names the phrase, reading and register, and the task asks the learner to use it at
  one real meal and note the context. The task is practice, not a claim of cultural mastery.
- Label three household objects with the target-language words used in the lesson, then say each
  label aloud when passing it for two days.
- Ask one shop or cafe question from the lesson in a real interaction if the learner is
  comfortable; otherwise rehearse it aloud and record a self-report.

The phrases and readings must come from the course's sourced material at authoring time. The
plan does not make an unsourced cultural claim.

### 10A.6 Adult learner path

On any lesson, a quiet `Take this with you` action opens the same homework generator. The learner
can:

- accept one task, edit the context, or skip it;
- save it to the notebook;
- print or export a one-page sheet;
- mark it done or skipped later;
- ask the tutor for a reminder of the phrase, not for a grade.

The action is available in Game, Guided and Textbook modes. It is not a reason to leave the
lesson or start a chat.

### 10A.7 Acceptance

- A parent can open an existing Game course, preview a section, generate a take-home pack, and
  export a print-ready PDF without changing the source course.
- A parent can open an existing Textbook course and do the same; no world art is required.
- A learner can generate and print one homework task from a Japanese lesson.
- A head-gasket take-home pack keeps the procedure diagram deterministic or sourced and never
  presents an AI image as a torque or safety authority.
- Completing homework writes `self_reported` or `parent_reported`, not a pass or mastery.
- The learner page has no answer key; the answer guide is a separate parent artifact.
- A print proof exists at A4/Letter, with no clipped text and no color-only meaning.

## 10B. Game-mode engagement layer (owner override)

### 10B.1 Recorded override

The owner has explicitly decided that game mode may use XP, levels, progress bars and collectible
feedback because the mode must be engaging and fun, not a textbook with a skin. This overrides
the earlier learning-research prohibition **for game mode only**. The override is recorded here
and must be reflected in the quality documents and tests rather than hidden as an exception.

The override does not permit false learning claims. It separates **play progress** from
**learning evidence**:

- XP, levels and game bars are a play/engagement layer.
- Attempts, checks, evidence classes, review dates and source support remain the learning
  record.
- No screen may call XP "mastery", "proficiency", "verified skill" or an equivalent.
- No parent, teacher, pack or export may treat XP as evidence.
- No core lesson is locked behind XP; evidence and the course plan still decide access.
- No purchase, loot box, energy, gambling or pay-to-win mechanic.
- No loss-framed streak or guilt copy. A missed day is not a damaged save.

### 10B.2 Allowed mechanics for the first Game slice

| Mechanic | Allowed use | Not allowed |
|---|---|---|
| XP | Derived from graded evidence only: base by evidence target (recall 4, comprehension 6, discrimination 8, production 12, procedure 14, transfer 16), times the verdict (pass 1.0, partial 0.6, failure 0), times how independently it was demonstrated (cold 1.0, hinted 0.5, observed 0.5, shown/self-reported/override 0.2). A completed delayed review pays the transfer base. | XP for a reading step, a page open, a click, idle time, a return visit or a daily check-in; XP as a grade; a flat number per action kind; any XP the surface computes itself |
| Level | Cosmetic profile level from accumulated XP; shown in the Game header | Level gating a core lesson; level shown in parent evidence |
| Progress bar | Session progress or course completion of assigned steps; labelled `Game progress` | A bar implying mastery, a percentage of skill, or a fake completion |
| Collectible cards | Course/section cards earned or revealed by real course activity; cosmetic frames and stamps | Cards that imply a credential or a verified skill |
| Badges | Named for a real event (first check, first review, first take-home task) | Generic "engagement" badges that mean nothing |
| Streak | Optional later; only with a freeze/repair path and total practice days | Zero-reset guilt, loss aversion, a dying mascot |

Stars, ratings and review counts from the concept image are **not** data. The shipped card shows
real progress or none; it never invents a five-star review.

### 10B.3 Data and presentation

- Add a profile-scoped `game_engagement` table keyed by course and enrollment, not a second
  evidence store.
- XP events are idempotent and tied to a real action id (`attempt`, `lesson_run`, `homework`).
- The Game UI reads `course`, `path`, `attempt` and `homework` facts and adds the engagement
  layer. It does not write attempts or change transitions.
- The Game header shows a small XP/level chip and a `Game progress` bar; the course path remains
  the primary navigation.
- A settings toggle `Game feedback` can hide XP/level animation without changing the course.
- Textbook and Guided never show XP, levels or game bars. Parent Studio never shows them in a
  pack or a parent guide.
- If a learner switches Game to Textbook, the engagement record is retained but hidden; switching
  back restores it. No data is deleted.

### 10B.4 Quality guardrails

- Every XP award must name a real action AND carry graded evidence; no arbitrary timer.
- The number is recomputed from the graded row, not asserted at award time: the same attempt pays
  the same points in any later session, and the response carries the three facts it was built from.
- XP exists so learning is visible, not so activity is. The failure mode to refuse is the one where
  a daily check-in outranks a checkpoint, which produces active users who learn nothing.
- The game layer must not hide a check, a source, a warning or a recovery action.
- The game layer must not make a wrong answer feel like a lost life; feedback remains informative.
- Motion and sound follow the existing reduced-motion and optional-sound rules.
- A child using a parent-led lesson does not get a child-facing XP surface; Parent Studio remains
  adult-only.
- The final visual review must judge the game layer as part of the page, not as an overlay that
  damages the reading hierarchy.

### 10B.5 Acceptance

- A Game lesson awards XP once for a real check and once for a completed homework task; replay
  does not duplicate.
- The XP total is not returned by any evidence, parent, pack or course-export read.
- Textbook and Guided render no XP or level.
- A learner can hide game feedback.
- No core lesson is locked by XP.
- The visual reviewer confirms the Game header is playful but does not displace `Continue`, the
  current objective or the check.

## 10C. Independent visual review and quality gate

### 10C.1 Why this exists

The approved concept images are the bar. A green unit suite does not prove that a screen looks
like Coursebook, that the type is premium, or that the illustration is subject-specific. Workers
must not certify their own visual output.

### 10C.2 Roles

- **Maker**: implements, tests, commits, and submits a review packet. The maker does not mark
  the card done.
- **Visual reviewer**: a separate profile, default `quill`, compares screenshots to the approved
  concept frames and scores the visual rubric. The reviewer may request changes.
- **QA reviewer**: `sentinel` or `cbqa` verifies behavior, accessibility, security, evidence and
  export truth. A QA pass is not a visual pass.
- **Manager/integrator**: `atlas` or the operator merges only after both reviews pass. The manager
  may approve a small layout adjustment that preserves the concept's quality; the manager may
  not waive the visual threshold.

### 10C.3 Visual rubric

Score each dimension 1 to 5. A visual card passes only if every dimension is at least 4 and the
overall composition is judged near the approved concept.

| Dimension | What the reviewer checks |
|---|---|
| Focal hierarchy | One obvious primary; the eye lands on the course/action, not a card grid |
| Composition | Authored layout, asymmetry, route/reading column; not header + equal boxes |
| Type | One type system, body measure, heading scale, no tiny unexplained labels |
| Palette and texture | Parchment/ink/ochre/coral tokens; no raw colors or generic gradient |
| Illustration | Subject-specific, textless, consistent, high-quality; not stock or generic fantasy |
| Card/game system | Collectible cards feel tactile and meaningful; no fake ratings or numbers |
| State coverage | Empty/loading/error/offline/approved/rejected states look intentional |
| Responsiveness | 1049/900/460, 200% text, no clipped primary action, keyboard focus visible |
| Truth | All labels real DOM; no AI-generated text; no invented progress or evidence |

The reviewer records screenshots at 1049/900/460, light/dark, 200% text and the relevant state
matrix. `docs/visual-review/<card>/` holds the evidence. The reviewer names the concept frame
used for comparison and the differences that remain.

### 10C.4 Loop

1. Maker completes implementation and evidence.
2. Maker calls `hermes kanban request-review --reviewer quill --summary ...` (visual) and/or
   `sentinel` (behavior). The maker never calls `complete`.
3. Reviewer either passes or calls `request-changes` with specific fixes.
4. Maker revises in the same branch and resubmits.
5. Maximum three visual loops. If the third still fails, the manager splits the screen into a
   smaller card rather than accepting a lower-quality screen or hiding the defect.
6. Only a reviewer or the manager closes the card; the final integration card is a separate
   adversarial acceptance.

### 10C.5 Hard visual refusals

- No generated screenshot used as the product UI.
- No AI-generated letters, labels, numbers, logos or UI chrome.
- No invented star rating, review count, XP value or progress claim.
- No generic atlas on a technical procedure; no lanterns in a head-gasket world.
- No card grid replacing the course/route composition.
- No "close enough" pass without screenshots and a named reviewer.
- No worker self-certification.

## 11. Build sequence

Each phase is independently reviewable. The owner authorized this build on 2026-11-09; the
card graph below is the execution plan. Nothing is published or submitted without explicit
owner sign-off. The code goes in isolated worktrees; the operator checkout is not the build tree.

### Parallel execution

Run independent cards concurrently, up to the board's six-worker cap. Serialize only real
overlap:

- one writer for `desktop/plugin.js`: Home, World Studio, Parent Studio, Homework, engagement and
  tutor rail run in that order;
- one owner for migration 0013 and the frozen contract manifest;
- QA and final visual acceptance wait for their parents;
- backend cards in different modules (world, take-home, homework, engagement, tutor) run in
  parallel after their contract seam exists.

The current wave and the file-ownership map are in `docs/GAME-MODE-CARD-DAG.md`.

### Phase 0: freeze the contract and the home split

Deliverables:

- this plan and the adversarial review accepted;
- card graph and review protocol frozen;
- `cb.rpc` additive design and migration 0013 reviewed;
- `Home`/`FieldDeskHome` responsibility split agreed;
- concept image and textless-art rule recorded;
- acceptance matrix and test names frozen.

Evidence:

- a one-page screen map;
- a field mapping for every new visible value;
- no code.

### Phase 1: global Home and course home

Deliverables:

- `CoursebookHome` with shelf, create, browse, empty/loading/error/offline;
- `FieldDeskHome` retained as course home;
- mode badge on course cards;
- no course-bound hero on global Home;
- 1049/900/460, light/dark, 200% text, keyboard.

Evidence:

- before/after screenshots;
- first-screen comprehension script;
- `test_home_is_not_course_bound`;
- `test_empty_home_has_one_create_action`.

### Phase 2: course mode and World Studio

Deliverables:

- `courses.presentation_mode`;
- mode control in create;
- Textbook-to-Game dialog and Game-to-Textbook switch;
- `WorldStudio` concepts, edit, kit preview, approve;
- `WorldPolicy` with grammar table and quality checks;
- world prompts and host media job;
- world assets render on course home and shelf cards;
- textbook fallback and provider failure.

Evidence:

- one Japanese world and one head-gasket world generated in the same build;
- three concept boards, selected kit, final approval;
- no embedded text in any generated plate;
- `test_technical_world_never_carries_torque_or_sequence`;
- `test_world_style_swap_rejects_generic_art`;
- `test_textbook_generates_no_world_art`;
- `test_switch_to_game_requires_approved_world`;
- `test_switch_does_not_touch_attempts_or_evidence`.

### Phase 3: Parent Studio, homework, and game engagement

Deliverables:

- Parent Studio source picker over existing Game and Textbook courses;
- read-only lesson preview and take-home pack draft/approval/print;
- take-home pack PDF with parent guide, learner page, separate answer guide and sources;
- `homework_task` domain, `homework.create/read/complete/skip`, self/parent-reported events;
- adult `Take this with you` action and one-page export;
- Japanese demo tasks: pre/post-meal greetings and household labels, sourced in the lesson;
- game engagement store and Game header XP/level/`Game progress`;
- `Game feedback` setting, and no XP in Textbook, Guided, Parent Studio or print packs;
- independent parent/print content review.

Evidence:

- a parent opens an existing Game course, previews a section, generates and exports a
  print-ready pack; source course hash unchanged;
- a parent opens a Textbook course and does the same with no world art;
- a learner completes a Japanese take-home task and the record is `self_reported`;
- learner page has no answer key; answer guide is separate;
- print proof at A4/Letter with no clipped text;
- XP is idempotent per real action, hidden in Textbook/Guided, and absent from parent/export;
- `test_takehome_source_course_unchanged`;
- `test_takehome_learner_page_has_no_answer_key`;
- `test_homework_completion_is_self_reported`;
- `test_game_xp_not_in_evidence_or_export`;
- `test_textbook_has_no_engagement_surface`;
- `test_core_lesson_not_gated_by_xp`.

### Phase 4: tutor rail

Deliverables:

- `TutorRail` in the right pane, bound to the active lesson run;
- `tutor.ask` and `tutor.history`;
- `Practice` mode for a check that declares conversation practice, using the existing
  `practice.*` commands;
- selection pill and quote chip;
- authored glossary terms and inline cards;
- hint policy and assist integration;
- no-tool, no-answer-key context;
- citation-to-block links;
- bottom sheet at 460 px;
- empty, unavailable, provider-failure and changed-lesson states.

Evidence:

- a real lesson: select a word, ask, receive a cited answer, click the citation, return;
- a hint on an open check records `lesson.assist` and does not reveal the answer;
- a practice check starts, exchanges learner and tutor turns, and ends with only learner turns
  graded;
- `test_tutor_context_excludes_answer_key`;
- `test_tutor_has_no_tool_or_shell_access`;
- `test_selection_does_not_auto_send`;
- `test_tutor_turn_never_writes_attempt_or_evidence`;
- `test_practice_tutor_turn_cannot_produce_a_pass`;
- `test_tutor_thread_is_excluded_from_export`.

### Phase 5: generalization and release hardening

Deliverables:

- all matrix rows exercised with fixtures or real generated courses;
- source-grounded technical media checks;
- art budget and cache proof;
- 460/200%/reduced-motion/keyboard;
- cost report per course world and tutor turn;
- docs updated: `HOME-HUB-ARCHITECTURE.md`, `FINAL-POLISH-SPEC.md`, `VISUAL_MEDIA_PLAN.md`,
  `COURSEBOOK-VISUAL-IDENTITY-V2.md`, `CONTRACTS.md`;
- no publication or catalog submission without explicit owner sign-off.

## 12. Tests and evidence

Backend tests:

- world grammar is deterministic for language, technical procedure, mathematics, history,
  astronomy, cooking and unknown;
- world prompts are textless and include no answer keys or attempts;
- world cache keys prevent duplicate spend;
- partial provider failure produces named missing roles, not fake files;
- final approval is hash-fenced;
- mode switch refuses Game without an approved world;
- mode switch never mutates attempts, evidence, checks or lesson document hashes;
- take-home source course remains unchanged and content-hash bound;
- take-home learner page has no answer key; answer guide is separate;
- homework completion writes `self_reported` or `parent_reported`, never a pass;
- homework creation rejects generic "practise for ten minutes" tasks;
- game XP is idempotent per real action and absent from evidence/export/parent reads;
- textbook and guided create no engagement surface and no world job;
- core lessons are not gated by XP;
- tutor context is bounded and excludes hidden keys;
- tutor citations resolve to lesson blocks or source ids;
- tutor cannot write attempts, transitions, evidence or exports;
- tutor text is excluded from pack and course export.

Desktop tests:

- global Home has no course-bound hero and exactly one create primary;
- course home still has the trailhead and Continue;
- mode dialog copy and disabled reasons;
- World Studio state matrix;
- Parent Studio source picker opens Game and Textbook courses;
- take-home preview and print proof have no learner answer key;
- homework sheet is one page and one task;
- Game header shows XP/level/`Game progress` only in Game;
- Textbook and Guided have no engagement surface;
- `Game feedback` hides XP without changing the course;
- selection pill is not shown on a single click;
- quote chip can be removed and never auto-sends;
- glossary terms are real buttons with accessible names;
- 460 px bottom sheet;
- 200% text, keyboard focus, reduced motion, no overflow;
- screen reader reading order includes the tutor context and citations.

Quality evidence:

- human walkthrough on the Home -> course -> game world -> lesson -> selection -> tutor path;
- one non-Japanese course, preferably head gasket, read by a subject-competent reviewer;
- screenshots at 1049/900/460, light/dark, 200% text;
- a cost and latency note for concept generation, kit generation and tutor turn;
- a list of unresolved risks signed by the reviewer.

## 13. Risks and refusals

| Risk | Mitigation |
|---|---|
| Game world becomes a generic skin | Subject grammar table, anti-generic swap test, human review, no "one atlas for every course" |
| Generated images contain gibberish text | Textless prompts, OCR/text check where available, real UI text, no screenshot generation |
| AI art implies technical authority | Art is orientation; deterministic schematics and sourced references carry procedure; tests and warnings |
| Image generation cost or latency | Three low-res concepts, capped kit, content-addressed cache, real stages, Textbook fallback |
| Provider failure loses the course | Course and plan remain; Textbook fallback; missing roles named; no fake assets |
| Two chat surfaces confuse the learner | Tutor rail is the only learner tutor; authoring chat stays in builder mode; no host-chat fallback |
| Tutor leaks an answer or changes state | Context excludes keys; no tools; no write methods; hint via `lesson.assist`; tests |
| Migration breaks old courses | Nullable mode; old rows read Textbook; no backfill; no lesson rewrite |
| Game mode blocks learning when art is slow | Plan and lessons remain readable; Textbook fallback; world approval is a gate only for Game lesson build |
| Home becomes a dashboard again | One create primary; shelf of courses; no stats-first layout; quality gates |
| Parent mode becomes child chat | Parent Studio remains the parent's surface; tutor is not exposed to a child profile |
| Parent print pack uses AI art as authority | Captioned orientation only; deterministic/sourced diagrams; print proof and independent review |
| Homework invents a grade or surveillance | One self/parent-reported task; no photo/geolocation; retrieval check follows separately |
| Game engagement becomes fake mastery | Game-only XP layer; no evidence/export/parent exposure; no core locking; visual and QA review |

Refusals:

- No AI-generated screenshot as the product UI.
- No AI image carrying a torque, clearance, sequence, measurement, safety instruction or answer.
- No image with embedded text, logos or watermarks in a primary surface.
- No fake world when generation fails.
- No silent switch to Game or Textbook.
- No XP, streak, level, mastery percentage, currency or lock in Textbook, Guided, Parent Studio,
  evidence, packs or exports. Game mode may show the separate play layer in §10B only; it may
  never be called mastery or used as evidence.
- No core lesson locked behind XP or game currency.
- No learner-page answer key; no graded homework.
- No tutor with shell, browser, file or authoring tools.
- No export of tutor turns or private learning history.
- No publication or catalog submission before owner sign-off.

## 14. Open decisions for the owner

1. **Textbook and diagrams.** Confirm that Textbook mode means "no generated world art" but may
   still show deterministic schematics or sourced instructional figures. My recommendation is
   yes; otherwise a head-gasket lesson loses safety-critical information. If you want a strict
   text-only option, it should be a separate setting.
2. **Guided view.** Confirm that Guided remains a lesson view under either course mode, rather
   than becoming a third course world. My recommendation is yes.
3. **Style choice size.** Three concept boards is the recommended balance of agency and cost.
   Two is cheaper; four is more choice but slower.
4. **World art in packs.** My recommendation is local-only for `cb.pack`/catalog export, while
   an approved take-home print pack may include captioned world plates with provenance. Packs
   carry teaching content; the print pack is a separate artifact.
5. **Tutor backend.** My recommendation is the Coursebook-owned `tutor.ask` with `ctx.llm`;
   the host chat is not embeddable in the current pane and would create a second chat. If a
   dockable host chat seam lands, the renderer can change without changing the context model.
6. **World approval versus plan approval.** My recommendation is separate gates: content first,
   visual second, then build. This keeps a rejected plan from spending image money and keeps a
   rejected world from blocking a readable textbook course.
7. **Homework delivery.** Recommendation for the first slice: print/download plus an in-app
   completion record. No email/SMS send until an explicit channel and confirmation exist; that
   avoids sending learner data or turning homework into a notification product.
8. **Game engagement scope.** Recommendation: ship XP, cosmetic levels, `Game progress` and
   collectible section cards in the first Game slice. Leave streaks out until a freeze/repair
   path is designed; do not ship loss-framed streaks.
9. **Parent print art rights.** Recommendation: use only locally generated, approved world
   plates and existing sourced instructional figures; no stock art and no AI art in a
   procedure; record provenance on the pack.

## 15. Concept assets

The production UI is composed from textless art plates and real DOM type. These concept frames
are references for composition, palette and subject identity, not production screenshots.

- Approved global Home concept (owner-approved 2026-11-09):
  `~/Pictures/coursebook-direction-a/home-generic-first-open.png`
  `https://files.catbox.moe/rdu9lr.png`
- Open-atlas alternate (not the approved Home):
  `~/Pictures/coursebook-direction-a/home-generic-open-atlas-variant.png`
  `https://files.catbox.moe/nuzhnb.png`
- Japanese classroom reference (the earlier course-bound frame, preserved):
  `~/Pictures/coursebook-direction-a/japanese-classroom-reference.png`

The Japanese classroom frame is not the global Home. The generic Home is the launcher. The
Japanese frame becomes the reference for the Japanese course's own home and world.
