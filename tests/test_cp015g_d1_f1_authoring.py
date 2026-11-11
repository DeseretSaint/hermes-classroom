"""CP-015g/D1-F1: a hands-on plan must evidence the performance, and a citation must carry it.

Two live runs of the CP-015g flow (`docs/cp015g-d1/run-live-12000.json`) authored a four-objective
Short plan for *"Set up a small backyard telescope and find and observe the moons of Jupiter on a
clear night"* in which every objective was `comprehension` and every check a quiz, and every
objective in the second unit was marked `sourced` against excerpts that do not carry the claim.
The independent validator refused both:

* "All checks are comprehension quizzes, so they cannot evidence the required hands-on setup,
  alignment, focusing, and centering performance."
* "It is marked sourced with three source_ids, but the supplied excerpts do not show how to
  distinguish Jupiter's moons from background stars."

These tests pin the two authoring rules that close that gap: a typed performance requirement shared
by the author and the validator, and a verbatim claim link on every `sourced` objective. The
deterministic half runs before validation, so a plan that breaks either is regenerated with the
reason instead of reaching the learner as a rejection.

Nothing here is a provider call or a hand-authored validator verdict.
"""

from __future__ import annotations

import unittest

from coursebook import curriculum
from coursebook import generation as gen
from coursebook import research

from tests.blueprint_support import blueprint_plan

GOAL = (
    "Set up a small backyard telescope and find and observe the moons of Jupiter on a clear night"
)
KNOWLEDGE_GOAL = (
    "Understand intervals, triads and the circle of fifths well enough to analyse a pop song."
)

EXCERPT_ONE = (
    "Jupiter's four largest moons appear as points of light in a line crossing the planet. "
    "Ganymede, Callisto, Io and Europa change position from night to night because they orbit "
    "Jupiter; a background star keeps the same position relative to the others."
)
EXCERPT_TWO = (
    "Note the time and date of each sketch. On a second night, sketch the same field again: "
    "the pattern changes because the moons move in their orbits, while field stars do not."
)


def _source(source_id: str, excerpt: str) -> research.SourceRecord:
    return research.SourceRecord(
        source_id=source_id,
        url=f"https://example.test/{source_id}",
        title=f"Recorded page {source_id}",
        publisher="example.test",
        source_type="web_page",
        fetched_at="2026-11-11T12:00:00Z",
        published_at=None,
        content_hash=research.sha256_of_text(excerpt),
        excerpt=excerpt,
    )


def _declared_plan() -> dict:
    """The live plan's shape: Short scope, two units, every objective comprehension."""
    plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2, recipe="casual")
    titles = [
        "Explain the safe setup steps and align the finder so a distant target stays centered",
        "Use a sky chart or planetarium app to locate Jupiter and place it in a low-power eyepiece",
        "Identify Jupiter's bright moons in the eyepiece and explain how to tell them from "
        "background stars",
        "Sketch the moons' positions on two different nights and explain why the pattern changes",
    ]
    for objective, title in zip(plan["objectives"], titles, strict=True):
        objective["title"] = title
    return plan


def _rules(plan: dict, *, goal: str | None = GOAL, recipe: str = "casual", ledger=()) -> None:
    gen.enforce_plan_rules(
        plan,
        recipe=recipe,
        dials={},
        locale=None,
        ledger=list(ledger),
        scope=plan.get("scope"),
        goal=goal,
    )


class PerformanceRequirementTest(unittest.TestCase):
    """The goal detector is a typed, deterministic block — not prose in one prompt."""

    def test_the_astronomy_goal_requires_a_performance(self) -> None:
        block = curriculum.performance_requirement(GOAL)
        self.assertIsNotNone(block)
        assert block is not None
        self.assertEqual(block["performance_families"], ["procedure", "transfer"])
        self.assertEqual(block["detected_action"], "set up")
        self.assertIn("procedure", block["rule"])

    def test_the_soldering_and_bicycle_goals_require_a_performance(self) -> None:
        for goal in (
            "Prepare for a first soldering repair on a through-hole PCB: safety, component "
            "placement, joints, inspection and desoldering.",
            "Walk me through replacing the inner tube on my road bike and checking the brakes "
            "before I ride it today.",
        ):
            with self.subTest(goal=goal[:30]):
                self.assertIsNotNone(curriculum.performance_requirement(goal))

    def test_a_knowledge_goal_does_not_require_a_performance(self) -> None:
        for goal in (
            KNOWLEDGE_GOAL,
            "Learn to order coffee and ask for the bill in Japanese",
            "Understand how the moons of Jupiter move without using a telescope",
            "Observe the rules of Japanese polite speech",
        ):
            with self.subTest(goal=goal[:30]):
                self.assertIsNone(curriculum.performance_requirement(goal))

    def test_a_weak_act_needs_a_physical_object(self) -> None:
        self.assertIsNotNone(curriculum.performance_requirement("Observe the moons on two nights"))
        self.assertIsNone(curriculum.performance_requirement("Observe the difference between two forms"))
        # A noun that is also an act ("mounts", "the wiring") is a topic, not a performance.
        self.assertIsNone(curriculum.performance_requirement("Understand the telescope mounts on the market"))
        self.assertIsNone(curriculum.performance_requirement("Learn about the wiring in a house"))
        self.assertIsNotNone(curriculum.performance_requirement("Mount the telescope on its tripod"))


class PlanPromptCarriesTheRuleTest(unittest.TestCase):
    """The author and the validator are told the same typed requirement."""

    def _requests(self):
        run = research.ResearchRun(
            status="ok",
            reason=None,
            queries=[],
            sources=[
                _source("src_moons", EXCERPT_ONE),
                _source("src_sketch", EXCERPT_TWO),
            ],
        )
        plan_request = gen.build_plan_request(
            goal=GOAL,
            recipe="casual",
            dials={},
            locale="en-US",
            research_run=run,
            scope="short",
        )
        validation_requests = gen.build_plan_validation_requests(
            plan=_declared_plan(),
            goal=GOAL,
            recipe="casual",
            dials={},
            locale="en-US",
            research_run=run,
            scope="short",
        )
        return plan_request, validation_requests

    def test_the_author_prompt_states_both_rules(self) -> None:
        request, _ = self._requests()
        self.assertEqual(request.prompt_version, gen.PLAN_PROMPT_VERSION_V2)
        text = request.instructions
        self.assertIn("carry out a physical act ('set up')", text)
        self.assertIn("At least one objective in the plan", text)
        self.assertIn("a quiz cannot evidence a performance", text)
        self.assertIn("'Optional' is about grading, not about form", text)
        self.assertIn("`source_ids` is a claim link, not a reading list", text)
        self.assertIn("Where a supplied excerpt does carry the claim, citing it is required", text)

    def test_the_payload_carries_the_typed_block_on_both_sides(self) -> None:
        request, validation_requests = self._requests()
        self.assertIn('"performance"', request.input_text)
        self.assertIn('"detected_action": "set up"', request.input_text)
        for validation in validation_requests:
            self.assertEqual(validation.prompt_version, gen.VALIDATION_PROMPT_VERSION)
            self.assertIn('"detected_action": "set up"', validation.input_text)
            self.assertNotEqual(validation.purpose, request.purpose)

    def test_a_knowledge_brief_carries_no_performance_block(self) -> None:
        run = research.ResearchRun(status="ok", reason=None, queries=[], sources=[])
        request = gen.build_plan_request(
            goal=KNOWLEDGE_GOAL,
            recipe="committed",
            dials={},
            locale="en-US",
            research_run=run,
            scope="short",
        )
        self.assertNotIn('"performance"', request.input_text)
        self.assertNotIn("carry out a physical act", request.instructions)


class PerformanceIsEnforcedNotJustStatedTest(unittest.TestCase):
    """The deterministic rule that closes the live defect."""

    def test_the_live_plan_is_refused_for_having_no_performance_objective(self) -> None:
        plan = _declared_plan()
        # The defect's shape: every objective comprehension, every check a quiz.
        self.assertEqual({obj["evidence_target"] for obj in plan["objectives"]}, {"comprehension"})
        self.assertEqual({item["kind"] for item in plan["check_plan"]}, {"quiz"})
        # Without the goal the same document breaks no rule: the refusal is about the goal.
        _rules(plan, goal=None)
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan)
        reasons = caught.exception.reasons
        self.assertTrue(
            any("no objective declares a 'procedure' or 'transfer'" in reason for reason in reasons),
            reasons,
        )

    def test_an_opening_unit_of_terminology_is_refused(self) -> None:
        plan = _declared_plan()
        plan["objectives"][2]["evidence_target"] = "procedure"
        plan["check_plan"][2]["evidence_target"] = "procedure"
        plan["check_plan"][2]["kind"] = "verification"
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan)
        self.assertTrue(
            any("unit 1 opens a course whose goal is a physical act" in reason
                for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_a_performed_plan_passes(self) -> None:
        plan = _declared_plan()
        plan["objectives"][0]["evidence_target"] = "procedure"
        plan["check_plan"][0]["evidence_target"] = "procedure"
        plan["check_plan"][0]["kind"] = "verification"
        _rules(plan)

    def test_a_knowledge_goal_keeps_a_quiz_plan_valid(self) -> None:
        plan = _declared_plan()
        _rules(plan, goal=KNOWLEDGE_GOAL)

    def test_a_parent_plan_is_not_forced_into_a_performance_family(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1, recipe="parent")
        plan["delivery"] = "parent_led"
        plan["parent"] = {
            "age_band": "8-10",
            "reading_level": "grade 3",
            "supervision_notes": "An adult holds the torch and sets the tripod height.",
            "hazards": ["Never look at the sun through the telescope."],
            "materials": ["a small telescope", "a torch"],
        }
        plan["check_plan"][0]["kind"] = "observation"
        _rules(plan, recipe="parent")


class CitationCarriesTheClaimTest(unittest.TestCase):
    """`source_ids` is a claim link: the cited excerpt must carry the quoted claim."""

    def _plan(self) -> dict:
        plan = _declared_plan()
        # One performance objective so the plan passes the performance rule and only the citation
        # rules are in play.
        plan["objectives"][0]["evidence_target"] = "procedure"
        plan["check_plan"][0]["evidence_target"] = "procedure"
        plan["check_plan"][0]["kind"] = "verification"
        return plan

    def _sourced(self, plan: dict, **overrides) -> dict:
        objective = plan["objectives"][2]
        objective["support"] = "sourced"
        objective["source_ids"] = ["src_moons", "src_sketch"]
        objective["source_quote"] = "the pattern changes because the moons move in their orbits"
        objective.update(overrides)
        return objective

    def test_a_sourced_objective_without_a_quote_is_refused(self) -> None:
        plan = self._plan()
        self._sourced(plan, source_quote=None)
        plan["objectives"][2].pop("source_quote", None)
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger=[_source("src_moons", EXCERPT_ONE), _source("src_sketch", EXCERPT_TWO)])
        self.assertTrue(
            any("without a source_quote" in reason for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_the_live_over_citation_is_refused(self) -> None:
        plan = self._plan()
        # The claim the validator refused: the excerpts do not show how to tell the moons from
        # background stars, yet three source ids were attached to it.
        self._sourced(
            plan,
            source_quote="a small refractor resolves the four Galilean moons as separate points",
        )
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger=[_source("src_moons", EXCERPT_ONE), _source("src_sketch", EXCERPT_TWO)])
        self.assertTrue(
            any("does not appear in the supplied excerpt" in reason
                for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_a_verbatim_quote_from_a_cited_excerpt_passes(self) -> None:
        plan = self._plan()
        self._sourced(plan)
        _rules(plan, ledger=[_source("src_moons", EXCERPT_ONE), _source("src_sketch", EXCERPT_TWO)])

    def test_the_quote_match_ignores_case_and_whitespace(self) -> None:
        plan = self._plan()
        self._sourced(plan, source_quote="THE PATTERN   CHANGES Because the moons move in their orbits")
        _rules(plan, ledger=[_source("src_moons", EXCERPT_ONE), _source("src_sketch", EXCERPT_TWO)])

    def test_quoting_an_uncited_source_is_refused(self) -> None:
        plan = self._plan()
        self._sourced(plan, source_ids=["src_moons"])
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger=[_source("src_moons", EXCERPT_ONE), _source("src_sketch", EXCERPT_TWO)])
        self.assertTrue(
            any("does not appear in the supplied excerpt" in reason
                for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_citing_without_marking_sourced_is_refused(self) -> None:
        plan = self._plan()
        objective = plan["objectives"][2]
        objective["source_ids"] = ["src_moons"]
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger=[_source("src_moons", EXCERPT_ONE)])
        self.assertTrue(
            any("but marks its support" in reason for reason in caught.exception.reasons),
            caught.exception.reasons,
        )

    def test_a_reason_is_regenerated_not_a_rejection(self) -> None:
        """The refusal lands in the author's feedback path, never in a fake validator record."""
        plan = self._plan()
        self._sourced(plan, source_quote="a phrase that no supplied excerpt contains")
        with self.assertRaises(gen._RuleViolation) as caught:
            _rules(plan, ledger=[_source("src_moons", EXCERPT_ONE)])
        feedback = "The plan broke required rules:\n- " + "\n- ".join(caught.exception.reasons)
        self.assertIn("unverified", feedback)

    def test_a_quoted_link_inside_the_excerpt_is_not_an_invented_citation(self) -> None:
        """A verbatim quote may contain a link the excerpt carries; it is not authored provenance."""
        excerpt = (
            "Moon positions are recorded on a sketch sheet, see https://example.test/sketch-sheet "
            "for the printable template, and the pattern changes because the moons move in orbit."
        )
        plan = self._plan()
        self._sourced(
            plan,
            source_quote="see https://example.test/sketch-sheet for the printable template",
        )
        _rules(plan, ledger=[_source("src_moons", excerpt)])



class ObjectiveSchemaCarriesTheClaimLinkTest(unittest.TestCase):
    def test_both_objective_schemas_expose_the_bound(self) -> None:
        for schema in (gen.OBJECTIVE_SCHEMA, gen.OBJECTIVE_SCHEMA_V2):
            properties = schema["properties"]
            self.assertIn("source_quote", properties)
            self.assertEqual(properties["source_quote"]["minLength"], 12)
            self.assertLessEqual(properties["source_quote"]["maxLength"], 300)
            self.assertNotIn("source_quote", schema["required"])


if __name__ == "__main__":
    unittest.main()
