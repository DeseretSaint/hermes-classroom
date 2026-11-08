#!/usr/bin/env python3
"""H-186 renderer captures: the shipped MediaFrame/SectionPage with the real imported page.

This is a **renderer audit, not a live-app capture**: it renders the shipped `desktop/plugin.js`
through real React with the document `lesson.page` returned for the imported demo pack
(`audit/h186/page-1.json`, `page-2.json`), at 1049 / 460 and at 200% text. Every number comes from
the painted DOM; the PNGs come from the same document.

The static `SectionPage` cannot fetch an artifact preview (that needs a live RPC round trip), so
each page is followed by the shipped `MediaFrame` carrying the pack's real bytes as a data URL.
That second frame is the artifact-render probe; the page frame is the composition probe. The
authored `text_equivalent` is displayed as the page frame's figcaption (pack v2 defines the
caption as the equivalent), so the audit accepts a caption that is byte-equal to the authored
equivalent, and prefers an explicit disclosure when one is rendered.

    PYTHONPATH=. python3 scripts/h186-frames.py
    node scripts/h186-shot.mjs
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "audit" / "h186"
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"

_spec = importlib.util.spec_from_file_location("m2v_frames", ROOT / "scripts" / "m2v-frames.py")
assert _spec and _spec.loader
m2v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m2v)

HARNESS = """
globalThis.__CB_TEST_WIDTH__ = process.env.CB_TEST_WIDTH || '1049'
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const page = JSON.parse(process.env.CB_TEST_PAGE)
const mediaSpecs = JSON.parse(process.env.CB_TEST_MEDIA || '[]')
const mode = process.env.CB_TEST_MODE
const scope = (children) =>
  React.createElement('div', {
    'data-cb-scope': mode,
    'data-cb-motion': 'full',
    style: mod.cbScopeStyle(mode)
  }, children)
const section = renderToStaticMarkup(scope(
  React.createElement(mod.SectionPage, {
    row: { enrollment_id: 'enr_h186', profile: 'default', next_step: { kind: 'start_lesson', label: 'Start' } },
    objectiveId: page.document.objective_id,
    page,
    pageStatus: 'ready',
    pageError: null,
    onRetryPage: () => {},
    implemented: new Set(['check.open', 'artifact.get']),
    onBack: () => {},
    onChanged: () => {},
    review: null,
    defaultLessonView: 'textbook'
  })
))
const mediaChild = (spec) =>
  spec.mime.startsWith('audio/')
    ? React.createElement('audio', {
        controls: true,
        preload: 'metadata',
        src: spec.data_url,
        'aria-label': spec.caption
      })
    : React.createElement('img', {
        alt: spec.caption,
        src: spec.data_url,
        style: { maxHeight: '380px', width: '100%', objectFit: 'contain' }
      })
const media = mediaSpecs.map((spec) =>
  renderToStaticMarkup(scope(
    React.createElement(mod.MediaFrame, {
      artifactId: spec.artifact_id,
      kind: spec.kind,
      label: spec.kind === 'audio' ? 'Narration' : 'Illustration',
      caption: spec.caption,
      provenance: spec.mime + ' · ' + spec.bytes + ' bytes · packaged artifact',
      textEquivalent: spec.text_equivalent,
      children: mediaChild(spec)
    })
  ))
)
process.stdout.write(JSON.stringify({ section, media, width: Number(process.env.CB_TEST_WIDTH || '1049'), mode }))
"""

FRAMES = [
    {"id": "audio-1049", "mode": "light", "width": 1049, "height": 1400, "font": None, "page": 2},
    {"id": "audio-460", "mode": "light", "width": 460, "height": 1800, "font": None, "page": 2},
    {"id": "audio-1049-text200", "mode": "light", "width": 1049, "height": 1900, "font": "32px", "page": 2},
    {"id": "audio-460-text200", "mode": "light", "width": 460, "height": 2600, "font": "32px", "page": 2},
    {"id": "visual-1049", "mode": "light", "width": 1049, "height": 1400, "font": None, "page": 1},
    {"id": "visual-460", "mode": "light", "width": 460, "height": 1800, "font": None, "page": 1},
    {"id": "visual-1049-text200", "mode": "light", "width": 1049, "height": 1900, "font": "32px", "page": 1},
    {"id": "visual-460-text200", "mode": "light", "width": 460, "height": 2600, "font": "32px", "page": 1},
]


def _pack_file_by_hash() -> dict[str, Path]:
    manifest = json.loads((JAPANESE / "pack.json").read_text(encoding="utf-8"))
    mapping: dict[str, Path] = {}
    for entry in manifest["files"]:
        path = JAPANESE / entry["path"]
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        mapping[digest] = path
    return mapping


def _media_payload(page: dict, by_hash: dict[str, Path]) -> list[dict]:
    paths = {a["artifact_id"]: by_hash.get(a["content_hash"]) for a in page["artifacts"]}
    payload = []
    for block in page["document"].get("blocks") or []:
        for child in block.get("media") or []:
            path = paths.get(child["artifact_id"])
            if path is None:
                continue
            bytes_ = path.read_bytes()
            payload.append({
                "artifact_id": child["artifact_id"],
                "kind": child["kind"],
                "mime": "audio/mpeg" if path.suffix == ".mp3" else "image/png",
                "bytes": len(bytes_),
                "data_url": f"data:{'audio/mpeg' if path.suffix == '.mp3' else 'image/png'};base64,"
                            + base64.b64encode(bytes_).decode("ascii"),
                "caption": child["purpose"],
                "text_equivalent": child["text_equivalent"],
            })
    return payload


def _expected(page: dict) -> list[str]:
    return [
        child["text_equivalent"]
        for block in page["document"].get("blocks") or []
        for child in block.get("media") or []
    ]


def main() -> int:
    modules = m2v._desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    pages = {index: json.loads((OUT / f"page-{index}.json").read_text(encoding="utf-8")) for index in (1, 2)}
    by_hash = _pack_file_by_hash()
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-h186-frames-") as tmp:
        root = Path(tmp)
        m2v.build_env(root)
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        for frame in FRAMES:
            page = pages[frame["page"]]
            page["document"]["objective_id"] = page["section"]["objective_id"]
            expected = _expected(page)
            env = dict(os.environ)
            env.update({
                "CB_TEST_PAGE": json.dumps(page),
                "CB_TEST_MEDIA": json.dumps(_media_payload(page, by_hash)),
                "CB_TEST_MODE": frame["mode"],
                "CB_TEST_WIDTH": str(frame["width"]),
            })
            result = subprocess.run(["node", "harness.mjs"], cwd=root, env=env, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            html = m2v.shell_html(rendered["section"], "".join(rendered.get("media") or []), frame["font"])
            html = html.replace(
                "</body>",
                "<script>window.__CB_EXPECTED_EQUIVALENTS__="
                + json.dumps(expected, ensure_ascii=False).replace("</", "<\\/")
                + ";</script></body>",
            )
            frames.append({
                "id": frame["id"],
                "page": frame["page"],
                "width": frame["width"],
                "height": frame["height"],
                "font": frame["font"],
                "expected_text_equivalents": expected,
                "html": html,
            })
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
