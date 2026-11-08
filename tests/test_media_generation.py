"""Lesson media generation: host adapter, cache, fallback, projection and preview."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path

from coursebook import artifacts, db, generation, media

from tests.kernel_support import KernelCase

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"x" * 32
MP3 = b"\xff\xfb\x90\x00" + b"x" * 32
NOW = "2026-11-06T12:00:00Z"
HASH = "sha256:" + "a" * 64


class FakeHost:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.images: list[str] = []
        self.speeches: list[str] = []

    def image(self, prompt: str, *, aspect_ratio: str = "landscape"):
        self.images.append(prompt)
        if self.fail:
            raise media.MediaGenerationError("image provider offline")
        return PNG, "image/png"

    def speech(self, text: str, *, voice=None, language=None, instructions=None):
        self.speeches.append(text)
        if self.fail:
            raise media.MediaGenerationError("tts provider offline")
        return MP3, "audio/mpeg"


class MediaGenerationTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.course_id, self.plan_id = self.new_course()
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        self.objective_id = self.seed_objective(self.plan_id)
        self.enrollment_id = self.new_enrollment(self.course_id)
        # The canonical store the preview route reads from, not a fixture-local root: the route
        # refuses any path outside ``<plugin data>/artifacts``, so a test store elsewhere would be
        # testing a layout production never has.
        self.store = artifacts.ArtifactStore()
        self.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
            " document_json, research_json, generation_state, validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, '{}', 'validated', NULL, '{}', ?)",
            ("gen_doc_1", self.plan_id, self.course_id, "fp-1", HASH, json.dumps({"locale": "ja"}), NOW),
        )
        self.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
            " objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, ?, ?, ?, '[]', '[]')",
            ("sec_1", self.plan_id, HASH, "Greeting", "Say hello", json.dumps([1])),
        )
        self.media_items = [
            {
                "kind": "visual",
                "role": "illustration",
                "purpose": "See the workshop bench",
                "spec": "An editorial illustration of a workshop bench with a torque wrench",
                "text_equivalent": "A workshop bench with a torque wrench.",
            },
            {
                "kind": "audio",
                "role": "narration",
                "purpose": "Hear the greeting",
                "spec": "A slow, clear Japanese greeting",
                "text_equivalent": "こんにちは",
                "transcript": "こんにちは",
                "language": "ja-JP",
                "voice": "default",
            },
        ]
        self.lesson_id = "gen_lesson_1"
        self.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
            " media_json, parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, 'validated', '{}', ?, '{}', '[]', NULL, ?, ?)",
            (self.lesson_id, self.plan_id, "sec_1", HASH, json.dumps(self.media_items), NOW, NOW),
        )

    def generate(self, host, *, lesson_ids=None):
        with db.read() as connection:
            return media.generate_for_lessons(
                connection,
                lesson_ids=lesson_ids or [self.lesson_id],
                job_id="job_media_1",
                host=host,
                store=self.store,
                now=datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc),
            )

    def stored_media(self) -> list[dict]:
        row = self.rows("SELECT media_json FROM gen_lessons WHERE id = ?", (self.lesson_id,))[0]
        return json.loads(row["media_json"])

    def test_generates_images_and_audio_and_attaches_artifacts(self) -> None:
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.generated, 2)
        self.assertEqual(len(host.images), 1)
        self.assertEqual(len(host.speeches), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 2)
        stored = self.stored_media()
        self.assertTrue(all(item.get("artifact_id") for item in stored))
        self.assertEqual({item["mime"] for item in stored}, {"image/png", "audio/mpeg"})
        self.assertTrue(all(item.get("label") for item in stored))

    def test_second_run_reuses_cached_artifacts_without_provider_calls(self) -> None:
        self.generate(FakeHost())
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.reused, 2)
        self.assertEqual(summary.generated, 0)
        self.assertEqual(host.images, [])
        self.assertEqual(host.speeches, [])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 2)

    # ── H-169: a model_assessed page is readable, so its media is content ───────────────

    def set_lesson_state(self, state: str) -> None:
        self.execute("UPDATE gen_lessons SET state = ? WHERE id = ?", (state, self.lesson_id))

    def test_model_assessed_lesson_generates_visual_and_audio(self) -> None:
        self.set_lesson_state("model_assessed")
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.generated, 2)
        self.assertEqual(summary.skipped, 0)
        self.assertEqual(len(host.images), 1)
        self.assertEqual(len(host.speeches), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 2)
        stored = self.stored_media()
        self.assertEqual({item["mime"] for item in stored}, {"image/png", "audio/mpeg"})
        self.assertTrue(all(item.get("artifact_id") for item in stored))
        # The page's own provenance travels with each artifact it produced: a model-assessed
        # page never yields bytes that read as independently validated.
        for item in stored:
            provenance = json.loads(
                str(self.scalar("SELECT provenance_json FROM artifacts WHERE id = ?", (item["artifact_id"],)))
            )
            self.assertEqual(provenance["lesson_state"], "model_assessed")
            self.assertFalse(provenance["independent"])
            self.assertNotIn("independently validated", str(item["label"]).casefold())
        # The preview route exposes the same judgement, not just the bytes.
        visual = next(item for item in stored if item["kind"] == "visual")
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["lesson_state"], "model_assessed")
        self.assertFalse(preview["independent"])

    def test_model_assessed_lesson_reuses_cached_artifacts(self) -> None:
        self.set_lesson_state("model_assessed")
        self.generate(FakeHost())
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.reused, 2)
        self.assertEqual(summary.generated, 0)
        self.assertEqual(host.images, [])
        self.assertEqual(host.speeches, [])
        stored = self.stored_media()
        self.assertTrue(all(item.get("artifact_id") for item in stored))

    def test_needs_review_lesson_generates_no_media_and_stays_text_complete(self) -> None:
        self.set_lesson_state("needs_review")
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.generated, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(host.images, [])
        self.assertEqual(host.speeches, [])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)
        stored = self.stored_media()
        self.assertTrue(all(item["text_equivalent"] for item in stored))
        self.assertTrue(all(not item.get("artifact_id") for item in stored))

    def test_model_assessed_learner_page_carries_artifact_mime_equivalent_and_warning(self) -> None:
        self.set_lesson_state("model_assessed")
        self.generate(FakeHost())
        with db.read() as connection:
            page = generation.learner_page(connection, self.lesson_id)
        self.assertEqual(page["provenance"]["outcome"], "model_assessed")
        self.assertTrue(page["provenance"]["check_enabled"])
        self.assertFalse(page["provenance"]["independent"])
        self.assertIn("not independently validated", page["provenance"]["warning"])
        media = page["media"]
        self.assertEqual(len(media), 2)
        self.assertEqual({item["mime"] for item in media}, {"image/png", "audio/mpeg"})
        self.assertTrue(all(item.get("artifact_id") for item in media))
        self.assertTrue(all(item.get("text_equivalent") for item in media))
        # The projected document attaches the same artifacts to a teaching block.
        children = [child for block in page["document"]["blocks"] for child in block["media"]]
        self.assertEqual(
            {child["artifact_id"] for child in children},
            {item["artifact_id"] for item in media},
        )

    def test_provider_failure_keeps_text_equivalent_and_marks_degraded(self) -> None:
        summary = self.generate(FakeHost(fail=True))
        self.assertEqual(summary.generated, 0)
        self.assertEqual(summary.degraded, 2)
        stored = self.stored_media()
        self.assertTrue(all(item["degraded"] for item in stored))
        self.assertTrue(all(item.get("reason") for item in stored))
        self.assertTrue(all(item["text_equivalent"] for item in stored))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)

    def test_authored_media_is_projected_into_the_lesson_run(self) -> None:
        self.generate(FakeHost())
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, ?, ?, ?)",
            ("run_media_1", self.enrollment_id, self.objective_id, NOW, NOW, NOW),
        )
        with db.transaction() as connection:
            count = media.seed_authored_media(
                connection,
                lesson_run_id="run_media_1",
                objective_id=self.objective_id,
                now=NOW,
            )
        self.assertEqual(count, 2)
        segments = self.rows("SELECT kind, text, artifact_id FROM lesson_segments ORDER BY ordinal")
        self.assertEqual([row["kind"] for row in segments], ["media", "media"])
        self.assertTrue(all(row["artifact_id"] for row in segments))
        self.assertIn("こんにちは", [row["text"] for row in segments])

    def test_authored_media_is_projected_into_a_model_assessed_lesson_run(self) -> None:
        self.set_lesson_state("model_assessed")
        self.generate(FakeHost())
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, ?, ?, ?)",
            ("run_media_2", self.enrollment_id, self.objective_id, NOW, NOW, NOW),
        )
        with db.transaction() as connection:
            count = media.seed_authored_media(
                connection,
                lesson_run_id="run_media_2",
                objective_id=self.objective_id,
                now=NOW,
            )
        self.assertEqual(count, 2)
        segments = self.rows(
            "SELECT kind, text, artifact_id FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal",
            ("run_media_2",),
        )
        self.assertEqual([row["kind"] for row in segments], ["media", "media"])
        self.assertTrue(all(row["artifact_id"] for row in segments))

    def test_preview_returns_a_verified_data_url_and_rejects_unknown(self) -> None:
        self.generate(FakeHost())
        visual = next(item for item in self.stored_media() if item["kind"] == "visual")
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(media.preview_artifact("art_missing")["code"], "NOT_FOUND")

    def test_preview_passes_the_artifacts_permission_and_sources_to_the_reader(self) -> None:
        self.generate(FakeHost())
        visual = next(item for item in self.stored_media() if item["kind"] == "visual")
        provenance = json.loads(
            str(
                self.scalar(
                    "SELECT provenance_json FROM artifacts WHERE id = ?", (visual["artifact_id"],)
                )
            )
        )
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertEqual(preview["permission"], provenance["permission"])
        self.assertEqual(preview["source_ids"], provenance["source_ids"])
        self.assertIn("permission", preview)

    # ── H-115-D2: a row is a record, not a warrant ────────────────────────
    # The route used to serve whatever path an ``artifacts`` row named, with the row's declared
    # MIME. These three tests are the probe's T3a/T3c reproduced as suite tests.

    def insert_row(self, artifact_id: str, *, path: Path, mime: str, data: bytes, kind: str = "visual") -> None:
        self.execute(
            "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
            " provenance_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                self.course_id,
                kind,
                hashlib.sha256(data).hexdigest(),
                str(path),
                len(data),
                mime,
                json.dumps({"label": "probe"}),
                NOW,
            ),
        )

    def test_preview_refuses_a_row_pointing_outside_the_artifact_store(self) -> None:
        outside = Path(self.home) / "outside.png"
        outside.write_bytes(PNG)
        self.insert_row("art_outside0000000000000000000000001", path=outside, mime="image/png", data=PNG)
        preview = media.preview_artifact("art_outside0000000000000000000000001")
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["code"], "NOT_FOUND")
        self.assertNotIn("data_url", preview)
        # The refusal never echoes the path it refused.
        self.assertNotIn(str(outside), json.dumps(preview))

    def test_preview_refuses_a_symlink_that_escapes_the_artifact_store(self) -> None:
        outside = Path(self.home) / "outside-target.png"
        outside.write_bytes(PNG)
        store = artifacts.read_root()
        store.mkdir(parents=True, exist_ok=True)
        link = store / "escape.png"
        link.symlink_to(outside)
        self.insert_row("art_symlink000000000000000000000001", path=link, mime="image/png", data=PNG)
        preview = media.preview_artifact("art_symlink000000000000000000000001")
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["code"], "NOT_FOUND")

    def test_preview_refuses_html_bytes_declared_as_svg(self) -> None:
        payload = b"<html><script>alert(document.domain)</script></html>"
        store = artifacts.read_root()
        store.mkdir(parents=True, exist_ok=True)
        target = store / "mime-confusion.bin"
        target.write_bytes(payload)
        self.insert_row(
            "art_mimeconfusion00000000000000000001", path=target, mime="image/svg+xml", data=payload
        )
        preview = media.preview_artifact("art_mimeconfusion00000000000000000001")
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["code"], "UNSAFE_MEDIA")
        self.assertNotIn("data_url", preview)

    def test_preview_still_serves_a_genuine_svg_from_the_store(self) -> None:
        svg = artifacts.make_schematic_svg("Torque order", [{"label": "Step 1", "value": "20 Nm"}])
        store = artifacts.read_root()
        store.mkdir(parents=True, exist_ok=True)
        target = store / "schematic.svg"
        target.write_bytes(svg)
        self.insert_row("art_goodsvg00000000000000000000000001", path=target, mime="image/svg+xml", data=svg)
        preview = media.preview_artifact("art_goodsvg00000000000000000000000001")
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["mime"], "image/svg+xml")
        self.assertTrue(preview["data_url"].startswith("data:image/svg+xml;base64,"))


class MediaSpecTest(unittest.TestCase):
    def test_audio_spec_defaults_voice_and_language_from_locale(self) -> None:
        spec = media._media_spec(
            {
                "kind": "audio",
                "role": "narration",
                "text_equivalent": "こんにちは",
                "transcript": "こんにちは",
            },
            locale="ja-JP",
        )
        self.assertEqual(spec.voice, "default")
        self.assertEqual(spec.language, "ja-JP")
        self.assertEqual(spec.transcript, "こんにちは")
        self.assertEqual(media.artifacts.media_problems(spec), [])

    def test_illustration_technical_claim_is_refused(self) -> None:
        spec = media._media_spec(
            {
                "kind": "visual",
                "role": "illustration",
                "spec": "A torque sequence",
                "text_equivalent": "A torque sequence",
                "technical": True,
            }
        )
        self.assertTrue(media.artifacts.media_problems(spec))
