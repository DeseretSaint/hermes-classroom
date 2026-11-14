"""Item 47: a provider's picture is normalised before it becomes an artifact.

At HEAD ``HostMedia.image`` returned the provider's bytes unchanged: the plate arrived at whatever
dimensions, raster format and metadata block the provider emitted, up to the 8 MiB visual ceiling.
These tests are written against the bytes that ship — never a Desktop window, a rig backend or a
CDP probe (owner directive 2026-11-12).

The acceptance named by the card is
``MediaNormaliseTest::test_a_6000x4000_png_with_exif_arrives_small_and_clean``: it fails at HEAD
(the bytes come back 6000x4000 with the EXIF intact) and passes after the change.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import struct
import tempfile
import unittest
import zlib
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from coursebook import artifacts, db, generation, image_normalise, media

from tests.kernel_support import KernelCase

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
SCHEMA_NOW = "2026-11-14T12:00:00Z"
HASH = "sha256:" + "a" * 64

#: The card's fixture size. Built once for the module: 24 MP is the shape a provider returns.
SOURCE_PIXELS = (6000, 4000)


def _png_with_exif(size: tuple[int, int] = SOURCE_PIXELS) -> bytes:
    """A real PNG of ``size`` carrying the kind of metadata block a provider attaches."""
    image = Image.new("RGB", size, (247, 241, 228))
    exif = Image.Exif()
    exif[271] = "Coursebook Test Camera"  # Make
    exif[272] = "Provider-1"  # Model
    exif[274] = 1  # Orientation
    exif[305] = "coursebook-test 1.0"  # Software
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", exif=exif)
    return buffer.getvalue()


def _png_claiming(width: int, height: int) -> bytes:
    """A small PNG whose IHDR *declares* ``width`` x ``height`` — a decompression bomb.

    The chunk's CRC is recomputed over the forged header so the image plugin actually parses the
    dimensions: the point of the fixture is the pixel ceiling, not a checksum refusal.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (0, 0, 0)).save(buffer, format="PNG")
    data = bytearray(buffer.getvalue())
    start = data.find(b"IHDR")
    data[start + 4 : start + 8] = struct.pack(">I", width)
    data[start + 8 : start + 12] = struct.pack(">I", height)
    crc = zlib.crc32(bytes(data[start : start + 17])) & 0xFFFFFFFF
    data[start + 17 : start + 21] = struct.pack(">I", crc)
    return bytes(data)


class MediaNormaliseTest(KernelCase):
    """The seam, its transform record, and the artifact row that ships from it."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._fixtures = Path(tempfile.mkdtemp(prefix="coursebook-normalise-"))
        cls.big_png = _png_with_exif()
        cls.big_path = cls._fixtures / "provider-6000x4000.png"
        cls.big_path.write_bytes(cls.big_png)
        # 49 MP sits between our 40 MP ceiling and Pillow's own 2x threshold: only an explicit
        # header check refuses it, so the test proves the ceiling is ours and not a side effect.
        cls.between_thresholds = _png_claiming(7000, 7000)
        cls.bomb = _png_claiming(30000, 30000)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._fixtures, ignore_errors=True)
        super().tearDownClass()

    # ── the seam ────────────────────────────────────────────────────────

    def host_for(self, path: Path) -> media.HostMedia:
        """A real ``HostMedia`` over a dispatch that answers like the host's image tool."""

        def dispatch(name: str, arguments: dict) -> dict:
            if name != "image_generate":
                raise AssertionError(f"unexpected host tool {name}")
            return {"success": True, "image": str(path)}

        return media.HostMedia(dispatch)

    def normalise(self, data: bytes, *, aspect_ratio: str | None = "4:3") -> image_normalise.NormalisedImage:
        return image_normalise.normalise_image(
            data,
            mime=artifacts.sniff_mime(data),
            aspect_ratio=aspect_ratio,
            target_width_px=media.MIN_FIGURE_WIDTH_PX,
            max_bytes=artifacts._MAX_BYTES["visual"],
        )

    # ── acceptance ──────────────────────────────────────────────────────

    def test_a_6000x4000_png_with_exif_arrives_small_and_clean(self) -> None:
        # The fixture is proven to carry EXIF, so the assertion below cannot pass vacuously.
        with Image.open(io.BytesIO(self.big_png)) as origin:
            self.assertEqual(origin.size, SOURCE_PIXELS)
            self.assertTrue(dict(origin.getexif()), "the fixture must carry EXIF")

        data, mime = self.host_for(self.big_path).image(
            "An editorial illustration of a workshop bench", aspect_ratio="4:3"
        )

        self.assertEqual(mime, "image/png")
        self.assertLessEqual(len(data), artifacts._MAX_BYTES["visual"])
        with Image.open(io.BytesIO(data)) as shipped:
            width, height = shipped.size
            # The role's ratio (4:3) at the 1024 px width floor: measured, not declared.
            self.assertEqual(width, media.MIN_FIGURE_WIDTH_PX)
            self.assertLessEqual(abs(width / height - 4 / 3), 0.01)
            self.assertEqual(dict(shipped.getexif()), {})
            self.assertFalse({"exif", "xmp", "icc_profile", "comment"} & set(shipped.info))

        # Every pixel is smaller than the source: this is a downscale, not an upscale.
        self.assertLess(width * height, SOURCE_PIXELS[0] * SOURCE_PIXELS[1])
        self.assertLess(len(data), len(self.big_png))

    def test_the_transform_is_reported_for_provenance(self) -> None:
        data, _mime, transform = self.host_for(self.big_path).image_with_transform(
            "An editorial illustration of a workshop bench", aspect_ratio="4:3"
        )
        self.assertEqual(transform["policy"], image_normalise.NORMALISE_POLICY)
        self.assertEqual(transform["source_pixels"], list(SOURCE_PIXELS))
        self.assertEqual(transform["source_bytes"], len(self.big_png))
        self.assertEqual(transform["output_pixels"], list(Image.open(io.BytesIO(data)).size))
        self.assertEqual(transform["output_bytes"], len(data))
        self.assertTrue(transform["exif_present"])
        self.assertTrue(transform["metadata_stripped"])
        self.assertEqual(transform["width_floor_px"], media.MIN_FIGURE_WIDTH_PX)
        self.assertTrue(transform["downscaled"])

    # ── the three refusals ──────────────────────────────────────────────

    def test_a_decompression_bomb_raises_rather_than_allocating(self) -> None:
        with self.assertRaises(image_normalise.ImageNormaliseError) as caught:
            self.normalise(self.bomb)
        self.assertIn("decode ceiling", str(caught.exception))
        self.assertIn(str(image_normalise.MAX_IMAGE_PIXELS), str(caught.exception))

    def test_the_ceiling_is_ours_not_pillows_doubling(self) -> None:
        # 49 MP: under Pillow's 2x threshold (80 MP after our MAX_IMAGE_PIXELS is set), over ours.
        self.assertGreater(7000 * 7000, image_normalise.MAX_IMAGE_PIXELS)
        self.assertLess(7000 * 7000, 2 * image_normalise.MAX_IMAGE_PIXELS)
        with self.assertRaises(image_normalise.ImageNormaliseError) as caught:
            self.normalise(self.between_thresholds)
        self.assertIn("over the", str(caught.exception))

    def test_bytes_over_the_visual_ceiling_are_refused_before_decode(self) -> None:
        over = b"\x89PNG\r\n\x1a\n" + b"x" * (artifacts._MAX_BYTES["visual"] + 1)
        with self.assertRaises(image_normalise.ImageNormaliseError) as caught:
            self.normalise(over)
        self.assertIn("over the", str(caught.exception))

    def test_a_svg_is_not_mistaken_for_a_provider_picture(self) -> None:
        with self.assertRaises(image_normalise.ImageNormaliseError):
            self.normalise(artifacts.make_schematic_svg("Rows", [{"label": "a", "value": "1"}]))

    # ── geometry is the role's, never the provider's ─────────────────────

    def test_a_source_off_ratio_is_cropped_not_stretched(self) -> None:
        wide = io.BytesIO()
        Image.new("RGB", (1600, 900), (10, 20, 30)).save(wide, format="PNG")
        out = self.normalise(wide.getvalue(), aspect_ratio="3:4")
        with Image.open(io.BytesIO(out.data)) as shipped:
            # A landscape source cropped to 3:4 leaves a 675 px-wide plate. It is not stretched
            # back up to the floor: inventing pixels is the one thing a downscale must not do.
            self.assertEqual(shipped.size, (675, 900))
            self.assertLessEqual(abs(shipped.size[0] / shipped.size[1] - 3 / 4), 0.01)
        self.assertEqual(out.transform["crop"], "centre")
        self.assertFalse(out.transform["downscaled"])

    def test_a_small_picture_is_never_upscaled(self) -> None:
        small = io.BytesIO()
        Image.new("RGB", (800, 600), (10, 20, 30)).save(small, format="PNG")
        out = self.normalise(small.getvalue(), aspect_ratio="4:3")
        with Image.open(io.BytesIO(out.data)) as shipped:
            self.assertEqual(shipped.size, (800, 600))
        self.assertFalse(out.transform["downscaled"])
        self.assertEqual(out.transform["crop"], "none")

    def test_an_unreadable_ratio_keeps_the_source_ratio(self) -> None:
        out = self.normalise(_png_with_exif((2000, 1000)), aspect_ratio="landscape")
        with Image.open(io.BytesIO(out.data)) as shipped:
            self.assertEqual(shipped.size, (1024, 512))
        self.assertEqual(out.transform["crop"], "none")

    def test_an_exif_rotated_picture_is_stored_upright(self) -> None:
        upright = io.BytesIO()
        Image.new("RGB", (1200, 900), (200, 100, 50)).save(upright, format="PNG")
        exif = Image.Exif()
        exif[274] = 6  # rotate 90° clockwise on display
        rotated = io.BytesIO()
        with Image.open(io.BytesIO(upright.getvalue())) as image:
            image.save(rotated, format="PNG", exif=exif)
        out = self.normalise(rotated.getvalue(), aspect_ratio="4:3")
        with Image.open(io.BytesIO(out.data)) as shipped:
            # The stored pixels are already upright: portrait source (900x1200) cropped to 4:3.
            self.assertLessEqual(abs(shipped.size[0] / shipped.size[1] - 4 / 3), 0.01)
            self.assertEqual(dict(shipped.getexif()), {})
        self.assertTrue(out.transform["orientation_applied"])

    # ── the artifact row ────────────────────────────────────────────────

    def _prepare_lesson(self) -> None:
        self.course_id, self.plan_id = self.new_course()
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        self.objective_id = self.seed_objective(self.plan_id)
        self.store = artifacts.ArtifactStore()
        self.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
            " document_json, research_json, generation_state, validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, '{}', 'validated', NULL, '{}', ?)",
            ("gen_doc_1", self.plan_id, self.course_id, "fp-1", HASH, json.dumps({"locale": "en"}), SCHEMA_NOW),
        )
        self.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
            " objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, ?, ?, ?, '[]', '[]')",
            ("sec_1", self.plan_id, HASH, "Bench", "See the bench", json.dumps([1])),
        )
        media_json = [
            {
                "kind": "visual",
                "role": "illustration",
                "purpose": "See the workshop bench",
                "spec": "An editorial illustration of a workshop bench with a torque wrench",
                "text_equivalent": "A workshop bench with a torque wrench.",
            }
        ]
        self.lesson_id = "gen_lesson_1"
        self.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
            " media_json, parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, 'validated', '{}', ?, '{}', '[]', NULL, ?, ?)",
            (self.lesson_id, self.plan_id, "sec_1", HASH, json.dumps(media_json), SCHEMA_NOW, SCHEMA_NOW),
        )

    def _generate(self, path: Path) -> media.MediaGenerationSummary:
        with db.read() as connection:
            summary = media.generate_for_lessons(
                connection,
                lesson_ids=[self.lesson_id],
                job_id="job_normalise_1",
                host=self.host_for(path),
                store=self.store,
                now=NOW,
            )
        return summary

    def _stored_items(self) -> list[dict]:
        row = self.rows("SELECT media_json FROM gen_lessons WHERE id = ?", (self.lesson_id,))[0]
        return json.loads(row["media_json"])

    def test_the_stored_artifact_carries_the_transform_and_the_clean_bytes(self) -> None:
        self._prepare_lesson()
        summary = self._generate(self.big_path)
        self.assertEqual(summary.generated, 1)

        item = self._stored_items()[0]
        self.assertTrue(item.get("artifact_id"))
        self.assertEqual(item["mime"], "image/png")

        row = self.rows("SELECT * FROM artifacts WHERE id = ?", (item["artifact_id"],))[0]
        stored = Path(str(row["path"])).read_bytes()
        self.assertEqual(len(stored), int(row["bytes"]))
        with Image.open(io.BytesIO(stored)) as shipped:
            self.assertEqual(shipped.size[0], media.MIN_FIGURE_WIDTH_PX)
            self.assertEqual(dict(shipped.getexif()), {})

        provenance = json.loads(row["provenance_json"])
        record = provenance["normalisation"]
        self.assertEqual(record["policy"], image_normalise.NORMALISE_POLICY)
        self.assertEqual(record["source_pixels"], list(SOURCE_PIXELS))
        self.assertEqual(record["output_pixels"], [media.MIN_FIGURE_WIDTH_PX, 768])
        self.assertTrue(record["exif_present"])
        self.assertTrue(record["metadata_stripped"])
        # The geometry the artifact layer already advertised is now a fact about the bytes.
        self.assertEqual(provenance["min_width_px"], media.MIN_FIGURE_WIDTH_PX)

    def test_the_content_hash_is_derived_from_the_reencoded_bytes(self) -> None:
        """The dedupe key must be re-derived after re-encoding, never carried over from the source.

        ``ArtifactStore.record`` dedupes on ``(content_hash, kind)``. The hash of the provider's
        bytes would address a file the store does not have; the hash of the normalised bytes is the
        only one that identifies this artifact.
        """
        self._prepare_lesson()
        self._generate(self.big_path)
        item = self._stored_items()[0]
        row = self.rows("SELECT * FROM artifacts WHERE id = ?", (item["artifact_id"],))[0]
        stored = Path(str(row["path"])).read_bytes()

        shipped_hash = hashlib.sha256(stored).hexdigest()
        provider_hash = hashlib.sha256(self.big_png).hexdigest()
        self.assertNotEqual(shipped_hash, provider_hash)
        self.assertEqual(row["content_hash"], artifacts.labelled_hash(shipped_hash))
        self.assertEqual(item["content_hash"], artifacts.labelled_hash(shipped_hash))
        # No row is addressed by the provider's byte identity.
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM artifacts WHERE content_hash IN (?, ?)",
                artifacts.hash_forms(provider_hash),
            ),
            0,
        )
        # And the re-derived identity dedupes: the same plate saved again is one row, not two.
        again = self.store.save(
            course_id=self.course_id,
            kind="visual",
            data=stored,
            mime="image/png",
            provenance=json.loads(row["provenance_json"]),
            now=NOW,
        )
        self.assertEqual(again["artifact_id"], item["artifact_id"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 1)

    def test_a_bomb_from_the_provider_degrades_to_text_and_stores_nothing(self) -> None:
        bomb_path = self._fixtures / "bomb.png"
        bomb_path.write_bytes(self.bomb)
        self._prepare_lesson()
        summary = self._generate(bomb_path)

        self.assertEqual(summary.generated, 0)
        self.assertEqual(summary.degraded, 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)
        item = self._stored_items()[0]
        self.assertIsNone(item.get("artifact_id"))
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_DEGRADED)
        # The reason names the failure class, and the text equivalent is still the whole medium.
        self.assertIn("MediaGenerationError", item["reason"])
        self.assertEqual(item["text_equivalent"], "A workshop bench with a torque wrench.")


if __name__ == "__main__":
    unittest.main()
