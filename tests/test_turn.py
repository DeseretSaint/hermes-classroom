"""The pre-turn gate: classification, fail-closed grading, continuation, and fences.

Every test here runs through the real dispatcher and a real SQLite database: the gate is an
adapter over ``attempt.submit``, not a second implementation of it.
"""

from __future__ import annotations

import threading
import unittest
from unittest import mock

from coursebook import db, hooks, turn
from tests.kernel_support import KernelCase, numeric_spec

_STORED = "stored-lesson-1"


class GateCase(KernelCase):
    """A prepared lesson bound to one stored chat id."""

    def prepare_bound(self, spec: dict | None = None) -> dict:
        lesson = self.prepare_lesson(spec or numeric_spec("42.7"))
        run_id = "run_0001_test"
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, '2026-01-01T00:00:00+00:00',"
            " '2026-01-01T00:00:00+00:00', NULL)",
            (run_id, lesson["enrollment_id"], lesson["objective_id"]),
        )
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, cwd_fingerprint, compression_tip, status, revision, updated_at,"
            " lesson_run_id, objective_id) VALUES ('bnd_test', ?, 'cinder', 'conn-1', 'rt-1', ?,"
            " 'cwd-fp', NULL, 'active', 0, '2026-01-01T00:00:00+00:00', ?, ?)",
            (lesson["enrollment_id"], _STORED, run_id, lesson["objective_id"]),
        )
        lesson["run_id"] = run_id
        self.base_transitions = self.transitions()
        return lesson

    def transitions(self) -> int:
        return int(self.scalar("SELECT COUNT(*) FROM transitions") or 0)

    def new_transitions(self) -> int:
        return self.transitions() - int(getattr(self, "base_transitions", 0))


class ClassificationTest(unittest.TestCase):
    def classify(self, text: str, *, open_check: bool = True, explicit: str | None = None):
        return turn.classify_inbound(text, open_check=open_check, explicit=explicit)

    def test_plain_answer_inside_an_open_check_creates_an_attempt(self) -> None:
        decision = self.classify("42.7")
        self.assertEqual(decision.kind, "answer")
        self.assertTrue(decision.creates_attempt)

    def test_question_is_a_clarification_and_never_creates_an_attempt(self) -> None:
        for text in ("what does 計算 mean?", "I don't understand the task", "can you explain again", "why?"):
            decision = self.classify(text)
            self.assertEqual(decision.kind, "clarification", text)
            self.assertFalse(decision.creates_attempt, text)

    def test_hint_request_is_a_hint_not_an_answer(self) -> None:
        decision = self.classify("give me a hint")
        self.assertEqual(decision.kind, "hint")
        self.assertFalse(decision.shows_answer)

    def test_answer_request_shows_the_answer(self) -> None:
        decision = self.classify("just tell me the answer")
        self.assertEqual(decision.kind, "hint")
        self.assertTrue(decision.shows_answer)

    def test_skip_and_override_are_separate(self) -> None:
        self.assertEqual(self.classify("skip this").kind, "skip")
        self.assertEqual(self.classify("override, I know this").kind, "override")

    def test_greeting_is_chat(self) -> None:
        self.assertEqual(self.classify("hi there").kind, "chat")

    def test_without_an_open_check_there_is_nothing_to_grade(self) -> None:
        decision = self.classify("42.7", open_check=False)
        self.assertEqual(decision.kind, "chat")
        self.assertFalse(decision.creates_attempt)

    def test_explicit_controls_are_deterministic(self) -> None:
        self.assertEqual(self.classify("", explicit="submit_answer").kind, "answer")
        self.assertEqual(self.classify("", explicit="hint").kind, "hint")
        self.assertTrue(self.classify("", explicit="show_answer").shows_answer)
        self.assertEqual(self.classify("", explicit="skip").kind, "skip")
        with self.assertRaises(ValueError):
            self.classify("", explicit="not_a_control")


class GateTest(GateCase):
    def test_correct_answer_commits_a_transition_before_teaching_context(self) -> None:
        lesson = self.prepare_bound()
        outcome = turn.pre_turn(_STORED, "42.7")
        self.assertIsNotNone(outcome.hook)
        self.assertIn("context", outcome.hook)
        self.assertNotIn("action", outcome.hook)
        # The transition is durable before the hook returns anything to the teaching turn.
        self.assertEqual(self.new_transitions(), 1)
        self.assertEqual(outcome.verdict, "pass")
        attempts = self.rows("SELECT * FROM attempts")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["state"], "committed")
        self.assertEqual(attempts[0]["verdict"], "pass")

    def test_continuation_prompt_never_contains_the_reference_answer(self) -> None:
        self.prepare_bound()
        outcome = turn.pre_turn(_STORED, "42.7")
        self.assertNotIn("42.7", outcome.hook["context"])

    def test_wrong_answer_never_passes_and_offers_a_retry(self) -> None:
        self.prepare_bound()
        outcome = turn.pre_turn(_STORED, "1")
        self.assertNotEqual(outcome.verdict, "pass")
        self.assertIn("not yet", outcome.hook["context"])
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "needs_review")

    def test_clarification_creates_no_attempt_and_consumes_no_retry(self) -> None:
        lesson = self.prepare_bound()
        before = self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))
        outcome = turn.pre_turn(_STORED, "what does this question mean?")
        self.assertIsNone(outcome.hook)
        self.assertEqual(self.rows("SELECT * FROM attempts"), [])
        self.assertEqual(self.new_transitions(), 0)
        self.assertEqual(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)), before
        )

    def test_chat_is_not_governed(self) -> None:
        self.prepare_bound()
        self.assertIsNone(turn.pre_turn(_STORED, "hello").hook)
        self.assertEqual(self.rows("SELECT * FROM attempts"), [])

    def test_hint_marks_the_next_answer_hinted(self) -> None:
        self.prepare_bound()
        self.assertIsNone(turn.pre_turn(_STORED, "give me a hint").hook)
        self.assertEqual(self.scalar("SELECT kind FROM evidence"), "hint_request")
        outcome = turn.pre_turn(_STORED, "42.7")
        self.assertEqual(outcome.verdict, "pass")
        attempt = self.rows("SELECT * FROM attempts")[0]
        self.assertEqual(attempt["evidence_class"], "hinted")
        # Access advanced, independent evidence did not.
        self.assertNotEqual(self.scalar("SELECT state FROM objectives"), "independent_evidence")
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM evidence WHERE layer = 2"), 0
        )
        self.assertIn("does not count as independent evidence", outcome.hook["context"])

    def test_shown_answer_is_recorded_as_answer_shown(self) -> None:
        self.prepare_bound()
        turn.pre_turn(_STORED, "show me the answer")
        self.assertEqual(self.scalar("SELECT kind FROM evidence"), "answer_shown")
        turn.pre_turn(_STORED, "42.7")
        self.assertEqual(self.rows("SELECT * FROM attempts")[0]["evidence_class"], "answer_shown")

    def test_a_hint_contaminates_only_the_answer_it_preceded(self) -> None:
        lesson = self.prepare_bound()
        turn.pre_turn(_STORED, "give me a hint")
        turn.pre_turn(_STORED, "42.7")  # hinted pass closes the check
        self.assertEqual(self.rows("SELECT * FROM attempts")[0]["evidence_class"], "hinted")
        # A fresh, cold item after the contaminated one is independent again.
        opened = self.ok("check.open", {"enrollment_id": lesson["enrollment_id"],
                                        "objective_id": lesson["objective_id"]},
                         expected_revision=int(self.scalar(
                             "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))))["result"]
        self.assertEqual(opened["check_id"] != lesson["check_id"], True)
        turn.pre_turn(_STORED, "42.7")
        classes = [row["evidence_class"] for row in self.rows("SELECT evidence_class FROM attempts ORDER BY created_at")]
        self.assertEqual(classes, ["hinted", "cold"])
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "independent_evidence")

    def test_skip_grants_access_but_is_labelled_an_override(self) -> None:
        self.prepare_bound()
        outcome = turn.pre_turn(_STORED, "skip this")
        attempt = self.rows("SELECT * FROM attempts")[0]
        self.assertEqual(attempt["evidence_class"], "override")
        self.assertNotEqual(attempt["verdict"], "pass")
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "overridden")
        self.assertIn("not mastery", outcome.hook["context"])

    def test_grading_outage_is_needs_retry_and_advances_nothing(self) -> None:
        lesson = self.prepare_bound()
        with mock.patch("coursebook.domain.grading.grade", side_effect=RuntimeError("provider down")):
            outcome = turn.pre_turn(_STORED, "42.7")
        self.assertEqual(outcome.verdict, "needs_retry")
        self.assertEqual(outcome.hook["action"], "block")
        self.assertEqual(self.new_transitions(), 0)
        self.assertEqual(self.scalar("SELECT verdict FROM attempts"), "needs_retry")
        self.assertEqual(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)),
            lesson["revision"],
        )
        self.assertEqual(self.scalar("SELECT state FROM objectives"), "not_started")

    def test_unaudited_check_is_refused_never_graded(self) -> None:
        lesson = self.prepare_bound()
        # A check that loses its audit (e.g. its source went stale) must stop being gradable.
        self.execute("UPDATE checks SET audit_state = 'failed' WHERE id = ?", (lesson["check_id"],))
        outcome = turn.pre_turn(_STORED, "42.7")
        self.assertEqual(outcome.hook["action"], "block")
        self.assertEqual(self.rows("SELECT * FROM attempts"), [])

    def test_stale_revision_blocks_without_creating_an_attempt(self) -> None:
        lesson = self.prepare_bound()
        from coursebook import api

        raced = {"done": False}

        def dispatch(envelope):
            # Another window commits a transition between this turn's read and its submit.
            if envelope.get("method") == "attempt.submit" and not raced["done"]:
                raced["done"] = True
                self.execute("UPDATE enrollments SET revision = revision + 1 WHERE id = ?",
                             (lesson["enrollment_id"],))
            return api.dispatch(envelope)

        outcome = turn.pre_turn(_STORED, "42.7", dispatch=dispatch)
        self.assertEqual(outcome.hook["action"], "block")
        self.assertIn("moved on", outcome.hook["message"])
        self.assertEqual(self.rows("SELECT * FROM attempts"), [])
        self.assertEqual(self.new_transitions(), 0)

    def test_two_windows_produce_exactly_one_transition(self) -> None:
        lesson = self.prepare_bound()
        results: list = []

        def answer(text: str) -> None:
            results.append(turn.pre_turn(_STORED, text, deadline_ms=8000))

        threads = [threading.Thread(target=answer, args=(text,)) for text in ("42.7", "42.7")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(self.new_transitions(), 1)
        self.assertEqual(len(self.rows("SELECT * FROM attempts")), 1)
        blocked = [r for r in results if r.hook and r.hook.get("action") == "block"]
        # Both windows may report the same committed result; none may create a second transition.
        self.assertLessEqual(len(blocked), 1)
        self.assertEqual(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)),
            lesson["revision"] + 1,
        )

    def test_no_binding_means_ungoverned(self) -> None:
        self.prepare_lesson()
        self.assertIsNone(turn.pre_turn(_STORED, "42.7").hook)
        self.assertEqual(self.rows("SELECT * FROM attempts"), [])

    def test_detached_binding_is_not_graded(self) -> None:
        self.prepare_bound()
        self.execute("UPDATE bindings SET status = 'detached'")
        self.assertIsNone(turn.pre_turn(_STORED, "42.7").hook)


class ContinuationTest(GateCase):
    def test_continuation_key_is_stable_per_attempt_and_action(self) -> None:
        first = turn.continuation_key("att_1", action="continue")
        self.assertEqual(first, turn.continuation_key("att_1", action="continue"))
        self.assertNotEqual(first, turn.continuation_key("att_1", action="next_section"))
        self.assertGreaterEqual(len(first), 8)

    def test_continuation_prompt_names_the_permitted_action_only(self) -> None:
        text = turn.continuation_prompt(verdict="not_yet", next_action="retry_attempt",
                                       evidence_class="cold", objective_id="obj_1")
        self.assertIn("different explanation", text)
        self.assertNotIn("answer:", text.lower())


class ObserverAndResumeTest(GateCase):
    def test_post_turn_records_the_teaching_segment(self) -> None:
        self.prepare_bound()
        hooks.pre_llm_call(session_id=_STORED, user_message="42.7")
        hooks.post_llm_call(session_id=_STORED, user_message="42.7", assistant_response="Nice work.")
        segments = self.rows("SELECT * FROM lesson_segments WHERE kind = 'teaching'")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], "Nice work.")

    def test_late_callback_cannot_write_into_a_newer_revision(self) -> None:
        lesson = self.prepare_bound()
        hooks.pre_llm_call(session_id=_STORED, user_message="1")  # wrong answer, keeps check open
        # Another window advances the lesson before this turn's callback arrives.
        turn.pre_turn(_STORED, "42.7")
        hooks.post_llm_call(session_id=_STORED, user_message="1", assistant_response="late text")
        self.assertEqual(self.rows("SELECT * FROM lesson_segments WHERE kind = 'teaching'"), [])

    def test_restart_drops_the_pending_turn_and_resume_uses_the_stored_binding(self) -> None:
        self.prepare_bound()
        hooks.pre_llm_call(session_id=_STORED, user_message="42.7")
        # A restart clears process memory: the pending nonce is gone, so no late snapshot is written.
        hooks._TURNS.clear()
        hooks.post_llm_call(session_id=_STORED, user_message="42.7", assistant_response="after restart")
        self.assertEqual(self.rows("SELECT * FROM lesson_segments WHERE kind = 'teaching'"), [])

        resumed = self.ok(
            "lesson.begin",
            {"enrollment_id": self.scalar("SELECT enrollment_id FROM bindings"),
             "objective_id": self.scalar("SELECT objective_id FROM bindings"), "mode": "resume"},
            idempotency_key="resume-after-restart",
            expected_revision=0,
        )["result"]
        self.assertEqual(resumed["run_state"], "resumed")
        self.assertTrue(resumed["resume"]["available"])

    def test_compaction_tip_is_adopted_and_a_cwd_change_detaches(self) -> None:
        self.prepare_bound()
        adopted = turn.reconcile_binding(_STORED, compression_tip="tip-2")
        self.assertEqual(adopted["status"], "active")
        self.assertTrue(adopted["changed"])
        self.assertEqual(self.scalar("SELECT compression_tip FROM bindings"), "tip-2")

        detached = turn.reconcile_binding(_STORED, cwd_fingerprint="a-different-cwd")
        self.assertEqual(detached["status"], "detached")
        # A detached chat is ungoverned: the gate passes the turn through without grading.
        self.assertIsNone(hooks.pre_llm_call(session_id=_STORED, user_message="42.7"))

    def test_reconcile_does_not_invent_a_binding(self) -> None:
        self.prepare_lesson()
        self.assertEqual(turn.reconcile_binding("unknown-stored")["status"], "unbound")


if __name__ == "__main__":
    unittest.main()
