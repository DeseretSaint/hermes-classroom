"""Build the M3-U1 Pronunciation Studio evidence frames from the shipped Desktop module.

Renders the studio in the states the card names — available, recording, assessed, saved,
unavailable, empty speech, contract refusal, no recorder, reduced motion — by mounting the real
exported component in jsdom and driving Record/Stop/Save, then writes one self-contained HTML
document per frame for `scripts/m2fn-shot.mjs`. Two document frames prove where the studio sits in
the lesson (Textbook at 1280 px, Guided at 460 px), rendered through `react-dom/server`.

What this is: a renderer audit of the shipped components at the widths, modes and text scales the
card names, with the state produced by the component itself. What it is not: a live-app capture —
`scripts/m3p-live.mjs` is the separate live run against the isolated window.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from importlib.util import module_from_spec, spec_from_file_location


def _load_frame_shell():
    """Import the M2 frame shell by path: `scripts/` is not an installed package."""
    spec = spec_from_file_location("m2fn_frames", ROOT / "scripts" / "m2fn-frames.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.shell_html


shell_html = _load_frame_shell()
from tests.test_desktop_lesson_views import (  # noqa: E402
    COMPLETE_BLOCKS,
    SDK_STUB,
    _desktop_node_modules,
    document,
)
from tests.test_desktop_pronunciation import NARRATION_MEDIA, renumbered  # noqa: E402

OUT = ROOT / "audit" / "visual" / "m3-pronunciation"

SSR_HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as mod from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const mode = payload.mode || 'light'
const index = { src_affection01: { source_id: 'src_affection01', title: 'Affection and register — field notes' } }
const scope = (children) =>
  React.createElement('div', { 'data-cb-scope': mode, 'data-cb-motion': payload.motion || 'full', style: mod.cbScopeStyle(mode) },
    React.createElement('div', { 'data-cb-route': '/coursebook', style: { padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem', minHeight: '100vh' } }, children))
const html = renderToStaticMarkup(scope(React.createElement(mod.LessonDocumentView, {
  document: payload.document,
  view: payload.view,
  sources: index,
  checkSlot: null,
  pronunciation: payload.pronunciation,
  onSaveBlock: () => {}
})))
process.stdout.write(JSON.stringify({ html }))
"""

ASSESSMENT = {
    "transcript": "こんにちは。今日はいい天気ですね。",
    "target": "こんにちは。今日はいい天気ですね。",
    "locale": "ja", "provider": "coursebook_local_whisper", "model": "small", "language": "ja",
    "unit": "character", "word_accuracy": 0.7778, "phoneme_accuracy": None, "confidence": 0.7526,
    "words": [
        {"expected": "こ", "heard": "こ", "match": True, "confidence": 0.91},
        {"expected": "ん", "heard": "ん", "match": True, "confidence": 0.72},
        {"expected": "に", "heard": "に", "match": True, "confidence": 0.66},
        {"expected": "ち", "heard": "ち", "match": True, "confidence": 0.8},
        {"expected": "は", "heard": "わ", "match": False, "confidence": None},
        {"expected": "今", "heard": "今", "match": True, "confidence": 0.77},
        {"expected": "日", "heard": "日", "match": True, "confidence": 0.71},
        {"expected": "天", "heard": "て", "match": False, "confidence": None},
        {"expected": "気", "heard": "気", "match": True, "confidence": 0.69},
    ],
    "verdict": "close",
    "evidence_class": "model_assessed",
}

ASSESSED = {"ok": True, "result": {"status": "assessed", "recorded": True,
                                   "attempt_id": "prn_0123456789abcdef0123", "revision": 7,
                                   "assessment": ASSESSMENT, "reason": None}}
EMPTY = {"ok": True, "result": {"status": "empty", "recorded": False, "attempt_id": None,
                                "revision": 7, "reason": "empty_transcript",
                                "assessment": {"target": "こんにちは。今日はいい天気ですね。", "verdict": "unavailable"}}}
REFUSAL = {"ok": False, "error": {"code": "VALIDATION_FAILED", "category": "validation",
                                  "message": "the take is longer than 30 seconds", "retryable": False}}

FRAMES = [
    {"id": "01-studio-available-light-1280", "mode": "light", "width": 1280, "height": 620,
     "state": {"name": "available"}},
    {"id": "02-studio-recording-dark-1280", "mode": "dark", "width": 1280, "height": 620,
     "state": {"name": "recording"}},
    {"id": "03-studio-assessed-light-1280", "mode": "light", "width": 1280, "height": 820,
     "state": {"name": "assessed"}},
    {"id": "04-studio-assessed-dark-460", "mode": "dark", "width": 460, "height": 1100,
     "state": {"name": "assessed"}},
    {"id": "05-studio-unavailable-light-1280", "mode": "light", "width": 1280, "height": 620,
     "state": {"name": "unavailable"}},
    {"id": "06-studio-empty-speech-light", "mode": "light", "width": 1280, "height": 720,
     "state": {"name": "empty", "attempt": EMPTY}},
    {"id": "07-studio-refusal-light", "mode": "light", "width": 1280, "height": 720,
     "state": {"name": "refusal", "attempt": REFUSAL}},
    {"id": "08-studio-no-recorder-light-460", "mode": "light", "width": 460, "height": 760,
     "state": {"name": "no-recorder", "noRecorder": True}},
    {"id": "09-studio-saved-light-1280", "mode": "light", "width": 1280, "height": 900,
     "state": {"name": "saved"}},
    {"id": "10-studio-assessed-200pct-dark", "mode": "dark", "width": 1280, "height": 1200,
     "font": "32px", "state": {"name": "assessed"}},
    {"id": "11-studio-assessed-460-200pct", "mode": "light", "width": 460, "height": 1500,
     "font": "32px", "state": {"name": "assessed"}},
    {"id": "12-studio-unavailable-reduced-motion", "mode": "light", "width": 1280, "height": 620,
     "reduced_motion": True, "state": {"name": "unavailable"}},
]


def build_env(root: Path) -> None:
    modules = _desktop_node_modules()
    if modules is None:
        raise SystemExit("react/react-dom are not installed beside the desktop app")
    (root / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "states.mjs").write_text((ROOT / "scripts" / "m3p-states.mjs").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "ssr.mjs").write_text(SSR_HARNESS, encoding="utf-8")
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
    (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")


def scoped(fragment: str, style: str, mode: str, motion: str) -> str:
    return (
        f'<div data-cb-scope="{mode}" data-cb-motion="{motion}" style="{style}">'
        f'<div data-cb-route="/coursebook" style="padding:1.25rem clamp(1rem,4vw,4rem) 2rem;min-height:100vh">'
        f"{fragment}</div></div>"
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    evidence = {"frames": [], "states": []}
    with tempfile.TemporaryDirectory(prefix="coursebook-m3p-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        for frame in FRAMES:
            env = dict(os.environ)
            env.update(
                {
                    "CB_PRONUNCIATION_STATE": json.dumps(frame["state"]),
                    "CB_TEST_MODE": frame["mode"],
                    "CB_TEST_MOTION": "reduced" if frame.get("reduced_motion") else "full",
                }
            )
            result = subprocess.run(["node", "states.mjs"], cwd=root, env=env, capture_output=True, text=True, timeout=240)
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            html = scoped(rendered["markup"], rendered["style"], frame["mode"], rendered["motion"])
            frames.append(
                {
                    "id": frame["id"],
                    "state": rendered["phase"],
                    "width": frame["width"],
                    "height": frame["height"],
                    "reduced_motion": bool(frame.get("reduced_motion")),
                    "html": shell_html(html, frame.get("font")),
                }
            )
            evidence["states"].append(
                {
                    "frame": frame["id"],
                    "phase": rendered["phase"],
                    "availability": rendered["availability"],
                    "buttons": rendered["buttons"],
                    "calls": rendered["calls"],
                    "text": rendered["text"][:600],
                }
            )

        # The lesson seat: the studio in Textbook at 1280 px, then Guided at 460 px.
        lesson_doc = document(guided=True, blocks=renumbered(COMPLETE_BLOCKS), check_id="chk_0123456789abcdef")
        for frame_id, view, mode, width, height in (
            ("13-lesson-textbook-studio-light-1280", "textbook", "light", 1280, 1500),
            ("14-lesson-guided-studio-dark-460", "guided", "dark", 460, 1200),
        ):
            payload = {
                "document": lesson_doc,
                "view": view,
                "mode": mode,
                "motion": "full",
                "pronunciation": {
                    "enrollmentId": "enr_0123456789abcdef",
                    "objectiveId": "obj_0123456789abcdef",
                    "revision": 7,
                    "locale": "ja",
                    "implemented": ["pronunciation.attempt"],
                },
            }
            case = root / "case.json"
            case.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(["node", "ssr.mjs", str(case)], cwd=root, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            frames.append(
                {
                    "id": frame_id,
                    "state": f"lesson-{view}",
                    "width": width,
                    "height": height,
                    "reduced_motion": False,
                    "html": shell_html(rendered["html"], None),
                }
            )

    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
