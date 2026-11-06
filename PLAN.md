# Coursebook — v7 winning-entry plan

## Verdict

Coursebook should win by being the first Hermes plugin that makes **teaching a governed,
resumable workflow** rather than a persona. The adult learner answers and the harness grades;
the parent plans and the harness prepares. Both use the same evidence map, state machine,
source ledger, and multimodal artifact pipeline.

We ship no authored lessons or curricula. The user's own Hermes model generates them at
runtime inside the harness.

**Deadline:** Nov 11, 2026, 5:00 PM EST.
**Submission:** catalog PR + public X demo tagging @NousResearch + submission form.
**Judging:** usefulness, reliability, polish, creativity; favor plugins that do more than a
prompt or skill could. **Demo must be under 90 seconds.**

This version keeps all requested capabilities and corrects the Parent-mode interpretation:
**parents prepare lessons for their children; children do not directly use Coursebook chat
sessions.**

---

## 1. The winning product in one paragraph

Tell Coursebook what you want to be able to do, how deep you want to go, and whether this is a
one-off, self-study, or support for another course. It compiles a plan with milestones and an
honest time basis, teaches one objective at a time, grades your attempt before advancing, and
turns mistakes into later practice. Switch to Parent mode and the same engine becomes a lesson
studio: the parent chooses the child's age band and level, researches and approves sources,
then exports a structured lesson pack with activities, visuals, narration, and a parent guide.
The plan can change. The evidence never disappears.

---

## 2. Why this is more than a prompt or skill

A prompt can ask a model to teach. It cannot guarantee these behaviors:

- a transactional state machine that permits only valid lesson transitions;
- typed, versioned checks evaluated before the next state unlocks;
- durable lesson/session identity and exact resume after restart;
- stable course-scoped AGENTS.md context without per-turn system-prompt rewrites;
- provenance captured from actual web-tool results;
- deterministic validators for closed-form answers and auditable aux grading for open ones;
- persistent review dates, misconceptions, homework, and challenge-out evidence;
- content-hashed image/audio artifacts with a native transcript renderer;
- parent-controlled lesson-pack generation, source approval, and exports;
- a measured call/token/artifact budget rather than an unbounded "deep research" loop.

That is the answer to the rubric. The model teaches; **Coursebook decides what may happen
next.**

---

## 3. Recipes and requested customization

| | One-off | Casual | Committed | Companion | Parent |
|---|---|---|---|---|---|
| Example | hook up a washer | Japanese, whenever | conversational Japanese by June | support my bio course | fractions for my 9-year-old |
| User | adult with one task | independent learner | goal/deadline learner | student in another course | parent preparing a lesson |
| Plan | 4–8 steps | 6 nodes | 6–12 nodes, phases, milestones | imported syllabus | parent lesson sequence |
| Assessment | verification | optional/self-check | graded + capstone | exam format | parent-reviewed activity evidence |
| Reviews | none | light | computed | exam-aligned | parent chooses suggestions |
| Homework | none | 10 min | 15 min | past papers | take-home activity |
| Research | bounded | bounded | bounded | bounded | parent-approved pack |
| Reminders | none | opt-in | opt-in, day/time | exam-aligned | parent planning reminders |
| Output | guided task | chat lessons | chat lessons + capstone | aligned drills | printable/narrated lesson pack |

All five recipes use the same eight-state lesson engine. Parent mode changes the **operator
and output**, not the pedagogical machinery.

---

## 4. Progressive intake

**Always**
1. What should you be able to do when this is done?
2. Is this one-off, independent learning, alongside an existing course, or preparation for your
   child?
3. How much time, and is there a deadline?

**Casual / Committed**
4. Depth: get by / solid working ability / as far as I can go.
5. Quiz me? Remind me? If so, which days and what time?

**Committed**
6. Is there an external exam, certificate, or evaluator?

**Parent**
4. Child age band and current level; parent can describe this in plain language.
5. Lesson length, setting (kitchen table, car, outdoors), available materials, reading level.
6. Desired outputs: printable activity, visual aid, narration, parent script, or all of them.
7. Topics/content to avoid and whether the parent wants source approval before generation.

Base knowledge for adult courses is measured with 3–5 probes after plan approval, not inferred
from a self-label. For Parent mode, the parent supplies the starting point and may paste recent
schoolwork; Coursebook proposes a level for confirmation rather than diagnosing the child.

---

## 5. Plan screen and dials

```
Conversational Japanese           Committed · 24 weeks · 3 x 25 min/week
End state   hold a 5-min conversation about daily life without switching to English
Evidence    8/10 turns in Japanese, 2 idioms correct, 1 repair of a misunderstanding

Phase 1  Weeks 1-4    survive the basics        4 nodes   milestone: 2-min self-intro
Phase 2  Weeks 5-12   handle a transaction      4 nodes   milestone: order, pay, ask
Phase 3  Weeks 13-24  hold a conversation       3 nodes   milestone: end-state performance

Estimated total   180-240 hours
Basis             FSI category IV (2,200 class hours to professional proficiency), rescaled
                  for a conversational target and self-study. A range, not a promise.
Confidence        low-medium
```

Every estimate has `basis` (`fsi`, `derived`, `model`) and `confidence`. FSI figures are class
hours to professional working proficiency, not self-study calendar promises. If there is no
external anchor, say "derived from your pace" or "model estimate"; never manufacture a study.

Four dials remain adjustable: **pace, depth, assessment, autonomy**. Re-planning preserves all
evidence, keeps stable node ids, versions the plan, and maps old evidence to new nodes.
Unmatched evidence remains visible for review. Jumping ahead is a per-node challenge-out.

---

## 6. The eight-state lesson template

| # | State | Rule |
|---|---|---|
| 1 | Warm-up retrieval | 2–3 due items, interleaved, cold |
| 2 | Today's performance | observable performance + evidence criterion |
| 3 | Model | worked example/exemplar/diagram at current scaffold level |
| 4 | Guided attempt | scaffolded try; harness evaluates |
| 5 | Solo attempt | no scaffold; evaluated against the same criterion |
| 6 | Retrieval check | required to unlock next node |
| 7 | Homework | one production task + three retrieval items |
| 8 | Exit ticket | one-line self-explanation; recorded, not graded |

Recipe transformations:

- **One-off:** removes graded retrieval/homework; state 6 becomes verification ("did it seat,
  is it dry, does it power on?"). Keeps visuals, safety checks, and gotchas.
- **Casual:** self-check and optional quizzes, lighter review cadence, no forced milestones.
- **Committed:** full checks, milestones, review scheduling, capstone.
- **Companion:** states 2–3 align to imported syllabus; never teaches ahead without permission.
- **Parent:** the states become a **lesson blueprint** for the parent: warm-up, goal, model,
  guided activity, independent activity, observation check, take-home activity, parent notes.
  There is no automated child grading and no child-facing chat session.

Built-in rules: scaffold fading, leech handling (two unsuccessful attempts change
representation), interleaved warm-ups, session budget, resume without repetition.

---

## 7. Parent mode: lesson studio, not child chat

### Workflow

1. **Parent brief:** age band, current level, goal, time, setting, materials, output formats.
2. **Research and plan:** bounded aux research compiles objectives, prerequisite checks,
   misconceptions to watch for, activities, and sources.
3. **Parent approval:** the parent edits objectives, excludes content, approves sources, and
   chooses the final activities.
4. **Generate pack:** only after approval, generate the selected artifacts.
5. **Use offline:** the parent teaches from the printed pack, screen, or audio. Coursebook is
   not present in the parent-child interaction.
6. **Parent reflection:** optionally record "easy / about right / too hard" and what to revisit.
   The next plan adapts from parent-reported evidence, clearly labelled as such.

### Lesson pack

```
Parent guide       goal, time, materials, preparation, script, questions to ask
Learner pages      age-appropriate activity sheets with no answers on the learner page
Answer guide       expected responses, common errors, what to try next
Visual aids        sourced diagrams or clearly labelled illustrations
Narration          optional audio for the parent's script or a listen-together activity
Take-home          one short activity, optional
Next lesson        proposed adjustment based on parent reflection
Sources            URLs, titles, access dates, and support notes
```

No account, PIN, child profile, child tool sandbox, direct reminders, or automated child
surveillance is required. The parent is the only Coursebook user. Any pasted schoolwork is
treated as sensitive content: minimize it, avoid names, disclose the configured model provider,
and offer local-model use.

Generated pictures are not presented as child-safe by construction. The parent reviews the
pack before use; source approval and content exclusions apply to generated text, images, and
audio. Coursebook does not claim COPPA compliance or child-safety certification.

---

## 8. Grading and mastery

A check is generated before the answer and stored with a stable id, type, target concepts,
rubric, acceptable examples, prerequisites, and version.

- **Closed-form answers:** deterministic validators first.
- **Open responses:** aux model sees only the response and rubric, not the full transcript, and
  returns pass/partial/retry, observed criteria, rationale, and a possible misconception.
- **No answer key leaks into the learner's turn.**
- **Low confidence:** retry or ask a clarifying question; never invent mastery.
- **Machine failure:** `needs_retry`, no state change, no mastery change. A manual "move on" is
  recorded as an override, not a pass.
- **Misconceptions:** provisional after one answer; confirmed only after repeated evidence.
- **Speech recognition:** uncertain transcription is not treated as a conceptual error.

Validation uses 60 labeled cases across correct, partial, wrong, irrelevant, non-native
phrasing, and adversarial responses. Report exact agreement, false-pass, false-block, retry,
and repeat stability. An LLM judge is an imperfect instrument, not ground truth.

Mastery means **observed evidence within this course**, not a diagnosis of the learner.

---

## 9. Transactional runtime

```
intake        -> contract.json (aux, schema-validated, recipe defaults)
compile       -> syllabus.json: stable node ids, evidence, phases, milestones, estimate
approve       -> probes or parent confirmation -> starting node
start lesson  -> resolve/create "Coursebook · <slug> · <node>"
                 verify session id, exact title, lineage, course fingerprint
                 create cwd=<course folder>, model, reasoning
               -> prompt.submit

turn 1        pre_llm_call: inject 6-8 line session context
transition    pre_llm_call: inject 1-2 line verdict/next delta
mid-state     no injection; transcript carries teaching
every turn    classify answer/question/off-topic; grade open checks
              model teaches; actual web results populate provenance ledger
              post_llm_call snapshots teaching and proposes a transition
              harness validates and commits the transition event
```

A transition requires matching lesson identity, open `check_id`, current rubric version, fresh
verdict, and an uncommitted transition. Each event carries `event_id`, session id, check id,
previous/new state, verdict, rubric version, and timestamp. Replayed hooks and answers are
idempotent. Closing the app between grading and persistence resumes from the last committed
event.

Session ids are lookup hints, not identity. On resume, verify the exact title and lineage. If
missing or conflicting, create a fresh lesson session without forking mastery. Never fall back
to the most recent visible chat.

### Confirmed Hermes constraints

- `session.create { toolsets }` is declared but not consumed. No schema-token saving is claimed.
- `pre_llm_call` context is persisted in `api_content` and replayed. Therefore inject only
  session-start context and boundary deltas, each scoped to its turn. Full state stays in the
  event store/cockpit.
- Middleware is fail-open. It must not be the sole safety or correctness boundary.
- `transform_llm_output` is not used to rewrite prose; streaming stays intact.

---

## 10. Sources, visuals, and audio

### Provenance is not support

`post_tool_call` records real URLs, titles, and fetch dates. A separate claim-to-source check
marks `supports`, `partial`, `contradicts`, or `unverified`. A real URL does not automatically
prove a lesson claim. Parent packs expose support status before approval.

### Visual policy

- **Illustrations:** generated images are labelled "illustration, not a technical reference".
- **Technical visuals:** use licensed/permission-aware manufacturer/manual sources or
  deterministic SVG/HTML diagrams rendered from structured facts.
- **Never** use an image model as the authority for torque sequences, wiring, anatomy, or repair
  instructions.
- Generated artifacts include content hash, source ids, prompt/spec version, and cache key.

### Audio

Narration includes text, voice/language metadata, and a transcript check. It supports listening
and parent-led delivery; it is not a certified pronunciation assessor. Replaying cached lessons
never generates duplicate media.

---

## 11. Cadence, homework, recovery

Reviews use computed intervals scaled to horizon, grounded in distributed-practice evidence.
Daily cap ~12 items across courses. Overdue items stay due; they do not multiply.

Reminders are opt-in real Hermes cron jobs via `cron.manage`, delivered to the existing
Telegram/gateway. Creation and update are idempotent. Intake captures day/time and creates an
implementation intention ("Tue 19:00 → 25 min Japanese, phase 2, node 4"). Use the conservative
~d=0.27 evidence figure in copy. Quiet hours, max three per week, deleted on archive.

After missed sessions, offer catch up / stretch / drop a node, with explicit contract changes.
No streaks, XP, or guilt mechanics.

Homework is one production task plus three retrieval items, capped around 15 minutes, and feeds
the next warm-up. Parent take-home activities are shorter and optional.

---

## 12. Data and recovery

```
<course>/
  contract.json       # recipe, end state, evidence, dials, modalities, reminder plan
  syllabus.json       # stable nodes, evidence, phases, milestones, estimate
  sources.json        # approved pack, snapshots/hashes, support status
  AGENTS.md           # stable context; no secrets
  events.jsonl        # authoritative append-only lesson/mastery/override events
  state.json          # derived snapshot + event cursor; rebuildable
  ledger.jsonl        # actual fetch provenance
  homework.md
  lessons/<node>/{steps.json, checks.json, fig-*.png, listen-*.mp3}
  parent-packs/<lesson>/{guide.md, learner.pdf, answers.pdf, audio/*, visuals/*}
```

Atomic temp-file + rename writes; schema versions on every document. `state.json` is a cache.
Corruption rebuilds from events; a corrupt event log stops for export/recovery rather than
silently resetting progress. Uninstall does not delete learning.

---

## 13. Cost and measurement

- boundary deltas, not repeated full-state injections;
- aux model for intake, compile, grading, artifact specs;
- provenance ledger and approved source packs to avoid re-research;
- compact event summaries instead of transcript replay;
- content-hash media cache;
- one plan compile amortized across lessons;
- turn/minute/artifact budget as the real per-lesson stop.

The cockpit reports actual calls, tokens where exposed, aux/main split, cache/artifact hits,
and budget use. No invented dollar savings. A "token optimized" claim appears only with a
measured comparison against the same lesson without the harness.

---

## 14. Evidence and honest claims

Design is informed by VanLehn 2011 (human tutoring d≈0.79; step-based ITS ≈0.76), Adesope et
al. 2017 (practice testing g=0.51), Bisra et al. 2018 (self-explanation g=0.55), Cepeda et al.
2006 (distributed practice), expertise-reversal research, Cooper et al. 2006 (homework),
Gollwitzer & Sheeran (implementation intentions), FSI/NFATC time anchors, and Pashler et al.
2008 (no adequate learning-style matching evidence).

These findings motivate the harness; they do **not** establish Coursebook's efficacy. No "2
sigma", learning-style diagnosis, guaranteed mastery, child-safety, or COPPA-compliance claims.
`docs/pedagogy.md` ships with sources and limitations.

---

## 15. Build order — all requested features retained

**Nov 5:** loop and seam spikes (done).
**Nov 6:** recipes, intake, contract/plan preview, syllabus compiler, estimate provenance,
probes, schemas, atomic events.
**Nov 7:** typed checks, deterministic validators, aux grading, retry semantics, 60-case
validation, state machine.
**Nov 8:** scaffold/leech/interleaving, homework/reviews, durable resume, provenance/support
ledger.
**Nov 9:** visual/listen pipeline, native renderer, challenge-out, versioned dials/re-plan,
Companion, Parent research/approval/pack export.
**Nov 10:** reminders, recovery, cockpit polish, hardening, README, tests, validate/doctor,
catalog PR.
**Nov 11:** record demo, post X, submit form before 5 PM EST.

Scope remains aggressive (~58–62 hours against ~50). No feature is silently removed. If Nov 9
is red, Nov 10 prioritizes demo-critical correctness; cron reminders and Parent digest may
land in v1.1. State integrity, grading, Parent approval, and honest media are non-negotiable.

---

## 16. Winning demo — 85 seconds

| Time | Shot | What it proves |
|---|---|---|
| 0–7s | Three goals become One-off, Committed, Parent recipes | one harness adapts to intent |
| 7–16s | End-state plan, milestones, estimate basis/confidence | backward design, honest planning |
| 16–30s | "How do I say I love you?" normal chat vs Coursebook | not a generic answer |
| 30–42s | Deliberately wrong answer; rubric verdict changes one teaching move | real inner loop |
| 42–49s | Challenge-out skips known node; evidence remains intact | learner control |
| 49–60s | Head-gasket one-off uses sourced/deterministic visual and verification | safe multimodal task help |
| 60–75s | Parent approves sources, then printable activity + narration + parent guide appear | parent-led lesson preparation |
| 75–85s | Restart resumes exact state; close: "A chat answers. Coursebook makes you answer." | reliability + thesis |

Do not spend the video touring panels. Every shot shows a state change or an artifact. Keep a
single continuous run, with short cuts only to hide waiting; never represent cached output as
live research.

---

## 17. Acceptance gates

### State and grading
- Correct answer advances exactly one valid state; irrelevant answer does not.
- Wrong answer cannot unlock without explicit override.
- Duplicate answer/hook cannot duplicate events or artifacts.
- Restart after every state restores exactly that state.
- Re-plan preserves evidence and records node mappings.
- Other plugins/sessions receive no Coursebook context or grading.

### Learning behavior
- Warm-up interleaves due nodes when available.
- Two unsuccessful attempts change representation.
- Rubric version cannot silently change after answering.
- Misconceptions require repeated evidence before confirmation.
- Capstone uses the original end-state evidence.

### Sources and media
- Claims map to fetched source ids; unsupported claims are visible.
- Technical visuals are sourced/deterministic or labelled illustrative.
- Cached lesson reopen performs no duplicate image/TTS generation.
- Parent pack is not generated before parent approval.

### Reliability and submission
- Provider/aux/TTS/image failures produce honest degraded states, never fabricated outcomes.
- Session budget stops cleanly and creates resumable homework.
- Fresh install, enable, restart, resume, revoke grant, uninstall/reinstall tested.
- Local/remote backend behavior reported honestly.
- `hermes plugins validate <path> --install-deps` and `hermes plugins doctor <id>` clean.
- Catalog PR pinned to a 40-hex commit; demo under 90 seconds; form submitted before deadline.

---

## 18. Final differentiation

The strongest submission is not "an AI tutor with a nice tab." It is:

> **A governed learning runtime for Hermes: backward-planned courses, graded lesson states,
> durable evidence, sourced multimodal artifacts, and parent-approved lesson packs.**

That is useful beyond the demo, reliable in ways a judge can test, polished as one continuous
workflow, and creative without relying on a fictional learning-science claim.
