#!/usr/bin/env python3
"""Build the GM-013 reference boards and their provenance manifest.

Every board is **host-composed**: flat geometry drawn here from the Atlas Lamp token palette in
``contracts/cb.tokens.v2.json``. No model call, no stock imagery, no third-party asset, no text in
a plate. The four plates are textless by construction; the swap diagram is a diagram and is allowed
labels because it is a review instrument, not art.

Run: ``python3 scripts/build_gm_visual_assets.py``
Output: ``docs/gm-visual/boards/*.svg`` and ``docs/gm-visual/manifest.json``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "contracts" / "cb.tokens.v2.json"
OUT = ROOT / "docs" / "gm-visual" / "boards"

W, H = 640, 360


def palette() -> dict[str, str]:
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    return {name: data["modes"]["light"][name] for name in data["tokens"]}


P = palette()


def svg(body: str, width: int = W, height: int = H, background: str | None = None) -> str:
    bg = f'<rect width="{width}" height="{height}" fill="{background}"/>' if background else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f"{bg}{body}</svg>\n"
    )


# --------------------------------------------------------------------------------------
# 1. Japanese L0 — lantern district / cafe lesson (field_atlas, lantern variant)
# --------------------------------------------------------------------------------------
def japanese_lantern_district() -> str:
    b = []
    # street ground: hard-edged lamp-soft flood, lower third
    b.append(f'<rect x="0" y="252" width="640" height="108" fill="{P["lamp-soft"]}"/>')
    # ceiling beam: the cords hang from it, so nothing reads as clipped
    b.append(f'<rect x="0" y="0" width="640" height="10" fill="{P["ink"]}"/>')
    # hanging cords
    for x, y in ((148, 96), (282, 66), (454, 104)):
        b.append(f'<rect x="{x - 1}" y="10" width="2" height="{y - 10}" fill="{P["ink"]}"/>')
    # lanterns: capsule body, ink cap, one horizontal rib
    for x, y, w, h in ((120, 96, 56, 84), (250, 66, 64, 100), (430, 104, 48, 74)):
        b.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w // 3}" '
            f'fill="{P["lamp"]}"/>'
        )
        b.append(f'<rect x="{x - 3}" y="{y - 6}" width="{w + 6}" height="6" fill="{P["ink"]}"/>')
        b.append(
            f'<rect x="{x + 2}" y="{y + h // 2}" width="{w - 4}" height="2" '
            f'fill="{P["ink"]}" opacity="0.55"/>'
        )
    # noren panel with slits
    b.append(
        f'<rect x="502" y="150" width="96" height="128" fill="{P["paper-raised"]}" '
        f'stroke="{P["ink"]}" stroke-width="2"/>'
    )
    b.append(f'<rect x="502" y="150" width="96" height="12" fill="{P["lamp"]}"/>')
    for x in (532, 562, 592):
        b.append(f'<rect x="{x}" y="170" width="2" height="108" fill="{P["paper"]}"/>')
    # counter edge
    b.append(f'<rect x="40" y="296" width="560" height="10" fill="{P["ink"]}"/>')
    # stools
    for cx in (196, 372):
        b.append(f'<circle cx="{cx}" cy="262" r="17" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="3"/>')
        b.append(f'<rect x="{cx - 2}" y="276" width="4" height="22" fill="{P["ink"]}"/>')
        b.append(f'<rect x="{cx - 16}" y="294" width="32" height="4" fill="{P["ink"]}"/>')
    # cup with steam (steam is the second motif: cafe service)
    b.append(f'<path d="M262 292 L262 270 L300 270 L300 292 Z" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="3"/>')
    b.append(f'<path d="M300 276 q10 0 10 8 q0 8 -10 8" fill="none" stroke="{P["ink"]}" stroke-width="3"/>')
    b.append(
        f'<path d="M272 262 q6 -10 0 -18 q-6 -8 0 -16" fill="none" stroke="{P["ink-soft"]}" stroke-width="2"/>'
    )
    b.append(
        f'<path d="M286 262 q6 -8 0 -16 q-6 -8 0 -14" fill="none" stroke="{P["ink-soft"]}" stroke-width="2"/>'
    )
    return svg("".join(b), background=P["paper"])


# --------------------------------------------------------------------------------------
# 2. Head gasket — service bay / workshop manual (workshop_manual)
# --------------------------------------------------------------------------------------
def head_gasket_service_bay() -> str:
    b = []
    # floor
    b.append(f'<rect x="0" y="316" width="640" height="44" fill="{P["lamp-soft"]}"/>')
    b.append(f'<rect x="0" y="314" width="640" height="4" fill="{P["ink"]}"/>')
    # lift posts and crossbeam
    for x in (56, 548):
        b.append(f'<rect x="{x}" y="86" width="12" height="228" fill="{P["ink"]}"/>')
    b.append(f'<rect x="56" y="86" width="504" height="12" fill="{P["ink"]}"/>')
    # vehicle body silhouette, no wheels detail beyond circles
    b.append(
        f'<path d="M150 250 L150 206 Q150 196 162 196 L300 196 Q316 196 328 176 '
        f'L392 176 Q406 176 414 196 L470 196 Q482 196 482 208 L482 250 Z" '
        f'fill="{P["rule"]}" stroke="{P["ink"]}" stroke-width="4"/>'
    )
    for cx in (206, 268, 392, 450):
        b.append(f'<circle cx="{cx}" cy="252" r="20" fill="{P["paper"]}" stroke="{P["ink"]}" stroke-width="4"/>')
    # tool wall: pegboard panel with wrench silhouettes
    b.append(
        f'<rect x="376" y="24" width="238" height="128" fill="{P["paper-raised"]}" '
        f'stroke="{P["rule"]}" stroke-width="1"/>'
    )
    for ox, oy, rot in ((410, 46, 18), (470, 40, 42), (536, 50, -12)):
        b.append(
            f'<g transform="translate({ox} {oy}) rotate({rot})">'
            f'<rect x="0" y="-4" width="66" height="8" rx="4" fill="{P["ink"]}"/>'
            f'<circle cx="0" cy="0" r="11" fill="none" stroke="{P["ink"]}" stroke-width="6"/>'
            f'<circle cx="0" cy="0" r="4" fill="{P["paper-raised"]}"/>'
            f'<rect x="-14" y="-3" width="8" height="6" fill="{P["paper-raised"]}"/>'
            f"</g>"
        )
    # component tray with the gasket ring (the second motif, orientation only)
    b.append(
        f'<rect x="216" y="268" width="108" height="40" rx="2" fill="{P["paper-raised"]}" '
        f'stroke="{P["ink"]}" stroke-width="3"/>'
    )
    b.append(f'<circle cx="270" cy="288" r="13" fill="none" stroke="{P["ink"]}" stroke-width="5"/>')
    # open workshop manual, blank pages, ink spine
    b.append(
        f'<path d="M36 300 L36 250 L108 240 L108 292 Z" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="3"/>'
    )
    b.append(
        f'<path d="M108 240 L180 250 L180 300 L108 292 Z" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="3"/>'
    )
    b.append(f'<rect x="106" y="240" width="4" height="54" fill="{P["ink"]}"/>')
    return svg("".join(b), background=P["paper"])


# --------------------------------------------------------------------------------------
# 3. Astronomy — observatory (observatory)
# --------------------------------------------------------------------------------------
def astronomy_observatory() -> str:
    b = []
    # night field, one subject accent, hard edge
    b.append(f'<rect x="0" y="0" width="640" height="150" fill="{P["accent"]}"/>')
    # stars: paper dots, no numbers, no constellation claim
    for x, y, r in (
        (60, 30, 2), (96, 74, 1.6), (140, 44, 1.4), (188, 96, 2), (232, 26, 1.4),
        (286, 62, 2.2), (330, 112, 1.4), (372, 34, 1.8), (418, 82, 1.4), (470, 22, 2),
        (514, 60, 1.4), (560, 104, 1.8), (604, 40, 1.4), (348, 140, 1.4),
    ):
        b.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{P["paper"]}"/>')
    # horizon
    b.append(f'<rect x="0" y="148" width="640" height="3" fill="{P["ink"]}"/>')
    # dome silhouette with slit
    b.append(
        f'<path d="M64 250 A 92 92 0 0 1 248 250 Z" fill="{P["paper-raised"]}" '
        f'stroke="{P["ink"]}" stroke-width="4"/>'
    )
    b.append(f'<path d="M148 160 L168 250 L186 250 L170 160 Z" fill="{P["paper"]}"/>')
    # telescope tube on a pier, aimed up-right
    b.append(
        f'<g transform="translate(210 228) rotate(-27)">'
        f'<rect x="0" y="-9" width="150" height="18" rx="9" fill="{P["ink"]}"/>'
        f'<rect x="118" y="-12" width="10" height="24" fill="{P["ink-soft"]}"/>'
        f'<rect x="64" y="-12" width="8" height="24" fill="{P["ink-soft"]}"/>'
        f"</g>"
    )
    b.append(f'<rect x="204" y="226" width="10" height="74" fill="{P["ink"]}"/>')
    b.append(f'<rect x="180" y="300" width="58" height="6" fill="{P["ink"]}"/>')
    b.append(f'<path d="M196 300 L206 288 L220 288 L230 300 Z" fill="{P["ink"]}"/>')
    # star chart: grid and plotted points, no numbers
    b.append(
        f'<rect x="398" y="182" width="212" height="148" fill="{P["paper-raised"]}" '
        f'stroke="{P["ink"]}" stroke-width="2"/>'
    )
    for i in range(1, 5):
        b.append(f'<rect x="398" y="{182 + i * 30}" width="212" height="1" fill="{P["rule"]}"/>')
        b.append(f'<rect x="{398 + i * 42}" y="182" width="1" height="148" fill="{P["rule"]}"/>')
    for x, y in ((432, 214), (462, 244), (498, 226), (540, 276), (566, 238), (520, 304)):
        b.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{P["accent"]}"/>')
    b.append(f'<circle cx="540" cy="276" r="14" fill="none" stroke="{P["ink"]}" stroke-width="1.5"/>')
    return svg("".join(b), background=P["paper"])


# --------------------------------------------------------------------------------------
# 4. Sourdough — kitchen table (kitchen_table)
# --------------------------------------------------------------------------------------
def sourdough_kitchen_table() -> str:
    b = []
    # table surface and hard edge
    b.append(f'<rect x="0" y="238" width="640" height="122" fill="{P["lamp-soft"]}"/>')
    b.append(f'<rect x="0" y="236" width="640" height="3" fill="{P["ink"]}"/>')
    # banneton: bowl outline with three coil arcs
    b.append(
        f'<path d="M92 236 A 82 82 0 0 0 256 236 Z" fill="{P["paper-raised"]}" '
        f'stroke="{P["ink"]}" stroke-width="4"/>'
    )
    for r in (58, 40, 22):
        b.append(f'<path d="M{174 - r} 236 A {r} {r} 0 0 1 {174 + r} 236" fill="none" stroke="{P["ink-soft"]}" stroke-width="2"/>')
    # dough dome with scoring slashes
    b.append(
        f'<path d="M286 236 A 62 62 0 0 1 410 236 Z" fill="{P["lamp"]}" stroke="{P["ink"]}" stroke-width="4"/>'
    )
    for dx, top in ((-26, 208), (0, 204), (26, 209)):
        b.append(
            f'<path d="M{348 + dx} 216 q8 -14 2 -{216 - top} q-3 -8 1 -12" fill="none" '
            f'stroke="{P["paper"]}" stroke-width="3" stroke-linecap="round"/>'
        )
    # bench scraper
    b.append(f'<rect x="440" y="168" width="34" height="68" rx="2" fill="{P["ink"]}"/>')
    b.append(f'<rect x="440" y="168" width="34" height="22" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="2"/>')
    # linen fold
    b.append(
        f'<path d="M492 236 L508 196 L556 208 L548 236 Z" fill="{P["paper-raised"]}" '
        f'stroke="{P["rule"]}" stroke-width="1"/>'
    )
    for y in (208, 218, 228):
        b.append(f'<rect x="498" y="{y}" width="54" height="1" fill="{P["rule"]}"/>')
    # three jars, lids in lamp
    for x, w, h in ((576, 24, 46), (606, 22, 38), (632, 0, 0)):
        if w:
            b.append(f'<rect x="{x}" y="{236 - h}" width="{w}" height="{h}" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="2"/>')
            b.append(f'<rect x="{x - 2}" y="{236 - h - 6}" width="{w + 4}" height="6" fill="{P["lamp"]}"/>')
    return svg("".join(b), background=P["paper"])


# --------------------------------------------------------------------------------------
# 5. Anti-generic swap diagram (a review instrument; labels allowed)
# --------------------------------------------------------------------------------------
def swap_diagram() -> str:
    panel_w, panel_h = 300, 300
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="430" viewBox="0 0 640 430" '
        f'role="img"><rect width="640" height="430" fill="{P["paper-raised"]}"/>'
    )
    b = [head]
    # panel frames
    for x in (20, 320):
        b.append(
            f'<rect x="{x}" y="56" width="{panel_w}" height="{panel_h}" fill="{P["paper"]}" '
            f'stroke="{P["rule"]}" stroke-width="1"/>'
        )
    # left pane: Japanese motifs (lantern + steam + noren)
    b.append(f'<rect x="96" y="96" width="52" height="84" rx="18" fill="{P["lamp"]}"/>')
    b.append(f'<rect x="93" y="90" width="58" height="6" fill="{P["ink"]}"/>')
    b.append(f'<rect x="148" y="120" width="4" height="140" fill="{P["ink"]}"/>')
    b.append(f'<rect x="152" y="120" width="88" height="96" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="2"/>')
    b.append(f'<rect x="152" y="120" width="88" height="10" fill="{P["lamp"]}"/>')
    for x in (176, 200, 224):
        b.append(f'<rect x="{x}" y="136" width="2" height="80" fill="{P["paper"]}"/>')
    b.append(f'<path d="M64 280 q6 -10 0 -18 q-6 -8 0 -16" fill="none" stroke="{P["ink-soft"]}" stroke-width="2"/>')
    # right pane: same composition, head gasket motifs swapped in
    b.append(f'<rect x="396" y="96" width="52" height="84" rx="6" fill="{P["rule"]}" stroke="{P["ink"]}" stroke-width="3"/>')
    b.append(f'<circle cx="422" cy="138" r="14" fill="none" stroke="{P["ink"]}" stroke-width="5"/>')
    b.append(f'<rect x="448" y="120" width="4" height="140" fill="{P["ink"]}"/>')
    b.append(f'<rect x="452" y="120" width="88" height="96" fill="{P["paper-raised"]}" stroke="{P["ink"]}" stroke-width="2"/>')
    b.append(f'<rect x="452" y="120" width="88" height="10" fill="{P["rule"]}"/>')
    for y in (140, 164, 188):
        b.append(f'<rect x="460" y="{y}" width="72" height="1" fill="{P["rule"]}"/>')
    b.append(f'<g transform="translate(372 268) rotate(24)"><rect x="0" y="-4" width="56" height="8" rx="4" fill="{P["ink"]}"/><circle cx="0" cy="0" r="9" fill="none" stroke="{P["ink"]}" stroke-width="5"/></g>')
    # labels
    def label(x, y, text, fill, size=13, weight=600):
        return (
            f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}">{text}</text>'
        )

    b.append(label(20, 32, "ANTI-GENERIC SWAP CHECK", P["ink"], 14, 600))
    b.append(label(20, 82, "A. Japanese L0 \u2014 field_atlas / lantern district", P["ink"], 12, 600))
    b.append(label(320, 82, "B. Same plate, subject swapped to head gasket", P["ink"], 12, 600))
    b.append(label(20, 384, "PASS only if the motifs, grammar and palette path change. A plate that still reads after the swap is REJECTED.", P["ink-soft"], 11, 400))
    b.append(label(20, 404, "Plate A: lantern + noren + cafe steam + counter. Plate B: gasket ring + pegboard wrench + manual spine + tray.", P["ink-soft"], 11, 400))
    b.append(f'<rect x="20" y="410" width="0" height="0" fill="{P["paper"]}"/>')
    b.append("</svg>\n")
    return "".join(b)


SANS = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'


BOARDS = {
    "japanese-lantern-district.svg": (
        japanese_lantern_district,
        "Japanese L0 course world \u2014 lantern district / cafe lesson. Grammar field_atlas (lantern variant). "
        "Motifs: paper lantern with ink cap and one horizontal rib; cafe counter edge with two stools; "
        "noren doorway panel; cup with steam. Textless; orientation only.",
    ),
    "head-gasket-service-bay.svg": (
        head_gasket_service_bay,
        "Head gasket course world \u2014 service bay / workshop manual. Grammar workshop_manual. "
        "Motifs: two-post lift and crossbeam; tool wall with wrench silhouettes; component tray with gasket ring; "
        "open blank shop manual. Textless; never a torque, clearance or sequence authority.",
    ),
    "astronomy-observatory.svg": (
        astronomy_observatory,
        "Astronomy course world \u2014 observatory. Grammar observatory. "
        "Motifs: dome slit and telescope on a pier; plotted star-chart grid with one circle mark; horizon line. "
        "Textless; the chart is decorative, never a measurement.",
    ),
    "sourdough-kitchen-table.svg": (
        sourdough_kitchen_table,
        "Sourdough course world \u2014 kitchen table. Grammar kitchen_table. "
        "Motifs: coiled banneton with three arcs; scored dough dome; bench scraper; linen fold and stoneware jars. "
        "Textless; no temperature, timing or recipe value.",
    ),
    "anti-generic-swap.svg": (
        swap_diagram,
        "Anti-generic swap instrument: the Japanese plate beside the same composition with head-gasket motifs. "
        "A diagram, not a plate; labels are allowed here only.",
    ),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "card": "GM-013",
        "lane": "host-composed reference boards",
        "palette_source": "contracts/cb.tokens.v2.json",
        "palette_tokens_used": ["paper", "paper-raised", "ink", "ink-soft", "rule", "lamp", "lamp-soft", "accent"],
        "rules": {
            "text": "no <text> element in any plate",
            "state_hues_forbidden": ["ochre", "coral", "plum"],
            "model_call": "none",
            "licence": "CC0-1.0 (our own work)",
            "role": "orientation",
        },
        "boards": {},
    }
    for name, (fn, note) in BOARDS.items():
        body = fn()
        path = OUT / name
        path.write_text(body, encoding="utf-8")
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        manifest["boards"][name] = {
            "sha256": digest,
            "bytes": len(body.encode("utf-8")),
            "width": 640,
            "height": 360 if name != "anti-generic-swap.svg" else 430,
            "role": "orientation" if name != "anti-generic-swap.svg" else "review-instrument",
            "produced_by": "scripts/build_gm_visual_assets.py",
            "model": None,
            "prompt": None,
            "licence": "CC0-1.0",
            "note": note,
        }
        print(f"{name}: {digest[:12]} {len(body)} bytes")
    manifest_path = ROOT / "docs" / "gm-visual" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"manifest: {manifest_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
