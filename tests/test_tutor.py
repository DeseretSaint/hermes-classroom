"""GM-011: the lesson-bound tutor backend and its practice integration.

The security property under test is a separation, not a feature. ``tutor.ask`` is a bounded,
lesson-scoped command with no tools, no answer key in its context, no write path into attempts,
transitions or evidence, and citations that must resolve or be omitted. Practice mode reuses the
existing ``practice.*`` session and grader, so only learner turns can produce a verdict.

Every case runs against a real migrated database through the real dispatcher. The provider is a
scripted host LLM, so nothing here fabricates a provider result: a failure is scripted as a failure
and must surface as a named state.
"""

from __future__ import annotations

import json
import os
import unittest
import zipfile

from coursebook import db, domain, generation
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

# The practice and export suites already own the expensive fixtures; these tests reuse the same
# real commands rather than re-deriving a second world.
from tests.test_conversation_practice import PracticeCase as _PracticeCase
from tests.test_course_export import AuthoredCourseCase as _AuthoredCourseCase

#: The phrase the check grades. It is answer key and must never appear in learner context.
SECRET_ANSWER = "the mitochondria is the powerhouse of the cell"
SECRET_ALT = "powerhouse of the cell"
#: A second secret marker planted in the worked example, which is not a context source either.
WORKED_EXAMPLE_SECRET = "ATP synthase spins like a turbine"


class ScriptedHostLLM:
    """The minimal ``ctx.llm`` surface: one queued reply, or one queued exception, per call."""

    def __init__(self, replies=None) -> None:
        self.replies = list(replies or [])
        self.calls: list[dict] = []
        self.default = {"answer": "This lesson explains how cells release energy.", "citations": []}

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if self.replies else self.default
        if isinstance(reply, BaseException):
            raise reply
        payload = reply if isinstance(reply, dict) else {"answer": str(reply), "citations": []}
        usage = type("Usage", (), {"input_tokens": 11, "output_tokens": 22, "cost_usd": 0.0})()
        return type(
            "Result",
            (),
            {
                "text": json.dumps(payload),
                "parsed": payload,
                "provider": "fake",
                "model": "fake-tutor-1",
                "usage": usage,
            },
        )()


class TutorCase(KernelCase):
    """One committed course with an open check, a lesson run and a projected lesson document."""

    def setUp(self) -> None:
        super().setUp()
        self.host = ScriptedHostLLM()
        generation.bind_host_llm(self.host)
        self.addCleanup(generation.bind_host_llm, None)

        spec = numeric_spec()
        # An exact answer makes the leak test about a real reference answer, not a number.
        spec["reference"] = {"kind": "exact", "answers": [SECRET_ANSWER, SECRET_ALT]}
        spec["stimulus"] = {
            "prompt": "Explain what the organelle does for the cell.",
            "format": "text",
            "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "hinted"},
        }
        course_id, plan_id = self.new_course(title="Cell biology")
        objective_id = domain.record_objective(
            plan_id,
            title="Explain cellular respiration",
            evidence_target="procedure",
            criteria=criteria_with(spec),
        )
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        run = self.ok(
            "lesson.begin",
            {"enrollment_id": enrollment_id, "objective_id": objective_id, "mode": "fresh"},
            idempotency_key=f"key-begin-{os.urandom(4).hex()}",
        )["result"]

        self.course_id = course_id
        self.plan_id = plan_id
        self.objective_id = objective_id
        self.enrollment_id = enrollment_id
        self.check_id = opened["check_id"]
        self.revision = opened["revision"]
        self.lesson_run_id = run["lesson_run_id"]
        self.source_id = "src_respiration"
        self._seed_page(run["lesson_run_id"])

    # ── fixture ────────────────────────────────────────────────────────
    def _seed_page(self, lesson_run_id: str) -> None:
        now = db.utcnow()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at,"
                " fetched_at, support_status, claim_count, created_at)"
                " VALUES (?, ?, 'https://example.org/respiration', 'Cell respiration primer',"
                " 'reference', NULL, ?, 'authoritative_documentation', 1, ?)",
                (self.source_id, self.course_id, now, now),
            )
            connection.execute(
                "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, artifact_id,"
                " source_id, created_at) VALUES ('seg_orient', ?, 1, 'teaching', ?, NULL, ?, ?)",
                (
                    lesson_run_id,
                    "Cells release usable energy by breaking down glucose in a series of steps.",
                    self.source_id,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, artifact_id,"
                " source_id, created_at) VALUES ('seg_recap', ?, 2, 'teaching', ?, NULL, NULL, ?)",
                (
                    lesson_run_id,
                    "The lesson keeps the steps separate so you can name each one.",
                    now,
                ),
            )

    # ── helpers ────────────────────────────────────────────────────────
    def ask(self, *, question: str = "What does the organelle do?", mode: str = "ask",
            block_id: str | None = None, selected_text: str | None = None,
            revision: int | None = None, key: str | None = None) -> dict:
        payload = {
            "course_id": self.course_id,
            "enrollment_id": self.enrollment_id,
            "objective_id": self.objective_id,
            "lesson_run_id": self.lesson_run_id,
            "question": question,
            "mode": mode,
        }
        if block_id is not None:
            payload["block_id"] = block_id
        if selected_text is not None:
            payload["selected_text"] = selected_text
        return self.dispatch(
            "tutor.ask",
            payload,
            expected_revision=self.revision if revision is None else revision,
            idempotency_key=key or f"key-ask-{os.urandom(6).hex()}",
        )

    def page_blocks(self) -> list[dict]:
        page = self.ok(
            "lesson.page",
            {"enrollment_id": self.enrollment_id, "objective_id": self.objective_id},
        )["result"]
        return page["document"]["blocks"]

    def context_text(self) -> str:
        return json.dumps(self.host.calls[0], ensure_ascii=False, sort_keys=True)


class TutorAskTest(TutorCase):
    def test_tutor_context_excludes_answer_key(self) -> None:
        blocks = self.page_blocks()
        self.assertTrue(blocks)
        self.host.replies = [
            {
                "answer": "The organelle releases energy the cell can use.",
                "citations": [blocks[0]["id"], self.source_id],
            }
        ]
        response = self.ask(block_id=blocks[0]["id"])
        self.assertTrue(response["ok"], response.get("error"))

        sent = self.context_text()
        for secret in (SECRET_ANSWER, SECRET_ALT, WORKED_EXAMPLE_SECRET):
            self.assertNotIn(secret, sent, "answer key reached the tutor context")
        # The sealed spec keys themselves are not sent, even with a benign value.
        for forbidden in ("reference_json", "rubric_json", "accepted_answers", "worked_example"):
            self.assertNotIn(forbidden, sent)
        # The learner-visible lesson text and the objective title are present: this is not a
        # context that simply omits everything and cannot answer.
        self.assertIn("Cells release usable energy", sent)
        self.assertIn("Explain cellular respiration", sent)

        history = self.ok(
            "tutor.history",
            {
                "course_id": self.course_id,
                "enrollment_id": self.enrollment_id,
                "objective_id": self.objective_id,
                "lesson_run_id": self.lesson_run_id,
            },
        )["result"]
        history_text = json.dumps(history, ensure_ascii=False)
        for secret in (SECRET_ANSWER, SECRET_ALT):
            self.assertNotIn(secret, history_text)

    def test_tutor_has_no_tool_or_shell_access(self) -> None:
        import coursebook.tutor as tutor

        self.assertEqual(tutor.TOOLS, ())
        self.assertNotIn("tools", json.dumps(self.host.calls))
        self.host.replies = [{"answer": "Stored energy.", "citations": []}]
        response = self.ask()
        self.assertTrue(response["ok"], response.get("error"))
        call = self.host.calls[0]
        self.assertNotIn("tools", call)
        self.assertNotIn("functions", call)
        # The structured output is an answer and citations only: no tool call envelope.
        self.assertEqual(set(call["json_schema"]["properties"]), {"answer", "citations"})
        source = (__import__("pathlib").Path(tutor.__file__)).read_text(encoding="utf-8")
        for forbidden in ("import subprocess", "import socket", "import requests",
                          "import urllib", "os.system", "subprocess."):
            self.assertNotIn(forbidden, source)

    def test_tutor_turn_never_writes_attempt_or_evidence(self) -> None:
        before = {
            "attempts": self.scalar("SELECT COUNT(*) FROM attempts"),
            "evidence": self.scalar("SELECT COUNT(*) FROM evidence"),
            "transitions": self.scalar("SELECT COUNT(*) FROM transitions"),
            "revision": self.scalar(
                "SELECT revision FROM enrollments WHERE id = ?", (self.enrollment_id,)
            ),
        }
        self.host.replies = [{"answer": "A short explanation.", "citations": []}]
        response = self.ask()
        self.assertTrue(response["ok"], response.get("error"))
        after = {
            "attempts": self.scalar("SELECT COUNT(*) FROM attempts"),
            "evidence": self.scalar("SELECT COUNT(*) FROM evidence"),
            "transitions": self.scalar("SELECT COUNT(*) FROM transitions"),
            "revision": self.scalar(
                "SELECT revision FROM enrollments WHERE id = ?", (self.enrollment_id,)
            ),
        }
        self.assertEqual(after["attempts"], before["attempts"])
        self.assertEqual(after["evidence"], before["evidence"])
        self.assertEqual(after["transitions"], before["transitions"])
        # A turn is a learner-facing mutation, so the same enrollment fence moves; it just never
        # moves a learning record.
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM tutor_turns WHERE thread_id = ?",
                        (response["result"]["thread_id"],)),
            2,
        )

    def test_tutor_citations_resolve_to_lesson_or_source(self) -> None:
        blocks = self.page_blocks()
        block_id = blocks[0]["id"]
        self.host.replies = [
            {
                "answer": "Both steps are in the lesson.",
                "citations": [block_id, self.source_id, "blk_invented0000000000",
                              "src_invented", block_id],
            }
        ]
        response = self.ask(block_id=block_id)
        self.assertTrue(response["ok"], response.get("error"))
        citations = response["result"]["citations"]
        self.assertEqual(
            [(item["kind"], item["id"]) for item in citations],
            [("block", block_id), ("source", self.source_id)],
        )
        # A citation carries a label the UI can render and a resolvable id; nothing else.
        self.assertEqual(set(citations[0]), {"kind", "id", "label"})
        self.assertTrue(citations[0]["label"])

    def test_tutor_provider_failure_is_named(self) -> None:
        # No host model bound: the contract's HOST_UNAVAILABLE, nothing invented.
        generation.bind_host_llm(None)
        error = self.ask()["error"]
        self.assertEqual(error["code"], "HOST_UNAVAILABLE")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM tutor_turns"), 0)

        # A bound model that fails at call time is a named state, not an empty answer.
        generation.bind_host_llm(ScriptedHostLLM([RuntimeError("provider down")]))
        response = self.ask()
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["result"]["state"], "provider_failure")
        self.assertIsNone(response["result"]["turn"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM tutor_turns"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)

        # And the failure did not poison the thread: a retry can answer.
        generation.bind_host_llm(self.host)
        self.host.replies = [{"answer": "Back again.", "citations": []}]
        retry = self.ask()
        self.assertTrue(retry["ok"], retry.get("error"))
        self.assertEqual(retry["result"]["state"], "answered")

    def test_tutor_hint_does_not_reveal_answer(self) -> None:
        # The model disobeys: a full answer comes back while the check is open. The backend
        # withholds it, persists only the safe message and labels the assist policy.
        self.host.replies = [
            {"answer": f"Well, {SECRET_ANSWER}.", "citations": []},
            {"answer": "Start with the first step in the lesson: what input does the cell break down?",
             "citations": []},
        ]

        leaked = self.ask(question="What is the answer?")
        self.assertTrue(leaked["ok"], leaked.get("error"))
        self.assertEqual(leaked["result"]["state"], "answer_withheld")
        self.assertEqual(leaked["result"]["turn"]["text"], __import__("coursebook.tutor", fromlist=["WITHHELD_ANSWER"]).WITHHELD_ANSWER)
        for secret in (SECRET_ANSWER, SECRET_ALT):
            self.assertNotIn(secret, json.dumps(leaked["result"], ensure_ascii=False))
            self.assertNotIn(
                secret,
                json.dumps(self.rows("SELECT text FROM tutor_turns"), ensure_ascii=False),
            )
        assist = leaked["result"]["assist"]
        self.assertEqual(assist["kind"], "hint_request")
        self.assertEqual(assist["policy"], "available")
        self.assertTrue(assist["available"])
        self.assertEqual(assist["evidence_class"], "hinted")
        self.revision = leaked["revision"]

        hint = self.ask(question="Give me a hint.")
        self.assertTrue(hint["ok"], hint.get("error"))
        self.assertEqual(hint["result"]["state"], "answered")
        self.assertIn("first step", hint["result"]["turn"]["text"])
        for secret in (SECRET_ANSWER, SECRET_ALT):
            self.assertNotIn(secret, hint["result"]["turn"]["text"])


class TutorPracticeTest(_PracticeCase):
    """``mode=practice`` writes the existing practice log; tutor prose is never graded."""

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
            idempotency_key=f"key-practice-{os.urandom(6).hex()}",
        )

    def test_practice_tutor_turn_cannot_produce_a_pass(self) -> None:
        started = self.start(self.lesson)
        revision = started["revision"]

        # Every tutor reply loudly contains both graded expressions. If the grader read tutor
        # prose, this transcript would pass.
        self.host.replies = [
            {"answer": "Kyoto! And how much is it? One ticket to Kyoto, please.", "citations": []},
            {"answer": "Kyoto is lovely. How much is it?", "citations": []},
            {"answer": "One ticket to Kyoto, please. How much is it?", "citations": []},
        ]
        learner_lines = [
            "I would like to travel somewhere.",
            "Could you help me, please?",
            "Thank you very much.",
        ]
        for line in learner_lines:
            response = self.ask_practice(line, revision=revision)
            self.assertTrue(response["ok"], response.get("error"))
            revision = response["revision"]
            self.assertEqual(response["result"]["state"], "answered")
            self.assertEqual(response["result"]["turn"]["role"], "tutor")

        # The practice engine, not a second one, recorded the exchange: opening + 3 learner + 3 tutor.
        turns = self.rows("SELECT speaker, text FROM practice_turns ORDER BY ordinal")
        self.assertEqual([row["speaker"] for row in turns],
                         ["tutor", "learner", "tutor", "learner", "tutor", "learner", "tutor"])
        tutor_text = " ".join(row["text"] for row in turns if row["speaker"] == "tutor")
        self.assertIn("Kyoto", tutor_text)

        graded = self.ok(
            "practice.end",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "check_id": self.lesson["check_id"],
                "check_version": self.lesson["check_version"],
                "attempt_nonce": "nonce-tutor-practice",
            },
            expected_revision=revision,
            idempotency_key=f"key-end-{os.urandom(6).hex()}",
        )["result"]
        # Only the learner turns were read: no speaker produced a target, so no pass exists even
        # though every tutor turn did.
        self.assertNotEqual(graded["verdict"], "pass")
        self.assertEqual(graded["learner_turns"], 3)

    def test_practice_mode_requires_an_active_session(self) -> None:
        error = self.ask_practice("Are you there?", revision=self.lesson["revision"])["error"]
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "practice_not_active")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM tutor_turns"), 0)


class TutorExportTest(_AuthoredCourseCase):
    """Tutor turns are learner-owned history; pack and course export never read them."""

    MARKER = "TUTOR-TRANSCRIPT-MARKER-not-in-any-export"

    def setUp(self) -> None:
        super().setUp()
        self.host = ScriptedHostLLM([{"answer": self.MARKER, "citations": []}])
        generation.bind_host_llm(self.host)
        self.addCleanup(generation.bind_host_llm, None)
        self.seeded = self.seed_course(sections=1)
        self.seed_validated_lessons(self.seeded)
        self.objective_id = self.seeded["objective_ids"][0]
        self.enrollment_id = self.seeded["enrollment_id"]
        run = self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.enrollment_id,
                "objective_id": self.objective_id,
                "mode": "fresh",
            },
            idempotency_key=f"key-begin-{os.urandom(4).hex()}",
        )["result"]
        self.lesson_run_id = run["lesson_run_id"]

    def test_tutor_thread_is_excluded_from_export(self) -> None:
        revision = int(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (self.enrollment_id,))
        )
        asked = self.ok(
            "tutor.ask",
            {
                "course_id": self.seeded["course_id"],
                "enrollment_id": self.enrollment_id,
                "objective_id": self.objective_id,
                "lesson_run_id": self.lesson_run_id,
                "question": "What should I remember?",
                "mode": "ask",
            },
            expected_revision=revision,
            idempotency_key=f"key-ask-{os.urandom(6).hex()}",
        )["result"]
        self.assertEqual(asked["turn"]["text"], self.MARKER)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM tutor_turns"), 2)

        read = self.ok("course.export.read", {"enrollment_id": self.enrollment_id})["result"]
        exported = self.export(self.enrollment_id, read["content_hash"])
        archive = self.archive_path(exported)
        self.assertTrue(archive.is_file(), archive)
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            payload = b"".join(bundle.read(name) for name in names)
        self.assertNotIn(self.MARKER.encode(), payload)
        self.assertFalse(any("tutor" in name for name in names), names)
        # The tutor row still exists: the export omitted it rather than the turn never existing.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM tutor_turns"), 2)


if __name__ == "__main__":
    unittest.main()
