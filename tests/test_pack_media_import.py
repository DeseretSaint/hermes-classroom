"""H-137: pack-authored ``media[]`` becomes a playable artifact and a media segment.

The frozen decision is ``docs/PACK-MEDIA-PLAYBACK.md`` (H-73): a ``cb.pack`` v2 pack declares which
``narration``/``visual`` file belongs to which section, import materializes one ``artifacts`` row
and one ``lesson_segments(kind='media')`` row per link, ``lesson.page`` projects the media child,
and the existing ``/media/{artifact_id}`` route serves the bytes with its licence and attribution.

These tests run against a real SQLite profile built by the real migrations, a real zip archive,
and the real dispatcher. No provider is called and no byte is fabricated: the fixture is the
bundled Japanese L0 pack, whose narration MP3 already ships real bytes (H-72).
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from coursebook import __version__, archive, media, pack_flow, packs
from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"

NARRATION = "content/narration-polite-confession.mp3"
VISUAL = "content/relationship-map.png"
SECTION = "content/section-02-choosing.md"
CAPTION = (
    '好きです。付き合ってください。 (suki desu. tsukiatte kudasai.) — "I like you. Please go out with me."'
)


class PackMediaCase(KernelCase):
    """A migrated profile plus a v2 fixture built from the real bundled pack."""

    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-packmedia-"))
        self.addCleanup(shutil.rmtree, self.work, True)

    # ── fixtures ───────────────────────────────────────────────────────────

    def v2_pack(self, media_entries: list[dict] | None = None) -> tuple[dict, dict[str, bytes]]:
        """The bundled Japanese pack re-stamped as ``cb.pack`` v2 with one narration link."""
        manifest, files = archive.read_directory(JAPANESE)
        manifest = copy.deepcopy(manifest)
        manifest["contract_version"] = 2
        manifest["minimum_coursebook_version"] = __version__
        manifest["media"] = (
            [{"path": NARRATION, "section_path": SECTION, "caption": CAPTION}]
            if media_entries is None
            else media_entries
        )
        manifest.pop("content_hash", None)
        manifest = packs.with_content_hash(manifest)
        return manifest, files

    def grant(self, manifest: dict, files: dict[str, bytes], name: str = "pack.zip") -> str:
        destination = self.work / name
        archive.write_archive(destination, manifest, files)
        return pack_flow.grant_local_file(destination)

    def grant_raw(self, manifest: dict, files: dict[str, bytes], name: str = "raw.zip") -> str:
        """Write an archive the writer's own validation would refuse.

        ``archive.write_archive`` validates the manifest before writing, which is right for a
        legitimate export and useless for proving a *refusal*: these fixtures must reach
        ``pack.preview``/``pack.import`` so the refusal under test is the one being measured.
        """
        destination = self.work / name
        root = f"{manifest['pack_id']}-{manifest['pack_version']}/"
        with zipfile.ZipFile(destination, "w") as bundle:
            bundle.writestr(root + "pack.json", json.dumps(manifest))
            for path, data in files.items():
                bundle.writestr(root + path, data)
        return pack_flow.grant_local_file(destination)

    def import_pack(self, staged_id: str, mode: str = "fresh") -> dict:
        return self.ok("pack.import", {"staged_id": staged_id, "mode": mode})["result"]

    # ── reads ──────────────────────────────────────────────────────────────

    def counts(self) -> dict[str, int]:
        return {
            table: int(self.scalar(f"SELECT COUNT(*) FROM {table}"))
            for table in ("packs", "courses", "plans", "objectives", "enrollments",
                          "lesson_runs", "lesson_segments", "artifacts")
        }

    def media_segments(self) -> list:
        return self.rows(
            "SELECT * FROM lesson_segments WHERE kind = 'media' ORDER BY ordinal"
        )

    def page_for(self, enrollment_id: str, course_id: str) -> dict:
        objective_id = self.scalar(
            "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
            " WHERE p.course_id = ? AND o.ordinal = 2",
            (course_id,),
        )
        return self.ok(
            "lesson.page", {"enrollment_id": enrollment_id, "objective_id": objective_id}
        )["result"]


class DeclaredNarrationImportTest(PackMediaCase):
    def test_one_artifact_and_one_media_segment_are_materialized(self) -> None:
        manifest, files = self.v2_pack()
        before = self.counts()
        result = self.import_pack(self.grant(manifest, files))
        after = self.counts()

        self.assertEqual(after["artifacts"], before["artifacts"] + 1)
        self.assertEqual(after["packs"], before["packs"] + 1)

        rows = self.rows("SELECT * FROM artifacts")
        self.assertEqual(len(rows), 1)
        artifact = rows[0]
        self.assertEqual(artifact["kind"], "audio")
        self.assertEqual(artifact["mime"], "audio/mpeg")
        self.assertEqual(artifact["course_id"], result["course_id"])

        provenance = json.loads(artifact["provenance_json"])
        self.assertEqual(provenance["generator"], "coursebook.pack_import")
        self.assertIsNone(provenance["model"])
        self.assertEqual(provenance["license_id"], "Apache-2.0")
        self.assertIn("Kokoro-82M", provenance["attribution"])
        self.assertIn("好きです", provenance["text_equivalent"])
        self.assertIn("suki desu", provenance["text_equivalent"])
        self.assertEqual(provenance["pack_id"], manifest["pack_id"])
        self.assertEqual(provenance["pack_version"], manifest["pack_version"])
        self.assertEqual(provenance["pack_content_hash"], manifest["content_hash"])
        self.assertEqual(provenance["pack_file"], NARRATION)
        self.assertEqual(provenance["pack_file_sha256"], manifest_file_hash(manifest, NARRATION))
        self.assertIn("pack author's transcript", provenance["label"])
        self.assertIn("not pronunciation assessment", provenance["label"])

        segments = self.media_segments()
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], CAPTION)
        self.assertEqual(segments[0]["artifact_id"], artifact["id"])

        # Placement: the media row sits inside section 2's teaching block, after its text and
        # before the objective's check prompt (H-73 §8.2).
        run = self.rows(
            "SELECT * FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal",
            (segments[0]["lesson_run_id"],),
        )
        kinds = [row["kind"] for row in run]
        media_index = kinds.index("media")
        self.assertEqual(kinds[-1], "check_prompt")
        self.assertGreater(media_index, 0)
        self.assertEqual(kinds[media_index - 1], "teaching")

    def test_lesson_page_returns_the_media_child_and_the_route_serves_rights(self) -> None:
        manifest, files = self.v2_pack()
        result = self.import_pack(self.grant(manifest, files))
        page = self.page_for(result["enrollment_id"], result["course_id"])

        blocks = page["document"]["blocks"]
        media_children = [child for block in blocks for child in block["media"]]
        self.assertEqual(len(media_children), 1)
        child = media_children[0]
        self.assertEqual(child["kind"], "audio")
        self.assertEqual(child["artifact_id"], self.scalar("SELECT id FROM artifacts"))
        self.assertEqual(child["purpose"], CAPTION)
        self.assertEqual(child["text_equivalent"], CAPTION)
        self.assertFalse(child["degraded"])

        # The page itself lists the artifact before the client asks the route for it.
        self.assertEqual([item["artifact_id"] for item in page["artifacts"]], [child["artifact_id"]])

        served = media.preview_artifact(child["artifact_id"])
        self.assertTrue(served["ok"], served)
        self.assertEqual(served["mime"], "audio/mpeg")
        self.assertEqual(served["bytes"], len(files[NARRATION]))
        self.assertTrue(served["data_url"].startswith("data:audio/mpeg;base64,"))
        self.assertEqual(served["license_id"], "Apache-2.0")
        self.assertIn("Kokoro-82M", served["attribution"])
        self.assertIn("好きです", served["text_equivalent"])
        self.assertIn("pack author's transcript", served["label"])

    def test_repeated_import_reuses_the_artifact_across_courses(self) -> None:
        manifest, files = self.v2_pack()
        first = self.import_pack(self.grant(manifest, files, "first.zip"))
        second = self.import_pack(self.grant(manifest, files, "second.zip"))

        self.assertNotEqual(first["course_id"], second["course_id"])
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM artifacts")), 1)
        self.assertEqual(int(self.scalar("SELECT ref_count FROM artifacts")), 2)
        # Two media segments, both pointing at the one reused artifact row.
        self.assertEqual(len({row["artifact_id"] for row in self.media_segments()}), 1)

        # The reuse case that fails on a naive ``WHERE course_id = ?`` read (H-73 §2.4.1): the
        # second course's page must still project the player.
        for result in (first, second):
            page = self.page_for(result["enrollment_id"], result["course_id"])
            children = [child for block in page["document"]["blocks"] for child in block["media"]]
            self.assertEqual(len(children), 1, f"page lost its media child for {result['course_id']}")
            self.assertEqual(children[0]["kind"], "audio")

    def test_export_roundtrip_preserves_media_link_text_equivalent_and_licence(self) -> None:
        manifest, files = self.v2_pack()
        exported, exported_files = packs.build_export(manifest, files)
        self.assertEqual(exported["content_hash"], manifest["content_hash"])
        self.assertEqual(exported["contract_version"], 2)
        self.assertEqual(exported["media"], manifest["media"])
        narration = next(entry for entry in exported["files"] if entry["path"] == NARRATION)
        self.assertIn("好きです", narration["text_equivalent"])
        licensed = {item["path"]: item for item in exported["license"]["per_artifact"]}
        self.assertEqual(licensed[NARRATION]["license_id"], "Apache-2.0")
        self.assertEqual(exported_files[NARRATION], files[NARRATION])


class UnchangedAndRefusedTest(PackMediaCase):
    def v1_pack(self) -> tuple[dict, dict[str, bytes]]:
        """The bundled pack's bytes re-stamped as a document that predates ``media[]``.

        H-186 made the shipped pack v2, so the "no links, no player" behaviour needs a v1
        fixture built from the same content rather than the shipped manifest.
        """
        manifest, files = archive.read_directory(JAPANESE)
        manifest = copy.deepcopy(manifest)
        manifest["contract_version"] = 1
        manifest["pack_version"] = "1.0.0"
        manifest.pop("media", None)
        manifest.pop("content_hash", None)
        return packs.with_content_hash(manifest), files

    def test_a_pack_without_media_is_unchanged(self) -> None:
        """A v1 pack stays stored-only: no artifact, no media segment, no player."""
        before = self.counts()
        manifest, files = self.v1_pack()
        staged_id = self.grant(manifest, files, name="v1.zip")
        preview = self.ok("pack.preview", {"staged_id": staged_id})["result"]
        result = self.import_pack(self.grant(manifest, files, name="v1-import.zip"))

        self.assertEqual(self.counts()["artifacts"], before["artifacts"])
        self.assertEqual(self.media_segments(), [])
        page = self.page_for(result["enrollment_id"], result["course_id"])
        self.assertEqual([child for block in page["document"]["blocks"] for child in block["media"]], [])
        self.assertEqual(page["artifacts"], [])
        self.assertNotIn("media", preview["manifest"])

    def test_v1_document_may_not_carry_media(self) -> None:
        manifest, files = self.v2_pack()
        manifest["contract_version"] = 1
        manifest = packs.with_content_hash(manifest)
        with self.assertRaises(packs.PackRejected):
            packs.validate_manifest(manifest)

        before = self.counts()
        error = self.err("pack.preview", {"staged_id": self.grant_raw(manifest, files, "bad-v1.zip")})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertEqual(self.counts(), before)

    def test_dangling_media_link_is_refused_before_any_write(self) -> None:
        manifest, files = self.v2_pack(
            [{"path": "content/does-not-exist.mp3", "section_path": SECTION, "caption": "Missing."}]
        )
        before = self.counts()
        error = self.err("pack.preview", {"staged_id": self.grant_raw(manifest, files)})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertIn("not a declared file", error["message"])
        self.assertEqual(self.counts(), before)

    def test_media_link_to_an_undeclared_section_is_refused(self) -> None:
        manifest, files = self.v2_pack(
            [{"path": NARRATION, "section_path": "content/section-99-nowhere.md", "caption": CAPTION}]
        )
        before = self.counts()
        error = self.err("pack.import", {"staged_id": self.grant_raw(manifest, files), "mode": "fresh"})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertIn("not a section of any objective", error["message"])
        self.assertEqual(self.counts(), before)

    def test_caption_over_the_media_child_cap_is_refused(self) -> None:
        manifest, files = self.v2_pack(
            [{"path": NARRATION, "section_path": SECTION, "caption": "x" * 201}]
        )
        before = self.counts()
        error = self.err("pack.preview", {"staged_id": self.grant_raw(manifest, files)})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertEqual(self.counts(), before)

    def test_a_text_file_cannot_be_linked_as_narration(self) -> None:
        section = "content/section-01-two-ways.md"
        manifest, files = self.v2_pack(
            [{"path": section, "section_path": SECTION, "caption": "A section is not audio."}]
        )
        before = self.counts()
        error = self.err("pack.preview", {"staged_id": self.grant_raw(manifest, files)})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertIn("may be linked to a lesson page", error["message"])
        self.assertEqual(self.counts(), before)

    def test_more_than_eight_links_on_one_section_is_refused(self) -> None:
        links = [
            {"path": VISUAL, "section_path": SECTION, "caption": f"Image {index}"}
            for index in range(9)
        ]
        manifest, files = self.v2_pack(links)
        before = self.counts()
        error = self.err("pack.preview", {"staged_id": self.grant_raw(manifest, files)})
        self.assertEqual(error["code"], "PACK_REJECTED")
        self.assertIn("more than 8 media files", error["message"])
        self.assertEqual(self.counts(), before)


def manifest_file_hash(manifest: dict, path: str) -> str:
    for entry in manifest["files"]:
        if entry["path"] == path:
            return str(entry["sha256"])
    raise AssertionError(f"{path} is not declared")


class SegmentBudgetTest(unittest.TestCase):
    """H-73 §2.4.3: linked media counts against the page's 500-segment budget."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "content").mkdir()
        # 499 pieces of the 8,000-character segment cap: 499 teaching + 1 check = exactly 500.
        (self.root / "content" / "big.md").write_text("a" * 3_992_000, encoding="utf-8")

    def manifest(self, media: list[dict] | None = None) -> dict:
        return {
            "objectives": [
                {
                    "objective_id": "obj_12345678",
                    "ordinal": 1,
                    "sections": [{"path": "content/big.md"}],
                    "checks": [{"check_id": "chk_12345678", "stimulus": "Answer."}],
                }
            ],
            "media": media or [],
        }

    def test_a_page_at_the_budget_without_media_is_allowed(self) -> None:
        from coursebook import segments

        segments.audit_objective_texts(self.manifest(), self.root)

    def test_one_linked_file_over_the_budget_is_refused(self) -> None:
        from coursebook import segments
        from coursebook.archive import PackRejected

        media = [{"path": "content/n.mp3", "section_path": "content/big.md", "caption": "Play."}]
        with self.assertRaises(PackRejected) as caught:
            segments.audit_objective_texts(self.manifest(media), self.root)
        message = str(caught.exception)
        self.assertIn("501 lesson segments", message)
        self.assertIn("1 linked media segment(s)", message)
        self.assertIn("at most 500", message)


if __name__ == "__main__":
    unittest.main()
