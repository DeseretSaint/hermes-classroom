"""CP-015j: a review section is authorable while its owner pages are parked ``needs_review``.

Reproduction: plan ``pln_5dde08c973f94cc0a444caa77a09d53c`` unit 1 stored owner sections for
objectives 1–3 and one review section reinforcing ``[1, 2, 3]``. The lesson stage authored all
three owners in ordinal order and parked every one ``needs_review`` (a truncated clause, answer
leakage, a ``source_support`` reject). A ``needs_review`` page closes its check, so
``_resolve_review_target`` found no *open* owner check and raised — and
``job_57a89f823d274b2ba7d769edd81eee0c`` ended ``VALIDATION_FAILED`` without ever authoring the
review section.

The unit is then stranded: the owners were authored first, in the required order, and nothing in
the message ("author the owner lessons first") can be satisfied differently. Fail-closed belongs to
*serving* evidence, not to the authoring job.

These cases pin the kernel rule: a closed owner check is still a real check, so the review page is
authored and parked ``needs_review`` with the closed owner checks named; the job completes. An
objective with no owner lesson at all remains a structural refusal, and a review over an approved
owner still binds the open check and validates.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation as gen

from tests.blueprint_support import NOW, blueprint_plan, response, unit_sections_document
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import FakeLLM, lesson_fixture, lesson_from_request, validation_from_fixture

T0 = NOW


def owner_check_payload() -> dict:
    """The exact stored-check projection of the Japanese fixture's quiz.

    Built by the kernel's own ``_check_payloads`` so the seeded row has the shape a real owner
    lesson writes. The reference answer is replaced with a token that never appears in the fixture
    narrative: this module isolates the *binding* rule, not the answer-leak rule, and the fixture
    prose legitimately names こんにちは.
    """
    lesson = lesson_fixture("lesson_ja")
    payloads = gen._check_payloads(
        lesson, locale=None, recipe="casual", practice_check_already=False
    )
    sealed = gen.validators.seal_reference(
        {
            "kind": "exact",
            "answers": ["zq7token"],
            "reference_answer": "zq7token",
            "accepted_answers": ["zq7token"],
            "accepted_alternatives": [],
        }
    )
    return {
        "stimulus": payloads["stimulus"],
        "reference": sealed,
        "rubric": payloads["rubric"],
        # The plan's objectives declare `comprehension`; the fixture check's own
        # `discrimination` target would make the capability policy judge the wrong lane.
        "evidence_target": "comprehension",
    }


class ClosedOwnerCheckCase(UnitStageCase):
    """An approved blueprint plan, a stored unit batch, and owner lessons in a chosen state."""

    def setUp(self) -> None:
        super().setUp()
        self.plan = blueprint_plan(scope="short", units=1, objectives_per_unit=3, reviews=[1])
        _course_id, self.plan_id = self.seed(self.plan)
        self.digest = gen.plan_hash(self.plan)
        self.store_sections()

    def store_sections(self) -> None:
        unit = self.plan["units"][0]
        document = unit_sections_document(
            unit=unit, objectives=self.plan["objectives"], reviews=1
        )
        with db.transaction() as connection:
            for index, section in enumerate(document["sections"], start=1):
                role = str(section.get("role") or "owner")
                refs = (
                    [int(section["primary_objective_ref"])]
                    if role == "owner"
                    else [int(ref) for ref in section.get("reinforces") or []]
                )
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                    " lesson_intent, media_need_json, objective_refs_json, context_needs_json,"
                    " source_ids_json, unit_id, section_role) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"sec_{index}",
                        self.plan_id,
                        index,
                        self.digest,
                        str(section["title"]),
                        str(section["lesson_intent"]),
                        json.dumps(section["media_need"]),
                        json.dumps(refs),
                        json.dumps(section.get("context_needs") or []),
                        json.dumps(section.get("source_ids") or []),
                        "unt_1",
                        role,
                    ),
                )

    def seed_owner_lesson(
        self,
        *,
        ordinal: int,
        lesson_state: str,
        check_state: str,
        with_check: bool = True,
    ) -> str:
        """Recreate exactly what a parked owner lesson leaves behind.

        A ``needs_review`` owner page is a real ``gen_lessons`` row with a real ``checks`` row,
        and that check is ``closed``. This is the stored shape the review section must bind.
        """
        lesson_id = f"lsn_owner_{ordinal}"
        check_id = f"chk_owner_{ordinal}"
        payload = owner_check_payload()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, rejection_reasons_json, created_at, updated_at)"
                " VALUES (?,?,?,?,1,?,?,?,?,?)",
                (
                    lesson_id,
                    self.plan_id,
                    f"sec_{ordinal}",
                    self.digest,
                    lesson_state,
                    json.dumps({"check": {"kind": "quiz"}}),
                    json.dumps(["seeded parked owner page"]),
                    T0.isoformat(),
                    T0.isoformat(),
                ),
            )
            if with_check:
                connection.execute(
                    "INSERT INTO checks (id, objective_id, version, evidence_target,"
                    " stimulus_json, rubric_json, reference_json, locale, audit_state, state,"
                    " created_at) VALUES (?,?,1,?,?,?,?,?,?,?,?)",
                    (
                        check_id,
                        f"obj_{ordinal}",
                        payload["evidence_target"],
                        json.dumps(payload["stimulus"]),
                        json.dumps(payload["rubric"]),
                        json.dumps(payload["reference"]),
                        "ja-JP",
                        "failed" if check_state != "open" else "passed",
                        check_state,
                        T0.isoformat(),
                    ),
                )
                connection.execute(
                    "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref)"
                    " VALUES (?,?,?)",
                    (lesson_id, check_id, ordinal),
                )
        return lesson_id

    def lessons_llm(self) -> FakeLLM:
        return FakeLLM(
            {
                "coursebook.lesson.generate": lesson_from_request(),
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )

    def run_lessons(self, llm: FakeLLM) -> dict:
        return gen.run_lesson_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": self.plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=self.plan_id,
            unit_ordinal=1,
            now=T0,
        )

    def review_lesson_row(self, review: dict) -> dict:
        lesson_id = review["lesson_id"]
        with db.read() as connection:
            row = connection.execute(
                "SELECT * FROM gen_lessons WHERE id = ?", (lesson_id,)
            ).fetchone()
        return dict(row)


class EveryOwnerParkedTest(ClosedOwnerCheckCase):
    """The measured shape: all three owners parked, the review still gets authored."""

    def setUp(self) -> None:
        super().setUp()
        self.owner_lessons = [
            self.seed_owner_lesson(ordinal=ordinal, lesson_state="needs_review", check_state="closed")
            for ordinal in (1, 2, 3)
        ]

    def test_the_job_completes_and_authors_the_review_section_parked(self) -> None:
        llm = self.lessons_llm()
        result = self.run_lessons(llm)

        self.assertEqual(result["sections_total"], 4)
        self.assertEqual(len(result["lessons"]), 4, "the review section is part of the unit")
        review = next(item for item in result["lessons"] if item["section_id"] == "sec_4")
        self.assertEqual(review["state"], "needs_review")
        self.assertFalse(review["check_enabled"])
        self.assertTrue(review["parked"])
        self.assertFalse(review["review_check_open"])
        self.assertIn("review section 4 presents a closed owner check", review["park_reason"])
        for ordinal in (1, 2, 3):
            self.assertIn(f"objective {ordinal}", review["park_reason"])
        self.assertIn("approve or regenerate the owner lessons", review["park_reason"])

    def test_the_review_page_is_stored_for_revision_and_serves_nothing(self) -> None:
        self.run_lessons(self.lessons_llm())
        with db.read() as connection:
            row = connection.execute(
                "SELECT * FROM gen_lessons WHERE section_id = 'sec_4'"
            ).fetchone()
            checks = connection.execute("SELECT COUNT(*) AS n FROM checks").fetchone()["n"]
            links = connection.execute("SELECT COUNT(*) AS n FROM gen_lesson_checks").fetchone()["n"]
        stored = dict(row)
        self.assertEqual(stored["state"], "needs_review")
        reasons = json.loads(stored["rejection_reasons_json"])
        self.assertTrue(reasons and reasons[0].startswith("review section 4 presents a closed owner check"))
        self.assertEqual(int(checks), 3, "a review authors no new check")
        self.assertEqual(int(links), 4, "the review links the owner check it presents")
        with self.assertRaises(gen.LessonNotAvailable):
            gen.learner_page(db.connect(), stored["id"])

    def test_the_owners_are_reused_not_re_authored_and_no_spend_is_wasted(self) -> None:
        llm = self.lessons_llm()
        self.run_lessons(llm)
        # Only the review section is authored; the three parked owners are reused as stored.
        self.assertEqual(llm.calls_for("coursebook.lesson.generate"), 1)
        self.assertEqual(llm.calls_for("coursebook.lesson.validate"), 1)

    def test_the_review_binds_the_first_closed_owner_check_deterministically(self) -> None:
        self.run_lessons(self.lessons_llm())
        with db.read() as connection:
            target = gen._resolve_review_target(
                connection, self.plan_id, {"ordinal": 4, "objective_refs": [1, 2, 3]}
            )
        self.assertFalse(target["check_open"])
        self.assertEqual(target["check_id"], "chk_owner_1")
        self.assertEqual(target["objective_ordinal"], 1)
        self.assertEqual(sorted(target["closed_refs"]), [1, 2, 3])
        self.assertEqual([item["lesson_id"] for item in target["closed_owner_checks"]], self.owner_lessons)


class OneOwnerApprovedTest(ClosedOwnerCheckCase):
    """The acceptance test's first clause: one open owner check still serves the review."""

    def setUp(self) -> None:
        super().setUp()
        self.seed_owner_lesson(ordinal=1, lesson_state="validated", check_state="open")
        self.seed_owner_lesson(ordinal=2, lesson_state="needs_review", check_state="closed")
        self.seed_owner_lesson(ordinal=3, lesson_state="needs_review", check_state="closed")

    def test_the_review_binds_the_open_owner_check_and_is_servable(self) -> None:
        result = self.run_lessons(self.lessons_llm())
        review = next(item for item in result["lessons"] if item["section_id"] == "sec_4")
        self.assertEqual(review["check_id"], "chk_owner_1")
        self.assertTrue(review["check_enabled"])
        self.assertTrue(review["review_check_open"])
        self.assertNotIn("parked", review)
        # The fixture run has no research, so a pass is `model_assessed`, never `validated`: the
        # point under test is that an open owner check makes the review servable at all.
        self.assertEqual(review["state"], "model_assessed")
        with db.read() as connection:
            row = connection.execute(
                "SELECT * FROM gen_lessons WHERE section_id = 'sec_4'"
            ).fetchone()
        self.assertEqual(dict(row)["state"], "model_assessed")


class FullAuthoringPathTest(ClosedOwnerCheckCase):
    """The measured path: the same lesson job authors the owners and then the review.

    The author answers with the Japanese fixture page whose guided segment states its own check's
    reference answer, so every owner lesson is refused by the deterministic leak gate on both
    attempts and parked ``needs_review`` with a closed check — exactly the stored shape of run 3.
    The review section must still be authored, and the job must complete.
    """

    def parked_author(self, request):
        base = lesson_from_request()(request)
        lesson = json.loads(base.text)
        for segment in lesson["segments"]:
            if segment.get("kind") == "guided":
                segment["body"] = segment["body"] + " The phrase to choose is こんにちは."
                segment["short"] = "The phrase to choose is こんにちは."
        return response(lesson, model="fake-author")

    def test_a_job_that_parks_every_owner_still_authors_the_review(self) -> None:
        llm = FakeLLM(
            {
                "coursebook.lesson.generate": self.parked_author,
                "coursebook.lesson.validate": validation_from_fixture(),
            }
        )
        result = self.run_lessons(llm)

        self.assertEqual(result["sections_total"], 4)
        self.assertEqual(len(result["lessons"]), 4)
        owners = [item for item in result["lessons"] if item["section_id"] != "sec_4"]
        self.assertEqual(len(owners), 3)
        for owner in owners:
            self.assertEqual(owner["state"], "needs_review")
            self.assertFalse(owner["check_enabled"])
        review = next(item for item in result["lessons"] if item["section_id"] == "sec_4")
        self.assertEqual(review["state"], "needs_review")
        self.assertTrue(review.get("parked"))
        self.assertIn("presents a closed owner check", review["park_reason"])
        with db.read() as connection:
            states = {
                row["section_id"]: row["state"]
                for row in connection.execute("SELECT section_id, state FROM gen_lessons")
            }
        self.assertEqual(states, {"sec_1": "needs_review", "sec_2": "needs_review",
                                  "sec_3": "needs_review", "sec_4": "needs_review"})


class NoOwnerLessonTest(ClosedOwnerCheckCase):
    """A review that predates its owners is still a structural refusal, with an honest message."""

    def test_a_review_with_no_owner_check_names_the_missing_owner_lessons(self) -> None:
        with db.read() as connection:
            with self.assertRaises(gen.GenerationRejected) as caught:
                gen._resolve_review_target(
                    connection, self.plan_id, {"ordinal": 4, "objective_refs": [1, 2, 3]}
                )
        message = str(caught.exception)
        self.assertIn("no owner lesson has authored a check", message)
        self.assertIn("author the owner lessons", message)

    def test_a_section_scoped_review_names_the_missing_objectives(self) -> None:
        """An owner with no check at all is named in the park reason, not hidden.

        A whole-unit job authors the missing owners first; a section-scoped regeneration authors
        only the review, so the mixed state is reachable and must be reported honestly.
        """
        self.seed_owner_lesson(ordinal=1, lesson_state="needs_review", check_state="closed")
        llm = self.lessons_llm()
        result = gen.run_lesson_job(
            db.connect(),
            {
                "job_id": None,
                "brief": {
                    "plan_id": self.plan_id,
                    "unit_ordinal": 1,
                    "section_id": "sec_4",
                    "regenerate": True,
                },
            },
            llm,
            plan_id=self.plan_id,
            unit_ordinal=1,
            now=T0,
        )
        review = next(item for item in result["lessons"] if item["section_id"] == "sec_4")
        self.assertEqual(review["state"], "needs_review")
        self.assertIn("objective 1", review["park_reason"])
        self.assertIn("[2, 3] have no owner check at all", review["park_reason"])


if __name__ == "__main__":
    unittest.main()
