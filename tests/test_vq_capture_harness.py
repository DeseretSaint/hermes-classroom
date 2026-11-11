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
import subprocess
import unittest
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
           fonts_ok: bool = True) -> dict:
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
        "backgrounds": [],
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


class HarnessCase(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def judge(self, rec: dict) -> dict:
        blob = b"png-bytes"
        (self.dir / "shot.png").write_bytes(blob)
        rec["screenshot"]["sha256"] = hashlib.sha256(blob).hexdigest()
        name = rec["cell"]["name"]
        (self.dir / f"{name}.json").write_text(json.dumps(rec))
        return vq.judge_cell(rec, self.dir, vq.press_plate_registry())

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


class TestMatrix(HarnessCase):
    def test_missing_matrix_cells_are_named(self):
        self.judge(record("home", home_images()))
        manifest = vq.build_manifest(self.dir)
        self.assertEqual(len(manifest["missing_cells"]), len(vq.DESTINATIONS) * len(vq.WIDTHS) - 1)
        self.assertIn({"destination": "design-system", "width": 1344}, manifest["missing_cells"])
        self.assertFalse(manifest["summary"]["ok"])

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

    def test_camera_records_the_required_fields(self):
        source = (SCRIPTS / "vq-capture.mjs").read_text()
        for field in ("selector", "current_src", "natural", "rendered", "sha256", "bundled_asset"):
            self.assertIn(field, source, field)
        self.assertIn("readPluginSource", source)

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
