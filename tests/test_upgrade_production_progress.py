"""Upgrade 22: a production or procedure objective can never reach independent evidence.

The defect this pins (``docs/UPGRADES-50-2026-11-14.md`` item 22): ``CHECK_KIND_BY_TARGET`` maps
``procedure`` to a verification checklist and ``production`` to a checklist or an observation. A
checklist answer takes the confirmation lane, which stamps ``evidence_class = "self_reported"``
(``grading.CONFIRMATION_EVIDENCE_CLASS``), and ``domain._commit_attempt`` writes a layer-2 row
only for a ``cold`` pass. So no answer to that lane can ever reach ``independent_evidence``: the
objective stays ``introduced`` forever, ``sections_done`` never counts it, and the card reports a
section that the learner can never finish.

The decision this module holds, stated once in ``generation.SELF_REPORT_ONLY_TARGETS``:

* ``procedure`` has no verified lane in this build (a quiz about the act is refused, and the
  recorded-take assessor is unbuilt), so a procedure objective is **practice**: the tick-list keeps
  recording the learner's own report at layer 1, and the objective is excluded from
  ``sections_done`` / ``sections_total`` instead of being a permanently unfinished section.
* ``production`` is practice too *unless* its check declares a hidden conversation practice, which
  ``conversation.grade_transcript`` grades provider-free from the stored learner turns and which
  does reach layer 2 on a cold pass.

What must never happen — and the adversarial note on the card says so — is a ticked checklist
granting independent evidence. These cases assert the honest outcome: the pass stays
``self_reported`` with no layer-2 row, and the progress count stops promising a section it can
never count.
"""

from __future__ import annotations

import json
import unittest

from coursebook import domain, generation

from tests.kernel_support import numeric_spec
from tests.test_checklist_confirmation import ChecklistConfirmationCase


class ProductionProgressCase(ChecklistConfirmationCase):
    """The one-off procedure course (four tick-lists), plus progress and library reads."""

    def authored(self) -> dict:
        return self.author(
            plan_name="plan_one_off", recipe="one_off", lesson_name="lesson_one_off"
        )

    def library_item(self, enrollment_id: str) -> dict:
        items = self.ok("library.list", {})["result"]["items"]
        matches = [item for item in items if item["enrollment_id"] == enrollment_id]
        self.assertEqual(len(matches), 1, items)
        return matches[0]

    def objective_state(self, objective_id: str) -> str:
        return str(self.scalar("SELECT state FROM objectives WHERE id = ?", (objective_id,)))

    def objective_target(self, objective_id: str) -> str:
        return str(self.scalar("SELECT evidence_target FROM objectives WHERE id = ?", (objective_id,)))

    def confirm_objective(self, authored: dict, index: int) -> dict:
        """Open the objective's check, tick every declared item, return the graded result."""

        opened = self.open_generated(authored, index)
        items = self.declared_items(opened)
        return self.confirm(opened, [item["id"] for item in items], key=f"key-confirm-{index}")


class ProcedureIsPracticeOnlyTest(ProductionProgressCase):
    """A passed tick-list is a self-report, and a self-report is not a section."""

    def test_a_production_objective_has_a_path_to_independent_evidence_or_is_not_counted(self) -> None:
        authored = self.authored()
        first = self.open_generated(authored, 0)
        self.assertEqual(self.objective_target(first["objective_id"]), "procedure")
        items = self.declared_items(first)
        result = self.confirm(first, [item["id"] for item in items])

        # The lane that exists: a pass, recorded as a self-report, never as evidence.
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "self_reported")
        self.assertEqual(result["next_action"], "review_objective")
        self.assertEqual(self.layer2_rows(authored["enrollment_id"]), 0)
        self.assertEqual(self.objective_state(first["objective_id"]), "introduced")

        # The honest count: the objective is practice, so it is neither done nor outstanding.
        item = self.library_item(authored["enrollment_id"])
        self.assertEqual(item["sections_done"], 0, item["evidence_summary"])
        self.assertEqual(item["sections_total"], 0, item["evidence_summary"])
        self.assertEqual(item["checks_recorded"], 1)

        # And it is still a real section the learner works: the outline lists it.
        outline = self.ok(
            "course.outline", {"enrollment_id": authored["enrollment_id"]}
        )["result"]
        self.assertEqual(outline["total"], 4)
        self.assertIn("procedure", {row["evidence_target"] for row in outline["objectives"]})

    def test_a_fulfilled_practice_does_not_park_the_course_on_the_first_section(self) -> None:
        authored = self.authored()
        for index in range(4):
            opened = self.open_generated(authored, index)
            items = self.declared_items(opened)
            self.confirm(opened, [item["id"] for item in items], key=f"key-confirm-{index}")

        item = self.library_item(authored["enrollment_id"])
        # Every practice is finished; none of them claims evidence, so the count stays empty.
        self.assertEqual(item["sections_done"], 0)
        self.assertEqual(item["sections_total"], 0)
        self.assertEqual(item["checks_recorded"], 4)
        self.assertIsNone(item["evidence_summary"]["current_objective_id"])
        # The course is finished as practice rather than stuck on objective 1 forever.
        self.assertEqual(item["next_step"]["kind"], "complete")

        # The evidence tray must not demand the evidence the count no longer promises.
        inspected = self.ok(
            "evidence.inspect", {"enrollment_id": authored["enrollment_id"]}
        )["result"]
        kinds = [entry["kind"] for entry in inspected["l3"]["recommendations"]]
        self.assertNotIn("needs_independent_evidence", kinds, inspected["l3"])
        self.assertIn("practice section(s)", inspected["l3"]["recommendations"][0]["text"])
        # Layer 2 still tells the truth: no objective holds evidence.
        self.assertEqual(
            [row["independent"] for row in inspected["l2"]["objectives"]],
            [False, False, False, False],
        )

    def test_the_count_stops_at_the_first_unfinished_practice(self) -> None:
        authored = self.authored()
        first = self.open_generated(authored, 0)
        items = self.declared_items(first)
        self.confirm(first, [item["id"] for item in items], key="key-confirm-0")

        item = self.library_item(authored["enrollment_id"])
        # Objective 1 is done as practice; the shelf points at objective 2, not back at objective 1.
        second = self.scalar(
            "SELECT id FROM objectives WHERE plan_id = ("
            " SELECT plan_id FROM objectives WHERE id = ?) AND ordinal = 2",
            (first["objective_id"],),
        )
        self.assertEqual(item["evidence_summary"]["current_objective_id"], second)
        self.assertEqual(item["next_step"]["kind"] in ("start_lesson", "resume_lesson", "review_lesson"), True)


class EvidenceBearingTargetsStillCountTest(ProductionProgressCase):
    """The exclusion is targeted: a closed-lane objective keeps its place in the count."""

    def test_a_cold_pass_on_a_closed_lane_is_still_a_section(self) -> None:
        course = self.prepare_evidence_course()

        item = self.library_item(course["enrollment_id"])
        self.assertEqual(item["sections_total"], 1)
        self.assertEqual(item["sections_done"], 0)

        self.pass_numeric(course)
        item = self.library_item(course["enrollment_id"])
        self.assertEqual(item["sections_done"], 1)
        self.assertEqual(item["sections_total"], 1)
        self.assertEqual(self.objective_state(course["objective_id"]), "independent_evidence")

    def test_a_declared_verified_lane_keeps_a_production_objective_in_the_count(self) -> None:
        """A production check with a hidden conversation practice *can* reach layer 2, so it counts.

        This is the other half of the card: "the objective either reaches independent_evidence
        through a verified lane or is excluded from the progress count". The practice lane is
        provider-free and grades the stored transcript, so a production objective that declares
        one is not practice-only.
        """

        course = self.prepare_evidence_course(target="production", practice=True)
        item = self.library_item(course["enrollment_id"])
        self.assertEqual(item["sections_total"], 1, item["evidence_summary"])

        # A visible practice is graded `hinted`, so it is not a verified lane and must not count.
        visible = self.prepare_evidence_course(target="production", practice=True, targets_visible=True)
        visible_item = self.library_item(visible["enrollment_id"])
        self.assertEqual(visible_item["sections_total"], 0, visible_item["evidence_summary"])

    # ── fixtures ────────────────────────────────────────────────────────────
    def prepare_evidence_course(self, *, target: str = "recall", practice: bool = False,
                                targets_visible: bool = False) -> dict:
        course_id, plan_id = self.new_course()
        enrollment_id = self.new_enrollment(course_id)
        if practice:
            # A practice objective declares no closed-form check spec: its only lane is the
            # conversation transcript, and the check below carries it.
            objective_id = domain.record_objective(
                plan_id,
                title="Order a drink",
                evidence_target=target,
                criteria=[{"id": "c1", "description": "Ordered a drink"}],
            )
        else:
            objective_id = self.seed_objective(
                plan_id, numeric_spec(), evidence_target=target
            )
        revision = self.approve(enrollment_id, plan_id, 0)
        if practice:
            self.write_check(objective_id, target=target, targets_visible=targets_visible)
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "enrollment_id": enrollment_id,
            "objective_id": objective_id,
            "revision": revision,
        }

    def write_check(self, objective_id: str, *, target: str,
                    targets_visible: bool) -> str:
        """Store one rubric-only check whose stimulus declares a conversation practice."""

        check_id = f"chk_{objective_id}"
        stimulus = {
            "prompt": "Order a drink.",
            "format": "text",
            "choices": [],
            "items": [],
            "learner_instructions": "Answer in one short turn.",
            "practice": {
                "scenario": "A cafe counter",
                "learner_role": "customer",
                "tutor_role": "barista",
                "turns": {"min": 3, "max": 5},
                "targets": [{"id": "t1", "label": "one drink, please"}],
                "targets_visible": targets_visible,
                "rubric_angle": "production",
                "opening": "Good morning.",
            },
        }
        reference = {
            "kind": "rubric_only",
            "reference_answer": "one drink, please",
            "accepted_answers": [],
            "accepted_alternatives": [],
        }
        rubric = {"criteria": [{"id": "c1", "description": "Ordered a drink", "met": False}]}
        self.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
            " rubric_json, reference_json, locale, audit_state, state, created_at, revisit)"
            " VALUES (?, ?, 1, ?, ?, ?, ?, NULL, 'passed', 'open', '2026-11-14T00:00:00Z', 0)",
            (
                check_id,
                objective_id,
                target,
                json.dumps(stimulus),
                json.dumps(rubric),
                json.dumps(reference),
            ),
        )
        return check_id

    def pass_numeric(self, course: dict) -> dict:
        opened = self.ok(
            "check.open",
            {"enrollment_id": course["enrollment_id"], "objective_id": course["objective_id"]},
            expected_revision=course["revision"],
        )["result"]
        response = self.submit(
            {
                "enrollment_id": course["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            "4",
        )
        self.assertTrue(response["ok"], response)
        return response["result"]


class DecisionGuardTest(unittest.TestCase):
    """The decision is stated once; a lane added for a practice-only target must revisit it."""

    def test_every_self_report_target_has_no_closed_lane(self) -> None:
        for target in generation.SELF_REPORT_ONLY_TARGETS:
            kinds = generation.CHECK_KIND_BY_TARGET.get(target) or ()
            self.assertTrue(kinds, target)
            self.assertNotIn("quiz", kinds, target)
            self.assertTrue(generation.is_self_report_only_target(target))

    def test_the_decision_covers_production_and_procedure_only(self) -> None:
        # A closed lane (quiz) is still a real lane; only the two performance targets are excluded.
        self.assertEqual(set(generation.SELF_REPORT_ONLY_TARGETS), {"production", "procedure"})
        for target in ("recall", "comprehension", "discrimination"):
            self.assertFalse(generation.is_self_report_only_target(target), target)
            self.assertIn("quiz", generation.CHECK_KIND_BY_TARGET[target])

    def test_the_progress_filter_reads_the_one_authority(self) -> None:
        sql, params = domain._progress_only_sql()
        self.assertEqual(set(params), set(generation.SELF_REPORT_ONLY_TARGETS))
        # The verified lane exception is the conversation practice: a stored practice block with
        # its targets hidden is the one production shape that can reach layer 2.
        self.assertIn("practice.targets_visible", sql)
        self.assertIn("NOT EXISTS", sql)

    def test_the_chat_surface_says_self_report_not_hint(self) -> None:
        # A ticked checklist was not helped; the honest reason it is not evidence is that the
        # learner reported it themselves. The hint wording would be a false reason.
        from coursebook import turn

        prompt = turn.continuation_prompt(
            verdict="pass", next_action="review_objective", evidence_class="self_reported"
        )
        self.assertIn("learner's own checklist report", prompt)
        self.assertNotIn("followed a hint", prompt)
        self.assertIn("move to the next section", prompt)


if __name__ == "__main__":
    unittest.main()
