"""CP-020a — the v3 style scope: one route ground, byte-real tokens, embedded type, materials.

The card's contract, in executable form:

* ``[data-cb-v3]`` is the route root, exactly once, and it is the same element as
  ``[data-cb-route]`` — a second nested container would make ``cqi`` resolve against the wrong box;
* ``CB_TOKENS_V3_JSON`` carries ``contracts/cb.tokens.v3.json`` (the five build-critical sections)
  in canonical bytes, so no surface can paint a value the contract did not define;
* the one ``<style>`` element inside the route carries ``CB_V3_CSS`` plus the ``@font-face`` rules
  composed from ``CB_ASSETS.fonts`` data URLs, with ``font-display: swap``;
* grain and vignette are ``aria-hidden``, ``pointer-events: none`` layers, and a forced-colors reader
  loses the paint but keeps the DOM;
* ``data-cb-v3-ready`` appears only after ``document.fonts.ready`` and the texture decode settle —
  never on the first synchronous paint, and never blocked forever by a texture that never loads.

What this does NOT prove: that contrast holds on real pixels, that the ground reads well, or that a
browser paints the tiles. Those are ``scripts/cp-capture.mjs`` frames and the reviewer's rubric.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import subprocess
import unittest
from pathlib import Path

from tests.cb_source_scope import (
    PLUGIN_JS,
    ROOT,
    V3_CSS_CONST,
    V3_TOKEN_CONST,
    css_blocks,
    declarations,
    literal_text,
    style_rules,
)
from tests.test_desktop_lesson_views import _desktop_node_modules, SDK_STUB

CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
V3_SECTIONS = ("modes", "elevation", "radii", "type", "motion")

HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/', pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

// A controllable `document.fonts.ready`: the test decides when the face settles, so "waits for
// fonts" is observed rather than assumed. jsdom has no FontFaceSet.
let settleFonts = () => {}
const fontsReady = new Promise((resolve) => { settleFonts = resolve })
Object.defineProperty(document, 'fonts', {
  configurable: true,
  value: { ready: fontsReady, status: 'loading', add() {}, delete() {}, has() { return false } }
})

const mod = await import('./plugin.js')
const calls = []
const responses = payload.responses || {}
const generic = { items: [], entries: [], objectives: [], total: 0 }
const runtime = {
  wire_version: 6,
  implemented_methods: ['library.list', 'course.outline', 'review.queue', 'notebook.list', 'quiz.history',
    'evidence.inspect', 'lesson.page', 'binding.get', 'pack.inspect', 'parent.brief.get',
    'parent.brief.list', 'course.export.read', 'course.create', 'pack.import'],
  single_home_host: false
}
const fakeRest = async (path, options) => {
  const method = options && options.body && options.body.method
  calls.push({ path: String(path), method })
  const base = String(path).split('?')[0]
  if (base === '/rpc') {
    const result = Object.prototype.hasOwnProperty.call(responses, method) ? responses[method] : generic
    return { ok: true, contract_version: 6, operation_id: 'test', result }
  }
  if (base === '/runtime') return runtime
  if (base === '/health') return { ok: true, contract_version: 6, result: { db: { ready: true }, plugin_version: 'test', contract_version: 6 } }
  return { ok: true, result: {} }
}
const contributions = []
mod.default.register({
  rest: fakeRest,
  register: (entry) => contributions.push(entry),
  onDispose: () => {},
  setTimeout: (fn, ms) => { const handle = window.setTimeout(fn, ms); return () => window.clearTimeout(handle) },
  clearTimeout: (handle) => window.clearTimeout(handle)
})
const route = contributions.find((entry) => entry.area === 'routes')
if (!route) throw new Error('the plugin registered no route')

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 40) => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }

await act(async () => { root.render(route.render()) })
await flush(60)

const routeNode = document.querySelector('[data-cb-route]')
const v3Nodes = [...document.querySelectorAll('[data-cb-v3]')]
const styleNodes = [...document.querySelectorAll('[data-cb-v3] style')]
const material = [...document.querySelectorAll('[data-cb-v3] .cb3-material')]
const grain = document.querySelector('[data-cb-v3] .cb3-material-grain')
const vignette = document.querySelector('[data-cb-v3] .cb3-material-vignette')
const styleText = styleNodes.map((node) => node.textContent || '').join('\n')
const readyBefore = routeNode ? routeNode.hasAttribute('data-cb-v3-ready') : null
const computed = routeNode ? window.getComputedStyle(routeNode) : null

settleFonts()
await flush(1200)
const readyAfter = routeNode ? routeNode.hasAttribute('data-cb-v3-ready') : null

process.stdout.write(JSON.stringify({
  routeExists: Boolean(routeNode),
  v3Count: v3Nodes.length,
  v3IsRoute: v3Nodes.length === 1 && v3Nodes[0] === routeNode,
  styleCount: styleNodes.length,
  styleText,
  containerType: computed ? (computed.containerType || computed.getPropertyValue('container-type')) : null,
  containerName: computed ? (computed.containerName || computed.getPropertyValue('container-name')) : null,
  v3Vars: routeNode ? {
    canvas: routeNode.style.getPropertyValue('--cb3-canvas'),
    ink: routeNode.style.getPropertyValue('--cb3-ink'),
    elev: routeNode.style.getPropertyValue('--cb3-elev-1'),
    radius: routeNode.style.getPropertyValue('--cb3-radius-round'),
    fontDisplay: routeNode.style.getPropertyValue('--cb3-font-display')
  } : null,
  materialCount: material.length,
  materialAriaHidden: material.every((node) => node.getAttribute('aria-hidden') === 'true'),
  materialPointerEvents: material.every((node) => node.style.pointerEvents === 'none'),
  grainPresent: Boolean(grain),
  vignettePresent: Boolean(vignette),
  readyBefore,
  readyAfter,
  routeText: routeNode ? routeNode.textContent.slice(0, 120) : null
}))
"""

ROUTE_RESPONSES = {
    "library.list": {"items": [], "total": 0, "applied_filter": "all"},
    "review.queue": {"items": [], "total_overdue": 0},
    "notebook.list": {"entries": []},
    "quiz.history": {"items": []},
    "evidence.inspect": {"items": []},
    "parent.brief.list": {"items": []},
}


def contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class V3ScopeSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_v3_tokens_match_contract(self) -> None:
        raw = literal_text(self.source, V3_TOKEN_CONST)
        self.assertIsNotNone(raw, f"{V3_TOKEN_CONST} is missing: the route has no v3 tokens")
        assert raw is not None
        tokens = json.loads(raw)
        self.contract = contract()
        for key in V3_SECTIONS:
            self.assertIn(key, tokens, f"{V3_TOKEN_CONST} does not carry {key!r}")
            self.assertEqual(tokens[key], self.contract[key], f"{key} drifted from the contract")
        self.assertEqual(set(tokens), set(V3_SECTIONS),
                         "the literal carries only the five build-critical sections")
        self.assertEqual(raw, canonical({key: self.contract[key] for key in tokens}),
                         "the literal is not the contract's canonical bytes")

    def test_v3_textures_hidden_in_forced_colors(self) -> None:
        css = literal_text(self.source, V3_CSS_CONST)
        self.assertIsNotNone(css, f"{V3_CSS_CONST} is missing")
        assert css is not None
        blocks = css_blocks(css)
        forced = [(prelude, body) for prelude, body in blocks
                  if prelude.startswith("@media") and "forced-colors" in prelude.lower()]
        self.assertTrue(forced, "no @media (forced-colors: active) block in the v3 stylesheet")
        hidden = []
        for _, body in forced:
            for prelude, inner in css_blocks(body):
                if prelude.startswith("@"):
                    continue
                props = dict(declarations(inner))
                if "material" in prelude and props.get("display") == "none":
                    hidden.append(prelude)
        self.assertTrue(hidden, "forced colors keeps the grain/vignette layers painted")

    def test_ready_marker_is_not_a_first_paint_attribute(self) -> None:
        # The ready attribute is written by the settle effect, not by the JSX. A literal
        # `"data-cb-v3-ready": ""` on the route would let a capture stamp succeed before the
        # fonts settle and would make the flag meaningless.
        route = self.source[self.source.index("'data-cb-route': ROUTE_PATH"):]
        route = route[: route.index("PageBody")]
        self.assertNotIn("data-cb-v3-ready", route,
                         "the route root ships data-cb-v3-ready on its first paint")
        self.assertIn("data-cb-v3-ready", self.source)
        self.assertIn("document.fonts.ready", self.source)

    def test_materials_are_aria_hidden_and_pointer_transparent(self) -> None:
        for needle in ("cb3-material-grain", "cb3-material-vignette"):
            self.assertIn(needle, self.source, f"{needle} layer is not rendered")
        self.assertIn("aria-hidden: 'true'", self.source)


class V3ScopeRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-v3scope-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
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
        case = root / "case.json"
        case.write_text(json.dumps({"width": 1049, "responses": ROUTE_RESPONSES}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(root / "harness.mjs"), str(case)],
            cwd=root, capture_output=True, text=True, timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-6000:])
        cls.report = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_v3_scope_wraps_route_once(self) -> None:
        self.assertTrue(self.report["routeExists"])
        self.assertEqual(self.report["v3Count"], 1, "a second [data-cb-v3] container splits the route")
        self.assertTrue(self.report["v3IsRoute"], "[data-cb-v3] is not the [data-cb-route] root")
        self.assertEqual(self.report["styleCount"], 1, "the route must carry exactly one v3 <style>")
        self.assertIn("[data-cb-v3]", self.report["styleText"])
        self.assertEqual((self.report["containerType"] or "").strip(), "inline-size")
        self.assertEqual((self.report["containerName"] or "").strip(), "cb")
        self.assertIn("[data-cb-v3]", self.report["styleText"])

    def test_v3_tokens_reach_the_route(self) -> None:
        contract_light = contract()["modes"]["light"]
        variables = self.report["v3Vars"]
        assert variables is not None
        self.assertEqual(variables["canvas"], contract_light["canvas"])
        self.assertEqual(variables["ink"], contract_light["ink"])
        self.assertTrue(variables["elev"])
        self.assertEqual(variables["radius"], "12px")

    def test_v3_fonts_embedded_from_assets(self) -> None:
        css = self.report["styleText"]
        self.assertIn("@font-face", css)
        families = [value for prelude, body in css_blocks(css) if prelude.startswith("@font-face")
                    for prop, value in declarations(body) if prop == "font-family"]
        self.assertEqual(len(families), 2, families)
        self.assertEqual({value.strip().strip("'\"") for value in families}, {"CB Display", "CB UI"})
        self.assertIn("font-display: swap", css)
        self.assertIn("data:font/woff2;base64,", css)
        self.assertGreaterEqual(css.count("@font-face"), 2)

    def test_texture_layers_are_hidden_from_assistive_tech(self) -> None:
        self.assertGreaterEqual(self.report["materialCount"], 2)
        self.assertTrue(self.report["materialAriaHidden"], "a material layer is announced")
        self.assertTrue(self.report["materialPointerEvents"], "a material layer can intercept a click")
        self.assertTrue(self.report["grainPresent"])
        self.assertTrue(self.report["vignettePresent"])

    def test_v3_ready_marker_waits_for_fonts(self) -> None:
        self.assertFalse(self.report["readyBefore"],
                         "data-cb-v3-ready is painted before document.fonts.ready settles")
        self.assertTrue(self.report["readyAfter"],
                        "data-cb-v3-ready never appears after fonts and textures settle")
        self.assertTrue((self.report["routeText"] or "").strip(),
                        "the route painted no DOM text while the v3 ground was loading")


if __name__ == "__main__":
    unittest.main()
