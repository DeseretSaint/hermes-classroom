"""VQ-006 — the refusal rules of the installed visual capture harness.

`scripts/vq-manifest.py` is the judge: it decides whether a captured cell may be used as visual
evidence. These tests pin its refusals with synthetic cell records, so the rules are proven without
an Electron host and a future edit cannot quietly let a placeholder, a data-URI stand-in, a
sub-2x plate or a proof page through.

The camera (`scripts/vq-capture.mjs`) is checked statically: it must look for a real installed
surface and must never fall back to a proof fixture or a render-harness page.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

import sys

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import importlib.util

SPEC = importlib.util.spec_from_file_location("vq_manifest", SCRIPTS / "vq-manifest.py")
vq = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(vq)

FAKE_SHA = "a" * 64


def png_bytes(width: int, height: int, salt: int = 0) -> bytes:
    """A small, structurally valid PNG with the given dimensions.

    The judge reads the raster header, not the pixels; this gives the tests real bytes of a declared
    size so the evidence checks exercise the same path as a captured asset. `salt` changes the bytes
    without changing the dimensions, so rows that must be distinct assets get distinct shas.
    """

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\x00\x00\x00" * width
    text = chunk(b"tEXt", b"Comment\x00" + str(salt).encode()) if salt else b""
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height, 9))
        + text
        + chunk(b"IEND", b"")
    )


def image(selector: str, kind: str, natural: tuple[int, int], rendered: tuple[int, int],
          *, data_uri: bool = False, bundled: dict | None = None, complete: bool = True,
          src: str | None = None) -> dict:
    return {
        "selector": selector,
        "kind": kind,
        "markers": [f"data-cb3-{kind}"],
        "current_src": src if src is not None else (
            "data:image/webp;base64,AAAA" if data_uri else f"http://127.0.0.1/media/{selector.strip('/')}.webp"
        ),
        "current_src_data_uri": data_uri,
        "natural": {"width": natural[0], "height": natural[1]},
        "rendered": {"width": rendered[0], "height": rendered[1]},
        "complete": complete,
        "sha256": FAKE_SHA if complete else None,
        "bundled_asset": bundled,
    }


def record(destination: str, images: list[dict], *, width: int = 1344,
           protocol: str = "http:", proof_script: bool = False,
           proof_markers: list[str] | None = None, v3_ready: bool = True,
           fonts_ok: bool = True, backgrounds: list[dict] | None = None) -> dict:
    return {
        "schema": "vq.capture.v1",
        "cell": {"name": f"{destination}--{width}", "destination": destination,
                 "width": width, "height": 768},
        "window": {"cdp_port": 9396, "plugin": {"sha256": "b" * 64, "loaded_path": "/x/plugin.js"}},
        "route": {
            "selector": "[data-cb-route]", "present": True, "marker": "/coursebook",
            "destination": vq.EXPECTED_DESTINATION[destination] or "home",
            "scope": "dark", "v3_ready": v3_ready, "fonts_status": "loaded" if fonts_ok else "loading",
            "fonts_ok": fonts_ok, "width": width, "height": 768,
            "render_error_markers": [], "proof_markers": proof_markers or [],
        },
        "surface": {"requested": destination, "resolved": destination, "control": "x", "missing": None},
        "screenshot": {"file": "shot.png", "sha256": None, "bytes": 1, "clip": None},
        "images": images,
        "backgrounds": backgrounds or [],
        "page": {"url": "http://127.0.0.1:5174/#/coursebook", "protocol": protocol,
                 "proof_script": proof_script},
        "error": None,
    }


def home_images(cover_count: int = 4) -> list[dict]:
    covers = [
        image(f"[data-cb3-cover=art] > img", "cover_plate", (1200, 800), (600, 400))
        for _ in range(cover_count)
    ]
    covers.append(image("[data-cb3-fox=clock] > img", "fox_pose", (256, 256), (128, 128),
                        data_uri=True,
                        bundled={"key": "cb.asset.fox.clock.128", "path": "assets/fox/fox-clock-128.webp"}))
    return covers


def background(selector: str, natural: tuple[int, int], rendered: tuple[int, int], *,
               data_uri: bool = False, bundled: dict | None = None, sha: str | None = FAKE_SHA,
               repeat: str = "no-repeat", size: str = "auto", url: str | None = None) -> dict:
    return {
        "selector": selector,
        "url": url if url is not None else (
            "data:image/webp;base64,AAAA" if data_uri
            else f"http://127.0.0.1/media/{selector.strip('/')}.webp"
        ),
        "data_uri": data_uri,
        "natural": {"width": natural[0], "height": natural[1]},
        "rendered": {"width": rendered[0], "height": rendered[1]},
        "background_repeat": repeat,
        "background_size": size,
        "sha256": sha,
        "bundled_asset": bundled,
        "marks": [],
    }


class HarnessCase(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def attach_evidence(self, rec: dict) -> None:
        """Persist bytes for every row that can satisfy a required role, as the camera does.

        Rows with the shared fake sha get fresh bytes of their declared natural size — salted per
        row so each is a distinct asset — and are re-stamped with that file's real sha256. Files are
        named `<sha256>.png` under `evidence/`, exactly the shape the judge accepts. A row pinned to a
        bundled pack cover gets the cover's own bytes, so the Press Plate test still matches by hash.
        """
        registry = vq.press_plate_registry()
        kinds = vq.evidence_kinds()
        for index, row in enumerate(rec.get("images") or []):
            if row.get("kind") not in kinds or not row.get("complete"):
                continue
            natural = row.get("natural") or {}
            width = int(natural.get("width") or 0)
            height = int(natural.get("height") or 0)
            if width <= 0 or height <= 0:
                continue
            sha = str(row.get("sha256") or "")
            if sha and sha != FAKE_SHA and sha in registry:
                data = (ROOT / registry[sha]).read_bytes()
            else:
                data = png_bytes(width, height, salt=index + 1)
                row["sha256"] = hashlib.sha256(data).hexdigest()
            digest = hashlib.sha256(data).hexdigest()
            relative = f"evidence/{digest}.png"
            target = self.dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            row["evidence"] = {"file": relative, "sha256": digest, "bytes": len(data)}

    def judge(self, rec: dict, *, attach: bool = True) -> dict:
        blob = b"png-bytes"
        (self.dir / "shot.png").write_bytes(blob)
        rec["screenshot"]["sha256"] = hashlib.sha256(blob).hexdigest()
        if attach:
            self.attach_evidence(rec)
        name = rec["cell"]["name"]
        (self.dir / f"{name}.json").write_text(json.dumps(rec))
        return vq.judge_cell(rec, self.dir, vq.press_plate_registry())

    def persist(self, rec: dict) -> None:
        """Write a record (and its screenshot) without judging it, for manifest-level tests."""
        blob = b"png-bytes"
        (self.dir / "shot.png").write_bytes(blob)
        rec["screenshot"]["sha256"] = hashlib.sha256(blob).hexdigest()
        (self.dir / f"{rec['cell']['name']}.json").write_text(json.dumps(rec))

    def assert_fails_with(self, verdict: dict, needle: str) -> None:
        self.assertFalse(verdict["ok"], verdict)
        joined = " | ".join(verdict["problems"])
        self.assertIn(needle, joined)


class TestGoodCell(HarnessCase):
    def test_a_complete_home_cell_passes(self):
        verdict = self.judge(record("home", home_images()))
        self.assertTrue(verdict["ok"], verdict["problems"])
        self.assertEqual(len(verdict["images"]), 5)
        self.assertTrue(all(row["scale_ratio"] >= 2 for row in verdict["images"]))

    def test_the_bundled_fox_data_uri_is_not_a_stand_in(self):
        # The fox ships as a hashed data URI in `desktop/cb-assets.generated.js`; a hashed bundled
        # asset is not the invented data URI the gate refuses.
        verdict = self.judge(record("home", home_images()))
        fox = verdict["images"][-1]
        self.assertEqual(fox["kind"], "fox_pose")
        self.assertTrue(fox["bundled_asset"])
        self.assertFalse(fox["problems"])

    def test_manifest_names_every_required_image_and_sha(self):
        self.judge(record("home", home_images()))
        manifest = vq.build_manifest(self.dir, commit="c" * 40)
        cell = manifest["cells"][0]
        roles = {row["role"]: row for row in cell["requirements"]}
        self.assertTrue(roles["display_cover"]["ok"])
        self.assertEqual(roles["display_cover"]["found"], 4)
        self.assertTrue(all(row["sha256"] for row in cell["images"]))


class TestRefusals(HarnessCase):
    def test_placeholder_image_fails(self):
        images = home_images()
        images[0] = image("[data-cb3-cover=art] > img", "cover_plate", (0, 0), (600, 400),
                          complete=False, src="")
        verdict = self.judge(record("home", images))
        self.assert_fails_with(verdict, "image not complete")

    def test_data_uri_standing_in_for_a_kit_asset_fails(self):
        images = home_images()
        images[0] = image("[data-cb3-cover=art] > img", "cover_plate", (1280, 800), (640, 400),
                          data_uri=True)
        verdict = self.judge(record("home", images))
        self.assert_fails_with(verdict, "data URI stands in for a kit asset")

    def test_below_two_x_fails(self):
        images = home_images()
        images[0] = image("[data-cb3-cover=art] > img", "cover_plate", (640, 400), (640, 400))
        verdict = self.judge(record("home", images))
        self.assert_fails_with(verdict, "below 2x rendered")

    def test_one_x_fox_fails(self):
        # The shipped 128 px fox rendered at 128 px is a real finding, not a pass: Gate 2 wants 2x.
        verdict = self.judge(record("home", home_images()))
        strict = home_images()
        strict.append(image("[data-cb3-fox=point] > img", "fox_pose", (64, 64), (64, 64), data_uri=True,
                            bundled={"key": "cb.asset.fox.point.64"}))
        verdict = self.judge(record("home", strict))
        self.assert_fails_with(verdict, "image [data-cb3-fox=point] > img: natural 64px is below 2x")

    def test_proof_page_fails(self):
        verdict = self.judge(record("home", home_images(), protocol="file:"))
        self.assert_fails_with(verdict, "not a live page")

    def test_proof_fixture_script_fails(self):
        verdict = self.judge(record("home", home_images(), proof_script=True))
        self.assert_fails_with(verdict, "proof fixture script detected")

    def test_proof_marker_fails(self):
        verdict = self.judge(record("home", home_images(), proof_markers=["[data-cb-proof]"]))
        self.assert_fails_with(verdict, "proof-only markers")

    def test_press_plate_as_display_cover_fails(self):
        images = [
            image("[data-cb-workshop-cover-image] > img", "workshop_cover", (1200, 800), (300, 200),
                  src="http://127.0.0.1/media/pack/cover-4x5.png")
            for _ in range(4)
        ]
        images.append(image("[data-cb3-fox=clock] > img", "fox_pose", (256, 256), (128, 128),
                            data_uri=True, bundled={"key": "cb.asset.fox.clock.128"}))
        verdict = self.judge(record("home", images))
        self.assert_fails_with(verdict, "Press Plate(s) counted on a product surface")
        self.assert_fails_with(verdict, "required image missing: display_cover 0/4")

    def test_bundled_pack_cover_hash_is_a_press_plate(self):
        registry = vq.press_plate_registry()
        if not registry:
            self.skipTest("no bundled pack covers in this checkout")
        cover_sha, cover_path = next(iter(registry.items()))
        images = home_images()
        images[0] = image("[data-cb3-cover=art] > img", "cover_plate", (1200, 800), (600, 400))
        images[0]["sha256"] = cover_sha
        verdict = self.judge(record("home", images))
        press = verdict["images"][0]
        self.assertTrue(press["press_plate"])
        self.assertEqual(press["press_plate_source"], cover_path)
        self.assert_fails_with(verdict, "Press Plate(s) counted on a product surface")

    def test_screenshot_sha_mismatch_fails(self):
        rec = record("home", home_images())
        (self.dir / "shot.png").write_bytes(b"one")
        rec["screenshot"]["sha256"] = hashlib.sha256(b"two").hexdigest()
        verdict = vq.judge_cell(rec, self.dir)
        self.assert_fails_with(verdict, "screenshot sha256 does not match")

    def test_missing_screenshot_file_fails(self):
        rec = record("home", home_images())
        rec["screenshot"]["sha256"] = "0" * 64
        verdict = vq.judge_cell(rec, self.dir)
        self.assert_fails_with(verdict, "screenshot missing on disk")

    def test_missing_surface_fails(self):
        rec = record("design-system", home_images())
        rec["surface"]["missing"] = {"reason": "the installed plugin mounts no Design System surface",
                                    "probed": ["[data-cb-design-system]"]}
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "missing surface")

    def test_render_error_fails(self):
        rec = record("home", home_images())
        rec["route"]["render_error_markers"] = ["[data-cb-render-error]"]
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "render error")

    def test_unloaded_fonts_fail(self):
        verdict = self.judge(record("home", home_images(), fonts_ok=False))
        self.assert_fails_with(verdict, "fonts not loaded")

    def test_wrong_destination_fails(self):
        rec = record("discover", home_images())
        rec["route"]["destination"] = "home"
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "rendered destination 'home'")


class TestBackgroundRefusals(HarnessCase):
    """A kit asset delivered as a CSS layer must fail the same rules as one delivered as <img>.

    Reproduced from review: the same numbers passed as a background row while they failed as an
    image row, because the judge never read `record["backgrounds"]`.
    """

    def test_background_without_a_natural_size_is_a_placeholder(self):
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-hero] > div", (0, 0), (900, 900)),
        ])
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "background [data-cb-home-hero] > div: no natural size")
        self.assertTrue(verdict["backgrounds"][0]["placeholder"])

    def test_background_with_an_empty_url_is_a_placeholder(self):
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-hero] > div", (1800, 1800), (900, 900), url=""),
        ])
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "empty currentSrc")

    def test_data_uri_background_standing_in_for_a_kit_asset_fails(self):
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-hero] > div", (1800, 1800), (900, 900), data_uri=True),
        ])
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "data URI stands in for a kit asset")

    def test_below_two_x_background_fails(self):
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-hero] > div", (96, 96), (900, 900)),
        ])
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "natural 96x96px is below 2x rendered 900.00x900.00px")

    def test_background_matching_a_bundled_pack_cover_is_a_press_plate(self):
        registry = vq.press_plate_registry()
        if not registry:
            self.skipTest("no bundled pack covers in this checkout")
        cover_sha, cover_path = next(iter(registry.items()))
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-hero] > div", (1200, 800), (600, 400), sha=cover_sha),
        ])
        verdict = self.judge(rec)
        layer = verdict["backgrounds"][0]
        self.assertTrue(layer["press_plate"])
        self.assertEqual(layer["press_plate_source"], cover_path)
        self.assert_fails_with(verdict, "Press Plate(s) counted on a product surface")

    def test_a_bundled_tiled_background_is_not_a_stand_in_and_is_not_ratio_judged(self):
        # The grain/vignette materials ship as hashed data URIs and tile; a 96 px tile repeated
        # over a 900 px box is not an upscaled illustration, so the 2x rule does not apply.
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-grain]", (96, 96), (900, 714), data_uri=True,
                       repeat="repeat", bundled={"key": "cb.asset.material.grain-night"}),
        ])
        verdict = self.judge(rec)
        self.assertTrue(verdict["ok"], verdict["problems"])
        layer = verdict["backgrounds"][0]
        self.assertFalse(layer["placeholder"])
        self.assertFalse(layer["press_plate"])
        self.assertFalse(layer["ratio_judged"])
        self.assertEqual(layer["problems"], [])

    def test_a_cover_sized_layer_is_ratio_judged_even_when_it_repeats(self):
        # Round-2 finding: `background-repeat` alone exempted a box-scaled layer, and repeat is the
        # CSS default, so a 96 px file stretched with `cover` over 900 px passed. Size decides.
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-vignette]", (96, 96), (900, 714),
                       repeat="repeat", size="cover",
                       bundled={"key": "cb.asset.material.vignette"}),
        ])
        verdict = self.judge(rec)
        layer = verdict["backgrounds"][0]
        self.assertTrue(layer["ratio_judged"])
        self.assertEqual(layer["judged_axes"], ["x", "y"])
        self.assert_fails_with(verdict, "natural 96x96px is below 2x rendered 900.00x714.00px")

    def test_a_contain_sized_layer_is_ratio_judged_even_when_it_repeats(self):
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-vignette]", (96, 96), (900, 714),
                       repeat="repeat-y", size="contain",
                       bundled={"key": "cb.asset.material.vignette"}),
        ])
        verdict = self.judge(rec)
        self.assertTrue(verdict["backgrounds"][0]["ratio_judged"])
        self.assert_fails_with(verdict, "natural 96x96px is below 2x rendered 900.00x714.00px")

    def test_a_percentage_sized_layer_is_ratio_judged_even_when_it_repeats(self):
        # `100% 100%` is a full-box stretch: the paint size comes from the box, not the file.
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-vignette]", (96, 96), (900, 714),
                       repeat="repeat", size="100% 100%",
                       bundled={"key": "cb.asset.material.vignette"}),
        ])
        verdict = self.judge(rec)
        self.assertTrue(verdict["backgrounds"][0]["ratio_judged"])
        self.assert_fails_with(verdict, "natural 96x96px is below 2x rendered 900.00x714.00px")

    def test_a_tiling_layer_with_explicit_pixel_size_keeps_the_exemption(self):
        # An explicit px tile still paints at the file's size, so it stays decoration.
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-grain]", (96, 96), (900, 714), data_uri=True,
                       repeat="repeat", size="96px 96px",
                       bundled={"key": "cb.asset.material.grain-night"}),
        ])
        verdict = self.judge(rec)
        self.assertTrue(verdict["ok"], verdict["problems"])
        self.assertFalse(verdict["backgrounds"][0]["ratio_judged"])

    def test_a_horizontally_tiled_strip_is_judged_on_height_only(self):
        # The shelf plank is `repeat-x` with `auto 100%`: 256 px wide at its own size, stretched to
        # the box height. Width is a real tile and is not judged; height is a box stretch and is.
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb3-shelf]", (256, 256), (870, 20),
                       repeat="repeat-x", size="auto 100%",
                       bundled={"key": "cb.asset.material.plank"}),
        ])
        verdict = self.judge(rec)
        layer = verdict["backgrounds"][0]
        self.assertEqual(layer["judged_axes"], ["y"])
        # 256 px of source for 20 px of paint is a downscale, not an upscale.
        self.assertTrue(verdict["ok"], verdict["problems"])

    def test_a_horizontally_tiled_strip_stretched_on_height_fails(self):
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb3-shelf]", (256, 64), (870, 300),
                       repeat="repeat-x", size="auto 100%",
                       bundled={"key": "cb.asset.material.plank"}),
        ])
        verdict = self.judge(rec)
        self.assertEqual(verdict["backgrounds"][0]["judged_axes"], ["y"])
        self.assert_fails_with(verdict, "natural 64px is below 2x rendered 300.00px (height axis)")

    def test_a_background_with_no_repeat_mode_is_judged_as_a_one_shot(self):
        # A record that predates the repeat field must not be treated as a tile by accident.
        rec = record("home", home_images(), backgrounds=[
            background("[data-cb-home-vignette]", (96, 96), (900, 714), repeat="", size="auto"),
        ])
        verdict = self.judge(rec)
        self.assertEqual(verdict["backgrounds"][0]["judged_axes"], ["x", "y"])
        self.assert_fails_with(verdict, "natural 96x96px is below 2x rendered 900.00x714.00px")

    def test_a_background_row_cannot_satisfy_a_display_role(self):
        # Four 2x cover plates delivered as CSS layers are still 0 of 4 rendered display covers.
        rec = record("home", home_images(cover_count=0), backgrounds=[
            background(f"[data-cb-cover={index}]", (1200, 800), (600, 400))
            for index in range(4)
        ])
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "required image missing: display_cover 0/4")


class TestEvidenceBacking(HarnessCase):
    """A required-role row counts only when its bytes are in the packet and match.

    Reproduced from review: four invented `cover_plate` rows (1728x1152 natural at 400 px rendered)
    plus an edited fox size flipped a failing `home--1344` cell to PASS with the PNG untouched,
    because the judge trusted every camera-reported number. The rows must now be backed by files.
    """

    def test_four_invented_cover_rows_cannot_flip_a_failing_cell_to_pass(self):
        backgrounds = [background("[data-cb-home-vignette]", (96, 96), (900, 714),
                                  repeat="repeat", size="cover",
                                  bundled={"key": "cb.asset.material.vignette"})]
        images = [row for row in home_images() if row["kind"] != "cover_plate"]
        rec = record("home", images, backgrounds=backgrounds)
        self.attach_evidence(rec)
        for index in range(4):
            rec["images"].append(
                image(f"[invented-cover-{index}] > img", "cover_plate", (1728, 1152), (400, 300))
            )
        verdict = self.judge(rec, attach=False)
        self.assertFalse(verdict["ok"])
        self.assert_fails_with(verdict, "no persisted image evidence")
        self.assert_fails_with(verdict, "required image missing: display_cover 0/4")

    def test_a_required_role_row_without_bytes_is_refused(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        rec["images"][0].pop("evidence")
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "no persisted image evidence")
        self.assert_fails_with(verdict, "required image missing: display_cover 3/4")

    def test_evidence_must_hash_to_the_row_sha256(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        (self.dir / rec["images"][0]["evidence"]["file"]).write_bytes(png_bytes(10, 10))
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "evidence sha256 does not match the row sha256")

    def test_evidence_image_must_decode_to_the_declared_natural_size(self):
        # The forged-pass shape: keep the real file, edit `natural` to the invented 1728x1152.
        rec = record("home", home_images())
        self.attach_evidence(rec)
        rec["images"][0]["natural"] = {"width": 1728, "height": 1152}
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(
            verdict,
            "evidence image is 1200x800px but the record claims natural 1728x1152px",
        )

    def test_evidence_must_be_a_readable_raster(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        row = rec["images"][0]
        (self.dir / row["evidence"]["file"]).unlink()
        data = b"not an image"
        digest = hashlib.sha256(data).hexdigest()
        (self.dir / f"evidence/{digest}.png").write_bytes(data)
        row["sha256"] = digest
        row["evidence"] = {"file": f"evidence/{digest}.png", "sha256": digest, "bytes": len(data)}
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "evidence file is not a readable raster")

    def test_evidence_file_must_live_under_evidence_in_the_cell(self):
        # Review repro: leave the PNG untouched and point every required-role row at it through
        # `evidence.file`; with no confinement this minted a PASS with zero new bytes.
        rec = record("home", home_images())
        self.attach_evidence(rec)
        for row in rec["images"]:
            row["evidence"]["file"] = "shot.png"
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "evidence file must live at evidence/<row sha256>.<ext>")
        self.assert_fails_with(verdict, "required image missing: display_cover 0/4")

    def test_an_absolute_evidence_path_is_refused(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        row = rec["images"][0]
        row["evidence"]["file"] = str(self.dir / row["evidence"]["file"])
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "evidence file must be relative to the cell")

    def test_a_parent_step_out_of_evidence_is_refused(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        row = rec["images"][0]
        name = Path(row["evidence"]["file"]).name
        row["evidence"]["file"] = f"evidence/../evidence/{name}"
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "evidence file must not step outside the cell")

    def test_evidence_file_name_must_be_the_row_sha256(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        row = rec["images"][0]
        bytes_ = (self.dir / row["evidence"]["file"]).read_bytes()
        renamed = f"evidence/{'0' * 64}.png"
        (self.dir / renamed).write_bytes(bytes_)
        row["evidence"]["file"] = renamed
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "evidence file name must be the row sha256")

    def test_evidence_may_not_be_the_cell_screenshot(self):
        # A row backed by the frame's own bytes proves nothing about the asset it claims to show.
        rec = record("home", home_images())
        self.attach_evidence(rec)
        row = rec["images"][0]
        blob = png_bytes(1200, 800, salt=99)
        digest = hashlib.sha256(blob).hexdigest()
        (self.dir / "shot.png").write_bytes(blob)
        rec["screenshot"]["sha256"] = digest
        (self.dir / f"evidence/{digest}.png").write_bytes(blob)
        row["sha256"] = digest
        row["evidence"] = {"file": f"evidence/{digest}.png", "sha256": digest, "bytes": len(blob)}
        verdict = vq.judge_cell(rec, self.dir, vq.press_plate_registry())
        self.assert_fails_with(verdict, "evidence bytes are the cell screenshot")

    def test_one_asset_cannot_satisfy_two_rows_of_the_same_role(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        covers = [row for row in rec["images"] if row["kind"] == "cover_plate"]
        first = covers[0]
        data = (self.dir / first["evidence"]["file"]).read_bytes()
        digest = first["sha256"]
        for row in covers[1:]:
            row["sha256"] = digest
            row["evidence"] = {"file": f"evidence/{digest}.png", "sha256": digest, "bytes": len(data)}
        verdict = self.judge(rec, attach=False)
        self.assert_fails_with(verdict, "required role display_cover counts the same image bytes 4 times")
        self.assert_fails_with(verdict, "required image missing: display_cover 1/4")

    def test_a_non_required_row_needs_no_backing(self):
        # A row that satisfies no required role on Home is judged on its numbers alone.
        rec = record("home", home_images())
        rec["images"].append(image("[data-cb-slot-cover=\"x\"] > img", "artifact_media",
                                   (1200, 800), (400, 300)))
        self.attach_evidence(rec)
        verdict = self.judge(rec, attach=False)
        self.assertTrue(verdict["ok"], verdict["problems"])


class TestBuildIdentity(HarnessCase):
    def test_a_cell_that_names_no_plugin_build_fails(self):
        rec = record("home", home_images())
        rec["window"].pop("plugin")
        verdict = self.judge(rec)
        self.assert_fails_with(verdict, "cell names no plugin build")

    def test_every_cell_in_a_capture_set_names_the_plugin_sha(self):
        """Acceptance item 5 is about *every* record, refusals included, not one judge call."""
        home = record("home", home_images())
        home["run"] = {"id": "run-a"}
        refused = record("design-system", [])
        refused["run"] = {"id": "run-a"}
        refused["surface"] = {"requested": "design-system", "resolved": None,
                              "missing": {"reason": "the installed plugin mounts no Design System surface"}}
        refused["route"]["present"] = False
        refused["screenshot"] = {"file": None, "sha256": None, "bytes": 0, "clip": None}
        for rec in (home, refused):
            self.attach_evidence(rec)
            self.persist(rec)
        manifest = vq.build_manifest(self.dir, destinations=("home", "design-system"), widths=(1344,))
        self.assertEqual(len(manifest["cells"]), 2)
        for cell in manifest["cells"]:
            self.assertTrue(cell["plugin"].get("sha256"), cell["cell"])
        self.assertEqual(len(manifest["plugin_sha256"]), 1)


class TestUnreadableRecords(HarnessCase):
    """Unparsable and unknown-schema records are named failures, not missing matrix cells."""

    def test_a_truncated_record_is_a_named_failure(self):
        good = record("home", home_images())
        self.attach_evidence(good)
        self.persist(good)
        (self.dir / "home--460.json").write_text('{"schema": "vq.capture.v1", "cell": {"name"')
        manifest = vq.build_manifest(self.dir, destinations=("home",), widths=(1344, 460))
        by_name = {cell["cell"]: cell for cell in manifest["cells"]}
        self.assertIn("home--460", by_name)
        self.assertFalse(by_name["home--460"]["ok"])
        self.assertIn("could not be parsed", " | ".join(by_name["home--460"]["problems"]))
        self.assertEqual(manifest["summary"]["not_captured"], 0)
        self.assertFalse(manifest["summary"]["ok"])

    def test_an_unknown_schema_record_is_a_named_failure(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        rec["schema"] = "vq.capture.v2"
        (self.dir / "home--1344.json").write_text(json.dumps(rec))
        manifest = vq.build_manifest(self.dir, destinations=("home",), widths=(1344,))
        cell = manifest["cells"][0]
        self.assertFalse(cell["ok"])
        self.assertIn("has schema 'vq.capture.v2'", " ".join(cell["problems"]))
        self.assertEqual(manifest["summary"]["cells"], 1)


class TestCaptureSetIdentity(HarnessCase):
    def test_two_capture_runs_invalidate_the_set(self):
        first = record("home", home_images())
        first["run"] = {"id": "run-a"}
        second = record("discover", [])
        second["run"] = {"id": "run-b"}
        for rec in (first, second):
            self.attach_evidence(rec)
            self.persist(rec)
        manifest = vq.build_manifest(self.dir)
        self.assertTrue(manifest["summary"]["mixed_run"])
        self.assertEqual(manifest["capture_runs"], ["run-a", "run-b"])
        for cell in manifest["cells"]:
            self.assertTrue(any("more than one capture run" in problem for problem in cell["problems"]))


class TestSubsetMatrix(HarnessCase):
    def test_a_subset_run_is_judged_against_the_requested_matrix(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        self.persist(rec)
        manifest = vq.build_manifest(self.dir, destinations=("home",), widths=(1344,))
        self.assertEqual(manifest["summary"]["matrix_cells"], 1)
        self.assertEqual(manifest["summary"]["not_captured"], 0)
        self.assertTrue(manifest["summary"]["ok"], manifest["cells"][0]["problems"])

    def test_a_frame_outside_the_requested_subset_is_not_attributed(self):
        rec = record("home", home_images())
        self.attach_evidence(rec)
        self.persist(rec)
        manifest = vq.build_manifest(self.dir, destinations=("home",), widths=(460,))
        self.assertEqual(manifest["summary"]["cells"], 0)
        self.assertEqual(manifest["summary"]["not_captured"], 1)

    def test_an_unreadable_record_outside_the_requested_subset_is_ignored(self):
        # Review: a truncated home--460.json made a --widths 1344 run report two cells and FAIL.
        rec = record("home", home_images())
        self.attach_evidence(rec)
        self.persist(rec)
        (self.dir / "home--460.json").write_text('{"schema": "vq.capture.v1", "cell": {"name"')
        manifest = vq.build_manifest(self.dir, destinations=("home",), widths=(1344,))
        self.assertEqual(manifest["summary"]["matrix_cells"], 1)
        self.assertEqual(manifest["summary"]["cells"], 1)
        self.assertEqual(manifest["summary"]["not_captured"], 0)
        self.assertTrue(manifest["summary"]["ok"], manifest["cells"][0]["problems"])


class TestRasterDimensions(HarnessCase):
    def test_reads_png_dimensions(self):
        path = self.dir / "x.png"
        path.write_bytes(png_bytes(1200, 800))
        self.assertEqual(vq.raster_dimensions(path), (1200, 800))

    def test_reads_webp_vp8l_dimensions(self):
        width, height = 256, 256
        bits = ((width - 1) | ((height - 1) << 14)).to_bytes(4, "little")
        body = b"VP8L" + struct.pack("<I", 5) + b"\x2f" + bits + b"\x00" * 5
        data = b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body
        path = self.dir / "x.webp"
        path.write_bytes(data)
        self.assertEqual(vq.raster_dimensions(path), (width, height))

    def test_rejects_a_truncated_file(self):
        path = self.dir / "x.webp"
        path.write_bytes(b"RIFF\xff\x00\x00\x00WEBPVP8 ")
        self.assertIsNone(vq.raster_dimensions(path))


class TestMatrix(HarnessCase):
    def test_missing_matrix_cells_are_named(self):
        self.judge(record("home", home_images()))
        manifest = vq.build_manifest(self.dir)
        self.assertEqual(len(manifest["missing_cells"]), len(vq.DESTINATIONS) * len(vq.WIDTHS) - 1)
        self.assertIn({"destination": "design-system", "width": 1344}, manifest["missing_cells"])
        self.assertFalse(manifest["summary"]["ok"])

    def test_a_failed_cell_is_not_counted_as_never_captured(self):
        # Reproduced from review: 16 captured-but-failing cells were reported as 24 "not captured".
        self.judge(record("home", home_images()))
        broken = record("discover", [])
        name = broken["cell"]["name"]
        (self.dir / f"{name}.json").write_text(json.dumps(broken))
        rec_shot = self.dir / "shot.png"
        rec_shot.write_bytes(b"png-bytes")
        broken["screenshot"]["sha256"] = hashlib.sha256(b"png-bytes").hexdigest()
        (self.dir / f"{name}.json").write_text(json.dumps(broken))

        manifest = vq.build_manifest(self.dir)
        summary = manifest["summary"]
        self.assertEqual(summary["cells"], 2)
        self.assertEqual(summary["captured"], 2)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["not_captured"], len(vq.DESTINATIONS) * len(vq.WIDTHS) - 2)
        self.assertEqual(summary["matrix_cells"], 24)
        self.assertFalse(summary["ok"])

    def test_the_packet_wording_separates_failed_from_never_captured(self):
        self.judge(record("home", home_images()))
        broken = record("discover", [])
        broken["screenshot"]["sha256"] = hashlib.sha256(b"png-bytes").hexdigest()
        (self.dir / f"{broken['cell']['name']}.json").write_text(json.dumps(broken))
        manifest = vq.build_manifest(self.dir)
        text = vq.render_markdown(manifest, self.dir)
        self.assertIn("1 passed / 1 failed / 22 never captured", text)
        self.assertIn("## Never captured", text)
        self.assertNotIn("matrix cells not captured", text)
        self.assertIn("- classroom at 1344px", text)

    def test_a_second_plugin_build_invalidates_the_set(self):
        first = record("home", home_images())
        second = record("discover", [image("[data-cb3-cover=art] > img", "cover_plate", (1200, 800), (600, 400))] * 8)
        second["window"]["plugin"]["sha256"] = "c" * 64
        for rec in (first, second):
            name = rec["cell"]["name"]
            (self.dir / f"{name}.json").write_text(json.dumps(rec))
        (self.dir / "shot.png").write_bytes(b"png-bytes")
        blob = hashlib.sha256(b"png-bytes").hexdigest()
        for rec in (first, second):
            rec["screenshot"]["sha256"] = blob
        # Re-persist after the sha is stamped.
        for rec in (first, second):
            (self.dir / f"{rec['cell']['name']}.json").write_text(json.dumps(rec))
        manifest = vq.build_manifest(self.dir)
        self.assertTrue(manifest["summary"]["mixed_build"])
        self.assertFalse(manifest["summary"]["ok"])
        for cell in manifest["cells"]:
            self.assertTrue(any("more than one plugin build" in problem for problem in cell["problems"]))

    def test_manifest_requires_every_destination_and_width(self):
        self.assertEqual(set(vq.DESTINATIONS), {
            "home", "discover", "course-home", "classroom", "world-studio", "design-system",
        })
        self.assertEqual(set(vq.WIDTHS), {1344, 1049, 900, 460})

    def test_fox_is_not_required_below_its_design_breakpoint(self):
        covers = [
            image("[data-cb3-cover=art] > img", "cover_plate", (1200, 800), (600, 400))
            for _ in range(4)
        ]
        verdict = self.judge(record("home", covers, width=460))
        self.assertTrue(verdict["ok"], verdict["problems"])
        fox = next(row for row in verdict["requirements"] if row["role"] == "fox_pose")
        self.assertTrue(fox["ok"])
        self.assertIn("not required at 460px", fox["skipped"])


class TestCameraStatic(unittest.TestCase):
    def test_camera_never_substitutes_a_proof_page(self):
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        self.assertIn("proof_markers", source)
        self.assertIn("proof_script", source)
        self.assertIn("the installed plugin mounts no Design System surface", source)
        self.assertNotIn("--fixture", source)
        self.assertNotIn("proof.html", source)

    def test_camera_reads_the_files_pixels_not_natural_width(self):
        # A srcSet candidate carries a density descriptor and `img.naturalWidth` is divided by it,
        # so a 512 px fox selected from `512 2x` in a 2x window reads 256 while the evidence bytes
        # are 512 and the judge refuses the row. The camera must record the file's own pixels.
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        self.assertIn("const intrinsicSize = async (url) => {", source)
        self.assertIn("intrinsic.width || naturalWidth", source)
        self.assertIn("intrinsic.height || naturalHeight", source)

    def test_camera_classifies_the_wide_home_cover(self):
        # CP-053 paints the wide Home's card covers with `data-cb-home-scene-cover`; a classifier
        # that only knew `data-cb3-cover` scored those two 1200x800 kit plates as `unknown`, so the
        # 1344 cell reported display_cover 0/4 on a surface that had painted both of them.
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        self.assertIn("data-cb-home-scene-cover=", source)
        self.assertIn("return 'cover_plate'", source)

    def test_camera_records_the_required_fields(self):
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        for field in ("selector", "current_src", "natural", "rendered", "sha256", "bundled_asset"):
            self.assertIn(field, source, field)
        self.assertIn("readPluginSource", source)
        # A background layer must carry both modes the judge needs: repeat says whether it tiles at
        # all, size says whether it tiles at its natural size or is scaled to the box.
        self.assertIn("background_repeat", source)
        self.assertIn("background_size", source)

    def test_camera_identifies_the_build_before_navigation(self):
        # A `missing_surface` refusal happens inside navigate(); the plugin sha must already be in
        # the record so the refusal names the build it was refused on.
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        self.assertLess(
            source.index("record.window.plugin = await readWindowPlugin"),
            source.index("const nav = await navigate"),
        )
        self.assertLess(source.index("record.page = await cdp.eval"), source.index("const nav = await navigate"))

    def test_camera_persists_required_role_bytes(self):
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        self.assertIn("evidenceKinds: EVIDENCE_KINDS", source)
        self.assertIn("row.evidence = { file: relative", source)
        self.assertIn("evidence/${digest}", source)
        self.assertIn("evidenceExtension(bytes)", source)

    def test_camera_names_evidence_from_the_bytes(self):
        """The judge accepts only `<sha>.<raster ext>`; the name must describe the real container.

        Executed, not string-matched: the function is lifted out of the camera and run against real
        magic bytes, because a URL extension is a claim the file does not have to honour.
        """
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        match = re.search(r"function evidenceExtension\(bytes\) \{.*?\n\}\n", source, re.S)
        assert match is not None
        harness = match.group(0) + """
const samples = [
  Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,0,0,0,0]),
  Buffer.concat([Buffer.from('RIFF'), Buffer.alloc(4), Buffer.from('WEBP')]),
  Buffer.from([0xff,0xd8,0xff,0xe0,0,0]),
  Buffer.from('GIF89a'),
  Buffer.from('<?xml version="1.0"?><svg/>'),
  Buffer.from([0,1,2,3,4,5,6,7]),
]
console.log(samples.map(evidenceExtension).join(','))
"""
        result = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), ".png,.webp,.jpg,.gif,.svg,.bin")

    def test_camera_evidence_kinds_match_the_judge(self):
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        match = re.search(r"const EVIDENCE_KINDS = \[(.*?)\]", source)
        assert match is not None
        camera_kinds = {token.strip().strip("'\"") for token in match.group(1).split(",") if token.strip()}
        self.assertEqual(camera_kinds, set(vq.evidence_kinds()))

    def test_camera_records_one_run_id_per_set(self):
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        self.assertIn("VQ_RUN_ID", source)
        self.assertIn("run: runId ?", source)
        script = (SCRIPTS / "vq-capture.sh").read_text()
        self.assertIn("export VQ_RUN_ID=", script)
        self.assertIn('--widths "$WIDTHS" --destinations "$DESTINATIONS"', script)

    def test_one_command_runs_the_judge(self):
        script = (SCRIPTS / "vq-capture.sh").read_text()
        self.assertIn("scripts/vq-manifest.py", script)
        self.assertIn("scripts/vq-library.py", script)
        self.assertIn("install-local.sh", script)
        self.assertIn("CONTACT", script.upper())

    def test_harness_does_not_edit_product_source(self):
        changed = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        protected = (
            "desktop/src/", "desktop/plugin.js", "desktop/cb-assets.generated.js",
            "coursebook/", "contracts/",
        )
        offenders = [
            line for line in changed.splitlines()
            if any(line.startswith(part) or f"/{part}" in f"/{line}" for part in protected)
        ]
        self.assertEqual(offenders, [], f"the harness must not modify product source: {offenders}")


class TestLibraryScript(unittest.TestCase):
    def test_library_never_fabricates_a_game_course(self):
        source = (SCRIPTS / "vq-library.py").read_text()
        self.assertIn("presentation_mode", source)
        self.assertIn("--allow-no-game", source)
        # It reports a missing Game course (exit 3); it must not write one.
        self.assertNotIn("INSERT INTO", source)
        self.assertNotIn("course.create", source)


if __name__ == "__main__":
    unittest.main()
