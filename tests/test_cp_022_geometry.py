"""CP-022 — the shelf's real geometry and the mask re-measure.

The round-1 review found the shelf sized cards from the whole route while the fox shared their
flex row, so at route 900 one 868 px card was clipped and at 1049 the fourth card was cut with no
affordance. Counting DOM nodes cannot catch that; these tests measure the painted boxes.

Three layers, each with a distinct oracle:

  * `test_home_v3_shelf_fits_its_route` — renderer arithmetic at 1049 / 900 / 460: the cards plus
    gaps are never wider than the copy rule the shipped `.cb3-gutter` draws;
  * `test_home_v3_shelf_cards_sit_inside_the_row` — the shipped markup painted in Chromium at those
    widths: every `[data-cb-home-card]` border box lies inside `[data-cb-home-shelf-row]`'s clip
    box, and 4 / 3 / 1 full cards show;
  * `test_home_v3_mask_remeasures_on_a_route_change` — a jsdom mount with a stubbed
    `ResizeObserver` and stubbed row geometry: firing the observer callback (with no window resize)
    must re-measure the edge mask, and the route-width path is covered as a second assertion.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

RENDER = r"""
globalThis.__CB_TEST_WIDTH__ = process.env.CB_TEST_WIDTH || '1049'
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const payload = JSON.parse(process.env.CB_TEST_PAYLOAD)
const lib = (rows) => ({
  items: rows,
  next_cursor: null,
  total: rows.length,
  empty_reason: rows.length ? null : 'no_courses',
  applied_filter: 'all'
})
const html = renderToStaticMarkup(
  React.createElement('div', {
    'data-cb-route': '/coursebook',
    style: { padding: '0', width: '100%', display: 'block' }
  },
    React.createElement(mod.CoursebookHome, {
      library: { status: payload.status || 'ready', data: lib(payload.rows || []), error: null, stale: false },
      modes: {},
      modesSupported: true,
      online: true,
      canCreate: true,
      onStartCreate: () => {},
      onBrowseLibrary: () => {},
      onOpenCourse: () => {},
      onShowAll: () => {},
      onOpenStudio: () => {},
      onRetry: () => {}
    })
  )
)
process.stdout.write(JSON.stringify({ html }))
"""

MEASURE = r"""
import { spawn } from 'node:child_process'

const [htmlPath, widthsJson, userDataDir] = process.argv.slice(2)
const widths = JSON.parse(widthsJson)
const port = 9400 + (process.pid % 400)
const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${port}`, `--user-data-dir=${userDataDir}`, 'about:blank'
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
let targets = null
for (let attempt = 0; attempt < 80; attempt += 1) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
    if (targets.length) break
  } catch (error) { targets = null }
  await sleep(250)
}
if (!targets || !targets.length) { chromium.kill(); throw new Error('chromium CDP did not open') }
const page = targets.find((entry) => entry.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const entry = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) entry.fail(new Error(JSON.stringify(message.error)))
    else entry.done(message.result)
  }
})
const send = (method, params = {}) => new Promise((done, fail) => {
  const id = nextId++
  pending.set(id, { done, fail })
  socket.send(JSON.stringify({ id, method, params }))
})
await send('Page.enable')
const expression = `(() => {
  const row = document.querySelector('[data-cb-home-shelf-row]')
  if (!row) return { missing: true }
  const box = row.getBoundingClientRect()
  const cards = [...document.querySelectorAll('[data-cb-home-card]')].map((card) => {
    const rect = card.getBoundingClientRect()
    return {
      left: rect.left, right: rect.right, width: rect.width,
      basis: card.getAttribute('data-cb-home-card-basis')
    }
  })
  const fox = document.querySelector('[data-cb3-fox]')
  const foxRect = fox ? fox.getBoundingClientRect() : null
  const ledge = document.querySelector('[data-cb-home-ledge]')
  return {
    missing: false,
    row: {
      left: box.left, right: box.right,
      client: row.clientWidth, scroll: row.scrollWidth,
      direction: getComputedStyle(row).flexDirection,
      mask: row.getAttribute('data-cb-shelf-mask')
    },
    cards,
    foxOnShelfRow: Boolean(fox && row.contains(fox)),
    foxOnLedge: Boolean(fox && ledge && ledge.contains(fox)),
    fox: foxRect ? { left: foxRect.left, right: foxRect.right, width: foxRect.width } : null,
    hint: Boolean(document.querySelector('[data-cb-home-overflow-hint]')),
    pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
  }
})()`
const out = []
for (const width of widths) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: `file://${htmlPath}?w=${width}` })
  await sleep(450)
  const answer = await send('Runtime.evaluate', { expression, returnByValue: true })
  out.push({ width, ...answer.result.value })
}
socket.close()
chromium.kill()
process.stdout.write(JSON.stringify(out))
"""

MASK = r"""
const React = (await import('react')).default
const { createRoot } = await import('react-dom/client')
const { JSDOM } = await import('jsdom')

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

const payload = JSON.parse(process.env.CB_TEST_PAYLOAD)
const dom = new JSDOM(
  '<!doctype html><html><body><div id="root"><div data-cb-route></div></div></body></html>',
  { pretendToBeVisual: true, url: 'http://localhost/' }
)
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
globalThis.HTMLElement = dom.window.HTMLElement

const route = document.querySelector('[data-cb-route]')
let routeWidth = 1049
route.getBoundingClientRect = () => ({
  width: routeWidth, height: 800, top: 0, left: 0, right: routeWidth, bottom: 800, x: 0, y: 0
})

const mod = await import('./plugin.js')
const tick = () => new Promise((done) => setTimeout(done, 30))
const lib = (rows) => ({
  items: rows, next_cursor: null, total: rows.length, empty_reason: null, applied_filter: 'all'
})
const root = createRoot(document.getElementById('root'))
root.render(React.createElement(mod.CoursebookHome, {
  library: { status: 'ready', data: lib(payload.rows || []), error: null, stale: false },
  modes: {}, modesSupported: true, online: true, canCreate: true,
  onStartCreate: () => {}, onBrowseLibrary: () => {}, onOpenCourse: () => {},
  onShowAll: () => {}, onOpenStudio: () => {}, onRetry: () => {}
}))
await tick()
await tick()
const row = document.querySelector('[data-cb-home-shelf-row]')
if (!row) { process.stdout.write(JSON.stringify({ missing: true })); process.exit(0) }
let client = 985
let scroll = 984
Object.defineProperty(row, 'clientWidth', { configurable: true, get: () => client })
Object.defineProperty(row, 'scrollWidth', { configurable: true, get: () => scroll })
const before = row.getAttribute('data-cb-shelf-mask')
const observedRow = observers.some((observer) => observer.targets.includes(row))
const fire = () => {
  for (const observer of observers) {
    const targets = observer.targets.slice()
    if (targets.length) observer.callback(targets.map((target) => ({ target })), observer)
  }
}
// The row itself narrows (the chat rail opens) with no window resize event at all: only the
// observer can notice, so this probe fails if the component stops observing its shelf.
client = 700
scroll = 780
fire()
await tick()
await tick()
const afterObserver = row.getAttribute('data-cb-shelf-mask')
// Back to a fitting row: the same observer path must clear the mask.
client = 985
scroll = 984
fire()
await tick()
await tick()
const refit = row.getAttribute('data-cb-shelf-mask')
// And the route-width path stays covered as a second assertion.
client = 700
scroll = 780
routeWidth = 800
dom.window.dispatchEvent(new dom.window.Event('resize'))
await tick()
await tick()
const afterResize = row.getAttribute('data-cb-shelf-mask')
process.stdout.write(JSON.stringify({
  missing: false, before, afterObserver, refit, afterResize,
  observers: observers.length, observedRow
}))
"""

ROW_TEMPLATE = {
    "enrollment_id": "enr_{i:016x}",
    "course_id": "crs_{i:016x}",
    "title": "Course number {i}",
    "subtitle": None,
    "recipe": "committed",
    "level_label": None,
    "locale": None,
    "learner_label": None,
    "enrollment_status": "active",
    "course_status": "active",
    "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
    "next_step": {"kind": "resume_lesson", "label": "Resume this lesson"},
    "evidence_summary": {
        "independent": 1,
        "review_due": 0,
        "total_objectives": 4,
        "current_objective_id": "obj_0000000000000001",
    },
    "sections_done": 1,
    "sections_total": 4,
    "checks_recorded": 1,
    "is_new": False,
    "subject_label": "Small engines",
    "cover_artifact_id": None,
    "last_studied_at": None,
    "warning": None,
    "updated_at": "2026-11-01T09:00:00.000000+00:00",
    "revision": 1,
}


def rows(count: int) -> list[dict]:
    out = []
    for index in range(1, count + 1):
        row = json.loads(json.dumps(ROW_TEMPLATE))
        row["enrollment_id"] = f"enr_{index:016x}"
        row["course_id"] = f"crs_{index:016x}"
        row["title"] = f"Course number {index}"
        out.append(row)
    return out


class GeometryBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp022-geometry-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "render.mjs").write_text(RENDER, encoding="utf-8")
        (cls.root / "measure.mjs").write_text(MEASURE, encoding="utf-8")
        (cls.root / "mask.mjs").write_text(MASK, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, width: int, count: int, status: str = "ready") -> dict:
        import os

        env = dict(os.environ)
        env.update({"CB_TEST_WIDTH": str(width), "CB_TEST_PAYLOAD": json.dumps({"rows": rows(count), "status": status})})
        result = subprocess.run(
            ["node", str(self.root / "render.mjs")],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def paint(self, markup: str, widths: list[int]) -> list[dict]:
        html = (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\" />"
            "<style>html,body{margin:0;padding:0}body{font-family:system-ui,sans-serif}</style>"
            f"</head><body><div style=\"width:100%\">{markup}</div></body></html>"
        )
        path = self.root / "frame.html"
        path.write_text(html, encoding="utf-8")
        user_data = self.root / "chromium"
        result = subprocess.run(
            ["node", str(self.root / "measure.mjs"), str(path), json.dumps(widths), str(user_data)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class ShelfGeometryTest(GeometryBase):
    def test_home_v3_shelf_fits_its_route(self) -> None:
        # At each shell width the cards plus their gaps are no wider than the copy rule the shipped
        # `.cb3-gutter` leaves, so the row never clips a card and never needs to shrink one.
        for width, expected_columns, count in ((1049, 4, 4), (900, 3, 3), (460, 1, 1)):
            with self.subTest(width=width):
                markup = self.render(width, count)["html"]
                bases = [
                    int(value[:-2]) for value in re.findall(r'data-cb-home-card-basis="(\d+px)"', markup)
                ]
                self.assertEqual(len(bases), count, f"route {width} did not render {count} measured cards")
                self.assertEqual(len(set(bases)), 1, "one shelf must share one card width")
                if width >= 760:
                    gutter = min(64, max(20, width * 0.0305))
                else:
                    gutter = 0.7 * 16
                content = width - 2 * gutter
                gap = 16 if width >= 620 else 12
                needed = count * bases[0] + (count - 1) * gap
                self.assertLessEqual(
                    needed,
                    content + 0.5,
                    f"route {width}: {count} cards need {needed}px in a {content:.1f}px lane",
                )
                self.assertGreaterEqual(bases[0], 140, "a card must stay wide enough to read")
                # The fox owns the lower ledge and never a lane in the card row.
                if width == 460:
                    self.assertNotIn('data-cb-home-ledge=""', markup, "compact hides the fox ledge")
                    self.assertNotIn('data-cb3-fox', markup, "the fox box is hidden at compact")
                else:
                    self.assertIn('data-cb-home-ledge=""', markup, "the fox and tag stand on the lower ledge")
        # The overflow hint is placed wide and mid only: at 460 the shelf is a stacked column, so a
        # fifth course must not print \"More courses to the right\".
        compact_overflow = self.render(460, 5)["html"]
        self.assertNotIn('data-cb-home-overflow-hint', compact_overflow)
        self.assertEqual(compact_overflow.count('data-cb-home-card=""'), 4, "compact still holds four rows")
        mid_overflow = self.render(900, 4)["html"]
        self.assertIn('data-cb-home-overflow-hint', mid_overflow, "a fourth course at mid overflows")
        self.assertIn('data-cb-home-shelf-overflow="true"', mid_overflow)
        wide_fit = self.render(1049, 4)["html"]
        self.assertNotIn('data-cb-home-overflow-hint', wide_fit, "four courses fit wide")
        self.assertIn('data-cb-home-shelf-overflow="false"', wide_fit)

    def test_home_v3_shelf_cards_sit_inside_the_row(self) -> None:
        if shutil.which("chromium") is None:
            raise unittest.SkipTest("chromium is required to paint the shelf")
        cells = [(1049, 4), (900, 3), (460, 1)]
        measurements = []
        for width, count in cells:
            markup = self.render(width, count)["html"]
            measurements.extend(self.paint(markup, [width]))
        for (width, count), cell in zip(cells, measurements):
            with self.subTest(width=width):
                self.assertFalse(cell.get("missing"), f"route {width}: the shelf row did not paint")
                row = cell["row"]
                self.assertEqual(len(cell["cards"]), count, f"route {width} showed {len(cell['cards'])} cards")
                for index, card in enumerate(cell["cards"]):
                    self.assertGreaterEqual(
                        card["left"], row["left"] - 1,
                        f"route {width}: card {index} starts left of the row clip",
                    )
                    self.assertLessEqual(
                        card["right"], row["right"] + 1,
                        f"route {width}: card {index} is cut at the row edge",
                    )
                if width == 460:
                    self.assertEqual(row["direction"], "column", "compact stacks the shelf into rows")
                    self.assertFalse(cell["hint"], "the overflow hint is wide and mid only")
                else:
                    self.assertEqual(row["direction"], "row")
                self.assertLessEqual(
                    cell["pageOverflow"], 0,
                    f"route {width}: the Home painted {cell['pageOverflow']}px of page overflow",
                )
                if width == 460:
                    self.assertIsNone(cell["fox"], "compact hides the fox (H6)")
                else:
                    self.assertIsNotNone(cell["fox"], f"route {width}: the fox must stand on the ledge")
                    self.assertTrue(
                        cell["foxOnLedge"],
                        f"route {width}: the fox must be contained by the H6 ledge",
                    )
                    self.assertFalse(cell["foxOnShelfRow"], "the fox must not share the cards' flex row")

    def test_home_v3_mask_remeasures_on_a_route_change(self) -> None:
        import os

        env = dict(os.environ)
        env["CB_TEST_PAYLOAD"] = json.dumps({"rows": rows(4)})
        result = subprocess.run(
            ["node", str(self.root / "mask.mjs")],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        answer = json.loads(result.stdout)
        self.assertFalse(answer.get("missing"), "the client mount painted no shelf row")
        self.assertEqual(answer["before"], "none", "a row that fits must paint no edge mask")
        self.assertGreaterEqual(answer["observers"], 1, "the shelf did not construct a ResizeObserver")
        self.assertTrue(answer["observedRow"], "the ResizeObserver never observed the shelf row")
        # The observer path: the row geometry changes with no window resize at all.
        self.assertEqual(
            answer["afterObserver"],
            "right",
            "a row that narrows must re-measure to 'right' through its ResizeObserver alone",
        )
        self.assertEqual(answer["refit"], "none", "a fitting row must clear the mask again")
        # The route-width path stays covered as a second assertion.
        self.assertEqual(
            answer["afterResize"],
            "right",
            "a narrowed route leaves a scrollable shelf, so the mask must re-measure to 'right'",
        )


if __name__ == "__main__":
    unittest.main()
