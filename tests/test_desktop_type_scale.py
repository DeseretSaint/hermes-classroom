"""Type scale: six steps, no seventh, and a 50-75ch reading measure.

The runtime plugin is one ESM file, so the honest test mounts the registered route in jsdom with
the same stub SDK and stub ``ctx.rest`` the accessibility test uses, then reads the rendered tree:

  * every font size Coursebook authors resolves to one of the six contract steps;
  * a captured surface never shows more than six distinct authored sizes;
  * no authored text resolves under 12px, and the primary description on a surface is body (16px);
  * every long paragraph sits inside a column capped in ``ch`` at 75 or less.

Host-owned chrome (badges, buttons, tab strips, pickers, the host markdown renderer) declares none
of those sizes and the plugin never overrides it, so it is outside the claim. The live computed
check against the installed Desktop is ``scripts/h93-type-verify.mjs``; this test is the
deterministic half that runs in CI.
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
CONTRACT = ROOT / "contracts" / "cb.tokens.v2.json"

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

const mod = await import('./plugin.js')
const responses = payload.responses || {}
const generic = { items: [], entries: [], objectives: [], total: 0 }
const runtime = {
  wire_version: 6,
  implemented_methods: [
    'library.list', 'course.outline', 'review.queue', 'notebook.list', 'quiz.history',
    'evidence.inspect', 'lesson.page', 'binding.get', 'pack.inspect', 'parent.brief.get',
    'parent.brief.list', 'course.export.read', 'course.create', 'pack.import',
    'syllabus.intake.create', 'parent.brief.create'
  ],
  single_home_host: false
}
const fakeRest = async (path, options) => {
  const method = options && options.body && options.body.method
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
  setTimeout: (fn, ms) => { const h = window.setTimeout(fn, ms); return () => window.clearTimeout(h) },
  clearTimeout: (h) => window.clearTimeout(h)
})
const route = contributions.find((entry) => entry.area === 'routes')
if (!route) throw new Error('the plugin registered no route')

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 60) => { await act(async () => { await new Promise((r) => setTimeout(r, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const byText = (selector, wanted) => [...document.querySelectorAll(selector)].find((n) => text(n) === wanted) || null

// A size the plugin declares: an inline font-size, or a host utility class it applies itself.
const UTILITIES = { 'text-xs': 12, 'text-sm': 14, 'text-base': 16, 'text-lg': 18, 'text-xl': 20 }
const toPx = (value) => {
  const raw = String(value).trim()
  if (raw.startsWith('clamp(')) {
    const first = raw.slice(6).split(',')[0].trim()
    return toPx(first)
  }
  const n = parseFloat(raw)
  if (!Number.isFinite(n)) return null
  return /rem$/.test(raw) ? n * 16 : n
}
const declared = (el) => {
  const inline = el.style && el.style.fontSize
  if (inline) return toPx(inline)
  const cls = typeof el.className === 'string' ? el.className.split(/\s+/) : []
  const hit = cls.find((c) => Object.prototype.hasOwnProperty.call(UTILITIES, c))
  return hit ? UTILITIES[hit] : null
}
const resolveSize = (el) => {
  let n = el
  while (n && n.nodeType === 1) {
    const own = declared(n)
    if (own !== null) return own
    n = n.parentElement
  }
  return 16
}
const chCap = (el) => {
  let n = el
  while (n && n.nodeType === 1) {
    const raw = (n.style && n.style.maxWidth) || ''
    const m = /^(\d+(?:\.\d+)?)ch$/.exec(String(raw).trim())
    if (m) return Number(m[1])
    n = n.parentElement
  }
  return null
}

const snapshot = (name) => {
  const surface = document.querySelector('[data-cb-route]') || document.querySelector('[data-cb-scope]') || document.body
  const sized = []
  const prose = []
  for (const el of surface.querySelectorAll('*')) {
    const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    if (ownText) sized.push({ tag: el.tagName.toLowerCase(), size: resolveSize(el), text: text(el).slice(0, 40) })
    if (el.tagName === 'P' && text(el).length >= 60) prose.push({ ch: chCap(el), text: text(el).slice(0, 40) })
  }
  return {
    name,
    sizes: [...new Set(sized.map((s) => s.size))].sort((a, b) => a - b),
    texts: sized,
    prose,
    undefinedProse: prose.filter((p) => p.ch === null).map((p) => p.text)
  }
}

await act(async () => { root.render(route.render()) })
await flush(120)
const surfaces = [snapshot('home-desk')]

const navTo = async (destination) => {
  const button = document.querySelector(`[data-cb-nav-item="${destination}"]`)
  if (!button) throw new Error('no destination nav item ' + destination)
  await act(async () => { button.click() })
  await flush(120)
}
await navTo('library')
surfaces.push(snapshot('library'))
await navTo('studio')
surfaces.push(snapshot('studio'))

const pathItem = document.querySelector('[data-cb-path-item]')
if (pathItem) {
  await act(async () => { pathItem.closest('button').click() })
  await flush(160)
}
// Whether the desk path opened or not, the section surface is rendered from its own page
// document so the reading column is always measured (the live script walks it for real).
const lessonPage = responses['lesson.page']
await act(async () => {
  root.render(
    React.createElement('div', {
      'data-cb-scope': 'light',
      style: mod.cbScopeStyle('light')
    }, React.createElement(mod.SectionPage, {
      row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default', next_step: { kind: 'resume_lesson', label: 'Resume this lesson' } },
      objectiveId: lessonPage.document.objective_id,
      page: lessonPage,
      pageStatus: 'ready',
      pageError: null,
      onRetryPage: () => {},
      implemented: new Set(['check.open', 'artifact.get', 'notebook.save']),
      onBack: () => {},
      onChanged: () => {},
      review: null
    }))
  )
})
await flush(200)
surfaces.push(snapshot('section'))

process.stdout.write(JSON.stringify({ surfaces }))
"""

EXPECTED_STEPS = {
    "caption": "0.75rem",
    "meta": "0.875rem",
    "body": "1rem",
    "lead": "1.125rem",
    "heading": "1.5rem",
    "display": "clamp(2.25rem, 1.9rem + 0.7vw, 2.5rem)",
}


def library_responses() -> dict:
    document = {
        "schema_version": 1,
        "document_id": "doc_0123456789abcdef0123",
        "content_hash": "sha256:" + "a" * 64,
        "section_title": "Register and affection",
        "objective_id": "obj_0123456789abcdef",
        "state": "complete",
        "views": {"textbook": True, "guided": True, "field_quest": False, "field_notes": False},
        "blocks": [
            {"kind": "paragraph", "text": "A" * 80},
        ],
        "check_id": "chk_0123456789abcdef",
        "source_ids": ["src_affection01"],
    }
    row = {
        "enrollment_id": "enr_0123456789abcdef",
        "course_id": "crs_0123456789abcdef",
        "title": "Affection and register",
        "revision": 7,
        "enrollment_status": "active",
        "recipe": "learner",
        "provenance": {"source": "authored", "pack_id": "pack_0123456789ab", "pack_version": "1.0.0"},
        "next_step": {"kind": "resume_lesson", "label": "Continue: Register and affection"},
        "evidence_summary": {"total_objectives": 2, "independent": 0, "review_due": 0, "current_objective_id": "obj_0123456789abcdef"},
        "updated_at": "2026-11-01T10:00:00Z",
    }
    objectives = [
        {"objective_id": "obj_0123456789abcdef", "title": "Register and affection", "ordinal": 1, "state": "introduced", "evidence_target": "discrimination", "last_opened_at": None},
        {"objective_id": "obj_0123456789abcdea", "title": "Ask in the polite register", "ordinal": 2, "state": "not_started", "evidence_target": "production", "last_opened_at": None},
    ]
    return {
        "library.list": {"items": [row], "total": 1, "applied_filter": "all"},
        "course.outline": {"revision": 0, "objectives": objectives, "plan": {"units": []}},
        "pack.list": {"items": [], "total": 0},
        "parent.brief.list": {"items": [], "total": 0},
        "lesson.page": {
            "revision": 4,
            "section": {"objective_id": "obj_0123456789abcdef", "title": "Affection and register", "state": "in_progress", "evidence_target": "discrimination", "last_opened_at": None},
            "runtime": {"lesson_run_id": None, "binding_id": None, "binding_status": "detached", "session_state": "stored_only"},
            "segments": [],
            "attempts": [],
            "notebook_entries": [],
            "sources": [],
            "document": document,
        },
    }


class TypeScaleSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PLUGIN_JS.read_text(encoding="utf-8")
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_the_contract_declares_exactly_six_steps(self) -> None:
        self.assertEqual(self.contract["type_scale"], EXPECTED_STEPS)

    def test_the_shipped_scale_equals_the_contract(self) -> None:
        match = re.search(r"const CB_TYPE_SCALE_JSON =\s*\n?\s*'([^']+)'", self.source)
        self.assertIsNotNone(match, "desktop/plugin.js has no CB_TYPE_SCALE_JSON")
        assert match is not None
        self.assertEqual(json.loads(match.group(1)), self.contract["type_scale"])

    def test_no_authored_font_size_escapes_the_scale(self) -> None:
        literals = re.findall(r"fontSize:\s*('(?:[^'\\]|\\.)*'|CB_TYPE\.\w+)", self.source)
        self.assertTrue(literals, "no font sizes found at all")
        stray = [value for value in literals if not value.startswith("CB_TYPE.")]
        self.assertEqual(stray, [], f"font sizes outside CB_TYPE: {stray}")

    def test_body_is_sixteen_pixels_at_the_default_root(self) -> None:
        self.assertEqual(self.contract["type_scale"]["body"], "1rem")
        self.assertGreaterEqual(0.75 * 16, 12)


class TypeScaleRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-type-")
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
        cls.cache: dict[int, dict] = {}

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def report(self, width: int = 1049) -> dict:
        if width in self.cache:
            return self.cache[width]
        case = self.root / f"case-{width}.json"
        case.write_text(json.dumps({"width": width, "responses": library_responses()}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        data = json.loads(result.stdout)
        self.cache[width] = data
        return data

    def surfaces(self, width: int = 1049) -> list[dict]:
        return self.report(width)["surfaces"]

    def surface(self, name: str, width: int = 1049) -> dict:
        found = next((item for item in self.surfaces(width) if item["name"] == name), None)
        self.assertIsNotNone(found, f"{name} was not reached; got {[s['name'] for s in self.surfaces(width)]}")
        assert found is not None
        return found

    def test_each_surface_uses_six_authored_sizes_or_fewer(self) -> None:
        for width in (1049, 900, 460):
            for item in self.surfaces(width):
                with self.subTest(surface=item["name"], width=width):
                    self.assertLessEqual(len(item["sizes"]), 6, item["sizes"])
                    self.assertTrue(item["sizes"], f"{item['name']} rendered no sized text")

    def test_no_authored_text_is_under_twelve_pixels(self) -> None:
        for width in (1049, 900, 460):
            for item in self.surfaces(width):
                with self.subTest(surface=item["name"], width=width):
                    self.assertGreaterEqual(min(item["sizes"]), 12, item["sizes"])

    def test_body_copy_is_sixteen_pixels(self) -> None:
        for name in ("home-desk", "library", "studio", "section"):
            with self.subTest(surface=name):
                item = self.surface(name)
                self.assertIn(16, item["sizes"], f"{name} has no 16px body copy: {item['sizes']}")

    def test_every_long_paragraph_sits_inside_a_ch_cap_of_75(self) -> None:
        for name in [item["name"] for item in self.surfaces()]:
            with self.subTest(surface=name):
                item = self.surface(name)
                self.assertEqual(item["undefinedProse"], [], f"{name} prose with no ch cap")
                for paragraph in item["prose"]:
                    self.assertLessEqual(paragraph["ch"], 75, paragraph)
                    self.assertGreaterEqual(paragraph["ch"], 50, paragraph)


if __name__ == "__main__":
    unittest.main()
