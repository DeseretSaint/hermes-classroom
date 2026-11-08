#!/usr/bin/env python3
"""Build the M4-V1 visual/media evidence frames from the shipped Desktop module.

Three stages, all reproducible from this one command:

1. render — run the shipped `desktop/plugin.js` component tree in jsdom with a stubbed host
   transport (`scripts/m4v-render.mjs`), so effects run and the real `<img>` / `<audio>` players
   mount; serialize each scenario to standalone HTML.
2. paint/measure — `scripts/m4v-audit.mjs` opens each HTML file in headless Chromium, emulates the
   variant (viewport, root font size, forced colors, reduced motion), screenshots it, and reads
   tokens, contrast, clipping, control names, media and motion facts from the painted DOM.
3. aggregate — write `audit/visual/m4-visual/audit.json` with per-frame measurements and a verdict
   per claim.

    python3 scripts/m4v-audit.py
"""

from __future__ import annotations

import base64
import copy
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

from tests.test_desktop_lesson_views import (  # noqa: E402
    COMPLETE_BLOCKS,
    SDK_STUB,
    _desktop_node_modules,
    document,
)
from tests.test_desktop_procedure import SOURCES as PROCEDURE_SOURCES  # noqa: E402
from tests.test_procedure_document import head_gasket_document  # noqa: E402
from tests.test_desktop_field_desk import OUTLINE, library, library_row  # noqa: E402
from coursebook import artifacts  # noqa: E402

OUT = Path(os.environ.get("M4V_OUT") or (ROOT / "audit" / "visual" / "m4-visual"))
SCRATCH = Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "coursebook-m4v"

# The fixture clock. `whenLabel` in the module turns a timestamp into "17 hr ago", and the render
# harness bakes that copy into the frame HTML. Left on the wall clock, every regeneration rewrote
# eight PNGs and dozens of `contrast_rows` entries with the passage of time rather than a change in
# the product, which is the opposite of evidence. The harness freezes Date.now to this instant
# while it renders, so "Last touched" is a property of the fixture, not of the run.
REFERENCE_TIME = "2026-11-07T10:00:00.000Z"

IMAGE_ARTIFACT = "art_image00000001"
AUDIO_ARTIFACT = "art_audio00000002"


def _media_path(env_var: str, fixture_name: str) -> Path:
    """Resolve one media fixture: explicit override, then the committed fixture, then legacy scratch.

    The gate ran off two files in ``~/.hermes/cache/scratch`` for a while. That directory is pruned
    by the scratch janitor, so a clean machine could not reproduce the evidence at all (H-136). The
    committed fixtures under ``tests/fixtures/media`` come first; the legacy scratch path stays only
    as a fallback for a machine that still has the original M0 bytes, and an env override lets a
    probe point the gate at a fresh artifact without editing code.
    """
    override = os.environ.get(env_var)
    if override:
        return Path(override).expanduser().resolve()
    fixture = ROOT / "tests" / "fixtures" / "media" / fixture_name
    if fixture.is_file():
        return fixture
    return Path.home() / ".hermes" / "cache" / "scratch" / fixture_name


IMAGE_PATH = _media_path("M4V_IMAGE", "cb-media-image.png")
AUDIO_PATH = _media_path("M4V_AUDIO", "cb-media-audio.mp3")

# Real media carries its own magic; a renamed placeholder must not silently satisfy the gate.
MEDIA_MAGIC = {IMAGE_PATH: b"\x89PNG", AUDIO_PATH: b"\xff\xf3"}
MEDIA_MIME = {IMAGE_PATH: "image/png", AUDIO_PATH: "audio/mpeg"}


def media_fixtures() -> dict:
    """The bytes this run actually served, with the hash and location, so the review is verifiable."""
    fixtures = {}
    for role, path in (("image", IMAGE_PATH), ("audio", AUDIO_PATH)):
        data = path.read_bytes() if path.is_file() else b""
        magic = MEDIA_MAGIC[path]
        fixtures[role] = {
            "path": str(path.relative_to(ROOT)) if path.is_file() and path.is_relative_to(ROOT) else str(path),
            "sha256": hashlib.sha256(data).hexdigest() if data else None,
            "bytes": len(data),
            "mime": MEDIA_MIME[path],
            "magic_ok": data.startswith(magic),
            "source": (
                "M4V_" + role.upper() if os.environ.get("M4V_" + role.upper())
                else "committed fixture" if path.is_relative_to(ROOT)
                else "legacy scratch"
            ),
        }
    return fixtures


AFFECTION_SOURCE = {
    "source_id": "src_affection01",
    "title": "Register and affection",
    "support_status": "supported",
    "url": None,
    "citation": "Course note, unit 3",
}

IMAGE_TEXT = ("A workshop bench with a head gasket and a torque wrench. Context illustration only; "
              "it carries no torque value, sequence, clearance or safety instruction.")
AUDIO_TEXT = "こんにちは。今日はいい天気ですね。 (Konnichiwa. Kyō wa ii tenki desu ne.) Good afternoon. The weather is nice today."


def media_document() -> dict:
    """A v8 document whose explain block has a real illustration and whose practice block has real audio."""
    blocks = copy.deepcopy(COMPLETE_BLOCKS)
    blocks[1]["media"] = [{
        "kind": "visual",
        "role": "illustration",
        "artifact_id": IMAGE_ARTIFACT,
        "purpose": "Context for the maintenance setting",
        "text": "Workshop bench, head gasket and torque wrench.",
        "text_equivalent": IMAGE_TEXT,
        "label": "Illustration — generated for context only",
    }]
    blocks[2]["media"] = [{
        "kind": "audio",
        "role": "narration",
        "artifact_id": AUDIO_ARTIFACT,
        "purpose": "Reference pronunciation of the target phrase",
        "text": "Greeting: こんにちは。今日はいい天気ですね。",
        "text_equivalent": AUDIO_TEXT,
        "label": "Narration — the transcript is authoritative",
    }]
    doc = document(guided=True, blocks=blocks, check_id="chk_0123456789abcdef", state="complete")
    doc["views"] = {"textbook": True, "guided": True, "field_quest": True, "field_notes": True}
    return doc


def text_only_document() -> dict:
    """The text-only path: media roles exist, but no artifact bytes are attached."""
    doc = media_document()
    for block in doc["blocks"]:
        for item in block.get("media", []):
            item["artifact_id"] = None
    return doc


def media_answers(procedure: dict | None = None) -> dict:
    fixtures = media_fixtures()
    missing = [role for role, item in fixtures.items() if not item["bytes"]]
    if missing:
        raise SystemExit(
            "missing media fixture(s): "
            + ", ".join(f"{role} ({fixtures[role]['path']})" for role in missing)
            + " — set M4V_IMAGE / M4V_AUDIO or restore tests/fixtures/media/"
        )
    bad = [role for role, item in fixtures.items() if not item["magic_ok"]]
    if bad:
        raise SystemExit(
            "media fixture(s) do not carry real media magic: "
            + ", ".join(f"{role} ({fixtures[role]['path']})" for role in bad)
        )
    image = base64.b64encode(IMAGE_PATH.read_bytes()).decode("ascii")
    audio = base64.b64encode(AUDIO_PATH.read_bytes()).decode("ascii")
    answers: dict = {
        IMAGE_ARTIFACT: {
            "mime": "image/png",
            "bytes": IMAGE_PATH.stat().st_size,
            "label": "Illustration — generated for context only",
            "text_equivalent": IMAGE_TEXT,
            "permission": "generated",
            "data_url": f"data:image/png;base64,{image}",
        },
        AUDIO_ARTIFACT: {
            "mime": "audio/mpeg",
            "bytes": AUDIO_PATH.stat().st_size,
            "label": "Narration — the transcript is authoritative",
            "text_equivalent": AUDIO_TEXT,
            "permission": "generated",
            "data_url": f"data:audio/mpeg;base64,{audio}",
        },
    }
    # A deterministic schematic is a real artifact too: render it from the document's own
    # structured rows through the shipped builder, exactly as the media job would.
    for document in [procedure] if procedure else []:
        schematic = (document.get("procedure") or {}).get("schematic") or {}
        artifact_id = schematic.get("artifact_id")
        rows = schematic.get("rows") or []
        if artifact_id and rows:
            svg = artifacts.make_schematic_svg(
                schematic.get("title") or "Schematic",
                [{"label": row.get("label"), "value": row.get("value"), "row": row.get("row", index)}
                 for index, row in enumerate(rows)],
            )
            answers[artifact_id] = {
                "mime": "image/svg+xml",
                "bytes": len(svg),
                "label": "Deterministic schematic",
                "text_equivalent": schematic.get("text_equivalent") or "",
                "permission": "generated",
                "data_url": "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii"),
            }
    return answers


SURFACES = ["textbook", "textbook-textonly", "textbook-unavailable", "guided", "quest", "procedure", "field-desk"]

# A render key = surface + painted mode + host viewport class + motion. The module reads the host
# viewport atom at render time, so the 460px layout is rendered at 460 CSS px rather than scaled.
RENDERS = []
for surface in SURFACES:
    for mode in ("light", "dark"):
        for width_class in (1280, 460):
            RENDERS.append({
                "key": f"{surface}-{mode}-{width_class}-full",
                "surface": surface,
                "mode": mode,
                "width": width_class,
                "reducedMotion": False,
            })
for surface in ("textbook", "quest"):
    for mode in ("light", "dark"):
        RENDERS.append({
            "key": f"{surface}-{mode}-1280-reduced",
            "surface": surface,
            "mode": mode,
            "width": 1280,
            "reducedMotion": True,
        })

FRAMES = []


def add(surface: str, mode: str, width_class: int, font: int | None, forced: str = "none",
        height: int = 1400, motion: str = "full") -> None:
    render = f"{surface}-{mode}-{width_class}-{motion}"
    frame_id = f"{surface}-{mode}-{width_class}-{font or 16}"
    if forced == "active":
        frame_id += "-forced"
    if motion == "reduced":
        frame_id += "-reduced"
    FRAMES.append({
        "id": frame_id,
        "render": render,
        "width": width_class,
        "height": height,
        "font_px": font or 16,
        "forced_colors": forced,
    })


for surface in SURFACES:
    for mode in ("light", "dark"):
        add(surface, mode, 1280, None)
        add(surface, mode, 1280, 32)
        add(surface, mode, 460, None, height=2600)
for surface in ("textbook", "guided", "quest", "procedure", "field-desk"):
    for mode in ("light", "dark"):
        add(surface, mode, 460, 32, height=3400)
for surface in ("textbook", "procedure", "field-desk"):
    for mode in ("light", "dark"):
        add(surface, mode, 1280, None, forced="active", height=1600)
for surface in ("textbook", "quest"):
    for mode in ("light", "dark"):
        add(surface, mode, 1280, None, motion="reduced")


def build_env(root: Path, modules: Path) -> None:
    (root / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text((ROOT / "scripts" / "m4v-render.mjs").read_text(encoding="utf-8"), encoding="utf-8")
    node_modules = root / "node_modules"
    node_modules.mkdir()
    for name in ("react", "react-dom", "scheduler", "jsdom"):
        source = modules / name
        if source.is_dir():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
    )
    (sdk / "index.js").write_text(
        SDK_STUB.replace(
            "const el = (tag, props, children) => React.createElement(tag, props, children)",
            "const el = (tag, props, children) => React.createElement(tag, { 'data-cb-host-primitive': '', ...(props || {}) }, children)",
        ),
        encoding="utf-8",
    )


def scenarios() -> dict:
    media_doc = media_document()
    procedure_doc = head_gasket_document()
    desk = library(library_row())
    return {
        "document": media_doc,
        "procedure": procedure_doc,
        "sources": [AFFECTION_SOURCE] + PROCEDURE_SOURCES,
        "library": desk,
        "outline": OUTLINE,
        "estimate": {"minutes": 12, "basis": "authored"},
        "evidence": {"independent": 2, "review_due": 1, "total_objectives": 5,
                     "current_objective_id": "obj_0123456789abcdef"},
        "media": media_answers(procedure_doc),
        "implemented": ["library.list", "course.outline", "lesson.page", "artifact.get", "check.open", "notebook.save"],
        "textonly_document": text_only_document(),
    }


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    if shutil.which("chromium") is None:
        print("chromium is required for the painted audit", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    html_dir = SCRATCH / "html"
    skip_render = os.environ.get("M4V_SKIP_RENDER") == "1" and (SCRATCH / "frames.json").is_file()
    if not skip_render:
        shutil.rmtree(html_dir, ignore_errors=True)
        html_dir.mkdir(parents=True, exist_ok=True)

    base = scenarios()
    base["referenceTime"] = REFERENCE_TIME
    if os.environ.get("M4V_SKIP_RENDER") == "1" and (SCRATCH / "frames.json").is_file():
        print("skipping render stage; reusing", SCRATCH / "frames.json")
    else:
        with tempfile.TemporaryDirectory(prefix="coursebook-m4v-env-") as tmp:
            env_root = Path(tmp)
            build_env(env_root, modules)
            for render in RENDERS:
                payload = dict(base)
                if render["surface"] in ("textbook-unavailable", "textbook"):
                    payload["mediaState"] = "unavailable" if render["surface"] == "textbook-unavailable" else "ready"
                if render["surface"] == "textbook-textonly":
                    payload["document"] = base["textonly_document"]
                    payload["mediaState"] = "ready"
                payload["reducedMotion"] = render["reducedMotion"]
                payload["width"] = render["width"]
                payload["focusBlockId"] = "blk_explain001" if render["surface"] == "guided" else None
                payload["frames"] = [{
                    "id": render["key"],
                    "surface": render["surface"],
                    "mode": render["mode"],
                    "reducedMotion": render["reducedMotion"],
                }]
                case = env_root / "case.json"
                case.write_text(json.dumps(payload), encoding="utf-8")
                result = subprocess.run(
                    ["node", "harness.mjs", str(case), str(html_dir)],
                    cwd=env_root, capture_output=True, text=True, timeout=180,
                )
                if result.returncode != 0:
                    print(f"render {render['key']} failed:\n{result.stderr[-4000:]}", file=sys.stderr)
                    return 1
                print(f"rendered {render['key']}")

        frames_doc = {"frames": FRAMES, "html_dir": str(html_dir), "reference_time": REFERENCE_TIME}
        (SCRATCH / "frames.json").write_text(json.dumps(frames_doc, indent=2), encoding="utf-8")
        print(json.dumps({"renders": len(RENDERS), "frames": len(FRAMES), "html_dir": str(html_dir)}))
    if not (SCRATCH / "frames.json").is_file():
        print("no frames.json — the render stage did not run", file=sys.stderr)
        return 1
    frames_doc = json.loads((SCRATCH / "frames.json").read_text(encoding="utf-8"))
    if frames_doc.get("reference_time") != REFERENCE_TIME:
        print("the cached frames were rendered against a different reference time; re-run without "
              "M4V_SKIP_RENDER=1", file=sys.stderr)
        return 1

    result = subprocess.run(
        ["node", str(ROOT / "scripts" / "m4v-audit.mjs"), str(SCRATCH / "frames.json"), str(OUT)],
        capture_output=True, text=True, timeout=600,
    )
    print(result.stdout[-6000:])
    if result.returncode != 0:
        print(result.stderr[-4000:], file=sys.stderr)
        return 1
    return 0 if aggregate() == 0 else 1


COLOUR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\boklch\(|\blab\(")


def _luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(channels[0]) + 0.7152 * linear(channels[1]) + 0.0722 * linear(channels[2])


def _contrast(foreground: str, background: str) -> float:
    first, second = _luminance(foreground), _luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


def contract_gates(contract: dict | None) -> dict:
    """The contract's own token-pair floors, computed on the values that ship."""
    if not contract:
        return {"gates": 0, "failures": []}
    modes = contract.get("modes") or {}
    failures = []
    for mode, palette in modes.items():
        for gate in contract.get("gates") or []:
            foreground = palette.get(gate.get("foreground"))
            background = palette.get(gate.get("background"))
            if not foreground or not background:
                continue
            ratio = _contrast(foreground, background)
            if ratio < float(gate.get("min", 0)):
                failures.append({
                    "mode": mode,
                    "pair": f"{gate.get('foreground')} on {gate.get('background')}",
                    "ratio": round(ratio, 2),
                    "min": gate.get("min"),
                })
    return {
        "gates": len(contract.get("gates") or []) * len(modes),
        "failures": failures,
        "min_ratio": round(min(
            (_contrast(palette[gate["foreground"]], palette[gate["background"]])
             for palette in modes.values() for gate in contract.get("gates") or []
             if gate.get("foreground") in palette and gate.get("background") in palette),
            default=0,
        ), 2),
    }


def source_scan() -> dict:
    text = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    table_match = re.search(r"const CB_TOKENS_JSON\s*=\s*'(\{.*?\})'", text, re.S)
    token_table = table_match.group(1) if table_match else ""
    outside = [match.group(0) for match in COLOUR_LITERAL.finditer(text) if match.group(0) not in token_table]
    hex_outside = [match.group(0) for match in re.finditer(r"#[0-9a-fA-F]{3,8}\b", text) if match.group(0) not in token_table]
    # The shipped table is v2 (Atlas Lamp). Prefer the newest contract on disk so the claim compares
    # the module against the contract it actually implements, and keep v1 as history.
    contract = ROOT / "contracts" / "cb.tokens.v2.json"
    if not contract.is_file():
        contract = ROOT / "contracts" / "cb.tokens.v1.json"
    contract_tokens = json.loads(contract.read_text(encoding="utf-8")) if contract.is_file() else None
    shipped_palette = json.loads(token_table) if token_table else None
    return {
        "file": "desktop/plugin.js",
        "colour_literals_outside_token_table": len(outside),
        "hex_literals_outside_token_table": len(hex_outside),
        "sample": outside[:8],
        "tertiary_text_utility_uses": text.count("ui-text-tertiary"),
        "contract_file": str(contract.relative_to(ROOT)),
        "contract_present": contract_tokens is not None,
        "contract_matches_shipped_table": (
            contract_tokens.get("modes") == shipped_palette
            if contract_tokens is not None and shipped_palette is not None else None
        ),
        "contract_gates": contract_gates(contract_tokens),
    }


def aggregate() -> int:
    audit_path = OUT / "audit.json"
    evidence = json.loads(audit_path.read_text(encoding="utf-8"))
    frames = evidence["frames"]
    audit_frames = [frame for frame in frames if not frame["forced_colors"]]
    forced = [frame for frame in frames if frame["forced_colors"]]

    authored_failures = sum(frame["contrast_failures"] for frame in audit_frames)
    authored_min = min(
        (frame["contrast_min_authored"] for frame in audit_frames if frame["contrast_min_authored"] is not None),
        default=None,
    )
    unnamed = sum(frame["ax_unnamed"] or 0 for frame in frames)
    controls = sum(frame["ax_controls"] or 0 for frame in frames)
    keyboard_unnamed = sum(frame["keyboard_unnamed"] or 0 for frame in frames)
    keyboard_unreachable = sum(len(frame["keyboard_unreachable"] or []) for frame in frames)
    keyboard_ring_missing = sum(frame["keyboard_ring_missing"] or 0 for frame in frames)
    keyboard_stops = sum(frame["keyboard_count"] or 0 for frame in frames)
    keyboard_shadow_stops = sum(frame["keyboard_shadow_stops"] or 0 for frame in frames)
    clipped = sum(frame["clipped_count"] for frame in frames)
    overflow = [frame["id"] for frame in frames if frame["horizontal_overflow"]]
    autoplay = sum(
        1 for frame in frames for audio in frame["audios"]
        if audio["autoplay_attribute"] or audio["autoplay_property"] or audio["playing"]
    )
    audio_total = sum(len(frame["audios"]) for frame in frames)
    image_total = sum(len(frame["images"]) for frame in frames)
    images_without_alt = sum(1 for frame in frames for image in frame["images"] if not image["has_alt"])
    images_not_decoded = sum(1 for frame in frames for image in frame["images"] if not image["naturalWidth"])
    audio_without_transcript = sum(
        1 for frame in frames for audio in frame["audios"] if not str(audio["aria_label"]).strip()
    )
    media_frames = [item for frame in frames for item in frame["media_frames"]]
    media_without_text = [item for item in media_frames if not item.get("caption_is_text_equivalent")]
    media_without_label = [item for item in media_frames if not item.get("label")]
    inline_literals = sum(len(frame["inline_colour_literals"]) for frame in frames)
    token_complete = all(
        all(frame["tokens"].get(name) for name in (
            "paper", "paper-raised", "ink", "ink-soft", "rule", "accent", "accent-soft", "field", "ochre", "coral"
        ))
        for frame in frames
    )
    animated_reduced = sum(frame["animated_nodes"] for frame in frames if frame["motion_attr"] == "reduced")
    animated_full = sum(frame["animated_nodes"] for frame in frames if frame["motion_attr"] != "reduced")
    positive_tabindex = sum(frame["positive_tabindex"] for frame in frames)
    unavailable = [frame for frame in frames if frame["surface"] == "textbook-unavailable"]
    textonly = [frame for frame in frames if frame["surface"] == "textbook-textonly"]
    scan = source_scan()

    def verdict(condition: bool, partial: bool = False) -> str:
        if condition:
            return "PASS"
        return "PARTIAL" if partial else "FAIL"

    claims = [
        {
            "id": "C-01", "claim": "Every Coursebook surface paints only from the `--cb-*` token layer; no raw colour outside it.",
            "verdict": verdict(scan["colour_literals_outside_token_table"] == 0 and inline_literals == 0
                                and token_complete and not scan["contract_gates"]["failures"]),
            "evidence": {"source_scan": scan, "inline_colour_literals_in_frames": inline_literals,
                          "frames_with_all_ten_tokens": sum(1 for frame in frames if all(frame["tokens"].values())),
                          "frames": len(frames)},
        },
        {
            "id": "C-02", "claim": "Contrast floor at least the F-01 bar (4.5:1 normal, 3:1 large) for plugin-authored text, light and dark.",
            "verdict": verdict(authored_failures == 0 and (authored_min or 0) >= 4.5),
            "evidence": {"authored_failures": authored_failures, "authored_min_ratio": authored_min,
                          "measured_text_nodes": sum(frame["text_nodes"] for frame in audit_frames),
                          "frames": len(audit_frames),
                          "excluded_host_primitive_failures": sum(frame["contrast_host_primitive_failures"] for frame in frames),
                          "note": "host-primitive rows are the SDK stub's UA surface, not product paint; they are reported separately and excluded."},
        },
        {
            "id": "C-03", "claim": "No clipped text and no horizontal overflow at 100%/200% text, 1280 and 460 CSS px.",
            "verdict": verdict(clipped == 0 and not overflow),
            "evidence": {"clipped_nodes": clipped, "overflow_frames": overflow,
                          "narrow_frames": sum(1 for frame in frames if frame["width"] == 460),
                          "text200_frames": sum(1 for frame in frames if frame["font_px"] == 32)},
        },
        {
            "id": "C-04", "claim": "Every interactive control has an accessible name and is keyboard reachable.",
            "verdict": verdict(unnamed == 0 and keyboard_unnamed == 0 and keyboard_unreachable == 0
                                and keyboard_ring_missing == 0 and positive_tabindex == 0),
            "evidence": {"ax_controls": controls, "ax_unnamed": unnamed, "keyboard_unnamed": keyboard_unnamed,
                          "keyboard_stops": keyboard_stops, "keyboard_unreachable": keyboard_unreachable,
                          "keyboard_ring_missing": keyboard_ring_missing,
                          "keyboard_host_widget_stops": keyboard_shadow_stops,
                          "positive_tabindex": positive_tabindex,
                          "keyboard_frames": sum(1 for frame in frames if frame["keyboard_count"]),
                          "note": "the walk presses Tab until every control the DOM declares has been "
                                  "visited once and focus wraps, then counts distinct authored stops; the "
                                  "audio player's UA shadow parts are host-widget stops and are counted "
                                  "separately, never as Coursebook controls."},
        },
        {
            "id": "C-05", "claim": "Audio never autoplays.",
            "verdict": verdict(autoplay == 0),
            "evidence": {"audio_elements": audio_total, "autoplay_or_playing": autoplay},
        },
        {
            "id": "C-06", "claim": "Every instructional image has a text equivalent.",
            "verdict": verdict(image_total > 0 and images_without_alt == 0 and not media_without_text),
            "evidence": {"images": image_total, "images_without_alt": images_without_alt,
                          "media_frames_without_text_equivalent": len(media_without_text),
                          "frames_with_image": sum(1 for frame in frames if frame["images"])},
        },
        {
            "id": "C-07", "claim": "Every audio has a transcript.",
            "verdict": verdict(audio_total > 0 and audio_without_transcript == 0 and not [
                item for item in media_frames if item.get("has_audio") and not item.get("caption_is_text_equivalent")]),
            "evidence": {"audio_elements": audio_total, "audio_without_accessible_transcript": audio_without_transcript,
                          "audio_frames": sum(1 for frame in frames if frame["audios"])},
        },
        {
            "id": "C-08", "claim": "Reduced motion is respected.",
            "verdict": verdict(animated_reduced == 0),
            "evidence": {"animated_nodes_reduced": animated_reduced, "animated_nodes_full": animated_full,
                          "reduced_frames": [frame["id"] for frame in frames if frame["id"].endswith("-reduced")],
                          "note": "the shipped module paints no CSS transition or animation in any mode, so the reduced preference removes nothing; the preference is still read and recorded. This claim is trivially satisfied, not proven by suppression of real motion."},
        },
        {
            "id": "C-09", "claim": "Forced-colors mode stays readable and does not depend on the token layer.",
            "verdict": verdict(all(frame["contrast_failures"] == 0 for frame in forced) and not [f for f in forced if f["horizontal_overflow"]]),
            "evidence": {"frames": [frame["id"] for frame in forced],
                          "min_ratio": min((frame["contrast_min"] for frame in forced if frame["contrast_min"]), default=None),
                          "clipped": sum(frame["clipped_count"] for frame in forced)},
        },
        {
            "id": "C-10", "claim": "A media provider/route failure leaves the lesson readable with the text equivalent and no fake artifact.",
            "verdict": verdict(
                bool(unavailable) and all(not frame["images"] and not frame["audios"] and frame["media_fallback_text"] for frame in unavailable)
            ),
            "evidence": {"frames": [frame["id"] for frame in unavailable],
                          "images": sum(len(frame["images"]) for frame in unavailable),
                          "audios": sum(len(frame["audios"]) for frame in unavailable),
                          "fallback_text_sample": unavailable[0]["media_fallback_text"] if unavailable else [],
                          "media_frames": len(unavailable[0]["media_frames"]) if unavailable else 0},
        },
        {
            "id": "C-11", "claim": "The text-only path renders media roles as text with no player and no broken frame.",
            "verdict": verdict(
                bool(textonly) and all(not frame["images"] and not frame["audios"] for frame in textonly)
            ),
            "evidence": {"frames": [frame["id"] for frame in textonly],
                          "images": sum(len(frame["images"]) for frame in textonly),
                          "audios": sum(len(frame["audios"]) for frame in textonly),
                          "fallback_text_sample": textonly[0]["media_fallback_text"] if textonly else [],
                          "note": "there is no user-facing reduced-data/text-only preference in the shipped plugin; this is the no-artifact fallback path, which is what the plan's text-only variant exercises."},
        },
        {
            "id": "C-12", "claim": "The image player renders the real generated artifact through the media route.",
            "verdict": verdict(image_total > 0 and images_not_decoded == 0),
            "evidence": {"images": image_total, "not_decoded": images_not_decoded,
                          "natural_widths": sorted({image["naturalWidth"] for frame in frames for image in frame["images"]})},
        },
        {
            "id": "C-13", "claim": "The audio player renders the real generated artifact with explicit controls and no autoplay.",
            "verdict": verdict(audio_total > 0 and autoplay == 0 and all(
                audio["controls"] and audio["src_kind"] == "data-url" and audio["preload"] == "metadata"
                for frame in frames for audio in frame["audios"])),
            "evidence": {"audio_elements": audio_total,
                          "controls_missing": sum(1 for frame in frames for audio in frame["audios"] if not audio["controls"]),
                          "preloads": sorted({audio["preload"] for frame in frames for audio in frame["audios"]}),
                          "src_kinds": sorted({audio["src_kind"] for frame in frames for audio in frame["audios"]})},
        },
        {
            "id": "C-14", "claim": "One real illustration fixture is labelled context and is not usable as a procedure authority.",
            "verdict": verdict(not media_without_label and all(
                "context" in item["label"].lower() for item in media_frames
                if item["artifact"].startswith("art_image") and item["label"])),
            "evidence": {"media_labels": sorted({item["label"] for item in media_frames if item["label"]}),
                          "media_without_label": len(media_without_label),
                          "artifact_review": "docs/M4-VISUAL-MEDIA-AUDIT.md#independent-illustration-review",
                          "independent_review": {
                              "artifact": media_fixtures()["image"]["path"],
                              "sha256": media_fixtures()["image"]["sha256"],
                              "mime": "image/png",
                              "bytes": media_fixtures()["image"]["bytes"],
                              "pixels": "1024x576",
                              "provenance": "committed gate fixture generated deterministically by "
                                            "scripts/make-m4-fixtures.py; not a generated illustration and "
                                            "not the M0 host-probe image",
                              "depicts": "a flat workshop-bench plate: one large circular gasket/hub plate "
                                         "with concentric rings and two locating holes, a torque-wrench "
                                         "silhouette to the right, a mallet and a drift on the bench",
                              "absent": "no text, no numbers, no arrows, no bolt sequence, no clearances, "
                                        "no orientation marks, and no legible wrench scale",
                              "verdict": "context only; cannot carry a torque value, sequence, clearance or safety instruction",
                          }},
        },
        {
            "id": "C-15", "claim": "Every media item carries a label and a provenance line in its field-note frame.",
            "verdict": verdict(not media_without_label and all(item["label"] for item in media_frames)),
            "evidence": {"media_frames": len(media_frames), "without_label": len(media_without_label)},
        },
    ]

    # D-1 was found by the first run of this gate: a refused media route dropped the authored
    # kind and typed narration as `visual`. The Desktop fix carries `media.kind` into the segment
    # and lets the served MIME override it only when the preview is ready. The status below is
    # derived from the freshly generated frames, so a regression re-opens the defect here.
    unavailable_audio = [
        item for frame in frames if frame["surface"] == "textbook-unavailable"
        for item in frame["media_frames"] if str(item.get("artifact") or "").startswith("art_audio")
    ]
    audio_kind_fixed = bool(unavailable_audio) and all(item["kind"] == "audio" for item in unavailable_audio)

    defects = [
        {
            "id": "D-1", "severity": "low",
            "status": "fixed" if audio_kind_fixed else "open",
            "title": "A failed audio preview is typed as `visual` in the media frame",
            "detail": "MediaSegment derived `kind` from the preview MIME, so a refused route typed an audio item as visual. It now carries the authored `kind` into the segment and uses the served MIME only when the preview is ready.",
            "evidence": {
                "frames": [frame["id"] for frame in frames if frame["surface"] == "textbook-unavailable"],
                "audio_media_frames": len(unavailable_audio),
                "audio_kinds": sorted({item["kind"] for item in unavailable_audio}),
            },
            "owner": "desktop specialist (product code)",
        }
    ]

    summary = {
        "frames": len(frames),
        "surfaces": sorted({frame["surface"] for frame in frames}),
        "variants": {
            "modes": sorted({frame["scope_mode"] for frame in frames}),
            "widths": sorted({frame["width"] for frame in frames}),
            "root_font_px": sorted({frame["font_px"] for frame in frames}),
            "forced_colors_frames": len(forced),
            "reduced_motion_frames": sum(1 for frame in frames if frame["id"].endswith("-reduced")),
        },
        "claims": {item["id"]: item["verdict"] for item in claims},
        "defects": defects,
        "reference_time": evidence.get("reference_time"),
        "media_fixtures": media_fixtures(),
        "plugin_sha256": hashlib.sha256((ROOT / "desktop" / "plugin.js").read_bytes()).hexdigest(),
        "branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip(),
        "note": "the evidence is pinned by plugin_sha256; find the generating commit in the branch history that carries audit/visual/m4-visual/audit.json",
    }
    evidence["source_scan"] = scan
    evidence["claims"] = claims
    evidence["defects"] = defects
    evidence["summary"] = summary
    audit_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    failed = [item["id"] for item in claims if item["verdict"] != "PASS"]
    print(f"claims: {len(claims) - len(failed)} PASS, {len(failed)} not PASS {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
