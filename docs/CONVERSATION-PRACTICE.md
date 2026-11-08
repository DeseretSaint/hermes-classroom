# Conversation practice: frozen spec and contract (H-140)

| | |
|---|---|
| Card | `H-140` / `t_ed8f9900` (design and contract half of `H-120` / `t_5eadfbca`) |
| Status | Frozen. H-120 implements against this document; H-140 writes no product code |
| Base | `25467cf` (master) |
| Authority | `PREBUILD_SPEC.md` section 8 (grading gate), section 5 (evidence classes), `docs/GRADING-LANES.md`, `docs/ASSESSMENT-BREADTH.md` sections 2.2 and 9 |
| Contract delta | additive `cb.rpc` v15 (4 methods, 1 optional stimulus property) |
| Storage delta | additive `cb.db` v11 (2 tables, no backfill, no rewrite) |
| Out of scope | audio, pronunciation, model-assessed feedback (H-108), pack-declared practices, parent-recipe practices |

## 1. Problem, measured

The lesson chat is a tutor. It answers questions, teaches and continues a lesson, and
`coursebook/turn.py` grades exactly one thing: an inbound message classified as an `answer` while a
check is open, submitted through `attempt.submit` (`turn.pre_turn`, lines 353-417). Nothing in the
backend or the Desktop offers a bounded back-and-forth with a scenario, a turn limit and one
verdict.

What the repository already has, and what this spec is allowed to reuse:

| Seam | Where | What it already does |
|---|---|---|
| check spec on the section | `domain._check_spec` (line 310): `objectives.evidence_criteria_json[].check_spec` | carries `stimulus`, `reference`, `rubric`, `audit_state` for one objective |
| check row | `checks.stimulus_json` / `rubric_json` / `reference_json` | the durable, versioned item the learner is graded against; `reference_json` is never projected |
| check creation | `domain.check_open` (1311) and `generation` (8127) | two writers, both from a spec that passed audit |
| grading | `coursebook/grading.py: grade` (296) | routes by `reference.kind`; a grader that cannot finish is `needs_retry`, never a pass |
| commit | `domain.attempt_submit` (1576), one `BEGIN IMMEDIATE` | writes the attempt, the single transitions row, the evidence rows and the objective state together |
| chat gate | `coursebook/hooks.py: pre_llm_call` -> `turn.pre_turn` | classifies inbound text and injects a continuation prompt after the transition committed |
| post-turn observer | `turn.record_assistant_snapshot` (558) | writes the assistant turn as a `teaching` segment, revision-fenced |
| binding | `coursebook/bindings.py`, `cb.rpc binding.get` / `binding.abandon` | one authoritative chat per lesson run; detach is a recorded status, never a silent rebind |
| rubric angles | `coursebook/rubrics.py` | six profiles, `validate_rubric`, `serves(profile, evidence_target)` |

The open-response lane is **not** enabled: `configure_aux_grader` is called only from tests, and
`docs/GRADING-LANES.md` section 2.4 keeps it off behind `DEFECTS.md` CB-QA-11. A conversation mode
whose verdict came from a model would therefore be either a permanent `needs_retry` or a fabricated
pass. This spec does not turn that lane on.

## 2. The seven decisions

1. **A practice is a check property, not a new lesson kind.** The declaration rides in the check's
   stimulus. The authoring vocabulary stays `quiz | verification | observation` and
   `stimulus.format` stays `text | selection | verification`. A practice check is a `quiz` with
   `format: "text"` plus `stimulus.practice`.
2. **The verdict is provider-free.** It comes from a new closed reference kind, `conversation`,
   graded by matching the learner's stored turns against the declared targets. No model, no
   network, no adapter.
3. **The transcript is the graded artifact.** The learner's turns are stored by the backend before
   the tutor replies; the tutor's turns are stored for reading. The grader reads only the learner
   turns. Nothing the tutor says can produce a pass.
4. **The lesson run is the session scope, and one bounded practice record sits inside it.** No new
   chat engine, no job kind, no scheduler, no second lifecycle: `practice_sessions` is one row per
   attempt at a practice, `practice_turns` is its append-only log.
5. **The tutor keeps character by prompt directive, and that directive carries no grading power.**
   The opening line is authored, so starting a practice never needs a model call.
6. **Targets in view are a scaffold.** A practice whose target expressions were shown to the learner
   can pass, but the pass is `hinted` and never reaches `independent_evidence`. Only a practice with
   `targets_visible: false` can produce `cold` evidence.
7. **Cancel is not delete and not a grade.** Cancelling ends the practice record, keeps every turn,
   writes no attempt and moves no revision. The check stays open.

## 3. The section declaration

Authored per section (objective) in `objectives.evidence_criteria_json[i].check_spec`. A section may
declare **at most one** practice; a second `check_spec.practice` on the same objective is refused at
audit (`practice_declared_twice`).

The declaration, stored verbatim in `checks.stimulus_json.practice`:

```json
{
  "scenario": "Buying one train ticket at a station counter",
  "learner_role": "a traveller going to Kyoto",
  "tutor_role": "the station clerk",
  "turns": {"min": 3, "max": 5},
  "targets": [
    {"id": "t1", "label": "one ticket to Kyoto, please"},
    {"id": "t2", "label": "how much is it?"}
  ],
  "targets_visible": true,
  "rubric_angle": "language_production",
  "opening": "Welcome. Where are you travelling today?",
  "locale": "ja"
}
```

### 3.1 Validation, all refusal, no coercion

| Field | Rule | Refusal reason |
|---|---|---|
| `scenario` | string, 3 to 300 chars | `practice_malformed_declaration` |
| `learner_role` | string, 3 to 120 chars | `practice_malformed_declaration` |
| `tutor_role` | string, 3 to 120 chars | `practice_malformed_declaration` |
| `turns.min`, `turns.max` | integers, `3 <= min <= max <= 5` | `practice_turn_range` |
| `targets` | 2 to 5 entries; `id` matches `^[A-Za-z0-9][A-Za-z0-9_.:-]*$` and is unique; `label` 1 to 120 chars, unique after `validators.normalize_text` | `practice_targets_invalid` |
| `targets_visible` | boolean | `practice_malformed_declaration` |
| `rubric_angle` | one of `policy.RUBRIC_PROFILES` and `rubrics.serves(angle, objective.evidence_target)` must be true | `practice_rubric_off_profile` |
| `opening` | string, 1 to 300 chars | `practice_malformed_declaration` |
| `locale` | string or null, copied from the check | none |
| section | `objective.evidence_target == "production"` | `practice_evidence_target` |
| check | authoring `kind == "quiz"` and `stimulus.format == "text"` | `practice_check_shape` |
| course recipe | `courses.recipe != "parent"` | `practice_not_available_for_recipe` |
| course cap | at most one practice check per course | `practice_duplicate_in_course` |

The validator lives in one function, `coursebook.practice.validate_declaration(stimulus, reference,
rubric, *, evidence_target)`, and is called by **both** check writers:
`generation._check_payloads` (before the check row is inserted) and `domain.check_open` (after
`_check_spec`, before any write). A malformed practice can therefore never reach a learner, exactly
as an unaudited check cannot.

### 3.2 Key material, and what may be projected

The target expressions the learner must produce are answer key, so they are **not** in the
declaration:

```json
{"kind": "conversation",
 "targets": [{"id": "t1", "match": [{"type": "exact", "value": "..."},
                                   {"type": "regex", "value": "..."}]}],
 "min_turns": 3,
 "max_turns": 5}
```

stored in `checks.reference_json` (internal, never projected). Rules: every declaration target id
appears exactly once and no others; each `match` list holds 1 to 8 clauses; `exact` values are
non-empty strings of at most 300 chars; `regex` values compile and are at most 300 chars; a clause
whose pattern matches the empty string is refused (`practice_targets_invalid`).
`validators.seal_reference` gains this branch, so an unsealed conversation reference cannot be
written.

**Authored shape, and the split.** The lesson author writes one target list, not two. In
`gen_lessons.page_json` and in the section spec, a practice check carries
`stimulus.practice.targets[] = {id, label, match[]}`. `generation._check_payloads` splits it: the
declaration fields (scenario, roles, turns, ids, labels, `targets_visible`, `rubric_angle`, opening)
go to `stimulus.practice`, and only `{id, match[]}` goes to `reference.targets`. The legacy
`reference_answer` and `accepted_answers` fields are still written from the first label and the full
label list, so the answer-guide export keeps a readable entry; the lane is `conversation`, so
neither field can grade anything. `generation.assert_no_answer_leak` must also read the practice
`match` clauses and fail if any appears in the learner page or the document.

The rubric, stored in `checks.rubric_json`:

```json
{"profile": "language_production",
 "pass_rule": "all",
 "criteria": [
   {"id": "t1", "criterion": "Produces the first target expression", "detector": {"kind": "target_phrase", "target_id": "t1"}},
   {"id": "t2", "criterion": "Produces the second target expression", "detector": {"kind": "target_phrase", "target_id": "t2"}},
   {"id": "turns", "criterion": "Holds the exchange for at least 3 and at most 5 learner turns", "detector": {"kind": "turn_count"}}
 ]}
```

There are exactly `len(targets) + 1` criteria, so 3 to 6, which satisfies
`policy.MIN_RUBRIC_CRITERIA` and `rubrics.MAX_RUBRIC_CRITERIA`. `rubrics.validate_rubric(profile,
criteria, evidence_target)` must return `[]` before either writer stores the check. A criterion
without a known detector is refused (`practice_targets_invalid`). `rubric_angle` and
`rubric.profile` must be the same value.

For a generated practice, `_check_payloads` **synthesizes** this rubric from the targets and the
turn range; it does not copy the author's `rubric` array into `checks.rubric_json`. The authored
array stays in `gen_lessons.page_json` for authoring review only. A model cannot author a criterion
the deterministic lane is unable to score, and a practice whose stored rubric has an unknown
detector is ungradeable by construction.

**What the rubric does not claim.** The deterministic lane scores two observables: a target
expression was produced, and the exchange lasted the declared number of turns. It does not score
pronunciation, fluency, meaning, or register, and the practice copy never says it did. Those
aspects stay in the `language_production` profile for a future model-assessed lane with the gate
evidence `docs/ASSESSMENT-BREADTH.md` section 10 requires.

## 4. Where every fact lives

| Fact | Durable owner | Written by |
|---|---|---|
| The declaration (scenario, roles, turns, target labels, opening) | `checks.stimulus_json.practice` | `generation` and `check.open`, from the section spec |
| Target match clauses (key) | `checks.reference_json` | same, through `seal_reference` |
| Criteria and pass rule | `checks.rubric_json` | same, through `rubrics.validate_rubric` |
| Practice attempt state (start, cancel, grade, abandon) | `practice_sessions` (new) | `practice.start`, `practice.end`, `practice.cancel`, `binding`/`lesson.begin` detach paths |
| Learner and tutor turns | `practice_turns` (new) | `turn.pre_turn` (learner), `turn.record_practice_tutor_turn` (tutor) |
| The verdict and the evidence | `attempts`, `transitions`, `evidence` (unchanged) | `domain._commit_attempt`, shared with `attempt.submit` |
| The chat transcript | Hermes host | nobody in Coursebook reads it |
| Losses and refusals | `hook_errors` (existing) | existing snapshot-failure path only |

`lesson_segments` is deliberately **not** an owner. It is the backend-owned teaching record that
`lesson.page` renders (segment kinds `teaching | example | media | source_passage | check_prompt |
feedback | summary`), and learner text or in-character practice dialogue is not teaching prose.
Keeping practice out of it also keeps the Textbook page from growing a second copy of the
conversation. The section's authored practice block is unchanged: `lesson.page` needs no delta.

## 5. The bounded session

### 5.1 States

`practice_sessions.state` is one of `active | graded | cancelled | abandoned`.
"Turn limit reached" is derived (`learner_turns >= turns.max`), never stored.

| From | Event | To | What is written |
|---|---|---|---|
| none | `practice.start` | `active` | session row, revision 0, one `tutor` turn (the authored `opening`) |
| active | a learner chat turn | active | one `learner` turn, session revision + 1 |
| active | the tutor reply | active | one `tutor` turn, session revision + 1 |
| active | `practice.end` (graded) | `graded` | attempt + transitions + evidence, `attempt_id` on the session |
| active | `practice.cancel` | `cancelled` | `ended_at`, `end_reason = learner_cancelled` |
| active | binding detach, run pause, fresh run | `abandoned` | `ended_at`, `end_reason = binding_detached` / `run_paused` |

One **live** session per `(lesson_run_id, check_id)` is enforced inside the write transaction
(`practice_session_exists`). A previously graded, cancelled or abandoned session does not block a
new one: after a `not_yet` or `partial` verdict the learner may practice again on the same run and
check, and the old transcript stays readable and attributable to its own attempt.

### 5.2 Start

`practice.start` refuses unless: the objective and check belong to the enrollment's approved plan;
the check's `reference.kind` is `conversation`; `checks.state == "open"` and `audit_state ==
"passed"`; an active binding exists for the lesson run; the recipe is not `parent`. The opening
line is the authored `opening`, so start is deterministic and spends nothing.

Idempotent on `idempotency_key`: repeating the same start returns the same session, the same opening
turn and the same revision.

Session writes (`start`, `cancel`) carry `expected_revision` in the envelope like every other fenced
write, and refuse on a stale one, but they **never bump** the enrollment revision. A practice action
is not a learner transition; only `practice.end` commits one.

### 5.3 Turns and the limit

A learner turn is written by `turn.pre_turn`'s practice branch, **before** `pre_llm_call` returns
context, so a provider failure or a dropped connection never loses the learner's words. It is a
no-op if the same `turn_nonce(session_id, text, revision)` already exists, so a retried hook call
cannot double-append.

* learner turn text: 1 to 2000 chars. Empty text is not a turn; it is classified as a clarification
  and returns the directive unchanged.
* at `learner_turns == turns.max` the turn is refused with `practice_turn_limit` and the injected
  directive says the practice is complete. The chat turn still runs (the tutor says goodbye); no
  row is written.
* a tutor turn is 1 to 8000 chars, matching the `cb.rpc` segment cap, and is split by the existing
  `segments.split_text` rule rather than truncated.

Turns never bump the enrollment revision. A practice turn is not a transition, and a chat that
appends ten turns must not make every open pane's revision stale. Fencing is per session
(`practice_sessions.revision`): the post-turn observer carries the revision it read pre-turn and a
late callback against a newer revision is discarded, exactly as `record_assistant_snapshot` does for
teaching segments.

### 5.4 End and grade

`practice.end` requires `attempt_nonce` (8 to 64 chars, the caller's), refusals first, no writes:

| Condition | Answer |
|---|---|
| live session missing | `VALIDATION_FAILED` / `practice_not_open` |
| session already `graded` | replay the stored attempt result (idempotent), never re-grade |
| session `cancelled` or `abandoned` | `VALIDATION_FAILED` / `practice_not_open` |
| fewer than `turns.min` learner turns | `VALIDATION_FAILED` / `practice_not_complete`, transcript kept, check still open |
| zero learner turns | `VALIDATION_FAILED` / `practice_empty_transcript` |
| check closed, superseded, or a source revalidation paused it | `CHECK_STALE` or `POLICY_VIOLATION`, as `attempt.submit` does |
| binding not active | `BINDING_NOT_ACTIVE` |
| enrollment revision stale | `STALE_REVISION` |

Then, outside any transaction, `conversation.grade_transcript(reference, rubric, turns)` runs
(provider-free), and the commit half of `attempt_submit` writes everything in one `BEGIN IMMEDIATE`:
attempt row (`answer_kind = "text"`, `answer_json` holds the canonical transcript),
one transitions row, layer-1 `attempt` evidence, layer-2 evidence only for a cold pass, objective
state, check state, idempotency key. A grader failure persists `needs_retry` and advances nothing,
as today.

`answer.text` is the canonical transcript string (learner turns only, one per line, prefixed with
its ordinal). `answer_json` additionally carries `turns[]` (`speaker`, `text`) and
`transcript_sha256`. `answer_kind` stays `text` because `cb.vocabulary.answer_kind` is frozen at
`text | selection`.

**Refactor H-120 must land, named exactly:** extract lines 1663 to 1763 of `domain.attempt_submit`
into `domain._commit_attempt(connection, *, enrollment, check, objective, payload, attempt_id,
answer, answer_hash, graded, evidence_class, method, payload_hash, key, envelope, deadline_exceeded)
` and call it from both `attempt.submit` and `practice.end`. A test asserts the two entry points
produce the same attempt, transition and evidence rows for the same verdict. No second commit path
and no duplicated transaction.

### 5.5 Cancel and disconnect

* **Cancel** (`practice.cancel`, or the pane's Cancel control): session becomes `cancelled`, every
  turn stays. No attempt, no transitions row, no evidence row, no enrollment revision bump. The
  check stays `open` and the section reads "practice not completed". This is the only honest end
  that does not grade.
* **Bindings and runs.** `bindings.bind_session` already detaches a superseded section's binding
  (lines 194 to 198) and moves a chat to another section of the same course. `lesson_begin` pauses
  the previous run for `mode: "fresh"`. Both call sites must, in the same transaction, mark any
  `active` practice session on the affected run `abandoned` with `end_reason`. A detached chat can
  therefore never grade a practice, and a fresh run starts a fresh practice record.
* **Disconnect mid-turn.** The learner turn is already durable. The missing tutor turn is an
  absence, not a lost fact: `practice.state` reports `awaiting_tutor: true` until a tutor turn with
  a later ordinal exists. Reconnecting resumes the same session; `practice.end` does not require a
  tutor turn after every learner turn.
* **Crash or restart.** Sessions and turns are rows. A restarted backend resumes by reading
  `practice_sessions.state = 'active'`; nothing is replayed from the chat.
* **Deleted chat.** `enrollment.delete` / binding deletion keep attempts and practice rows by the
  existing deletion protocol. A conversation practice never depends on a host transcript for its
  verdict.

## 6. The tutor in character

### 6.1 Frozen directive

`coursebook/practice.py` holds one constant, `PRACTICE_DIRECTIVE`, with exactly this text and these
placeholders. `turn.pre_turn`'s practice branch returns it as the hook context; it replaces the
normal `continuation_prompt` for that turn and is appended with the existing
`prompts.CHAT_CAPABILITY_RULE`.

```
Coursebook practice is active. Scene: {scenario}. You are {tutor_role}; the learner is {learner_role}.
Stay in character for the whole practice. Reply in the target language at the learner's level, one
short turn at a time, and ask at most one question per turn.
This is learner turn {n} of at most {max}. {targets_line}
Do not grade, do not score, do not say whether the learner has passed, and do not claim the practice
is a success or a failure: the backend grades the transcript after End practice, and nothing you
write is read by the grader.
Do not break character to explain grammar unless the learner asks for help. When they ask, give one
short scaffold, in character.
When the learner reaches the last turn, close the scene, say the practice is complete and stop.
```

`targets_line` is one of two frozen strings:
`The learner is practising these expressions: {labels}.` when `targets_visible` is true;
`Do not list the target expressions and do not translate them: the learner was not shown them.`
when it is false.

### 6.2 What the tutor may not do

* It may not state or imply a verdict. A sentence like "you passed" changes nothing: the grader
  never reads tutor turns (`conversation.grade_transcript` filters `speaker == "learner"`).
* It may not end the practice. Only `practice.end` or `practice.cancel` changes session state.
* It may not reveal the key when `targets_visible` is false. The declaration carries labels for the
  author and the pane; the directive tells the model not to list them, and the public projection
  withholds them, so a cooperative model and a hostile one produce the same learner-visible facts.
* It may not invent a check, a turn count or a transition. The directive states the count; the
  backend owns it.

### 6.3 Chat controls during a practice

`turn.EXPLICIT_CONTROLS` gains `end_practice -> end_practice` and `cancel_practice -> cancel_practice`.
Both are deterministic (confidence `certain`), route through the same dispatcher envelope pattern as
`attempt.override`, and are handled in the practice branch **before** `turn.pre_turn`, so a message
that ends a practice is never also submitted as an attempt.

Text that is not an explicit control is a practice turn even if it looks like a question. The
classifier is bypassed while a practice is live: the practice branch runs first, and `pre_turn` is
not reached. A test pins that no `attempts` row exists for any practice turn.

Hint handling is unchanged in kind and different in effect. A Hint or Show answer during a practice
writes the existing `evidence.record_assist` row through the existing task, so the eventual attempt
is at most `answer_shown` or `hinted`. It never writes an attempt.

## 7. Grading the final transcript

### 7.1 The lane

`validators.REFERENCE_KINDS` becomes `("exact", "numeric", "selection", "rubric_only",
"conversation")`. `conversation` is a **closed** kind: it is graded locally by
`coursebook.conversation.grade_transcript`, which returns a `grading.GradingResult`. It is not
`rubric_only` and it never consults `configure_aux_grader`.

`docs/GRADING-LANES.md` section 2.1 must gain one row for the new kind and one sentence: the kind is
provider-free, deterministic and refuses a transcript it cannot read. That is the only amendment to
that decision record.

### 7.2 Criteria and verdict

For each criterion, in declared order:

* `target_phrase`: `met` when at least one **learner** turn matches at least one clause for
  `target_id`, after `validators.normalize_text` for `exact` and a case-insensitive search for
  `regex`. `observed` names the target label when `targets_visible` is true and says `target {id}
  not produced` when it is false.
* `turn_count`: `met` when `turns.min <= learner_turns <= turns.max`. `observed` gives both numbers.

Verdict through `validators.verdict_for(outcomes, pass_rule="all")`:
all met `pass`; some met `partial`; none met `not_yet`. No outcomes is `needs_retry`, never a pass.

`next_action` uses the existing vocabulary: `pass -> complete_objective` (forced to
`review_objective` when the evidence class is not `cold`, by the existing rule in
`attempt_submit`), `partial | not_yet -> retry_attempt`.

### 7.3 Evidence class

The class is computed by `_classify_evidence` with one added rule, in this order: a recorded hint or
shown answer still wins; otherwise `targets_visible: true` yields `hinted`, because the target
expressions were in view and producing them is not unaided recall; only `targets_visible: false`
can yield `cold`.

Consequences, stated plainly: a visible-target practice pass can complete the section, and the
objective reaches at most `introduced`, never `independent_evidence`. A hidden-target pass can
reach `independent_evidence`. Neither is mastery, and no copy says it is.

### 7.4 The one feedback result

The attempt result is the `attempt.submit` response shape, plus `transcript_sha256` and
`learner_turns`. The pane renders one compact line from the verdict and the criteria observations
(for example "Not yet: two of three targets were used, over four turns"), with the full criteria
under Review grading. No long rubric prose, no red failure treatment, no score.

## 8. The no-fake-pass refusal path

Every route to a verdict, and what it does:

| Route | Result |
|---|---|
| learner ends with fewer than `turns.min` learner turns | refusal, no attempt, no revision bump, check open |
| learner cancels | session `cancelled`, no attempt, no revision bump, check open |
| session abandoned (detach, fresh run, pause) | `practice_not_open`; no attempt is possible from another chat |
| transcript unreadable (session row missing, turns orphaned, ordinal gaps) | refusal `VALIDATION_FAILED` / `practice_transcript_unreadable`, no attempt, no revision bump |
| reference malformed at grade time (unknown detector, target id mismatch) | grader failure -> attempt persisted `needs_retry`, nothing advances |
| grader raises, times out or returns no outcomes | `needs_retry`, nothing advances |
| tutor says "you passed" | nothing: tutor turns are never read |
| aux grader configured and lying | nothing: the conversation lane never calls it |
| plain `answer.text` submitted to a practice check through `attempt.submit` | `POLICY_VIOLATION` / `practice_requires_practice_end`, no attempt (a practice is not a one-line answer) |
| model claims completion in chat | nothing: only `practice.end` grades |
| turn limit exceeded then more text sent | `practice_turn_limit`; the extra message is never appended or graded |

A pass therefore requires a stored, non-empty learner transcript of at least `turns.min` turns in
which every declared target was produced. There is no other path to `pass`.

## 9. Contract delta, `cb.rpc` v15

Additive over v14: every v14 method name and payload is preserved; the version echo moves to 15; the
method enum grows from 64 to 68. No `answer_kind`, `verdict`, `evidence_class`, `evidence_target`,
`next_action` or error code is added. New refusals ride as `error.details.reason` under an existing
code, the same shape H-130 blessed.

### 9.1 `check.get.stimulus.practice`

`$defs/check_stimulus` gains one optional property, `practice` (object or null, `additionalProperties
: false`):

```json
{"scenario": "...", "learner_role": "...", "tutor_role": "...",
 "turns": {"min": 3, "max": 5},
 "targets": [{"id": "t1", "label": "..."}],
 "targets_visible": true,
 "rubric_angle": "language_production",
 "opening": "..."}
```

Projected by `domain._stimulus_view` (line 3309), the existing closed allowlist that already drops
an unrecognised stored key rather than echoing it. The projection builds `practice` from named
fields only. When `targets_visible` is false, `label` is omitted from every entry and `targets`
carries ids only. The projection never carries a `match` clause, a rubric criterion or a reference:
`check.get` already withholds `reference_json`, and this addition must not reintroduce it. A test
stores a `practice.match` key and asserts the served stimulus does not contain it.

### 9.2 `practice.start`

request `{enrollment_id, objective_id}`;
response `{session_id, check_id, check_version, state, revision, session_revision, turns, transcript[]}`.
`transcript[]` entries are `{ordinal, speaker, text}` and the start returns the single opening
`tutor` turn. `revision` is the enrollment revision read (unchanged); `session_revision` is the
practice session's own counter.

### 9.3 `practice.state`

Read-only, revision 0, no writes: request `{enrollment_id, objective_id}`; response
`{session_id or null, check_id, check_version, state, learner_turns, remaining, awaiting_tutor,
transcript[], attempt_id or null, verdict or null, criteria[]}`. An absent session is `state:
"none"`, not an error. `remaining` is `max(0, turns.max - learner_turns)`.

### 9.4 `practice.end`

request `{enrollment_id, check_id, check_version, attempt_nonce}`; response is the `attempt.submit`
response plus `transcript_sha256` and `learner_turns`, and `session_revision`.

### 9.5 `practice.cancel`

request `{enrollment_id, check_id}`; response `{session_id, state: "cancelled", revision,
session_revision}`. Idempotent: cancelling a cancelled session returns it unchanged; cancelling a
`graded` session is `VALIDATION_FAILED` / `practice_already_graded`.

`practice.*` methods write no job, enqueue no worker and open no new lifecycle. There is no
`practice.turn`: turns arrive through the chat hook, which is already the learner's input surface.

## 10. Storage delta, `cb.db` v11

Additive, two tables, no column change to an existing table, no backfill, no rewrite. Migration
`0011_conversation_practice.sql`; `contracts/db.v11.json` is the new authority and v10 stays on disk
as immutable history.

### `practice_sessions`

`id` (pk), `enrollment_id` (ref enrollments), `objective_id` (ref objectives), `check_id` (ref
checks), `check_version` (integer), `lesson_run_id` (ref lesson_runs), `state`
(`active|graded|cancelled|abandoned`), `attempt_id` (nullable, ref attempts), `revision` (integer,
default 0), `started_at`, `ended_at` (nullable), `end_reason` (nullable:
`learner_cancelled|binding_detached|run_paused`). Indexes: `(lesson_run_id, check_id)`,
`(enrollment_id)`, `(state)`.

### `practice_turns`

`id` (pk), `session_id` (ref practice_sessions), `ordinal` (integer), `speaker`
(`learner|tutor`), `text`, `nonce` (nullable), `created_at`. Unique `(session_id, ordinal)`;
unique `(session_id, nonce)`; index `(session_id)`.

`practice_turns.text` holds learner words, so exports and pack export must treat the table as
learner-owned data: `pack.export` and `course.export` never include it, and `enrollment.delete`
follows the existing deletion protocol for it.

## 11. Files H-120 owns

Backend (Cinder):
`coursebook/practice.py` (new: declaration validator, directive, session and turn writes),
`coursebook/conversation.py` (new: `grade_transcript`),
`coursebook/validators.py` (kind and `seal_reference` branch),
`coursebook/grading.py` (route the kind),
`coursebook/domain.py` (`practice_start`, `practice_state`, `practice_end`, `practice_cancel`,
`_commit_attempt` extraction, the `attempt.submit` refusal, `_classify_evidence` rule, the two
detach call sites), `coursebook/turn.py` (practice branch, explicit controls, tutor turn writer),
`coursebook/hooks.py` (wire the branch), `coursebook/generation.py` (schema property, prompt
version `lesson-prompt.v8` -> `v9`, `_check_payloads`), `coursebook/pack_flow.py` (refuse a pack
check that declares a practice), `coursebook/db.py` and `coursebook/migrations/0011_*`.

Contract: `contracts/rpc.v15.json` (new), `contracts/db.v11.json` (new), `docs/CONTRACTS.md` v15 and
cb.db v11 deltas citing this document, `docs/GRADING-LANES.md` section 2.1 amendment.

UI (Vellum, in H-120 or its UI child): the practice surfaces in `desktop/plugin.js` and the frozen
copy strings. This card writes neither.

## 12. Tests H-120 must land

`tests/test_conversation_practice.py` (new, real migrated DB, real `check.open` or real generated
check, one fake model only where a chat turn is simulated):

| Case | Asserts |
|---|---|
| `test_declaration_refusals` | each row of 3.1 refuses with its named reason and no check row |
| `test_generated_practice_check` | a fake author that emits one practice produces exactly one valid practice check (`stimulus.practice` validates, `reference.kind == "conversation"`, no `match` clause in `check.get`); a second practice in the same course is refused `practice_duplicate_in_course` |
| `test_start_writes_opening_only` | one session, one tutor turn, `session_revision == 1`, enrollment revision unchanged; replay is idempotent |
| `test_start_refusals` | non-practice check, closed check, parent recipe, detached binding, no approved plan |
| `test_chat_turn_appends_once` | a learner message appends one turn; the same nonce twice appends one; no `attempts` row; enrollment revision unchanged |
| `test_turn_limit` | at `max` the next message is refused `practice_turn_limit`, no row, directive says complete |
| `test_end_before_min_turns` | refusal `practice_not_complete`, no attempt, no revision bump, check open |
| `test_end_empty_transcript` | refusal `practice_empty_transcript` |
| `test_full_pass` | all targets produced over the declared turns -> `pass`, check closed, `next_action complete_objective`, one layer-1 row, zero layer-2 for a hinted pass |
| `test_partial_and_not_yet` | one missing target -> `partial`, check open, objective `needs_review`, `retry_attempt`; none produced -> `not_yet` |
| `test_hidden_targets_cold` | `targets_visible: false` full pass -> `cold`, one layer-2 row, objective `independent_evidence`; observed text never names a target |
| `test_no_fake_pass_from_tutor` | tutor text claiming a pass creates no attempt and no verdict; grading reads learner turns only |
| `test_aux_grader_not_consulted` | a configured lying aux grader is never called on a conversation check |
| `test_malformed_reference_needs_retry` | unknown detector or id mismatch -> `needs_retry` attempt, nothing advances |
| `test_attempt_submit_refused_on_practice` | `POLICY_VIOLATION` / `practice_requires_practice_end`, no attempt row, no revision bump |
| `test_cancel_keeps_turns` | session cancelled, transcript intact, no attempt, no revision bump, check open |
| `test_detach_abandons_session` | `bind_session` detach and fresh `lesson.begin` mark the session abandoned in the same transaction; `practice.end` then refuses |
| `test_restart_resumes` | a reopened backend reads the same session and turns; `awaiting_tutor` is true after a learner turn with no reply |
| `test_transcript_hash` | `transcript_sha256` equals the canonical transcript hash and the attempt `answer_json` carries the same turns |
| `test_commit_parity` | `attempt.submit` and `practice.end` produce the same attempt, transition and evidence rows for the same verdict |

`tests/test_contracts.py` additions: v15 is additive over v14 (every v14 method and payload still
validates); the four new methods validate and refuse unknown properties; `check_stimulus.practice`
is nullable, drops a smuggled `match` key, and omits `label` when `targets_visible` is false;
`cb.db` v11 schema matches `contracts/db.v11.json` and a v10 database migrates with no row changes.

`tests/test_grading_lanes.py` additions: `REFERENCE_KINDS` contains `conversation`;
`seal_reference` refuses a conversation reference with no targets or a wildcard clause; a generated
practice check does not take the `exact` or `rubric_only` lane; the `rubric_only` open lane stays
unconfigured and unchanged.

Run order for H-120: the three test files above, then `tests.test_grading_lanes`,
`tests.test_kernel_grading`, `tests.test_generation`, `tests.test_contracts`, `tests.test_hooks*`,
`tests.test_desktop_contracts`, then the full suite.

## 13. Acceptance map for H-120

| H-120 acceptance line | What proves it |
|---|---|
| "A lesson section can declare a conversation practice: scenario, learner role, 3-5 turns, target phrases/grammar, and a rubric angle" | 3.1; `test_declaration_refusals`, `test_generated_practice_check` |
| "The tutor responds in character" | 6.1 to 6.3; directive tests pin the frozen copy and the two `targets_line` variants |
| "The grader evaluates only the final transcript against the section rubric" | 7.1 to 7.3; `test_full_pass`, `test_partial_and_not_yet`, `test_no_fake_pass_from_tutor` |
| "No always-on chat; one bounded session per section; explicit start and end" | 5.1 to 5.5; `test_start_writes_opening_only`, `test_turn_limit`, `test_cancel_keeps_turns`, `test_detach_abandons_session` |
| "The learner sees turns and one feedback result" | 9.2 to 9.4, 7.4; `practice.state` transcript plus the single `attempt.submit`-shaped result |
| "The backend owns the rubric/verdict; no model self-certification" | 8, the whole refusal table; `test_aux_grader_not_consulted`, `test_attempt_submit_refused_on_practice` |
| "Text-only first; audio/pronunciation is H-108" | section 14; no audio field, no upload, no retention anywhere in the delta |
| "Tests with a fake model for scenario/turn limit/rubric/refusal; no fake pass" | section 12 |

## 14. Out of scope, and the follow-ups that own it

* **Audio and pronunciation (H-108).** A spoken practice would add an audio answer surface, which
  `docs/ASSESSMENT-BREADTH.md` section 9 keeps unauthorized. The transcript schema above is
  text-only on purpose.
* **Model-assessed meaning, register or fluency.** Needs the aux lane, CB-QA-11 closed and the
  section 10 gate evidence. Until then the `language_production` profile's other three aspects are
  deliberately unscored, not silently passed.
* **Pack-declared practices.** `pack_flow.check_spec_from_pack_check` refuses a pack check that
  requests one (`practice_not_supported_in_packs`), so an imported pack cannot create an
  ungradeable practice.
* **Parent-recipe practices.** Refused at start and at authoring; a parent's recording path stays
  `observation.record`.
* **Practice in the Textbook document.** Not needed: the authored `practice` block and its check
  render through the existing document projection.

## 15. Risks

| Risk | Mitigation, already in the design |
|---|---|
| A practice check accidentally taking `attempt.submit` and producing a verdict from one line | explicit refusal (`practice_requires_practice_end`) and a test |
| Target matching becoming a gameable string match | the pass also requires the declared turn count, the practice is a scaffolded (`hinted`) evidence class when targets are visible, and no practice pass is ever mastery |
| A second commit path drifting from `attempt.submit` | one extracted `_commit_attempt` and `test_commit_parity` |
| The tutor leaking the key when targets are hidden | the key is never in the projected stimulus, and the directive forbids listing it; the grader and the pane never show it |
| Practice transcript polluting the teaching record | `lesson_segments` is not a writer; two tables own it |
| Scope creep into audio or model grading | section 14; both need a contract revision and gate evidence first |
