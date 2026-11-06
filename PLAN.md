# Coursebook — v6 plan

We ship no lessons and no curricula. We ship the runtime: recipe-driven intake, an approved
plan with milestones, a fixed lesson template, a session harness that teaches one state at a
time and gates progress on retrieval, and a parent mode for children.

Deadline: Nov 11, 2026, 5:00 PM EST. Judged on usefulness, reliability, polish, creativity,
and *"plugins that do more than a prompt or a skill could."*

v6 keeps the entire feature list and tightens the machinery: transactional state, a real
grading contract, durable session resumption, safety enforcement, honest media, and an
executable acceptance plan.

---

## 0. v6 refinements

1. **Fail-open grading was the wrong failure mode.** A broken grader cannot advance mastery
   automatically. It now yields `needs_retry`, preserves the state, and offers a learner/parent
   override. Machine failures are separate from pedagogy failures.
2. **The state machine is authoritative and transactional.** A model cannot advance it merely
   by writing a good answer. A transition is committed after grading; tool effects and state
   writes carry ids, so replay cannot double-spend artifacts or advance twice.
3. **Kids safety must survive plugin failure.** Hermes middleware failures are fail-open, so
   they are defense in depth, not a sandbox. Kids sessions therefore use a dedicated profile
   with no shell/browser tools configured and an explicit file-scope folder grant.
4. **Grading separates evidence from inference.** A check is typed and versioned before the
   learner sees it: target concepts, acceptable forms, prerequisites, rubric. Exact grading is
   deterministic where possible; the aux model handles open responses and produces a verdict
   plus rationale. Every answer, result, and override is auditable.
5. **Sessions resume by durable identity, never by recency.** Store the session id for fast
   lookup, then verify the exact `Coursebook · <slug> · <node>` title and lineage. A missing or
   conflicting row creates a new lesson session without forking mastery.
6. **Generated visuals are never called technical instructions.** For safety-critical or
   spatially precise work, retrieve and license-check real service-manual/manufacturer images
   or render deterministic SVG/HTML diagrams from a schema. Image models may provide
   illustrative analogies, labelled as such.
7. **Citations record provenance, not support.** Tool-derived URLs answer "where did this come
   from?" A separate model-assisted claim-to-source check marks whether a source actually
   supports a lesson claim. A URL in the ledger cannot itself certify accuracy.
8. **The default study plan is an estimate, not a diagnosis.** Mastery is "evidence in this
   course", not a claim about human cognition. Time ranges retain their basis and confidence.
9. **The cost readout reports measurements, not invented dollars.** Calls, token counts where
   the provider exposes them, aux/main split, cache hits where exposed, artifact spend/cap.
   "Saved tokens" requires a real comparison; otherwise show usage only.
10. **Every headline feature has a machine-checkable acceptance test.** See §15.

---

## 1. Product definition

You answer three questions and two follow-ups. Coursebook picks a recipe, compiles a plan with
milestones and an honest time estimate, shows it for approval, then runs lessons inside real
Hermes chat sessions whose working directory, model, per-turn context, and tool authority the
harness controls. You do the work; it grades you before it teaches the next thing. The plan is
disposable. The evidence map is durable.

The central claim is deliberately narrow:

> Coursebook changes what happens between turns: it keeps the current objective, evaluates an
> attempt, chooses the next permitted state, and preserves an inspectable record. A normal chat
> can be asked to do those things; it does not guarantee them.

---

## 2. Recipes

| | One-off | Casual | Committed | Companion | Kids |
|---|---|---|---|---|---|
| Trigger | one task, under ~2h | "I want to learn X" | end state + deadline | already in a course | a parent setting up a child |
| Example | hook up a washer | Japanese, whenever | conversational Japanese in 6 months | quiz me for my bio midterm | fractions, age 9 |
| Plan | 4–8 steps | 6 nodes | 6–12 nodes, 3 phases, milestones | their own syllabus | 6 nodes, play-shaped |
| Assessment | verification | self-check, optional | graded + capstone | exam-format | no fail display |
| Reviews | none | 7d, 21d | spaced, computed | compressed to exam | parent decides |
| Reminders | none | opt-in | opt-in, day/time | aligned to exam | parent only |
| Homework | none | 10 min | 15 min | past papers | 5 min, optional |
| Research | bounded | bounded | bounded | bounded | parent-approved pack |

Kids is a recipe, not a separate product; its extra authority and privacy rules are in §8.

---

## 3. Intake and plan

**Always:** end state as a performance → one-off / self-study / alongside a course → time and
deadline.
**Casual + Committed:** depth, whether to quiz/remind, and day/time for reminders.
**Committed:** external test?
**Kids:** who is this for, age band (5–7 / 8–10 / 11–13), what they're working on, what the
parent wants to see. Placement is three playful items, never a test display.

The plan contains an end state, measurable evidence, phases, milestones, a schedule, and an
estimate. Every estimate carries `basis` (fsi / derived / model) and `confidence`. FSI Category
I is 600–750 class hours and Category IV ~2,200 to professional working proficiency; a
conversational target is a fraction and self-study differs. Show a range with its basis, never
a calendar promise.

Four dials (pace, depth, assessment, autonomy) can change mid-course. Re-planning never
rewrites prior evidence: nodes have stable ids, old plan versions are retained, evidence is
mapped to the new nodes, and unmatched evidence stays visible for review. Jumping ahead is a
per-node challenge-out.

---

## 4. Lesson state machine

Eight states, fixed order. Recipes **remove** states; they never add new ones.

| # | State | Rule |
|---|---|---|
| 1 | Warm-up retrieval | 2–3 due items, interleaved, cold |
| 2 | Today's performance | something you'll do; evidence criterion visible |
| 3 | Model | worked example/exemplar/diagram at current scaffold level |
| 4 | Guided attempt | scaffolded try; harness evaluates |
| 5 | Solo attempt | no scaffold; evaluated against evidence criterion |
| 6 | Retrieval check | required for the next node (One-off: Verification; Kids: Show me) |
| 7 | Homework | 1 production + 3 retrieval items (optional in One-off and Kids) |
| 8 | Exit ticket | one line in your own words; recorded, not graded |

Per-node counters implement scaffold fading, leech handling (two unsuccessful attempts change
representation), session budget, and interleaved warm-ups. Resume reconstructs the exact state
from the event log, not from a prose summary.

### The contract for advancing a state

A transition occurs only when:

1. the active session matches the lesson's durable identity;
2. the submitted answer belongs to the currently open check (`check_id`);
3. the check's rubric has not been superseded;
4. the grade is fresh and within its retry budget;
5. the transition has not already been committed.

The harness commits an event containing `event_id`, `session_id`, `check_id`, previous state,
new state, verdict, rubric version, and timestamp. Re-delivery of the same answer or hook is
idempotent. Closing the app between grading and persistence resumes safely from the last
committed event.

---

## 5. Grading contract

A check is generated before the learner sees it and is stored as data:

```json
{
  "check_id": "n4-s6-v1",
  "kind": "short_answer",
  "prompt": "Explain why...",
  "target": ["concept:register", "concept:past-tense"],
  "rubric": ["mentions speaker/listener relationship", "uses past register correctly"],
  "accepted_examples": ["..."],
  "prerequisites": ["n3"],
  "rubric_version": 1,
  "scoring": {"pass": "all required criteria", "partial": "one required criterion missing"}
}
```

- **Closed-form checks** (numeric, selected response, exact conjugation) use deterministic
  validators before any model call.
- **Open responses** use the aux model with the rubric, target, and response — not the full
  teaching transcript — and return `pass | partial | retry`, rationale, observed criteria, and
  a possible misconception.
- **No answer key is injected into the learner turn.** The grader sees the key separately.
- **Low confidence** yields `retry` with a clarifying question or another representation; it
  never invents mastery.
- **Machine failure** yields `needs_retry`; state and mastery stay unchanged. A "let me move
  on" action records an explicit user override, not a pass.
- **Misconceptions are provisional.** One wrong answer creates a hypothesis; repeated evidence
  across items confirms it. A fluent wrong answer can otherwise create a confident fiction.
- **Grader validation:** 60 labeled cases spanning correct, partially correct, wrong,
  irrelevant, non-native phrasing, and adversarial answers. Report exact-match, false-pass,
  false-block, retry rate, and repeat stability. Twenty examples are not enough to establish
  false-pass behavior.

LLM-as-a-judge has known instability and bias; it is treated as an imperfect measurement
instrument, not as ground truth.

---

## 6. Runtime and durable session identity

```
intake        -> contract.json (aux model, JSON schema, recipe defaults)
compile       -> syllabus.json: stable node ids, evidence, phases, milestones, estimate
approve       -> probes -> starting node
start lesson  -> resolve/create "Coursebook · <slug> · <node>"
                 verify session id, exact title, lineage, course fingerprint
                 create cwd=<course folder>, model, reasoning
               -> prompt.submit

turn 1        pre_llm_call: inject 6-8 line session context
transition    pre_llm_call: inject a 1-2 line verdict/next delta
mid-state     no state injection; transcript carries teaching
every turn    classify answer/question/off-topic; grade open checks with rubric
              model teaches; tool results populate provenance ledger
              post_llm_call snapshots taught text and advances via §4 contract
```

`session.create` supports `title`, `cwd`, `model`, `reasoning`, and `idempotency_key`; it does
**not** support per-session toolsets (see §9). A stored session id is a lookup hint, not the
identity: if it cannot be resumed, look up the exact title, verify lineage, and create a new
lesson session only when no valid canonical row exists. Never use the most recent visible
session as a fallback.

`pre_llm_call` injection is persisted as an `api_content` sidecar and replayed. Therefore
injections are boundary deltas, scoped to their turn; full state lives in the event store and
cockpit. Do not inject repeated snapshots.

`post_tool_call` records actual URL/title/fetch date for web results. Provenance is separate
from support: claims cite source ids, and an unsupported claim is marked for correction rather
than hidden behind a real-looking URL.

`transform_llm_output` is not used to rewrite prose because it can require `hold_stream=True`
and kill streaming. Gate progress structurally.

---

## 7. Cadence

Reviews: passed evidence sets a date; intervals scale with horizon. Distributed practice beats
massed practice and the optimal gap grows with the retention interval (Cepeda et al. 2006).
Daily cap ~12 items across all courses; overdue items remain due without multiplying.

Reminders: opt-in real Hermes cron jobs through `cron.manage`, delivered to the user's existing
gateway/Telegram. Intake captures days and time; the message carries an implementation
intention ("Tue 19:00 → 25 min Japanese, phase 2, node 4"). The conservative adherence claim
is ~d=0.27 from the 2025 re-analysis, not the older d=0.65. Quiet hours, max three per week,
deleted on archive. Creating/updating a job is idempotent; no duplicate cron jobs after a
resume or reinstall.

Recovery: a missed week recomputes pace from actual events and offers catch up / stretch /
drop a node, with an explicit contract change. No streaks or XP.

Homework: 1 production + 3 retrieval, ~15 min, into the due queue and next warm-up. The effect
is modest and diminishing (Cooper et al. 2006); more is not a feature.

---

## 8. Kids mode

### Authority

- The parent creates the course, sets goal/dials, and holds a PIN to change them. The child can
  start and answer, not change pace, depth, topics, or research.
- A PIN is a **local control lock**, not an authentication boundary. Store only a salted hash
  outside the child-readable course folder; never store a plaintext PIN in JSON or AGENTS.md.
- Reminders and digests go to the parent only. Placement has no timer or score display.

### Session design

- 10–15 minutes for ages 5–10, up to 20 for 11–13; chunk by task transitions rather than
  claiming a universal attention-span formula. Research supports short, task-dependent bursts,
  not a fixed minutes-per-age rule.
- Audio on by default when reading is a barrier. Spoken answers use Hermes' existing dictation;
  transcription uncertainty is shown to the parent and never silently treated as a wrong
  concept.
- No fail state: "got it / almost / let's try another way". Mastery evidence still changes.
- Specific process feedback, not intelligence praise. Progress is a list of capabilities, not a
  streak.

### Sources and tools

The compile fetches sources and the parent approves the pack before lessons. Lessons draw from
approved source ids and snapshots, with content hashes. Live web is denied in kids sessions.

**Safety architecture:** middleware failures are fail-open, so tool middleware cannot be the
sole child-safety boundary. Kids sessions use a dedicated Hermes profile configured without
shell/browser/code-execution tools and with only the required course-folder grant. The
`tool_request` and `tool_execution` middleware add session checks, allowlists, and path
validation as a second layer. If the profile cannot enforce this, kids mode does not start.

No external links, real-person images, personal-information prompts, scary/violent content, or
unsupervised escalation. "Tell a grown-up" is an instruction, not a safeguarding guarantee; the
parent digest surfaces flagged turns for human review without claiming to detect all risk.

### Privacy

The parent operates the tool locally: no account, server, or plugin telemetry; a nickname and
age band rather than a name/birthdate. Lesson text, transcripts, and model calls still go to
whichever provider the parent configured, disclosed at intake with a local-model
recommendation. Parent digest content is minimal by default.

COPPA concerns online services collecting under-13 data and the 2025 amendments add retention
and disclosure duties. A local parent-operated plugin is a different shape, but the product
copy must not claim COPPA compliance or a child-safe guarantee. Hosted mode would require a
separate qualified privacy review; v1 has none.

---

## 9. Media and cost

### Media

`coursebook_visual` and `coursebook_listen` produce artifacts with a content hash, source ids,
prompt/spec version, and cache key. `TOOL_MEDIA_RENDERER_AREA` renders them in the transcript.

- **Illustrative images:** image generation is allowed, explicitly labelled "illustration, not
  a technical reference".
- **Technical visuals:** prefer a real manual/manufacturer image with provenance and permission
  status, or a deterministic SVG/HTML diagram from structured facts. A generated image is not
  a torque sequence, wiring diagram, anatomical reference, or repair instruction.
- **Audio:** generated narration includes the text version, voice/language metadata, and an
  explicit transcript check; it is not a pronunciation authority for a child's speech.
- Every generated artifact is optional, capped per lesson, and reproducible from its spec.

### Cost

| Mechanism | Effect |
|---|---|
| Delta-only boundary injection | avoids repeated state snapshots |
| Aux model for intake/compile/grading/artifact specs | separates mechanical work from teaching |
| Provenance ledger + approved pack | avoids re-research |
| Compact event/state summary | avoids replaying full transcripts |
| Artifact hash cache | generates once per spec |
| Compile once, lessons many | amortizes planning |
| Session turn/minute/artifact budget | the actual per-lesson stop |

Per-session toolsets are **not available**: the create contract declares `toolsets`, but the
handler does not consume it. Do not claim schema-token savings. The cockpit reports measured
calls, tokens where available, aux/main split, cache/artifact hits, and budget usage. It does
not invent savings or dollar amounts.

---

## 10. Evidence

| Finding | Source | Consequence |
|---|---|---|
| Human tutoring d≈0.79; step-based ITS ≈0.76 | VanLehn 2011 | step-level loop |
| ITS vs conventional ~0.4–0.7 | Kulik & Fletcher 2016; Ma et al. 2014 | realistic README |
| Practice testing g=0.51 | Adesope et al. 2017 | retrieval states |
| Self-explanation g=0.55 | Bisra et al. 2018 | exit ticket and "why" checks |
| Distributed beats massed; gap grows with retention | Cepeda et al. 2006 | computed intervals |
| Worked examples fade/reverse with expertise | expertise-reversal literature | probes and fading |
| Homework modest/diminishing | Cooper et al. 2006 | 15-minute cap |
| If-then plans d=0.65 (2006), ~0.27 (2025) | Gollwitzer & Sheeran | reminders carry a plan |
| FSI Cat I 600–750; Cat IV ~2,200 class hours | FSI/NFATC | ranges with basis |
| No learning-style matching evidence | Pashler et al. 2008 | preference only |
| Sustained attention is short and task-dependent | Ruff & Capozzoli 2003 | chunk by task |
| LLM judges can be unstable/biased | LLM-as-judge literature | rubrics, validation, retry |
| Bloom's "2 sigma" did not replicate as tutoring claim | VanLehn 2011 | do not claim it |

Ship `docs/pedagogy.md` with the explicit caveat: these findings motivate design choices; they
do not establish Coursebook's effect on adults or children.

---

## 11. Data and recovery

```
<course>/
  contract.json       # recipe, end state, evidence, horizon, dials, reminder plan
  syllabus.json       # stable nodes, evidence, phases, milestones, estimate
  sources.json        # approved pack, source snapshots/hashes, support status
  AGENTS.md           # stable voice/level/content rules; no secrets
  events.jsonl        # authoritative append-only lesson/mastery/override events
  state.json          # derived snapshot with event cursor; rebuildable
  ledger.jsonl        # actual fetched sources and provenance
  homework.md
  lessons/<node>/{steps.json, checks.json, fig-*.png, listen-*.mp3}
```

`state.json` is a cache, not the truth. Writes use atomic temp-file + rename, and every write
has a schema version. A corrupted snapshot rebuilds from `events.jsonl`; a corrupt event log
stops and offers export/recovery rather than silently resetting mastery.

The plugin stores only UI preferences and a course registry. Uninstall does not destroy
learning. PIN hashes, provider disclosures, and sensitive flags live outside the child-readable
folder.

---

## 12. Build plan — no feature cuts

**Nov 5 (Thu)** — loop and spike findings (done): hardcoded contract, one session, boundary
injection, state advance, next-turn grading.
**Nov 6 (Fri)** — recipes, progressive intake, contract screen, six-node syllabus, estimate
provenance, plan preview, probes. Add schema validation and atomic event writes now, not later.
**Nov 7 (Sat)** — typed checks, deterministic validators, aux grading, retry semantics, 60-case
grader set, kid verdict mapping. Do not advance mastery on grader errors.
**Nov 8 (Sun)** — transactional state machine, scaffold fading, leech rule, warm-up
interleaving, homework, review dates, durable resume tests.
**Nov 9 (Mon)** — provenance/support ledger, visual/listen tools and media renderer,
challenge-out, dials + versioned re-plan, Companion.
**Nov 10 (Tue)** — reminders, recovery, kids profile/tool enforcement/PIN/source approval/digest,
cockpit, hardening, README, validation, catalog PR.
**Nov 11 (Wed AM)** — demo and submission.

This remains ~58–62 hours against ~50 available. No feature is silently removed. If Nov 9 is
red, Nov 10 follows the demo-critical path; reminders and digest can be delivered as v1.1, but
safety, durable state, and grading cannot be traded away.

---

## 13. Demo (100s)

1. **0:00 — recipes:** Japanese → Casual, washer → One-off, fractions for a 9-year-old → Kids.
2. **0:15 — plan:** end state, phases, milestones, estimate with basis and confidence.
3. **0:30 — same question twice:** normal chat gives a flat answer; Coursebook places the
   learner, teaches one register, provides audio, and waits for a check.
4. **0:50 — wrong answer:** a rubric-based verdict names a provisional misconception, changes
   one teaching move, and schedules a later retrieval.
5. **1:05 — challenge-out:** a node is skipped without moving or erasing milestones.
6. **1:15 — one-off:** head gasket on a 2013 Civic uses a sourced/deterministic technical
   visual, no quiz/homework, and ends in verification.
7. **1:30 — kid:** spoken answer, supportive retry, approved sources, parent controls and
   digest.
8. **1:45 — close:** "A chat answers. This one makes you answer."

---

## 14. Risks and calls

| Risk | Call |
|---|---|
| Model writes past the current state | Only the transition contract can advance; prose is not authority |
| Grader error invents mastery | `needs_retry`, explicit override, validation metrics |
| Duplicate answer/tool result advances twice | `check_id`/`event_id` idempotency |
| App closes mid-turn | Rebuild from committed events; never reset mastery |
| Stale session id or duplicate title | Exact-title + lineage verification; never recency fallback |
| Injected state grows the prefix | Boundary deltas only; sidecar behavior verified |
| Tool middleware fails open | Dedicated restricted kids profile + scoped grant; no unsafe fallback |
| Generated diagram is wrong | Sourced/deterministic technical visuals; illustrations labelled |
| Real URL does not support claim | Provenance/support separation and correction state |
| Child speech transcription is wrong | Mark uncertain; do not turn recognition errors into misconceptions |
| Parent expects child-safety/COPPA guarantee | Explicit limits and disclosure; no hosted child service |
| Timeline false precision | Basis/confidence and ranges |
| Six-day scope | Demo-critical ordering; safety/state/grading non-negotiable |

---

## 15. Acceptance tests (the plan becomes executable)

### Harness

- A correct answer advances exactly one permitted state; an irrelevant answer does not.
- A wrong answer cannot unlock the next node without an explicit override.
- Replaying the same answer/hook does not duplicate an event or artifact.
- Closing/reopening after each of the eight states restores the same state.
- A course re-plan preserves evidence and records old/new node mappings.
- A child-denied tool cannot execute even when the model requests it.
- A second plugin's session never receives Coursebook context or grading.

### Learning behavior

- Warm-up contains due items from more than one node when available.
- Two failed attempts change representation rather than repeat the same prompt.
- A check uses its stored rubric version and cannot be silently changed after answering.
- A wrong answer creates a provisional misconception; only repeated evidence confirms it.
- A capstone uses the original end-state evidence criterion.

### Media/citations

- Every cited claim maps to a fetched source id; missing support is visibly marked.
- A technical visual is sourced/deterministic or clearly labelled illustrative.
- Reopening a cached lesson performs no duplicate image/TTS generation.

### Cost/reliability

- Session budget stops the lesson and writes resumable homework.
- A failed aux/provider/TTS/image call produces an honest degraded state, not a fabricated
  artifact or mastery result.
- The cockpit's counts come from actual recorded calls; no dollar estimate is shown without a
  configured price source.

### Submission

- `hermes plugins validate <path> --install-deps` clean.
- `hermes plugins doctor <id>` clean.
- Fresh install, enable, restart, resume, revoke folder grant, uninstall/reinstall.
- Desktop local and remote behavior explicitly reported; no silent remote filesystem claims.
- Catalog PR pinned to a 40-hex commit and submitted before the review deadline.

---

## Appendix A — retained v4 improvements

| # | Improvement | Impact | Effort | Verdict |
|---|---|---|---|---|
| 1 | Four recipe presets as data | 9 | 2.0 | v1 |
| 2 | Progressive intake | 8 | 1.5 | v1 |
| 3 | Plan preview with phases/milestones | 9 | 3.0 | v1 |
| 4 | Estimate provenance | 8 | 1.0 | v1 |
| 5 | Four dials + mastery-preserving re-plan | 9 | 3.0 | v1 |
| 6 | Challenge-out per node | 7 | 1.5 | v1 |
| 7 | Recovery after missed sessions | 8 | 1.5 | v1 |
| 8 | Implementation intentions | 7 | 0.5 | v1 |
| 9 | Telegram reminders via cron.manage | 8 | 3.0 | v1 |
| 10 | Misconception ledger | 9 | 2.0 | v1 |
| 11 | Session budget | 7 | 1.0 | v1 |
| 12 | Resume, don't restart | 8 | 1.0 | v1 |
| 13 | Interleaved warm-ups | 6 | 0.5 | v1 |
| 14 | Scaffold fading | 7 | 0.5 | v1 |
| 15 | Leech rule | 6 | 1.0 | v1 |
| 16 | Exit ticket | 6 | 0.5 | v1 |
| 17 | Daily review cap | 5 | 1.0 | v1 |
| 18 | Capstone | 7 | 1.0 | v1 |
| 19 | Cost readout/artifact budget | 6 | 2.0 | v1 |
| 20 | Recipe JSONs + failure-mode demo | 7 | 1.0 | v1 |

Deferred: phase boss/transfer item, 60-second explainer, community recipe catalog.
Cut: streaks/XP, learning-style diagnosis, separate SRS UI.

## Appendix B — retained kids decisions

| # | Decision | Impact | Effort | Verdict |
|---|---|---|---|---|
| K1 | Fifth recipe with subtractive defaults | 9 | 1.5 | v1 |
| K2 | Parent controls; child session | 8 | 2.0 | v1 |
| K3 | No fail display | 7 | 0.5 | v1 |
| K4 | Spoken answers | 8 | 1.0 | v1 |
| K5 | Approved source pack; no live browsing | 9 | 2.0 | v1 |
| K6 | Parent digest | 7 | 1.5 | v1 |
| K7 | Audio by task | 6 | 0.5 | v1 |
| K8 | Tool denial middleware | 7 | 1.5 | v1 (second layer) |
| K9 | Content rules in AGENTS.md | 7 | 0.5 | v1 |
| K10 | Age bands/nickname/local-model recommendation | 6 | 0.5 | v1 |
| K11 | Capability list, not streaks | 6 | 1.0 | v1 |
| K12 | Co-use parent/child roles | 5 | 3.0 | def |
| K13 | Printable worksheets | 4 | 2.0 | def |
| K14 | Multi-child profiles | 5 | 2.5 | def |

The kids additions are ~13 hours. The added v6 hardening is not a new product surface; it is
the cost of making the existing claims true.
