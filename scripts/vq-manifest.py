#!/usr/bin/env python3
"""VQ-006 — the judge for the installed visual capture harness.

The camera is `scripts/vq-capture.mjs`; this file decides whether the frames it produced may be
used as visual evidence. Keeping them apart is deliberate: the rules below are pure functions over
a cell record, so they can be tested without an Electron host, and a hand-edited cell record or a
swapped PNG is caught rather than trusted.

Rules applied to every cell (from `docs/launch/VISUAL-QUALITY-PROGRAM.md` Gate 2 and Gate 5):

1. **live product** — the page must be http(s), carry no proof markers and no proof fixture script.
   A proof HTML, a component-lab render harness or a design fixture is not product evidence.
2. **surface** — the destination must exist on the installed build and the route must have rendered
   it (no render-error marker, fonts loaded, v3 ready).
3. **required images** — the destination's declared roles must be present in the required count.
4. **asset quality** — every image that stands in for a kit or display asset must be complete,
   carry a sha256, have natural size at least 2x its rendered size, and not be a data URI unless it
   is a hashed bundled brand asset from `desktop/cb-assets.generated.js`.
5. **Press Plate lane** — a Press Plate is legal as a pack cover and illegal as a product-surface
   illustration. The judge counts them separately and fails a cell whose required display role was
   satisfied only by Press Plates.
6. **evidence integrity** — the PNG on disk must hash to the sha256 the cell record claims.

Usage:
    python3 scripts/vq-manifest.py --dir docs/visual-review/vq-006 [--commit <sha>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "vq.manifest.v1"
DESTINATIONS = (
    "home",
    "discover",
    "course-home",
    "classroom",
    "world-studio",
    "design-system",
)
WIDTHS = (1344, 1049, 900, 460)

#: Which route destination attribute each harness destination must render.
EXPECTED_DESTINATION = {
    "home": "home",
    "discover": "workshop",
    "course-home": "home",
    "classroom": "home",
    "world-studio": "home",
    "design-system": None,
}

#: The display-asset roles each surface needs, from VISUAL-QUALITY-PROGRAM §2. `kinds` is the set of
#: inventory `kind` values that can satisfy the role; a role with no marker anywhere in the tree
#: counts zero and says so, which is the honest reading of an unbuilt surface.
REQUIREMENTS = {
    "home": (
        {"role": "display_cover", "min": 4, "kinds": ("cover_plate",), "note": "four Home display covers"},
        {"role": "fox_pose", "min": 1, "kinds": ("fox_pose",), "min_width": 620,
         "note": "fox clock pose (hidden below 620 px by design)"},
    ),
    "discover": (
        {"role": "collectible_plate", "min": 8, "kinds": ("cover_plate",), "note": "eight collectible display plates"},
        {"role": "fox_pose", "min": 1, "kinds": ("fox_pose",), "min_width": 620,
         "note": "fox point pose (hidden below 620 px by design)"},
    ),
    "classroom": (
        {"role": "lesson_scene", "min": 1, "kinds": ("scene_plate",), "note": "lesson scene plate"},
        {"role": "fox_pose", "min": 1, "kinds": ("fox_pose",), "min_width": 620,
         "note": "fox read pose (hidden below 620 px by design)"},
    ),
    "course-home": (
        {"role": "course_map", "min": 1, "kinds": ("scene_plate", "cover_plate"), "note": "course-map plate"},
        {"role": "fox_pose", "min": 1, "kinds": ("fox_pose",), "min_width": 620,
         "note": "fox point pose (hidden below 620 px by design)"},
    ),
    "world-studio": (
        {"role": "world_plate", "min": 1, "kinds": ("cover_plate", "scene_plate"), "note": "approved world plate"},
    ),
    "design-system": (
        {"role": "specimen_plate", "min": 1, "kinds": ("cover_plate", "scene_plate", "unknown"), "note": "specimen sheet art"},
    ),
}

PLACEHOLDER_PATTERNS = ("placeholder", "blank", "spacer", "1x1", "transparent.", "no-image")
PRESS_PATTERNS = ("cover-4x5", "cover-3x2", "press-plate", "press_plate", "/press/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def press_plate_registry(root: Path | None = None) -> dict[str, str]:
    """sha256 -> path for every bundled pack cover in the checkout.

    The Press Plate lane is the bundled pack cover (`cover-4x5.png`, `cover-3x2.png` in
    `bundled/packs/<pack>/content/`). Matching a product-surface image's bytes against these
    hashes proves the surface reused a Press Plate as illustration — a mechanical fact, not an
    opinion about the picture.
    """
    base = (root or Path(__file__).resolve().parent.parent)
    registry: dict[str, str] = {}
    for path in sorted(base.glob("bundled/packs/*/content/cover-*.png")):
        try:
            registry[sha256_file(path)] = str(path.relative_to(base))
        except OSError:
            continue
    return registry


def classify_image(image: dict, press_plates: dict[str, str] | None = None) -> dict:
    """Return the judge's reading of one inventory row.

    Nothing here trusts a flag the camera set; every verdict is recomputed from the row's own
    values (`complete`, `natural`, `rendered`, `current_src`, `bundled_asset`, markers).
    """
    rendered_width = float((image.get("rendered") or {}).get("width") or 0)
    natural_width = int((image.get("natural") or {}).get("width") or 0)
    natural_height = int((image.get("natural") or {}).get("height") or 0)
    src = str(image.get("current_src") or "")
    data_uri = bool(image.get("current_src_data_uri"))
    bundled = image.get("bundled_asset") or None
    kind = str(image.get("kind") or "unknown")
    markers = " ".join(image.get("markers") or [])

    placeholder_reasons = []
    if not image.get("complete"):
        placeholder_reasons.append("image not complete")
    if natural_width <= 0 or natural_height <= 0:
        placeholder_reasons.append("no natural size")
    if not src:
        placeholder_reasons.append("empty currentSrc")
    haystack = f"{src} {markers}".lower()
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern in haystack:
            placeholder_reasons.append(f"source matches {pattern!r}")

    press = kind == "workshop_cover" or any(pattern in haystack for pattern in PRESS_PATTERNS)
    press_match = (press_plates or {}).get(str(image.get("sha256") or ""))
    if press_match:
        press = True
    data_uri_stand_in = data_uri and not bundled

    scale_ratio = (natural_width / rendered_width) if rendered_width > 0 else None
    scale_ok = bool(scale_ratio is not None and scale_ratio >= 1.998)

    problems = []
    if placeholder_reasons:
        problems.extend(placeholder_reasons)
    if data_uri_stand_in:
        problems.append("data URI stands in for a kit asset")
    if scale_ratio is None:
        problems.append("not rendered")
    elif not scale_ok:
        problems.append(f"natural {natural_width}px is below 2x rendered {rendered_width:.2f}px")
    if not image.get("sha256"):
        problems.append("no sha256")

    return {
        "kind": kind,
        "placeholder": bool(placeholder_reasons),
        "press_plate": bool(press),
        "press_plate_source": press_match,
        "data_uri_stand_in": bool(data_uri_stand_in),
        "bundled_asset": bundled,
        "scale_ok": scale_ok,
        "scale_ratio": round(scale_ratio, 3) if scale_ratio is not None else None,
        "problems": problems,
    }


def judge_cell(record: dict, cell_dir: Path, press_plates: dict[str, str] | None = None) -> dict:
    """Apply the six rules to one captured cell and return a verdict object."""
    press_plates = press_plates or {}
    name = (record.get("cell") or {}).get("name") or "unknown"
    destination = (record.get("cell") or {}).get("destination")
    width = (record.get("cell") or {}).get("width")
    route = record.get("route") or {}
    page = record.get("page") or {}
    surface = record.get("surface") or {}
    problems: list[str] = []
    warnings: list[str] = []

    # 1. live product
    if page.get("protocol") not in ("http:", "https:"):
        problems.append(f"not a live page ({page.get('protocol')})")
    if page.get("proof_script"):
        problems.append("proof fixture script detected")
    if route.get("proof_markers"):
        problems.append(f"proof-only markers: {', '.join(route['proof_markers'])}")
    expected = EXPECTED_DESTINATION.get(str(destination))
    if expected and route.get("destination") and route.get("destination") != expected:
        problems.append(f"rendered destination {route.get('destination')!r}, expected {expected!r}")

    # 2. surface
    if surface.get("missing"):
        problems.append(f"missing surface: {surface['missing'].get('reason')}")
    if not route.get("present"):
        problems.append("no [data-cb-route] in the cell record")
    if route.get("render_error_markers"):
        problems.append(f"render error: {', '.join(route['render_error_markers'])}")
    if route.get("present") and not route.get("fonts_ok"):
        problems.append(f"fonts not loaded ({route.get('fonts_status')})")
    if route.get("present") and not route.get("v3_ready"):
        warnings.append("v3 primitives are not mounted on this surface")

    # 3/4/5. required images and asset quality
    inventory = []
    for image in record.get("images") or []:
        verdict = classify_image(image, press_plates)
        inventory.append({
            "selector": image.get("selector"),
            "current_src": image.get("current_src"),
            "natural": image.get("natural"),
            "rendered": image.get("rendered"),
            "sha256": image.get("sha256"),
            "kind": verdict["kind"],
            "placeholder": verdict["placeholder"],
            "press_plate": verdict["press_plate"],
            "press_plate_source": verdict["press_plate_source"],
            "bundled_asset": verdict["bundled_asset"],
            "scale_ratio": verdict["scale_ratio"],
            "problems": verdict["problems"],
        })

    usable = [row for row in inventory if not row["placeholder"] and not row["press_plate"]]
    requirement_rows = []
    for requirement in REQUIREMENTS.get(str(destination), ()):
        min_width = requirement.get("min_width")
        if min_width and isinstance(width, (int, float)) and width < min_width:
            requirement_rows.append({
                "role": requirement["role"],
                "required": requirement["min"],
                "found": None,
                "ok": True,
                "skipped": f"not required at {width}px (min width {min_width}px)",
                "note": requirement["note"],
            })
            continue
        satisfying = [row for row in usable if row["kind"] in requirement["kinds"]]
        requirement_rows.append({
            "role": requirement["role"],
            "required": requirement["min"],
            "found": len(satisfying),
            "ok": len(satisfying) >= requirement["min"],
            "note": requirement["note"],
        })
        if len(satisfying) < requirement["min"]:
            problems.append(
                f"required image missing: {requirement['role']} {len(satisfying)}/{requirement['min']}"
            )

    press_rows = [row for row in inventory if row["press_plate"]]
    if press_rows and REQUIREMENTS.get(str(destination)):
        sources = sorted({row["press_plate_source"] for row in press_rows if row["press_plate_source"]})
        problems.append(
            f"{len(press_rows)} Press Plate(s) counted on a product surface"
            + (f" — bundled pack cover {', '.join(sources)}" if sources else "")
        )

    for row in inventory:
        for problem in row["problems"]:
            problems.append(f"image {row['selector']}: {problem}")

    # 6. evidence integrity
    screenshot = record.get("screenshot") or {}
    integrity = None
    if screenshot.get("file"):
        path = cell_dir / str(screenshot["file"])
        if not path.is_file():
            problems.append(f"screenshot missing on disk: {screenshot['file']}")
        else:
            digest = sha256_file(path)
            integrity = {
                "file": screenshot["file"],
                "declared": screenshot.get("sha256"),
                "measured": digest,
                "ok": digest == screenshot.get("sha256"),
            }
            if not integrity["ok"]:
                problems.append("screenshot sha256 does not match the cell record")
    else:
        problems.append("no screenshot recorded")

    # Deduplicate while preserving order: one image can break several rules.
    seen: set[str] = set()
    unique = [problem for problem in problems if not (problem in seen or seen.add(problem))]
    return {
        "cell": name,
        "destination": destination,
        "width": width,
        "ok": not unique,
        "problems": unique,
        "warnings": warnings,
        "requirements": requirement_rows,
        "images": inventory,
        "backgrounds": record.get("backgrounds") or [],
        "plugin": (record.get("window") or {}).get("plugin") or {},
        "route": {
            "marker": route.get("marker"),
            "destination": route.get("destination"),
            "width": route.get("width"),
            "height": route.get("height"),
            "v3_ready": route.get("v3_ready"),
            "fonts_status": route.get("fonts_status"),
            "scope": route.get("scope"),
        },
        "screenshot": integrity,
    }


def build_manifest(cell_dir: Path, commit: str | None = None) -> dict:
    registry = press_plate_registry()
    records = []
    for path in sorted(cell_dir.glob("*.json")):
        if path.name in ("manifest.json",) or path.name.endswith(".stamp.json"):
            continue
        try:
            record = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if record.get("schema") != "vq.capture.v1":
            continue
        records.append((path, record))

    cells = [judge_cell(record, cell_dir, registry) for _, record in records]
    present = {(cell["destination"], cell["width"]) for cell in cells if cell["ok"]}

    missing_cells = [
        {"destination": destination, "width": width}
        for destination in DESTINATIONS
        for width in WIDTHS
        if (destination, width) not in present
    ]
    plugin_shas = sorted({
        str(cell["plugin"].get("sha256"))
        for cell in cells
        if cell["plugin"].get("sha256")
    })
    mixed_build = len(plugin_shas) > 1
    if mixed_build:
        for cell in cells:
            cell["ok"] = False
            cell["problems"].append(
                "cells were captured from more than one plugin build "
                f"({', '.join(sha[:12] for sha in plugin_shas)}); the set is not one product"
            )
    manifest = {
        "schema": SCHEMA,
        "tool": "scripts/vq-manifest.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
        "plugin_sha256": plugin_shas,
        "matrix": {"destinations": list(DESTINATIONS), "widths": list(WIDTHS)},
        "press_plate_registry": registry,
        "cells": cells,
        "missing_cells": missing_cells,
        "summary": {
            "cells": len(cells),
            "passed": sum(1 for cell in cells if cell["ok"]),
            "failed": sum(1 for cell in cells if not cell["ok"]),
            "missing_matrix_cells": len(missing_cells),
            "mixed_build": mixed_build,
            "ok": bool(cells) and all(cell["ok"] for cell in cells) and not missing_cells,
        },
    }
    return manifest


def contact_sheet(cell_dir: Path, manifest: dict, output: Path) -> str | None:
    """One sheet of every captured frame, labelled, so the cross-screen set can be judged at once."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # pragma: no cover - Pillow is a tool dependency, not a product one
        return None
    shots = [
        (cell_dir / cell["screenshot"]["file"], cell)
        for cell in manifest["cells"]
        if cell.get("screenshot") and cell["screenshot"].get("ok")
    ]
    if not shots:
        return None
    thumb_width = 420
    margin = 12
    label_height = 34
    columns = min(3, max(1, len(shots)))
    thumbs = []
    for path, cell in shots:
        with Image.open(path) as image:
            ratio = thumb_width / max(1, image.width)
            thumb = image.convert("RGB").resize(
                (thumb_width, max(1, int(image.height * ratio))),
                getattr(Image, "Resampling", Image).LANCZOS,
            )
        thumbs.append((thumb, cell))
    rows = (len(thumbs) + columns - 1) // columns
    row_heights = []
    for row in range(rows):
        chunk = thumbs[row * columns:(row + 1) * columns]
        row_heights.append(max(thumb.height for thumb, _ in chunk) + label_height + margin)
    sheet = Image.new("RGB", (columns * (thumb_width + margin) + margin, sum(row_heights) + margin), (24, 21, 16))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=14)
    except TypeError:  # Pillow < 10
        font = ImageFont.load_default()
    y = margin
    for row in range(rows):
        chunk = thumbs[row * columns:(row + 1) * columns]
        x = margin
        for thumb, cell in chunk:
            sheet.paste(thumb, (x, y + label_height))
            label = f"{cell['cell']}  {'PASS' if cell['ok'] else 'FAIL'}"
            draw.text((x, y + 6), label, fill=(243, 230, 207) if cell["ok"] else (240, 160, 140), font=font)
            x += thumb_width + margin
        y += row_heights[row]
    sheet.save(output)
    return str(output)


def render_markdown(manifest: dict, output_dir: Path) -> str:
    lines = [
        "# VQ-006 installed capture manifest",
        "",
        f"Generated {manifest['generated_at']} by `{manifest['tool']}`.",
        f"Commit: `{manifest['commit'] or 'unrecorded'}`  ",
        f"Module sha256: {', '.join(f'`{sha}`' for sha in manifest['plugin_sha256']) or '**none recorded**'}",
        "",
        f"Cells: **{manifest['summary']['passed']} passed / {manifest['summary']['failed']} failed / "
        f"{manifest['summary']['missing_matrix_cells']} matrix cells not captured**",
        "",
        "## Matrix",
        "",
        "| destination | " + " | ".join(str(width) for width in manifest["matrix"]["widths"]) + " |",
        "|---|" + "---|" * len(manifest["matrix"]["widths"]),
    ]
    by_cell = {(cell["destination"], cell["width"]): cell for cell in manifest["cells"]}
    for destination in manifest["matrix"]["destinations"]:
        row = [f"| {destination} "]
        for width in manifest["matrix"]["widths"]:
            cell = by_cell.get((destination, width))
            row.append("| " + ("pass" if cell and cell["ok"] else ("fail" if cell else "not captured")) + " ")
        lines.append("".join(row) + "|")
    lines += ["", "## Failed cells", ""]
    failures = [cell for cell in manifest["cells"] if not cell["ok"]]
    if not failures:
        lines.append("None.")
    for cell in failures:
        lines.append(f"### {cell['cell']}")
        lines.append("")
        for problem in cell["problems"]:
            lines.append(f"- {problem}")
        lines.append("")
    lines += ["", "## Images per cell", ""]
    for cell in manifest["cells"]:
        lines.append(f"**{cell['cell']}** — {len(cell['images'])} image(s)")
        lines.append("")
        lines.append("| selector | kind | natural | rendered | ratio | sha256 |")
        lines.append("|---|---|---|---|---|---|")
        for image in cell["images"]:
            natural = image.get("natural") or {}
            rendered = image.get("rendered") or {}
            digest = image.get("sha256") or "none"
            lines.append(
                f"| `{image.get('selector')}` | {image.get('kind')} | "
                f"{natural.get('width')}x{natural.get('height')} | "
                f"{rendered.get('width')}x{rendered.get('height')} | "
                f"{image.get('scale_ratio')} | `{digest}` |"
            )
        lines.append("")
    text = "\n".join(lines) + "\n"
    (output_dir / "MANIFEST.md").write_text(text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="capture output directory")
    parser.add_argument("--commit", default=None)
    parser.add_argument("--require-complete", action="store_true",
                        help="also fail when a matrix cell was never captured")
    args = parser.parse_args()

    output_dir = Path(args.dir).resolve()
    if not output_dir.is_dir():
        print(f"vq: no such capture directory: {output_dir}", file=sys.stderr)
        return 2
    manifest = build_manifest(output_dir, args.commit)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    render_markdown(manifest, output_dir)
    sheet = contact_sheet(output_dir, manifest, output_dir / "contact-sheet.png")

    summary = manifest["summary"]
    print(f"output  : {output_dir}")
    print(f"contact : {sheet or 'not produced'}")
    print(f"cells   : {summary['cells']} ({summary['passed']} pass, {summary['failed']} fail)")
    print(f"missing : {summary['missing_matrix_cells']} of "
          f"{len(DESTINATIONS) * len(WIDTHS)} matrix cells")
    for cell in manifest["cells"]:
        print(f"  {'PASS' if cell['ok'] else 'FAIL'}  {cell['cell']}")
        for problem in cell["problems"][:4]:
            print(f"        - {problem}")
    ok = summary["ok"] and not (args.require_complete and manifest["missing_cells"])
    print(f"verdict : {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
