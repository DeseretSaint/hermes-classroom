"""M3-B1: the bounded pronunciation attempt, fail-closed recognition and separate evidence.

Everything runs against a real migrated SQLite database through the real RPC dispatcher. The only
test double is the recogniser adapter: unit tests never load a model, download weights or contact a
network. A separate regression test pins the faster-whisper call keyword (``initial_prompt``) that
a live run proved is required.
"""

from __future__ import annotations

import base64
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coursebook import db, packs, pronunciation, stt
from tests.kernel_support import KernelCase


def wav_bytes(seconds: float = 0.25, rate: int = 16_000) -> bytes:
    frames = b"\x00\x00" * max(1, int(rate * seconds))
    header = (
        b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data" + struct.pack("<I", len(frames))
    )
    return header + frames


def data_url(data: bytes, mime: str = "audio/wav") -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


class FakeStt:
    """A recogniser that returns exactly what the test declares — or a bounded failure."""

    def __init__(
        self,
        text: str = "good morning",
        *,
        confidence: float | None = 0.93,
        words: list[dict] | None = None,
        language: str = "en",
        fail: str | None = None,
    ) -> None:
        self.text = text
        self.confidence = confidence
        self.words = words if words is not None else [
            {"word": "good", "probability": 0.94},
            {"word": "morning", "probability": 0.92},
        ]
        self.language = language
        self.fail = fail
        self.calls = 0
        self.seen: list[Path] = []

    def transcribe(self, path: Path, *, language=None, prompt=None) -> stt.Transcription:
        self.calls += 1
        self.seen.append(Path(path))
        assert Path(path).exists(), "the take must be staged before the adapter sees it"
        if self.fail:
            raise stt.SttUnavailable(self.fail)
        return stt.Transcription(
            text=self.text,
            provider=stt.PROVIDER,
            model="fake-base",
            language=self.language,
            confidence=self.confidence,
            words=tuple(self.words),
            duration=1.0,
        )


class PronunciationAttemptTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()
        self.fake = FakeStt()
        stt.configure(self.fake)

    def tearDown(self) -> None:
        stt.reset_adapter()
        super().tearDown()

    # ── helpers ─────────────────────────────────────────────────────────

    def attempt(
        self,
        *,
        target: str = "good morning",
        locale: str = "en-US",
        audio: str | None = None,
        nonce: str = "nonce-pron-1",
        key: str | None = None,
        revision: int | None = None,
    ) -> dict:
        return self.dispatch(
            "pronunciation.attempt",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "attempt_nonce": nonce,
                "target": target,
                "locale": locale,
                "audio_data_url": audio or data_url(wav_bytes()),
            },
            expected_revision=self.lesson["revision"] if revision is None else revision,
            idempotency_key=key,
        )

    def rows_of(self, table: str) -> list[dict]:
        return self.rows(f"SELECT * FROM {table}")

    # ── success ─────────────────────────────────────────────────────────

    def test_a_real_transcript_records_a_separate_model_assessed_attempt(self) -> None:
        before = {
            table: len(self.rows_of(table)) for table in ("attempts", "evidence", "transitions")
        }
        response = self.attempt(key="key-pron-success")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "assessed")
        self.assertTrue(result["recorded"])
        self.assertIsNone(result["reason"])
        self.assertTrue(result["attempt_id"].startswith("prn_"))
        assessment = result["assessment"]
        self.assertEqual(assessment["transcript"], "good morning")
        self.assertEqual(assessment["target"], "good morning")
        self.assertEqual(assessment["provider"], "coursebook_local_whisper")
        self.assertEqual(assessment["model"], "fake-base")
        self.assertEqual(assessment["evidence_class"], "model_assessed")
        self.assertEqual(assessment["verdict"], "meets_target")
        self.assertEqual(assessment["word_accuracy"], 1.0)
        self.assertIsNone(assessment["phoneme_accuracy"])
        self.assertEqual([word["expected"] for word in assessment["words"]], ["good", "morning"])
        self.assertTrue(all(word["match"] for word in assessment["words"]))

        rows = self.rows_of("pronunciation_attempts")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], result["attempt_id"])
        self.assertEqual(rows[0]["evidence_class"], "model_assessed")
        self.assertEqual(rows[0]["verdict"], "meets_target")
        # Separate from a text attempt: no graded attempt, no new evidence row, no transition.
        self.assertEqual(len(self.rows_of("attempts")), before["attempts"])
        self.assertEqual(len(self.rows_of("evidence")), before["evidence"])
        self.assertEqual(len(self.rows_of("transitions")), before["transitions"])
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?", (self.lesson["objective_id"],)),
                         "not_started")
        self.assertEqual(self.scalar("SELECT state FROM checks WHERE id = ?", (self.lesson["check_id"],)),
                         "open")
        self.assertEqual(self.scalar("SELECT revision FROM enrollments WHERE id = ?",
                                     (self.lesson["enrollment_id"],)), self.lesson["revision"])

    def test_the_take_is_deleted_after_scoring_and_never_becomes_an_artifact(self) -> None:
        self.assertTrue(self.attempt(key="key-pron-temp")["ok"])
        self.assertEqual(self.rows_of("artifacts"), [])
        temp_root = db.data_root() / "pronunciation-tmp"
        self.assertEqual(list(temp_root.glob("*")), [], "the take must not survive scoring")
        stored = json.dumps(self.rows_of("pronunciation_attempts"), ensure_ascii=False)
        self.assertNotIn("pronunciation-tmp", stored)
        self.assertNotIn(base64.b64encode(wav_bytes()[:32]).decode("ascii"), stored)

    # ── fail closed ─────────────────────────────────────────────────────

    def test_no_recogniser_is_practice_only_and_writes_nothing(self) -> None:
        self.fake.fail = "stt_dependency_missing"
        response = self.attempt(key="key-pron-unavailable")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["recorded"])
        self.assertIsNone(result["attempt_id"])
        self.assertEqual(result["reason"], "stt_dependency_missing")
        self.assertEqual(result["assessment"]["verdict"], "unavailable")
        self.assertIsNone(result["assessment"]["transcript"])
        self.assertIsNone(result["assessment"]["word_accuracy"])
        self.assertEqual(result["assessment"]["words"], [])
        self.assertEqual(result["assessment"]["evidence_class"], "model_assessed")
        self.assertEqual(self.rows_of("pronunciation_attempts"), [])

        replay = self.attempt(key="key-pron-unavailable")
        self.assertEqual(replay["result"], result)
        self.assertEqual(self.fake.calls, 1, "a same-key replay must not recognise again")

    def test_an_empty_transcript_is_not_a_score(self) -> None:
        self.fake.text = "   "
        response = self.attempt(key="key-pron-empty")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "empty")
        self.assertFalse(result["recorded"])
        self.assertIsNone(result["attempt_id"])
        self.assertEqual(result["reason"], "empty_transcript")
        self.assertEqual(result["assessment"]["verdict"], "unavailable")
        self.assertIsNone(result["assessment"]["word_accuracy"])
        self.assertEqual(self.rows_of("pronunciation_attempts"), [])

    def test_a_wrong_phrase_is_needs_practice_not_a_pass(self) -> None:
        self.fake.text = "good evening everyone"
        self.fake.words = [{"word": "good", "probability": 0.9}]
        response = self.attempt(key="key-pron-wrong")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "assessed")
        self.assertEqual(result["assessment"]["verdict"], "needs_practice")
        self.assertLess(result["assessment"]["word_accuracy"], 1.0)
        self.assertEqual(result["assessment"]["evidence_class"], "model_assessed")
        self.assertEqual(len(self.rows_of("pronunciation_attempts")), 1)

    def test_a_provider_failure_is_unavailable_never_a_partial_evidence_row(self) -> None:
        self.fake.fail = "transcription_failed"
        response = self.attempt(key="key-pron-failure")
        result = response["result"]
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["recorded"])
        self.assertEqual(result["reason"], "transcription_failed")
        self.assertEqual(self.rows_of("pronunciation_attempts"), [])

    # ── bounds ──────────────────────────────────────────────────────────

    def test_oversized_audio_is_refused_before_any_recogniser_call(self) -> None:
        audio = data_url(b"RIFF" + b"\x00" * (pronunciation.MAX_AUDIO_BYTES + 1))
        response = self.attempt(audio=audio, key="key-pron-large")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(response["error"]["details"]["reason"], "audio_too_large")
        self.assertEqual(self.fake.calls, 0)
        self.assertEqual(self.rows_of("pronunciation_attempts"), [])

    def test_unsupported_mime_is_refused_before_any_recogniser_call(self) -> None:
        response = self.attempt(audio=data_url(wav_bytes(), "audio/flac"), key="key-pron-mime")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["details"]["reason"], "unsupported_mime")
        self.assertEqual(self.fake.calls, 0)

    def test_declared_mime_must_match_the_bytes(self) -> None:
        response = self.attempt(audio=data_url(wav_bytes(), "audio/ogg"), key="key-pron-spoof")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["details"]["reason"], "mime_mismatch")

    def test_empty_audio_is_refused(self) -> None:
        response = self.attempt(audio="data:audio/wav;base64,", key="key-pron-empty-audio")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["details"]["reason"], "empty_audio")
        self.assertEqual(self.fake.calls, 0)

    # ── idempotency and staleness ───────────────────────────────────────

    def test_same_key_replays_and_same_nonce_is_the_same_attempt(self) -> None:
        audio = data_url(wav_bytes())
        first = self.attempt(audio=audio, key="key-pron-replay", nonce="nonce-replay")
        second = self.attempt(audio=audio, key="key-pron-replay", nonce="nonce-replay")
        self.assertEqual(first["result"], second["result"])
        self.assertEqual(self.fake.calls, 1)
        third = self.attempt(audio=data_url(wav_bytes(0.5)), key="key-pron-other", nonce="nonce-replay")
        self.assertEqual(third["result"]["attempt_id"], first["result"]["attempt_id"])
        self.assertEqual(len(self.rows_of("pronunciation_attempts")), 1)
        self.assertEqual(self.fake.calls, 1, "a duplicate nonce is caught before recognition")

    def test_a_reused_key_with_a_different_payload_is_a_conflict(self) -> None:
        self.attempt(key="key-pron-conflict", nonce="nonce-conflict-1")
        response = self.attempt(
            target="good evening",
            key="key-pron-conflict",
            nonce="nonce-conflict-2",
            audio=data_url(wav_bytes(0.4)),
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(len(self.rows_of("pronunciation_attempts")), 1)

    def test_a_stale_revision_writes_nothing_and_never_calls_the_recogniser(self) -> None:
        response = self.attempt(revision=self.lesson["revision"] + 9, key="key-pron-stale")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "STALE_REVISION")
        self.assertEqual(response["error"]["current_revision"], self.lesson["revision"])
        self.assertEqual(self.fake.calls, 0)
        self.assertEqual(self.rows_of("pronunciation_attempts"), [])

    # ── dispute ─────────────────────────────────────────────────────────

    def test_a_dispute_is_appended_and_never_rewrites_the_verdict(self) -> None:
        result = self.attempt(key="key-pron-dispute")["result"]
        response = self.dispatch(
            "pronunciation.dispute",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "attempt_id": result["attempt_id"],
                "note": "I said the phrase but the recogniser heard something else.",
            },
            idempotency_key="key-dispute-1",
        )
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["result"]["state"], "open")
        row = self.rows_of("pronunciation_attempts")[0]
        disputes = json.loads(row["disputes_json"])
        self.assertEqual(len(disputes), 1)
        self.assertEqual(disputes[0]["state"], "open")
        self.assertEqual(row["verdict"], result["assessment"]["verdict"])
        self.assertEqual(row["evidence_class"], "model_assessed")
        # A dispute is a note on this attempt; it does not rewrite it and does not move the course.
        self.assertEqual(self.scalar("SELECT revision FROM enrollments WHERE id = ?",
                                     (self.lesson["enrollment_id"],)), self.lesson["revision"])

    def test_a_dispute_for_another_enrollments_attempt_is_not_found(self) -> None:
        result = self.attempt(key="key-pron-dispute-missing")["result"]
        response = self.dispatch(
            "pronunciation.dispute",
            {
                "enrollment_id": "enr_does_not_exist",
                "attempt_id": result["attempt_id"],
                "note": "wrong scope",
            },
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "NOT_FOUND")

    # ── pack exclusion ──────────────────────────────────────────────────

    def test_enrollment_delete_previews_and_removes_pronunciation_attempts(self) -> None:
        self.attempt(key="key-pron-delete")
        preview = self.ok(
            "enrollment.delete",
            {"enrollment_id": self.lesson["enrollment_id"], "dry_run": True},
            expected_revision=self.lesson["revision"],
            idempotency_key="key-delete-preview",
        )["result"]
        self.assertEqual(preview["data_scope"]["counts"]["pronunciation_attempts"], 1)
        self.assertIn("pronunciation attempt", preview["data_scope"]["summary"])
        self.ok(
            "enrollment.delete",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "dry_run": False,
                "data_scope_hash": preview["data_scope"]["scope_hash"],
            },
            expected_revision=self.lesson["revision"],
            idempotency_key="key-delete-run",
        )
        self.assertEqual(self.rows_of("pronunciation_attempts"), [])

    def test_pronunciation_data_cannot_ride_a_pack_export(self) -> None:
        result = self.attempt(key="key-pron-pack")["result"]
        assessment = result["assessment"]
        # The export allowlist has no pronunciation field, and the generic private-field audit
        # names the assessment's transcript/model/provider as private when someone tries to smuggle
        # one into a manifest.
        self.assertNotIn("pronunciation_attempts", packs.export_allowlist())
        found = packs.contains_private_fields({"assessment": assessment})
        self.assertTrue(found, "transcript/model/provider must be recognised as private")
        root = Path(__file__).resolve().parent.parent
        from coursebook import archive

        manifest, files = archive.read_directory(root / "bundled" / "packs" / "parent-measurement-practice")
        exported, _ = packs.build_export(manifest, files)
        text = packs.canonical_json_bytes(exported).decode("utf-8")
        self.assertNotIn("good morning", text)
        self.assertNotIn("coursebook_local_whisper", text)


class WhisperCallContractTest(unittest.TestCase):
    """Pin the live-proven faster-whisper keyword so it cannot drift back to ``prompt``."""

    def test_transcribe_passes_initial_prompt_and_never_prompt(self) -> None:
        received: dict = {}

        class _Word:
            def __init__(self, word: str, probability: float) -> None:
                self.word = word
                self.probability = probability

        class _Segment:
            text = "こんにちは。"
            words = [_Word("こんにちは", 0.8)]

        class _Info:
            language = "ja"

        class _Model:
            def __init__(self, *args, **kwargs):  # noqa: ANN002,ANN003 - mirrors WhisperModel
                pass

            def transcribe(self, audio, *, language=None, initial_prompt=None, **kwargs):  # noqa: ANN001
                if "prompt" in kwargs:  # faster-whisper 1.2.1 does not accept this name
                    raise TypeError("unexpected keyword argument 'prompt'")
                received.update(language=language, initial_prompt=initial_prompt, samples=len(audio))
                return iter([_Segment()]), _Info()

        class _Whisper:
            WhisperModel = _Model

        adapter = stt.LocalWhisperAdapter(model_name="regression", cache_dir=Path(tempfile.mkdtemp()))
        with mock.patch.object(stt, "_import_whisper", return_value=_Whisper), \
                mock.patch.object(adapter, "_decode", return_value=b"\x00\x00" * 16_000):
            result = adapter.transcribe(Path("/tmp/fake.webm"), language="ja-JP", prompt="こんにちは")

        self.assertEqual(received["language"], "ja")
        self.assertEqual(received["initial_prompt"], "こんにちは")
        self.assertEqual(result.text, "こんにちは。")
        self.assertEqual(result.provider, "coursebook_local_whisper")
        self.assertEqual(result.words[0]["word"], "こんにちは")


if __name__ == "__main__":
    unittest.main()
