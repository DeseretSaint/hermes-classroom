"""Hostile archive tests: traversal, links, bombs, active content, bad MIME, staging residue."""

from __future__ import annotations

import io
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from coursebook import archive, packs

ROOT = Path(__file__).resolve().parent.parent
PARENT = ROOT / "bundled" / "packs" / "parent-measurement-practice"
ROOT_NAME = "hostile-pack-1.0.0"
BENIGN = b"# A short lesson\n\nRead the task and answer on the line.\n"


def benign_manifest(files: dict[str, bytes], metadata: dict[str, dict]) -> dict:
    objectives = [
        {
            "objective_id": "obj-one",
            "ordinal": 1,
            "title": "One lesson",
            "evidence_target": "comprehension",
            "evidence_criteria": ["Answers the task"],
            "estimated_minutes": 5,
            "sections": [{"section_id": "sec-one", "title": "Lesson", "path": "content/lesson.md"}],
            "checks": [
                {
                    "check_id": "chk-one-1",
                    "version": 1,
                    "evidence_target": "comprehension",
                    "stimulus": "What is the answer?",
                    "rubric": ["Criterion one", "Criterion two", "Criterion three"],
                    "reference_answer": "the hidden answer 42",
                    "accepted_alternatives": ["42"],
                    "audit_state": "unreviewed",
                }
            ],
        }
    ]
    artifacts = [
        {"path": path, "license_id": "CC0-1.0", "attribution": "test"}
        for path, meta in metadata.items()
        if meta["mime"].startswith(("image/", "audio/", "application/pdf"))
    ]
    return packs.build_manifest(
        pack_id="hostile-pack",
        pack_version="1.0.0",
        title="Hostile pack fixture",
        recipe="casual",
        minimum_coursebook_version="0.1.0",
        license={"id": "unspecified", "redistribution": "local_only", "per_artifact": artifacts},
        attribution="test fixture",
        objectives=objectives,
        files=files,
        file_metadata=metadata,
    )


def raw_zip(path: Path, entries: list, *, compression=zipfile.ZIP_DEFLATED, modes=None):
    """Write a zip with exact member names, including entries a normal writer would refuse."""
    with zipfile.ZipFile(path, "w", compression=compression) as handle:
        for name, data in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = compression
            info.file_size = len(data or b"")
            if modes and name in modes:
                info.external_attr = modes[name] << 16
            if data is None:
                info.external_attr = (0o040755 << 16)
                handle.writestr(info, b"")
            else:
                handle.writestr(info, data)


def pack_zip(path: Path, manifest: dict, files: dict[str, bytes], *, mutate=None) -> None:
    entries: list = [(f"{ROOT_NAME}/pack.json", packs.canonical_json_bytes(manifest) + b"\n")]
    entries += [(f"{ROOT_NAME}/{relative}", data) for relative, data in files.items()]
    if mutate is not None:
        entries = mutate(entries)
    raw_zip(path, entries)


class ArchiveCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def reject(self, path: Path, fragment: str = "") -> None:
        destination = self.base / "extract"
        with self.assertRaises(packs.PackRejected) as caught:
            archive.extract_archive(path, destination)
        if fragment:
            self.assertIn(fragment, str(caught.exception))
        self.assertFalse(destination.exists(), "a rejection must remove its partial extraction")
        self.assertEqual([item for item in self.base.iterdir() if item.name == "extract"], [])


class MemberNameTests(ArchiveCase):
    def test_traversal_is_rejected(self) -> None:
        for name in ("../escape.md", "root/../../escape.md", "root/./inside.md"):
            with self.subTest(name=name):
                path = self.base / "bad.zip"
                raw_zip(path, [(f"{ROOT_NAME}/{name}", BENIGN)])
                self.reject(path, "segment")

    def test_absolute_path_is_rejected(self) -> None:
        path = self.base / "bad.zip"
        raw_zip(path, [("/etc/passwd", BENIGN)])
        self.reject(path, "absolute")

    def test_backslash_and_control_characters_are_rejected(self) -> None:
        for name in ("root\\content.md", "root/a\x01b.md"):
            with self.subTest(name=name):
                path = self.base / "bad.zip"
                raw_zip(path, [(name, BENIGN)])
                self.reject(path)

    def test_hidden_and_url_like_names_are_rejected(self) -> None:
        for name in ("root/.hidden.md", "file://root/pack.json"):
            with self.subTest(name=name):
                path = self.base / "bad.zip"
                raw_zip(path, [(name, BENIGN)])
                self.reject(path)

    def test_two_roots_are_rejected(self) -> None:
        path = self.base / "bad.zip"
        raw_zip(path, [(f"{ROOT_NAME}/pack.json", b"{}"), ("other/content.md", BENIGN)])
        self.reject(path, "one root")

    def test_case_collision_is_rejected(self) -> None:
        path = self.base / "bad.zip"
        raw_zip(path, [(f"{ROOT_NAME}/content/A.md", BENIGN), (f"{ROOT_NAME}/content/a.md", BENIGN)])
        self.reject(path, "collide by case")


class LinkAndBombTests(ArchiveCase):
    def test_symlink_and_device_entries_are_rejected(self) -> None:
        for kind in (stat.S_IFLNK | 0o777, stat.S_IFCHR | 0o644):
            with self.subTest(kind=kind):
                path = self.base / "bad.zip"
                raw_zip(
                    path,
                    [(f"{ROOT_NAME}/content/link.md", b"/etc/passwd")],
                    modes={f"{ROOT_NAME}/content/link.md": kind},
                )
                self.reject(path, "link or device")

    def test_high_compression_ratio_is_rejected(self) -> None:
        path = self.base / "bomb.zip"
        raw_zip(path, [(f"{ROOT_NAME}/content/zeros.md", b"0" * (1024 * 1024))])
        self.reject(path, "expansion ratio")

    def test_oversized_single_file_is_rejected(self) -> None:
        path = self.base / "big.zip"
        payload = os.urandom(33 * 1024 * 1024)
        raw_zip(path, [(f"{ROOT_NAME}/content/big.bin", payload)], compression=zipfile.ZIP_STORED)
        self.reject(path, "per-file limit" if False else "over the")

    def test_too_many_files_is_rejected(self) -> None:
        path = self.base / "many.zip"
        entries = [(f"{ROOT_NAME}/content/f{index}.md", b"x") for index in range(2100)]
        raw_zip(path, entries, compression=zipfile.ZIP_STORED)
        self.reject(path, "more than")

    def test_unsupported_compression_is_rejected(self) -> None:
        path = self.base / "bz.zip"
        raw_zip(path, [(f"{ROOT_NAME}/content/a.md", BENIGN)], compression=zipfile.ZIP_BZIP2)
        self.reject(path, "unsupported compression")

    def test_encrypted_entry_is_rejected(self) -> None:
        path = self.base / "enc.zip"
        raw_zip(path, [(f"{ROOT_NAME}/content/a.md", BENIGN)])
        # zipfile clears the encryption bit when writing; set it in both headers the way a
        # hostile producer would, so the reader must notice it in the central directory.
        payload = bytearray(path.read_bytes())
        for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            index = payload.find(signature)
            self.assertGreaterEqual(index, 0)
            flags = int.from_bytes(payload[index + offset : index + offset + 2], "little") | 0x1
            payload[index + offset : index + offset + 2] = flags.to_bytes(2, "little")
        path.write_bytes(bytes(payload))
        self.reject(path, "encrypted")


class ContentValidationTests(ArchiveCase):
    def write(self, files: dict[str, bytes], metadata: dict[str, dict]) -> Path:
        manifest = benign_manifest(files, metadata)
        path = self.base / "pack.zip"
        pack_zip(path, manifest, files)
        return path

    def test_undeclared_and_missing_files_are_rejected(self) -> None:
        files = {"content/lesson.md": BENIGN}
        metadata = {"content/lesson.md": {"mime": "text/markdown", "role": "section"}}
        manifest = benign_manifest(files, metadata)

        extra = self.base / "extra.zip"
        pack_zip(extra, manifest, files, mutate=lambda entries: entries + [(f"{ROOT_NAME}/content/extra.md", BENIGN)])
        self.reject(extra, "undeclared")

        missing = self.base / "missing.zip"
        pack_zip(missing, manifest, files, mutate=lambda entries: entries[:1])
        self.reject(missing, "missing")

    def test_hash_mismatch_is_rejected(self) -> None:
        files = {"content/lesson.md": BENIGN}
        metadata = {"content/lesson.md": {"mime": "text/markdown", "role": "section"}}
        manifest = benign_manifest(files, metadata)
        path = self.base / "pack.zip"
        tampered = BENIGN[:-1] + b"!"
        self.assertEqual(len(tampered), len(BENIGN))
        pack_zip(path, manifest, {"content/lesson.md": tampered})
        self.reject(path, "sha256")

    def test_declared_mime_must_match_bytes(self) -> None:
        files = {
            "content/lesson.md": BENIGN,
            "content/photo.png": b"this is definitely not a png",
        }
        metadata = {
            "content/lesson.md": {"mime": "text/markdown", "role": "section"},
            "content/photo.png": {"mime": "image/png", "role": "visual", "text_equivalent": "A photo"},
        }
        path = self.write(files, metadata)
        self.reject(path, "declared MIME")

    def test_html_svg_and_script_are_rejected(self) -> None:
        cases = {
            "content/page.md": (b"# hi\n<script>alert(1)</script>\n", "text/markdown", "active markup"),
            "content/svg.png": (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "image/png", "declared MIME"),
            "content/html.md": (b"<iframe src='https://example.com'></iframe>", "text/markdown", "active markup"),
        }
        for relative, (payload, mime, fragment) in cases.items():
            with self.subTest(file=relative):
                files = {"content/lesson.md": BENIGN, relative: payload}
                metadata = {
                    "content/lesson.md": {"mime": "text/markdown", "role": "section"},
                    relative: {
                        "mime": mime,
                        "role": "visual" if mime.startswith("image/") else "source_note",
                        "text_equivalent": "Equivalent text",
                    },
                }
                path = self.write(files, metadata)
                self.reject(path, fragment)

    def test_remote_image_in_markdown_is_rejected(self) -> None:
        files = {"content/lesson.md": BENIGN + b"\n![diagram](https://example.com/x.png)\n"}
        metadata = {"content/lesson.md": {"mime": "text/markdown", "role": "section"}}
        path = self.write(files, metadata)
        self.reject(path, "remote image")

    def test_pdf_active_content_is_rejected(self) -> None:
        pdf = b"%PDF-1.7\n1 0 obj\n<< /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>\nendobj\n"
        files = {"content/lesson.md": BENIGN, "content/guide.pdf": pdf}
        metadata = {
            "content/lesson.md": {"mime": "text/markdown", "role": "section"},
            "content/guide.pdf": {"mime": "application/pdf", "role": "source_note", "text_equivalent": "Guide text"},
        }
        path = self.write(files, metadata)
        self.reject(path, "active/embedded")

    def test_binary_disguised_as_text_is_rejected(self) -> None:
        files = {"content/lesson.md": BENIGN + b"\x00\x01\x02"}
        metadata = {"content/lesson.md": {"mime": "text/markdown", "role": "section"}}
        path = self.write(files, metadata)
        self.reject(path, "NUL")

    def test_answer_key_on_a_learner_page_is_rejected(self) -> None:
        files = {
            "content/lesson.md": BENIGN + b"\nThe answer is the hidden answer 42.\n",
        }
        metadata = {"content/lesson.md": {"mime": "text/markdown", "role": "section"}}
        path = self.write(files, metadata)
        self.reject(path, "reference answer")


class GrantAndStagingTests(ArchiveCase):
    def test_stage_requires_a_registered_grant(self) -> None:
        staging = archive.StagingArea(self.base / "staging")
        with self.assertRaises(packs.PackRejected) as caught:
            staging.stage("stg-" + "0" * 32)
        self.assertIn("local file grant", str(caught.exception))
        self.assertFalse((self.base / "staging").exists())

    def test_grant_refuses_urls_relative_paths_and_symlinks(self) -> None:
        staging = archive.StagingArea(self.base / "staging")
        with self.assertRaises(packs.PackRejected):
            staging.grant_local_file("file:///tmp/pack.zip")
        with self.assertRaises(packs.PackRejected):
            staging.grant_local_file("pack.zip")
        real = self.base / "real.zip"
        real.write_bytes(b"")
        link = self.base / "link.zip"
        link.symlink_to(real)
        with self.assertRaises(packs.PackRejected):
            staging.grant_local_file(link)

    def test_failed_stage_leaves_no_staging_residue(self) -> None:
        path = self.base / "bad.zip"
        raw_zip(path, [(f"{ROOT_NAME}/content/../escape.md", BENIGN)])
        staging = archive.StagingArea(self.base / "staging")
        staged_id = staging.grant_local_file(path)
        with self.assertRaises(packs.PackRejected):
            staging.stage(staged_id)
        root = self.base / "staging"
        self.assertTrue(root.is_dir())
        self.assertEqual(list(root.iterdir()), [])

    def test_valid_pack_stages_previews_and_adopts(self) -> None:
        manifest, files = archive.read_directory(PARENT)
        path = self.base / "parent.zip"
        archive.write_archive(path, manifest, files)
        staging = archive.StagingArea(self.base / "staging")
        staged_id = staging.grant_local_file(path)
        staged = staging.stage(staged_id)
        self.assertEqual(staged.content_hash, manifest["content_hash"])
        self.assertEqual(staged.integrity["file_count"], len(manifest["files"]))
        self.assertTrue(staged.integrity["hashes_match"])

        created = packs.preview(staged.manifest, integrity=staged.integrity)
        self.assertEqual(set(created), {"manifest", "integrity", "trust"})
        self.assertIn("integrity_verified", created["trust"]["labels"])

        library = archive.PackLibrary(self.base / "library")
        record = library.adopt(staged)
        self.assertFalse(record["duplicate"])
        self.assertEqual(record["manifest_hash"], manifest["content_hash"])
        again = library.adopt(archive.StagedPack(
            staged_id="stg-duplicate",
            directory=self.base / "unused",
            manifest=manifest,
            integrity=staged.integrity,
        ))
        self.assertTrue(again["duplicate"])
        self.assertEqual(len(library.list()), 1)
        adopted_manifest, adopted_files = library.read(manifest["pack_id"], manifest["pack_version"])
        self.assertEqual(adopted_manifest["content_hash"], manifest["content_hash"])
        self.assertEqual(adopted_files, files)

    def test_reconcile_removes_partial_and_expired_staging(self) -> None:
        root = self.base / "staging"
        partial = root / "stg-dead.partial"
        partial.mkdir(parents=True)
        (partial / "junk").write_text("x", encoding="utf-8")
        old = root / "stg-old"
        old.mkdir()
        (old / "staged.json").write_text('{"created_at": 0}', encoding="utf-8")
        staging = archive.StagingArea(root, ttl_seconds=60)
        removed = staging.reconcile()
        self.assertIn("stg-dead.partial", removed)
        self.assertIn("stg-old", removed)
        self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
