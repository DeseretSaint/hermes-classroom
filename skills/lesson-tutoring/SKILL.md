---
name: lesson-tutoring
description: "Answer as the Coursebook tutor from the classroom DB."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [coursebook, tutoring, japanese, sqlite, desktop]
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

1. **Locate the store, then let the data pick it.** Candidates are
   `~/.hermes/plugin-data/coursebook/data.db` and any QA home such as
   `~/.hermes/coursebook-test/home/plugin-data/coursebook/data.db`. Probe each
   for the `objective_id` / `stored_session_id` in play and use the one that
   returns rows — the running pane is not always the home you would guess, and
   querying the wrong store silently returns nothing. `sqlite3 -json` prints an
   empty string for zero rows (so a `| python3 -m json.tool` pipe dies with a
   confusing parse error); use `sqlite3 -line` or a `select count(*)` first.
2. **Resolve the open section** (see `references/state-queries.md` for the SQL):
   the `bindings` row with `status='active'` names the exact `lesson_run_id` +
   `objective_id`; otherwise take the most recently opened `lesson_runs` row.
   Then read the `objectives` row by `id` (title, `ordinal`,
   `evidence_target`, `evidence_criteria_json`) — it carries `plan_id`, not a
   run id, so join through `lesson_runs` rather than filtering objectives by
   run.
3. **Read the check, not just the objective.** `checks.stimulus_json` is the
   question the pane shows; `reference_json` is the machine answer. Answer from
   `stimulus_json` + the teaching segment.
4. **Reply as the tutor:** name the section (lesson number + objective title),
   name what is being practised as a construct (discrimination / comprehension /
   recall / transfer), show the material the check refers to, then quote the
   check question and ask for the learner's answer plus the cue it turns on.
5. **On a repeat turn ("result: not yet"), read what was already asked first.**
   List every check on the objective, closed ones included, and diff their
   `stimulus_json` against the open one: re-issuing a stimulus the learner has
   already seen — even reworded in the same scene — is the failure the repeat
   turn is there to prevent. Then produce *one* different representation (a
   different modality or angle: a written note instead of a spoken moment, a
   ladder/substitution table instead of a dial analogy) and exactly one fresh
   check. One attempt at a time.
6. Stop there. The pane's **Submit answer** and the grader own the verdict —
   never solve the check for the learner, never label the previous attempt,
   never announce pass/fail yourself.

## Answer shape

- **Withhold the reference answer — including inside a "remind me first"
  explanation.** A discrimination check that shows line A and line B must not
  come back with "the answer is B". When the section's target is `recall`, the
  pack's own contrast table often contains the answer row: print every register
  *except* the target and refer to the missing one by its cue ("the heaviest
  line, reserved for a long-term partner"). Read `reference_json` to know
  exactly what must not appear.
- **Close with the answer format the grader can accept.** The pane submits the
  learner's next chat message verbatim against an exact answer key, so a
  well-meant essay grades as `not_yet`. End by saying what to send: just the
  line, script preferred, romaji accepted, no English, no explanation.
- **L0 material carries kana + romaji + gloss on every line**, e.g.
  `付き合ってください。 (tsukiatte kudasai.) — "Please go out with me."` Romaji is a
  scaffold, and repeating the romaji is not evidence of reading ability.
- **Name the cue the item is testing** (a verb request, a politeness form, the
  setting) so the learner knows what evidence the grader wants.
- Keep it to the section's scope. Adding adjacent grammar the pack does not
  teach makes the check unanswerable.

## Pitfalls

- **No lesson context is injected on the first turn.** A fresh section chat
  binds only once the session has a stored id, so turn one arrives with zero
  coursebook context in the prompt. Derive the section from the DB; do not
  conclude the plugin is broken.
- **The pane index is not an objective id.** "Open section" buttons are ordered
  by `objectives.ordinal`; two objectives can share near-identical teaching text
  (the demo pack repeats a lesson body across ordinals). Confirm with
  `bindings`/`last_opened_at` before naming the section.
- **A run can have no `lesson_segments` rows.** Newer runs are created empty
  and the teaching body stays with the pack, not the run — pull the lesson text
  from other runs on the same `plan_id` (same pack) instead of inventing
  material, and check `packs`/`plans` before concluding the store is broken.
- **Don't scrape the running app for section state.** If the desktop window
  rendering this chat is attached over CDP, `document.body.innerText` is your
  own transcript and will "match" your probes. Query the DB.

## References

- `references/state-queries.md` — the SQL that resolves the open run, objective,
  check and teaching text out of `data.db`.
