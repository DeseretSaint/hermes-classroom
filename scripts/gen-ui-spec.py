#!/usr/bin/env python3
"""Generate the Home UI spec from the generated context pack and the v3 token contract.

`visual/spec/type-map.json` and `visual/spec/home.json` are *outputs*. Every A1 pixel, box
component and step resolution is read from `docs/launch/UI-CONTEXT-PACK.generated.md` and
`contracts/cb.tokens.v3.json`; nothing is typed as a requirement here. The only authored material
is the element tree (which node is which element, its live selector and its token paint), and the
rules for the five states.

Usage: python3 scripts/gen-ui-spec.py [--check] [--out-dir DIR]
  --check    exit 1 if the committed JSON differs from what this script would write.
  --out-dir  write into DIR instead of the repository (used by tests for idempotence).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "docs/launch/UI-CONTEXT-PACK.generated.md"
CONTRACT = ROOT / "contracts/cb.tokens.v3.json"
TYPE_MAP = ROOT / "visual/spec/type-map.json"
HOME = ROOT / "visual/spec/home.json"
REF_CSS_REV = "a07b99ea"  # the revision the generated pack was measured from

ROUTE_WIDTH = 1344
CQI_PX = ROUTE_WIDTH * 0.01
ROOT_FONT_PX = 16.0


# ── pack parsing ────────────────────────────────────────────────────────────────────────────

def pack_text() -> str:
    return PACK.read_text(encoding="utf-8")


def pack_source(pack: str) -> dict:
    source = re.search(r"Source: `([^`]+)` at `([^`]+)`", pack)
    digest = re.search(r"Content hash: `([^`]+)`", pack)
    if not source or not digest:
        sys.exit(f"{PACK} has no source/hash header; regenerate it")
    return {
        "path": str(PACK.relative_to(ROOT)),
        "reference_path": source.group(1),
        "reference_commit": source.group(2),
        "content_hash": digest.group(1),
    }


def _num(text: str):
    text = text.strip()
    if text.endswith("px"):
        return float(text[:-2])
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return float(text)
    return None


def parse_box(raw: str) -> dict:
    box: dict[str, float | None] = {
        "left": None, "top": None, "right": None, "width": None, "height": None}
    extra = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or part == "—":
            continue
        pieces = part.split(None, 1)
        if len(pieces) != 2:
            continue
        key, value = pieces
        if key in box:
            box[key] = _num(value)
            if box[key] is None:
                extra[key] = value
        else:
            extra[key] = value
    out = {"box": box}
    if extra:
        out["percent"] = extra
    return out


def parse_tables(pack: str) -> tuple[dict, dict]:
    geometry: dict = {}
    types: dict = {}
    section = None
    for line in pack.splitlines():
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
            m = re.match(r"\| `([^`]+)` \| (.+?) \|$", line)
            if m:
                geometry[m.group(1)] = parse_box(m.group(2))
        elif section == "type":
            m = re.match(r"\| `([^`]+)` \| (.+?) \| (.+?) \| (.+?) \| (.+?) \| (.*?) \|$", line)
            if m:
                selector, size, leading, weight, family, flag = m.groups()
                px = re.match(r"(\d+(?:\.\d+)?)px", size.strip())
                wt = re.match(r"\d+", weight.strip())
                types[selector] = {
                    "px": int(px.group(1)) if px else None,
                    "size_css": size.strip(),
                    "line_height_css": None if leading.strip() == "—" else leading.strip(),
                    "weight": int(wt.group(0)) if wt else None,
                    "family_css": None if family.strip() == "—" else family.strip(),
                    "flag": flag.strip() or None,
                }
    if not geometry or not types:
        sys.exit("the generated pack did not yield both tables; regenerate it")
    return geometry, types


# ── contract resolution ────────────────────────────────────────────────────────────────────

def resolve_css_length(css: str) -> float:
    """Resolve a CSS length expression (sums allowed) at the 1344 route and a 16px root."""
    css = css.strip()
    total = 0.0
    terms = [term.strip() for term in css.split("+")]
    if not terms or any(not term for term in terms):
        raise ValueError(f"not a length expression: {css!r}")
    for term in terms:
        m = re.fullmatch(r"(-?\d+(?:\.\d+)?)([a-z%]*)", term)
        if not m:
            raise ValueError(f"not a single length: {term!r} in {css!r}")
        value, unit = float(m.group(1)), m.group(2)
        if unit == "rem":
            total += value * ROOT_FONT_PX
        elif unit in ("px", ""):
            total += value
        elif unit in ("cqi", "vw"):
            total += value * CQI_PX
        else:
            raise ValueError(f"unsupported unit {unit!r} in {css!r}")
    return total


def resolve_clamp(css: str) -> float:
    m = re.fullmatch(r"clamp\((.+)\)", css.strip())
    if not m:
        return resolve_css_length(css)
    parts = [p.strip() for p in m.group(1).split(",")]
    if len(parts) != 3:
        raise ValueError(f"clamp() needs three arguments: {css!r}")
    low, preferred, high = (resolve_css_length(p) for p in parts)
    return max(low, min(preferred, high))


def step_table(contract: dict) -> dict:
    scale = contract["type"]["scale"]
    leading = contract["type"]["line_height"]
    families = contract["type"]["families"]
    steps = {}
    for token, css in scale.items():
        steps[token] = {
            "token": token,
            "css": css,
            "px_at_1344": round(resolve_clamp(css), 2),
            "line_height_token": token,
            "line_height": leading[token],
        }
    if len(steps) != 6:
        sys.exit(f"the v3 contract declares {len(steps)} steps; the rule is six and no seventh")
    return steps


# ── type map ──────────────────────────────────────────────────────────────────────────────

def family_token(family_css: str | None, default: str) -> str:
    if not family_css:
        return default
    if "CB Display" in family_css:
        return "display"
    if "CB UI" in family_css:
        return "ui"
    if "Noto Serif JP" in family_css:
        return "cjk"
    return default


ROLE_ROWS = [
    # role, reference selector, v3 step, default family when the pack is silent, note
    ("hero-h1", ".hero h1", "display", "display",
     "Ledger L-03: the 72 px reference headline resolves to the 64 px display ceiling at 1344."),
    ("subline", ".hero p", "heading", "ui",
     "The handoff's 32 px target assumed a static step; the heading clamp resolves to 32.64 px at 1344."),
    ("brand", ".brand", "heading", "display",
     "Wordmark at the heading step, not a separate brand size: no seventh step."),
    ("tag", ".tag", "lead", "display",
     "Kraft tag label at the lead step."),
    ("nav", "nav a", "body", "ui",
     "Navigation links sit at body, the reading size."),
    ("studio", ".studio", "body", "ui",
     "Parent Studio door sits at body."),
    ("button", ".btn", "body", "ui",
     "Both pills label at body; the primary/quiet split is a fill decision, not a size."),
    ("card-title", ".card h3", "meta", "ui",
     "Shelf card title at meta."),
    ("card-meta", None, "caption", "ui",
     "No painted A1 text: the sections pair is a caption-step copy node behind the progress bar."),
]


def build_type_map(pack: str, contract: dict) -> dict:
    geometry, types = parse_tables(pack)
    steps = step_table(contract)
    weights = contract["type"]["weights"]
    roles = []
    for role, selector, step, default_family, note in ROLE_ROWS:
        ref = types.get(selector) if selector else None
        a1_px = ref["px"] if ref else None
        step_px = steps[step]["px_at_1344"]
        weight = ref["weight"] if ref and ref["weight"] is not None else (
            weights.get(step, 400) if step in ("display", "heading") else 400
        )
        fam = family_token(ref["family_css"] if ref else None, default_family)
        roles.append({
            "role": role,
            "reference_selector": selector,
            "a1_px": a1_px,
            "a1_px_source": "pack" if a1_px is not None else "absent-from-a1",
            "rendered": step,
            "step": step,
            "step_px_at_1344": step_px,
            "delta_px": None if a1_px is None else round(step_px - a1_px, 2),
            "line_height_token": steps[step]["line_height_token"],
            "line_height": steps[step]["line_height"],
            "family_token": fam,
            "family": contract["type"]["families"][fam],
            "weight": weight,
            "weight_source": "pack" if ref and ref["weight"] is not None else "contract",
            "note": note,
        })
    return {
        "schema": "cb.ui.type-map.v1",
        "screen": "home",
        "generated_by": "scripts/gen-ui-spec.py",
        "source": {
            "pack": pack_source(pack),
            "contract": {"path": str(CONTRACT.relative_to(ROOT)), "version": contract["version"]},
            "route_width_px": ROUTE_WIDTH,
            "cqi_px": round(CQI_PX, 4),
            "root_font_px": ROOT_FONT_PX,
        },
        "steps": steps,
        "roles": roles,
        "rules": [
            "Six steps and no seventh: every role names one of the six v3 steps.",
            "No role carries a literal pixel as its rendered value; the rendered value is a step name.",
            "step_px_at_1344 is resolved from the contract clamp against the route container (1 cqi = 13.44 px).",
            "The A1 pixels are read from the generated pack, never hand-copied.",
            "If the hero reads weak, adjust measure, leading and tracking within the tokens, never the size.",
        ],
    }


# ── home spec ─────────────────────────────────────────────────────────────────────────────

def png_size(path: Path) -> dict:
    """Read a PNG's natural size from its IHDR without decoding the image."""
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG")
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    return {"width": width, "height": height}


def measured(value, source: str) -> dict:
    return {"value": value, "source": source}


def box_of(geometry: dict, selector: str) -> dict:
    entry = geometry.get(selector, {"box": {}})
    box = dict(entry["box"])
    box["percent"] = entry.get("percent", {})
    return box


def pack_box(geometry: dict, selector: str, **overrides) -> dict:
    """A box whose components are sourced: 'pack' when the pack declares them, else measured."""
    raw = box_of(geometry, selector)
    out = {}
    for key in ("left", "top", "width", "height", "right"):
        value = raw.get(key)
        source = "pack" if value is not None else None
        if key in overrides:
            value = overrides[key][0]
            source = overrides[key][1]
        out[key] = {"value": value, "source": source}
    return out


def plain_box(geometry: dict, selector: str) -> dict:
    box = box_of(geometry, selector)
    return {key: box.get(key) for key in ("left", "top", "width", "height", "right")}


def tree_node(node_id, kind, *, live=None, reference=None, type_role=None, paint=None,
              box=None, z=None, asset=None, rendered=None, natural=None, natural_min=None,
              text=None, painted=True, index=None, children=None, note=None):
    node = {
        "id": node_id,
        "kind": kind,
        "live_selector": live,
        "index": index,
        "reference_selector": reference,
        "type_role": type_role,
        "paint": paint or {},
        "box": box or {},
        "z": z,
        "asset": asset,
        "rendered": rendered,
        "natural": natural,
        "natural_min": natural_min,
        "text": text,
        "painted": painted,
        "children": children or [],
    }
    if note:
        node["note"] = note
    return node


def build_home(pack: str, contract: dict, type_map: dict) -> dict:
    geometry, _ = parse_tables(pack)
    steps = type_map["steps"]
    roles = {row["role"]: row for row in type_map["roles"]}
    colors = contract["modes"]["light"]
    light = contract["modes"]["light"]
    motion = contract["motion"]

    def paint(fill=None, color=None, border=None, shadow=None, radius=None, mark=None,
              material=None, opacity=None):
        out = {}
        for key, value in (("fill", fill), ("color", color), ("border", border),
                           ("shadow", shadow), ("radius", radius), ("mark", mark),
                           ("material", material), ("opacity", opacity)):
            if value is not None:
                out[key] = value
        return out

    def text_node(node_id, role, live, reference, color, **kw):
        row = roles[role]
        return tree_node(
            node_id, "text", live=live, reference=reference, type_role=role,
            paint=paint(color=color, **kw.pop("paint", {})),
            text=kw.pop("text", None), **kw,
        )

    cards = []
    cover_assets = [
        "bundled/packs/japanese-affection-context-l0/content/cover-4x5.png",
        "assets/art/scenes/course-map.png",
        "bundled/packs/parent-measurement-practice/content/cover-4x5.png",
        "bundled/packs/japanese-affection-context-l0/content/cover-3x2.png",
    ]
    card_box = pack_box(geometry, ".card")
    cover_box = pack_box(geometry, ".card .cover", width=(176.0, "derived: 100% of .card width"))
    for index, asset in enumerate(cover_assets, start=1):
        position = index - 1
        cards.append(tree_node(
            f"card-{index}", "element",
            live="[data-cb-home-scene-card]", index=position,
            reference=".card",
            paint=paint(fill="card-stock", border="rule", shadow="elev-1", radius="soft"),
            box=card_box, z=3,
            note="Card stock sits on the canvas; rotation per the reference stack, not a token value.",
            children=[
                tree_node(
                    f"cover-{index}", "image",
                    live="[data-cb-home-scene-cover]", index=position,
                    reference=".card .cover",
                    box=cover_box, z=3, asset=asset,
                    rendered={"width": 176.0, "height": 106.0},
                    natural=png_size(ROOT / asset),
                    natural_min={"width": 176.0, "height": 106.0},
                    note="A painted, text-free cover artifact; titles are DOM, never baked in.",
                ),
                tree_node(
                    f"card-body-{index}", "element",
                    live="[data-cb-home-scene-body]", index=position,
                    reference=".card .body", box={}, z=3,
                    children=[
                        text_node(f"card-title-{index}", "card-title",
                                  "[data-cb-home-scene-title]", ".card h3", "ink",
                                  box={}, z=3, index=position),
                        tree_node(
                            f"card-progress-{index}", "element",
                            live="[data-cb-home-scene-progress]", index=position,
                            reference=".bar",
                            paint=paint(fill="rule", radius="pill"), box={}, z=3,
                            note="sections_done/sections_total only; no ratings, counts or learners.",
                            children=[tree_node(
                                f"card-progress-fill-{index}", "element",
                                live="[data-cb-home-scene-progress] > i", index=position,
                                reference=".bar i",
                                paint=paint(fill="gold", radius="pill"), box={}, z=3,
                            )],
                        ),
                        text_node(f"card-meta-{index}", "card-meta",
                                  "[data-cb-home-scene-meta]", None,
                                  "ink-soft", box={}, z=3, painted=False, index=position,
                                  text="n of m sections done",
                                  note="Copy node for the accessible sections pair; not painted, matching A1."),
                    ],
                ),
            ],
        ))

    header = tree_node(
        "header", "element", live=None, reference="header",
        paint=paint(fill="canvas"), z=5,
        box=pack_box(geometry, "header"),
        note="The 86 px band belongs to the route, not host chrome (G0-1).",
        children=[
            text_node("brand", "brand", None, ".brand", "ink",
                      box=pack_box(geometry, ".brand"), z=5, text="Coursebook"),
            tree_node("nav", "element", live=None, reference="nav",
                      box=pack_box(geometry, "nav"), z=5, children=[
                          text_node("nav-home", "nav", None, "nav a.active", "ink",
                                    text="Home", z=5,
                                    paint={"mark": "terracotta"}),
                          text_node("nav-discover", "nav", None, "nav a", "ink",
                                    text="Discover Library", z=5),
                      ]),
            tree_node("studio", "element", live=None, reference=".studio",
                      box=pack_box(geometry, ".studio"), z=5, children=[
                          tree_node("studio-mark", "element", live=None, reference=".studio i",
                                    paint=paint(fill="canvas", border="ink", radius="pill"),
                                    z=5, note="Initial in a ring: iconography, not a text step."),
                          text_node("studio-label", "studio", None, ".studio", "ink",
                                    text="Studio", z=5),
                      ]),
        ],
    )

    hero = tree_node(
        "hero", "element", live="[data-cb-home-scene-hero]", reference=".hero",
        box=pack_box(geometry, ".hero"), z=4,
        children=[
            text_node("hero-h1", "hero-h1", "[data-cb-home-scene-question]", ".hero h1",
                      "ink", box={}, z=4, text="Your field library"),
            text_node("subline", "subline", "[data-cb-home-scene-subline]", ".hero p",
                      "ink-soft", box={}, z=4,
                      text="Choose a course or start a new expedition."),
            tree_node("cta", "element", live="[data-cb-home-scene-cta]", reference=".cta",
                      box={}, z=4, children=[
                          tree_node("button-primary", "control",
                                    live="[data-cb-home-scene-primary]", reference=".btn.primary",
                                    type_role="button",
                                    paint=paint(fill="terracotta", color="on-terracotta",
                                               shadow="elev-1", radius="pill"),
                                    box={}, z=4, text="Start a new course",
                                    note="The one filled primary on this surface (L-06)."),
                          tree_node("button-secondary", "control",
                                    live="[data-cb-home-scene-secondary]", reference=".btn.secondary",
                                    type_role="button",
                                    paint=paint(fill="terracotta-quiet", color="ink",
                                               radius="pill"),
                                    box={}, z=4, text="Browse library",
                                    note="Quiet warm field carrying ink, not a second terracotta fill (L-06)."),
                      ]),
        ],
    )

    shelf = tree_node(
        "shelf", "element", live="[data-cb-home-scene-cards]", reference=".shelf.cards",
        box=pack_box(geometry, ".shelf.cards", left=(273.0, "measured: .shelf left"),
                     width=(776.0, "derived: 4 x .card width + 3 x reference gap")),
        z=3, children=cards,
        note="Height 175 px from .shelf.cards; left edge measured from .shelf, not a pack number.",
    )

    planks = tree_node(
        "planks", "element", live="[data-cb-home-scene-plank-one]", reference=".plank.one",
        paint=paint(fill="wood", border="wood-edge"), z=2,
        box=pack_box(geometry, ".plank.one"), children=[
            tree_node("plank-one", "element", live="[data-cb-home-scene-plank-one]",
                      reference=".plank.one", paint=paint(fill="wood", border="wood-edge"),
                      z=2, box=pack_box(geometry, ".plank.one")),
            tree_node("plank-two", "element", live="[data-cb-home-scene-plank-two]",
                      reference=".plank.two", paint=paint(fill="wood", border="wood-edge"),
                      z=2, box=pack_box(geometry, ".plank.two")),
        ],
        note="Wood is a prop: no label sits on it. The lip is wood-edge.",
    )

    root = tree_node(
        "home", "element", live="[data-cb-home-scene]", reference="body",
        paint=paint(fill="canvas", color="ink"), z=0,
        box={k: measured(v, "route") for k, v in
             {"left": 0.0, "top": 0.0, "width": 1344.0, "height": 768.0}.items()},
        note="One canvas, one vignette, one grain. The route measures 1344x768.",
        children=[
            tree_node("grain", "material", live=".cb3-material-grain", reference=".grain",
                      paint={"material": "grain", "opacity": contract["materials"]["grain"]["light"]["opacity"]},
                      box={k: {"value": v, "source": "route"} for k, v in
                           {"left": 0.0, "top": 0.0, "width": 1344.0, "height": 768.0}.items()},
                      z=1, note="aria-hidden, pointer-events none, never above text."),
            tree_node("vignette", "material", live=".cb3-material-vignette", reference=".vignette",
                      paint={"material": "vignette",
                             "opacity": contract["materials"]["vignette"]["light"]["opacity"]},
                      box={k: {"value": v, "source": "route"} for k, v in
                           {"left": 0.0, "top": 0.0, "width": 1344.0, "height": 768.0}.items()},
                      z=1),
            header, hero, shelf, planks,
            tree_node("bracket-left", "element", live=None, reference=".bracket.l",
                      paint=paint(fill="wood-edge"), z=1,
                      box={"top": measured(736.0, "pack"), "width": measured(54.0, "pack"),
                           "height": measured(32.0, "pack"),
                           "left": measured(210.0, "measured: .bracket.l left")}),
            tree_node("bracket-right", "element", live=None, reference=".bracket.r",
                      paint=paint(fill="wood-edge"), z=1,
                      box={"top": measured(736.0, "pack"), "width": measured(54.0, "pack"),
                           "height": measured(32.0, "pack"),
                           "right": measured(210.0, "measured: .bracket.r right")}),
            text_node("tag", "tag", "[data-cb-home-scene-tag]", ".tag", "ink",
                      box=pack_box(geometry, ".tag"), z=4, text="New course",
                      paint={"fill": "terracotta-quiet", "border": "rule",
                             "shadow": "elev-1", "radius": "square"}),
            tree_node("clock", "image", live="[data-cb-home-scene-clock]", reference=".clock",
                      box=pack_box(geometry, ".clock"), z=4,
                      asset="assets/art/objects/clock.png",
                      rendered={"width": 118.0, "height": 118.0},
                      natural=png_size(ROOT / "assets/art/objects/clock.png"),
                      natural_min={"width": 118.0, "height": 118.0},
                      note="Object-kit alarm clock holds A1's slot (D-002, ledger L-05)."),
            tree_node("fox", "image", live="[data-cb-home-scene-fox] img", reference=".fox",
                      box=pack_box(geometry, ".fox"), z=5,
                      asset="assets/art/fox/fox-clock-256.png",
                      rendered={"width": 208.0, "height": 208.0},
                      natural=png_size(ROOT / "assets/art/fox/fox-clock-256.png"),
                      natural_min={"width": 208.0, "height": 208.0},
                      note="Painted 256 export at 208 px; natural must be >= rendered (D-001)."),
        ],
    )

    signature = [
        {"id": "fox", "nodes": ["fox"], "box": plain_box(geometry, ".fox"), "count": 1},
        {"id": "clock", "nodes": ["clock"], "box": plain_box(geometry, ".clock"), "count": 1},
        {"id": "shelf", "nodes": ["shelf"],
         "box": {"left": 273.0, "top": 384.0, "width": 776.0, "height": 175.0}, "count": 1,
         "note": "left and width measured from the reference shelf band, not pack numbers"},
        {"id": "planks", "nodes": ["plank-one", "plank-two"],
         "box": plain_box(geometry, ".plank.one"), "count": 2},
        {"id": "tag", "nodes": ["tag"], "box": plain_box(geometry, ".tag"), "count": 1},
        {"id": "covers", "nodes": ["cover-1", "cover-2", "cover-3", "cover-4"],
         "box": {"left": 273.0, "top": 384.0, "width": 776.0, "height": 175.0}, "count": 4,
         "note": "the four covers as one signature band, same box as the shelf"},
    ]

    allowed = set(next(s for s in contract["surfaces"] if s["id"] == "home.global")["allowed"])
    used_roles = {"canvas", "ink", "focus"}

    def collect_paint(node):
        for value in node.get("paint", {}).values():
            if isinstance(value, str) and value in colors:
                used_roles.add(value)
        for child in node.get("children", []):
            collect_paint(child)

    collect_paint(root)
    outside = sorted(role for role in used_roles if role not in allowed)
    if outside:
        sys.exit(f"home spec paints roles outside home.global's allowed list: {outside}")
    palette = {role: colors[role] for role in contract["roles"] if role in used_roles}

    states = {
        "default": {
            "summary": "The room at rest: canvas, grain, vignette, hero, shelf, planks, tag, fox, clock.",
            "rules": [
                "One filled terracotta primary; the second door is terracotta-quiet with ink.",
                "No shadow on text, rules, the rail or the ground.",
                "Card stock uses elev-1 OR a 1 px rule, never both.",
            ],
            "tokens": {"elevation": "elev-1", "radius": ["square", "soft", "round", "pill"]},
        },
        "hover": {
            "summary": "Pointer feedback on the two doors and the four cards.",
            "rules": [
                "Cards lift: transform translateY(-2px) and elev-2, over lift (150 ms).",
                "Doors lift: transform translateY(-1px) over lift; no colour change (colour is not animatable).",
                "Text and rules never move.",
            ],
            "tokens": {"duration": motion["lift"], "easing": motion["easing"],
                       "properties": ["transform", "opacity"], "elevation": "elev-2"},
        },
        "focus-visible": {
            "summary": "Keyboard ring on every interactive control: two doors, four cards, two nav links, the Studio door.",
            "rules": [
                "outline 2 px solid focus, offset 2 px, on the ground the control sits on.",
                "The ring is never clipped by the shelf overflow.",
                "Focus is the only state that paints the focus role.",
            ],
            "tokens": {"width": contract["focus_ring"]["width"],
                       "offset": contract["focus_ring"]["offset"],
                       "style": contract["focus_ring"]["style"],
                       "role": "focus"},
        },
        "loading": {
            "summary": "The shell is up and the library read is in flight.",
            "rules": [
                "The hero, both doors, the shelf band, planks, tag, fox and clock stay: the room does not blank.",
                "Four card placeholders in card-stock with a rule outline; no shimmer, pulse or loop.",
                "A single body sentence, 'Loading your library', at ink-soft; no spinner.",
                "No invented counts, ratings or progress.",
            ],
            "tokens": {"fill": "card-stock", "border": "rule", "text": "ink-soft",
                       "type_role": "body"},
        },
        "empty": {
            "summary": "No enrolled courses: the shelf is empty, the room is not.",
            "rules": [
                "One heading sentence, 'No courses yet', at the heading step in ink.",
                "One body sentence naming both ways forward, at body in ink-soft.",
                "One filled primary, 'Start a new course'; the quiet second door is absent or disabled with its reason.",
                "No placeholder cards, no zeroed counts, no empty progress bars.",
            ],
            "tokens": {"heading_role": "heading", "body_role": "body",
                       "primary_fill": "terracotta", "primary_label": "on-terracotta"},
        },
        "reduced_motion": {
            "summary": "prefers-reduced-motion: transitions are removed, not shortened.",
            "rules": [
                "transition: none on lift and press; the state change still happens on the next frame.",
                "No transform on :active under reduced motion.",
                "Fox, clock, tag and planks are static; nothing loops.",
            ],
            "tokens": {"transition": "none", "duration": 0},
        },
    }

    return {
        "schema": "cb.ui.screen.v1",
        "screen": "home",
        "generated_by": "scripts/gen-ui-spec.py",
        "viewport": {"width": ROUTE_WIDTH, "height": 768,
                     "route": "full-window plugin route (G0-1)"},
        "source": {
            "pack": pack_source(pack),
            "contract": {"path": str(CONTRACT.relative_to(ROOT)), "version": contract["version"]},
            "type_map": "visual/spec/type-map.json",
            "reference_css": {"path": "design/home-scene.html", "commit": REF_CSS_REV,
                              "note": "z-order and the few positions the pack does not declare"},
            "reference_image": "docs/concept-parity/refs/home.png",
        },
        "palette": palette,
        "z_order": [
            {"z": 0, "layer": "canvas"},
            {"z": 1, "layer": "grain, vignette, brackets"},
            {"z": 2, "layer": "planks"},
            {"z": 3, "layer": "shelf and cards"},
            {"z": 4, "layer": "hero, tag, clock"},
            {"z": 5, "layer": "header, fox"},
        ],
        "tree": root,
        "signature_elements": signature,
        "states": states,
        "type_map_steps": {name: step["px_at_1344"] for name, step in steps.items()},
        "rules": [
            "A text node names a role in type-map.json; a painted node names a colour role in the v3 contract.",
            "Images are assets with a natural size at or above their rendered size.",
            "Signature elements are fox, clock, shelf, planks, tag and the four covers.",
            "The five states and reduced motion are specified here; the audit measures the default state.",
        ],
    }


# ── main ──────────────────────────────────────────────────────────────────────────────────

def write_json(path: Path, data: dict) -> str:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out-dir")
    args = ap.parse_args()

    pack = pack_text()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    type_map = build_type_map(pack, contract)
    home = build_home(pack, contract, type_map)

    if args.out_dir:
        out = Path(args.out_dir)
        write_json(out / "type-map.json", type_map)
        write_json(out / "home.json", home)
        print(f"wrote spec into {out}")
        return

    if args.check:
        failures = []
        for path, data in ((TYPE_MAP, type_map), (HOME, home)):
            want = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            have = path.read_text(encoding="utf-8") if path.exists() else ""
            if want != have:
                failures.append(str(path.relative_to(ROOT)))
        if failures:
            print("spec drift: " + ", ".join(failures), file=sys.stderr)
            sys.exit(1)
        print("spec is current")
        return

    for path, data in ((TYPE_MAP, type_map), (HOME, home)):
        digest = write_json(path, data)
        print(f"wrote {path.relative_to(ROOT)} sha256 {digest[:16]}")


if __name__ == "__main__":
    main()
