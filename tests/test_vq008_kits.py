"""VQ-008 — the kit judge must pass the shipped kits and fail a broken claim.

The rule this file enforces: `--check` passing means nothing if the judge cannot fail. Each mutation
below breaks one load-bearing claim in a copy of `workshop_manual/kit.json`, runs the real judge,
and requires a non-zero exit; the shipped manifest is restored before the test ends.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vq008-kits.py"
KIT = ROOT / "assets" / "visual-kits" / "workshop_manual" / "kit.json"
GRAMMAR = "workshop_manual"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT
    )


class KitJudge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = KIT.read_text()

    @classmethod
    def tearDownClass(cls):
        KIT.write_text(cls.original)

    def _check(self) -> subprocess.CompletedProcess:
        return run("--check-one", GRAMMAR)

    def test_every_grammar_passes(self):
        out = run("--check")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("8 grammars", out.stdout)
        self.assertIn("every claim re-derived", out.stdout)

    def test_tampered_hash_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["hero"][0]["sha256"] = "0" * 64
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("sha256 is stale", out.stdout)
        KIT.write_text(self.original)

    def test_pack_cover_fallback_fails(self):
        kit = json.loads(self.original)
        kit["fallbacks"]["cover"] = ["course-master", "pack-cover"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("forbidden step", out.stdout)
        KIT.write_text(self.original)

    def test_grammar_drift_fails(self):
        kit = json.loads(self.original)
        kit["palette"]["ochre"] = "#000000"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("palette drifted from the grammar table", out.stdout)
        KIT.write_text(self.original)

    def test_faked_cover_ratio_fails(self):
        kit = json.loads(self.original)
        master = [p for p in kit["roles"]["cover"] if "derived_from" not in p][0]
        master["provenance"]["source_frame"]["ratios"]["natural_vs_shipped"] = 9.99
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("cover ratio natural_vs_shipped", out.stdout)
        KIT.write_text(self.original)

    def test_placeholder_name_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["path"] = "section/placeholder.png"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("missing", out.stdout)
        KIT.write_text(self.original)


if __name__ == "__main__":
    unittest.main()
