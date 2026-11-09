# Adversarial review: game mode, home, parent studio and tutor rail

Status: review before card creation. Date: 2026-11-09.
Reviewed plan: `docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`.
Verdict: **CONDITIONAL GO FOR CARDING.** The direction is sound and the home concept is approved,
but the plan was not build-ready as written. Five gaps were blocking (parent reuse, offline
homework, game-mode engagement, independent visual acceptance, and the parent print artifact).
They are addressed in the amended plan. Cards must not be marked done by their makers.

## Facts checked

- Global Home is currently `FieldDeskHome`, which is a course-bound Continue plate for a selected
  classroom. The approved Home concept is a generic library launcher, so the global and
  course-level homes must split.
- The existing right-side Coursebook pane is a lesson-context card bound to the focused chat. It
  is not a chat and its "Not a Coursebook lesson" copy is accurate for that surface. The tutor
  rail needs a new binding to the active lesson run.
- `Game`, `Guided`, and `Textbook` are currently lesson views (`CB_PRESENTATION_OPTIONS` maps
  `game` to `field_quest`). Game is not a generated world yet.
- `Parent Studio` currently authors parent-led courses through `parent.brief.create`; it does not
  take an existing learner course and generate a take-home pack from it. That is a real gap.
- There is no homework/offline-practice domain, no XP/engagement store, no course-world table,
  and no `tutor.ask` command. These are new product surfaces and must be carded as such.
- The approved Home concept has placeholder caveats: generated text is unreliable, some cards
  show invented stars, and there are two same-weight orange actions. None of those may become
  product truth. The production screen must use real type, real progress, and one primary.
- The existing `VISUAL_MEDIA_PLAN` media rules remain valid: AI illustration is never a
  procedure, measurement or safety authority. World art is a new, separate orientation layer.

## Findings

### F1 — Parent Studio cannot reuse an existing lesson (P0, blocking)

The user asked for a Parent Studio that opens lessons that already exist in game mode or
textbook mode and produces high-quality printouts, activity plans and homework. The current
Parent Studio only authors new parent-led courses. A parent cannot select a learner course,
choose a section, preview the validated lesson, and print a take-home pack.

Required: a source-course picker, a read-only lesson preview, a take-home pack bound to the
source lesson version and content hash, separate parent guide/learner page/answer guide, and a
print/PDF proof. Do not clone or rewrite the source course; do not touch its evidence.

### F2 — Offline homework is missing (P0, blocking)

The plan has no way to send a learner away with a real-world task. The user's Japanese example
is concrete: practise the before-meal and after-meal greetings, or label household objects in
the target language. Adult learners need this too, not only parents.

Required: a typed `homework_task` tied to a course/objective, a specific context, one success
criterion, an optional printable/export, and a completion record that is honestly
`self_reported` or `parent_reported`. No fake grade, no surveillance, no generic "practise for
ten minutes" card. One task, not a second course.

### F3 — The owner's game-engagement override is not in the plan (P0, blocking)

The quality bar currently forbids XP, levels, streaks, badges and progress bars. The owner has
explicitly overridden that for **game mode only**: game mode must be engaging and fun, not a
textbook with a skin. The plan did not record the override, so a worker would either ignore the
owner or silently violate the old gate.

Required: a game-only engagement layer with XP, levels, progress and collectible feedback,
derived from real actions, never used as mastery or evidence, never shown in Parent Studio or
printed packs, and never gating core learning. Textbook and Guided stay calm. The override is a
recorded owner decision, not an unstated exception.

### F4 — Worker output can pass tests without matching the approved visual (P0, blocking)

The concept images are the quality bar. A worker can produce a functionally correct screen that
is still a card grid with wrong type and a generic illustration. The plan named visual quality
but had no independent acceptance process.

Required: every visual card submits to a named visual reviewer with the approved concept frames;
the reviewer scores composition, type, palette, illustration, subject fit and state coverage;
the maker does not call the card done. A failed review returns the card for changes. A final
integration card compares the shipped screens to the concepts at 1049/900/460, light/dark and
200% text. No self-certification.

### F5 — The generated-home concept is not a production UI (P0, blocking)

The approved concept contains garbled microcopy, invented star ratings and a duplicate
create affordance. It is a reference, not a screenshot to reproduce.

Required: production art is textless; all labels, cards, buttons, prices, ratings and progress
are DOM. No fake star ratings or review counts. One primary action. The image model never
generates a UI screenshot. This rule must be in every visual card, not just the plan.

### F6 — Parent print quality is underspecified (P1, fix before print card)

A PDF that dumps lesson prose is not the high-quality take-home pack the user asked for. The
plan must define page roles, low-ink layout, selectable text, image provenance, answer-guide
separation, print margins and a visual proof.

Required: print stylesheet and PDF proof; parent guide, learner page and answer guide distinct;
world art only as captioned orientation; technical diagrams deterministic or sourced; no
answer key on a learner page; no fake completion claim.

### F7 — Game world generation needs a subject policy and a hard technical boundary (P1)

The plan lists subject grammars, but the implementation must prove a head-gasket course cannot
become a lantern district, and AI art cannot carry a torque sequence. A prose prompt is not
enough.

Required: `WorldPolicy` as a pure, tested selector; subject matrix fixtures; anti-generic swap
test; deterministic schematic path for technical procedures; no AI image in an instructional
authority role.

### F8 — Tutor rail can become a second chat by accident (P1)

The current lesson chat and the new rail could both be live, with different bindings. The plan
must make the rail the only learner tutor and move conversation practice into it, or explicitly
keep practice in a named mode of the same rail.

Required: one rail, one thread per run, `Practice` mode using existing `practice.*`, no host
chat in learner mode, authoring chat in Studio only, no tools, no answer keys, no state writes.

### F9 — The card graph can serialize badly (P1, process risk)

All front-end cards edit `desktop/plugin.js`. If they run in parallel, they will collide, and a
worktree created from `HEAD` will not contain a parent's branch changes.

Required: one UI writer at a time; each child merges its parent branch before editing; the
manager/integrator merges only after the reviewer passes; every card has a bounded runtime and
an independent reviewer. No worker completes its own card.

### F10 — Cost and failure honesty for worlds (P1)

Three concept boards plus a kit is real image spend. A failed provider must not leave a broken
Game course.

Required: capped assets, cache by style/course/role/section, real job stages, Textbook fallback,
partial-failure reporting, and no silent retry spend.

### F11 — Approved Home concept details conflict with product truth (P1)

The concept's stars, XP tags and "New course" sign are visual energy, not data. The plan must
not copy invented ratings or duplicate create controls into the shipped screen.

Required: course cards use real course state; no invented reviews; one create primary; layout
may be adjusted by the manager to preserve the concept's feel without false facts.

### F12 — "Textbook mode" ambiguity (P1)

The user said no images for Textbook, but a head-gasket lesson without a diagram loses safety
information. The plan records the distinction: no generated world art, but deterministic or
sourced instructional media may render. This must be confirmed, not assumed.

## Required amendments

The amended plan now includes:

1. Parent Studio source-any-course take-home packs, print proofs and parent/learner homework.
2. A typed homework domain with self-reported/parent-reported completion.
3. A game-only engagement layer with XP/levels/progress, explicitly separated from evidence.
4. A named independent visual reviewer and a concept-parity gate.
5. Textless art and real DOM type as a hard rule.
6. A card DAG with serialized UI writers, review handoffs and bounded runtimes.

## Verdict

Proceed to cards only with those amendments. The first card must freeze the contracts and the
review process; visual cards must route through the visual reviewer. A green test suite is not a
visual pass. A worker saying "done" is not a merge. The final card must be an independent
adversarial acceptance run, not another implementation card.
