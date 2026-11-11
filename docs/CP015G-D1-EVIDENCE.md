# CP-015g/D1 — plan validation: repair, records, output bound

Card: `t_754a8332`. Defect found by CP-015g (`t_3fd13051`): the installed product could not
produce a plan, because a validator answer that was not JSON failed the job with
`repair_attempted: false`, wrote no `gen_validation_records` row, and discarded a ~30k-output-token
authored plan.

Branch: `wt/cp-015g-d1-validation-repair`, based on `origin/master` (`58ce4d85`). The CP-015d/CP-015e
branches are not merged into master, so this fix is made on master — the tree the operator's install
runs — rather than waiting on that merge.

## What changed

`coursebook/generation.py`

* `VALIDATION_OUTPUT_TOKENS` 4 000 → 12 000, with the two measurements below recorded beside it.
* `_validation_answer_with_repair`: every validator answer is parsed **inside** the stage. An answer
  that carries no verdict (prose, cut-off JSON, an empty body, a schema violation) is re-asked
  **once** on the same pass, schema, purpose and input bytes, under the `.validate-repair` prompt
  label, inheriting what is left of the pass deadline. A second unreadable answer raises
  `ModelOutputInvalid` with `repair_attempted: true` and a named `parse_outcome`. A *verdict*
  violation (ungrounded `reject`) is not re-asked.
* `_answer_was_cut`: a recorded completion count at the cap is named a **truncation**, not "invalid
  JSON"; the provider reports no `finish_reason` through this seam.
* `_record_validation_attempt`: one `gen_validation_records` row per unreadable attempt — the
  first-time answer, its repair, and each pass of a multi-pass review — with
  `validator_prompt_version`, `validator_model`, `validator_provider`, `parse_outcome`,
  `attempt_index`, `pass_index`, `repair_attempted` and a `failure_json` block. `verdict` is
  `invalid`, `outcome` is `unreadable`: an unreadable answer is not a rejection.
* `gen_validation_records` gains `pass_index`, `pass_total`, `attempt_index`, `parse_outcome`,
  `repair_attempted`, `failure_json`; the unique key includes `attempt_index` and `pass_index`. A
  database created before this change is rebuilt in place with every row copied across
  (`pass_index = -1` marks a legacy merged row).

`docs/GENERATION.md` §7.1 and the H-192c bound paragraph state the new contract.

## Tests

`tests/test_cp015g_d1_validation_repair.py` (8 tests): non-JSON answer repaired once and the plan
validates; cut answer recorded as a truncation and repaired; both attempts unreadable ⇒ failure only
after the repair, `repair_attempted: true` in `details`, one row per attempt with its own prompt
version; every unreadable pass gets its own row; verdict violation not re-asked; cap sized above the
measured answers; legacy table rebuilt without losing a row.

Updated for the new contract: `tests/test_validation_shape_repair.py` (a failed attempt now leaves
one `unreadable` row), `tests/test_validation_reject_basis.py` (a verdict violation leaves one row
per pass, `repair_attempted: 0`).

## Live reproduction

Backend: `hermes serve --isolated --port 44319` on a fresh home installed from this checkout
(`scripts/install-local.sh`), model route `nous / deepseek/deepseek-v4.1-flash-1017`, contract
`cb.rpc` v26. Driven over the mounted `POST /api/plugins/coursebook/rpc` route exactly as the
Desktop half does: `course.create` (goal: "Set up a small backyard telescope and find and observe the
moons of Jupiter on a clear night", Short course, Game presentation, recipe casual, depth working) →
`enrollment.create` → `jobs.create` kind `plan` → `jobs.get` polling. No plan text, fixture or
authored content was supplied; the product's own generator and validator did the work.

### Run 1 — cap 8 000 (repair exercised)

| fact | value |
| --- | --- |
| job | `job_6d04ba3e21b3460c90e2a62445be8768` — **completed** in 213 s |
| `coursebook.plan.generate` | 9 643 and 10 741 output tokens |
| `coursebook.plan.validate` | 3 923, **8 000 (at cap, cut mid-JSON, 59.9 s)**, 4 247, 1 815 |
| repair | `validation-prompt.v5.validate-repair`, 3 587 tokens, 25 s — parsed |
| record | `parse_outcome: truncated`, `output_tokens: 8000`, `max_tokens: 8000`, pass 1 of 2, `repair_attempted: false` on the failed answer |
| outcome | validator gave a real verdict after the repair; plan parked `needs_review` with itemised reasons |

Without `_validation_answer_with_repair` this run fails the job exactly as CP-015g measured: the
8 000-token answer was unparseable and non-retryable.

### Run 2 — cap 12 000 (no call at the cap)

| fact | value |
| --- | --- |
| job | `job_d54065dcf81b4cc6affe55b32107fa6d` — **completed** in 99 s |
| objective laid down | 4 objectives, 2 units (`generation_state: needs_review`) |
| `coursebook.plan.generate` | 8 037 and 10 752 output tokens |
| `coursebook.plan.validate` | 2 193 and 3 658 — **no call at the 12 000 cap** |
| records | one merged row, `parse_outcome: parsed`, `repair_attempted: 0`, `validator_model` `deepseek/deepseek-v4.1-flash-1017`, `validator_prompt_version` `validation-prompt.v5` |
| verdict | `reject` on `source_support` for objectives 3 and 4 (the researched excerpts do not support them) — a **named, non-truncation** outcome, not a parse failure |

The plan is not approvable on its content, and that is a separate authoring/ledger verdict: the
validator read the plan, judged it, and named why, instead of the pipeline failing on its own
model's output. The failure path this card removes (truncated/unparseable answer → discarded plan →
no record) did not occur in run 2.

Raw run record and the scripts that produced it are in `docs/cp015g-d1/`
(`run-live-12000.json`, `repro_cp015g_d1.py`, `read_cp015g_d1.py`). The failed-host first attempt
(`job_8400bc93bf6a4ac18eff2cca6acff28c`) is not included: it failed inside the host
(`UnscopedSecretError` resolving `GOOGLE_API_KEY` for the auxiliary task) before the pipeline ran,
and was fixed by pointing the isolated home's `model` route at `nous`.

## Limits stated, not papered over

* The validator still runs on the author model in these runs (`independence: same_model`), so the
  plan is `model_assessed`/`needs_review`, never "independently validated". No validator model was
  configured in the isolated home.
* Run 1 shows the route can still spend a whole answer budget on one pass; the repair keeps the
  authored plan, and the cap that made it rare is measured, not assumed.
