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
* the assertion count of the eight migrated v2 modules never drops below the CP-003 baseline, and
  neither does the count of ``assert*`` calls, so a later card cannot quietly delete a protection
  (or its assertion, keeping the method) and call it a migration.

This module is not a substitute for running the migrated suites; it is the proof that the seam they
now depend on is load-bearing.
"""

from __future__ import annotations

import ast
import re
import tempfile
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

#: This module is the proof the eight modules above were not weakened, so it needs its own pin:
#: the migrated-module BASELINE does not cover it, and deleting a seam claim would otherwise be
#: invisible. Additions are fine; a drop means a proof was removed.
SEAM_BASELINE = 24

#: CP-003 round 2 review defect D4: a *method* count cannot see a deleted assertion, so
#: ``test_no_colour_literal_outside_the_token_table`` could lose its ``assertEqual`` and stay green.
#: These are the ``assert*`` **call** counts per file, recomputed over the AST at base ``7a0841f``
#: (the eight migrated modules) and at ``d63b65d`` (this module, which had 38 at review time).
#: Additions are legal; a drop means a v2 protection was weakened even though its method survived.
ASSERT_BASELINE = {
    "test_desktop_tokens.py": 63,
    "test_desktop_type_scale.py": 16,
    "test_desktop_h152_motion.py": 96,
    "test_desktop_field_desk.py": 170,
    "test_desktop_h150_library_shelf.py": 99,
    "test_h197_covers.py": 81,
    "test_gm_visual_spec.py": 56,
    "test_desktop_home_hub.py": 103,
}
SEAM_ASSERT_BASELINE = 38


def assertion_calls(path: Path) -> int:
    """Count ``assert*`` call nodes anywhere in a module (``self.assertEqual``, ``assertRaises``...).

    Whole-module, not per-method: a protection may live in a helper a test calls, and the point of
    the pin is that bytes of checking cannot disappear while the module still imports.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else None
        )
        if name is not None and name.startswith("assert"):
            count += 1
    return count



def gate_is_armed() -> bool:
    """Read ``V3_REQUIRED`` from the v3 gate module at call time.

    Read dynamically, not imported by value: CP-020a flips the flag on its first commit, and the
    negative controls below temporarily arm it to prove the hand-off. A test that bound the value at
    import would keep asserting today's state forever.
    """
    import tests.test_desktop_tokens_v3 as v3_gate

    return bool(getattr(v3_gate, "V3_REQUIRED", False))

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


def v3_free_module() -> str:
    """The shipped module with CP-020a's two v3 literals and their declarations removed.

    The seam controls append their *own* v3 appendix. Starting from the shipped module would
    append a second literal, and ``literal_span`` reads only the first: the shipped one. The
    controls would then inspect the real stylesheet instead of the appendix and silently stop
    testing the seam (CP-020a's landing made that exact hole). The empty declarations are removed
    too, or the extractor stops at a declaration with no literal and reports ``None``.
    """
    stripped = v2_source(PLUGIN_JS.read_text(encoding="utf-8"))
    return re.sub(
        r"const (?:CB_TOKENS_V3_JSON|CB_V3_CSS)\s*=\s*(?=const|/\*)",
        "",
        stripped,
    )


def synthetic(extra_v2: str = "") -> str:
    return v3_free_module() + extra_v2 + V3_APPENDIX


def v2_hex_scan(source: str) -> list[str]:
    """The exact scan ``TokenContractTest.test_no_colour_literal_outside_the_token_table`` runs."""
    scoped = v2_source(source)
    span = literal_span(scoped, "CB_TOKENS_JSON")
    text = scoped if span is None else scoped[:span[0]] + scoped[span[1]:]
    return HEX.findall(text)


class SeamDirectionTest(unittest.TestCase):
    def test_without_v3_material_the_v2_region_is_the_whole_file(self) -> None:
        # Superseded the moment the gate is armed: CP-020a's compliant build *has* v3 material, and
        # this claim must not red it. The hand-off is a skip, not an edit — §6.1 (D1) forbids CP-020a
        # editing an assertion, and the converse test below keeps the skip from being a hole.
        if gate_is_armed():
            self.skipTest("V3_REQUIRED is True: v3 material is expected; the v3 gate owns this state")
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertEqual(v3_spans(source), [])
        self.assertEqual(v2_source(source), source)

    def test_v3_material_may_not_exist_while_the_gate_is_disarmed(self) -> None:
        # The mirror hole: with the flag False the v3 gate classes skip, so material that landed
        # ahead of the flip would be examined by nothing. This is the test that closes it.
        if gate_is_armed():
            self.skipTest("V3_REQUIRED is True: the gate is armed, so the v3 claims govern the material")
        spans = v3_spans(PLUGIN_JS.read_text(encoding="utf-8"))
        self.assertEqual(
            spans, [],
            "v3 material exists while V3_REQUIRED is False — the gate is disarmed: flip "
            "V3_REQUIRED in tests/test_desktop_tokens_v3.py and tests/test_v3_visual_audit.py",
        )

    def test_the_v3_literals_are_cut_from_the_v2_region(self) -> None:
        # The seam cuts literal *bodies* from the shipped module; everything before an appended
        # appendix must survive untouched.
        base = v3_free_module()
        source = base + V3_APPENDIX
        stripped = v2_source(source)
        # The seam cuts literal *bodies*, not identifiers: the constant names stay as inert text.
        self.assertNotIn("#f5e3c8", stripped)
        self.assertNotIn("--cb3-elev-1", stripped)
        self.assertNotIn("[data-cb-v3]", stripped)
        self.assertNotIn("url(data:font", stripped)
        # Everything before the v3 appendix is untouched: the seam cuts, it does not rewrite.
        self.assertTrue(stripped.startswith(base))

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


class SeamHandoffControlTest(unittest.TestCase):
    """The CP-020a hand-off, executed rather than asserted: arm the flag, replay the seam claims.

    Reviewer round 1, D1: the seam used to red a legitimate v3 build. These controls point the seam
    module and the v3 gate at the card's own contract-canonical compliant module in a temp dir and
    flip ``V3_REQUIRED`` in memory, so both directions of the hand-off are proven today:

    * armed + compliant build → the seam claims skip, they do not fail (CP-020a can go green);
    * disarmed + compliant build → the converse fails, naming the disarmed gate (material may not
      land ahead of the flip, which is the hole the old suite left).
    """

    def _run(self, method: str, source: str, armed: bool) -> None:
        import tests.test_desktop_gate_scope as scope
        import tests.test_desktop_tokens_v3 as gate

        with tempfile.TemporaryDirectory(prefix="coursebook-cb003-handoff-") as tmp:
            path = Path(tmp) / "plugin.js"
            path.write_text(source, encoding="utf-8")
            original_plugin, original_gate_plugin, original_armed = (
                scope.PLUGIN_JS, gate.PLUGIN_JS, gate.V3_REQUIRED,
            )
            scope.PLUGIN_JS = path
            gate.PLUGIN_JS = path
            gate.V3_REQUIRED = armed
            try:
                case = SeamDirectionTest(method)
                getattr(case, method)()
            finally:
                scope.PLUGIN_JS = original_plugin
                gate.PLUGIN_JS = original_gate_plugin
                gate.V3_REQUIRED = original_armed

    def _compliant_module(self) -> str:
        builder = V3GateBitesTest("test_a_compliant_v3_block_passes_every_gated_claim")
        return builder.module_text()

    def test_a_compliant_build_passes_the_seam_once_the_gate_is_armed(self) -> None:
        source = self._compliant_module()
        for method in (
            "test_without_v3_material_the_v2_region_is_the_whole_file",
            "test_v3_material_may_not_exist_while_the_gate_is_disarmed",
        ):
            with self.subTest(claim=method):
                with self.assertRaises(unittest.SkipTest):
                    self._run(method, source, True)

    def test_material_that_lands_before_the_flip_fails_loudly(self) -> None:
        with self.assertRaises(AssertionError) as caught:
            self._run("test_v3_material_may_not_exist_while_the_gate_is_disarmed",
                      self._compliant_module(), False)
        self.assertIn("disarmed", str(caught.exception))


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


class V3GateBitesTest(unittest.TestCase):
    """Run the **real** v3 gate against synthetic module text, good and bad.

    A gate that has only ever failed because the literal was absent has not shown it would catch a
    bad stylesheet. These controls point the real gate at a temporary module (never the product
    file), prove a compliant v3 block passes every gated claim, and prove each defect class trips
    the named assertion. The gate classes are skipped at import while ``V3_REQUIRED`` is False, so
    the controls call their bodies directly rather than through the test runner.
    """

    TOKEN_KEYS = ("modes", "elevation", "radii", "type", "motion")

    def good_css(self) -> str:
        return (
            '@font-face { font-family: "CB Display"; src: url(data:font/woff2;base64,AAAA) format("woff2"); font-display: swap; }\n'
            '@font-face { font-family: "CB UI"; src: url(data:font/woff2;base64,BBBB) format("woff2"); font-display: swap; }\n'
            "[data-cb-v3] {\n"
            "  --cb3-elev-1: 0 1px 1px rgba(58, 35, 24, 0.10), 0 6px 14px -8px rgba(58, 35, 24, 0.28);\n"
            "  --cb3-vignette: radial-gradient(ellipse at 50% 40%, transparent 40%, var(--cb3-canvas-edge) 100%);\n"
            "  --cb3-dur-press: 120ms;\n"
            "  --cb3-dur-lift: 150ms;\n"
            "  --cb3-dur-route: 240ms;\n"
            "  --cb3-dur-verdict: 300ms;\n"
            "  --cb3-dur-complete: 600ms;\n"
            "  background-image: var(--cb3-vignette);\n"
            "  container-type: inline-size;\n"
            "}\n"
            "[data-cb-v3] .cb3-card {\n"
            "  box-shadow: var(--cb3-elev-1);\n"
            "  font-family: var(--cb3-font-ui);\n"
            "  transition: opacity var(--cb3-dur-route);\n"
            "}\n"
            '[data-cb-v3] .cb3-title { font-family: "CB Display", Georgia, serif; }\n'
            "[data-cb-v3] .cb3-shelf { border-bottom: 1px solid var(--cb3-wood-edge); }\n"
        )

    def module_text(self, css: str | None = None, literal: str | None = None) -> str:
        import json

        from tests.cb_source_scope import v2_source

        contract = json.loads(
            (ROOT / "contracts" / "cb.tokens.v3.json").read_text(encoding="utf-8")
        )
        body = json.dumps(
            {key: contract[key] for key in self.TOKEN_KEYS},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        # A JS single-quoted literal must escape its backslashes; the extractor undoes exactly that.
        body = literal if literal is not None else body.replace("\\", "\\\\")
        # CP-020a ships the two v3 literals in the real module. Cut their declarations and values
        # before appending this control's own pair, or `literal_span` finds the shipped stylesheet
        # and the mutation is never seen (a control that silently stopped testing anything).
        import re

        stripped = re.sub(
            r"const (?:CB_TOKENS_V3_JSON|CB_V3_CSS)\s*=\s*(?=const|/\*)",
            "",
            v2_source(PLUGIN_JS.read_text(encoding="utf-8")),
        )
        return (
            stripped
            + "\nconst CB_TOKENS_V3_JSON =\n  '" + body + "'\n"
            + "const CB_V3_CSS = `\n" + (self.good_css() if css is None else css) + "\n`\n"
        )

    def run_gate(self, class_name: str, method: str, source: str) -> None:
        import tests.test_desktop_tokens_v3 as gate

        with tempfile.TemporaryDirectory(prefix="coursebook-v3gate-") as tmp:
            path = Path(tmp) / "plugin.js"
            path.write_text(source, encoding="utf-8")
            original = gate.PLUGIN_JS
            gate.PLUGIN_JS = path
            try:
                case = getattr(gate, class_name)(method)
                case.setUp()
                getattr(case, method)()
            finally:
                gate.PLUGIN_JS = original

    GATED = [
        ("V3TokenLiteralTest", "test_the_literal_equals_the_contract_byte_for_byte"),
        ("V3TokenLiteralTest", "test_hex_appears_only_in_the_two_token_literals"),
        ("V3TokenLiteralTest", "test_both_modes_carry_every_role_the_contract_declares"),
        ("V3StylesheetTest", "test_no_backdrop_filter_and_no_blur"),
        ("V3StylesheetTest", "test_the_stylesheet_is_not_a_stub"),
        ("V3StylesheetTest", "test_box_shadow_only_inside_the_stylesheet_and_only_as_elevation_tokens"),
        ("V3StylesheetTest", "test_the_only_gradient_is_the_named_vignette"),
        ("V3StylesheetTest", "test_every_selector_is_scoped_to_data_cb_v3_except_font_face"),
        ("V3StylesheetTest", "test_every_font_family_starts_with_cb"),
        ("V3StylesheetTest", "test_motion_durations_come_only_from_the_motion_table"),
        ("V3StylesheetTest", "test_no_looping_animation_or_keyframes"),
        ("V3StylesheetTest", "test_no_viewport_unit_on_the_v3_surface"),
    ]

    def test_a_compliant_v3_block_passes_every_gated_claim(self) -> None:
        source = self.module_text()
        for class_name, method in self.GATED:
            with self.subTest(claim=f"{class_name}.{method}"):
                self.run_gate(class_name, method, source)

    def test_each_defect_class_trips_the_named_claim(self) -> None:
        cases = [
            ("V3StylesheetTest", "test_no_backdrop_filter_and_no_blur",
             lambda css: css.replace("container-type: inline-size;", "backdrop-filter: saturate(1.2);")),
            ("V3StylesheetTest", "test_box_shadow_only_inside_the_stylesheet_and_only_as_elevation_tokens",
             lambda css: css.replace("box-shadow: var(--cb3-elev-1);", "box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);")),
            ("V3StylesheetTest", "test_the_only_gradient_is_the_named_vignette",
             lambda css: css.replace("border-bottom: 1px solid var(--cb3-wood-edge);",
                                     "background: linear-gradient(#fff, #000);")),
            ("V3StylesheetTest", "test_every_selector_is_scoped_to_data_cb_v3_except_font_face",
             lambda css: css.replace("[data-cb-v3] .cb3-shelf", ".cb3-shelf")),
            ("V3StylesheetTest", "test_every_font_family_starts_with_cb",
             lambda css: css.replace('font-family: "CB Display", Georgia, serif;', 'font-family: "Inter", sans-serif;')),
            ("V3StylesheetTest", "test_motion_durations_come_only_from_the_motion_table",
             lambda css: css.replace("transition: opacity var(--cb3-dur-route);", "transition: opacity 90ms;")),
            ("V3StylesheetTest", "test_no_looping_animation_or_keyframes",
             lambda css: css + "\n@keyframes cb3-spin { from { transform: rotate(0); } }\n"),
            ("V3StylesheetTest", "test_no_viewport_unit_on_the_v3_surface",
             lambda css: css.replace("container-type: inline-size;", "padding: 4vw;")),
            # D5: the same defect classes, spelled the way CSS actually allows. Property/function
            # names and units are ASCII case-insensitive and vendor prefixes paint, so a
            # case-sensitive string scan reported PASS on every one of these.
            ("V3StylesheetTest", "test_box_shadow_only_inside_the_stylesheet_and_only_as_elevation_tokens",
             lambda css: css.replace("box-shadow: var(--cb3-elev-1);",
                                     "-webkit-box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);")),
            ("V3StylesheetTest", "test_no_backdrop_filter_and_no_blur",
             lambda css: css.replace("container-type: inline-size;", "Backdrop-Filter: Blur(8px);")),
            ("V3StylesheetTest", "test_motion_durations_come_only_from_the_motion_table",
             lambda css: css.replace("transition: opacity var(--cb3-dur-route);",
                                     "transition: opacity 900MS;")),
            ("V3StylesheetTest", "test_no_looping_animation_or_keyframes",
             lambda css: css.replace("container-type: inline-size;", "ANIMATION: spin INFINITE;")),
        ]
        for class_name, method, mutate in cases:
            with self.subTest(claim=f"{class_name}.{method}"):
                with self.assertRaises(AssertionError):
                    self.run_gate(class_name, method, self.module_text(css=mutate(self.good_css())))

        # A drifted token value: one hex changed in the literal only.
        stale = self.module_text().replace('"canvas":"#f5e3c8"', '"canvas":"#f5e3c9"', 1)
        with self.subTest(claim="V3TokenLiteralTest drifted value"):
            with self.assertRaises(AssertionError):
                self.run_gate("V3TokenLiteralTest", "test_the_literal_equals_the_contract_byte_for_byte", stale)

    def test_css_number_spellings_trip_the_motion_and_vw_claims(self) -> None:
        # D6: CSS `<number>` is not only `\d+(\.\d+)?`. A leading dot (`.9s`) and scientific
        # notation (`1e3ms`) are legal spellings. A duration scan that cannot see them skips the
        # declaration entirely, so it is neither entered in the motion table nor listed as escaped
        # and the claim reports PASS on an out-of-table duration. `vw` reads the same grammar.
        cases = (
            ("test_motion_durations_come_only_from_the_motion_table",
             lambda css: css.replace("transition: opacity var(--cb3-dur-route);",
                                     "transition: opacity .9s;")),
            ("test_motion_durations_come_only_from_the_motion_table",
             lambda css: css.replace("transition: opacity var(--cb3-dur-route);",
                                     "transition: opacity 1e3ms;")),
            ("test_motion_durations_come_only_from_the_motion_table",
             lambda css: css.replace("transition: opacity var(--cb3-dur-route);",
                                     "transition-duration: .4s;")),
            ("test_no_viewport_unit_on_the_v3_surface",
             lambda css: css.replace("container-type: inline-size;", "padding: .5vw;")),
            # CP-003c (R1): a CSS unit is ASCII case-insensitive, so `100VW` is the same legal
            # viewport measurement as `100vw`. The numeric grammar was shared after D6 but `VW` had
            # no `re.I`, so every uppercase spelling was invisible to the scan and this claim
            # reported PASS on a declaration a browser paints.
            ("test_no_viewport_unit_on_the_v3_surface",
             lambda css: css.replace("container-type: inline-size;", "padding: 100VW;")),
            ("test_no_viewport_unit_on_the_v3_surface",
             lambda css: css.replace("container-type: inline-size;", "padding: 100Vw;")),
            ("test_no_viewport_unit_on_the_v3_surface",
             lambda css: css.replace("container-type: inline-size;", "padding: 1E3VW;")),
        )
        good = self.good_css()
        for method, mutate in cases:
            css = mutate(good)
            with self.subTest(claim=method, mutation=css):
                self.assertNotEqual(css, good, "the mutation did not apply")
                with self.assertRaises(AssertionError):
                    self.run_gate("V3StylesheetTest", method, self.module_text(css=css))

    def test_signed_viewport_measurements_trip_the_vw_claim(self) -> None:
        # CP-003d: a CSS `<number>` may carry a leading sign, so `margin: -2vw` is a declaration a
        # browser paints. The shared grammar had no `[+-]?` and the negative lookbehind excludes
        # `-`, so the `2vw` inside `-2vw` was never matched and both the gate and V-12 reported
        # PASS. The sign must not become a false positive: a bare `-2`, another unit, or an
        # identifier whose `-` is part of the name (`x-2vw`) is not a viewport measurement.
        positives = (
            "margin: -2vw;",
            "margin: -2VW;",
            "margin: -0.5VW;",
            "margin: -1e3vw;",
            "margin: +2vw;",
            "margin: calc(-2vw + 1px);",
        )
        good = self.good_css()
        for declaration in positives:
            css = good.replace("container-type: inline-size;", declaration)
            with self.subTest(declaration=declaration):
                self.assertNotEqual(css, good, "the mutation did not apply")
                with self.assertRaises(AssertionError):
                    self.run_gate("V3StylesheetTest",
                                  "test_no_viewport_unit_on_the_v3_surface",
                                  self.module_text(css=css))

        negatives = (
            "margin: -2;",
            "margin: -2px;",
            "--gap-2vw: 4px;",
            "grid-column: x-2vw;",
        )
        for declaration in negatives:
            css = good.replace("container-type: inline-size;", declaration)
            with self.subTest(control=declaration):
                self.assertNotEqual(css, good, "the mutation did not apply")
                self.run_gate("V3StylesheetTest",
                              "test_no_viewport_unit_on_the_v3_surface",
                              self.module_text(css=css))
        with self.subTest(control="selector .x-2vw"):
            self.run_gate("V3StylesheetTest", "test_no_viewport_unit_on_the_v3_surface",
                          self.module_text(css=good + "[data-cb-v3] .x-2vw { color: red; }\n"))

    def test_the_sign_applies_to_viewport_measurements_only(self) -> None:
        # CP-003d, required outcome 2: deliberate decision. A negative duration is invalid CSS and
        # never paints, so DURATION keeps the unsigned shared number; a signed viewport measurement
        # is legal and paints, so VW composes the same number with an optional sign. Pinning both
        # directions stops a later card from "unifying" the sign onto durations (turning a
        # non-painting declaration into a failure) or from dropping it from VW again.
        from tests.cb_source_scope import DURATION, VW

        for text in ("-2vw", "-2VW", "-0.5VW", "-1e3vw", "+2vw", "calc(-2vw + 1px)"):
            with self.subTest(positive=text):
                self.assertIsNotNone(VW.search(text), f"VW cannot see {text!r}")
        for text in ("x-2vw", ".x-2vw", "--gap-2vw", "margin: -2;", "margin: -2px;"):
            with self.subTest(control=text):
                self.assertIsNone(VW.search(text), f"VW false-positives on {text!r}")
        self.assertIsNotNone(DURATION.search("900MS"),
                             "DURATION lost its case-insensitive unit")
        self.assertIsNone(DURATION.search("-0.9s"),
                          "DURATION must stay unsigned: a negative duration never paints")

    def test_a_marker_region_cannot_smuggle_a_shadow_or_a_gradient(self) -> None:
        # Reviewer round 1, D3: a CB-V3-BEGIN…END region is cut from the v2 region, so exempting
        # it from the v3 paint scans as well would leave its content in no gate at all. Only the
        # shipped CB_V3_CSS literal may carry these declarations.
        cases = (
            ("const cb3Glow = `[data-cb-v3] { box-shadow: 0 0 24px rgba(0, 0, 0, 0.4); }`",
             "V3StylesheetTest",
             "test_box_shadow_only_inside_the_stylesheet_and_only_as_elevation_tokens"),
            ("const cb3Wash = `[data-cb-v3] { background-image: linear-gradient(120deg, #ffffff, #000000); }`",
             "V3StylesheetTest",
             "test_the_only_gradient_is_the_named_vignette"),
        )
        for body, class_name, method in cases:
            source = self.module_text() + "\n// CB-V3-BEGIN\n" + body + "\n// CB-V3-END\n"
            with self.subTest(claim=method):
                with self.assertRaises(AssertionError):
                    self.run_gate(class_name, method, source)

    def test_a_raw_hex_in_the_stylesheet_is_caught(self) -> None:
        css = self.good_css().replace("border-bottom: 1px solid var(--cb3-wood-edge);",
                                      "border-bottom: 1px solid #a5763f;")
        with self.assertRaises(AssertionError):
            self.run_gate("V3TokenLiteralTest", "test_hex_appears_only_in_the_two_token_literals",
                          self.module_text(css=css))


class NoProtectionDeletedTest(unittest.TestCase):
    """The migrated v2 modules may gain assertions, never lose one."""

    def test_the_seam_proof_itself_never_loses_a_claim(self) -> None:
        # The eight-module BASELINE does not cover this module; without a pin, deleting a seam
        # claim would leave the migration's own proof unguarded.
        path = ROOT / "tests" / "test_desktop_gate_scope.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count = sum(
            1
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            for item in node.body
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_")
        )
        self.assertGreaterEqual(
            count, SEAM_BASELINE,
            f"test_desktop_gate_scope.py has {count} claims, below the CP-003 seam baseline of "
            f"{SEAM_BASELINE}. Restore the deleted seam proof or record an owner-approved reason.",
        )

    def test_the_seam_proof_itself_never_loses_an_assertion(self) -> None:
        # D4 for this module: a claim can survive while its assertion is deleted, so the proof
        # module needs the same assertion-call floor the eight migrated modules get. 38 at d63b65d.
        path = ROOT / "tests" / "test_desktop_gate_scope.py"
        count = assertion_calls(path)
        self.assertGreaterEqual(
            count, SEAM_ASSERT_BASELINE,
            f"test_desktop_gate_scope.py has {count} assert* calls, below the CP-003 seam "
            f"baseline of {SEAM_ASSERT_BASELINE}. A seam proof was weakened without deleting a "
            "method: restore the assertion or record an owner-approved reason.",
        )

    def test_the_claim_count_never_drops_below_the_cp_003_baseline(self) -> None:
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
                f"{name} has {count} test claims, below the CP-003 baseline of {expected}. A v2 "
                "protection was removed: restore it, move it to the v3 gate, or record the "
                "owner-approved supersession in docs/concept-parity/GATE-MIGRATION.md.",
            )

    def test_the_assertion_calls_never_drop_below_the_cp_003_baseline(self) -> None:
        # D4 (cbqa round 2): the method count above cannot see "delete the assert, keep the
        # method". The cheapest way to weaken a v2 gate must fail here, on this pin, not pass.
        for name, expected in ASSERT_BASELINE.items():
            path = ROOT / "tests" / name
            count = assertion_calls(path)
            self.assertGreaterEqual(
                count, expected,
                f"{name} has {count} assert* calls, below the CP-003 baseline of {expected}. An "
                "assertion was deleted while its test method survived: restore it, move it to the "
                "v3 gate, or record the owner-approved supersession in "
                "docs/concept-parity/GATE-MIGRATION.md §4.",
            )


if __name__ == "__main__":
    unittest.main()
