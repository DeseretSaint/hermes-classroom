#!/usr/bin/env python3
"""H-177 — render the trail frames (and the pre-change module) through one pipeline.

The harness renders the shipped `CheckpointPath` inside the route wrapper the plugin paints, so the
frames prove the real module's geometry. Pass `--plugin <path>` (default: this worktree's
`desktop/plugin.js`) and `--out <dir>` (default: `audit/visual/h177-trail/after`). The same command
with `--plugin <git-show-of-HEAD>` produces the before set, so both sides are measured identically.

What this is: a renderer audit at the card's widths, modes and text scales. What it is not: a live
app capture — the live read is `scripts/h177-live-check.mjs`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_desktop_field_desk import SDK_STUB, _desktop_node_modules  # noqa: E402

# The shared stub drops a button's inline style, so a static frame would measure the UA's default
# button padding instead of the host Button, which honours the inline padding. Forward it: the
# frames must measure the geometry the installed Desktop paints.
_OLD_BUTTON = SDK_STUB[SDK_STUB.index("export const Button"):SDK_STUB.index("export const Badge")]
_BUTTON_STUB = """export const Button = (props) => {
  const attrs = { type: 'button', disabled: Boolean(props.disabled), onClick: props.onClick }
  for (const key of ['onPointerDown', 'onPointerUp', 'onPointerLeave', 'onPointerCancel', 'onBlur', 'onFocus']) {
    if (typeof props[key] === 'function') attrs[key] = props[key]
  }
  for (const key of ['className', 'aria-expanded', 'aria-controls', 'aria-current', 'aria-label', 'id', 'role', 'title']) {
    if (props[key] !== undefined) attrs[key] = props[key]
  }
  for (const key of Object.keys(props)) {
    if ((key.startsWith('data-') || key.startsWith('aria-')) && props[key] !== undefined && !(key in attrs)) attrs[key] = props[key]
  }
  if (props.style) attrs.style = props.style
  return el('button', attrs, textOf(props))
}
"""
SDK_STUB = SDK_STUB.replace(_OLD_BUTTON, _BUTTON_STUB)

OUT = ROOT / "audit" / "visual" / "h177-trail" / "after"

HARNESS = r"""
globalThis.__CB_TEST_MODE__ = process.env.CB_TEST_MODE || 'light'
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const payload = JSON.parse(process.env.CB_TEST_PAYLOAD)
const mode = process.env.CB_TEST_MODE || 'light'
const desk = mod.buildDeskModel({
  library: { items: [payload.row] },
  outline: payload.outline,
  estimate: payload.estimate || { status: 'none', minutes: null }
})
const html = renderToStaticMarkup(
  React.createElement('div', {
    'data-cb-scope': mode,
    style: mod.cbScopeStyle(mode)
  }, React.createElement('div', {
    'data-cb-route': '/coursebook',
    style: { padding: '1.25rem clamp(1rem, 4vw, 2rem) 2rem', minHeight: '100vh', boxSizing: 'border-box' }
  }, React.createElement(mod.CheckpointPath, {
    desk,
    onOpenSection: () => {},
    outlineStatus: 'ready',
    outlineError: null,
    onRetryOutline: () => {},
    companionEnabled: false
  })))
)
process.stdout.write(JSON.stringify({ html }))
"""


def objective(objective_id, ordinal, title, *, state="not_started", check_state="none",
              attempt_count=0, evidence_target="recall", independent=False, last_opened_at=None):
    return {
        "objective_id": objective_id,
        "ordinal": ordinal,
        "title": title,
        "evidence_target": evidence_target,
        "state": state,
        "check_state": check_state,
        "attempt_count": attempt_count,
        "independent": independent,
        "last_opened_at": last_opened_at,
    }


OUTLINE = {
    "enrollment_id": "enr_h177",
    "objectives": [
        objective("obj_01", 1, "Name the three things an engine needs", state="independent_evidence",
                  check_state="closed", attempt_count=2, evidence_target="recall", independent=True,
                  last_opened_at="2026-11-05T09:00:00.000000+00:00"),
        objective("obj_02", 2, "Diagnose a no-start", state="review_due", check_state="open",
                  attempt_count=1, evidence_target="procedure"),
        objective("obj_03", 3, "Replace a fouled plug", state="introduced", check_state="open",
                  evidence_target="production"),
        objective("obj_04", 4, "Check compression safely", state="not_started", check_state="none",
                  evidence_target="comprehension"),
    ],
}

ROW = {
    "enrollment_id": "enr_h177",
    "course_id": "crs_h177",
    "title": "Small-engine maintenance",
    "recipe": "committed",
    "revision": 3,
    "evidence_summary": {
        "total_objectives": 4,
        "independent": 1,
        "review_due": 1,
        "current_objective_id": "obj_02",
    },
    "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
}

STATE_MATRIX = {
    "enrollment_id": "enr_h177_matrix",
    "objectives": [
        objective("st_01", 1, "Not started yet", state="not_started", check_state="none"),
        objective("st_02", 2, "Started, no check yet", state="introduced", check_state="none",
                  attempt_count=1, evidence_target="recall"),
        objective("st_03", 3, "Evidence already held", state="independent_evidence",
                  check_state="closed", attempt_count=2, independent=True,
                  last_opened_at="2026-11-06T09:00:00.000000+00:00"),
        objective("st_04", 4, "A review is due", state="review_due", check_state="open",
                  attempt_count=1, evidence_target="procedure"),
        objective("st_05", 5, "Answer needs review", state="needs_review", check_state="open",
                  attempt_count=1, evidence_target="production"),
        objective("st_06", 6, "Overridden by the author", state="overridden",
                  check_state="superseded"),
        objective("st_07", 7, "A real gate at the end", state="not_started", check_state="open",
                  evidence_target="comprehension"),
    ],
}

MATRIX_ROW = {
    **ROW,
    "enrollment_id": "enr_h177_matrix",
    "course_id": "crs_h177_matrix",
    "title": "Every recorded state",
    "evidence_summary": {
        "total_objectives": 7,
        "independent": 1,
        "review_due": 2,
        "current_objective_id": "st_04",
    },
    "next_step": {"kind": "resolve_review_due", "label": "Review 2 objective(s)"},
}

MAIN = {
    "row": ROW,
    "outline": OUTLINE,
    "estimate": {"status": "ready", "minutes": 6, "source": "parent_brief", "error": None},
}

NO_ESTIMATE = {**MAIN, "estimate": {"status": "none", "minutes": None, "error": None}}

MATRIX = {
    "row": MATRIX_ROW,
    "outline": STATE_MATRIX,
    "estimate": {"status": "ready", "minutes": 6, "source": "parent_brief", "error": None},
}

FRAMES = [
    {"id": "01-light-1049", "mode": "light", "width": 1049, "height": 1100, "font": None, "payload": MAIN},
    {"id": "02-dark-1049", "mode": "dark", "width": 1049, "height": 1100, "font": None, "payload": MAIN},
    {"id": "03-light-900", "mode": "light", "width": 900, "height": 1100, "font": None, "payload": MAIN},
    {"id": "04-dark-900", "mode": "dark", "width": 900, "height": 1100, "font": None, "payload": MAIN},
    {"id": "05-light-460", "mode": "light", "width": 460, "height": 1400, "font": None, "payload": MAIN},
    {"id": "06-dark-460", "mode": "dark", "width": 460, "height": 1400, "font": None, "payload": MAIN},
    {"id": "07-light-460-text200", "mode": "light", "width": 460, "height": 1900, "font": "32px", "payload": MAIN},
    {"id": "08-dark-1049-text200", "mode": "dark", "width": 1049, "height": 1700, "font": "32px", "payload": MAIN},
    {"id": "09-matrix-light-1049", "mode": "light", "width": 1049, "height": 1700, "font": None, "payload": MATRIX},
    {"id": "10-matrix-dark-460", "mode": "dark", "width": 460, "height": 2200, "font": None, "payload": MATRIX},
    {"id": "11-no-estimate-light-1049", "mode": "light", "width": 1049, "height": 900, "font": None, "payload": NO_ESTIMATE},
    {"id": "12-keyboard-1049", "mode": "light", "width": 1049, "height": 1100, "font": None, "payload": MAIN, "focus": 1},
    {"id": "13-reduced-motion-1049", "mode": "light", "width": 1049, "height": 1100, "font": None, "payload": MAIN, "reduced": True},
]


def build_env(root: Path, plugin: Path) -> None:
    (root / "plugin.js").write_text(plugin.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
    node_modules = root / "node_modules"
    node_modules.mkdir()
    modules = _desktop_node_modules()
    if modules is None:
        raise SystemExit("react/react-dom are not installed beside the desktop app")
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.mjs"}),
        encoding="utf-8",
    )
    (sdk / "index.mjs").write_text(SDK_STUB, encoding="utf-8")


def shell_html(body: str, font: str | None) -> str:
    root_font = f"<style>html{{font-size:{font};}}</style>" if font else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
{root_font}
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
</style></head>
<body>{body}</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", default=str(ROOT / "desktop" / "plugin.js"))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    plugin = Path(args.plugin)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-h177-frames-") as tmp:
        root = Path(tmp)
        build_env(root, plugin)
        for frame in FRAMES:
            env = dict(os.environ)
            env.update(
                {
                    "CB_TEST_PAYLOAD": json.dumps(frame["payload"]),
                    "CB_TEST_MODE": frame["mode"],
                    "CB_TEST_WIDTH": str(frame["width"]),
                }
            )
            result = subprocess.run(
                ["node", "harness.mjs"], cwd=root, env=env, capture_output=True, text=True, timeout=180
            )
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            frames.append(
                {
                    "id": frame["id"],
                    "mode": frame["mode"],
                    "width": frame["width"],
                    "height": frame["height"],
                    "font": frame.get("font"),
                    "focus": frame.get("focus"),
                    "reduced": frame.get("reduced", False),
                    "html": shell_html(rendered["html"], frame.get("font")),
                }
            )
    (out / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "plugin": str(plugin), "path": str(out / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
