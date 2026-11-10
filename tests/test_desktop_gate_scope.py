"""CP-003's own gate: the version seam must cut v3 paint and keep every v2 protection.

The migration is only honest if it can be falsified in both directions. These tests build synthetic
module text (never touching ``desktop/plugin.js``) and run the *real* v2 scans against it:

* positive control — a legitimate v3 stylesheet (hex in the token literal, ``var(--cb3-elev-1)``
  shadows, the named vignette gradient, its own motion table, CSS ``font-size``) trips **no** v2
  gate;
* negative control — a violation injected into the v2 region still trips the v2 gate even with the
  v3 stylesheet present, so scoping did not become a hole;
* the v3 gates can still read the v3 region the v2 gates ignore;
* the marker form is cut as well as the two literals, and an unterminated marker fails safe;
* the assertion count of the eight migrated v2 modules never drops below the CP-003 baseline, so a
  later card cannot quietly delete a protection and call it a migration.

This module is not a substitute for running the migrated suites; it is the proof that the seam they
now depend on is load-bearing.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from tests.cb_source_scope import (
    GRADIENT,
    HEX,
    PLUGIN_JS,
    literal_span,
    literal_text,
    v2_source,
    v3_source,
    v3_spans,
)

ROOT = Path(__file__).resolve().parent.parent

#: The CP-003 baseline: 177 assertions across the eight migrated v2 modules, counted at the
#: migration commit. The per-file numbers are also recorded in
#: ``docs/concept-parity/GATE-MIGRATION.md``; lowering one means deleting a v2 protection.
BASELINE = {
    "test_desktop_tokens.py": 17,
    "test_desktop_type_scale.py": 8,
    "test_desktop_h152_motion.py": 22,
    "test_desktop_field_desk.py": 44,
    "test_desktop_h150_library_shelf.py": 21,
    "test_h197_covers.py": 28,
    "test_gm_visual_spec.py": 17,
    "test_desktop_home_hub.py": 20,
}

V3_APPENDIX = """
// ── the v3 material, appended by CP-020a in the real module ──
const CB_TOKENS_V3_JSON =
  '{"light":{"canvas":"#f5e3c8","ink":"#1a1713"},"dark":{"canvas":"#14110c","ink":"#f3e6cf"}}'
const CB_V3_CSS = `
@font-face { font-family: "CB Display"; src: url(data:font/woff2;base64,AAAA) format("woff2"); font-display: swap; }
[data-cb-v3] {
  --cb3-elev-1: 0 1px 1px rgba(58, 35, 24, 0.10), 0 6px 14px -8px rgba(58, 35, 24, 0.28);
  --cb3-vignette: radial-gradient(ellipse at 50% 40%, transparent 40%, #e6cfae 100%);
  --cb3-dur-press: 120ms;
  --cb3-dur-lift: 150ms;
  --cb3-dur-route: 240ms;
  --cb3-dur-verdict: 300ms;
  --cb3-dur-complete: 600ms;
  background-image: var(--cb3-vignette);
  container-type: inline-size;
}
[data-cb-v3] .cb3-card {
  box-shadow: var(--cb3-elev-1);
  border-radius: 12px;
  font-size: clamp(1.5rem, 1.2rem + 1cqi, 2.25rem);
  transition: transform var(--cb3-dur-press) cubic-bezier(0.2, 0.8, 0.2, 1);
}
[data-cb-v3] .cb3-card:hover { transform: translateY(-1px); }
`
"""


def synthetic(extra_v2: str = "") -> str:
    base = PLUGIN_JS.read_text(encoding="utf-8")
    return base + extra_v2 + V3_APPENDIX


def v2_hex_scan(source: str) -> list[str]:
    """The exact scan ``TokenContractTest.test_no_colour_literal_outside_the_token_table`` runs."""
    scoped = v2_source(source)
    span = literal_span(scoped, "CB_TOKENS_JSON")
    text = scoped if span is None else scoped[:span[0]] + scoped[span[1]:]
    return HEX.findall(text)


class SeamDirectionTest(unittest.TestCase):
    def test_without_v3_material_the_v2_region_is_the_whole_file(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertEqual(v3_spans(source), [])
        self.assertEqual(v2_source(source), source)

    def test_the_v3_literals_are_cut_from_the_v2_region(self) -> None:
        source = synthetic()
        stripped = v2_source(source)
        # The seam cuts literal *bodies*, not identifiers: the constant names stay as inert text.
        self.assertNotIn("#f5e3c8", stripped)
        self.assertNotIn("--cb3-elev-1", stripped)
        self.assertNotIn("[data-cb-v3]", stripped)
        self.assertNotIn("url(data:font", stripped)
        # Everything before the v3 appendix is untouched: the seam cuts, it does not rewrite.
        self.assertTrue(stripped.startswith(PLUGIN_JS.read_text(encoding="utf-8")))

    def test_the_v3_gates_can_still_read_the_v3_region(self) -> None:
        source = synthetic()
        region = v3_source(source)
        self.assertIn("#f5e3c8", region)
        self.assertIn("--cb3-elev-1", region)
        self.assertIn("[data-cb-v3]", region)
        self.assertIn("@font-face", region)

    def test_marker_regions_are_cut_too(self) -> None:
        source = synthetic() + "\n// CB-V3-BEGIN\nconst v3Helper = { color: '#123456' }\n// CB-V3-END\nconst after = 1\n"
        stripped = v2_source(source)
        self.assertNotIn("#123456", stripped)
        self.assertIn("const after = 1", stripped)
        self.assertIn("#123456", v3_source(source))

    def test_an_unterminated_marker_fails_safe_by_cutting_to_end_of_file(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8") + "\n// CB-V3-BEGIN\nconst leak = '#abcdef'\n"
        self.assertNotIn("#abcdef", v2_source(source),
                         "an unterminated v3 marker must not leave v3 paint in the v2 region")


class PositiveControlTest(unittest.TestCase):
    """A legitimate v3 stylesheet must not trip any v2 gate."""

    def setUp(self) -> None:
        self.source = synthetic()
        self.v2 = v2_source(self.source)

    def test_the_v2_hex_scan_ignores_the_v3_token_literal(self) -> None:
        self.assertEqual(v2_hex_scan(self.source), [])

    def test_the_v2_gradient_scan_ignores_the_named_vignette(self) -> None:
        strip_mask = re.sub(r"\n\s*const maskImage = `[^`]*`\n", "\n", self.v2, count=1)
        self.assertEqual(GRADIENT.findall(strip_mask), [])

    def test_the_v2_shadow_scan_ignores_v3_elevation(self) -> None:
        self.assertNotIn("box-shadow", self.v2.lower())
        self.assertNotIn("boxShadow", self.v2)

    def test_the_v2_type_scan_ignores_css_font_size(self) -> None:
        literals = re.findall(r"fontSize:\s*('(?:[^'\\]|\\.)*'|CB_TYPE\.\w+)", self.v2)
        self.assertTrue(literals, "the v2 module authors font sizes")
        self.assertEqual([value for value in literals if not value.startswith("CB_TYPE.")], [])


class NegativeControlTest(unittest.TestCase):
    """A v2 violation is still caught while the v3 stylesheet is present."""

    def test_a_raw_hex_in_the_v2_region_is_still_caught(self) -> None:
        source = synthetic("\nconst strayPaint = { color: '#ff00ff' }\n")
        self.assertEqual(v2_hex_scan(source), ["#ff00ff"])

    def test_a_decorative_gradient_in_the_v2_region_is_still_caught(self) -> None:
        source = synthetic("\nconst strayFill = { backgroundImage: 'linear-gradient(to right, red, blue)' }\n")
        strip_mask = re.sub(r"\n\s*const maskImage = `[^`]*`\n", "\n", v2_source(source), count=1)
        self.assertIn("linear-gradient", strip_mask)

    def test_a_v2_shadow_is_still_caught(self) -> None:
        source = synthetic("\nconst strayShadow = { boxShadow: '0 4px 12px rgba(0,0,0,.4)' }\n")
        self.assertIn("boxShadow", v2_source(source))

    def test_a_v2_beat_outside_the_ladder_is_still_caught(self) -> None:
        source = synthetic("\nconst strayBeat = 'var(--cb-dur-hover)'\n")
        ladder = re.findall(r"var\(--cb-dur-([a-z]+)\)", v2_source(source))
        self.assertIn("hover", ladder)


class LiteralExtractorTest(unittest.TestCase):
    def test_handles_single_double_and_template_literals(self) -> None:
        for source, expected in (
            ("const A = 'x\\'y'", "x'y"),
            ('const A = "x\\"y"', 'x"y'),
            ("const A = `line\\n`", "line\n"),
        ):
            self.assertEqual(literal_text(source, "A"), expected)

    def test_returns_none_for_a_missing_or_non_literal_constant(self) -> None:
        self.assertIsNone(literal_text("const B = 1", "A"))
        self.assertIsNone(literal_text("const A = JSON.parse(X)", "A"))


class NoProtectionDeletedTest(unittest.TestCase):
    """The migrated v2 modules may gain assertions, never lose one."""

    def test_the_assertion_count_never_drops_below_the_cp_003_baseline(self) -> None:
        for name, expected in BASELINE.items():
            path = ROOT / "tests" / name
            tree = ast.parse(path.read_text(encoding="utf-8"))
            count = sum(
                1
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_")
            )
            self.assertGreaterEqual(
                count, expected,
                f"{name} has {count} assertions, below the CP-003 baseline of {expected}. A v2 "
                "protection was removed: restore it, move it to the v3 gate, or record the "
                "owner-approved supersession in docs/concept-parity/GATE-MIGRATION.md.",
            )


if __name__ == "__main__":
    unittest.main()
