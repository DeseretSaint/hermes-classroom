# Optional placement check: frozen specification for H-119

| | |
|---|---|
| Card | `H-141` / `t_3178c5b3` (spec half), implementing card `H-119` / `t_657ef10d` (Vellum) |
| Base | `25467cf1df3062748c63a5a77c7e77975b775aba` (master at pickup) |
| Status | Frozen. H-119 implements exactly this; deviations come back to Atlas before code |
| Contract delta | None. No `cb.rpc` bump, no `cb.db` migration, no new job kind, no new error code, no new route, no provider call |
| Authority | `docs/ADVERSARIAL-REVIEW-V3.md` item 28, `AUDIT.md` item 3 (placement must not add a surprise model call), `PREBUILD_SPEC.md` (one coherent working slice, no partially wired control) |

This document freezes the optional starting-point check the create flow gains before a learner
course is written. It is a decision document, not product code. It changes no contract and makes
no claim about any learner.

## 1. The decision in one paragraph

The create flow already has an optional free-text field labelled Where you are starting from
(`desktop/plugin.js:4637`, sha256
f1b0aba981c3f54275d70e44244337b0deac795b15cd8ebb7bceff1bdefe28e5). A learner who does not know
what to type gets a generic plan. The fix is a short, optional, offline check of four tiny
Japanese tasks that writes at most one bare token, `L0` or `L1`, into that same field. The token
travels through the existing `course.create` and plan-brief inputs, so the plan, the curriculum
brief and the beginner scaffold policy read it with no new plumbing. Nothing else is stored: no
score, no answers, no band history, no evidence row. The check never calls a provider, never
starts a job, never blocks Continue, and never tells a learner what they have mastered.

Why only two outcomes. `L0` and `L1` are Coursebook's own learner levels, and they are the only
tokens the Japanese beginner scaffold table recognises that are not CEFR labels
(`coursebook/localization.py:88-100`, sha256
319736f01832605b3e75240b134d819d8b45d8dc8100d97379c49e65462239ef). The table also accepts `A1`,
`A2` and `BEGINNER`, but a four-item check must not emit a CEFR label: that would be a
certification claim the check cannot support. A four-item multiple-choice check also cannot
support a finer ladder, and inventing `L2` through `L4` would be a diagnosis with no consumer, no
authored content behind it and no way to falsify it. So the check answers one question only: does
this plan start at the very beginning, or past single kana? Everything past that is the learner's
own sentence in the free-text field.

## 2. Where the check lives

The check sits inside the existing Help me tune it (optional) panel, directly under the
Where you are starting from field, on step 2 of the create flow. It is not a fourth wizard step,
not a modal, not a route and not a separate screen. It is offered only when both of these hold:

1. the recipe is not `parent` (Parent Studio has its own typed brief, not a learner level);
2. the Language or locale field names a language with an authored item bank.

For v1 the only authored bank is Japanese, so the offer appears for a locale whose primary
subtag is `ja` (`ja`, `ja-JP`, `JA-jp`). When the locale is blank the entry is not rendered at
all: there is no target language to test. When the locale names another language the panel shows
the one unavailable line in section 5 and the free-text field stays as it is. H-119 must not
generate items for an unauthored language, call a model to make them, or translate the Japanese
bank.

The item bank is product copy, authored in the same place as `RECIPE_COPY`, exported for tests,
and frozen here. It is not learner content, is never served as a lesson, and is not stored in a
pack.

## 3. The four tasks

Each task is one multiple-choice question with four options. There is no free-text scoring, no
audio, no timer and no adaptive branch beyond the early stop in section 4. The learner never sees
whether an individual answer was right, because per-item feedback would turn a placement into a
lesson and leak the bank.

| id | prompt | options (the correct one is marked) | what it separates |
|---|---|---|---|
| `ja-kana-ka` | Which kana is `ka`? | `あ` / `か` (correct) / `さ` / `の` | does the learner know any kana at all |
| `ja-word-neko` | What does `ねこ` mean? | `neko (cat)` (correct) / `inu (dog)` / `tori (bird)` / `uma (horse)` | can the learner decode a kana word |
| `ja-phrase-onegai` | You are at a counter and want to ask for something politely. Which phrase do you use? | `おねがいします` (correct) / `いただきます` / `ごめんなさい` / `おかえりなさい` | does the learner know a set phrase by sight |
| `ja-cost-ikura` | What does `これは いくらですか。` ask? | `How much is this?` (correct) / `Where is this?` / `What is this?` / `Whose is this?` | can the learner read a whole short sentence |

Stored shape per item, one array `PLACEMENT_BANK_JA`:

```
{
  id: 'ja-kana-ka',
  prompt: 'Which kana is "ka"?',
  options: [
    { id: 'a', label: 'あ' },
    { id: 'ka', label: 'か' },
    { id: 'sa', label: 'さ' },
    { id: 'no', label: 'の' }
  ],
  answerOptionId: 'ka'
}
```

Option ids are for the implementation and tests. The learner reads only `label`. The prompt
string in the table above uses backticks for the kana so the document stays readable; the shipped
string is `Which kana is "ka"?` with straight double quotes and no backticks.

## 4. The outcome rule

The check is deterministic and does not use a percentage, a score, a pass mark or a threshold
that the learner can see.

1. The learner answers items in bank order.
2. After two answers that do not match `answerOptionId`, the check stops. The outcome is `L0`.
3. If the learner answers all four with at most one mismatch, the outcome is `L1`.
4. If the learner activates I'm not sure on any item, or stops the check, the outcome is no hint
   (`null`). No later answer repairs an unsure item.
5. If the learner has answered fewer than two items and has not used I'm not sure, the only way to
   leave is to stop, which is rule 4.

The internal result shape, held in React state for the life of the create flow and never sent to
the backend:

| field | type | meaning | leaves the client |
|---|---|---|---|
| `band` | `'L0'` or `'L1'` or `null` | the outcome of section 4 | no |
| `answers` | `{ itemId: optionId }` plus unsure item ids | what the learner picked | no |
| `mismatches` | integer | internal count used by the rule | no |
| `stopped` | `'two_mismatches'` or `'finished'` or `'unsure'` or `'skipped'` | why the check ended | no |
| `level` | `'L0'` or `'L1'` or `null` | the one value written to the level field | yes, only through the existing field |

Two helpers carry this and must be exported from `desktop/plugin.js` for the Node harness:
`placementIsAvailable({ locale, recipe })` returns a boolean, and
`placementOutcome({ answers })` returns the shape above. Both are pure, take no rpc, and read no
clock, provider or database.

## 5. The exact copy H-119 must implement

These strings are frozen. Tests assert them verbatim. The constant is `PLACEMENT_COPY`. No string
here may claim mastery, certification, a score, a percentage, a CEFR label or a pass.

| id | exact string | where |
|---|---|---|
| `entry` | `Not sure where you are starting from?` | directly under the level field, inside the optional panel |
| `entryAction` | `Find my starting point` | the button that opens the check |
| `entrySkip` | `Skip` | beside the entry button, dismisses for this create only |
| `introTitle` | `A starting point, not a test` | first line of the check |
| `introBody` | `Up to four small Japanese tasks. There is no grade and no certificate. Your answers only decide where the plan starts, not what you have mastered.` | under the title |
| `start` | `Start` | primary button on the intro |
| `skip` | `Skip` | always present on the intro and every item |
| `progress` | `Question {n}` | above each prompt, with the live number substituted |
| `unsure` | `I'm not sure` | beside the options on every item |
| `resultL0Title` | `Starting point: L0` | result heading |
| `resultL0Body` | `Your plan will start at the beginning, with kana, romaji and a gloss.` | result body |
| `resultL1Title` | `Starting point: L1` | result heading |
| `resultL1Body` | `Your plan will start past single kana, and keep romaji and furigana.` | result body |
| `resultCaption` | `You can change this.` | shared result caption |
| `accept` | `Use this starting point` | writes the token into the level field and closes the check |
| `change` | `Change` | returns to the level field, which stays focused and editable |
| `unknownTitle` | `No starting point set` | shown for an unsure, stopped or empty outcome |
| `unknownBody` | `The check did not get enough answers to set one. Type where you are starting from, or leave it blank.` | under the unknown heading |
| `unavailable` | `A check is not available for this language yet. Type where you are starting from, or leave it blank.` | replaces the entry when the locale has no bank |
| `provenance` | `From the starting-point check. You can change it.` | under the level field after accept, until the field is edited |
| `locked` | `Saved with the course: {value}` | under the level field once a course row exists for this create |

The check adds no other learner-facing string. Button labels reuse `Skip`, `Start`, `Change` and
`Use this starting point`; there is no second wording for the same action. The words score,
result, grade, pass, level test, CEFR, A1, B1, certified and mastered may not appear anywhere in
the placement surface.

## 6. What the backend records

One value: the level string, stored at `courses.level`. Nothing else about the check reaches the
database.

The exact path, all of it existing today:

1. Accepting a result writes `L0` or `L1` into the create flow's level state. The field stays
   editable and the learner's own edit always wins.
2. `course.create` receives that string in its existing optional `level` property, maxLength 35,
   described as advisory and "never a grade or a diagnosis"
   (`contracts/rpc.v14.json:558-565`, sha256
   b454fab7e5b9fbc5e8fb536954486d01b0a3c580b55b8858450734f37357cc4e).
3. The course row stores it in `courses.level`, nullable text
   (`contracts/db.v10.json:104-110`, sha256
   8bfe23413db17614f61a43d3be176e7a376ddd6a6ffc38d611652368f9d9209f).
4. The plan job brief carries the same value in its optional `level` field
   (`contracts/rpc.v14.json:8047-8117`, same digest as above), so a retry and the course row agree.
   The stored plan job result echoes the declared level back as `result.level`
   (`coursebook/generation.py:6340-6344`).
5. The planner prompt states it as a declared input: `Learner level: {level}. It is declared by
   the brief; never infer a level from the locale, and do not move objectives outside it.`
   (`coursebook/generation.py:2557-2561`, sha256
   1f1bc68350f408fc3483a66507fab94e5d74cf3176f0ef75d87ba99e31128f72).
6. The curriculum brief echoes it as `brief["level"]`
   (`coursebook/curriculum.py:142-143`, sha256
   229841e35d239ad707eb4f7da55cf710d80fe73df7bc10c5761383e6d1eb7817).
7. For Japanese at `L0` or `L1`, the scaffold table mandates romaji, furigana and a gloss
   (`coursebook/localization.py:139-157`, digest above). This is the one behaviour the check is
   allowed to change, and it is the reason the token must be bare (section 7).

Why no evidence row. `observation.record`, the only client-reachable way to write evidence,
requires an `enrollment_id` and an `objective_id`
(`coursebook/domain.py:3749-3759`, sha256
03131c7bfa17381e02b8646b62ea66d5a54502d359e12362726a8d932302949b), and its accepted classes are
self and parent reports. A placement happens before a course, an enrollment or an objective
exists. Recording the answers afterwards would attach a claim to an objective they never assessed
and would read as evidence of learning. The check therefore writes no attempt, no evidence, no
objective state, no verdict and no revision.

Why no provenance column. The tempting addition is `courses.level_source` with values `typed` and
`placement`. It is refused for 0.1.0. The level is advisory and editable by design; a source column
would make a four-item check look like a durable diagnostic record, and `course.get` would then
have to explain a diagnosis the product does not stand behind. If the learner later reopens the
course, if the learner later reopens it, the level is shown without saying where it came from. That
limitation is deliberate and is recorded in the scope list in section 9, not hidden.

## 7. The bare-token constraint

The level field must receive `L0` or `L1` and nothing else. The scaffold policy uppercases the
whole string and tests membership in a set:

```
level = str((dials or {}).get("level") or "").upper()
if rule is not None and level in rule["levels"]:
```

(`coursebook/localization.py:148-152`, digest above). A decorated value such as
`L1 (kana and set phrases)` or `L1 - past single kana` would silently fail that membership test
and drop romaji, furigana and the gloss for exactly the beginner who needs them. The human-readable
band name therefore lives in the result copy, never in the stored level. H-119 must not
"improve" the token, must not parse the field, and must not rewrite a learner's own text.

The same constraint is why the check writes to the existing field rather than a new one: the field
is what `course.create` already accepts, what the course row already stores, and what the planner
and scaffold policy already read. One seam, one value, no parallel path.

## 8. Skip, unknown and refusal

Skip is one activation from the intro, from any item and from the result. It writes nothing,
leaves any text already typed in the level field untouched, closes the check and returns focus to
the field. There is no confirmation dialog, no second question and no stored regret: reopening the
create flow later offers the check again, and a skip is never remembered against the learner.

Unknown is shown when the learner uses I'm not sure, stops the check, or otherwise ends it without
an outcome. It shows `unknownTitle` and `unknownBody`, leaves the level field empty or as typed,
and never shows a number, a fraction, a percentage or a best guess. The create flow continues
normally; an empty level simply means the brief named none, which is the pre-existing meaning of a
null `level`.

A backend refusal is not a new error path. If `course.create` fails, the existing error handling
runs, the typed error is shown through `describeError`, and the placement level stays in the field
so nothing is silently replaced. Two cases must be distinguished, and both already exist in the
flow's state:

1. Failure before a course row exists (`stage` is `course.create`, no recoverable course id).
   The learner may accept a different band or type a different level. Because the create flow
   has already burned an operation key, any handler that changes the level input while an error is
   showing and no recoverable course exists must clear the pending key, so the retry is a new
   operation with the new payload rather than an `IDEMPOTENCY_CONFLICT` on a changed hash.
2. Failure after the course row exists (enrollment or jobs stage, recoverable id present). The
   course already stores the earlier level. The level field becomes read-only with the `locked`
   copy, the check entry is not offered, and the retry repeats the same payload and the same
   stored level. H-119 must not invent a level-edit RPC to escape this: `cb.rpc` v16 has no
   `course.update`, and adding one is a contract decision, not part of this card.

The result screen never invents a score to explain a refusal, and the refusal message never claims
the check failed.

## 9. What H-119 changes, and what it must not

H-119 owns `desktop/plugin.js` and its tests. It adds the item bank, the two pure helpers, the
check component, the copy constant, the level-field wiring and the locked state. It changes no
Python, no contract, no job and no route.

It must not add an rpc method, job kind, table, column, error code, feature flag, provider call,
telemetry, timer, progress bar, percentage, adaptive model scoring, free-text answer checking,
translation of the bank, or a second place that stores a level. It must not change the create
flow's three-step shape, its wording elsewhere, or the existing behavior of a blank level. It must
not show per-item correctness. It must not make the check required, pre-checked, or reachable
before the locale names a language with a bank.

The create confirm step already renders the value as the Starting point row
(`desktop/plugin.js:4718-4722`), and that is the only place this card requires it. The plan surface
today has no course read (it never calls `course.get`), so H-119 must not add one to display the
level: that is a new request on a screen this card does not own.

## 10. Tests H-119 must land

All desktop tests use the same Node harness as `tests/test_desktop_create_flow.py`: import the
shipped ESM module, drive exported functions and the component's pure helpers, and assert exact
payloads and exact strings. Source-level assertions are allowed only where a stub cannot see the
surface (the existing suite already does this).

`tests/test_desktop_placement.py` (new):

| test | asserts |
|---|---|
| `test_the_check_is_offered_only_for_a_language_with_an_authored_bank` | `placementIsAvailable` is true for `ja`, `ja-JP`, `JA-jp`; false for `fr-FR`, an empty locale and `parent` |
| `test_the_check_calls_no_rpc_and_starts_no_job` | the recording transport sees zero calls while the check runs; the first call is still `course.create` after accept |
| `test_two_mismatches_stop_the_check_and_set_l0` | answers in bank order, second mismatch ends it, no third prompt is rendered, outcome band is `L0` |
| `test_four_answers_with_one_mismatch_set_l1` | all four prompts shown, one wrong, band `L1` |
| `test_an_unsure_answer_sets_no_starting_point` | unsure at item two, no band, unknown copy shown, level field unchanged |
| `test_stopping_the_check_keeps_the_typed_level` | typed value survives skip at intro, mid-item and result |
| `test_the_result_shows_no_count_percentage_or_mastery_word` | result DOM text has no `%`, no `1 of 4`, no score, grade, pass, CEFR, certified or mastered |
| `test_the_frozen_copy_is_exactly_this_specification` | every string in `PLACEMENT_COPY` equals section 5 |
| `test_accept_writes_one_bare_token_and_edit_replaces_it` | accept writes `L0` or `L1` with no decoration and shows `provenance`; editing clears `provenance` |
| `test_the_options_are_a_native_radiogroup_with_no_timer` | each item is a fieldset with a legend and native radio inputs; no interval, no countdown, no auto-advance |

`tests/test_desktop_create_flow.py` (extend):

| test | asserts |
|---|---|
| `test_the_chosen_placement_level_reaches_course_create_and_the_plan_brief` | `level: 'L1'` appears in both payloads and in the job brief |
| `test_a_skipped_check_omits_level_from_both_payloads` | no `level` key at all, matching current optional-input behavior |
| `test_a_refused_course_create_can_retry_with_a_new_placement_level` | after a `course.create` refusal, accepting a different band produces a new operation key and a second `course.create`; no `IDEMPOTENCY_CONFLICT` |
| `test_a_recoverable_course_locks_the_starting_point` | once a recoverable id exists, the field is read-only, shows `locked` with the stored value, and the retry payload keeps that value |

`tests/test_learner_plan_flow.py` (extend, real dispatch against a database):

| test | asserts |
|---|---|
| `test_the_placement_level_is_the_stored_course_level` | `course.get` returns `level: 'L1'` after a create with that level |
| `test_the_plan_job_brief_carries_the_same_level` | the `jobs.create` plan brief and the stored plan job result both echo `L1` |
| `test_the_level_moves_no_objective_and_writes_no_evidence` | objective states, check states and the evidence table are identical to a create with a null level |

`tests/test_locale_scaffolds.py` (extend):

| test | asserts |
|---|---|
| `test_the_placement_tokens_are_the_tokens_the_scaffold_table_reads` | `scaffold_requirements('ja-JP', {'level': 'L0'})` and the same for `L1` return romaji, furigana and gloss; a decorated `L1 (kana)` returns an empty dict |

`tests/test_contracts.py` (extend):

| test | asserts |
|---|---|
| `test_placement_adds_no_contract_surface` | the v14 method set, the job kinds, the error codes and the `db.v10` table set are unchanged; no `placement` method, table or column exists |

## 11. Acceptance map for H-119

| H-119 acceptance line | this specification | tests |
|---|---|---|
| a short optional step of 3 to 5 items | sections 2 and 3, four items, offered only with a bank | offered, L0, L1 |
| asks the learner to do a tiny task, not self-report a CEFR label | section 3, four kana and phrase tasks, no label anywhere | L0, L1, copy |
| returns a level hint only when the backend can use it | sections 1, 6 and 7, only `L0` and `L1`, which the scaffold table reads | scaffold tokens, stored level |
| skippable and never blocks creating a course | section 8, one activation, no confirmation, create continues | stopping keeps the field, skipped omits level |
| shows what the answer changes | section 5 result bodies and `provenance` copy | copy, accept and edit |
| no fabricated score, labelled starting point and editable | sections 4, 5 and 8, no count, no percentage, edit replaces | no count, accept and edit |
| tests for skip, answer and backend refusal | section 10 | all desktop and refusal tests |
| the plan records the chosen level | section 6, course row, plan brief, planner prompt | stored level, plan brief, advisory |
| no claim of mastery or certification | sections 4, 5 and 9 | copy, contract surface |
| one plugin writer, no product code in this card | this document only | n/a |

## 12. Known limits and the counter-arguments

The check cannot place a learner above `L1`. A comfortable reader sees `L1` and the result copy
invites them to change it. Under-placing is the safe direction: a plan that starts too easy is a
wasted lesson, a plan that starts too hard is a failed one.

The check exists only for Japanese. That is honest coverage, not a general placement product. A
second bank is additive content plus one table row, not a new contract, and belongs to a later
card with an author for that language.

The result is not durable. Reopening the course shows the level, not that the check produced it.
A provenance column was considered and refused in section 6.

An unsure answer at the last item discards earlier correct answers. That is deliberate: a partial
signal is not a basis for a starting point, and the free-text field remains for the learner who
wants to say more.

The one place this specification can rot is the scaffold token set. If a later card widens
`BEGINNER_LEVELS`, the placement tokens do not change; if a later card adds a level with
behaviour, the band rule in section 4 is where the new mapping belongs, decided as a contract,
not patched in the UI.

## 13. Sources and digests

Every source cited above, hashed at the base commit.

| path | lines cited | sha256 |
|---|---|---|
| `desktop/plugin.js` | 4637 (level field), 4196-4225 (payloads), 4233-4260 (create orchestrator), 4718-4722 (confirm row) | `f1b0aba981c3f54275d70e44244337b0deac795b15cd8ebb7bceff1bdefe28e5` |
| `contracts/rpc.v14.json` | 531-639 (`course.create`), 8047-8117 (`plan_brief`) | `b454fab7e5b9fbc5e8fb536954486d01b0a3c580b55b8858450734f37357cc4e` |
| `contracts/db.v10.json` | 104-110 (`courses.level`), 519-567 (`evidence` required ids) | `8bfe23413db17614f61a43d3be176e7a376ddd6a6ffc38d611652368f9d9209f` |
| `coursebook/localization.py` | 88-100, 139-157 (beginner levels, exact match) | `319736f01832605b3e75240b134d819d8b45d8dc8100d97379c49e65462239ef` |
| `coursebook/generation.py` | 2557-2561 (planner level line), 4602-4665 (plan payload), 6340-6344 (job result echo) | `1f1bc68350f408fc3483a66507fab94e5d74cf3176f0ef75d87ba99e31128f72` |
| `coursebook/curriculum.py` | 142-143 (brief level) | `229841e35d239ad707eb4f7da55cf710d80fe73df7bc10c5761383e6d1eb7817` |
| `coursebook/domain.py` | 3749-3759 (observation needs an objective), 162-231 (payload hash and `IDEMPOTENCY_CONFLICT`) | `03131c7bfa17381e02b8646b62ea66d5a54502d359e12362726a8d932302949b` |
| `PREBUILD_SPEC.md` | the vertical-slice rule quoted in the Authority row | `cbdeccdcd6007eb902bea969008b58b4192f1a8fb3f3d1fda62ee6ec99640e5c` |
| `AUDIT.md` | item 3, placement takes no surprise model call | `7eb6152a63e7a981f0b272ca9a9e490dedfb5e885c88c72a826ac536c1e51005` |
| `docs/ADVERSARIAL-REVIEW-V3.md` | item 28, optional 3 to 5 item diagnostic | `d481155b02465884199884899aa7f49c61d1c55d46fb9a4292a9a82d89aa4ad1` |

Base commit `25467cf1df3062748c63a5a77c7e77975b775aba`. This card wrote no product code, ran no
provider, changed no contract and published nothing.
