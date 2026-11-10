"""CP-012: the A3 cover kit is what the card claims.

These tests read the bytes this card ships. They do not judge whether the art is any good — that is
the owner's approval on the contact sheet and the reviewer's swap check. They prove that the three
bundled packs each have a 1200x800 master with a mechanical 4:5 crop, that every file sits on the
contract paper with no alpha and no black contour, that no forbidden state pigment is painted
anywhere on a plate, that every declared motif is really painted and survives the mechanical 4:5
crop, that the provenance hashes are the files' actual hashes, that the swap-check record proves the
three motif sets are disjoint, and that the witness document names the packs it claims.

The motif and state-hue tests are the round-2 closures for the two review defects: the plum cloth
that the acceptance script had been widened to admit, and the 4:5 crop that severed the Japanese
lantern (18 % of its ink survived in round 1).
"""

from __future__ import annotations

import hashlib
import json
import re
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


class FourByFiveKeepsTheSubjects(unittest.TestCase):
    """Round-2 defect 2: the 4:5 crop must not drop a declared motif."""

    CROP = (280, 920)
    MIN_INK = 150
    MIN_RETAINED = 0.60

    @staticmethod
    def ink_mask(path):
        import numpy as np
        from PIL import Image

        with Image.open(path) as im:
            a = np.asarray(im.convert("RGB")).astype(np.int16)
        return (np.abs(a - np.array(PAPER)).max(axis=2) > 60)

    def test_the_4x5_variant_keeps_every_declared_motif(self):
        covers = {c["pack"]: c for c in load("swap-check.json")["covers"]}
        for pack, slug in PACKS.items():
            cover = covers[pack]
            mask = self.ink_mask(COVERS / f"{slug}-master-1200x800.png")
            for motif in cover["motifs"]:
                with self.subTest(pack=pack, motif=motif["mark"]):
                    x0, y0, x1, y1 = motif["bbox"]
                    self.assertLess(x0, x1)
                    self.assertLess(y0, y1)
                    self.assertGreaterEqual(x1 - x0, 20, "a motif zone must be a real region")
                    self.assertGreaterEqual(y1 - y0, 20)
                    zone = mask[y0:y1, x0:x1]
                    painted = int(zone.sum())
                    self.assertGreaterEqual(
                        painted, self.MIN_INK,
                        f"{slug}/{motif['mark']}: only {painted} painted pixels in {motif['bbox']} — "
                        "the motif is not where the record says it is")
                    ix0, ix1 = max(x0, self.CROP[0]), min(x1, self.CROP[1])
                    kept = int(mask[y0:y1, ix0:ix1].sum()) if ix1 > ix0 else 0
                    retained = kept / painted
                    self.assertGreaterEqual(
                        retained, self.MIN_RETAINED,
                        f"{slug}/{motif['mark']}: {retained:.1%} of its {painted} painted pixels "
                        f"survive the 4:5 crop window {self.CROP}")

    def test_the_motif_zones_do_not_all_cover_the_whole_plate(self):
        # Zones are per-motif, not one box around everything: at least one pair per bundle
        # must be disjoint, otherwise the retention check would be satisfied by one big box.
        for cover in load("swap-check.json")["covers"]:
            boxes = [tuple(m["bbox"]) for m in cover["motifs"]]
            disjoint = any(
                a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
                for i, a in enumerate(boxes) for b in boxes[i + 1:]
            )
            self.assertTrue(disjoint, f"{cover['pack']}: motif zones are one undifferentiated mass")


class NoStateHue(unittest.TestCase):
    """Round-2 defect 1: GM §0 bans ochre, coral and plum in art."""

    # docs/GM-SUBJECT-WORLDS.md §0 and ART-BIBLE.md §2
    STATE = {"ochre": (123, 75, 10), "coral": (156, 46, 28), "plum": (106, 62, 116)}
    MAX_SHARE = 0.005

    @staticmethod
    def _lab(rgb):
        c = [v / 255.0 for v in rgb]
        c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        x = c[0] * 0.4124 + c[1] * 0.3576 + c[2] * 0.1805
        y = c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722
        z = c[0] * 0.0193 + c[1] * 0.1192 + c[2] * 0.9505
        f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
        fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
        return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

    def test_no_forbidden_state_pigment_is_painted(self):
        import numpy as np
        from PIL import Image

        anchors = {name: np.array(self._lab(rgb)) for name, rgb in self.STATE.items()}
        for pack, slug in PACKS.items():
            with self.subTest(pack=pack):
                with Image.open(COVERS / f"{slug}-master-1200x800.png") as im:
                    a = np.asarray(im.convert("RGB")).astype(np.float64)
                c = a / 255.0
                lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
                m = np.array([[0.4124, 0.3576, 0.1805],
                              [0.2126, 0.7152, 0.0722],
                              [0.0193, 0.1192, 0.9505]])
                xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
                t = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
                lab = np.stack([116 * t[..., 1] - 16,
                                500 * (t[..., 0] - t[..., 1]),
                                200 * (t[..., 1] - t[..., 2])], axis=-1)
                for name, anchor in anchors.items():
                    share = float((np.linalg.norm(lab - anchor, axis=-1) <= 12).mean())
                    self.assertLessEqual(
                        share, self.MAX_SHARE,
                        f"{slug}: {share:.2%} of the frame is within dE 12 of the banned "
                        f"{name} pigment ({self.STATE[name]})")

    def test_the_plum_hue_band_is_absent(self):
        import colorsys
        from PIL import Image

        for pack, slug in PACKS.items():
            with self.subTest(pack=pack):
                with Image.open(COVERS / f"{slug}-master-1200x800.png") as im:
                    raw = im.convert("RGB").resize((300, 200)).tobytes()
                px = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
                plum = 0
                for rgb in px:
                    h, _l, _s = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
                    hue = h * 360
                    chroma = (max(rgb) - min(rgb)) / max(max(rgb), 1)
                    if 270 <= hue <= 340 and chroma > 0.15:
                        plum += 1
                self.assertLessEqual(plum / len(px), 0.005,
                                     f"{slug}: {plum / len(px):.2%} of sampled pixels are plum-hued")


class AcceptanceGateCanFail(unittest.TestCase):
    """Negative controls: the round-2 gates must reject what they claim to reject.

    A gate that only ever passes is not a gate. These run the real acceptance script on a
    temporary copy of the tree, so the shipped record is untouched.
    """

    @staticmethod
    def _stage(tmp: Path) -> None:
        for name in ("scripts", "audit", "assets"):
            shutil.copytree(ROOT / name, tmp / name,
                            ignore=shutil.ignore_patterns("__pycache__"))

    def _run(self, tmp: Path) -> subprocess.CompletedProcess:
        return subprocess.run(("python3", str(tmp / "scripts" / "cp012-cover-accept.py")),
                              capture_output=True, text=True, cwd=tmp)

    def test_a_plum_patch_on_a_shipped_master_is_rejected(self):
        import tempfile
        from PIL import Image

        tmp = Path(tempfile.mkdtemp(prefix="cp012-gate-plum-"))
        self._stage(tmp)
        master = tmp / "assets" / "art" / "covers" / "parent-master-1200x800.png"
        with Image.open(master) as im:
            art = im.convert("RGB")
        # 60x120 = 7,200 px of #6a3e74, 0.75 % of a 1200x800 frame -> over the 0.5 % line
        patch = Image.new("RGB", (60, 120), (106, 62, 116))
        art.paste(patch, (100, 100))
        art.save(master)
        r = self._run(tmp)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no state hue shipped", r.stdout)

    def test_a_motif_zone_outside_the_crop_window_is_rejected(self):
        import json
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix="cp012-gate-crop-"))
        self._stage(tmp)
        swap_path = tmp / "audit" / "cp012-covers" / "swap-check.json"
        swap = json.loads(swap_path.read_text())
        for cover in swap["covers"]:
            if cover["pack"] == "parent-measurement-practice":
                cover["motifs"][0]["bbox"] = [10, 10, 260, 200]   # painted, but left of x=280
        swap_path.write_text(json.dumps(swap, indent=2))
        r = self._run(tmp)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("4:5 keeps jug", r.stdout)


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
    """The accept script owns its own total; the witness doc must match it.

    Round 2 shipped `COVERS.md` claiming 88 checks against a script that ran 80,
    because nothing owned the number. The script now prints
    `<N> checks: <N> pass, <F> fail` as its last line and these tests read that
    line instead of trusting the document.
    """

    SUMMARY = re.compile(r"^(\d+) checks: (\d+) pass, (\d+) fail$", re.M)

    @classmethod
    def setUpClass(cls):
        cls.result = subprocess.run(
            ("python3", str(ROOT / "scripts" / "cp012-cover-accept.py")),
            capture_output=True, text=True, cwd=ROOT)
        found = cls.SUMMARY.findall(cls.result.stdout)
        cls.summary = found[-1] if found else None

    def test_the_machine_acceptance_passes(self):
        r = self.result
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("A3 cover kit accepted", r.stdout)

    def test_the_script_reports_its_own_total(self):
        self.assertIsNotNone(
            self.summary,
            "the accept script must print a final '<N> checks: <N> pass, <F> fail' line")
        assert self.summary is not None
        total, passed, failed = (int(v) for v in self.summary)
        self.assertEqual(failed, 0, "a shipped packet must have no failing check")
        self.assertEqual(total, passed, "every reported check must be a counted pass")
        self.assertGreater(total, 50, "the machine half must not shrink silently")

    def test_the_declared_check_count_matches_the_script(self):
        self.assertIsNotNone(self.summary, "no total line in the accept script's output")
        assert self.summary is not None
        total = int(self.summary[0])
        declared = re.search(r"\*\*(\d+) checks, exit 0\*\*", DOC.read_text())
        self.assertIsNotNone(
            declared, "COVERS.md must declare the accept total as '**<N> checks, exit 0**'")
        assert declared is not None
        self.assertEqual(
            int(declared.group(1)), total,
            "COVERS.md's declared check total must equal the accept script's reported total")


if __name__ == "__main__":
    unittest.main()
