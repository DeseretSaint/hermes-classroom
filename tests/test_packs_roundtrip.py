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


if __name__ == "__main__":
    unittest.main()
