# Procedure evidence: no capture lane in 0.1.0

| | |
|---|---|
| Card | `H-173e` / `t_20a8d28c` (follow-up from H-173a `t_c7fff5b4`) |
| Branch | `wt/h173e-procedure-evidence` |
| Base | `38ecc22` (master at pickup) |
| Author | Atlas (architecture), 2026-11-08 |
| Status | **Decided.** Answer is option 3, narrowed: no procedure-evidence lane in 0.1.0, and the checklist stays the lane. |
| Contract / DB delta | **None.** No `cb.rpc` bump, no `cb.db` migration, no new check kind, answer kind, evidence class, verdict, RPC method, upload path or retention rule. |
| Code delta | **None.** Documentation only. |

This card is a decision card. It writes no product code, changes no contract, edits no fixture, no
rubric and no score, calls no provider and spends no money.

---

## 1. Decision

**0.1.0 does not own a procedure-evidence lane.** A procedure objective keeps the verification
checklist it has today, and the checklist keeps recording the learner's own attestation as
`self_reported`. No attempt-level upload and no observer countersign is added, so the honest
boundary is stated instead of the artifact being faked.

The three options in the card, answered:

| Option | Answer | Ground |
|---|---|---|
| 1. Attempt-level artifact attachment with its own evidence class, not `self_reported` | **Rejected for 0.1.0** | Contradicts the frozen construct decision (`docs/ASSESSMENT-BREADTH.md` §1, §5) and would overclaim an evidence class §5 already bounded at `self_reported` |
| 2. Observer confirmation lane recorded `reported`/`observed` | **Rejected for 0.1.0, and rejected on method** | No identity for a second person exists in this build; `parent_reported` already carries the one observer with a stable relationship, and a typed name is not an observation |
| 3. Neither; document the boundary | **Adopted, with the checklist kept** | See §4. The card's second half ("procedure objectives should stop declaring a checklist as their evidence target") is refused: the checklist is the only thing 0.1.0 can collect, and completion on a self-reported checklist is already promised by `PREBUILD_SPEC.md` §5 |

---

## 2. Measured state at `38ecc22`

Everything below is read from the tree, not inferred from the card.

| Fact | Evidence |
|---|---|
| Attempt answers are text or selection only | `contracts/vocabulary.v1.json:49-53`, `answer_kind` enum `["text","selection"]`; the description states "Audio/image answers are rejected with a text alternative" |
| The confirmation lane can only claim one class | `coursebook/grading.py:40` `CONFIRMATION_EVIDENCE_CLASS = "self_reported"`, used at `:194` |
| Only `cold` counts as independent evidence, and `override` never grants mastery | `contracts/vocabulary.v1.json:18-21` |
| No learner submission path exists in the artifact store | `docs/ASSESSMENT-BREADTH.md:127`; `grep -c '"artifact.submit"' contracts/rpc.v17.json` → `0`; `coursebook/artifacts.py` has `stage/adopt/record` for **Coursebook-authored** media (`ARTIFACT_KINDS` at `:44`) |
| The product already discloses the ceiling before the plan is approved | `docs/ASSESSMENT-BREADTH.md:283-284` — "This build cannot collect or grade a program, a recording, **a photo**, or a built object"; frozen by `tests/test_desktop_breadth_copy.py:19-23` and asserted against `desktop/plugin.js` |
| The kernel's own procedure rubric expects a checklist as the verification criterion | `coursebook/rubrics.py:144-166`, `procedural`: `ordered_steps`, `safety_stop_condition`, `verification` ("Checks the finished result against the stated measurement **or checklist**") |
| The generations gate is already explicit about the evidence class | `docs/ASSESSMENT-BREADTH.md:34` "Submitted artifact … **Out** … Gated … an evidence class that can never advance alone" |

The card's factual premise is therefore correct and the architectural answer is already recorded:
the ledger, the RPC, the grader and the artifact store agree, and §7.1 already tells the learner the
photo cannot be collected. What was missing was not a lane; it was the sentence saying so for
procedure objectives.

---

## 3. Why not option 1

1. **It is the construct `ASSESSMENT-BREADTH.md` §1 froze out of 0.1.0.** Re-opening it is a product
   scope decision, not a contract amendment, and §10.3 names four gates that are all unmet: a
   bounded submission method with magic-byte MIME validation and a mandatory text equivalent; an
   evidence class that can never advance an objective alone; no execution/render of uploads; and a
   retention/deletion rule with pack-export exclusion. None of the four exists, and the fourth has
   no design at all (`coursebook/artifacts.py` `reconcile()` is a stale-row sweep, not a learner-data
   retention policy).
2. **"Its own evidence class, not `self_reported`" contradicts §5, which is right.** §5 states the
   ceiling directly: "an uploaded photo of a birdhouse proves a photo exists. At best
   `self_reported`; it can never be `cold` without a person inspecting the object." The
   `evidence_class` enum is a frozen shared vocabulary (`contracts/vocabulary.v1.json:14-21`) whose
   values describe **how the answer was produced** (`cold`, `hinted`, `answer_shown`,
   `self_reported`, `parent_reported`, `override`). "Learner-supplied opaque bytes" is not one of
   those; it is a storage attribute. A seventh label would either need an independence meaning the
   kernel cannot test or would smuggle a storage fact into the policy field that decides objective
   advancement.
3. **It would be a partially wired control at release, with a content-safety surface the product
   does not have.** §5 already prices that risk as Medium and names the distribution risk
   ("accepting learner photos invites a content-safety policy the product does not have and should
   not improvise"). The submission date is 2026-11-11; a collection surface plus retention plus UI
   plus adversarial tests is not a three-day item, and shipping it half-wired is the failure mode
   `PREBUILD_SPEC.md` §2 forbids.
4. **It would require editing a frozen learner-facing string.** The plan preview at
   `ASSESSMENT-BREADTH.md:283-284` states the build cannot collect a photo, and
   `tests/test_desktop_breadth_copy.py` asserts it verbatim against `desktop/plugin.js`. Shipping a
   photo lane without rewriting that string would make the product lie on its own plan screen.

---

## 4. Why not option 2

The observation lane exists and is closed (`observation.record`, `cb.rpc` v14, `cb.db` v9), and it
records exactly two classes: `self_reported` and `parent_reported` (`coursebook/domain.py:4191`,
`_OBSERVATION_CLASSES`). That is the whole vocabulary of observation this build has, and it is
correct as far as it goes: a parent holds the profile, so the parent's report is a report by a
different person, labelled as such (`"Reported by the parent — not graded by Coursebook."`).

A **generic** second-person lane fails on identity, not on schema. A countersign typed on the
learner's machine is a string in a text field; there is no login for the observer, no second device,
no key, and no way to distinguish "my brother checked the lever" from "I typed my brother's name".
Recording that as `observed` — a class that does not exist — would be a stronger claim than the
system can support, and it is the same overclaim the generation pipeline refuses when it declines
to call a same-model validation `independent` (`docs/GENERATION.md` §1). The one case worth keeping
is already covered: a parent-led course uses `parent_reported`, and the brake course's
second-person item is stored as the learner's own attestation of what the second person said. That
is what H-173a did, and it is the honest version.

---

## 5. The boundary this decision fixes

For every course authored, validated or scored in 0.1.0:

- `evidence_target: procedure` names **the construct the course teaches**. It does not name a
  submission lane, and it never implies that an artifact was collected.
- The only lane that can carry a procedure check is a `verification` check with
  `reference.kind = rubric_only`, submitted as a `selection` of item ids and recorded
  `evidence_class = self_reported`.
- The course must say, in the plan and in the lesson's own instructions, that the result is the
  learner's attestation, and it must name the observable acts (a photo taken, a second person
  present) as acts a **human reviewer** could check. It must not claim an upload, an observer record
  or an independent verification exists.
- **The rubric's D3 anchor for this case is 2, not 3.** `docs/COURSE-QUALITY-RUBRIC.md` D3 (on
  `wt/h173-course-quality-rubric`, unmerged at this base) already names it: "2: the target is
  plausible but the task is weaker than claimed (**self-ticked
  checklist for a procedure**, recognition for transfer)". Labelling the checklist honestly and
  naming the observable acts makes the weakness visible; it does not change what was collected, so
  it does not lift the anchor. 0.1.0 therefore has a **D3 ceiling of 2** for any course that
  declares `procedure` and collects only a checklist. That ceiling is a construct fact, not a
  defect to be papered over, and it is why §7.1 discloses the limit before the plan is approved.

Two gates, two questions — they are not supposed to agree, and neither is wrong:

| Gate | Question | Answer for a checklist-only procedure course |
|---|---|---|
| Validator criterion `evidence_target_fit` (`coursebook/generation.py:188`) | Is this the strongest lane this build can give the declared target? | **pass** — in 0.1.0 the checklist *is* the procedure lane, and the alternative is no course at all |
| Rubric dimension D3 `evidence_target_fit` | Is the task as strong as the target the objective claims? | **2** — it is not as strong, and the course says so |

A validator pass is a structural gate ("this may reach a learner"); D3 is a design lens ("this is
weaker than it claims"). Reading one as a refutation of the other is the error this boundary
prevents.

---

## 6. Contradiction reported, not fixed: H-173a's D3 score

`docs/reviews/H173a-S1-single-brake-rescored.md:113-117` (on `wt/h173a-s1-single-brake`, unmerged)
records **D3 = 3** and reasons: "The criteria are the objectives' criteria in observable form and
the learner instructions label the result a self-report, so **the check no longer presents a tick
alone as procedure evidence**".

The second clause is false at the storage layer, and the same record says so two lines later
("the build has no attachment lane"). After the repair, `attempt.submit` still stores a `selection`
of ticked item ids with `evidence_class = self_reported`; the photo and the second-person item are
ticked, not captured. The task is still a self-ticked checklist for a `procedure`, which the
rubric's own D3 anchor scores 2.

Per this card's non-goals, the record, the fixture and the score are **not** edited here. The
finding is routed to the rubric owner (the D3 anchor's wording and the 0.1.0 ceiling) and to the
independent reviewer (H-173d `t_99f1cb89`, which re-scores with its own evidence). If the operator
accepts this reading, H-173a's D3 is 2 and its "D3 went 2 → 3" claim is withdrawn; the fixture
repair stands on its own, since the honesty of the labels is still an improvement over a bare tick.

---

## 7. What changes, and what does not

**Changes (documentation only).** A decision note in `docs/ASSESSMENT-BREADTH.md` §5 pointing at
this record, so the next person reading the construct table cannot conclude that the lane decision
is still open.

**Does not change.** No fixture (`tests/fixtures/generation/plan_one_off.json`,
`lesson_one_off.json`), no review record, no score, no `docs/COURSE-QUALITY-RUBRIC.md` text, no
validator, no prompt, no RPC, no `cb.db` schema, no grading lane, no UI, no frozen learner copy.
`coursebook/grading.py:40` stays `self_reported`; `contracts/vocabulary.v1.json` keeps six classes
and two answer kinds.

**What would flip the answer.** A product-scope decision by the operator to admit submitted
artifacts after 0.1.0, plus §10.3's four gates satisfied with evidence: a bounded submission method
with sniffed MIME and a text equivalent, a class that can never advance an objective alone, no
execution or active rendering of uploads, and a retention/deletion rule with pack-export exclusion.
Until all four have executable proof, procedure objectives record attestation and say so.
