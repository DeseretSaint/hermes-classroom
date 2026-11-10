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

    def test_art_bible_states_the_measured_cuff_band(self):
        """§3 must quote the band the art carries, not a number nobody measured."""
        sheet = json.loads((AUDIT / "marking-audit.json").read_text())["sheet"]
        text = BIBLE.read_text()
        arms, feet = sheet["arm_bands"], sheet["foot_bands"]

        def span(values, places: int | None = 1):
            lo, hi = min(values), max(values)
            fmt = (lambda v: f"{v}") if places is None else (lambda v: f"{v:.{places}f}")
            return f"{fmt(lo)}–{fmt(hi)}"

        for expected in (
            span([b["height_px"] for b in arms], None) + " px",
            span([b["height_px"] for b in feet], None) + " px",
            span([b["height_percent_figure"] for b in arms]) + " %",
            span([b["height_percent_figure"] for b in feet]) + " %",
            span([b["top_percent_figure"] for b in arms]) + " %",
            span([b["top_percent_figure"] for b in feet]) + " %",
            f"{sheet['front_view']['height_px']} px",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text,
                              "the bible's cuff band is not the band marking-audit.json measured")

    def test_pose_section_cites_the_head_band_instead_of_restating_a_number(self):
        text = BIBLE.read_text()
        section = text.split("## 4. Pose set", 1)[1].split("## 5.", 1)[0]
        self.assertIn("§3", section)
        self.assertNotIn("45", section,
                         "§4 restates a head proportion; it must cite §3 so one number is the rule")

    def test_contact_sheets_exist_and_are_readable(self):
        from PIL import Image

        for path, min_width in ((CONTACT, 1200), (MODEL_CONTACT, 800)):
            with self.subTest(path=path.name):
                self.assertTrue(path.exists(), f"{path.name} missing")
                with Image.open(path) as im:
                    self.assertGreaterEqual(im.width, min_width)
                    self.assertGreaterEqual(im.height, 800)


class Stance(unittest.TestCase):
    """A pose that reads as a different character is the named defect class of this card.

    Geometry is the check that does not depend on a vision read: a quadruped standing on a ground
    line is wider than it is tall, an upright chibi is taller than it is wide. The round-1 point
    plate measured 669x622 (1.076) — four legs down, horizontal torso — and this guard is what
    would have caught it before it reached a contact sheet.
    """

    STANDING = ["wave", "point", "clock", "cheer", "think"]
    SEATED_OR_UPRIGHT = ["read"]
    LIMIT = 0.90

    def aspect(self, pose):
        from PIL import Image

        with Image.open(ART / f"fox-{pose}.png") as im:
            box = im.convert("RGBA").getchannel("A").getbbox()
        self.assertIsNotNone(box, f"fox-{pose} has no opaque pixels")
        w = box[2] - box[0]
        h = box[3] - box[1]
        return w / h, w, h

    def test_every_standing_pose_is_taller_than_it_is_wide(self):
        for pose in self.STANDING + self.SEATED_OR_UPRIGHT:
            with self.subTest(pose=pose):
                ratio, w, h = self.aspect(pose)
                self.assertLessEqual(
                    ratio, self.LIMIT,
                    f"fox-{pose} silhouette is {w}x{h} (aspect {ratio:.3f}): wider than tall, which "
                    "is a horizontal body on a ground line, not the model sheet's upright biped",
                )

    def test_point_is_asserted_by_name(self):
        ratio, w, h = self.aspect("point")
        self.assertLessEqual(
            ratio, self.LIMIT,
            f"fox-point is {w}x{h} (aspect {ratio:.3f}); ART-BIBLE.md §3 requires a bipedal stance",
        )

    def test_sleep_is_the_only_horizontal_plate_and_that_is_deliberate(self):
        ratio, _, _ = self.aspect("sleep")
        self.assertGreater(ratio, 1.0, "the curled sleep pose should read horizontal")


class Pipeline(unittest.TestCase):
    """The art bible binds CP-011..CP-013, so its cutout numbers must be the numbers that ran."""

    def test_bible_fuzz_is_the_script_default(self):
        import re

        bible = BIBLE.read_text()
        stated = re.findall(r"-fuzz (\d+)%", bible)
        self.assertTrue(stated, "ART-BIBLE.md §8 states no -fuzz value")
        source = (ROOT / "scripts" / "cp010-fox-prep.py").read_text()
        default = re.search(r'else "(\d+)"', source)
        self.assertIsNotNone(default, "cp010-fox-prep.py has no --fuzz default")
        for value in set(stated):
            with self.subTest(stated=value):
                self.assertEqual(
                    value, default.group(1),
                    f"the bible says -fuzz {value}% and the script defaults to {default.group(1)}%; "
                    "a binding document that disagrees with the pipeline regenerates nothing",
                )

    def test_the_shipped_masters_are_what_the_pipeline_produces(self):
        """Re-key every recorded raw with the script's own default and compare pixels."""
        import tempfile

        from PIL import Image

        provenance = json.loads((AUDIT / "provenance.json").read_text())["rows"]
        for row in provenance:
            with self.subTest(plate=row["plate_id"]):
                raw = AUDIT / "raw" / Path(row["raw_asset"]).name
                self.assertTrue(raw.exists(), f"{raw.name} missing; the raw must be kept")
                out = Path(tempfile.mkdtemp(prefix="cp010-rekey-")) / "master.png"
                subprocess.run(
                    ["python3", "scripts/cp010-fox-prep.py", str(raw), str(out), "--master-only"],
                    cwd=ROOT, check=True, capture_output=True,
                )
                with Image.open(out) as made, Image.open(ROOT / row["asset"]) as shipped:
                    self.assertEqual(made.size, shipped.size)
                    self.assertEqual(
                        made.convert("RGBA").tobytes(), shipped.convert("RGBA").tobytes(),
                        f"{row['asset']} is not reproducible from {raw.name} at the script default; "
                        "either the master or the pipeline changed and the other was not updated",
                    )


class VisionRecord(unittest.TestCase):
    """A check without a record is not a check.

    ART-PROVENANCE.md §Known gaps claimed a recorded vision comparison per plate while no such file
    existed. This asserts the record exists, covers every shipped plate, cites the model sheet, and
    agrees with the independently measured silhouette numbers.
    """

    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((AUDIT / "vision.json").read_text())
        cls.rows = {r["plate_id"]: r for r in cls.doc["rows"]}
        cls.shape = json.loads((AUDIT / "shape-audit.json").read_text())["plates"]
        cls.sheet_url = next(
            p for p in json.loads((AUDIT / "prompts.json").read_text())["prompts"]
            if p["id"] == "M1"
        )["media_url"]

    def test_one_row_per_shipped_plate(self):
        self.assertEqual(set(self.rows), {name.removesuffix(".png") for name, _ in masters()})

    def test_every_pose_cites_the_model_sheet(self):
        for plate, row in self.rows.items():
            with self.subTest(plate=plate):
                if plate == "fox-model-sheet":
                    # The sheet is the authority; it was generated from the round-1 sheet.
                    self.assertNotEqual(row["reference_media_url"], self.sheet_url)
                    continue
                self.assertEqual(row["reference_media_url"], self.sheet_url,
                                 f"{plate} does not name the model sheet as its comparison reference")
                self.assertIn("fal.media", row["media_url"])

    def test_no_row_is_a_silent_pass(self):
        for plate, row in self.rows.items():
            with self.subTest(plate=plate):
                self.assertIn(row["verdict"], {"pass", "deviation"})
                self.assertTrue(row["lettering"].startswith("none"),
                                f"{plate} lettering is {row['lettering']!r}")
                for field in ("cream_bib", "cream_tail_tip", "dark_ear_backs", "limb_marking"):
                    self.assertIn(field, row["markings"])
                self.assertTrue(row["stance"] and row["colour_family"] and row["notes"])

    def test_rows_agree_with_the_measured_silhouette(self):
        for plate, row in self.rows.items():
            with self.subTest(plate=plate):
                self.assertEqual(self.shape[plate]["aspect"], row["aspect"],
                                 f"{plate} vision row and shape audit disagree on aspect")

    def test_open_items_name_a_decision_and_its_options(self):
        for item in self.doc["open_items"]:
            with self.subTest(item=item["id"]):
                self.assertTrue(item["owner_decision"])
                self.assertGreaterEqual(len(item["options"]), 2,
                                        "an open item with one option is a decision that was not made")
                self.assertTrue(item["finding"] and item["why_it_matters"])


if __name__ == "__main__":
    unittest.main()
