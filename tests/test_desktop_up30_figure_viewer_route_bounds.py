"""UP-30 — the full-size figure dialog is bounded by the route, not by the window.

The learner's report: with the chat rail open on a 1344 px window the lesson route is about
640 px wide, but the dialog's scroll frame was capped at ``92vw`` / ``82vh``. Those units resolve
against the Desktop *window*, so the frame asked for ~1236 px inside a 640 px pane: the image
frame left the dialog and the dialog left the route.

This gate reads the declarations the shipped module actually emits — ``desktop/plugin.js``, the
one file the Desktop runtime loads — from a jsdom mount of ``MediaSegment`` with a stubbed route
rect, and holds them to the card's acceptance at a 640 px route inside a 1344 px window:

  * ``[data-cb-media-scroll]``'s resolved width cap is <= ``[data-cb-media-viewer]``'s width;
  * the dialog's box is the *route's* box (left/top/width/height), so the dialog cannot leave the
    pane, and the frame's cap is a percentage of that box rather than of the window;
  * no viewport-relative unit survives anywhere in the media subtree or in
    ``desktop/src/80-components.js`` — the source file the segment is built from;
  * the route box is re-read through the ``ResizeObserver`` the width hook already uses, with no
    window resize: narrowing the route to 520 px moves the dialog with it, and the figure's height
    cap follows the route's height.

Why arithmetic and not pixels: jsdom has no layout engine, so ``documentElement.scrollWidth`` is
0/0 there and asserting it would prove nothing. What this test proves is the declared geometry —
every length the media subtree emits is resolved against its containing block, and the resolved
frame cap lands inside the dialog. That is the property whose violation produced the overflow; the
page-level ``scrollWidth === clientWidth`` equality is a paint fact and belongs to the audit's
frame, not to a unit test. It is also why the fail-then-pass evidence below is computed, not
photographed: at HEAD ``92vw`` resolves to 1236.48 px inside a 608 px dialog content box.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB
from tests.test_v3_scope import layout_declarations

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
COMPONENTS_SRC = ROOT / "desktop" / "src" / "80-components.js"

WINDOW_WIDTH = 1344
WINDOW_HEIGHT = 768
ROUTE_WIDTH = 640
ROUTE_HEIGHT = 720
NARROW_ROUTE_WIDTH = 520
NARROW_ROUTE_HEIGHT = 600
REM = 16.0
VIEWER_PADDING = 1.0 * REM  # the dialog's own `padding: 1rem`

HARNESS = r"""
const payload = JSON.parse((await import('node:fs')).readFileSync(process.argv[2], 'utf8'))

const { JSDOM } = await import('jsdom')
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.KeyboardEvent = dom.window.KeyboardEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
// The host atom reports the whole window; the route is the box under test.
globalThis.__CB_TEST_WIDTH__ = String(payload.windowWidth || 1344)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

// jsdom has no ResizeObserver. Stub it *before* the plugin is imported so the component's observer
// branch is the one under test: firing this callback must re-measure with no window resize.
const observers = []
class StubResizeObserver {
  constructor(callback) { this.callback = callback; this.targets = []; observers.push(this) }
  observe(target) { this.targets.push(target) }
  unobserve(target) { this.targets = this.targets.filter((entry) => entry !== target) }
  disconnect() { this.targets = [] }
}
globalThis.ResizeObserver = StubResizeObserver

const rootNode = document.getElementById('root')
const route = document.createElement('div')
route.setAttribute('data-cb-route', '')
rootNode.appendChild(route)

let routeBox = {
  left: payload.routeLeft === undefined ? 0 : payload.routeLeft,
  top: 0,
  width: payload.routeWidth || 640,
  height: payload.routeHeight || 720
}
route.getBoundingClientRect = () => ({
  width: routeBox.width,
  height: routeBox.height,
  left: routeBox.left,
  top: routeBox.top,
  right: routeBox.left + routeBox.width,
  bottom: routeBox.top + routeBox.height,
  x: routeBox.left,
  y: routeBox.top
})

const React = (await import('react')).default
const { createRoot } = await import('react-dom/client')
const mod = await import('./plugin.js')

const IMAGE = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
const runtime = { wire_version: 6, implemented_methods: ['artifact.get'], single_home_host: false }
const fakeRest = async (path) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') return runtime
  if (base.startsWith('/media/')) {
    return { ok: true, data_url: IMAGE, mime: 'image/png', bytes: 68 }
  }
  return { ok: false, message: 'not stubbed in this harness' }
}
mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => window.setTimeout(fn, ms),
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const { act } = React
const root = createRoot(route)
const flush = async (ms = 60) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}

const segment = {
  artifact_id: 'art_0123456789abcdef',
  kind: 'visual',
  text: 'Jaws clamp the workpiece.',
  label: 'Figure',
  labels: []
}

const fire = () => {
  for (const observer of observers) {
    const targets = observer.targets.slice()
    if (targets.length) observer.callback(targets.map((target) => ({ target })), observer)
  }
}

const stylesOf = (node) => (node ? node.getAttribute('style') : null)

await act(async () => {
  root.render(React.createElement(mod.MediaSegment, { segment }))
})
await flush(90)

const facts = {}
const preview = document.querySelector('[data-cb-media-frame] img')
facts.previewStyle = stylesOf(preview)
const trigger = document.querySelector('[data-cb-media-open]')
facts.hasTrigger = Boolean(trigger)
const routeObserver = observers.find((observer) => observer.targets.includes(route))
facts.observedRoute = Boolean(routeObserver)

if (trigger) {
  await act(async () => { trigger.click() })
  await flush(40)
}

const viewer = document.querySelector('[data-cb-media-viewer]')
const frame = document.querySelector('[data-cb-media-scroll]')
const natural = document.querySelector('[data-cb-media-natural]')
facts.viewerStyle = stylesOf(viewer)
facts.frameStyle = stylesOf(frame)
facts.naturalStyle = stylesOf(natural)
facts.subtreeStyles = [...(viewer ? viewer.querySelectorAll('*') : [])].map(stylesOf).filter(Boolean)
facts.viewerPresent = Boolean(viewer)
facts.framePresent = Boolean(frame)
facts.closeFocused = Boolean(document.activeElement && document.activeElement.hasAttribute('data-cb-media-close'))

// The route narrows (the chat rail opens) with no window resize at all: only the observer can
// notice, so this probe fails if the dialog stopped reading the route's box.
routeBox = {
  left: routeBox.left,
  top: routeBox.top,
  width: payload.narrowRouteWidth || 520,
  height: payload.narrowRouteHeight || 600
}
fire()
await flush(60)
facts.afterNarrow = {
  viewerStyle: stylesOf(document.querySelector('[data-cb-media-viewer]')),
  viewerPresent: Boolean(document.querySelector('[data-cb-media-viewer]')),
  previewStyle: stylesOf(document.querySelector('[data-cb-media-frame] img'))
}

process.stdout.write(JSON.stringify(facts), () => process.exit(0))
"""


def declarations(style_attr: str | None) -> dict[str, str]:
    """The inline style as a lower-cased property -> value map, custom properties dropped."""
    kept = layout_declarations(style_attr or "")
    out: dict[str, str] = {}
    for declaration in kept.split(";"):
        if ":" not in declaration:
            continue
        name, value = declaration.split(":", 1)
        name = name.strip()
        if name:
            out[name] = value.strip()
    return out


def length(value: str, *, container: float | None = None, window: float | None = None) -> float:
    """Resolve one CSS length. Percentages need `container`; viewport units need `window`."""
    text = str(value).strip().lower()
    if text in ("", "auto", "none", "normal"):
        return 0.0
    match = re.fullmatch(r"(-?[0-9.]+)\s*(px|%|rem|vw|vh|em)", text)
    if not match:
        raise AssertionError(f"unresolved length {value!r}")
    amount = float(match.group(1))
    unit = match.group(2)
    if unit == "px":
        return amount
    if unit == "rem":
        return amount * REM
    if unit == "em":
        return amount * REM
    if unit == "%":
        if container is None:
            raise AssertionError(f"{value!r} needs a containing-block width")
        return container * amount / 100.0
    if unit == "vw":
        if window is None:
            raise AssertionError(f"{value!r} is a window-relative unit with no window")
        return window * amount / 100.0
    if unit == "vh":
        raise AssertionError(f"{value!r} is a window-relative height: the route is the measured box")
    raise AssertionError(f"unknown unit in {value!r}")


def px(style: dict[str, str], name: str, *, container: float | None = None, window: float | None = None) -> float | None:
    if name not in style:
        return None
    return length(style[name], container=container, window=window)


class FigureViewerRouteBoundsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-up30-")
        root = Path(cls.tmp.name)
        if stage_desktop_node_modules(root) is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        write_sdk_stub(root, SDK_STUB)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        cls.root = root
        cls.facts = cls.run_harness(
            {
                "windowWidth": WINDOW_WIDTH,
                "windowHeight": WINDOW_HEIGHT,
                "routeWidth": ROUTE_WIDTH,
                "routeHeight": ROUTE_HEIGHT,
                "narrowRouteWidth": NARROW_ROUTE_WIDTH,
                "narrowRouteHeight": NARROW_ROUTE_HEIGHT,
            }
        )

    @classmethod
    def run_harness(cls, payload: dict) -> dict:
        case = cls.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(case)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-3000:])
        return json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── the dialog is the route's box ──────────────────────────────────────────────────────
    def test_the_dialog_is_inset_within_the_route_box(self) -> None:
        self.assertTrue(self.facts["viewerPresent"], "the figure dialog did not open")
        self.assertTrue(self.facts["observedRoute"], "the route box was never observed")
        viewer = declarations(self.facts["viewerStyle"])
        self.assertEqual(viewer.get("position"), "fixed")
        self.assertNotIn(
            "inset",
            viewer,
            "a window-anchored inset leaves the dialog covering the window, not the route",
        )
        self.assertEqual(px(viewer, "width"), ROUTE_WIDTH, "the dialog must take the route's width")
        self.assertEqual(px(viewer, "height"), ROUTE_HEIGHT, "the dialog must take the route's height")
        self.assertEqual(px(viewer, "left"), 0.0)
        self.assertEqual(px(viewer, "top"), 0.0)
        self.assertEqual(
            viewer.get("overflow"),
            "hidden",
            "the dialog must clip its own column instead of spilling out of the route",
        )

    def test_the_scroll_frame_is_bounded_by_the_dialog(self) -> None:
        self.assertTrue(self.facts["framePresent"], "the dialog has no scroll frame")
        frame = declarations(self.facts["frameStyle"])
        dialog_width = ROUTE_WIDTH
        content_width = dialog_width - 2 * VIEWER_PADDING
        cap = px(frame, "max-width", container=content_width, window=WINDOW_WIDTH)
        self.assertIsNotNone(cap, "the scroll frame has no width cap")
        assert cap is not None
        self.assertLessEqual(
            cap,
            dialog_width,
            f"the frame asks for {cap}px inside a {dialog_width}px dialog",
        )
        height_cap = frame.get("max-height")
        self.assertIsNotNone(height_cap, "the scroll frame has no height cap")
        assert height_cap is not None
        self.assertNotIn(
            "vh",
            str(height_cap),
            "a window-height cap is what pushed the frame past the route",
        )
        self.assertLessEqual(
            length(height_cap, container=ROUTE_HEIGHT - 2 * VIEWER_PADDING),
            ROUTE_HEIGHT,
        )

    def test_the_dialog_follows_a_route_change_with_no_window_resize(self) -> None:
        after = declarations(self.facts["afterNarrow"]["viewerStyle"])
        self.assertTrue(self.facts["afterNarrow"]["viewerPresent"], "the dialog closed on re-measure")
        self.assertEqual(
            px(after, "width"),
            NARROW_ROUTE_WIDTH,
            "a narrower route must re-measure the dialog through its ResizeObserver alone",
        )
        self.assertEqual(px(after, "height"), NARROW_ROUTE_HEIGHT)

    # ── the figure's height share is the route's, not the window's ────────────────────────
    def test_the_figure_cap_is_a_share_of_the_route_height(self) -> None:
        preview = declarations(self.facts["previewStyle"])
        cap = px(preview, "max-height", container=ROUTE_HEIGHT)
        self.assertIsNotNone(cap, "the preview figure has no height cap")
        assert cap is not None
        self.assertEqual(
            cap,
            round(ROUTE_HEIGHT * 0.7),
            "the figure's cap must be 70% of the route's measured height",
        )
        after = declarations(self.facts["afterNarrow"]["previewStyle"])
        after_cap = px(after, "max-height", container=NARROW_ROUTE_HEIGHT)
        self.assertEqual(
            after_cap,
            round(NARROW_ROUTE_HEIGHT * 0.7),
            "the figure's cap must follow the route's height, not the window's",
        )

    # ── no viewport-relative unit is left behind ──────────────────────────────────────────
    def test_no_viewport_unit_survives_in_the_media_subtree(self) -> None:
        styles = [self.facts["viewerStyle"], self.facts["frameStyle"], self.facts["naturalStyle"]]
        styles.extend(self.facts["subtreeStyles"])
        offending = [
            style
            for style in styles
            if style and re.search(r"[0-9a-z.]\s*vw\b|[0-9a-z.]\s*vh\b", layout_declarations(style))
        ]
        self.assertEqual(offending, [], f"the media subtree still sizes itself against the window: {offending}")

    def test_no_viewport_unit_remains_in_the_component_source(self) -> None:
        source = COMPONENTS_SRC.read_text(encoding="utf-8")
        hits = [
            (number, line.strip())
            for number, line in enumerate(source.splitlines(), 1)
            if re.search(r"[0-9a-z.]vw\b|[0-9a-z.]vh\b", line)
        ]
        self.assertEqual(hits, [], f"desktop/src/80-components.js still carries viewport units: {hits}")

    def test_the_natural_image_is_still_unscaled(self) -> None:
        natural = declarations(self.facts["naturalStyle"])
        self.assertEqual(natural.get("max-width"), "none")
        self.assertEqual(natural.get("max-height"), "none")


if __name__ == "__main__":
    unittest.main()
