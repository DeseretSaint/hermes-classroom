#!/usr/bin/env python3
"""The v3 visual audit: the v2 M4 audit's claims, re-versioned against the v3 contract.

``scripts/m4v-audit.py`` is the v2 evidence gate. Its claims (C-01 … C-15) are written against the
Atlas Lamp v2 tokens, the v2 screens and the v2 text_placements, so they cannot be pointed at v3
without either weakening them or changing the contract they read. This script is the v3 half:

* **static phase** (always runnable) — recompute the contract's own gates, check the contract's
  internal text-placement rule, and check every v3 source claim (token literal equals the contract,
  hex only in the two token literals, no blur/glass, elevation shadows only, the named vignette only,
  selectors scoped to ``[data-cb-v3]``, ``CB `` font families, motion durations from the v3 table,
  no ``vw``).
* **paint phase** (``--full``) — refuses, always and non-zero, until a painted-claim implementation
  exists. The v3 surfaces and a headless Chromium existing is not a measurement: no frame is read
  and no capture stamp is verified, so the phase may not write a PASS it did not earn. It names what
  is missing and what is unimplemented, and the screen cards own the stamped frames it will read.

Every run writes an audit JSON with a **module sha pin** (``plugin_sha256``) and a contract pin
(``contract_sha256``); ``tests/test_v3_visual_audit.py`` re-derives both and fails if they do not
match the files on disk, so evidence cannot be inherited from another build.

    python3 scripts/v3-audit.py                 # static, writes ${TMPDIR}/coursebook-v3-audit/
    V3A_OUT=audit/visual/v3-visual python3 scripts/v3-audit.py --full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.cb_source_scope import (  # noqa: E402
    DURATION,
    GRADIENT,
    HEX,
    PLUGIN_JS,
    TOKEN_LITERAL_CONSTS,
    V3_CSS_CONST,
    V3_TOKEN_CONST,
    css_blocks,
    declarations,
    literal_span,
    literal_text,
    split_selectors,
    style_rules,
    stylesheet_spans,
    without_shelf_edge_mask,
)

CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
DEFAULT_OUT = Path(os.environ.get("V3A_OUT") or (Path(tempfile.gettempdir()) / "coursebook-v3-audit"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(channels[0]) + 0.7152 * linear(channels[1]) + 0.0722 * linear(channels[2])


def contrast(foreground: str, background: str) -> float:
    first, second = luminance(foreground), luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


def claim(ident: str, text: str, status: str, evidence: dict) -> dict:
    return {"id": ident, "claim": text, "status": status, "evidence": evidence}


def static_claims(contract: dict, source: str) -> tuple[list[dict], dict]:
    claims: list[dict] = []

    # -- V-01 contract shape ------------------------------------------------------------------
    roles = contract.get("roles") or []
    modes = contract.get("modes") or {}
    shape_ok = (
        contract.get("version") == 3
        and len(roles) == 18
        and set(modes) == {"light", "dark"}
        and all(set(palette) == set(roles) for palette in modes.values())
    )
    claims.append(claim(
        "V-01",
        "The v3 contract declares 18 roles, both modes, and every mode carries every role.",
        "PASS" if shape_ok else "FAIL",
        {"roles": len(roles), "modes": sorted(modes), "version": contract.get("version")},
    ))

    # -- V-02 contrast gates ------------------------------------------------------------------
    failures = []
    ratios = []
    for mode, palette in modes.items():
        for gate in contract.get("gates") or []:
            foreground = palette.get(gate.get("foreground"))
            background = palette.get(gate.get("background"))
            if not foreground or not background:
                continue
            ratio = contrast(foreground, background)
            ratios.append((mode, gate["foreground"], gate["background"], ratio, gate["min"]))
            if round(ratio, 2) < float(gate["min"]):
                failures.append({"mode": mode, "pair": f"{gate['foreground']} on {gate['background']}",
                                 "ratio": round(ratio, 2), "min": gate["min"]})
    min_ratio = min(ratios, key=lambda item: item[3] / item[4]) if ratios else None
    claims.append(claim(
        "V-02",
        "Every contract gate clears its floor in both modes, computed on the values that ship.",
        "PASS" if ratios and not failures else "FAIL",
        {
            "gates": len(contract.get("gates") or []) * len(modes),
            "failures": failures,
            "tightest": (
                {"mode": min_ratio[0], "pair": f"{min_ratio[1]} on {min_ratio[2]}",
                 "ratio": round(min_ratio[3], 4), "min": min_ratio[4]}
                if min_ratio else None
            ),
            "method": "WCAG 2.x relative luminance; compare round(ratio, 2) to the floor",
        },
    ))

    # -- V-03 text placements -----------------------------------------------------------------
    placements = contract.get("text_placements") or {}
    gated = {(gate["foreground"], gate["background"]) for gate in contract.get("gates") or []
             if gate.get("kind") == "text"}
    placement_gaps = [f"{text_role} on {ground}"
                      for text_role, grounds in placements.items() for ground in grounds
                      if (text_role, ground) not in gated]
    claims.append(claim(
        "V-03",
        "Every text role paints only on a ground the contract gates for it, at 4.5:1 or better.",
        "PASS" if placements and not placement_gaps else "FAIL",
        {"text_roles": sorted(placements), "ungated_pairs": placement_gaps},
    ))

    # -- V-04 … V-11 the v3 material ----------------------------------------------------------
    token_literal = literal_text(source, V3_TOKEN_CONST)
    css = literal_text(source, V3_CSS_CONST)
    built = token_literal is not None and css is not None
    not_built = "v3 material is not built yet (CP-020a); this claim is armed and unproven"

    def status(ok: bool) -> str:
        return ("PASS" if ok else "FAIL") if built else "NOT-BUILT"

    # V-04 token literal
    literal_evidence: dict = {"constant": V3_TOKEN_CONST}
    literal_ok = False
    if token_literal is not None:
        try:
            parsed = json.loads(token_literal)
        except json.JSONDecodeError as error:
            literal_evidence["parse_error"] = str(error)
            parsed = None
        if isinstance(parsed, dict):
            projection = {key: contract[key] for key in parsed if key in contract}
            literal_ok = (
                all(key in parsed for key in ("modes", "elevation", "radii", "type", "motion"))
                and set(parsed).issubset(contract)
                and all(parsed[key] == contract[key] for key in parsed if key in contract)
                and token_literal == json.dumps(projection, ensure_ascii=False, separators=(",", ":"))
            )
            literal_evidence.update({
                "keys": sorted(parsed),
                "canonical": token_literal == json.dumps(projection, ensure_ascii=False, separators=(",", ":")),
                "matches_contract": all(parsed[key] == contract[key] for key in parsed if key in contract),
            })
    claims.append(claim(
        "V-04",
        f"`{V3_TOKEN_CONST}` carries the v3 contract byte for byte (canonical serialization).",
        status(literal_ok), literal_evidence | ({} if built else {"reason": not_built}),
    ))

    # V-05 raw hex only in the token literals
    masked = source
    for name in TOKEN_LITERAL_CONSTS:
        span = literal_span(masked, name)
        if span is not None:
            masked = masked[:span[0]] + " " * (span[1] - span[0]) + masked[span[1]:]
    stray = HEX.findall(masked)
    claims.append(claim(
        "V-05",
        "A raw hex appears only inside the two token literals, never in a surface or stylesheet rule.",
        status(not stray), {"stray_hex": stray[:12], "count": len(stray),
                            **({} if built else {"reason": not_built})},
    ))

    rules = css_blocks(css) if css is not None else []
    style = style_rules(css) if css is not None else []
    pairs = [(prop, value) for _, body in rules for prop, value in declarations(body)]

    # V-06 glass
    bans = [word for word in ("backdrop-filter", "backdropFilter", "blur(") if word in source]
    claims.append(claim(
        "V-06",
        "No backdrop-filter, no blur and no glass anywhere in the module.",
        status(not bans), {"found": bans, **({} if built else {"reason": not_built})},
    ))

    # V-07 elevation shadows
    outside = source
    # Only CB_V3_CSS is an exemption; a CB-V3-* marker is cut from the v2 region by the seam and
    # must not become a second, ungated home for paint declarations.
    for start, end in reversed(stylesheet_spans(source)):
        outside = outside[:start] + outside[end:]
    shadow_values = [value for prop, value in pairs if prop == "box-shadow"]
    shadow_ok = (
        "box-shadow" not in outside.lower()
        and "boxShadow" not in outside
        and all(value.startswith("var(--cb3-elev-") and value.endswith(")") for value in shadow_values)
    )
    claims.append(claim(
        "V-07",
        "`box-shadow` appears only inside `CB_V3_CSS` and only as a `var(--cb3-elev-*)` token.",
        status(shadow_ok),
        {"declarations": len(shadow_values), "values": sorted(set(shadow_values)),
         **({} if built else {"reason": not_built})},
    ))

    # V-08 the named vignette
    gradients = [(prop, value) for prop, value in pairs if GRADIENT.search(value)]
    outside_gradients = GRADIENT.findall(without_shelf_edge_mask(outside))
    gradient_ok = not outside_gradients and all(prop.startswith("--cb3-vignette")
                                                for prop, _ in gradients)
    claims.append(claim(
        "V-08",
        "The only gradient is the named vignette, declared on a `--cb3-vignette*` property.",
        status(gradient_ok),
        {"gradients": [prop for prop, _ in gradients], "outside_stylesheet": len(outside_gradients),
         **({} if built else {"reason": not_built})},
    ))

    # V-09 scope
    unscoped = [selector for prelude, _ in style for selector in split_selectors(prelude)
                if not selector.startswith("[data-cb-v3]")]
    claims.append(claim(
        "V-09",
        "Every selector in `CB_V3_CSS` starts with `[data-cb-v3]` (at-rules excepted).",
        status(not unscoped),
        {"style_rules": len(style), "unscoped": unscoped[:10], **({} if built else {"reason": not_built})},
    ))

    # V-10 fonts
    faces = [(prelude, body) for prelude, body in rules if prelude.startswith("@font-face")]
    face_families = [value.strip().strip("'\"") for _, body in faces
                     for prop, value in declarations(body) if prop == "font-family"]
    literal_families = [value for prop, value in pairs if prop == "font-family" and not value.startswith("var(")]
    font_ok = all(name.startswith("CB ") for name in face_families) and all(
        (split_selectors(value)[0] if value else "").strip().strip("'\"").startswith("CB ")
        for value in literal_families
    )
    claims.append(claim(
        "V-10",
        "Every `@font-face` family and every literal `font-family` declaration leads with a `CB ` face.",
        status(font_ok),
        {"faces": face_families, "literal_declarations": len(literal_families),
         **({} if built else {"reason": not_built})},
    ))

    # V-11 motion
    motion = contract.get("motion") or {}
    expected = {name: f"{motion[name]}ms" for name in ("press", "lift", "route", "verdict", "complete")}
    table: dict[str, str] = {}
    escaped = []
    for prop, value in pairs:
        if not DURATION.search(value):
            continue
        if prop.startswith("--cb3-dur-"):
            table[prop[len("--cb3-dur-"):]] = value
        else:
            escaped.append((prop, value))
    animation = [word for word in ("@keyframes", "animation:", "animation-name", "infinite")
                 if css is not None and word in css]
    motion_ok = table == expected and not escaped and not animation
    claims.append(claim(
        "V-11",
        "Motion durations come only from the v3 motion table; no keyframe, animation or infinite loop.",
        status(motion_ok),
        {"table": table, "expected": expected, "escaped": escaped, "animation": animation,
         **({} if built else {"reason": not_built})},
    ))

    # V-12 route-relative measurement
    vw = [] if css is None else re.findall(r"(?<![\w.-])\d+(?:\.\d+)?vw\b", css)
    claims.append(claim(
        "V-12",
        "No `vw` value on a v3 surface: measurement is route-relative (SPEC-V3 §3.1).",
        status(not vw), {"vw_values": vw, **({} if built else {"reason": not_built})},
    ))

    summary = {
        "phase": "static",
        "surfaces_built": built,
        "plugin": str(PLUGIN_JS.relative_to(ROOT)),
        "plugin_sha256": sha256(PLUGIN_JS),
        "contract": str(CONTRACT.relative_to(ROOT)),
        "contract_sha256": sha256(CONTRACT),
        "branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip(),
        "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip(),
        "claims": {item["id"]: item["status"] for item in claims},
        "failed": [item["id"] for item in claims if item["status"] == "FAIL"],
        "not_built": [item["id"] for item in claims if item["status"] == "NOT-BUILT"],
        "note": "the evidence is pinned by plugin_sha256 and contract_sha256; a frame without a "
                "matching pin is stale evidence",
    }
    return claims, summary


def full_phase() -> int:
    """The painted audit. Refuses until a painted-claim implementation exists.

    Returning success here would be the exact failure the card forbids: `CB_V3_CSS` existing and a
    browser being installed is *not* a measurement. No frame is read and no stamp is verified below,
    so the phase reports the missing inputs and then refuses unconditionally. A later card that
    implements the paint claims replaces this refusal with the real reads (and must still return
    non-zero if a frame or its stamp is missing).
    """
    missing = []
    if literal_text(PLUGIN_JS.read_text(encoding="utf-8"), V3_CSS_CONST) is None:
        missing.append(f"desktop/plugin.js has no {V3_CSS_CONST} (CP-020a)")
    if shutil.which("chromium") is None:
        missing.append("chromium is not on PATH")
    if not (ROOT / "scripts" / "cp-capture.mjs").is_file():
        missing.append("scripts/cp-capture.mjs is missing (CP-000)")
    print("v3 paint audit refused — the paint phase is unimplemented:", file=sys.stderr)
    for item in missing:
        print("  -", item, file=sys.stderr)
    print("  - no painted-claim implementation exists: this phase reads no frame and verifies no "
          "stamp, so it cannot report a painted PASS", file=sys.stderr)
    print("  - the screen cards own their stamped captures through scripts/cp-capture.mjs; until "
          "this phase reads those frames and stamps it must stay non-zero", file=sys.stderr)
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="also require the painted v3 surfaces")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="audit output directory")
    args = parser.parse_args()

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = PLUGIN_JS.read_text(encoding="utf-8")
    claims, summary = static_claims(contract, source)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    evidence = {"version": 3, "claims": claims, "summary": summary}
    (out / "audit.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"claims: {sum(1 for c in claims if c['status'] == 'PASS')} PASS, "
          f"{len(summary['failed'])} FAIL, {len(summary['not_built'])} NOT-BUILT")
    if summary["failed"]:
        return 1
    if args.full:
        return full_phase()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
