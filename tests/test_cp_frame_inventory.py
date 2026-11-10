"""CP-000 — every committed review frame must be classified or explicitly unverifiable.

`docs/concept-parity/frame-inventory.json` is generated from the two review packets and their
manifests. The gate is simple: every PNG on disk is present in the inventory, every manifest row is
matched to a file, and anything without a manifest row carries a recorded reason and classification.
A frame with no provenance is exactly the defect CP-000 must make impossible to submit again.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cp-frame-inventory.py"
INVENTORY = ROOT / "docs" / "concept-parity" / "frame-inventory.json"
REPORT = ROOT / "docs" / "concept-parity" / "CP-000-RENDER.md"
ORPHAN = "home.course--460--light--200--continue.png"


def run_inventory(*extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(SCRIPT), *extra], capture_output=True, text=True, timeout=120, cwd=str(ROOT)
    )


class FrameInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = json.loads(INVENTORY.read_text())

    def test_committed_inventory_matches_disk_and_manifests(self) -> None:
        completed = run_inventory("--check")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("OK: frame inventory matches", completed.stdout)

    def test_gm_002_orphan_is_recorded_and_classified(self) -> None:
        packet = self.inventory["packets"]["gm-002"]
        self.assertEqual(packet["png_count"], 32)
        self.assertEqual(packet["manifest_row_count"], 31)
        self.assertEqual(packet["unlisted"], [ORPHAN])
        orphan = next(frame for frame in packet["frames"] if frame["file"] == ORPHAN)
        self.assertEqual(orphan["source"], "unlisted")
        self.assertEqual(orphan["classification"], "unverifiable")
        self.assertTrue(orphan["reason"])
        self.assertEqual(orphan["md5"], "39ac247b0a23264e13bcf13d17976ba7")
        # The report must name the unverifiable frame, not hide it behind a count.
        self.assertIn(ORPHAN, REPORT.read_text())

    def test_every_frame_is_classified(self) -> None:
        allowed = {"live-rig", "static-render", "unverifiable"}
        total = 0
        for packet_id, packet in self.inventory["packets"].items():
            self.assertTrue(packet["frames"], packet_id)
            for frame in packet["frames"]:
                total += 1
                self.assertIn(frame["classification"], allowed, f"{packet_id}/{frame['file']}")
                self.assertEqual(len(frame["md5"]), 32, frame["file"])
                if frame["source"] == "manifest":
                    self.assertTrue(frame["md5_matches_manifest"], f"{packet_id}/{frame['file']}")
        self.assertEqual(total, 76)

    def test_static_packet_frames_are_not_live_evidence(self) -> None:
        packet = self.inventory["packets"]["gm-002/renderer-frames"]
        self.assertEqual(packet["classification"], "static-render")
        self.assertIsNone(packet["manifest_sha256"])
        for frame in packet["frames"]:
            self.assertEqual(frame["classification"], "static-render")

    def test_gm_004_packet_is_fully_manifested_live_rig(self) -> None:
        packet = self.inventory["packets"]["gm-004"]
        self.assertEqual(packet["classification"], "live-rig")
        self.assertEqual(packet["png_count"], 42)
        self.assertEqual(packet["manifest_row_count"], 42)
        self.assertEqual(packet["unlisted"], [])
        self.assertEqual(packet["manifest_sha256"][:8], "5918cdff")

    def test_check_rejects_a_stale_inventory(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="cp000-inventory-"))
        try:
            stale = json.loads(INVENTORY.read_text())
            stale["packets"]["gm-004"]["frames"].pop()
            target = tmp / "frame-inventory.json"
            target.write_text(json.dumps(stale))
            completed = run_inventory("--check", "--out", str(target))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(completed.returncode, 1, completed.stdout)
        self.assertIn("stale", completed.stderr)


if __name__ == "__main__":
    unittest.main()
