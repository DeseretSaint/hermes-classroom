"""Import/export/reimport roundtrip: teaching content survives, private data cannot be carried."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from coursebook import archive, packs

ROOT = Path(__file__).resolve().parent.parent
PARENT = ROOT / "bundled" / "packs" / "parent-measurement-practice"
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"

#: A course record with everything a pack must never carry. It is passed to the test as a
#: separate object, exactly as the coursebook kernel would hold it beside the teaching content.
PRIVATE_RECORD = {
    "transcript": [{"role": "user", "text": "I think the answer is 300 ml"}],
    "attempts": [{"attempt_id": "att-1", "evidence_class": "cold"}],
    "notebook_entries": [{"note": "I always forget to count the marks"}],
    "provider": {"model": "some-model", "api_key": "sk-not-a-real-key"},
    "local_path": "/home/someone/coursebook/data.db",
    "reflections": ["The learner was tired today."],
}


class RoundtripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.manifest, self.files = archive.read_directory(PARENT)

    def export_and_reimport(self, manifest: dict, files: dict[str, bytes]):
        exported, exported_files = packs.build_export(manifest, files)
        path = self.base / f"{exported['pack_id']}-{exported['pack_version']}.zip"
        archive.write_archive(path, exported, exported_files)
        staging = archive.StagingArea(self.base / "staging")
        staged = staging.stage(staging.grant_local_file(path))
        library = archive.PackLibrary(self.base / "library")
        record = library.adopt(staged)
        adopted_manifest, adopted_files = library.read(exported["pack_id"], exported["pack_version"])
        return exported, exported_files, record, adopted_manifest, adopted_files

    def test_roundtrip_preserves_teaching_content_and_hash(self) -> None:
        exported, exported_files, record, adopted_manifest, adopted_files = self.export_and_reimport(
            self.manifest, self.files
        )
        self.assertEqual(exported["content_hash"], self.manifest["content_hash"])
        self.assertEqual(adopted_manifest, exported)
        self.assertEqual(adopted_files, self.files)
        self.assertEqual(record["manifest_hash"], self.manifest["content_hash"])
        # The teaching content itself is byte-identical through export, archive and reimport.
        for relative, data in self.files.items():
            with self.subTest(file=relative):
                self.assertEqual(adopted_files[relative], data)

    def test_private_learning_data_is_absent_from_the_export(self) -> None:
        exported, _, _, _, _ = self.export_and_reimport(self.manifest, self.files)
        self.assertEqual(packs.contains_private_fields(exported), [])
        text = packs.canonical_json_bytes(exported).decode("utf-8")
        for secret in ("I think the answer is", "sk-not-a-real-key", "/home/someone", "att-1", "tired today"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, text)
        for forbidden in packs.PRIVATE_FIELDS:
            self.assertNotIn(forbidden, exported)

    def test_export_document_uses_only_allowlisted_fields(self) -> None:
        exported, _ = packs.build_export(self.manifest, self.files)
        self.assertLessEqual(set(exported), set(packs.export_allowlist()))

    def test_export_refuses_bytes_outside_the_manifest(self) -> None:
        leaked = dict(self.files)
        leaked["content/transcript.jsonl"] = b'{"text": "private"}\n'
        with self.assertRaises(packs.PackRejected) as caught:
            packs.build_export(self.manifest, leaked)
        self.assertIn("undeclared", str(caught.exception))

    def test_export_refuses_a_field_outside_the_contract(self) -> None:
        tampered = copy.deepcopy(self.manifest)
        tampered["attempts"] = PRIVATE_RECORD["attempts"]
        with self.assertRaises(packs.PackRejected):
            packs.build_export(tampered, self.files)

    def test_reexporting_a_fork_keeps_attribution_and_changes_identity(self) -> None:
        exported, exported_files = packs.build_export(
            self.manifest,
            self.files,
            pack_id="parent-measurement-practice-remix",
            pack_version="1.0.1",
        )
        self.assertEqual(exported["derived_from"], {"pack_id": self.manifest["pack_id"], "pack_version": self.manifest["pack_version"]})
        self.assertNotEqual(exported["content_hash"], self.manifest["content_hash"])
        self.assertEqual(exported["attribution"], self.manifest["attribution"])
        self.assertEqual(set(exported_files), set(self.files))
        packs.validate_manifest(exported)
        packs.validate_minima(exported)

    def test_reimporting_the_same_pack_is_idempotent(self) -> None:
        _, _, record, _, _ = self.export_and_reimport(self.manifest, self.files)
        self.assertFalse(record["duplicate"])
        path = self.base / f"{self.manifest['pack_id']}-{self.manifest['pack_version']}.zip"
        staging = archive.StagingArea(self.base / "staging")
        second = staging.stage(staging.grant_local_file(path))
        library = archive.PackLibrary(self.base / "library")
        again = library.adopt(second)
        self.assertTrue(again["duplicate"])
        self.assertEqual(len(library.list()), 1)

    def test_same_version_with_different_content_is_refused(self) -> None:
        self.export_and_reimport(self.manifest, self.files)
        changed = dict(self.files)
        changed["content/answer-guide.md"] += b"\nA second printing note, no answer changed.\n"
        changed_manifest = copy.deepcopy(self.manifest)
        entry = next(item for item in changed_manifest["files"] if item["path"] == "content/answer-guide.md")
        entry["sha256"] = packs.file_sha256(changed["content/answer-guide.md"])
        entry["bytes"] = len(changed["content/answer-guide.md"])
        changed_manifest = packs.with_content_hash(changed_manifest)
        altered, altered_files = packs.build_export(changed_manifest, changed)
        self.assertNotEqual(altered["content_hash"], self.manifest["content_hash"])
        path = self.base / "altered.zip"
        archive.write_archive(path, altered, altered_files)
        staging = archive.StagingArea(self.base / "staging")
        staged = staging.stage(staging.grant_local_file(path))
        library = archive.PackLibrary(self.base / "library")
        with self.assertRaises(packs.PackRejected) as caught:
            library.adopt(staged)
        self.assertIn("immutable", str(caught.exception))
        # The working version is untouched.
        still, _ = library.read(self.manifest["pack_id"], self.manifest["pack_version"])
        self.assertEqual(still["content_hash"], self.manifest["content_hash"])

    def test_japanese_pack_roundtrip_keeps_visual_and_sources(self) -> None:
        manifest, files = archive.read_directory(JAPANESE)
        exported, exported_files, _, adopted_manifest, adopted_files = self.export_and_reimport(manifest, files)
        self.assertEqual(exported["content_hash"], manifest["content_hash"])
        self.assertEqual([source["source_id"] for source in adopted_manifest["sources"]], [source["source_id"] for source in manifest["sources"]])
        visual = "content/relationship-map.png"
        self.assertEqual(adopted_files[visual], files[visual])
        self.assertTrue(adopted_files[visual].startswith(b"\x89PNG\r\n\x1a\n"))

    def test_imported_japanese_pack_exposes_the_narration_audio_and_its_text_equivalent(self) -> None:
        """The one audio asset survives export/reimport with its MIME, rights and text equivalent.

        This is the probe H-72 owes the demo: the bundled pack really carries playable MP3 bytes, the
        imported manifest still declares them as ``role: narration``/``audio/mpeg``, the per-artifact
        licence still covers the file, and the text equivalent still carries the Japanese line, its
        romaji and its English meaning. It proves the bytes exist and are declared; it does not prove
        a listening check, a pronunciation score or a native-speaker review, none of which the pack
        implements.
        """
        manifest, files = archive.read_directory(JAPANESE)
        _, _, _, adopted_manifest, adopted_files = self.export_and_reimport(manifest, files)
        narration = next(entry for entry in adopted_manifest["files"] if entry["role"] == "narration")
        path = narration["path"]
        self.assertEqual(narration["mime"], "audio/mpeg")
        self.assertEqual(narration["bytes"], len(adopted_files[path]))
        self.assertEqual(narration["sha256"], packs.file_sha256(adopted_files[path]))
        self.assertEqual(adopted_files[path], files[path])

        # Real MPEG audio, not a silent or placeholder stub: frames parse and the clip has duration.
        seconds, frames = mp3_duration_seconds(adopted_files[path])
        self.assertGreaterEqual(frames, 20)
        self.assertGreater(seconds, 1.5)
        self.assertLess(seconds, 6.0)

        # Accessibility and rights travel with the asset through the roundtrip.
        text = narration["text_equivalent"]
        self.assertIn("好きです", text)  # the Japanese line
        self.assertIn("suki desu", text)  # its romaji
        self.assertIn("I like you", text)  # its English meaning
        self.assertIn("not a native-speaker", text.lower())
        licensed = {item["path"]: item for item in adopted_manifest["license"]["per_artifact"]}
        self.assertIn(path, licensed)
        self.assertEqual(licensed[path]["license_id"], "Apache-2.0")
        self.assertIn("Kokoro-82M", licensed[path]["attribution"])
        self.assertIn("no human speaker", licensed[path]["attribution"].lower())
        self.assertIn(path, adopted_files)
        self.assertTrue(adopted_files[path].startswith(b"ID3") or adopted_files[path][0] == 0xFF)


#: MPEG Layer III tables, enough to time the pack's clip without an audio library. The demo asset is
#: 24 kHz mono MPEG-2 Layer III; MPEG-1 is accepted too so a future re-encode cannot silently pass a
#: stub. ``0`` marks a reserved/free entry, which is treated as "not a frame header".
_MP3_BITRATES_V1_L3 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0)
_MP3_BITRATES_V2_L3 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0)
_MP3_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


def mp3_duration_seconds(data: bytes) -> tuple[float, int]:
    """Return ``(duration_seconds, frame_count)`` read from MPEG Layer III frame headers."""
    offset = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        offset = 10 + size
    seconds = 0.0
    frames = 0
    while offset + 4 <= len(data):
        first, second, third = data[offset], data[offset + 1], data[offset + 2]
        if first != 0xFF or (second & 0xE0) != 0xE0:
            offset += 1
            continue
        version = (second >> 3) & 0x03  # 3 MPEG-1, 2 MPEG-2, 0 MPEG-2.5, 1 reserved
        layer = (second >> 1) & 0x03  # 1 Layer III
        bitrate_index = (third >> 4) & 0x0F
        rate_index = (third >> 2) & 0x03
        padding = (third >> 1) & 0x01
        if version == 1 or layer != 1 or rate_index == 3 or bitrate_index in (0, 15):
            offset += 1
            continue
        sample_rate = _MP3_RATES[version][rate_index]
        table = _MP3_BITRATES_V1_L3 if version == 3 else _MP3_BITRATES_V2_L3
        bitrate_kbps = table[bitrate_index]
        if version == 3:
            frame_bytes = (144000 * bitrate_kbps) // sample_rate + padding
            samples = 1152
        else:
            frame_bytes = (72000 * bitrate_kbps) // sample_rate + padding
            samples = 576
        if frame_bytes <= 4 or offset + frame_bytes > len(data):
            break
        seconds += samples / sample_rate
        frames += 1
        offset += frame_bytes
    return seconds, frames


if __name__ == "__main__":
    unittest.main()
