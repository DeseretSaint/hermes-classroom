# Coursebook experience quality bar

Status: binding interim standard for every UI/product card. Owner review is still required before
this becomes the frozen experience spec. It does not change the plugin architecture, the evidence
contract, or the publication gate.

Date: 2026-11-07. Base: `origin/master` `14a6443`.

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

## 5. Anti-patterns: this is what "not high quality" looks like

- A page made of a heading, a bordered box, a row of three equal stat cards and two buttons.
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

## 7. Required shape of the first experience redesign

This is a direction, not a frozen implementation. The research pass may refine it.

1. **Home is a classroom hub, not a dashboard.** The first thing is a single Continue surface for
   the most recently active classroom, with the next checkpoint named. Below it, classrooms are
   presented as distinct places (cover/motif, subject, progress, next checkpoint), not identical
   admin rows. One action creates a new classroom.
2. **A classroom opens on its path.** The path shows chapters/units, the current checkpoint, the
   next checkpoint and completed ground. A node opens the lesson; there is no separate catalogue
   of equal rows to decode.
3. **A lesson is a player, not a document.** Default to one concept per step, a visual/example,
   an interaction or check, immediate feedback, and a close that returns to the path with the
   recorded result. Textbook remains an optional reference view, not the default learning surface.
4. **The seal is retired from primary navigation, first-run and pack rows.** Replace it with a
   meaningful classroom identity (subject/title/cover/motif) or nothing. Do not defend an ornament
   that needs an explanation.
5. **Parent Studio stays a separate, legible authoring space.** It is not the learner's home, and
   its primary action is preparing a lesson for a child, not chatting as the child.
6. **Library remains the pack shelf.** It is not the home and does not pretend a pack is a course.

The first vertical slice is Home → Continue → Path → one lesson step → check → return. Do not
start with a full animated world map, avatars, leagues, currencies or generated art pipelines.
Those are later roadmap items, and only if they serve the loop.

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
