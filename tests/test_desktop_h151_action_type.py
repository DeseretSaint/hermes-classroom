"""H-151: one Coursebook action primitive, one type hierarchy.

H-151 found 44 host-blue `variant: 'default'` call sites and no Coursebook action primitive, so a
Coursebook route inherited the settings-page control language: the loudest Library action was the
host accent, the page h1 was smaller than the plate h2, and Codicon sizes had drifted to 12-14px.

This file reads the *shipped* module. It asserts the source contract (one four-variant wrapper,
one `default` variant in the file and it is inside the wrapper) and then renders the real route
and the real Section / Course Detail surfaces through React in jsdom, with a stub SDK whose
`Button` keeps inline style so target size and fill can be measured:

  * every default-variant button on a surface is a `CbAction primary`;
  * at most one primary per core surface, and it is lamp/on-lamp at 44px;
  * secondary is 44px, tertiary is 24px, row is 44px and full-width;
  * exactly one h1, at display; PlateHead h2s at heading; no second display-sized heading;
  * every Codicon is 16px (UI) or 20px (plate), never 12-14px.

What this does NOT prove: that the installed Desktop paints the same pixels. The live frames and
computed styles are captured separately by ``scripts/h151-action-capture.mjs``.
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
from tests.test_desktop_type_scale import library_responses

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

OLD_BUTTON = """export const Button = (props) => {
  const attrs = {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }
  if (props.className) attrs.className = props.className
  if (props.title) attrs.title = props.title
  for (const [name, value] of Object.entries(props)) {
    if ((name.startsWith('data-') || name.startsWith('aria-')) && value !== undefined && !(name in attrs)) {
      attrs[name] = value
    }
  }
  return el('button', attrs, textOf(props))
}"""

NEW_BUTTON = """export const Button = (props) => {
  const attrs = {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }
  if (props.className) attrs.className = props.className
  if (props.style) attrs.style = props.style
  if (props.title) attrs.title = props.title
  for (const [name, value] of Object.entries(props)) {
    if ((name.startsWith('data-') || name.startsWith('aria-')) && value !== undefined && !(name in attrs)) {
      attrs[name] = value
    }
  }
  return el('button', attrs, textOf(props))
}"""

OLD_CODICON = "export const Codicon = () => null"
NEW_CODICON = "export const Codicon = (props) => el('span', { className: 'codicon', 'data-icon': props.name || '', 'data-size': props.size || '' }, null)"

STUB = SDK_STUB.replace(OLD_BUTTON, NEW_BUTTON).replace(OLD_CODICON, NEW_CODICON)

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

const read = (el) => ({
  tag: el.tagName.toLowerCase(),
  text: text(el).slice(0, 48),
  action: el.getAttribute('data-cb-action'),
  variant: el.getAttribute('data-variant'),
  breadcrumb: el.getAttribute('data-cb-breadcrumb'),
  disabled: Boolean(el.disabled),
  minHeight: el.style.minHeight || '',
  fontSize: el.style.fontSize || '',
  background: el.style.backgroundColor || el.style.background || '',
  color: el.style.color || '',
  width: el.style.width || '',
  styleAttr: el.getAttribute('style') || '',
  className: typeof el.className === 'string' ? el.className : ''
})

const declaredSize = (el) => {
  const inline = (el.style && el.style.fontSize) || ''
  if (inline) return inline
  const attr = el.getAttribute('style') || ''
  const match = /font-size:\s*([^;]+)/.exec(attr)
  return match ? match[1].trim() : ''
}

const snapshot = (name) => {
  const surface = document.querySelector('[data-cb-route]') || document.querySelector('[data-cb-scope]') || document.body
  const buttons = [...surface.querySelectorAll('button')].map(read)
  const headings = [...surface.querySelectorAll('h1,h2,h3,h4,h5,h6')].map((h) => ({
    tag: h.tagName.toLowerCase(),
    text: text(h).slice(0, 40),
    fontSize: declaredSize(h),
    pageTitle: h.hasAttribute('data-cb-page-title'),
    plateHead: Boolean(h.closest('[data-cb-plate-head]'))
  }))
  const icons = [...surface.querySelectorAll('.codicon')].map((i) => i.getAttribute('data-size'))
  return { name, buttons, headings, icons }
}

await act(async () => { root.render(route.render()) })
await flush(160)
const surfaces = [snapshot('home')]

// GM-002: the path (and its row-variant checkpoint actions) lives on the selected course's home,
// one step in from the library Home.
const shelfCard = document.querySelector('[data-cb-home-card] button')
if (shelfCard) {
  await act(async () => { shelfCard.click() })
  await flush(240)
  surfaces.push(snapshot('course-home'))
  await act(async () => {
    const back = document.querySelector('[data-cb-home-back]')
    if (back) back.click()
  })
  await flush(240)
}

const navTo = async (destination) => {
  const button = document.querySelector(`[data-cb-nav-item="${destination}"]`)
  if (!button) throw new Error('no destination nav item ' + destination)
  await act(async () => { button.click() })
  await flush(160)
}
for (const destination of ['courses', 'workshop', 'studio']) {
  await navTo(destination)
  surfaces.push(snapshot(destination))
}

// Course Detail: the course page a learner reaches from the Courses catalog. This runs before
// the section mount, because that mount replaces the route root. An empty profile has no row to
// open, so the step is skipped rather than failing the whole harness.
await navTo('courses')
const openCourse = [...document.querySelectorAll('[data-cb-course-cover] button')].find((b) => text(b) === 'Open')
if (openCourse) {
  await act(async () => { openCourse.click() })
  await flush(240)
  surfaces.push(snapshot('course-detail'))
}

// The section surface is rendered from its own page document, so the reading column always mounts.
const lessonPage = responses['lesson.page']
await act(async () => {
  root.render(
    React.createElement('div', { 'data-cb-scope': 'light', style: mod.cbScopeStyle('light') },
      React.createElement(mod.SectionPage, {
        row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default', next_step: { kind: 'resume_lesson', label: 'Resume this lesson' } },
        objectiveId: lessonPage.document.objective_id,
        page: lessonPage,
        pageStatus: 'ready',
        pageError: null,
        onRetryPage: () => {},
        implemented: new Set(['check.open', 'artifact.get', 'notebook.save', 'lesson.page']),
        onBack: () => {},
        onChanged: () => {},
        review: null
      }))
  )
})
await flush(220)
surfaces.push(snapshot('section'))

process.stdout.write(JSON.stringify({ surfaces }))
"""


def to_px(value: str):
    raw = str(value or "").strip()
    if raw.startswith("clamp("):
        raw = raw[6:].split(",")[0].strip()
    match = re.match(r"^(-?\d+(?:\.\d+)?)(rem|px)?$", raw)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or "px"
    return number * 16 if unit == "rem" else number


class ActionSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_one_wrapper_with_exactly_four_variants(self) -> None:
        match = re.search(r"const CB_ACTION_VARIANTS = Object\.freeze\(\[([^\]]+)\]\)", self.source)
        self.assertIsNotNone(match, "desktop/plugin.js has no CB_ACTION_VARIANTS")
        assert match is not None
        variants = [item.strip().strip("'") for item in match.group(1).split(",")]
        self.assertEqual(variants, ["primary", "secondary", "tertiary", "row"])

    def test_the_wrapper_is_the_only_place_a_host_default_button_is_built(self) -> None:
        # `variant: 'default'` is the host accent fill. Exactly one declaration may exist: the
        # primary row of CB_ACTION_STYLES. Every other call site asks for a Coursebook variant.
        self.assertEqual(self.source.count("variant: 'default'"), 1, self.source.count("variant: 'default'"))
        loop = self.source.index("function CbAction(")
        table = self.source.index("const CB_ACTION_STYLES")
        self.assertLess(table, loop)
        self.assertIn("jsx(sdk.Button, {", self.source[loop:])

    def test_primary_fill_is_the_lamp_and_never_the_host_accent(self) -> None:
        table = self.source[self.source.index("const CB_ACTION_STYLES") : self.source.index("function CbAction(")]
        primary = table[table.index("primary: {") : table.index("secondary: {")]
        self.assertIn("background: 'var(--cb-lamp)'", primary)
        self.assertIn("color: 'var(--cb-on-lamp)'", primary)
        self.assertIn("minHeight: '44px'", primary)

    def test_codicon_sizes_are_16_or_20_only(self) -> None:
        sizes = re.findall(r"jsx\(sdk\.Codicon, \{[^}]*size: ([^,}]+)", self.source)
        self.assertTrue(sizes, "no Codicon call sites found")
        allowed = {"CB_ICON_UI", "CB_ICON_PLATE"}
        stray = [value.strip() for value in sizes if value.strip() not in allowed]
        self.assertEqual(stray, [], f"Codicon sizes outside the 16/20 pair: {stray}")
        self.assertIn("const CB_ICON_UI = '1rem'", self.source)
        self.assertIn("const CB_ICON_PLATE = '1.25rem'", self.source)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class ActionRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h151-")
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
        (sdk / "index.js").write_text(STUB, encoding="utf-8")
        cls.cache: dict[tuple[int, bool], dict] = {}

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def report(self, width: int = 1049, empty_catalog: bool = False) -> dict:
        key = (width, empty_catalog)
        if key in self.cache:
            return self.cache[key]
        responses = library_responses()
        if empty_catalog:
            # The welcome owns the primary when the profile has no courses; the route header must
            # then drop its own "New course" (UX-01: one screen, one primary).
            responses = dict(responses)
            responses["library.list"] = {"items": [], "total": 0, "applied_filter": "all"}
        suffix = "empty" if empty_catalog else "shelf"
        case = self.root / f"case-{width}-{suffix}.json"
        case.write_text(json.dumps({"width": width, "responses": responses}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        data = json.loads(result.stdout)
        self.cache[key] = data
        return data

    def surfaces(self, width: int = 1049, empty_catalog: bool = False) -> list[dict]:
        return self.report(width, empty_catalog)["surfaces"]

    def surface(self, name: str, width: int = 1049, empty_catalog: bool = False) -> dict:
        found = next((item for item in self.surfaces(width, empty_catalog) if item["name"] == name), None)
        self.assertIsNotNone(found, f"{name} was not reached; got {[s['name'] for s in self.surfaces(width, empty_catalog)]}")
        assert found is not None
        return found

    def px(self, value: str, label: str = "") -> float:
        number = to_px(value)
        assert number is not None, f"{label} has no parsable size: {value!r}"
        return number

    def test_no_core_surface_renders_a_host_blue_default_button(self) -> None:
        for width in (1049, 900, 460):
            for item in self.surfaces(width):
                with self.subTest(surface=item["name"], width=width):
                    stray = [b for b in item["buttons"] if b["variant"] == "default" and not b["action"]]
                    self.assertEqual(stray, [], f"{item['name']} still paints host-blue primaries: {stray}")

    def test_no_core_surface_carries_two_primaries(self) -> None:
        for width in (1049, 900, 460):
            for item in self.surfaces(width):
                with self.subTest(surface=item["name"], width=width):
                    primaries = [b for b in item["buttons"] if b["action"] == "primary"]
                    self.assertLessEqual(len(primaries), 1, primaries)

    def test_courses_carries_exactly_its_new_course_primary(self) -> None:
        # H-160. "At most one" cannot catch a defect of omission, and H-151's live facts recorded
        # `primaryCount: 0` on the catalog — the surface a learner lands on had no primary at all.
        # UX_SPEC §4 names the Courses page-header primary: **New course**. Pin the one primary,
        # its label, and its lamp fill at every measured width.
        for width in (1049, 900, 460):
            with self.subTest(width=width):
                item = self.surface("courses", width)
                primaries = [b for b in item["buttons"] if b["action"] == "primary"]
                self.assertEqual([b["text"] for b in primaries], ["New course"], primaries)
                self.assertEqual(primaries[0]["background"], "var(--cb-lamp)", primaries[0])
                self.assertEqual(primaries[0]["color"], "var(--cb-on-lamp)", primaries[0])
                self.assertEqual(self.px(primaries[0]["minHeight"], "New course"), 44, primaries[0])

    def test_the_empty_catalog_keeps_exactly_one_primary(self) -> None:
        # The same header button is one eligibility check, not an unconditional render: an empty
        # profile shows the welcome, whose own primary replaces it. Two primaries here would mean
        # the catalog's new primary double-painted the first-run screen.
        for width in (1049, 460):
            with self.subTest(width=width):
                item = self.surface("courses", width, empty_catalog=True)
                primaries = [b for b in item["buttons"] if b["action"] == "primary"]
                self.assertEqual(len(primaries), 1, primaries)
                self.assertNotEqual(primaries[0]["text"], "New course", primaries)
                self.assertEqual(
                    [b for b in item["buttons"] if b["text"] == "New course"], [],
                    "the route header kept its New course action beside the welcome's primary",
                )

    def test_the_primary_is_the_lamp_field_at_44_px(self) -> None:
        seen = 0
        for item in self.surfaces():
            for button in item["buttons"]:
                if button["action"] != "primary":
                    continue
                seen += 1
                if button["disabled"]:
                    # A disabled primary is honest paper, not a lamp field that still invites a click.
                    self.assertEqual(button["background"], "var(--cb-paper)", button)
                    continue
                self.assertEqual(button["background"], "var(--cb-lamp)", button)
                self.assertEqual(button["color"], "var(--cb-on-lamp)", button)
                self.assertEqual(self.px(button["minHeight"], button["text"]), 44, button)
        self.assertGreater(seen, 0, "no primary action rendered on any surface")

    def test_every_variant_meets_its_target(self) -> None:
        floors = {"primary": 44, "secondary": 44, "tertiary": 24, "row": 44}
        for item in self.surfaces():
            for button in item["buttons"]:
                action = button["action"]
                if not action:
                    continue
                with self.subTest(surface=item["name"], text=button["text"]):
                    self.assertGreaterEqual(self.px(button["minHeight"], button["text"]), floors[action], button)

    def test_every_authored_action_stays_above_the_24_px_floor(self) -> None:
        for item in self.surfaces():
            for button in item["buttons"]:
                if not button["action"]:
                    continue
                with self.subTest(surface=item["name"], text=button["text"]):
                    self.assertGreaterEqual(self.px(button["minHeight"], button["text"]), 24, button)

    def test_the_row_variant_is_full_width_and_left_aligned(self) -> None:
        rows = [b for item in self.surfaces() for b in item["buttons"] if b["action"] == "row"]
        self.assertTrue(rows, "the home route rendered no row action")
        for row in rows:
            self.assertIn("w-full", row["className"], row)
            self.assertIn("justify-start", row["className"], row)

    def test_the_route_h1_is_the_only_display_heading(self) -> None:
        # jsdom drops the `clamp()` display value, so the byte-level claim is made here and the
        # rendered half only has to prove there is one h1 and no other large heading.
        #
        # Merge reconciliation (H-148/H-149 over H-151): the player's close plate is a real
        # completion moment and H-149 gives it the display step, so the byte-level count is two —
        # the route h1 and that one close heading — and never more.
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertEqual(source.count("fontSize: CB_TYPE.display"), 2)
        self.assertIn("'data-cb-page-title': '',", source)
        self.assertIn("'data-cb-player-close': '',", source)
        for item in self.surfaces():
            with self.subTest(surface=item["name"]):
                h1s = [h for h in item["headings"] if h["tag"] == "h1"]
                if not h1s:
                    # Section and Course Detail are panes under the route's own h1, not pages.
                    continue
                self.assertEqual(len(h1s), 1, h1s)
                self.assertTrue(h1s[0]["pageTitle"], h1s[0])
                big = [h for h in item["headings"] if h["tag"] != "h1" and (to_px(h["fontSize"]) or 0) >= 36]
                self.assertEqual(big, [], f"{item['name']} has a plate competing with the page h1: {big}")

    def test_plate_heads_are_heading_not_display(self) -> None:
        for item in self.surfaces():
            for head in item["headings"]:
                if head["plateHead"]:
                    with self.subTest(surface=item["name"], text=head["text"]):
                        self.assertEqual(to_px(head["fontSize"]), 24, head)

    def test_every_codicon_is_sixteen_or_twenty(self) -> None:
        for item in self.surfaces():
            for size in item["icons"]:
                with self.subTest(surface=item["name"]):
                    self.assertIn(size, ("1rem", "1.25rem"), size)

    def test_no_measurement_is_zero_by_zero(self) -> None:
        # Every rendered action declares a target; the live rig measures painted boxes, but a
        # missing min-height here is how a 0x0 control starts.
        for item in self.surfaces():
            for button in item["buttons"]:
                if button["action"]:
                    self.assertIsNotNone(to_px(button["minHeight"]), button)

    def test_the_section_route_wraps_its_widest_tokens_at_460_200_percent(self) -> None:
        # H-160. The live frame at a 460 px window and a 32 px root measured `routeOverflowX: 53`
        # on the section route: three unbreakable tokens were wider than the pane. jsdom has no
        # layout, so this pins the declarations that removed the overflow; the number itself is
        # re-taken by `scripts/h151-action-capture.mjs`, which now prints `routeOverflowX` for
        # every surface and for the 200% frame.
        #
        #   wordmark   "COURSEBOOK" at 28 px + 0.14em tracking = 239 px (pane 215, content 170)
        #   page title "Course" at the display step (72 px at a 32 px root)
        #   breadcrumb the course title in a host text button: shrink-0 + whitespace-nowrap = 790 px
        source = PLUGIN_JS.read_text(encoding="utf-8")
        for anchor in ("'data-cb-wordmark': ''", "'data-cb-page-title': ''"):
            with self.subTest(anchor=anchor):
                start = source.index(anchor)
                block = source[start : start + 1600]
                self.assertIn("overflowWrap: 'anywhere'", block)
                self.assertIn("minWidth: 0", block)
        section = self.surface("section")
        crumbs = [b for b in section["buttons"] if b["breadcrumb"] == "sections"]
        self.assertEqual(len(crumbs), 1, crumbs)
        crumb = crumbs[0]
        # A breadcrumb is prose: it must ask for a Coursebook variant and declare that it wraps,
        # rather than inherit the host button's `shrink-0 whitespace-nowrap`.
        self.assertEqual(crumb["action"], "tertiary", crumb)
        self.assertRegex(crumb["styleAttr"], r"white-space:\s*normal", crumb["styleAttr"])
        self.assertRegex(crumb["styleAttr"], r"flex-shrink:\s*1", crumb["styleAttr"])



if __name__ == "__main__":
    unittest.main()
