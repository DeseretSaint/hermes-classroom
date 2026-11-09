"""GM-005: the take-home pack backend over an existing Game or Textbook lesson.

These tests drive the real dispatcher against a real migrated SQLite database. Every course is
created through ``course.create`` and its lessons are staged the way ``generation`` stages them
(``gen_lessons.state = 'validated'``), so the only content under test is content this test
authored. The pack must:

* read the source lesson and never mutate, clone or re-approve the course;
* bind the row to the exact lesson version and content hash it rendered;
* keep the learner page free of the answer guide and the answer guide in its own page;
* export real, selectable-text PDF bytes through the existing artifact store;
* work for a Textbook course that has no world art;
* carry a technical diagram only when it is deterministic or sourced;
* fail with a named error, never a blank pack, when the source is missing.

The tests are named exactly as the GM-005 card names them.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from coursebook import db, domain, generation
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

GEN_HASH = "sha256:" + "b" * 64
NOW = "2026-11-07T09:00:00Z"

#: Strings that only exist in the answer guide. If one appears on the learner page, the
#: separation failed.
ANSWER_MARKER = "REFERENCE-ONLY: shimmers before the meat goes in"
RUBRIC_MARKER = "RUBRIC-ONLY: browns every face without crowding"
#: A learner page sentence that must survive on the page verbatim.
LEARNER_MARKER = "Watch the oil, then lay the ribs away from you."


def page_document(title: str, *, media: list[dict] | None = None, procedure: bool = False) -> dict:
    """A validated learner page in the shape ``generation`` writes into ``gen_lessons.page_json``."""
    page: dict = {
        "section_title": title,
        "lesson_intent": "Sear the meat hard before the liquid goes in.",
        "segments": [
            {
                "kind": "explain",
                "heading": "Why the sear matters",
                "body": "Browning builds the flavour the braise carries for two hours.",
            },
            {
                "kind": "guided",
                "heading": "Do this next",
                "body": LEARNER_MARKER,
            },
        ],
        "worked_example": {
            "prompt": "The pan is only warm.",
            "steps": ["Wait until the oil shimmers", "Lay the ribs away from you"],
            "answer": "Wait for the shimmer",
        },
        "learner_explanation": "Choose the moment that actually sears the meat.",
        "check": {
            "kind": "short_answer",
            "stimulus": {"prompt": "In one sentence, describe the moment the ribs go in.", "format": "short_text"},
            "learner_instructions": "Write one sentence.",
            "evidence_target": "production",
        },
        "sources": [],
        "media": list(media or []),
        "parent_notes": "Ask why a cold pan cannot sear.",
        "supervision_notes": ["Use the back burner"],
    }
    if procedure:
        page["procedure"] = {
            "steps": ["Heat the pan", "Sear every face", "Lower the heat and add liquid"],
            "hazards": ["Hot oil"],
            "tools": ["Heavy pan", "Tongs"],
        }
    return page


class TakeHomeCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-takehome-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        with db.read() as connection:
            generation.ensure_schema(connection)

    # ── fixtures ────────────────────────────────────────────────────────────
    def seed_course(
        self,
        *,
        sections: int = 2,
        recipe: str = "committed",
        media: list[dict] | None = None,
        procedure: bool = False,
    ) -> dict:
        created = self.ok(
            "course.create",
            {
                "title": "Braising at home",
                "recipe": recipe,
                "goal": "Braise short ribs at home without a pressure cooker.",
                "locale": "en-US",
            },
        )["result"]
        course_id = created["course_id"]
        plan_id = created["plan_id"]
        objective_ids: list[str] = []
        for ordinal in range(1, sections + 1):
            objective_ids.append(
                domain.record_objective(
                    plan_id,
                    title=f"Objective {ordinal}: sear and braise",
                    evidence_target="production",
                    criteria=criteria_with(numeric_spec()),
                )
            )
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
        self.approve(enrollment_id, plan_id, 0)
        seeded = {
            "course_id": course_id,
            "plan_id": plan_id,
            "enrollment_id": enrollment_id,
            "objective_ids": objective_ids,
        }
        self.seed_validated_lessons(seeded, media=media, procedure=procedure)
        return seeded

    def seed_validated_lessons(
        self,
        seeded: dict,
        *,
        media: list[dict] | None = None,
        procedure: bool = False,
    ) -> None:
        plan_id = seeded["plan_id"]
        course_id = seeded["course_id"]
        objective_ids = seeded["objective_ids"]
        with db.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO gen_plan_documents (id, plan_id, course_id,"
                " request_fingerprint, plan_hash, document_json, research_json, generation_state,"
                " validation_id, result_json, created_at)"
                " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
                (f"gpd_{plan_id}", plan_id, course_id, GEN_HASH, NOW),
            )
            for ordinal in range(1, len(objective_ids) + 1):
                section_id = f"sec_{ordinal}_{plan_id}"
                lesson_id = f"lsn_{ordinal}_{plan_id}"
                check_id = f"chk_{ordinal}_{plan_id}"
                title = f"Section {ordinal}: the sear"
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                    " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                    " VALUES (?, ?, ?, ?, ?, 'Sear first, then braise.', ?, '[]', '[]')",
                    (section_id, plan_id, ordinal, GEN_HASH, title, f"[{ordinal}]"),
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
                        json.dumps(page_document(title, media=media, procedure=procedure)),
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
                        json.dumps({"prompt": "When do the ribs go into the pan?", "format": "selection"}),
                        json.dumps(
                            {
                                "criteria": [
                                    {"criterion": "a", "description": "Browns every face"},
                                    {"criterion": "b", "description": RUBRIC_MARKER},
                                    {"criterion": "c", "description": "Does not crowd the pan"},
                                ]
                            }
                        ),
                        json.dumps(
                            {
                                "reference_answer": ANSWER_MARKER,
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

    def add_approved_world(self, seeded: dict) -> dict:
        """One approved world with a cover plate, after the course exists."""
        artifact = self._artifact()
        world_id = f"wld_{seeded['course_id']}"
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO course_worlds (id, course_id, revision, state, brief_json,"
                " concepts_json, selected_concept_id, style_hash, kit_hash, approved_hash,"
                " approved_at, created_at, updated_at)"
                " VALUES (?, ?, 1, 'approved', '{}', '[]', 'c1', ?, ?, ?, ?, ?, ?)",
                (world_id, seeded["course_id"], "sha256:" + "c" * 64, "sha256:" + "d" * 64,
                 "sha256:" + "e" * 64, NOW, NOW, NOW),
            )
            connection.execute(
                "INSERT INTO world_assets (id, world_id, role, section_id, section_key,"
                " artifact_id, style_hash, prompt_hash, textless, created_at)"
                " VALUES (?, ?, 'cover', NULL, '', ?, ?, ?, 1, ?)",
                (f"was_{world_id}", world_id, artifact, "sha256:" + "c" * 64, "sha256:" + "f" * 64, NOW),
            )
        return {"world_id": world_id, "artifact_id": artifact}

    def add_full_world(self, seeded: dict, *, sections: int = 6, scenes: int = 2) -> int:
        """A complete approved world kit: one cover, per-section plates and lesson scenes."""
        artifact = self._artifact()
        world_id = f"wld_full_{seeded['course_id']}"
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO course_worlds (id, course_id, revision, state, brief_json,"
                " concepts_json, selected_concept_id, style_hash, kit_hash, approved_hash,"
                " approved_at, created_at, updated_at)"
                " VALUES (?, ?, 1, 'approved', '{}', '[]', 'c1', ?, ?, ?, ?, ?, ?)",
                (world_id, seeded["course_id"], "sha256:" + "c" * 64, "sha256:" + "d" * 64,
                 "sha256:" + "e" * 64, NOW, NOW, NOW),
            )
            rows: list[tuple[str, str, str]] = [("cover", "cover", "")]
            for index in range(sections):
                rows.append(("section", f"sec{index}", f"section_key_{index}"))
            for index in range(scenes):
                rows.append(("lesson_scene", f"scene{index}", f"scene_key_{index}"))
            for number, (role, section_id, section_key) in enumerate(rows):
                connection.execute(
                    "INSERT INTO world_assets (id, world_id, role, section_id, section_key,"
                    " artifact_id, style_hash, prompt_hash, textless, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                    (f"was_full_{number}", world_id, role, section_id, section_key, artifact,
                     "sha256:" + "c" * 64, "sha256:" + "f" * 64, NOW),
                )
        return len(rows)

    def _artifact(self) -> str:
        from coursebook import artifacts

        saved = artifacts.ArtifactStore().save(
            course_id=None,
            kind="visual",
            data=b"\x89PNG\r\n\x1a\n" + b"0" * 32,
            mime="image/png",
            provenance={"generator": "fixture", "notes": "test plate"},
        )
        return str(saved["artifact_id"])

    # ── commands ────────────────────────────────────────────────────────────
    def lesson_identity(self, seeded: dict, index: int = 0) -> tuple[str, str]:
        row = self.rows(
            "SELECT l.id AS lesson_id, l.version, l.page_json FROM gen_lessons l"
            " JOIN gen_plan_sections s ON s.id = l.section_id"
            " WHERE s.plan_id = ? ORDER BY s.ordinal LIMIT 1 OFFSET ?",
            (seeded["plan_id"], index),
        )[0]
        return f"{row['lesson_id']}:v{int(row['version'])}", str(row["lesson_id"])

    def preview(self, seeded: dict, *, audience: str = "parent", kind: str = "print_pack", index: int = 0) -> dict:
        version, _lesson_id = self.lesson_identity(seeded, index)
        return self.ok(
            "takehome.preview",
            {
                "course_id": seeded["course_id"],
                "objective_id": seeded["objective_ids"][index],
                "source_lesson_version": version,
                "audience": audience,
                "kind": kind,
            },
        )["result"]

    def create(self, seeded: dict, *, preview: dict | None = None, title: str = "Take-home: searing", key: str | None = None) -> dict:
        preview = preview or self.preview(seeded)
        version, _lesson_id = self.lesson_identity(seeded)
        return self.ok(
            "takehome.create",
            {
                "course_id": seeded["course_id"],
                "objective_id": seeded["objective_ids"][0],
                "source_lesson_version": version,
                "audience": "parent",
                "kind": "print_pack",
                "title": title,
            },
            expected_revision=0,
            idempotency_key=key or f"key-takehome-create-{seeded['course_id']}",
        )["result"]

    def approved_pack(self, seeded: dict) -> tuple[dict, dict]:
        preview = self.preview(seeded)
        created = self.create(seeded, preview=preview)
        approved = self.ok(
            "takehome.approve",
            {"pack_id": created["pack_id"], "preview_hash": preview["preview_hash"]},
            expected_revision=created["revision"],
            idempotency_key=f"key-takehome-approve-{seeded['course_id']}",
        )["result"]
        return created, approved

    def exported_pack(self, seeded: dict) -> dict:
        created, approved = self.approved_pack(seeded)
        return self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"] + 1,
            idempotency_key=f"key-takehome-export-{seeded['course_id']}",
        )["result"]

    # ── assertions helpers ─────────────────────────────────────────────────
    def pdf_text(self, artifact_id: str) -> str:
        row = self.rows("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))[0]
        data = Path(str(row["path"])).read_bytes()
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)

    def set_lesson_body(self, seeded: dict, body: str, index: int = 0) -> None:
        """Rewrite one validated lesson segment's body so print-path text can be exercised."""
        _version, lesson_id = self.lesson_identity(seeded, index)
        page = page_document(f"Section {index + 1}: the sear")
        page["segments"][1]["body"] = body
        self.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?",
            (json.dumps(page), lesson_id),
        )

    def pdf_bytes(self, artifact_id: str) -> bytes:
        row = self.rows("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))[0]
        return Path(str(row["path"])).read_bytes()

    def export_learner_sheet(self, seeded: dict) -> tuple[dict, str]:
        version, _lesson_id = self.lesson_identity(seeded)
        payload = {
            "course_id": seeded["course_id"],
            "objective_id": seeded["objective_ids"][0],
            "source_lesson_version": version,
            "audience": "learner",
            "kind": "homework_sheet",
        }
        preview = self.ok("takehome.preview", payload)["result"]
        created = self.ok(
            "takehome.create",
            dict(payload, title="Learner sheet"),
            expected_revision=0,
            idempotency_key=f"key-learner-create-{seeded['course_id']}",
        )["result"]
        self.ok(
            "takehome.approve",
            {"pack_id": created["pack_id"], "preview_hash": preview["preview_hash"]},
            expected_revision=created["revision"],
            idempotency_key=f"key-learner-approve-{seeded['course_id']}",
        )
        exported = self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"] + 1,
            idempotency_key=f"key-learner-export-{seeded['course_id']}",
        )["result"]
        return created, exported["artifact_id"]

    def table_snapshot(self, course_id: str) -> dict:
        def _in(ids: list[str]) -> tuple[str, tuple]:
            if not ids:
                return "''", ()
            return ",".join("?" for _ in ids), tuple(ids)

        plan = self.rows("SELECT * FROM plans WHERE course_id = ?", (course_id,))
        plan_ids = [row["id"] for row in plan]
        plan_in, plan_params = _in(plan_ids)
        objectives = self.rows(
            f"SELECT * FROM objectives WHERE plan_id IN ({plan_in}) ORDER BY id", plan_params
        )
        objective_ids = [row["id"] for row in objectives]
        obj_in, obj_params = _in(objective_ids)
        checks = self.rows(
            f"SELECT * FROM checks WHERE objective_id IN ({obj_in}) ORDER BY id", obj_params
        )
        check_ids = [row["id"] for row in checks]
        chk_in, chk_params = _in(check_ids)
        return {
            "courses": self.rows("SELECT * FROM courses WHERE id = ?", (course_id,)),
            "plans": plan,
            "objectives": objectives,
            "checks": checks,
            "gen_lessons": self.rows(
                f"SELECT * FROM gen_lessons WHERE plan_id IN ({plan_in}) ORDER BY id", plan_params
            ),
            "gen_sections": self.rows(
                f"SELECT * FROM gen_plan_sections WHERE plan_id IN ({plan_in}) ORDER BY id", plan_params
            ),
            "attempts": self.rows(
                f"SELECT * FROM attempts WHERE check_id IN ({chk_in}) ORDER BY id", chk_params
            ),
            "evidence": self.rows(
                f"SELECT * FROM evidence WHERE objective_id IN ({obj_in}) ORDER BY id", obj_params
            ),
        }


class TakeHomeSourcePickerTest(TakeHomeCase):
    def test_takehome_sources_lists_objective_section_and_lesson(self) -> None:
        seeded = self.seed_course()
        result = self.ok("takehome.sources", {"course_id": seeded["course_id"]})["result"]
        self.assertEqual(result["course_id"], seeded["course_id"])
        self.assertEqual(result["presentation_mode"], "textbook")
        self.assertEqual(len(result["objectives"]), 2)
        first = result["objectives"][0]
        self.assertEqual(first["objective_id"], seeded["objective_ids"][0])
        self.assertEqual(first["section_title"], "Section 1: the sear")
        self.assertEqual(first["lesson_version"], self.lesson_identity(seeded)[0])
        self.assertTrue(first["available"])
        self.assertRegex(first["content_hash"], r"^sha256:[a-f0-9]{64}$")

    def test_takehome_sources_excludes_parent_authoring_course(self) -> None:
        seeded = self.seed_course(recipe="parent")
        error = self.err("takehome.sources", {"course_id": seeded["course_id"]})
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "parent_only_course")

    def test_takehome_missing_source_is_a_named_error(self) -> None:
        error = self.err("takehome.sources", {"course_id": "crs_does_not_exist"})
        self.assertEqual(error["code"], "NOT_FOUND")


class TakeHomeBindingTest(TakeHomeCase):
    def test_takehome_source_course_unchanged(self) -> None:
        """Preview, create, approve and export write no row of the source course."""
        seeded = self.seed_course(sections=2)
        before = self.table_snapshot(seeded["course_id"])
        self.exported_pack(seeded)
        after = self.table_snapshot(seeded["course_id"])
        self.assertEqual(before, after)
        # The pack is a separate table, and its row exists.
        packs = self.rows("SELECT * FROM takehome_packs WHERE source_course_id = ?", (seeded["course_id"],))
        self.assertEqual(len(packs), 1)

    def test_takehome_binds_source_lesson_hash(self) -> None:
        seeded = self.seed_course()
        preview = self.preview(seeded)
        created = self.create(seeded, preview=preview)
        row = self.rows("SELECT * FROM takehome_packs WHERE id = ?", (created["pack_id"],))[0]
        self.assertEqual(row["content_hash"], preview["content_hash"])
        self.assertEqual(row["source_lesson_version"], self.lesson_identity(seeded)[0])
        self.assertEqual(created["content_hash"], preview["content_hash"])

        # A wrong version is a named refusal, not a pack bound to something else.
        error = self.err(
            "takehome.create",
            {
                "course_id": seeded["course_id"],
                "objective_id": seeded["objective_ids"][0],
                "source_lesson_version": "lsn_missing:v9",
                "audience": "parent",
                "kind": "print_pack",
                "title": "Wrong version",
            },
            expected_revision=0,
            idempotency_key="key-wrong-version",
        )
        self.assertEqual(error["code"], "NOT_FOUND")

        # The source is read-only: editing it after binding cannot silently re-render the pack.
        self.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?",
            (json.dumps(page_document("Rewritten section")), self.lesson_identity(seeded)[1]),
        )
        read = self.ok("takehome.read", {"pack_id": created["pack_id"]})["result"]["pack"]
        self.assertEqual(read["content_hash"], preview["content_hash"])
        self.assertEqual(read["source_lesson_version"], self.lesson_identity(seeded)[0])
        self.assertIn("Section 1: the sear", read["pages"]["learner_page"]["text"])

    def test_takehome_create_is_idempotent(self) -> None:
        seeded = self.seed_course()
        first = self.create(seeded, key="key-same")
        second = self.create(seeded, key="key-same")
        self.assertEqual(first["pack_id"], second["pack_id"])
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM takehome_packs"), 1
        )


class TakeHomePagesTest(TakeHomeCase):
    def test_takehome_learner_page_has_no_answer_key(self) -> None:
        seeded = self.seed_course()
        read = self.ok("takehome.read", {"pack_id": self.create(seeded)["pack_id"]})["result"]["pack"]
        learner = read["pages"]["learner_page"]["text"]
        self.assertIn(LEARNER_MARKER, learner)
        self.assertNotIn(ANSWER_MARKER, learner)
        self.assertNotIn(RUBRIC_MARKER, learner)
        self.assertNotIn("Answer guide", learner)
        self.assertNotIn("Reference answer", learner)
        # The worked example keeps its steps but not its answer; the answer is parent-only.
        self.assertNotIn("Answer: Wait for the shimmer", learner)
        self.assertNotIn("Wait for the shimmer", learner)
        # Nothing in the learner page is labelled grading.
        self.assertNotIn("Rubric", learner)

    def test_takehome_answer_guide_is_separate(self) -> None:
        seeded = self.seed_course()
        read = self.ok("takehome.read", {"pack_id": self.create(seeded)["pack_id"]})["result"]["pack"]
        pages = read["pages"]
        self.assertEqual(pages["learner_page"]["audience"], "learner")
        self.assertEqual(pages["answer_guide"]["audience"], "parent")
        self.assertEqual(pages["parent_guide"]["audience"], "parent")
        self.assertEqual(len({pages["learner_page"]["role"], pages["answer_guide"]["role"]}), 2)
        self.assertIn(ANSWER_MARKER, pages["answer_guide"]["text"])
        self.assertIn("Wait for the shimmer", pages["answer_guide"]["text"])
        self.assertNotIn(ANSWER_MARKER, pages["learner_page"]["text"])
        # The answer guide is not a suffix of the learner page: it is its own page object.
        self.assertNotEqual(pages["learner_page"]["text"], pages["answer_guide"]["text"])

    def test_takehome_export_requires_approval_of_the_previewed_pages(self) -> None:
        seeded = self.seed_course()
        preview = self.preview(seeded)
        created = self.create(seeded, preview=preview)
        error = self.err(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"],
            idempotency_key="key-export-unapproved",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "pack_not_approved")

        error = self.err(
            "takehome.approve",
            {"pack_id": created["pack_id"], "preview_hash": "sha256:" + "0" * 64},
            expected_revision=created["revision"],
            idempotency_key="key-approve-wrong-hash",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "preview_hash_mismatch")


class TakeHomeExportTest(TakeHomeCase):
    def test_takehome_export_pdf_is_selectable_text(self) -> None:
        seeded = self.seed_course(sections=2)
        exported = self.exported_pack(seeded)
        self.assertEqual(exported["state"], "exported")
        row = self.rows("SELECT * FROM artifacts WHERE id = ?", (exported["artifact_id"],))[0]
        self.assertEqual(row["kind"], "pdf")
        self.assertEqual(row["mime"], "application/pdf")
        data = Path(str(row["path"])).read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertNotIn(b"/JavaScript", data)
        reader = PdfReader(io.BytesIO(data))
        self.assertGreaterEqual(len(reader.pages), 2)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        # Selectable text: the authored sentence is extractable, not an image of it.
        self.assertIn("Watch the oil", text)
        self.assertIn("the sear", text)
        # The answer guide is a real page in the parent copy, clearly separated.
        self.assertIn("Answer guide", text)
        self.assertIn(ANSWER_MARKER, text)
        profile = self.ok("takehome.read", {"pack_id": exported["pack_id"]})["result"]["pack"]["print_profile"]
        self.assertEqual(profile["paper"], "letter")
        self.assertTrue(profile["selectable_text"])
        self.assertTrue(profile["low_ink"])
        self.assertGreater(profile["margin_pt"], 0)

    def test_takehome_learner_audience_export_has_no_answer_guide(self) -> None:
        """A learner-audience sheet is printed for the learner: no parent guide, no answer key."""
        seeded = self.seed_course(sections=1)
        created, artifact_id = self.export_learner_sheet(seeded)
        text = self.pdf_text(artifact_id)
        self.assertIn(LEARNER_MARKER, text)
        self.assertNotIn("Answer guide", text)
        self.assertNotIn("Parent guide", text)
        self.assertNotIn(ANSWER_MARKER, text)
        self.assertNotIn(RUBRIC_MARKER, text)
        self.assertNotIn("REFERENCE-ONLY", text)
        # The operator (the parent) still reads the separate answer guide from the stored pack.
        read = self.ok("takehome.read", {"pack_id": created["pack_id"]})["result"]["pack"]
        self.assertIn("answer_guide", read["pages"])

    def test_takehome_export_replay_same_key_returns_stored_result(self) -> None:
        """A transport retry of the same export replays the stored result, never STALE_REVISION."""
        seeded = self.seed_course(sections=1)
        created, _approved = self.approved_pack(seeded)
        approved_rev = created["revision"] + 1
        first = self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=approved_rev,
            idempotency_key="key-export-replay",
        )["result"]
        second = self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=approved_rev,
            idempotency_key="key-export-replay",
        )["result"]
        self.assertEqual(second["artifact_id"], first["artifact_id"])
        self.assertEqual(second["state"], "exported")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 1)
        row = self.rows("SELECT state, revision FROM takehome_packs WHERE id = ?", (created["pack_id"],))[0]
        self.assertEqual(row["state"], "exported")
        self.assertEqual(int(row["revision"]), approved_rev + 1)

    def test_takehome_pdf_headings_are_typographic_not_markdown(self) -> None:
        """The print template converts Markdown headings into real typographic headings."""
        seeded = self.seed_course(sections=1)
        exported = self.exported_pack(seeded)
        row = self.rows("SELECT * FROM artifacts WHERE id = ?", (exported["artifact_id"],))[0]
        data = Path(str(row["path"])).read_bytes()
        text = self.pdf_text(exported["artifact_id"])
        for line in text.splitlines():
            self.assertFalse(
                line.lstrip().startswith("#"),
                f"literal Markdown heading marker printed: {line!r}",
            )
        self.assertIn("Parent guide - Section 1: the sear", text)
        self.assertIn("Lesson intent", text)
        self.assertIn("Answer guide - parent only", text)
        # A real bold face, not a bigger copy of the body font.
        self.assertIn(b"/Helvetica-Bold", data)

    def test_takehome_export_renders_bound_pages_not_the_live_lesson(self) -> None:
        seeded = self.seed_course()
        created, approved = self.approved_pack(seeded)
        self.execute(
            "UPDATE gen_lessons SET page_json = ? WHERE id = ?",
            (json.dumps(page_document("Rewritten after approval")), self.lesson_identity(seeded)[1]),
        )
        exported = self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"] + 1,
            idempotency_key="key-export-after-edit",
        )["result"]
        row = self.rows("SELECT * FROM artifacts WHERE id = ?", (exported["artifact_id"],))[0]
        text = "\n".join(
            page.extract_text() or "" for page in PdfReader(io.BytesIO(Path(str(row["path"])).read_bytes())).pages
        )
        self.assertIn("Section 1: the sear", text)
        self.assertNotIn("Rewritten after approval", text)

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext (poppler) is required for the bbox check")
    def test_takehome_long_title_never_clips(self) -> None:
        """A contract-maximum title is wrapped and every printed word stays inside the margin."""
        seeded = self.seed_course(sections=1)
        title = (
            "Searing and braising the short ribs for a family Sunday dinner with a heavy pan "
            * 3
        )[:200]
        self.assertEqual(len(title), 200)
        preview = self.preview(seeded)
        created = self.create(seeded, preview=preview, title=title)
        self.ok(
            "takehome.approve",
            {"pack_id": created["pack_id"], "preview_hash": preview["preview_hash"]},
            expected_revision=created["revision"],
            idempotency_key="key-long-title-approve",
        )
        exported = self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"] + 1,
            idempotency_key="key-long-title-export",
        )["result"]
        path = self.work / "long-title.pdf"
        path.write_bytes(self.pdf_bytes(exported["artifact_id"]))
        run = subprocess.run(
            ["pdftotext", "-bbox", "-f", "1", "-l", "1", str(path), "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        xs = [float(value) for value in re.findall(r'xMax="([0-9.]+)"', run.stdout)]
        self.assertTrue(xs, "no words were extracted from the title page")
        # Letter width 612 pt, 56 pt margin: the printable right edge is 556 pt.
        self.assertLessEqual(max(xs), 556.5, f"title text clipped past the margin: xMax={max(xs)}")
        text = self.pdf_text(exported["artifact_id"])
        # The whole title survived, split across wrapped lines rather than truncated.
        self.assertIn("Searing and braising", text)
        self.assertIn(title[-24:].strip(), text)

    def test_takehome_non_ascii_lesson_is_a_named_refusal_not_mojibake(self) -> None:
        """Text the built-in print font cannot encode is refused by name, never replaced by '?'."""
        seeded = self.seed_course(sections=1)
        body = "こんにちは café 日本語 — naïve"
        self.set_lesson_body(seeded, body)
        preview = self.preview(seeded)
        learner_text = next(page["text"] for page in preview["pages"] if page["role"] == "learner_page")
        self.assertIn("こんにちは", learner_text)  # preview keeps the exact lesson text
        created = self.create(seeded, preview=preview)
        self.ok(
            "takehome.approve",
            {"pack_id": created["pack_id"], "preview_hash": preview["preview_hash"]},
            expected_revision=created["revision"],
            idempotency_key="key-nonascii-approve",
        )
        error = self.err(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"] + 1,
            idempotency_key="key-nonascii-export",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "print_font_cannot_render_text")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)
        row = self.rows(
            "SELECT state, artifact_id, revision FROM takehome_packs WHERE id = ?",
            (created["pack_id"],),
        )[0]
        self.assertEqual(row["state"], "approved")
        self.assertIsNone(row["artifact_id"])
        self.assertEqual(int(row["revision"]), created["revision"] + 1)

    def test_takehome_accented_latin_prints_exactly(self) -> None:
        """WinAnsi text (accented Latin, dashes) prints the lesson's exact characters."""
        seeded = self.seed_course(sections=1)
        self.set_lesson_body(seeded, "Un café très naïf — voilà, ça marche.")
        exported = self.exported_pack(seeded)
        text = self.pdf_text(exported["artifact_id"])
        self.assertIn("café", text)
        self.assertIn("naïf", text)
        self.assertIn("—", text)


class TakeHomeWorldArtTest(TakeHomeCase):
    def test_takehome_textbook_source_needs_no_world_art(self) -> None:
        seeded = self.seed_course()
        sources = self.ok("takehome.sources", {"course_id": seeded["course_id"]})["result"]
        self.assertEqual(sources["presentation_mode"], "textbook")
        preview = self.preview(seeded)
        self.assertEqual([page for page in preview["pages"] if page["role"] == "plate"], [])
        exported = self.exported_pack(seeded)
        read = self.ok("takehome.read", {"pack_id": exported["pack_id"]})["result"]["pack"]
        self.assertEqual(read["plates"], [])
        self.assertTrue(read["export"]["artifact_id"])

    def test_takehome_full_world_kit_preview_fits_page_budget(self) -> None:
        """A full 9-plate world kit previews, capped to the contract's 12-page budget."""
        seeded = self.seed_course(sections=1)
        self.assertEqual(self.add_full_world(seeded), 9)
        preview = self.preview(seeded)
        self.assertLessEqual(len(preview["pages"]), 12)
        plate_pages = [page for page in preview["pages"] if page["role"] == "plate"]
        self.assertEqual(len(plate_pages), 8)
        self.assertIn("Orientation plate", plate_pages[0]["text"])

    def test_takehome_export_prints_world_plate_caption_and_provenance(self) -> None:
        """Every advertised plate page is printed with its caption and provenance."""
        seeded = self.seed_course(sections=1)
        world = self.add_approved_world(seeded)
        preview = self.preview(seeded)
        self.assertEqual([p["role"] for p in preview["pages"]].count("plate"), 1)
        exported = self.exported_pack(seeded)
        text = self.pdf_text(exported["artifact_id"])
        self.assertIn("Orientation plate (cover)", text)
        self.assertIn("Provenance", text)
        self.assertIn(world["world_id"], text)
        self.assertIn(world["artifact_id"], text)

    def test_takehome_world_plates_are_captioned_orientation_only(self) -> None:
        seeded = self.seed_course()
        world = self.add_approved_world(seeded)
        read = self.ok("takehome.read", {"pack_id": self.create(seeded)["pack_id"]})["result"]["pack"]
        self.assertEqual(len(read["plates"]), 1)
        plate = read["plates"][0]
        self.assertEqual(plate["role"], "cover")
        self.assertTrue(plate["textless"])
        self.assertEqual(plate["artifact_id"], world["artifact_id"])
        self.assertIn("orientation", plate["caption"].lower())
        self.assertIn("not instructional", plate["caption"].lower())
        self.assertEqual(plate["provenance"]["style_hash"], "sha256:" + "c" * 64)


class TakeHomeDiagramTest(TakeHomeCase):
    def test_takehome_technical_diagram_is_sourced_or_deterministic(self) -> None:
        schematic = {
            "kind": "visual",
            "role": "schematic",
            "purpose": "torque sequence",
            "text_equivalent": "Tighten bolts in a cross pattern.",
            "label": "Deterministic torque sequence",
            "facts": {"order": ["1", "3", "2", "4"]},
        }
        seeded = self.seed_course(sections=1, procedure=True, media=[schematic])
        read = self.ok("takehome.read", {"pack_id": self.create(seeded)["pack_id"]})["result"]["pack"]
        self.assertEqual(len(read["diagrams"]), 1)
        self.assertEqual(read["diagrams"][0]["kind"], "deterministic")
        self.assertEqual(read["diagrams"][0]["role"], "schematic")

        sourced = dict(schematic, role="sourced_technical", source_ids=["src_manual"])
        seeded = self.seed_course(sections=1, procedure=True, media=[sourced])
        read = self.ok("takehome.read", {"pack_id": self.create(seeded)["pack_id"]})["result"]["pack"]
        self.assertEqual(read["diagrams"][0]["kind"], "sourced")
        self.assertEqual(read["diagrams"][0]["source_ids"], ["src_manual"])

        # AI art is never the procedure authority: an illustration-only procedure is refused.
        illustration = dict(schematic, role="illustration")
        seeded = self.seed_course(sections=1, procedure=True, media=[illustration])
        error = self.err(
            "takehome.preview",
            {
                "course_id": seeded["course_id"],
                "objective_id": seeded["objective_ids"][0],
                "source_lesson_version": self.lesson_identity(seeded)[0],
                "audience": "parent",
                "kind": "print_pack",
            },
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "ai_art_as_procedure")


class TakeHomeRejectionTest(TakeHomeCase):
    def test_takehome_missing_source_lesson_is_a_named_error(self) -> None:
        seeded = self.seed_course(sections=1)
        version = self.lesson_identity(seeded)[0]
        self.execute("DELETE FROM gen_lessons WHERE plan_id = ?", (seeded["plan_id"],))
        error = self.err(
            "takehome.preview",
            {
                "course_id": seeded["course_id"],
                "objective_id": seeded["objective_ids"][0],
                "source_lesson_version": version,
                "audience": "parent",
                "kind": "print_pack",
            },
        )
        self.assertEqual(error["code"], "NOT_FOUND")
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM takehome_packs WHERE source_course_id = ?", (seeded["course_id"],)),
            0,
        )


if __name__ == "__main__":
    unittest.main()
