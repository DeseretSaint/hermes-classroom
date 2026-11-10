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
IDENTITY_DOC = ROOT / "docs" / "COURSEBOOK-VISUAL-IDENTITY-V3.md"

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
    "surfaces",
    "surface_rules",
    "text_placements",
    "text_placement_rule",
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

# The only roles that may carry text, and the only grounds each may sit on. A colour that is a
# fill, a rule or a ring is absent here by design: it never carries a label.
TEXT_ROLES = ("ink", "ink-soft", "on-forest", "on-terracotta", "plum", "alert")

# Pinned text-gate roster. This is the card's "contrast pairs for every text-on-surface
# combination" written down, so deleting a gate from the contract fails the suite instead of
# quietly shrinking coverage. Growth is allowed only by editing this tuple in review.
PINNED_TEXT_GATE_ROSTER = (
    ("ink", "canvas"),
    ("ink", "canvas-edge"),
    ("ink", "card-stock"),
    ("ink", "terracotta-quiet"),
    ("ink-soft", "canvas"),
    ("ink-soft", "canvas-edge"),
    ("ink-soft", "card-stock"),
    ("ink-soft", "terracotta-quiet"),
    ("on-forest", "forest"),
    ("on-terracotta", "terracotta"),
    ("plum", "canvas"),
    ("plum", "card-stock"),
    ("alert", "canvas"),
    ("alert", "canvas-edge"),
    ("alert", "card-stock"),
    ("alert", "terracotta-quiet"),
)

# Every text role must be permitted on every route surface, because an error or offline state
# can appear anywhere; alert is the one that was missing in round 1.
ROUTE_SURFACE_IDS = ("home.global", "discover", "classroom", "course.home", "parent.studio")

# Every surface in this contract takes input, including the on-screen evidence tray. Pinned so the
# interactive flag cannot be flipped to false to dodge the focus requirement without review.
INTERACTIVE_SURFACE_IDS = (
    "home.global",
    "discover",
    "classroom",
    "course.home",
    "parent.studio",
    "evidence",
    "component.lab",
)

# Round-2 D4: a graphic role that sits on a surface's own ground must have a non-text gate for that
# exact pairing, or an object can merge into the paper it rests on. wood-edge is excluded because it
# is gated against its parent object (wood), which is how it reads as thickness.
GRAPHIC_ROLES_ON_GROUND = ("rule", "terracotta", "wood", "gold", "sage")

# Pinned non-text roster with its floors, so a gate can neither vanish nor be quietly weakened.
PINNED_NON_TEXT_GATE_ROSTER = (
    ("rule", "canvas", 1.25),
    ("rule", "card-stock", 1.25),
    ("terracotta", "canvas", 3.0),
    ("wood", "canvas", 3.0),
    ("wood", "card-stock", 3.0),
    ("wood-edge", "wood", 1.5),
    ("gold", "canvas", 3.0),
    ("sage", "canvas", 1.5),
    ("sage", "card-stock", 1.5),
)

# Pinned focus roster: one gate per ground a ring can be drawn on.
PINNED_FOCUS_GATE_ROSTER = (
    ("focus", "canvas"),
    ("focus", "card-stock"),
    ("focus", "canvas-edge"),
    ("focus", "forest"),
    ("focus", "terracotta-quiet"),
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


DISPLAY_CLAMP = re.compile(r"^clamp\(([0-9.]+)rem, ([0-9.]+)rem \+ ([0-9.]+)cqi, ([0-9.]+)rem\)$")


def display_px(clamp: str, container_px: float) -> float:
    """Resolve a rem/rem+cqi clamp against a route container width in px, at a 16px root."""
    match = DISPLAY_CLAMP.match(clamp)
    if not match:
        raise AssertionError(f"not a rem/rem+cqi clamp: {clamp!r}")
    floor, base, slope, ceiling = (float(group) for group in match.groups())
    preferred = base * 16 + (slope / 100) * container_px
    return max(floor * 16, min(ceiling * 16, preferred))


def doc_section(prefix: str) -> str:
    text = IDENTITY_DOC.read_text(encoding="utf-8")
    start = text.index(prefix)
    rest = text[start + len(prefix):]
    end = re.search(r"\n## ", rest)
    return rest[: end.start()] if end else rest


def parse_surface_table() -> dict:
    """Parse the §9 markdown table. The doc is the human rendering; the JSON is the source."""
    rows = {}
    for line in doc_section("## 9.").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] == "Surface" or set(cells[0]) <= set("-: "):
            continue
        name, ground, allowed, note = cells
        allowed_set = (
            set(REQUIRED_ROLES) if allowed == "all roles" else {role.strip() for role in allowed.split(",")}
        )
        rows[name] = {"ground": ground, "allowed": allowed_set, "note": note}
    return rows


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


class SurfaceContractTest(unittest.TestCase):
    """Round-1 D1: a role must be permitted somewhere, and alert must reach every route."""

    def setUp(self) -> None:
        self.contract = load_contract()
        self.surfaces = {surface["id"]: surface for surface in self.contract["surfaces"]}

    def test_surfaces_have_unique_ids_real_roles_and_five_routes(self) -> None:
        ids = [surface["id"] for surface in self.contract["surfaces"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([sid for sid, s in self.surfaces.items() if s["route"]], list(ROUTE_SURFACE_IDS))
        roles = set(self.contract["roles"])
        for surface in self.contract["surfaces"]:
            self.assertTrue(surface["name"].strip(), surface["id"])
            self.assertTrue(surface["ground"].strip(), surface["id"])
            self.assertTrue(surface["note"].strip(), surface["id"])
            self.assertTrue(surface["allowed"], surface["id"])
            self.assertLessEqual(set(surface["allowed"]), roles, surface["id"])

    def test_every_role_is_permitted_on_at_least_one_surface(self) -> None:
        permitted = {role for surface in self.contract["surfaces"] for role in surface["allowed"]}
        self.assertEqual(permitted, set(self.contract["roles"]))

    def test_alert_is_permitted_on_every_route_surface(self) -> None:
        for surface_id in ROUTE_SURFACE_IDS:
            self.assertIn("alert", self.surfaces[surface_id]["allowed"], surface_id)

    def test_alert_is_not_exempt_on_the_evidence_sheet(self) -> None:
        # Not a route, but a refused export reports on paper; the sheet must not forbid the colour.
        self.assertIn("alert", self.surfaces["evidence"]["allowed"])

    def test_a_permitted_text_role_has_a_gated_ground_on_that_surface(self) -> None:
        placements = self.contract["text_placements"]
        grounds = {"canvas", "canvas-edge", "card-stock", "terracotta", "terracotta-quiet", "forest"}
        for surface in self.contract["surfaces"]:
            surface_grounds = set(surface["allowed"]) & grounds
            for role in set(surface["allowed"]) & set(TEXT_ROLES):
                self.assertTrue(
                    set(placements[role]) & surface_grounds,
                    f"{surface['id']} permits {role} text but has no gated ground for it",
                )

    def test_wood_always_brings_its_edge(self) -> None:
        for surface in self.contract["surfaces"]:
            if "wood" in surface["allowed"]:
                self.assertIn("wood-edge", surface["allowed"], surface["id"])

    def test_every_surface_declares_machine_readable_grounds(self) -> None:
        # Round-2 D4: the prose ground ("canvas + grain + vignette") is for the doc; the gates need
        # a role list they can be computed against.
        roles = set(self.contract["roles"])
        for surface in self.contract["surfaces"]:
            self.assertIsInstance(surface.get("interactive"), bool, surface["id"])
            grounds = surface.get("grounds")
            self.assertTrue(grounds, f"{surface['id']} has no grounds list")
            self.assertLessEqual(set(grounds), roles, surface["id"])
            self.assertEqual(len(grounds), len(set(grounds)), surface["id"])

    def test_an_interactive_surface_can_always_show_focus(self) -> None:
        # Round-2 D4b: a surface with a control and no permitted focus ring is a keyboard dead end.
        self.assertEqual(
            tuple(s["id"] for s in self.contract["surfaces"] if s["interactive"]),
            INTERACTIVE_SURFACE_IDS,
        )
        focus_gates = {
            gate["background"] for gate in self.contract["gates"] if gate["kind"] == "focus"
        }
        for surface in self.contract["surfaces"]:
            if not surface["interactive"]:
                continue
            self.assertIn("focus", surface["allowed"], surface["id"])
            for ground in surface["grounds"]:
                self.assertIn(
                    ground,
                    focus_gates,
                    f"{surface['id']} is interactive on {ground} but no focus ring is gated there",
                )

    def test_a_graphic_role_on_a_surface_ground_has_a_non_text_gate(self) -> None:
        # Round-2 D4a: the evidence tray's wood sat on card-stock with no gate and merged into the
        # night sheet. Every object painted on a surface's own paper must clear its non-text floor.
        non_text = {
            (gate["foreground"], gate["background"])
            for gate in self.contract["gates"]
            if gate["kind"] == "non-text"
        }
        for surface in self.contract["surfaces"]:
            for role in set(surface["allowed"]) & set(GRAPHIC_ROLES_ON_GROUND):
                self.assertTrue(
                    any((role, ground) in non_text for ground in surface["grounds"]),
                    f"{surface['id']} permits {role} on its own ground but has no non-text gate for it",
                )

    def test_doc_section_nine_matches_the_contract(self) -> None:
        # The doc may not drift: a role permitted in prose but absent from the JSON (or the
        # reverse) would let a downstream card paint a colour the gates never proved.
        parsed = parse_surface_table()
        self.assertEqual(set(parsed), {surface["name"] for surface in self.contract["surfaces"]})
        for surface in self.contract["surfaces"]:
            row = parsed[surface["name"]]
            self.assertEqual(row["ground"], surface["ground"], surface["id"])
            self.assertEqual(row["allowed"], set(surface["allowed"]), surface["id"])
            self.assertTrue(row["note"], surface["id"])


class TypeContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_display_uses_the_pinned_container_clamp(self) -> None:
        scale = self.contract["type"]["scale"]
        self.assertEqual(scale["display"], "clamp(2.5rem, 1.5rem + 3cqi, 4rem)")

    def test_display_clamp_arithmetic(self) -> None:
        # Round-1 D3: the fluid term is 24px + 3% of the *container*. The floor is reached below
        # a 533.33px container, the 64px ceiling only above 1333.33px; 1049px is fluid, not capped.
        display = self.contract["type"]["scale"]["display"]

        self.assertAlmostEqual(display_px(display, 320), 40.0, places=2)
        self.assertAlmostEqual(display_px(display, 460), 40.0, places=2)
        self.assertAlmostEqual(display_px(display, 900), 51.0, places=2)
        self.assertAlmostEqual(display_px(display, 1049), 55.47, places=2)
        self.assertLess(display_px(display, 1049), 64.0)
        self.assertLess(display_px(display, 1333.0), 64.0)
        self.assertAlmostEqual(display_px(display, 1333.4), 64.0, places=2)
        self.assertAlmostEqual(display_px(display, 1920), 64.0, places=2)

    def test_the_doc_does_not_claim_the_ceiling_at_1049(self) -> None:
        section = doc_section("## 4.")
        self.assertIn("1333", section)
        self.assertNotIn("at 1049 it reaches its ceiling", section)
        self.assertIn("55.5", section)

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

    def test_the_text_gate_roster_is_pinned(self) -> None:
        # Round-1 D2: coverage must not be able to shrink by deleting a gate. The literal
        # roster below is the card's "every text-on-surface combination", written down.
        gates = [(gate["foreground"], gate["background"]) for gate in self.contract["gates"] if gate["kind"] == "text"]
        self.assertEqual(len(gates), len(set(gates)), "duplicate text gate")
        self.assertEqual(set(gates), set(PINNED_TEXT_GATE_ROSTER))

    def test_the_non_text_gate_roster_and_floors_are_pinned(self) -> None:
        # Round-2 D4a: a non-text gate could previously be added for one ground and silently omitted
        # for another, leaving a real object below its floor in one theme.
        gates = [
            (gate["foreground"], gate["background"], gate["min"])
            for gate in self.contract["gates"]
            if gate["kind"] == "non-text"
        ]
        self.assertEqual(len(gates), len(set((fg, bg) for fg, bg, _ in gates)), "duplicate non-text gate")
        self.assertEqual(set(gates), set(PINNED_NON_TEXT_GATE_ROSTER))

    def test_the_focus_gate_roster_is_pinned(self) -> None:
        gates = [
            (gate["foreground"], gate["background"])
            for gate in self.contract["gates"]
            if gate["kind"] == "focus"
        ]
        self.assertEqual(len(gates), len(set(gates)), "duplicate focus gate")
        self.assertEqual(set(gates), set(PINNED_FOCUS_GATE_ROSTER))

    def test_every_gate_kind_is_exactly_one_of_three(self) -> None:
        kinds = {gate["kind"] for gate in self.contract["gates"]}
        self.assertEqual(kinds, {"text", "non-text", "focus"})

    def test_every_text_placement_has_a_gate_and_no_gate_is_unplaced(self) -> None:
        placements = self.contract["text_placements"]
        self.assertEqual(set(placements), set(TEXT_ROLES))
        derived = {(role, ground) for role, grounds in placements.items() for ground in grounds}
        self.assertEqual(derived, set(PINNED_TEXT_GATE_ROSTER))
        gated = {(gate["foreground"], gate["background"]) for gate in self.contract["gates"] if gate["kind"] == "text"}
        self.assertEqual(gated, derived)

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
        self.assertEqual(focus_grounds, {background for _, background in PINNED_FOCUS_GATE_ROSTER})
        self.assertEqual(focus_grounds, {"canvas", "card-stock", "canvas-edge", "forest", "terracotta-quiet"})


# --- Cross-document parity: SPEC-V3 and the v3 rubric against the contract ----------------------
#
# CP-001r (t_3788bb37). SPEC-V3 was written after the contract and drifted from it on type step
# names, type sizes, measure and card radius; the rubric repeated two of those numbers. Nothing
# failed when they crossed, so the drift was found by eye in a review instead of by a suite. This
# class reads all three documents, recomputes every value from the contract at run time and fails
# on any disagreement.

SPEC_DOC = ROOT / "docs" / "concept-parity" / "SPEC-V3.md"
RUBRIC_DOC = ROOT / "docs" / "GM-CONCEPT-PARITY-RUBRIC.md"
COPY_DOC = ROOT / "docs" / "concept-parity" / "COPY.md"

# CP-001r-b (t_342e4a2e). SPEC-V3 §5 S9 tells the lab to draw six type rows in contract order and
# COPY.md is the deck CP-020b paints them from, so the two documents have to agree positionally.
# The v2 deck rows named six steps the v3 contract does not have (`title`, `section`, `label`,
# `micro`), cited their v2 sizes and sourced the values at `type.<step>`, which is not a path in
# the contract at all. The six v3 rows map, in contract order, to these copy ids. A copy id keeps
# its name when the step under it changes, so this tuple — not the id's own spelling — is the only
# authority on which id paints which step. `lab.type.section` stays in the deck for the v2 lab and
# is deliberately not one of these six.
S9_TYPE_COPY_IDS = (
    ("caption", "lab.type.micro"),
    ("meta", "lab.type.label"),
    ("body", "lab.type.body"),
    ("lead", "lab.type.lead"),
    ("heading", "lab.type.title"),
    ("display", "lab.type.display"),
)

# A visible type row reads `<step name> · <px>/<line-height px> · <sample line>`. The pair is
# parsed exactly, never by substring, so `16/26` cannot be read as `16/2`.
COPY_SIZE_PAIR = re.compile(r"(?<![\d./])(\d{1,2}(?:\.\d{1,2})?)/(\d{1,2}(?:\.\d{1,2})?)(?![\d/])")

# The retired step names and the contract step each one becomes. This mapping is explicit and is
# not one-to-one (`title` and `section` both become `heading`), and it is a mapping of step names,
# never of copy ids: `home.title` and `discover.section` are copy keys, not type steps.
STEP_NAME_MAP = {
    "title": "heading",
    "section": "heading",
    "label": "meta",
    "micro": "caption",
    "body": "body",
    "display": "display",
}

RETIRED_STEPS = ("title", "section", "label", "micro")

# Route-container widths the spec renders its derived table at.
ROUTE_WIDTHS = (1049, 900, 460)

# A size citation that is adjacent to one of these words is a type-step citation and must be one
# of the contract's renderings; a measurement such as `166/159 wide` or `905/905` is not.
SIZE_WORDS = ("title", "section", "label", "micro", "question", "display", "heading", "body", "lead", "sub", "subject", "line")
PAIR = r"(\d{1,2}(?:\.\d{1,2})?)/(\d{1,2}(?:\.\d{1,2})?)"
SIZE_BEFORE = re.compile(r"\b(?:%s)\s+%s(?=[\s,.;|)])" % ("|".join(SIZE_WORDS), PAIR))
SIZE_AFTER = re.compile(r"(?<![\d/])%s\s+(?:%s)\b" % (PAIR, "|".join(SIZE_WORDS)))
# A retired step name followed by a size on the same cell is a citation of a step that no longer
# exists, whichever order the pair is written in.
RETIRED_NAME_WITH_SIZE = re.compile(r"(?<![\w.])(?:%s)\b[^\n|]{0,40}?%s\b" % ("|".join(RETIRED_STEPS), PAIR))


def _md_section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading):]
    end = re.search(r"\n#{2,3} ", rest)
    return rest[: end.start()] if end else rest


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def _step_rendering(contract: dict, step: str, width: int) -> tuple[float, float]:
    """Resolve one contract step to (px, line-height px) at a route-container width."""
    scale = contract["type"]["scale"][step]
    line_height = contract["type"]["line_height"][step]
    if scale.endswith("rem"):
        px = float(scale[: -len("rem")]) * 16
    else:
        px = display_px(scale, width)
    px = round(px, 2)
    return px, round(px * line_height, 2)


def _contract_renderings(contract: dict) -> set[tuple[float, float]]:
    return {
        _step_rendering(contract, step, width)
        for step in contract["type"]["scale"]
        for width in ROUTE_WIDTHS
    }


def _rubric_v3_type_cells(rubric: str) -> list[str]:
    for cells in _table_rows(_md_section(rubric, "### 7.1 The ten dimensions")):
        if len(cells) >= 5 and cells[0] == "3" and "Type" in cells[1]:
            return cells
    raise AssertionError("rubric §7.1 has no dimension-3 Type row")


def _rubric_v3_type_row(rubric: str) -> str:
    return " | ".join(_rubric_v3_type_cells(rubric))


class CrossDocumentParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()
        cls.spec = SPEC_DOC.read_text(encoding="utf-8")
        cls.rubric = RUBRIC_DOC.read_text(encoding="utf-8")
        cls.type_section = _md_section(cls.spec, "### 3.4 Type roles")
        cls.radius_section = _md_section(cls.spec, "### 3.6 Physical objects, not floating cards")

    def test_spec_names_the_contracts_six_steps_and_no_seventh(self) -> None:
        steps = tuple(cell[0] for cell in _table_rows(self.type_section)[1:])
        self.assertEqual(steps, tuple(self.contract["type"]["scale"]))
        self.assertEqual(len(steps), 6)

    def test_spec_maps_every_retired_step_name_explicitly(self) -> None:
        pairs = dict(re.findall(r"`([a-z]+)` \u2192 `([a-z]+)`", self.type_section))
        self.assertEqual(pairs, STEP_NAME_MAP)
        contract_steps = set(self.contract["type"]["scale"])
        for retired, current in STEP_NAME_MAP.items():
            self.assertIn(current, contract_steps, retired)
        for retired in RETIRED_STEPS:
            self.assertNotIn(retired, contract_steps, retired)

    def test_no_spec_step_row_uses_a_retired_name(self) -> None:
        rows = {cell[0] for cell in _table_rows(self.type_section)[1:]}
        self.assertFalse(rows & set(RETIRED_STEPS), rows)

    def test_spec_renders_every_step_from_the_contract_at_each_route_width(self) -> None:
        for cells in _table_rows(self.type_section)[1:]:
            step = cells[0]
            self.assertEqual(len(cells), 6, step)
            for index, width in enumerate(ROUTE_WIDTHS):
                written = cells[1 + index]
                px_text, _, lh_text = written.partition("/")
                expected_px, expected_lh = _step_rendering(self.contract, step, width)
                self.assertAlmostEqual(float(px_text), expected_px, places=2, msg=f"{step} at {width}: px")
                self.assertAlmostEqual(float(lh_text), expected_lh, places=2, msg=f"{step} at {width}: line-height")

    def test_spec_labels_the_table_as_a_rendering_of_the_contract(self) -> None:
        flat = re.sub(r"\s+", " ", self.type_section).lower()
        self.assertIn("the contract governs, this table is a rendering", flat)
        self.assertIn("route-container value", flat)
        self.assertIn("cqi", flat)

    def test_spec_invariant_covers_radius_and_type_not_only_colour(self) -> None:
        needle = "a hex, a px radius or a rem size written here as authority is a second contract"
        flat = re.sub(r"\s+", " ", self.spec)
        self.assertTrue(needle in flat, "SPEC-V3 lines 17-20 must cover radius and type, not colour only")

    def test_rubric_dim_three_names_the_contracts_six_steps(self) -> None:
        # The rubric repeats the step names in its own words, so a revert there reinstates
        # divergence 1 in the second document this card names. Only the dim-3 pass cell is read:
        # §1's v2 table keeps the v2 six and must stay out of this assertion.
        pass_cell = _rubric_v3_type_cells(self.rubric)[-1]
        named = re.findall(r"`([a-z]+)`", pass_cell)
        contract_steps = set(self.contract["type"]["scale"])
        self.assertEqual(set(named), contract_steps, pass_cell)
        self.assertEqual(len(named), len(contract_steps), pass_cell)
        for retired in RETIRED_STEPS:
            self.assertNotIn(retired, named, f"rubric §7 dim 3 still offers the retired step {retired!r}")

    def test_prose_and_display_measure_agree_with_the_contract(self) -> None:
        measure = self.contract["type"]["measure"]
        self.assertIn("50-75ch", measure)
        self.assertIn("20ch", measure)
        self.assertIn("34ch", measure)
        for text, label in ((self.type_section, "SPEC §3.4"), (_rubric_v3_type_row(self.rubric), "rubric §7 dim 3")):
            self.assertIn("50\u201375ch", text, label)
            self.assertIn("\u226420ch", text, label)
            self.assertIn("\u226434ch", text, label)
            self.assertNotIn("50\u201366ch", text, label)
            self.assertNotIn("\u226418ch", text, label)
        # §7 does not rewrite the v2 table: §1 keeps the v2 prose cap for v2 screens.
        self.assertIn("\u226466ch", _md_section(self.rubric, "## 1. The nine dimensions"))

    def test_card_radius_is_the_contracts_round_role_written_once(self) -> None:
        self.assertNotIn("radius 6", self.spec)
        self.assertIn("radius `round`", self.radius_section)
        rules = {rule.split(":", 1)[0].strip(): rule.split(":", 1)[1] for rule in self.contract["radius_rules"]}
        self.assertIn("card", rules["round"])
        round_px = int(self.contract["radii"]["round"].removesuffix("px"))
        self.assertRegex(self.radius_section, rf"\b{round_px}\s*px\b")

    def test_no_spec_line_assigns_a_card_its_own_px_radius(self) -> None:
        # A cell that puts a number on a card's radius must attribute it to the contract. Cells are
        # checked, not whole table rows, so a pill on an action and a passing mention of a card on
        # the same row cannot be confused with a card radius.
        for number, line in enumerate(self.spec.splitlines(), start=1):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")] if line.startswith("|") else [line]
            for cell in cells:
                low = cell.lower()
                if "card" not in low or "radius" not in low:
                    continue
                if not (re.search(r"radius\s+`?\d", cell) or re.search(r"\b\d+\s*px\b", cell)):
                    continue
                self.assertIn("contract", cell, f"SPEC-V3.md:{number} gives a card a px radius as its own authority")

    def test_no_spec_cites_a_type_size_that_no_contract_step_renders(self) -> None:
        allowed = _contract_renderings(self.contract)
        for number, line in enumerate(self.spec.splitlines(), start=1):
            # Step names are written in backticks throughout this spec, so normalise them away
            # before matching; otherwise `` `heading` 31/36 `` never reaches the guard.
            plain = line.replace("`", "")
            for match in list(SIZE_BEFORE.finditer(plain)) + list(SIZE_AFTER.finditer(plain)):
                pair = (float(match.group(1)), float(match.group(2)))
                self.assertIn(pair, allowed, f"SPEC-V3.md:{number} cites {match.group(0)!r}, not a contract step")
    def test_copy_deck_s9_type_rows_are_the_contracts_six_steps(self) -> None:
        # The deck is load-bearing: CP-020b paints these rows, and tests/test_cp_spec.py resolves
        # copy ids to rows. A row that names a retired step, quotes a v2 size or sources a path the
        # contract does not have is a screen that draws a step the product no longer ships.
        deck = {cells[0].strip("`"): cells for cells in _table_rows(COPY_DOC.read_text(encoding="utf-8"))}
        lab_rows = {copy_id: cells for copy_id, cells in deck.items() if copy_id.startswith("lab.type.")}
        renderings = _contract_renderings(self.contract)
        scale = self.contract["type"]["scale"]
        line_height = self.contract["type"]["line_height"]

        for step, copy_id in S9_TYPE_COPY_IDS:
            with self.subTest(copy_id=copy_id, step=step):
                self.assertIn(copy_id, lab_rows, f"COPY.md has no `{copy_id}` row")
                cells = lab_rows[copy_id]
                self.assertGreaterEqual(len(cells), 5, f"{copy_id} is not a full copy row: {cells}")
                text, source = cells[1], cells[2]

                # The step the row paints, exactly — not by substring, so `Heading` cannot pass as
                # `heading` by accident and `Meta` is never read as the retired `micro`.
                named = text.split("\u00b7")[0].strip()
                self.assertEqual(named.lower(), step, f"{copy_id} paints {named!r}, not the contract step {step!r}")
                self.assertNotIn(named.lower(), RETIRED_STEPS, f"{copy_id} names the retired step {named!r}")

                # The size it quotes is a rendering of that step (SPEC §3.4 renders the 1049 column;
                # this row quotes the same column, so the deck and the region map cannot disagree).
                match = COPY_SIZE_PAIR.search(text)
                if match is None:
                    self.fail(f"{copy_id} cites no px/line-height pair: {text!r}")
                written = (float(match.group(1)), float(match.group(2)))
                self.assertIn(written, renderings, f"{copy_id} cites {written}, which no contract step renders")
                self.assertEqual(
                    written,
                    _step_rendering(self.contract, step, ROUTE_WIDTHS[0]),
                    f"{copy_id} must quote the {ROUTE_WIDTHS[0]} px rendering of {step}",
                )

                # The source is a real path in the contract's own tree: `type.<step>` at the top
                # level is not a path, and a retired step has no scale entry to point at.
                tokens = re.findall(r"contract:`([^`]+)`", source)
                self.assertEqual(
                    tokens,
                    [f"type.scale.{step}", f"type.line_height.{step}"],
                    f"{copy_id} sources {source!r}; a quoted line-height cites both paths for {step}",
                )
                for token in tokens:
                    parts = token.split(".")
                    self.assertEqual(len(parts), 3, f"{copy_id}: {token!r} is not a dotted contract path")
                    group = parts[1]
                    self.assertIn(group, ("scale", "line_height"), f"{copy_id}: {token!r} is not a type path")
                    self.assertIn(parts[2], (scale if group == "scale" else line_height), f"{copy_id}: {token!r} does not exist")

        # Positional agreement with the region map, and no extra lab.type row claiming S9.
        s9 = [cells for cells in _table_rows(_md_section(self.spec, "### 5.5 R-SYS")) if cells[0] == "S9"]
        self.assertEqual(len(s9), 1, "§5.5 region map must have exactly one S9 row")
        self.assertEqual(
            re.findall(r"`(lab\.type\.[a-z_]+)`", s9[0][5]),
            [copy_id for _step, copy_id in S9_TYPE_COPY_IDS],
            "§5 S9's Copy ids column must list the six ids in contract order",
        )
        for copy_id, cells in lab_rows.items():
            if copy_id in {known for _step, known in S9_TYPE_COPY_IDS}:
                continue
            self.assertNotIn("S9", cells[-1], f"{copy_id} claims S9 but is not one of the six v3 rows")
        self.assertIn("lab.type.section", lab_rows, "the v2 deck row `lab.type.section` was deleted, not parked")


if __name__ == "__main__":
    unittest.main()
