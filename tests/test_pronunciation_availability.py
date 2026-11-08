"""H-138: the stable pronunciation availability contract and the no-score path.

These tests run against a real migrated SQLite database. The only double is the recogniser
adapter, exactly like ``tests/test_pronunciation.py``: no model, no network, no ffmpeg.

The contract under test (what H-108's pane renders) is:

* ``available``    — narration exists (or no block context was asked) and the recogniser can run;
* ``practice_only`` — narration exists but the recogniser cannot run right now;
* ``no_audio``     — the named block/objective/artifact has no usable narration audio child;
* ``unavailable``  — the named context could not be established at all.

Every state carries a bounded ``reason`` and exactly one ``next_action``. An attempt that never
ran a recogniser must never carry a word/phoneme accuracy or a passing verdict.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from coursebook import db, pronunciation, stt
from tests.kernel_support import KernelCase
from tests.test_pronunciation import FakeStt, data_url, wav_bytes

GEN_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS gen_plan_documents (
        id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, course_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL, plan_hash TEXT NOT NULL,
        document_json TEXT NOT NULL, research_json TEXT NOT NULL,
        generation_state TEXT NOT NULL, validation_id TEXT,
        result_json TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(course_id, request_fingerprint)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_plan_sections (
        id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
        plan_hash TEXT NOT NULL, title TEXT NOT NULL, lesson_intent TEXT NOT NULL,
        media_need_json TEXT, objective_refs_json TEXT NOT NULL DEFAULT '[]',
        context_needs_json TEXT NOT NULL DEFAULT '[]',
        source_ids_json TEXT NOT NULL DEFAULT '[]', unit_id TEXT,
        section_role TEXT NOT NULL DEFAULT 'owner',
        UNIQUE(plan_id, plan_hash, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_lessons (
        id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, section_id TEXT NOT NULL,
        plan_hash TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL,
        page_json TEXT NOT NULL, media_json TEXT NOT NULL DEFAULT '[]',
        parent_notes_json TEXT, rejection_reasons_json TEXT NOT NULL DEFAULT '[]',
        validation_id TEXT, policy_json TEXT, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, UNIQUE(section_id, plan_hash, version)
    )
    """,
)


class OfflineLocalWhisper(stt.LocalWhisperAdapter):
    """The production adapter with a recogniser that is honestly unavailable."""

    def __init__(self, reason: str = "stt_dependency_missing") -> None:
        super().__init__(model_name="offline")
        self.reason = reason

    def availability(self) -> tuple[bool, str | None]:
        return False, self.reason


class ExplodingStt(FakeStt):
    """A recogniser bug, not a typed ``SttUnavailable``."""

    def transcribe(self, path: Path, *, language=None, prompt=None):  # noqa: ANN001
        self.calls += 1
        raise RuntimeError("recogniser exploded")


def insert_artifact(kind: str = "audio", mime: str = "audio/mpeg") -> str:
    artifact_id = f"art_{os.urandom(8).hex()}"
    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
            " provenance_json, ref_count, created_at) VALUES (?, NULL, ?, ?, ?, 0, ?, '{}', 0, ?)",
            (artifact_id, kind, "sha256:" + os.urandom(16).hex(), "artifacts/x.bin", mime, db.utcnow()),
        )
    return artifact_id


class AvailabilityContractTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()
        stt.configure(FakeStt())

    def tearDown(self) -> None:
        stt.reset_adapter()
        super().tearDown()

    # ── shapes ──────────────────────────────────────────────────────────

    def test_the_probe_answers_one_of_four_states_with_a_reason_and_one_next_action(self) -> None:
        result = pronunciation.availability()
        self.assertIn(result["status"], pronunciation.AVAILABILITY_STATES)
        self.assertIn("reason", result)
        self.assertTrue(result["next_action"])
        self.assertEqual(result["retention"]["audio_retained"], False)
        self.assertIn("staged_take_ttl_seconds", result["retention"])
        self.assertEqual(result["local_only"], True)

    def test_a_ready_recogniser_without_block_context_is_available(self) -> None:
        result = pronunciation.availability()
        self.assertEqual(result["status"], "available")
        self.assertTrue(result["available"])
        self.assertIsNone(result["reason"])
        self.assertEqual(result["provider"], stt.PROVIDER)
        self.assertFalse(result["narration"]["checked"])
        self.assertEqual(result["next_action"], pronunciation._NEXT_ACTION["available"])

    # ── missing model / recogniser ──────────────────────────────────────

    def test_a_missing_recogniser_is_practice_only_never_unavailable_or_a_score(self) -> None:
        stt.configure(OfflineLocalWhisper())
        result = pronunciation.availability()
        self.assertEqual(result["status"], "practice_only")
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "stt_dependency_missing")
        self.assertIn("faster-whisper", result["next_action"])
        self.assertFalse(("word_accuracy" in result))

    def test_a_missing_ffmpeg_is_practice_only_with_an_install_action(self) -> None:
        stt.configure(OfflineLocalWhisper("ffmpeg_missing"))
        result = pronunciation.availability()
        self.assertEqual(result["status"], "practice_only")
        self.assertEqual(result["reason"], "ffmpeg_missing")
        self.assertIn("ffmpeg", result["next_action"])

    def test_the_probe_never_loads_or_downloads_a_model(self) -> None:
        adapter = stt.LocalWhisperAdapter(model_name="never-download", cache_dir=Path(tempfile.mkdtemp()))
        with mock.patch.object(stt, "_import_whisper", return_value=object()), \
                mock.patch.object(stt.shutil, "which", return_value="/usr/bin/ffmpeg"), \
                mock.patch.object(adapter, "_model", side_effect=AssertionError("model loaded")):
            stt.configure(adapter)
            result = pronunciation.availability()
        self.assertEqual(result["status"], "available")

    # ── missing narration ───────────────────────────────────────────────

    def test_a_missing_artifact_is_no_audio_not_a_practice_only_dead_end(self) -> None:
        result = pronunciation.availability(media_artifact_id="art_does_not_exist")
        self.assertEqual(result["status"], "no_audio")
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "narration_missing")
        self.assertTrue(result["narration"]["checked"])
        self.assertFalse(result["narration"]["present"])
        self.assertIn("narration", result["next_action"])

    def test_a_non_audio_artifact_is_not_a_narration_reference(self) -> None:
        visual = insert_artifact(kind="visual", mime="image/png")
        result = pronunciation.availability(media_artifact_id=visual)
        self.assertEqual(result["status"], "no_audio")
        self.assertEqual(result["reason"], "narration_missing")

    def test_an_audio_artifact_seats_the_studio(self) -> None:
        narration = insert_artifact(kind="audio", mime="audio/mpeg")
        result = pronunciation.availability(media_artifact_id=narration)
        self.assertEqual(result["status"], "available")
        self.assertTrue(result["narration"]["present"])

    def test_an_objective_without_generated_media_is_no_audio(self) -> None:
        result = pronunciation.availability(
            enrollment_id=self.lesson["enrollment_id"], objective_id=self.lesson["objective_id"]
        )
        self.assertEqual(result["status"], "no_audio")
        self.assertEqual(result["reason"], "no_authored_media")
        self.assertIn("authored media", result["next_action"])

    def test_an_objective_outside_the_enrollments_approved_plan_is_unavailable(self) -> None:
        other = self.prepare_lesson()
        result = pronunciation.availability(
            enrollment_id=self.lesson["enrollment_id"], objective_id=other["objective_id"]
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "objective_not_in_approved_plan")
        self.assertIn("approved plan", result["next_action"])

    def test_a_store_read_failure_is_unavailable_never_an_exception(self) -> None:
        with mock.patch.object(db, "read", side_effect=RuntimeError("store gone")):
            result = pronunciation.availability(objective_id=self.lesson["objective_id"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "availability_unreadable")
        self.assertIn("backend log", result["next_action"])

    # ── authored narration through the generation tables ────────────────

    def _seed_generated_narration(self, media: list[dict]) -> None:
        ordinal = self.scalar(
            "SELECT ordinal FROM objectives WHERE id = ?", (self.lesson["objective_id"],)
        )
        self.assertIsNotNone(ordinal)
        objective_refs = json.dumps([int(str(ordinal))])
        plan_hash = f"hash_{os.urandom(6).hex()}"
        section_id = f"sec_{os.urandom(6).hex()}"
        now = db.utcnow()
        for statement in GEN_SCHEMA:
            self.execute(statement)
        self.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
            " document_json, research_json, generation_state, validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, '{}', '{}', 'validated', NULL, '{}', ?)",
            (f"doc_{os.urandom(6).hex()}", self.lesson["plan_id"], self.lesson["course_id"],
             os.urandom(16).hex(), plan_hash, now),
        )
        self.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
            " media_need_json, objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, 'Greeting', 'say hello', '{}', ?, '[]', '[]')",
            (section_id, self.lesson["plan_id"], plan_hash, objective_refs),
        )
        self.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
            " media_json, rejection_reasons_json, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, 'validated', '{}', ?, '[]', ?, ?)",
            (f"lsn_{os.urandom(6).hex()}", self.lesson["plan_id"], section_id, plan_hash,
             json.dumps(media), now, now),
        )

    def test_authored_narration_audio_is_available(self) -> None:
        narration = insert_artifact()
        self._seed_generated_narration(
            [{"kind": "audio", "role": "narration", "artifact_id": narration}]
        )
        result = pronunciation.availability(
            enrollment_id=self.lesson["enrollment_id"], objective_id=self.lesson["objective_id"]
        )
        self.assertEqual(result["status"], "available")
        self.assertTrue(result["narration"]["present"])

    def test_authored_narration_without_an_artifact_is_no_audio_degraded(self) -> None:
        self._seed_generated_narration(
            [{"kind": "audio", "role": "narration", "artifact_id": None, "degraded": True}]
        )
        result = pronunciation.availability(
            enrollment_id=self.lesson["enrollment_id"], objective_id=self.lesson["objective_id"]
        )
        self.assertEqual(result["status"], "no_audio")
        self.assertEqual(result["reason"], "narration_degraded")

    def test_authored_narration_with_the_recogniser_offline_is_practice_only(self) -> None:
        narration = insert_artifact()
        self._seed_generated_narration(
            [{"kind": "audio", "role": "narration", "artifact_id": narration}]
        )
        stt.configure(OfflineLocalWhisper("model_unavailable"))
        result = pronunciation.availability(
            enrollment_id=self.lesson["enrollment_id"], objective_id=self.lesson["objective_id"]
        )
        self.assertEqual(result["status"], "practice_only")
        self.assertEqual(result["reason"], "model_unavailable")
        self.assertIn("model", result["next_action"])

    # ── retention ───────────────────────────────────────────────────────

    def test_a_stale_orphaned_take_is_swept_and_a_fresh_one_is_kept(self) -> None:
        root = db.data_root() / "pronunciation-tmp"
        root.mkdir(parents=True, exist_ok=True)
        stale = root / "take-orphan.bin"
        fresh = root / "take-live.bin"
        stale.write_bytes(b"old")
        fresh.write_bytes(b"new")
        old = time.time() - (pronunciation.MAX_TAKE_AGE_SECONDS + 60)
        os.utime(stale, (old, old))
        result = pronunciation.availability()
        self.assertFalse(stale.exists(), "a take past the retention window must be removed")
        self.assertTrue(fresh.exists(), "a take inside its attempt window must not be swept")
        self.assertEqual(result["retention"]["swept_stale_takes"], 1)


class NoScorePathTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()
        self.fake = FakeStt()
        stt.configure(self.fake)

    def tearDown(self) -> None:
        stt.reset_adapter()
        super().tearDown()

    def attempt(self, *, key: str, nonce: str = "nonce-h138", audio: str | None = None) -> dict:
        return self.dispatch(
            "pronunciation.attempt",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "attempt_nonce": nonce,
                "target": "good morning",
                "locale": "en-US",
                "audio_data_url": audio or data_url(wav_bytes()),
            },
            expected_revision=self.lesson["revision"],
            idempotency_key=key,
        )

    def assert_no_score(self, result: dict) -> None:
        self.assertFalse(result["recorded"])
        self.assertIsNone(result["attempt_id"])
        assessment = result["assessment"]
        self.assertEqual(assessment["verdict"], "unavailable")
        self.assertIsNone(assessment["transcript"])
        self.assertIsNone(assessment["word_accuracy"])
        self.assertIsNone(assessment["phoneme_accuracy"])
        self.assertIsNone(assessment["confidence"])
        self.assertEqual(assessment["words"], [])
        self.assertNotIn("accuracy", assessment, "there is no invented scalar to render")
        self.assertEqual(self.rows("SELECT * FROM pronunciation_attempts"), [])

    def test_a_missing_model_is_unavailable_with_no_score_and_replays(self) -> None:
        self.fake.fail = "model_unavailable"
        response = self.attempt(key="key-h138-model")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "model_unavailable")
        self.assert_no_score(result)
        replay = self.attempt(key="key-h138-model")
        self.assertEqual(replay["result"], result)
        self.assertEqual(self.fake.calls, 1, "a replay must not recognise again")

    def test_a_recogniser_exception_is_unavailable_with_no_score(self) -> None:
        exploding = ExplodingStt()
        stt.configure(exploding)
        response = self.attempt(key="key-h138-explode")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "transcription_failed")
        self.assert_no_score(result)
        self.assertEqual(exploding.calls, 1)

    def test_a_take_longer_than_the_bound_is_refused_before_inference(self) -> None:
        adapter = stt.LocalWhisperAdapter(model_name="bounded", cache_dir=Path(tempfile.mkdtemp()))
        done = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"\x00" * (stt.MAX_PCM_BYTES + 2), stderr=b""
        )
        with mock.patch.object(stt.shutil, "which", return_value="/usr/bin/ffmpeg"), \
                mock.patch.object(stt.subprocess, "run", return_value=done), \
                mock.patch.object(adapter, "_model", side_effect=AssertionError("model loaded")):
            with self.assertRaises(stt.SttUnavailable) as raised:
                adapter.transcribe(Path("/tmp/take.bin"), language="en")
        self.assertEqual(raised.exception.reason, "audio_too_long")

    def test_a_known_missing_recogniser_writes_no_audio_at_all(self) -> None:
        stt.configure(OfflineLocalWhisper())
        response = self.attempt(key="key-h138-preflight")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "stt_dependency_missing")
        self.assert_no_score(result)
        root = db.data_root() / "pronunciation-tmp"
        self.assertEqual(list(root.glob("take-*.bin")), [], "no take may be staged preflight")

    def test_a_passing_verdict_requires_a_real_transcript(self) -> None:
        result = self.attempt(key="key-h138-pass")["result"]
        self.assertEqual(result["status"], "assessed")
        self.assertEqual(result["assessment"]["verdict"], "meets_target")
        self.assertEqual(result["assessment"]["word_accuracy"], 1.0)


class SttDiagnosticsTest(unittest.TestCase):
    def test_described_reports_the_bounded_failure_class_not_a_message(self) -> None:
        class _Model:
            def __init__(self, *args, **kwargs):  # noqa: ANN002,ANN003
                raise MemoryError("allocation failed at /home/private/path/model.bin")

        class _Whisper:
            WhisperModel = _Model

        adapter = stt.LocalWhisperAdapter(model_name="diag", cache_dir=Path(tempfile.mkdtemp()))
        stt.configure(adapter)
        try:
            with mock.patch.object(stt, "_import_whisper", return_value=_Whisper), \
                    mock.patch.object(adapter, "_decode", return_value=b"\x00\x00" * 8_000):
                with self.assertRaises(stt.SttUnavailable) as raised:
                    adapter.transcribe(Path("/tmp/take.bin"))
            self.assertEqual(raised.exception.reason, "model_unavailable")
            self.assertEqual(raised.exception.detail, "MemoryError")
            described = stt.described()
            self.assertEqual(described["last_failure"]["reason"], "model_unavailable")
            self.assertEqual(described["last_failure"]["detail"], "MemoryError")
            self.assertNotIn("private", json.dumps(described), "no message or path may leak")
        finally:
            stt.reset_adapter()


class StatusRouteTest(KernelCase):
    """The host route the pane actually calls returns the same contract as the kernel function."""

    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()

    @staticmethod
    def _module():
        import importlib.util
        import sys

        path = Path(__file__).resolve().parent.parent / "dashboard" / "plugin_api.py"
        spec = importlib.util.spec_from_file_location("coursebook_plugin_api_h138", path)
        if spec is None or spec.loader is None:  # pragma: no cover - packaging error
            raise AssertionError("cannot load dashboard/plugin_api.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_the_status_route_returns_state_reason_and_one_next_action(self) -> None:
        import asyncio

        body = asyncio.run(self._module().pronunciation_status())
        self.assertTrue(body["ok"])
        self.assertIn(body["status"], pronunciation.AVAILABILITY_STATES)
        self.assertTrue(body["next_action"])
        self.assertIn("retention", body)
        self.assertEqual(body["retention"]["audio_retained"], False)

    def test_the_status_route_answers_no_audio_for_a_missing_narration(self) -> None:
        import asyncio

        body = asyncio.run(
            self._module().pronunciation_status(media_artifact_id="art_missing")
        )
        self.assertEqual(body["status"], "no_audio")
        self.assertEqual(body["reason"], "narration_missing")
        self.assertIn("narration", body["next_action"])


if __name__ == "__main__":
    unittest.main()
