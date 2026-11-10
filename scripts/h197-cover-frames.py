#!/usr/bin/env python3
"""H-197 — build the cover evidence frames from recorded real backend payloads.

Additive to H-196: it does not touch `audit/visual/h196-workshop/`. It reuses that card's renderer
and SDK stub, but records a different state: *both* cover-bearing packs imported through the real
`workshop.install()` gate, so the storefront, the Library rows and the pack detail all resolve the
same catalogue-named plate through the real `media.preview_artifact` route. The parent pack stays
uninstalled to show the typographic fallback.

Output: `audit/visual/h197-covers/frames.json` and, after `scripts/h197-cover-shot.mjs`, the PNGs.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import api, db, media, workshop  # noqa: E402
from tests.kernel_support import request  # noqa: E402


def _load_base():
    spec = importlib.util.spec_from_file_location(
        "h196_workshop_frames", ROOT / "scripts" / "h196-workshop-frames.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the H-196 frame builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_base()
OUT = ROOT / "audit" / "visual" / "h197-covers"
SITE = OUT / "site"
HTML_DIR = OUT / "html"
base.OUT = OUT
base.SITE = SITE
base.HTML_DIR = HTML_DIR

COVER_PACKS = ("japanese-affection-context-l0", "technical-pack-literacy")


def _envelope(method: str, payload: dict) -> dict:
    return api.dispatch(request(method, payload))


def build_payloads() -> dict:
    home = tempfile.mkdtemp(prefix="coursebook-h197-frames-")
    previous = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = home
    try:
        db.migrate()
        library_empty = _envelope("library.list", {"filter": "all", "limit": 50, "sort": "title"})
        catalog_fresh = {"ok": True, **workshop.catalog_view()}
        installs = {}
        for pack_id in COVER_PACKS:
            installs[pack_id] = {"ok": True, **workshop.install(pack_id)}
        catalog_installed = {"ok": True, **workshop.catalog_view()}
        library_full = _envelope("library.list", {"filter": "all", "limit": 50, "sort": "title"})
        packs = _envelope("pack.list", {"filter": "all", "limit": 100})

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
        "implemented_methods": list(api.implemented_methods()),
        "single_home_host": False,
    }
    rest = {"/runtime": runtime, "/workshop/catalog": catalog_fresh}
    for artifact_id, payload in covers.items():
        rest[f"/media/{artifact_id}"] = payload
    rpc = {"library.list": library_empty, "pack.list": packs}
    return {
        "catalog_fresh": catalog_fresh,
        "catalog_installed": catalog_installed,
        "library_empty": library_empty,
        "library_full": library_full,
        "rest": rest,
        "rpc": rpc,
        "rpc_full": {**rpc, "library.list": library_full},
        "media_ids": sorted(covers),
        "installs": installs,
    }


FRAMES = [
    # The storefront as a returning reader sees it: two real plates, one typographic fallback.
    {"id": "01-storefront-first-impression-light-1049", "view": "workshop", "mode": "light", "width": 1049, "height": 1560, "catalog": "catalog_installed", "rpc": "rpc_full"},
    {"id": "02-storefront-dark-1049", "view": "workshop", "mode": "dark", "width": 1049, "height": 1560, "catalog": "catalog_installed", "rpc": "rpc_full"},
    {"id": "03-storefront-light-900", "view": "workshop", "mode": "light", "width": 900, "height": 1660, "catalog": "catalog_installed", "rpc": "rpc_full"},
    {"id": "04-storefront-dark-900", "view": "workshop", "mode": "dark", "width": 900, "height": 1660, "catalog": "catalog_installed", "rpc": "rpc_full"},
    {"id": "05-storefront-light-460", "view": "workshop", "mode": "light", "width": 460, "height": 2400, "catalog": "catalog_installed", "rpc": "rpc_full"},
    {"id": "06-storefront-dark-460", "view": "workshop", "mode": "dark", "width": 460, "height": 2400, "catalog": "catalog_installed", "rpc": "rpc_full"},
    {"id": "07-storefront-200pct-460", "view": "workshop", "mode": "light", "width": 460, "height": 3600, "font": "32px", "catalog": "catalog_installed", "rpc": "rpc_full"},
    {"id": "08-storefront-reduced-motion-1049", "view": "workshop", "mode": "light", "width": 1049, "height": 1560, "motion": "reduced", "catalog": "catalog_installed", "rpc": "rpc_full"},
    # Cover detail: the plate the catalogue names, with its caption and text equivalent.
    {"id": "09-cover-detail-light-1049", "view": "detail", "pack_id": "japanese-affection-context-l0", "mode": "light", "width": 1049, "height": 1900, "catalog": "catalog_installed"},
    {"id": "10-cover-detail-dark-900", "view": "detail", "pack_id": "japanese-affection-context-l0", "mode": "dark", "width": 900, "height": 2000, "catalog": "catalog_installed"},
    {"id": "11-cover-detail-light-460", "view": "detail", "pack_id": "japanese-affection-context-l0", "mode": "light", "width": 460, "height": 2600, "catalog": "catalog_installed"},
    # Fallback: the parent pack still has no artifact, and its cover is composed type.
    {"id": "12-cover-fallback-light-1049", "view": "detail", "pack_id": "parent-measurement-practice", "mode": "light", "width": 1049, "height": 1800, "catalog": "catalog_installed"},
]


def main() -> int:
    modules = base._desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    payloads = build_payloads()
    base.build_site(modules)
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
            "catalogAfterInstall": None,
            "rest": payloads["rest"],
            "rpc": payloads[frame.get("rpc", "rpc")],
            "implemented": list(api.implemented_methods()),
            "prefs": {"favorites": [], "categories": {}},
        }
        case_file = SITE / "case.json"
        case_file.write_text(json.dumps(case), encoding="utf-8")
        env = dict(os.environ)
        env["CB196_CASE"] = str(case_file)
        import subprocess

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
                "html": base.shell_html(rendered["html"], frame.get("font")),
            }
        )
        print(f"{frame['id']}: ok", file=sys.stderr)

    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json"), "media_ids": payloads["media_ids"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
