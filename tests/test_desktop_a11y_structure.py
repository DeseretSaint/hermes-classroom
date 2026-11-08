"""Accessibility structure: one page title, ordered headings, named landmarks, one skip path.

The runtime plugin is one ESM file, so the honest test mounts the *registered route* — the same
``CoursebookPage`` the host renders — in jsdom with a stub SDK and a stub ``ctx.rest``. From that
live tree the test reads the real DOM: heading levels in document order, landmark roles and names,
and the first focus stop. Surfaces are reached the way a person reaches them (the destination nav,
then a path row), not by rendering fragments out of context.

What this does NOT prove: that the host chrome around the route is accessible, or that a screen
reader announces the tree the way Chromium's AX tree exposes it. Those are captured live against
the installed Desktop (see the card's audit frames).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import COMPLETE_BLOCKS, SDK_STUB, _desktop_node_modules, document

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The shared stub renders markdown as one plain div. For the prose-tier assertions the stub must
# produce the heading the host's markdown renderer would produce for an authored `#` title.
PROSE_SDK_STUB = SDK_STUB.replace(
    "export const MessageTextContent = (props) => el('div', { className: 'md' }, props.text)",
    "export const MessageTextContent = (props) =>\n"
    "  el('div', { className: 'md' }, String(props.text || '').split('\\n').map((line, index) =>\n"
    "    line.startsWith('# ') ? el('h1', { key: index }, line.slice(2)) : el('p', { key: index }, line)))",
)
assert PROSE_SDK_STUB != SDK_STUB, "the shared SDK stub changed shape; update the prose stub"

HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

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
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const calls = []
const responses = payload.responses || {}
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
const generic = { items: [], entries: [], objectives: [], total: 0 }

const fakeRest = async (path, options) => {
  const method = options && options.body && options.body.method
  calls.push({ path: String(path), method })
  const base = String(path).split('?')[0]
  if (base === '/rpc') {
    const result = Object.prototype.hasOwnProperty.call(responses, method) ? responses[method] : generic
    return { ok: true, contract_version: 6, operation_id: 'test', result }
  }
  if (base === '/runtime') return runtime
  if (base === '/health') {
    return { ok: true, contract_version: 6, result: { db: { ready: true }, plugin_version: 'test', contract_version: 6 } }
  }
  return { ok: true, result: {} }
}

const contributions = []
mod.default.register({
  rest: fakeRest,
  register: (entry) => contributions.push(entry),
  onDispose: () => {},
  setTimeout: (fn, ms) => {
    const handle = window.setTimeout(fn, ms)
    return () => window.clearTimeout(handle)
  },
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const route = contributions.find((entry) => entry.area === 'routes')
if (!route) throw new Error('the plugin registered no route')

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))

const flush = async (ms = 60) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const byText = (selector, wanted) =>
  [...document.querySelectorAll(selector)].find((node) => text(node) === wanted) || null

const focusables = () =>
  [...document.querySelectorAll(
    'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
  )].filter((node) => node.getAttribute('aria-hidden') !== 'true' && node.offsetParent !== null || node.hasAttribute('data-cb-skip'))

const headings = () =>
  [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map((node) => ({
    level: Number(node.tagName.slice(1)),
    text: text(node).slice(0, 90)
  }))

const landmarks = () =>
  [...document.querySelectorAll('header,nav,main,aside,footer,[role]')].map((node) => ({
    tag: node.tagName.toLowerCase(),
    role: node.getAttribute('role'),
    label: node.getAttribute('aria-label')
  }))

const skipProbe = async () => {
  const skip = document.querySelector('[data-cb-skip]')
  if (!skip) return { present: false }
  const firstFocusable = document.querySelectorAll(
    'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
  )[0]
  const hiddenWidth = skip.style.width
  await act(async () => { skip.focus() })
  await flush(10)
  const revealed = skip.style.width === 'auto' && skip.style.position === 'absolute'
  await act(async () => { skip.click() })
  await flush(10)
  const active = document.activeElement
  return {
    present: true,
    href: skip.getAttribute('href'),
    isFirstFocusable: firstFocusable === skip,
    hiddenWidth,
    revealedOnFocus: revealed,
    focusedTag: active ? active.tagName.toLowerCase() : null,
    focusedIsReadingColumn: Boolean(active && active.hasAttribute('data-cb-reading-column')),
    focusedIsMain: Boolean(active && active.id === 'cb-main-content'),
    focusedLabel: active ? active.getAttribute('aria-label') : null
  }
}

const snapshot = async (name) => {
  await flush()
  const surface = {
    name,
    headings: headings(),
    landmarks: landmarks(),
    skip: await skipProbe(),
    title: text(document.querySelector('[data-cb-page-title]')),
    destination: document.querySelector('[data-cb-route]') && document.querySelector('[data-cb-route]').getAttribute('data-cb-destination')
  }
  return surface
}

await act(async () => { root.render(route.render()) })
await flush()

const surfaces = []
if (payload.kind === 'prose') {
  const doc = payload.document
  await act(async () => {
    root.render(React.createElement(mod.LessonDocumentView, { document: doc, view: 'textbook', sources: {}, checkSlot: null }))
  })
  await flush(120)
  const prose = [...document.querySelectorAll('[data-cb-reading-body] h1')].map((node) => ({
    text: text(node),
    role: node.getAttribute('role'),
    ariaLevel: node.getAttribute('aria-level')
  }))
  process.stdout.write(JSON.stringify({ prose, proseH1Count: prose.length, routeH1Count: document.querySelectorAll('h1[data-cb-page-title]').length }))
} else {
surfaces.push(await snapshot('courses-desk'))

if (payload.firstRun) {
  process.stdout.write(JSON.stringify({ surfaces }))
} else {

const navTo = async (destination) => {
  const button = document.querySelector(`[data-cb-nav-item="${destination}"]`)
  if (!button) throw new Error('no destination nav item ' + destination)
  await act(async () => { button.click() })
  await flush()
}

await navTo('library')
surfaces.push(await snapshot('library'))
await navTo('studio')
surfaces.push(await snapshot('studio'))
await navTo('courses')

// The desk path is the same route a learner takes into a section: path row -> course -> textbook
// open section -> WorkspaceShell reading column.
const pathItem = document.querySelector('[data-cb-path-item]')
if (!pathItem) throw new Error('the desk rendered no path row')
await act(async () => { pathItem.closest('button').click() })
await flush(120)
surfaces.push(await snapshot('section'))

const clickText = async (selector, wanted) => {
  const node = byText(selector, wanted)
  if (!node) {
    const seen = [...document.querySelectorAll('button, a[href]')].map((item) => text(item)).join(' | ')
    throw new Error('no control ' + wanted + ' among: ' + seen)
  }
  await act(async () => { node.click() })
  await flush(120)
}

// Back to the section index, then each course surface the tabs can reach. H-149 moved the exit
// control into the player header (`Exit`), so the harness accepts either and proves the real one.
await clickText('button', byText('button', 'Exit') ? 'Exit' : 'Back to the section index')
for (const tab of ['Notebook', 'Quizzes', 'Evidence', 'Plan', 'Export']) {
  const control = byText('button', tab)
  if (!control) continue
  await act(async () => { control.click() })
  await flush(120)
  surfaces.push(await snapshot('course-' + tab.toLowerCase()))
}

// The list mode and the create flow are destinations of the same route.
await clickText('button', 'All courses')
await clickText('button', 'Search and manage courses')
surfaces.push(await snapshot('courses-list'))
await clickText('button', 'New course')
surfaces.push(await snapshot('create-course'))

process.stdout.write(JSON.stringify({ surfaces }))
}
}
"""


def library_responses() -> dict:
    document = {
        "schema_version": 1,
        "document_id": "doc_0123456789abcdef0123",
        "content_hash": "sha256:" + "a" * 64,
        "section_title": "Register and affection",
        "objective_id": "obj_0123456789abcdef",
        "state": "complete",
        "views": {"textbook": True, "guided": True, "field_quest": False, "field_notes": False},
        "blocks": COMPLETE_BLOCKS,
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
        "evidence_summary": {
            "total_objectives": 2,
            "independent": 0,
            "review_due": 0,
            "current_objective_id": "obj_0123456789abcdef",
        },
        "updated_at": "2026-11-01T10:00:00Z",
    }
    objectives = [
        {
            "objective_id": "obj_0123456789abcdef",
            "title": "Register and affection",
            "ordinal": 1,
            "state": "introduced",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        {
            "objective_id": "obj_0123456789abcdea",
            "title": "Ask in the polite register",
            "ordinal": 2,
            "state": "not_started",
            "evidence_target": "production",
            "last_opened_at": None,
        },
    ]
    return {
        "library.list": {"items": [row], "total": 1, "applied_filter": "all"},
        "course.outline": {"revision": 0, "objectives": objectives, "plan": {"units": []}},
        "lesson.page": {
            "revision": 4,
            "section": {
                "objective_id": "obj_0123456789abcdef",
                "title": "Register and affection",
                "ordinal": 1,
                "state": "introduced",
                "evidence_target": "discrimination",
                "last_opened_at": None,
            },
            "runtime": {"lesson_run_id": "run_1", "binding_id": None, "binding_status": "detached", "session_state": "stored_only"},
            "segments": [],
            "attempts": [],
            "notebook_entries": [],
            "sources": [{"source_id": "src_affection01", "title": "Affection and register — field notes", "support_status": "supported"}],
            "document": document,
        },
        "review.queue": {"items": [], "total_overdue": 0},
        "notebook.list": {"entries": []},
        "quiz.history": {"items": []},
        "evidence.inspect": {"items": []},
        "parent.brief.list": {"items": []},
        "pack.inspect": {},
        "parent.brief.get": {},
    }


class A11yStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-a11y-")
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
        (sdk / "index.js").write_text(PROSE_SDK_STUB, encoding="utf-8")
        cls.root = root
        cls.cache: dict[tuple[int, bool], dict] = {}

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def report(self, width: int = 1049, first_run: bool = False) -> dict:
        key = (width, first_run)
        if key in self.cache:
            return self.cache[key]
        responses = library_responses()
        if first_run:
            responses["library.list"] = {"items": [], "total": 0, "applied_filter": "all"}
        case = self.root / f"case-{width}-{int(first_run)}.json"
        case.write_text(json.dumps({"width": width, "firstRun": first_run, "responses": responses}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-6000:])
        data = json.loads(result.stdout)
        self.cache[key] = data
        return data

    def surface(self, name: str, width: int = 1049, first_run: bool = False) -> dict:
        data = self.report(width, first_run)
        found = next((item for item in data["surfaces"] if item["name"] == name), None)
        self.assertIsNotNone(found, f"{name} was not reached; got {[s['name'] for s in data['surfaces']]}")
        assert found is not None
        return found

    def all_surfaces(self, width: int = 1049) -> list[dict]:
        return self.report(width)["surfaces"]

    # -- the invariants, on every surface ------------------------------------------------
    def test_every_surface_has_exactly_one_h1_and_it_is_first(self) -> None:
        for width in (1049, 900, 460):
            names = [item["name"] for item in self.all_surfaces(width)]
            for name in names:
                with self.subTest(surface=name, width=width):
                    surface = self.surface(name, width)
                    levels = [heading["level"] for heading in surface["headings"]]
                    self.assertTrue(levels, f"{name} rendered no heading at all")
                    self.assertEqual(levels.count(1), 1, surface["headings"])
                    self.assertEqual(levels[0], 1, f"first heading is not h1: {surface['headings']}")

    def test_first_run_still_has_one_h1_first(self) -> None:
        surface = self.surface("courses-desk", first_run=True)
        levels = [heading["level"] for heading in surface["headings"]]
        self.assertEqual(levels[0], 1)
        self.assertEqual(levels.count(1), 1, surface["headings"])
        self.assertEqual(surface["headings"][0]["text"], "Courses")

    def test_no_heading_level_is_skipped(self) -> None:
        for name in [item["name"] for item in self.all_surfaces()]:
            with self.subTest(surface=name):
                levels = [heading["level"] for heading in self.surface(name)["headings"]]
                previous = levels[0]
                for level in levels[1:]:
                    self.assertLessEqual(level, previous + 1, f"{name} skips a level: {levels}")
                    previous = level

    def test_first_run_heading_is_an_h2_under_the_page_title(self) -> None:
        levels = [heading["level"] for heading in self.surface("courses-desk", first_run=True)["headings"]]
        self.assertIn(2, levels, levels)
        previous = levels[0]
        for level in levels[1:]:
            self.assertLessEqual(level, previous + 1, f"first run skips a level: {levels}")
            previous = level

    def test_the_desks_first_heading_is_the_page_title(self) -> None:
        surface = self.surface("courses-desk")
        self.assertEqual(surface["title"], "Courses")
        self.assertEqual(surface["headings"][0]["text"], "Courses")
        self.assertNotEqual(surface["headings"][0]["text"], "Register and affection")

    def test_landmarks_are_named(self) -> None:
        for name in ("courses-desk", "library", "studio", "section"):
            with self.subTest(surface=name):
                surface = self.surface(name)
                navs = [item for item in surface["landmarks"] if item["tag"] == "nav"]
                self.assertTrue(navs, f"{name} has no nav landmark")
                self.assertTrue(any(item["label"] for item in navs), f"{name} nav is unnamed: {navs}")
                mains = [item for item in surface["landmarks"] if item["tag"] == "main"]
                self.assertEqual(len(mains), 1, surface["landmarks"])
                self.assertTrue(mains[0]["label"], "the main landmark is unnamed")
                self.assertIn(surface["title"], mains[0]["label"])
                if name in ("courses-desk", "section"):
                    asides = [item for item in surface["landmarks"] if item["tag"] == "aside"]
                    if name == "section" or asides:
                        self.assertTrue(asides, f"{name} has no complementary landmark")
                        self.assertTrue(all(item["label"] for item in asides), f"{name} aside is unnamed: {asides}")

    def test_skip_link_is_the_first_focus_stop_and_reveals_on_focus(self) -> None:
        names = [item["name"] for item in self.all_surfaces()]
        for name in names:
            with self.subTest(surface=name):
                skip = self.surface(name)["skip"]
                self.assertTrue(skip.get("present"), f"{name} has no skip link")
                self.assertTrue(skip["isFirstFocusable"], f"{name} focus order does not start with the skip link")
                self.assertEqual(skip["href"], "#cb-main-content")
                self.assertTrue(skip["revealedOnFocus"], f"{name} skip link stays clipped while focused")

    def test_skip_link_moves_focus_into_content_never_the_header(self) -> None:
        for name in ("courses-desk", "library", "studio"):
            with self.subTest(surface=name):
                skip = self.surface(name)["skip"]
                self.assertTrue(skip["focusedIsMain"], f"{name} skip focus landed on {skip['focusedTag']}")
                self.assertFalse(skip["focusedIsReadingColumn"])
        section = self.surface("section")["skip"]
        self.assertTrue(section["focusedIsReadingColumn"], "the section skip path must land on the reading column")
        self.assertFalse(section["focusedIsMain"])

    def test_library_and_studio_have_their_own_page_title(self) -> None:
        self.assertEqual(self.surface("library")["title"], "Library")
        self.assertEqual(self.surface("studio")["title"], "Parent Studio")
        self.assertEqual(self.surface("section")["title"], "Courses")

    def test_each_destination_heading_regions_are_h2(self) -> None:
        library = [h["level"] for h in self.surface("library")["headings"]]
        self.assertIn(2, library, library)
        studio = [h["level"] for h in self.surface("studio")["headings"]]
        self.assertIn(2, studio, studio)
        desk = self.surface("courses-desk")["headings"]
        self.assertTrue(any(h["level"] == 2 for h in desk), desk)

    def test_authored_prose_h1_is_announced_as_level_two(self) -> None:
        """The reading body may carry its own `#` title; the page stays the only h1."""
        blocks = [dict(COMPLETE_BLOCKS[0], deep="# Measuring ingredients\nRead the jug on the counter."), *COMPLETE_BLOCKS[1:]]
        doc = document(guided=True, blocks=blocks, check_id="chk_0123456789abcdef")
        case = self.root / "case-prose.json"
        case.write_text(json.dumps({"kind": "prose", "document": doc}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        report = json.loads(result.stdout)
        self.assertEqual(report["proseH1Count"], 1, report)
        heading = report["prose"][0]
        self.assertEqual(heading["text"], "Measuring ingredients")
        self.assertEqual(heading["role"], "heading")
        self.assertEqual(heading["ariaLevel"], "2")
        self.assertEqual(report["routeH1Count"], 0, "the prose unit must not add a route page title")


if __name__ == "__main__":
    unittest.main()
