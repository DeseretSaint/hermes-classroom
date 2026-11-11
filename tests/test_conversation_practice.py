"""Conversation practice: declaration, bounded session, transcript grading, refusals.

Every case runs against a real migrated database. The only simulation is the chat turn: a test
calls ``turn.pre_turn`` with text, exactly as the host hook does, instead of starting a model. The
grader is provider-free by construction, and ``test_aux_grader_not_consulted`` proves the aux lane
is never reached (docs/CONVERSATION-PRACTICE.md §12).
"""

from __future__ import annotations

import copy
import os
import unittest

from coursebook import api, bindings, db, domain, generation, grading, practice, turn, validators

# ``discover -s tests`` imports this module top-level (no parent package), so the relative form
# raises ImportError there and the suite counts a loader error as a failure. The package form is
# used, as every other module in ``tests/`` does.
from tests.kernel_support import KernelCase, criteria_with, request


def practice_declaration(*, visible: bool = True, turns=(3, 5), angle: str = "language_production"):
    return {
        "scenario": "Buying one train ticket at a station counter",
        "learner_role": "a traveller going to Kyoto",
        "tutor_role": "the station clerk",
        "turns": {"min": turns[0], "max": turns[1]},
        "targets": [
            {"id": "t1", "label": "one ticket to Kyoto, please"},
            {"id": "t2", "label": "how much is it?"},
        ],
        "targets_visible": visible,
        "rubric_angle": angle,
        "opening": "Welcome. Where are you travelling today?",
    }


def practice_key(*, turns=(3, 5), wildcard: bool = False):
    return {
        "kind": "conversation",
        "targets": [
            {"id": "t1", "match": [{"type": "exact", "value": "Kyoto"}]},
            {"id": "t2", "match": [{"type": "regex", "value": r"how much|ikura"}]},
        ],
        "min_turns": turns[0],
        "max_turns": turns[1],
    }


def practice_spec(*, visible: bool = True, turns=(3, 5), angle: str = "language_production"):
    declaration = practice_declaration(visible=visible, turns=turns, angle=angle)
    reference = validators.seal_reference(practice_key(turns=turns))
    return {
        "audit_state": "passed",
        "stimulus": {"prompt": "Practise buying a ticket.", "format": "text", "practice": declaration},
        "reference": reference,
        "rubric": practice.synthesize_rubric(declaration),
        "locale": "ja",
    }


class PracticeCase(KernelCase):
    def prepare_practice(self, *, recipe: str = "committed", spec: dict | None = None, visible: bool = True,
                         turns=(3, 5)):
        spec = spec or practice_spec(visible=visible, turns=turns)
        course_id, plan_id = self.new_course(recipe=recipe)
        objective_id = domain.record_objective(
            plan_id, title="Buy a train ticket", evidence_target="production",
            criteria=criteria_with(spec),
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        run = self.ok(
            "lesson.begin",
            {"enrollment_id": enrollment_id, "objective_id": objective_id, "mode": "fresh"},
            idempotency_key=f"key-begin-{os.urandom(4).hex()}",
        )["result"]
        self.session_id = f"sess-practice-{os.urandom(4).hex()}"
        bindings.bind_session(
            stored_session_id=self.session_id,
            enrollment_id=enrollment_id,
            objective_id=objective_id,
            lesson_run_id=run["lesson_run_id"],
            profile="tester",
        )
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": opened["revision"],
            "lesson_run_id": run["lesson_run_id"],
        }

    def start(self, lesson: dict) -> dict:
        return self.ok(
            "practice.start",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=lesson["revision"],
            idempotency_key=f"key-start-{os.urandom(4).hex()}",
        )["result"]

    def say(self, text: str, *, explicit: str | None = None):
        return turn.pre_turn(self.session_id, text, explicit=explicit)


class DeclarationTest(PracticeCase):
    def test_declaration_refusals(self):
        cases = [
            ("practice_malformed_declaration", lambda d: d.update({"scenario": ""})),
            ("practice_turn_range", lambda d: d.update({"turns": {"min": 2, "max": 6}})),
            ("practice_targets_invalid", lambda d: d.update({"targets": [d["targets"][0]]})),
            ("practice_rubric_off_profile", lambda d: d.update({"rubric_angle": "procedural"})),
        ]
        for reason, mutate in cases:
            spec = practice_spec()
            mutate(spec["stimulus"]["practice"])
            with self.subTest(reason=reason):
                course_id, plan_id = self.new_course()
                objective_id = domain.record_objective(
                    plan_id, title="Buy a ticket", evidence_target="production",
                    criteria=criteria_with(spec),
                )
                enrollment_id = self.new_enrollment(course_id)
                revision = self.approve(enrollment_id, plan_id, 0)
                error = self.err(
                    "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
                    expected_revision=revision,
                )
                self.assertEqual(error["details"]["reason"], reason)
                self.assertEqual(
                    self.scalar("SELECT COUNT(*) FROM checks WHERE objective_id = ?", (objective_id,)), 0
                )

    def test_check_shape_and_evidence_target(self):
        spec = practice_spec()
        spec["stimulus"]["format"] = "selection"
        with self.subTest("check shape"):
            course_id, plan_id = self.new_course()
            objective_id = domain.record_objective(
                plan_id, title="Buy a ticket", evidence_target="production", criteria=criteria_with(spec),
            )
            enrollment_id = self.new_enrollment(course_id)
            revision = self.approve(enrollment_id, plan_id, 0)
            error = self.err(
                "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
                expected_revision=revision,
            )
            self.assertEqual(error["details"]["reason"], "practice_check_shape")

        good = practice_spec()
        with self.subTest("evidence target"):
            course_id, plan_id = self.new_course()
            objective_id = domain.record_objective(
                plan_id, title="Recall", evidence_target="recall", criteria=criteria_with(good),
            )
            enrollment_id = self.new_enrollment(course_id)
            revision = self.approve(enrollment_id, plan_id, 0)
            error = self.err(
                "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
                expected_revision=revision,
            )
            self.assertEqual(error["details"]["reason"], "practice_evidence_target")

    def test_parent_recipe_refused(self):
        spec = practice_spec()
        course_id, plan_id = self.new_course(recipe="parent")
        objective_id = domain.record_objective(
            plan_id, title="Buy a ticket", evidence_target="production", criteria=criteria_with(spec),
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        error = self.err(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )
        self.assertEqual(error["details"]["reason"], "practice_not_available_for_recipe")

    def test_duplicate_practice_in_course(self):
        course_id, plan_id = self.new_course()
        first = domain.record_objective(
            plan_id, title="Buy a train ticket", evidence_target="production",
            criteria=criteria_with(practice_spec()),
        )
        second = domain.record_objective(
            plan_id, title="Second scene", evidence_target="production",
            criteria=criteria_with(practice_spec()),
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": first},
            expected_revision=revision,
        )["result"]
        error = self.err(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": second},
            expected_revision=opened["revision"],
        )
        self.assertEqual(error["details"]["reason"], "practice_duplicate_in_course")

    def test_generated_practice_check(self):
        declaration = practice_declaration()
        authored = {
            "check": {
                "kind": "quiz",
                "evidence_target": "production",
                "stimulus": {
                    "prompt": "Practise buying a ticket.", "format": "text",
                    "practice": {
                        **declaration,
                        "targets": [
                            {"id": "t1", "label": "one ticket to Kyoto, please",
                             "match": [{"type": "exact", "value": "Kyoto"}]},
                            {"id": "t2", "label": "how much is it?",
                             "match": [{"type": "regex", "value": r"how much|ikura"}]},
                        ],
                    },
                },
                "learner_instructions": "Talk to the clerk.",
                "reference_answer": "one ticket to Kyoto, please",
                "accepted_answers": ["one ticket to Kyoto, please", "how much is it?"],
                "rubric": [{"criterion": "target phrase", "weight": 1, "description": "x"}],
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "hinted"},
            }
        }
        payload = generation._check_payloads(authored, locale="ja", recipe="committed")
        self.assertEqual(payload["reference"]["kind"], "conversation")
        self.assertEqual(payload["reference"]["min_turns"], 3)
        self.assertNotIn("match", str(payload["stimulus"]["practice"]))
        self.assertEqual(len(payload["rubric"]["criteria"]), 3)
        self.assertNotIn("match", str(payload["stimulus"]["practice"]))
        self.assertNotIn("match", str(domain._practice_view(payload["stimulus"]["practice"])))
        hidden_authored = copy.deepcopy(authored)
        hidden_authored["check"]["stimulus"]["practice"]["targets_visible"] = False
        hidden = generation._check_payloads(hidden_authored, locale="ja", recipe="committed")
        hidden_view = domain._practice_view(hidden["stimulus"]["practice"])
        self.assertNotIn("label", str(hidden_view))
        self.assertNotIn("Kyoto", str(hidden_view["targets"]))
        with self.assertRaises(practice.PracticeDeclarationError) as caught:
            generation._check_payloads(
                authored, locale="ja", recipe="committed", practice_check_already=True
            )
        self.assertEqual(caught.exception.reason, "practice_duplicate_in_course")


class SessionTest(PracticeCase):
    def test_start_writes_opening_only(self):
        lesson = self.prepare_practice()
        before = self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))
        started = self.start(lesson)
        self.assertEqual(started["state"], "active")
        self.assertEqual(started["session_revision"], 1)
        self.assertEqual(started["revision"], before)
        self.assertEqual(len(started["transcript"]), 1)
        self.assertEqual(started["transcript"][0]["speaker"], "tutor")
        self.assertEqual(started["transcript"][0]["text"], "Welcome. Where are you travelling today?")
        again = self.start(lesson)
        self.assertEqual(again["session_id"], started["session_id"])
        self.assertEqual(again["session_revision"], 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM practice_sessions"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM practice_turns"), 1)

    def test_start_refusals(self):
        lesson = self.prepare_lesson()  # numeric check, not a practice
        error = self.err(
            "practice.start",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
            expected_revision=lesson["revision"],
            idempotency_key="key-start-numeric",
        )
        self.assertEqual(error["details"]["reason"], "practice_not_a_practice_check")

    def test_chat_turn_appends_once(self):
        lesson = self.prepare_practice()
        self.start(lesson)
        outcome = self.say("I would like one ticket to Kyoto, please.")
        self.assertIsNotNone(outcome.hook)
        self.assertIn("Coursebook practice is active", outcome.hook["context"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM practice_turns WHERE speaker = 'learner'"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        before = self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))
        with db.transaction() as connection:
            session = connection.execute("SELECT * FROM practice_sessions").fetchone()
            nonce = practice.turn_nonce("sess-practice-1", "again", int(session["revision"]))
            first, _ = practice.append_turn(connection, session, speaker="learner", text="again", nonce=nonce, now=db.utcnow())
            second, reason = practice.append_turn(connection, session, speaker="learner", text="again", nonce=nonce, now=db.utcnow())
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(reason, "duplicate_nonce")
        after = self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))
        self.assertEqual(before, after)

    def test_turn_limit(self):
        lesson = self.prepare_practice(turns=(3, 3))
        self.start(lesson)
        for text in (" Kyoto please", " how much is it?", " card ok"):
            self.say(text)
        outcome = self.say("one more")
        self.assertEqual(outcome.hook.get("action"), "block")
        self.assertIn("last turn", outcome.hook["message"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM practice_turns WHERE speaker = 'learner'"), 3)

    def test_end_before_min_turns(self):
        lesson = self.prepare_practice()
        self.start(lesson)
        self.say("Kyoto please")
        error = self.err(
            "practice.end",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"],
             "check_version": lesson["check_version"], "attempt_nonce": "nonce-end-0001"},
            expected_revision=lesson["revision"],
            idempotency_key="key-end-early-1",
        )
        self.assertEqual(error["details"]["reason"], "practice_not_complete")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT state FROM checks WHERE id = ?", (lesson["check_id"],)), "open")

    def test_end_empty_transcript(self):
        lesson = self.prepare_practice()
        self.start(lesson)
        error = self.err(
            "practice.end",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"],
             "check_version": lesson["check_version"], "attempt_nonce": "nonce-end-0002"},
            expected_revision=lesson["revision"],
            idempotency_key="key-end-empty-1",
        )
        self.assertEqual(error["details"]["reason"], "practice_empty_transcript")

    def test_cancel_keeps_turns(self):
        lesson = self.prepare_practice()
        started = self.start(lesson)
        self.say("Kyoto please")
        result = self.ok(
            "practice.cancel",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]},
            expected_revision=lesson["revision"],
        )["result"]
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(self.scalar("SELECT state FROM practice_sessions WHERE id = ?", (started["session_id"],)), "cancelled")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM practice_turns"), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT state FROM checks WHERE id = ?", (lesson["check_id"],)), "open")
        error = self.err(
            "practice.end",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"],
             "check_version": lesson["check_version"], "attempt_nonce": "nonce-end-0003"},
            expected_revision=lesson["revision"],
            idempotency_key="key-end-cancelled",
        )
        self.assertEqual(error["details"]["reason"], "practice_not_open")

    def test_detach_abandons_session(self):
        course_id, plan_id = self.new_course()
        first = domain.record_objective(
            plan_id, title="Buy a train ticket", evidence_target="production",
            criteria=criteria_with(practice_spec()),
        )
        second = domain.record_objective(
            plan_id, title="Second section", evidence_target="recall",
            criteria=criteria_with({
                "audit_state": "passed",
                "stimulus": {"prompt": "Say the number.", "format": "text"},
                "reference": {"kind": "exact", "answers": ["4"]},
                "rubric": {"criteria": [{"id": "c1", "description": "Correct value"}]},
            }),
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": first},
            expected_revision=revision,
        )["result"]
        lesson = {
            "enrollment_id": enrollment_id,
            "objective_id": first,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": opened["revision"],
        }
        run = self.ok(
            "lesson.begin", {"enrollment_id": enrollment_id, "objective_id": first, "mode": "fresh"},
            idempotency_key=f"key-begin-{os.urandom(4).hex()}",
        )["result"]
        self.session_id = f"sess-detach-{os.urandom(4).hex()}"
        bindings.bind_session(
            stored_session_id=self.session_id, enrollment_id=enrollment_id,
            objective_id=first, lesson_run_id=run["lesson_run_id"], profile="tester",
        )
        started = self.start(lesson)
        # A different section of the same course moves the chat: the superseded binding detaches,
        # and the practice session on that run is abandoned in the same transaction.
        second_run = self.ok(
            "lesson.begin", {"enrollment_id": enrollment_id, "objective_id": second, "mode": "fresh"},
            idempotency_key=f"key-begin-{os.urandom(4).hex()}",
        )["result"]
        bindings.bind_session(
            stored_session_id=self.session_id, enrollment_id=enrollment_id,
            objective_id=second, lesson_run_id=second_run["lesson_run_id"], profile="tester",
        )
        self.assertEqual(
            self.scalar("SELECT state FROM practice_sessions WHERE id = ?", (started["session_id"],)),
            "abandoned",
        )
        error = self.err(
            "practice.end",
            {"enrollment_id": enrollment_id, "check_id": opened["check_id"],
             "check_version": opened["check_version"], "attempt_nonce": "nonce-end-0004"},
            expected_revision=opened["revision"],
            idempotency_key="key-end-abandoned",
        )
        self.assertEqual(error["details"]["reason"], "practice_not_open")

    def test_restart_resumes(self):
        lesson = self.prepare_practice()
        started = self.start(lesson)
        self.say("Kyoto please")
        state = self.ok(
            "practice.state",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]
        self.assertEqual(state["session_id"], started["session_id"])
        self.assertEqual(state["learner_turns"], 1)
        self.assertEqual(state["remaining"], 4)
        self.assertTrue(state["awaiting_tutor"])
        self.assertEqual(len(state["transcript"]), 2)


class GradingTest(PracticeCase):
    def run_to_end(self, lesson: dict, texts: list[str]):
        self.start(lesson)
        for text in texts:
            self.say(text)
        return self.ok(
            "practice.end",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"],
             "check_version": lesson["check_version"], "attempt_nonce": f"nonce-end-{len(texts)}xx"},
            expected_revision=lesson["revision"],
            idempotency_key=f"key-end-{len(texts)}-{texts[0][:4]}",
        )["result"]

    def test_full_pass_visible_is_hinted(self):
        lesson = self.prepare_practice(visible=True)
        result = self.run_to_end(lesson, ["Kyoto please", "how much is it?", "thanks"])
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "hinted")
        self.assertEqual(result["next_action"], "review_objective")
        self.assertEqual(self.scalar("SELECT state FROM checks WHERE id = ?", (lesson["check_id"],)), "closed")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 1"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 2"), 0)
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],)), "introduced"
        )

    def test_hidden_targets_cold(self):
        lesson = self.prepare_practice(visible=False)
        result = self.run_to_end(lesson, ["Kyoto please", "how much is it?", "thanks"])
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "cold")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 2"), 1)
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],)),
            "independent_evidence",
        )
        observed = " ".join(str(row["observed"]) for row in result["criteria"])
        self.assertNotIn("Kyoto", observed)
        self.assertNotIn("how much", observed)

    def test_partial_and_not_yet(self):
        lesson = self.prepare_practice()
        partial = self.run_to_end(lesson, ["Kyoto please", "card ok", "thanks"])
        self.assertEqual(partial["verdict"], "partial")
        self.assertEqual(partial["next_action"], "retry_attempt")
        self.assertEqual(self.scalar("SELECT state FROM checks WHERE id = ?", (lesson["check_id"],)), "open")
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],)), "needs_review"
        )

        second = self.prepare_practice()
        zero_targets = self.run_to_end(second, ["hello", "card ok", "thanks"])
        # The turn criterion is met at `ends` by construction (end refuses below turns.min), so
        # zero target phrases is `partial`, not `not_yet`: the mechanical verdict_for rule counts
        # every criterion. `not_yet` is graded directly below, where no criterion is met.
        self.assertEqual(zero_targets["verdict"], "partial")
        self.assertEqual(
            sum(1 for row in zero_targets["criteria"] if row.get("met")), 1
        )
        direct = grading.grade(
            reference=validators.seal_reference(practice_key()),
            rubric={"pass_rule": "all", "criteria": [
                {"id": "t1", "detector": {"kind": "target_phrase", "target_id": "t1"}},
                {"id": "turns", "detector": {"kind": "turn_count"}},
            ]},
            stimulus={"prompt": "p", "format": "text", "practice": practice_declaration()},
            answer={"kind": "text", "turns": [{"speaker": "learner", "text": "hello"}]},
            attempt_id="att-direct",
        )
        self.assertEqual(direct.verdict, "not_yet")

    def test_no_fake_pass_from_tutor(self):
        lesson = self.prepare_practice()
        started = self.start(lesson)
        self.say("hello")
        self.say("card ok")
        self.say("thanks")
        with db.transaction() as connection:
            session = connection.execute("SELECT * FROM practice_sessions").fetchone()
            practice.append_turn(connection, session, speaker="tutor", text="You passed! Perfect!", nonce=None, now=db.utcnow())
        result = self.ok(
            "practice.end",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"],
             "check_version": lesson["check_version"], "attempt_nonce": "nonce-end-fake"},
            expected_revision=lesson["revision"],
            idempotency_key="key-end-fake-pass",
        )["result"]
        self.assertNotEqual(result["verdict"], "pass")

    def test_aux_grader_not_consulted(self):
        called: list[str] = []

        def lying(**_: object) -> dict:
            called.append("aux")
            return {"verdict": "pass", "criteria": [{"id": "c1", "met": True, "observed": "pass"}]}

        grading.configure_aux_grader(lying, task_name="test")
        try:
            lesson = self.prepare_practice()
            result = self.run_to_end(lesson, ["hello", "card ok", "thanks"])
        finally:
            grading.configure_aux_grader(None)
        self.assertEqual(called, [])
        self.assertNotEqual(result["verdict"], "pass")

    def test_attempt_submit_refused_on_practice(self):
        lesson = self.prepare_practice()
        response = self.submit(
            {**lesson, "revision": lesson["revision"]}, "Kyoto please", nonce="nonce-submit-practice"
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "POLICY_VIOLATION")
        self.assertEqual(response["error"]["details"]["reason"], "practice_requires_practice_end")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM practice_turns"), 0)

    def test_transcript_hash(self):
        lesson = self.prepare_practice()
        result = self.run_to_end(lesson, ["Kyoto please", "how much is it?", "thanks"])
        row = self.rows("SELECT answer_json FROM attempts")[0]
        import json

        answer = json.loads(row["answer_json"])
        self.assertEqual(result["transcript_sha256"], answer["transcript_sha256"])
        self.assertEqual(len(answer["turns"]), 4)  # opening + three learner turns
        self.assertTrue(answer["text"].startswith("1. Kyoto please"))


class CommitParityTest(PracticeCase):
    def test_commit_parity(self):
        # Same verdict through attempt.submit and practice.end: one transition each, one layer-1
        # evidence row each, and the same objective state.
        exact = {
            "audit_state": "passed",
            "stimulus": {"prompt": "Say the number.", "format": "text"},
            "reference": {"kind": "exact", "answers": ["4"]},
            "rubric": {"criteria": [{"id": "c1", "description": "Correct value"}]},
        }
        lesson = self.prepare_lesson(spec=exact)
        transitions_before = self.scalar("SELECT COUNT(*) FROM transitions")
        submitted = self.submit(lesson, "4").get("result")
        self.assertEqual(submitted["verdict"], "pass")
        submit_rows = (
            self.scalar("SELECT COUNT(*) FROM transitions") - transitions_before,
            self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 1 AND attempt_id = ?",
                        (submitted["attempt_id"],)),
        )

        practice_lesson = self.prepare_practice(visible=True)
        started = self.start(practice_lesson)
        for text in ("Kyoto please", "how much is it?", "thanks"):
            self.say(text)
        ended = self.ok(
            "practice.end",
            {"enrollment_id": practice_lesson["enrollment_id"], "check_id": practice_lesson["check_id"],
             "check_version": practice_lesson["check_version"], "attempt_nonce": "nonce-end-parity"},
            expected_revision=practice_lesson["revision"],
            idempotency_key="key-end-parity-1",
        )["result"]
        self.assertEqual(ended["verdict"], "pass")
        self.assertEqual(started["session_id"], self.scalar("SELECT id FROM practice_sessions"))
        self.assertEqual(self.scalar("SELECT state FROM practice_sessions"), "graded")
        self.assertEqual(
            self.scalar("SELECT attempt_id FROM practice_sessions"), ended["attempt_id"]
        )
        # Each entry point wrote exactly one transition and one layer-1 row for its attempt.
        self.assertEqual(submit_rows, (1, 1))
        practice_attempt_rows = self.scalar(
            "SELECT COUNT(*) FROM evidence WHERE layer = 1 AND attempt_id = ?", (ended["attempt_id"],)
        )
        self.assertEqual(practice_attempt_rows, 1)
