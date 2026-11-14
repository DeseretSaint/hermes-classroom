"""UP-21: the practice tutor carries the transcript it is inside, and the targets already matched.

Before this upgrade ``_ask_practice`` rebuilt the context from the objective, glossary and the
authored scene only: turn three was structurally identical to turn one, so the partner could not
answer the learner's last line or steer to an unused target. The fix carries the session's bounded
turn list and the ids of targets the learner has already produced, scoped to this one session.
"""

from __future__ import annotations

import json
import os

from coursebook import generation
from tests.test_conversation_practice import PracticeCase as _PracticeCase
from tests.test_tutor import ScriptedHostLLM

LEARNER_ONE = "MARKER-LEARNER-ONE one ticket to Kyoto, please"
LEARNER_TWO = "MARKER-LEARNER-TWO how much is it?"
LEARNER_THREE = "MARKER-LEARNER-THREE thank you very much"
TUTOR_ONE = "TUTOR-REPLY-ONE welcome aboard"
TUTOR_TWO = "TUTOR-REPLY-TWO that will be two thousand yen"


class PracticeContextTest(_PracticeCase):
    """One real practice session through the real dispatcher and a scripted host model."""

    def setUp(self) -> None:
        super().setUp()
        self.host = ScriptedHostLLM()
        generation.bind_host_llm(self.host)
        self.addCleanup(generation.bind_host_llm, None)
        self.lesson = self.prepare_practice()

    def ask_practice(self, question: str, *, revision: int) -> dict:
        return self.dispatch(
            "tutor.ask",
            {
                "course_id": self.lesson["course_id"],
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "lesson_run_id": self.lesson["lesson_run_id"],
                "question": question,
                "mode": "practice",
            },
            expected_revision=revision,
            idempotency_key=f"key-practice-context-{os.urandom(6).hex()}",
        )

    @staticmethod
    def sent_context(call: dict) -> dict:
        request = json.loads(call["input"][0]["text"])
        return request["lesson_context"]["practice"]

    def test_the_practice_tutor_context_carries_the_prior_turns(self) -> None:
        started = self.start(self.lesson)
        revision = started["revision"]
        self.host.replies = [
            {"answer": TUTOR_ONE, "citations": []},
            {"answer": TUTOR_TWO, "citations": []},
            {"answer": "TUTOR-REPLY-THREE safe travels", "citations": []},
        ]
        for line in (LEARNER_ONE, LEARNER_TWO, LEARNER_THREE):
            response = self.ask_practice(line, revision=revision)
            self.assertTrue(response["ok"], response.get("error"))
            self.assertEqual(response["result"]["state"], "answered")
            revision = response["revision"]

        self.assertEqual(len(self.host.calls), 3)

        # Turn one sees only the authored opening: the list grows with the session, not before it.
        first = self.sent_context(self.host.calls[0])
        self.assertEqual(
            [(turn["speaker"], turn["text"]) for turn in first["turns"]],
            [("tutor", started["transcript"][0]["text"])],
        )
        self.assertEqual(first["matched_target_ids"], [])

        # Turn three sees the two prior exchanges, in order, and the ids already produced.
        third = self.sent_context(self.host.calls[2])
        exchanges = [(turn["speaker"], turn["text"]) for turn in third["turns"]]
        self.assertEqual(
            [speaker for speaker, _text in exchanges],
            ["tutor", "learner", "tutor", "learner", "tutor"],
        )
        seen = json.dumps(third["turns"], ensure_ascii=False)
        for marker in (LEARNER_ONE, LEARNER_TWO, TUTOR_ONE, TUTOR_TWO):
            self.assertIn(marker, seen, "a prior exchange is missing from the turn-three context")
        # The question of this turn travels as the question, not duplicated inside the history.
        self.assertNotIn(LEARNER_THREE, seen)
        self.assertEqual(third["matched_target_ids"], ["t1", "t2"])

        # The scope fence is this session's stored log, not a broader thread: every carried turn is
        # a durable practice turn, and the two turns this call is about to write are not in it yet.
        stored = [
            (row["speaker"], row["text"])
            for row in self.rows("SELECT speaker, text FROM practice_turns ORDER BY ordinal")
        ]
        self.assertEqual(exchanges, stored[: len(exchanges)])
        self.assertEqual(len(stored) - len(exchanges), 2)

        # Ids only: the sealed key's match clauses and the reference row never ride in context.
        sent = json.dumps(third, ensure_ascii=False)
        self.assertNotIn("reference_json", sent)
        self.assertNotIn('"match"', sent)
        self.assertNotIn("rubric_json", sent)


class PracticeContextScopeTest(_PracticeCase):
    """No transcript is built from a thread: without an active session there is no practice context."""

    def setUp(self) -> None:
        super().setUp()
        self.host = ScriptedHostLLM()
        generation.bind_host_llm(self.host)
        self.addCleanup(generation.bind_host_llm, None)

    def test_no_context_is_built_without_an_active_session(self) -> None:
        lesson = self.prepare_practice()
        error = self.dispatch(
            "tutor.ask",
            {
                "course_id": lesson["course_id"],
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "lesson_run_id": lesson["lesson_run_id"],
                "question": "Are you there?",
                "mode": "practice",
            },
            expected_revision=lesson["revision"],
            idempotency_key=f"key-no-practice-{os.urandom(6).hex()}",
        )["error"]
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "practice_not_active")
        self.assertEqual(self.host.calls, [])
