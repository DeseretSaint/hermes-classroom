"""The v3 material gate: every claim CP-002's contract makes, checked against the shipped module.

``contracts/cb.tokens.v3.json`` is the v3 visual contract. CP-003 does not build any v3 surface —
CP-020a does — so this module is written as the TDD hand-off: the claims are executable today, the
v3 literals are absent today, and ``V3_REQUIRED`` keeps the suite green until the card that owns
``desktop/plugin.js`` deliberately flips it.

**The hand-off contract.** CP-020a's first commit sets ``V3_REQUIRED = True`` and nothing else.
The tests below then fail for exactly the reason the card needs: there is no ``CB_TOKENS_V3_JSON``
and no ``CB_V3_CSS`` yet. CP-020a implements the stylesheet until they pass. If the flag is flipped
without the literals, ``test_the_gate_is_armed_only_when_the_v3_material_exists`` fails first with
the same message, so the RED is never mistaken for a broken test.

What this proves when the material exists:

  * ``CB_TOKENS_V3_JSON`` carries the contract byte for byte (canonical serialization, every top
    level key it carries equal to the contract, and ``modes`` / ``elevation`` / ``radii`` / ``type``
    / ``motion`` all present);
  * hex appears only inside the two token literals — v2's and v3's — and nowhere else in the file;
  * ``box-shadow`` appears only inside ``CB_V3_CSS`` and only as ``var(--cb3-elev-*)``;
  * no ``backdrop-filter`` and no ``blur(`` anywhere;
  * the only gradient is the named vignette, declared on a ``--cb3-vignette*`` custom property;
  * every selector in ``CB_V3_CSS`` starts with ``[data-cb-v3]`` except ``@font-face``;
  * every ``@font-face`` family name starts with ``CB ``, and every literal ``font-family``
    declaration names a ``CB `` family first;
  * every duration in ``CB_V3_CSS`` is a ``--cb3-dur-*`` table entry whose value equals the
    contract's motion table, and no animation/keyframes/infinite loop exists;
  * no ``vw`` unit on a v3 surface (SPEC-V3 §3.1: route-relative, never viewport-relative).

What this does NOT prove: that the stylesheet paints correctly in a browser, that contrast holds on
real pixels, or that a screen uses the stylesheet. Those are ``scripts/v3-audit.py`` (contract
gates + painted frames once surfaces exist) and the reviewer's captures.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.cb_source_scope import (
    DURATION,
    GRADIENT,
    HEX,
    PLUGIN_JS,
    ROOT,
    TOKEN_LITERAL_CONSTS,
    V3_CSS_CONST,
    V3_TOKEN_CONST,
    css_blocks,
    declarations,
    literal_span,
    literal_text,
    split_selectors,
    style_rules,
    v3_spans,
    without_shelf_edge_mask,
)

#: CP-020a flips this to True as its first commit, watches the gate go red, then builds until it
#: is green. Nothing else in this file changes on the flip.
V3_REQUIRED = False

CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
REQUIRED_TOP_LEVEL = ("modes", "elevation", "radii", "type", "motion")


def contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def plugin_source() -> str:
    return PLUGIN_JS.read_text(encoding="utf-8")


def canonical(value: object) -> str:
    """The one serialization the module must carry: compact, order-preserving, UTF-8."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def v3_tokens() -> dict:
    text = literal_text(plugin_source(), V3_TOKEN_CONST)
    if text is None:
        raise AssertionError(
            f"desktop/plugin.js has no {V3_TOKEN_CONST} literal — CP-020a builds it from "
            "contracts/cb.tokens.v3.json"
        )
    return json.loads(text)


def v3_css() -> str:
    text = literal_text(plugin_source(), V3_CSS_CONST)
    if text is None:
        raise AssertionError(
            f"desktop/plugin.js has no {V3_CSS_CONST} stylesheet — CP-020a adds the "
            "[data-cb-v3] style scope"
        )
    return text


class V3ContractFixtureTest(unittest.TestCase):
    """Ungated: the contract this gate enforces is well formed before any surface exists."""

    def setUp(self) -> None:
        self.contract = contract()

    def test_the_contract_is_version_three_with_eighteen_roles(self) -> None:
        self.assertEqual(self.contract["version"], 3)
        roles = self.contract["roles"]
        self.assertEqual(len(roles), 18, roles)
        self.assertEqual(len(set(roles)), 18, "a role name is duplicated")
        for mode in ("light", "dark"):
            self.assertEqual(set(self.contract["modes"][mode]), set(roles), mode)

    def test_every_role_value_is_a_six_digit_hex(self) -> None:
        for mode, palette in self.contract["modes"].items():
            for role, value in palette.items():
                self.assertRegex(value, r"^#[0-9a-f]{6}$", f"{mode}.{role}")

    def test_the_motion_table_stays_inside_its_own_ceiling(self) -> None:
        motion = self.contract["motion"]
        beats = {name: motion[name] for name in ("press", "lift", "route", "verdict", "complete")}
        self.assertEqual(len(set(beats.values())), 5, f"two beats share a duration: {beats}")
        for name, value in beats.items():
            self.assertLessEqual(value, motion["ceiling"], name)
            self.assertGreater(value, 0, name)
        self.assertFalse(motion["loops"])

    def test_the_gate_is_armed_only_when_the_v3_material_exists(self) -> None:
        # Passes while the gate is off. On CP-020a's first commit (V3_REQUIRED=True before the
        # literals exist) this is the first, clearest RED rather than eight confusing ones.
        if not V3_REQUIRED:
            self.skipTest("V3_REQUIRED is False: CP-020a owns the flip")
        source = plugin_source()
        self.assertIsNotNone(literal_span(source, V3_TOKEN_CONST),
                             f"V3_REQUIRED is True but {V3_TOKEN_CONST} does not exist")
        self.assertIsNotNone(literal_span(source, V3_CSS_CONST),
                             f"V3_REQUIRED is True but {V3_CSS_CONST} does not exist")


@unittest.skipUnless(V3_REQUIRED, "CP-020a flips V3_REQUIRED; see the module docstring")
class V3TokenLiteralTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = contract()
        self.source = plugin_source()
        self.raw = literal_text(self.source, V3_TOKEN_CONST)
        assert self.raw is not None
        self.tokens = json.loads(self.raw)

    def test_the_literal_equals_the_contract_byte_for_byte(self) -> None:
        # Every top-level key the module carries must exist in the contract with an equal value,
        # and the five build-critical keys must all be carried.
        for key in REQUIRED_TOP_LEVEL:
            self.assertIn(key, self.tokens, f"{V3_TOKEN_CONST} does not carry {key!r}")
        for key, value in self.tokens.items():
            self.assertIn(key, self.contract, f"{V3_TOKEN_CONST} invented key {key!r}")
            self.assertEqual(value, self.contract[key], f"{key} drifted from the contract")
        projection = {key: self.contract[key] for key in self.tokens}
        self.assertEqual(
            self.raw,
            canonical(projection),
            "the literal is not the contract's canonical bytes; regenerate it instead of hand-editing",
        )

    def test_hex_appears_only_in_the_two_token_literals(self) -> None:
        masked = self.source
        for name in TOKEN_LITERAL_CONSTS:
            span = literal_span(masked, name)
            if span is None:
                continue
            masked = masked[:span[0]] + " " * (span[1] - span[0]) + masked[span[1]:]
        stray = HEX.findall(masked)
        self.assertEqual(stray, [], f"raw colours outside the token literals: {stray[:12]}")

    def test_both_modes_carry_every_role_the_contract_declares(self) -> None:
        roles = set(self.contract["roles"])
        for mode in ("light", "dark"):
            self.assertEqual(set(self.tokens["modes"][mode]), roles, mode)


@unittest.skipUnless(V3_REQUIRED, "CP-020a flips V3_REQUIRED; see the module docstring")
class V3StylesheetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = contract()
        self.source = plugin_source()
        self.css = v3_css()
        self.rules = css_blocks(self.css)

    def test_no_backdrop_filter_and_no_blur(self) -> None:
        for banned in ("backdrop-filter", "backdropFilter", "blur("):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, self.source)

    def test_the_stylesheet_is_not_a_stub(self) -> None:
        # An empty CB_V3_CSS would satisfy every "must not contain" rule below vacuously.
        rules = style_rules(self.css)
        self.assertGreaterEqual(len(rules), 3, f"only {len(rules)} v3 style rules")
        self.assertGreaterEqual(len(self.css), 400, "the v3 stylesheet is too small to be real")

    def test_box_shadow_only_inside_the_stylesheet_and_only_as_elevation_tokens(self) -> None:
        outside = self.source
        for start, end in reversed(v3_spans(self.source)):
            outside = outside[:start] + outside[end:]
        self.assertNotIn("box-shadow", outside.lower())
        self.assertNotIn("boxShadow", outside)
        shadows = [(prop, value) for _, body in self.rules for prop, value in declarations(body)
                   if prop == "box-shadow"]
        for _, value in shadows:
            self.assertRegex(
                value,
                r"^var\(--cb3-elev-[a-z0-9-]+\)$",
                "a v3 shadow must be an elevation token, never a raw recipe or a glow",
            )

    def test_the_only_gradient_is_the_named_vignette(self) -> None:
        gradients: list[tuple[str, str]] = []
        for _, body in self.rules:
            for prop, value in declarations(body):
                if GRADIENT.search(value):
                    gradients.append((prop, value))
        for prop, value in gradients:
            self.assertTrue(
                prop.startswith("--cb3-vignette"),
                f"the only permitted gradient is the named vignette; found {prop}: {value}",
            )
        outside = self.source
        for start, end in reversed(v3_spans(self.source)):
            outside = outside[:start] + outside[end:]
        self.assertEqual(GRADIENT.findall(without_shelf_edge_mask(outside)), [],
                         "a gradient escaped the v3 stylesheet and the v2 mask exemption")

    def test_every_selector_is_scoped_to_data_cb_v3_except_font_face(self) -> None:
        # At-rules (@font-face, @media, @supports) are not selectors and are excepted; every rule
        # that paints must be scoped to the v3 route root.
        for prelude, _ in style_rules(self.css):
            for selector in split_selectors(prelude):
                self.assertTrue(
                    selector.startswith("[data-cb-v3]"),
                    f"selector {selector!r} is not scoped to [data-cb-v3]",
                )

    def test_every_font_family_starts_with_cb(self) -> None:
        faces = [(prelude, body) for prelude, body in self.rules if prelude.startswith("@font-face")]
        for prelude, body in faces:
            families = [value for prop, value in declarations(body) if prop == "font-family"]
            self.assertEqual(len(families), 1, f"{prelude} must name exactly one family")
            name = families[0].strip().strip("'\"")
            self.assertTrue(name.startswith("CB "), f"@font-face {name!r} is not a `CB ` family")

        for _, body in self.rules:
            for prop, value in declarations(body):
                if prop != "font-family":
                    continue
                if value.startswith("var("):
                    continue
                # First named family only: the contract's own stacks carry system fallbacks after
                # `CB Display` / `CB UI`, and banning those would ban the contract.
                first = split_selectors(value)[0] if value else ""
                first = first.strip().strip("'\"")
                self.assertTrue(
                    first.startswith("CB "),
                    f"font-family {value!r} does not lead with a `CB ` family (use a token)",
                )

    def test_motion_durations_come_only_from_the_motion_table(self) -> None:
        motion = self.contract["motion"]
        expected = {name: f"{motion[name]}ms" for name in ("press", "lift", "route", "verdict", "complete")}
        table: dict[str, str] = {}
        for _, body in self.rules:
            for prop, value in declarations(body):
                if not DURATION.search(value):
                    continue
                self.assertTrue(
                    prop.startswith("--cb3-dur-"),
                    f"duration {value!r} on {prop!r} escapes the motion table",
                )
                table[prop[len("--cb3-dur-"):]] = value
        self.assertEqual(set(table), set(expected), f"motion table beats: {sorted(table)}")
        for beat, value in table.items():
            self.assertEqual(value, expected[beat], f"--cb3-dur-{beat}")

    def test_no_looping_animation_or_keyframes(self) -> None:
        for banned in ("@keyframes", "animation:", "animation-name", "infinite"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, self.css)

    def test_no_viewport_unit_on_the_v3_surface(self) -> None:
        # SPEC-V3 §3.1: v3 measures against the route container, never the window.
        self.assertEqual(re.findall(r"(?<![\w.-])\d+(?:\.\d+)?vw\b", self.css), [],
                         "a vw value on a v3 surface ignores the route width")


if __name__ == "__main__":
    unittest.main()
