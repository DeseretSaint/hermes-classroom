"""W2-2 — a cut lesson is re-asked once, and attempt 2 repairs the draft it was given.

Three measured defects, one card:

* **A cut lesson was reported as malformed JSON.** ``_parse_structured`` had no truncation signal
  while every validator did, so a lesson answer cut at ``max_tokens=4000`` raised
  ``GenerationRejected("lesson is not valid JSON")`` and failed the whole unit job after the unit's
  earlier sections had already been authored and paid for.
* **The lesson cap contradicted the prompt's own prose budget.** The prompt asks for 2-6 segments
  of up to 2 000 characters each; 4 000 completion tokens cannot hold that answer on a route that
  tokenises Japanese at roughly one token per character.
* **Attempt 2 rewrote the lesson from scratch.** It re-sent at most eight feedback lines and none of
  the draft, so the parts that had already passed were paid for twice — and a reason past the
  eighth was never told to the author at all.

The prompt/schema scan at the end is the regression guard for the fourth item: two stage
instructions named or forbade keys their own schema disagrees with (``independent_evidence`` in the
mastery directives, and a sourcing rule that forbade the plan's own declared ``support:
'unverified'`` gap).

Every test runs offline against a scripted seam. No provider is called and no answer is invented.
"""

from __future__ import annotations

import json
import re
import unittest

from coursebook import generation as gen
from coursebook import mastery_path
from coursebook import research
from tests.blueprint_support import narrowed_validation_answer
from tests.test_generation import (
    NOW,
    FakeLLM,
    FakeSearch,
    GenerationTestBase,
    fixture,
    lesson_from_request,
    plan_from_fixture,
    plan_fixture,
    plan_job,
    response,
    source_ids_from,
    validation_from_fixture,
)

#: JSON that starts and stops mid-string — the shape a cut answer arrives in.
CUT_LESSON = '{"section_title": "Ordering coffee", "segments": [{"kind": "model", "heading": "Why the pol'

#: The model that answered the measured calls (the host's configured author route).
MEASURED_MODEL = "deepseek-v4.1-flash-1017"


def cut_lesson(request: gen.LLMRequest) -> gen.LLMResponse:
    """An answer that consumed its whole completion budget and arrived mid-JSON."""
    return gen.LLMResponse(
        text=CUT_LESSON,
        parsed=None,
        provider="nous",
        model=MEASURED_MODEL,
        input_tokens=8000,
        output_tokens=int(request.max_tokens),
        cost_usd=0.03,
    )


def cut_once(after=None):
    """A seam that answers the first call cut and every later call normally."""
    later = after or lesson_from_request()
    calls = {"count": 0}

    def answer(request: gen.LLMRequest) -> gen.LLMResponse:
        calls["count"] += 1
        if calls["count"] == 1:
            return cut_lesson(request)
        return later(request)

    return answer


class LessonStageBase(GenerationTestBase):
    """The lesson job's own harness: an aligned validator script and the production budget."""

    def lesson_script(self, validate, generate=None) -> FakeLLM:
        def aligned(answer: dict):
            def _answer(request: gen.LLMRequest) -> dict:
                return narrowed_validation_answer(request, answer)

            return _answer

        if isinstance(validate, list):
            validate = [aligned(entry) if isinstance(entry, dict) else entry for entry in validate]
        elif isinstance(validate, dict):
            validate = aligned(validate)
        return FakeLLM(
            {
                "coursebook.lesson.generate": generate or lesson_from_request(),
                "coursebook.lesson.validate": validate,
            }
        )

    def run_lessons(self, plan_result: dict, llm: FakeLLM, job_id: str = "job-w22-lesson") -> dict:
        return gen.run_lesson_job(
            self.connection,
            {"job_id": job_id, "kind": "plan", "brief": {"plan_id": plan_result["plan_id"]}},
            llm,
            now=NOW,
        )

    def generation_requests(self, llm: FakeLLM) -> list[gen.LLMRequest]:
        return [r for r in llm.requests if r.purpose == "coursebook.lesson.generate"]


class CutLessonIsReaskedOnceTest(LessonStageBase):
    def test_a_lesson_cut_at_its_cap_is_re_asked_once_and_then_authored(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(
            validation_from_fixture(),
            generate=cut_once(),
        )

        result = self.run_lessons(plan_result, llm)

        requests = self.generation_requests(llm)
        self.assertEqual(len(requests), 5, "four sections plus the one re-ask of the cut answer")
        self.assertEqual(requests[0].prompt_version, gen.LESSON_PROMPT_VERSION)
        self.assertEqual(
            requests[1].prompt_version,
            gen.LESSON_PROMPT_VERSION + gen.TRUNCATION_REPAIR_PROMPT_SUFFIX,
            "the re-ask carries its own marked label, never the first-pass one",
        )
        self.assertIn("cut off", requests[1].instructions)
        self.assertEqual(len(result["lessons"]), 4)
        self.assertTrue(all(item["state"] == "validated" for item in result["lessons"]))

    def test_two_cut_lessons_are_a_typed_truncation_not_invalid_json(self) -> None:
        plan_result = self.approved_plan()
        llm = self.lesson_script(validation_from_fixture(), generate=cut_lesson)

        with self.assertRaises(gen.ModelOutputInvalid) as caught:
            self.run_lessons(plan_result, llm)

        error = caught.exception
        self.assertTrue(error.repair_attempted, "the re-ask was spent and the record says so")
        self.assertEqual(error.parse_outcome, "truncated")
        self.assertEqual(error.schema_name, "coursebook_lesson_v1")
        self.assertIn("cut off", str(error))
        self.assertIn("truncated:", str(error))
        # Before W2-2 this raised GenerationRejected("lesson is not valid JSON"), which named the
        # wrong cause and lost the section with no repair spent.
        self.assertNotIsInstance(error, gen.GenerationRejected)

        requests = self.generation_requests(llm)
        self.assertEqual(len(requests), 2, "exactly one re-ask, not a resample loop")
        self.assertEqual(
            requests[1].prompt_version,
            gen.LESSON_PROMPT_VERSION + gen.TRUNCATION_REPAIR_PROMPT_SUFFIX,
        )
        # Nothing was authored: the first section never produced a page.
        self.assertEqual(self.count("gen_lessons"), 0)

    def test_the_lesson_cap_covers_the_prose_the_prompt_asks_for(self) -> None:
        request = gen.build_lesson_request(
            plan={},
            section={"source_ids": []},
            objective=None,
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
        )
        self.assertEqual(request.max_tokens, gen.LESSON_OUTPUT_TOKENS)
        self.assertEqual(gen.LESSON_OUTPUT_TOKENS, 24000)
        self.assertIn("Segments: 2-6", request.instructions)
        # The prompt's stated prose budget: 2-6 segments of up to 2 000 characters. A cap below
        # that character count cannot hold the answer the prompt itself asks for on a route that
        # tokenises Japanese at roughly one token per character.
        self.assertGreaterEqual(request.max_tokens, 6 * 2000)


class AttemptTwoRepairsTheDraftTest(LessonStageBase):
    def test_lesson_attempt_two_carries_the_refused_draft_and_every_reason(self) -> None:
        plan_result = self.approved_plan()
        reject = validation_from_fixture("validation_reject_check")
        accept = validation_from_fixture()
        llm = self.lesson_script([reject, accept, accept, accept, accept])

        self.run_lessons(plan_result, llm)

        requests = self.generation_requests(llm)
        self.assertEqual(len(requests), 5)
        first, second = requests[0], requests[1]
        payload = json.loads(second.input_text)

        self.assertIn("previous_draft", payload, "attempt 2 is shown the draft it repairs")
        draft = payload["previous_draft"]
        self.assertEqual(draft["section_title"], json.loads(first.input_text)["section"]["title"])
        self.assertTrue(draft["segments"])
        self.assertIn("check", draft)
        self.assertIn("worked_example", draft)

        self.assertEqual(
            second.prompt_version, gen.LESSON_PROMPT_VERSION + gen.REVISION_PROMPT_SUFFIX
        )
        self.assertIn("repair of the previous draft", second.instructions)
        self.assertIn("do not restart the lesson", second.instructions)

        revision = payload["revision_instructions"]
        rejected = fixture("validation_reject_check")
        for entry in rejected["rejections"]:
            self.assertIn(entry["reason"], revision)
            self.assertIn(entry["fix_hint"], revision)
        # The reasons are the validator's, not the generic fallback the old path fell back to.
        self.assertNotIn("without itemised reasons", revision)

    def test_plan_attempt_two_carries_the_refused_draft(self) -> None:
        def uncovered_objective(request: gen.LLMRequest) -> gen.LLMResponse:
            plan = plan_fixture("plan_ja", source_ids_from(request))
            plan["check_plan"] = plan["check_plan"][:3]  # objective 4 loses its check
            return response(plan)

        llm = FakeLLM(
            {
                "coursebook.plan.generate": [uncovered_objective, plan_from_fixture()],
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(self.connection, plan_job(), llm, FakeSearch(), now=NOW)

        requests = [r for r in llm.requests if r.purpose == "coursebook.plan.generate"]
        self.assertEqual(len(requests), 2)
        payload = json.loads(requests[1].input_text)
        self.assertIn("previous_draft", payload)
        self.assertEqual(len(payload["previous_draft"]["check_plan"]), 3)
        self.assertEqual(
            requests[1].prompt_version, gen.PLAN_PROMPT_VERSION + gen.REVISION_PROMPT_SUFFIX
        )
        self.assertIn("repair of the previous draft", requests[1].instructions)

        revision = payload["revision_instructions"]
        self.assertTrue(revision.startswith("The plan broke required rules:"))
        self.assertGreaterEqual(revision.count("\n- "), 1, "the rule reasons travel with the draft")
        self.assertEqual(result["validation_verdict"], "pass")

    def test_feedback_keeps_every_reason_not_the_first_eight(self) -> None:
        verdict = {
            "rejections": [
                {
                    "item": f"objective:{index}",
                    "criterion": "source_support",
                    "reason": f"reason number {index}",
                }
                for index in range(1, 13)
            ]
        }
        text = gen._feedback(verdict)
        for index in range(1, 13):
            self.assertIn(f"reason number {index}", text)
        # CP-015g states the hint-application rule once ahead of the item blocks; the twelve
        # rejections still travel in full, so the count is the rule plus every reason.
        self.assertIn("Apply every 'fix' hint literally", text)
        self.assertEqual(text.count("\n- "), 13)


# ── Prompt/schema agreement ──────────────────────────────────────────────────


def _property_keys(node, found: set[str]) -> set[str]:
    """Every JSON object property name declared anywhere inside one schema."""
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            found.update(str(key) for key in properties)
            for value in properties.values():
                _property_keys(value, found)
        for key in ("items", "additionalProperties", "oneOf", "anyOf", "allOf", "$defs"):
            if key in node:
                _property_keys(node[key], found)
    elif isinstance(node, list):
        for item in node:
            _property_keys(item, found)
    return found


#: Every key any generation/validation schema in this module spells. The scan's question is not
#: "is this a key?" but "does this stage's own schema allow the key its prompt names?", so the
#: vocabulary has to include the keys another version of the contract carries — that is exactly how
#: ``independent_evidence`` slipped into the v2 plan prompt.
KEY_VOCABULARY: set[str] = set()
for _schema in (
    gen.OBJECTIVE_SCHEMA,
    gen.SECTION_SCHEMA,
    gen.CHECK_PLAN_SCHEMA,
    gen.CHECK_PLAN_SCHEMA_V2,
    gen.PLAN_SCHEMA_V1,
    gen.PLAN_SCHEMA_V2,
    gen.UNIT_SECTIONS_SCHEMA,
    gen.LESSON_SCHEMA,
    gen.VALIDATION_SCHEMA,
):
    _property_keys(_schema, KEY_VOCABULARY)
#: Only compound (snake_case) names are scanned. ``goal``, ``check``, ``sources`` and ``value`` are
#: property names *and* ordinary English words, so a scan that matched them would report prose as a
#: field reference and prove nothing. A compound name (``independent_evidence``, ``source_quote``,
#: ``objective_ref``) is how a prompt addresses a JSON field it is not discussing as a concept, and
#: that is the shape the measured contradiction had.
KEY_VOCABULARY = {key for key in KEY_VOCABULARY if "_" in key and len(key) > 3}

#: Cues that mark a mention as a prohibition ("do not emit count or independent_evidence") rather
#: than an instruction to author the field. The prompt legitimately forbids keys a schema lacks.
_PROHIBITION = re.compile(
    r"\b(do not|don't|never|must not|may not|cannot|not|without|no)\b", re.IGNORECASE
)


def _sentences(text: str) -> list[str]:
    lines: list[str] = []
    for line in str(text or "").splitlines():
        lines.extend(part for part in re.split(r"(?<=\.)\s+", line) if part.strip())
    return lines


def _asks_for(sentence: str, key: str) -> bool:
    """Does this sentence name *key* outside a prohibition?"""
    for match in re.finditer(rf"(?<![a-z0-9_]){re.escape(key)}(?![a-z0-9_])", sentence):
        if not _PROHIBITION.search(sentence[: match.start()]):
            return True
    return False


class PromptSchemaAgreementTest(unittest.TestCase):
    """No stage instruction may ask for a key its own schema rejects.

    Two measured contradictions (W2-2): ``mastery_path.plan_policy_lines`` told the v2 plan author
    that "a gate check writes independent_evidence", which ``PLAN_SCHEMA_V2``'s check_plan entry
    forbids and the enforce gate rejects; and ``_plan_sourcing_rules`` told the author never to
    leave an objective at ``support: 'unverified'``, contradicting the declared-gap contract those
    same instructions and the validator are built around.
    """

    def stages(self) -> list[tuple[str, gen.LLMRequest]]:
        run = research.ResearchRun(
            status="unavailable", queries=[], sources=[], reason="no search seam in this test"
        )
        plan_v1 = gen.build_plan_request(
            goal="Order coffee in Japanese",
            recipe="committed",
            dials={},
            locale="ja-JP",
            research_run=run,
        )
        plan_v2 = gen.build_plan_request(
            goal="Order coffee in Japanese",
            recipe="committed",
            dials={},
            locale="ja-JP",
            research_run=run,
            scope="short",
        )
        lesson = gen.build_lesson_request(
            plan={},
            section={"source_ids": []},
            objective=None,
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
        )
        lesson_repair = gen.build_lesson_request(
            plan={},
            section={"source_ids": []},
            objective=None,
            recipe="casual",
            dials={},
            locale=None,
            sources=[],
            feedback="fix this",
            previous_draft={"section_title": "x", "segments": []},
        )
        plan_repair = gen.build_plan_request(
            goal="Order coffee in Japanese",
            recipe="committed",
            dials={},
            locale="ja-JP",
            research_run=run,
            scope="short",
            feedback="fix this",
            previous_draft={"title": "x", "objectives": []},
        )
        return [
            ("plan v1", plan_v1),
            ("plan v2", plan_v2),
            ("plan v2 repair", plan_repair),
            ("lesson", lesson),
            ("lesson repair", lesson_repair),
        ]

    def test_no_stage_instruction_names_a_key_its_schema_forbids(self) -> None:
        for name, request in self.stages():
            schema = request.schema or {}
            permitted = _property_keys(schema, set())
            forbidden = sorted(KEY_VOCABULARY - permitted)
            violations: list[str] = []
            for sentence in _sentences(request.instructions):
                for key in forbidden:
                    if _asks_for(sentence, key):
                        violations.append(f"{name} asks for {key!r}: {sentence.strip()}")
            self.assertEqual(violations, [], "\n".join(violations))

    def test_the_scan_can_still_see_a_contradiction(self) -> None:
        """The guard must fail on the text W2-2 removed, or it proves nothing."""
        sentence = "A gate check writes independent_evidence and a delayed check writes more."
        self.assertTrue(_asks_for(sentence, "independent_evidence"))
        prohibition = "Do not emit count or independent_evidence."
        self.assertFalse(_asks_for(prohibition, "independent_evidence"))

    def test_the_mastery_directives_no_longer_ask_for_a_forbidden_field(self) -> None:
        text = " ".join(mastery_path.plan_policy_lines())
        self.assertNotIn("independent_evidence", text)
        self.assertIn("check_plan entry carries objective_ref, kind and evidence_target", text)

    def test_the_sourcing_rules_allow_a_declared_gap(self) -> None:
        rules = " ".join(gen._plan_sourcing_rules())
        self.assertNotIn("do not leave it at support 'unverified'", rules)
        self.assertIn("declared gap", rules)
        self.assertIn("set support to 'unverified'", rules)


if __name__ == "__main__":
    unittest.main()
