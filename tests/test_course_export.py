"""H-08: a course the learner authored packages itself.

The card's claim is that "package the result for reuse" works for a course created from a goal, not
only for a pack-backed course or a Parent Studio blueprint. These tests drive ``course.export.read``
and ``course.export`` through the real dispatcher against a real SQLite database, then hand the
written archive back to the real import pipeline: a course that exports but cannot be imported is
not a package for reuse.

Nothing here uses a prepared pack as proof. Every course is created through ``course.create`` and
its lessons are staged the way ``generation`` stages them (``gen_lessons.state = 'validated'``), so
the only content under test is content this test authored.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from coursebook import db, domain, generation, pack_flow, packs
from coursebook.parent_authoring import AUTHORED_LICENSE
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

GOAL = "Braise short ribs at home without a pressure cooker."
GEN_HASH = "sha256:" + "b" * 64
NOW = "2026-11-07T09:00:00Z"

#: Strings planted in tables the export must never read. If one reaches the archive or the
#: response, the allowlist failed.
NOTE_MARKER = "NOTE-MARKER-not-a-pack-file"
ATTEMPT_MARKER = "ANSWER-MARKER-not-in-the-archive"
#: A layer-1 observation note (cb.rpc v14 / cb.db v9). It is learner/parent prose about what
#: happened, so it belongs to the same "never export personal rows" rule as a notebook entry.
OBSERVATION_MARKER = "OBSERVATION-MARKER-not-a-pack-file"


def page_document(title: str) -> dict:
    """A validated learner page in the shape ``generation`` writes into ``gen_lessons.page_json``."""
    return {
        "section_title": title,
        "lesson_intent": "Sear the meat hard before the liquid goes in.",
        "segments": [
            {
                "kind": "explain",
                "heading": "Why the sear matters",
                "body": "Browning builds the flavour the braise will carry for two hours.",
            },
            {
                "kind": "model",
                "heading": "What good looks like",
                "body": "The ribs are dark brown on every face before they meet the liquid.",
            },
        ],
        "worked_example": {
            "prompt": "The pan is only warm.",
            "steps": ["Wait until the oil shimmers", "Lay the ribs away from you"],
            "answer": "Wait for the shimmer",
        },
        "learner_explanation": "Choose the moment that actually sears the meat.",
        "check": {
            "kind": "observation",
            # A short-answer prompt, deliberately: the pack audit refuses a learner page that
            # prints the reference answer verbatim, and a printed multiple-choice key does.
            "stimulus": {
                "prompt": "In one sentence, describe the moment the ribs go into the pan.",
                "format": "short_text",
            },
            "learner_instructions": "Write one sentence.",
            "evidence_target": "production",
            "scaffolds": {},
            "assistance_policy": {},
        },
        "sources": [],
        "media": [],
        "parent_notes": "Ask why a cold pan cannot sear.",
        "supervision_notes": ["Use the back burner"],
    }


class AuthoredCourseCase(KernelCase):
    """A learner course with a validated lesson per objective, built through the real commands."""

    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-course-export-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        # The generation staging tables are created by the generation module, not the kernel
        # migrations; a real profile gets them when a plan/lesson job first runs.
        with db.read() as connection:
            generation.ensure_schema(connection)

    # ── fixtures ────────────────────────────────────────────────────────
    def seed_course(
        self, *, sections: int = 2, recipe: str = "committed", approve: bool = True
    ) -> dict:
        created = self.ok(
            "course.create",
            {"title": "Braising at home", "recipe": recipe, "goal": GOAL, "locale": "en-US"},
        )["result"]
        course_id = created["course_id"]
        plan_id = created["plan_id"]
        objective_ids = []
        for ordinal in range(1, sections + 1):
            objective_ids.append(
                domain.record_objective(
                    plan_id,
                    title=f"Objective {ordinal}: sear and braise",
                    evidence_target="production",
                    criteria=criteria_with(numeric_spec()),
                )
            )
        # The plan's own criteria are the rubric source for the pack. Store plain sentences rather
        # than the check-spec dicts so the exported rubric reads like the authored criteria it is.
        for ordinal, objective_id in enumerate(objective_ids, start=1):
            self.execute(
                "UPDATE objectives SET evidence_criteria_json = ? WHERE id = ?",
                (
                    json.dumps(
                        [
                            f"Criterion {ordinal}a: browns the meat on every face",
                            f"Criterion {ordinal}b: keeps the heat steady",
                            f"Criterion {ordinal}c: does not crowd the pan",
                        ]
                    ),
                    objective_id,
                ),
            )
        enrollment_id = self.new_enrollment(course_id)
        if approve:
            self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "enrollment_id": enrollment_id,
            "objective_ids": objective_ids,
        }

    def seed_validated_lessons(self, seeded: dict, *, sections: int | None = None) -> None:
        """Stage what ``generation`` stages: one section + one validated lesson per objective."""
        plan_id = seeded["plan_id"]
        course_id = seeded["course_id"]
        objective_ids = seeded["objective_ids"]
        count = len(objective_ids) if sections is None else sections
        with db.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO gen_plan_documents (id, plan_id, course_id,"
                " request_fingerprint, plan_hash, document_json, research_json, generation_state,"
                " validation_id, result_json, created_at)"
                " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
                (f"gpd_{plan_id}", plan_id, course_id, GEN_HASH, NOW),
            )
            for ordinal in range(1, count + 1):
                section_id = f"sec_{ordinal}_{plan_id}"
                lesson_id = f"lsn_{ordinal}_{plan_id}"
                check_id = f"chk_{ordinal}_{plan_id}"
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                    " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                    " VALUES (?, ?, ?, ?, ?, 'Sear first, then braise.', ?, '[]', '[]')",
                    (
                        section_id,
                        plan_id,
                        ordinal,
                        GEN_HASH,
                        f"Section {ordinal}: the sear",
                        f"[{ordinal}]",
                    ),
                )
                connection.execute(
                    "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                    " page_json, media_json, parent_notes_json, rejection_reasons_json,"
                    " validation_id, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', '{}', '[]', NULL, ?, ?)",
                    (
                        lesson_id,
                        plan_id,
                        section_id,
                        GEN_HASH,
                        json.dumps(page_document(f"Section {ordinal}: the sear")),
                        NOW,
                        NOW,
                    ),
                )
                connection.execute(
                    "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
                    " rubric_json, reference_json, locale, audit_state, state, created_at)"
                    " VALUES (?, ?, 1, 'production', ?, ?, ?, 'en-US', 'passed', 'open', ?)",
                    (
                        check_id,
                        objective_ids[ordinal - 1],
                        json.dumps(
                            {"prompt": "When do the ribs go into the pan?", "format": "selection"}
                        ),
                        json.dumps(
                            {
                                "criteria": [
                                    {"criterion": "a", "description": "Browns every face"},
                                    {"criterion": "b", "description": "Keeps the heat steady"},
                                    {"criterion": "c", "description": "Does not crowd the pan"},
                                ]
                            }
                        ),
                        json.dumps(
                            {
                                "reference_answer": "When the oil shimmers and the pan is hot",
                                "accepted_answers": [],
                                "accepted_alternatives": [],
                            }
                        ),
                        NOW,
                    ),
                )
                connection.execute(
                    "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref)"
                    " VALUES (?, ?, ?)",
                    (lesson_id, check_id, ordinal),
                )

    def seed_learning_history(self, seeded: dict) -> None:
        """Personal rows that exist for this enrollment and must never reach an export."""
        enrollment_id = seeded["enrollment_id"]
        objective_id = seeded["objective_ids"][0]
        domain.record_observation(
            enrollment_id, objective_id, evidence_class="parent_reported", note=OBSERVATION_MARKER
        )
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO notebook_entries (id, enrollment_id, objective_id, lesson_run_id,"
                " kind, excerpt, note, tags_json, source_ref, created_at, updated_at)"
                " VALUES ('nbt_marker', ?, ?, NULL, 'personal_note', ?, ?, '[]', NULL, ?, ?)",
                (enrollment_id, objective_id, NOTE_MARKER, NOTE_MARKER, NOW, NOW),
            )
            connection.execute(
                "INSERT INTO notebook_entries (id, enrollment_id, objective_id, lesson_run_id,"
                " kind, excerpt, note, tags_json, source_ref, created_at, updated_at)"
                " VALUES ('nbt_marker_2', ?, ?, NULL, 'quiz_moment', ?, ?, '[]', NULL, ?, ?)",
                (enrollment_id, objective_id, ATTEMPT_MARKER, ATTEMPT_MARKER, NOW, NOW),
            )

    def export(self, enrollment_id: str, expected_hash: str, *, key: str = "key-export-1") -> dict:
        return self.ok(
            "course.export",
            {"enrollment_id": enrollment_id, "expected_content_hash": expected_hash},
            idempotency_key=key,
        )["result"]

    def archive_path(self, result: dict) -> Path:
        row = self.rows(
            "SELECT path FROM artifacts WHERE id = ?", (result["artifacts"][0]["artifact_id"],)
        )[0]
        return Path(str(row["path"]))

    def artifacts(self, kind: str = "export") -> int:
        return int(self.scalar("SELECT COUNT(*) FROM artifacts WHERE kind = ?", (kind,)))

    def export_files(self) -> list[Path]:
        root = pack_flow.export_root()
        if not root.is_dir():
            return []
        return sorted(root.glob("*.zip"))


class CourseExportReadTest(AuthoredCourseCase):
    """The review half: exact files, content hash, rights and the no-upload statement."""

    def test_a_validated_authored_course_is_ready_with_an_exact_file_list(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)

        read = self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})["result"]

        self.assertTrue(read["ready"], read)
        self.assertIsNone(read["blocked_reason"])
        self.assertIsNone(read["blocked_message"])
        self.assertEqual(read["problems"], [])
        self.assertFalse(read["pack_backed"])
        self.assertRegex(read["content_hash"], r"^sha256:[a-f0-9]{64}$")
        self.assertEqual(read["license"], AUTHORED_LICENSE)
        self.assertIn("All rights reserved", read["rights"])
        self.assertIn("Nothing was uploaded", read["no_upload"])
        self.assertEqual(read["plan"]["plan_id"], seeded["plan_id"])
        self.assertEqual(read["plan"]["state"], "approved")
        self.assertEqual(read["sections"], {"total": 2, "validated": 2})

        # Two sections, three files each, every one hashed and sized: the list is the manifest.
        self.assertEqual(len(read["files"]), 6)
        self.assertEqual(
            {item["role"] for item in read["files"]},
            {"parent_guide", "learner_page", "answer_guide"},
        )
        for item in read["files"]:
            self.assertRegex(item["sha256"], r"^sha256:[a-f0-9]{64}$")
            self.assertGreater(item["bytes"], 0)
            self.assertEqual(item["mime"], "text/markdown")
            self.assertNotIn("\\", item["name"])
            self.assertFalse(item["name"].startswith("/"))

    def test_the_review_read_writes_nothing(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        before = self.artifacts()
        for _ in range(3):
            self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})
        self.assertEqual(self.artifacts(), before)
        self.assertEqual(self.export_files(), [])

    def test_an_unapproved_plan_blocks_the_export(self) -> None:
        seeded = self.seed_course(approve=False)
        self.seed_validated_lessons(seeded)

        read = self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})["result"]
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "plan_not_approved")
        self.assertIsNone(read["content_hash"])
        self.assertEqual(read["files"], [])

        error = self.err(
            "course.export",
            {"enrollment_id": seeded["enrollment_id"], "expected_content_hash": "sha256:" + "0" * 64},
            idempotency_key="key-unapproved",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "plan_not_approved")
        self.assertEqual(self.artifacts(), 0)
        self.assertEqual(self.export_files(), [])

    def test_an_approved_plan_with_no_lessons_blocks_the_export(self) -> None:
        seeded = self.seed_course()

        read = self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})["result"]
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "no_generated_content")
        self.assertEqual(read["sections"], {"total": 0, "validated": 0})

        error = self.err(
            "course.export",
            {"enrollment_id": seeded["enrollment_id"], "expected_content_hash": "sha256:" + "0" * 64},
            idempotency_key="key-empty",
        )
        self.assertEqual(error["details"]["reason"], "no_generated_content")
        self.assertEqual(self.artifacts(), 0)

    def test_a_page_parked_for_review_blocks_the_export_and_is_named(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        self.execute(
            "UPDATE gen_lessons SET state = 'needs_review' WHERE id = ?",
            (f"lsn_2_{seeded['plan_id']}",),
        )

        read = self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})["result"]
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "lessons_not_validated")
        self.assertEqual(read["sections"], {"total": 2, "validated": 1})
        self.assertEqual(len(read["problems"]), 1)
        self.assertIn("section 2", read["problems"][0])
        self.assertIn("needs_review", read["problems"][0])

        reviewed = read["content_hash"] or ("sha256:" + "0" * 64)
        error = self.err(
            "course.export",
            {"enrollment_id": seeded["enrollment_id"], "expected_content_hash": reviewed},
            idempotency_key="key-unvalidated",
        )
        self.assertEqual(error["details"]["reason"], "lessons_not_validated")
        self.assertEqual(self.artifacts(), 0)
        self.assertEqual(self.export_files(), [])

    def test_a_pack_backed_course_is_told_to_use_pack_export(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]["content_hash"]
        exported = self.export(seeded["enrollment_id"], reviewed, key="key-authored-first")

        staged_id = pack_flow.grant_local_file(self.archive_path(exported))
        self.ok("pack.preview", {"staged_id": staged_id})
        imported = self.ok(
            "pack.import",
            {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key="key-import-authored",
        )["result"]

        read = self.ok("course.export.read", {"enrollment_id": imported["enrollment_id"]})["result"]
        self.assertFalse(read["ready"])
        self.assertTrue(read["pack_backed"])
        self.assertEqual(read["blocked_reason"], "course_pack_backed")
        self.assertEqual(read["files"], [])

        error = self.err(
            "course.export",
            {
                "enrollment_id": imported["enrollment_id"],
                "expected_content_hash": "sha256:" + "0" * 64,
            },
            idempotency_key="key-pack-backed",
        )
        self.assertEqual(error["details"]["reason"], "course_pack_backed")


class CourseExportWriteTest(AuthoredCourseCase):
    """The write half: a real archive, a real artifact, a real import."""

    def test_the_export_writes_a_verifiable_archive_that_imports_as_a_course(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]

        result = self.export(seeded["enrollment_id"], reviewed["content_hash"], key="key-round-trip")

        # The exported identity is the reviewed content, not a different page the caller never saw.
        self.assertEqual(result["content_hash"], reviewed["content_hash"])
        self.assertTrue(result["pack"]["pack_id"].startswith("authored-"))
        self.assertEqual(result["pack"]["pack_version"], "1.0.0")
        self.assertRegex(result["pack"]["manifest_hash"], r"^sha256:[a-f0-9]{64}$")
        self.assertEqual(result["license"], AUTHORED_LICENSE)
        self.assertIn("Nothing was uploaded", result["no_upload"])
        self.assertEqual(len(result["files"]), len(reviewed["files"]))
        self.assertEqual([item["name"] for item in result["files"]],
                         [item["name"] for item in reviewed["files"]])
        self.assertEqual(len(result["artifacts"]), 1)
        artifact = result["artifacts"][0]
        self.assertEqual(artifact["kind"], "export")
        self.assertEqual(artifact["mime"], "application/zip")

        # The bytes on disk re-hash to the manifest they declare: never trust the writer.
        archive = self.archive_path(result)
        self.assertTrue(archive.is_file())
        self.assertEqual(artifact["content_hash"], packs.file_sha256(archive.read_bytes()))
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            manifest_name = [name for name in names if name.count("/") == 1 and name.endswith("/pack.json")].pop()
            document = json.loads(bundle.read(manifest_name).decode("utf-8"))
            lessons = [name for name in names if "/lessons/" in name]
            lesson_text = bundle.read(sorted(lessons)[0]).decode("utf-8")
        packs.verify_content_hash(document)
        self.assertEqual(document["content_hash"], result["pack"]["manifest_hash"])
        self.assertEqual(set(document) - set(packs.export_allowlist()), set())
        self.assertEqual(document["license"], AUTHORED_LICENSE)
        self.assertEqual(document["contributors"], [{"name": "Course author", "role": "author"}])
        self.assertTrue(document["attribution"].endswith("authored in Coursebook."))
        self.assertEqual(len(document["objectives"]), 2)
        for objective in document["objectives"]:
            self.assertEqual(len(objective["sections"]), 1)
            self.assertEqual(len(objective["checks"]), 1)
            self.assertGreaterEqual(len(objective["checks"][0]["rubric"]), packs.MIN_RUBRIC_CRITERIA)
        # The text is in the archive as Markdown; the learner surface offers no PDF.
        self.assertEqual(len(lessons), 2)
        self.assertIn("Section 1: the sear", lesson_text)
        self.assertTrue(all(item["mime"] == "text/markdown" for item in result["files"]))
        self.assertFalse(any(item["kind"] == "pdf" for item in result["artifacts"]))

        # Import round-trip: the same pipeline any pack goes through cuts a real course.
        staged_id = pack_flow.grant_local_file(archive)
        preview = self.ok("pack.preview", {"staged_id": staged_id})["result"]
        self.assertEqual(preview["manifest"]["pack_id"], result["pack"]["pack_id"])
        imported = self.ok(
            "pack.import",
            {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key="key-import-round-trip",
        )["result"]
        self.assertNotEqual(imported["course_id"], seeded["course_id"])
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM objectives WHERE plan_id IN"
                            " (SELECT id FROM plans WHERE course_id = ?)", (imported["course_id"],))),
            2,
        )
        page = self.ok(
            "lesson.page",
            {
                "enrollment_id": imported["enrollment_id"],
                "objective_id": str(self.scalar(
                    "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                    " WHERE p.course_id = ? ORDER BY o.ordinal", (imported["course_id"],)
                )),
            },
        )["result"]
        self.assertTrue(page["section"]["title"])

        # The imported course is pack-backed: its bytes belong to pack.export, not course.export.
        repack = self.ok(
            "pack.export",
            {"enrollment_id": imported["enrollment_id"]},
            idempotency_key="key-export-imported",
        )["result"]
        self.assertEqual(repack["content_hash"], document["content_hash"])

    def test_learning_history_cannot_reach_the_archive(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        self.seed_learning_history(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]

        # The review read does not leak either: nothing personal is on the wire.
        wire = json.dumps(reviewed)
        self.assertNotIn(NOTE_MARKER, wire)
        self.assertNotIn(ATTEMPT_MARKER, wire)
        self.assertNotIn(OBSERVATION_MARKER, wire)
        self.assertNotIn("notebook", wire)
        self.assertNotIn("attempts", wire)

        result = self.export(seeded["enrollment_id"], reviewed["content_hash"], key="key-private")
        self.assertNotIn(NOTE_MARKER, json.dumps(result))
        self.assertNotIn(ATTEMPT_MARKER, json.dumps(result))
        self.assertNotIn(OBSERVATION_MARKER, json.dumps(result))

        with zipfile.ZipFile(self.archive_path(result)) as bundle:
            for name in bundle.namelist():
                payload = bundle.read(name)
                self.assertNotIn(NOTE_MARKER.encode(), payload, name)
                self.assertNotIn(ATTEMPT_MARKER.encode(), payload, name)
                self.assertNotIn(OBSERVATION_MARKER.encode(), payload, name)
            manifest_name = [name for name in bundle.namelist() if name.endswith("/pack.json")].pop()
            document = json.loads(bundle.read(manifest_name).decode("utf-8"))
        self.assertEqual(packs.contains_private_fields(document), [])

    def test_a_changed_page_blocks_a_reviewed_hash_and_writes_nothing(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]["content_hash"]

        # The page is edited after review: the reviewed hash is now the wrong page.
        self.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?",
            (
                json.dumps(page_document("Section 1: a different page")),
                f"lsn_1_{seeded['plan_id']}",
            ),
        )
        error = self.err(
            "course.export",
            {"enrollment_id": seeded["enrollment_id"], "expected_content_hash": reviewed},
            idempotency_key="key-stale",
        )
        self.assertEqual(error["code"], "DELETE_SCOPE_STALE")
        self.assertIn("current_data_scope_hash", error["details"])
        self.assertNotEqual(error["details"]["current_data_scope_hash"], reviewed)
        self.assertEqual(self.artifacts(), 0)
        self.assertEqual(self.export_files(), [])

        # Re-reading gives the new hash, and exporting that page works: the fence is the text.
        fresh = self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})["result"]
        self.assertNotEqual(fresh["content_hash"], reviewed)
        result = self.export(seeded["enrollment_id"], fresh["content_hash"], key="key-fresh")
        self.assertEqual(result["content_hash"], fresh["content_hash"])

    def test_a_changed_page_after_a_final_approval_blocks(self) -> None:
        # A Parent Studio course carries an active final approval. course.export does not require
        # one, but it honours it: text an adult signed off cannot change and then ship.
        seeded = self.seed_course(recipe="parent")
        self.seed_validated_lessons(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]
        self.assertTrue(reviewed["ready"])
        self.execute(
            "INSERT INTO final_approvals (id, course_id, plan_id, plan_hash, content_hash, state,"
            " invalidation_reason, approved_at, superseded_at)"
            " VALUES ('fap_test', ?, ?, ?, ?, 'active', NULL, ?, NULL)",
            (
                seeded["course_id"],
                seeded["plan_id"],
                domain.plan_hash(seeded["plan_id"]),
                reviewed["content_hash"],
                NOW,
            ),
        )
        still_ready = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]
        self.assertTrue(still_ready["ready"])

        self.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?",
            (
                json.dumps(page_document("Section 2: edited after approval")),
                f"lsn_2_{seeded['plan_id']}",
            ),
        )
        read = self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})["result"]
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "changes_need_review")

        error = self.err(
            "course.export",
            {"enrollment_id": seeded["enrollment_id"], "expected_content_hash": reviewed["content_hash"]},
            idempotency_key="key-approved-changed",
        )
        self.assertEqual(error["details"]["reason"], "changes_need_review")
        self.assertEqual(self.artifacts(), 0)

    def test_the_same_key_replays_and_a_different_payload_conflicts(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]["content_hash"]

        first = self.export(seeded["enrollment_id"], reviewed, key="key-replay")
        second = self.ok(
            "course.export",
            {"enrollment_id": seeded["enrollment_id"], "expected_content_hash": reviewed},
            idempotency_key="key-replay",
        )["result"]
        self.assertEqual(first, second)
        self.assertEqual(self.artifacts(), 1)

        conflict = self.err(
            "course.export",
            {
                "enrollment_id": seeded["enrollment_id"],
                "expected_content_hash": "sha256:" + "1" * 64,
            },
            idempotency_key="key-replay",
        )
        self.assertEqual(conflict["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.artifacts(), 1)

    def test_a_second_export_of_unchanged_text_reuses_the_artifact(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]["content_hash"]
        first = self.export(seeded["enrollment_id"], reviewed, key="key-artifact-1")
        second = self.export(seeded["enrollment_id"], reviewed, key="key-artifact-2")
        self.assertEqual(
            first["artifacts"][0]["artifact_id"], second["artifacts"][0]["artifact_id"]
        )
        self.assertEqual(self.artifacts(), 1)

    def test_the_export_requires_a_validated_hash_not_just_any_hash(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        error = self.err(
            "course.export",
            {"enrollment_id": seeded["enrollment_id"], "expected_content_hash": "sha256:" + "2" * 64},
            idempotency_key="key-blind",
        )
        self.assertEqual(error["code"], "DELETE_SCOPE_STALE")
        self.assertEqual(self.artifacts(), 0)
        self.assertEqual(self.export_files(), [])


class CourseExportCrossProfileImportTest(AuthoredCourseCase):
    """H-121: the archive a learner exports is importable on a *different* profile.

    Profile A authors the course and exports it; profile B is a second, empty ``HERMES_HOME``. The
    only thing that travels is the zip. Nothing else is copied: no database file, no packs directory,
    no learner rows. That makes the assertions here the real cross-profile claim rather than a
    same-database round trip.
    """

    def _fresh_profile(self) -> str:
        other = tempfile.mkdtemp(prefix="coursebook-kernel-profile-b-")
        self.addCleanup(shutil.rmtree, other, True)
        os.environ["HERMES_HOME"] = other
        db.migrate()
        return other

    def test_exported_course_imports_into_a_fresh_profile_with_resume_and_fresh(self) -> None:
        seeded = self.seed_course()
        self.seed_validated_lessons(seeded)
        self.seed_learning_history(seeded)
        reviewed = self.ok(
            "course.export.read", {"enrollment_id": seeded["enrollment_id"]}
        )["result"]
        exported = self.export(seeded["enrollment_id"], reviewed["content_hash"], key="key-cross-profile")
        archive = self.archive_path(exported)
        self.assertTrue(archive.is_file())
        origin_attempts = self.artifacts("export")

        # ── a genuinely different profile: new home, new database, none of A's rows ──
        profile_b = self._fresh_profile()
        self.assertTrue(str(profile_b) in str(pack_flow.data_root()))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM packs"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM notebook_entries"), 0)

        staged = pack_flow.grant_local_file(archive)
        preview = self.ok("pack.preview", {"staged_id": staged})["result"]
        # The pack identity is the reviewed manifest hash, byte-for-byte what A exported.
        self.assertEqual(preview["manifest"]["content_hash"], exported["pack"]["manifest_hash"])
        self.assertEqual(preview["manifest"]["pack_id"], exported["pack"]["pack_id"])

        first = self.ok(
            "pack.import",
            {"staged_id": staged, "mode": "fresh"},
            idempotency_key="key-b-fresh",
        )["result"]
        self.assertEqual(first["pack_id"], exported["pack"]["pack_id"])
        self.assertNotEqual(first["enrollment_id"], seeded["enrollment_id"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM packs"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments"), 1)

        # Resume names the *existing* classroom and writes no second course for the same pack.
        resume_stage = pack_flow.grant_local_file(archive)
        resumed = self.ok(
            "pack.import",
            {"staged_id": resume_stage, "mode": "resume"},
            idempotency_key="key-b-resume",
        )["result"]
        self.assertEqual(resumed["course_id"], first["course_id"])
        self.assertEqual(resumed["enrollment_id"], first["enrollment_id"])
        self.assertEqual(int(resumed["revision"]), int(first["revision"]))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments"), 1)

        # A fresh run is a distinct enrollment on the same immutable content: one pack row, two
        # enrollments, and each course id is its own — pack identity is never the enrollment id.
        fresh_stage = pack_flow.grant_local_file(archive)
        second = self.ok(
            "pack.import",
            {"staged_id": fresh_stage, "mode": "fresh"},
            idempotency_key="key-b-fresh-2",
        )["result"]
        self.assertNotEqual(second["enrollment_id"], first["enrollment_id"])
        self.assertNotEqual(second["course_id"], first["course_id"])
        self.assertEqual(second["pack_id"], first["pack_id"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM packs"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments"), 2)

        # No learner history travelled: the fresh profile starts with empty personal tables, even
        # though profile A had a notebook note and an observation for the same course text.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM notebook_entries"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)

        # The imported course serves real lesson pages in profile B and re-exports through
        # pack.export (not course.export: the imported course is pack-backed).
        page = self.ok(
            "lesson.page",
            {
                "enrollment_id": first["enrollment_id"],
                "objective_id": str(self.scalar(
                    "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                    " WHERE p.course_id = ? ORDER BY o.ordinal", (first["course_id"],)
                )),
            },
        )["result"]
        self.assertTrue(page["section"]["title"])
        repack = self.ok(
            "pack.export",
            {"enrollment_id": first["enrollment_id"]},
            idempotency_key="key-b-repack",
        )["result"]
        self.assertEqual(repack["content_hash"], exported["pack"]["manifest_hash"])

        # A's export artifact still exists on A; nothing from here was uploaded or published.
        self.assertEqual(origin_attempts, 1)


#: The reference answer ``seed_validated_lessons`` writes for every check.
CHECK_KEY = "When the oil shimmers and the pan is hot"


class AuthoredAnswerLeakGateTest(AuthoredCourseCase):
    """H-173d follow-up: pack export mirrors the presenting-surface rule.

    A lesson may present the form it checks on exactly one surface (``kind: model`` segments,
    ``role: narration`` media, and the model's projected block); every other learner surface stays
    scanned. An authored ``document`` carries no segment kind, so it has no presenting surface and
    every block is scanned (the strict reading recorded in docs/DECISION-TAUGHT-TARGET.md §7).
    """

    def set_page(self, seeded: dict, page: dict) -> None:
        self.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?",
            (json.dumps(page), f"lsn_1_{seeded['plan_id']}"),
        )

    def one_section(self) -> dict:
        seeded = self.seed_course(sections=1)
        self.seed_validated_lessons(seeded, sections=1)
        return seeded

    def read(self, seeded: dict) -> dict:
        return self.ok("course.export.read", {"enrollment_id": seeded["enrollment_id"]})["result"]

    def test_the_key_in_the_model_segment_exports(self) -> None:
        seeded = self.one_section()
        page = page_document("Section 1: the sear")
        # The model segment is the one authored surface allowed to teach the keyed form.
        page["segments"][1] = {
            "kind": "model",
            "heading": "What good looks like",
            "body": CHECK_KEY,
        }
        self.set_page(seeded, page)

        read = self.read(seeded)
        self.assertTrue(read["ready"], read)
        self.assertIsNone(read["blocked_reason"])

        result = self.export(seeded["enrollment_id"], read["content_hash"], key="key-model-export")
        archive = self.archive_path(result)
        with zipfile.ZipFile(archive) as bundle:
            lessons = sorted(name for name in bundle.namelist() if "/lessons/" in name)
            self.assertEqual(len(lessons), 1)
            # The exported learner page really does present it: this is not a gate-only exemption.
            self.assertIn(CHECK_KEY, bundle.read(lessons[0]).decode("utf-8"))

    def test_the_key_in_the_explanation_still_blocks_the_export(self) -> None:
        seeded = self.one_section()
        page = page_document("Section 1: the sear")
        page["learner_explanation"] = f"Choose this: {CHECK_KEY}"
        self.set_page(seeded, page)

        read = self.read(seeded)
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "answer_leak_in_learner_page")
        self.assertEqual(read["files"], [])

        error = self.err(
            "course.export",
            {
                "enrollment_id": seeded["enrollment_id"],
                "expected_content_hash": "sha256:" + "3" * 64,
            },
            idempotency_key="key-explanation-leak",
        )
        self.assertEqual(error["details"]["reason"], "answer_leak_in_learner_page")
        self.assertEqual(self.artifacts(), 0)
        self.assertEqual(self.export_files(), [])

    def test_the_key_in_a_guided_segment_still_blocks_the_export(self) -> None:
        seeded = self.one_section()
        page = page_document("Section 1: the sear")
        page["segments"][0] = {
            "kind": "guided",
            "heading": "Try it",
            "body": f"Say: {CHECK_KEY}",
        }
        self.set_page(seeded, page)

        read = self.read(seeded)
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "answer_leak_in_learner_page")
        self.assertEqual(self.artifacts(), 0)

    def test_an_authored_document_that_presents_its_key_is_refused(self) -> None:
        # No segment kinds: a document block can only present through a role that also carries
        # the worked example, so under the strict reading it is scanned.
        seeded = self.one_section()
        page = {
            "section_title": "Section 1: the sear",
            "document": {
                "section_title": "Section 1: the sear",
                "blocks": [
                    {
                        "role": "example",
                        "headline": "What good looks like",
                        "short": "",
                        "deep": CHECK_KEY,
                    }
                ],
            },
        }
        self.set_page(seeded, page)

        read = self.read(seeded)
        self.assertFalse(read["ready"])
        self.assertEqual(read["blocked_reason"], "answer_leak_in_learner_page")
        self.assertEqual(self.artifacts(), 0)

    def test_an_authored_document_without_the_key_still_exports(self) -> None:
        seeded = self.one_section()
        page = {
            "section_title": "Section 1: the sear",
            "document": {
                "section_title": "Section 1: the sear",
                "blocks": [
                    {
                        "role": "example",
                        "headline": "What good looks like",
                        "short": "",
                        "deep": "The ribs are dark brown on every face before they meet the liquid.",
                    }
                ],
            },
        }
        self.set_page(seeded, page)

        read = self.read(seeded)
        self.assertTrue(read["ready"], read)
        self.assertIsNone(read["blocked_reason"])


if __name__ == "__main__":
    unittest.main()
