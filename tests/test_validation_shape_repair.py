"""H-191 §5 — a validator answer's shape violation is repaired once, then typed.

Measured on the live tree (see ``audit/adversarial/h191-validate-stall/STATUS.md`` §5 of
``t_9a2ab1a0``): one ``coursebook.plan.validate`` call returned in 54.2 s and the host's
JSON-schema gate threw the whole document away because one ``item`` label was 81 characters
against ``maxLength: 80`` — a limit the prompt never stated. The pipeline mapped that
``ValueError`` to ``ProviderFailure``, and the job reported retryable ``HOST_UNAVAILABLE``: an
outage label for a healthy host, and neither a validation nor a rejection of the plan.

These tests replay the *recorded* answer — the measured 81-character string, verbatim — through a
host-seam double that performs the host's own check (``jsonschema.validate`` against the request's
schema, raising the same ``ValueError`` text as ``agent.plugin_llm._parse_structured_text``). No
provider is called and no model behaviour is invented: each scripted item is a fixed document, and
whether it passes is decided by the real schema.

What is asserted:

* the recorded answer is repaired by exactly one distinct re-ask, and the artifact is then
  validated on its merits (``outcome``/``independence`` computed from the answering response);
* the re-ask is recorded as real spend (``outcome: schema_rejected``) and the validation record
  carries ``shape_violations: 1`` — a repaired answer is never presented as a first-time one;
* a second malformed answer raises :class:`generation.ModelOutputInvalid`, which the job service
  reports as ``VALIDATION_FAILED`` (non-retryable) with the failed rule in ``details`` — not
  ``HOST_UNAVAILABLE``, and not a rejection: no validation record and no verdict are written;
* the schema's bound, ``required`` list, ``enums`` and ``additionalProperties: false`` are
  untouched, and the re-ask never runs when too little of the deadline is left to finish.
"""

from __future__ import annotations

import json
import sqlite3
import time
import unittest

import jsonschema

from coursebook import contracts, generation as gen, job_service
from tests.kernel_support import KernelCase
from tests.test_generation import NOW, FakeSearch, fixture, plan_fixture, plan_job, source_ids_from

#: The exact string the live validator wrote (81 characters). Verbatim from the measured failure.
MEASURED_ITEM = "check_plan: pressing harder does not fix a rolled edge; light strokes are correct"

#: The host's own wording, so a test failure shows the same message an operator saw.
HOST_GATE_PREFIX = "Plugin LLM structured output did not match schema: "


def _claim_verdicts_for(request: gen.LLMRequest | None) -> list[dict]:
    """Claim verdicts for exactly the labels this pass was told to judge.

    H-191's narrowed demand (``plan_claim_labels`` / ``validation_pass_schema``) pins
    ``claim_verdicts`` to the plan's own named claims, so a fixture answer that carries an empty
    claim set is no longer schema-valid for a plan pass. The fixtures stay recorded answers; only
    the claim set is derived from the request, so the shape under test is still the measured
    over-long ``item`` and not a stale claim list.
    """
    if request is None or request.schema is None:
        return []
    claim = (request.schema.get("properties") or {}).get("claim_verdicts") or {}
    labels = (((claim.get("items") or {}).get("properties") or {}).get("item") or {}).get("enum")
    if not labels:
        return []
    return [
        {"item": label, "support": "unverified", "reason": "not assessed by this fixture"}
        for label in labels
    ]


def _claim_block(request: gen.LLMRequest | None) -> dict:
    return (((request.schema if request is not None else None) or {}).get("properties") or {})


def _with_claims(document: dict, request: gen.LLMRequest | None) -> dict:
    """Carry claim verdicts only for a pass whose schema carries them.

    A criteria pass with no claims, or a pass whose claim batch is empty, has no
    ``claim_verdicts`` property and ``additionalProperties: false``; a stray empty list would be
    rejected by the narrowed schema before the recorded shape under test is reached.
    """
    if "claim_verdicts" in _claim_block(request):
        document["claim_verdicts"] = _claim_verdicts_for(request)
    else:
        document.pop("claim_verdicts", None)
    return document


def _owned_criteria(request: gen.LLMRequest | None) -> list[str]:
    """The criteria this pass owns, read from its narrowed schema."""
    block = ((request.schema if request is not None else None) or {}).get("properties", {}).get(
        "criteria"
    ) or {}
    enum = (((block.get("items") or {}).get("properties") or {}).get("id") or {}).get("enum")
    return list(enum or gen.VALIDATION_CRITERIA)


def _narrow_to_pass(document: dict, request: gen.LLMRequest | None) -> dict:
    """Answer exactly the pass: its criteria, its rejections, its claims.

    H-192b splits the review into passes, so a recorded wide answer would fail the narrowed schema
    on ``criteria`` (too long) before the shape under test is reached. Narrowing keeps the recorded
    text and only removes what another pass owns. CP-015a added an eleventh criterion, so a pass can
    own a criterion the recorded answer predates; that slot is filled with a plain ``pass`` entry
    (as ``tests/blueprint_support.narrowed_validation_answer`` does) rather than letting the count
    be what the schema rejects — the recorded defect under test here is the over-long ``item``.
    """
    owned = _owned_criteria(request)
    owned_set = set(owned)
    document["criteria"] = [
        entry for entry in document.get("criteria") or [] if entry.get("id") in owned_set
    ]
    if ((_claim_block(request).get("criteria") or {}) if request is not None else {}):
        answered = {entry.get("id") for entry in document["criteria"]}
        document["criteria"].extend(
            {
                "id": criterion,
                "verdict": "pass",
                "reason": "nothing in the artifact contradicts this criterion",
            }
            for criterion in owned
            if criterion not in answered
        )
    document["rejections"] = [
        entry for entry in document.get("rejections") or [] if entry.get("criterion") in owned_set
    ]
    return _with_claims(document, request)


def measured_document(request: gen.LLMRequest | None = None) -> dict:
    """The recorded validator answer: schema-minimal, with the measured over-long ``item``."""
    document = json.loads(json.dumps(fixture("validation_measured_item_81")))
    return _narrow_to_pass(document, request)


def clean_document(request: gen.LLMRequest | None = None) -> dict:
    """A schema-valid validator answer with no claim coupling (the ledger stays untouched)."""
    document = json.loads(json.dumps(fixture("validation_pass")))
    return _narrow_to_pass(document, request)


def _owns_measured_rejection(request: gen.LLMRequest | None) -> bool:
    """Does this pass own the criterion the measured rejection names?

    The recorded answer rejects ``evidence_target_fit``, which H-192b puts in the second pass
    only. ``_narrow_to_pass`` therefore strips that rejection from the first pass, leaving a
    document that still *declares* ``reject`` while failing no criterion of its own. H-182 reads a
    declared refusal as a plan that can be re-authored, so serving the recorded answer to the
    pass that does not own the rejection turned the shape repair under test into a second
    ``plan.generate`` — decided by thread order, not by the behaviour. The answer is served to
    the owning pass, where the over-long ``item`` is the violation the test is about.
    """
    measured = (fixture("validation_measured_item_81").get("rejections") or [{}])[0]
    criterion = str(measured.get("criterion") or "")
    return bool(criterion) and criterion in _owned_criteria(request)


class FirstValidationAnswerMalformed:
    """Recorded-answer script: exactly one plan-validate call gets the measured 81-char answer.

    H-192b splits plan validation into two passes that run together, so a per-call list would
    depend on thread order; the recorded answer is served to the pass that owns the criterion it
    rejects (H-182: a refusal on any pass re-authors the plan, so a refusal must land where its
    rejection is schema-valid). Its repair and every other pass answer cleanly, and it never
    repeats.
    """

    def __call__(self, request: gen.LLMRequest) -> dict:
        if request.prompt_version.endswith(gen.REPAIR_PROMPT_SUFFIX):
            return clean_document(request)
        if _owns_measured_rejection(request):
            return measured_document(request)
        return clean_document(request)


class HostStructuredSeam:
    """The host's structured-output seam, replaying recorded answers.

    ``complete_structured`` on the host validates the parsed document against the request's
    ``json_schema`` and raises ``ValueError`` for the whole document when it does not match
    (``agent.plugin_llm._parse_structured_text``). This double does the same check with the same
    library call, so an 81-character ``item`` fails here for exactly the reason it failed live.

    A script entry is either a list (one recorded answer per call, popped in order) or a callable
    applied to every call of that purpose (``(request) -> document``). The callable form exists
    because H-192b made the plan validation two passes: a per-call list would depend on which
    thread reached the seam first, while the recorded-answer property under test does not.
    """

    def __init__(self, script: dict[str, object], *, models: dict[str, str] | None = None) -> None:
        self.script = {
            purpose: list(items) if isinstance(items, list) else items
            for purpose, items in script.items()
        }
        self.models = models or {
            "coursebook.plan.generate": "author-model",
            "coursebook.plan.validate": "second-opinion-model",
        }
        self.requests: list[gen.LLMRequest] = []

    def __call__(self, request: gen.LLMRequest) -> gen.LLMResponse:
        self.requests.append(request)
        items = self.script.get(request.purpose)
        if callable(items) and not isinstance(items, list):
            document = items(request)
        elif not items:
            raise AssertionError(f"unexpected provider call {request.purpose!r}: script exhausted")
        else:
            assert isinstance(items, list)
            item = items.pop(0)
            document = item(request) if callable(item) else item
        text = json.dumps(document, ensure_ascii=False)
        parsed = json.loads(text)
        if request.schema is not None:
            try:
                jsonschema.validate(parsed, request.schema)
            except jsonschema.ValidationError as exc:
                raise ValueError(f"{HOST_GATE_PREFIX}{exc.message}") from exc
        return gen.LLMResponse(
            text=text,
            parsed=parsed,
            provider="nous",
            model=self.models.get(request.purpose, "model"),
            input_tokens=1000,
            output_tokens=2000,
            cost_usd=0.02,
        )

    def calls_for(self, purpose: str) -> list[gen.LLMRequest]:
        return [request for request in self.requests if request.purpose == purpose]


def plan_document(request: gen.LLMRequest) -> dict:
    return plan_fixture("plan_ja", source_ids_from(request))


class ShapeRepairCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        gen.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def run_plan(self, seam: HostStructuredSeam) -> dict:
        return gen.run_plan_job(
            self.connection, plan_job(), seam, FakeSearch(), now=NOW
        )

    def rows(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]


class SchemaIsNotRelaxedTest(unittest.TestCase):
    """The forbidden shortcuts are asserted against, not narrated in a comment."""

    def test_item_bound_is_pinned_and_the_rest_of_the_schema_is_untouched(self) -> None:
        schema = gen.VALIDATION_SCHEMA
        for section in ("rejections", "claim_verdicts"):
            item = schema["properties"][section]["items"]["properties"]["item"]
            self.assertEqual(item["maxLength"], gen.ITEM_REFERENCE_MAX_CHARS)
            self.assertEqual(gen.ITEM_REFERENCE_MAX_CHARS, 80)
            self.assertEqual(item["minLength"], 1)
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(schema["required"], ["verdict", "criteria", "rejections"])
        self.assertEqual(
            schema["properties"]["verdict"]["enum"], ["pass", "reject"]
        )
        self.assertEqual(
            schema["properties"]["criteria"]["items"]["properties"]["id"]["enum"],
            list(gen.VALIDATION_CRITERIA),
        )
        self.assertIs(schema["properties"]["criteria"]["items"]["additionalProperties"], False)
        self.assertIs(
            schema["properties"]["rejections"]["items"]["additionalProperties"], False
        )
        self.assertIs(
            schema["properties"]["claim_verdicts"]["items"]["additionalProperties"], False
        )

    def test_the_measured_string_really_is_one_character_over_the_bound(self) -> None:
        self.assertEqual(len(MEASURED_ITEM), 81)
        self.assertEqual(len(MEASURED_ITEM), gen.ITEM_REFERENCE_MAX_CHARS + 1)
        with self.assertRaises(jsonschema.ValidationError) as caught:
            jsonschema.validate(
                MEASURED_ITEM,
                gen.VALIDATION_SCHEMA["properties"]["rejections"]["items"]["properties"]["item"],
            )
        self.assertIn("is too long", str(caught.exception))


class PromptStatesTheRuleTest(unittest.TestCase):
    def test_validator_instructions_state_the_locator_rule_and_the_bound(self) -> None:
        instructions = gen._validation_instructions(
            subject="plan", criteria=gen.VALIDATION_CRITERIA
        )
        self.assertIn("'item' is a short locator", instructions)
        self.assertIn(f"at most {gen.ITEM_REFERENCE_MAX_CHARS} characters", instructions)
        self.assertIn("every explanation goes in 'reason'", instructions)

    def test_the_prompt_label_advanced_with_the_instruction_text(self) -> None:
        # A label is part of stored validation bindings and the idempotency fingerprint; a
        # different instruction text under a reused label is never silently accepted.
        # v5 (`t_0affea08`) added the declared-reject rule to the pass instructions; the label
        # advances with it (`docs/DECISION-VALIDATION-REJECT-BASIS.md`).
        # v6 (CP-015) lowers the per-pass claim demand to three (criteria pass) and four
        # (claim-only pass) because a six-claim pass overran the 24 576-byte answer bound.
        # v7 (CP-015d) states the narrowed-plan rubric for objective_alignment /
        # internal_contradiction / goal_capability_disclosure and sizes the answer demand.
        # v8 (CP-015g) states that a unit-sections pass judges one unit against its own goal and
        # objectives, and drops the whole-course learner_outcome from the unit-stage brief.
        self.assertEqual(gen.VALIDATION_PROMPT_VERSION, "validation-prompt.v8")


class RepairedAnswerIsValidOnTheMeritsTest(ShapeRepairCase):
    def test_the_recorded_81_char_answer_is_re_asked_once_and_then_validated(self) -> None:
        seam = HostStructuredSeam(
            {
                "coursebook.plan.generate": [plan_document],
                "coursebook.plan.validate": FirstValidationAnswerMalformed(),
            }
        )
        result = self.run_plan(seam)

        validate_calls = seam.calls_for("coursebook.plan.validate")
        repairs = [
            call
            for call in validate_calls
            if call.prompt_version.endswith(gen.REPAIR_PROMPT_SUFFIX)
        ]
        self.assertEqual(len(repairs), 1, "exactly one re-ask")
        repair = repairs[0]
        first = next(
            call for call in validate_calls if call is not repair and call.schema is repair.schema
        )
        self.assertEqual(
            len(validate_calls), len(gen.VALIDATION_CRITERIA_PASSES) + 1, validate_calls
        )

        # The re-ask is a distinct call: different instructions, marked prompt version, same
        # pass (system prompt, schema and input bytes unchanged).
        self.assertNotEqual(first.instructions, repair.instructions)
        self.assertIn(HOST_GATE_PREFIX.split(":")[0], repair.instructions)
        self.assertIn("is too long", repair.instructions)
        self.assertIn(gen.UNTRUSTED_SOURCE_BEGIN, repair.instructions)
        self.assertEqual(repair.system_prompt, first.system_prompt)
        self.assertIs(repair.schema, first.schema)
        self.assertEqual(repair.input_text, first.input_text)
        self.assertEqual(repair.purpose, first.purpose)
        self.assertEqual(
            repair.prompt_version, first.prompt_version + gen.REPAIR_PROMPT_SUFFIX
        )
        # The repair answers inside what was left of the original deadline, never a fresh one.
        self.assertLessEqual(repair.timeout_s, first.timeout_s)
        # Separation is untouched: the generation request and the validation pass still differ.
        gen.assert_separate_pass(seam.calls_for("coursebook.plan.generate")[0], repair)

        # The artifact is validated on its merits — by the answering response's identity.
        self.assertEqual(result["validation_verdict"], "pass")
        self.assertEqual(result["validation"]["independence"], "independent")
        self.assertEqual(result["validation"]["validator"]["model"], "second-opinion-model")
        self.assertEqual(result["validation"]["outcome"], gen.OUTCOME_INDEPENDENT)
        self.assertEqual(result["validation"]["shape_violations"], 1)

        record = gen.validation_record(self.connection, result["validation_id"])
        self.assertIsNotNone(record)
        # The recorded binding is the *pass* label, not the re-ask's marked label.
        stored = self.rows(
            "SELECT validator_prompt_version FROM gen_validation_records WHERE id = ?",
            (result["validation_id"],),
        )
        self.assertEqual(stored[0]["validator_prompt_version"], gen.VALIDATION_PROMPT_VERSION)
        self.assertEqual(record["shape_violations"], 1)
        self.assertEqual(record["validator"]["model"], "second-opinion-model")
        self.assertEqual(record["independence"], "independent")

        # The discarded call is recorded as real spend, never dropped.
        usage_rows = self.rows(
            "SELECT tokens_json FROM usage_events WHERE operation_id = ?", (result["job_id"],)
        )
        per_validate = []
        for row in usage_rows:
            tokens = json.loads(row["tokens_json"])
            if str(tokens.get("purpose") or "").endswith(".validate"):
                per_validate.append(tokens)
        self.assertEqual(len(per_validate), len(validate_calls), per_validate)
        self.assertEqual(
            result["usage"]["calls"], result["usage"]["by_purpose"]["coursebook.plan.validate"]["calls"]
            + result["usage"]["by_purpose"]["coursebook.plan.generate"]["calls"],
        )
        self.assertEqual(result["validation"]["cost"]["calls"], len(validate_calls))

    def test_the_author_pass_gets_the_same_single_re_ask(self) -> None:
        seam = HostStructuredSeam(
            {
                "coursebook.plan.generate": [{"verdict": "pass"}, plan_document],
                "coursebook.plan.validate": clean_document,
            }
        )
        result = self.run_plan(seam)
        author_calls = seam.calls_for("coursebook.plan.generate")
        self.assertEqual(len(author_calls), 2)
        self.assertEqual(
            author_calls[1].prompt_version,
            author_calls[0].prompt_version + gen.REPAIR_PROMPT_SUFFIX,
        )
        self.assertEqual(result["validation_verdict"], "pass")


class SecondViolationIsTypedNotAnOutageTest(ShapeRepairCase):
    def test_a_second_malformed_answer_raises_a_typed_contract_failure(self) -> None:
        seam = HostStructuredSeam(
            {
                "coursebook.plan.generate": [plan_document],
                "coursebook.plan.validate": measured_document,
            }
        )
        with self.assertRaises(gen.ModelOutputInvalid) as caught:
            self.run_plan(seam)
        error = caught.exception
        self.assertGreaterEqual(len(seam.calls_for("coursebook.plan.validate")), 2)
        self.assertEqual(error.code, "VALIDATION_FAILED")
        self.assertEqual(error.purpose, "coursebook.plan.validate")
        self.assertEqual(error.schema_name, "coursebook_validation_v1")
        self.assertTrue(error.repair_attempted)
        self.assertIn("is too long", error.violation)
        self.assertNotIsInstance(error, gen.ProviderFailure)
        self.assertEqual(job_service._error_code(error), "VALIDATION_FAILED")

        # No verdict, no rejection, no validation record: a malformed answer is not an artifact
        # verdict, and nothing is presented as validated or rejected.
        self.assertEqual(self.rows("SELECT COUNT(*) AS n FROM gen_validation_records")[0]["n"], 0)
        self.assertEqual(self.rows("SELECT COUNT(*) AS n FROM gen_plan_documents")[0]["n"], 0)
        self.assertEqual(self.rows("SELECT COUNT(*) AS n FROM plans")[0]["n"], 0)

    def test_no_re_ask_is_spent_when_the_deadline_cannot_cover_it(self) -> None:
        request = gen.LLMRequest(
            purpose="coursebook.plan.validate",
            prompt_version=gen.VALIDATION_PROMPT_VERSION,
            system_prompt="validate",
            instructions=gen._validation_instructions(
                subject="plan", criteria=gen.VALIDATION_CRITERIA
            ),
            input_text="{}",
            schema=gen.VALIDATION_SCHEMA,
            schema_name="coursebook_validation_v1",
            max_tokens=2000,
            timeout_s=gen.MIN_SHAPE_REPAIR_SECONDS / 2,
        )
        seam = HostStructuredSeam({"coursebook.plan.validate": [measured_document()]})
        usage = gen._Usage(budget=gen.CostBudget(max_calls=4, max_cost_usd=None))
        with self.assertRaises(gen.ModelOutputInvalid) as caught:
            gen._call_llm(seam, request, usage)
        self.assertFalse(caught.exception.repair_attempted)
        self.assertEqual(len(seam.requests), 1, "no second call may be bought without time for it")
        self.assertEqual(usage.calls[0]["outcome"], "schema_rejected")


class JobReportsTheTruthTest(ShapeRepairCase):
    def test_the_job_reports_validation_failed_not_host_unavailable(self) -> None:
        seam = HostStructuredSeam(
            {
                "coursebook.plan.generate": [plan_document],
                "coursebook.plan.validate": measured_document,
            }
        )
        connection = self.connection

        def plan_stage(_lease):
            # The real pipeline raises the real exception; the job service decides the label.
            gen.run_plan_job(connection, plan_job(), seam, FakeSearch(), now=NOW)

        stage = job_service.Stage("plan", plan_stage)
        error = job_service._stage_error(self._raised(stage))
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["category"], "validation")
        self.assertFalse(error["retryable"])
        self.assertEqual(error["details"]["purpose"], "coursebook.plan.validate")
        self.assertEqual(error["details"]["schema_name"], "coursebook_validation_v1")
        self.assertTrue(error["details"]["repair_attempted"])
        self.assertIn("is too long", error["details"]["violation"])
        contracts.validate_definition("cb.errors", "error", error)
        self.assertNotEqual(error["code"], "HOST_UNAVAILABLE")

    def _raised(self, stage) -> Exception:
        try:
            stage.run(None)
        except Exception as exc:  # noqa: BLE001 - the raised error is the artifact under test
            return exc
        raise AssertionError("the stage did not raise")


class ProviderFailureStaysAnOutageTest(KernelCase):
    """The label that *is* right for a host outage must not move with this change."""

    def test_a_provider_failure_is_still_host_unavailable_and_retryable(self) -> None:
        job_id = self.ok("jobs.create", {"kind": "research", "brief": {"goal": "x"}})["result"]["job_id"]

        def stage(_lease):
            raise gen.ProviderFailure("coursebook.plan.validate failed: RuntimeError: boom",
                                      purpose="coursebook.plan.validate")

        view = job_service.execute(job_id, [job_service.Stage("plan", stage)])
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["error"]["code"], "HOST_UNAVAILABLE")
        self.assertEqual(view["error"]["category"], "capability")
        self.assertTrue(view["error"]["retryable"])


if __name__ == "__main__":
    unittest.main()
