# H-173d — independent review of the course-quality rubric, packet and first records

Reviewer: Sentinel (cbqa, adversarial QA — independent of the rubric author, the packet author and
the fixture repairs)
Task: `t_99f1cb89` (H-173d)
Base: master `4358249` (H-173a/b/c repairs merged)
Rubric: `docs/COURSE-QUALITY-RUBRIC.md` sha256 `70bce6af…`
Packet: `scripts/course_quality_review.py` sha256 `68dc4e1b…`

## 1. What this is, and what it is not

This is the independent re-score the rubric asks for in §8. It is **not** a review of a live
output. H-172 (`t_fe097fe7`) is still blocked — its live three-scope run waits on H-184
(`t_742c3242`) and H-185 (`t_77dbd582`) — so the three artifacts scored here are the recorded
fixtures, exactly as the card's entry condition directs. Nothing in this document is a live claim
and none of it may be cited as one.

Independence was protected by sequence: the eight verdicts for each sample were decided from the
raw fixture JSON **before** the corresponding author-run record was opened. Where my read differs
from an author record, the author record is left untouched; the disagreement is named here and in
my own record.

## 2. Artifacts scored

| Sample | Plan | Lesson | Validation | Author record compared |
|---|---|---|---|---|
| S1 single | `plan_one_off.json` `fcca6450…` | `lesson_one_off.json` `a96a6559…` | `validation_pass.json` `9da8cc15…` | `docs/reviews/H173a-S1-single-brake-rescored.md` |
| S2 short (ja) | `plan_ja.json` `58865aec…` | `lesson_ja.json` `983a6cd7…` | `validation_reject_check.json` `e152c05a…` | `docs/reviews/H173b-S2-short-japanese-cafe-repaired.md` |
| S3 short (parent) | `plan_parent.json` `9358219c…` | `lesson_parent_safe.json` `9b59cf96…` | none supplied | `docs/reviews/H173c-S3-parent-kitchen-rescore.md` |

**Provenance defect found before scoring S2.** The handoff comment for S2 instructed me to score
`plan_ja.json` sha256 `160f8c7e5887115ccf2737b2a162e84eb2c1adf3e8af1e99049dfc52a70e1416`. That hash
has never existed: master `4358249` and branch `wt/h173b-s2-quality` both carry
`58865aec3544a4b2ddc72ed32918f90d756bf015f57ae9944e49e170754d55ca`, and
`git log --all -S160f8c7e` finds no commit. I scored the committed artifact. The H-173b record
itself cites `58865aec…` correctly, so the defect is in the comment, not the fixture.

Reproduce:

```bash
git -C . show 4358249:tests/fixtures/generation/plan_ja.json | sha256sum   # 58865aec…
git -C . show wt/h173b-s2-quality:tests/fixtures/generation/plan_ja.json | sha256sum  # 58865aec…
git -C . log --all --oneline -S160f8c7e -- .                            # empty
```

## 3. The three independent records

- `docs/reviews/H173d-S1-independent.md`
- `docs/reviews/H173d-S2-independent.md`
- `docs/reviews/H173d-S3-independent.md`

Each was produced with the packet, filled with my own evidence, and accepted by the checker:

```
course-quality-review: docs/reviews/H173d-S1-independent.md PASS (8 dimensions, reviewer named, validator verdict echoed)
course-quality-review: docs/reviews/H173d-S2-independent.md PASS (8 dimensions, reviewer named, validator verdict echoed)
course-quality-review: docs/reviews/H173d-S3-independent.md PASS (8 dimensions, reviewer named, validator verdict echoed)
```

## 4. Scores, and every disagreement with the author records

| dim | S1 mine | S1 author | S2 mine | S2 author | S3 mine | S3 author |
|---|---|---|---|---|---|---|
| D1 capability_objective_fit | **4** | 3 | **4** | 3 | **4** | 3 |
| D2 sequencing_prerequisite_truth | 3 | 3 | 3 | 3 | 3 | 3 |
| D3 evidence_target_fit | **2** | 3 | **2** | 3 | **2** | 3 |
| D4 example_explanation_quality | 3 | 3 | 3 | 3 | 3 | 3 |
| D5 cognitive_load_session_arc | 3 | 3 | **2** | 3 | 3 | 3 |
| D6 source_grounding_citation_honesty | 3 | 3 | 3 | 3 | **2** | 3 |
| D7 media_necessity | **2** | 3 | **2** | 3 | **2** | 3 |
| D8 learner_agency_recoverability | **2** | 3 | **3** | 4 | **2** | 3 |

**14 of 24 verdicts disagree.** The author-run records score 8×3 on S1, 7×3 + 1×4 on S2 and 8×3 on
S3; an independent read with the rubric in hand does not reproduce that uniformity.

### The disagreements, with reasons

**D3 = 2 on all three (author: 3).** The rubric's own text settles this: lines 147-153 set a 0.1.0
ceiling of 2 for a `procedure` objective carried by a checklist whose attempt stores ticked item
ids with `evidence_class = self_reported` (`coursebook/grading.py:40`). On S1 all four objectives
are `procedure` with `kind: verification` checks; the S1 author record scores 3 and, eight lines
below the claim, says "the build has no attachment lane". On S2 `check_plan[1]` still pairs
`evidence_target: production` with `kind: quiz` (a selection lane), and objectives 2-4 have no
check in the supplied lesson. On S3, three of four `check_plan` entries are bare observations and
the visible check pairs `kind: observation` with `stimulus.format: text`. The validator's
`evidence_target_fit` pass does not answer this question — it asks whether the check is the
strongest lane the build can give the target, not whether the task is as strong as the target the
course claims.

**D7 = 2 on all three (author: 3).** Each plan names media constructs it then fails to supply:
S1 declares `image.level: required` on four sections and the lesson ships one schematic — the
packet prints the mismatch itself ("Lesson media artifacts: 1"); S2 instructs the learner to "say
each phrase aloud" while every `media_need.audio.level` is `none` with `construct: ""`; S3 sorts
"four picture cards" that are never specified and whose `media_need` is `none`. Naming a construct
and then shipping nothing is the anchor-2 case, not anchor 3.

**D8 = 2 on S1 and S3 (author: 3).** D8 anchor 3 requires "a failed attempt has a next move"; both
lessons have `assistance_policy.hint: available` with no hint text anywhere and no stated recovery
after an unticksble item or a wrong sort. A hazard stop condition is not a failed-attempt path. On
S2 I scored 3 against the author's 4: anchor 4 requires "the record says what evidence a retry
produces", and nothing does; the hint named by the policy is never written.

**D6 = 2 on S3 (author: 3).** The plan is honest (`evidence_note`: "a house rule the parent
supplied"; `exclusions`: "No sourced safety claim"), but the learner-facing segment body states
the rule as a general fact: "A grown-up is the only person who fills or switches on the kettle,
because hot water can burn." The mark exists in the plan and never reaches the reader — anchor 2,
"the honest marks are present but thin".

**D5 = 2 on S2 (author: 3).** The check keys the script form こんにちは, which appears first in
`check.stimulus.choices` and `accepted_answers`; the model segment teaches the request, thanks and
farewell in script and the later segments call the target only "the standard daytime greeting".
The learner must recognise a form the session never presents. Cinder's comment asked me to name
this if I disagreed rather than score it as modelled — I disagree, and I name it. The constraint
behind it (`assert_no_answer_leak`) is real; the consequence is a decision for Atlas
(`t_fdf16735`), not a fixture tweak.

**D1 = 4 on all three (author: 3).** This one is me scoring higher, and I hold it: the author
records' stated reason ("the four objectives are steps of one procedure rather than separate
capabilities", "I score the artifact") is not a condition of the D1 4-anchor. That anchor asks for
a stated criterion per objective (every objective has `evidence_criteria`), a named transfer
context (S1: the learner's own brake model from their own manual; S2: "At a café"; S3: with a
parent in the kitchen) and exclusions that bound the claim. All three meet it. If the rubric's
intent is that a single-procedure course cannot reach 4, the anchor text should say so — that is a
wording question for `t_f770bf62`, not a reason to bend the score.

## 5. Timing, and the 15-minute acceptance claim

Measured on this run, UTC 2026-11-08:

| Step | Time |
|---|---|
| Begin protocol reading (§7-§8) | 15:44:44 |
| §3-§4 read as well (see finding F1) | → 15:45:04 |
| S1 packet written | 15:45:04 |
| S1 eight verdicts decided from plan + lesson | → 15:45:47 |
| S2 packet / S3 packet | 15:45:47 / 15:46:55 |
| Three records filled and checker-PASS | 15:48:57 |
| **One course, packet → checker-PASS record** | **3.9 min** |
| **Whole three-sample independent pass** | **4.2 min** |
| `packet` runtime (one course) | 31 ms |
| `check` runtime (one record) | 31 ms |

**Verdict on the 15-minute claim: not falsified, not proven.** The clock above is an agent's, not
a human reviewer's — I read the entire 181-line plan and 116-line lesson in single calls, and the
protocol's own rule ("if a dimension needs more than three minutes ... at most a 2") was never
approached. So the number is a floor, and its usefulness is limited: it shows the mechanical half
is free (31 ms) and that **the entire reviewer cost is reading the raw JSON**, because roughly 80%
of my evidence cites fields the packet does not print — `check_plan[].kind`, `check.stimulus.format`,
`media_need` constructs, `evidence_criteria` text, `exclusions`, segment bodies. The packet summary
alone would not have supported any of the 14 disagreements above. If the claim is meant as "a
human can do this in 15 minutes", it needs a human clock; the honest statement today is "one
reviewer, all-artifact-in-context, 3.9 minutes, dominated by raw-JSON reading the packet could
carry".

## 6. Rubric findings a reviewer cannot resolve

**F1 — §7/§8 cannot be read alone.** The card says to read §7 and §8 only. Both reference D1-D8 by
id; the anchors live in §4 and the scale in §3. A reviewer who literally read only §7-§8 could not
decide a single dimension. Either §7 should inline the anchors or the instruction should say
"§3, §4, §7, §8".

**F2 — D6 anchors 2 and 3 overlap.** Anchor 2 is "most objectives are `unverified`"; anchor 3 is
"an explicit `unverified` mark". A course with 4/4 objectives unverified satisfies 3 literally and
2 in spirit. S1 is exactly that artifact: two reviewers can honestly score 2 and 3 on identical
evidence, and the "below 3 becomes a follow-up card" rule then turns a wording coin-flip into a
work item.

**F3 — D3's procedure ceiling is a decision, not a judgement.** With the 0.1.0 ceiling codified,
every `procedure` course in this build scores exactly 2 on D3 no matter how good it is. That is a
deliberate, recorded limitation (`t_20a8d28c`), but the rubric presents it as a dimension verdict;
the record should have to say "capped by build, not by artifact" so the number is not read as a
quality claim about the course.

**F4 — coverage is unpriced.** The plan authors four sections; the packet takes one lesson. D3/D4/
D5 for the other three objectives are unreadable, yet the packet presents the sample as fully
reviewable and §9's "must say which dimensions had no lesson to read" is not checked. Scored D3 =
2 on S2 and S3 for this reason alone; follow-up `t_7f46fb7f`.

**F5 — no dimension was fully undecidable in these three samples.** Two had ambiguous evidence and
were scored, with the ambiguity named in the record: S2 D6 (`SRC_ALPHA` cannot be resolved to a
ledger from the supplied artifacts — `validation_reject_check.json` carries no source ledger) and
S1 D4 (the example's "model matches the manual" cannot be shown when no manual exists). I did not
invent a score for anything I could not read; where coverage blocked a dimension I scored 2 and
said why.

## 7. Checker acceptance: would I accept this record from someone else?

Partly. The packet is a good artifact: deterministic, hashed, stdlib-only, echoes the validator
verdict, and refuses to emit an aggregate. But `check` is a format check with holes, and after
probing it I would not accept a PASS as proof that a record is honest. Reproduced on this run:

```bash
B=docs/reviews/H173d-S1-independent.md
C="python3 scripts/course_quality_review.py check"
mkdir -p /tmp/neg

# 1. blank reviewer line -> PASS ("reviewer named")
sed 's/^Reviewer: Sentinel (independent, cbqa)$/Reviewer: /' $B > /tmp/h173d-neg/a.md && $C /tmp/h173d-neg/a.md
#   course-quality-review: /tmp/h173d-neg/a.md PASS (8 dimensions, reviewer named, validator verdict echoed)
#   ^ REVIEWER_RE uses \s* which spans the newline, so it captures "Sample: S1" as the name.

# 2. score below 3 with "Follow-up: none" -> PASS
sed 's/^Follow-up: t_fc59d3c6$/Follow-up: none/' $B > /tmp/h173d-neg/b.md && $C /tmp/h173d-neg/b.md
#   course-quality-review: /tmp/h173d-neg/b.md PASS (8 dimensions, reviewer named, validator verdict echoed)
#   ^ violates §8's own rule; `fill` refuses this, `check` accepts it.

# 3. aggregate line outside a dimension block -> PASS
{ cat $B; echo "Aggregate score: 24 out of 32."; } > /tmp/h173d-neg/c.md && $C /tmp/h173d-neg/c.md
#   course-quality-review: /tmp/h173d-neg/c.md PASS (8 dimensions, reviewer named, validator verdict echoed)

# 4. a percentage and a mastery-shaped sentence -> PASS
{ cat $B; echo "Overall quality: 78% across the eight dimensions."; echo "Mastery: 4 of 8 dimensions are strong."; } > /tmp/h173d-neg/d.md && $C /tmp/h173d-neg/d.md
#   course-quality-review: /tmp/h173d-neg/d.md PASS (8 dimensions, reviewer named, validator verdict echoed)
#   ^ FORBIDDEN_PATTERNS is a short phrase list ("average score", "total score", ...). "aggregate",
#     "%", "Mastery:" outside "mastery score"/"mastery percentage" all slip through.
```

What *does* bite, verified: a duplicated dimension id, a missing dimension, wrong dimension order,
a blank score, a non-1-4 score, evidence under 40 characters, and a missing `Sample:`/`Scope:` line
each fail. So the checker catches structural sloppiness and misses the three rules that matter most
for trust: **who reviewed it, whether a low score was actually routed, and whether an aggregate
crept in.**

Two structural gaps beyond the regexes:

- **The record has no provenance field.** Nothing in the format says "fixture" or "live", and the
  checker cannot tell. An author can score a fixture, score every dimension 3, and the record
  passes as a review of a course. That is how the first dry run read before this card.
- **The declared input hashes are never verified.** `check` reads only the record; nothing re-hashes
  `tests/fixtures/generation/*.json`. A record can cite any sha256 it likes. (The S2 handoff comment
  above is a live example of a hash nobody could reconcile.)

Follow-up card for the checker/packet owner: `t_7f46fb7f` covers packet coverage; the regex and
provenance gaps are recorded here for Quill (`t_f770bf62` owns wording) and should become
regression tests before the checker is used to gate anything.

## 8. Verdict and follow-ups

- **15-minute claim:** met on the clock (3.9 min per course, 4.2 min for all three), but the clock
  is an agent's and the protocol's per-dimension budget was never exercised. Not falsified; not yet
  proven as human usability.
- **Packet/check record:** the packet, yes; the checker, no — a PASS is necessary and not
  sufficient, for the three reasons in §7.
- **Independence result:** the author-run records and this independent read disagree on 14 of 24
  verdicts, in both directions. The rubric does discriminate; the first records were too generous
  on D3, D7 and D8 in particular.
- **The rubric is usable.** Eight dimensions, evidence-anchored, no aggregate, and it caught real
  defects (unmodelled target form, missing schematics, unmarked safety copy) that the structural
  validator passes. Its wording needs F1-F4 fixed before the next cycle.

Follow-up cards opened by this review (all gated on this card):

| Card | Owner | Finding |
|---|---|---|
| `t_7f46fb7f` | quill | one lesson cannot cover a four-section plan; D3/D4/D5 coverage unpriced |
| `t_fc59d3c6` | cinder | fixture media declarations do not match what the lesson ships (S1/S2/S3, D7) |
| `t_a84d7ba3` | cinder | failed attempt has no stated next move; hint=available with no hint text (S1/S3, D8) |
| `t_f14d54f7` | cinder | S3 learner-facing safety copy states a house rule as general fact (D6) |
| `t_fdf16735` | atlas | answer-leak rule makes a taught target unmodellable (S2, D5) |

D3 = 2 on all three is not an open card: it is the recorded 0.1.0 ceiling (`t_20a8d28c`).

## 9. What this review did not do

No product code, fixture, rubric, validator, grading, RPC or schema change. No author record was
edited — every disagreement is named here and in my own records. No provider call was made and no
live output is claimed. No operator course or credential was touched. Nothing was pushed.
