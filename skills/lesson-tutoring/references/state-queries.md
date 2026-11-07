# Reading Coursebook state from data.db

All queries run against `plugin-data/coursebook/data.db` under the HERMES_HOME
in play (`~/.hermes`, or `~/.hermes/coursebook-test/home` for the isolated dev
install). Check both: the objective id you were given decides which store is
live.

## Which run/objective is open

```python
import sqlite3, json
c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
for r in c.execute("select * from bindings"):
    print(dict(r))   # stored_session_id, lesson_run_id, objective_id, status
```

`bindings` holds one row **per session**, not per enrollment: the same
enrollment accumulates `detached` rows as chats close and keeps a single
`status='active'` row for the live one. Order by `updated_at desc` and trust the
active row; `runtime_session_id` is often null while `stored_session_id` is set.

Fallback ordering when nothing is bound yet:

```sql
select id, objective_id, state, last_opened_at from lesson_runs
order by last_opened_at desc limit 3;
```

## Schema facts worth not rediscovering

- `objectives(id, plan_id, ordinal, title, evidence_target, evidence_criteria_json, state)`
  — keyed to a **plan**, no run column. `evidence_target` ∈ recall /
  comprehension / production / discrimination / procedure / transfer.
- `lesson_runs(id, enrollment_id, objective_id, state, last_opened_at)` — one
  live run per objective; no `plan_id`.
- `lesson_segments(lesson_run_id, ordinal, kind, text)` — `kind` ∈ teaching /
  example / media / source_passage / check_prompt / feedback / summary. A new
  run may have **none**; reuse the pack's text from sibling runs on the same
  `plan_id`.
- `checks(objective_id, state, stimulus_json, rubric_json, reference_json)` —
  a closed check plus a fresh open one is normal on a retry turn.
- `attempts(check_id, answer_json, verdict, evidence_class, criteria_json,
  grading_provenance_json)` — `answer_json.text` holds exactly what the pane
  submitted, which is how you prove a mis-shaped answer was graded.

## The objective and its teaching text

```python
obj = dict(c.execute("select * from objectives where id=?", (objective_id,)).fetchone())
# title, ordinal, evidence_target, evidence_criteria_json -> [{description, id, check_spec?}]
segs = c.execute("select ordinal, kind, text from lesson_segments "
                 "where lesson_run_id=? order by ordinal", (run_id,)).fetchall()
# kind='teaching' is the lesson body, kind='check_prompt' restates the question
```

`check_spec` inside `evidence_criteria_json` duplicates the check's stimulus,
rubric and reference — usable when the `checks` row is missing.

## The graded check

```python
rows = [dict(r) for r in c.execute(
    "select id, state, stimulus_json from checks where objective_id=? order by rowid",
    (objective_id,))]
chk = dict(c.execute("select * from checks where objective_id=? and state='open'",
                     (objective_id,)).fetchone())
json.loads(chk['stimulus_json'])    # what the pane shows the learner
json.loads(chk['rubric_json'])      # criteria + pass_rule ('all' or a count)
json.loads(chk['reference_json'])   # {'kind':'exact','answers':[...]} or {'kind':'rubric_only'}
```

`reference_json` is tutor-facing only — read it to know what to withhold, then
neither quote the answers nor paraphrase them into the explanation.

## Before answering a repeat turn

```sql
select id, state, stimulus_json from checks where objective_id=? order by rowid;
select check_id, verdict, evidence_class, answer_json from attempts
order by rowid desc limit 5;
select * from transitions order by rowid desc limit 5;   -- next_action: retry_attempt
```

Compare the closed check's stimulus with the open one. Identical or
same-scene stimuli mean the previous item is the one to avoid; `next_action`
`retry_attempt` confirms the harness expects a fresh attempt, not a lecture.

## Course, plan and pack framing

```sql
select title, goal, locale, dials_json from courses;   -- dials: assessment/autonomy/depth/pace
select * from plans;                                   -- pack_version, plan_hash
```

`dials_json` sets how much scaffolding to give: `assessment='self_check'`,
`depth='survey'`, `pace='light'` mean short explanations and one attempt at a
time, not a full curriculum dump.
