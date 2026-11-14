"""UP-43: a lessons job whose every section parked must not report lessons authored.

`run_lesson_job` stores a page the validator parked as ``needs_review`` and still returns it in
``lessons`` (the row is authored work), so the executor's completion line — which counted rows —
told an operator "6 lessons authored" for a unit where the learner could open none of them. The
job itself stays ``completed``: the work did complete, and the next action is the repair, not a
re-run. What changes is that the checkpoint and the line carry the split.

These call the real lessons stage with a canned `run_lesson_job` result shaped exactly as the
function returns it (section ids, states, the stored rejection reasons) and a media summary that
generated nothing. What this does NOT prove: that a live provider parks a real section. That is
the generation suite's job.
"""

from __future__ import annotations

import unittest
from unittest import mock

from coursebook import executor, job_service, media as media_mod

SECTIONS_TOTAL = 6

#: The reasons the validator stored on each parked page. They are pipeline words and must reach
#: the checkpoint (an operator surface) but never the completion line (a learner surface).
PARK_REASONS = {
    f"sec_{ordinal}": f"check item repeats 'item_{ordinal}' and the answer appears in the prompt"
    for ordinal in range(1, SECTIONS_TOTAL + 1)
}


class _FakeConnection:
    def close(self) -> None:
        pass


def _lesson_summary(section_id: str, state: str, *, reason: str | None = None) -> dict:
    summary = {
        "section_id": section_id,
        "lesson_id": f"lesson_{section_id}",
        "check_id": f"check_{section_id}",
        "state": state,
        "check_enabled": state == "validated",
        "reused": False,
    }
    if state == "needs_review":
        summary["rejection_reasons"] = [reason] if reason else []
    return summary


class ParkedCompletionTest(unittest.TestCase):
    def _stage_result(self, lessons: list[dict], *, generated: int = 0) -> job_service.StageResult:
        result = {
            "plan_id": "plan_1",
            "plan_hash": "hash_1",
            "plan_schema": "cb.lesson@1",
            "unit_ordinal": 1,
            "next_unit_ordinal": None,
            "sections_total": SECTIONS_TOTAL,
            "lessons": lessons,
            "needs_review": [
                item["section_id"]
                for item in lessons
                if item["state"] in ("needs_review", "model_assessed")
            ],
        }
        media_summary = media_mod.MediaGenerationSummary(
            artifact_ids=[],
            usage=[],
            skipped=len(lessons),
            generated=generated,
        )
        lease = job_service.Lease("job_lessons_1", "att_1", "test", "2099-01-01T00:00:00+00:00")
        stage = executor._Resolvers(llm=object(), search=None, now=None)._lessons_stage(
            {"stage": "lessons", "plan_id": "plan_1"}
        )
        with mock.patch.object(executor.db, "connect", return_value=_FakeConnection()), mock.patch.object(
            executor.job_service, "cancel_requested", return_value=False
        ), mock.patch.object(
            executor.generation, "run_lesson_job", return_value=result
        ), mock.patch.object(
            executor.media_mod, "generate_for_lessons", return_value=media_summary
        ):
            return stage(lease)

    def test_all_parked_unit_does_not_read_as_authored(self) -> None:
        """Every section parked: the checkpoint says zero servable, and so does the line."""
        lessons = [
            _lesson_summary(f"sec_{ordinal}", "needs_review", reason=PARK_REASONS[f"sec_{ordinal}"])
            for ordinal in range(1, SECTIONS_TOTAL + 1)
        ]
        outcome = self._stage_result(lessons)

        checkpoint = outcome.checkpoint
        self.assertEqual(checkpoint["servable"], 0)
        self.assertEqual(checkpoint["parked"], SECTIONS_TOTAL)
        self.assertEqual(checkpoint["sections_total"], SECTIONS_TOTAL)
        # One reason per parked section, and the section it belongs to — never a prose wall.
        self.assertEqual(len(checkpoint["parked_reasons"]), SECTIONS_TOTAL)
        self.assertEqual(
            [entry["section_id"] for entry in checkpoint["parked_reasons"]],
            [f"sec_{ordinal}" for ordinal in range(1, SECTIONS_TOTAL + 1)],
        )
        for entry in checkpoint["parked_reasons"]:
            self.assertEqual(entry["reason"], PARK_REASONS[entry["section_id"]])

        message = outcome.message or ""
        self.assertIn("0 of 6", message)
        self.assertIn("parked for repair", message)
        self.assertNotIn("lessons authored", message)
        # The learner-facing words stay out of the pipeline's words: no reason prose, no ids.
        self.assertNotIn("item_", message)
        self.assertNotIn("sec_", message)
        self.assertNotIn("plan_1", message)
        # The stage returned rather than raised, so the job is still `completed` — the repair is
        # the next action, not a retry of work that already landed.
        self.assertIsInstance(outcome, job_service.StageResult)

    def test_partly_parked_unit_reads_as_a_split(self) -> None:
        lessons = [
            _lesson_summary(f"sec_{ordinal}", "validated" if ordinal <= 3 else "needs_review",
                           reason=PARK_REASONS[f"sec_{ordinal}"])
            for ordinal in range(1, SECTIONS_TOTAL + 1)
        ]
        outcome = self._stage_result(lessons)
        self.assertEqual(outcome.checkpoint["servable"], 3)
        self.assertEqual(outcome.checkpoint["parked"], 3)
        self.assertEqual(len(outcome.checkpoint["parked_reasons"]), 3)
        message = outcome.message or ""
        self.assertIn("3 of 6", message)
        self.assertIn("3 parked for repair", message)

    def test_a_fully_servable_unit_does_not_mention_repair(self) -> None:
        lessons = [_lesson_summary(f"sec_{ordinal}", "validated") for ordinal in range(1, 7)]
        outcome = self._stage_result(lessons, generated=2)
        self.assertEqual(outcome.checkpoint["servable"], SECTIONS_TOTAL)
        self.assertEqual(outcome.checkpoint["parked"], 0)
        self.assertEqual(outcome.checkpoint["parked_reasons"], [])
        message = outcome.message or ""
        self.assertIn("6 of 6", message)
        self.assertNotIn("parked", message)
        self.assertIn("2 media artifacts generated", message)


if __name__ == "__main__":
    unittest.main()
