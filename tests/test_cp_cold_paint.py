"""CP-000 — the cold-paint baseline must carry module provenance.

`scripts/cp-cold-paint.mjs` is the source of the v3 performance baseline. A number that cannot be
tied to a module sha, a state dir, a backend contract and a theme is not a baseline, so the script
reads the module sha through the same in-window `readPluginSource` door the capture tool uses and
refuses to report a baseline when it does not match the checkout.

These tests run the real script in its fixture mode against a recorded page that stubs the two host
doors (`readPluginSource`, `zoom.get`); chromium is required.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cp-cold-paint.mjs"
FIXTURE = ROOT / "tests" / "fixtures" / "cp-capture" / "cold-paint.html"
MODULE_TEXT = "CP000 COLD PAINT FIXTURE MODULE TEXT"
GOOD_SHA = hashlib.sha256(MODULE_TEXT.encode()).hexdigest()
STALE_SHA = "b" * 64


def run_cold_paint(tmp: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "node", str(SCRIPT), "--fixture", str(FIXTURE), "--out", str(tmp / "cold.json"),
            "--loaded-plugin", "/tmp/fixture/plugin.js", *extra,
        ],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT),
    )


@unittest.skipUnless(shutil.which("node") and shutil.which("chromium"),
                     "node + chromium are required for the cold-paint tests")
class ColdPaintProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cp000-cold-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_baseline_carries_module_state_backend_theme_and_route(self) -> None:
        completed = run_cold_paint(self.tmp, "--runs", "2", "--expect-sha", GOOD_SHA)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        baseline = json.loads((self.tmp / "cold.json").read_text())
        self.assertTrue(baseline["ok"])
        self.assertEqual(baseline["plugin"]["window_sha256"], GOOD_SHA)
        self.assertEqual(baseline["plugin"]["expected_sha256"], GOOD_SHA)
        self.assertEqual(baseline["plugin"]["loaded_path"], "/tmp/fixture/plugin.js")
        self.assertIn("state_dir", baseline)
        self.assertEqual(baseline["theme"], "light")
        self.assertEqual(baseline["route_width"], 400)
        self.assertEqual(baseline["route_height"], 300)
        self.assertEqual(baseline["zoom_percent"], 100)
        self.assertIn("backend", baseline)
        self.assertEqual(len(baseline["samples"]), 2)
        self.assertIsNotNone(baseline["median_ms"])
        self.assertIn("median_ms", baseline)
        self.assertIn(baseline["median_ms"], [sample["ms"] for sample in baseline["samples"]])

    def test_stale_module_sha_refuses_to_report_a_baseline(self) -> None:
        completed = run_cold_paint(self.tmp, "--runs", "1", "--expect-sha", STALE_SHA)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        baseline = json.loads((self.tmp / "cold.json").read_text())
        self.assertFalse(baseline["ok"])
        self.assertEqual(baseline["plugin"]["window_sha256"], GOOD_SHA)
        self.assertEqual(baseline["plugin"]["expected_sha256"], STALE_SHA)
        self.assertIn("REFUSED", completed.stderr)


    def test_geometry_is_recorded_and_a_mismatch_refuses_the_timing(self) -> None:
        # A timing is only a comparison at the baseline's route width. The script records the
        # geometry and refuses a run whose route box does not match what the comparison expects.
        completed = run_cold_paint(self.tmp, "--runs", "1", "--expect-sha", GOOD_SHA,
                                   "--expect-route-width", "400")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = json.loads((self.tmp / "cold.json").read_text())
        self.assertTrue(record["geometry"]["matches"])
        self.assertEqual(record["geometry"]["expect_route_width"], 400)
        self.assertEqual(record["geometry"]["route_width"], 400)

        completed = run_cold_paint(self.tmp, "--runs", "1", "--expect-sha", GOOD_SHA,
                                   "--expect-route-width", "809")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        record = json.loads((self.tmp / "cold.json").read_text())
        self.assertFalse(record["ok"])
        self.assertFalse(record["geometry"]["matches"])
        self.assertIn("not comparable", completed.stderr)


if __name__ == "__main__":
    unittest.main()
