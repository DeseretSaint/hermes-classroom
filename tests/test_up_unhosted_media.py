"""UP-39: an illustration the host never attempted is degraded, not silently empty.

A host with no media seam cannot draw a figure. Skipping the item left the learner page with a
media child that had no artifact, ``degraded: false`` and ``reason: null``: indistinguishable from
a lesson that never asked for art. The item now carries the typed reason that names the missing
host capability, the text equivalent still ships, and the run's summary counts it.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from coursebook import artifacts, db, generation, media

from tests.kernel_support import KernelCase

NOW = "2026-11-14T12:00:00Z"
HASH = "sha256:" + "a" * 64
UNHOSTED_REASON = "no media provider is bound in this host"


class UnhostedMediaTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.course_id, self.plan_id = self.new_course()
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        self.objective_id = self.seed_objective(self.plan_id)
        self.enrollment_id = self.new_enrollment(self.course_id)
        self.store = artifacts.ArtifactStore()
        self.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
            " document_json, research_json, generation_state, validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, '{}', 'validated', NULL, '{}', ?)",
            (
                "gen_doc_1",
                self.plan_id,
                self.course_id,
                "fp-1",
                HASH,
                json.dumps({"locale": "en"}),
                NOW,
            ),
        )
        self.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
            " objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, ?, ?, ?, '[]', '[]')",
            ("sec_1", self.plan_id, HASH, "The bench", "Recognise a torque wrench", json.dumps([1])),
        )
        self.media_items = [
            {
                "kind": "visual",
                "role": "illustration",
                "purpose": "See the workshop bench",
                "spec": "An editorial illustration of a workshop bench with a torque wrench",
                "text_equivalent": "A workshop bench with a torque wrench.",
            }
        ]
        self.lesson_id = "gen_lesson_unhosted_1"
        self.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
            " media_json, parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, 'validated', ?, ?, '{}', '[]', NULL, ?, ?)",
            (
                self.lesson_id,
                self.plan_id,
                "sec_1",
                HASH,
                json.dumps({"locale": "en", "section_title": "The bench"}),
                json.dumps(self.media_items),
                NOW,
                NOW,
            ),
        )

    def generate_unhosted(self):
        """Run the real media pass with no host seam bound (``host=None``)."""
        with db.read() as connection:
            return media.generate_for_lessons(
                connection,
                lesson_ids=[self.lesson_id],
                job_id="job_media_unhosted_1",
                host=None,
                store=self.store,
                now=datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc),
            )

    def stored_media(self) -> list[dict]:
        row = self.rows("SELECT media_json FROM gen_lessons WHERE id = ?", (self.lesson_id,))[0]
        return json.loads(row["media_json"])

    def test_unattempted_illustration_is_degraded_with_a_reason(self) -> None:
        summary = self.generate_unhosted()

        # One illustration was not attempted, so the summary says one item degraded. It is not a
        # silent zero, and it is not counted as a skipped lesson either.
        self.assertEqual(summary.degraded, 1)
        self.assertEqual(summary.skipped, 0)
        self.assertEqual(summary.generated, 0)

        item = self.stored_media()[0]
        self.assertFalse(item.get("artifact_id"))
        self.assertTrue(item["degraded"])
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_DEGRADED)
        self.assertEqual(item["reason"], UNHOSTED_REASON)
        # The text equivalent is what the learner gets, and it stays intact.
        self.assertEqual(item["text_equivalent"], "A workshop bench with a torque wrench.")

        with db.read() as connection:
            page = generation.learner_page(connection, self.lesson_id)
        served = page["media"][0]
        self.assertFalse(served.get("artifact_id"))
        self.assertTrue(served["degraded"])
        self.assertEqual(served["reason"], UNHOSTED_REASON)
        self.assertEqual(served["text_equivalent"], "A workshop bench with a torque wrench.")
        # The learner copy names the host capability, not a generation failure or a job code.
        self.assertIn("host", served["reason"])
        self.assertNotIn("job", served["reason"])
        self.assertNotIn("failed", served["reason"])

    def test_the_checkpoint_reports_the_unattempted_item(self) -> None:
        summary = self.generate_unhosted()
        checkpoint = summary.as_checkpoint()
        self.assertEqual(checkpoint["degraded"], 1)
        self.assertEqual(checkpoint["skipped"], 0)

    def test_an_ineligible_lesson_records_the_reason_but_counts_as_skipped(self) -> None:
        # A page a learner cannot open is not served, so the run counts the lesson as skipped, but
        # the stored item still says why there is no figure instead of looking authored without art.
        self.execute(
            "UPDATE gen_lessons SET state = 'needs_review' WHERE id = ?", (self.lesson_id,)
        )
        summary = self.generate_unhosted()
        self.assertEqual(summary.degraded, 0)
        self.assertEqual(summary.skipped, 1)
        item = self.stored_media()[0]
        self.assertTrue(item["degraded"])
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_DEGRADED)
        self.assertEqual(item["reason"], UNHOSTED_REASON)


if __name__ == "__main__":
    unittest.main()
