"""An imported pack must be *usable*: the page's question has to be gradable.

The pack lifecycle tests prove the content arrives. They did not prove the learner can answer
it: ``pack.import`` wrote a ``check_prompt`` lesson segment but no ``checks`` row, so every
imported course — including the bundled demo course a clean profile seeds from — had zero rows in
``checks``. ``check.open`` had nothing to open and ``attempt.submit`` could not be reached, which
is the "import it and it just works" promise failing at the first thing a learner does.

These tests drive the real dispatcher against a real migrated database and the real bundled packs.
"""

from __future__ import annotations

import json
from pathlib import Path

from coursebook import archive, pack_flow
from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
PARENT = ROOT / "bundled" / "packs" / "parent-measurement-practice"


class PackUsabilityCase(KernelCase):
    def import_bundle(self, source: Path, key: str) -> dict:
        manifest, files = archive.read_directory(source)
        destination = Path(self.home) / f"{source.name}.zip"
        archive.write_archive(destination, manifest, files)
        staged_id = pack_flow.grant_local_file(destination)
        return self.ok(
            "pack.import",
            {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key=key,
        )["result"]

    def first_objective(self, course_id: str) -> str:
        return str(
            self.scalar(
                "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                " WHERE p.course_id = ? ORDER BY o.ordinal",
                (course_id,),
            )
        )


class ImportedCheckTest(PackUsabilityCase):
    def test_an_imported_course_has_one_gradable_check_per_objective(self) -> None:
        imported = self.import_bundle(JAPANESE, "key-import-usable-1")
        objectives = int(
            self.scalar(
                "SELECT COUNT(*) FROM objectives WHERE plan_id IN"
                " (SELECT id FROM plans WHERE course_id = ?)",
                (imported["course_id"],),
            )
        )
        self.assertEqual(objectives, 4)
        checks = self.rows(
            "SELECT c.* FROM checks c JOIN objectives o ON o.id = c.objective_id"
            " JOIN plans p ON p.id = o.plan_id WHERE p.course_id = ?",
            (imported["course_id"],),
        )
        self.assertEqual(len(checks), objectives)
        self.assertEqual({row["state"] for row in checks}, {"open"})
        self.assertEqual({row["audit_state"] for row in checks}, {"passed"})
        # The judged item is the one the pack declared: the exact accepted answer set is sealed
        # in the reference, never invented by the importer.
        reference = json.loads(checks[0]["reference_json"])
        self.assertEqual(reference["kind"], "exact")
        self.assertTrue(reference["answers"])

    def test_an_imported_check_accepts_an_answer_and_commits_evidence(self) -> None:
        imported = self.import_bundle(JAPANESE, "key-import-usable-2")
        objective_id = self.first_objective(imported["course_id"])
        reference = json.loads(
            str(
                self.scalar(
                    "SELECT reference_json FROM checks WHERE objective_id = ?", (objective_id,)
                )
            )
        )
        answer = str(reference["answers"][0])

        opened = self.ok(
            "check.open",
            {"enrollment_id": imported["enrollment_id"], "objective_id": objective_id},
            expected_revision=0,
        )["result"]
        submitted = self.ok(
            "attempt.submit",
            {
                "enrollment_id": imported["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "attempt_nonce": "nonce-import-usable-1",
                "answer": {"kind": "text", "text": answer},
            },
            expected_revision=opened["revision"],
            idempotency_key="key-import-attempt-1",
        )["result"]

        self.assertEqual(submitted["verdict"], "pass")
        self.assertEqual(submitted["evidence_class"], "cold")
        self.assertGreater(int(self.scalar("SELECT COUNT(*) FROM evidence")), 0)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM transitions")), 1)

    def test_a_parent_pack_imports_no_gradable_check(self) -> None:
        imported = self.import_bundle(PARENT, "key-import-usable-3")
        self.assertEqual(
            int(
                self.scalar(
                    "SELECT COUNT(*) FROM checks c JOIN objectives o ON o.id = c.objective_id"
                    " JOIN plans p ON p.id = o.plan_id WHERE p.course_id = ?",
                    (imported["course_id"],),
                )
            ),
            0,
        )
