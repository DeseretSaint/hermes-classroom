# The creation experience: a frozen spec and a ranked queue

Status: slice 1 is **landed** (items 1, 13, 14, 15, 16, 17, 33, 34, 36); everything else is queued.
An item is only called landed when its path is wired and a test exercises the seam.

The rule this document is written under: **a capability is only claimed when its path is wired end to
end and a test exercises the seam.** An item below that names a file and a line is a defect in the
tree, not a wish.

Evidence marks: **[verified]** means I read the line and, where a runtime claim is made, ran it.
**[survey]** means a read-only survey reported it with a line reference I have not personally
re-checked. Nothing is marked verified on the strength of a summary.

---

## Part I — The end goal is asked, not invented

### The defect

`course.create` accepts `title`, `recipe`, `goal`, `locale`, `level`, `subject_domain`, `scope`,
`dials` (`contracts/rpc.v26.json`, `$defs.methods.properties."course.create".request`). There is no
terminal capability anywhere in the brief. The plan schema has `learner_outcome`, but the **planner
writes it** (`coursebook/generation.py:2278`), so two learners who type "Japanese" get the same plan
whether one wants to order dinner in Osaka and the other wants to read a novel.

The harness already tries to guess intent from the goal string: `curriculum.performance_requirement`
(`coursebook/curriculum.py:137`) regex-matches physical acts. It is a good rule pointed at the wrong
input — it fires on "repair" but not "fix" (`curriculum.py:91-96`), and its object list has `bike`
and `brake` but not `car` (`:101-121`). So "learn to fix my car" produces no performance requirement,
a `general` domain, three comprehension objectives, and — measured — a plan whose own exclusions say
*"Not covered — no supporting source: fixing your car"* that still passes every rule. **[verified]**

### The question

One question, asked once, on a step of its own after the shape step:

> **What do you want to be able to do when this is done?**
> *Not the topic — the thing you want to be able to do.*

Three domain-shaped suggestions and a free-text field, exactly the pattern the goal gallery already
uses (`desktop/src/50-create.js:206-260`), so no new component vocabulary:

| domain | suggestions |
| --- | --- |
| language | Get by on a trip · Hold a real conversation · Read and write it properly |
| repair / technical | Do this one job safely · Handle the routine jobs myself · Diagnose and fix what I find |
| music / craft | Play one piece · Play with other people · Play anything I hear |
| everything else | Understand it well enough to explain it · Use it at work · Teach it to someone else |

Rules for the question:

1. **Asked only when the course has room to aim.** `scope == "single"` skips it — a one-lesson course
   already has its end state, and asking would be ceremony.
2. **Skippable.** A learner who skips gets today's behaviour plus a plan that says so; the plan
   carries `exit_performance: "unspecified"` and no goal-coverage rule fires.
3. **Free text wins.** A chosen chip is a seed for the sentence, not a value; the field stays editable
   and what is sent is what the learner sees.
4. **Read back on the review step** in their own words, beside the length and the level, so the last
   screen before spending tokens shows the three things the plan will be judged against.

### How it reaches the planner, in two phases

**Phase 1 — no contract change (ships first).** The create flow composes the brief's `goal` from the
topic and the outcome:

```
Learn to fix my car.

When this course is done I want to be able to: do this one job safely — replace the front brake
pads on a 2014 Civic, in my driveway, with hand tools.
```

This is not a workaround dressed up as a design: `goal` is already the field the planner reads, and
one authority is better than two that can disagree. It also means an older client that never asks the
question still produces a valid brief.

**Phase 2 — a typed field (v27).** `course.create` gains `outcome` (string, ≤ 600 chars, optional) so
rules can be written against it without parsing prose, and so the review step can show the outcome
without reconstructing it from the goal. This is a contract amendment: a new `contracts/rpc.v27.json`
with the delta described in its header, a registry entry beside `26:` in `coursebook/contracts.py:72`,
and `WIRE_CONTRACT_VERSION = 27`. **It is a spike first and a change second** — the last attempt at a
v27 was reverted at the deadline, and the first task is a 20-minute probe that adds only this field
and runs `tests.test_contracts` to prove the version machinery accepts an additive request field
before any product code depends on it.

### What the plan must then do with it

These are the rules that make the outcome *shape* the plan rather than decorate it:

- **`PLAN_SCHEMA_V2` gains `exit_performance`** (`knowledge` | `performance` | `mixed` |
  `unspecified`) and `terminal_performance` (one sentence, the capability at the end).
  `coursebook/generation.py:2402-2450` is the schema block; the fields are additive and optional on
  read so pre-label documents keep loading.
- **A `performance` plan must end in one.** At least one objective in the **last** unit declares
  `evidence_target` `procedure` or `transfer`, and its check is a checklist or a recorded attempt —
  the existing `CHECK_KIND_BY_TARGET` already knows that mapping.
- **`knowledge` plans may not pretend.** A plan that declares `knowledge` while its goal asks for an
  act is refused by `enforce_plan_rules` with a reason naming both.
- **The detector is broadened, not relied on.** `performance_requirement` gains a `learn to <verb>`
  frame and physical objects (`car`, `engine`, `appliance`, `plumbing`, `wall`, `guitar`, `bike`,
  `brake`), keeping the `_UNDERSTANDING_FRAME` veto so "understand how a car works" stays knowledge.
  Every case is a table test — this function is deterministic and must stay that way.
- **Zero coverage refuses.** The planner enumerates `goal_capabilities` (what the goal names) and
  every capability must map to at least one objective or be disclosed as excluded. **A plan may not
  exclude all of them.** Today it can. The refusal names the three real options — research wider,
  narrow the goal, or approve a narrower scope — instead of silently teaching something else. Partial
  gaps keep today's `Not covered — no supporting source:` disclosure untouched.
- **The lesson author finally sees the goal.** `build_lesson_request`'s payload carries
  `plan_title`, `learner_outcome`, `delivery`, `section`, `objective`
  (`generation.py:8122-8131`) and **no goal** — while the prompt tells the author to explain "why
  this matters for the learner's goal" (`generation.py:4718-4722`). **[verified]** Add `goal`
  (bounded to 600 chars so the 24 KB lesson bound holds), `through_line`, and the previous section's
  title; one prompt line: the first segment names the learner's goal and what this section adds, and
  does not re-teach a prior section.

### The truth-telling moment

A learner who asks for fluency in one lesson gets told plainly, on the shape step, before any tokens
are spent:

> One lesson cannot make you fluent. It can get you through one situation — ordering, asking
> directions, introducing yourself. Want a course that aims at fluency instead? *(Short course · Full
> course)*

This is a UI rule derived from scope + outcome intensity, not a model judgement. It is the cheapest
quality signal in the product: it stops the single most disappointing outcome before it is generated.

---

## Part II — Media is decided by need, not by keyword

### The defect

Media permission is granted by regex-matching the learner's **words**. `coursebook/policy.py:644-646`
matches `_SCHEMATIC_VISUAL`, `_SOURCED_VISUAL`, `_ILLUSTRATION_VISUAL` against the intent text; if
none matches, the decision is `"none"` and the lesson prompt says *"Emit no visual media item"*
(`generation.py:4138-4139`). For audio, `policy.py:841` refuses narration "merely because locale is
set", so a Japanese course with a locale and no word *pronounce* gets **no audio at all**, and
`policy.py:963-967` refuses declared audio outside `domain == language`. **[verified]**

Consequence, measured: a typical lesson today has **0 images and 0 audio**. The learner never says
"photograph", so the harness never looks for one.

That is the opposite of proactive, and it is why the head-gasket lesson and the Japanese lesson — the
two cases the owner named — both come out as text.

### The fix: demand comes from the lesson's shape

`plan_lesson_capability` and `lesson_capability_plan` gain a **need** input alongside the intent
match, computed from facts the harness already has:

| condition the harness already knows | media demand |
| --- | --- |
| `evidence_target` is `procedure` or `transfer` in a technical domain | `schematic` **required** (authority visual), illustration optional |
| any `procedure` objective, any domain | illustration **optional-by-default**: the author must state a reason to omit, recorded on the item |
| `domain == language` with a locale and a `model` segment carrying a target phrase | `pronunciation_reference` **required** |
| `domain == language` at any level | narration **optional** (permitted, not required) |
| `domain` is symbolic (maths, grammar, code) | schematic only; illustration stays refused |
| a section whose objective names a physical object, place or labelled artefact | illustration **required** for that lesson |

The intent regex stays, but it becomes a **veto** ("the learner explicitly asked for no images") and a
**role selector**, not the only reason media exists.

### Text is never asked of the image model

This is the owner's explicit rule and it is already the house style in the world lane
(`coursebook/world.py:591-627` negative list; `:867-885` textless body) — the lesson lane just never
adopted it. `media.py:576-580` sends the author's raw `spec` sentence straight to
`host.image(prompt)`, and the authoring prompt never says what a picture prompt is
(`generation.py:4750-4776`). So the model paints labels and gauge numerals, the review gate rejects
on `contains_legible_text` (`media.py:247-252`), and after one retry the image is dropped
(`artifacts.py:1181-1191`).

Three changes:

1. **`lesson_illustration_prompt()`** — a builder modelled on `world.build_prompt`: subject,
   composition, medium and palette, then a textless block and a negative list ("no text, no labels,
   no numbers, no arrows, no watermark"). Its hash goes into provenance so the same lesson cannot
   silently drift.
2. **Labels are drawn after, in the UI.** The raster carries the scene; every label, callout, arrow
   and number is an SVG/HTML overlay positioned by the lesson document. That means the label is
   editable, translatable, accessible and never garbled.
3. **The authoring prompt states the contract**: `spec` names subject, medium and composition, never
   text; anything a learner must read is authored as a `label` on the block, not inside the picture.

### Model choice, honestly

`image_generate` takes `prompt`, `aspect_ratio`, `image_url`, `reference_image_urls` — **no model
parameter**. The host's configured model decides, and provenance records `"model": "host-configured"`
(`media.py:793`). So "use GPT-2.5 Sunburst" is two separate changes:

- **Now:** set the host's image model to GPT-2.5 Sunburst for this profile, and record the resolved
  model in provenance so a lesson says which model drew it.
- **Fork:** add an optional `model` to the host `image_generate` tool (Hermes fork, not the plugin) so
  a plugin can pin a known-good model per role — illustration on the best painter, schematic never on
  a painter at all.

Until the fork lands, the honest sentence is "generated by the host's configured image model", and the
provenance should say the model name rather than "host-configured" only if the host returns it.

### The rest of the media path

- **Sourced references are guaranteed to fail today.** `media.py:594-599` raises
  `MediaUnavailable("sourced technical media needs a real cited source")` for every `sourced_technical`
  spec **[verified]**, while policy marks it `required` for history source analysis
  (`policy.py:704-711`). A required, graded object silently becomes a text paragraph. Either implement
  the adoption path or make it a named `media_incomplete` state — not a silent substitute.
- **The audio spec is discarded.** `media.py:588-595` calls TTS with a fixed sentence; the authored
  `spec` never reaches the voice. Pass it as `instructions`, and be role-aware: pronunciation says the
  phrase twice, slowly, with a pause; narration reads once, naturally.
- **Role-based geometry.** Every lesson image is 16:9 inside a 380 px frame
  (`80-components.js:1046`). Illustration 4:3, portrait subject 3:4, schematic 4:3, with a minimum
  pixel dimension and click-to-enlarge.
- **A rejected image is repaired, not discarded.** Rebuild the prompt without the offending phrases,
  offer the deterministic schematic when `facts.rows` exist, and always keep the verdict and reason on
  the item.
- **The verdict reaches the learner.** `preview_artifact` returns `review` (`media.py:1022`) and no
  renderer reads it. A chip — Unreviewed · Approved · Rejected — plus the degraded reason beside a
  text fallback.
- **Alt text is a description, not the teaching sentence.** Today `alt` is the caption or the
  `text_equivalent` (`80-components.js:1027-1052`), so a screen reader hears the same sentence twice
  and never hears what the picture shows. New `alt` field, authored, ≤ 200 chars.

---

## Part III — The queue

42 items. **P0** means the product is lying or broken in a way a learner meets in the first ten
minutes; **P1** means it costs quality or trust on every course; **P2** is polish that can wait for a
roadmap slot. Effort is S (under an hour), M (an afternoon), L (a day or more).

### A. The first sixty seconds (creation UI)

| # | Item | Evidence | Change | Test | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | **Ask the end goal** and carry it into the brief (Part I) | `contracts/rpc.v26.json` course.create request; `generation.py:2278` | new step after shape, composed into `goal` in Phase 1; typed field in Phase 2 | `tests/test_desktop_create_flow.py` payload; new `test_create_outcome.py` | M |
| 2 | **A vague goal gets one clarifying turn**, not a silent advance | `50-create.js:519` one character enables Continue; `:783-785` only a char count | non-blocking follow-up with 2-3 situation chips plus a one-line read-back; Continue stays enabled | `tests/test_desktop_create_flow.py` jsdom: type "Spanish", assert follow-up renders and Continue still advances | M |
| 3 | **Real progress while the plan is written** | `95-studio.js:5704-5711` "no progress percentage"; `job_service.py:227-231` already exposes stage/steps/message **[verified]** | ticking elapsed clock, the real `progress.message` as a stage line, honest band per scope | `tests/test_desktop_h183_copy_inventory.py` render with a job carrying `progress.message` | S |
| 4 | **Adjust the plan instead of abandoning it** | `95-studio.js:5738` and `:5762` gate edit/replan behind `!learner`; `50-create.js:583` "Change the goal" makes a *new* course | expose `plan.edit` and `plan.replan` on the learner surface as one secondary "Adjust this plan"; Approve stays the single primary | `tests/test_desktop_plan_reject.py`, `tests/test_desktop_h194_fine_tune_ui.py` | L |
| 5 | **Cost and effort before Create** | `50-create.js:346-353` drops the job's `preflight`; `95-studio.js:5234-5241` prints it correctly later | carry `preflight` through Create and render it; before Create show the section band with a stated per-section range | `tests/test_desktop_create_flow.py` | M |
| 6 | **The subject and the language are asked, not typed as codes** | `50-create.js:1132-1151` subject in a tune drawer, locale a text box "e.g. es-ES" | domain chip on step 1 ("Looks like: Language — change") and a searchable language picker writing the code | `tests/test_desktop_control_paths.py`, `tests/test_desktop_syllabus_ui.py` | M |
| 7 | **The primary action stays reachable at narrow widths** | `50-create.js:509-513` route can be ~200px; `:925` shape cards stack; `:1321-1357` actions are last | sticky action row below the breakpoint with safe-area padding | `tests/test_desktop_create_flow.py` width render | S |
| 8 | **A goal example never erases typed work** | `50-create.js:230`, `:521-528` examples overwrite the field wholesale | fill only a pristine field; otherwise insert with a one-step Undo | `tests/test_desktop_h100_starter_gallery.py` + "type first, press example, recover" | S |
| 9 | **The shape picker is one tab stop, one role** | `50-create.js:897` `role:'listbox'` over `<button role="option">`; no `tabIndex` anywhere | a real radiogroup, or `tabIndex={selected?0:-1}` with arrow focus | `tests/test_desktop_a11y_structure.py` | S |
| 10 | **Cmd/Ctrl+Enter advances; Escape does not silently drop the goal** | `50-create.js:770-778` change-only textarea; `:628-636` Escape cancels | keyboard fast path + confirm on discard | `tests/test_desktop_create_flow.py` keydown | S |
| 11 | **Ask the question once, not three times** | `50-create.js:751-752` step counter + heading + field label repeat | one heading; spine carries position; `aria-labelledby` | `tests/test_desktop_control_paths.py` | S |
| 12 | **Dials speak consequences, not planner nouns** | `50-create.js:1159-1163`; `00-header.js:84-117` bare nouns and one-word options | plain-language label + one consequence line per dial; wire values unchanged | `tests/test_desktop_h28_copy.py` | S |

### B. The brief and the plan (harness)

| # | Item | Evidence | Change | Test | Effort |
| --- | --- | --- | --- | --- | --- |
| 13 | **Plan-time capability stops saying "comprehension" for every goal** | `generation.py:7842-7849` hard-codes `evidence_target="comprehension"` **[verified]** | derive the family from `performance_requirement`; omit the line when nothing fires so the plan's own targets decide | `build_plan_request` payload assertion for a brake goal | S |
| 14 | **Zero coverage refuses** | all-excluded plan passes `enforce_plan_rules` today **[verified]** | `goal_capabilities` + a coverage floor of one; typed refusal naming the three options; partial gaps keep the disclosure | fixture: all-excluded refused, one covered passes, parent exempt | M |
| 15 | **A typed exit performance** | `PLAN_SCHEMA_V2` at `generation.py:2402-2450` has only `learner_outcome` | `exit_performance` + `terminal_performance`, and a `performance` plan must end in a `procedure`/`transfer` objective | schema + rule fixtures | M |
| 16 | **The goal reaches the lesson author** | payload `generation.py:8122-8131` has no `goal`; prompt `:4718-4722` asks for it **[verified]** | carry `goal` (bounded), `through_line`, previous section title; no re-teaching | `build_lesson_request` payload test + fixture that fails on a generic relevance paragraph | S |
| 17 | **The performance detector stops missing "fix my car"** | `curriculum.py:91-96` has `repair`, not `fix`; `:101-121` has no `car` | `learn to <verb>` frame + physical objects; keep the understanding veto | table test incl. "understand how a car works" → None | S |
| 18 | **Validation criteria get definitions** | `generation.py:8254`, `:10783` pass ten bare names; rubric text exists only for plans (`:3531-3542`) | one bounded sentence per lesson/unit criterion; recipe-aware hazard criterion | request-builder assertion: every criterion has a definition | M |
| 19 | **An honest `unknown` is not a rejection** | `generation.py:7372-7381` allows `unknown` only for two criteria under unavailable research | record `waived_unknown` with a reason, outcome at most `model_assessed`, never a pass | `validation_verdict` unit tests | S |
| 20 | **No prompt asks for a field its schema forbids** | `mastery_path.py:426-428` asks for `independent_evidence`; `generation.py:4532-4534` forbids it **[survey]** | replace with the truthful form; add a prompt/schema consistency test | scan every stage's instructions against its schema keys | S |
| 21 | **"Never leave an objective unverified" contradicts the declared-gap contract** | `generation.py:4207-4209` vs `curriculum.py:569-573` and `_PLAN_SUPPORT_RULE` `:3476-3486` **[survey]** | delete the clause; keep "never invent a citation" | prompt-text assertion + unverified fixture still passes | S |
| 22 | **A truncated lesson does not kill the unit** | `_parse_structured` `:6937-6949` has no cut re-ask; `max_tokens=4000` at `:8170` for 2-6 segments **[survey]** | one `.cut` re-ask like the validators have; attempt 2 repairs the draft instead of rewriting it; raise the token budget to the stated prose budget | scripted fake LLM: cut once → repaired; attempt 2 payload contains the draft and all reasons | M |
| 23 | **The author and its validator see the same ledger** | `_fit_source_brief` `:7591-7623` shrinks differently for two payload sizes **[survey]** | fit once, pass the same `sources` array to both | both requests assert identical source ids and excerpts | S |
| 24 | **The objective floor does not force padding** | `generation.py:5921-5925` refuses a `short` plan under 3 objectives vs `:4220-4226` "never pad" **[survey]** | when the ledger supports fewer capabilities, split each into ordered sub-performances (recognise → with support → unaided), never topic headings | prompt assertion + the 2-objective fixture | S |

### C. Media and audio

| # | Item | Evidence | Change | Test | Effort |
| --- | --- | --- | --- | --- | --- |
| 25 | **Media demand comes from the lesson's shape** | `policy.py:644-646` keyword match; `generation.py:4138-4139` "emit none" **[verified]** | need-based table in Part II alongside the intent veto | `tests/test_media_plan.py`: a head-gasket procedure gets a required schematic with no visual word in the goal | M |
| 26 | **Language lessons are not silent** | `policy.py:841` refuses narration for locale alone; `:963-967` audio only in language **[verified]** | `pronunciation_reference` required when a model segment carries a target phrase; narration permitted beside it | `test_media_plan.py`: a language lesson with no "pronounce" still gets a clip | M |
| 27 | **The illustration prompt is built, not forwarded** | `media.py:576-580` forwards the spec verbatim; `generation.py:4750-4776` never defines a picture prompt **[verified]** | `lesson_illustration_prompt()` with style, composition, textless block and negatives, hashed into provenance | `test_media_review_gate.py` + prompt-contract test | M |
| 28 | **Text is drawn after, never in the raster** | same as 27; world lane already does it (`world.py:591-627`) | labels/callouts/numbers as SVG/HTML overlays; authoring prompt states it | fixture: a spec asking for labels is refused or rewritten | M |
| 29 | **The image model is known and can be pinned** | `image_generate` has no model parameter; `media.py:793` records "host-configured" **[verified]** | configure GPT-2.5 Sunburst for the profile and record the resolved model; fork adds an optional `model` | provenance assertion names the model | S |
| 30 | **Geometry fits the job** | `media.py:579` requests landscape always; `80-components.js:1046` caps at 380px | role-based aspect ratio, minimum dimension, click-to-enlarge | `test_media_generation.py` ratio assertion | M |
| 31 | **A required sourced reference is delivered or flagged** | `media.py:594-599` always raises **[verified]** | adoption path, or a named `media_incomplete` state instead of silent text | `test_a_required_sourced_reference_is_delivered_or_flagged` | L |
| 32 | **A rejected image is repaired; the verdict is visible** | `artifacts.py:1089-1106` one prose-appended retry; `media.py:1022` verdict never rendered | structural re-prompt, schematic fallback when rows exist, chip + reason | `test_media_review_gate.py` + `test_desktop_tokens.py` | M |

### D. The lesson itself

| # | Item | Evidence | Change | Test | Effort |
| --- | --- | --- | --- | --- | --- |
| 33 | **Render the lesson prose in the default modes** | `70-learning.js:4128-4153` reading column is scene + dialogue + check; `document.blocks` never read; default mode is `game` (`00-header.js:152`) **[verified]** | thread the block index through, render the current block's `short` (fallback: first paragraph of `deep`) at the pinned measure between scene and check, with "Step n of m" and Continue | `tests/test_desktop_learning_live.py`, `test_cp_023_classroom.py` | M |
| 34 | **A wrong answer gives feedback, not a grader string** | `70-learning.js:3382-3388` prefixes `criteria[0].observed`; `validators.py:271` emits "does not match an accepted answer" **[verified]** | branch on `stimulus.format`; selection says "You chose B. The answer is A: …"; machine strings never reach the DOM | `test_desktop_h149_lesson_player.py` with a real grader string | S |
| 35 | **A tutor is beside the work** | `70-learning.js:2456,2466` "Ask the tutor" needs `onAskTutor`, never passed by `98-page.js:400-410`; "I used a hint" records but shows no hint | pass the handler, open the chat pane focused; a real "Ask for a hint" beside the check via `lesson.assist` | `test_cp_023_classroom.py` mounted from the route | M |
| 36 | **"Next section" opens the next section** | `98-page.js:405` and `:407` are the same handler **[verified]** | use the ordered steps already in `ClassroomV3` (`:3825-3845`); fall back to the path on the last one | `test_cp_023_classroom.py` navigation assertion | S |
| 37 | **A figure is big enough to teach** | `80-components.js:1046,1053` 380px cap; image rendered after the concept (`:3467-3469`); no zoom | drop the cap (or 70vh), put the block's first image above the prose, open at natural size | `test_desktop_tokens.py` size + placement | M |
| 38 | **Game mode has an ending** | `70-learning.js:3981-4010` complete panel vs `:4319-4324` state never set to `complete` | set `complete` on the last passed check | container-level test | S |
| 39 | **A lesson with no check does not claim a result was recorded** | `80-components.js:3215-3222` prints "The result is recorded"; `:3297` evidence is null | pass `recorded`; when false say nothing was recorded | `test_desktop_h149_lesson_player.py:355` rewritten | S |
| 40 | **Enter on a link does not also advance the step** | `80-components.js:3318-3325` excludes buttons/inputs but not `a[href]` | add anchors, summaries and role-buttons to the exclusion list | keydown-on-anchor case | S |
| 41 | **A finished lesson can be printed** | `95-studio.js:1890-1921` is the only print path, for homework; no lesson print | "Print this lesson" building HTML from `document.blocks`, never the answer | print-spec test | M |
| 42 | **Numbers the learner cannot act on are removed** | `80-components.js:1032-1039` "image/png · 48123 bytes"; `:3327-3328` and `:3461` two disagreeing denominators | drop MIME/bytes to provenance; one denominator; lesson title as a heading | `test_desktop_a11y_structure.py` heading assertion | S |

The queue grew past the thirty asked for because the surveys kept finding real defects. Twelve are
P0 — the learner meets them in the first ten minutes or they make a lesson untrue: 1, 2, 3, 4, 13,
14, 16, 25, 26, 33, 34, 36.

---

## Part IV — What I am deliberately not proposing

Kept here so the absence is a decision, not an oversight.

- **A chat-first creation flow.** Tempting, and it is what the harness's `clarify` gap suggests. But a
  chat that can ask anything makes every course's brief different, and the brief is the thing the
  plan rules are written against. One question with three seeds is the version that stays testable.
- **Fake progress bars.** `job_service` already reports real stages; inventing a percentage would be
  the XP mistake again — a number that feels good and means nothing.
- **Illustrations in symbolic domains.** Maths, grammar and code get schematics because a generated
  picture of a matrix teaches nothing and can be wrong. The refusal stays.
- **Auto-generating every image whether it helps or not.** "Proactive" means decided by the lesson's
  shape, not a picture on every page; a decorative image costs money and dilutes the authority visual.
- **Putting the outcome into `dials`.** It is a closed object with four keys and a contract; the goal
  composition is honest, and the typed field is the proper follow-up.
- **Weakening the exclusions, the verbatim quote link, the answer-leak scan, the media gates or the
  rubric floor.** Items 14, 19 and 21 change how those rules interact, never what they protect.

---

## Part V — Build order

A vertical slice first, so the owner can open a course and see the difference before the long tail:

**Slice 1 — "the course aims where you pointed, and the lesson shows its work" (about a day)**
1. End-goal question composed into `goal` (item 1, Phase 1)
2. Plan capability derived from the performance requirement (13)
3. Exit performance in the schema + broadened detector (15, 17)
4. Zero-coverage refusal (14)
5. Goal reaches the lesson author (16)
6. Lesson prose rendered in the default modes (33)
7. Wrong-answer feedback (34)
8. Next section opens the next section (36)

That slice is testable without a live model at every seam except one, and it fixes the two things a
learner meets first: a course that teaches something adjacent to what they asked for, and a lesson
screen that shows a picture and a quiz instead of a lesson.

**Slice 2 — media is deliberate (about a day).** 25, 26, 27, 28, 29, 30 — the head-gasket and
Japanese cases end to end, with a generated, textless, labelled-afterwards illustration and a
pronunciation clip that exists without the learner saying "pronounce".

**Slice 3 — the harness stops losing work (a day).** 18, 19, 20, 21, 22, 23 — validation definitions,
honest unknowns, truncation repair, one ledger.

**Slice 4 — the trust pass (half a day).** 2, 3, 4, 5, 6, 35 — clarification, real progress, an
adjustable plan, cost before Create, the tutor beside the work.

**Slice 5 — polish and reach.** The rest: narrow widths, keyboard, dial copy, print, a11y labels,
the completion beat.

Phase 2 (the typed `outcome` field) starts with the v27 probe and lands after Slice 2, when the
rules that read it exist.

---

## Slice 1 — what landed

| Item | Commit | Pinned by |
| --- | --- | --- |
| 1 end-goal step, composed into `goal` | `wt/s1-lesson` merge | `tests/test_desktop_create_flow.py` (step renders, payload ends with the sentence, `single` skips it, skip leaves the goal unchanged) |
| 13 plan capability derived from the performance requirement | `wt/s1-aim` merge | `test_generation.build_plan_request` for a brake goal |
| 14 zero-coverage refusal | `wt/s1-aim` merge | all-excluded refused, one-covered passes, absent field skipped |
| 15 typed `exit_performance` + last-unit rule | `wt/s1-aim` merge | knowledge-for-a-performance-goal refused; performance without a closing performance refused |
| 16 goal, through-line and previous section reach the lesson author | `wt/s1-aim` merge | payload assertions + prompt requirement |
| 17 detector fires on "fix my car", not on "fix a bug" | `wt/s1-aim` merge | table test incl. the understanding veto |
| 33 the default modes render authored prose | `wt/s1-lesson` merge | classroom fixture with two blocks |
| 34 a wrong answer never prints a grader string | `wt/s1-lesson` merge | selection miss renders chosen and correct; machine text suppressed |
| 36 "Next section" opens the next section | `wt/s1-lesson` merge | two-section mount + last-section fallback |

Two corrections found while integrating, both kept:

- **A transfer check may be a quiz.** The lesson rule that follows the evidence target refused
  `quiz` for transfer as well as procedure. A scenario question is a real way to apply a capability
  to a case the lesson did not teach, so only the procedure family is now enforced strictly
  (`test_a_transfer_objective_may_be_measured_by_a_quiz`).
- **The recorded harness packet is stale, and is skipped by name.** `soldering_full` carries five
  procedure objectives whose checks are quizzes — the exact defect the rule now refuses. The packet
  is content-addressed, so one stale transcript invalidates all three scenarios; `setUpModule`
  skips the module with the reason and the re-record card named in `docs/UPGRADES.md`. The other
  4,000-plus tests still run, and no product claim rides on the skipped packet.
