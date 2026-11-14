# The chat gate is check-shaped — what the chat lane can collect

| | |
|---|---|
| Card | `t_d4f5bf24` (Upgrade 20 of 50, `docs/UPGRADES-50-2026-11-14.md` §20) |
| Authority | `docs/GRADING-LANES.md` (a stored reference always declares its lane), `docs/CHECKLIST-CONFIRMATION.md` (the confirmation lane is membership-only and self-reported) |
| Contract / DB delta | **None.** No `cb.rpc` bump, no migration, no new answer kind, evidence class or RPC method |
| Code | `coursebook/turn.py` (`chat_answer_for`), `coursebook/grading.py` (`parse_confirmation_numbers`, `chat_collection_refusal`) |
| Proof | `tests/test_upgrade_chat_checklist.py` |

## 1. Defect as measured

`turn.pre_turn` submitted **every** chat answer as `{"kind": "text"}`. A verification checklist
stores `{"kind": "rubric_only"}` with `stimulus.format == "verification"`, and the confirmation
lane only accepts `{"kind": "selection"}`. A typed answer therefore fell through to the open lane,
which this build never configures, so `grading.grade_open` raised `GradingUnavailable`, the command
persisted `needs_retry`, and the learner was told there was a grading outage on every retry while
nothing advanced. The check could not be completed from chat at all.

## 2. Frozen decision

### 2.1 The chat lane collects answers in the check's own kind

Before `attempt.submit`, `turn.chat_answer_for` reads the open check's `reference_json` and
`stimulus_json` and shapes the message into the answer kind that check can collect:

| Check | Chat answer | Lane |
|---|---|---|
| `exact` / `numeric` / `selection` | `{"kind": "text", "text": <message>}` (unchanged) | deterministic, `coursebook.validators` |
| `rubric_only` + `stimulus.format == "verification"` + declared `{id, label}` items | `{"kind": "selection", "selection": [item ids]}` | confirmation, provider-free, `self_reported` |
| `conversation` | `{"kind": "text", ...}` (the transcript lane reads the stored turns) | transcript |
| any other `rubric_only` with no configured aux grader | **refused before submit** | none in this build |
| a checklist on a parent-recipe enrollment | **refused before submit** (`CHAT_CHECK_PARENT_REPORTED`) | `observation.record`, from Parent Studio |

### 2.2 A checklist is answered by numbers, never by prose

`grading.parse_confirmation_numbers` reads step numbers (digits, `1-3`, `one through three`) and
maps each in-range number to the declared item at that position, in declared order. It reads no
other word of the message and consults no model — the confirmation lane's membership-only property
(`CHECKLIST-CONFIRMATION.md` §4) is preserved. A message with no in-range number selects nothing,
so `1` alone is a `partial` confirmation and the phrase **"all of them" is not a tick-list**. That
is the adversarial note on this upgrade, kept as a test: the gate refuses unnumbered prose and
replies with the numbered steps and one sentence saying nothing has been recorded yet.

Standalone number *words* are not read as steps ("no one told me" never ticks step 1); only a
range such as `one through three` uses words.

### 2.3 A check no lane can grade is refused, not looped

`grading.chat_collection_refusal` returns the one readable sentence the learner sees
(`CHAT_CHECK_UNCOLLECTABLE`) when the check is `rubric_only` and not a checklist and
`grading._aux_grader is None`. The gate returns a `block` outcome with that sentence, writes no
attempt row, bumps no revision and leaves the check open. The learner is never told about a grading
outage for a check that has no grader in the first place.

The refusal is therefore at the chat lane's own check-open point — the gate reads the check shape
before it will submit anything for it — and not at submit time. Refusing it inside the
`check.open` RPC for a chat-bound caller would need a new request property on a frozen
`additionalProperties: false` contract (`cb.rpc` v29), which is a wire amendment with release-doc
consequences and is deliberately not part of this change.

## 3. What is unchanged

* `attempt.submit` still fails closed on a text answer to a checklist (`needs_retry`): the command
  layer is not made lenient, only the chat adapter stops sending the wrong kind.
* A parent-recipe enrollment still never takes the confirmation lane; the chat gate refuses a
  checklist for it before submit and points at Parent Studio, where `observation.record` is the
  only recording path.
* The stored reference is still `rubric_only`; nothing is upgraded to a closed kind.
* No learner surface shows a job id, stage name or reason code: the refusal and the numbering
  prompt are whole sentences.
