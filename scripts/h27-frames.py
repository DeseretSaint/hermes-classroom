"""Build the H-27 evidence frames from the shipped Desktop module.

Renders `SyllabusParseReview` and `SyllabusAlignmentReview` through real React, inside the same
scoped root the Coursebook route paints, then writes one self-contained HTML document per frame
for `scripts/h27-shot.mjs`.

The syllabus document is the FIXTURE from `tests/test_desktop_syllabus_ui.py` (labelled fixture
there): it is the frozen `syllabus.parse.v1` shape, not a backend response. This is a renderer
audit of the shipped components and the token layer — no backend, no chat, no RPC. Every number in
`evidence.json` is measured from the painted DOM.
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
from tests.test_desktop_syllabus_ui import FIXTURE_PARSE, _fixture_alignment  # noqa: E402

OUT = ROOT / "audit" / "visual" / "h27-student-syllabus"

HARNESS = """
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const mode = process.env.CB_TEST_MODE
const parsed = JSON.parse(process.env.CB_TEST_PARSED)
const alignment = JSON.parse(process.env.CB_TEST_ALIGNMENT)
const scope = (children) =>
  React.createElement('div', {
    'data-cb-scope': mode,
    'data-cb-motion': 'full',
    style: mod.cbScopeStyle(mode)
  }, children)
const parse = renderToStaticMarkup(scope(
  React.createElement(mod.SyllabusParseReview, {
    parsed,
    blocks: parsed.blocks || [],
    busy: false,
    onBack: () => {},
    onContinue: () => {},
    onReparse: () => {}
  })
))
const align = renderToStaticMarkup(scope(
  React.createElement(mod.SyllabusAlignmentReview, {
    alignment,
    busy: false,
    onDecision: () => {},
    onApprove: () => {},
    onRealign: () => {}
  })
))
process.stdout.write(JSON.stringify({ parse, align }))
"""

FRAMES = [
    {"id": "01-parse-light-1280", "surface": "parse", "mode": "light", "width": 1280, "height": 1500},
    {"id": "02-parse-dark-1280", "surface": "parse", "mode": "dark", "width": 1280, "height": 1500},
    {"id": "03-parse-light-460", "surface": "parse", "mode": "light", "width": 460, "height": 1900},
    {"id": "04-parse-dark-460", "surface": "parse", "mode": "dark", "width": 460, "height": 1900},
    {"id": "05-align-light-1280", "surface": "align", "mode": "light", "width": 1280, "height": 1200},
    {"id": "06-align-dark-1280", "surface": "align", "mode": "dark", "width": 1280, "height": 1200},
    {"id": "07-align-light-460", "surface": "align", "mode": "light", "width": 460, "height": 1600},
    {"id": "08-align-dark-460", "surface": "align", "mode": "dark", "width": 460, "height": 1600},
]

# A small utility shim: the frame has no Tailwind build, so the shipped utility class names are
# resolved here. Tokens stay the shipped ones (--cb-*, --ui-*), never a hard-coded colour.
UTILITY_CSS = """
  *, *::before, *::after { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  .cb-audit { padding: 1.5rem clamp(1rem, 4vw, 3rem); min-height: 100vh; }
  .flex { display: flex; } .grid { display: grid; }
  .flex-col { flex-direction: column; } .flex-wrap { flex-wrap: wrap; }
  .items-baseline { align-items: baseline; } .items-start { align-items: flex-start; }
  .items-center { align-items: center; } .justify-between { justify-content: space-between; }
  .gap-0\\.5 { gap: 0.125rem; } .gap-1 { gap: 0.25rem; } .gap-2 { gap: 0.5rem; }
  .gap-3 { gap: 0.75rem; } .gap-4 { gap: 1rem; }
  .gap-x-8 { column-gap: 2rem; } .gap-y-1 { row-gap: 0.25rem; }
  .min-w-0 { min-width: 0; } .max-w-prose { max-width: 65ch; }
  .w-full { width: 100%; } .h-px { height: 1px; } .self-start { align-self: flex-start; }
  .grid-cols-1 { grid-template-columns: repeat(1, minmax(0, 1fr)); }
  .text-xs { font-size: 0.75rem; line-height: 1.45; }
  .text-sm { font-size: 0.875rem; line-height: 1.5; }
  .font-medium { font-weight: 500; } .font-semibold { font-weight: 600; }
  .italic { font-style: italic; } .tracking-tight { letter-spacing: -0.01em; }
  .leading-relaxed { line-height: 1.7; }
  .mb-2 { margin-bottom: 0.5rem; } .mb-4 { margin-bottom: 1rem; }
  .mt-0\\.5 { margin-top: 0.125rem; } .mt-2 { margin-top: 0.5rem; } .mt-4 { margin-top: 1rem; }
  .pt-3 { padding-top: 0.75rem; } .py-1\\.5 { padding: 0.375rem 0; }
  .py-2 { padding: 0.5rem 0; } .pl-3 { padding-left: 0.75rem; }
  .border-b { border-bottom: 1px solid var(--ui-stroke-tertiary, #d9d1c2); }
  .border-t { border-top: 1px solid var(--ui-stroke-tertiary, #d9d1c2); }
  .border-l-2 { border-left: 2px solid var(--ui-stroke-secondary, #b5aa97); }
  .last\\:border-b-0:last-child { border-bottom: 0; }
  .whitespace-pre-wrap { white-space: pre-wrap; } .break-words { overflow-wrap: anywhere; }
  .text-\\(--ui-text-secondary\\) { color: var(--ui-text-secondary, #5a5347); }
  .bg-\\(--ui-stroke-tertiary\\) { background: var(--ui-stroke-tertiary, #d9d1c2); }
  button { font: inherit; border: 1px solid var(--ui-stroke-tertiary, #d9d1c2);
    background: transparent; color: inherit; border-radius: 0.375rem; padding: 0.2rem 0.55rem;
    cursor: pointer; }
  button[data-variant="default"] { background: var(--cb-accent, #2f4a8a); color: var(--cb-paper, #fff);
    border-color: var(--cb-accent, #2f4a8a); }
  button[data-variant="text"] { border-color: transparent; padding: 0 0.2rem; text-decoration: underline; }
  button[disabled] { opacity: .55; cursor: default; }
  .badge { display: inline-block; border: 1px solid var(--ui-stroke-tertiary, #d9d1c2);
    border-radius: 999px; padding: 0 0.45rem; font-size: 0.7rem; }
  .panel-label { font-size: 0.7rem; letter-spacing: .08em; text-transform: uppercase;
    color: var(--ui-text-secondary, #5a5347); margin: 1.1rem 0 0.35rem; }
  .panel-empty { font-size: 0.8rem; color: var(--ui-text-secondary, #5a5347); }
  .error-state { border-left: 2px solid var(--cb-coral, #9e2f1d); padding-left: .75rem; }
  @media (min-width: 47.5rem) {
    .min-\\[47\\.5rem\\]\\:grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .min-\\[47\\.5rem\\]\\:flex-row { flex-direction: row; }
    .min-\\[47\\.5rem\\]\\:w-72 { width: 18rem; }
  }
"""


def build_env(root: Path) -> None:
    (root / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
    modules = _desktop_node_modules()
    node_modules = root / "node_modules"
    node_modules.mkdir()
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.mjs"}), encoding="utf-8"
    )
    (sdk / "index.mjs").write_text(SDK_STUB, encoding="utf-8")


def shell_html(body: str, mode: str) -> str:
    tokens = {
        "light": {
            "paper": "#f7f3ea",
            "paper-raised": "#fffdf7",
            "ink": "#191713",
            "ink-soft": "#5a5347",
            "rule": "#d9d1c2",
            "accent": "#2f4a8a",
            "accent-soft": "#e4e9f4",
            "field": "#3f5c33",
            "ochre": "#7a4e0d",
            "coral": "#9e2f1d",
        },
        "dark": {
            "paper": "#141312",
            "paper-raised": "#1e1c19",
            "ink": "#f2ece0",
            "ink-soft": "#b5aa97",
            "rule": "#3b372f",
            "accent": "#9db5ee",
            "accent-soft": "#232b3c",
            "field": "#9cba87",
            "ochre": "#d7a94e",
            "coral": "#e38a76",
        },
    }[mode]
    vars_css = "\n".join(f"  --cb-{name}: {value};" for name, value in tokens.items())
    return f"""<!doctype html>
<html lang="en" class="{'dark' if mode == 'dark' else ''}"><head><meta charset="utf-8" />
<meta name="color-scheme" content="{mode}" />
<style>
:root {{
{vars_css}
  --ui-text-secondary: {tokens['ink-soft']};
  --ui-stroke-tertiary: {tokens['rule']};
  --ui-stroke-secondary: {tokens['ink-soft']};
}}
{UTILITY_CSS}
</style></head>
<body><div class="cb-audit" style="background: var(--cb-paper); color: var(--cb-ink);">{body}</div></body></html>"""


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-h27-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        env = dict(os.environ)
        env["CB_TEST_PARSED"] = json.dumps(FIXTURE_PARSE)
        env["CB_TEST_ALIGNMENT"] = json.dumps(_fixture_alignment())
        rendered_by_mode = {}
        for mode in ("light", "dark"):
            env["CB_TEST_MODE"] = mode
            result = subprocess.run(["node", "harness.mjs"], cwd=root, env=env, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered_by_mode[mode] = json.loads(result.stdout)
        for frame in FRAMES:
            rendered = rendered_by_mode[frame["mode"]]
            frames.append(
                {
                    "id": frame["id"],
                    "mode": frame["mode"],
                    "surface": frame["surface"],
                    "width": frame["width"],
                    "height": frame["height"],
                    "reduced_motion": False,
                    "html": shell_html(rendered[frame["surface"]], frame["mode"]),
                }
            )
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
