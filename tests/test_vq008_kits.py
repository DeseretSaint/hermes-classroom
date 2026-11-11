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

    def test_faked_quiet_field_fails(self):
        # The quiet-field block is a measurement, so --check must re-measure the band from the
        # shipped pixels instead of reading the numbers the manifest reports.
        kit = json.loads(self.original)
        qf = kit["roles"]["hero"][0]["provenance"]["measured"]["quiet_field"]
        for key in list(qf):
            if isinstance(qf[key], (int, float)) and not isinstance(qf[key], bool):
                qf[key] = 0
        qf["best_contrast"] = 99
        qf["contrast_p5_on_cream"] = 99
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("quiet field", out.stdout)
        KIT.write_text(self.original)

    def test_faked_derived_cover_derivation_fails(self):
        # The 4:5 row nests `derived_from` and is derived from the master's own crop. A sentence
        # naming a frame that was never used must fail, not sail through as untested prose.
        kit = json.loads(self.original)
        derived = [p for p in kit["roles"]["cover"] if "derived_from" in p][0]
        derived["provenance"]["derivation"] = (
            "centre crop of the cover-3x2 natural 40000x30000 frame to 2x2, resized to 640x800"
        )
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("4:5 derivation does not state the crop actually taken", out.stdout)
        KIT.write_text(self.original)

    def test_derived_crop_must_match_master_crop(self):
        kit = json.loads(self.original)
        derived = [p for p in kit["roles"]["cover"] if "derived_from" in p][0]
        derived["provenance"]["source_frame"]["frame"] = [40000, 30000]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("4:5 row names frame", out.stdout)
        KIT.write_text(self.original)

    def test_missing_resolution_fails(self):
        # build_cb_assets.py reads resolution[role].source for a full-bleed plate and stops when
        # it is absent, so a kit without it is not loadable and must not pass acceptance.
        kit = json.loads(self.original)
        del kit["resolution"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("no resolution block", out.stdout)
        KIT.write_text(self.original)

    def test_stale_generation_log_pin_fails(self):
        kit = json.loads(self.original)
        kit["generation_log"]["rows"] = kit["generation_log"]["rows"] + 1
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("generation_log row count is stale", out.stdout)
        KIT.write_text(self.original)

    def test_kernel_reference_as_role_fails(self):
        # A shared-kernel row is a reference into one kernel. Mounting it as a role would hand a
        # loader an out-of-kit path it cannot open; the judge must refuse that shape.
        kit = json.loads(self.original)
        kit["roles"]["frame"] = [dict(kit["kernel"]["assets"][0])]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("loader vocabulary", out.stdout)
        KIT.write_text(self.original)

    def test_role_path_outside_kit_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["path"] = "../../../assets/objects/clock.webp"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("resolves outside its own kit directory", out.stdout)
        KIT.write_text(self.original)

    def test_missing_kernel_refs_fails(self):
        kit = json.loads(self.original)
        del kit["kernel"]["assets"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("kernel.assets is missing", out.stdout)
        KIT.write_text(self.original)

    def test_kit_id_mismatch_fails(self):
        kit = json.loads(self.original)
        kit["kit_id"] = "workshop_manual@9"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("is not workshop_manual@1", out.stdout)
        KIT.write_text(self.original)


if __name__ == "__main__":
    unittest.main()
