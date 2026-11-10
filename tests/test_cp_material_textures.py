"""CP-011 — material tiles: size, seam, alpha ceiling, legibility and evidence.

These tests read the committed PNG bytes, not the manifest's claims about them. A tile that drifts,
grows past the budget, stops wrapping, or raises its alpha far enough to soften 16 px body text
fails here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TILE_DIR = ROOT / "assets" / "art" / "material"
MANIFEST = TILE_DIR / "manifest.json"
PROOF_DIR = ROOT / "docs" / "concept-parity" / "art" / "material"
MAX_BYTES = 60_000
TEXT_MIN_CONTRAST = 4.5
ROLES = ("paper-grain", "card-stock-fibre", "parchment-vignette", "wood-plank")
MODES = ("light", "dark")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


material = _load("build_cb_material", ROOT / "scripts" / "build_cb_material.py")
sheet = _load("cp_material_sheet", ROOT / "scripts" / "cp_material_sheet.py")


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def rows() -> list[dict]:
    return manifest()["tiles"]


class ManifestTests(unittest.TestCase):
    def test_the_card_ships_four_families_in_both_modes(self) -> None:
        self.assertTrue(MANIFEST.exists(), "run scripts/build_cb_material.py build")
        document = manifest()
        self.assertEqual(document["schema"], "cb.material.v1")
        self.assertEqual(document["card"], "CP-011")
        self.assertEqual(document["tile_count"], 8)
        self.assertEqual(
            sorted((row["id"], row["mode"]) for row in rows()),
            sorted((role, mode) for role in ROLES for mode in MODES),
        )

    def test_every_row_is_a_host_drawn_asset_with_a_licence(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                self.assertEqual(row["source"]["provider"], "host")
                self.assertEqual(row["source"]["model"], "none")
                self.assertIsNone(row["source"]["prompt_hash"])
                self.assertEqual(row["licence"], "CC0-1.0")
        ids = [row["provenance_id"] for row in rows()]
        self.assertEqual(len(ids), len(set(ids)), "provenance ids must be unique")

    def test_only_wood_is_baked_colour_and_carries_no_alpha(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"]):
                if row["id"] == "wood-plank":
                    self.assertEqual(row["format"], "RGB")
                    self.assertEqual(row["alpha_ceiling"], 0)
                    self.assertEqual(row["tiling"], "repeat")
                else:
                    self.assertEqual(row["format"], "RGBA")

    def test_the_vignette_is_declared_one_shot(self) -> None:
        for row in rows():
            if row["id"] == "parchment-vignette":
                self.assertEqual(row["tiling"], "one-shot")
                self.assertIn("applied once", row["application"])


class TileFileTests(unittest.TestCase):
    def test_every_tile_matches_its_manifest_row(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                path = ROOT / row["path"]
                self.assertTrue(path.exists(), row["path"])
                blob = path.read_bytes()
                self.assertEqual(hashlib.sha256(blob).hexdigest(), row["sha256"])
                self.assertEqual(len(blob), row["bytes"])

    def test_every_tile_is_under_the_60_kb_budget(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                self.assertLessEqual(row["bytes"], MAX_BYTES, f"{row['path']} is {row['bytes']} B")

    def test_every_tile_is_a_square_within_the_size_window(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                image = material.read_png(ROOT / row["path"])
                self.assertEqual(image["width"], image["height"])
                self.assertGreaterEqual(image["width"], material.MIN_PX)
                self.assertLessEqual(image["width"], material.MAX_PX)
                self.assertEqual(image["width"], row["width"])
                self.assertEqual(image["channels"], 4 if row["format"] == "RGBA" else 3)


class SeamTests(unittest.TestCase):
    """The wrap is measured on the committed bytes, not trusted from the manifest."""

    def test_no_tile_has_a_step_at_the_wrap(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                seams = material.seam_delta(material.read_png(ROOT / row["path"]))
                self.assertLessEqual(
                    seams["column_ratio"], 1.25,
                    f"{row['id']}/{row['mode']} column wrap is {seams['column_ratio']}x an interior step",
                )
                self.assertLessEqual(
                    seams["row_ratio"], 1.25,
                    f"{row['id']}/{row['mode']} row wrap is {seams['row_ratio']}x an interior step",
                )

    def test_a_broken_tile_would_fail_this_test(self) -> None:
        """A deliberately feathered edge must be caught, or the check above proves nothing."""
        tile = material.read_png(ROOT / "assets/art/material/paper-grain-light.png")
        width, height, channels = tile["width"], tile["height"], tile["channels"]
        pixels = bytearray(tile["pixels"])
        for y in range(height):  # force the last column to a value no interior pixel holds
            for k in range(channels):
                index = (y * width + width - 1) * channels + k
                pixels[index] = 255
        broken = {"width": width, "height": height, "channels": channels, "pixels": bytes(pixels)}
        self.assertGreater(material.seam_delta(broken)["column_ratio"], 1.25)


class AlphaCeilingTests(unittest.TestCase):
    def test_no_overlay_pixel_exceeds_its_declared_alpha(self) -> None:
        for row in rows():
            if row["format"] != "RGBA":
                continue
            with self.subTest(tile=row["id"], mode=row["mode"]):
                image = material.read_png(ROOT / row["path"])
                alpha = image["pixels"][3::4]
                self.assertLessEqual(max(alpha), row["alpha_ceiling"], f"{row['path']} alpha ceiling")

    def test_body_text_keeps_4_5_to_1_at_the_worst_pixel(self) -> None:
        for row in rows():
            if row["id"] == "wood-plank":
                continue  # no text ever sits on wood
            with self.subTest(tile=row["id"], mode=row["mode"]):
                field = material.worst_field(row["mode"], row["id"], row["alpha_ceiling"])
                ink = material.hex_rgb(material.PALETTE[row["mode"]]["ink"])
                self.assertGreaterEqual(
                    material.contrast(ink, field), TEXT_MIN_CONTRAST,
                    f"{row['id']}/{row['mode']} worst field {field}",
                )

    def test_the_declared_contrast_matches_a_fresh_computation(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                self.assertGreaterEqual(row["ink_worst_contrast"], TEXT_MIN_CONTRAST)
                field = material.worst_field(row["mode"], row["id"], row["alpha_ceiling"])
                ink = material.hex_rgb(material.PALETTE[row["mode"]]["ink"])
                self.assertAlmostEqual(
                    material.contrast(ink, field), row["ink_worst_contrast"], places=2
                )


class DeterminismTests(unittest.TestCase):
    def test_repainting_reproduces_the_committed_bytes(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                size = row["width"]
                pixels, _ceiling = material.PAINTERS[row["id"]](size, row["mode"])
                if row["format"] == "RGBA":
                    expected = material.read_png(ROOT / row["path"])["pixels"]
                    self.assertEqual(pixels, expected, f"{row['path']} is not reproducible")
                else:
                    expected = material.read_png(ROOT / row["path"])["pixels"]
                    self.assertEqual(pixels, expected, f"{row['path']} is not reproducible")


class ProofTests(unittest.TestCase):
    def test_every_tile_has_a_3x3_composite_proof(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                proof = PROOF_DIR / f"proof-3x3-{row['id']}-{row['mode']}.png"
                self.assertTrue(proof.exists(), proof.name)
                image = material.read_png(proof)
                self.assertEqual(image["width"], row["width"] * 3)
                self.assertEqual(image["height"], row["height"] * 3)

    def test_the_vignette_also_gets_its_actual_single_application(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                once = PROOF_DIR / f"proof-once-parchment-vignette-{mode}.png"
                self.assertTrue(once.exists(), once.name)
                image = material.read_png(once)
                self.assertEqual(image["width"], 512 * 3)
                self.assertEqual(image["height"], 512 * 3)

    def test_the_composites_are_byte_reproducible(self) -> None:
        """Evidence that cannot be re-derived from the tiles is not evidence."""
        if shutil.which("magick") is None:
            self.skipTest("ImageMagick is not installed")
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with contextlib.redirect_stdout(io.StringIO()):
                material.prove(Path(first))
                material.prove(Path(second))
            for produced in sorted(Path(first).glob("proof-*.png")):
                twin = Path(second) / produced.name
                self.assertTrue(twin.exists(), twin.name)
                self.assertEqual(
                    hashlib.sha256(produced.read_bytes()).hexdigest(),
                    hashlib.sha256(twin.read_bytes()).hexdigest(),
                    f"{produced.name} is not reproducible",
                )
            # and the committed proof must equal a fresh one
            for produced in sorted(PROOF_DIR.glob("proof-*.png")):
                twin = Path(first) / produced.name
                self.assertEqual(
                    hashlib.sha256(produced.read_bytes()).hexdigest(),
                    hashlib.sha256(twin.read_bytes()).hexdigest(),
                    f"{produced.name} drifted from the committed bytes",
                )


class TextureSheetTests(unittest.TestCase):
    def test_both_sheets_and_stamps_exist_and_match(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                image_path = PROOF_DIR / f"texture-sheet-{mode}.png"
                stamp_path = PROOF_DIR / f"texture-sheet-{mode}.stamp.json"
                self.assertTrue(image_path.exists(), image_path.name)
                self.assertTrue(stamp_path.exists(), stamp_path.name)
                record = json.loads(stamp_path.read_text(encoding="utf-8"))
                self.assertEqual(record["card"], "CP-011")
                self.assertEqual(record["mode"], mode)
                self.assertEqual(
                    hashlib.sha256(image_path.read_bytes()).hexdigest(), record["sheet_sha256"]
                )
                self.assertEqual(record["body_px"], 16)
                self.assertEqual(len(record["tiles"]), 4)
                self.assertTrue(record["wood_has_no_text"])

    def test_the_sheet_is_honest_about_its_capture_rig(self) -> None:
        record = json.loads((PROOF_DIR / "texture-sheet-light.stamp.json").read_text(encoding="utf-8"))
        self.assertIn("proof sheet", record["capture_rig"])
        self.assertIn("cp-capture.mjs", record["capture_rig"])
        self.assertIn("not on this branch", record["capture_rig"])

    def test_the_sheet_would_notice_a_changed_tile(self) -> None:
        record = json.loads((PROOF_DIR / "texture-sheet-light.stamp.json").read_text(encoding="utf-8"))
        declared = {row["id"]: row["sha256"] for row in rows() if row["mode"] == "light"}
        for tile in record["tiles"]:
            self.assertEqual(tile["sha256"], declared[tile["id"]], f"{tile['id']} drifted from the sheet")


class WoodRuleTests(unittest.TestCase):
    def test_the_sheet_puts_no_text_inside_the_wood_surfaces(self) -> None:
        markup = sheet.html("light")
        section = markup.split("<h2>wood plank", 1)[1].split("</section>", 1)[0]
        body = section.split("</h2>", 1)[1]
        self.assertIn('class="plank"', body)
        self.assertIn('class="tray"', body)
        # the two surfaces must be empty elements: any inner text would be a label on wood
        for needle in ('class="plank"', 'class="tray"'):
            start = body.index(needle)
            close = body.index(">", start)
            self.assertEqual(body[close + 1:close + 7], "</div>", f"{needle} carries inner content")
        self.assertNotIn("<p", body)
        self.assertNotIn("<span", body)

    def test_no_tile_contains_a_letter(self) -> None:
        for row in rows():
            with self.subTest(tile=row["id"], mode=row["mode"]):
                check = row.get("text_check")
                self.assertIsNotNone(check, "every tile records a text check")
                assert check is not None
                self.assertIn(check["result"], ("none", "skipped"), check)
                if check["result"] == "skipped":
                    self.skipTest("tesseract is not installed on this machine")
                self.assertEqual(check["characters"], 0)

    @unittest.skipUnless(
        shutil.which("tesseract") and shutil.which("magick"),
        "needs tesseract and ImageMagick to prove the check can see a word",
    )
    def test_the_text_check_can_actually_see_a_word(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stamped = Path(temporary) / "with-word.png"
            subprocess.run(
                ["magick", str(ROOT / "assets/art/material/paper-grain-light.png"),
                 "-pointsize", "40", "-fill", "black", "-annotate", "+20+120", "PACK", str(stamped)],
                check=True,
            )
            check = material.ocr_check(stamped)
            self.assertTrue(check["result"].startswith("hit:"), check)


if __name__ == "__main__":
    unittest.main()
