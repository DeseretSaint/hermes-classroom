"""cb.rpc v5 handler tests: the three commands CB-026 froze, driven through ``api.dispatch``.

``scripts/proof_contract_v5.py`` proves the happy paths against a real database; this module pins
the fences and refusals the contract text promises and a proof of composition cannot show: a
replayed ``lesson.assist`` key writes one row, a same-key/different-payload replay is a conflict, a
stale revision writes nothing, an assist is not a transition, and ``check.get``/``course.outline``
stay read-only at revision 0.
"""

from __future__ import annotations

import unittest

from coursebook import api, domain

from tests.kernel_support import KernelCase

FORBIDDEN = ("reference_answer", "reference", "reference_json", "rubric", "rubric_json",
             "accepted_answers", "grading_provenance", "check_spec")


def assist(self, lesson: dict, kind: str, *, key: str, revision: int | None = None) -> dict:
    return self.dispatch(
        "lesson.assist",
        {
            "enrollment_id": lesson["enrollment_id"],
            "objective_id": lesson["objective_id"],
            "kind": kind,
        },
        expected_revision=lesson["revision"] if revision is None else revision,
        idempotency_key=key,
    )


class LessonAssistHandlerTest(KernelCase):
    def test_a_replayed_key_returns_the_original_event_and_writes_one_row(self) -> None:
        lesson = self.prepare_lesson()
        first = assist(self, lesson, "hint_request", key="idem-assist-replay-1")
        self.assertTrue(first["ok"], first.get("error"))
        second = assist(self, lesson, "hint_request", key="idem-assist-replay-1")
        self.assertTrue(second["ok"], second.get("error"))
        self.assertEqual(second["result"], first["result"])
        self.assertEqual(second["revision"], first["revision"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 1)
        # The replay did not bump a second time.
        self.assertEqual(self.scalar("SELECT revision FROM enrollments"), lesson["revision"] + 1)

    def test_same_key_with_a_different_payload_is_a_conflict(self) -> None:
        lesson = self.prepare_lesson()
        first = assist(self, lesson, "hint_request", key="idem-assist-conflict-1")
        self.assertTrue(first["ok"], first.get("error"))
        lesson["revision"] = first["revision"]
        conflicting = assist(self, lesson, "answer_shown", key="idem-assist-conflict-1")
        self.assertFalse(conflicting["ok"])
        self.assertEqual(conflicting["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 1)

    def test_a_stale_expected_revision_writes_nothing(self) -> None:
        lesson = self.prepare_lesson()
        stale = assist(
            self, lesson, "hint_request", key="idem-assist-stale-1",
            revision=lesson["revision"] + 7,
        )
        self.assertFalse(stale["ok"])
        self.assertEqual(stale["error"]["code"], "STALE_REVISION")
        self.assertEqual(stale["error"]["current_revision"], lesson["revision"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)
        self.assertEqual(self.scalar("SELECT revision FROM enrollments"), lesson["revision"])

    def test_an_assist_is_not_a_transition(self) -> None:
        lesson = self.prepare_lesson()
        before = self.scalar("SELECT COUNT(*) FROM transitions")
        response = assist(self, lesson, "answer_shown", key="idem-assist-notrans-1")
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["result"]["evidence_class"], "answer_shown")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions"), before)
        event = self.rows("SELECT * FROM evidence WHERE id = ?", (response["result"]["event_id"],))[0]
        self.assertEqual(int(event["layer"]), 1)
        self.assertIsNone(event["attempt_id"])
        # The revision moved so an in-flight submit loses the fence.
        self.assertEqual(response["revision"], lesson["revision"] + 1)


class CheckGetHandlerTest(KernelCase):
    def test_the_stimulus_is_a_closed_allowlist_through_dispatch(self) -> None:
        lesson = self.prepare_lesson()
        smuggled = {
            "prompt": "Which expression is polite to a professor?",
            "format": "selection",
            "choices": ["ありがとう", "ありがとうございます"],
            "learner_instructions": "Choose one option.",
            "reference_answer": "ありがとうございます",
            "rubric": ["politeness"],
        }
        self.execute(
            "UPDATE checks SET stimulus_json = ? WHERE id = ?",
            (domain._json_dump(smuggled), lesson["check_id"]),
        )
        response = self.ok(
            "check.get", {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]}
        )
        self.assertEqual(response["revision"], 0, "a read carries the read revision")
        stimulus = response["result"]["stimulus"]
        self.assertEqual(stimulus["format"], "selection")
        self.assertEqual(stimulus["choices"], ["ありがとう", "ありがとうございます"])
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, stimulus)
            self.assertNotIn(forbidden, response["result"])

    def test_a_stimulus_without_a_prompt_is_refused_not_rendered_empty(self) -> None:
        lesson = self.prepare_lesson()
        self.execute(
            "UPDATE checks SET stimulus_json = ? WHERE id = ?",
            (domain._json_dump({"reference_answer": "4"}), lesson["check_id"]),
        )
        error = self.err(
            "check.get", {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]}
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"].get("reason"), "stimulus_missing_prompt")

    def test_unknown_check_is_not_found(self) -> None:
        lesson = self.prepare_lesson()
        error = self.err(
            "check.get", {"enrollment_id": lesson["enrollment_id"], "check_id": "chk_never_existed"}
        )
        self.assertEqual(error["code"], "NOT_FOUND")


class CourseOutlineHandlerTest(KernelCase):
    def test_the_outline_is_read_only(self) -> None:
        lesson = self.prepare_lesson()
        before_revision = self.scalar("SELECT revision FROM enrollments")
        before_transitions = self.scalar("SELECT COUNT(*) FROM transitions")
        response = self.ok("course.outline", {"enrollment_id": lesson["enrollment_id"]})
        self.assertEqual(response["revision"], 0)
        self.assertEqual(self.scalar("SELECT revision FROM enrollments"), before_revision)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions"), before_transitions)
        self.assertEqual(response["result"]["objectives"][0]["check_state"], "open")

    def test_the_objective_list_is_bounded_and_reports_the_true_total(self) -> None:
        course_id, plan_id = self.new_course()
        for _ in range(3):
            self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        result = self.ok("course.outline", {"enrollment_id": enrollment_id, "limit": 2})["result"]
        self.assertEqual(len(result["objectives"]), 2)
        self.assertEqual(result["total"], 3)
        self.assertTrue(result["truncated"])
        self.assertEqual([entry["ordinal"] for entry in result["objectives"]], [1, 2])

    def test_the_three_v5_methods_are_implemented(self) -> None:
        for method in ("course.outline", "check.get", "lesson.assist"):
            with self.subTest(method=method):
                self.assertIn(method, api.implemented_methods())
                self.assertIs(api.METHOD_HANDLERS.get(method), domain.HANDLERS[method])


if __name__ == "__main__":
    unittest.main()
