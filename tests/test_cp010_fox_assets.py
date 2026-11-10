"""CP-010: the fox asset set, its provenance rows and its contact sheets are what the card claims.

These tests read the bytes this card ships. They do not judge whether the fox is charming — that is
the owner's approval and the reviewer's vision pass. They prove that every shipped plate is a keyed
RGBA cutout at the sizes the plan promises, carries no lettering tesseract can read, carries no pure
black contour, and has a provenance row whose hashes are the file's actual hashes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "art" / "fox"
AUDIT = ROOT / "audit" / "cp010-fox"
BIBLE = ROOT / "docs" / "concept-parity" / "ART-BIBLE.md"
PROVENANCE_DOC = ROOT / "docs" / "concept-parity" / "ART-PROVENANCE.md"
CONTACT = ROOT / "docs" / "concept-parity" / "art" / "fox-contact-sheet.png"
MODEL_CONTACT = ROOT / "docs" / "concept-parity" / "art" / "fox-model-sheet-contact.png"

POSES = ["wave", "point", "clock", "read", "cheer", "think", "sleep"]
SIZES = [512, 256, 128, 64]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def masters():
    yield "fox-model-sheet.png", ART / "fox-model-sheet.png"
    for pose in POSES:
        yield f"fox-{pose}.png", ART / f"fox-{pose}.png"


class ShippedAssets(unittest.TestCase):
    def test_every_master_exists_and_is_a_square_rgba_cutout(self):
        from PIL import Image

        for name, path in masters():
            with self.subTest(name=name):
                self.assertTrue(path.exists(), f"{name} missing")
                with Image.open(path) as im:
                    self.assertEqual(im.mode, "RGBA")
                    self.assertEqual(im.width, im.height, f"{name} is not padded square")
                    alpha = im.getchannel("A")
                    bbox = alpha.getbbox()
                    self.assertIsNotNone(bbox, f"{name} has no opaque pixels")
                    # A cutout must actually be cut out: the padded corner is transparent.
                    self.assertEqual(alpha.getpixel((0, 0)), 0, f"{name} corner is not transparent")

    def test_every_pose_ships_all_four_export_sizes(self):
        from PIL import Image

        for pose in POSES:
            for size in SIZES:
                path = ART / f"fox-{pose}-{size}.png"
                with self.subTest(pose=pose, size=size):
                    self.assertTrue(path.exists(), f"{path.name} missing")
                    with Image.open(path) as im:
                        self.assertEqual(im.height, size)

    def test_no_pure_black_contour(self):
        audit = json.loads((AUDIT / "art-audit.json").read_text())
        for row in audit["poses"]:
            with self.subTest(plate=row["file"]):
                self.assertLess(
                    row["pure_black_share"], 0.001,
                    f"{row['file']} is {row['pure_black_share']:.3%} pure black; the contour must "
                    "stay warm brown (#3a2318 class), never black",
                )

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract is not installed")
    def test_no_plate_carries_readable_lettering(self):
        for name, path in masters():
            with self.subTest(plate=name):
                out = subprocess.run(
                    ["tesseract", str(path), "-"], capture_output=True, text=True, check=False,
                )
                self.assertEqual(out.returncode, 0, out.stderr)
                text = out.stdout.replace("\f", "").strip()
                self.assertEqual(text, "", f"{name} OCR returned {text!r}; art must be textless")


class Provenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((AUDIT / "provenance.json").read_text())["rows"]
        cls.prompts = {p["id"]: p for p in json.loads(
            (AUDIT / "prompts.json").read_text())["prompts"]}

    def test_one_row_per_shipped_plate(self):
        expected = {name for name, _ in masters()}
        got = {Path(r["asset"]).name for r in self.rows}
        self.assertEqual(got, expected)

    def test_row_hashes_are_the_files_actual_hashes(self):
        for row in self.rows:
            with self.subTest(plate=row["plate_id"]):
                self.assertEqual(sha256(ROOT / row["asset"]), row["asset_sha256"])
                self.assertGreater(row["bytes"], 50_000)

    def test_prompt_hash_is_the_hash_of_the_recorded_prompt(self):
        for row in self.rows:
            with self.subTest(plate=row["plate_id"]):
                prompt = self.prompts[row["prompt_id"]]
                self.assertEqual(
                    hashlib.sha256(prompt["text"].encode()).hexdigest(), row["prompt_hash"],
                )

    def test_every_pose_cites_the_model_sheet_as_its_reference(self):
        sheet_url = self.prompts["M1"]["media_url"]
        for row in self.rows:
            if row["plate_id"] == "fox-model-sheet":
                # The shipped sheet is round 2, which was itself produced from round 1.
                self.assertEqual(len(row["reference_image_urls"]), 1)
                self.assertNotEqual(row["reference_image_urls"][0], sheet_url)
                continue
            with self.subTest(plate=row["plate_id"]):
                self.assertEqual(row["reference_image_urls"], [sheet_url],
                                 "a pose must be generated from the approved model sheet")

    def test_rows_do_not_invent_a_model_id(self):
        for row in self.rows:
            with self.subTest(plate=row["plate_id"]):
                # The honest value is either a real model id or the explicit gap marker.
                self.assertTrue(row["model"])
                if "not reported" not in row["model"]:
                    self.assertRegex(row["model"], r"[a-z0-9][\w.\-]{2,}")
                self.assertIn("fal.media", row["media_url"])
                self.assertTrue(row["provider"])

    def test_text_check_is_recorded_and_passed(self):
        for row in self.rows:
            with self.subTest(plate=row["plate_id"]):
                self.assertIn("no text", row["text_check"])


class Documents(unittest.TestCase):
    def test_art_bible_states_the_binding_rules(self):
        text = BIBLE.read_text()
        lowered = text.lower()
        for needle in [
            "45 %", "#3a2318", "never black", "cream bib", "cream tail tip",
            "to the elbow", "dark ear backs", "upper left", "negatives", "reference_image_urls",
            "gouache",
        ]:
            with self.subTest(needle=needle):
                self.assertIn(needle.lower(), lowered)

    def test_provenance_document_names_every_plate(self):
        text = PROVENANCE_DOC.read_text()
        for row in json.loads((AUDIT / "provenance.json").read_text())["rows"]:
            with self.subTest(plate=row["plate_id"]):
                self.assertIn(row["plate_id"], text)
                self.assertIn(row["asset_sha256"][:16], text)

    def test_contact_sheets_exist_and_are_readable(self):
        from PIL import Image

        for path, min_width in ((CONTACT, 1200), (MODEL_CONTACT, 800)):
            with self.subTest(path=path.name):
                self.assertTrue(path.exists(), f"{path.name} missing")
                with Image.open(path) as im:
                    self.assertGreaterEqual(im.width, min_width)
                    self.assertGreaterEqual(im.height, 800)


if __name__ == "__main__":
    unittest.main()
