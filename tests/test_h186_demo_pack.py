"""H-186: the prepared demo is playable and gradable end to end.

These tests import the shipped `bundled/packs/japanese-affection-context-l0` archive through the
real dispatcher into a throwaway profile, then read it the way the Desktop does:

* ``pack.preview`` reports the two ``media[]`` links and their captions;
* ``pack.import`` writes one active lesson run per objective and two playable artifacts;
* ``lesson.page`` returns non-empty ``artifacts`` and ``media`` children whose caption and text
  equivalent are present (the 1049/460/200% renders read the same children);
* ``library.list`` points at the first objective as a Start, not the last run as a Resume;
* the fourth objective's corrected check grades a wrong answer ``not_yet`` and a correct answer
  ``pass`` with criteria, through the deterministic exact lane.

No provider is called, no network is used and no native-speaker review is claimed.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coursebook import archive, pack_flow, packs
from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"


class DemoPackCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-h186-"))
        self.addCleanup(shutil.rmtree, self.work, True)

    def import_demo(self) -> dict:
        manifest, files = archive.read_directory(JAPANESE)
        destination = self.work / "demo.zip"
        archive.write_archive(destination, manifest, files)
        staged_id = pack_flow.grant_local_file(destination)
        return self.ok("pack.import", {"staged_id": staged_id, "mode": "fresh"})["result"]

    def objective_id(self, course_id: str, ordinal: int) -> str:
        return str(self.scalar(
            "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
            " WHERE p.course_id = ? AND o.ordinal = ?",
            (course_id, ordinal),
        ))

    def check_row(self, objective_id: str) -> dict:
        row = self.rows("SELECT * FROM checks WHERE objective_id = ?", (objective_id,))
        self.assertEqual(len(row), 1)
        return row[0]

    def library_row(self, enrollment_id: str) -> dict:
        rows = self.ok("library.list", {})["result"]["items"]
        for row in rows:
            if row.get("enrollment_id") == enrollment_id:
                return row
        self.fail(f"no library row for {enrollment_id}")

    def open_check(self, enrollment_id: str, objective_id: str) -> dict:
        revision = int(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,)
        ))
        return self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]

    def submit_answer(self, enrollment_id: str, check: dict, answer: str, *, key: str) -> dict:
        revision = int(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,)
        ))
        response = self.ok(
            "attempt.submit",
            {
                "enrollment_id": enrollment_id,
                "check_id": check["id"],
                "check_version": int(check["version"]),
                "attempt_nonce": f"nonce-{key}",
                "answer": {"kind": "text", "text": answer},
            },
            expected_revision=revision,
            idempotency_key=key,
        )
        return response["result"]


class DemoPackMediaTest(DemoPackCase):
    def test_import_makes_one_active_run_per_objective_and_two_artifacts(self) -> None:
        result = self.import_demo()
        objectives = int(self.scalar(
            "SELECT COUNT(*) FROM objectives o JOIN plans p ON p.id = o.plan_id"
            " WHERE p.course_id = ?",
            (result["course_id"],),
        ))
        self.assertEqual(objectives, 4)
        runs = self.rows(
            "SELECT * FROM lesson_runs WHERE enrollment_id = ? ORDER BY created_at, rowid",
            (result["enrollment_id"],),
        )
        self.assertEqual(len(runs), objectives)
        self.assertEqual({row["state"] for row in runs}, {"active"})
        self.assertEqual(
            {row["objective_id"] for row in runs},
            {
                self.objective_id(result["course_id"], ordinal)
                for ordinal in range(1, objectives + 1)
            },
        )
        for run in runs:
            teaching = self.rows(
                "SELECT * FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal",
                (run["id"],),
            )
            self.assertTrue(any(row["kind"] == "teaching" for row in teaching))
            self.assertEqual(teaching[-1]["kind"], "check_prompt")

        artifacts = self.rows("SELECT * FROM artifacts")
        # H-197 added the Press Plate cover as this pack's third media artifact.
        self.assertEqual(len(artifacts), 3)
        self.assertEqual({row["kind"] for row in artifacts}, {"audio", "visual"})

    def test_lesson_page_returns_media_children_with_captions_and_text_equivalents(self) -> None:
        result = self.import_demo()
        manifest = packs.load_manifest(JAPANESE / "pack.json")
        captions = {link["path"]: link["caption"] for link in manifest["media"]}

        # H-197: objective 1 now carries the cover plate and then the relationship map, in
        # ``media[]`` order; objective 2 carries the narration.
        for ordinal, expected_paths in (
            (1, ["content/cover-16x9.png", "content/relationship-map.png"]),
            (2, ["content/narration-polite-confession.mp3"]),
        ):
            page = self.ok(
                "lesson.page",
                {
                    "enrollment_id": result["enrollment_id"],
                    "objective_id": self.objective_id(result["course_id"], ordinal),
                },
            )["result"]
            self.assertGreaterEqual(len(page["artifacts"]), 1, ordinal)
            children = [child for block in page["document"]["blocks"] for child in block["media"]]
            self.assertEqual(len(children), len(expected_paths), ordinal)
            for child, expected_path in zip(children, expected_paths):
                self.assertEqual(child["purpose"], captions[expected_path])
                self.assertEqual(child["text_equivalent"], captions[expected_path])
                self.assertTrue(child["text_equivalent"].strip())
                self.assertFalse(child["degraded"])
            media_segments = [row for row in page["segments"] if row["kind"] == "media"]
            self.assertEqual(len(media_segments), len(expected_paths))
            for segment, child in zip(media_segments, children):
                self.assertEqual(segment["artifact_id"], child["artifact_id"])
            for segment, expected_path in zip(media_segments, expected_paths):
                self.assertEqual(segment["text"], captions[expected_path])

        # A section with no link keeps a prose page and no invented media child.
        page = self.ok(
            "lesson.page",
            {
                "enrollment_id": result["enrollment_id"],
                "objective_id": self.objective_id(result["course_id"], 3),
            },
        )["result"]
        self.assertEqual(
            [child for block in page["document"]["blocks"] for child in block["media"]], []
        )


class DemoPackNextStepTest(DemoPackCase):
    def test_a_fresh_import_starts_at_objective_one(self) -> None:
        result = self.import_demo()
        row = self.library_row(result["enrollment_id"])
        self.assertEqual(row["next_step"]["kind"], "start_lesson")
        self.assertIn("Start", row["next_step"]["label"])
        self.assertEqual(
            row["evidence_summary"]["current_objective_id"],
            self.objective_id(result["course_id"], 1),
        )

    def test_the_next_step_is_the_first_incomplete_objective_not_the_last_run(self) -> None:
        result = self.import_demo()
        # Touch the last run so recency and ordinal disagree: a run-recency query would pick it.
        self.execute(
            "UPDATE lesson_runs SET updated_at = '2999-01-01T00:00:00Z'"
            " WHERE objective_id = ?",
            (self.objective_id(result["course_id"], 4),),
        )
        row = self.library_row(result["enrollment_id"])
        self.assertEqual(row["next_step"]["kind"], "start_lesson")
        self.assertEqual(
            row["evidence_summary"]["current_objective_id"],
            self.objective_id(result["course_id"], 1),
        )

        # Complete objective 1 with a cold pass; the next step moves to objective 2, not to 4.
        opened = self.open_check(result["enrollment_id"], self.objective_id(result["course_id"], 1))
        check = {"id": opened["check_id"], "version": opened["check_version"]}
        graded = self.submit_answer(result["enrollment_id"], check, "B", key="h186-obj1-pass")
        self.assertEqual(graded["verdict"], "pass")
        row = self.library_row(result["enrollment_id"])
        self.assertEqual(row["next_step"]["kind"], "start_lesson")
        self.assertEqual(
            row["evidence_summary"]["current_objective_id"],
            self.objective_id(result["course_id"], 2),
        )


class DemoPackGradingTest(DemoPackCase):
    def prepared_fourth_check(self) -> tuple[dict, dict]:
        result = self.import_demo()
        objective_id = self.objective_id(result["course_id"], 4)
        opened = self.open_check(result["enrollment_id"], objective_id)
        check = {"id": opened["check_id"], "version": opened["check_version"]}
        stored = self.check_row(objective_id)
        self.assertEqual(stored["state"], "open")
        reference = json.loads(stored["reference_json"])
        self.assertEqual(reference["kind"], "exact", reference)
        self.assertIn("A", reference["answers"])
        return result, check

    def test_a_wrong_answer_is_not_yet_with_criteria(self) -> None:
        result, check = self.prepared_fourth_check()
        wrong = self.submit_answer(result["enrollment_id"], check, "B", key="h186-obj4-wrong")
        self.assertEqual(wrong["verdict"], "not_yet")
        self.assertNotEqual(wrong["verdict"], "needs_retry")
        self.assertTrue(wrong["criteria"], "a graded attempt must return its criteria")
        self.assertEqual(
            self.scalar(
                "SELECT state FROM objectives WHERE id = ?",
                (self.objective_id(result["course_id"], 4),),
            ),
            "needs_review",
        )

    def test_a_correct_answer_passes_and_completes_the_objective(self) -> None:
        result, check = self.prepared_fourth_check()
        correct = self.submit_answer(result["enrollment_id"], check, "casual", key="h186-obj4-right")
        self.assertEqual(correct["verdict"], "pass")
        self.assertNotEqual(correct["verdict"], "needs_retry")
        self.assertTrue(correct["criteria"], "a graded attempt must return its criteria")
        self.assertEqual(
            self.scalar(
                "SELECT state FROM objectives WHERE id = ?",
                (self.objective_id(result["course_id"], 4),),
            ),
            "independent_evidence",
        )


if __name__ == "__main__":
    unittest.main()
