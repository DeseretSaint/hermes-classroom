"""Build the M4 procedure-layout evidence frames from the shipped Desktop module.

Renders the real `LessonDocumentView` with the validated head-gasket document inside the same
scoped token root the Coursebook route paints, then writes one self-contained HTML document per
frame for `scripts/m4p-shot.mjs`.

This is a renderer audit of the procedure layout: no backend, no chat, no RPC, and no artifact
bytes (the schematic rows are the authority; the attached SVG degrades to its text equivalent).
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

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules  # noqa: E402
from tests.test_desktop_procedure import SOURCES  # noqa: E402
from tests.test_procedure_document import head_gasket_document  # noqa: E402

OUT = ROOT / "audit" / "visual" / "m4-procedure"

HARNESS = """
globalThis.__CB_TEST_WIDTH__ = process.env.CB_TEST_WIDTH || '1280'
globalThis.__CB_TEST_MODE__ = process.env.CB_TEST_MODE || 'light'
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const page = JSON.parse(process.env.CB_TEST_PROCEDURE)
const mode = process.env.CB_TEST_MODE || 'light'
const index = {}
for (const source of page.sources || []) index[source.source_id] = source
const checkNode = React.createElement('div', { 'data-cb-audit-check': '' }, 'VERIFICATION-CHECKLIST')
const scope = React.createElement(
  'div',
  { 'data-cb-scope': mode, 'data-cb-motion': process.env.CB_TEST_MOTION || 'full', style: mod.cbScopeStyle(mode) },
  React.createElement(mod.LessonDocumentView, {
    document: page.document,
    view: 'textbook',
    sources: index,
    checkSlot: checkNode
  })
)
const html = renderToStaticMarkup(scope)
process.stdout.write(JSON.stringify({ html, width: Number(process.env.CB_TEST_WIDTH || '1280'), mode }))
"""

FRAMES = [
    {"id": "01-light-wide", "mode": "light", "width": 1280, "height": 1600, "font": None, "motion": "full"},
    {"id": "02-dark-wide", "mode": "dark", "width": 1280, "height": 1600, "font": None, "motion": "full"},
    {"id": "03-light-460", "mode": "light", "width": 460, "height": 2200, "font": None, "motion": "full"},
    {"id": "04-dark-460", "mode": "dark", "width": 460, "height": 2200, "font": None, "motion": "full"},
    {"id": "05-dark-200pct", "mode": "dark", "width": 1280, "height": 2600, "font": "32px", "motion": "full"},
    {"id": "06-dark-460-200pct", "mode": "dark", "width": 460, "height": 3400, "font": "32px", "motion": "full"},
    {"id": "07-light-reduced-motion", "mode": "light", "width": 1280, "height": 1600, "font": None, "motion": "reduced"},
]


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


def shell_html(section: str, font: str | None) -> str:
    root_font = f"<style>html{{font-size:{font};}}</style>" if font else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
{root_font}
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .cb-audit {{ padding: 1.5rem clamp(1rem, 4vw, 3rem); min-height: 100vh; }}
</style></head>
<body><div class="cb-audit">{section}</div></body></html>"""


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    page = {"document": head_gasket_document(), "sources": SOURCES}
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-m4p-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        for frame in FRAMES:
            env = dict(os.environ)
            env.update({
                "CB_TEST_PROCEDURE": json.dumps(page),
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
                "font": frame["font"],
                "reduced_motion": frame["motion"] == "reduced",
                "html": shell_html(rendered["html"], frame["font"]),
            })
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
