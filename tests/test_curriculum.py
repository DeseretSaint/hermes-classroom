"""The curriculum brief is deterministic policy, not a second course engine.

These tests pin the parts that must not be lost: every non-survey course researches how the
subject is sequenced; a language course carries the frequency/coverage caveat; a procedure gets
task-analysis guidance; the brief reaches both the plan author and the independent validator.
"""

from __future__ import annotations

import json
import unittest

from coursebook import curriculum, generation, research


def unavailable_run() -> research.ResearchRun:
    return research.ResearchRun(
        status="unavailable",
        queries=[],
        sources=[],
        reason="test seam",
    )


class CurriculumBriefTest(unittest.TestCase):
    def test_a_language_brief_is_frequency_first_without_claiming_comprehension(self) -> None:
        brief = curriculum.curriculum_brief(
            domain="language", locale="ja-JP", level="L0", recipe="short"
        )
        self.assertEqual(brief["profile"], "frequency_and_communication")
        language = brief["language"]
        self.assertEqual(language["target_language"], "Japanese")
        self.assertTrue(language["frequency_first"])
        self.assertIn("Particles", language["function_words_are_grammar"])
        self.assertIn("95-98%", language["coverage_targets"])
        self.assertIn("80%", language["coverage_targets"])
        self.assertIn("not comprehension", brief["coverage_policy"].lower())

    def test_a_procedure_brief_asks_for_task_analysis_not_vocabulary(self) -> None:
        brief = curriculum.curriculum_brief(
            domain="technical_procedure", locale="en-US", level=None, recipe="one_off"
        )
        self.assertEqual(brief["profile"], "task_analysis_and_safety")
        self.assertNotIn("language", brief)
        self.assertIn("worked procedure", brief["procedure"]["order"])

    def test_an_undeclared_domain_falls_back_to_general_sequence_reasoning(self) -> None:
        brief = curriculum.curriculum_brief(
            domain=None, locale=None, level=None, recipe="casual"
        )
        self.assertEqual(brief["domain"], "general")
        self.assertEqual(brief["profile"], "backward_design_and_prerequisite")
        self.assertIn("prerequisite", brief["sequence_rule"].lower())


class CurriculumQueryTest(unittest.TestCase):
    def test_working_depth_asks_how_to_teach_and_what_comes_first(self) -> None:
        queries = research.derive_queries(
            "Order coffee politely",
            recipe="committed",
            dials={"depth": "working"},
            locale="ja-JP",
            subject_domain="language",
            level="L0",
        )
        joined = " | ".join(queries)
        self.assertIn("how to teach curriculum sequence", joined)
        self.assertIn("Japanese beginner curriculum high frequency vocabulary grammar order", joined)
        self.assertIn("L0 level learner vocabulary phrases", joined)

    def test_survey_remains_one_query_and_does_not_spend_the_budget(self) -> None:
        queries = research.derive_queries(
            "learn knots", recipe="casual", dials={"depth": "survey"}, max_queries=12
        )
        self.assertEqual(queries, ["learn knots"])

    def test_a_declared_non_language_domain_gets_prerequisite_research_not_language(self) -> None:
        queries = research.derive_queries(
            "Replace the front brake pads",
            recipe="committed",
            dials={"depth": "deep"},
            locale="es-MX",
            subject_domain="technical_procedure",
        )
        joined = " | ".join(queries)
        self.assertIn("prerequisite knowledge learning progression", joined)
        self.assertNotIn("Spanish beginner curriculum", joined)

    def test_the_budget_still_caps_the_extended_set(self) -> None:
        queries = research.derive_queries(
            "learn knots",
            recipe="casual",
            dials={"depth": "deep"},
            max_queries=2,
        )
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0], "learn knots")


class CurriculumReachesTheModelTest(unittest.TestCase):
    def test_plan_request_carries_the_brief_and_sequence_directives(self) -> None:
        request = generation.build_plan_request(
            goal="Order coffee politely",
            recipe="committed",
            dials={"depth": "working"},
            locale="ja-JP",
            research_run=unavailable_run(),
            level="L0",
            subject_domain="language",
            scope="short",
        )
        payload = json.loads(request.input_text)
        self.assertEqual(payload["curriculum"]["language"]["target_language"], "Japanese")
        self.assertIn("curriculum", payload)
        self.assertIn("Sequence units by prerequisite dependency", request.instructions)
        self.assertIn("Coverage is not comprehension", request.instructions)
        self.assertIn("particles, copulas and verb endings", request.instructions)

    def test_plan_validation_request_sees_the_same_brief_and_explicit_sequence_rule(self) -> None:
        planning = generation.build_plan_request(
            goal="Replace the front brake pads",
            recipe="casual",
            dials={"depth": "working"},
            locale="en-US",
            research_run=unavailable_run(),
            subject_domain="technical_procedure",
            scope="short",
        )
        plan = json.loads(planning.input_text)
        # The validator receives the brief, not a different policy inferred from the plan.
        request = generation.build_plan_validation_requests(
            plan={"plan_schema": generation.PLAN_SCHEMA_V2_NAME},
            goal="Replace the front brake pads",
            recipe="casual",
            dials={"depth": "working"},
            locale="en-US",
            research_run=unavailable_run(),
            subject_domain="technical_procedure",
            scope="short",
        )[0]
        payload = json.loads(request.input_text)
        self.assertEqual(payload["curriculum"]["profile"], "task_analysis_and_safety")
        self.assertIn("curriculum sequence", request.instructions)
        self.assertIn("no unit may require a concept taught later", request.instructions)
        self.assertNotIn("target_language", request.instructions)


if __name__ == "__main__":
    unittest.main()
