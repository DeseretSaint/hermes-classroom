"""The v3 display face must reach the page, not just be declared.

The defect this guards against: the scope registers @font-face "CB Display" from a data
URL, but every heading writes the v2 OS stack inline, so the face stays `unloaded` and the
approved typography silently degrades to Georgia. These assertions fail the moment that
wiring is lost again.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "desktop" / "src" / "75-tokens.js"
SCOPE = ROOT / "desktop" / "src" / "76-v3-scope.js"
MODULE = ROOT / "desktop" / "plugin.js"


def _stack(source: str, name: str) -> str:
    match = re.search(rf"const {name} = '([^']+)'", source)
    assert match is not None, f"{name} is missing"
    return match.group(1)


class DisplayFaceWiringTest(unittest.TestCase):
    def test_serif_stack_prefers_the_scoped_display_face(self) -> None:
        stack = _stack(TOKENS.read_text(encoding="utf-8"), "CB_SERIF")
        self.assertIn("var(--cb3-font-display", stack,
                      "CB_SERIF must prefer the v3 display face before the OS stack")

    def test_sans_stack_prefers_the_scoped_ui_face(self) -> None:
        stack = _stack(TOKENS.read_text(encoding="utf-8"), "CB_SANS")
        self.assertIn("var(--cb3-font-ui", stack,
                      "CB_SANS must prefer the v3 UI face before the system stack")

    def test_scope_composes_both_faces_from_the_asset_segment(self) -> None:
        scope = SCOPE.read_text(encoding="utf-8")
        self.assertIn("CB3_V3_FAMILIES = Object.freeze(['CB Display', 'CB UI'])", scope)
        self.assertIn("function cbV3FontCss()", scope)
        self.assertIn("CB_ASSETS.fonts", scope,
                      "faces must come from the frozen asset segment, never hand-written URLs")
        self.assertIn("font-display: swap", scope)

    def test_shipped_module_carries_the_wiring(self) -> None:
        module = MODULE.read_text(encoding="utf-8")
        self.assertIn("var(--cb3-font-display", module,
                      "desktop/plugin.js was not rebuilt after the token change")
        self.assertIn("'CB Display'", module,
                      "the shipped module does not register the display family")
        self.assertGreaterEqual(module.count("data:font/woff2;base64,"), 2,
                                "both faces must ship as data URLs; the host cannot serve files")


if __name__ == "__main__":
    unittest.main()
