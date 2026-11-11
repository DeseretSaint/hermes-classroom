#!/usr/bin/env python3
"""VQ-006 — the judge for the installed visual capture harness.

The camera is `scripts/vq-capture.mjs`; this file decides whether the frames it produced may be
used as visual evidence. Keeping them apart is deliberate: the rules below are pure functions over
a cell record, so they can be tested without an Electron host.

What the judge re-verifies instead of trusting the record:

- **screenshot bytes** — the PNG on disk hashes to the sha256 the cell record claims;
- **required-role image bytes** — every inventory row that would satisfy a required display role
  carries persisted bytes written by the camera into `evidence/`. The record's `evidence.file` is
  untrusted input: the judge accepts only `evidence/<row sha256>.<raster ext>` relative to the cell,
  refuses absolute paths, `..`, other directories and any name that is not the row's own sha256,
  and refuses bytes identical to the cell screenshot. It hashes the file against the row sha256
  and reads the raster header, so the declared natural size must match the file it claims to
  describe. One asset may not satisfy two rows of the same role. A record whose required-role row
  has no verifiable backing is refused, so forging a pass needs image files with matching bytes
  rather than four edited numbers;
- **build identity** — the cell names the plugin sha the window read (`window.plugin.sha256`);
- **one capture set** — every captured cell carries one run id and one plugin sha.

What is camera-asserted and *not* independently re-verified: rendered geometry (`rendered`), the
inventory `kind`, `complete`, `current_src`, background `repeat`/`size`, and the screenshot clip.
Those describe what the live DOM measured; a record edited after capture can still lie about them,
and the judge does not claim otherwise.

Rules applied to every cell (from `docs/launch/VISUAL-QUALITY-PROGRAM.md` Gate 2 and Gate 5):

1. **live product** — the page must be http(s), carry no proof markers and no proof fixture script.
   A proof HTML, a component-lab render harness or a design fixture is not product evidence.
2. **surface** — the destination must exist on the installed build and the route must have rendered
   it (no render-error marker, fonts loaded, v3 ready).
3. **required images** — the destination's declared roles must be present in the required count.
4. **asset quality** — every image that stands in for a kit or display asset must be complete,
   carry a sha256, have natural size at least 2x its rendered size, and not be a data URI unless it
   is a hashed bundled brand asset from `desktop/cb-assets.generated.js`. The same rules apply to
   every `background-image` layer the camera recorded, so an asset cannot escape judgement by being
   delivered as CSS; the 2x rule covers each axis that the layer paints at a box-derived size, so an
   axis that tiles at the file's own natural size is exempt while `cover`/`contain`/percentage sizes
   are judged (a `repeat` + `cover` layer is still an upscale). A record with no repeat mode is judged
   as a one-shot image.
5. **Press Plate lane** — a Press Plate is legal as a pack cover and illegal as a product-surface
   illustration. The judge counts them separately and fails a cell whose required display role was
   satisfied only by Press Plates.
6. **evidence integrity** — the PNG on disk must hash to the sha256 the cell record claims.

Usage:
    python3 scripts/vq-manifest.py --dir docs/visual-review/vq-006 [--commit <sha>]
        [--destinations "home discover"] [--widths "1344 460"]
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
#: `background-repeat` values that tile the layer. A layer tiling *at its natural size* is
#: decoration, not a display illustration, so the 2x rule does not apply to it — the same 96 px grain
#: tile that is correct as a repeating overlay would be an upscaled asset as a one-shot image. Only an
#: explicit repeat mode in the cell record starts the exemption; a record without one is judged as a
#: one-shot image.
REPEATING_MODES = ("repeat", "repeat-x", "repeat-y", "round", "space")
#: `background-size` tokens that scale the painted layer to the box instead of keeping the file's
#: natural size. A tiling layer with one of these does not tile at natural size, so the exemption
#: above cannot apply: `cover`/`contain` on a 96 px file over a 900 px box is an upscale whatever the
#: repeat mode says. Percentages are included for the same reason (`100% 100%` is a full-box stretch).
BOX_SCALING_SIZES = ("cover", "contain")


#: Where, inside a cell packet, the camera persists the inventoried bytes for required-role rows.
#: The judge reads evidence from nowhere else: a record may not point at another file in the packet
#: (the screenshot included), and the basename must be the row's own sha256. A forged required-role
#: row therefore needs a file whose bytes hash to the number it claims, not four edited numbers.
EVIDENCE_DIR = "evidence"
#: Raster extensions the camera writes and the judge can read a header from.
RASTER_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def required_kinds(destination: str | None) -> frozenset[str]:
    """The inventory kinds that can satisfy a required role on this destination."""
    requirements = REQUIREMENTS.get(str(destination), ())
    return frozenset(kind for requirement in requirements for kind in requirement["kinds"])


def evidence_kinds() -> frozenset[str]:
    """Every kind any destination holds to a required role; the camera persists bytes for these."""
    return frozenset(
        kind
        for requirements in REQUIREMENTS.values()
        for requirement in requirements
        for kind in requirement["kinds"]
    )


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    if data[12:16] != b"IHDR" or b"IEND" not in data[-64:]:
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return (width, height) if width and height else None


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        length = int.from_bytes(data[index + 2:index + 4], "big")
        if length < 2:
            return None
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height = int.from_bytes(data[index + 5:index + 7], "big")
            width = int.from_bytes(data[index + 7:index + 9], "big")
            return (width, height) if width and height else None
        index += 2 + length
    return None


def _gif_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    return (width, height) if width and height else None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    if int.from_bytes(data[4:8], "little") + 8 > len(data):
        return None  # a truncated RIFF payload is not a readable image
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return (width, height)
    if chunk == b"VP8L":
        if len(data) < 25 or data[20] != 0x2F:
            return None
        bits = int.from_bytes(data[21:25], "little")
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    if chunk == b"VP8 ":
        start = data.find(b"\x9d\x01\x2a", 20)
        if start < 0 or start + 7 > len(data):
            return None
        width = int.from_bytes(data[start + 3:start + 5], "little") & 0x3FFF
        height = int.from_bytes(data[start + 5:start + 7], "little") & 0x3FFF
        return (width, height) if width and height else None
    return None


def raster_dimensions(path: Path) -> tuple[int, int] | None:
    """Width and height read from the file's own header, or None when it is not a known raster.

    Only the container header is inspected: the judge is checking that the persisted bytes are a
    real image of the declared size, not re-rendering them.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
    for reader in (_png_dimensions, _jpeg_dimensions, _gif_dimensions, _webp_dimensions):
        dimensions = reader(data)
        if dimensions:
            return dimensions
    return None


def evidence_path(file_name: str, cell_dir: Path, row_sha256: str | None) -> tuple[Path | None, list[str]]:
    """Resolve a row's `evidence.file` to a confined path, or name why it is not acceptable.

    The record supplies this path, so it is treated as untrusted input. Only one shape is accepted:
    `evidence/<row sha256>.<raster ext>` relative to the cell. Anything else — an absolute path, a
    `..` step, another directory, a name that is not the row's own sha256 — is refused, because a
    path with no confinement let a hand-edited record back a required-role row with a file already
    in the packet (its own screenshot included) and mint a PASS without any new bytes.
    """
    relative = Path(file_name)
    if relative.is_absolute():
        return None, [f"evidence file must be relative to the cell, got the absolute path {file_name!r}"]
    if ".." in relative.parts:
        return None, [f"evidence file must not step outside the cell, got {file_name!r}"]
    if len(relative.parts) != 2 or relative.parts[0] != EVIDENCE_DIR:
        return None, [
            f"evidence file must live at {EVIDENCE_DIR}/<row sha256>.<ext> in this cell, got {file_name!r}"
        ]
    if relative.suffix.lower() not in RASTER_EXTENSIONS:
        return None, [
            f"evidence file must carry a raster extension ({', '.join(RASTER_EXTENSIONS)}), got {file_name!r}"
        ]
    if not row_sha256 or relative.stem.lower() != str(row_sha256).lower():
        return None, [
            f"evidence file name must be the row sha256 ({row_sha256 or 'none'}), got {relative.name!r}"
        ]
    return cell_dir / relative, []


def evidence_verdict(image: dict, cell_dir: Path,
                     screenshot_sha256: str | None = None) -> tuple[list[str], dict | None]:
    """Check the persisted bytes a required-role row points at, and return (problems, info)."""
    evidence = image.get("evidence") or {}
    file_name = str(evidence.get("file") or "")
    if not file_name:
        return ["no persisted image evidence (evidence.file is absent)"], None
    path, path_problems = evidence_path(file_name, cell_dir, image.get("sha256"))
    if path is None:
        return path_problems or [f"evidence file could not be resolved: {file_name}"], None
    if not path.is_file():
        return [f"evidence file missing on disk: {file_name}"], None
    measured = sha256_file(path)
    natural = image.get("natural") or {}
    natural_width = int(natural.get("width") or 0)
    natural_height = int(natural.get("height") or 0)
    info = {
        "file": file_name,
        "row_sha256": image.get("sha256"),
        "evidence_sha256": evidence.get("sha256"),
        "measured_sha256": measured,
        "bytes": path.stat().st_size,
        "dimensions": None,
        "ok": False,
    }
    problems: list[str] = []
    if measured != image.get("sha256"):
        problems.append("evidence sha256 does not match the row sha256")
    if evidence.get("sha256") and measured != evidence.get("sha256"):
        problems.append("evidence sha256 does not match the evidence row")
    if screenshot_sha256 and measured == screenshot_sha256:
        problems.append(
            "evidence bytes are the cell screenshot, not the inventoried asset"
        )
    dimensions = raster_dimensions(path)
    if dimensions is None:
        problems.append("evidence file is not a readable raster (png/jpeg/gif/webp)")
    else:
        info["dimensions"] = {"width": dimensions[0], "height": dimensions[1]}
        if dimensions != (natural_width, natural_height):
            problems.append(
                f"evidence image is {dimensions[0]}x{dimensions[1]}px but the record claims natural "
                f"{natural_width}x{natural_height}px"
            )
    info["ok"] = not problems
    return problems, info


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


def classify_image(image: dict, press_plates: dict[str, str] | None = None,
                   judged_axes: tuple[str, ...] = ("x",)) -> dict:
    """Return the judge's reading of one inventory row.

    Nothing here trusts a flag the camera set; every verdict is recomputed from the row's own
    values (`complete`, `natural`, `rendered`, `current_src`, `bundled_asset`, markers).

    `judged_axes` says which dimension the 2x rule covers. An `<img>` is judged on its width, which
    is how it is laid out; a CSS background layer passes the axes that do not paint at natural size,
    so a tile repeated at its own width but stretched in height is held to the rule on height only.
    An empty tuple means the layer tiles at natural size on both axes and is decoration.
    """
    rendered_width = float((image.get("rendered") or {}).get("width") or 0)
    rendered_height = float((image.get("rendered") or {}).get("height") or 0)
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
    scale_ratio_y = (natural_height / rendered_height) if rendered_height > 0 else None
    axes = tuple(axis for axis in judged_axes if axis in ("x", "y"))
    failing = []
    for axis in axes:
        ratio = scale_ratio if axis == "x" else scale_ratio_y
        painted = rendered_width if axis == "x" else rendered_height
        if ratio is None or ratio < 1.998:
            failing.append(axis)
    axis_problems = []
    if failing == ["x", "y"]:
        # One finding per layer: a `cover` layer stretched on both axes is one upscale, not two.
        axis_problems.append(
            f"natural {natural_width}x{natural_height}px is below 2x rendered "
            f"{rendered_width:.2f}x{rendered_height:.2f}px (both axes)"
        )
    else:
        for axis in failing:
            natural = natural_width if axis == "x" else natural_height
            painted = rendered_width if axis == "x" else rendered_height
            if axis == "x" and scale_ratio is None:
                axis_problems.append("not rendered")
            elif axis == "y" and scale_ratio_y is None:
                axis_problems.append("not rendered (height)")
            elif axis == "x":
                axis_problems.append(f"natural {natural}px is below 2x rendered {painted:.2f}px")
            else:
                axis_problems.append(
                    f"natural {natural}px is below 2x rendered {painted:.2f}px (height axis)"
                )
    scale_ok = not axis_problems

    problems = []
    if placeholder_reasons:
        problems.extend(placeholder_reasons)
    if data_uri_stand_in:
        problems.append("data URI stands in for a kit asset")
    problems.extend(axis_problems)
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
        "scale_ratio_y": round(scale_ratio_y, 3) if scale_ratio_y is not None else None,
        "ratio_judged": bool(axes),
        "judged_axes": list(axes),
        "problems": problems,
    }


def box_scaled_size_token(token: str) -> bool:
    """True when one `background-size` component derives its paint size from the box."""
    token = token.strip().lower()
    return token in BOX_SCALING_SIZES or token.endswith("%")


def background_judged_axes(repeat: str | None, size: str | None) -> tuple[str, ...]:
    """Which dimensions of a CSS background layer the 2x rule must judge.

    An axis is exempt only when the layer both repeats on that axis and paints it at the file's
    natural size; anything else is a box-derived paint. So:

    - `repeat` + `auto` → nothing judged (a real tile);
    - `repeat` + `cover` → both axes judged (the repeat is invisible; `cover` stretches the file);
    - `repeat-x` + `auto 100%` → height judged, width exempt (a strip that tiles at its own width
      but is stretched to the box height is not misleading on width, and may be on height).

    A missing repeat mode exempts nothing: an old record must not become decoration by omission.
    """
    modes = str(repeat or "").strip().lower().split()
    repeats_x = repeats_y = False
    for mode in modes:
        if mode == "repeat-x":
            repeats_x = True
        elif mode == "repeat-y":
            repeats_y = True
        elif mode in REPEATING_MODES:
            repeats_x = repeats_y = True

    tokens = str(size or "").strip().lower().split()
    if not tokens:
        size_x = size_y = "auto"
    elif len(tokens) == 1:
        size_x = tokens[0]
        size_y = tokens[0] if tokens[0] in BOX_SCALING_SIZES else "auto"
    else:
        size_x, size_y = tokens[0], tokens[1]

    judged = []
    if not (repeats_x and not box_scaled_size_token(size_x)):
        judged.append("x")
    if not (repeats_y and not box_scaled_size_token(size_y)):
        judged.append("y")
    return tuple(judged)



def classify_background(background: dict, press_plates: dict[str, str] | None = None) -> dict:
    """Judge one CSS `background-image` layer with the same rules as an `<img>`.

    A background layer carries `url`/`data_uri` instead of `currentSrc` and has no `complete` flag:
    a layer that painted is loaded, so an empty url or a zero natural size is the placeholder
    signal instead of an incompleteness flag. Everything else — data URI stand-in, 2x ratio, Press
    Plate by bundled-cover hash — is the rule applied to an image, so a kit asset cannot escape
    judgement by being delivered as a CSS layer. The 2x exemption is narrower than "repeats": an
    axis is exempt only when the layer tiles on that axis at the file's own size, so `cover` +
    `repeat` cannot pass a 96 px file at 900 px while a `repeat` + `auto` grain tile still can.
    """
    judged = background_judged_axes(
        background.get("background_repeat"), background.get("background_size")
    )
    row = {
        "selector": background.get("selector"),
        "kind": str(background.get("kind") or "background"),
        "current_src": background.get("url") or "",
        "current_src_data_uri": bool(background.get("data_uri")),
        "natural": background.get("natural") or {},
        "rendered": background.get("rendered") or {},
        "sha256": background.get("sha256"),
        "bundled_asset": background.get("bundled_asset"),
        "markers": background.get("marks") or background.get("markers") or [],
        "complete": True,
    }
    return classify_image(row, press_plates, judged_axes=judged)


def judge_cell(record: dict, cell_dir: Path, press_plates: dict[str, str] | None = None) -> dict:
    """Apply the six rules to one captured cell and return a verdict object."""
    press_plates = press_plates or {}
    name = (record.get("cell") or {}).get("name") or "unknown"
    destination = (record.get("cell") or {}).get("destination")
    width = (record.get("cell") or {}).get("width")
    route = record.get("route") or {}
    page = record.get("page") or {}
    surface = record.get("surface") or {}
    plugin = (record.get("window") or {}).get("plugin") or {}
    problems: list[str] = []
    warnings: list[str] = []

    # Every cell must name the build it was captured from, including a refusal record: a
    # `missing_surface` throw must not leave the cell untraceable to a plugin sha.
    if not plugin.get("sha256"):
        problems.append("cell names no plugin build (window.plugin.sha256 is absent)")

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
    declared_screenshot_sha = (record.get("screenshot") or {}).get("sha256")
    required_for_destination = required_kinds(destination)
    inventory = []
    for image in record.get("images") or []:
        verdict = classify_image(image, press_plates)
        evidence_problems: list[str] = []
        evidence = None
        evidence_required = bool(
            verdict["kind"] in required_for_destination
            and not verdict["placeholder"]
            and not verdict["press_plate"]
            and not verdict["problems"]
        )
        if evidence_required:
            evidence_problems, evidence = evidence_verdict(
                image, cell_dir, screenshot_sha256=declared_screenshot_sha
            )
            if evidence_problems:
                problems.extend(f"image {image.get('selector')}: {p}" for p in evidence_problems)
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
            "evidence_required": evidence_required,
            "evidence": evidence,
            "evidence_ok": (not evidence_problems) if evidence_required else None,
        })

    usable = [
        row for row in inventory
        if not row["placeholder"] and not row["press_plate"] and row["evidence_ok"] is not False
    ]
    # Background layers are judged for quality but do not satisfy a display role: a role is a
    # placement the surface must show, and accepting a CSS layer would let a surface pass a
    # requirement it never rendered as an image.
    background_inventory = []
    for background in record.get("backgrounds") or []:
        verdict = classify_background(background, press_plates)
        background_inventory.append({
            "selector": background.get("selector"),
            "url": background.get("url"),
            "data_uri": bool(background.get("data_uri")),
            "background_repeat": background.get("background_repeat"),
            "background_size": background.get("background_size"),
            "natural": background.get("natural"),
            "rendered": background.get("rendered"),
            "sha256": background.get("sha256"),
            "kind": verdict["kind"],
            "placeholder": verdict["placeholder"],
            "press_plate": verdict["press_plate"],
            "press_plate_source": verdict["press_plate_source"],
            "bundled_asset": verdict["bundled_asset"],
            "scale_ratio": verdict["scale_ratio"],
            "scale_ratio_y": verdict["scale_ratio_y"],
            "ratio_judged": verdict["ratio_judged"],
            "judged_axes": verdict["judged_axes"],
            "problems": verdict["problems"],
        })
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
        # One asset may not satisfy several copies of the same role. The camera writes one file per
        # distinct asset, so rows that share evidence bytes are the same picture counted twice: four
        # rows pointing at one real cover is a missing display set, not a complete one.
        evidence_shas = [
            row["evidence"]["measured_sha256"]
            for row in satisfying
            if (row.get("evidence") or {}).get("measured_sha256")
        ]
        reused = sorted({sha for sha in evidence_shas if evidence_shas.count(sha) > 1})
        for sha in reused:
            problems.append(
                f"required role {requirement['role']} counts the same image bytes "
                f"{evidence_shas.count(sha)} times ({sha[:12]}); each row of a role needs its own asset"
            )
        distinct = len(satisfying) - sum(evidence_shas.count(sha) - 1 for sha in reused)
        requirement_rows.append({
            "role": requirement["role"],
            "required": requirement["min"],
            "found": distinct,
            "ok": distinct >= requirement["min"],
            "note": requirement["note"],
        })
        if distinct < requirement["min"]:
            problems.append(
                f"required image missing: {requirement['role']} {distinct}/{requirement['min']}"
            )

    press_rows = [row for row in inventory + background_inventory if row["press_plate"]]
    if press_rows and REQUIREMENTS.get(str(destination)):
        sources = sorted({row["press_plate_source"] for row in press_rows if row["press_plate_source"]})
        problems.append(
            f"{len(press_rows)} Press Plate(s) counted on a product surface"
            + (f" — bundled pack cover {', '.join(sources)}" if sources else "")
        )

    for row in inventory:
        for problem in row["problems"]:
            problems.append(f"image {row['selector']}: {problem}")
    for row in background_inventory:
        for problem in row["problems"]:
            problems.append(f"background {row['selector']}: {problem}")

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
        "backgrounds": background_inventory,
        "plugin": plugin,
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


def _record_identity(path: Path) -> tuple[str | None, int | None]:
    """Destination and width from a `<destination>--<width>.json` filename."""
    destination, separator, width_text = path.stem.rpartition("--")
    if not separator:
        return None, None
    try:
        return destination or None, int(width_text)
    except ValueError:
        return destination or None, None


def _unreadable_cell(path: Path, reason: str) -> dict:
    """A named failure for a record the judge cannot read, instead of silently dropping it.

    Skipping these made a truncated record look like a matrix cell that was never captured, and a
    `vq.capture.v2` typo look like an empty capture set. Both are failures about a file the run
    wrote, so they are reported as such, with the offending filename.
    """
    destination, width = _record_identity(path)
    return {
        "cell": path.stem,
        "destination": destination,
        "width": width,
        "ok": False,
        "problems": [f"cell record {path.name} {reason}"],
        "warnings": [],
        "requirements": [],
        "images": [],
        "backgrounds": [],
        "plugin": {},
        "route": {},
        "screenshot": None,
        "unreadable": True,
    }


def build_manifest(cell_dir: Path, commit: str | None = None,
                   destinations: tuple[str, ...] | None = None,
                   widths: tuple[int, ...] | None = None) -> dict:
    registry = press_plate_registry()
    matrix_destinations = tuple(destinations) if destinations else DESTINATIONS
    matrix_widths = tuple(widths) if widths else WIDTHS
    records = []
    unreadable = []
    requested = {
        (destination, width) for destination in matrix_destinations for width in matrix_widths
    }

    def outside_subset(path: Path) -> bool:
        """A record the run did not ask for is not judged here, readable or not."""
        return _record_identity(path) not in requested

    for path in sorted(cell_dir.glob("*.json")):
        if path.name in ("manifest.json",) or path.name.endswith(".stamp.json"):
            continue
        try:
            record = json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            if outside_subset(path):
                continue
            unreadable.append(_unreadable_cell(path, f"could not be parsed ({error})"))
            continue
        if not isinstance(record, dict):
            if outside_subset(path):
                continue
            unreadable.append(_unreadable_cell(path, "is not a JSON object"))
            continue
        if record.get("schema") != "vq.capture.v1":
            if outside_subset(path):
                continue
            unreadable.append(
                _unreadable_cell(path, f"has schema {record.get('schema')!r}, expected 'vq.capture.v1'")
            )
            continue
        cell = record.get("cell") or {}
        if (cell.get("destination"), cell.get("width")) not in requested:
            # A frame outside the requested subset belongs to another run; judging it here would
            # attribute it to this matrix. A subset run says what it asked for.
            continue
        records.append((path, record))

    cells = [judge_cell(record, cell_dir, registry) for _, record in records] + unreadable
    # A cell that was captured and failed is *failed*; a matrix cell with no record at all is
    # *not captured*. Conflating them reported 16 failed frames as 24 missing ones.
    captured = {
        (cell["destination"], cell["width"])
        for cell in cells
        if cell["destination"] in matrix_destinations and cell["width"] in matrix_widths
    }

    missing_cells = [
        {"destination": destination, "width": width}
        for destination in matrix_destinations
        for width in matrix_widths
        if (destination, width) not in captured
    ]
    plugin_shas = sorted({
        str(cell["plugin"].get("sha256"))
        for cell in cells
        if cell["plugin"].get("sha256")
    })
    run_ids = sorted({
        str((record.get("run") or {}).get("id"))
        for _, record in records
        if (record.get("run") or {}).get("id")
    })
    mixed_build = len(plugin_shas) > 1
    if mixed_build:
        for cell in cells:
            cell["ok"] = False
            cell["problems"].append(
                "cells were captured from more than one plugin build "
                f"({', '.join(sha[:12] for sha in plugin_shas)}); the set is not one product"
            )
    mixed_run = len(run_ids) > 1
    if mixed_run:
        for cell in cells:
            cell["ok"] = False
            cell["problems"].append(
                "cells come from more than one capture run "
                f"({', '.join(run_ids)}); frames from an earlier run cannot be attributed to this one"
            )
    manifest = {
        "schema": SCHEMA,
        "tool": "scripts/vq-manifest.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
        "plugin_sha256": plugin_shas,
        "capture_runs": run_ids,
        "matrix": {"destinations": list(matrix_destinations), "widths": list(matrix_widths)},
        "press_plate_registry": registry,
        "cells": cells,
        "missing_cells": missing_cells,
        "summary": {
            "cells": len(cells),
            "captured": len(captured),
            "passed": sum(1 for cell in cells if cell["ok"]),
            "failed": sum(1 for cell in cells if not cell["ok"]),
            "not_captured": len(missing_cells),
            "matrix_cells": len(matrix_destinations) * len(matrix_widths),
            "mixed_build": mixed_build,
            "mixed_run": mixed_run,
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
        f"Capture run: {', '.join(f'`{run}`' for run in manifest.get('capture_runs') or []) or '**unrecorded**'}",
        "",
        f"Cells: **{manifest['summary']['passed']} passed / {manifest['summary']['failed']} failed / "
        f"{manifest['summary']['not_captured']} never captured** "
        f"({manifest['summary']['captured']} of {manifest['summary']['matrix_cells']} matrix cells have a frame)",
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
    lines += ["", "## Never captured", ""]
    if not manifest["missing_cells"]:
        lines.append("None — every matrix cell has a frame.")
    else:
        lines.append(
            f"{len(manifest['missing_cells'])} matrix cell(s) have no cell record at all. These are "
            "not failures: nothing was captured for them, so there is nothing to judge."
        )
        lines.append("")
        for cell in manifest["missing_cells"]:
            lines.append(f"- {cell['destination']} at {cell['width']}px")
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
        lines.append(f"**{cell['cell']}** — {len(cell['images'])} image(s), "
                     f"{len(cell['backgrounds'])} background layer(s)")
        lines.append("")
        lines.append("| selector | kind | natural | rendered | ratio | sha256 | evidence |")
        lines.append("|---|---|---|---|---|---|---|")
        for image in cell["images"]:
            natural = image.get("natural") or {}
            rendered = image.get("rendered") or {}
            digest = image.get("sha256") or "none"
            if image.get("evidence_required"):
                backing = "verified" if image.get("evidence_ok") else "**missing**"
            else:
                backing = "not required"
            lines.append(
                f"| `{image.get('selector')}` | {image.get('kind')} | "
                f"{natural.get('width')}x{natural.get('height')} | "
                f"{rendered.get('width')}x{rendered.get('height')} | "
                f"{image.get('scale_ratio')} | `{digest}` | {backing} |"
            )
        lines.append("")
        if cell["backgrounds"]:
            lines.append("Background layers (judged for placeholder, data URI stand-in, Press Plate "
                         "and, unless the layer tiles at its natural size, 2x):")
            lines.append("")
            lines.append("| selector | repeat | size | natural | rendered | ratio | 2x judged | sha256 | problems |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for layer in cell["backgrounds"]:
                natural = layer.get("natural") or {}
                rendered = layer.get("rendered") or {}
                digest = layer.get("sha256") or "none"
                problems = "; ".join(layer["problems"]) or "none"
                judged_axes = layer.get("judged_axes") or []
                judged = ", ".join(judged_axes) if judged_axes else "no (tiles at natural size)"
                lines.append(
                    f"| `{layer.get('selector')}` | {layer.get('background_repeat') or 'unrecorded'} | "
                    f"{layer.get('background_size') or 'unrecorded'} | "
                    f"{natural.get('width')}x{natural.get('height')} | "
                    f"{rendered.get('width')}x{rendered.get('height')} | "
                    f"{layer.get('scale_ratio')} | {judged} | `{digest}` | {problems} |"
                )
            lines.append("")
    text = "\n".join(lines) + "\n"
    (output_dir / "MANIFEST.md").write_text(text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="capture output directory")
    parser.add_argument("--commit", default=None)
    parser.add_argument("--widths", default=None,
                        help="judge only these route widths (space or comma separated); default is the full matrix")
    parser.add_argument("--destinations", default=None,
                        help="judge only these destinations (space or comma separated); default is the full matrix")
    parser.add_argument("--require-complete", action="store_true",
                        help="deprecated and redundant: summary.ok has always required every requested cell")
    args = parser.parse_args()

    output_dir = Path(args.dir).resolve()
    if not output_dir.is_dir():
        print(f"vq: no such capture directory: {output_dir}", file=sys.stderr)
        return 2
    widths = None
    if args.widths:
        try:
            widths = tuple(int(token) for token in str(args.widths).replace(",", " ").split())
        except ValueError:
            print(f"vq: --widths must be integers: {args.widths}", file=sys.stderr)
            return 2
        unknown = [width for width in widths if width not in WIDTHS]
        if unknown:
            print(f"vq: unknown width(s) {unknown}; the installed matrix is {list(WIDTHS)}", file=sys.stderr)
            return 2
    destinations = None
    if args.destinations:
        destinations = tuple(str(args.destinations).replace(",", " ").split())
        unknown = [name for name in destinations if name not in DESTINATIONS]
        if unknown:
            print(f"vq: unknown destination(s) {unknown}; the installed matrix is {list(DESTINATIONS)}",
                  file=sys.stderr)
            return 2
    manifest = build_manifest(output_dir, args.commit, destinations=destinations, widths=widths)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    render_markdown(manifest, output_dir)
    sheet = contact_sheet(output_dir, manifest, output_dir / "contact-sheet.png")

    summary = manifest["summary"]
    print(f"output  : {output_dir}")
    print(f"contact : {sheet or 'not produced'}")
    print(f"matrix  : {len(manifest['matrix']['destinations'])} destinations x "
          f"{len(manifest['matrix']['widths'])} widths = {summary['matrix_cells']} cells")
    print(f"cells   : {summary['cells']} captured ({summary['passed']} pass, {summary['failed']} fail)")
    print(f"missing : {summary['not_captured']} of {summary['matrix_cells']} matrix cells were never "
          f"captured ({summary['captured']} have a frame)")
    for cell in manifest["cells"]:
        print(f"  {'PASS' if cell['ok'] else 'FAIL'}  {cell['cell']}")
        for problem in cell["problems"][:4]:
            print(f"        - {problem}")
    ok = summary["ok"]
    print(f"verdict : {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
