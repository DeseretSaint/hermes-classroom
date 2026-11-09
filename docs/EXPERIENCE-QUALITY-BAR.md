# Coursebook experience quality bar

Status: binding interim standard for every UI/product card. Owner review is still required before
this becomes the frozen experience spec. It does not change the plugin architecture, the evidence
contract, or the publication gate.

Date: 2026-11-07. Base: `origin/master` `14a6443`.

## Owner amendment — game mode engagement (2026-11-09)

The owner has explicitly overridden the earlier no-XP/no-progress-bar rule **for game mode only**.
Game mode may show XP, cosmetic levels, a `Game progress` bar and collectible feedback because it
must be engaging and fun. The play layer is never evidence, never mastery, never a parent/print/
export value, and never a gate on a core lesson. Textbook, Guided and Parent Studio remain calm and
free of game chrome. See `docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md` §10B for the complete rules; this
amendment resolves the conflict in this file without changing the evidence contract.

Why this file exists: the current product is still mostly formatted text, rules, cards and
standard buttons. A learner has to read the interface to understand it, the course seal needs
explanation, and the home is a dashboard rather than a place to learn. Those are product defects,
not styling preferences. "Make it prettier" is not an acceptance criterion. This file defines what
we mean by high quality, what evidence a worker must produce, and what does not count.

## 1. Definition

High quality means all four of these are true at the same time:

1. **A first-time user can act without being taught.** The screen shows one obvious next move,
   the current place, and what happens when they press it. No tooltip, tour, legend or paragraph
   is needed to explain the interface.
2. **The product has an authored identity.** The composition, type, imagery, motion and sound
   belong to Coursebook and to the subject being learned. It is not a generic dashboard with a
   logo and an accent colour. Decoration that does not encode something the user can name is
   removed.
3. **Progress is real and felt.** The path, checkpoints, checks and completion states come from
   recorded learning evidence. The interface makes that progress legible and satisfying without
   inventing XP, mastery percentages, streaks or locks.
4. **The whole loop works.** Home → continue → path → lesson → check → feedback → return is
   complete, recoverable, fast and accessible. A beautiful screenshot with a dead control is a
   failure.

A card is not high quality because it passes tests, has no lint errors, or "looks plausible".
Tests prove behavior; they do not prove comprehension, craft or fun.

## 2. The five quality pillars

### 2.1 Wayfinding and comprehension

- One primary action per screen. A second filled/primary control is a hierarchy defect.
- The first screen answers, without instruction: where am I, what can I do now, what happens next.
- The current course, current section/checkpoint and next checkpoint are visible in the same
  reading order. The learner never has to reconstruct their position.
- Every control has a visible label and an obvious consequence. No dead, duplicate,
  disabled-without-reason, or "mystery" control.
- No decorative mark stands in for identity. If a seal, monogram or icon is used, a first-time
  user must be able to name what it means without help; otherwise remove it from that surface.
- Copy is plain, literal and short. Do not explain the interface in prose when the layout can
  show it. No internal enums, no "governed learning workspace" language, no self-congratulatory
  slogan.

### 2.2 Product loop and state

The minimum complete loop is:

```
Home / classroom hub
  → Continue (or choose a classroom)
  → Path with current checkpoint and next checkpoint
  → Lesson step (one concept, one action)
  → Check / practice with immediate feedback
  → Return to path with visible, recorded progress
```

Every screen in that loop needs:

- a **first-use** state that leads to one real action;
- a **loading** state that preserves layout and does not flash an empty result;
- an **empty** state that says why it is empty and gives one next action;
- an **error/offline** state that says what failed, what is preserved, and how to recover;
- a **cleared/completed** state that acknowledges the result and gives the next move.

No state may silently turn a failed read into "no courses", "not started" or "no evidence".
No state may ask the learner to press a disabled control with no explanation.

### 2.3 Visual and interaction craft

- **One focal hierarchy per frame.** The thing to do now is unmistakable. A screen where every
  element has equal weight is a defect, not "clean".
- **Authored composition, not a card grid.** Do not build the page out of same-size header +
  box + button rows. Use one featured learning surface, asymmetry, a route, a reading column, or
  a purposeful spatial model. Cards are for heterogeneous choices, not for every object on the
  page.
- **One type system.** Six sizes maximum on a body-first ramp; body line-height around 1.5;
  prose measure 50–75 ch. No random `0.8rem`/`0.85rem` strings. Type must be legible before it is
  stylish.
- **Colour does one job at a time.** Identity, mode and state are separate jobs. At most two
  hues plus the error hue in one viewport. No gradients, glass, blur, thick decorative left bars,
  hard offset shadows or emoji-as-icon. No raw colour outside the token contract.
- **Meaningful visual moments.** A core screen needs at least one authored visual that carries
  meaning: a classroom cover/motif, a path/checkpoint composition, a lesson illustration, a
  result mark. It must encode the subject, the route or the learning action. A generic icon or a
  colour splash is not a visual moment.
- **Motion is feedback, not decoration.** 100–200 ms for feedback, 200–300 ms for transitions;
  transform/opacity only; reduced-motion strips movement but keeps the state change. No generic
  wipes, no animation above the fold on a tool screen, no confetti as the only reward.
- **Sound and haptics are optional and user-controlled.** If used, they confirm a real action
  (check submitted, checkpoint reached), never mask a missing state or autoplay.
- **Performance is part of the feel.** No blank route while data loads; interactions acknowledge
  within 100 ms; animation holds 60 fps; no layout shift on load; no scroll jump when state
  changes.

### 2.4 Learning and engagement integrity

- The learning action is the game. Do not bolt a game skin onto a text page. A checkpoint is a
  real synthesis/retrieval moment, not a decorative gate.
- Lessons are short arcs: one concept, one example, one action/check, one feedback, one close.
  Target a 3–8 minute session beat; long prose belongs in the optional Textbook view, not the
  default path.
- Checks are frequent, low-stakes and informative. Feedback says what was right or wrong and
  what to try next. Errors are information, never shame.
- Spacing, retrieval, interleaving and mastery evidence drive sequencing. The path must not be a
  random list of topics dressed as levels.
- Gamified mechanics must map to a real learning event. Competence, autonomy and relatedness are
  the baseline, not points, badges and leaderboards.
- No invented XP, level, mastery percentage, streak, leaderboard, lock or "energy" unless the
  backend has a durable, user-visible contract for it and the owner has approved the mechanic.
- No streak guilt, loss-aversion pressure, opaque ranking or compulsory competition. If a social
  or competitive feature exists, it is opt-in and can be turned off.
- At most two primary progression metrics, and they must be concrete (sections with evidence,
  checks passed, practice days), not abstract "wellness points".

### 2.5 Content and product truth

- Every visible number, state, source, image, audio clip and progress claim maps to a recorded
  backend fact. If the fact is unavailable, say so.
- No test fixtures, debug titles, raw IDs, internal enums or "H103 live reject check" rows in a
  user-facing profile. Demo data is seeded, labelled and resettable.
- Every image and audio asset has a purpose in the lesson and a provenance/licence row. No
  decorative stock photo, no autoplay, no fake pronunciation score.
- The same course document, check and evidence back Textbook, Guided and Field Quest. Views may
  change presentation; they may not invent different learning states.

## 3. Hard gates

A UI/product card may not be marked done unless every applicable gate passes. "N/A" must be
justified in the card, not assumed.

| Gate | Pass condition | Evidence the card must include |
|---|---|---|
| Q1 First-screen grasp | 5 of 5 first-time testers can say what to press and what happens next within 5 seconds, without prompting | Short task script + result; screenshot at the target width |
| Q2 One primary action | Exactly one primary/filled action per screen; no duplicate CTA; every secondary action has a distinct job | Before/after screenshot with callouts |
| Q3 Path legibility | Current position, next checkpoint, completed checkpoint and remaining route are visible; every node opens a real destination | Path state table; screenshot at 1049/900/460 |
| Q4 Real progress | Every displayed progress/state value maps to a backend field; no invented XP/streak/mastery/percentage | Field mapping table; sample data proof |
| Q5 Authored visual | One focal hierarchy; no unexplained seal/monogram/decorative mark; at least one meaningful visual per core screen; no same-size card grid as page structure | Visual rationale + before/after screenshots |
| Q6 Lesson loop | One concept per step; a real interaction/check before the summary; immediate feedback; a clear close and return | Lesson script + screenshots of step, check, feedback and close |
| Q7 State completeness | First-use, loading, empty, error/offline and cleared states each have one next action and preserve work | State matrix + one screenshot per state |
| Q8 Motion/feedback | Press, check, checkpoint and completion feedback are visible; timings within 100–300 ms; reduced-motion equivalent exists | Motion note + reduced-motion capture/test |
| Q9 Accessibility | WCAG 2.2 AA; 460/900/1049 px; 200% text; keyboard focus; visible focus; no horizontal overflow; 24 px minimum targets (44 px for primary learning actions) | axe/keyboard/manual checklist; 460/200% captures |
| Q10 Performance | No blank route; feedback within 100 ms; no layout shift; 60 fps for authored motion; no blocking spinner without a progress state | Measurement note or profiler trace |
| Q11 Copy and truth | Plain language; no internal jargon; no self-explaining UI prose; no test/debug content; every claim sourced | Copy diff + data provenance |
| Q12 Human proof | A human has completed the primary task end to end; screenshots exist at three widths and both light/dark; a reviewer signs the quality score | Review record with score and unresolved risks |

Automation does not certify quality. axe catches only part of WCAG; a green test suite does not
prove comprehension, craft or fun. Q12 is mandatory.

## 4. Review score

Score each pillar from 1 to 5:

- 5 = ship quality; a first-time user would believe this is a professional product.
- 4 = pass; minor polish remains but no comprehension or trust defect.
- 3 = needs work; usable but visibly unfinished.
- 2 = fail; a user would need help or would lose trust.
- 1 = not a product surface yet.

A card cannot be done if any applicable hard gate fails. A card with any pillar below 4 needs a
named follow-up card before it can be called ship quality. The target for the core home/path/lesson
loop is **4.5 or higher on every pillar**, not an average that hides a 2.

### 4.1 Recommendation review

Every research recommendation is reviewed before it becomes a card. A recommendation passes only
if all of these are true:

1. **Outcome:** it makes the primary learning loop clearer, more engaging or more trustworthy for
   a first-time learner. "It looks nicer" is not an outcome.
2. **Evidence:** it is backed by a named source or recorded product evidence, with vendor claims
   labelled as vendor claims. A confident blog post is not a law.
3. **Honesty:** it does not invent progress, mastery, social proof, urgency or a metric the backend
   cannot support.
4. **Fit:** it works inside the existing plugin, RPC/evidence contracts and token system without a
   speculative rewrite. If it needs a new contract, that contract is named and scoped.
5. **Comprehension:** it reduces, rather than adds, the need to explain the interface. A new mode,
   panel or badge must earn its place.
6. **Access and resilience:** it works at 460/900/1049 px, light/dark, 200% text, keyboard,
   reduced motion, and in the empty/loading/error states.
7. **Scope:** it is either part of the first vertical slice or explicitly deferred with a reason.
   It does not smuggle a world map, an invented avatar system, currency or other second product into the slice. The host's existing pet sprite is identity, not a second product.
8. **Measurability:** there is a way to tell whether it worked, not just whether it shipped.

Verdicts are **ADOPT** (card it), **ADAPT** (card the smaller honest version), **DEFER** (card only
if the later trigger is real), or **REJECT** (record why, no card). Every ADOPT/ADAPT item gets a
card with the gate(s) it advances, the evidence, the exposed states, and the acceptance evidence
from §8. No card is created for a recommendation that only changes styling.

## 5. Anti-patterns: this is what "not high quality" looks like

- A page made of a heading, a bordered box, a row of three equal stat cards and two buttons.
- A full RPG world map, open exploration, invented avatar systems, currencies or a game engine. The Hollow Knight
  reference is a launcher home, not an RPG. The learner's existing Hermes pet sprite may appear as
  identity and a study companion (owner amendment 2026-11-08); that is not an avatar system, a new
  progression track, or an invitation to build one.
- Adding colour, a gradient or a decorative seal and calling the result "designed".
- A seal/monogram that requires the owner to ask what it means.
- A home screen that is a dashboard of counts before it is a place to continue learning.
- A path that is a vertical list of equal rows with no current/next/checkpoint hierarchy.
- A lesson that is a wall of prose with a "Next" button, or a quiz bolted onto the bottom.
- A "checkpoint" that is a decorative lock with no learning event behind it.
- XP, levels, streaks, badges, leaderboards or mastery percentages that are not backed by a real
  contract, or several of them at once.
- Confetti, shake, sound or animation used to cover a missing state.
- Disabled buttons with no reason, duplicate primaries, dead "Resume" controls.
- A loading screen that flashes "No courses"; an error that looks like an empty profile.
- Test packs, developer titles, raw IDs or debug counts in the user's Library.
- Copy that explains the UI instead of the UI explaining itself.
- A card marked done on tests alone, with no human walkthrough and no screenshots.

## 6. Game and engagement baseline from the vault

These are design inputs, not a licence to copy a game. The full research indexes are:

- `~/Obsidian/personal-vault/JP-Lingo/game-designer-research.md` — mechanics, fail/retry,
  progression, feel/beat research; hard rules include **2D-only, Japanese-themed,
  game = learning** (the game lives inside the learning task), ledger-first, and the
  anti-generic check: if the design could be reskinned to medieval Europe, redesign it.
- `~/Obsidian/personal-vault/JP-Lingo/storyteller-research.md` — 3–8 minute session arcs,
  progression-as-story, show-don't-tell, companion/guide, stakes without darkness.
- `~/Obsidian/personal-vault/JP-Lingo/humanifier-research.md` — human-check lenses, mistake
  tolerance, no shaming retry, parent legibility, low-stimulation.
- `~/Obsidian/personal-vault/JP-Game-OSS-Quality-Stack.md` — the quality stack that actually
  moves feel: audio, juice/hit-stop/transitions, typography, dialogue, accessibility. Audio is
  called the biggest lever; use it where it confirms a real learning event.
- `~/Obsidian/personal-vault/UI-UX One-Shot Playbook.md` Q240 — self-determination theory
  (competence, autonomy, relatedness); generic points/badges/leaderboards backfire; streak
  psychology is loss aversion and shifts motivation to obligation; one or two primary metrics;
  milestone celebrations; opt out of competition.

What we take:

- **Session arc:** open with one clear challenge, let the learner act, give specific feedback,
  close with a visible result and a reason to return.
- **Progression as place:** the path is a route through a subject, with checkpoints that mark
  real synthesis, not a list of files.
- **Game feel:** press feedback, check feedback, checkpoint transitions and a completion moment.
  These are small, timed, and tied to real events.
- **Mistake tolerance:** retry is cheap and never shaming; a wrong answer is information.
- **One learning game at a time:** the interaction must be the learning action, not a mini-game
  beside it.

What we do not take:

- Child-oriented art, mascots or voices for an adult product.
- A fake open world, fake locks or fake currencies.
- Streaks as the main loop; loss aversion is not engagement.
- Multiple progression systems stacked because a game has them.
- Decoration that has no meaning in the subject or the learning act.

### 6.1 The game layer we may build

| Mechanic | What it means here | Source |
|---|---|---|
| Self-determination | Competence: the path shows what the learner can now do. Autonomy: the learner sets pace and session length. Relatedness: a shared parent/learner view, not a public league. One or two metrics; concrete counts beat points. | Q240 |
| Streaks, if ever used | Only with a durable daily fact, a freeze/repair path and "total practice days"; never zero-reset or loss-framed. Not in the first slice. | Q240 |
| Progression as story | Unlocks are path milestones and capability statements ("you can now order food"), not XP thresholds. A session is a 3–8 minute arc: enter, teach, check, settle, exit. | storyteller-research |
| Show, don't tell | The path and checkpoint embody the idea; no copy names the theme. Choice must change what is practised. | storyteller-research |
| Feel beats | Design the moment before and after the answer: preview, attention cue, commit, settle. | game-designer-research |
| Juice and transitions | One authored functional beat per commit; semantic and low-stim. Audio only when it confirms a real learning event, off by default. No shake, damage numbers or coin SFX. | JP-Game-OSS-Quality-Stack |
| Mistake tolerance | Free retry, no shaming, specific correction. A wrong answer becomes a review item, not a damaged save. | humanifier-research |
| Anti-generic test | If the design could be reskinned to medieval Europe, redesign it. | game-designer-research |

UI never invents a learning mechanic. A game element may visualise a real evidence fact or lower
the cost of the next repetition; if it creates a number the backend does not record, it is fake.

### 6.2 Rulings on contradictions

| Tension | Ruling |
|---|---|
| "No XP, streaks, leagues or levels ever" vs the owner's game baseline | The ban is on fabricated facts, not motivation. SDT-backed mechanics are allowed only when the fact exists. No XP/levels/leagues in the first slice; conditional streak is deferred. |
| Owner wants a game; the constraint is "game = learning" | No currency, shop, energy, loot or XP economy. The path, checkpoint and evidence are the game. |
| Four to six type sizes vs many identity roles | Budget per route, not a token census. Roles may reuse a step; labels stay at least 0.75rem. |
| No card rows vs the shelf | Rows on rules, one featured element, one line of labelled facts. Cards only for a small heterogeneous shelf; never nested. |
| "No motion by default" vs "motion must read as the intended physical act" | No decorative motion; every state change gets next-frame feedback and at most one authored functional beat. |
| Plain language vs college-level subject matter | The plain-language rule governs chrome, instructions and errors; the subject keeps its register. |
- A "profile slot" vs the existing data model | A classroom slot is course + active enrollment. Do not invent a learner profile or avatar; true multi-learner evidence is a later data-model card. The host's existing pet sprite may be displayed as the learner's identity/companion; it carries no learner data and no progress claim.
| The seal as identity vs the owner's confusion | Retire it from primary surfaces. A mark that needs explanation is not doing an identity job. |

## 7. Required shape of the first experience redesign

Owner clarification (amended 2026-11-08): the Hollow Knight reference means **a home/launcher
screen only**, not an RPG world map. The intended read is: open Coursebook, hit Continue, choose
which classroom/save file to continue, change a few settings if wanted, and get on with learning.
The learning path stays a Duolingo-like linear route with checkpoints. No open exploration, new
avatar system, currencies or game engine. The learner's **existing Hermes pet sprite** may appear
as identity and a study companion on the launcher, path and completion moments, because the owner
asked for the product to feel personal; it is the host's asset, not a new progression mechanic and
not a reason to build an avatar editor.

This is a direction, not a frozen implementation. The research pass may refine it.

1. **Home is a launcher, not a dashboard or a world.** The first thing is a single Continue
   surface for the most recently active classroom, with the next checkpoint named. Below it,
   classrooms are presented as distinct places (cover/motif, subject, progress, next checkpoint),
   not identical admin rows. One action creates a new classroom.
2. **Settings live on Home, not in a separate maze.** One compact settings sheet: appearance
   (system/light/dark), default presentation mode (Game/Guided/Textbook), sound/haptics,
   reduced motion, and a per-classroom override. Toggles apply immediately; no Save button. Do not
   build a settings page until the list actually grows past one sheet.
3. **A classroom opens on its path.** The path shows chapters/units, the current checkpoint, the
   next checkpoint and completed ground. It is a linear route, not a map. A node opens the lesson;
   there is no separate catalogue of equal rows to decode.
4. **A lesson is a player, not a document.** Default to one concept per step, a visual/example,
   an interaction or check, immediate feedback, and a close that returns to the path with the
   recorded result. Textbook remains an optional reference view, not the default learning surface.
   The Home setting chooses the learner's default view; the classroom can override it.
5. **The seal is retired from primary navigation, first-run and pack rows.** Replace it with a
   meaningful classroom identity (subject/title/cover/motif) or nothing. Do not defend an ornament
   that needs an explanation.
6. **Parent Studio stays a separate, legible authoring space.** It is not the learner's home, and
   its primary action is preparing a lesson for a child, not chatting as the child.
7. **Library remains the pack shelf.** It is not the home and does not pretend a pack is a course.

The first vertical slice is Home → Continue → Path → one lesson step → check → return, plus the
Home settings sheet with the default-view control. Do not start with a world map, a new avatar
system, leagues, currencies or generated art pipelines. Those are not part of the Hollow Knight
reference; they are later roadmap ideas only if they serve the loop. The existing Hermes pet sprite
is the one identity asset that may be used without opening that door.

## 8. Definition of done for a card

A UI/product card is done only when it includes:

- the user task and the one primary action;
- before/after screenshots at 1049, 900 and 460 px, light and dark;
- the state matrix (first-use, loading, empty, error/offline, cleared);
- the exact copy, with no internal jargon;
- a field mapping for every number/state shown;
- keyboard and focus evidence, 200% text, reduced motion;
- performance/motion notes;
- a human walkthrough and a quality score against this file;
- no test/debug content in the surface;
- a named reviewer and any residual risk.

A card that only changes CSS, adds a badge, or replaces one box with another box is not a quality
card. It needs a product reason and evidence.

Generated course content has a separate lens. A card that changes what the generator writes (plan,
objectives, units, lesson prose, worked examples, checks, reference answers or media need) must
also attach a completed eight-dimension record from `docs/COURSE-QUALITY-RUBRIC.md` (H-173) with a
named reviewer and the validator's recorded verdict, and must turn every dimension below 3 into a
follow-up card. This file judges the product surface; that rubric judges the course. The rubric is
not a mastery score, an engagement metric or a public badge, it does not replace the validator's
structural pass, and it does not block a course a human has approved. The first record is
`docs/H173-COURSE-QUALITY-REVIEW.md`.

## 9. Worker rules

1. Read this file and `docs/UX-RESEARCH-STANDARDS.md` before starting any UI card.
2. Write a one-page slice note first: screen, user task, primary action, states, visual idea,
   motion, copy and data mapping.
3. Build in the card's own worktree; never edit `desktop/plugin.js` in the shared checkout.
4. A UI card that cannot show a before/after at three widths and a human walkthrough is not done.
5. No new gamified mechanic may be invented in a UI card. It needs a research row, a backend
   contract, and owner approval.
6. If a design idea conflicts with this file, the file wins unless the owner explicitly overrides
   it in chat and the override is recorded.

## 10. Open research questions

The eight research agents currently running must resolve these before the experience spec is
frozen:

- Which Duolingo mechanics produce clarity and which produce engagement, and which should
  Coursebook reject?
- Which game-hub/save-slot patterns transfer to an adult learning product without becoming a
  child's game?
- What does the learning-science evidence require from the path, checkpoints, spacing and
  feedback?
- What visual/interaction craft separates a premium consumer app from a styled document?
- Which gamification mechanics are defensible under self-determination theory, and which are
  padding or dark patterns?
- What is the smallest data/contract change needed for classroom/profile slots and a Continue
  hub?
- Which current screens are failing Q1–Q12, and what is the highest-leverage first slice?
- What do the owner's vault game-design/UI research and existing standards require that this
  interim bar does not yet capture?

Until those are answered, this file is binding for quality but not a frozen visual direction.
