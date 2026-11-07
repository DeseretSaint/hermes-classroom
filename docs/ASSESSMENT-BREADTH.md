# Assessment construct breadth — frozen decision for 0.1.0

| | |
|---|---|
| Card | `H-16` / `t_3c5d969c` ("Assessment construct breadth decision — code, performance, artifact") |
| Branch | `wt/harness-assessment-breadth` |
| Base | `a12176b` (current master: `wt/harness-contract-v10` and `wt/harness-source-trust` merged) |
| Author | Atlas (architecture), 2026-11-07 |
| Source finding | `docs/ADVERSARIAL-AUDIT-ROUND2.md` P1-5 (Sable) |
| Status | **Frozen.** Implementation of any *new* construct is not authorized by this document. |
| Contract / DB delta | **None.** No `cb.rpc` version bump, no `cb.db` migration, no schema change. |

This card is a decision card. It writes no product code, changes no contract, spends no provider
money and is not demo copy. `PREBUILD_SPEC.md` §2 already says a contest submission must be "a
coherent working vertical slice, not a wide set of partially functional controls"; this document
applies that rule to assessment constructs.

Card key note: the round-2 report calls this work "H-14", the board registered it as **H-16**
(`docs/HARNESS-NEXT-CARDS.md:44`), and `HARNESS-NEXT-CARDS.md` §"Second wave" makes the board keys
authoritative over the report's proposed numbering. H-16 is used throughout.

---

## 1. Decision

**Executable code, recorded performance and submitted artifacts are out of scope for 0.1.0.**
They are deferred behind named gates (§10), not silently dropped and not faked. No check kind, no
answer kind, no evidence class and no RPC method is added for them.

| Construct | 0.1.0 | Later | Gate |
|---|---|---|---|
| Executable code (program submitted, tests run) | **Out** | Gated | §10.1 — a documented host-provided sandbox seam plus a deterministic execution grading lane |
| Recorded performance (spoken pitch, played music, timed delivery) | **Out** as evidence. Language pronunciation practice already ships as `model_assessed` practice and stays labelled practice only | Gated | §10.2 — a transcription seam the plugin may legally reach, retention policy, and a measured rubric lane |
| Submitted artifact (photo, audio of a built object, document, image evidence) | **Out** | Gated | §10.3 — a contract submission method, bounded bytes/MIME, and an evidence class that can never advance alone |

**Why this is consistent with "teach anybody anything."** The mission claim is about the
*curriculum* being able to target any subject, not about the harness collecting any object a
learner can produce. Any topic can still be planned, taught and checked through the surfaces in
§2 — what changes for the three constructs above is the *evidence ceiling*: the harness can teach
the topic but cannot independently verify work that is a program, a performance or a physical
object. That ceiling is a product fact, and §7 states it to the learner **before** they invest in a
check, not at submission.

**Why not "in scope now."** Each construct needs (a) a collection surface, (b) a storage and
retention rule, (c) an evidence class that does not overclaim, (d) a grading lane, and (e) a UI.
None of (a)–(e) exists for any of the three, and two of them would have to widen the *contract*,
which is frozen. Adding a check kind the grader cannot grade is the exact failure this card exists
to prevent.

---

## 2. What the harness can collect and grade at `a12176b` (measured, not assumed)

### 2.1 The closed vocabulary

| Surface | Values | Authority |
|---|---|---|
| Check kind | `quiz \| verification \| observation` | `coursebook/generation.py:565` (`CHECK_PLAN_SCHEMA`) and the lesson schema at `:797`. Authoring vocabulary only: `checks` has no kind column (`coursebook/migrations/0001_initial.sql:87-101`) and `cb.pack` checks declare none, so a stored check carries a stimulus format and an evidence target, not a kind. |
| Stimulus format | `text \| selection \| verification` | `generation.py:804`; `contracts/rpc.v10.json:6153-6159` (`check_stimulus.format`) |
| Answer kind | `text \| selection` | `contracts/vocabulary.v1.json:49-53` — "Audio/image answers are rejected with a text alternative." |
| Evidence target | `recall, comprehension, production, discrimination, procedure, transfer` | `generation.py:127`; `contracts/vocabulary.v1.json:23-27` |
| Evidence class | `cold, hinted, answer_shown, self_reported, parent_reported, override` | `contracts/vocabulary.v1.json:18-21` — "Only `cold` can count as independent evidence; `override` grants access, never mastery." |
| Verdict | `pass, partial, not_yet, needs_retry, clarification` | `contracts/vocabulary.v1.json:28-32` |

`tests/test_adversarial_round2.py:323-332` (`test_check_vocabulary_is_closed`) pins the absence:
`format: "code"` and `format: "performance"` are schema-rejected, and `performance`/`artifact` are
not evidence targets. That test stays green after this decision — the decision does not widen the
vocabulary.

### 2.2 Two grading lanes — and the gap that governs this whole card

`coursebook/grading.py:201-227` routes an answer by the **reference** the check stores:

- `reference.kind ∈ {exact, numeric, selection}` (`validators.py:29`) → deterministic, in-process
  grading. No provider. This is the only lane that produces a real verdict today.
- anything else — including a **missing** `kind`, or `rubric_only` — → the open lane. The open lane
  is a bounded aux adapter that the shipped runtime never configures:
  `configure_aux_grader` is called only from tests, and `docs/ARCHITECTURE.md` §4.4 states it
  plainly ("the auxiliary open-response lane stays unconfigured … so it sends nothing"). With no
  adapter, `grade_open` raises `GradingUnavailable`, the attempt is persisted as `needs_retry`,
  and **nothing advances** (`domain.py:1184-1204`; no transition row is written on that path).

Two writes make that gap reachable in normal use, and neither is in the audit's P1-5:

1. **Generated lessons store no reference `kind` at all.** `generation._check_payloads`
   (`generation.py:3524-3528`) writes `reference_answer`, `accepted_answers`,
   `accepted_alternatives`; `tests/test_generation.py:868-872` asserts those three keys are present
   in the stored reference and asserts nothing about a lane. A generated check therefore routes to
   the open lane.
2. **Imported packs with a `production` or `transfer` target store `{"kind": "rubric_only"}`**
   (`coursebook/pack_flow.py:253-261`), which is also the open lane.

Measured on `a12176b`, through the real command path (`domain.record_objective` → `plan.approve` →
`check.open` → `attempt.submit`), correct answer in both cases:

```
# generated shape: reference {reference_answer, accepted_answers, accepted_alternatives}, no kind
{"ok": true, "verdict": "needs_retry", "next_action": "retry_grading", "provenance": null}

# control: same path, reference {"kind": "numeric", "value": "4", "tolerance": {"abs": "0"}}
{"ok": true, "verdict": "pass", "next_action": "complete_objective", "provenance": null}
```

Probe scripts (not committed; they exercise the public commands, no provider):
`~/.hermes/profiles/atlas/cache/scratch/probe_breadth_ref.py` and
`probe_breadth_closed.py`. Run as
`PYTHONPATH=. python3 <probe>.py` from the worktree root.

`tests/kernel_support.py:1-6` states the same thing in its module docstring: nothing is mocked
except the aux grader, "which has no implementation in this build by design", so the closed lane is
the shipped truth, not a test artefact. `DEFECTS.md` CB-QA-11 records that enabling the lane today
is unsafe (an injection-bearing "pass" is accepted with no structural cross-check).
Consequence: **enabling the open lane is not a one-line fix and is not part of this card.**

This matters for the card's own question. The audit asks whether the harness should widen from
three input formats to code/performance/artifact. Measured, the harness's *existing* written-answer
surface is narrower than the docs suggest: a learner can submit free text, but in this build a
written explanation is **collected, persisted, and not graded**. So the honest alternative to a
program, a pitch or a birdhouse is not "write an explanation and get it graded" — §8 states what it
actually is.

### 2.3 Non-text evidence that already exists — and what it is for

| Surface | What it actually does | Not what it does |
|---|---|---|
| Pronunciation (`coursebook/pronunciation.py`) | One explicit record action, ≤3 MB, MIME sniffed from bytes, local recogniser only, take written to a `0600` temp file and deleted in a `finally` block, typed result stored with `evidence_class = 'model_assessed'` in a separate `pronunciation_attempts` table | It never retains audio, never writes an `attempts` row, never advances an objective, and is not "verified pronunciation". `docs/PRONUNCIATION-SEAM.md` row 2 records the host STT seam as unreachable. |
| Artifact store (`coursebook/artifacts.py`) | Content-addressed store for **Coursebook-authored** media: kinds `visual/audio/pdf/pack/export/other`, caps 8/64/32/64 MB, magic-byte sniff against a MIME allowlist, mandatory text equivalent | It has no learner-submission path. The only artifact RPC is `artifact.get` (read). There is no `artifact.submit`, no upload control, and no evidence class for a learner-supplied file. |
| Observation (`domain.record_observation`) | Writes a layer-1 record with `self_reported` or `parent_reported`; refuses anything else (`domain.py:2998-3028`) | It is **not reachable from the contract**: `grep -rn record_observation` finds only its definition and two test call sites. No RPC method, no handler, no UI. See §11 B-2. |

### 2.4 What the breadth limit actually is

The harness's declared breadth (three check kinds, three stimulus formats, six evidence targets) is
adequate for text-shaped subjects. The binding limits today are, in order:

1. the open-response lane is unconfigured, so generated checks cannot be graded at all (B-1);
2. the observation path exists but is unreachable (B-2);
3. therefore no construct that needs a non-text *submission* can be honestly added, because there
   is no working lane to attach it to.

Points 1 and 2 are follow-up cards (§11), not this card's work. The construct decision does not
depend on them being fixed: even with both fixed, code, performance and artifact each still need
§10's gates.

---

## 3. Construct: executable code

**What "in scope" would require.** Collection: a code check kind with a language tag, a bounded
source field (byte cap), and an explicit submit action. Storage: source + language + run outcome,
with a retention/deletion rule and a pack-export exclusion. Evidence class: execution is
deterministic when it runs hidden tests, so it could be `cold` — but only if the learner never saw
the tests, and the harness has no proctoring claim. Grading lane: a runner that executes the
submission against tests, returns per-test outcomes plus a verdict, and fails closed to
`needs_retry` on timeout. Sandbox: process isolation, wall-clock and memory caps, network denied,
read-only host filesystem except a scratch dir, no credentials in the environment, and no path from
the runner back into the host profile (`$HERMES_HOME`, `cb.db`, artifacts). UI: a source editor or
textarea with a visible run budget and an honest "tests are hidden" label. Source/media: the
submitted program is untrusted input; it must never be rendered, evaluated in the plugin process,
or fed to a model as instructions.

**Cost.** L. A sandbox is a new runtime dependency in the distribution, a toolchain matrix (the
learner's language set is open-ended), a concurrency/time budget, and a storage story. It is not a
schema change plus a textarea.

**Risk.** High, and the highest of the three. Arbitrary code is the only construct here that can
exfiltrate the learner's files, the profile database, or host credentials; `docs/ARCHITECTURE.md`
§3 lists no execution or container seam the plugin may use, and the plugin's Python half runs
in-process on the host. The only `subprocess` in the package today is the fixed local `ffmpeg`
invocation in `coursebook/stt.py:162-195` with an argv the learner cannot influence; that is not a
sandbox and must not be described as one. Secondary risk: a pass on hidden tests is a real
capability claim, so a flaky or under-specified test suite becomes a false claim of programming
ability.

**Pedagogical value.** High for a large slice of "anybody anything" (programming, data, scripting,
statistics). This is the construct whose absence is most visible in the product's promise.

**Verdict.** Out for 0.1.0. Gate: §10.1.

---

## 4. Construct: recorded performance

**What "in scope" would require.** Collection: a bounded audio/video submission (duration cap,
MIME sniffed from bytes, explicit record action, no background capture). Storage: a retention rule
that the learner can read before recording, plus pack-export exclusion. Evidence class: a rubric
assessment is `model_assessed` at best — never `cold`, because the grader is a model and the
recording does not prove conditions. Grading lane: the open lane, measured on a per-language/per-
skill slice (`PREBUILD_SPEC.md` §8's 60-case floor per grader configuration and slice). Runtime:
transcription that the plugin may legally reach.

**What already exists and is honestly labelled.** `pronunciation.attempt` is a real, shipped,
non-text lane: local recogniser, typed comparison, `model_assessed`, no retention, explicit
"Practice only, not graded" UI (`desktop/plugin.js:5112, 5126, 5580`). It is a practice measurement
and it cannot advance an objective. That is the correct template for this construct — and it is
also evidence of how much remains: transcription of a free performance, rubric dimensions
(delivery, structure, audibility), and retention are all absent.

**Cost.** M–L. The recogniser exists; the seam to the host's STT does not (`docs/PRONUNCIATION-SEAM.md`
row 2: `no_transcription_tool`, `no_transcription_rpc`, `ctx_rest_is_namespaced`). Retention alone
turns a "never stored" design into a data-protection design with deletion, export exclusion and a
learner-visible policy.

**Risk.** Medium–high. Voice is personal data; a stored recording is a new breach surface and a new
thing packs must exclude. The larger product risk is false precision: a model's score on a
two-minute pitch will be read as an expert judgement unless the copy fights that reading. An
artifact/recording must never become a repair authority either: it may be *referenced* by an
attempt, never parsed into the rubric or used to rewrite a check.

**Pedagogical value.** High for languages, music, public speaking, interviewing, clinical and
trades communication — and it is the construct the pronunciation slice already proved is wanted.

**Verdict.** Out as evidence for 0.1.0; the existing practice-only lane stays and stays labelled.
Gate: §10.2.

---

## 5. Construct: submitted artifact (photo, document, built object)

**What "in scope" would require.** Collection: `artifact.submit` (or equivalent) in the contract,
bounded bytes, MIME sniffed from magic bytes rather than the declared type, one text equivalent
mandatory, and an explicit learner action. Storage: content-addressed like
`coursebook/artifacts.py` but with a retention/deletion rule and pack-export exclusion. Evidence
class: an uploaded photo of a birdhouse proves a photo exists. At best `self_reported`; it can never
be `cold` without a person inspecting the object. Grading lane: none that is honest — the harness
can verify file integrity and nothing about the object. UI: an upload surface, a preview that never
executes or renders active content, and a label that says who assessed it. Security: MIME/decoder
validation, size caps, no SVG/HTML rendering, no path traversal, no remote fetch, and no route from
uploaded bytes into a prompt.

**Cost.** M. The store and its validation patterns exist; the contract method, the retention rule,
the evidence class decision and the UI do not.

**Risk.** Medium. Uploaded bytes are the classic attack surface (polyglot files, decompression
bombs, active content), and the product risk is a false verification claim — "I photographed it,
therefore I built it" is not evidence. Distribution risk is real too: accepting learner photos
invites a content-safety policy the product does not have and should not improvise.

**Pedagogical value.** High for crafts, trades, cooking, art, lab work and parent-led projects.

**Verdict.** Out for 0.1.0. Gate: §10.3.

---

## 6. Comparison

| | Code | Performance | Artifact |
|---|---|---|---|
| Collection surface today | none | bounded audio (pronunciation only, practice) | none (author media only) |
| Storage/retention today | n/a | take deleted after scoring; nothing retained | authored media only, no learner uploads |
| Honest evidence class | `cold` only with hidden tests; otherwise none | `model_assessed` | `self_reported` at best |
| Grading lane that could carry it | new deterministic execution lane | the open lane, currently unconfigured and unsafe to enable | none that verifies the object |
| Sandbox requirement | **mandatory**, none available | bounded inputs, no execution | no execution/render of uploads |
| Cost | **L** | **M–L** | **M** |
| Risk | **High** | **Medium–high** | **Medium** |
| Pedagogical value | **High** | **High** | **High** |
| 0.1.0 verdict | out | out (practice lane stays) | out |

Nothing in this table is a capability claim. All three are valuable and all three are blocked by
missing infrastructure, not by missing ambition.

---

## 7. Learner-facing copy (frozen strings)

Copy is **keyed to the harness's real lane**, never to a guess about the topic. The product must
not run a keyword classifier over the learner's goal and announce a construct-specific limit it
cannot actually detect; the same static disclosure is shown for every plan. This is the same rule
`docs/CAPABILITY-POLICY.md` §2 applies to media: a decision that cannot name its construct is a
preference.

### 7.1 Plan preview — always shown above `OUTCOMES`

Anchor: `desktop/plugin.js:1147` (`PanelSectionLabel` "OUTCOMES (n)"), objective rows
`1150-1175`.

> **What Coursebook can check**
> Written answers, choices, and checklists. This build cannot collect or grade a program, a
> recording, a photo, or a built object. Checks marked "practice only" never advance a section.

No per-topic variant. If the goal is "write and test a Python function" or "build a birdhouse",
this same line is already on screen before the plan is approved — the learner learns the ceiling
while the plan is still editable.

### 7.2 Check card — footer, always

Anchor: the attempt card at `desktop/plugin.js:3960-3995` (result block) and the check surface
above it.

> Your answer is text, a choice, or a checklist. Nothing you type is executed.

### 7.3 Evidence screen — keyed to the lane, not the construct

Anchor: `EvidenceClassText` (`desktop/plugin.js:3732`) and `NEXT_ACTION_COPY`
(`3709`).

- Closed reference (`kind ∈ exact|numeric|selection`): existing copy, unchanged.
- Open reference (`rubric_only` or missing kind) — the state of every generated check in this
  build (B-1):

  > **Saved, not graded.** This build has no grading model for open answers, so no verdict was
  > produced. Your answer is saved, no progress was changed, and Retry grading does not consume an
  > attempt.

  Actions stay exactly as `UX_SPEC.md` §8 already specifies for `needs_retry`: Retry grading, Edit
  answer, Move on (records override).
- Observation (`self_reported` / `parent_reported`) — once B-2 makes it reachable:

  > Reported by you — not independently verified.
  >
  > Reported by the parent — not graded by Coursebook.

  These two strings must be added to `EVIDENCE_CLASS_COPY` (`desktop/plugin.js:3690-3695`), which
  today has four of the six contract classes and falls back to the raw enum value at `3732`.

### 7.4 What the teaching chat may and may not claim

The continuation prompt already carries only the committed public verdict
(`PREBUILD_SPEC.md` §8). Add to the lesson/continuation directive set, as a hard rule:

> Never claim that Coursebook ran code, heard a recording, or inspected a photo. You may discuss
> code, describe how to test it, and ask the learner to explain their result. Coursebook's check
> verdicts come only from the check surface.

This is the chat-side half of the same rule: no fake capability in prose when the harness has none.

### 7.5 Implementation anchors

| Copy | Where it goes | Owner |
|---|---|---|
| 7.1 plan disclosure | plan preview panel, above `OUTCOMES` | Vellum |
| 7.2 check footer | check surface / attempt card | Vellum |
| 7.3 lane-keyed evidence copy + two evidence-class labels | `EVIDENCE_CLASS_COPY`, `NEXT_ACTION_COPY`, `EvidenceClassText` | Vellum |
| 7.4 chat directive | generation prompt constants + continuation prompt | Cinder |

None of this is implemented by this card.

---

## 8. Alternatives the harness actually offers

The card asks which alternatives the harness offers instead. Measured at `a12176b`, the honest
answer is narrower than the design intends, and the table must say so:

| Alternative | Reachable today? | What it yields | What it cannot yield |
|---|---|---|---|
| Written answer graded against a **closed** reference (`exact`/`numeric`/`selection`) | **Yes** — imported pack checks whose target is not `production`/`transfer`; any check whose reference carries a closed kind | A real verdict, `cold`/`hinted`/`answer_shown` evidence, an objective transition | Judging an explanation, a program, a design or a performance |
| Written explanation graded by a model | **No** — the open lane is unconfigured; the attempt persists as `needs_retry` (B-1) | A saved answer and an honest "not graded" | Any verdict, any progress, until the lane is configured and measured (and CB-QA-11 says enabling it as-is is unsafe) |
| Checklist / rubric-scored plan | **No** — same lane problem for generated checks; `pack_flow` maps `production`/`transfer` to `rubric_only` | A saved submission | A verdict in this build |
| Observation (`self_reported` / `parent_reported`) | **No** — `record_observation` has no RPC method, handler or UI (B-2) | Nothing a learner can reach | Any record, until a contract method exists |
| Pronunciation practice | **Yes** — `pronunciation.attempt`, local recogniser | A `model_assessed` practice measurement | Evidence, progress, or a mastery claim |

So the truthful learner-facing position is: **"the harness checks what it can compare."** For a
program, a pitch or a birdhouse, 0.1.0 offers teaching, discussion, and closed-form checks about
the work — and it says so instead of collecting a submission it cannot grade. §11's B-1/B-2 cards
are what turn the second and fourth rows into real alternatives.

---

## 9. Frozen interface surface (what 0.1.0 may not change)

No new values may be added to these in 0.1.0, for any construct in this document:

- `CHECK_PLAN_SCHEMA.kind` and the lesson check `kind` stay `quiz | verification | observation`
  (`generation.py:565`, `:797`). This is authoring vocabulary, not a stored column — do not add a
  `kind` column to `checks` either.
- `stimulus.format` stays `text | selection | verification` (`generation.py:804`;
  `contracts/rpc.v10.json:6153-6159`).
- `answer_kind` stays `text | selection` (`contracts/vocabulary.v1.json:49`).
- `evidence_target` stays the six labels (`generation.py:127`).
- `evidence_class` stays the six labels (`contracts/vocabulary.v1.json:18`). `model_assessed` is
  **not** an evidence class and must never be promoted into one.
- No `artifact.submit`, `code.run`, `performance.submit` or `observation.record` method.
- No learner-upload path in the artifact store; `artifact.get` stays read-only.
- No retention of learner audio, video or files.

If a later implementation needs any of these, it needs a contract revision, a migration, a new
lane, and the gate evidence in §10 — in that order.

---

## 10. Gates and acceptance tests for a later implementation

Nothing below is authorized now. Each gate is a fact that must exist **before** a spike card, and
each acceptance test is what the spike must demonstrate with real command output.

### 10.1 Code execution — gate

1. A **documented** host/plugin seam for sandboxed execution (or an approved out-of-process runner
   the plugin is permitted to launch), with wall-clock, memory, process-count and network limits.
   "We can call `subprocess` from the plugin's Python half" is not a gate; that is the host process.
2. A deterministic execution grading lane that runs hidden tests, records per-test outcomes, and
   fails closed to `needs_retry` on timeout/error — never a pass.
3. A retention rule (delete source and run logs after N days, exclude from packs and exports).
4. A decision on the evidence class that states what a hidden-test pass does *not* prove.

**Acceptance test (vertical slice).** Given a course whose objective is "write a function that
returns the second-largest distinct value", a learner submits (a) a correct function, (b) a
function that returns the maximum, and (c) an infinite loop. Expect: (a) `pass` with per-test
outcomes and `cold` only if the tests were never shown; (b) `not_yet` naming the failing test, no
state advance; (c) `needs_retry` after the wall-clock cap, no process left running, no state
advance. Repeat with a submission that tries to read `$HERMES_HOME/cb.db`, open a socket, and write
outside its scratch dir: all three attempts are refused by the sandbox, and the attempt is
`needs_retry`, not `pass`.

### 10.2 Recorded performance — gate

1. A transcription path the plugin may legally use (unblock `docs/PRONUNCIATION-SEAM.md` row 2, or
   contract the local recogniser explicitly), plus a stated quality bound.
2. A retention policy visible before recording, with deletion and pack exclusion.
3. The open lane configured **and measured** on a labeled slice (`PREBUILD_SPEC.md` §8: 60 cases
   per grader configuration and domain/language slice; per-category false-pass/false-block/retry),
   with CB-QA-11's injection cross-check closed.
4. Copy that never turns a model score into verified pronunciation, mastery or an expert review.

**Acceptance test.** Given a two-minute spoken answer against a rubric of four observable criteria:
expect a typed rubric result with `model_assessed` provenance, no objective transition, a stored
retention record that the learner can read before recording, an export that contains no audio, and
a deliberately off-topic/gibberish take that returns `practice_only`/`needs_retry` — never a
fabricated score.

### 10.3 Submitted artifact — gate

1. A contract submission method with bounded bytes, magic-byte MIME validation, mandatory text
   equivalent and an explicit learner action.
2. An evidence class that can never advance an objective alone; an artifact is opaque bytes and may
   be *referenced* by an attempt, never parsed into the rubric, never used to regenerate
   remediation, never used to amend a check or plan (**no repair authority**).
3. No execution, no active rendering (no SVG/HTML), no remote fetch, no path traversal; preview in
   a passive image/PDF viewer with an explicit size limit.
4. A retention/deletion rule and pack-export exclusion.

**Acceptance test.** Given "build a birdhouse": submitting a photo stores it, shows the file with
its text equivalent and an explicit `self_reported` label, and leaves the objective at
`introduced` — a pass still requires the closed-form or observation check. Submitting a polyglot
file, a 200 MB file, a file whose declared MIME disagrees with its bytes, and a file whose name
contains `../` are each refused with a typed error and no row. No marker appears in any prompt or
generation input.

---

## 11. Defects found while deciding (report only; not fixed here)

| ID | Severity | Owner | Summary |
|---|---|---|---|
| **B-1** | High | Cinder | Generated lesson checks store no reference `kind`, so `grading.grade` routes every generated check to the unconfigured open lane: the learner's answer is persisted and the verdict is `needs_retry`. Imported `production`/`transfer` checks do the same via `rubric_only`. |
| **B-2** | High | Cinder | `domain.record_observation` has no RPC method, handler or UI. `self_reported`/`parent_reported` are declared contract classes that no learner can produce. |
| **B-3** | Low | Vellum | `EVIDENCE_CLASS_COPY` (`desktop/plugin.js:3690`) covers 4 of 6 contract evidence classes; `self_reported`/`parent_reported` render as raw enum text once B-2 makes them reachable. |

Reproduction for B-1 (verbatim, `a12176b`):

```
$ PYTHONPATH=. python3 ~/.hermes/profiles/atlas/cache/scratch/probe_breadth_ref.py
PROBE_RESULT={"ok": true, "verdict": "needs_retry", "next_action": "retry_grading", "provenance": null}
$ PYTHONPATH=. python3 ~/.hermes/profiles/atlas/cache/scratch/probe_breadth_closed.py
PROBE_RESULT={"ok": true, "verdict": "pass", "next_action": "complete_objective", "provenance": null}
```

B-2 reproduction: `grep -rn "record_observation" --include=*.py .` returns
`coursebook/domain.py:2998` plus two call sites in `tests/test_kernel_transitions.py`; no
`api.py`, `contracts.py` or `desktop/plugin.js` reference exists.

Follow-up cards are created by this card's completion (§12). They are not this card's work and do
not block the construct decision: even with B-1 and B-2 closed, code, performance and artifact
still need §10's gates.

---

## 12. Scope, non-goals and verification

**Non-goals.** No check-kind widening, no answer-kind widening, no evidence-class widening, no new
RPC method, no migration, no learner upload, no retention of learner media, no sandbox, no provider
spend, no demo recording, no push, no tag, no catalog PR, no "installable" claim. No prepared
Japanese pack is used as evidence for anything in this document.

**What would change this decision.** Only the gates in §10, with their acceptance tests passing on
a real run. A desire to demo a code lesson is not evidence.

**Verify (this card).**

```
python3 -m unittest discover -s tests -t .
node --check desktop/plugin.js          # only if desktop/plugin.js was touched (it was not)
bash scripts/validate-plugin.sh        # on a clean export
git show --stat HEAD                    # changed files = docs/ASSESSMENT-BREADTH.md only
```

**Final position.** Coursebook can teach any subject now. It can *check* written, selected and
checklist answers against a closed reference, and it can measure pronunciation as practice. It
cannot run a program, hear a performance, or inspect a built object, and 0.1.0 will say so on the
plan screen rather than collect a submission it cannot grade.
