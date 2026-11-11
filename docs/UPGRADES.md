# Coursebook upgrade queue

Adversarial review of the tree as it stands, in priority order. Every item names the defect, the
fix, and its state. "Landed" means the change is in this branch with a test that fails without it;
"in review" means a lane is implementing it in its own worktree and it is not yet verified here;
"open" means nothing has been written.

The rule this list is held to: a capability is only claimed when its path is wired end to end and a
test exercises the seam, not when a function exists.

## P0 — a stated capability cannot complete

| # | Defect | Fix | State |
| --- | --- | --- | --- |
| 1 | GEN-7: a procedure objective needs a `verification` checklist, but the lesson rule required `quiz` for every recipe except one-off/parent, so a hands-on lesson either cannot author or ships a quiz about the act | the check kind follows the evidence target (`CHECK_KIND_BY_TARGET`); plan rule 5b compares kind as well as family; lesson fixtures migrate to real verification checks | in review |
| 2 | GEN-1: an unsourced plan can be stored `independently_validated` with `facts_unverified: false` | an independent outcome requires a `sourced` objective or a `supported` claim verdict; otherwise the weaker honest label and `facts_unverified: true` | in review |
| 3 | MEDIA-1: no image coherence check existed; a generated picture was stored after magic-byte and size checks only | a review gate dispatches the host vision tool, requires three typed checks, and never approves on prose, error or missing keys; a rejected picture re-prompts once then degrades to text with the reason | landed |
| 4 | MEDIA-3: the image prompt was outside the answer-leak scan, so a figure could carry the checked answer while the check was open | the same scan covers `media[].spec` | in review |
| 5 | The review gate cannot obtain an approval from the host: `vision_analyze` returns a multimodal envelope with no text, and under `hermes serve` the registry answers `Unknown tool`, so art ships `unreviewed` | a verdict-capable host tool (`media_review`: image plus rubric in, JSON out) or an in-plugin aux-vision call with a JSON contract | open |
| 6 | CREATE-1: "One task" plus any size was refused on every attempt, so the plan was never authored | `coerce_recipe_scope` in the kernel, the domain row and the form | landed |
| 7 | CREATE-2/CREATE-3: starting level was an optional free-text box whose own placeholder matched no level token | a one-tap None/Some/Confident question on the create screen, carried into the plan input | in review |
| 8 | GEN-3: no deterministic rule read level, so a learner who said "none" at auto repair could be handed a head-gasket replacement first | plan rule 1b refuses a beginner's first objective when it is a procedure or a transfer | landed |
| 9 | WIRE-1: the syllabus mapping could never be approved — the only control that records the review waited on that review | the primary is enabled whenever the mapping is fresh, and the empty decision set the backend accepts is sent | landed |
| 10 | WIRE-6: generated world art never reached a lesson; the resolver read `kit.plates` while the backend serves `world.assets` | resolve `assets` by section, then the world hero, then the typographic field | landed |

## P1 — the beginner experience, which is the stated purpose

| # | Defect | Fix | State |
| --- | --- | --- | --- |
| 11 | GEN-5: scope caps units, objectives and weeks but not sections, so a "short" plan can carry 24 | sections-per-unit and total caps derived from the existing dials, enforced in the plan rules | in review |
| 12 | GEN-6: curriculum and prerequisite queries are appended last and cut at the budget, so both sequencing questions vanish for a multi-capability goal | reserve a share of the budget for sequencing queries | in review |
| 13 | WIRE-9: `engagement.award` has no caller, so XP is permanently 0 and the level permanently 1 | award on the real completion seam | in review |
| 14 | WIRE-8: the Field Challenge prompt is the check already on screen and "Try it yourself" leaves the lesson | a distinct prompt, and a control that does what it says (or an honest label) | in review |
| 15 | WIRE-3/WIRE-4: a syllabus course is created with no goal, locale, level or subject domain, and always as Textbook | ask the same three questions after approval and pass all five fields | in review |
| 16 | CREATE-7: "Subject, in your own words" resolves by exact alias, so `auto repair`, `Spanish` and `electrical safety` fall to the generic profile | normalised stem/alias matching | in review |
| 17 | CREATE-4: the approval screen lists objectives with no unit, section, week or time estimate, so approving "the length I asked for" is blind | show the shape being approved: units, sections, weeks, estimated minutes | open |
| 18 | CREATE-6: approval queues nothing, while the copy says it starts the first lesson | approval queues the lesson job (or the copy stops saying it does) | open |
| 19 | WIRE-11: a game course has three lesson surfaces — Home opens a chat, a path node opens the classroom, Courses opens the reader | one entry point per course kind | open |
| 20 | MEDIA-2: `sourced_technical` media raises `MediaUnavailable`, and required media is enforced at spec level, not artifact level | state the unavailability as a typed reason at spec time; enforce required at artifact level | open |
| 21 | MEDIA-7: with no host media seam, declared media disappears with no per-item reason | every dropped item carries its reason into the lesson document | open |

## P2 — polish that reads as dishonesty or a dead end

| # | Defect | Fix | State |
| --- | --- | --- | --- |
| 22 | UX-2: the settings sheet says XP and streaks "never" exist and then shows an XP chip | one voice, one conditional | in review |
| 23 | CREATE-5: "Change the goal" prints "The create form is not reachable from this surface." | return to the form with the brief prefilled, or the real reason plus a control that works | in review |
| 24 | GEN prompt: `_capability_prompt_lines` named only `image_roles[0]` and `audio_roles[0]`, hiding a second permitted role | name every permitted role and its authority | in review |
| 25 | WIRE-12: "Choose a syllabus file" calls `files.requestFolder()` and silently takes the first acceptable file | a real file choice, with the chosen name shown | open |
| 26 | WIRE-13: the egress acknowledgement claims a transfer that does not happen, and the path bypasses it | acknowledge what actually leaves the machine, at the point it leaves | open |
| 27 | UX-3: first run is an invitation plate plus a separate empty shelf with no control of its own | one plate, one action | open |
| 28 | UX-4: the only working install is a clone, two enables and a script | one documented command, verified in a clean profile | open |

## Instruments

- `scripts/check-audit-pin.py` fails when the painted audit was generated against a different
  `desktop/plugin.js` than the one in the tree, and prints the regeneration command.
- `scripts/bump-catalog-pin.sh` moves the catalog entry to a new sha and validates it, so a release
  cannot drift from the pinned tree.

## What is already sound, and should not be re-litigated

Research on the host's own tools with a ledgered fetch and a quote check; scope enforced on units,
objectives and weeks; plan approval gated on a durable fact with a re-read digest; procedure
imagery as a deterministic schematic or a cited source; media generation with typed degradation; the
tutor bound to one lesson run, withholding open answers and dropping unresolvable citations; 93 of
93 contract methods wired.
