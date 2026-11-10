"""The v3 visual contract: schema, role parity, and every contrast pair computed on the file.

These tests read ``contracts/cb.tokens.v3.json`` and nothing else, so they pass before any UI
exists and they cannot be satisfied by a stylesheet that disagrees with the contract. WCAG
contrast is computed here from the shipped values; a pair that is merely claimed in prose does
not pass.

What this does NOT prove: that the plugin paints these values, that a font loads, or that a
surface is legible in context. CP-003 and CP-020a own the module-level gates.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"

REQUIRED_ROLES = (
    "canvas",
    "canvas-edge",
    "card-stock",
    "ink",
    "ink-soft",
    "rule",
    "forest",
    "on-forest",
    "terracotta",
    "on-terracotta",
    "terracotta-quiet",
    "gold",
    "sage",
    "wood",
    "wood-edge",
    "plum",
    "alert",
    "focus",
)

TOP_LEVEL_KEYS = (
    "version",
    "name",
    "scope",
    "roles",
    "role_rules",
    "modes",
    "elevation",
    "radii",
    "radius_scale",
    "type",
    "materials",
    "motion",
    "gates",
    "never_text_on",
)

HEX = re.compile(r"^#[0-9a-f]{6}$")


def _relative_luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(channels[0]) + 0.7152 * linear(channels[1]) + 0.0722 * linear(channels[2])


def contrast_ratio(foreground: str, background: str) -> float:
    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


class ContractSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_required_sections_exist(self) -> None:
        for key in TOP_LEVEL_KEYS:
            self.assertIn(key, self.contract, key)

    def test_version_is_three(self) -> None:
        self.assertEqual(self.contract["version"], 3)

    def test_the_role_list_is_exactly_the_required_roles(self) -> None:
        self.assertEqual(tuple(self.contract["roles"]), REQUIRED_ROLES)
        self.assertEqual(len(set(self.contract["roles"])), len(REQUIRED_ROLES))

    def test_every_role_has_a_rule(self) -> None:
        self.assertEqual(set(self.contract["role_rules"]), set(REQUIRED_ROLES))
        for role, text in self.contract["role_rules"].items():
            self.assertTrue(text.strip(), role)

    def test_both_modes_define_every_role_as_a_six_digit_hex(self) -> None:
        for mode in ("light", "dark"):
            table = self.contract["modes"][mode]
            self.assertEqual(set(table), set(REQUIRED_ROLES), mode)
            for role, value in table.items():
                self.assertRegex(value, HEX, f"{mode}.{role}")

    def test_light_and_dark_role_parity(self) -> None:
        light = set(self.contract["modes"]["light"])
        dark = set(self.contract["modes"]["dark"])
        self.assertEqual(light, dark)
        self.assertEqual(light, set(REQUIRED_ROLES))

    def test_elevation_defines_three_levels_per_mode(self) -> None:
        for mode in ("light", "dark"):
            levels = self.contract["elevation"][mode]
            self.assertEqual(set(levels), {"elev-1", "elev-2", "inset-1"}, mode)
            for value in levels.values():
                self.assertIn("rgba(", value)

    def test_radii_are_exactly_zero_six_twelve_and_pill(self) -> None:
        self.assertEqual(sorted(self.contract["radius_scale"]), [0, 6, 12, 999])
        values = sorted(int(re.sub(r"[^0-9]", "", v)) for v in self.contract["radii"].values())
        self.assertEqual(values, [0, 6, 12, 999])


class TypeContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_display_uses_the_pinned_container_clamp(self) -> None:
        scale = self.contract["type"]["scale"]
        self.assertEqual(scale["display"], "clamp(2.5rem, 1.5rem + 3cqi, 4rem)")

    def test_six_type_steps_and_no_seventh(self) -> None:
        scale = self.contract["type"]["scale"]
        self.assertEqual(
            set(scale), {"caption", "meta", "body", "lead", "heading", "display"}
        )
        self.assertEqual(scale["caption"], "0.75rem")
        self.assertEqual(scale["body"], "1rem")

    def test_fluid_steps_are_measured_on_the_route_container(self) -> None:
        scale = self.contract["type"]["scale"]
        for step in ("heading", "display"):
            self.assertIn("cqi", scale[step], step)
            self.assertNotIn("vw", scale[step], step)
        self.assertEqual(self.contract["type"]["container"]["type"], "inline-size")
        self.assertIn("route container", self.contract["type"]["container"]["measured_against"])

    def test_two_embedded_families_and_a_system_cjk_stack(self) -> None:
        families = self.contract["type"]["families"]
        self.assertTrue(families["display"].startswith('"CB Display"'))
        self.assertTrue(families["ui"].startswith('"CB UI"'))
        self.assertEqual(set(self.contract["type"]["subsets"]), {"CB Display", "CB UI", "cjk"})
        self.assertIn("Fraunces", self.contract["type"]["subsets"]["CB Display"])
        self.assertIn("Source Sans 3", self.contract["type"]["subsets"]["CB UI"])
        self.assertIn("Noto Serif JP", families["cjk"])
        self.assertIn("Hiragino", families["cjk"])

    def test_font_failure_falls_back_rather_than_blanking(self) -> None:
        self.assertIn("swap", self.contract["type"]["loading"])
        self.assertIn("never blanks", self.contract["type"]["loading"])


class MaterialsAndMotionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_grain_vignette_and_wood_name_a_tile_and_opacity_per_theme(self) -> None:
        materials = self.contract["materials"]
        for name in ("grain", "vignette", "wood"):
            for mode in ("light", "dark"):
                row = materials[name][mode]
                self.assertTrue(row["tile"].strip(), f"{name}.{mode}.tile")
                self.assertIn("opacity", row, f"{name}.{mode}")
                self.assertTrue(0 <= row["opacity"] <= 1, f"{name}.{mode}")

    def test_grain_opacity_respects_the_legibility_ceiling(self) -> None:
        materials = self.contract["materials"]
        ceiling = materials["opacity_ceiling"]
        for mode in ("light", "dark"):
            self.assertLessEqual(materials["grain"][mode]["opacity"], ceiling, mode)
        self.assertLessEqual(ceiling, 0.25)

    def test_motion_beats(self) -> None:
        motion = self.contract["motion"]
        self.assertEqual(
            {k: motion[k] for k in ("press", "lift", "route", "verdict", "complete", "ceiling")},
            {"press": 120, "lift": 150, "route": 240, "verdict": 300, "complete": 600, "ceiling": 600},
        )

    def test_no_loop_and_no_duration_above_the_ceiling(self) -> None:
        motion = self.contract["motion"]
        self.assertIs(motion["loops"], False)
        self.assertLessEqual(
            max(motion["press"], motion["lift"], motion["route"], motion["verdict"], motion["complete"]),
            motion["ceiling"],
        )
        self.assertEqual(set(motion["properties"]), {"transform", "opacity"})
        self.assertIn("removed", motion["reduced_motion"])


class ContrastGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_every_gate_names_existing_roles(self) -> None:
        roles = set(self.contract["roles"])
        for gate in self.contract["gates"]:
            self.assertIn(gate["foreground"], roles, gate)
            self.assertIn(gate["background"], roles, gate)
            self.assertIn(gate["kind"], {"text", "non-text", "focus"}, gate)
            self.assertTrue(gate["why"].strip(), gate)

    def test_every_pair_passes_in_both_modes(self) -> None:
        for mode in ("light", "dark"):
            table = self.contract["modes"][mode]
            for gate in self.contract["gates"]:
                ratio = contrast_ratio(table[gate["foreground"]], table[gate["background"]])
                self.assertGreaterEqual(
                    round(ratio, 2),
                    gate["min"],
                    f"{mode}: {gate['foreground']} on {gate['background']} is {ratio:.2f}, "
                    f"floor {gate['min']} ({gate['why']})",
                )

    def test_text_gates_meet_the_text_floor(self) -> None:
        for gate in self.contract["gates"]:
            if gate["kind"] != "text":
                continue
            self.assertGreaterEqual(gate["min"], 4.5, gate)
            ratio = contrast_ratio(
                self.contract["modes"]["light"][gate["foreground"]],
                self.contract["modes"]["light"][gate["background"]],
            )
            self.assertGreaterEqual(round(ratio, 2), 4.5, gate)

    def test_the_primary_label_reaches_four_point_five(self) -> None:
        for mode in ("light", "dark"):
            table = self.contract["modes"][mode]
            ratio = contrast_ratio(table["on-terracotta"], table["terracotta"])
            self.assertGreaterEqual(round(ratio, 2), 4.5, mode)

    def test_every_ground_a_text_gate_uses_is_covered(self) -> None:
        # A role may carry text only if some text gate proves its floor. Fills that must never
        # carry text are declared in never_text_on and are asserted absent here.
        text_backgrounds = {g["background"] for g in self.contract["gates"] if g["kind"] == "text"}
        for role in ("canvas", "card-stock", "terracotta", "forest", "terracotta-quiet", "canvas-edge"):
            self.assertIn(role, text_backgrounds, role)

    def test_wood_gold_and_sage_never_carry_text(self) -> None:
        banned = set(self.contract["never_text_on"])
        self.assertEqual(banned, {"wood", "gold", "sage"})
        for gate in self.contract["gates"]:
            if gate["kind"] == "text":
                self.assertNotIn(gate["background"], banned, gate)

    def test_focus_is_never_a_text_colour(self) -> None:
        for gate in self.contract["gates"]:
            if gate["kind"] == "text":
                self.assertNotEqual(gate["foreground"], "focus", gate)

    def test_focus_ring_is_gated_on_every_ground_it_sits_on(self) -> None:
        focus_grounds = {g["background"] for g in self.contract["gates"] if g["kind"] == "focus"}
        self.assertEqual(focus_grounds, {"canvas", "card-stock", "canvas-edge", "forest", "terracotta-quiet"})


if __name__ == "__main__":
    unittest.main()
