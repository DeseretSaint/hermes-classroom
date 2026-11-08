# Final polish spec: The Trailhead

Status: working spec for the final adversarial product pass, 2026-11-08. It is subordinate to
`EXPERIENCE-QUALITY-BAR.md`, `UX-RESEARCH-STANDARDS.md` and the evidence contract. It changes no
backend claim and does not close the publication gate.

Owner amendment: the learner's **existing Hermes pet sprite** may appear as identity and a study
companion. It is not a new avatar system, a progression track, or a reason to build an avatar
editor. If the host has no pet, Coursebook shows no invented avatar.

## 1. Why this pass exists

The current product is correct enough to be interesting and too quiet to win. The first viewport
is a large section title, two equal grey actions, a flat route list and count blocks. The route is
technically a route but reads as a table; the learner is not visible; the course is a database row;
the create flow asks for a goal, a name, a size, a recipe and four dials before the learner sees
where they are going. The judge sees a good backend before they see a product.

The target is not "add a game skin". It is to make the real learning loop feel like a place:

- one **trailhead** on Home, with one Continue and a visible next stop;
- one **trail** through the course, with the current stop larger than the future ones;
- one **field stop** per lesson, with one action and one check;
- the learner's own Hermes companion at the threshold and the close;
- a course that looks like this subject, not like a generic dashboard.

Every visual element must encode identity, position or state. Nothing is added just to decorate.

## 2. The concept

**The Trailhead** keeps the Atlas Lamp palette and type. It adds one spatial model: a course is a
trail through a subject. Home is the trailhead; the path is the trail; a lesson is a field stop; a
check is a gate; the close returns to the trail with one more recorded section. The companion is
the learner's Hermes pet, not a mascot with dialogue.

The model is linear on purpose. No open world, no branching map, no currency, no XP, no league.
The game is the sequence of real learning events the backend already records.

## 3. Home: the trailhead

One screen, one object: the trail.

1. **Trailhead plate** — full content width, flat `lamp-soft` field, 3 px `lamp` top edge. At wide:
   young-forest contour SVG at low ink on the right, a 64 px companion at the edge; at narrow the
   contour becomes a narrow top band and the companion sits beside the label, not over text.
2. **Copy** — one label (`CONTINUE THE TRAIL`), the course title (display serif, max 2 lines), one
   sentence that names the next stop and what the learner will do. No counts before the action.
3. **Actions** — one primary `Continue` (the backend's next step; if it is a review, the label says
   `Start the review`). Secondary `Open section`; tertiary `See the plan`. Settings is a small
   labelled button in the top-right, not a competing primary.
4. **Trail** — `CheckpointPath` directly below, visually joined to the plate: a continuous route
   line, current stop large, next smaller, future quiet, evidence states in words. It is not a
   second card.
5. **Field notebooks** — a horizontal shelf of the learner's other classrooms at the bottom, each a
   distinct cover/motif, subject and last touched; one `Open`. `New course` is the only other
   primary-adjacent action and is visually secondary to Continue. These are save/classroom choices,
   not admin rows.
6. **Field notes / sources** — stay available but not in the first viewport; one tertiary link or a
   drawer, not a third column of empty boxes.

First-run: the same plate with no course: a 240 x 120 contour ghost, `Name a goal` as the only
primary, one sentence, and `Use a course I already have` as a tertiary. Settings and companion are
present; no fake path.

Parent classroom: `plum-soft` plate and `plum` seal edge; same composition, parent copy. The
companion is the adult's own; no child avatar is invented.

Loading: preserve the plate geometry with a restrained `Reading the trail…` line; no skeleton
shimmer. Error: name the failed read, keep Continue if the backend recorded a next step, offer one
retry. Empty: say what is missing and one next action. Cleared: acknowledge the recorded evidence
and give the next stop.

## 4. Path: the trail

The existing `CheckpointPath` keeps its honest data: every objective is a node, the current node is
`aria-current="step"`, no node is locked, and state/check words come from the backend.

Visual change:

- **Geometry** — one continuous 1.5 px `rule` route that curves between stops, not a straight
  spine. At wide, stops alternate around a center line with at most 48 px lateral offset; at 620 px
  and below the route is a straight vertical spine. An inline SVG route is decorative
  (`aria-hidden`); the `<ol>` remains the accessible structure and reading order.
- **Perspective** — current 56 px (44 compact), next 40 (32), done/future 28 (24); current has one
  2 px accent ring and a soft halo only. No pulse after the first visit; reduced motion is static.
- **Stop content** — current and next show the destination, state word, check word, and one honest
  detail line. Future stops show title and state; details stay collapsed. No equal action buttons
  per row; the whole stop is the target.
- **Gates** — a stop whose `check_state` is not `none` gets one diamond gate mark on the route and
  the word `Check` beside it. A gate is a real check, not a decorative lock.
- **Start/end** — a small `Start` horizon before the first stop and `Course end` after the last;
  `Course end` is only a position label, not a completion claim.
- **Evidence** — one tally row or caption, no percentage. The caption is the backend's count.
- **Companion** — one 32 px companion at the current stop's outer edge at wide; hidden below 620
  px to protect the title and on reduced motion no idle motion. It is never the only marker of
  position; `aria-current` and the state word carry that.

## 5. Lesson: the field stop

One lesson surface, not a document with a check bolted on.

- **Header** — `STOP 2 OF 6`, section title, one objective sentence. No course metadata strip.
- **Body** — one concept, one example/artifact, one action. A sourced image or diagram is a
  first-class artifact with its caption and text equivalent; audio has a visible transcript. If
  media is unavailable, the text equivalent is the lesson, not a broken frame.
- **Check** — the existing typed check is the gate; it stays in the same surface, not a separate
  page. On submit: specific feedback, one retry path, one recorded evidence row. A wrong answer is
  information, not a red failure state.
- **Close** — when evidence is recorded, the companion appears at the gate (one authored beat) and
  the primary action is `Return to the trail`, which lands on the path with the just-recorded stop
  visibly changed. No confetti; no invented score. A secondary `Read the section` opens Textbook
  for the same document.
- **Textbook** remains the full reference. The Guided/Game default shows the short arc; the
  learner can switch views on Home without changing the underlying document.

## 6. Create: choose the shape of the course

- **Step 1 — the goal.** One question, one textarea, real examples. Course name is auto-suggested
  and lives in an `Name (optional)` disclosure; the learner never has to name a course before they
  have seen its shape. Continue is enabled by a non-empty goal.
- **Step 2 — the shape.** Three route cards, not a list of scope labels: `One lesson`, `Short
  course`, `Full course`. Each shows a small honest trail preview, the number of sections if the
  backend/constant knows it, estimated minutes, and the research depth floor. Selecting a card
  selects the scope; the recipe becomes a single `How you will use it` segmented control with plain
  consequences; `Help me tune it` stays collapsed. No extra primary action.
- **Step 3 — the preview.** A trailhead preview with the suggested title, the chosen shape, the
  first stop, and one sentence about what will happen after Create. One primary `Create course`;
  Back secondary; Cancel tertiary. No wall of StatusRows; only facts that change the decision.
- Keep the H-170 rules: title follows goal until edited; no auto-submit; a rejected plan returns
  with its goal and choices; Create writes one course and one draft plan, no lesson until approval.

## 7. Companion seam

Use only the supported host seam, verified against the installed host source. The expected shape is
`host.request('pet.info')` returning the selected pet's name, spritesheet bytes and frame geometry;
the implementation must cache the sheet, draw one frame to a small canvas, and fall back silently
when the pet is absent, disabled, still loading or the request fails. No private imports, no
credential read, no network fetch, no autoplay, no motion if `prefers-reduced-motion`. The sprite is
`aria-hidden` with adjacent visible copy (`Your study companion` or the pet's name); it is never the
only progress marker and never appears in a state where it would imply a metric.

If the host cannot expose the sprite safely, the card ships the Home/path/lesson composition
without it and records the gap; it does not invent a placeholder face.

## 8. Card sequence and evidence

1. **Identity** — companion seam, home header/Continue plate, settings toggle, completion close.
2. **Home** — trailhead plate, one Continue, classroom shelf, settings placement, states.
3. **Path** — trail geometry, perspective, gates, 460/900/1049.
4. **Lesson** — field stop, check, feedback, close.
5. **Create** — goal, shape cards, preview, one create.
6. **Final acceptance** — cold walkthrough and visual score.

One UI writer at a time; each card runs the existing preview harness and M4 gates. No card is done
without before/after captures at 1049/900/460, light/dark, 200% text, reduced motion, keyboard focus
and a state matrix. The final card is adversarial: it tries to find a reason the product is not
impressive, not a reason to call it done.

## 9. Non-goals

- No new avatar system, avatar editor, character creator, pet dialogue, pet progression or pet
  currency. Use the learner's existing Hermes pet or nothing.
- No world map, open exploration, branching narrative, loot, energy, streak pressure, XP, levels,
  leagues, leaderboards, badges or mastery percentage.
- No gradients, glass, blur, drop shadows, decorative left bars, emoji icons, stock photos or
  generated course art presented as evidence.
- No new backend fact, fake demo data or unlabelled precomputed generation.
- No publication, catalog PR, release tag or public announcement. The operator gate stays closed.
