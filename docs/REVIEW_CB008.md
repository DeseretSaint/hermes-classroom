# CB-008 review packet — learning kernel integration

Branch `wt/cb-008-cinder`, base `df224b8` plus the CB-002 kernel merge (`afa36cc`). Every claim
below is from a command that ran on this branch; the JSON files next to this packet are raw output,
not hand-written.

## 1. What landed

The learning loop now runs behind one authoritative command path: the chat hook is an adapter over
`attempt.submit`, never a second implementation.

| Module | What it owns |
|---|---|
| `coursebook/turn.py` (new) | inbound classification, pre-turn gate, continuation prompt, binding reconcile, post-turn snapshot with a revision/nonce fence |
| `coursebook/review.py` (new) | review queue: due/overdue/cap/snooze/stretch/drop, derived from committed evidence, plus `refresh_due()` which marks the contracted `objectives.state='review_due'` |
| `coursebook/evidence.py` (new) | L1 raw events, L2 objective evidence linked to L1, L3 revisable recommendations, dispute history |
| `coursebook/hooks.py` | the three Hermes hooks are now real: gate, observer, provenance |
| `coursebook/domain.py` | hint/answer consumption (one hint contaminates exactly one answer), `delayed_evidence` on a cold pass of a due review, review tick in `library.list`, `binding.get` duplication removed |
| `tests/test_turn.py`, `tests/test_review_evidence.py` (new) | 46 new cases against real SQLite |

### Decisions worth recording

1. **`binding.get` belongs to `coursebook/api.py`.** The kernel had registered a second handler that
   matched `runtime_session_id` as well and accepted both identifiers. That contradicts `AUDIT.md`
   R1 (a runtime id is a live-gateway id, never identity) and silently overrode Sable's handler.
   The duplicate is gone; the kernel reads its own binding row internally when it needs the v2
   columns (`lesson_run_id`, `objective_id`).
2. **A hint is consumed by the answer it preceded.** `evidence.attempt_id` stays `NULL` on a
   `hint_request`/`answer_shown` event until the next committed attempt links it. Without this, one
   hint marked every later answer on that objective as hinted forever — a false negative for the
   learner and a false "contaminated" claim in the evidence view.
3. **A cold pass on a `review_due` objective is `delayed_evidence`,** and its layer-2 row is
   `delayed_retrieval`. That is what separates same-session success from delayed retrieval
   (`AUDIT.md` R10) and what advances the review ladder.
4. **The review queue is derived, not stored.** `cb.db` v2 has no review-schedule table; a second
   copy of "what is due" would be a competing authority (`AUDIT.md` R5). The clock starts at the
   last cold L2 pass; snooze/stretch/drop/resume are layer-1 events with
   `evidence_class='self_reported'`, i.e. learner scheduling statements, never mastery evidence.
   Intervals are a declared heuristic per evidence target, not an attainment prediction (`R9`).
5. **The gate fails closed on every path.** Refused dispatch (stale revision, stale check,
   unaudited check, detached binding), a grader exception, and a grade that lands after the hook
   budget all return `{"action": "block"}` with a local message. Only a committed verdict returns
   context, and the context never contains the reference answer.
6. **Late callbacks are discarded, not reconciled.** The post-turn observer carries the pre-turn
   nonce and revision; if the enrollment revision moved (another window, another turn) or the
   process restarted (in-memory nonce gone), nothing is written.

## 2. Acceptance matrix

| Acceptance | Test | Result |
|---|---|---|
| wrong/irrelevant never pass | `test_turn.GateTest.test_wrong_answer_never_passes_and_offers_a_retry` | verdict `not_yet`, objective `needs_review`, no transition |
| clarification never consumes retry | `test_turn.GateTest.test_clarification_creates_no_attempt_and_consumes_no_retry` | no attempt row, revision unchanged |
| hint class correct | `test_turn.GateTest.test_hint_marks_the_next_answer_hinted`, `test_a_hint_contaminates_only_the_answer_it_preceded` | `hinted`, no layer-2 evidence, next cold item independent again |
| answer/override class correct | `test_turn.GateTest.test_shown_answer_is_recorded_as_answer_shown`, `test_skip_grants_access_but_is_labelled_an_override` | `answer_shown`; `override` with `verdict=not_yet` |
| grading outage no pass | `test_turn.GateTest.test_grading_outage_is_needs_retry_and_advances_nothing` | `needs_retry`, no transition, objective state unchanged |
| unaudited check never graded | `test_turn.GateTest.test_unaudited_check_is_refused_never_graded` | blocked, no attempt |
| two windows one transition | `test_turn.GateTest.test_two_windows_produce_exactly_one_transition` | two threads, one transitions row, one attempt |
| transition commits before teaching | `test_turn.GateTest.test_correct_answer_commits_a_transition_before_teaching_context` | transitions row present when the hook returns |
| restart resumes exact state | `test_turn.ObserverAndResumeTest.test_restart_drops_the_pending_turn_and_resume_uses_the_stored_binding` + restart run (§3) | `run_state=resumed`, same `lesson_run_id`, attempts preserved |
| cwd change / compaction explicit | `test_compaction_tip_is_adopted_and_a_cwd_change_detaches` | tip adopted; changed cwd → `detached`, then ungoverned |
| review due/overdue/cap | `test_review_evidence.ReviewQueueTest` (first four) | due count, overdue flag, cap bounds items but not totals |
| snooze/stretch/drop | `test_snooze_restarts_the_interval_from_now`, `test_stretch_advances_the_ladder_step`, `test_drop_removes_the_item_and_resume_puts_it_back` | as named |
| L1/L2/L3 + disputes | `test_review_evidence.EvidenceLayerTest` | reference answer never in L1; L2 only for cold passes; L3 `is_persona: false`; disputes first-class |

## 3. State trace and restart run (real output)

`docs/REVIEW_CB008-trace.json` — produced by running a lesson through the real commands and the
real gate in a throwaway `HERMES_HOME`:

* wrong answer → 1 attempt, verdict `not_yet`
* clarification → still 1 attempt (no retry consumed)
* hint → 1 attempt, evidence=2 (the hint event)
* correct answer after hint → verdict `pass`, `evidence_class=hinted`, context says the pass does
  not count as independent evidence
* cold answer on a fresh check → independent evidence
* review queue after back-dating the L2 row: `total_due=1`, `overdue_days=7`,
  `interval_days=3`, ladder `[3,7,16,35]`; `library.list` next step `resolve_review_due`
* snooze → `total_due=0`

`docs/REVIEW_CB008-restart.json` — a **separate process** against the same database:

```
binding_found_by_stored_id: true   binding_status: active
lesson_begin.run_state: resumed    resume.available: true
attempts_after_restart: 3          transitions_after_restart: 6
reconcile: active, changed true (compaction tip adopted)
```

The trace and restart artefacts were generated with the CB-008 code at the commit that carries this
packet; their digests at generation time were:

```
a45f3131ca9b9326235ee2cc04d0231e49b8bf06ac04a98d0f35eeb44efb4dbd  docs/REVIEW_CB008-trace.json
607cff40bd91f45b8d8e3c944ed44315dcbceb2ef423a6da07e70d8ef8768c0c  docs/REVIEW_CB008-restart.json
```

## 4. Gates (run on this branch)

```
python3 -m unittest discover -s tests -t .   -> Ran 375 tests ... OK
node --check desktop/plugin.js               -> NODE_OK
hermes plugins validate .                    -> Validation passed (16/16)
hermes plugins doctor .                      -> OK: runtime discovery, manifest parsing, import,
                                                and registration passed; 1 tool, 3 hooks
bash scripts/validate.sh                     -> Validation passed
   mounted backend trace: 9/9 expectations passed, 31/34 contract methods registered
```

## 5. Cross-owner edits (recorded because the file has another owner)

* `scripts/probe-backend.py` (Sable): one line. The "method not in the mounted contract is
  refused" step used `library.list`, which the kernel now implements, so the probe asserted the
  opposite of the truth. It now uses `pack.preview` (still unimplemented, still a contract method).
* `tests/test_kernel_commands.py` (kernel-owned by Cinder): `BindingTest` updated to the
  stored-id-only contract and a plan-hash-covers-criteria case added.
* `coursebook/hooks.py` is the shared file per `docs/WORK_PACKAGES.md` §3; this branch owns the
  gate body and does not touch Sable's binding validation.

## 6. Contract gaps found (follow-up card `t_37b9f9f8`, owner Atlas)

The backend semantics for three surfaces exist and are tested, but `cb.rpc` v2 has no method for
them, so the Desktop half cannot call them:

1. `review.queue` / `review.action` (`snooze|stretch|drop|resume`) — Vellum's review queue has no
   command path today; `library.list` can only surface the count and `resolve_review_due`.
2. `evidence.inspect` (L1/L2/L3 + disputes) — the Evidence tab has no read method.
3. `disputes` as queryable records — currently inside `attempts.grading_provenance_json`;
   `quiz.history` exposes them per attempt, a course-wide history does not.

No table was added and no contract file was edited: `cb.db` still matches the frozen 19-table
inventory and `cb.rpc` still matches v2. The follow-up card carries the proposed shapes.

## 7. Known limits (honest)

* Review intervals are a product heuristic (per evidence target), not a validated forgetting curve.
  They are exposed as `ladder_days` so the UI can show them; they are not an attainment estimate.
* `review.action` and `evidence.inspect` have no RPC method yet (above). They are exercised by
  unit tests and by the trace script, not by the Desktop.
* The open-response grader still fails closed to `needs_retry` (Sentinel probe #4 owns the aux
  lane). The gate's outage path is therefore the normal path for open responses today, and it is
  tested as such.
* `post_tool_call` records provenance as a usage event (`provider="tool:<name>"`, duration when
  known, tokens omitted rather than fabricated). It is correlation, not a source ledger; the
  source ledger is CB-012.
* The classification patterns are English-first and bounded. A learner writing in Japanese who
  asks a question without a `?` may be classified as an answer; grading then returns a verdict and
  never a pass, so the failure mode is a graded attempt, not a false pass. A native-language
  classifier belongs to the grader/localisation work, not this packet.
