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
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cp-capture.mjs"
FIXTURES = ROOT / "tests" / "fixtures" / "cp-capture"
VALID_SHA = "a" * 64

STAMP_KEYS = {
    "stamp_version", "tool", "mode", "name", "captured_at", "ok", "gates", "plugin",
    "backend", "route", "console", "capture", "page_url", "zoom",
}
ROUTE_KEYS = {
    "selector", "marker", "width", "height", "theme", "text_scale_root_px", "reduced_motion",
    "forced_colors", "fonts_status", "images_total", "images_decoded", "host_slots",
    "host_overlays", "host_overlay_fraction", "content_width", "content_height",
    "content_rect", "html_background", "background_color", "v3_textures",
}
CAPTURE_KEYS = {"file", "sha256", "bytes", "clip", "crop_mode", "pixel_check"}
BACKEND_KEYS = {"url", "wire_version", "contract_methods", "implemented_count", "plugin_root"}
REQUIRED_GATES = {
    "plugin_sha_match", "route_present", "no_render_error", "fonts_loaded", "images_decoded",
    "no_host_overlay", "no_unpainted_region", "zoom_neutral",
}


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
        self.assertTrue(REQUIRED_GATES.issubset(stamp["gates"]), sorted(REQUIRED_GATES - set(stamp["gates"])))
        self.assertEqual(stamp["route"]["v3_textures"], "ready")
        self.assertEqual(stamp["console"]["key_warnings"], 0)
        self.assertTrue(ROUTE_KEYS.issubset(stamp["route"]), sorted(ROUTE_KEYS - set(stamp["route"])))
        self.assertTrue(CAPTURE_KEYS.issubset(stamp["capture"]))
        self.assertEqual(len(stamp["capture"]["sha256"]), 64)
        self.assertEqual(stamp["capture"]["crop_mode"], "route")
        self.assertIsNotNone(stamp["capture"]["pixel_check"])
        self.assertTrue(stamp["capture"]["pixel_check"]["ok"])
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

    def test_v3_texture_fallback_is_refused(self) -> None:
        # The route is present and the fonts settled, but the ground tiles never decoded. Stamping
        # that frame "ready" is the round-1 defect: the packet could not tell a painted ground from
        # a flat one.
        completed = run_capture(self.tmp, "v3-textures-fallback.html", "--require-v3")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "v3-textures-fallback.refused.json").read_text())
        self.assertFalse(refused["gates"]["v3_ready"])
        self.assertEqual(refused["route"]["v3_textures"], "fallback")
        self.assertTrue(any("textures" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "v3-textures-fallback.stamp.json").exists())

    def test_react_key_warning_is_refused(self) -> None:
        # Every visual gate passes; only the renderer's console says the tree is warning-noisy.
        completed = run_capture(self.tmp, "key-warning.html")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "key-warning.refused.json").read_text())
        self.assertFalse(refused["gates"]["no_react_key_warning"])
        self.assertTrue(any("key" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "key-warning.stamp.json").exists())

    def test_render_error_marker_is_refused(self) -> None:
        completed = run_capture(self.tmp, "render-error.html", "--require-v3")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "render-error.refused.json").read_text())
        self.assertFalse(refused["gates"]["no_render_error"])
        self.assertTrue(any("render-error" in reason for reason in refused["reasons"]))
        self.assertFalse(refused["gates"]["v3_ready"])


    def test_host_overlay_occlusion_is_refused(self) -> None:
        completed = run_capture(self.tmp, "host-overlay.html")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "host-overlay.refused.json").read_text())
        self.assertFalse(refused["gates"]["no_host_overlay"])
        self.assertTrue(any("occludes the route" in reason for reason in refused["reasons"]))
        self.assertTrue(refused["route"]["host_overlays"])
        overlay = refused["route"]["host_overlays"][0]
        self.assertIn("rect", overlay)
        self.assertIn("background", overlay)
        self.assertLess(refused["route"]["content_width"], refused["route"]["width"])
        # The route crop is also demonstrably unpainted: host background shows inside the clip.
        self.assertFalse(refused["gates"]["no_unpainted_region"])
        self.assertGreater(refused["route"]["host_overlay_fraction"], 0)
        self.assertFalse((self.tmp / "host-overlay.stamp.json").exists())
        self.assertFalse((self.tmp / "host-overlay.png").exists())

    def test_crop_to_content_excludes_and_records_overlay(self) -> None:
        completed = run_capture(self.tmp, "host-overlay.html", "--crop-to-content")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = json.loads((self.tmp / "host-overlay.stamp.json").read_text())
        self.assertEqual(stamp["capture"]["crop_mode"], "content")
        self.assertTrue(stamp["gates"]["no_host_overlay"])
        self.assertTrue(stamp["gates"]["host_overlay_excluded"])
        self.assertTrue(stamp["route"]["host_overlays"])
        self.assertLessEqual(stamp["route"]["content_width"], stamp["route"]["width"] - 70)
        self.assertLessEqual(stamp["route"]["content_height"], stamp["route"]["height"] - 50)
        self.assertAlmostEqual(stamp["capture"]["clip"]["width"], stamp["route"]["content_width"], delta=1.5)
        self.assertAlmostEqual(stamp["capture"]["clip"]["height"], stamp["route"]["content_height"], delta=1.5)
        self.assertEqual(stamp["capture"]["pixel_check"]["host_bg_fraction"], 0)
        self.assertTrue(stamp["capture"]["pixel_check"]["distinct_backgrounds"])
        png = self.tmp / stamp["capture"]["file"]
        self.assertTrue(png.is_file())

    def test_backend_block_shape_is_stamped(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), _RuntimeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            completed = run_capture(self.tmp, "ok.html", "--require-v3", "--backend-url", f"http://127.0.0.1:{port}")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = json.loads((self.tmp / "ok.stamp.json").read_text())
        self.assertTrue(BACKEND_KEYS.issubset(stamp["backend"]), sorted(BACKEND_KEYS - set(stamp["backend"])))
        self.assertEqual(stamp["backend"]["wire_version"], 24)
        self.assertEqual(stamp["backend"]["contract_methods"], 93)
        self.assertEqual(stamp["backend"]["implemented_count"], 93)
        self.assertEqual(stamp["backend"]["plugin_root"], "/tmp/cp000-checkout")


class _RuntimeHandler(BaseHTTPRequestHandler):
    payload = {
        "wire_contract": "cb.rpc",
        "wire_version": 24,
        "contract_methods": 93,
        "implemented_methods": [f"method.{index}" for index in range(93)],
        "plugin_root": "/tmp/cp000-checkout",
        "backend_package": "coursebook_plugin_backend",
    }

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        body = json.dumps(self.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - http.server API
        return


if __name__ == "__main__":
    unittest.main()
