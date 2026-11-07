"""H-15 — validator identity and the no-research factual waiver.

These are regressions for findings H10-3/H10-4 in ``docs/ADVERSARIAL-AUDIT-ROUND2.md``:

* a second prompt answered by the *same model* was recorded as a pass and could upgrade source
  support;
* when research was unavailable, ``factual_correctness`` and ``source_support`` could be answered
  ``unknown`` and the plan was still presented as a validated draft.

No provider is called. Every model is a scripted fake, so a pass here is a property of the
harness, not of a model.
"""

from __future__ import annotations

import json
import sqlite3
import types
import unittest

from coursebook import generation as gen
from coursebook import research
from coursebook.research import ResearchRun, SourceRecord, canonical_json
from tests.test_generation import (
    NOW,
    FakeLLM,
    FakeSearch,
    fixture,
    lesson_from_request,
    plan_fixture,
    plan_job,
    response,
    validation_from_fixture,
)

CRITERIA = list(gen.VALIDATION_CRITERIA)
EXCERPT = "A polite greeting when entering a shop is こんにちは. Standard polite forms are the safe default."


def validation_report(
    *,
    verdict: str = "pass",
    fail: str | None = None,
    unknown: tuple[str, ...] = (),
    claim_verdicts: list | None = None,
) -> dict:
    criteria = []
    for criterion in CRITERIA:
        value = "pass"
        if criterion == fail:
            value = "fail"
        elif criterion in unknown:
            value = "unknown"
        criteria.append({"id": criterion, "verdict": value, "reason": f"{criterion} checked"})
    return {
        "verdict": verdict,
        "criteria": criteria,
        "rejections": (
            [{"item": "plan", "criterion": fail, "reason": "the validator found a defect"}] if fail else []
        ),
        "claim_verdicts": claim_verdicts or [],
    }


class ScriptedLLM:
    """One model for both passes unless ``validator_model`` differs."""

    def __init__(self, plan: dict, validation: dict, *, model: str = "same-host-model") -> None:
        self.plan = plan
        self.validation = validation
        self.model = model
        self.requests: list[gen.LLMRequest] = []

    def __call__(self, request: gen.LLMRequest) -> gen.LLMResponse:
        self.requests.append(request)
        if request.purpose == "coursebook.plan.generate":
            return response(self.plan, model=self.model)
        if request.purpose == "coursebook.plan.validate":
            return response(self.validation, model=self.model)
        if request.purpose == "coursebook.lesson.generate":
            return lesson_from_request()(request)
        if request.purpose == "coursebook.lesson.validate":
            return response(self.validation, model=self.model)
        raise AssertionError(f"unexpected provider call {request.purpose!r}")


class TrustError(Exception):
    """Name matches the host's ``PluginLlmTrustError`` classification."""


class FakePluginLlm:
    """A host ``ctx.llm`` that records overrides and can refuse them."""

    def __init__(self, *, model: str = "second-model", provider: str = "second-provider", refuse: bool = False) -> None:
        self.model = model
        self.provider = provider
        self.refuse = refuse
        self.calls: list[dict] = []

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        if self.refuse and ("model" in kwargs or "provider" in kwargs):
            raise TrustError("model override is not allowed for this plugin")
        payload = validation_report()
        return types.SimpleNamespace(
            text=json.dumps(payload),
            parsed=payload,
            provider=self.provider,
            model=self.model,
            usage=types.SimpleNamespace(input_tokens=10, output_tokens=10, cost_usd=0.02),
        )


def request(purpose: str = "coursebook.plan.validate") -> gen.LLMRequest:
    return gen.LLMRequest(
        purpose=purpose,
        prompt_version=gen.VALIDATION_PROMPT_VERSION,
        system_prompt="system",
        instructions="instructions",
        input_text="{}",
        schema={"type": "object"},
        schema_name="coursebook_validation_v1",
        max_tokens=10,
        timeout_s=10.0,
    )


def memory_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    gen.ensure_schema(connection)
    return connection


class IdentityTest(unittest.TestCase):
    def tearDown(self) -> None:
        gen.bind_validator_llm(None)

    def test_classification(self) -> None:
        self.assertEqual(
            gen.validation_independence({"model": "a", "provider": "p"}, {"model": "a", "provider": "p"}),
            gen.INDEPENDENCE_SAME_MODEL,
        )
        self.assertEqual(
            gen.validation_independence({"model": "a", "provider": "p"}, {"model": "b", "provider": "p"}),
            gen.INDEPENDENCE_INDEPENDENT,
        )
        self.assertEqual(
            gen.validation_independence({"model": None, "provider": "p"}, {"model": "b", "provider": "p"}),
            gen.INDEPENDENCE_UNIDENTIFIED,
        )
        self.assertEqual(
            gen.validation_independence({"model": "a", "provider": None}, {"model": "A", "provider": "p"}),
            gen.INDEPENDENCE_SAME_MODEL,
        )

    def test_cross_model_binding_passes_the_host_override(self) -> None:
        host = FakePluginLlm(model="second-model", provider="second-provider")
        gen.bind_validator_llm(host, provider="second-provider", model="second-model")
        validator = gen.validator_llm()
        self.assertIsNotNone(validator)
        answer = validator(request())
        self.assertEqual(host.calls[0]["model"], "second-model")
        self.assertEqual(host.calls[0]["provider"], "second-provider")
        self.assertEqual(answer.model, "second-model")
        self.assertEqual(answer.provider, "second-provider")
        # The author's own route is untouched: no override leaks into generation calls.
        gen.bind_host_llm(host)
        gen.host_llm()(request("coursebook.plan.generate"))
        self.assertNotIn("model", host.calls[-1])

    def test_host_trust_refusal_is_a_documented_error_not_a_silent_fallback(self) -> None:
        host = FakePluginLlm(refuse=True)
        gen.bind_validator_llm(host, provider="second-provider", model="second-model")
        with self.assertRaises(gen.GenerationRejected) as raised:
            gen.validator_llm()(request())
        self.assertIn("allow_model_override", str(raised.exception))
        self.assertIn("non-independent", str(raised.exception))

    def test_no_second_model_configured_is_reported(self) -> None:
        gen.bind_validator_llm(None, provider="", model="")
        self.assertIsNone(gen.validator_llm())
        self.assertFalse(gen.validator_config()["configured"])


class SycophanticPassTest(unittest.TestCase):
    """The H10-3 probe: a false claim accepted by the author's own model."""

    def setUp(self) -> None:
        gen.bind_validator_llm(None)
        self.connection = memory_connection()

    def tearDown(self) -> None:
        gen.bind_validator_llm(None)
        self.connection.close()

    def test_same_model_pass_is_model_assessed_not_a_validated_draft(self) -> None:
        plan = plan_fixture("plan_ja")
        plan["objectives"][0]["title"] = "State that water boils at 50 °C at sea level"
        plan["objectives"][0]["evidence_criteria"] = ["Recites 50 °C as the boiling point"]
        llm = ScriptedLLM(plan, validation_report(verdict="pass"), model="same-host-model")

        result = gen.run_plan_job(self.connection, plan_job(), llm, FakeSearch(), now=NOW)

        self.assertEqual(result["validation_verdict"], "pass")
        self.assertEqual(result["validation"]["independence"], "same_model")
        self.assertEqual(result["validation"]["outcome"], "model_assessed")
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(result["approval_provenance"]["needs_review"])
        self.assertIn("model assessed", result["approval_provenance"]["warning"])

        record = self.connection.execute("SELECT * FROM gen_validation_records").fetchone()
        self.assertEqual(record["generator_model"], "same-host-model")
        self.assertEqual(record["validator_model"], "same-host-model")
        self.assertEqual(record["independence"], "same_model")
        self.assertEqual(record["outcome"], "model_assessed")
        # The two prompt hashes still differ; separation of prompts is not independence.
        self.assertNotEqual(record["generator_prompt_sha256"], record["validator_prompt_sha256"])

        document = gen.plan_document(self.connection, result["plan_id"])
        self.assertEqual(document["generation_state"], "needs_review")
        self.assertEqual(document["approval"]["outcome"], "model_assessed")
        self.assertFalse(document["approval"]["independent"])
        self.assertIn("model assessed", document["approval"]["warning"])

    def test_same_model_validator_cannot_upgrade_support_even_with_a_verbatim_quote(self) -> None:
        source = SourceRecord(
            source_id="src_1",
            url="https://example.test",
            title="T",
            publisher="example.test",
            source_type="web_page",
            fetched_at="2026-11-06T12:00:00Z",
            published_at=None,
            content_hash="sha256:0",
            excerpt=EXCERPT,
        )
        upgraded = research.apply_support_verdicts(
            [source],
            [{"source_id": "src_1", "support": "supported", "evidence_quote": "こんにちは", "reason": "trust me"}],
            independent=False,
        )
        self.assertEqual(upgraded[0].support_status, "unverified")

    def test_independent_upgrade_requires_a_verbatim_quote(self) -> None:
        source = SourceRecord(
            source_id="src_1",
            url="https://example.test",
            title="T",
            publisher="example.test",
            source_type="web_page",
            fetched_at="2026-11-06T12:00:00Z",
            published_at=None,
            content_hash="sha256:0",
            excerpt=EXCERPT,
        )
        invented = research.apply_support_verdicts(
            [source],
            [{"source_id": "src_1", "support": "supported", "evidence_quote": "水は50度で沸騰する", "reason": "invented"}],
            independent=True,
        )
        self.assertEqual(invented[0].support_status, "unverified")
        verified = research.apply_support_verdicts(
            [source],
            [{"source_id": "src_1", "support": "supported", "evidence_quote": "こんにちは", "reason": "quoted"}],
            independent=True,
        )
        self.assertEqual(verified[0].support_status, "supported")


class NoResearchWaiverTest(unittest.TestCase):
    """The H10-4 probe: unknown factual criteria were waived into a validated pass."""

    def setUp(self) -> None:
        gen.bind_validator_llm(None)
        self.connection = memory_connection()

    def tearDown(self) -> None:
        gen.bind_validator_llm(None)
        self.connection.close()

    def test_factual_unknown_closes_the_gate_even_when_allowed(self) -> None:
        report = validation_report(verdict="pass", unknown=("factual_correctness", "source_support"))
        waived = gen.validation_verdict(
            report, research_status="unavailable", independence=gen.INDEPENDENCE_INDEPENDENT
        )
        self.assertEqual(waived["verdict"], "pass")
        self.assertEqual(waived["waived_unknown"], ["factual_correctness", "source_support"])
        self.assertTrue(waived["facts_unverified"])
        self.assertEqual(waived["outcome"], gen.OUTCOME_MODEL_ASSESSED)
        self.assertIn(
            "facts unverified, no sources",
            gen._provenance_warning(
                waived["outcome"], waived["independence"], waived["facts_unverified"]
            ),
        )

        strict = gen.validation_verdict(
            report, research_status="ok", independence=gen.INDEPENDENCE_INDEPENDENT
        )
        self.assertEqual(strict["verdict"], "reject")

    def test_no_research_plan_is_needs_review_and_carries_the_warning(self) -> None:
        llm = FakeLLM(
            {
                "coursebook.plan.generate": lambda request: response(
                    plan_fixture("plan_ja", ()), model="fake-model"
                ),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(self.connection, plan_job(), llm, None, now=NOW)

        self.assertEqual(result["research"]["status"], "unavailable")
        self.assertEqual(result["validation_verdict"], "pass")
        self.assertEqual(result["validation"]["outcome"], "model_assessed")
        self.assertTrue(result["validation"]["facts_unverified"])
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(
            any("facts unverified, no sources" in warning for warning in result["warnings"])
        )
        document = gen.plan_document(self.connection, result["plan_id"])
        self.assertTrue(document["approval"]["facts_unverified"])
        self.assertTrue(document["approval"]["needs_review"])
        self.assertIn("facts unverified, no sources", document["approval"]["warning"])

    def test_model_assessed_lesson_is_readable_with_a_warning_and_no_check(self) -> None:
        # A no-research plan, then an approved version, then one authored section. The lesson is
        # served with its provenance banner; its check is closed.
        plan_llm = FakeLLM(
            {
                "coursebook.plan.generate": lambda request: response(
                    plan_fixture("plan_ja", ()), model="fake-model"
                ),
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        plan_result = gen.run_plan_job(self.connection, plan_job(), plan_llm, None, now=NOW)
        self.connection.execute(
            "UPDATE plans SET state = 'approved', approved_at = ? WHERE id = ?",
            ("2026-11-06T12:05:00Z", plan_result["plan_id"]),
        )
        lesson_llm = FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request(),
                # Same author model, same validation model: model_assessed.
                "coursebook.lesson.validate": lambda request: response(
                    validation_from_fixture()(request).parsed, model="fake-author"
                ),
            }
        )
        lessons = gen.run_lesson_job(
            self.connection,
            {"job_id": "job-lesson-h15", "kind": "plan", "brief": {"plan_id": plan_result["plan_id"]}},
            lesson_llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=32),
        )
        self.assertEqual(lessons["lessons"][0]["state"], "model_assessed")
        self.assertFalse(lessons["lessons"][0]["check_enabled"])
        page = gen.learner_page(self.connection, lessons["lessons"][0]["lesson_id"])
        self.assertEqual(page["provenance"]["outcome"], "model_assessed")
        self.assertFalse(page["provenance"]["check_enabled"])
        self.assertIn("facts unverified, no sources", page["provenance"]["warning"])
        check_state = self.connection.execute("SELECT state, audit_state FROM checks").fetchone()
        self.assertEqual((check_state["state"], check_state["audit_state"]), ("closed", "pending"))


class RecordedIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        gen.bind_validator_llm(None)
        self.connection = memory_connection()

    def tearDown(self) -> None:
        gen.bind_validator_llm(None)
        self.connection.close()

    def test_cross_model_pass_is_recorded_as_independent(self) -> None:
        result = gen.run_plan_job(
            self.connection,
            plan_job(),
            FakeLLM(
                {
                    "coursebook.plan.generate": lambda request: response(
                        plan_fixture("plan_ja", ()), model="author-model"
                    ),
                    "coursebook.plan.validate": lambda request: response(
                        validation_from_fixture()(request).parsed, model="judge-model"
                    ),
                }
            ),
            FakeSearch(),
            now=NOW,
        )
        self.assertEqual(result["validation"]["independence"], "independent")
        self.assertEqual(result["validation"]["generator"]["model"], "author-model")
        self.assertEqual(result["validation"]["validator"]["model"], "judge-model")
        self.assertEqual(result["validation"]["outcome"], "independently_validated")
        self.assertEqual(result["status"], "draft")
        record = self.connection.execute("SELECT * FROM gen_validation_records").fetchone()
        self.assertEqual(record["validator_provider"], "fake")
        self.assertEqual(record["generator_provider"], "fake")
        self.assertEqual(record["independence"], "independent")
        self.assertEqual(record["facts_unverified"], 0)
        self.assertIsNotNone(result["validation"]["cost"])
        self.assertEqual(result["validation"]["cost"]["calls"], 1)
        self.assertIn("coursebook.plan.validate", result["usage"]["by_purpose"])


if __name__ == "__main__":
    unittest.main()
