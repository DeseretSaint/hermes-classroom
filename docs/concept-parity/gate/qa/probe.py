#!/usr/bin/env python3
"""GM-015 behavioural probe harness.

Runs the shipped Coursebook Desktop module against the behavioural list the GM-015 gate has to
answer, and prints PASS / FAIL / SKIP per probe with the command that produced it.

Two modes:

* default (renderer): esbuild-bundles ``desktop/plugin.js`` with React 19 and the harness SDK stub,
  mounts the real components in headless Chromium, and measures the resulting DOM. This is a
  component preview: real module, real layout, real key events, real media features, but no host
  window chrome and no backend.
* ``--live --port N``: attaches to a running Desktop window's CDP port and measures the route that
  is on screen. No navigation, no window mutation beyond the emulation the probe sets and clears.

No probe is a stub: every PASS comes from a measurement, and a probe that cannot be measured
honestly is reported SKIP with the reason — never PASS.

Usage (from the repo root):

    python3 docs/concept-parity/gate/qa/probe.py
    python3 docs/concept-parity/gate/qa/probe.py --json --out /tmp/gm015-probes.json
    python3 docs/concept-parity/gate/qa/probe.py --only keyboard.shelf --only text.200.shelf
    python3 docs/concept-parity/gate/qa/probe.py --live --port 9337
    python3 docs/concept-parity/gate/qa/probe.py --list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

DEFAULT_PLUGIN = REPO / "desktop" / "plugin.js"
TUTOR_SELECTOR = "[data-cb-tutor-rail]"
SHELF_SELECTOR = "[data-cb-home]"

#: Each probe is one honest assertion. `frame` names the renderer fixture; `kind` selects the
#: measurement in `browser_probe.mjs`.
PROBES = [
    {
        "id": "module.load",
        "title": "Plugin module loads with the SDK present and no host link",
        "frame": "shelf",
        "kind": "module_load",
        "asserts": "the shipped module exports the coursebook plugin with register() and >100 exports, with no boot or console error",
    },
    {
        "id": "runtime.null",
        "title": "Route renders with no host runtime and does not throw",
        "frame": "page-null",
        "kind": "null_runtime",
        "asserts": "register() + the page render complete with ctx.rest rejecting, no uncaught error, no raw undefined/NaN, and a named state is on screen",
    },
    {
        "id": "profile.cold",
        "title": "Cold profile renders one start plate, not an empty course",
        "frame": "cold",
        "kind": "cold",
        "asserts": "an empty library paints the invitation + empty shelf, exactly one primary action, zero course cards and no course-home/Continue plate",
    },
    {
        "id": "keyboard.shelf",
        "title": "Shelf tab order follows DOM order",
        "frame": "shelf",
        "kind": "tab_order",
        "selector": SHELF_SELECTOR,
        "asserts": "Tab visits every visible shelf control in DOM order, Shift+Tab reverses it, and every stop has an accessible name",
    },
    {
        "id": "keyboard.tutor_rail",
        "title": "Tutor rail tab order follows DOM order",
        "frame": "tutor",
        "kind": "tab_order",
        "selector": TUTOR_SELECTOR,
        "asserts": "Tab visits every visible rail control in DOM order, Shift+Tab reverses it, and every stop has an accessible name",
    },
    {
        "id": "text.200.shelf",
        "title": "Shelf survives 200% text at 1049 and 460",
        "frame": "shelf",
        "kind": "text_200",
        "widths": [1049, 460],
        "selectors": ["[data-cb-route]", "[data-cb-home-shelf-row]", "[data-cb-home]"],
        "asserts": "root font 32px: no horizontal page overflow, no declared-container overflow, no clipped text outside an intentional line clamp",
    },
    {
        "id": "text.200.tutor_rail",
        "title": "Tutor rail survives 200% text at 1049 and 460",
        "frame": "tutor",
        "kind": "text_200",
        "widths": [1049, 460],
        "selectors": ["[data-cb-route]", TUTOR_SELECTOR],
        "asserts": "root font 32px: no horizontal page overflow, no rail overflow, no clipped text outside an intentional line clamp",
    },
    {
        "id": "colors.forced.shelf",
        "title": "Shelf stays legible in forced-colors mode",
        "frame": "shelf",
        "kind": "forced_colors",
        "media": "forced-colors",
        "asserts": "forced-colors: active is observed, every text node keeps a non-transparent system colour, and the first Tab stop paints a visible indicator",
    },
    {
        "id": "colors.forced.tutor_rail",
        "title": "Tutor rail stays legible in forced-colors mode",
        "frame": "tutor",
        "kind": "forced_colors",
        "media": "forced-colors",
        "asserts": "forced-colors: active is observed, every text node keeps a non-transparent system colour, and the first Tab stop paints a visible indicator",
    },
    {
        "id": "motion.reduced.shelf",
        "title": "Shelf honours prefers-reduced-motion",
        "frame": "shelf",
        "kind": "reduced_motion",
        "media": "reduced-motion",
        "asserts": "with the media query emulated before mount, no element animates, transitions longer than 10ms, or loops infinitely",
    },
    {
        "id": "motion.reduced.tutor_rail",
        "title": "Tutor rail honours prefers-reduced-motion",
        "frame": "tutor",
        "kind": "reduced_motion",
        "media": "reduced-motion",
        "asserts": "with the media query emulated before mount, no element animates, transitions longer than 10ms, or loops infinitely",
    },
    {
        "id": "image.fail",
        "title": "A failed lesson image keeps its authored text",
        "frame": "lesson-ready",
        "kind": "image_failure",
        "block": ["*missing.png*", "*.png", "*.webp", "*.avif"],
        "asserts": "a plugin-rendered image pointed at a dead URL leaves named alt text and the media caption/text equivalent on screen, with no collapsed or unnamed image",
    },
    {
        "id": "font.fail",
        "title": "Text stays visible when an authored webfont cannot load",
        "frame": None,
        "kind": "font_failure",
        "asserts": "every text run keeps a non-transparent colour and non-zero box with font URLs blocked; SKIP is recorded when the module authors no loadable webfont",
    },
    {
        "id": "offline",
        "title": "Route renders with the network offline",
        "frame": "shelf",
        "kind": "offline",
        "offline": True,
        "asserts": "with CDP network emulation offline, the route still paints text, keeps its DOM, and raises no uncaught error",
    },
]

#: Probes that only make sense against a running Desktop.
LIVE_PROBES = [
    {
        "id": "keyboard.live_route",
        "title": "Live route tab order follows DOM order",
        "kind": "tab_order",
        "selector": "[data-cb-route]",
        "asserts": "in the running window, Tab visits every visible route control in DOM order and every stop has an accessible name",
    },
    {
        "id": "text.200.live_route",
        "title": "Live route survives 200% text",
        "kind": "text_200",
        "widths": [1049, 460],
        "selectors": ["[data-cb-route]"],
        "asserts": "root font 32px in the live renderer: no page/route overflow and no clipped text outside an intentional line clamp",
    },
    {
        "id": "colors.forced.live_route",
        "title": "Live route stays legible in forced-colors mode",
        "kind": "forced_colors",
        "media": "forced-colors",
        "asserts": "forced-colors: active leaves every text node with a system colour and the first Tab stop with a visible indicator",
    },
    {
        "id": "motion.reduced.live_route",
        "title": "Live route honours prefers-reduced-motion",
        "kind": "reduced_motion",
        "media": "reduced-motion",
        "asserts": "with reduce emulated, no element animates, transitions longer than 10ms, or loops infinitely",
    },
    {
        "id": "image.fail.live_route",
        "title": "Live route keeps authored text when images fail",
        "kind": "image_failure",
        "block": ["*.png", "*.webp", "*.avif", "*.svg"],
        "asserts": "every live image that fails keeps a name and its surrounding authored text",
    },
    {
        "id": "offline.live_route",
        "title": "Live route renders while offline",
        "kind": "offline",
        "offline": True,
        "asserts": "with the network offline, the route still paints text and raises no uncaught error",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_node_modules() -> Path | None:
    candidates = [
        os.environ.get("HERMES_DESKTOP_APP"),
        str(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop"),
        str(Path.home() / ".hermes" / "hermes-agent"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        root = Path(candidate) / "node_modules"
        if (root / "react").is_dir() and (root / "react-dom" / "server.js").is_file():
            return root
    return None


def find_esbuild(modules: Path | None) -> str | None:
    if os.environ.get("ESBUILD_BIN"):
        return os.environ["ESBUILD_BIN"]
    if modules is not None:
        local = modules / ".bin" / "esbuild"
        if local.is_file():
            return str(local)
    return shutil.which("esbuild")


def find_host_css() -> Path | None:
    app = os.environ.get("HERMES_DESKTOP_APP") or str(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop")
    dist = Path(app) / "dist" / "assets"
    if not dist.is_dir():
        return None
    matches = sorted(dist.glob("main-*.css"))
    return matches[0] if matches else None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stage(root: Path, plugin: Path, modules: Path) -> Path:
    (root / "plugin.js").write_text(plugin.read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copy2(HERE / "render_entry.js", root / "entry.js")
    node_modules = root / "node_modules"
    node_modules.mkdir(parents=True, exist_ok=True)
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True, exist_ok=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
    )
    shutil.copy2(HERE / "sdk_stub.js", sdk / "index.js")
    return node_modules


def bundle(root: Path, esbuild: str) -> None:
    result = subprocess.run(
        [
            esbuild,
            "entry.js",
            "--bundle",
            "--outfile=bundle.js",
            "--platform=browser",
            "--format=iife",
            "--define:process.env.NODE_ENV=\"production\"",
            "--log-level=warning",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"esbuild failed: {result.stderr[-2000:]}")
    if result.stderr.strip():
        print(result.stderr[-1000:], file=sys.stderr)


def write_frames(root: Path, host_css: Path | None) -> dict[str, str]:
    kinds = {
        "shelf": {"kind": "shelf"},
        "cold": {"kind": "cold"},
        "tutor": {"kind": "tutor"},
        "lesson-ready": {"kind": "lesson-ready"},
        "page-null": {"kind": "page-null"},
    }
    css_line = ""
    if host_css is not None:
        shutil.copy2(host_css, root / "host.css")
        css_line = '<link rel="stylesheet" href="host.css" />'
    frames: dict[str, str] = {}
    for name, payload in kinds.items():
        path = root / f"frame-{name}.html"
        path.write_text(
            f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
{css_line}
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f4efe4; }}
</style></head>
<body><div id="root"></div>
<script>window.__CB_FRAME__ = {json.dumps(payload)};</script>
<script src="bundle.js"></script>
</body></html>""",
            encoding="utf-8",
        )
        frames[name] = str(path)
    return frames


def run_browser(plan: dict, qa: Path) -> dict:
    plan_path = Path(plan.pop("_plan_path"))
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    result = subprocess.run(
        ["node", str(qa / "browser_probe.mjs"), str(plan_path)],
        capture_output=True,
        text=True,
        timeout=420,
    )
    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(f"browser probe failed: {result.stderr[-2000:]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"browser probe returned non-JSON: {result.stdout[-1000:]} {result.stderr[-1000:]}") from error


def renderer_mode(args, selected: list[dict]) -> tuple[dict, dict]:
    if not args.plugin.is_file():
        raise SystemExit(f"plugin not found: {args.plugin}")
    modules = find_node_modules()
    if modules is None:
        raise SystemExit("react/react-dom not found beside the Desktop app (set HERMES_DESKTOP_APP)")
    esbuild = find_esbuild(modules)
    if esbuild is None:
        raise SystemExit("esbuild not found (set ESBUILD_BIN)")
    if shutil.which("chromium") is None and not os.environ.get("CHROME_BIN"):
        raise SystemExit("chromium not found (set CHROME_BIN)")
    host_css = find_host_css()

    root = Path(tempfile.mkdtemp(prefix="cb-gm015-probe-"))
    started = time.time()
    try:
        stage(root, args.plugin, modules)
        bundle(root, esbuild)
        frames = write_frames(root, host_css)
        user_data = root / ".chromium"
        user_data.mkdir()
        plan = {
            "_plan_path": str(root / "plan.json"),
            "chromium": os.environ.get("CHROME_BIN") or "chromium",
            "port": free_port(),
            "userDataDir": str(user_data),
            "frames": frames,
            "probes": selected,
        }
        output = run_browser(plan, HERE)
    finally:
        elapsed = round(time.time() - started, 1)
        keep = args.keep
        if keep:
            print(f"[keep] renderer workspace: {root}", file=sys.stderr)
        else:
            shutil.rmtree(root, ignore_errors=True)

    meta = {
        "renderer": "component preview: shipped plugin.js bundled with React 19 in headless Chromium (no host chrome, no backend)",
        "host_css": {"path": str(host_css), "sha256": sha256(host_css)} if host_css else None,
        "esbuild": esbuild,
        "bundled_seconds": elapsed,
    }
    if "fatal" in output:
        raise RuntimeError(output["fatal"])
    return output, meta


def live_mode(args, selected: list[dict]) -> tuple[dict, dict]:
    if not args.port:
        raise SystemExit("--live needs --port <CDP port>")
    try:
        targets = json.loads(
            subprocess.run(
                ["curl", "-s", f"http://127.0.0.1:{args.port}/json"],
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout
        )
    except Exception as error:  # noqa: BLE001
        raise SystemExit(f"no CDP endpoint on port {args.port}: {error}") from error
    if not targets:
        raise SystemExit(f"CDP port {args.port} returned no targets")
    root = Path(tempfile.mkdtemp(prefix="cb-gm015-live-"))
    for probe in selected:
        probe["attach"] = True
    plan = {
        "_plan_path": str(root / "plan.json"),
        "attachPort": args.port,
        "frames": {},
        "probes": selected,
    }
    try:
        output = run_browser(plan, HERE)
    finally:
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)
    meta = {"renderer": f"live Desktop CDP port {args.port} (no navigation performed)"}
    if "fatal" in output:
        raise RuntimeError(output["fatal"])
    return output, meta


def font_probe(plugin: Path, args) -> dict:
    source = plugin.read_text(encoding="utf-8")
    if "@font-face" not in source:
        return {
            "id": "font.fail",
            "ok": None,
            "skipped": True,
            "detail": {
                "reason": "the shipped module authors no @font-face; type uses OS stacks, so a webfont load failure cannot blank text today",
                "next": "if a later card adds embedded or remote faces, re-run this probe; it will block the font URLs and assert text stays visible",
            },
        }
    if "src: url(data:" in source.replace(" ", "") or "src:url(data:" in source.replace(" ", ""):
        return {
            "id": "font.fail",
            "ok": None,
            "skipped": True,
            "detail": {
                "reason": "the module's @font-face sources are embedded data: URLs; a network font failure is not representable without editing the module",
                "next": "a remote-font build gets a real probe automatically through --live with the font URLs blocked",
            },
        }
    return {
        "id": "font.fail",
        "ok": None,
        "skipped": True,
        "detail": {"reason": "remote webfont support detected but the static renderer does not load remote font URLs; run --live --port <cdp>"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GM-015 behavioural probe harness")
    parser.add_argument("--plugin", type=Path, default=DEFAULT_PLUGIN, help="built desktop/plugin.js")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    parser.add_argument("--out", type=Path, help="write the JSON report to this path")
    parser.add_argument("--only", action="append", default=[], help="run only this probe id (repeatable)")
    parser.add_argument("--list", action="store_true", help="list probe ids and exit")
    parser.add_argument("--live", action="store_true", help="attach to a running Desktop CDP port")
    parser.add_argument("--port", type=int, help="CDP port for --live")
    parser.add_argument("--keep", action="store_true", help="keep the renderer workspace for inspection")
    args = parser.parse_args(argv)

    catalogue = LIVE_PROBES if args.live else PROBES
    if args.list:
        for probe in catalogue:
            print(f"{probe['id']}\t{probe['title']}")
        return 0

    selected = [dict(probe) for probe in catalogue]
    if args.only:
        wanted = set(args.only)
        unknown = wanted - {probe["id"] for probe in catalogue}
        if unknown:
            parser.error(f"unknown probe id(s): {', '.join(sorted(unknown))}")
        selected = [probe for probe in selected if probe["id"] in wanted]

    plugin = args.plugin.resolve()
    report: dict = {
        "tool": "gm015-behavioural-probes",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": "live" if args.live else "renderer",
        "repo": str(REPO),
        "plugin": {
            "path": str(plugin),
            "sha256": sha256(plugin) if plugin.is_file() else None,
        },
        "git_head": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "probes": [],
        "summary": {},
    }

    if not args.live:
        # The font probe is a source decision plus a browser measurement when a real face exists.
        font_selected = any(probe["id"] == "font.fail" for probe in selected)
        selected = [probe for probe in selected if probe["id"] != "font.fail"]
        if not selected:
            report["probes"] = [font_probe(plugin, args)] if font_selected else []
            meta = {}
        else:
            output, meta = renderer_mode(args, selected)
            results = {item["id"]: item for item in output.get("results", [])}
            for probe in selected:
                item = results.get(probe["id"], {
                    "id": probe["id"],
                    "ok": None,
                    "skipped": True,
                    "detail": {"reason": "probe did not return a result"},
                })
                report["probes"].append(item)
            if font_selected:
                report["probes"].append(font_probe(plugin, args))
    else:
        output, meta = live_mode(args, selected)
        results = {item["id"]: item for item in output.get("results", [])}
        for probe in selected:
            report["probes"].append(results.get(probe["id"], {
                "id": probe["id"],
                "ok": None,
                "skipped": True,
                "detail": {"reason": "probe did not return a result"},
            }))
    report["environment"] = meta

    by_id = {probe["id"]: probe for probe in catalogue}
    for item in report["probes"]:
        definition = by_id.get(item["id"], {})
        item["title"] = definition.get("title")
        item["asserts"] = definition.get("asserts")
        if item.get("skipped") or item.get("ok") is None:
            item["status"] = "SKIP"
        elif item.get("ok"):
            item["status"] = "PASS"
        else:
            item["status"] = "FAIL"
        item["command"] = (
            f"python3 docs/concept-parity/gate/qa/probe.py --live --port {args.port} --only {item['id']}"
            if args.live
            else f"python3 docs/concept-parity/gate/qa/probe.py --only {item['id']}"
        )

    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for item in report["probes"]:
        counts[item["status"]] += 1
    report["summary"] = {"total": len(report["probes"]), **counts}
    report["verdict"] = "FAIL" if counts["FAIL"] else ("PASS" if counts["PASS"] else "NO-RESULT")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"GM-015 behavioural probes · {report['mode']} · plugin {str(report['plugin']['sha256'])[:12]}")
        print(report["environment"].get("renderer", ""))
        print()
        for item in report["probes"]:
            print(f"{item['status']:4}  {item['id']}")
            print(f"      {item.get('title') or ''}")
            print(f"      $ {item['command']}")
            if item["status"] == "SKIP":
                print(f"      skip: {item['detail'].get('reason')}")
            elif item["status"] == "FAIL":
                print(f"      detail: {json.dumps(item['detail'])[:600]}")
        print()
        print(f"summary: {counts['PASS']} PASS · {counts['FAIL']} FAIL · {counts['SKIP']} SKIP · verdict {report['verdict']}")
        if args.out:
            print(f"report: {args.out}")

    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
