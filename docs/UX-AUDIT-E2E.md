# Coursebook end-to-end experience audit

Date: 2026-11-11. Tree: `master` at `4c2a89b3` (`desktop/plugin.js` module `d557c82c`).
Read-only audit: no product file was edited to produce this document.

## Question

Has Coursebook kept its purpose as a Hermes Desktop plugin: a learner gives a brief,
answers a few questions, and gets a researched course on any topic, at the length they
chose, starting at their real level, with generated media, a tutor beside every lesson,
syllabus import, and a game mode whose cards, buttons and mascot live inside the world.

## Method

Five independent passes over the repository, each required to cite `file:line` and to
separate what is wired from what is only declared:

1. creation and onboarding (`desktop/src/50-create.js`, `coursebook/generation.py`)
2. research and pedagogy (`coursebook/research.py`, `curriculum.py`, `generation.py`)
3. media and tutor (`coursebook/media.py`, `artifacts.py`, `tutor.py`)
4. syllabus and game-mode wiring (`desktop/src/60-syllabus.js`, `62-syllabus-surfaces.js`, `70-learning.js`)
5. plugin surface and the quality bar (`docs/EXPERIENCE-QUALITY-BAR.md`, `desktop/src/30-home.js`)

Three of the most consequential claims were re-checked by hand before this document
was written: the one-off scope conflict, the `kit.plates` versus `assets` mismatch, and
the quiz-versus-verification rule. All three reproduce.

## Verdict

The purpose is intact in the architecture and broken in five specific places. This is not
a product that drifted into being a chat wrapper: research really runs on the host's own
`web_search`/`web_extract`, scope really constrains unit and objective counts, the tutor
really is bound to one lesson run and really withholds an open answer, media really is
generated through the host and degrades with a stated reason.

What fails is the promise a beginner can feel. Five defects each stop a stated capability
outright, and two of them stop the exact example the owner named: a learner who says "none"
at auto repair.

## P0: capabilities that cannot complete

| id | Defect | Evidence | Fix |
| --- | --- | --- | --- |
| CREATE-1 | "One task" plus "Short course" or "Full course" is refused on every attempt, so the plan is never authored and "Try again" replays the same refusal. | `desktop/src/50-create.js:495-510` rewrites the recipe only while untouched; `coursebook/generation.py:5721-5724` requires a one-off to be exactly 1 unit, 1 objective and scope `single` | Coerce on submit: `single` forces `one_off`; any other scope remaps `one_off` to that scope's default recipe |
| GEN-1 | An unsourced plan can be stored `outcome: independently_validated`, `facts_unverified: false`, and be approvable, because the outcome is computed from criteria and rejections only and `facts_unverified` comes from `research_status` alone. | `coursebook/generation.py:7037-7044`, `:9542`, `:9039-9040` | Derive "grounded" from the claim ledger: require at least one `sourced` objective or a `supported` claim verdict before an independent outcome |
| GEN-7 | A procedure objective must be evidenced by a `verification` checklist, but every recipe except `one_off` and `parent` refuses any check kind other than `quiz`. A hands-on course therefore either cannot author its lesson or ships a quiz about the act. | `coursebook/generation.py:4161-4165` (prompt) versus `:6342-6352` (rule); plan rule 5b compares `evidence_target` only, never `kind`, at `:5789-5802` | Map check kind to evidence target, not to recipe, and make plan rule 5b compare `kind` as well |
| WIRE-1 | The syllabus mapping can never be approved. "Approve this mapping" is disabled until `reviewed_revision` matches, and that button is the only caller of `syllabus.alignment.review`; the backend also rejects the empty decision set it is told is allowed. | `desktop/src/62-syllabus-surfaces.js:303,454`; `60-syllabus.js:620`; `coursebook/syllabus.py:1402` | Enable the primary whenever the mapping is fresh and unblocked, and let review send `decisions: []` |
| WIRE-6 | Generated world art never reaches a lesson. The classroom resolver reads `world.kit.plates`; `world.read` serves `world.assets`. Every game lesson falls back to one field-atlas room. | `desktop/src/70-learning.js:3199-3205` versus `coursebook/world.py:2505` | Resolve `world.assets` by role `section` and `section_id`, then the world hero, then the honest typographic field |

## P1: the beginner experience, which is the stated purpose

| id | Defect | Evidence |
| --- | --- | --- |
| CREATE-2 | Starting level is an optional free-text box inside "Help me tune it", not a question. Its own placeholder, "complete beginner", matches no level token. | `desktop/src/50-create.js:981-1001`; `coursebook/localization.py:88-100,139-157` |
| CREATE-3 / GEN-3 / GEN-4 | No deterministic rule reads level. A plan whose first objective is a head-gasket replacement, for a learner who declared `none`, passes `enforce_plan_rules` with prerequisite assumptions that say the learner can already strip an engine. | `generation.py:5031-5043`, `:5364-5373`, `:5668-5851`; reproduced by the audit |
| GEN-5 | Scope caps units, objectives and weeks but not sections: a "short" plan with 24 sections and a "single" plan with 8 both pass. | `generation.py:344-375`, `:2269`, `:5810-5827` |
| GEN-6 | Curriculum and prerequisite queries are appended after capability clauses and cut at the budget, so at the default short/working cell both sequencing questions are dropped for any goal that names several capabilities. | `coursebook/research.py:652-664,685-686` |
| CREATE-4 | The approval screen shows a flat objective list with no unit, section, week or time estimate, so approving "the length I asked for" is blind. | `desktop/src/95-studio.js:5875`; `generation.py:9661` |
| CREATE-6 | Approval queues nothing. The copy says approval starts the first lesson; the learner must find "Generate lessons", then "Open in Courses", then open the course. | `desktop/src/50-create.js:214`; `95-studio.js:5514-5516,5745-5751` |
| CREATE-7 | "Subject, in your own words" resolves by exact alias, so `auto repair`, `Spanish` and `electrical safety` all fall to the generic domain profile. | `desktop/src/50-create.js:1005-1012`; `coursebook/policy.py:443-447,224-249` |
| MEDIA-1 | No image coherence check exists. Generated illustrations are stored after magic-byte, size and render-safety checks only; nothing compares the picture to the lesson. | `coursebook/artifacts.py:729-742`; `executor.py:326,346` |
| MEDIA-3 | The image prompt (`media[].spec`) is outside the answer-leak scan, and the pixels are never inspected, so a figure can carry the checked answer while the check is open. | `generation.py:6466-6470`, `:2889`; `media.py:159-162` |
| WIRE-8 | The Field Challenge is not a challenge: its prompt is the check already on screen and "Try it yourself" calls `onNextSection`, which leaves the lesson. | `desktop/src/70-learning.js:4021-4027` |
| WIRE-9 | `engagement.award` has no caller anywhere, so XP is permanently 0 and the level permanently 1. | `coursebook/engagement.py:280,355` |
| WIRE-11 | A game course has three lesson surfaces: Home "Continue" opens a chat, a path node opens the classroom, Courses opens the Field Quest reader. | `desktop/src/32-desk.js:600,636`; `90-course.js:3500` |
| WIRE-3 / WIRE-4 | A syllabus course is created with no goal, locale, level or subject domain, and always as Textbook. | `desktop/src/60-syllabus.js:517-520` |
| UX-1 | The first five minutes end in a wait: create writes a course and queues research, and the first lesson needs that job, an approval and a second job. | `desktop/src/50-create.js:212-216,270-318` |

## P2: polish that still reads as dishonesty or dead ends

- UX-2: the settings sheet says XP and streaks "never" exist and, two sections later, admits it shows an XP chip.
- UX-3: first run is an invitation plate plus a separate empty shelf plate with no control of its own.
- CREATE-5: "Change the goal" on the create result screen prints "The create form is not reachable from this surface."
- WIRE-12: "Choose a syllabus file" calls `files.requestFolder()` and silently takes the first acceptable file.
- WIRE-13: the egress acknowledgement claims a transfer that does not happen, and the file path bypasses it.
- MEDIA-2: `sourced_technical` media raises `MediaUnavailable`, and required media is enforced at spec level, not artifact level.
- MEDIA-7: with no host media seam, declared media disappears with no per-item reason.
- GEN-8: eight of eleven validator criteria reach the validator as bare names, including `source_support`.
- UX-4: the only working install is a clone plus `scripts/install-local.sh` plus two separate enables.

## What is genuinely working

- Research on the host's tools, with a bounded budget per scope and depth, a ledgered fetch per source, and a claim-link rule that refuses a fabricated `source_quote`.
- Scope enforced on units, objectives and the week cap, proven by execution.
- Plan approval gated on a durable approvability fact with a re-read digest.
- Procedure imagery is a deterministic schematic or a cited source, never an AI illustration, and schematic values must appear in the cited source text.
- Media generation through `image_generate` and `text_to_speech`, with graceful degradation and a typed reason.
- The tutor is bound to one lesson run, refuses a mismatched run, withholds an open answer, and drops citations that do not resolve.
- Home has one filled action on first run, no launch tour, no fabricated ratings, and distinct loading, error and offline states.
- 93 of 93 contract methods have handlers and every REST call resolves to a route.

## Recommended order

1. **CREATE-1** and **WIRE-1**: two one-file fixes that unblock two whole journeys.
2. **GEN-7**: makes the owner's own example authorable as a checklist instead of a quiz.
3. **CREATE-2 + CREATE-3 + GEN-3**: make level a required question and a deterministic rule. This is the difference between "starts at your level" as copy and as behaviour.
4. **WIRE-6**: makes generated worlds visible in the lesson that was generated for them.
5. **GEN-1 + GEN-8**: stop an unsourced plan from being labelled independently validated.
6. **MEDIA-1 + MEDIA-3**: the coherence gate the product promises.
7. **GEN-5, GEN-6, CREATE-4, CREATE-6**: length honesty and one-action approval.

## Skills and tools used

- `coursebook-desktop-rig` for the product contract, the quality bar and the front-end/back-end ledger method.
- `dogfood` and `requesting-code-review` for the finding shape and the adversarial stance.
- `coursebook-course-generation` for the generation contract; `coursebook-visual-production` for the surface rules.
- Repository instruments: `contracts/rpc.v26.json` enumeration, `scripts/validate_plugin.sh`, `tests/adversarial/attack_state.py`, `scripts/build_plugin.py --check`.
