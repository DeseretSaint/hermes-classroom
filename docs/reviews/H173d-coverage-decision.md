# Decision: a one-lesson packet states its coverage instead of pretending to review the course

| | |
|---|---|
| Kind | Decision note plus the wording and packet fix it requires. Not a scored review record. |
| Deciding card | H-173d / `t_7f46fb7f`, from the independent re-score `t_99f1cb89` |
| Base | `master` `4358249` |
| Branch | `wt/h173d-lesson-coverage` (unmerged at the time of writing) |
| Files changed | `docs/COURSE-QUALITY-RUBRIC.md`, `scripts/course_quality_review.py`, `tests/test_course_quality_rubric.py`, this note |
| Action on scores, fixtures, validator | None. No review score, fixture, rubric anchor or `coursebook/generation.py` criterion is edited here. |

## 1. The finding

A `short` or `full` review packet carries one plan and one lesson. The S2 fixture pair
(`plan_ja.json` + `lesson_ja.json`) and the S3 pair (`plan_parent.json` + `lesson_parent_safe.json`)
both author or declare four sections and supply the lesson for the first one. In both, the lesson's
single `check` carries objective 1; `check_plan[1..3]` are declarations with a `kind` and an
`evidence_target` and nothing a reviewer can read as a check.

The packet presented that sample as reviewable without saying so. The rubric's section 9 asked a
record to "say which dimensions had no lesson to read", but nothing mechanical produced that
statement and nothing checked it, so an author-run record could pass with the gap unmentioned. The
independent re-score then read D3 = 2 on S2 and S3 for this reason alone.

This note decides the ask in the card: (a) take one lesson per section, (b) print the coverage and
require the limitation to be stated, or (c) score a one-lesson sample at most 2 by definition.

## 2. The decision: (b), with the count taken from the plan's schedule

**Chosen: (b).** The packet prints a mechanical coverage block, and a record whose packet reported
partial coverage must state a `Coverage limit:` that names the dimensions it limits. The checker
enforces it.

Why not (a), one lesson per section. The packet's whole value is that it is bounded: one plan, one
lesson, one validation record, stdlib only, no model, no network, and a 15-minute human protocol.
Making it demand a lesson per section changes the artifact the review can run on: a course that
authored one lesson for four scheduled sessions would produce no packet at all, so the review would
either be skipped or run on something else. The incomplete course is exactly the artifact H-173
must judge; refusing to packetise it hides the gap instead of recording it. (a) also needs a field
the generated lesson does not have: see section 5.

Why not (c), a definitional ceiling. (c) prices a property of the *packet* as a verdict about the
*artifact*, and it hands a reviewer three free 2s without reading anything. That is the same shape
of mistake H-173f had to name inside D3: a build decision wearing an artifact verdict. It also
misfires on a real, complete sample: `plan_one_off.json` schedules **one** 45-minute session and its
rationale says "the four sections are steps inside that one session, not four separate sessions", so
one lesson is full coverage there. A blanket "one lesson means at most 2" would score a complete
artifact as partial, which is the same error in the other direction.

Why (b) works. It states a measured fact (N of M scheduled sessions have a lesson), requires the
reviewer to carry the consequence into the record, and leaves every score to the anchors. The gap
stays visible, is priced in the record, and no fixture, score or validator criterion moves. Which
number an uncovered objective earns (1 or 2) is still the reviewer's call under the existing
anchors; this note does not decide it and does not re-score S2 or S3.

The count is taken from the plan's schedule (`sessions_per_week` x `weeks`) rather than the raw
section count, because the two fixtures disagree about what a section is: `plan_one_off` puts four
sections inside one session, while `plan_ja` and `plan_parent` schedule one session per section.
Counting sections would have called the first sample partial and been wrong about it.

## 3. What changed

`scripts/course_quality_review.py`:

- a `## Coverage` block after `## Inputs`, computed by `_coverage_state` / `_coverage_facts`:
  schedule arithmetic, authored section/objective/check-plan counts, the section the lesson's
  `section_title` matches (and the note that the lesson carries no `section_ordinal` or
  `objective_ref`, so a title match is all the packet has), a `Lesson coverage:` count, and a
  `Coverage limit:` line;
- the `Coverage limit:` line is pre-filled `none` only when every scheduled session has a lesson;
  otherwise it is blank under `## Reviewer notes` for the reviewer to write;
- the `packet` command prints the coverage count alongside the verdict;
- `check_record` now requires, when the record's own `Lesson coverage:` line reports fewer lessons
  than sessions, a `Coverage limit:` of at least 40 characters that names at least one dimension.
  `fill_packet` refuses to emit a record that leaves it blank, because it runs the checker.

`docs/COURSE-QUALITY-RUBRIC.md`:

- header amendment line naming this card;
- D3, D4 and D5 each gain one "Coverage in a packet" paragraph: score what the packet supplies,
  name what it does not, and do not let the packet's count become a definitional ceiling;
- section 7 protocol: "one lesson is one session", and the D3 and D4/D5 rows say to name the
  objectives and sections that had no lesson or check to read;
- section 8: describes the coverage block, the session arithmetic, the title-match limit, and the
  new checker rule;
- section 9: replaces the single "coverage is only as good as the artifact" bullet with four
  bullets - what the count says, that it is priced rather than scored by definition, that the count
  degrades to sections when no schedule is declared, and that pre-existing records are not
  retro-charged because the checker cannot require a line the packet never printed.

`tests/test_course_quality_rubric.py`: a `CoverageTest` class (9 tests) covering the partial count
and unread objectives, a packet with no lesson, complete coverage, a session-spanning lesson, a
record that omits or weakens the limit, the legacy-record exemption, and the rubric wording.

## 4. Verified output

Run on the three committed fixture pairs at `4358249`, `python3 scripts/course_quality_review.py
packet ...` (paths abbreviated; no score was filled, no record was written):

```
S1  plan_one_off + lesson_one_off
- Schedule: sessions_per_week=1 x weeks=1 = 1 authored session(s); authored sections: 4; objectives: 4; check_plan entries: 4
- Lesson section_title: 'Replace one brake pad' matches no single authored section; the lesson carries no `section_ordinal` or `objective_ref`, so any match here is by title only
- Lesson coverage: 1 of 1 authored session(s) have a lesson in this packet; the plan schedules 4 section(s) inside those session(s), so one lesson can cover more than one section
- Coverage limit: none; every authored session has a lesson in this packet. Which sections a spanning lesson covers is a D4 and D5 reading, not a coverage count.

S2  plan_ja + lesson_ja
- Schedule: sessions_per_week=1 x weeks=4 = 4 authored session(s); authored sections: 4; objectives: 4; check_plan entries: 4
- Lesson section_title: 'Greeting and opening' matches authored section 1 (objective_refs=[1]); the lesson carries no `section_ordinal` or `objective_ref`, so any match here is by title only
- Lesson coverage: 1 of 4 authored session(s) have a lesson in this packet; 3 of 4 objective(s) have no authored check the reviewer can read (2, 3, 4)
- Coverage limit: D3 can be read for 1 of 4 objectives only (objective_refs=[1], matched by section title); D4, D5, D7 and D8 read one lesson, not the course. State this limit under Reviewer notes.

S3  plan_parent + lesson_parent_safe
- Schedule: sessions_per_week=2 x weeks=2 = 4 authored session(s); authored sections: 4; objectives: 4; check_plan entries: 4
- Lesson section_title: 'Warm things at home' matches authored section 1 (objective_refs=[1]); the lesson carries no `section_ordinal` or `objective_ref`, so any match here is by title only
- Lesson coverage: 1 of 4 authored session(s) have a lesson in this packet; 3 of 4 objective(s) have no authored check the reviewer can read (2, 3, 4)
- Coverage limit: D3 can be read for 1 of 4 objectives only (objective_refs=[1], matched by section title); D4, D5, D7 and D8 read one lesson, not the course. State this limit under Reviewer notes.
```

The checker teeth, exercised in `CoverageTest`: a filled S2-style record with the `Coverage limit:`
line blank fails with "the packet reports 1 of 4 authored sessions supplied; the record must state a
'Coverage limit:' naming the dimensions it limits"; a limit that names no dimension fails with
"Coverage limit: must name at least one dimension (D1 to D8) it limits"; the committed H-173 records,
which carry no coverage line, still pass unchanged.

The same two states were run through the CLI end to end on the S2 packet, in the scratch directory
only - this is a probe of the tool, not a review record and not a score for S2:

```
$ course_quality_review.py fill --packet S2-cov.md --scores probe-scores.json
course-quality-review: filled record is invalid: the packet reports 1 of 4 authored sessions
supplied; the record must state a 'Coverage limit:' naming the dimensions it limits
exit 2

$ course_quality_review.py fill --packet S2-cov-limited.md --scores probe-scores.json
filled S2-filled-limited.md: 8 dimension verdicts, validator verdict echoed
exit 0

$ course_quality_review.py check S2-filled-limited.md
course-quality-review: S2-filled-limited.md PASS (8 dimensions, reviewer named, validator verdict
echoed)
exit 0
```

`python3 -m unittest tests.test_course_quality_rubric tests.test_course_quality_s2_repair
tests.test_course_quality_s3_fixture` passes (49 tests). The full suite passed on this branch
before this note's last line was added: `python3 -m unittest discover -s tests -t .` ran 2357
tests in 654.776s, `OK (skipped=1)`. No test reads this file.

## 5. What this does not do, and what it exposes

- It does not re-score S2 or S3, and it does not edit the independent records on
  `wt/h173d-independent-review`. The gap was the artifact's coverage, not the reviewer's effort.
- It does not move a D3, D4 or D5 anchor and does not decide 1 versus 2 for an uncovered objective.
- It does not change the lesson schema, and this is the real remaining weakness: a generated lesson
  records `section_title` and nothing else, so the packet can only match a lesson to a section by
  title, and S1's title matches nothing. A `section_ordinal` or `objective_ref` on the lesson would
  make the objective mapping mechanical instead of nominal. That is a generation and contract
  change, outside this card; recorded here so the next reader does not mistake the title match for
  a strong link.
- It does not retro-charge the records written before the coverage line existed. Their packets
  never printed a count, so the checker cannot require a limitation for them. Re-run the packet on
  the course before citing an old record as coverage evidence.
