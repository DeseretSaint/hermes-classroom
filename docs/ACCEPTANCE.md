# ACCEPTANCE: adversarial matrix

Owner: Sentinel. Sources: `UX_SPEC.md` §16 proof suite, `PREBUILD_SPEC.md` §16 gates,
`AUDIT.md` acceptance expansion. Every PASS or FAIL below was derived from a command run on
candidate `e5b9686` (plugin 0.1.0, cb.rpc v6), not from an owner's report; rows still pending say
why no command can run yet.

Status vocabulary:

- verified: a command run on this commit records PASS, and the row names the test or probe
  plus its evidence path. A row whose user-visible half cannot run is never verified.
- seam: the backend/kernel half records PASS at the `api.dispatch`/`cb.rpc` seam on this
  commit, but the user-visible half cannot run because the Desktop route does not mount
  (CB-QA-09). A seam row is progress, not a passed acceptance row, and never counts toward the
  demo gate.
- blocked: the runtime topology cannot exercise it here (reason given).
- pending: no executable probe exists yet for this row on this commit (reason given).
- failing: the named command currently fails (defect id in `DEFECTS.md`).

Evidence lives in `probes/raw/`; probe scripts are `probes/p*.sh`. Rule: no claim is accepted from
a self-report: not from a bot, an owner, or a model answer quoted by a probe. Owners: Atlas
(contracts, identity, runtime topology), Cinder (learning kernel, grader, DB, jobs), Sable
(Desktop route/panes/media renderer), Sentinel (verification).

> **H-102 reconciliation (2026-11-07, `master` `48be4af` + the H-102 test edit).** Every
> `attack_state.py` result below is a record of its own commit (`e5b9686`). The hook has since
> gained the bundled-skill instruction (`coursebook/lesson_skills.py`), which **changes the
> expected shape of S08 and S09 and adds S17**:
>
> - **S08** no longer forbids the word `reference` (the tutor instruction legitimately says
>   "Never print the reference answer"). It reads the check's `reference_json` and asserts no
>   **value** from it and no secret key name (`answer_key`, `reference_json`, `pass_rule`,
>   `tolerance`, `"value":`) appears in the pre-turn teaching context. In-scenario canaries prove
>   the detector fires on the real value and on an `answer_key`.
> - **S09** no longer requires `hook is None`. A clarification now returns a skill instruction,
>   which is allowed; the scenario asserts attempts stay `0`, the transition delta is `0`, the
>   enrollment revision is unchanged, and the context is not a grading continuation (no
>   `Coursebook result:`, `attempt_id`, `evidence_class`). No attempt/revision assertion was
>   weakened.
> - **S17** (new): a bound lesson is told to load `skill_view(name="coursebook:lesson-tutoring")`
>   with its one store path; an unrelated chat in the same profile gets no hook return and no
>   binding row.
>
> Current command, run for H-102:
>
> ```
> $ python3 tests/adversarial/attack_state.py
> RESULT scenario=S08 verdict=PASS … detail=context_returned=True teaching_verdict=True reference_value_leaks=[] canary_value=True canary_key=True
> RESULT scenario=S09 verdict=PASS … detail=attempts=0 transitions_delta=0 transitions_total=2 revision=2 unchanged=True skill_instruction=True attempt_markers=[] blocked=False
> RESULT scenario=S17 verdict=PASS … detail=tutor_namespaced=True store_named=True unrelated_context=None unrelated_rows=True store_untouched=True
> RESULT scenario=S13 verdict=BLOCKED …
> SUMMARY total=23 fail=0 pass=23
> ```
>
> `S13` remains `BLOCKED` (aux lane disabled, CB-QA-11). Evidence:
> `tests/adversarial/evidence/attack-state.json`. The older `22`-scenario / `21 PASS, 1 FAIL`
> numbers elsewhere in this file are historical records of their own commits, not the current
> matrix.

## Evidence run on this candidate (2026-11-06)

All commands were run from this tree at `e5b9686`:

| Command | Result |
|---|---|
| `bash scripts/test.sh` | `Ran 636 tests ... OK`; `desktop/plugin.js: syntax OK`; `All checks passed.`, exit 0 |
| `python3 tests/adversarial/attack_state.py` | 21 PASS, 1 FAIL (S07, CB-QA-10), 1 BLOCKED (S13, aux lane disabled) — historical `e5b9686`; current matrix is 23 scenarios, `fail=0`, S13 `BLOCKED` (H-102 note above) |
| `python3 tests/adversarial/attack_packs.py` | 21/21 PASS, every rejection leaves zero residue |
| `bash probes/p1_ids.sh` | PASS; compression BLOCKED (CB-QA-06) |
| `bash probes/p2_injection.sh` | FAIL: injected text persisted in `api_content`; `sentinel_in_earlier_history: true` on the resumed turn (CB-QA-01) |
| `bash probes/p3_context.sh` | PASS isolated/outside/ignore-rules; in-repo course admits repo policy (CB-QA-05) |
| `bash probes/p7_authority.sh` | PASS: submit idempotent with no hook; hook fails open; a timed-out hook stops firing until reload |
| `git diff --name-only f4a42f3 e5b9686 -- desktop/` | empty: `desktop/plugin.js` is byte-identical to the build the live CB-QA-09 failure was reproduced on |

Because the Desktop module is unchanged between `f4a42f3` and this commit, no UI row can be
re-verified here: the `/coursebook` route still renders the session home (CB-QA-09, reproduced live
against the installed candidate in `docs/REVIEW_CB014.md`). Rows below say `seam` when the backend
half passed and the UI half is blocked by that defect.

## A. Runtime assumptions (probes)

| Item | Probe / test | Status | Owner | Evidence (run on this commit) |
|---|---|---|---|---|
| Runtime/stored ids across create/first turn/resume/tool | p1 | verified | Cinder | `raw/p1/assert.json` (re-run): session id stable across resume, turn id per turn, tool sees session/task ids |
| Ids across compression | p1 | blocked (CB-QA-06) | Atlas | `raw/p1/assert.json` (re-run): compressor no-op/refusal on the transcript, `post_compaction` never fired |
| `pre_llm_call` injection replay semantics | p2 | failing (CB-QA-01) | Atlas/Cinder | `raw/p2/assert_storage.json` and `events_turn2.jsonl` (re-run): `injected_text_persisted_in_api_content: true`, `sentinel_in_earlier_history: true` |
| Isolated cwd policy discovery | p3 | verified | Cinder | `raw/p3/assert.json` (re-run): isolated, outside and ignore-rules load only the intended policy |
| Course inside a git repo | p3 | failing constraint (CB-QA-05) | Cinder | `raw/p3/assert.json` (re-run): `repo_course` markers include both `CB_CTX_COURSE` and `CB_CTX_REPO` |
| Remote Desktop/backend topology | p3/p5 | blocked (no remote backend) | Atlas | - |
| Aux grading latency / invalid JSON / timeout / outage | p4 + S10-S12 | verified (fail-closed), caveats CB-QA-03/04 | Cinder | S10 invalid JSON → `needs_retry`, no transition; S11 hung grader → `needs_retry` in 8.04 s, no transition; S12 exception → fail closed. The p4 latency/outage caveats are from `raw/p4/assert.json` and were not re-run today |
| `jsonschema` missing must fail closed | p4 seam | verified (with package) / hazard recorded | Cinder | `raw/p4/p4_runtime_seam.json` |
| Hook lifecycle provisions no storage | T1-T7 | verified | Cinder/Sable | `tests/test_hook_provisioning.py` (10 tests) and `tests/test_hook_usage_telemetry.py` (10 tests) in the 636-test run: unbound hooks and post callbacks create no DB file; `health.get` provisions; a broken store stays broken rather than half-provisioned |
| Tool → artifact → `MEDIA:` → renderer | p5 | blocked (render) | Sable | `raw/p5/p5_media_seam.json` proves the artifact and text fallback data; no renderer exists to exercise |
| Cron explicit vs omitted delivery | p6 | verified (DST untested) | Cinder/Atlas | `raw/p6/jobs.json` (recorded on `b9da9f3`, not re-run today) |
| `submit_attempt` authoritative without hook | p7 | verified | Cinder | `raw/p7/assert.json` (re-run): first submit, replay, conflict and stale all correct while the hook is disabled |
| Hook exception/timeout fail-open | p7 | verified (CB-QA-02) | Atlas/Cinder | `raw/p7/p7_hook_bypass.json` (re-run): raise and timeout turns proceed; `pre_llm_after_timeout: false` until plugin reload, the documented silent gate loss |

## B. UX proof suite (`UX_SPEC.md` §16)

Every row is a user-visible proof. None can be promoted past `seam` while CB-QA-09 is open.
Verdicts are the command result on `e5b9686`; the verdict cell names what could not run.

| # | Proof | Status | Verdict on this commit (command → result) | Owner |
|---|---|---|---|---|
| 1 | Fresh profile → sidebar → bundled preview → import → lesson | seam | P20 PASS (reimport offers resume and fresh, same pack); S01 fixture creates course → plan → enrollment → `lesson.begin`; sidebar and bundled preview are Desktop surfaces, not runnable | Sable/Cinder |
| 2 | Backend disabled → enable → brief preserved | seam | `tests/test_job_service.py::test_pump_passes_the_persisted_brief_not_a_live_form` PASS: the brief is durable, not a live form; disable/enable is a Desktop action | Sable |
| 3 | New goal → cancel generation → reattach → approve edited plan | seam | J03 PASS (cancel queued spends nothing), J05 PASS (restart → `interrupted_requires_retry` with checkpoint), `test_edit_is_draft_only_and_fenced_on_hash_then_revision` PASS; reattach is UI | Cinder |
| 4 | Chat answer and pane answer race → one attempt | seam | S02 PASS: two concurrent submits at one revision, one ok, one `STALE_REVISION`, exactly 1 attempt and 1 transition; the chat/pane race is UI | Cinder |
| 5 | Wrong answer → alternate representation → clarification not a retry | seam | S09 PASS (a clarification writes no attempt and no transition, leaves the revision unchanged, and its turn carries only the tutor skill instruction — not a grading continuation); S05 PASS (a shown answer produces `answer_shown` evidence, not independence); `test_the_three_v5_methods_are_implemented` PASS; the representation is a Desktop render | Cinder |
| 6 | Grader timeout → needs_retry → override recorded | seam | S11 PASS (hung grader fails closed to `needs_retry` in 8.04 s with no transition); S10 PASS (invalid JSON fails closed); S06 PASS (override grants access, never a pass); the retry banner is UI | Cinder |
| 7 | Hide/reopen/split pane during attempt → no lost/duplicate submit | seam | S01 PASS (same idempotency key replays one attempt); S02 PASS (one commit under concurrency); pane hide/split is UI | Sable/Cinder |
| 8 | Restart at every attempt state → same objective/pending | pending | S14 PASS for the open-check state only (a separate process resumes the exact revision and refuses the replay); the other attempt states and compression are blocked (CB-QA-06) | Cinder/Atlas |
| 9 | Parent edit after approval → reapproval | seam | `test_an_approved_plan_cannot_be_edited` PASS; `test_a_content_change_supersedes_export_with_changes_need_review` PASS; `test_blueprint_refusal_before_approval_and_no_path_leaks` PASS, export waits on final approval | Cinder |
| 10 | Invalid/malicious pack → precise error, no residue, no network render | seam | P01-P16 PASS (the 21-scenario pack suite passed 21/21): traversal, absolute path, symlink, duplicate/case collision, bomb, lying sizes, active SVG/HTML, remote-image refusal (P11), MIME mismatch, answer-key copy, prompt injection; P16 residue `{}`; the error text is UI | Cinder/Lattice |
| 11 | Offline lesson → cached content; research explains pause | pending | `test_unavailable_voice_reuses_cached_original_without_new_spend` and `test_generation_failure_completes_with_text_fallback` PASS, so the artifact cache/fallback exists; offline lesson rendering and the research-pause explanation were never probed (CB-QA-09) | Cinder/Sable |
| 12 | Source stale → impact banner; evidence retained | seam | `test_changed_source_marks_dependent_check_stale` PASS; `test_stale_check_refuses_grading_and_creates_no_attempt` PASS, stale grading writes nothing and prior attempts stay; the banner is UI | Cinder |
| 13 | Reimport same pack → resume vs fresh | seam | P20 PASS: `resumed_same=True`, `fresh_new=True`, `same_pack=True` | Cinder/Lattice |
| 14 | Course/chat/pack deletion distinct & recoverable | seam | P21 PASS (pack delete keeps the enrollment and blocks reimport of the frozen pack); `test_delete_previews_scope_and_refuses_a_stale_hash` PASS; `test_save_list_and_delete` PASS (notebook). Chat deletion is a host surface and was not probed | Cinder |
| 15 | Keyboard-only, text-only, reduced motion, 200 %, narrow | blocked (CB-QA-09) | no DOM: the route renders the session home, so there is nothing to audit with a keyboard or an accessibility tree | Sable |
| 16 | 50+ objectives / long JP text / many sources stay usable | blocked (CB-QA-09) | `test_the_objective_list_is_bounded_and_reports_the_true_total` PASS, the list is bounded and reports the true total; layout and readability need the route | Sable |
| 17 | Save moment → tag/search → exact section → new run | seam | `test_save_list_and_delete` PASS; `test_edit_is_fenced_on_the_entry_revision` and `test_provenance_fields_cannot_be_edited` PASS; `test_fresh_mode_abandons_the_previous_run` PASS; `test_binding_reports_the_section_it_is_bound_to` PASS | Cinder/Sable |
| 18 | Past quiz read-only → new version keeps both | pending | S04 PASS (a second answer to a closed check writes no attempt and no transition); `test_criteria_observations_never_contain_the_reference` PASS (`quiz.history` returns the attempt without the reference); coexistence of a new check version with the old attempt is not separately probed | Cinder |
| 19 | Jump early/late sections → context-bound runs | seam | `test_begin_creates_then_resumes_by_run_not_recency` PASS; `test_binding_reports_the_section_it_is_bound_to` PASS; S16 PASS (a detached binding refuses submission instead of grading into the void); jumping is UI | Cinder/Sable |

## C. PREBUILD §16 gates (condensed)

| Gate | Status | Probe / owner |
|---|---|---|
| Duplicate submits/two windows commit once | verified: S01/S02 commit one attempt and one transition | p7 → Cinder |
| Same key+payload returns original; mismatch/stale conflict | verified: S01 replay, S03 `STALE_REVISION`, J01 one job per key | p7 → Cinder |
| Late callback cannot change newer revision | verified: S15 writes zero segments | Cinder |
| Restart after every state restores state | pending: S14 covers the open-check state; compression blocked (CB-QA-06) | Cinder/Atlas |
| Rename/branch/edit/delete/compress/repeat explicit | pending: delete/replan/notebook paths tested (P21, `test_replan_supersedes_the_approved_plan_and_pauses_checks`); compression blocked; branch/rename have no probe | Cinder |
| Unrelated sessions get no Coursebook context | verified: T1 unbound `pre_llm_call` returns none and creates nothing; S16 detached binding refuses | Cinder |
| Wrong/irrelevant answers do not pass | verified for closed checks: `test_unreadable_answer_is_not_yet_not_a_pass`, `test_verdict_mapping_never_passes_without_an_outcome`, S05/S06; open-response grading with the aux lane enabled is the recorded risk CB-QA-11 (S13 BLOCKED) | Cinder |
| Flawed question/key/rubric fails closed | verified: `test_aux_invalid_output_is_refused`, `test_aux_pass_with_unmet_criteria_is_refused`, `test_aux_exception_is_refused`, `test_aux_deadline_is_bounded` | p4 → Cinder |
| Answer-shown/hint/override evidence classes | verified: S05 `answer_shown`, S06 `override` is never a pass, zero independent rows | Cinder |
| Physical completion self-reported | pending: no probe for a self-reported physical objective | Cinder |
| Pack/web prompt injection cannot change policy | verified: P15 (injected prose imports as data, no spec/plan/AGENTS row changes); S08 (the pre-turn teaching context carries no reference value, `answer_key` or rubric key — S08 canaries prove the detector fires) | Cinder/Atlas |
| Traversal/bombs/links/SVG/remote images/MIME reject | verified: P01-P14 all `PACK_REJECTED` with no residue; P11 refuses remote image fetches | Cinder/Lattice |
| Offline cached content works; staleness visible | pending: cache/fallback tested, offline lesson UI not probed (row 11) | Cinder/Sable |
| Rights/ND enforced; exports leak nothing | pending: P17 PASS (the export carries no learner history, notebook or attempt text); ND/rights enforcement has no separate probe | Cinder/Lattice |
| Jobs cancel/recover without duplicate artifacts | verified: J01-J06 (cancel spends nothing, restart keeps the checkpoint, late completion records once); P18 PASS (repeat export reuses one artifact) | Cinder |
| Keyboard/text/reduced-motion/no-media complete | blocked (CB-QA-09): no DOM; p5 proves text fallback data exists | Sable |
| Local/remote explicit, not silently wrong | verified local; remote blocked | p3/p5 |
| Fresh install/enable/restart/revoke/uninstall | pending: install/uninstall observed on throwaway homes (`docs/INSTALL.md`); hot reload can drop `pre_llm_call` (CB-QA-07), so the restart/revoke path is not acceptance-clean | Atlas |
| Demo below 90 s, no fake live research | pending: no demo recorded; gate 7 cannot start until CB-QA-09 closes | Atlas/Sable |
| Catalog PR pinned + form on time | pending: the catalog validator passes, the pin still points at the skeleton commit (`docs/SUBMISSION.md` gate 11) | Atlas |

## D. Gate conditions for sign-off

1. No acceptance item may be marked verified or seam from a self-report; each row needs a command
   result plus an artifact path or a test name. A model answer quoted by a probe is a self-report.
2. CB-QA-01…03 must be closed or explicitly accepted by Atlas before the grader ships.
3. Compression/restart (CB-QA-06) must be re-run on a restarted gateway before sign-off.
4. Remote topology stays `TOPOLOGY_UNSUPPORTED` until p3/p5 remote halves pass.
5. No UX row may move from seam to verified until CB-QA-09 closes and that row is re-run through
   the mounted route on the release commit. Gate 7 (demo shots) counts only verified rows.
6. The status vocabulary is enforced by `tests/test_acceptance_evidence.py`; adding a status
   requires updating that test in the same commit and re-running the suite.
