"""CP-012: the A3 cover kit is what the card claims.

These tests read the bytes this card ships. They do not judge whether the art is any good — that is
the owner's approval on the contact sheet and the reviewer's swap check. They prove that the three
bundled packs each have a 1200x800 master with a mechanical 4:5 crop, that every file sits on the
contract paper with no alpha and no black contour, that the provenance hashes are the files' actual
hashes, that the swap-check record proves the three motif sets are disjoint, and that the witness
document names the packs it claims.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERS = ROOT / "assets" / "art" / "covers"
AUDIT = ROOT / "audit" / "cp012-covers"
CONTACT = ROOT / "docs" / "concept-parity" / "covers" / "cover-contact-sheet.png"
DOC = ROOT / "docs" / "concept-parity" / "COVERS.md"

PACKS = {
    "japanese-affection-context-l0": "japanese",
    "parent-measurement-practice": "parent",
    "technical-demo-pack": "technical",
}
PAPER = (247, 241, 228)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    return json.loads((AUDIT / name).read_text())


class ShippedFiles(unittest.TestCase):
    def test_every_pack_ships_a_master_3x2_and_4x5(self):
        from PIL import Image

        for pack, slug in PACKS.items():
            with self.subTest(pack=pack):
                master = COVERS / f"{slug}-master-1200x800.png"
                crop32 = COVERS / f"{slug}-crop-3x2-1200x800.png"
                crop45 = COVERS / f"{slug}-crop-4x5-640x800.png"
                for path in (master, crop32, crop45):
                    self.assertTrue(path.exists(), f"{path.name} missing")
                with Image.open(master) as im:
                    self.assertEqual(im.size, (1200, 800))
                    self.assertEqual(im.mode, "RGB")
                with Image.open(crop45) as im:
                    self.assertEqual(im.size, (640, 800))
                    self.assertEqual(im.mode, "RGB")
                # A second drawing would not be byte-identical; a crop would not be pixel-equal.
                self.assertEqual(sha256(master), sha256(crop32))

    def test_the_4x5_file_is_the_master_centre_crop(self):
        from PIL import Image

        for pack, slug in PACKS.items():
            with self.subTest(pack=pack):
                with Image.open(COVERS / f"{slug}-master-1200x800.png") as master:
                    crop = master.crop((280, 0, 920, 800))
                with Image.open(COVERS / f"{slug}-crop-4x5-640x800.png") as shipped:
                    self.assertEqual(crop.tobytes(), shipped.tobytes())

    def test_every_file_sits_on_the_contract_paper(self):
        from PIL import Image, ImageStat

        for slug in PACKS.values():
            with self.subTest(slug=slug):
                with Image.open(COVERS / f"{slug}-master-1200x800.png") as im:
                    patch = im.crop((1168, 0, 1200, 32))
                    mean = ImageStat.Stat(patch).mean
                corner = tuple(round(v) for v in mean)
                self.assertLessEqual(
                    max(abs(corner[i] - PAPER[i]) for i in range(3)), 4, f"{slug} corner {corner}")

    def test_no_plate_carries_a_black_contour(self):
        from PIL import Image

        for slug in PACKS.values():
            with self.subTest(slug=slug):
                with Image.open(COVERS / f"{slug}-master-1200x800.png") as im:
                    small = im.resize((300, 200)).convert("RGB")
                    colours = small.getcolors(maxcolors=1 << 20) or []
                total = sum(n for n, _ in colours)
                near_black = sum(n for n, rgb in colours if max(rgb) <= 15)
                self.assertLess(near_black / total, 0.002,
                                f"{slug}: {near_black} near-black pixels of {total}")


class Provenance(unittest.TestCase):
    def test_every_hash_in_the_record_is_the_file_on_disk(self):
        prov = load("provenance.json")
        self.assertEqual(len(prov["rows"]), 3)
        self.assertEqual({row["pack"] for row in prov["rows"]}, set(PACKS))
        for row in prov["rows"]:
            for shipped in row["shipped"]:
                path = ROOT / shipped["path"]
                self.assertTrue(path.exists(), f"{shipped['path']} missing")
                self.assertEqual(sha256(path), shipped["sha256"], shipped["path"])
                self.assertEqual(path.stat().st_size, shipped["bytes"])
            raw = ROOT / row["raw"]["path"]
            self.assertEqual(sha256(raw), row["raw"]["sha256"])

    def test_prompt_hashes_match_the_recorded_prompts(self):
        prompts = {r["id"]: r for r in load("prompts.json")["rows"]}
        prov = load("provenance.json")
        for row in prov["rows"]:
            prompt = prompts[row["id"]]["prompt"]
            self.assertEqual(hashlib.sha256(prompt.encode()).hexdigest(), row["prompt_sha256"])
            self.assertIn("No text", prompt, "the negative block is part of the recorded prompt")

    def test_no_model_id_is_claimed(self):
        prov = load("provenance.json")
        self.assertEqual(prov["provider"]["model_id"], "not reported by the host tool")


class SwapCheck(unittest.TestCase):
    def test_three_covers_cover_the_three_bundled_packs(self):
        swap = load("swap-check.json")
        self.assertEqual({c["pack"] for c in swap["covers"]}, set(PACKS))
        self.assertEqual(len(swap["covers"]), 3)

    def test_each_cover_declares_at_least_two_motifs_and_rejects_every_swap(self):
        for cover in load("swap-check.json")["covers"]:
            with self.subTest(pack=cover["pack"]):
                self.assertGreaterEqual(len(cover["motifs"]), 2)
                for motif in cover["motifs"]:
                    self.assertTrue(motif["mark"])
                    self.assertTrue(motif["must_never_become"])
                self.assertTrue(cover["swaps"])
                for swap in cover["swaps"]:
                    self.assertEqual(swap["verdict"], "rejected")
                    self.assertGreater(len(swap["reason"]), 20)

    def test_mark_sets_are_pairwise_disjoint(self):
        covers = load("swap-check.json")["covers"]
        marks = [{m["mark"].lower() for m in c["motifs"]} for c in covers]
        for i in range(len(marks)):
            for j in range(i + 1, len(marks)):
                self.assertFalse(marks[i] & marks[j],
                                 f"{covers[i]['pack']} and {covers[j]['pack']} share marks")


class Evidence(unittest.TestCase):
    def test_the_contact_sheet_is_a_labelled_rgb_review_artifact(self):
        from PIL import Image

        self.assertTrue(CONTACT.exists())
        with Image.open(CONTACT) as im:
            self.assertEqual(im.mode, "RGB")
            self.assertGreaterEqual(im.width, 1200)
            self.assertGreaterEqual(im.height, 900)

    def test_the_witness_document_names_all_three_packs(self):
        text = DOC.read_text()
        for pack in PACKS:
            self.assertIn(pack, text)
        self.assertIn("not yet signed", text)
        self.assertIn("CP-014", text, "the document must say this kit does not touch the packs")


@unittest.skipUnless(shutil.which("magick") and shutil.which("tesseract"), "needs magick + tesseract")
class AcceptanceScript(unittest.TestCase):
    def test_the_machine_acceptance_passes(self):
        r = subprocess.run(("python3", str(ROOT / "scripts" / "cp012-cover-accept.py")),
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("A3 cover kit accepted", r.stdout)


if __name__ == "__main__":
    unittest.main()
