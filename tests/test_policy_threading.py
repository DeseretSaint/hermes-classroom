"""H-13: level, subject_domain and scope reach the plan runtime, not just the contract.

The cb.rpc v10 brief carries three declared inputs beside the four closed dials. H-01 proved the
wire and the database accept them. This file proves the *runtime* uses them:

* ``run_plan_job`` reads them from the brief and they appear in the plan prompt, the validator
  prompt and in the plan-time capability decision (never smuggled into ``dials``);
* the request fingerprint and the reuse cache include them, so two same-goal courses that differ
  only in ``subject_domain`` or ``level`` cannot reuse one another's plan document;
* ``locale`` (language of delivery) and ``subject_domain`` (what the course is about) stay
  separate: a Spanish brake-pad procedure is a technical procedure and a Japanese maths lesson is
  symbolic, in both directions;
* ``scope`` is recorded, stated in the prompt and capped deterministically on the plan's own time
  estimate — this branch has no second scope engine, and none is pretended;
* ``course.get`` and the plan document round-trip the declared values with no silent nulls.

Every case runs offline against the real migrated SQLite kernel with the deterministic fake
provider from ``tests.test_generation``. No provider spend, no invented output.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation as gen, policy, research

from tests.blueprint_support import (
    blueprint_plan,
    response as blueprint_response,
    validation_pass,
    validation_responder,
)
from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    NOW,
    lesson_from_request,
    validation_from_fixture,
)


def plan_job(
    *,
    course_id: str,
    goal: str = "Replace the front brake pads and torque the caliper to spec",
    recipe: str = "one_off",
    locale: str | None = "es-MX",
    level: str | None = "novice",
    subject_domain: str | None = "technical_procedure",
    scope: str | None = "single",
    dials: dict | None = None,
    job_id: str = "job-h13",
) -> dict:
    brief: dict = {
        "goal": goal,
        "recipe": recipe,
        "dials": dials if dials is not None else {},
        "locale": locale,
        "course_id": course_id,
    }
    for name, value in (("level", level), ("subject_domain", subject_domain), ("scope", scope)):
        if value is not None:
            brief[name] = value
    return {"job_id": job_id, "kind": "plan", "attempt_id": "attempt-1", "brief": brief}


def blueprint() -> dict:
    """A schema-valid blueprint plan for the default one-off, single-scope brief."""
    return blueprint_plan(scope="single", units=1, objectives_per_unit=1, recipe="one_off")


def plan_script(plan: dict | None = None) -> FakeLLM:
    plan = plan if plan is not None else blueprint()
    return FakeLLM(
        {
            "coursebook.plan.generate": blueprint_response(plan),
            "coursebook.plan.validate": validation_responder(
                blueprint_response, validation_pass()
            ),
        }
    )


class PolicyThreadingTest(KernelCase):
    # ── helpers ─────────────────────────────────────────────────────────────

    def create_course(self, **overrides) -> str:
        payload = {
            "title": "Replace the front brake pads",
            "recipe": "one_off",
            "goal": "Replace the front brake pads and torque the caliper to spec",
            "locale": "es-MX",
            "level": "novice",
            "subject_domain": "technical_procedure",
            "scope": "single",
            "dials": {},
        }
        payload.update(overrides)
        return self.ok("course.create", payload)["result"]["course_id"]

    def run_plan(self, job: dict) -> tuple[dict, FakeLLM]:
        llm = plan_script()
        connection = db.connect()
        try:
            return gen.run_plan_job(connection, job, llm, FakeSearch(), now=NOW), llm
        finally:
            connection.close()

    def plan_document(self, plan_id: str) -> dict:
        connection = db.connect()
        try:
            return gen.plan_document(connection, plan_id)
        finally:
            connection.close()

    def fingerprints(self, course_id: str) -> list[str]:
        connection = db.connect()
        try:
            rows = connection.execute(
                "SELECT request_fingerprint FROM gen_plan_documents WHERE course_id = ?"
                " ORDER BY rowid",
                (course_id,),
            ).fetchall()
        finally:
            connection.close()
        return [str(row["request_fingerprint"]) for row in rows]

    # ── 1. the declared inputs reach prompt, decision and record ────────────

    def test_declared_inputs_reach_the_plan_prompt_and_the_policy_decision(self) -> None:
        course_id = self.create_course()
        result, llm = self.run_plan(plan_job(course_id=course_id))

        request = llm.requests[0]
        self.assertEqual(request.purpose, "coursebook.plan.generate")
        payload = json.loads(request.input_text)
        # dials is a closed object: nothing from the brief was written into it.
        self.assertEqual(payload["dials"], {})
        self.assertNotIn("level", payload["dials"])
        self.assertNotIn("subject_domain", payload["dials"])
        # The declared inputs are their own fields.
        self.assertEqual(payload["level"], "novice")
        self.assertEqual(payload["subject_domain"], "technical_procedure")
        self.assertEqual(payload["scope"], "single")

        # The plan-time capability decision uses the declared domain, not the locale.
        decision = payload["capability_policy"]
        self.assertEqual(decision["subject_domain"], "technical_procedure")
        self.assertEqual(decision["locale"], "es-MX")
        self.assertEqual(decision["level"], "novice")
        self.assertEqual(decision["image"], "none")
        self.assertEqual(decision["audio"], "none")
        self.assertTrue(
            any("procedure intent names no sequence" in reason for reason in decision["reasons"]),
            decision["reasons"],
        )

        # …and the instructions state each input as itself, including the locale/domain split.
        text = request.instructions
        self.assertIn("Learner level: novice", text)
        self.assertIn("Subject domain: technical_procedure", text)
        self.assertIn("not the language it is delivered in", text)
        self.assertIn("Scope: single", text)
        self.assertIn("Content locale: es-MX", text)
        self.assertIn("Produce 1 to 1 unit(s) and 1 to 1 objective(s)", text)
        self.assertIn("Capability policy decision for these inputs", text)

        # The validator sees the same declared inputs.
        validator = [r for r in llm.requests if r.purpose == "coursebook.plan.validate"][0]
        validated = json.loads(validator.input_text)
        self.assertEqual(validated["subject_domain"], "technical_procedure")
        self.assertEqual(validated["level"], "novice")
        self.assertEqual(validated["scope"], "single")

        # The job result round-trips them.
        self.assertEqual(result["level"], "novice")
        self.assertEqual(result["subject_domain"], "technical_procedure")
        self.assertEqual(result["scope"], "single")
        self.assertEqual(result["scope_cap_weeks"], 1)

        # The plan document round-trips them, and its dials stay the four (here: empty).
        document = self.plan_document(result["plan_id"])
        self.assertEqual(document["level"], "novice")
        self.assertEqual(document["subject_domain"], "technical_procedure")
        self.assertEqual(document["scope"], "single")
        self.assertEqual(document["locale"], "es-MX")
        self.assertEqual(document["dials"], {})

        # `course.get` reads the same values from the same database.
        course = self.ok("course.get", {"course_id": course_id})["result"]["course"]
        self.assertEqual(course["level"], "novice")
        self.assertEqual(course["subject_domain"], "technical_procedure")
        self.assertEqual(course["scope"], "single")
        self.assertEqual(course["dials"], {})

    def test_a_course_created_by_the_plan_job_round_trips_the_same_values(self) -> None:
        # The desktop path creates the course in the plan job itself, not with course.create.
        job = plan_job(course_id="", job_id="job-h13-created")
        job["brief"].pop("course_id")
        result, _ = self.run_plan(job)
        course = self.ok("course.get", {"course_id": result["course_id"]})["result"]["course"]
        self.assertEqual(course["level"], "novice")
        self.assertEqual(course["subject_domain"], "technical_procedure")
        self.assertEqual(course["scope"], "single")
        self.assertEqual(course["dials"], {})

    # ── 2. the reuse cache is keyed on every capability input ──────────────

    def test_same_goal_different_subject_domain_never_reuses_the_plan(self) -> None:
        course_id = self.create_course(subject_domain="technical_procedure")
        first, _ = self.run_plan(plan_job(course_id=course_id, subject_domain="technical_procedure"))
        second, _ = self.run_plan(
            plan_job(course_id=course_id, subject_domain="language", job_id="job-h13-second")
        )
        self.assertFalse(first["reused"])
        self.assertFalse(second["reused"])
        self.assertNotEqual(first["plan_id"], second["plan_id"])
        prints = self.fingerprints(course_id)
        self.assertEqual(len(prints), 2)
        self.assertNotEqual(prints[0], prints[1])
        self.assertEqual(
            self.plan_document(second["plan_id"])["subject_domain"], "language"
        )

    def test_same_goal_different_level_never_reuses_the_plan(self) -> None:
        course_id = self.create_course(level="novice", subject_domain="language")
        first, _ = self.run_plan(plan_job(course_id=course_id, level="novice", subject_domain="language"))
        second, _ = self.run_plan(
            plan_job(course_id=course_id, level="advanced", subject_domain="language", job_id="job-h13-2")
        )
        self.assertFalse(first["reused"])
        self.assertFalse(second["reused"])
        self.assertEqual(len(self.fingerprints(course_id)), 2)
        self.assertEqual(self.plan_document(first["plan_id"])["level"], "novice")
        self.assertEqual(self.plan_document(second["plan_id"])["level"], "advanced")

    def test_a_retried_identical_brief_still_reuses_its_plan(self) -> None:
        # The cache must keep working for the honest case: same course, same declared inputs.
        course_id = self.create_course()
        first, _ = self.run_plan(plan_job(course_id=course_id))
        again, llm = self.run_plan(plan_job(course_id=course_id, job_id="job-h13-retry"))
        self.assertFalse(first["reused"])
        self.assertTrue(again["reused"])
        self.assertEqual(again["plan_id"], first["plan_id"])
        self.assertEqual(llm.requests, [])
        self.assertEqual(len(self.fingerprints(course_id)), 1)

    # ── 3. locale ≠ subject_domain, both directions ─────────────────────────

    def test_spanish_brake_pad_procedure_gets_a_deterministic_schematic(self) -> None:
        intent = "labelled schematic of the caliper with the torque sequence"
        section = {"ordinal": 1, "lesson_intent": intent, "objective_refs": [1]}
        objective = {"ordinal": 1, "evidence_target": "procedure"}

        declared = gen.lesson_capability_plan(
            recipe="one_off",
            section=section,
            objective=objective,
            locale="es-MX",
            dials={},
            plan={"subject_domain": "technical_procedure", "level": "novice"},
        )
        self.assertEqual(declared.subject_domain, "technical_procedure")
        self.assertEqual(declared.image, "required")
        self.assertEqual(declared.image_role, "schematic")
        self.assertEqual(declared.audio, "none")
        self.assertEqual(declared.rubric_profile, "procedural")
        # A realistic payload spelling reaches the same decision through the one alias table.
        self.assertEqual(policy.normalise_subject_domain("repair"), "technical_procedure")

        # The pre-v10 shape (locale only, no declared domain) inferred a language course from
        # the Spanish locale. That is the defect this branch closes; the domain is the input.
        inferred = policy.plan_lesson_capability(
            recipe="one_off",
            evidence_target="procedure",
            lesson_intent=intent,
            locale="es-MX",
        )
        self.assertEqual(inferred.subject_domain, "language")
        self.assertNotEqual(declared.to_dict(), inferred.to_dict())

    def test_japanese_math_lesson_keeps_symbolic_protection(self) -> None:
        intent = "an illustration of the derivation steps for the quadratic formula"
        section = {"ordinal": 1, "lesson_intent": intent, "objective_refs": [1]}
        objective = {"ordinal": 1, "evidence_target": "comprehension"}

        protected = gen.lesson_capability_plan(
            recipe="casual",
            section=section,
            objective=objective,
            locale="ja-JP",
            dials={},
            plan={"subject_domain": "mathematics", "level": "L0"},
        )
        self.assertEqual(protected.subject_domain, "mathematics")
        self.assertEqual(protected.image, "none")
        self.assertIsNone(protected.image_role)
        self.assertTrue(
            any("symbolic" in reason for reason in protected.reasons), protected.reasons
        )

        # A named graph may still become a deterministic schematic — never an illustration.
        graph = gen.lesson_capability_plan(
            recipe="casual",
            section={**section, "lesson_intent": "labelled graph of the function"},
            objective=objective,
            locale="ja-JP",
            dials={},
            plan={"subject_domain": "mathematics", "level": "L0"},
        )
        self.assertEqual(graph.image, "optional")
        self.assertEqual(graph.image_role, "schematic")

        # Locale alone said "language", which is what used to let the illustration through.
        inferred = policy.plan_lesson_capability(
            recipe="casual",
            evidence_target="comprehension",
            lesson_intent=intent,
            locale="ja-JP",
        )
        self.assertEqual(inferred.subject_domain, "language")
        self.assertNotEqual(protected.image, inferred.image)

    # ── 4. the lesson stage reads the same declared inputs ─────────────────

    def test_lesson_stage_inherits_the_plan_document_inputs(self) -> None:
        from tests.blueprint_support import unit_sections_document

        course_id = self.create_course()
        plan = blueprint()
        plan_result, _ = self.run_plan(plan_job(course_id=course_id))
        unit = plan["units"][0]
        objectives = [item for item in plan["objectives"] if int(item["unit_ref"]) == 1]
        connection = db.connect()
        try:
            connection.execute(
                "UPDATE plans SET state = 'approved', approved_at = ? WHERE id = ?",
                ("2026-11-06T12:05:00Z", plan_result["plan_id"]),
            )
            # The blueprint authors sections in the unit stage, after approval. The section
            # declares the required labelled schematic that lesson_one_off.json actually
            # produces, so the lesson is validated rather than left in review.
            sections_document = unit_sections_document(unit=unit, objectives=objectives)
            for section in sections_document["sections"]:
                section["media_need"] = {
                    "construct": "the labelled parts diagram of the caliper and its fastener",
                    "image": {"level": "required", "role": "schematic"},
                    "audio": {"level": "none", "role": "none"},
                }
            gen.run_unit_sections_job(
                connection,
                {"job_id": "job-h13-sections", "brief": {"plan_id": plan_result["plan_id"], "unit_ordinal": 1}},
                FakeLLM(
                    {
                        "coursebook.unit_sections.generate": blueprint_response(
                            sections_document
                        ),
                        "coursebook.unit_sections.validate": blueprint_response(validation_pass()),
                    }
                ),
                plan_id=plan_result["plan_id"],
                unit_ordinal=1,
                now=NOW,
            )
            lesson_llm = FakeLLM(
                {
                    "coursebook.lesson.generate": lesson_from_request("lesson_one_off"),
                    "coursebook.lesson.validate": validation_from_fixture(),
                }
            )
            gen.run_lesson_job(
                connection,
                {
                    "job_id": "job-h13-lessons",
                    "brief": {"plan_id": plan_result["plan_id"], "unit_ordinal": 1},
                },
                lesson_llm,
                now=NOW,
                budget=gen.CostBudget(max_calls=32),
            )
        finally:
            connection.close()

        generate = [r for r in lesson_llm.requests if r.purpose == "coursebook.lesson.generate"]
        self.assertTrue(generate)
        payload = json.loads(generate[0].input_text)
        self.assertEqual(payload["dials"], {})
        self.assertEqual(payload["level"], "novice")
        self.assertEqual(payload["subject_domain"], "technical_procedure")
        self.assertEqual(payload["capability_policy"]["subject_domain"], "technical_procedure")
        self.assertEqual(payload["capability_policy"]["locale"], "es-MX")
        self.assertEqual(payload["capability_policy"]["check_angle"], "verification")

    # ── 5. research asks about the subject, not the delivery language ──────

    def test_research_queries_use_the_subject_domain_not_the_locale(self) -> None:
        queries = research.derive_queries(
            "Replace the front brake pads",
            recipe="one_off",
            dials={"depth": "thorough"},
            locale="es-MX",
            subject_domain="technical_procedure",
        )
        self.assertEqual(queries[0], "Replace the front brake pads")
        self.assertIn(
            "Replace the front brake pads official procedure steps safety limits", queries
        )
        joined = " | ".join(queries).lower()
        self.assertNotIn("spanish", joined)
        self.assertNotIn("beginner guide", joined)
        self.assertNotIn("official instructions safety", joined)

        # A language course still researches in the target language, with its declared level.
        language = research.derive_queries(
            "Order coffee politely",
            recipe="committed",
            dials={"depth": "thorough"},
            locale="ja-JP",
            subject_domain="language",
            level="L0",
        )
        joined_language = " | ".join(language)
        self.assertIn("L0 level learner vocabulary phrases", joined_language)
        self.assertIn("Japanese", joined_language)

        # A declared domain with no qualifier falls back to the recipe query, not an invention.
        unknown = research.derive_queries(
            "Braise short ribs",
            recipe="committed",
            dials={},
            locale=None,
            subject_domain="cooking",
        )
        self.assertIn("Braise short ribs syllabus learning objectives", unknown)

        # The research-job worker carries the same declared inputs beside the closed dials.
        from coursebook import workers

        request = workers.ResearchRequest(
            goal="Replace the front brake pads",
            recipe="one_off",
            locale="es-MX",
            subject_domain="technical_procedure",
            level="novice",
        )
        brief = request.as_brief()
        self.assertEqual(brief["subject_domain"], "technical_procedure")
        self.assertEqual(brief["level"], "novice")
        self.assertEqual(brief["dials"], {})

    # ── 5. scope is recorded, stated and capped — no second engine ─────────

    def test_scope_caps_the_plan_time_estimate(self) -> None:
        from tests.test_generation import _unsourced, plan_fixture

        plan = _unsourced(plan_fixture("plan_ja"))
        weeks = plan["time_estimate"]["weeks"]
        with self.assertRaises(gen._RuleViolation) as raised:
            gen.enforce_plan_rules(
                plan, recipe="committed", dials={"level": "L0"}, locale="ja-JP",
                ledger=[], scope="single",
            )
        joined = " ".join(raised.exception.reasons)
        self.assertIn("scope 'single' caps the plan at 1 week(s)", joined)
        self.assertIn(f"the time estimate says {weeks} week(s)", joined)

        # `short` allows the same estimate: the cap is the scope's, not a blanket one.
        gen.enforce_plan_rules(
            plan, recipe="committed", dials={"level": "L0"}, locale="ja-JP",
            ledger=[], scope="short",
        )

    def test_an_unknown_scope_is_refused_before_any_provider_call(self) -> None:
        course_id = self.create_course(scope=None)
        llm = plan_script()
        connection = db.connect()
        try:
            with self.assertRaises(gen.GenerationRejected) as raised:
                gen.run_plan_job(
                    connection,
                    plan_job(course_id=course_id, scope="term"),
                    llm,
                    FakeSearch(),
                    now=NOW,
                )
        finally:
            connection.close()
        self.assertIn("unknown scope 'term'", str(raised.exception))
        self.assertEqual(llm.requests, [])

    def test_scope_is_stated_in_the_plan_instructions(self) -> None:
        text = gen._plan_instructions(
            recipe="committed",
            dials={},
            locale="ja-JP",
            research_status="ok",
            level="L0",
            subject_domain="language",
            scope="short",
        )
        self.assertIn("Scope: short", text)
        self.assertIn("within 8 week(s)", text)
        self.assertIn("Produce 4 to 6 objectives", text)
        self.assertIn("Subject domain: language", text)
        self.assertIn("Learner level: L0", text)


if __name__ == "__main__":
    unittest.main()
