"""CP-015g/D1 — a validator answer that is not JSON is repaired once, then typed and recorded.

Measured defect (packet ``docs/concept-parity/demo/cp015g/CP-015g-REVIEW.md``): on the installed
product, both ``coursebook.plan.validate`` calls of an Observatory/Short/Game plan returned
exactly 4 000 output tokens against ``VALIDATION_OUTPUT_TOKENS = 4000``; the answers arrived
truncated or unparseable, the job failed ``VALIDATION_FAILED`` with ``repair_attempted: false``,
``gen_validation_records`` was empty, and a ~30k-output-token authored plan was discarded.

These tests replay that shape through a seam double: the recorded answer is returned as *text
with no parsed document*, exactly as the host delivered it (``LLMResponse.parsed is None``). No
provider is called and no model behaviour is invented.

What is asserted:

* a non-JSON validator answer is re-asked once inside the stage, and the plan then validates on
  its merits — the job is not failed and the authored plan is not discarded;
* the repaired answer is recorded as repaired (``repair_attempted`` / ``shape_violations``), never
  as a first-time clean one;
* an answer that is cut off at the completion cap is named a *truncation* in the record and in
  the failure, not "invalid JSON";
* when the repair also fails, the job fails only after the repair, the error names it
  (``repair_attempted: true``), and ``gen_validation_records`` holds a row for **each** attempt
  with the validator prompt version, model and parse outcome;
* the output budget is sized above the answers the product actually receives on a short plan, so
  a normal plan does not return at the cap;
* a database created before this change is migrated in place, keeping every recorded review.
"""

from __future__ import annotations

import json
import sqlite3
import unittest

from coursebook import db, generation as gen, job_service
from tests.test_generation import (
    NOW,
    FakeSearch,
    plan_fixture,
    plan_job,
    source_ids_from,
    validation_from_fixture,
)

#: Prose, not JSON — the shape attempt-2 answers arrived in ("Expecting value at line 1").
NOT_JSON = "I reviewed the plan and it looks reasonable overall. No blocking issues found."

#: A cut answer: JSON that starts and stops mid-string — the measured attempt-1 shape.
TRUNCATED_JSON = '{"verdict": "pass", "criteria": [{"id": "objective_alignment", "verdict": "pa'

#: The model that answered the measured calls (the host's configured author route).
MEASURED_MODEL = "deepseek-v4.1-flash-1017"


def plan_answer(request: gen.LLMRequest) -> gen.LLMResponse:
    return gen.LLMResponse(
        text=json.dumps(plan_fixture("plan_ja", source_ids_from(request))),
        parsed=plan_fixture("plan_ja", source_ids_from(request)),
        provider="nous",
        model=MEASURED_MODEL,
        input_tokens=4000,
        output_tokens=30000,
        cost_usd=0.50,
    )


def raw_answer(text: str, *, output_tokens: int) -> gen.LLMResponse:
    """The host's delivery shape for an unparseable answer: the text is there, ``parsed`` is not."""
    return gen.LLMResponse(
        text=text,
        parsed=None,
        provider="nous",
        model=MEASURED_MODEL,
        input_tokens=9000,
        output_tokens=output_tokens,
        cost_usd=0.03,
    )


def valid_answer(request: gen.LLMRequest) -> gen.LLMResponse:
    """A schema-valid answer from the measured route."""
    answer = validation_from_fixture()(request)
    answer.model = MEASURED_MODEL
    answer.provider = "nous"
    return answer


def owns(request: gen.LLMRequest, criterion: str) -> bool:
    """Does this narrowed pass judge ``criterion``?"""
    properties = (request.schema or {}).get("properties") or {}
    enum = (
        (((properties.get("criteria") or {}).get("items") or {}).get("properties") or {})
        .get("id", {})
        .get("enum")
    ) or []
    return criterion in enum


class ValidatorSeam:
    """Scripted validator. ``script`` maps a call to a response; the call is inspected, not counted.

    Plan validation is several passes that run together, so a per-call list would depend on thread
    order. The script decides from the request itself: a first-time pass that owns
    ``objective_alignment``, or a repair pass (marked prompt version). That is deterministic.
    """

    def __init__(self, first_time, repair, *, every_pass: bool = False) -> None:
        self.first_time_answer = first_time
        self.repair_answer = repair
        #: When true, every pass's first-time answer is the scripted one (the measured shape: the
        #: whole review was unreadable). Otherwise only the pass that owns ``objective_alignment``.
        self.every_pass = every_pass
        self.requests: list[gen.LLMRequest] = []

    def __call__(self, request: gen.LLMRequest) -> gen.LLMResponse:
        self.requests.append(request)
        if request.purpose == "coursebook.plan.generate":
            return plan_answer(request)
        if request.prompt_version.endswith(gen.VALIDATION_REPAIR_PROMPT_SUFFIX):
            return self.repair_answer(request)
        if self.every_pass or owns(request, "objective_alignment"):
            return self.first_time_answer(request)
        return valid_answer(request)

    def validation_calls(self) -> list[gen.LLMRequest]:
        return [request for request in self.requests if request.purpose == "coursebook.plan.validate"]

    def repair_calls(self) -> list[gen.LLMRequest]:
        return [request for request in self.validation_calls() if request.prompt_version.endswith(gen.VALIDATION_REPAIR_PROMPT_SUFFIX)]


class RepairCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        gen.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def run_plan(self, seam) -> dict:
        return gen.run_plan_job(self.connection, plan_job(), seam, FakeSearch(), now=NOW)

    def records(self) -> list[dict]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM gen_validation_records ORDER BY pass_index, validator_prompt_version"
            ).fetchall()
        ]

    def merged(self) -> dict:
        rows = [row for row in self.records() if row["pass_index"] == -1]
        self.assertEqual(len(rows), 1, "exactly one merged review row")
        return rows[0]


class NonJsonAnswerIsRepairedOnceTest(RepairCase):
    def test_the_plan_validates_after_one_repair_instead_of_failing_the_job(self) -> None:
        seam = ValidatorSeam(
            first_time=lambda request: raw_answer(NOT_JSON, output_tokens=3433),
            repair=valid_answer,
        )
        result = self.run_plan(seam)

        self.assertEqual(result["validation_verdict"], "pass")
        self.assertEqual(len(seam.repair_calls()), 1, "exactly one repair re-ask, not a resample loop")
        repair = seam.repair_calls()[0]
        self.assertEqual(
            repair.prompt_version,
            gen.VALIDATION_PROMPT_VERSION + gen.VALIDATION_REPAIR_PROMPT_SUFFIX,
        )
        # The repair is the same pass, same schema: only the instruction text is different.
        self.assertIn("could not be read", repair.instructions)

        merged = self.merged()
        self.assertEqual(merged["verdict"], "pass")
        self.assertEqual(merged["repair_attempted"], 1)
        self.assertEqual(merged["validator_model"], MEASURED_MODEL)
        self.assertEqual(
            json.loads(merged["rejections_json"])["shape_violations"], 1,
            "a repaired answer is never recorded as first-time clean",
        )

        attempts = [row for row in self.records() if row["pass_index"] >= 0]
        self.assertEqual(len(attempts), 1, "the unreadable attempt keeps its own row")
        attempt = attempts[0]
        self.assertEqual(attempt["parse_outcome"], "not_json")
        self.assertEqual(attempt["verdict"], "invalid")
        self.assertEqual(attempt["outcome"], gen.OUTCOME_UNREADABLE)
        self.assertEqual(attempt["validator_prompt_version"], gen.VALIDATION_PROMPT_VERSION)
        self.assertEqual(attempt["validator_model"], MEASURED_MODEL)
        self.assertEqual(json.loads(attempt["failure_json"])["output_tokens"], 3433)


class CutAnswerIsNamedAndRepairedTest(RepairCase):
    def test_an_answer_that_consumed_the_cap_is_recorded_as_a_truncation(self) -> None:
        seam = ValidatorSeam(
            first_time=lambda request: raw_answer(TRUNCATED_JSON, output_tokens=request.max_tokens),
            repair=valid_answer,
        )
        result = self.run_plan(seam)

        self.assertEqual(result["validation_verdict"], "pass")
        attempt = [row for row in self.records() if row["pass_index"] >= 0][0]
        self.assertEqual(attempt["parse_outcome"], "truncated")
        self.assertIn("truncated", attempt["failure_json"])
        # The repair note for a cut answer asks for a shorter answer, not just a well-shaped one.
        self.assertIn("cut off", seam.repair_calls()[0].instructions)


class RepairAlsoFailsTest(RepairCase):
    def test_the_job_fails_only_after_the_repair_and_names_it(self) -> None:
        seam = ValidatorSeam(
            first_time=lambda request: raw_answer(NOT_JSON, output_tokens=3433),
            repair=lambda request: raw_answer(NOT_JSON, output_tokens=3582),
        )
        with self.assertRaises(gen.ModelOutputInvalid) as caught:
            self.run_plan(seam)

        error = caught.exception
        self.assertEqual(error.code, "VALIDATION_FAILED")
        self.assertTrue(error.repair_attempted)
        self.assertEqual(len(seam.repair_calls()), 1)
        self.assertIn("repair re-ask also failed", str(error))
        details = job_service._stage_error(error)["details"]
        self.assertIs(details.get("repair_attempted"), True)
        self.assertEqual(details.get("schema_name"), "coursebook_validation_v1")

        # One row per attempt: the first-time pass answer and its repair, both under their own
        # prompt versions, both naming the model and the parse outcome.
        attempts = [row for row in self.records() if row["pass_index"] >= 0]
        versions = sorted(row["validator_prompt_version"] for row in attempts)
        self.assertEqual(
            versions,
            sorted(
                [
                    gen.VALIDATION_PROMPT_VERSION,
                    gen.VALIDATION_PROMPT_VERSION + gen.VALIDATION_REPAIR_PROMPT_SUFFIX,
                ]
            ),
        )
        for row in attempts:
            self.assertEqual(row["parse_outcome"], "not_json")
            self.assertEqual(row["validator_model"], MEASURED_MODEL)
            self.assertEqual(row["verdict"], "invalid")
        self.assertEqual([row for row in self.records() if row["pass_index"] == -1], [])

    def test_every_unreadable_pass_gets_its_own_row(self) -> None:
        """Both passes of the review answered, and neither parsed: both are recorded."""
        seam = ValidatorSeam(
            first_time=lambda request: raw_answer(NOT_JSON, output_tokens=3433),
            repair=lambda request: raw_answer(NOT_JSON, output_tokens=3582),
            every_pass=True,
        )
        with self.assertRaises(gen.ModelOutputInvalid):
            self.run_plan(seam)

        pass_indexes = {row["pass_index"] for row in self.records()}
        self.assertGreaterEqual(len(pass_indexes), 2, "each pass's failure is its own row")
        self.assertNotIn(-1, pass_indexes, "no merged review row is written for an unreadable review")

    def test_a_verdict_violation_is_not_re_asked(self) -> None:
        """An ungrounded ``reject`` is not a parse failure; a second call cannot ground it."""

        def ungrounded(request: gen.LLMRequest) -> gen.LLMResponse:
            fixture = json.loads(json.dumps(validation_from_fixture()(request).parsed))
            fixture["verdict"] = "reject"
            for entry in fixture.get("criteria") or []:
                entry["verdict"] = "pass"
            fixture["rejections"] = []
            return gen.LLMResponse(
                text=json.dumps(fixture),
                parsed=fixture,
                provider="nous",
                model=MEASURED_MODEL,
                input_tokens=100,
                output_tokens=200,
                cost_usd=0.01,
            )

        seam = ValidatorSeam(first_time=ungrounded, repair=validation_from_fixture())
        with self.assertRaises(gen.ModelOutputInvalid) as caught:
            self.run_plan(seam)
        self.assertFalse(caught.exception.repair_attempted)
        self.assertEqual(seam.repair_calls(), [])
        row = self.records()[0]
        self.assertEqual(row["parse_outcome"], "verdict_violation")
        self.assertEqual(row["repair_attempted"], 0)


class BudgetIsSafeTest(RepairCase):
    def test_the_cap_is_above_the_answers_a_short_plan_receives(self) -> None:
        self.assertEqual(gen.VALIDATION_OUTPUT_TOKENS, 12000)
        # The measured attempt-2 answers used 3 433 and 3 582 tokens and were not truncated by the
        # provider; at 12 000 they are comfortably below the cap, and the 4 000 cap that cut
        # attempt 1 is gone. The live rerun at 8 000 still saw one pass return exactly 8 000
        # (cut mid-JSON) while its sibling passes used 1 815–3 923, so the cap was sized again.
        request = gen.LLMRequest(
            purpose="coursebook.plan.validate",
            prompt_version=gen.VALIDATION_PROMPT_VERSION,
            system_prompt="s",
            instructions="i",
            input_text="{}",
            schema=gen.VALIDATION_SCHEMA,
            schema_name="coursebook_validation_v1",
            max_tokens=gen.VALIDATION_OUTPUT_TOKENS,
            timeout_s=180.0,
        )
        measured = gen.LLMResponse(text="", parsed=None, output_tokens=3582)
        self.assertFalse(gen._answer_was_cut(measured, request))
        at_cap = gen.LLMResponse(text="", parsed=None, output_tokens=gen.VALIDATION_OUTPUT_TOKENS)
        self.assertTrue(gen._answer_was_cut(at_cap, request))

    def test_the_declared_bound_the_host_applies_is_the_new_cap(self) -> None:
        config = gen.validator_config()
        self.assertEqual(config["output_bound"]["completion_cap"], gen.VALIDATION_OUTPUT_TOKENS)
        self.assertEqual(
            gen.VALIDATION_AUX_DEFAULTS["extra_body"]["max_tokens"], gen.VALIDATION_OUTPUT_TOKENS
        )


class LegacyDatabaseIsMigratedTest(unittest.TestCase):
    """A database written before this card keeps every recorded review, and gains the pass key."""

    def test_ensure_schema_rebuilds_the_table_without_losing_a_row(self) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                "CREATE TABLE gen_validation_records ("
                " id TEXT PRIMARY KEY, subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL,"
                " subject_hash TEXT NOT NULL, generator_prompt_version TEXT NOT NULL,"
                " validator_prompt_version TEXT NOT NULL, validator_model TEXT, generator_model TEXT,"
                " generator_provider TEXT, validator_provider TEXT, independence TEXT,"
                " facts_unverified INTEGER, outcome TEXT, verdict TEXT NOT NULL,"
                " criteria_json TEXT NOT NULL, rejections_json TEXT NOT NULL,"
                " generator_prompt_sha256 TEXT NOT NULL, validator_prompt_sha256 TEXT NOT NULL,"
                " created_at TEXT NOT NULL,"
                " UNIQUE(subject_kind, subject_id, subject_hash, validator_prompt_version))"
            )
            connection.execute(
                "INSERT INTO gen_validation_records (id, subject_kind, subject_id, subject_hash,"
                " generator_prompt_version, validator_prompt_version, validator_model, outcome,"
                " verdict, criteria_json, rejections_json, generator_prompt_sha256,"
                " validator_prompt_sha256, created_at)"
                " VALUES ('v-legacy','plan','plan-1','hash-1','plan-prompt.v10','validation-prompt.v5',"
                " 'legacy-model','model_assessed','pass','[]','{}','a','b','2026-11-01T00:00:00Z')"
            )
            gen.ensure_schema(connection)
            row = dict(connection.execute("SELECT * FROM gen_validation_records").fetchone())
            self.assertEqual(row["id"], "v-legacy")
            self.assertEqual(row["verdict"], "pass")
            self.assertEqual(row["validator_model"], "legacy-model")
            self.assertEqual(row["pass_index"], -1, "a legacy merged row is not claimed as pass 0")
            self.assertEqual(row["parse_outcome"], "parsed")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
