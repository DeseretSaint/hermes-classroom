"""Pack lifecycle integration: preview → import → learn → export → delete (CB-010).

These tests run against a real SQLite database built by the real migrations, real zip archives
built from the bundled packs, and the real dispatcher. The only thing that is not real is the
host: the file grant is called directly, exactly as a native picker adapter would.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from coursebook import api, archive, db, domain, pack_flow, packs
from coursebook.archive import PackRejected
from tests.kernel_support import KernelCase, request

ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
PARENT = ROOT / "bundled" / "packs" / "parent-measurement-practice"


def build_pack_zip(source: Path, destination: Path) -> dict:
    """Write a pack directory as a real archive and return its manifest."""
    manifest, files = archive.read_directory(source)
    archive.write_archive(destination, manifest, files)
    return manifest


class PackFlowCase(KernelCase):
    """A migrated profile plus helpers for granting a real archive."""

    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-packflow-"))
        self.addCleanup(shutil.rmtree, self.work, True)

    # ── staging helpers ────────────────────────────────────────────────

    def grant(self, source: Path = JAPANESE, name: str = "pack.zip") -> tuple[str, dict]:
        manifest, files = archive.read_directory(source)
        destination = self.work / name
        archive.write_archive(destination, manifest, files)
        return pack_flow.grant_local_file(destination), manifest

    def grant_zip(self, path: Path) -> str:
        return pack_flow.grant_local_file(path)

    def import_pack(self, staged_id: str, mode: str = "fresh", **kwargs) -> dict:
        return self.ok("pack.import", {"staged_id": staged_id, "mode": mode}, **kwargs)

    def counts(self) -> dict[str, int]:
        return {
            table: int(self.scalar(f"SELECT COUNT(*) FROM {table}"))
            for table in (
                "packs",
                "courses",
                "plans",
                "objectives",
                "enrollments",
                "lesson_runs",
                "lesson_segments",
                "sources",
                "artifacts",
            )
        }


class PreviewTest(PackFlowCase):
    def test_preview_returns_manifest_integrity_and_separate_trust_labels(self) -> None:
        staged_id, manifest = self.grant()
        result = self.ok("pack.preview", {"staged_id": staged_id})["result"]
        self.assertEqual(set(result), {"manifest", "integrity", "trust"})
        self.assertEqual(result["manifest"]["pack_id"], manifest["pack_id"])
        self.assertEqual(result["manifest"]["attribution"], manifest["attribution"])
        self.assertEqual(result["manifest"]["license"], manifest["license"])
        self.assertEqual(result["integrity"]["file_count"], len(manifest["files"]))
        self.assertTrue(result["integrity"]["hashes_match"])
        labels = result["trust"]["labels"]
        self.assertIn("integrity_verified", labels)
        self.assertIn("automated_checks_passed", labels)
        # No native-speaker review was recorded, so the label must be absent — and no verdict.
        self.assertNotIn("human_review_recorded", labels)
        self.assertNotIn("safe", labels)
        self.assertNotIn("verified", labels)
        self.assertEqual(set(result["trust"]), {"labels"})

    def test_preview_admits_support_state_instead_of_a_safety_badge(self) -> None:
        staged_id, _manifest = self.grant()
        result = self.ok("pack.preview", {"staged_id": staged_id})["result"]
        states = {source.get("support_status") for source in result["manifest"]["sources"]}
        self.assertTrue(states, "the bundled pack must carry its source/support ledger")
        self.assertNotIn("safe", result["trust"]["labels"])
        self.assertEqual(set(result["trust"]["labels"]) - {
            "integrity_verified", "automated_checks_passed", "human_review_recorded", "model_assessed_support"
        }, set())

    def test_an_unknown_staged_id_is_refused_not_guessed(self) -> None:
        error = self.err("pack.preview", {"staged_id": "stg-doesnotexist000000"})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertEqual(error["details"]["reason"], "pack_not_importable")


class ImportTest(PackFlowCase):
    def test_import_creates_a_learnable_course_from_the_pack(self) -> None:
        staged_id, manifest = self.grant()
        result = self.import_pack(staged_id)["result"]
        self.assertEqual(result["pack_id"], manifest["pack_id"])
        course = self.rows("SELECT * FROM courses WHERE id = ?", (result["course_id"],))[0]
        self.assertEqual(course["recipe"], manifest["recipe"])
        self.assertEqual(course["title"], manifest["title"])
        self.assertEqual(course["locale"], manifest["locale"])
        plan = self.rows("SELECT * FROM plans WHERE course_id = ?", (result["course_id"],))[0]
        self.assertEqual(plan["state"], "approved")
        # The stored hash is the kernel's own hash for this plan; they cannot drift.
        self.assertEqual(plan["plan_hash"], domain.plan_hash(plan["id"]))
        objectives = self.rows(
            "SELECT * FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan["id"],)
        )
        self.assertEqual([row["title"] for row in objectives], [o["title"] for o in manifest["objectives"]])

        # The authored section text is a durable lesson page, not a paraphrase.
        page = self.ok(
            "lesson.page",
            {"enrollment_id": result["enrollment_id"], "objective_id": objectives[0]["id"]},
        )["result"]
        self.assertTrue(page["segments"], "an imported pack must render its own lesson content")
        self.assertIn("teaching", {segment["kind"] for segment in page["segments"]})
        self.assertTrue(page["sources"], "the pack's source ledger must reach the course")

    def test_fresh_import_twice_shares_content_and_separates_progress(self) -> None:
        first = self.import_pack(self.grant(name="a.zip")[0])["result"]
        second = self.import_pack(self.grant(name="b.zip")[0])["result"]
        self.assertNotEqual(first["course_id"], second["course_id"])
        self.assertNotEqual(first["enrollment_id"], second["enrollment_id"])
        # Immutable content is stored once; a second course is a second learner, not a second copy.
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM packs")), 1)

    def test_resume_reopens_the_existing_enrollment_without_new_rows(self) -> None:
        first = self.import_pack(self.grant(name="a.zip")[0])["result"]
        before = self.counts()
        resumed = self.import_pack(self.grant(name="b.zip")[0], mode="resume")["result"]
        self.assertEqual(resumed["enrollment_id"], first["enrollment_id"])
        self.assertEqual(resumed["course_id"], first["course_id"])
        self.assertEqual(self.counts(), before)

    def test_resume_with_no_history_creates_one_course(self) -> None:
        result = self.import_pack(self.grant()[0], mode="resume")["result"]
        self.assertIsNotNone(result["enrollment_id"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM courses")), 1)

    def test_an_idempotency_key_returns_the_first_import(self) -> None:
        staged_id, _manifest = self.grant()
        key = "pack-import-key-0001"
        first = self.import_pack(staged_id, idempotency_key=key)["result"]
        again = self.import_pack(staged_id, idempotency_key=key)["result"]
        self.assertEqual(first, again)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM courses")), 1)

    def test_rejection_leaves_no_course_residue(self) -> None:
        # A pack whose bytes do not match its manifest hashes must be refused at staging, before
        # the first database write.
        manifest, files = archive.read_directory(JAPANESE)
        tampered = dict(manifest)
        tampered["files"] = [
            {**entry, "sha256": "sha256:" + "0" * 64} for entry in manifest["files"]
        ]
        tampered = packs.with_content_hash(tampered)
        destination = self.work / "tampered.zip"
        with zipfile.ZipFile(destination, "w") as bundle:
            root = f"{tampered['pack_id']}-{tampered['pack_version']}"
            for path, data in files.items():
                bundle.writestr(f"{root}/{path}", data)
            bundle.writestr(f"{root}/pack.json", packs.canonical_json_bytes(tampered) + b"\n")
        staged_id = self.grant_zip(destination)
        error = self.err("pack.import", {"staged_id": staged_id, "mode": "fresh"})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertEqual(set(self.counts().values()), {0})
        self.assertEqual(pack_flow.library().list(), [])

    def test_path_traversal_archive_is_refused_with_no_residue(self) -> None:
        destination = self.work / "traversal.zip"
        with zipfile.ZipFile(destination, "w") as bundle:
            bundle.writestr("root/../escape.txt", "nope")
            bundle.writestr("root/pack.json", "{}")
        staged_id = self.grant_zip(destination)
        error = self.err("pack.preview", {"staged_id": staged_id})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertFalse((self.work / "escape.txt").exists())
        self.assertEqual(set(self.counts().values()), {0})

    def test_active_markup_inside_a_text_file_is_refused(self) -> None:
        manifest, files = archive.read_directory(JAPANESE)
        destination = self.work / "active.zip"
        markup = b"# Lesson\n\n<svg onload='alert(1)'></svg>\n"
        broken = dict(manifest)
        broken["files"] = [
            packs.file_record("content/learner-page.md", markup, mime="text/markdown", role="section")
        ] + [entry for entry in manifest["files"] if entry["path"] != "content/learner-page.md"]
        broken = packs.with_content_hash(broken)
        with zipfile.ZipFile(destination, "w") as bundle:
            root = f"{broken['pack_id']}-{broken['pack_version']}"
            for entry in broken["files"]:
                bundle.writestr(f"{root}/{entry['path']}", markup if entry["path"].endswith("learner-page.md") else files.get(entry["path"], b""))
            bundle.writestr(f"{root}/pack.json", packs.canonical_json_bytes(broken) + b"\n")
        staged_id = self.grant_zip(destination)
        error = self.err("pack.preview", {"staged_id": staged_id})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertEqual(set(self.counts().values()), {0})

    def test_a_newer_minimum_version_is_refused(self) -> None:
        manifest, files = archive.read_directory(JAPANESE)
        bumped = dict(manifest)
        bumped["minimum_coursebook_version"] = "99.0.0"
        bumped = packs.with_content_hash(bumped)
        destination = self.work / "future.zip"
        with zipfile.ZipFile(destination, "w") as bundle:
            root = f"{bumped['pack_id']}-{bumped['pack_version']}"
            for path, data in files.items():
                bundle.writestr(f"{root}/{path}", data)
            bundle.writestr(f"{root}/pack.json", packs.canonical_json_bytes(bumped) + b"\n")
        error = self.err("pack.import", {"staged_id": self.grant_zip(destination), "mode": "fresh"})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertEqual(set(self.counts().values()), {0})


class ParentGuardTest(PackFlowCase):
    def test_parent_pack_imports_as_parent_and_never_as_a_graded_course(self) -> None:
        staged_id, manifest = self.grant(PARENT, "parent.zip")
        self.assertEqual(manifest["recipe"], "parent")
        result = self.import_pack(staged_id)["result"]
        course = self.rows("SELECT * FROM courses WHERE id = ?", (result["course_id"],))[0]
        self.assertEqual(course["recipe"], "parent")
        dials = json.loads(course["dials_json"])
        self.assertEqual(dials["assessment"], "none")
        self.assertEqual(dials["recipe_source"], "pack_manifest")

        objective = self.rows(
            "SELECT * FROM objectives WHERE plan_id = (SELECT id FROM plans WHERE course_id = ?) LIMIT 1",
            (result["course_id"],),
        )[0]
        criteria = json.loads(objective["evidence_criteria_json"])
        self.assertFalse(
            any("check_spec" in entry for entry in criteria),
            "a parent pack must not carry a machine-graded check spec",
        )
        error = self.err(
            "check.open",
            {"enrollment_id": result["enrollment_id"], "objective_id": objective["id"]},
            expected_revision=0,
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "objective_not_checkable")

    def test_conversion_requires_explicit_confirmation_and_a_new_identity(self) -> None:
        manifest, files = archive.read_directory(PARENT)
        with self.assertRaises(PackRejected):
            pack_flow.build_conversion(
                manifest, files, pack_id="fractions-adult-v1", pack_version="1.0.0", recipe="casual"
            )
        with self.assertRaises(PackRejected):
            pack_flow.build_conversion(
                manifest,
                files,
                pack_id=str(manifest["pack_id"]),
                pack_version="1.0.1",
                recipe="casual",
                confirm=True,
            )
        converted, _exported = pack_flow.build_conversion(
            manifest,
            files,
            pack_id="fractions-adult-v1",
            pack_version="9.9.9",
            recipe="casual",
            confirm=True,
        )
        self.assertEqual(converted["recipe"], "casual")
        self.assertEqual(converted["pack_id"], "fractions-adult-v1")
        self.assertEqual(converted["derived_from"]["pack_id"], manifest["pack_id"])
        # The original is untouched: identity, recipe and hash are unchanged.
        self.assertEqual(packs.content_hash(manifest) if "content_hash" in manifest else manifest["content_hash"], manifest["content_hash"])


class ExportTest(PackFlowCase):
    def test_export_is_the_reviewed_hash_and_reimports_byte_identically(self) -> None:
        staged_id, manifest = self.grant()
        imported = self.import_pack(staged_id)["result"]
        result = self.ok(
            "pack.export",
            {
                "enrollment_id": imported["enrollment_id"],
                "options": {"expected_content_hash": manifest["content_hash"]},
            },
        )["result"]
        self.assertEqual(result["content_hash"], manifest["content_hash"])
        self.assertEqual(result["file_count"], len(manifest["files"]))

        artifact = self.ok("artifact.get", {"artifact_id": result["artifact_id"]})["result"]
        # The artifact records the bytes on disk; pack.export reports the pack content hash.
        self.assertEqual(artifact["content_hash"], "sha256:" + hashlib.sha256(
            pack_flow.export_root().joinpath(
                f"{manifest['pack_id']}-{manifest['pack_version']}-{manifest['content_hash'].split(':')[1][:16]}.zip"
            ).read_bytes()
        ).hexdigest())
        self.assertEqual(artifact["kind"], "export")
        self.assertEqual(artifact["mime"], "application/zip")
        self.assertTrue(artifact["download"]["requires_session"])
        path, mime, size = pack_flow.open_artifact(artifact["download"]["handle"])
        self.assertEqual(mime, "application/zip")
        self.assertEqual(size, result["bytes"])

        # The archive carries no private state and re-imports to the same content hash.
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            document = json.loads(bundle.read(next(n for n in names if n.endswith("/pack.json"))))
        self.assertEqual(packs.contains_private_fields(document), [])
        for forbidden in ("transcript", "attempt", "notebook", "enrollment_id", "course_id"):
            self.assertNotIn(forbidden, json.dumps(document))

        staged_again = self.grant_zip(path)
        reimported = self.import_pack(staged_again)["result"]
        self.assertEqual(reimported["pack_id"], manifest["pack_id"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM courses")), 2)

    def test_export_never_carries_a_saved_field_note(self) -> None:
        """A personal excerpt/note/tags stays on this profile; the archive is teaching truth only."""
        staged_id, manifest = self.grant()
        imported = self.import_pack(staged_id)["result"]
        objective = self.scalar(
            "SELECT id FROM objectives WHERE plan_id = (SELECT id FROM plans WHERE course_id = ?)",
            (imported["course_id"],),
        )
        excerpt = "FIELD-NOTE-EXCERPT-marker-42"
        note = "PRIVATE-NOTE-marker-77"
        self.ok(
            "notebook.save",
            {
                "enrollment_id": imported["enrollment_id"],
                "objective_id": objective,
                "kind": "artifact",
                "excerpt": excerpt,
                "note": note,
                "tags": ["private-tag-marker"],
                "source_ref": json.dumps({"block": "blk_private_marker", "sources": ["src_private_marker"]}),
            },
            idempotency_key="notebook-private-0001",
        )
        result = self.ok("pack.export", {"enrollment_id": imported["enrollment_id"]})["result"]
        artifact = self.ok("artifact.get", {"artifact_id": result["artifact_id"]})["result"]
        path, _mime, _size = pack_flow.open_artifact(artifact["download"]["handle"])
        with zipfile.ZipFile(path) as bundle:
            blob = b"".join(bundle.read(name) for name in bundle.namelist())
        text = blob.decode("utf-8", "ignore")
        for forbidden in (excerpt, note, "private-tag-marker", "blk_private_marker", "src_private_marker"):
            self.assertNotIn(forbidden, text)
        # The exclusion is from the export, not a delete: the moment is still on this profile.
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM notebook_entries")), 1)
        self.assertEqual(result["content_hash"], manifest["content_hash"])

    def test_repeat_export_of_unchanged_content_reuses_the_artifact(self) -> None:
        """Clicking Export twice must return the first artifact, not an IntegrityError."""
        imported = self.import_pack(self.grant()[0])["result"]
        first = self.ok(
            "pack.export",
            {"enrollment_id": imported["enrollment_id"]},
            idempotency_key="cb-export-repeat-first",
        )["result"]
        second = self.ok(
            "pack.export",
            {"enrollment_id": imported["enrollment_id"]},
            idempotency_key="cb-export-repeat-second",
        )["result"]
        self.assertEqual(second["artifact_id"], first["artifact_id"])
        self.assertEqual(second["content_hash"], first["content_hash"])
        self.assertEqual(second["file_count"], first["file_count"])
        self.assertEqual(second["bytes"], first["bytes"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM artifacts WHERE kind = 'export'")), 1)
        self.assertEqual(
            int(self.scalar("SELECT ref_count FROM artifacts WHERE id = ?", (first["artifact_id"],))),
            2,
        )
        # The reused row still resolves to real bytes.
        path, mime, size = pack_flow.open_artifact(
            self.ok("artifact.get", {"artifact_id": first["artifact_id"]})["result"]["download"]["handle"]
        )
        self.assertEqual(mime, "application/zip")
        self.assertEqual(size, first["bytes"])
        self.assertTrue(path.is_file())

    def test_a_different_pack_content_exports_a_new_artifact(self) -> None:
        japanese = self.import_pack(self.grant()[0])["result"]
        parent = self.import_pack(self.grant(PARENT, "parent.zip")[0])["result"]
        first = self.ok("pack.export", {"enrollment_id": japanese["enrollment_id"]})["result"]
        second = self.ok("pack.export", {"enrollment_id": parent["enrollment_id"]})["result"]
        self.assertNotEqual(second["artifact_id"], first["artifact_id"])
        self.assertNotEqual(second["content_hash"], first["content_hash"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM artifacts WHERE kind = 'export'")), 2)

    def test_export_refuses_a_hash_the_reviewer_did_not_see(self) -> None:
        imported = self.import_pack(self.grant()[0])["result"]
        error = self.err(
            "pack.export",
            {
                "enrollment_id": imported["enrollment_id"],
                "options": {"expected_content_hash": "sha256:" + "a" * 64},
            },
        )
        self.assertEqual(error["code"], "DELETE_SCOPE_STALE")
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM artifacts WHERE kind = 'export'")), 0)

    def test_export_refuses_an_unknown_option_instead_of_ignoring_it(self) -> None:
        imported = self.import_pack(self.grant()[0])["result"]
        error = self.err(
            "pack.export",
            {"enrollment_id": imported["enrollment_id"], "options": {"include_transcripts": True}},
        )
        self.assertEqual(error["code"], "PACK_REJECTED")

    def test_export_refuses_a_course_that_did_not_come_from_a_pack(self) -> None:
        created = self.ok("course.create", {"title": "Authored", "recipe": "casual", "goal": "Do a thing"})["result"]
        enrollment = self.new_enrollment(created["course_id"])
        error = self.err("pack.export", {"enrollment_id": enrollment})
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "course_not_pack_backed")

    def test_file_review_lists_every_included_file(self) -> None:
        manifest, files = archive.read_directory(JAPANESE)
        document, exported = packs.build_export(manifest, files)
        review = pack_flow.review_export_tree(document, exported)
        self.assertEqual([entry["path"] for entry in review], sorted(entry["path"] for entry in manifest["files"]))
        for entry in review:
            self.assertTrue(entry["present"])
            self.assertTrue(entry["role"])
            self.assertTrue(entry["mime"])
            self.assertGreater(entry["bytes"], 0)


class ArtifactDownloadContainmentTest(PackFlowCase):
    """H-115-D2: a download handle resolves only to a file the plugin itself wrote."""

    def insert_export_row(self, artifact_id: str, path: Path, data: bytes) -> str:
        self.execute(
            "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
            " provenance_json, created_at) VALUES (?, NULL, 'export', ?, ?, ?, 'application/zip',"
            " '{}', '2026-11-07T00:00:00Z')",
            (artifact_id, "sha256:" + hashlib.sha256(data).hexdigest(), str(path), len(data)),
        )
        expires = int(datetime.now(timezone.utc).timestamp()) + 600
        return f"{artifact_id}_{expires}"

    def test_a_row_naming_a_path_outside_the_export_store_is_refused(self) -> None:
        outside = self.work / "outside.zip"
        outside.write_bytes(b"PK\x03\x04 outside-the-store")
        handle = self.insert_export_row("art_" + "a" * 32, outside, outside.read_bytes())
        with self.assertRaises(api.RpcError) as caught:
            pack_flow.open_artifact(handle)
        self.assertEqual(caught.exception.error["code"], "NOT_FOUND")

    def test_a_symlink_escaping_the_export_store_is_refused(self) -> None:
        outside = self.work / "outside-target.zip"
        outside.write_bytes(b"PK\x03\x04 outside-the-store")
        root = pack_flow.export_root()
        root.mkdir(parents=True, exist_ok=True)
        link = root / "escape.zip"
        link.symlink_to(outside)
        handle = self.insert_export_row("art_" + "b" * 32, link, outside.read_bytes())
        with self.assertRaises(api.RpcError) as caught:
            pack_flow.open_artifact(handle)
        self.assertEqual(caught.exception.error["code"], "NOT_FOUND")


class DeleteTest(PackFlowCase):
    def test_delete_freezes_the_pack_keeps_evidence_and_blocks_reimport(self) -> None:
        staged_id, manifest = self.grant()
        imported = self.import_pack(staged_id)["result"]
        self.ok(
            "notebook.save",
            {
                "enrollment_id": imported["enrollment_id"],
                "objective_id": self.scalar(
                    "SELECT id FROM objectives WHERE plan_id = (SELECT id FROM plans WHERE course_id = ?)",
                    (imported["course_id"],),
                ),
                "kind": "personal_note",
                "note": "my private note",
            },
            idempotency_key="notebook-save-key-0001",
        )
        preview = self.ok(
            "pack.delete",
            {"pack_id": manifest["pack_id"], "dry_run": True},
            expected_revision=0,
            idempotency_key="pack-delete-dry-0001",
        )["result"]
        self.assertFalse(preview["deleted"])
        self.assertTrue(preview["data_scope"]["preserved"]["notebook_entries"])
        deleted = self.ok(
            "pack.delete",
            {
                "pack_id": manifest["pack_id"],
                "dry_run": False,
                "data_scope_hash": preview["data_scope"]["scope_hash"],
            },
            expected_revision=0,
            idempotency_key="pack-delete-real-0001",
        )["result"]
        self.assertTrue(deleted["deleted"])

        # Evidence survives the tombstone.
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM notebook_entries")), 1)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM courses")), 1)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM enrollments")), 1)
        self.assertEqual(self.scalar("SELECT state FROM packs WHERE pack_id = ?", (manifest["pack_id"],)), "frozen")

        # The file library is reconciled with the tombstone, and re-import is refused.
        pack_flow.sync_tombstones()
        record = pack_flow.library().list()[0]
        self.assertEqual(record["state"], "frozen")
        error = self.err("pack.import", {"staged_id": self.grant(name="again.zip")[0], "mode": "fresh"})
        self.assertEqual(error["code"], "POLICY_VIOLATION")

    def test_library_list_shows_the_frozen_warning(self) -> None:
        staged_id, manifest = self.grant()
        self.import_pack(staged_id)
        preview = self.ok(
            "pack.delete",
            {"pack_id": manifest["pack_id"], "dry_run": True},
            expected_revision=0,
            idempotency_key="list-dry-run-0001",
        )["result"]
        self.ok(
            "pack.delete",
            {
                "pack_id": manifest["pack_id"],
                "dry_run": False,
                "data_scope_hash": preview["data_scope"]["scope_hash"],
            },
            expected_revision=0,
            idempotency_key="list-delete-0001",
        )
        listing = self.ok("library.list", {})["result"]
        entries = [
            row for row in listing["items"]
            if (row.get("provenance") or {}).get("pack_id") == manifest["pack_id"]
        ]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["warning"], "pack_frozen")


class RecoveryTest(PackFlowCase):
    def test_a_journaled_interrupted_import_is_reported_not_hidden(self) -> None:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO jobs (id, kind, state, operation_id, brief_json, checkpoint_json,"
                " attempt_id, progress_json, error_json, created_at, updated_at)"
                " VALUES ('job_interrupted_0001', 'import', 'running', 'op-import-1', '{}', '{}',"
                " 'jat_000000000001', '{}', '{}', '2026-01-01', '2026-01-01')"
            )
        recovered = pack_flow.recover_interrupted_imports()
        self.assertIn("job_interrupted_0001", recovered)
        listing = self.ok("jobs.list", {"kind": ["import"]})["result"]
        self.assertEqual(listing["counts"]["interrupted"], 1)
        self.assertEqual(listing["jobs"][0]["state"], "interrupted_requires_retry")

    def test_staging_reconciliation_removes_orphan_directories(self) -> None:
        area = pack_flow.staging()
        area.root.mkdir(parents=True, exist_ok=True)
        orphan = area.root / "stg-orphaned0000000000"
        orphan.mkdir()
        (orphan / "leftover.txt").write_text("partial")
        recovered = pack_flow.recover_interrupted_imports()
        self.assertFalse(orphan.exists())
        self.assertIn("stg-orphaned0000000000", recovered)


class CheckAuditTest(unittest.TestCase):
    def test_a_flawed_check_is_withheld_not_graded(self) -> None:
        check = {
            "check_id": "chk-1",
            "version": 1,
            "evidence_target": "recall",
            "stimulus": "The answer is 150 ml. How much is in the jug?",
            "rubric": ["Says 150 ml"],
            "reference_answer": "150 ml",
            "audit_state": "passed",
        }
        self.assertIsNone(pack_flow.check_spec_from_pack_check(check, recipe="casual"))
        passed, problems = pack_flow.audit_check_for_import(check)
        self.assertFalse(passed)
        self.assertIn("reference answer appears in the stimulus", problems)

    def test_an_audited_check_becomes_a_closed_form_spec(self) -> None:
        check = {
            "check_id": "chk-2",
            "version": 1,
            "evidence_target": "comprehension",
            "stimulus": "The jug is marked every 50 ml. Liquid reaches the third mark. How many millilitres?",
            "rubric": ["Answers 150 ml", "Counts the marks"],
            "reference_answer": "150 ml",
            "accepted_alternatives": ["150", "150ml"],
            "audit_state": "unreviewed",
        }
        spec = pack_flow.check_spec_from_pack_check(check, recipe="casual")
        self.assertIsNotNone(spec)
        self.assertEqual(spec["audit_state"], "passed")
        self.assertEqual(spec["audit_source"], "import_automated_audit")
        self.assertEqual(spec["declared_audit_state"], "unreviewed")
        self.assertEqual(spec["reference"]["kind"], "exact")

    def test_no_accepted_alternatives_is_not_a_flaw(self) -> None:
        # cb.projection R5: the reference answer is already an accepted form.
        check = {
            "check_id": "chk-3",
            "version": 1,
            "evidence_target": "recall",
            "stimulus": "What is the capital of Utah?",
            "rubric": ["Names Salt Lake City"],
            "reference_answer": "Salt Lake City",
            "accepted_alternatives": [],
            "audit_state": "unreviewed",
        }
        self.assertEqual(pack_flow.audit_check_for_import(check), (True, []))
        spec = pack_flow.check_spec_from_pack_check(check, recipe="casual")
        self.assertIsNotNone(spec)
        self.assertEqual(spec["reference"], {"kind": "exact", "answers": ["Salt Lake City"]})

    def test_alternatives_that_only_repeat_the_reference_are_withheld(self) -> None:
        # cb.projection R5, negative half: a list in disguise is still a flaw.
        check = {
            "check_id": "chk-4",
            "version": 1,
            "evidence_target": "recall",
            "stimulus": "What is 2 + 2?",
            "rubric": ["States four"],
            "reference_answer": "4",
            "accepted_alternatives": ["4", " 4 "],
            "audit_state": "unreviewed",
        }
        self.assertEqual(
            pack_flow.audit_check_for_import(check),
            (False, ["accepted alternatives do not add an accepted form"]),
        )
        self.assertIsNone(pack_flow.check_spec_from_pack_check(check, recipe="casual"))

    def test_a_check_its_author_marked_failed_is_never_graded(self) -> None:
        # cb.projection R6: a declaration can never grant gradability, and may always refuse it.
        check = {
            "check_id": "chk-5",
            "version": 1,
            "evidence_target": "recall",
            "stimulus": "What is 2 + 2?",
            "rubric": ["States four"],
            "reference_answer": "4",
            "accepted_alternatives": ["four"],
            "audit_state": "failed",
        }
        passed, problems = pack_flow.audit_check_for_import(check)
        self.assertFalse(passed)
        self.assertIn("the pack declares this check failed its own audit", problems)
        self.assertIsNone(pack_flow.check_spec_from_pack_check(check, recipe="casual"))
        # A declared 'passed' or 'unreviewed' still has to pass R1-R5 on its own.
        check["audit_state"] = "passed"
        self.assertIsNotNone(pack_flow.check_spec_from_pack_check(check, recipe="casual"))


class InstalledPackReadTest(PackFlowCase):
    """cb.rpc v4: ``pack.list`` / ``pack.inspect`` read installed packs, grant-free."""

    def install(self, source: Path = JAPANESE, *, name: str = "pack.zip") -> dict:
        staged_id, manifest = self.grant(source, name=name)
        self.import_pack(staged_id)
        return manifest

    def adopt_only(self, source: Path = JAPANESE, *, name: str = "adopted-only.zip") -> dict:
        """Adopt without importing: an identity installed with no ``packs`` row."""
        manifest, files = archive.read_directory(source)
        destination = self.work / name
        archive.write_archive(destination, manifest, files)
        staged = pack_flow.staging().stage(pack_flow.grant_local_file(destination))
        pack_flow.validate_and_audit(staged)
        pack_flow.library().adopt(staged, source="local")
        return manifest

    # ── pack.list ──────────────────────────────────────────────────────
    def test_list_slices_to_limit_but_reports_the_true_total(self) -> None:
        from coursebook import contracts

        japanese = self.install()
        parent = self.install(PARENT, name="parent.zip")

        full = self.ok("pack.list", {})["result"]
        contracts.validate_response_payload("pack.list", full)
        self.assertEqual(full["total"], 2)
        self.assertEqual(len(full["items"]), 2)
        self.assertFalse(full["truncated"])
        self.assertEqual(full["applied_filter"], "all")
        self.assertEqual(
            {item["pack_id"] for item in full["items"]},
            {japanese["pack_id"], parent["pack_id"]},
        )

        limited = self.ok("pack.list", {"limit": 1})["result"]
        contracts.validate_response_payload("pack.list", limited)
        self.assertEqual(limited["total"], 2)
        self.assertEqual(len(limited["items"]), 1)
        self.assertTrue(limited["truncated"])

        # Documented ordering: installed_at desc, then pack_id, then pack_version asc.
        expected = sorted(
            full["items"],
            key=lambda item: (item["pack_id"], item["pack_version"]),
        )
        expected.sort(key=lambda item: item["installed_at"], reverse=True)
        self.assertEqual([item["pack_id"] for item in full["items"]], [item["pack_id"] for item in expected])

        filtered = self.ok("pack.list", {"filter": "installed"})["result"]
        self.assertEqual(filtered["total"], 2)
        self.assertEqual(filtered["applied_filter"], "installed")
        none_frozen = self.ok("pack.list", {"filter": "frozen"})["result"]
        self.assertEqual(none_frozen["total"], 0)
        self.assertEqual(none_frozen["items"], [])

    def test_an_adopted_pack_without_a_packs_row_is_listed(self) -> None:
        from coursebook import contracts

        manifest = self.adopt_only()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM packs"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM enrollments"), 0)

        listing = self.ok("pack.list", {})["result"]
        contracts.validate_response_payload("pack.list", listing)
        self.assertEqual(listing["total"], 1)
        row = listing["items"][0]
        self.assertEqual(row["pack_id"], manifest["pack_id"])
        self.assertEqual(row["pack_version"], manifest["pack_version"])
        # The index is the fallback authority when the kernel has no row yet.
        self.assertEqual(row["state"], "installed")
        self.assertEqual(row["revision"], 0)
        self.assertEqual(row["content_hash"], manifest["content_hash"])

    def test_a_list_row_carries_no_path_and_no_manifest(self) -> None:
        manifest = self.install()
        listing = self.ok("pack.list", {})["result"]
        row = listing["items"][0]
        self.assertEqual(
            set(row),
            {
                "pack_id",
                "pack_version",
                "content_hash",
                "recipe",
                "source",
                "state",
                "revision",
                "installed_at",
                "file_count",
                "expanded_bytes",
                "license",
            },
        )
        self.assertEqual(row["file_count"], len(manifest["files"]))
        self.assertEqual(
            row["expanded_bytes"], sum(int(entry["bytes"]) for entry in manifest["files"])
        )
        text = json.dumps(listing)
        self.assertNotIn("directory", text)
        self.assertNotIn("manifest", text)
        self.assertNotIn(str(self.home), text)
        # No enrollment claim either: library.list owns that fact.
        for forbidden in ("course_id", "enrollment_id", "enrolled"):
            self.assertNotIn(forbidden, row)

    # ── pack.inspect ───────────────────────────────────────────────────
    def test_inspect_reports_matching_hashes_and_separate_trust_labels(self) -> None:
        from coursebook import contracts

        manifest = self.install()
        response = self.ok(
            "pack.inspect",
            {"pack_id": manifest["pack_id"], "pack_version": manifest["pack_version"]},
        )["result"]
        contracts.validate_response_payload("pack.inspect", response)
        self.assertEqual(
            set(response), {"pack", "manifest", "integrity", "trust"}
        )
        self.assertEqual(response["manifest"]["pack_id"], manifest["pack_id"])
        self.assertTrue(response["integrity"]["hashes_match"])
        self.assertEqual(response["integrity"]["file_count"], len(manifest["files"]))
        labels = response["trust"]["labels"]
        self.assertIn("integrity_verified", labels)
        self.assertIn("automated_checks_passed", labels)
        self.assertNotIn("human_review_recorded", labels)
        self.assertNotIn("safe", labels)
        self.assertNotIn("verified", labels)
        self.assertNotIn("directory", json.dumps(response))
        self.assertNotIn(str(self.home), json.dumps(response))

    def test_inspect_reports_drift_instead_of_raising(self) -> None:
        manifest = self.install()
        record = pack_flow.library().list()[0]
        directory = Path(str(record["directory"]))
        entry = manifest["files"][0]
        target = directory / str(entry["path"])
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"x")
            drifted = self.ok(
                "pack.inspect",
                {"pack_id": manifest["pack_id"], "pack_version": manifest["pack_version"]},
            )["result"]
            self.assertFalse(drifted["integrity"]["hashes_match"])
            self.assertNotIn("integrity_verified", drifted["trust"]["labels"])
        finally:
            target.write_bytes(original)

        restored = self.ok(
            "pack.inspect",
            {"pack_id": manifest["pack_id"], "pack_version": manifest["pack_version"]},
        )["result"]
        self.assertTrue(restored["integrity"]["hashes_match"])
        self.assertIn("integrity_verified", restored["trust"]["labels"])

    def test_inspect_unknown_identity_is_not_found(self) -> None:
        manifest = self.install()
        error = self.err(
            "pack.inspect",
            {"pack_id": manifest["pack_id"], "pack_version": "9.9.9"},
        )
        self.assertEqual(error["code"], "NOT_FOUND")


class RegistryTest(unittest.TestCase):
    def test_every_pack_method_is_registered_and_frozen(self) -> None:
        from coursebook.contracts import method_names

        frozen = set(method_names())
        for method in pack_flow.PACK_METHODS:
            self.assertIn(method, frozen)
            self.assertIn(method, api.implemented_methods())


if __name__ == "__main__":
    unittest.main()
