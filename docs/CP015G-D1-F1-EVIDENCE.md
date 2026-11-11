# CP-015g/D1-F1 — what the plan author writes: performed evidence, and a citation that carries it

Card: `t_285529c8`. Found while proving CP-015g/D1 (`t_754a8332`): with the plan-validation failure
repaired, the CP-015g flow (backyard-observatory goal, Short course, Game) reached validation and
authored a plan, and the independent validator refused the plan's **content**:

* "All checks are comprehension quizzes, so they cannot evidence the required hands-on setup,
  alignment, focusing, and centering performance." (`check_plan objectives 1-3`,
  `evidence_target_fit` / `alternative_coverage`).
* "It is marked sourced with three source_ids, but the supplied excerpts do not show how to
  distinguish Jupiter's moons from background stars." (`source_support`, objective 3, and the same
  for objective 4's dated two-night sketches).

Branch: `wt/cp-015g-d1-f1-authoring`, based on `wt/cp-015g-d1-validation-repair` (`5abd5c74`, i.e.
`origin/master` plus CP-015g/D1). The D1 branch is not merged, and this card's live reproduction
needs D1's repair path, so the base is stated rather than hidden. Nothing was pushed.

## What changed

`coursebook/curriculum.py`

* `performance_requirement(goal)` — a deterministic, goal-only detector of a goal the learner
  *carries out*: `set up`, `assemble`, `solder`, `calibrate`, `collimate`, `align`, `replace`,
  `repair`, `mount`, … or a weaker act (`observe`, `measure`, `record`, `sketch`, `focus`) when the
  goal also names an instrument or object (`telescope`, `eyepiece`, `board`, `meter`, `bike`,
  `sky`, `moons`, …). It deliberately does not fire on a goal that opens by asking for
  understanding, and it does not read the resolved subject domain — an undeclared domain resolves
  to the locale default (`language`), which is the wrong answer for a hands-on goal (filed
  separately as `t_2c045efc`).
* The typed block (`rule`, `check_rule`, `performance_families`) is added to the curriculum brief
  under `performance`, so **the plan author and the plan validator are told the same thing**.
* `curriculum_prompt_lines` states, for every plan: the evidence family is the performance the
  learner must demonstrate (a quiz evidences recall/comprehension/discrimination only), and
  `source_ids` is a claim link — cite only with a verbatim `source_quote`, mark `unverified` when no
  supplied excerpt carries the claim, and cite where one does.

`coursebook/generation.py`

* `PLAN_SCHEMA` / `PLAN_SCHEMA_V2` objective: optional `source_quote` (12–280 characters).
* Both plan prompts state the check-kind rule, the casual self-check form rule ("optional is about
  grading, not about form"), and the claim-link rule; on the merged tree the labels are
  `plan-prompt.v19` and `plan-prompt.v20` (this card was authored on a pre-CP-015a base, where the
  same edits read `v10` → `v12` and `v11` → `v13`; see the table in `docs/GENERATION.md` §1). The
  casual line no longer reads as "checks are optional, so a quiz will do".
* `_enforce_plan_tail` refuses, before validation and as a `_RuleViolation` (so attempt 1
  regenerates with the reason and attempt 2 parks the plan `needs_review`):
  * a plan for a performance goal with **no** `procedure`/`transfer` objective;
  * a plan whose **opening unit** has none ("a hands-on course starts with doing, not with
    terminology"); `parent` plans are exempt;
  * a `sourced` objective with no `source_quote`, with a quote shorter than 12 characters, or with a
    quote that does not occur verbatim (case- and whitespace-insensitive) in the supplied excerpt of
    a source it cites;
  * an objective that cites source ids but does not mark its support `sourced`.
* `VALIDATION_PROMPT_VERSION` → `validation-prompt.v10` on the merged tree (`v5` → `v6` on this
  card's pre-CP-015a base): the plan-validation payload now carries the curriculum `performance`
  block. The validator's instruction text is unchanged and its repair path is untouched — the
  validation contract is CP-015g/D1's, not this card's.

`docs/GENERATION.md` §1 (prompt table and prose) and a new §5b state both rules and what they do
*not* decide: a verbatim quote is not proof that it carries the claim — that stays the independent
validator's `source_support` judgment.

## Tests

`tests/test_cp015g_d1_f1_authoring.py` (21 tests):

* the detector fires for the astronomy, soldering and bicycle goals and not for a knowledge goal or
  a "the rules of polite speech" goal; a weak act needs a physical object;
* the author prompt and the validator payload both carry the typed block; the author prompt states
  both rules; a knowledge brief carries neither;
* the live plan's shape (four `comprehension` objectives, four `quiz` checks) is refused by name;
  an opening unit of terminology is refused; a performed plan passes; a knowledge goal keeps its
  quiz plan; a parent plan is not forced into a performance family;
* `sourced` without a quote is refused; the live over-citation (three ids, a claim no excerpt
  carries) is refused; a verbatim quote from a cited excerpt passes; matching ignores case and
  whitespace; quoting an uncited source is refused; citing without `sourced` is refused; the
  refusal text is the author's feedback, not a validator record;
* both objective schemas expose the bound and do not require the field.

Updated for the new contract: `tests/fixtures/generation/plan_ja.json` (its `sourced` objective now
carries a `source_quote` copied from the recorded page), `tests/test_generation.py`
(`plan_fixture(source_quote=...)`, `excerpt_quote_from(request)`), `tests/test_policy_threading.py`
(the one-off brake-pad fixture now declares a `procedure` objective), and the prompt-version
assertions in `tests/test_media_plan.py`, `tests/test_scope_copy.py`,
`tests/test_validation_shape_repair.py`.

The recorded H-40 packet was regenerated after the prompt-version change
(`PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py`, 3/3 scenarios PASS,
`--verify` FRESH). The ceiling probe's synthetic full-scope plan now declares a `procedure`
objective every fourth ordinal — its brief's goal is a physical act, and its objective *count*,
which is what the bound is about, is unchanged.

## Live reproduction

Same flow as CP-015g/D1: `hermes serve --isolated --port 44633` on a home installed from this
checkout (`scripts/install-local.sh --source <worktree>`), model route
`nous / deepseek/deepseek-v4.1-flash-1017`, contract `cb.rpc` v26, driven over
`POST /api/plugins/coursebook/rpc` exactly as the Desktop half does (`course.create` →
`enrollment.create` → `jobs.create kind=plan` → `jobs.get`). No plan text, fixture or authored
content is supplied. Raw records: `docs/cp015g-d1-f1/run-f1-live-r2.json` and
`docs/cp015g-d1/run-f1-live.json`.

### Run at `plan-prompt.v12` (card base; merged-tree label is `v19`) — `job_c4e86e5c9ee341518ae3d6a68150f770`

| fact | value |
| --- | --- |
| job | **completed** in 216 s; 2 `plan.generate` + 4 `plan.validate` (2 passes × 2 attempts) |
| objectives | 4: `procedure`, `comprehension`, `procedure`, `transfer` (run before: all `comprehension`) |
| check plan | `verification`, `quiz`, `verification`, `observation` (run before: all `quiz`) |
| claims | every objective `unverified`, no `source_ids` |
| verdict | **reject** on `source_support` only — `evidence_target_fit` and `alternative_coverage` no longer fail |

That run is the first ask, proven on the live path: the author now writes objectives whose evidence
target is the performance and checks that are a performance checklist and an observation log. It
also shows the claim-link rule is not a licence to abandon citation: the author dropped *all*
citations, and the validator answered that the plan's claims were then unsupported.

### Run at `plan-prompt.v13` (card base; merged-tree label is `v20`) — `job_c3a5f5ca512a4d518e7b06c924e53eed`

| fact | value |
| --- | --- |
| job | **completed** in 294 s; 6 calls |
| objectives | 4: `comprehension` (sourced + quote), `procedure`, `transfer` (sourced + quote), `comprehension` |
| check plan | `quiz`, `verification`, `observation`, `quiz` |
| citations | two objectives carry a `source_quote` copied verbatim from the CESAR student guide excerpt; the two the excerpts do not carry are `unverified` with no ids |
| verdict | **reject**, per item: "objective:2: The setup/aim procedure is unsourced and must not be presented to a learner as verified content." / "objective:4: The orbital-explanation objective is unsourced and must not be presented to a learner as verified content." |

Both asks in the card are answered on this run: the performance families and check kinds are the
performed ones, and no objective cites a source whose excerpt does not carry its claim — the two
objectives the supplied excerpts do not support say `unverified` instead of borrowing three source
ids.

## Limits stated, not papered over

* **The validator still refuses the plan**, on `source_support`, for the two objectives marked
  `unverified`. That is no longer an over-citation; it is the validator treating an honestly
  unverified claim as unapprovable content. Whether that is the intended reading of the
  `source_support` criterion is a validation-contract question, and this card is barred from
  changing the validation contract — filed as `t_65054c74` for the contract owner, not fixed here.
* **Three of the eight fetched excerpts are page chrome.** Every excerpt in the ledger is exactly
  600 characters, and for three sources those 600 characters are navigation: the ESA article opens
  with `[Skip to content]`, the NASA Science article with `Search ## Suggested Searches - [Artemis]`,
  and the EarthSky article with its logo image. The five PDF/prose sources carry real text, and the
  two objectives that ended up `unverified` are exactly the ones the chrome-only sources were
  fetched for. That is a research/extraction defect, filed separately as `t_41f23b3e`; it is a large
  part of why two objectives could not be sourced.
* **The validator is the author model** (`independence: same_model`): every plan here is
  `needs_review`/`model_assessed`, never "independently validated". No validator route was
  configured in the isolated home.
* **The deterministic citation rule did not fire in either live run** — both authored plans passed
  the rule set. Its evidence is the 20 fixture tests, not a live refusal; the live runs show the
  authoring behaviour the rule exists to protect.
* **Cost is unknown, not zero.** The route reports no per-call cost (`unknown_cost_calls: 6`,
  `cost_usd: null`); the job's own estimate was reported by the preflight, not by the provider.
