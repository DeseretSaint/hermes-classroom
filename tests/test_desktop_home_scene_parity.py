"""CP-053 — the Home parity proof is the shipped component, and cannot drift from it.

`design/home-scene.html` is the page every recorded similarity is measured from. It is generated
by `scripts/gen-home-proof.py` from `desktop/plugin.js`, so this test re-runs the generator into a
temporary directory and fails when the committed page differs from a fresh render. That is the tie
the previous proof claimed but did not have: a hand-authored page could (and did) paint strings the
product never ships.

It also pins the recorded measurement to the module it was taken on, so a parity number measured
on an older module fails here instead of travelling into a release.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "design" / "home-scene.html"
MEASURE = ROOT / "docs" / "concept-parity" / "cp053" / "measure.json"
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

REFERENCE_STRINGS = (
    "Your field library",
    "Choose a course or start a new expedition.",
    "Start a new course",
    "Browse library",
    "New course",
)


def _node_modules_available() -> bool:
    import os

    candidates = [
        os.environ.get("HERMES_DESKTOP_APP"),
        str(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop"),
        str(Path.home() / ".hermes" / "hermes-agent"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        modules = Path(candidate) / "node_modules"
        if (modules / "react").is_dir() and (modules / "react-dom" / "server.js").is_file():
            return True
    return False


@unittest.skipIf(shutil.which("node") is None, "node is required to render the shipped module")
@unittest.skipIf(not _node_modules_available(), "react/react-dom are not installed beside the desktop app")
class HomeSceneProofTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        import sys

        sys.path.insert(0, str(ROOT))
        spec = importlib.util.spec_from_file_location("gen_home_proof", ROOT / "scripts" / "gen-home-proof.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.generator = module
        cls.committed = PROOF.read_text(encoding="utf-8")

    def test_the_committed_proof_is_a_fresh_render_of_the_shipped_module(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="cp053-parity-") as tmp:
            fresh = Path(tmp) / "home-scene.html"
            self.generator.render(fresh)
            rendered = fresh.read_text(encoding="utf-8")
        self.assertEqual(
            rendered,
            self.committed,
            "design/home-scene.html no longer matches a render of desktop/plugin.js; "
            "regenerate it with `python3 scripts/gen-home-proof.py`",
        )

    def test_the_proof_paints_the_scene_and_the_reference_strings(self) -> None:
        for hook in (
            'data-cb-home-scene=""',
            "data-cb-home-scene-question",
            "data-cb-home-scene-subline",
            "data-cb-home-scene-card",
            "data-cb-home-scene-plank-one",
            "data-cb-home-scene-plank-two",
            "data-cb-home-scene-tag",
            "data-cb-home-scene-clock",
            "data-cb-home-scene-fox",
        ):
            self.assertIn(hook, self.committed, f"the proof does not carry {hook}")
        for text in REFERENCE_STRINGS:
            self.assertIn(text, self.committed, f"the proof does not paint the reference string {text!r}")
        # The two typos in the owner's frame are corrected, never reproduced.
        for typo in ("Repir", "Bascics", "Astamamy"):
            self.assertNotIn(typo, self.committed)

    def test_the_recorded_measurement_names_the_module_it_was_taken_on(self) -> None:
        if not MEASURE.exists():
            self.skipTest("no CP-053 measurement is recorded yet")
        import hashlib

        recorded = json.loads(MEASURE.read_text(encoding="utf-8"))
        current = hashlib.sha256(PLUGIN_JS.read_bytes()).hexdigest()
        self.assertEqual(
            recorded.get("module_sha256"),
            current,
            "docs/concept-parity/cp053/measure.json was measured on a different module; re-measure it",
        )
        self.assertEqual(recorded.get("size"), [1344, 768], "a parity claim on a resized frame is not a claim")
        self.assertGreaterEqual(recorded.get("sim_grey", 0), 0)


if __name__ == "__main__":
    unittest.main()
