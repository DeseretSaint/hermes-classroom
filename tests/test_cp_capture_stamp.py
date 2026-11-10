"""CP-000 — the capture stamp gate.

These tests exercise the real `scripts/cp-capture.mjs` refusal path against recorded fixture pages
(`tests/fixtures/cp-capture/*.html`). Each fixture page publishes the exact probe object a live
capture would read (`window.__CP000_FIXTURE__`), so the gate logic, the stamp schema and the exit
codes are tested without an Electron host. Chromium is used for the same `Page.captureScreenshot`
crop the live path uses; the tests skip when chromium or node is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cp-capture.mjs"
FIXTURES = ROOT / "tests" / "fixtures" / "cp-capture"
VALID_SHA = "a" * 64

STAMP_KEYS = {
    "stamp_version", "tool", "mode", "name", "captured_at", "ok", "gates", "plugin",
    "backend", "route", "console", "capture", "page_url",
}
ROUTE_KEYS = {
    "selector", "marker", "width", "height", "theme", "text_scale_root_px", "reduced_motion",
    "forced_colors", "fonts_status", "images_total", "images_decoded", "host_slots",
}
CAPTURE_KEYS = {"file", "sha256", "bytes", "clip"}


def run_capture(tmp: Path, fixture: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "node", str(SCRIPT), "--name", Path(fixture).stem, "--out", str(tmp),
            "--fixture", str(FIXTURES / fixture), "--expect-sha", VALID_SHA, *extra,
        ],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT),
    )


@unittest.skipUnless(shutil.which("node") and shutil.which("chromium"),
                     "node + chromium are required for the capture gate tests")
class CaptureStampTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cp000-stamp-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_fixture_writes_stamp_and_png(self) -> None:
        completed = run_capture(self.tmp, "ok.html", "--require-v3")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = json.loads((self.tmp / "ok.stamp.json").read_text())
        self.assertTrue(STAMP_KEYS.issubset(stamp), sorted(STAMP_KEYS - set(stamp)))
        self.assertTrue(stamp["ok"])
        self.assertEqual(stamp["plugin"]["window_sha256"], VALID_SHA)
        self.assertEqual(stamp["plugin"]["expected_sha256"], VALID_SHA)
        self.assertTrue(all(stamp["gates"].values()))
        self.assertTrue(ROUTE_KEYS.issubset(stamp["route"]), sorted(ROUTE_KEYS - set(stamp["route"])))
        self.assertTrue(CAPTURE_KEYS.issubset(stamp["capture"]))
        self.assertEqual(len(stamp["capture"]["sha256"]), 64)
        png = self.tmp / stamp["capture"]["file"]
        self.assertTrue(png.is_file())
        self.assertEqual(png.stat().st_size, stamp["capture"]["bytes"])
        self.assertFalse((self.tmp / "ok.refused.json").exists())

    def test_stale_module_is_refused(self) -> None:
        completed = run_capture(self.tmp, "stale-sha.html")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "stale-sha.refused.json").read_text())
        self.assertFalse(refused["ok"])
        self.assertFalse(refused["gates"]["plugin_sha_match"])
        self.assertTrue(any("stale module" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "stale-sha.stamp.json").exists())
        self.assertFalse((self.tmp / "stale-sha.png").exists())

    def test_unsettled_fonts_are_refused(self) -> None:
        completed = run_capture(self.tmp, "fonts-loading.html")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "fonts-loading.refused.json").read_text())
        self.assertFalse(refused["gates"]["fonts_loaded"])
        self.assertTrue(any("document.fonts.status" in reason for reason in refused["reasons"]))

    def test_undecoded_image_is_refused(self) -> None:
        completed = run_capture(self.tmp, "undecoded-image.html")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "undecoded-image.refused.json").read_text())
        self.assertFalse(refused["gates"]["images_decoded"])
        self.assertTrue(any("undecoded image" in reason for reason in refused["reasons"]))
        self.assertEqual(refused["route"]["images_decoded"], 0)

    def test_render_error_marker_is_refused(self) -> None:
        completed = run_capture(self.tmp, "render-error.html", "--require-v3")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "render-error.refused.json").read_text())
        self.assertFalse(refused["gates"]["no_render_error"])
        self.assertTrue(any("render-error" in reason for reason in refused["reasons"]))
        self.assertFalse(refused["gates"]["v3_ready"])


if __name__ == "__main__":
    unittest.main()
