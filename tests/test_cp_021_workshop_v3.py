"""CP-021 — Discover / Workshop v3, executed rather than described.

The card's contract, in executable form:

* the page head, tabs, feature plate and pack grid are one v3 composition: the banner and the
  grid share one track, so no right-side dead band and no 80 px mismatch can exist;
* the grid's column count is a function of the **route** width — 4 at 1000+, 3 at 900, 1 row at
  460 — and the card grid never returns at compact;
* every card carries one metadata pattern: subject chip, real section count, one trust label. No
  star row, no review count, no invented badge; the strings the surface authors are deck rows;
* the store card and the pack detail resolve the same cover artifact through `/media/:id`;
* the fox points at the grid from inside its safe area at wide/mid and is absent at compact;
* exactly one filled control on the surface: `Preview this pack` on the feature plate;
* empty, error, offline and loading keep the banner's geometry and name one next action.

What this does NOT prove: that the browser paints the material well, that the plate reads at
1049/900/460, or that the composition passes the v3 rubric. Those are `scripts/cp-capture.mjs`
frames and the reviewer's scorecard.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.cb_source_scope import PLUGIN_JS, ROOT
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

SEGMENT = ROOT / "desktop" / "src" / "96-workshop.js"
COPY = ROOT / "docs" / "concept-parity" / "COPY.md"
COPY_ROW = re.compile(r"^\| `[a-z0-9._]+` \| (.*?) \|", re.MULTILINE)

#: The CP-021 block inside the workshop segment. A v2 `--cb-` token or a raw colour in here is a
#: second design system on the same screen, even when the surrounding H-196 code still uses v2.
V3_BEGIN = "/* ── CP-021 · Discover v3 (R-DISC)"


def _deck_texts() -> set[str]:
    return {text.strip() for text in COPY_ROW.findall(COPY.read_text(encoding="utf-8"))}


HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
globalThis.__CB_TEST_MODE__ = payload.mode === 'dark' ? 'dark' : 'light'

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
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
Object.defineProperty(document, 'fonts', {
  configurable: true,
  value: { ready: Promise.resolve(), status: 'loaded', add() {}, delete() {}, has() { return false } }
})
// jsdom never decodes an image; every data URL settles synchronously for this harness.
dom.window.Image = class ImmediateImage {
  constructor() { this.onload = null; this.onerror = null; this._src = '' }
  get src() { return this._src }
  set src(value) { this._src = value; setTimeout(() => { if (this.onload) this.onload() }, 0) }
}

const consoleErrors = []
const realConsoleError = console.error.bind(console)
console.error = (...args) => { consoleErrors.push(args.map((value) => String(value)).join(' ')) }

const INSTALLED = 'art_cover_japanese'
const ITEMS = [
  {
    pack_id: 'japanese-affection-context-l0',
    title: 'Japanese: the two ways to say it',
    subtitle: 'Choose the register that fits the person you are speaking to.',
    outcome: 'Choose the Japanese expression that fits the person you are speaking to, and say why it fits.',
    pack_version: '2.2.0',
    categories: ['Languages', 'Japanese'],
    section_count: 6,
    objective_count: 4,
    minutes: 40,
    featured: true,
    will_not_teach: ['Kanji beyond the lines each section writes out.'],
    creator_note: 'Written as the sample L0 classroom.',
    sections: [
      { title: 'Two ways to say it', objective: 'Pick the register', minutes: 10 },
      { title: 'Choosing the addressee', objective: 'Pick the register', minutes: 10 },
      { title: 'A new context', objective: 'Pick the register', minutes: 10 }
    ],
    sources: [],
    contributors: [],
    integrity: { hashes_match: true, file_count: 6, expanded_bytes: 4096 },
    license: { id: 'CC0-1.0', note: '', redistribution: 'allowed' },
    attribution: '',
    content_hash: 'sha256:1111111111111111111111111111111111111111111111111111111111111111',
    recipe: 'japanese',
    locale: 'ja-JP',
    level_label: 'CEFR A1',
    changelog: [],
    trust_labels: ['integrity_verified', 'automated_checks_passed'],
    validated: true,
    cover: { kind: 'artifact', artifact_id: INSTALLED, alt: 'A painted lantern', caption: 'Cover plate' },
    installed: { course_id: 'course_jp', enrollment_id: 'enr_jp', next_step: { kind: 'start_lesson', label: 'Start section 1' } }
  },
  {
    pack_id: 'parent-measurement-practice',
    title: 'Measuring at the kitchen table',
    subtitle: 'Read a jug and double a quantity with a parent.',
    outcome: 'Read a measuring jug and double a quantity, with a parent guiding.',
    pack_version: '2.0.0',
    categories: ['For parents', 'Measurement'],
    section_count: 3,
    objective_count: 2,
    minutes: 25,
    featured: false,
    will_not_teach: [],
    creator_note: '',
    sections: [{ title: 'Read the jug', objective: 'Read the jug', minutes: 12 }],
    sources: [],
    contributors: [],
    integrity: { hashes_match: true, file_count: 6, expanded_bytes: 4096 },
    license: { id: 'CC0-1.0', note: '', redistribution: 'allowed' },
    attribution: '',
    content_hash: 'sha256:1111111111111111111111111111111111111111111111111111111111111111',
    recipe: 'japanese',
    locale: 'ja-JP',
    level_label: 'CEFR A1',
    changelog: [],
    trust_labels: ['integrity_verified'],
    validated: false,
    cover: { kind: 'typographic', artifact_id: null, alt: null, caption: null },
    installed: null
  },
  {
    pack_id: 'technical-demo-pack',
    title: 'What a pack manifest declares',
    subtitle: 'Read the contract behind the shelf.',
    outcome: 'Read what a pack manifest declares and what its trust labels can and cannot prove.',
    pack_version: '2.1.0',
    categories: ['Technical'],
    section_count: 2,
    objective_count: 2,
    minutes: 15,
    featured: false,
    will_not_teach: [],
    creator_note: '',
    sections: [{ title: 'Anatomy', objective: 'Read the manifest', minutes: 8 }],
    sources: [],
    contributors: [],
    integrity: { hashes_match: true, file_count: 6, expanded_bytes: 4096 },
    license: { id: 'CC0-1.0', note: '', redistribution: 'allowed' },
    attribution: '',
    content_hash: 'sha256:1111111111111111111111111111111111111111111111111111111111111111',
    recipe: 'japanese',
    locale: 'ja-JP',
    level_label: 'CEFR A1',
    changelog: [],
    trust_labels: [],
    validated: false,
    cover: { kind: 'artifact', artifact_id: 'art_cover_technical', alt: null, caption: null },
    installed: null
  }
]

const CATALOG = {
  ok: true,
  items: payload.variant === 'empty' ? [] : ITEMS,
  featured_pack_id: 'japanese-affection-context-l0',
  refused: [],
  count: payload.variant === 'empty' ? 0 : ITEMS.length
}

let resolveCatalog
const catalogGate = new Promise((resolve) => { resolveCatalog = resolve })
const rest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return {
      wire_version: 24,
      implemented_methods: ['library.list', 'course.outline', 'review.queue', 'notebook.list', 'quiz.history',
        'evidence.inspect', 'lesson.page', 'binding.get', 'pack.inspect', 'parent.brief.get',
        'parent.brief.list', 'course.export.read', 'course.create', 'pack.import', 'pack.list', 'pack.preview'],
      single_home_host: false
    }
  }
  if (base === '/health') {
    return { ok: true, contract_version: 24, result: { db: { ready: true }, plugin_version: 'test', contract_version: 24 } }
  }
  if (base === '/workshop/catalog') {
    if (payload.variant === 'loading' || payload.variant === 'held') return catalogGate
    if (payload.variant === 'error') {
      return { ok: false, code: 'WORKSHOP_UNAVAILABLE', message: 'The catalogue did not answer.' }
    }
    if (payload.variant === 'offline') throw new Error('network unreachable')
    return CATALOG
  }
  if (base.startsWith('/media/')) {
    return { ok: true, data_url: `data:image/png;base64,${base.replace('/media/', '')}` }
  }
  if (base === '/rpc') {
    const method = options && options.body && options.body.method
    if (method === 'library.list') return { ok: true, contract_version: 24, operation_id: 't', result: { items: [], total: 0 } }
    if (method === 'pack.list') return { ok: true, contract_version: 24, operation_id: 't', result: { items: [] } }
    return { ok: true, contract_version: 24, operation_id: 't', result: { items: [], entries: [], objectives: [], total: 0 } }
  }
  return { ok: true, result: {} }
}

const mod = await import('./plugin.js')
const contributions = []
mod.default.register({
  rest,
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
const click = async (node) => {
  if (!node) throw new Error('click target is missing')
  await act(async () => {
    node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  await flush(60)
}
const text = (node) => (node ? (node.textContent || '').replace(/\s+/g, ' ').trim() : null)

await act(async () => { root.render(route.render()) })
await flush(60)
await click(document.querySelector('[data-cb-nav-item="workshop"]'))
await flush(120)
if (payload.variant === 'held') {
  resolveCatalog(CATALOG)
  await flush(120)
}

const head = document.querySelector('[data-cb3-discover-head]')
const track = document.querySelector('[data-cb3-discover-track]')
const grid = document.querySelector('[data-cb3-discover-grid]')
const feature = document.querySelector('[data-cb3-feature]')
const cards = [...document.querySelectorAll('[data-cb3-pack]')]
const pills = [...document.querySelectorAll('[data-cb3-pill]')]
const primaries = pills.filter((node) => node.getAttribute('data-cb3-pill') === 'primary')
const gridPrimaries = grid ? [...grid.querySelectorAll('[data-cb3-pill="primary"]')] : []
const fox = document.querySelector('[data-cb3-discover-fox] [data-cb3-fox]')
const state = document.querySelector('[data-cb3-discover-state]')
const skeleton = document.querySelector('[data-cb3-discover-skeleton]')
const tabs = [...document.querySelectorAll('[data-cb-workshop-tab]')].map((node) => ({
  id: node.getAttribute('data-cb-workshop-tab'),
  label: text(node),
  current: node.getAttribute('aria-current'),
  active: node.getAttribute('data-cb-workshop-tab-active')
}))
const headingOrder = [...document.querySelectorAll('[data-cb-route] h1, [data-cb-route] h2, [data-cb-route] h3')]
  .map((node) => node.tagName.toLowerCase())

const storeCover = (() => {
  const first = document.querySelector('[data-cb3-pack="japanese-affection-context-l0"] img')
  return first ? first.getAttribute('src') : null
})()

// Snapshot the console before the Library/detail interactions: those surfaces are H-196's and a
// warning they raise is not a Discover render result.
const discoverKeyErrors = consoleErrors.filter((line) => /unique "key"/.test(line))

// The one filled control opens the pack detail; the detail must serve the same cover bytes.
let detailCover = null
let detailOpened = false
if (payload.variant === 'default') {
  const card = document.querySelector('[data-cb3-pack="japanese-affection-context-l0"]')
  if (card) {
    await click(card)
    const detail = document.querySelector('[data-cb-workshop-detail]')
    detailOpened = Boolean(detail)
    const image = detail ? detail.querySelector('img') : null
    detailCover = image ? image.getAttribute('src') : null
  }
}

// The Library tab keeps H-196's surface and a visible active state.
let libraryActive = null
if (payload.variant === 'default') {
  await click(document.querySelector('[data-cb-workshop-tab="library"]'))
  const current = document.querySelector('[data-cb-workshop-tab][aria-current="page"]')
  libraryActive = current ? current.getAttribute('data-cb-workshop-tab') : null
}

process.stdout.write(JSON.stringify({
  destination: document.querySelector('[data-cb-route]') ? document.querySelector('[data-cb-route]').getAttribute('data-cb-destination') : null,
  headTitle: head ? text(head.querySelector('h2')) : null,
  headBody: head ? text(head.querySelector('p')) : null,
  tabs,
  tabCount: tabs.length,
  bannerTitle: feature ? text(feature.querySelector('h3')) : null,
  bannerBody: feature ? text(feature.querySelector('p')) : null,
  bannerOnTrack: Boolean(feature && track && feature.parentElement === track),
  bannerPrimary: feature ? feature.querySelectorAll('[data-cb3-pill="primary"]').length : 0,
  primaryCount: primaries.length,
  gridPrimaryCount: gridPrimaries.length,
  gridColumns: grid ? grid.getAttribute('data-cb3-discover-grid') : null,
  gridTemplate: grid ? grid.style.gridTemplateColumns : null,
  cardCount: cards.length,
  cardTitles: cards.map((node) => text(node.querySelector('h3'))),
  cardCovers: cards.map((node) => {
    const plate = node.querySelector('[data-cb3-cover]')
    const img = plate ? plate.querySelector('img') : null
    return {
      pack: node.getAttribute('data-cb3-pack'),
      kind: plate ? plate.getAttribute('data-cb3-cover') : null,
      src: img ? img.getAttribute('src') : null
    }
  }),
  kitCovers: {
    japanese: mod.cb3KitSource('japanese-cover-3x2'),
    parent: mod.cb3KitSource('parent-cover-3x2'),
    technical: mod.cb3KitSource('technical-cover-3x2')
  },
  cardMetas: cards.map((node) => text(node.querySelector('[data-cb3-card-meta]') || node.querySelector('p'))),
  cardSubjects: cards.map((node) => text(node.querySelector('[data-cb3-chip="subject"]'))),
  cardCoordinates: cards.map((node) => node.getAttribute('role') + '/' + node.getAttribute('tabindex')),
  trackText: track ? text(track) : null,
  state: state ? state.getAttribute('data-cb3-discover-state') : null,
  stateTitle: state ? text(state.querySelector('h3')) : null,
  stateBody: state ? text(state.querySelector('p')) : null,
  stateAction: state ? text(state.querySelector('[data-cb3-pill]')) : null,
  statePrimaries: state ? state.querySelectorAll('[data-cb3-pill="primary"]').length : 0,
  skeleton: Boolean(skeleton),
  foxPose: fox ? fox.getAttribute('data-cb3-fox') : null,
  foxAriaHidden: fox ? fox.getAttribute('aria-hidden') : null,
  foxSafe: fox ? fox.getAttribute('data-cb3-fox-safe') : null,
  foxBox: fox ? fox.style.width : null,
  storeCover,
  detailOpened,
  detailCover,
  libraryActive,
  headingOrder,
  consoleKeyErrors: discoverKeyErrors,
  consoleKeyErrorsAfterTabs: consoleErrors.filter((line) => /unique "key"/.test(line)),
  consoleErrors: consoleErrors.slice(0, 10)
}))
"""


class WorkshopV3SourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")
        start = cls.source.index(V3_BEGIN)
        end = cls.source.index("/** The imported-pack ledger", start)
        cls.block = cls.source[start:end]

    def test_the_surface_authors_only_deck_copy(self) -> None:
        deck = _deck_texts()
        start = self.block.index("const CB3_DISCOVER_COPY")
        end = self.block.index("})", start)
        literals = re.findall(r"^\s{2}([a-zA-Z]+): '([^']+)'", self.block[start:end], re.MULTILINE)
        self.assertTrue(literals, "the Discover copy block is missing")
        for key, value in literals:
            with self.subTest(key=key):
                self.assertIn(value, deck, f"{key} renders a string the copy deck does not own")

    def test_the_v3_block_paints_only_v3_tokens(self) -> None:
        self.assertNotRegex(self.block, r"#[0-9a-fA-F]{3,8}\b", "a raw colour in the Discover block")
        self.assertNotRegex(self.block, r"var\(--cb-(?!3-)", "a v2 --cb- token on the v3 Discover surface")
        self.assertNotRegex(self.block, r"\b\d+(?:\.\d+)?vw\b", "a viewport unit measures the Desktop window")
        self.assertNotIn("gradient(", self.block)
        self.assertNotIn("backdropFilter", self.block)

    def test_the_grid_measures_the_route_not_the_window(self) -> None:
        self.assertIn("cb3DiscoverColumns(routeWidth)", self.block)
        self.assertIn("useCbViewportWidth()", self.source)

    def test_no_rating_star_or_life_badge_is_authorable(self) -> None:
        for needle in ("★", "☆", "Life", "rating", "reviewCount", "stars"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, self.block)


class WorkshopV3RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp021-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
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
        cls.reports = {}

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, variant: str = "default", width: int = 1049, mode: str = "light") -> dict:
        key = f"{variant}-{width}-{mode}"
        if key not in self.reports:
            case = self.root / f"{key}.json"
            case.write_text(json.dumps({"variant": variant, "width": width, "mode": mode}), encoding="utf-8")
            result = subprocess.run(
                ["node", str(self.root / "harness.mjs"), str(case)],
                cwd=self.root, capture_output=True, text=True, timeout=240,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr[-6000:])
            self.reports[key] = json.loads(result.stdout)
        return self.reports[key]

    # ── the named card tests ────────────────────────────────────────────────────────────────

    def test_no_typographic_cover_for_the_three_seeded_packs(self) -> None:
        """D-007: a mapped pack reads the approved display cover, never a typographic plate."""
        report = self.render()
        covers = {row["pack"]: row for row in report["cardCovers"]}
        self.assertEqual(set(covers), {
            "japanese-affection-context-l0",
            "parent-measurement-practice",
            "technical-demo-pack",
        })
        for pack, row in covers.items():
            with self.subTest(pack=pack):
                self.assertEqual(row["kind"], "art", f"{pack} still renders a typographic cover")
                self.assertTrue(row["src"], f"{pack} serves no plate")
        # A real pack artifact still wins over the kit plate.
        self.assertTrue(covers["japanese-affection-context-l0"]["src"].startswith("data:image/png;base64,art_cover_japanese"))
        self.assertTrue(covers["technical-demo-pack"]["src"].startswith("data:image/png;base64,art_cover_technical"))
        # The pack with no cover artifact of its own is the one that has to read the kit plate.
        self.assertEqual(covers["parent-measurement-practice"]["src"], report["kitCovers"]["parent"])
        self.assertTrue(covers["parent-measurement-practice"]["src"].startswith("data:image/webp;base64,"))
        self.assertNotEqual(report["kitCovers"]["japanese"], report["kitCovers"]["parent"])
        self.assertNotEqual(report["kitCovers"]["parent"], report["kitCovers"]["technical"])

    def test_workshop_v3_no_ratings_or_counts(self) -> None:
        report = self.render()
        self.assertEqual(report["consoleKeyErrors"], [], "the Discover render raises a React key warning")
        self.assertIsNone(report["state"], "the default state painted a state plate")
        self.assertEqual(report["cardCount"], 3, "one card per catalogue pack")
        self.assertEqual(report["gridPrimaryCount"], 0, "a card carries a filled control")
        self.assertEqual(report["primaryCount"], 1, "the surface does not have exactly one filled control")
        self.assertEqual(report["bannerPrimary"], 1, "the one primary is not on the feature plate")
        self.assertEqual(report["primaryCount"], report["bannerPrimary"])
        self.assertNotIn("★", report["trackText"] or "")
        for needle in (" XP", "Life", "reviews", "rating"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, report["trackText"] or "")
        # One metadata pattern: real sections + one trust label, in the same order on every card.
        self.assertEqual(report["cardSubjects"], ["Languages", "For parents", "Technical"])
        self.assertEqual(
            report["cardMetas"],
            ["6 sections·Files checked", "3 sections·Files checked", "2 sections"],
            "the card metadata pattern is not the same order on every card",
        )
        for coordinate in report["cardCoordinates"]:
            self.assertEqual(coordinate, "link/0", "a card is not a keyboard-reachable link")

    def test_workshop_v3_grid_aligned_to_banner(self) -> None:
        report = self.render()
        self.assertTrue(report["bannerOnTrack"], "the banner is not on the shared track")
        self.assertEqual(report["gridColumns"], "4", "1049 route px is not the 4-column layout")
        self.assertEqual(report["gridTemplate"], "repeat(4, minmax(0, 1fr))")
        # Both regions are width:100% children of one track, so they share a left and right edge.
        self.assertIn("width: '100%'", self.source_block_of("data-cb3-discover-track"))
        self.assertIn("width: '100%'", self.source_block_of("data-cb3-feature"))
        self.assertEqual(report["headTitle"], "Discover")
        self.assertEqual(report["headBody"], "Packs you can learn from, already on this device.")
        self.assertEqual([tab["label"] for tab in report["tabs"]], ["Discover", "Library", "Provenance", "Share to store"])
        self.assertEqual(report["tabs"][0]["current"], "page")
        self.assertEqual(report["tabs"][0]["active"], "true")

    def test_workshop_v3_same_cover_in_store_library_detail(self) -> None:
        report = self.render()
        self.assertTrue(report["storeCover"], "the store card serves no cover artifact")
        self.assertTrue(report["detailOpened"], "the one primary did not open the pack detail")
        self.assertEqual(
            report["storeCover"], report["detailCover"],
            "the store card and the pack detail serve different covers for the same pack",
        )
        self.assertEqual(report["libraryActive"], "library", "the Library tab has no visible active state")

    def test_workshop_v3_columns_from_route_width(self) -> None:
        wide = self.render(width=1049)
        mid = self.render(width=900)
        compact = self.render(width=460)
        self.assertEqual(wide["gridColumns"], "4")
        self.assertEqual(mid["gridColumns"], "3")
        self.assertEqual(compact["gridColumns"], "1", "a card grid appears at 460")
        self.assertEqual(compact["cardCount"], 3, "compact drops cards instead of stacking them")
        self.assertEqual(wide["foxPose"], "point")
        self.assertEqual(wide["foxSafe"], "24px")
        self.assertEqual(mid["foxSafe"], "16px")
        self.assertIsNone(compact["foxPose"], "the fox is painted at 460 where the spec hides it")

    def test_workshop_v3_empty_error_offline_loading_states(self) -> None:
        empty = self.render("empty")
        self.assertEqual(empty["state"], "empty")
        self.assertEqual(empty["stateAction"], "Import a pack")
        self.assertEqual(empty["statePrimaries"], 0, "the empty state added a second filled control")
        error = self.render("error")
        self.assertEqual(error["state"], "error")
        self.assertEqual(error["stateTitle"], "The workshop could not be read")
        self.assertEqual(error["stateAction"], "Try again")
        offline = self.render("offline")
        self.assertEqual(offline["state"], "offline")
        self.assertEqual(offline["stateTitle"], "You are offline")
        loading = self.render("loading")
        self.assertTrue(loading["skeleton"], "loading paints no skeleton of the real regions")
        self.assertEqual(loading["cardCount"], 0, "the skeleton painted real cards")
        self.assertEqual(self.render("held")["cardCount"], 3, "the skeleton never resolves to content")

    def test_workshop_v3_heading_order(self) -> None:
        report = self.render()
        order = report["headingOrder"]
        self.assertEqual(order[0], "h1", "the route's first heading is not its page title")
        self.assertLess(order.index("h2"), order.index("h3"), "a card title precedes the page regions")

    # ── helpers ────────────────────────────────────────────────────────────────────────────

    def source_block_of(self, marker: str) -> str:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        start = source.index(marker)
        return source[start : start + 2200]


if __name__ == "__main__":
    unittest.main()
