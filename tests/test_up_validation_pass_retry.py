"""UP-34: one timed-out validation pass is retried in place, not paid for twice.

Measured defect at HEAD ``c3f4e34b``: ``_run_validation_passes`` settles every pass and then
raises the first error, and ``run_plan_job`` re-raises it after recording. A full plan whose
fourteenth pass timed out therefore discarded thirteen answered passes and failed the job with
``HOST_UNAVAILABLE`` even though the plan was fine. The learner's retry then paid for research and
a whole second authoring cycle, and a slow pass that stayed slow never completed.

The repair: a failed pass whose failure is in the transport class (``ProviderTimeout`` /
``ProviderFailure``, not a job-deadline cut and not a contract violation) is re-run **once inside
the same attempt**, with the same request object — same schema, same prompt version, same purpose —
its own fresh bounded deadline and its own usage row. Only a retry that also fails ends the stage.
Each retry is written to ``gen_validation_records.pass_retries`` so the review is never presented
as first-time clean.

The adversarial half (CP-015e): a retry is a legal extra provider call, so ``plan_calls`` must
count one per pass or the ceiling aborts a run behaving as designed. The last test pins that
arithmetic against the real job, not against a constant.

Red proof at HEAD: ``test_one_timed_out_pass_is_retried_in_place`` raises ``ProviderTimeout`` out
of ``run_plan_job`` (the job service maps it to ``HOST_UNAVAILABLE``) instead of returning a
passing verdict, and no ``pass_retries`` entry exists because the column and the retry do not.

Run only these with::

    python3 -m unittest tests.test_up_validation_pass_retry -v
"""

from __future__ import annotations

import json
import sqlite3
import threading
import unittest
from datetime import datetime, timezone

from coursebook import generation as gen
from tests.test_generation import (
    FakeSearch,
    excerpt_quote_from,
    plan_fixture,
    plan_job,
    response,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)


def enriched_plan(*, source_ids: tuple[str, ...] = (), source_quote: str = "") -> dict:
    """The recorded café plan plus two objectives, so its claim set needs a third pass.

    Six objectives plus the learner outcome is seven claims: the two criteria passes carry three
    each and the remainder becomes a claim-only pass — the "pass 3" this card names. Everything
    else (through-line, time estimate, media declarations, checks) stays the recorded fixture's.
    """
    plan = plan_fixture("plan_ja", source_ids, source_quote=source_quote)
    media_need = {
        "construct": "",
        "image": {"level": "none", "role": "none"},
        "audio": {"level": "none", "role": "none"},
    }
    plan["objectives"].extend(
        [
            {
                "ordinal": 5,
                "title": "Ask for the bill at the end of the café visit",
                "evidence_target": "production",
                "evidence_criteria": [
                    "Names the bill request",
                    "Uses a polite request form",
                ],
                "support": "unverified",
            },
            {
                "ordinal": 6,
                "title": "Recognize the written drink-size words 小 / 中 / 大",
                "evidence_target": "comprehension",
                "evidence_criteria": [
                    "Matches each written size word to small, medium or large",
                ],
                "support": "unverified",
            },
        ]
    )
    plan["sections"].extend(
        [
            {
                "ordinal": 5,
                "title": "Paying and leaving",
                "lesson_intent": (
                    "Model the bill request, then have the learner ask for the bill politely."
                ),
                "media_need": dict(media_need),
                "objective_refs": [5],
                "context_needs": ["romaji", "english meaning"],
                "source_ids": [],
            },
            {
                "ordinal": 6,
                "title": "Reading size words",
                "lesson_intent": (
                    "Show the three written size words, then have the learner match each to a size."
                ),
                "media_need": dict(media_need),
                "objective_refs": [6],
                "context_needs": ["furigana", "english meaning"],
                "source_ids": [],
            },
        ]
    )
    plan["check_plan"].extend(
        [
            {
                "objective_ref": 5,
                "kind": "quiz",
                "evidence_target": "production",
                "count": 1,
                "independent_evidence": True,
            },
            {
                "objective_ref": 6,
                "kind": "quiz",
                "evidence_target": "comprehension",
                "count": 1,
                "independent_evidence": True,
            },
        ]
    )
    return plan


#: The plan the seam authors, and the ordered pass plan its claim set produces. Pass 3 is
#: identified by content (its criteria batch and its claim batch), never by thread arrival order.
PLANNED_PLAN = enriched_plan()
PASS_PLAN = gen._validation_pass_plan(gen.plan_claim_labels(PLANNED_PLAN))
TIMED_PASS = PASS_PLAN[2]
PASS_COUNT = len(PASS_PLAN)


def _pass_signature(request: gen.LLMRequest) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What this request judges: its own criteria batch and its own claim batch."""
    claim_enum = (
        ((request.schema or {}).get("properties", {}).get("claim_verdicts") or {})
        .get("items", {})
        .get("properties", {})
        .get("item", {})
        .get("enum")
        or ()
    )
    return gen.validation_pass_criteria(request), tuple(claim_enum)


class PassRetrySeam:
    """Author once; fail the third validation pass the given number of times, then answer it.

    The failure is raised as ``TimeoutError`` — the host seam's own shape — so ``_call_llm``
    translates it into the typed ``ProviderTimeout`` the job service would normally report as
    ``HOST_UNAVAILABLE``.
    """

    def __init__(self, *, fail_pass_three: int = 1) -> None:
        self._validation_answer = validation_from_fixture()
        self._lock = threading.Lock()
        self.remaining_failures = int(fail_pass_three)
        self.authoring_calls = 0
        self.timed_pass_calls = 0
        self.requests: list[gen.LLMRequest] = []

    def _plan_answer(self, request: gen.LLMRequest) -> gen.LLMResponse:
        payload = json.loads(request.input_text)
        source_ids = tuple(
            str(source.get("source_id"))
            for source in payload.get("sources") or []
            if source.get("source_id")
        )
        plan = enriched_plan(source_ids=source_ids, source_quote=excerpt_quote_from(request))
        return response(plan)

    def __call__(self, request: gen.LLMRequest) -> gen.LLMResponse:
        with self._lock:
            self.requests.append(request)
        if request.purpose == "coursebook.plan.generate":
            with self._lock:
                self.authoring_calls += 1
            return self._plan_answer(request)
        if not request.prompt_version.endswith(
            (gen.VALIDATION_REPAIR_PROMPT_SUFFIX, gen.TRUNCATION_REPAIR_PROMPT_SUFFIX)
        ) and _pass_signature(request) == TIMED_PASS:
            with self._lock:
                self.timed_pass_calls += 1
                fire = self.remaining_failures > 0
                if fire:
                    self.remaining_failures -= 1
            if fire:
                raise TimeoutError("validator pass 3 did not answer inside its deadline")
        return self._validation_answer(request)

    def validation_calls(self) -> list[gen.LLMRequest]:
        return [item for item in self.requests if item.purpose == "coursebook.plan.validate"]


class ValidationPassRetryTest(unittest.TestCase):
    """The acceptance case: a timeout on pass 3 buys one retry, not a second authoring cycle."""

    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        gen.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def run_plan(self, seam: PassRetrySeam) -> dict:
        return gen.run_plan_job(
            self.connection, plan_job(), seam, FakeSearch(), now=NOW
        )

    def merged_record(self, validation_id: str) -> dict:
        record = gen.validation_record(self.connection, validation_id)
        self.assertIsNotNone(record, "the passing review wrote no validation record")
        assert record is not None
        return record

    def test_one_timed_out_pass_is_retried_in_place(self) -> None:
        """A pass 3 timeout answers on the retry: attempt 1 passes, one retry entry, one author."""
        seam = PassRetrySeam(fail_pass_three=1)
        result = self.run_plan(seam)

        # The plan is validated, in the first attempt: a second authoring call would mean the
        # timeout was billed as an authoring failure instead of a pass retry.
        self.assertEqual(result["validation_verdict"], "pass", result.get("warnings"))
        self.assertTrue(result["plan_id"])
        self.assertEqual(seam.authoring_calls, 1, "the timeout triggered a second authoring call")
        self.assertEqual(seam.timed_pass_calls, 2, "pass 3 did not get exactly one retry")

        # Every pass was called once; the failed pass was called twice. Nothing else was re-run.
        self.assertEqual(
            len(seam.validation_calls()),
            PASS_COUNT + 1,
            [item.prompt_version for item in seam.validation_calls()],
        )

        record = self.merged_record(result["validation_id"])
        retries = record["pass_retries"]
        self.assertEqual(len(retries), 1, f"expected exactly one pass_retries entry: {retries}")
        entry = retries[0]
        self.assertEqual(entry["pass_index"], 2, "the retried pass is not the third pass")
        self.assertEqual(entry["pass_total"], PASS_COUNT)
        self.assertEqual(entry["outcome"], "answered")
        self.assertEqual(entry["attempts"], 2)
        self.assertEqual(entry["failed_attempt"]["error"], "ProviderTimeout")
        self.assertIn("deadline", entry["failed_attempt"]["message"])
        self.assertEqual(entry["retry"]["model"], "fake-validator")

        # A persisted plan really exists beside the record; the review is not a loose dict.
        stored = self.connection.execute(
            "SELECT COUNT(*) AS n FROM plans WHERE id = ?", (result["plan_id"],)
        ).fetchone()["n"]
        self.assertEqual(stored, 1)

    def test_a_retry_that_also_times_out_fails_the_stage(self) -> None:
        """The retry is bounded at one: a pass that stays slow still fails, after two calls."""
        seam = PassRetrySeam(fail_pass_three=2)
        with self.assertRaises(gen.ProviderTimeout) as raised:
            self.run_plan(seam)

        self.assertEqual(seam.authoring_calls, 1, "a failed retry triggered a second authoring call")
        self.assertEqual(seam.timed_pass_calls, 2, "the pass was retried more than once")
        # The failure names the pass it came from, which is what the operator record needs.
        self.assertEqual(getattr(raised.exception, "validation_pass_index", None), 2)
        merged = self.connection.execute(
            "SELECT COUNT(*) AS n FROM gen_validation_records WHERE pass_index = -1"
        ).fetchone()["n"]
        self.assertEqual(merged, 0, "a failed review must not be recorded as a pass")

    def test_a_contract_violation_is_not_retried(self) -> None:
        """A schema-gate rejection is a typed VALIDATION_FAILED, not a transport blip to re-run."""

        class RejectingSeam(PassRetrySeam):
            def __call__(self, request):
                if request.purpose == "coursebook.plan.validate":
                    with self._lock:
                        self.requests.append(request)
                    raise ValueError("answer violates the pass schema")
                return super().__call__(request)

        seam = RejectingSeam()
        with self.assertRaises(gen.ModelOutputInvalid):
            self.run_plan(seam)
        # One original call plus ``_call_llm``'s own bounded shape re-ask per pass; no second
        # round of passes, because an answered-but-invalid answer is not a lost pass.
        first_time = [
            item
            for item in seam.validation_calls()
            if item.prompt_version == gen.VALIDATION_PROMPT_VERSION
        ]
        self.assertEqual(len(first_time), PASS_COUNT, "a schema rejection was retried as a pass")
        self.assertEqual(
            len(seam.validation_calls()),
            2 * PASS_COUNT,
            "a schema rejection is the shape re-ask, not a pass retry",
        )

    def test_the_call_ceiling_sizes_one_retry_per_pass(self) -> None:
        """CP-015e: the worst legal path now includes the retry, or the fix aborts the run."""
        _, worst_legal = gen.plan_calls(PASS_COUNT)
        self.assertGreaterEqual(
            worst_legal,
            gen.PLAN_ATTEMPTS * (1 + 2 * PASS_COUNT),
            "the ceiling does not cover one retry per validation pass",
        )

        seam = PassRetrySeam(fail_pass_three=1)
        result = self.run_plan(seam)
        budget = result["usage"]["budget"]
        made = int(result["usage"]["calls"])
        self.assertLessEqual(
            made,
            int(budget["max_calls"]),
            "the retry ran past the declared call ceiling",
        )
        # The timed-out call charged no tokens and therefore has no usage row; the retry does.
        # So the honest total is author + one recorded row per pass: the retry occupies the slot
        # the lost call left empty, and it is still a real call the ceiling must cover.
        self.assertEqual(made, 1 + PASS_COUNT, "expected author, every pass, one retry")


if __name__ == "__main__":  # pragma: no cover - convenience
    unittest.main()
