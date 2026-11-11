"""CP-010: the fox asset set, its provenance rows and its contact sheets are what the card claims.

These tests read the bytes this card ships. They do not judge whether the fox is charming — that is
the owner's approval and the reviewer's vision pass. They prove that every shipped plate is a keyed
RGBA cutout at the sizes the plan promises, carries no lettering tesseract can read, carries no pure
black contour, and has a provenance row whose hashes are the file's actual hashes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "art" / "fox"
AUDIT = ROOT / "audit" / "cp010-fox"
BIBLE = ROOT / "docs" / "concept-parity" / "ART-BIBLE.md"
PROVENANCE_DOC = ROOT / "docs" / "concept-parity" / "ART-PROVENANCE.md"
CONTACT = ROOT / "docs" / "concept-parity" / "art" / "fox-contact-sheet.png"
MODEL_CONTACT = ROOT / "docs" / "concept-parity" / "art" / "fox-model-sheet-contact.png"
FOX_MANIFEST = ROOT / "assets" / "fox" / "manifest.json"
GENERATED = ROOT / "desktop" / "cb-assets.generated.js"
PLUGIN = ROOT / "desktop" / "plugin.js"
BUILDER = ROOT / "scripts" / "build_cb_assets.py"

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


class BrandSegmentAdoption(unittest.TestCase):
    """CP-005f — the brand-asset segment encodes the owner-signed painted fox, not the placeholder.

    The owner approved the painted A1 set on 2026-11-10 (``docs/launch/FOX-SIGNOFF.md``) and the
    product kept shipping the procedural SVG derivative for another day, because no test asserted
    where the segment's fox bytes came from. These tests are that assertion:

    * every manifest row for the seven poses at 64/128/256/512 names
      ``assets/art/fox/fox-<pose>-<size>.png`` as its source and master, and carries that file's
      real hash;
    * the shipped WebP decodes to that painted plate at that size (alpha identical), so the bytes
      cannot quietly come from anywhere else;
    * the generated segment has one key per pose and export, pointing at that file with that hash;
    * ``cb3FoxSource``/``cb3FoxPixels`` in the built module select 512 at >=416, 256 at >=208,
      128 at >=128 and 64 below, and ``FoxPose`` renders 208 and 512 from those exports with a
      1x/2x srcSet;
    * no ``assets/masters/fox`` path is reachable from the manifest, the segment or the module.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = json.loads(FOX_MANIFEST.read_text())
        cls.by_path = {row["path"]: row for row in cls.rows}
        text = GENERATED.read_text()
        start = text.index("Object.freeze(") + len("Object.freeze(")
        cls.assets = json.loads(text[start:text.rindex(");")])["assets"]

    #: The audit's rule (``docs/launch/FOX-ASSET-AUDIT.md`` item 3), stated here independently of
    #: the module so a silent change to the thresholds is a failure, not a new truth.
    @staticmethod
    def expected_export(size: int) -> int:
        if size >= 416:
            return 512
        if size >= 208:
            return 256
        if size >= 128:
            return 128
        return 64

    def manifest_row(self, pose: str, size: int) -> dict:
        path = "assets/fox/fox-%s-%d.webp" % (pose, size)
        self.assertIn(path, self.by_path, "no manifest row for %s" % path)
        return self.by_path[path]

    def test_one_row_per_pose_and_export_from_the_painted_file(self):
        self.assertEqual(len(self.rows), len(POSES) * len(SIZES), "fox manifest row count changed")
        from PIL import Image

        for pose in POSES:
            for size in SIZES:
                with self.subTest(pose=pose, size=size):
                    row = self.manifest_row(pose, size)
                    painted_rel = "assets/art/fox/fox-%s-%d.png" % (pose, size)
                    self.assertEqual(row["source"], "authored:%s" % painted_rel)
                    self.assertEqual(row["master"], painted_rel)
                    painted = ROOT / painted_rel
                    self.assertTrue(painted.is_file(), "%s is missing" % painted_rel)
                    self.assertEqual(row["master_sha256"], sha256(painted))
                    with Image.open(painted) as img:
                        self.assertEqual(img.mode, "RGBA")
                        self.assertEqual(img.size, (size, size))
                        self.assertEqual(img.getchannel("A").getpixel((0, 0)), 0,
                                         "%s is not an alpha cutout" % painted_rel)
                    shipped = ROOT / row["path"]
                    self.assertEqual(row["sha256"], sha256(shipped))
                    self.assertEqual(row["bytes"], shipped.stat().st_size)
                    self.assertEqual((row["width"], row["height"]), (size, size))

    def test_shipped_webp_is_that_painted_plate(self):
        """A hash chain proves the bookkeeping; the pixels prove it is the same animal.

        Measured on the shipped set: alpha is byte-identical to the painted PNG at every size, the
        mean RGB delta is 0.78–2.45/255 and no channel anywhere is off by more than 47/255. The
        placeholder can never pass this: it is a different drawing, not a lossy encode.
        """
        from PIL import Image, ImageChops, ImageStat

        for pose in POSES:
            for size in SIZES:
                with self.subTest(pose=pose, size=size):
                    row = self.manifest_row(pose, size)
                    with Image.open(ROOT / row["master"]) as master, \
                            Image.open(ROOT / row["path"]) as shipped:
                        self.assertEqual(shipped.size, (size, size))
                        a = master.convert("RGBA")
                        b = shipped.convert("RGBA")
                        self.assertEqual(
                            ImageChops.difference(a.getchannel("A"), b.getchannel("A")).getbbox(),
                            None,
                            "%s alpha drifted from the painted plate" % row["path"],
                        )
                        # Compare the visible plate: RGB under a transparent pixel is not paint.
                        paper = Image.new("RGBA", a.size, (255, 255, 255, 255))
                        flattened = [
                            Image.alpha_composite(paper, image).convert("RGB") for image in (a, b)
                        ]
                    diff = ImageChops.difference(*flattened)
                    mean = sum(ImageStat.Stat(diff).mean) / 3.0
                    worst = max(channel.getextrema()[1] for channel in diff.split())
                    self.assertLess(mean, 3.0,
                                    "%s is not an encode of the painted plate (mean delta %.2f)"
                                    % (row["path"], mean))
                    self.assertLess(worst, 64,
                                    "%s has a %d/255 channel error against the painted plate"
                                    % (row["path"], worst))

    def test_no_placeholder_path_is_reachable(self):
        for name, path in (("fox manifest", FOX_MANIFEST), ("generated segment", GENERATED),
                           ("built module", PLUGIN)):
            with self.subTest(artifact=name):
                self.assertNotIn("assets/masters/fox", path.read_text(),
                                 "%s still reaches the procedural placeholder" % name)

    def test_registry_has_every_pose_and_export(self):
        for pose in POSES:
            for size in SIZES:
                with self.subTest(pose=pose, size=size):
                    key = "cb.asset.fox.%s.%d" % (pose, size)
                    self.assertIn(key, self.assets, "segment has no %s" % key)
                    entry = self.assets[key]
                    row = self.manifest_row(pose, size)
                    self.assertEqual(entry["path"], row["path"])
                    self.assertEqual(entry["sha256"], row["sha256"])
                    self.assertEqual(entry["width"], size)
                    self.assertTrue(entry["src"].startswith("data:image/webp;base64,"))

    def test_builder_reads_the_painted_set(self):
        source = BUILDER.read_text()
        self.assertIn("FOX_EXPORTS = (512, 256, 128, 64)", source)
        self.assertIn('ART_FOX = ASSETS / "art" / "fox"', source)
        self.assertNotIn('"authored:assets/masters/fox', source)
        # The procedural SVG generator may survive for --write-masters, but the fox branch may not
        # rasterize it: a fallback here would re-ship the placeholder behind a missing-export typo.
        fox_branch = source.split("# fox ---", 1)[1].split("# objects ---", 1)[0]
        self.assertNotIn("rasterize_svg", fox_branch, "the fox branch rasterizes an SVG again")
        self.assertIn("missing painted fox export", fox_branch)

    # ── the built module: selection rule, srcSet and a real FoxPose render ────────────────────

    PROBE = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createHash } from 'node:crypto'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1344)
const mod = await import('./plugin.js')

const sha = (url) => {
  if (!url) return null
  const comma = String(url).indexOf(',')
  if (comma < 0) return null
  return createHash('sha256').update(Buffer.from(String(url).slice(comma + 1), 'base64')).digest('hex')
}
const candidates = (set) => String(set || '')
  .split(', ')
  .filter(Boolean)
  .map((candidate) => {
    const [url, descriptor] = candidate.split(' ')
    return { descriptor: descriptor || '', sha: sha(url) }
  })

const probes = payload.sizes.map((size) => ({
  size,
  px: mod.cb3FoxPixels(size),
  src: sha(mod.cb3FoxSource(payload.pose, size)),
  srcset: candidates(mod.cb3FoxSrcSet(payload.pose, size))
}))

const markup = renderToStaticMarkup(
  React.createElement('div', null,
    ...payload.renders.map((r) => React.createElement(mod.FoxPose, { pose: r.pose, size: r.size }))
  )
)
const imgs = []
for (const tag of markup.match(/<img[^>]*>/g) || []) {
  const get = (name) => {
    const m = tag.match(new RegExp('\\s' + name + '="([^"]*)"', 'i'))
    return m ? m[1] : null
  }
  imgs.push({ src: sha(get('src')), srcset: candidates(get('srcset')) })
}
const wrappers = []
for (const m of markup.matchAll(/data-cb3-fox="([^"]+)"[^>]*?data-cb3-fox-export="(\d+)"/g)) {
  wrappers.push({ pose: m[1], px: Number(m[2]) })
}
process.stdout.write(JSON.stringify({ exports: mod.CB3_FOX_EXPORTS, probes, imgs, wrappers }))
"""

    @classmethod
    def setUpClassModule(cls) -> None:
        if cls.module is not None:
            return

        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        root = Path(tempfile.mkdtemp(prefix="coursebook-cp005f-probe-"))
        (root / "plugin.js").write_text(PLUGIN.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "probe.mjs").write_text(cls.PROBE, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.module = root

    module = None

    def probe(self, payload: dict) -> dict:
        self.setUpClassModule()
        case = self.module / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.module / "probe.mjs"), str(case)],
            cwd=self.module, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_the_primitive_selects_the_export_the_audit_names(self):
        sizes = [16, 32, 64, 96, 112, 127, 128, 160, 207, 208, 220, 256, 320, 415, 416, 512, 768]
        out = self.probe({"pose": "clock", "sizes": sizes, "renders": []})
        self.assertEqual(out["exports"], [64, 128, 256, 512])
        for probe in out["probes"]:
            size = probe["size"]
            expected = self.expected_export(size)
            with self.subTest(size=size):
                self.assertEqual(probe["px"], expected,
                                 "a %d px box resolved to the %s export" % (size, probe["px"]))
                self.assertEqual(probe["src"], self.manifest_row("clock", expected)["sha256"],
                                 "a %d px box embedded something other than the %d WebP"
                                 % (size, expected))
                next_up = next((px for px in (64, 128, 256, 512) if px > expected), 512)
                self.assertEqual(
                    [c["descriptor"] for c in probe["srcset"]], ["1x", "2x"],
                    "a %d px box has no 1x/2x srcSet" % size,
                )
                self.assertEqual(
                    [c["sha"] for c in probe["srcset"]],
                    [self.manifest_row("clock", expected)["sha256"],
                     self.manifest_row("clock", next_up)["sha256"]],
                    "the srcSet candidates are not the %d and %d painted WebPs"
                    % (expected, next_up),
                )

    def test_foxpose_renders_208_and_512_from_the_painted_set(self):
        renders = [{"pose": "wave", "size": 208}, {"pose": "clock", "size": 208},
                   {"pose": "clock", "size": 512}]
        out = self.probe({"pose": "clock", "sizes": [], "renders": renders})
        self.assertEqual(out["wrappers"], [
            {"pose": "wave", "px": 256},
            {"pose": "clock", "px": 256},
            {"pose": "clock", "px": 512},
        ], "FoxPose did not mount the 208 boxes on the 256 export")
        expected = [("wave", 256), ("clock", 256), ("clock", 512)]
        self.assertEqual(len(out["imgs"]), len(expected))
        for image, (pose, px) in zip(out["imgs"], expected):
            with self.subTest(pose=pose, px=px):
                self.assertEqual(image["src"], self.manifest_row(pose, px)["sha256"])
                self.assertEqual([c["descriptor"] for c in image["srcset"]], ["1x", "2x"])
                self.assertEqual(image["srcset"][0]["sha"], self.manifest_row(pose, px)["sha256"])


class FoxProofPage(unittest.TestCase):
    """The frame in the review packet is generated from the module, not drawn by hand.

    ``design/fox-adoption.html`` mounts ``FoxPose`` from ``desktop/plugin.js`` at 208 for the two
    poses the acceptance names. Re-running the generator must reproduce the committed bytes, and
    the page must actually carry two 208 px boxes resolved to the 256 export.
    """

    PAGE = ROOT / "design" / "fox-adoption.html"
    GENERATOR = ROOT / "scripts" / "gen-fox-proof.py"

    def test_the_committed_page_pins_the_current_module(self):
        self.assertTrue(self.PAGE.is_file(), "design/fox-adoption.html is missing")
        page = self.PAGE.read_text()
        self.assertIn(hashlib.sha256(PLUGIN.read_bytes()).hexdigest(), page,
                      "the proof page names a module sha that is not desktop/plugin.js")
        self.assertEqual(page.count('style="width:208px;height:208px'), 2,
                         "the proof does not show two 208 px boxes")
        self.assertGreaterEqual(page.count('data-cb3-fox-export="256"'), 2,
                                "a 208 px box is not mounted on the 256 export")
        for pose in POSES:
            with self.subTest(pose=pose):
                self.assertIn('data-cb3-fox="%s"' % pose, page)

    def test_a_fresh_render_reproduces_the_committed_page(self):
        import sys

        if _desktop_node_modules() is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        result = subprocess.run(
            [sys.executable, str(self.GENERATOR), "--check"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0,
                         "%s\n%s" % (result.stdout[-2000:], result.stderr[-2000:]))


if __name__ == "__main__":
    unittest.main()
