# Course quality rubric for generated courses

Status: binding quality lens, 2026-11-08. Card: H-173 `t_c579dfa7`. This file defines what we
mean by a good generated course. It changes no generation, validation, grading or UI behavior.
Amended by H-173d `t_7f46fb7f`: the packet now states how much of the plan its one lesson covers,
and a partial packet obliges the record to state that limit.

Read with:

- `docs/EXPERIENCE-QUALITY-BAR.md` - the UI and product quality bar. That file judges the
  surface a learner touches. This file judges the course the generator wrote.
- `docs/GENERATION.md` - the pipeline stages that produce a plan, lesson, check and validation.
- `docs/RUBRICS.md` - check rubrics, which are scoring guides inside one check, not a judgment
  of the course.
- `coursebook/generation.py` - `VALIDATION_CRITERIA`, the ten structural criteria the
  independent pass owes the pipeline.

## 1. Why this file exists

The independent validator has ten criteria: `objective_alignment`, `source_support`,
`factual_correctness`, `answer_uniqueness`, `alternative_coverage`, `rubric_consistency`,
`internal_contradiction`, `answer_leakage`, `hazard_age_appropriateness`,
`evidence_target_fit` (`coursebook/generation.py`). Every one is structural, factual or safety
oriented. A plan can pass all ten and still be a weak course:

- objectives that are topics rather than capabilities;
- units that do not build on each other;
- one example repeated across a course;
- checks that test recall while the objective claims production or transfer;
- a lesson that is accurate but unreadable.

The live H-63 evidence records real failures in that class: a goal that over-promises a general
skill while its only objective covers C major, negative evidence criteria that mark a true
answer wrong, and a self-ticked checklist offered as comprehension evidence
(`audit/adversarial/h63-live-generation/STATUS.md`). The structural gate did not catch those as
quality defects because they are quality, not shape.

Without a rubric, "high quality" is an adjective and every worker optimises a different thing.
This file makes the adjective observable.

## 2. What this rubric is and is not

This rubric is:

- a reviewer's checklist with eight dimensions, each scored 1 to 4 against observable evidence;
- a written record per course, with a named reviewer and a quote or location for every score;
- a triage rule: any dimension below 3 becomes a follow-up card with a concrete fix.

This rubric is not:

- a mastery score, a mastery percentage or a claim that a learner mastered anything;
- an engagement metric, a completion metric, a streak, a leaderboard or a public badge;
- a time-to-complete promise or an attainment-hours estimate;
- a learning-styles diagnosis or a modality preference test;
- a second validator. The ten structural criteria stay the gate. This is a lens beside the gate,
  and it does not replace the validator's structural pass;
- a reason to block a course a human has approved.

The 1 to 4 values are reviewer judgments about course design. They are never summed, averaged,
ranked across courses or shown to a learner. A score of 4 is never required for release.

**Where the deterministic floor sits (H-195).** Before any of this is scored, the pipeline applies
`teaching_quality_problems` to the authored lesson. That floor is code, not a reviewer judgment: it
refuses a lesson with no `model`/`guided` arc, a worked example with fewer than two steps, a
template heading, fewer than `MIN_TEACHING_PROSE_CHARS` (400) characters of segment prose, or
boilerplate filler. It is deliberately **not** a ninth dimension and **not** an eleventh
`VALIDATION_CRITERIA` entry: the floor answers "is this a lesson at all", these eight dimensions
answer "is this lesson good", and a course that reaches a reviewer has already cleared the floor.
A thin draft is regenerated or parked `needs_review` before it is ever scored.

## 3. The scale

| Score | Meaning | Test a reviewer applies |
|---|---|---|
| 1 | Absent or contradictory | The evidence for this dimension is missing, or the artifact contradicts itself here in a way that would mislead the learner. |
| 2 | Present but weak or cosmetic | Something exists, but it does not carry the load. The learner or the reviewer must infer, repair or ignore it. |
| 3 | Adequate | The evidence is present, specific and usable without repair. This is the minimum for a course presented to a learner. |
| 4 | Strong | The evidence is specific, varied and honest under scrutiny. A second reviewer reaches the same verdict without the author explaining it. |

Three rules for scoring:

1. Score the artifact in front of you, not the intent in a commit message or card body.
2. Quote or name the location of the evidence. A score without evidence is not a score.
3. If a dimension needs more than three minutes of reading to decide, the artifact is at most a
   2 on that dimension: usable quality does not require the author present.

## 4. The eight dimensions

| ID | Dimension | The question it answers |
|---|---|---|
| D1 | `capability_objective_fit` | Does the course promise a capability, and do the objectives name observable performances rather than topics? |
| D2 | `sequencing_prerequisite_truth` | Does each objective arrive after what it needs, and are prerequisites real rather than decorative? |
| D3 | `evidence_target_fit` | Does the check measure the evidence target the objective declares? |
| D4 | `example_explanation_quality` | Do the worked example and explanation teach this case, or restate one generic example? |
| D5 | `cognitive_load_session_arc` | Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite? |
| D6 | `source_grounding_citation_honesty` | Is each load-bearing claim traceable to a fetched source or honestly marked unverified? |
| D7 | `media_necessity` | Does each image or audio artifact carry a job the construct requires, or is it decoration? |
| D8 | `learner_agency_recoverability` | Can the learner see, choose and recover from their own path without a hidden failure? |

### D1 `capability_objective_fit`

Question: does the course promise a capability, and do the objectives name observable
performances rather than topics?

Where to look: `learner_outcome`, every `objectives[].title`, every
`objectives[].evidence_criteria`, and the scope.

- 1: objectives are topics ("cover the circle of fifths", "learn greetings") or the outcome
  promises a general skill the objectives do not cover.
- 2: some objectives are performances and some are topics; the outcome is broader than the
  objectives but a reviewer can guess the intended performance.
- 3: every objective names something the learner does or produces, and the outcome is
  consistent with their union.
- 4: every objective is a performance with a stated criterion, the outcome names the transfer
  context, and the exclusions say what the course does not claim.

Does not count: a confident title, a longer objective list, or a phrase such as "understand
deeply" without an observable act.

### D2 `sequencing_prerequisite_truth`

Question: does each objective arrive after what it needs, and are prerequisites real rather than
decorative?

Where to look: objective order, `units[].prereq_unit_ordinals`,
`units[].target_lessons`, sections' `objective_refs`, and the schedule arithmetic
(`sessions_per_week` x `weeks` against the authored target lessons).

- 1: a check or objective requires material that no earlier unit teaches, or the declared
  prerequisites contradict the order.
- 2: the order is plausible but a prerequisite is implicit, a unit edge is decorative, or the
  schedule cannot hold the declared units.
- 3: each objective is reachable from earlier material, every prerequisite edge is used, and
  the schedule arithmetic holds.
- 4: the sequence has a named reason (block first, interleave confusables later) that a
  reviewer can verify from the plan, and review material points back at the unit it revisits.

Does not count: ordinals alone, or the claim that a subject "naturally" has an order.

### D3 `evidence_target_fit`

Question: does the check measure the evidence target the objective declares?

Where to look: each objective's `evidence_target` and `evidence_criteria`, the matching
`check_plan[]` entry, and the lesson's `check.kind`, `check.stimulus.format` and
`check.evidence_target`.

- 1: the check measures a different target (a selection quiz for `production`), or the
  objective's criteria cannot be observed by the check at all.
- 2: the target is plausible but the task is weaker than claimed (self-ticked checklist for a
  procedure, recognition for transfer), or the check's own rubric adds criteria the objective
  never stated.
- 3: the check's task matches the declared target and its criteria are the objective's criteria
  in observable form.
- 4: the check measures the target cold, with no cue leakage, and a second check samples the
  same target differently.

0.1.0 ceiling on anchor 2: a course that declares `evidence_target: procedure` and collects only
a checklist scores at most 2 here, whatever its labels say. Honest wording and the named
observable acts make the weakness visible; they do not change what was collected, because the
attempt still stores a `selection` of ticked item ids with `evidence_class = self_reported`
(`coursebook/grading.py:40`). A validator pass on `evidence_target_fit` is not a D3 pass: that
criterion asks whether the check is the strongest lane this build can give the declared target,
while D3 asks whether the task is as strong as the target the course claims.

Does not count: the label `production` on a multiple-choice item, or a rubric weight as proof
that the target was measured.

Coverage in a packet: the packet supplies one lesson, and a plan may schedule more sessions than
that. Score D3 against the objectives whose check you can read, and name the objectives that have
no authored check to read. D3 is not a 3 while an objective's check cannot be read: an unread check
has not been shown to measure the target it declares. Whether an uncovered objective is a 1 or a 2
on those checks is decided by the anchors above, not by the packet's count.

### D4 `example_explanation_quality`

Question: do the worked example and explanation teach this case, or restate one generic example?

Where to look: `segments[]`, `worked_example`, `learner_explanation`, and whether the example's
answer agrees with the objective, the check and the reference answer.

- 1: the explanation contradicts the example or the check, or the example's answer belongs to a
  different task.
- 2: one example is reused for every segment, the steps are named but not shown, or the
  explanation restates the prompt without explaining why.
- 3: at least one worked example shows the reasoning step by step, and the explanation names
  the rule that makes it work.
- 4: examples vary the case while holding the rule fixed, and at least one near-miss or boundary
  case is explained.

Does not count: more prose, a second heading, or a worked example whose answer is never used.

Coverage in a packet: D4 judges the lesson the record supplies. When the packet reports fewer
lessons than scheduled sessions, score the example you read and say in the evidence which sections
had no lesson to read. A session with no lesson is a coverage finding about the course; it is not
evidence about the lesson that was read.

### D5 `cognitive_load_session_arc`

Question: can a learner finish the session, in the stated order, without a jump or an unstated
prerequisite?

Where to look: the number and kind of segments, the session length, the one-concept-per-step
shape, and the transition from model to guided work to the check. A taught target must be
*presented*, not merely named: the `kind: model` segment is where the form, its reading and its
function appear together. A lesson that describes the target only as "the standard daytime
greeting" and never prints it has not modelled it, and the check that keys that form rests on an
unstated prerequisite. A model segment that does print it is modelling, not answer leakage:
`generation.assert_no_answer_leak` permits exactly that surface, together with the narration that
reads it, and refuses the key on every other learner surface it scans — explain, guided and
retrieval segments, the worked example, the learner explanation, parent notes and non-narration
media.

- 1: the lesson requires a step the lesson never models, or the session cannot fit its own
  authored content.
- 2: two concepts arrive in one step, the arc jumps from explanation to assessment with no
  guided attempt, or the session length and section count disagree.
- 3: one concept per step, a model, a guided attempt and a check in an order a learner can
  follow, inside the stated session length.
- 4: the arc has a deliberate opening, a guided attempt that fades support, and a close that
  returns the learner to the path with the recorded result.

Does not count: a timer, a progress percentage, or "learn in 15 minutes" copy.

Coverage in a packet: D5 judges the session arc of the lesson the record supplies. A plan whose
other sessions have no lesson is a coverage finding under section 9, not a fact about this
lesson's arc; say which sections you did not read.

### D6 `source_grounding_citation_honesty`

Question: is each load-bearing claim traceable to a fetched source or honestly marked
unverified?

Where to look: `source_ids` on the plan, objectives, sections and lesson; each objective's
`support` value; `evidence_note`; and the lesson `sources` list. A source id must resolve to a
fetched source in the run's ledger; an invented id is a failure of this dimension.

- 1: a load-bearing or safety claim has no source and no `unverified` mark, or a source id
  names a page that was never fetched.
- 2: the honest marks are present but thin: most objectives are `unverified`, a named source is
  never tied to the claim it supports, or the one fetched source is generic.
- 3: every load-bearing claim has either a source id tied to what it supports or an explicit
  `unverified` mark, and the exclusions state what is not claimed.
- 4: claims are attributed per sentence or per criterion, conflicting sources are named as
  conflicting, and the plan states what would need a new fetch to upgrade.

Does not count: a bibliography with no claim mapping, a publisher name without a URL, or the
model's confidence.

### D7 `media_necessity`

Question: does each image or audio artifact carry a job the construct requires, or is it
decoration?

Where to look: `sections[].media_need` (`image.level`, `image.role`, `audio.level`,
`audio.role`), the lesson `media` list, and the construct that justified each decision.

- 1: media is present as decoration, or a construct that requires a visual or audio (procedure,
  pronunciation, listening comprehension) is declared with no media and no reason.
- 2: a role is named but the level or artifact cannot perform it; or the need is real but the
  plan leaves it undecided.
- 3: every media decision names its construct and role, and construct-requiring items have the
  media they need; everything else is honestly `none`.
- 4: media is the evidence, not a supplement: a schematic carries the procedure, a model
  recording carries the pronunciation target, and the lesson says how the artifact is used.

Does not count: a stock illustration, a decorative icon, or audio added because the course is a
language course.

### D8 `learner_agency_recoverability`

Question: can the learner see, choose and recover from their own path without a hidden failure?

Where to look: `assistance_policy`, `scaffolds`, supervision notes, exclusions, stop
conditions, retry guidance, and whether parent instructions and learner instructions agree.

- 1: the learner is told to do something the safety or supervision notes forbid, or a failure
  has no stated next move.
- 2: a hint or scaffold exists but its timing is unstated, or a failure path exists only in the
  author's head; parent and learner copy contradict each other.
- 3: hints, scaffolds and stop conditions are stated, a failed attempt has a next move, and
  parent and learner instructions agree.
- 4: the learner can choose to continue with an unresolved item, scaffolds fade by design, and
  the record says what evidence a retry produces.

Does not count: a generic "try again" button, a tooltip, or an unlockable path.

## 5. What this rubric explicitly excludes

These are refused as evidence, not merely deprioritised:

- engagement metrics: clicks, time in app, streaks, return rate, completion rate;
- mastery claims: mastery score, mastery percentage, "mastered", a ring or bar that implies
  mastery, a certificate;
- time-to-complete promises: "learn this in 20 minutes", attainment hours, a speed claim;
- learning-styles diagnosis or modality preference (visual/auditory learner);
- leaderboards, public rankings, quality badges, or any score visible to a learner;
- average or total quality scores. Eight dimension verdicts stay separate.

A course with strong engagement numbers and weak dimensions is a weak course. A course with
weak engagement numbers and strong dimensions is still a candidate for use; the product's
engagement question is separate and lives in `docs/ENGAGEMENT-AUDIT.md`.

## 6. How the validator relates to each dimension

The rubric does not re-run the validator. It reads the validator's recorded verdict and then
judges what the validator does not.

| Dimension | Depends on validator criterion | What the rubric adds |
|---|---|---|
| D1 | `objective_alignment` | Whether the aligned objective is a capability or a topic |
| D2 | `internal_contradiction` | Whether order and prerequisite edges are true, not merely consistent |
| D3 | `evidence_target_fit` | Whether the task is as strong as the target label |
| D4 | `factual_correctness` | Whether the example teaches the case and agrees with the check |
| D5 | none | Whether the session arc is followable in the authored length |
| D6 | `source_support` | Whether the grounding is specific and honestly bounded |
| D7 | none | Whether media is required by the construct or decorative |
| D8 | `hazard_age_appropriateness` | Whether the learner has agency and a recovery path |

If the validator rejects an artifact, the rubric dimensions may still be scored, but the record
must say that the artifact did not reach a learner and must not present a quality score as a
pass. If the validator passes, a low rubric dimension is still a real finding.

## 7. The 15-minute review protocol

One course per record. The reviewer must not be the author of the course being reviewed. One
lesson is one session: when the packet reports fewer lessons than the sessions the plan schedules,
that is a coverage limit to state, not a course to skim.

| Minutes | Action | Dimension |
|---|---|---|
| 0-2 | Read `learner_outcome`, scope and objective list. Ask what the learner can do at the end that they could not do before. | D1 |
| 2-5 | Walk the objectives and units in order. Check one prerequisite and the schedule arithmetic. | D2 |
| 5-8 | Compare every authored check to its objective's evidence target and criteria. When the packet reports partial coverage, score D3 from the checks you can read and name the objectives with no check to read. | D3 |
| 8-11 | Read one lesson end to end: segments, worked example, explanation, check. Say which sections that lesson covers and which had no lesson to read. | D4, D5 |
| 11-13 | Trace every load-bearing claim to a source id or an honest `unverified`. | D6 |
| 13-14 | Check each media decision against the construct, then the hints, scaffolds and stop conditions. | D7, D8 |
| 14-15 | Write the eight verdicts with evidence, then run the record checker. | all |

If the course needs more than 15 minutes, record that as a finding. A course that cannot be
reviewed in 15 minutes is not yet a 3 on D5, and probably not on D1.

## 8. The review record

The bounded packet is `scripts/course_quality_review.py`. It is stdlib only, reads at most one
plan, one lesson and one validation record, never calls a model, the database or the network, and
reports how much of the plan that one lesson actually covers.

```bash
python3 scripts/course_quality_review.py packet \
  --plan tests/fixtures/generation/plan_ja.json \
  --lesson tests/fixtures/generation/lesson_ja.json \
  --validation tests/fixtures/generation/validation_reject_check.json \
  --sample-id S2 --scope short --reviewer "name" \
  --out docs/reviews/S2-review.md

python3 scripts/course_quality_review.py check docs/reviews/S2-review.md
```

The `packet` command writes the deterministic facts (input hashes, coverage, plan shape,
objective and media counts, validator verdict and criteria, rejection reasons) plus eight empty
dimension blocks. It does not fill a score. The reviewer writes each block:

```markdown
### D3 evidence_target_fit
Score: 2
Evidence: The objective declares production but the check is a three-choice selection item
  (`check.stimulus.format = selection`), so the task measures recognition. The rubric restates
  the production criteria anyway.
Follow-up: t_0123456789ab
```

The `## Coverage` block is mechanical and is never a score. Coverage is counted against the
sessions the plan schedules (`sessions_per_week` x `weeks`), not the raw section count: a plan
whose four sections are steps inside one 45-minute session is covered by one lesson, and a plan
that schedules one session per section is not. When the plan declares no schedule the packet counts
authored sections instead and says so. The block prints that schedule arithmetic, the section the
lesson's `section_title` matches (noting that the lesson document carries no `section_ordinal` or
`objective_ref`, so a title match is all the packet has), and two lines:

- `Lesson coverage:` how many authored sessions (or sections) have a lesson in this packet, and
  how many objectives have no authored check the reviewer can read, named by ordinal.
- `Coverage limit:` which dimensions that leaves partial. When the packet supplies a lesson for
  every scheduled session the line reads `none`. Otherwise it is blank for the reviewer, and the
  reviewer must fill it under Reviewer notes.

Rules the checker enforces:

- all eight ids appear exactly once, in D1 to D8 order;
- each score is an integer 1 to 4;
- each evidence entry is at least 40 characters and names a location, field or quote;
- a score below 3 has a follow-up reference (`t_...` or `H-...`); a score of 3 or 4 says
  `Follow-up: none`;
- the record names a reviewer and echoes the validator verdict from the packet;
- a record whose packet reported fewer lessons than scheduled sessions states a `Coverage limit:`
  of at least 40 characters that names at least one dimension (D1 to D8);
- the record contains no aggregate score, mastery score, percentage, leaderboard or badge.

A dimension below 3 is not smoothed into a pass. It becomes a follow-up card with a concrete
fix before the course is called ready.

## 9. Known limits

- This rubric does not prove that a course teaches better. It makes design quality reviewable;
  it is not an experiment.
- It judges an artifact, not a learner. Nothing here measures a person.
- The first recorded review (H-173) is an author-run dry run on fixtures because H-172's live
  outputs do not exist yet. It records that limitation and asks an independent reviewer to
  re-score the same samples.
- Coverage is only as good as the artifact supplied. The packet prints a `Lesson coverage:` line:
  N of M scheduled sessions have a lesson in the record, and the objectives with no authored check
  to read. A plan without a lesson can score D1, D2 and part of D6; it cannot score D3, D4, D5,
  D7 or D8. When the packet reports partial coverage, the record must state a `Coverage limit:`
  naming the dimensions it limits, and the checker rejects a record that leaves that line blank.
- Partial coverage is priced, not scored by definition. The packet's count does not price a
  one-lesson packet as a ceiling on D4 or D5: those dimensions judge the lesson that was read, and
  the anchors decide the score. The count does stop a one-lesson packet from being read as a pass
  on D3 across the course: D3 is not a 3 while an objective's check cannot be read, and the record
  must name the objectives it could not read.
- The count depends on a declared schedule. When `sessions_per_week` and `weeks` are absent the
  packet counts sections, so a plan that schedules four sections inside one session without
  declaring the schedule is reported as partial. That is a planning-fact gap, not a coverage
  judgment; the record should say which arithmetic it relied on.
- Records written before the coverage line existed carry no count. The checker does not
  retro-charge them, because it cannot require a limitation the packet never asked for. Re-run the
  packet on that course before citing the old record as coverage evidence.
