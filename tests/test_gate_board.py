"""GM-016 D1: `board.py` must read a real capture stamp, not the legacy key it never wrote.

`scripts/cp-capture.mjs` records the route box at `stamp.capture.clip`; before this fix the board
builder only looked at `stamp["clip"]`, so every genuine frame fell through to a refusal that
claimed the stamp file was missing.  These tests pin the reader, the two refusal reasons being
distinguishable and true, and the E2 module-sha gate (the same comparison `coverage.py` makes:
sha256 of ``desktop/plugin.js`` against ``plugin.window_sha256``).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "docs" / "concept-parity" / "gate" / "board.py"
MODULE = ROOT / "desktop" / "plugin.js"

# A 1049x1166 route at the rig's device scale of 2 — the shape every real cp-capture PNG has.
FRAME_W, FRAME_H = 1049, 1166
DEVICE_SCALE = 2
CLIP = {"x": 260, "y": 34, "width": FRAME_W, "height": FRAME_H}


def module_sha() -> str:
    return hashlib.sha256(MODULE.read_bytes()).hexdigest()


def run_board(product: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(BOARD),
            "--screen",
            "R-CLASS",
            "--product",
            str(product),
            "--out",
            str(out),
            "--dry-run",
            *extra,
        ],
        capture_output=True,
        text=True,
    )


def plan_of(stdout: str) -> dict:
    head = stdout.split("delegating:")[0].strip()
    return json.loads(head)


class BoardStampTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="gate-board-test-")
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def frame(self, name: str = "frame") -> Path:
        path = self.tmp / f"{name}.png"
        Image.new("RGB", (FRAME_W * DEVICE_SCALE, FRAME_H * DEVICE_SCALE), (20, 17, 12)).save(path)
        return path

    def stamp(self, product: Path, body: dict) -> None:
        product.with_suffix(".stamp.json").write_text(json.dumps(body, indent=2) + "\n")

    def test_capture_clip_resolves_geometry(self):
        product = self.frame()
        self.stamp(
            product,
            {"ok": True, "plugin": {"window_sha256": module_sha()}, "capture": {"clip": dict(CLIP)}},
        )
        result = run_board(product, self.tmp / "board.png")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = plan_of(result.stdout)
        # The PNG is the clip rectangle: the route box inside it starts at (0, 0).
        self.assertEqual(plan["product_box_css"], [0, 0, FRAME_W, FRAME_H])
        self.assertEqual(plan["device_scale"], DEVICE_SCALE)
        self.assertEqual(plan["stamp_sha"], module_sha())
        self.assertFalse((self.tmp / "board.png").exists(), "a dry run must write nothing")

    def test_legacy_top_level_clip_still_works(self):
        product = self.frame("legacy")
        self.stamp(product, {"ok": True, "plugin": {"window_sha256": module_sha()}, "clip": dict(CLIP)})
        result = run_board(product, self.tmp / "board.png")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plan_of(result.stdout)["product_box_css"], [0, 0, FRAME_W, FRAME_H])

    def test_capture_clip_wins_over_legacy_clip(self):
        product = self.frame("both")
        self.stamp(
            product,
            {
                "ok": True,
                "plugin": {"window_sha256": module_sha()},
                "clip": {"x": 9, "y": 9, "width": 400, "height": 400},
                "capture": {"clip": dict(CLIP)},
            },
        )
        result = run_board(product, self.tmp / "board.png")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(plan_of(result.stdout)["product_box_css"], [0, 0, FRAME_W, FRAME_H])

    def test_missing_stamp_names_the_missing_stamp(self):
        product = self.frame("no-stamp")
        result = run_board(product, self.tmp / "board.png")
        self.assertEqual(result.returncode, 2)
        self.assertIn("has no .stamp.json", result.stderr)
        self.assertNotIn("records no capture.clip", result.stderr)

    def test_stamp_without_clip_does_not_claim_the_stamp_is_missing(self):
        product = self.frame("no-clip")
        self.stamp(product, {"ok": True, "plugin": {"window_sha256": module_sha()}})
        result = run_board(product, self.tmp / "board.png")
        self.assertEqual(result.returncode, 2)
        self.assertIn("records no capture.clip", result.stderr)
        self.assertNotIn("has no .stamp.json", result.stderr)

    def test_wrong_module_sha_is_refused_as_e2(self):
        product = self.frame("wrong-sha")
        other = "ab" * 32
        self.stamp(
            product,
            {"ok": True, "plugin": {"window_sha256": other}, "capture": {"clip": dict(CLIP)}},
        )
        result = run_board(product, self.tmp / "board.png")
        self.assertEqual(result.returncode, 2)
        self.assertIn("RUBRIC-V3 E2", result.stderr)
        self.assertIn(other, result.stderr)
        self.assertIn(module_sha(), result.stderr)

    def test_stamp_without_module_sha_is_refused(self):
        product = self.frame("no-sha")
        self.stamp(product, {"ok": True, "plugin": {}, "capture": {"clip": dict(CLIP)}})
        result = run_board(product, self.tmp / "board.png")
        self.assertEqual(result.returncode, 2)
        self.assertIn("records no plugin.window_sha256", result.stderr)


if __name__ == "__main__":
    unittest.main()
