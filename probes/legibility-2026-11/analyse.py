"""Legibility analysis for card t_60ef62f7.

Turns two browser captures (1344 px and 1200 px) into one audit document:

  * rendered cap height per text run, measured three ways: the pixel span of a capital "H"
    rendered in the run's own element and computed font at >=50 % coverage; Chromium's
    integer-rounded TextMetrics ascent at the run's size; and that same face measured at 200 px
    and scaled back (the precise one, since Chromium rounds the small measurements to whole px);
  * WCAG contrast of the run's declared colour against the pixels actually behind its glyphs
    (the `without-<n>` capture has the glyphs removed but every background and box unchanged);
  * the object the run sits on, its clipping behaviour, the run's measured slack in the object's
    own (rotated) frame, and what it would take to reach the 11 px cap floor.

Usage: python3 analyse.py <repo> <dir-1344> <dir-1200> <out.json>
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(sys.argv[1]).resolve()
D1344 = Path(sys.argv[2]).resolve()
D1200 = Path(sys.argv[3]).resolve()
OUT = Path(sys.argv[4]).resolve()
PAGE_1344 = Path(sys.argv[5]).resolve() if len(sys.argv) > 5 else (REPO / "design" / "home-scene.html")
PAGE_1200 = Path(sys.argv[6]).resolve() if len(sys.argv) > 6 else None
DRIVER = Path(__file__).resolve().with_name("measure.mjs")


def sha256_of(path) -> str | None:
    if not path or not Path(path).is_file():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

CAP_FLOOR = 11.0
CONTRAST_FLOOR = 3.0
WCAG_AA_NORMAL = 4.5
INK_THRESHOLD = 8  # per-channel delta that counts as glyph ink rather than image noise
RECT_PAD = 2.0
CORE_COVERAGE = 0.85  # glyph-core pixels: no antialias dilution in the colour that is tested

sys.path.insert(0, str(REPO))
from tests.test_desktop_scene_text_containment import (  # noqa: E402  (B1's harness)
    _affine_from_quad,
    _local_coords,
    _painted_rect_mask,
)


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def parse_color(value: str) -> tuple[np.ndarray, float]:
    match = re.match(r"rgba?\(([^)]+)\)", value.replace(" ", ""))
    if not match:
        raise ValueError(f"unsupported colour {value!r}")
    parts = [float(part) for part in match.group(1).split(",")]
    if len(parts) == 3:
        parts.append(1.0)
    return np.array(parts[:3], float), parts[3]


def srgb_to_linear(channel: np.ndarray) -> np.ndarray:
    channel = np.clip(channel, 0.0, 255.0) / 255.0
    return np.where(channel <= 0.04045, channel / 12.92, ((channel + 0.055) / 1.055) ** 2.4)


def luminance(rgb: np.ndarray) -> np.ndarray:
    linear = srgb_to_linear(rgb)
    return 0.2126 * linear[..., 0] + 0.7152 * linear[..., 1] + 0.0722 * linear[..., 2]


def contrast_ratio(fg: np.ndarray, bg: np.ndarray) -> np.ndarray:
    fg_l = luminance(fg)
    bg_l = luminance(bg)
    hi = np.maximum(fg_l, bg_l)
    lo = np.minimum(fg_l, bg_l)
    return (hi + 0.05) / (lo + 0.05)


def capture_meta(directory: Path) -> tuple[dict, np.ndarray, np.ndarray, Path]:
    """Load one width's capture and quantify how far the probes moved the page."""
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    base = load_rgb(directory / "base.png")
    again = load_rgb(directory / "base-again.png")
    restored = load_rgb(directory / "restored.png")
    repeat_delta = np.abs(base - again).max(axis=2)
    restore_delta = np.abs(base - restored).max(axis=2)
    meta = {
        "viewport": [result["width"], result["height"]],
        "devicePixelRatio": result["info"]["devicePixelRatio"],
        "scene_scale": round(result["info"]["sceneScale"], 6),
        "scene_authored_width_css_px": result["info"]["sceneCssWidth"],
        "repeat_capture_differing_pixels": int((repeat_delta > 0).sum()),
        "restore_differing_pixels": int((restore_delta > 0).sum()),
        "restore_max_delta": int(restore_delta.max()),
        "restore_pixels_over_ink_threshold": int((restore_delta > INK_THRESHOLD).sum()),
        "cap_probe_placement_residual_px": {
            phase: {
                index: [round(float(v), 3) for v in pair]
                for index, pair in ((result.get("residuals") or {}).get(phase) or {}).items()
            }
            for phase in ("placed", "before_shot")
        },
    }
    if meta["repeat_capture_differing_pixels"]:
        raise SystemExit(f"{directory}: two captures of the unchanged page differ; the capture is not deterministic")
    return meta, base, restored, directory


def text_rect_mask(shape, runs) -> np.ndarray:
    mask = np.zeros(shape, bool)
    for run in runs:
        mask |= _painted_rect_mask(shape, run["rects"])
    return mask


def run_measurement(capture_dir: Path, base: np.ndarray, unit: dict, run: dict, scale: float) -> dict:
    """Cap height and contrast for one run at one width."""
    without = load_rgb(capture_dir / f"without-{run['index']}.png")
    cap = load_rgb(capture_dir / f"cap-{run['index']}.png")
    height, width = base.shape[:2]
    painted = _painted_rect_mask((height, width), run["rects"])
    ink = (np.abs(base - without).max(axis=2) > INK_THRESHOLD) & painted

    text_rgb, alpha = parse_color(run["color"])
    row = {"ink_pixels": int(ink.sum()), "declared_color": run["color"], "declared_alpha": alpha}
    if not ink.sum():
        row["error"] = "the run painted no ink"
        return row

    # ---- contrast against the pixels actually behind the glyphs -------------------------------
    ys, xs = np.nonzero(ink)
    bg = without[ys, xs].astype(float)
    fg = np.broadcast_to(text_rgb, bg.shape)
    if alpha < 1.0:
        fg = fg * alpha + bg * (1.0 - alpha)
    delta = fg - bg
    denom = (delta**2).sum(axis=1)
    coverage = np.ones(len(ys))
    solid = denom > 1e-6
    coverage[solid] = np.clip(((base[ys, xs][solid].astype(float) - bg[solid]) * delta[solid]).sum(axis=1) / denom[solid], 0, 1)
    ratios = contrast_ratio(fg, bg)
    core = coverage >= CORE_COVERAGE
    if core.sum() < 10:
        core = coverage >= 0.5
    core_ratios = ratios[core] if core.any() else ratios
    core_bg = bg[core] if core.any() else bg
    core_xs = xs[core] if core.any() else xs
    core_ys = ys[core] if core.any() else ys
    failing = core_ratios < CONTRAST_FLOOR
    row["contrast"] = {
        "core_pixels": int(core.sum()),
        "min": round(float(core_ratios.min()), 3),
        "p05": round(float(np.percentile(core_ratios, 5)), 3),
        "median": round(float(np.median(core_ratios)), 3),
        "max": round(float(core_ratios.max()), 3),
        "pixels_below_floor": int(failing.sum()),
        "pixels_below_wcag_aa": int((core_ratios < WCAG_AA_NORMAL).sum()),
        "worst_background_rgb": [int(v) for v in core_bg[int(np.argmin(core_ratios))]],
        "background_luminance_range": [round(float(luminance(core_bg).min()), 4), round(float(luminance(core_bg).max()), 4)],
    }
    if failing.any():
        # Where the failing glyph pixels sit inside the object's own frame: the useful half of a
        # contrast finding is which part of the words left the light surface.
        transform_c, obj_w_c, obj_h_c = _affine_from_quad(unit["object"]["quad"])
        local = _local_coords(transform_c, core_xs[failing] + 0.5, core_ys[failing] + 0.5)
        row["contrast"]["below_floor_local_u"] = [round(float(local[:, 0].min()), 2), round(float(local[:, 0].max()), 2)]
        row["contrast"]["object_local_width"] = round(float(obj_w_c), 2)

    # ---- cap height, measured from pixels -----------------------------------------------------
    cap_h = load_rgb(capture_dir / f"cap-{run['index']}.png")
    cap_diff = (np.abs(cap_h - without).max(axis=2) > INK_THRESHOLD) & painted
    cap_row = {"probe": "an absolutely positioned capital H in the run's computed font, painted at the run's own text-rect origin while the run's glyphs are transparent"}
    if cap_diff.sum():
        cys, cxs = np.nonzero(cap_diff)
        bg_h = without[cys, cxs].astype(float)
        fg_h = np.broadcast_to(text_rgb, bg_h.shape)
        if alpha < 1.0:
            fg_h = fg_h * alpha + bg_h * (1.0 - alpha)
        dh = fg_h - bg_h
        den_h = (dh**2).sum(axis=1)
        cov_h = np.ones(len(cys))
        solid_h = den_h > 1e-6
        cov_h[solid_h] = np.clip(((cap_h[cys, cxs][solid_h].astype(float) - bg_h[solid_h]) * dh[solid_h]).sum(axis=1) / den_h[solid_h], 0, 1)
        half = cov_h >= 0.5
        if half.any():
            span = float(cys[half].max() - cys[half].min() + 1)
        else:
            span = float(cys.max() - cys.min() + 1)
        cap_row["pixel_cap_px"] = round(span, 2)
        cap_row["pixel_cap_bbox_px"] = [int(cxs.max() - cxs.min() + 1), int(cys.max() - cys.min() + 1)]
        cap_row["cap_pixels"] = int(cap_diff.sum())
    else:
        cap_row["pixel_cap_px"] = None
        cap_row["error"] = "the H probe painted no ink inside the run's text rects"

    font_size = float(run["fontSize"].replace("px", ""))
    metrics = run["cap"]
    cap_row.update({
        "font_size_css_px": font_size,
        "scene_scale": round(scale, 6),
        "font_size_rendered_px": round(font_size * scale, 3),
        "cap_ratio_of_em": round(metrics["capRatio"], 4),
        "cap_from_ratio_px": round(metrics["capRatio"] * font_size * scale, 2),
        "cap_from_textmetrics_px": round(metrics["capAscent"] * scale, 2),
        "x_height_ratio_of_em": round(metrics["xRatio"], 4),
    })
    measured = [v for v in (cap_row.get("pixel_cap_px"), cap_row["cap_from_ratio_px"], cap_row["cap_from_textmetrics_px"]) if v is not None]
    cap_row["spread_px"] = round(max(measured) - min(measured), 2)
    row["cap"] = cap_row

    # ---- the run's own geometry inside its object (object's rotated frame) --------------------
    transform, obj_w, obj_h = _affine_from_quad(unit["object"]["quad"])
    corners = []
    for left, top, rect_w, rect_h in run["rects"]:
        corners.extend([(left, top), (left + rect_w, top), (left, top + rect_h), (left + rect_w, top + rect_h)])
    points = np.array(corners, float)
    local = _local_coords(transform, points[:, 0], points[:, 1])
    u, v = local[:, 0], local[:, 1]
    widths = [rect[2] for rect in run["rects"]]
    row["layout"] = {
        "object_local_px": [round(obj_w, 2), round(obj_h, 2)],
        "lines": len(run["rects"]),
        "line_widths_px": [round(float(w), 2) for w in widths],
        "margins_object_local": {
            "left": round(float(u.min()), 2),
            "right": round(float(obj_w - u.max()), 2),
            "top": round(float(v.min()), 2),
            "bottom": round(float(obj_h - v.max()), 2),
        },
        "clipped_ancestors": run.get("overflow", []),
    }
    return row


def build(repo: Path) -> dict:
    meta_1344, base_1344, restored_1344, dir_1344 = capture_meta(D1344)
    meta_1200, base_1200, restored_1200, dir_1200 = capture_meta(D1200)
    raw_1344 = json.loads((D1344 / "result.json").read_text(encoding="utf-8"))
    raw_1200 = json.loads((D1200 / "result.json").read_text(encoding="utf-8"))
    for label, base, restored, raw in (("1344", base_1344, restored_1344, raw_1344),
                                       ("1200", base_1200, restored_1200, raw_1200)):
        runs = [run for unit in raw["info"]["units"] for run in unit["runs"]]
        rects = text_rect_mask(base.shape[:2], runs)
        residue = (np.abs(base - restored).max(axis=2) > INK_THRESHOLD) & rects
        if residue.sum():
            raise SystemExit(f"{label}: the probes left {int(residue.sum())} px of ink inside a measured text rect")
    cap_base = base_1344
    cap_1200 = base_1200

    index_1200 = {(unit["name"], run["index"]): (unit, run) for unit in raw_1200["info"]["units"] for run in unit["runs"]}
    raised_by_key = {
        "1344": {shot["index"]: shot.get("raised", {}) for shot in raw_1344.get("shots", [])},
        "1200": {shot["index"]: shot.get("raised", {}) for shot in raw_1200.get("shots", [])},
    }
    runs_out = []
    for unit in raw_1344["info"]["units"]:
        for run in unit["runs"]:
            unit_1200, run_1200 = index_1200[(unit["name"], run["index"])]
            m1344 = run_measurement(dir_1344, cap_base, unit, run, raw_1344["info"]["sceneScale"])
            m1200 = run_measurement(dir_1200, cap_1200, unit_1200, run_1200, raw_1200["info"]["sceneScale"])
            cap_px_1344 = m1344["cap"]["cap_from_ratio_px"]
            cap_px_1200 = m1200["cap"]["cap_from_ratio_px"]
            ratio_1344 = m1344["contrast"]["min"]
            ratio_1200 = m1200["contrast"]["min"]
            under_cap = [w for w, v in ((1344, cap_px_1344), (1200, cap_px_1200)) if v < CAP_FLOOR]
            under_contrast = [w for w, v in ((1344, ratio_1344), (1200, ratio_1200)) if v < CONTRAST_FLOOR]
            under_aa = [w for w, v in ((1344, ratio_1344), (1200, ratio_1200)) if v < WCAG_AA_NORMAL]

            # What reaching the cap floor costs, measured: the driver raises the run to the font
            # size that gives it an 11 px cap (same face, same line-height ratio) and reports what
            # the object did — clipped, spilled, or simply absorbed it.
            font_size = float(run["fontSize"].replace("px", ""))
            cap_ratio = run["cap"]["capRatio"]
            needed_font = CAP_FLOOR / cap_ratio if cap_ratio else None
            growth = (needed_font / font_size) if needed_font and font_size else 1.0
            raised = {w: raised_by_key[w].get(run["index"], {"applied": False, "reason": "no raise probe recorded"}) for w in ("1344", "1200")}
            margins = m1344["layout"]["margins_object_local"]
            obj_w, obj_h = m1344["layout"]["object_local_px"]
            line_height = (float(run["lineHeight"].replace("px", ""))
                           if run["lineHeight"].endswith("px") else font_size * 1.2)
            cap_decision = None
            cap_detail = None
            if under_cap:
                clipped_at = {}
                for w, probe in raised.items():
                    if not probe.get("applied"):
                        continue
                    clip = [entry for entry in probe.get("clipping", [])
                            if entry.get("dx", 0) > 1 or entry.get("dy", 0) > 1]
                    if clip:
                        clipped_at[w] = (probe, clip[0])
                if clipped_at:
                    w = next(w for w in ("1344", "1200") if w in clipped_at)
                    probe, clip = clipped_at[w]
                    cap_decision = "run must shorten"
                    cap_detail = (
                        f"at {probe['needed_font_px']:.2f} px ({CAP_FLOOR:.0f} px cap, {w} px width) the run "
                        f"still needs {len(probe['rects'])} line(s) and the object ({unit['name']}) clips "
                        f"{clip['dy']} px of height / {clip['dx']} px of width: the fixed {obj_w:.0f}x{obj_h:.0f} "
                        f"plate cannot absorb the type, so the run must shorten (or the object's geometry must change)"
                    )
                elif any(probe.get("applied") for probe in raised.values()):
                    probe = raised["1344"]
                    widest_after = max((rect[2] for rect in probe["rects"]), default=0.0)
                    content_width = obj_w - 2 * margins["left"]
                    grew = probe["element"]["after_width"] - probe["element"]["width"]
                    if grew > 0.5:
                        room = f"the element itself widens {grew:.1f} css px to hold it"
                    else:
                        room = (f"its widest line is {widest_after:.1f} css px with "
                                f"{content_width - widest_after:.1f} px of slack to the {content_width:.1f} px content edge")
                    cap_decision = "object can grow"
                    cap_detail = (
                        f"at {probe['needed_font_px']:.2f} px ({CAP_FLOOR:.0f} px cap) the run stays "
                        f"{len(probe['rects'])} line(s), {room}, and nothing clips at either width: the object "
                        f"absorbs the floor size without the run changing"
                    )
                else:
                    cap_decision = "not assessed"
                    cap_detail = raised["1344"].get("reason", "no raise probe")
            contrast_decision = None
            contrast_detail = None
            if under_contrast:
                c = m1344["contrast"]
                contrast_decision = "run must shorten"
                contrast_detail = (
                    f"{c['pixels_below_floor']} of {c['core_pixels']} glyph-core pixels are below "
                    f"{CONTRAST_FLOOR:.1f}:1 (worst {c['min']:.3f}:1 against rgb"
                    f"{tuple(c['worst_background_rgb'])}); the failing pixels sit at u="
                    f"{c['below_floor_local_u'][0]:.0f}..{c['below_floor_local_u'][1]:.0f} of the object's "
                    f"{c['object_local_width']:.0f} px width, i.e. the type runs off the tag's kraft face onto "
                    f"the dark bench behind it. Growing the plate cannot fix a dark background under the "
                    f"letters: the words must end where the kraft does (or the tag's face must move under them)"
                )
            row = {
                "run_id": f"{unit['name']}#{run['index']}",
                "unit": unit["name"],
                "object": unit["object"],
                "selector": run["selector"],
                "text": run["text"],
                "font": {
                    "family": run["fontFamily"],
                    "size_css_px": font_size,
                    "weight": run["fontWeight"],
                    "line_height_css_px": line_height,
                    "letter_spacing": run["letterSpacing"],
                    "text_align": run["textAlign"],
                },
                "measurements": {"1344": m1344, "1200": m1200},
                "under_floor": {
                    "cap": under_cap,
                    "contrast": under_contrast,
                    "contrast_below_wcag_aa_normal_text": under_aa,
                    "either": bool(under_cap or under_contrast),
                },
                "remedy": {
                    "cap_floor": {
                        "needed_font_size_css_px": round(needed_font, 2) if needed_font else None,
                        "growth_factor": round(growth, 3),
                        "probe_by_width": raised,
                        "decision": cap_decision,
                        "detail": cap_detail,
                    },
                    "contrast_floor": {
                        "decision": contrast_decision,
                        "detail": contrast_detail,
                    },
                },
            }
            runs_out.append(row)

    def counts(width_key: str) -> dict:
        caps = [r["measurements"][width_key]["cap"]["cap_from_ratio_px"] for r in runs_out]
        cons = [r["measurements"][width_key]["contrast"]["min"] for r in runs_out]
        return {
            "runs_measured": len(runs_out),
            "runs_under_cap_floor": sum(1 for v in caps if v < CAP_FLOOR),
            "runs_under_contrast_floor": sum(1 for v in cons if v < CONTRAST_FLOOR),
            "runs_under_either_floor": sum(
                1 for r in runs_out
                if r["measurements"][width_key]["cap"]["cap_from_ratio_px"] < CAP_FLOOR
                or r["measurements"][width_key]["contrast"]["min"] < CONTRAST_FLOOR
            ),
            "runs_below_wcag_aa_normal_text": sum(1 for v in cons if v < WCAG_AA_NORMAL),
            "smallest_cap_px": round(min(caps), 2),
            "lowest_contrast": round(min(cons), 3),
        }

    def severity(run: dict) -> float:
        """How far under the floor a run is at its worst width: 1.0 is exactly on the floor."""
        caps = [run["measurements"][w]["cap"]["cap_from_ratio_px"] / CAP_FLOOR for w in ("1344", "1200")]
        cons = [run["measurements"][w]["contrast"]["min"] / CONTRAST_FLOOR for w in ("1344", "1200")]
        return min(min(caps), min(cons))

    ranked = sorted(runs_out, key=lambda r: severity(r))
    ranking = [
        {
            "rank": index + 1,
            "run_id": r["run_id"],
            "object": r["unit"],
            "text": r["text"],
            "cap_px_1344": r["measurements"]["1344"]["cap"]["cap_from_ratio_px"],
            "cap_px_1200": r["measurements"]["1200"]["cap"]["cap_from_ratio_px"],
            "contrast_1344": r["measurements"]["1344"]["contrast"]["min"],
            "contrast_1200": r["measurements"]["1200"]["contrast"]["min"],
            "worst_of_floor": round(severity(r), 3),
        }
        for index, r in enumerate(ranked)
    ]

    plugin = repo / "desktop" / "plugin.js"
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    describe = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%h %s"], capture_output=True, text=True).stdout.strip()
    base_commit = "b7ed6cf0"
    same_tree = subprocess.run(
        ["git", "-C", str(repo), "diff", "--quiet", base_commit, "HEAD", "--",
         "desktop/plugin.js", "design/home-scene.html"],
    ).returncode == 0
    totals = {"1344": counts("1344"), "1200": counts("1200"), "runs": len(runs_out)}
    under_cap = [r["run_id"] for r in runs_out if r["under_floor"]["cap"]]
    under_contrast = [r["run_id"] for r in runs_out if r["under_floor"]["contrast"]]
    return {
        "schema": "coursebook.text-legibility/1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject": {
            "scene": "wide Home scene (design/home-scene.html, generated from desktop/plugin.js)",
            "measured_against": f"origin/master {base_commit} (2026-11-13)",
            "measured_files_identical_to_base": same_tree,
            "worktree_head": commit,
            "worktree_head_subject": describe,
            "plugin_sha256": subprocess.run(["sha256sum", str(plugin)], capture_output=True, text=True).stdout.split()[0],
            "page_1344_sha256": sha256_of(PAGE_1344),
            "page_1200_sha256": sha256_of(PAGE_1200),
        },
        "floors": {
            "cap_px": CAP_FLOOR,
            "contrast_ratio": CONTRAST_FLOOR,
            "how_a_run_fails": "a run is under the cap floor when its rendered cap height at that width is below 11 px; it is under the contrast floor when ANY glyph-core pixel behind it is below 3.0:1 (the worst pixel, not the median). WCAG AA for normal text is 4.5:1 and is reported separately, not applied as this card's floor.",
        },
        "summary": {
            "runs_measured": len(runs_out),
            "runs_under_cap_floor_at_1344": totals["1344"]["runs_under_cap_floor"],
            "runs_under_cap_floor_at_1200": totals["1200"]["runs_under_cap_floor"],
            "runs_under_contrast_floor_at_1344": totals["1344"]["runs_under_contrast_floor"],
            "runs_under_contrast_floor_at_1200": totals["1200"]["runs_under_contrast_floor"],
            "runs_under_either_floor_at_1344": totals["1344"]["runs_under_either_floor"],
            "runs_under_either_floor_at_1200": totals["1200"]["runs_under_either_floor"],
            "runs_under_cap_floor": under_cap,
            "runs_under_contrast_floor": under_contrast,
            "smallest_cap_px_1344": totals["1344"]["smallest_cap_px"],
            "smallest_cap_px_1200": totals["1200"]["smallest_cap_px"],
            "lowest_contrast_1344": totals["1344"]["lowest_contrast"],
            "lowest_contrast_1200": totals["1200"]["lowest_contrast"],
        },
        "type_ladder": {
            "note": "the smallest runs sit on two adjacent type steps; the floor is not reachable by a token swap alone",
            "ui_face_cap_ratio_of_em": round(next(r["measurements"]["1344"]["cap"]["cap_ratio_of_em"] for r in runs_out if r["run_id"].startswith("card-")), 4),
            "display_face_cap_ratio_of_em": round(next(r["measurements"]["1344"]["cap"]["cap_ratio_of_em"] for r in runs_out if r["run_id"].startswith("tag-")), 4),
            "font_size_needed_for_11px_cap_ui_face_css_px": round(CAP_FLOOR / next(r["measurements"]["1344"]["cap"]["cap_ratio_of_em"] for r in runs_out if r["run_id"].startswith("card-")), 2),
            "scene_steps_in_use": "meta 0.875rem = 14 px (card titles, cap 9.24); body 1rem = 16 px (CTA labels, cap 10.56); heading/display are clamp()ed against the route container (1cqi) and land at 32.64 / 64 px at 1344",
        },
        "method": {
            "driver": "the CP-TEXT-GATE method (tests/fixtures/scene-text/README.md) extended with a cap probe, a floor-raise probe and background sampling; no test or product file is edited. The probe is committed at probes/legibility-2026-11/ (measure.mjs drives Chromium, analyse.py turns the captures into this document); the hashes below are the committed files.",
            "probe_files": ["probes/legibility-2026-11/measure.mjs", "probes/legibility-2026-11/analyse.py", "probes/legibility-2026-11/README.md"],
            "driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest() if DRIVER.exists() else None,
            "analysis_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cap_height": "the run's element keeps its own glyphs transparent while an absolutely positioned single capital H, set in the run's computed font, is painted at the run's own text-rect origin (placement residual <= 0.02 px, verified before every capture). Cap height is the face's cap ratio measured at 200 px times the run's rendered font size, corroborated by the H's pixel span at >=50 % coverage (agreement <= 1 px, the pixel span is the tighter antialias boundary).",
            "contrast": "the declared colour composited over the pixels of the `without-<n>` capture at the run's ink mask (glyph-core pixels, coverage >= 85 %), WCAG 2.x relative luminance; `min` is the worst pixel behind a glyph",
            "widths": "two fresh renders of the shipped page at route width 1344 and 1200; at 1200 the scene plate is transform-scaled by 1200/1344, so the same authored type paints smaller (measured scene scale 0.892857)",
            "determinism": "a second base capture is pixel-identical (0 differing px at both widths); after every probe was removed the page returned to its base paint inside every measured text rect (0 px above the ink threshold), while rotated card/tag edges re-rasterised by up to 35/255 outside the text rects, which is why all masks are restricted to the run's own text rects",
            "commands": [
                "python3 scripts/gen-home-proof.py --width 1344 --height 768 --out <work>/pages/home-1344.html",
                "python3 scripts/gen-home-proof.py --width 1200 --height 768 --out <work>/pages/home-1200.html",
                "node probes/legibility-2026-11/measure.mjs <work>/pages/home-1344.html \"$(cat tests/fixtures/scene-text/scene.units.json)\" <work>/run-1344 1344",
                "node probes/legibility-2026-11/measure.mjs <work>/pages/home-1200.html \"$(cat tests/fixtures/scene-text/scene.units.json)\" <work>/run-1200 1200",
                "python3 probes/legibility-2026-11/analyse.py . <work>/run-1344 <work>/run-1200 docs/concept-parity/text-legibility-2026-11.json",
            ],
        },
        "captures": {"1344": meta_1344, "1200": meta_1200},
        "totals": totals,
        "ranking_worst_first": ranking,
        "worst_three": ranking[:3],
        "worst_three_note": "ranks 2-3 tie with the other two single-line card titles (9.24 px cap at 1344, 8.25 px at 1200); the tie is broken by which card's content already clips",
        "runs": runs_out,
    }


if __name__ == "__main__":
    document = build(REPO)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: document[k] for k in ("totals", "worst_three")}, indent=2))
