#!/usr/bin/env python3
"""H-196 — build the Workshop evidence frames from recorded real backend payloads.

Every fact in a frame is read from the shipped code and the real backend on a throwaway, migrated
profile home:

* the catalogue is `coursebook.workshop.catalog_view()` — the same function the `/workshop/catalog`
  route calls, which re-hashes every bundled pack from disk;
* the installed state is produced by the real `workshop.install()` → the real atomic `pack.import`
  gate, not by editing a JSON blob;
* the Library rows are a real `library.list` envelope from `coursebook.api.dispatch`;
* the cover image is the pack's own file, encoded by the real `media.preview_artifact` route (which
  re-verifies size and sha256 and refuses anything that is not render-safe).

The renderer (`scripts/h196-workshop-render.mjs`) mounts the shipped module in jsdom and replays
those payloads through `ctx.rest`; `scripts/h196-workshop-shot.mjs` screenshots the result in
Chromium at each width, mode, text scale and motion posture. The transport is stubbed; the data,
the components and the interactions are not.
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

from coursebook import api, db, media, workshop  # noqa: E402
from tests.kernel_support import request  # noqa: E402

OUT = ROOT / "audit" / "visual" / "h196-workshop"
SITE = OUT / "site"
HTML_DIR = OUT / "html"

SDK_STUB = """
import React from 'react'

const atom = (value) => ({ get: () => value, subscribe: () => () => {} })
const el = (tag, props, children) => React.createElement(tag, props, children)
const textOf = (props) => (props && props.children !== undefined ? props.children : null)

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const useValue = (a) => a.get()
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })

const pass = (props) => {
  const out = { type: 'button', onClick: props.onClick, disabled: Boolean(props.disabled) }
  for (const key of ['className', 'aria-expanded', 'aria-controls', 'aria-current', 'aria-label', 'id', 'role', 'title']) {
    if (props[key] !== undefined) out[key] = props[key]
  }
  for (const key of Object.keys(props)) {
    if (key.startsWith('data-') && props[key] !== undefined) out[key] = props[key]
  }
  return out
}

export const Button = (props) => el('button', pass(props), textOf(props))
export const RowButton = (props) => el('button', pass(props), textOf(props))
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const ListRow = (props) =>
  el('div', { className: 'list-row' }, [
    el('div', { key: 'title', className: 'list-row-title' }, props.title),
    el('div', { key: 'description', className: 'list-row-description' }, props.description),
    el('div', { key: 'action', className: 'list-row-action' }, props.action)
  ])
export const SegmentedControl = (props) =>
  el('div', { className: 'segmented' }, (props.options || []).map((option) =>
    el('button', { key: option.id, 'aria-pressed': option.id === props.value, type: 'button' }, option.label)))
export const Input = () => null
export const Textarea = () => null
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = () => null
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null
export const MessageTextContent = () => null

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: Number(globalThis.__CB_WIDTH__ || 1049), height: 900, narrow: false })
  },
  profileRoutes: async () => [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }],
  navigate: () => {},
  notify: () => {},
  openSession: async () => ({ ok: true }),
  newChat: async () => ({ ok: true })
}
"""


def _desktop_node_modules() -> Path | None:
    candidates = [
        os.environ.get("HERMES_DESKTOP_APP"),
        str(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop"),
        str(Path.home() / ".hermes" / "hermes-agent"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        modules = Path(candidate) / "node_modules"
        if (modules / "react").is_dir() and (modules / "react-dom" / "server.js").is_file():
            return modules
    return None


def _methods() -> list[str]:
    """The implemented-method list the backend advertises — the registry itself, as /runtime does."""
    return list(api.implemented_methods())


def _envelope(method: str, payload: dict) -> dict:
    return api.dispatch(request(method, payload))


def build_payloads() -> dict:
    home = tempfile.mkdtemp(prefix="coursebook-h196-frames-")
    previous = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = home
    try:
        db.migrate()
        library_empty = _envelope("library.list", {"filter": "all", "limit": 50, "sort": "title"})
        catalog_fresh = {"ok": True, **workshop.catalog_view()}
        installed = workshop.install("japanese-affection-context-l0")
        catalog_installed = {"ok": True, **workshop.catalog_view()}
        library_full = _envelope("library.list", {"filter": "all", "limit": 50, "sort": "title"})
        packs = _envelope("pack.list", {"filter": "all", "limit": 100})
        # The install response is what the route returns, captured from the real call. The first
        # press imported; a second press must be the idempotent answer, so both are captured and
        # the frame records the first (the honest "result of pressing Add").
        install_response = {"ok": True, **installed}
        install_repeat = {"ok": True, **workshop.install("japanese-affection-context-l0")}

        covers: dict[str, dict] = {}
        with db.read() as connection:
            for entry in catalog_installed["items"]:
                artifact_id = (entry.get("cover") or {}).get("artifact_id")
                if not artifact_id or artifact_id in covers:
                    continue
                row = connection.execute(
                    "SELECT id FROM artifacts WHERE id = ?", (artifact_id,)
                ).fetchone()
                if row is None:
                    continue
                covers[artifact_id] = media.preview_artifact(artifact_id)
    finally:
        if previous is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous
        shutil.rmtree(home, ignore_errors=True)

    runtime = {
        "ok": True,
        "wire_version": api.RPC_CONTRACT_VERSION,
        "implemented_methods": _methods(),
        "single_home_host": False,
    }
    rest = {
        "/runtime": runtime,
        "/workshop/catalog": catalog_fresh,
        "/workshop/install": install_response,
    }
    for artifact_id, payload in covers.items():
        rest[f"/media/{artifact_id}"] = payload
    rpc = {
        "library.list": library_empty,  # replaced per frame below when the installed shelf is wanted
        "pack.list": packs,
    }
    return {
        "catalog_fresh": catalog_fresh,
        "catalog_installed": catalog_installed,
        "library_empty": library_empty,
        "library_full": library_full,
        "rest": rest,
        "rpc": rpc,
        "rpc_full": {**rpc, "library.list": library_full},
        "media_ids": sorted(covers),
        "install_response": install_response,
        "install_repeat": install_repeat,
    }


FRAMES = [
    # Discover — the storefront itself.
    {"id": "01-discover-light-1049", "view": "workshop", "mode": "light", "width": 1049, "height": 1560},
    {"id": "02-discover-dark-1049", "view": "workshop", "mode": "dark", "width": 1049, "height": 1560},
    {"id": "03-discover-light-900", "view": "workshop", "mode": "light", "width": 900, "height": 1660},
    {"id": "04-discover-light-460", "view": "workshop", "mode": "light", "width": 460, "height": 2400},
    {"id": "05-discover-dark-460", "view": "workshop", "mode": "dark", "width": 460, "height": 2400},
    {"id": "06-discover-200pct-460", "view": "workshop", "mode": "light", "width": 460, "height": 3600, "font": "32px"},
    {
        "id": "07-discover-reduced-motion-1049",
        "view": "workshop",
        "mode": "light",
        "width": 1049,
        "height": 1560,
        "motion": "reduced",
    },
    # Installed Discover: the real pack artifact as hero, and Continue as the one primary.
    {
        "id": "08-discover-installed-light-1049",
        "view": "workshop",
        "mode": "light",
        "width": 1049,
        "height": 1560,
        "catalog": "catalog_installed",
        "rpc": "rpc_full",
    },
    # Pack detail — real outcomes, sections, sources, licence, changelog.
    {
        "id": "09-detail-light-1049",
        "view": "detail",
        "pack_id": "japanese-affection-context-l0",
        "mode": "light",
        "width": 1049,
        "height": 1900,
        "catalog": "catalog_installed",
    },
    {
        "id": "10-detail-dark-900",
        "view": "detail",
        "pack_id": "japanese-affection-context-l0",
        "mode": "dark",
        "width": 900,
        "height": 2000,
        "catalog": "catalog_installed",
    },
    {
        "id": "11-detail-light-460",
        "view": "detail",
        "pack_id": "japanese-affection-context-l0",
        "mode": "light",
        "width": 460,
        "height": 2600,
        "catalog": "catalog_installed",
    },
    # No-media fallback: a pack with no visual gets type, not a drawn shape.
    {
        "id": "12-no-media-fallback-light-1049",
        "view": "detail",
        "pack_id": "parent-measurement-practice",
        "mode": "light",
        "width": 1049,
        "height": 1800,
    },
    {
        "id": "13-no-media-fallback-light-460",
        "view": "detail",
        "pack_id": "technical-demo-pack",
        "mode": "light",
        "width": 460,
        "height": 2400,
    },
    # A card press opens the real detail panel (the shipped control, clicked).
    {
        "id": "14-card-opens-detail-1049",
        "view": "workshop",
        "mode": "light",
        "width": 1049,
        "height": 1900,
        "actions": [{"click": "[data-cb-workshop-open=\"japanese-affection-context-l0\"]", "note": "opened the featured card"}],
    },
    # Library — the installed shelf, with the real row the import produced.
    {
        "id": "15-library-light-1049",
        "view": "workshop",
        "mode": "light",
        "width": 1049,
        "height": 1100,
        "catalog": "catalog_installed",
        "rpc": "rpc_full",
        "actions": [{"click": "[data-cb-workshop-tab=\"library\"]", "note": "Library tab"}],
    },
    {
        "id": "16-library-dark-460",
        "view": "workshop",
        "mode": "dark",
        "width": 460,
        "height": 1400,
        "catalog": "catalog_installed",
        "rpc": "rpc_full",
        "actions": [{"click": "[data-cb-workshop-tab=\"library\"]", "note": "Library tab"}],
    },
    # Empty state — a profile that holds nothing, read through the real Library surface.
    {
        "id": "17-library-empty-light-1049",
        "view": "workshop",
        "mode": "light",
        "width": 1049,
        "height": 900,
        "actions": [{"click": "[data-cb-workshop-tab=\"library\"]", "note": "Library tab, nothing installed"}],
    },
    # Add to library, pressed: the real install envelope replayed, then the catalogue re-read.
    {
        "id": "18-add-to-library-result-1049",
        "view": "workshop",
        "mode": "light",
        "width": 1049,
        "height": 1900,
        "catalogAfterInstall": "catalog_installed",
        "rpc": "rpc_full",
        "actions": [
            {"click": "[data-cb-workshop-open=\"japanese-affection-context-l0\"]", "note": "opened the featured card"},
            {"clickText": "Add to library", "note": "pressed Add to library"},
        ],
    },
]


def shell_html(body: str, font: str | None) -> str:
    root_font = f"<style>html{{font-size:{font};}}</style>" if font else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
{root_font}
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  img {{ max-width: 100%; }}
  .empty-state {{ display: flex; flex-direction: column; gap: 0.3rem; }}
</style></head>
<body>{body}</body></html>"""


def build_site(modules: Path) -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    (SITE / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (SITE / "render.mjs").write_text(
        (ROOT / "scripts" / "h196-workshop-render.mjs").read_text(encoding="utf-8"), encoding="utf-8"
    )
    node_modules = SITE / "node_modules"
    node_modules.mkdir()
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    jsdom = modules.parent / "jsdom"
    if not jsdom.is_dir():
        jsdom = modules / "jsdom"
    (node_modules / "jsdom").symlink_to(jsdom, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.mjs"}), encoding="utf-8"
    )
    (sdk / "index.mjs").write_text(SDK_STUB, encoding="utf-8")


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    payloads = build_payloads()
    build_site(modules)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    (OUT / "recorded.json").write_text(json.dumps(payloads, indent=2), encoding="utf-8")

    frames = []
    for frame in FRAMES:
        case = {
            "view": frame["view"],
            "mode": frame["mode"],
            "width": frame["width"],
            "motion": frame.get("motion", "full"),
            "pack_id": frame.get("pack_id"),
            "actions": frame.get("actions", []),
            "catalog": payloads[frame.get("catalog", "catalog_fresh")],
            "catalogAfterInstall": payloads[frame["catalogAfterInstall"]]
            if frame.get("catalogAfterInstall")
            else None,
            "rest": payloads["rest"],
            "rpc": payloads[frame.get("rpc", "rpc")],
            "implemented": _methods(),
            "prefs": {"favorites": [], "categories": {}},
        }
        case_file = SITE / "case.json"
        case_file.write_text(json.dumps(case), encoding="utf-8")
        env = dict(os.environ)
        env["CB196_CASE"] = str(case_file)
        result = subprocess.run(
            ["node", "render.mjs"], cwd=SITE, env=env, capture_output=True, text=True, timeout=240
        )
        if result.returncode != 0:
            print(f"{frame['id']}: render failed", file=sys.stderr)
            print(result.stderr[-4000:], file=sys.stderr)
            return 1
        try:
            rendered = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"{frame['id']}: renderer printed no JSON\n{result.stdout[:2000]}", file=sys.stderr)
            return 1
        frames.append(
            {
                "id": frame["id"],
                "view": frame["view"],
                "mode": frame["mode"],
                "width": frame["width"],
                "height": frame["height"],
                "font": frame.get("font"),
                "motion": frame.get("motion", "full"),
                "notes": rendered.get("notes", []),
                "html": shell_html(rendered["html"], frame.get("font")),
            }
        )
        print(f"{frame['id']}: {', '.join(rendered.get('notes', [])) or 'no interaction'}", file=sys.stderr)
        if frame["id"] in ("15-library-light-1049", "18-add-to-library-result-1049"):
            print("   requests: " + " | ".join(rendered.get("requests", [])), file=sys.stderr)

    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json"), "media_ids": payloads["media_ids"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
