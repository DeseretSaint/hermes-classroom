---
name: lesson-tutoring
description: "Answer as the Coursebook tutor from the classroom DB."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [coursebook, tutoring, sqlite, desktop]
    related_skills: [inspecting-hermes-desktop-dom]
---

# Coursebook lesson tutoring

## Overview

A Coursebook prompt can arrive in a Hermes session that is the **lesson chat
itself** — "I want to try this section. What am I practising?" typed by the
learner, or injected by a QA script driving the section pane. There is no
attachment and no visible lesson on your screen: the section lives in the
Coursebook plugin's SQLite store, and your job is to answer as the tutor.

## When to Use

- A chat session receives a lesson-shaped prompt ("what am I practising here",
  "I want to try this section") with no attachment while a Coursebook classroom
  is open.
- A QA script or harness created this session and is driving a section pane; the
  prompt is real input and a correct tutor reply is the expected output.
- You need the objective, evidence target, teaching text or rubric of the section
  a learner is on — read them from `data.db`, never from the rendered app.
- Not for building the plugin itself; that is the classroom repo's own work.

## Procedure

1. **Use the injected binding first.** A governed lesson turn names the absolute
   plugin-data `data.db` and the bound `objective_id` in its instruction. Read
   only that store and that id; never search other homes, rank candidate stores
   by freshness, or let the data choose a different course. If the bound id is
   absent from the named store, answer `bound_objective_not_in_store`, say the
   bound lesson has no stored content, and stop; do not fall back to a sibling
   store. Only when no binding is injected (legacy/manual prompt) locate the
   store, and still use the active binding/run rather than a global freshness
   scan. `sqlite3 -json` prints an empty string for zero rows (so a `| python3
   -m json.tool` pipe dies with a confusing parse error); use `sqlite3 -line` or
   a `select count(*)` first.
   Objective ids come as pack-era `obj_<hex>` or newer bare `<hex>`; a
   `like 'obj_%'` probe silently misses the newer packs.
2. **Resolve the open section for an unbound prompt** (see `references/state-queries.md` for the SQL):
   when the turn already injected the bound `objective_id`, use it and skip this scan. Otherwise,
   the `bindings` row with `status='active'` names the exact `lesson_run_id` +
   `objective_id`; otherwise take the most recently opened `lesson_runs` row.
   Prefer the freshest run over the newest binding: opening a section creates
   the run before the chat binds, so on turn one the active binding belongs to
   an older chat and only `last_opened_at` identifies the section the learner
   just opened. Then read the `objectives` row by `id` (title, `ordinal`,
   `evidence_target`, `evidence_criteria_json`) — it carries `plan_id`, not a
   run id, so join through `lesson_runs` rather than filtering objectives by
   run.
3. **Read the check when the objective has one.** `checks.stimulus_json` is the
   question the pane shows; `reference_json` is the machine answer. Answer from
   `stimulus_json` + the teaching segment. Count the rows first: an objective
   with no `checks` row is a real state, not a broken store.
3a. **A section may have no check at all.** Generated courses with
   `dials.assessment='none'` (checklists, verification procedures, handwork)
   have zero `checks` rows by design: the material is the objective's
   `evidence_criteria_json` step list, `plans.schedule_json.check_plan`
   (`kind='verification'`) and `gen_plan_documents.document_json`. Never invent
   a check to fill the gap and never report the plugin as broken — reply with
   the section name, the construct (`procedure`), the kit the learner needs, the
   numbered steps, the stop condition, and what to send (each item ticked after
   doing it, plus the one observation step that has a real answer). If the plan
   marks the content `unverified` for lack of a source, say so before the
   learner acts on it. If the plan records a check that is merely not open yet,
   tell the learner to open it from the section pane instead of writing one.
3b. **A run may also have no teaching body.** Newer runs are created empty and
   the teaching body stays with the pack or the plan: read `gen_plan_documents`
   (`objectives[].evidence_criteria`, `learner_outcome`, `exclusions`,
   `evidence_note`) and the section's own pack text. Never fill the gap with
   invented material; if no stored body exists, say the bound section has no
   stored content and stop.
4. **Reply as the tutor:** name the section (lesson number + objective title),
   name what is being practised as a construct (discrimination / comprehension /
   recall / procedure / transfer), show the material the check refers to, then
   quote the check question and ask for the learner's answer plus the cue it
   turns on. A no-check procedure instead gets the steps and the evidence the
   criteria record; do not close it with a question the store does not grade.
5. **On a repeat turn ("result: not yet"), read what was already asked first.**
   List every check on the objective, closed ones included, and diff their
   `stimulus_json` against the open one: re-issuing a stimulus the learner has
   already seen — even reworded in the same scene — is the failure the repeat
   turn is there to prevent. Then produce *one* different representation (a
   different modality or angle: a written note instead of a spoken moment, a
   ladder/substitution table instead of a dial analogy) and exactly one fresh
   check. One attempt at a time. Keep the fresh item answerable as **one short
   line** in the exact format the checker accepts: the pane grades the learner's
   next chat message verbatim, so a three-part question with a `rubric_only`
   shape earns another `not_yet` no matter how well it is answered.
6. Stop there. The pane's **Submit answer** and the grader own the verdict — for
   a checked section, never solve the check for the learner, never label the
   previous attempt, never announce pass/fail yourself. A no-check section has no
   verdict to announce either; the parent or learner records the evidence.

## Answer shape

- **Withhold the reference answer — including inside a "remind me first"
  explanation.** A discrimination check that shows option A and option B must
  not come back with "the answer is B". When the section's target is `recall`,
  the pack's own contrast table often contains the answer row: print every
  register *except* the target and refer to the missing one by its cue. Read
  `reference_json` to know exactly what must not appear.
- **Close with the answer format the grader can accept.** The pane submits the
  learner's next chat message verbatim against an exact answer key, so a
  well-meant essay grades as `not_yet`. End by saying what to send in one line:
  just the answer, in the representation the check declares (target script for a
  script item, a declared transliteration accepted only when the check allows
  it), no framing sentence, no explanation. For a no-check section the send
  format is the evidence the criteria name: each step ticked after doing it,
  plus the one observation that has a real answer.
- **Scaffolded material carries every scaffold the pack declares on every
  line** — target script plus transliteration plus a gloss for a language item,
  units for a quantitative item. A transliteration is a scaffold, and repeating
  it is not evidence of the skill being tested.
- **Name the cue the item is testing** (a form, a boundary, the setting) so the
  learner knows what evidence the grader wants.
- Keep it to the section's scope. Adding adjacent material the pack does not
  teach makes the check unanswerable.

## Pitfalls

- **Never let a bound chat choose a different store.** A governed lesson turn
  carries the absolute plugin-data DB and bound `objective_id`; a freshness scan
  across `~/.hermes/plugin-data`, QA homes and scratch dirs can make the tutor
  teach a different course than the pane shows. If the named objective is
  absent, return `bound_objective_not_in_store` and stand down; only an unbound
  legacy prompt may locate the store.
- **The pane index is not an objective id.** "Open section" buttons are ordered
  by `objectives.ordinal`; two objectives can share near-identical teaching text.
  Confirm with `bindings`/`last_opened_at` before naming the section.
- **A run can have no `lesson_segments` rows.** Newer runs are created empty
  and the teaching body stays with the pack, not the run — pull the lesson text
  from other runs on the same `plan_id` (same pack) instead of inventing
  material, and check `packs`/`plans` before concluding the store is broken.
  For generated plans the body may live only in `gen_plan_documents`
  (`plan.objectives[].evidence_criteria`, `learner_outcome`, `exclusions`,
  `evidence_note`), with `gen_lessons`/`gen_plan_sections` empty while the plan
  is still `draft`/`needs_review`.
- **A section with no check is not a defect.** `dials.assessment='none'` means
  the evidence is the criteria step list, not a graded item. Never manufacture a
  check, never tell the learner the plugin is broken, and never reuse another
  section's check.
- **A `not_yet` whose `answer_json.text` is the learner's whole request means the
  tutor never named the send format.** The pane submits the next chat message
  verbatim, so an unlabelled reply gets graded as the answer. Always close with
  one line: what to send, in the check's own representation, no explanation.
- **Don't scrape the running app for section state.** If the desktop window
  rendering this chat is attached over CDP, `document.body.innerText` is your
  own transcript and will "match" your probes. Query the DB.

## References

- `references/state-queries.md` — the SQL that resolves the open run, objective,
  check, evidence criteria and teaching text out of `data.db`.
