"""CP-013: the scene plates, the object blanks and the pipeline that ships them are what the card says.

These tests read the bytes this card ships: the three painted scene masters under
``assets/art/scenes``, the seven object blanks under ``assets/art/objects``, the encoded kit under
``assets/objects``, the audit JSON and the provenance rows. They prove the mechanical claims — aspect,
quiet-field contrast, cutout shape, blank rim centres, no pure black, no readable lettering, hashes
that are the files' actual hashes, and a segment that carries no scene plate. They do not judge
whether the art is beautiful; that is the contact sheet and the reviewer's eye.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENES = ROOT / "assets" / "art" / "scenes"
OBJECTS = ROOT / "assets" / "art" / "objects"
SHIPPED = ROOT / "assets" / "objects"
AUDIT = ROOT / "audit" / "cp013-scenes"
BIBLE = ROOT / "docs" / "concept-parity" / "ART-BIBLE.md"
PROVENANCE_DOC = ROOT / "docs" / "concept-parity" / "ART-PROVENANCE-A4A5.md"
GENERATED = ROOT / "desktop" / "cb-assets.generated.js"

SCENE_PLATES = {
    "discover-banner": 4.4,
    "lesson-cafe": 16 / 9,
    "course-map": 16 / 9,
}
OBJECT_PLATES = ("stamp-rim", "medallion-rim", "passport-tray", "ticket", "clock", "tag", "shelf-plank")
RIM_CENTRES = ("stamp-rim", "medallion-rim")
EVENT_NAMES = ("first lesson step", "first check", "first review", "first take-home", "course complete")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_rows():
    return {Path(row["file"]).name: row for row in json.loads((AUDIT / "art-audit.json").read_text())["plates"]}


def provenance():
    return json.loads((AUDIT / "provenance.json").read_text())


def prompts():
    return {p["id"]: p for p in json.loads((AUDIT / "prompts.json").read_text())["prompts"]}


class ScenePlates(unittest.TestCase):
    def test_the_three_scene_plates_exist_at_the_named_aspects(self):
        from PIL import Image

        for plate, aspect in SCENE_PLATES.items():
            with self.subTest(plate=plate):
                path = SCENES / f"{plate}.png"
                self.assertTrue(path.is_file(), f"{plate} missing")
                with Image.open(path) as im:
                    self.assertEqual(im.mode, "RGB", f"{plate} should ship opaque")
                    self.assertAlmostEqual(im.width / im.height, aspect, delta=0.02,
                                           msg=f"{plate} is {im.width}x{im.height}")

    def test_the_banner_reserves_a_quiet_field_for_dom_type(self):
        row = audit_rows()["discover-banner.png"]
        field = row["quiet_field"]
        self.assertGreaterEqual(field["share_of_plate"], 0.35, "SPEC-V3 D5 reserves the left 40 %")
        self.assertLessEqual(field["detail_energy"], 8.0,
                             "the banner's reserved field carries detail the type would fight")
        self.assertGreaterEqual(field["ink_contrast_p05"], 4.5,
                                "the contract ink does not clear 4.5:1 on the darkest 5 % of the field")
        self.assertGreaterEqual(field["ink_contrast_median"], 7.0)

    def test_the_course_home_plate_reserves_a_quiet_field(self):
        row = audit_rows()["course-map.png"]
        field = row["quiet_field"]
        self.assertGreaterEqual(field["share_of_plate"], 0.10)
        self.assertLessEqual(field["detail_energy"], 12.0)
        self.assertGreaterEqual(field["ink_contrast_p05"], 4.5)

    def test_the_cafe_frame_reserves_no_field_and_says_so(self):
        row = audit_rows()["lesson-cafe.png"]
        self.assertNotIn("quiet_field", row, "the lesson frame carries the scene, not the type")


class Palette(unittest.TestCase):
    """ART-BIBLE §2 and §9 rule 5, under ruling `D-CP013-A`: one ratified cool pigment.

    The measured metric is the reviewer's: share of pixels with ``b - max(r, g) > 10``. The ruling
    permits the indigo noren only — never a sky, a ground, a shadow or a cutout — and only inside a
    named region that sits outside the quiet field. Either path the review offered closes here: under
    the ruling the mass must be confined and bounded; if the ruling is ever revoked, the region rows
    go with it and the ≤ 0.5 % cap applies to the whole plate.
    """

    def test_no_scene_carries_a_pigment_outside_the_bible_palette(self):
        bible = BIBLE.read_text()
        self.assertIn("D-CP013-A", bible, "the bible must carry the ruling this test judges by")
        self.assertIn("Noren indigo", bible, "the ratified pigment must be named in the palette table")
        rows = audit_rows()
        for name in SCENE_PLATES:
            row = rows[f"{name}.png"]
            width, height = row["width"], row["height"]
            with self.subTest(plate=name):
                noren = row.get("noren")
                if not noren:
                    self.assertLessEqual(
                        row["cool_share_of_plate"], 0.005,
                        f"{name} carries cool pigment but declares no ratified noren region")
                    continue
                self.assertEqual(noren["ruling"], "D-CP013-A")
                self.assertLessEqual(noren["cool_share_of_plate"], 0.10,
                                     f"{name}'s noren mass grew past the ratified bound")
                self.assertLessEqual(
                    noren["cool_share_outside_region"], 0.005,
                    f"{name} paints cool pigment outside its named noren region")
                x0, y0, x1, y1 = noren["box_px"]
                self.assertLessEqual((x1 - x0) * (y1 - y0) / (width * height), 0.25,
                                     "the region box is drifting into a licence to paint blue")
                self.assertGreaterEqual(x0 / width, 0.60,
                                        "the noren sits on the right, away from the title field")
                self.assertLessEqual(y1 / height, 0.70)
                field = row.get("quiet_field")
                if field:
                    fx0, fy0, fx1, fy1 = field["box_px"]
                    overlap = not (x1 <= fx0 or x0 >= fx1 or y1 <= fy0 or y0 >= fy1)
                    self.assertFalse(overlap, f"{name}'s noren overlaps the quiet field")
                self.assertTrue(noren["dark_tint_outside_region"]["warm"],
                                f"{name}'s darkest 5 % outside the noren is not a warm pigment")

    def test_no_scene_carries_pure_black_and_the_darkest_pigment_is_warm(self):
        for name, row in audit_rows().items():
            if not name.startswith(("discover-", "lesson-", "course-")):
                continue
            with self.subTest(plate=name):
                self.assertLessEqual(row["pure_black_fraction"], 0.001,
                                     f"{name} carries {row['pure_black_fraction']:.3%} pure black")
                self.assertTrue(row["dark_tint"]["warm"],
                                f"{name}'s darkest 5 % is {row['dark_tint']['hex']}, not a warm pigment")


class ObjectBlanks(unittest.TestCase):
    def test_the_seven_blanks_are_256px_rgba_cutouts(self):
        from PIL import Image

        for name in OBJECT_PLATES:
            with self.subTest(object=name):
                path = OBJECTS / f"{name}.png"
                self.assertTrue(path.is_file(), f"{name} missing")
                with Image.open(path) as im:
                    self.assertEqual(im.mode, "RGBA")
                    self.assertEqual((im.width, im.height), (256, 256))
                    alpha = im.getchannel("A")
                    self.assertEqual(alpha.getpixel((0, 0)), 0, f"{name} corner is not transparent")
                    self.assertIsNotNone(alpha.getbbox(), f"{name} has no opaque pixels")

    def test_no_blank_is_mostly_black(self):
        for name, row in audit_rows().items():
            if not row["kind"] == "object":
                continue
            with self.subTest(object=name):
                self.assertLessEqual(row["pure_black_fraction_of_opaque"] or 0, 0.001,
                                     f"{name} carries a near-black mass")
                self.assertGreaterEqual(row["opaque_fraction"], 0.20, f"{name} is nearly empty")

    def test_each_rim_carries_a_blank_centre_for_a_runtime_icon(self):
        rows = audit_rows()
        for name in RIM_CENTRES:
            with self.subTest(object=name):
                centre = rows[f"{name}.png"]["centre_probe"]
                self.assertEqual(centre["mode"], "flat")
                self.assertLessEqual(centre["detail_energy"], 16.0,
                                     f"{name}'s centre carries a painted mark")

    def test_no_blank_carries_a_cool_pigment(self):
        for name, row in audit_rows().items():
            if not row["kind"] == "object":
                continue
            with self.subTest(object=name):
                self.assertLessEqual(row["cool_fraction_of_opaque"] or 0, 0.005,
                                     f"{name} carries the ratified noren pigment or another cool mass")

    def test_props_are_not_asked_to_hold_an_icon(self):
        rows = audit_rows()
        for name in OBJECT_PLATES:
            if name in RIM_CENTRES:
                continue
            self.assertNotIn("centre_probe", rows[f"{name}.png"])


class Textless(unittest.TestCase):
    """The documented criterion (ART-PROVENANCE-A4A5.md, measured facts): no token of two or more
    characters at 70 confidence or above. tesseract on a full painted plate emits single-glyph
    contour noise ('W', 'U', 'I') that is not lettering; a two-character word at high confidence is.
    """

    @staticmethod
    def _words_at_confidence(path: Path) -> list[str]:
        out = subprocess.run(["tesseract", str(path), "-", "--psm", "3", "tsv"],
                             capture_output=True, text=True, check=False)
        if out.returncode != 0:
            raise AssertionError(out.stderr)
        words = []
        for line in out.stdout.splitlines()[1:]:
            fields = line.split("\t")
            if len(fields) < 12:
                continue
            text, conf = fields[11].strip(), fields[10]
            try:
                score = float(conf)
            except ValueError:
                continue
            if len(text) >= 2 and score >= 70:
                words.append(text)
        return words

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract is not installed")
    def test_no_plate_carries_readable_lettering(self):
        paths = [SCENES / f"{p}.png" for p in SCENE_PLATES] + [OBJECTS / f"{o}.png" for o in OBJECT_PLATES]
        for path in paths:
            with self.subTest(plate=path.name):
                words = self._words_at_confidence(path)
                self.assertEqual(words, [], f"{path.name} OCR read {words!r}; art must be textless")


class Provenance(unittest.TestCase):
    def test_one_row_per_shipped_plate(self):
        rows = provenance()["rows"]
        plates = {row["plate"] for row in rows}
        self.assertEqual(plates, set(SCENE_PLATES) | set(OBJECT_PLATES))
        self.assertEqual(len(rows), len(SCENE_PLATES) + len(OBJECT_PLATES))

    def test_row_hashes_are_the_files_actual_hashes(self):
        for row in provenance()["rows"]:
            with self.subTest(plate=row["plate"]):
                self.assertEqual(sha256(ROOT / row["asset"]), row["asset_sha256"])
                self.assertEqual((ROOT / row["asset"]).stat().st_size, row["bytes"])
                self.assertEqual(sha256(ROOT / row["raw_asset"]), row["raw_sha256"])

    def test_every_prompt_hash_is_the_hash_of_the_recorded_prompt(self):
        recorded = prompts()
        for row in provenance()["rows"]:
            with self.subTest(plate=row["plate"]):
                prompt = recorded[row["prompt_id"]]["prompt"]
                self.assertEqual(hashlib.sha256(prompt.encode("utf-8")).hexdigest(), row["prompt_sha256"])

    def test_rows_cite_a_provider_url_and_do_not_invent_a_model_id(self):
        for row in provenance()["rows"]:
            with self.subTest(plate=row["plate"]):
                self.assertTrue(row["media_url"].startswith("https://v3b.fal.media/"), row["media_url"])
                self.assertIn("not reported", row["provider"])

    def test_text_check_is_recorded_and_passed(self):
        for row in provenance()["rows"]:
            with self.subTest(plate=row["plate"]):
                self.assertTrue(row["ocr"]["run"], f"{row['plate']} has no recorded text check")
                self.assertEqual(row["ocr"]["text"], "", f"{row['plate']} recorded text {row['ocr']['text']!r}")

    def test_rejected_rounds_are_recorded_and_their_bytes_are_gone(self):
        rejected = provenance()["rejected"]
        self.assertGreaterEqual(len(rejected), 2)
        for row in rejected:
            with self.subTest(prompt=row["prompt_id"]):
                self.assertFalse(row["bytes_kept"])
                self.assertTrue(row["reason"].strip())
                kept = [p for p in (AUDIT / "raw").iterdir()
                        if sha256(p) == row["raw_sha256"]]
                self.assertEqual(kept, [], f"{row['prompt_id']}'s rejected bytes are still on disk")


class Pipeline(unittest.TestCase):
    def test_the_build_reads_the_painted_master_and_records_it(self):
        rows = {row["provenance_id"]: row for row in json.loads((SHIPPED / "manifest.json").read_text())}
        for name in OBJECT_PLATES:
            with self.subTest(object=name):
                row = rows[f"cb.asset.object.{name}"]
                self.assertEqual(row["master"], f"assets/art/objects/{name}.png")
                self.assertEqual(row["source"], f"generated:audit/cp013-scenes/provenance.json#{name}")
                self.assertEqual(sha256(ROOT / row["master"]), row["master_sha256"])
                self.assertLessEqual(row["bytes"], 300_000)

    def test_no_scene_plate_is_embedded_in_the_segment(self):
        text = GENERATED.read_text()
        self.assertNotIn("art/scenes", text)
        for plate in SCENE_PLATES:
            self.assertNotIn(plate, text)

    def test_the_documents_name_every_plate_and_bind_the_rules(self):
        doc = PROVENANCE_DOC.read_text()
        for plate in list(SCENE_PLATES) + list(OBJECT_PLATES):
            self.assertIn(plate, doc, f"ART-PROVENANCE-A4A5.md does not name {plate}")
        bible = BIBLE.read_text()
        self.assertIn("## 9. A4 scene plates", bible)
        self.assertIn("## 10. A5 object kit", bible)
        self.assertIn("-fuzz 30%", bible)

    def test_the_review_sheet_cites_this_card_s_own_record(self):
        """The sheet once pointed at the A1 fox provenance. A reviewer following it read the wrong
        card's hashes, so the citation is asserted here rather than trusted to a regeneration."""
        script = (ROOT / "scripts" / "cp013-contact-sheet.py").read_text()
        self.assertIn("ART-PROVENANCE-A4A5.md", script)
        self.assertNotIn("concept-parity/ART-PROVENANCE.md", script)

    def test_the_bible_calls_the_marking_a_cuff(self):
        """`D-CP010-A` retired "sock"; §2 re-introduced the word once and is not allowed to again."""
        bible = BIBLE.read_text()
        self.assertNotIn("Fox dark sock", bible)
        self.assertNotIn("sock-dark", bible)

    def test_the_medallion_set_names_five_real_events(self):
        doc = PROVENANCE_DOC.read_text()
        for event in EVENT_NAMES:
            self.assertIn(event, doc, f"the medallion table does not name {event}")
        self.assertIn("blocked on a copy id", doc,
                      "the fifth event's missing label id must be an honest gap, not an invented word")

    def test_the_medallion_set_accounts_for_every_real_action_kind(self):
        """The doc once claimed five kinds "plus the course-end" while mapping four and dropping
        ``returned``. The enum is the authority: every kind in it is named, mapped or explicitly out
        of scope. A sixth kind added to the product fails here until the doc says what happened to it.
        """
        from coursebook.gm_contract import EngagementAction

        kinds = [value for name, value in vars(EngagementAction).items()
                 if name.isupper() and isinstance(value, str)]
        self.assertEqual(len(kinds), 5, "EngagementAction changed shape; re-measure the medallion set")
        doc = PROVENANCE_DOC.read_text()
        for kind in kinds:
            with self.subTest(kind=kind):
                self.assertIn(kind, doc, f"the medallion section never mentions {kind}")
        self.assertIn("out of scope in this card", doc,
                      "`returned` must be named as deliberately out of scope, not dropped")
