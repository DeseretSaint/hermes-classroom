"""Build the M2-V1 evidence frames from the shipped Desktop module.

Renders `SectionPage` (the three-part lesson workspace) plus a `MediaFrame` through real React,
inside the same scoped root the Coursebook route paints, then writes one self-contained HTML
document per frame for `scripts/m2v-shot.cjs`.

This is a renderer audit of the token layer and the route shell. It is not a live-app capture: no
backend, no chat, no RPC. The DOM measurements and the PNGs come from the same document.
"""

from __future__ import annotations

import json
import os
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

OUT = ROOT / "audit" / "visual" / "m2-ink-field-notes"

HARNESS = """
globalThis.__CB_TEST_WIDTH__ = process.env.CB_TEST_WIDTH || '1280'
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const page = JSON.parse(process.env.CB_TEST_PAGE)
const mode = process.env.CB_TEST_MODE
const width = Number(process.env.CB_TEST_WIDTH || '1280')
const scope = (children) =>
  React.createElement('div', {
    'data-cb-scope': mode,
    'data-cb-motion': process.env.CB_TEST_MOTION || 'full',
    style: mod.cbScopeStyle(mode)
  }, children)
const section = renderToStaticMarkup(scope(
  React.createElement(mod.SectionPage, {
    row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default', next_step: { kind: 'resume_lesson', label: 'Resume this lesson' } },
    objectiveId: page.document.objective_id,
    page,
    pageStatus: 'ready',
    pageError: null,
    onRetryPage: () => {},
    implemented: new Set(['check.open', 'artifact.get']),
    onBack: () => {},
    onChanged: () => {},
    review: null
  })
))
const mediaFrame = renderToStaticMarkup(scope(
  React.createElement(mod.MediaFrame, {
    artifactId: 'art_0123456789abcdef',
    kind: 'audio',
    label: 'Narration',
    caption: 'Reference audio for “おはよう” in the casual register.',
    provenance: 'audio/mpeg · 18234 bytes · tts:openai · transcript authored',
    textEquivalent: 'Ohayou. A morning greeting used with friends and family.',
    children: React.createElement('audio', { controls: true, src: 'about:blank' })
  })
))
process.stdout.write(JSON.stringify({ section, mediaFrame, width, mode }))
"""

FRAMES = [
    {"id": "01-light-wide", "mode": "light", "width": 1280, "height": 1000, "font": None, "motion": "full"},
    {"id": "02-dark-wide", "mode": "dark", "width": 1280, "height": 1000, "font": None, "motion": "full"},
    {"id": "03-light-460", "mode": "light", "width": 460, "height": 1100, "font": None, "motion": "full"},
    {"id": "04-dark-460", "mode": "dark", "width": 460, "height": 1100, "font": None, "motion": "full"},
    {"id": "05-dark-200pct", "mode": "dark", "width": 1280, "height": 1400, "font": "32px", "motion": "full"},
    {"id": "06-dark-460-200pct", "mode": "dark", "width": 460, "height": 1500, "font": "32px", "motion": "full"},
    {"id": "07-light-reduced-motion", "mode": "light", "width": 1280, "height": 1000, "font": None, "motion": "reduced"},
]

PAGE = {
    "revision": 4,
    "section": {
        "objective_id": "obj_0123456789abcdef",
        "title": "Affection and register",
        "state": "in_progress",
        "evidence_target": "discrimination",
        "last_opened_at": None,
    },
    "runtime": {"lesson_run_id": "run_1", "binding_id": None, "binding_status": "detached", "session_state": "stored_only"},
    "segments": [],
    "attempts": [],
    "notebook_entries": [{"entry_id": "ent_1", "excerpt": "Keigo versus casual: who you can use it with."}],
    "sources": [
        {"source_id": "src_affection01", "title": "Register and affection in Japanese", "support_status": "supported"},
        {"source_id": "src_affection02", "title": "Keigo: a short field guide", "support_status": "supported"},
    ],
    "document": document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef"),
}


def build_env(root: Path) -> None:
    (root / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
    node_modules = root / "node_modules"
    node_modules.mkdir()
    modules = _desktop_node_modules()
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.mjs"}), encoding="utf-8")
    (sdk / "index.mjs").write_text(SDK_STUB, encoding="utf-8")


def shell_html(section: str, media: str, font: str | None) -> str:
    root_font = f"<style>html{{font-size:{font};}}</style>" if font else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
{root_font}
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .cb-audit {{ padding: 1.5rem clamp(1rem, 4vw, 3rem); min-height: 100vh; }}
  .cb-audit-rule {{ margin: 2rem 0; border: 0; border-top: 1px dashed currentColor; opacity: .4; }}
</style></head>
<body><div class="cb-audit">{section}<hr class="cb-audit-rule" />{media}</div></body></html>"""


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-m2v-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        for frame in FRAMES:
            env = dict(os.environ)
            env.update({
                "CB_TEST_PAGE": json.dumps(PAGE),
                "CB_TEST_MODE": frame["mode"],
                "CB_TEST_WIDTH": str(frame["width"]),
                "CB_TEST_MOTION": frame["motion"],
            })
            result = subprocess.run(["node", "harness.mjs"], cwd=root, env=env, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            frames.append({
                "id": frame["id"],
                "width": frame["width"],
                "height": frame["height"],
                "reduced_motion": frame["motion"] == "reduced",
                "html": shell_html(rendered["section"], rendered["mediaFrame"], frame["font"]),
            })
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
