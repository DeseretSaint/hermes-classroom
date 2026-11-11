"""Home type map and screen spec: six steps, no seventh, and no hand-copied numbers.

The card `t_c4bfc678` (UI program, G0-2/D-004) turns the reference's off-scale type roles into a
spec against the v3 token contract. This test is the gate, not a formality:

  * the contract declares exactly six type steps and the type map uses only those six;
  * no role carries a literal pixel as its *rendered* value: the rendered value is a step name,
    and the step's pixels are resolved from the contract clamp at the 1344 route (1 cqi = 13.44 px);
  * every A1 pixel and every pack-sourced box component is read from
    `docs/launch/UI-CONTEXT-PACK.generated.md` and is reproduced, not hand-copied;
  * `visual/spec/home.json` is regenerable: `scripts/gen-ui-spec.py --out-dir` must reproduce both
    committed JSON files byte for byte;
  * every text node names a role in the type map, every paint names a colour role the contract
    allows on `home.global`, and every image asset exists at a natural size at or above its
    rendered size.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "docs" / "launch" / "UI-CONTEXT-PACK.generated.md"
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
TYPE_MAP = ROOT / "visual" / "spec" / "type-map.json"
HOME = ROOT / "visual" / "spec" / "home.json"
GENERATOR = ROOT / "scripts" / "gen-ui-spec.py"

ROUTE_WIDTH = 1344
CQI_PX = ROUTE_WIDTH * 0.01
ROOT_FONT_PX = 16.0
SIX_STEPS = {"caption", "meta", "body", "lead", "heading", "display"}
SIGNATURE_IDS = {"fox", "clock", "shelf", "planks", "tag", "covers"}
STATE_KEYS = {"default", "hover", "focus-visible", "loading", "empty", "reduced_motion"}


# ── independent pack parsing (deliberately not the generator's code) ───────────────────────

def parse_pack() -> tuple[dict, dict, str]:
    text = PACK.read_text(encoding="utf-8")
    digest = re.search(r"Content hash: `([0-9a-f]+)`", text)
    commit = re.search(r"Source: `[^`]+` at `([0-9a-f]+)`", text)
    geometry: dict[str, dict[str, float | None]] = {}
    types: dict[str, dict] = {}
    section = None
    for line in text.splitlines():
        if line.startswith("## Geometry"):
            section = "geometry"
            continue
        if line.startswith("## Type inventory"):
            section = "type"
            continue
        if line.startswith("## "):
            section = None
            continue
        if section == "geometry":
            match = re.match(r"\| `([^`]+)` \| (.+?) \|$", line)
            if not match:
                continue
            box: dict[str, float | None] = {}
            for part in match.group(2).split(","):
                bits = part.strip().split(None, 1)
                if len(bits) != 2:
                    continue
                key, raw = bits
                raw = raw.strip()
                box[key] = float(raw[:-2]) if raw.endswith("px") else (
                    float(raw) if re.fullmatch(r"-?\d+(?:\.\d+)?", raw) else None)
            geometry[match.group(1)] = box
        elif section == "type":
            match = re.match(r"\| `([^`]+)` \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.*?) \|$", line)
            if not match:
                continue
            selector, size, _, weight, family, _ = match.groups()
            px = re.match(r"(\d+(?:\.\d+)?)px", size.strip())
            wt = re.match(r"\d+", weight.strip())
            types[selector] = {
                "px": float(px.group(1)) if px else None,
                "weight": int(wt.group(0)) if wt else None,
                "family": None if family.strip() == "—" else family.strip(),
            }
    assert digest and commit, "the generated pack has no source/hash header"
    return geometry, types, digest.group(1)


def resolve_css(css: str) -> float:
    """Resolve a length expression at the 1344 route; the test's own arithmetic."""
    total = 0.0
    for term in (piece.strip() for piece in css.split("+")):
        match = re.fullmatch(r"(-?\d+(?:\.\d+)?)([a-z%]*)", term)
        assert match, f"bad term {term!r} in {css!r}"
        value, unit = float(match.group(1)), match.group(2)
        total += value * {"rem": ROOT_FONT_PX, "": 1.0, "px": 1.0,
                          "cqi": CQI_PX, "vw": CQI_PX}[unit]
    return total


def clamp_px(css: str) -> float:
    match = re.fullmatch(r"clamp\((.+)\)", css.strip())
    if not match:
        return round(resolve_css(css), 2)
    low, preferred, high = (resolve_css(piece.strip()) for piece in match.group(1).split(","))
    return round(max(low, min(preferred, high)), 2)


def flatten(node: dict, out: list | None = None) -> list[dict]:
    out = [] if out is None else out
    out.append(node)
    for child in node.get("children", []):
        flatten(child, out)
    return out


class SpecFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.type_map = json.loads(TYPE_MAP.read_text(encoding="utf-8"))
        cls.home = json.loads(HOME.read_text(encoding="utf-8"))
        cls.geometry, cls.pack_types, cls.pack_hash = parse_pack()
        cls.roles = {row["role"]: row for row in cls.type_map["roles"]}
        cls.nodes = flatten(cls.home["tree"])


class TypeMapContractTest(SpecFixture):
    def test_the_contract_declares_exactly_six_named_steps(self) -> None:
        self.assertEqual(set(self.contract["type"]["scale"]), SIX_STEPS)
        self.assertEqual(len(self.contract["type"]["scale"]), 6)

    def test_the_type_map_declares_the_same_six_steps_and_no_seventh(self) -> None:
        self.assertEqual(set(self.type_map["steps"]), SIX_STEPS)
        self.assertEqual(len(self.type_map["steps"]), 6)
        unknown = [row["role"] for row in self.type_map["roles"] if row["step"] not in SIX_STEPS]
        self.assertEqual(unknown, [], f"roles escaping the six steps: {unknown}")

    def test_each_step_pixel_is_resolved_from_its_clamp_at_1344(self) -> None:
        for token, step in self.type_map["steps"].items():
            with self.subTest(step=token):
                self.assertEqual(step["px_at_1344"], clamp_px(self.contract["type"]["scale"][token]))

    def test_the_two_clamped_steps_land_on_the_documented_values(self) -> None:
        self.assertEqual(self.type_map["steps"]["heading"]["px_at_1344"], 32.64)
        self.assertEqual(self.type_map["steps"]["display"]["px_at_1344"], 64.0)
        self.assertEqual(self.type_map["steps"]["lead"]["px_at_1344"], 20.0)
        self.assertEqual(self.type_map["steps"]["caption"]["px_at_1344"], 12.0)

    def test_no_role_uses_a_literal_pixel_as_its_rendered_value(self) -> None:
        for role in self.type_map["roles"]:
            with self.subTest(role=role["role"]):
                rendered = role["rendered"]
                self.assertIsInstance(rendered, str)
                self.assertIn(rendered, SIX_STEPS)
                self.assertIsNone(re.search(r"\d|px", rendered),
                                  f"{role['role']} renders a literal value {rendered!r}")

    def test_each_role_resolves_to_its_step_pixels_and_delta(self) -> None:
        for role in self.type_map["roles"]:
            with self.subTest(role=role["role"]):
                step_px = self.type_map["steps"][role["step"]]["px_at_1344"]
                self.assertEqual(role["step_px_at_1344"], step_px)
                if role["a1_px"] is None:
                    self.assertIsNone(role["delta_px"])
                else:
                    self.assertEqual(role["delta_px"], round(step_px - role["a1_px"], 2))

    def test_every_a1_pixel_is_the_pack_value_not_a_copy(self) -> None:
        sourced = 0
        for role in self.type_map["roles"]:
            selector = role["reference_selector"]
            if role["a1_px_source"] == "pack":
                self.assertIn(selector, self.pack_types, f"{selector} is not in the pack")
                self.assertEqual(role["a1_px"], self.pack_types[selector]["px"])
                sourced += 1
            else:
                self.assertEqual(role["a1_px_source"], "absent-from-a1")
                self.assertIsNone(role["a1_px"])
        self.assertEqual(sourced, 8, "the eight A1 rows from D-004 must all be pack-sourced")
        self.assertEqual(self.roles["card-meta"]["a1_px_source"], "absent-from-a1")

    def test_line_height_family_and_weight_follow_the_contract(self) -> None:
        for role in self.type_map["roles"]:
            token = role["step"]
            with self.subTest(role=role["role"]):
                self.assertEqual(role["line_height_token"], token)
                self.assertEqual(role["line_height"], self.contract["type"]["line_height"][token])
                self.assertIn(role["family_token"], self.contract["type"]["families"])
                self.assertEqual(role["family"], self.contract["type"]["families"][role["family_token"]])
                self.assertIsInstance(role["weight"], int)
                self.assertIn(role["weight_source"], {"pack", "contract"})
                if role["weight_source"] == "pack":
                    self.assertIsNotNone(role["reference_selector"])
                    self.assertEqual(role["weight"], self.pack_types[role["reference_selector"]]["weight"])

    def test_the_eight_d004_rows_are_present_with_their_steps(self) -> None:
        expected = {
            "hero-h1": ("display", 72),
            "subline": ("heading", 32),
            "brand": ("heading", 34),
            "tag": ("lead", 23),
            "nav": ("body", 17),
            "studio": ("body", 17),
            "button": ("body", 16),
            "card-title": ("meta", 15),
        }
        for name, (step, a1) in expected.items():
            with self.subTest(role=name):
                self.assertIn(name, self.roles)
                self.assertEqual(self.roles[name]["step"], step)
                self.assertEqual(self.roles[name]["a1_px"], a1)
        self.assertEqual(self.roles["card-meta"]["step"], "caption")


class HomeSpecTest(SpecFixture):
    def test_every_text_node_names_a_role_in_the_type_map(self) -> None:
        text_nodes = [node for node in self.nodes if node["kind"] == "text"]
        self.assertGreater(len(text_nodes), 8)
        for node in text_nodes:
            with self.subTest(node=node["id"]):
                self.assertIn(node["type_role"], self.roles,
                              f"{node['id']} names {node['type_role']!r}, absent from type-map.json")

    def test_every_painted_text_node_matches_its_role_step(self) -> None:
        for node in self.nodes:
            if node["kind"] != "text" or node["painted"] is False:
                continue
            with self.subTest(node=node["id"]):
                self.assertIn(node["type_role"], self.roles)
                self.assertTrue(node["paint"].get("color"),
                                f"{node['id']} paints text without a colour role")

    def test_the_palette_is_inside_the_contract_and_the_home_surface(self) -> None:
        home_surface = next(surface for surface in self.contract["surfaces"] if surface["id"] == "home.global")
        allowed = set(home_surface["allowed"])
        for role, value in self.home["palette"].items():
            with self.subTest(role=role):
                self.assertIn(role, self.contract["roles"])
                self.assertIn(role, allowed)
                self.assertEqual(value, self.contract["modes"]["light"][role])
        for node in self.nodes:
            for key, role in node["paint"].items():
                if key in {"fill", "color", "border", "mark"}:
                    with self.subTest(node=node["id"], paint=key):
                        self.assertIn(role, self.home["palette"],
                                      f"{node['id']}.{key} = {role!r} is not in the palette")

    def test_every_image_asset_exists_and_is_at_least_rendered_size(self) -> None:
        images = [node for node in self.nodes if node["kind"] == "image"]
        self.assertEqual(len(images), 6, "four covers, the clock and the fox")
        for node in images:
            with self.subTest(node=node["id"]):
                asset = ROOT / node["asset"]
                self.assertTrue(asset.is_file(), f"missing asset {node['asset']}")
                raw = asset.read_bytes()
                self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
                natural = node["natural"]
                self.assertEqual(natural["width"], int.from_bytes(raw[16:20], "big"))
                self.assertEqual(natural["height"], int.from_bytes(raw[20:24], "big"))
                self.assertGreaterEqual(natural["width"], node["rendered"]["width"])
                self.assertGreaterEqual(natural["height"], node["rendered"]["height"])
                self.assertGreaterEqual(natural["width"], node["natural_min"]["width"])
                self.assertGreaterEqual(natural["height"], node["natural_min"]["height"])

    def test_the_fox_is_the_painted_256_export_at_208(self) -> None:
        fox = next(node for node in self.nodes if node["id"] == "fox")
        self.assertEqual(fox["asset"], "assets/art/fox/fox-clock-256.png")
        self.assertEqual(fox["rendered"], {"width": 208.0, "height": 208.0})
        self.assertEqual(fox["natural"], {"width": 256, "height": 256})

    def test_pack_sourced_box_components_reproduce_the_pack(self) -> None:
        checked = 0
        for node in self.nodes:
            selector = node["reference_selector"]
            if selector not in self.geometry:
                continue
            for component, entry in node["box"].items():
                if not isinstance(entry, dict) or entry.get("source") != "pack":
                    continue
                with self.subTest(node=node["id"], component=component):
                    self.assertEqual(entry["value"], self.geometry[selector].get(component),
                                     f"{node['id']}.{component} does not reproduce {selector}")
                checked += 1
        self.assertGreaterEqual(checked, 15, "too few pack-sourced box components were verified")

    def test_measured_components_are_labelled_so_they_are_not_requirements(self) -> None:
        for node in self.nodes:
            for component, entry in node["box"].items():
                with self.subTest(node=node["id"], component=component):
                    self.assertIsInstance(entry, dict)
                    self.assertIn("source", entry)
                    if entry["value"] is not None:
                        self.assertTrue(entry["source"])

    def test_the_six_signature_elements_are_flagged(self) -> None:
        signature = {element["id"]: element for element in self.home["signature_elements"]}
        self.assertEqual(set(signature), SIGNATURE_IDS)
        self.assertEqual(signature["covers"]["count"], 4)
        self.assertEqual(len(signature["covers"]["nodes"]), 4)
        self.assertEqual(signature["planks"]["count"], 2)
        for element in self.home["signature_elements"]:
            with self.subTest(element=element["id"]):
                box = element["box"]
                self.assertTrue(any(box.get(key) is not None for key in ("width", "height")))

    def test_the_five_states_and_reduced_motion_are_specified(self) -> None:
        self.assertEqual(set(self.home["states"]), STATE_KEYS)
        for name, state in self.home["states"].items():
            with self.subTest(state=name):
                self.assertTrue(state["summary"])
                self.assertTrue(state["rules"])
        reduced = self.home["states"]["reduced_motion"]
        self.assertIn("removed", " ".join(reduced["rules"] + [reduced["summary"]]).lower())
        self.assertEqual(reduced["tokens"]["duration"], 0)

    def test_the_spec_names_its_sources_and_the_pack_hash(self) -> None:
        for spec in (self.type_map, self.home):
            with self.subTest(spec=spec["schema"]):
                self.assertEqual(spec["source"]["pack"]["content_hash"], self.pack_hash)
                self.assertEqual(spec["source"]["contract"]["version"], self.contract["version"])
        self.assertEqual(self.home["source"]["type_map"], "visual/spec/type-map.json")
        self.assertEqual(self.home["viewport"]["width"], ROUTE_WIDTH)
        self.assertEqual(self.home["viewport"]["height"], 768)


class GeneratorIdempotenceTest(SpecFixture):
    def test_the_committed_spec_is_exactly_what_the_generator_writes(self) -> None:
        if not GENERATOR.is_file():
            self.skipTest("scripts/gen-ui-spec.py is absent")
        with tempfile.TemporaryDirectory(prefix="cb-ui-spec-") as tmp:
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--out-dir", tmp],
                cwd=ROOT, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-4000:])
            for committed, name in ((TYPE_MAP, "type-map.json"), (HOME, "home.json")):
                with self.subTest(file=name):
                    generated = Path(tmp) / name
                    self.assertTrue(generated.is_file(), result.stdout + result.stderr)
                    self.assertEqual(
                        committed.read_text(encoding="utf-8"),
                        generated.read_text(encoding="utf-8"),
                        f"{name} has drifted from scripts/gen-ui-spec.py; regenerate it",
                    )


class AuditScriptTest(unittest.TestCase):
    def test_the_audit_script_parses_under_node(self) -> None:
        script = ROOT / "scripts" / "audit-screen.mjs"
        self.assertTrue(script.is_file(), "scripts/audit-screen.mjs is missing")
        result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_the_audit_script_never_reloads_resizes_or_focuses(self) -> None:
        source = (ROOT / "scripts" / "audit-screen.mjs").read_text(encoding="utf-8")
        forbidden = ["page.reload(", "setViewportSize(", "setDeviceMetricsOverride",
                     "bringToFront(", ".focus("]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source, f"{needle} would touch a live window")
        self.assertIn("refused: the live window is", source)
        self.assertIn("no reload, no resize, no focus", source)


if __name__ == "__main__":
    unittest.main()
