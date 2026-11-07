"""Lesson media generation: host adapter, cache, fallback, projection and preview."""

from __future__ import annotations

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
        self.store = artifacts.ArtifactStore(Path(self.home) / "artifacts")
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

    def test_preview_returns_a_verified_data_url_and_rejects_unknown(self) -> None:
        self.generate(FakeHost())
        visual = next(item for item in self.stored_media() if item["kind"] == "visual")
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(media.preview_artifact("art_missing")["code"], "NOT_FOUND")


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
