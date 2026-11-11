"""GM-002 — the global Home launcher and the course-home split (v3 Home, CP-022).

Global Home answers one question ("what do I want to learn now?") and is a library, not a course
page. The selected course's home keeps the trailhead and Continue and is reached only from Home by
opening that course. These tests render the shipped module through React:

  * `CoursebookHome` (static render) — CP-022 replaced the composition with the v3 Home
    (SPEC-V3 §5.1): one threshold band, one filled `Start a new course` pill plus one quiet
    `Browse library` pill, a `ShelfPlank` of four card-fact courses with `See all`, and the copy
    deck's own strings (`docs/concept-parity/COPY.md` §2). The static cases below therefore assert
    the v3 shape, not the retired v2 card (six cards, a goal paragraph, `Browse the library`);
  * the real route in jsdom for the Home -> course home -> back walkthrough, so "global Home never
    silently becomes a course home" is a behaviour, not a comment.

The migration of this module is recorded per assertion in
`docs/concept-parity/GATE-MIGRATION.md` §4 (class V2/S, where it reads now, v3 counterpart). The
behavioural `HomeSplitRouteTest` and the focus-ring case are unchanged by that migration: they
assert behaviour, not composition.

What this does not prove: that a live backend returns these rows or that the pixels match the
concept frame. The live rig and `docs/visual-review/gm-002/` carry those.
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

STATIC_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
// These assertions are about the compact Home. Pin the viewport below the 1200 px scene
// breakpoint so a wide-route scene does not answer a compact-layout question. The width must be
// set before plugin.js is evaluated, so the import is dynamic (a static import would hoist).
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
const { CoursebookHome, FieldDeskHome, buildDeskModel, cbShelfEdgeMask } = await import('./plugin.js')

const lib = (rows, overrides = {}) => ({
  items: rows,
  next_cursor: null,
  total: rows.length,
  empty_reason: rows.length ? null : 'no_courses',
  applied_filter: 'all',
  ...overrides
})

if (payload.kind === 'shelf-mask') {
  const mask = cbShelfEdgeMask(payload.scrollLeft, payload.clientWidth, payload.scrollWidth)
  process.stdout.write(JSON.stringify({ mask }))
} else if (payload.kind === 'course-home') {
  const desk = buildDeskModel({
    library: lib(payload.rows),
    outline: payload.outline || null,
    estimate: null,
    selectedCourseId: payload.rows[0] ? payload.rows[0].course_id : null,
    outlineState: payload.outline ? 'ready' : 'idle'
  })
  const html = renderToStaticMarkup(
    React.createElement('div', null,
      React.createElement(FieldDeskHome, {
        desk,
        libraryStatus: 'ready',
        libraryError: null,
        stale: false,
        busy: false,
        notice: null,
        online: true,
        onRetry: () => {},
        onCreate: null,
        onSyllabus: null,
        onPrimary: () => {},
        onOpenSection: () => {},
        onSeePlan: () => {},
        onRetryEstimate: () => {},
        onSelectCourse: () => {},
        onOpenStudio: () => {},
        onOpen: () => {},
        onShowAll: () => {},
        sourcesOpen: false,
        onToggleSources: () => {},
        sourcesStatus: 'idle',
        sourcesError: null,
        sources: null,
        onRetrySources: () => {},
        outlineStatus: payload.outline ? 'ready' : 'idle',
        outlineError: null,
        onRetryOutline: () => {},
        implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'notebook.list']),
        onBrowseLibrary: () => {},
        companionEnabled: false
      })
    )
  )
  process.stdout.write(html)
} else {
  const html = renderToStaticMarkup(
    React.createElement('div', null,
      React.createElement(CoursebookHome, {
        library: {
          status: payload.status || 'ready',
          data: payload.status === 'idle' ? null : lib(payload.rows || [], payload.libraryOverrides || {}),
          error: payload.error || null,
          stale: Boolean(payload.stale)
        },
        modes: payload.modes || {},
        modesSupported: payload.modesSupported !== false,
        online: payload.online !== false,
        canCreate: payload.canCreate !== false,
        onStartCreate: () => {},
        onBrowseLibrary: () => {},
        onOpenCourse: () => {},
        onShowAll: () => {},
        onRetry: () => {}
      })
    )
  )
  process.stdout.write(html)
}
"""

ROUTE_HARNESS = r"""
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
  implemented_methods: ['library.list', 'course.outline', 'notebook.list', 'lesson.page', 'world.read', 'course.create'],
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
const flush = async (ms = 80) => { await act(async () => { await new Promise((r) => setTimeout(r, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const errors = []
const originalError = console.error
console.error = (...args) => { errors.push(args.map((a) => String(a)).join(' ')); originalError(...args) }

await act(async () => { root.render(route.render()) })
await flush(220)

const facts = {}
facts.fresh = {
  home: Boolean(document.querySelector('[data-cb-home]')),
  courseHome: Boolean(document.querySelector('[data-cb-course-home]')),
  desk: Boolean(document.querySelector('[data-cb-desk]')),
  continuePlate: Boolean(document.querySelector('[data-cb-continue]')),
  cards: [...document.querySelectorAll('[data-cb-home-card]')].map((n) => text(n).slice(0, 120)),
  title: text(document.querySelector('[data-cb-page-title]')),
  createButtons: [...document.querySelectorAll('[data-cb-home] button')]
    .filter((b) => /start a new course/i.test(text(b))).length
}

const primary = document.querySelector('[data-cb-action="primary"]')
if (primary) {
  await act(async () => { primary.dispatchEvent(new window.FocusEvent('focusin', { bubbles: true })) })
  await flush(40)
  const style = window.getComputedStyle(primary)
  facts.focus = {
    label: text(primary),
    ring: primary.getAttribute('data-cb-focus-ring'),
    outline: style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor
  }
}

const firstCard = document.querySelector('[data-cb-home-card] button')
const clickedTitle = firstCard ? text(firstCard.closest('[data-cb-home-card]').querySelector('h3')) : ''
if (firstCard) {
  await act(async () => { firstCard.click() })
  await flush(600)
}
facts.opened = {
  clickedTitle,
  home: Boolean(document.querySelector('[data-cb-home]')),
  courseHome: Boolean(document.querySelector('[data-cb-course-home]')),
  continuePlate: Boolean(document.querySelector('[data-cb-continue]')),
  desk: (document.querySelector('[data-cb-desk]') || {}).getAttribute
    ? document.querySelector('[data-cb-desk]').getAttribute('data-cb-desk')
    : null,
  courseTitle: text(document.querySelector('[data-cb-desk-course]')),
  errors: errors.slice(-3),
  wrapperChildren: (document.querySelector('[data-cb-course-home]') || {}).childElementCount,
  wrapperText: text(document.querySelector('[data-cb-course-home]')),
  wrapperHtml: ((document.querySelector('[data-cb-course-home]') || {}).outerHTML || '').slice(0, 400),
  back: Boolean([...document.querySelectorAll('button')].find((b) => /back to home/i.test(text(b)))),
  title: text(document.querySelector('[data-cb-page-title]'))
}

const back = [...document.querySelectorAll('button')].find((b) => /back to home/i.test(text(b)))
if (back) {
  await act(async () => { back.click() })
  await flush(260)
}
facts.back = {
  home: Boolean(document.querySelector('[data-cb-home]')),
  courseHome: Boolean(document.querySelector('[data-cb-course-home]')),
  continuePlate: Boolean(document.querySelector('[data-cb-continue]'))
}

process.stdout.write(JSON.stringify(facts))
"""


def row(index: int, **overrides) -> dict:
    value = {
        "enrollment_id": f"enr_{index:016x}",
        "course_id": f"crs_{index:016x}",
        "title": f"Course number {index}",
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
            "current_objective_id": f"obj_{index:016x}",
        },
        "warning": None,
        "updated_at": f"2026-11-0{min(index + 1, 9)}T18:00:00.000000+00:00",
        "revision": 1,
    }
    value.update(overrides)
    return value


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-gm002-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        for name, source in (("static.mjs", STATIC_HARNESS), ("route.mjs", ROUTE_HARNESS)):
            (cls.root / name).write_text(source, encoding="utf-8")
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

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_node(self, script: str, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / script), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return result.stdout

    def home(self, **payload) -> str:
        return self.run_node("static.mjs", {"kind": "home", **payload})


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class CoursebookHomeTest(Base):
    def test_home_is_not_course_bound(self) -> None:
        html = self.home(rows=[row(1), row(2)])
        self.assertIn('data-cb-home="', html)
        self.assertNotIn("data-cb-continue", html)
        self.assertNotIn("data-cb-trailhead", html)
        self.assertNotIn("data-cb-desk", html)
        self.assertNotIn(">Continue<", html)
        self.assertNotIn("CONTINUE THE TRAIL", html)

    def test_empty_home_has_one_create_action(self) -> None:
        # v3 (SPEC-V3 §5.1 H3, SPEC §3.10): one filled pill and one quiet pill. The quiet pill is
        # the copy deck's `home.secondary` ("Browse library"); the v2 wording "Browse the library"
        # was never a deck row and is retired with the six-card shelf.
        html = self.home(status="ready", rows=[])
        self.assertIn('data-cb-home="empty"', html)
        self.assertEqual(html.count("Start a new course"), 1, "the empty home repeated its create action")
        self.assertNotIn(">New course<", html, "the shelf carried a second create control")
        self.assertIn("No courses yet.", html)
        self.assertIn("Browse library", html)
        self.assertNotIn("Browse the library", html, "the v2 secondary label survived beside the deck row")
        self.assertEqual(html.count('data-cb-home-secondary=""'), 1, "the quiet pill is one control")

    def test_home_has_no_fake_rating_or_xp(self) -> None:
        html = self.home(rows=[row(1), row(2), row(3)])
        lowered = html.lower()
        for banned in (r"\bstars?\b", r"\brating", "recently played", r"\bxp\b", "streak", "mastery", r"\blevel\b"):
            self.assertIsNone(re.search(banned, lowered), f"global Home invented a {banned!r} claim")

    def test_shelf_shows_four_authored_cards_and_see_all(self) -> None:
        # SPEC-V3 §3.3 / §5.1 H5: the shelf is the first viewport, four cards at wide, and a fifth
        # course moves behind `See all`. The four are the newest rows (hub order); the older rows
        # are reached from Courses, so their titles are not painted here.
        html = self.home(rows=[row(index) for index in range(1, 8)])
        self.assertEqual(html.count('data-cb-home-card=""'), 4, "the v3 shelf holds four cards")
        self.assertIn('data-cb-home-see-all=""', html, "an overflowing shelf must offer See all")
        self.assertIn("See all", html)
        self.assertIn("Course number 7", html)
        self.assertIn("Course number 4", html, "the fourth card of the four-card shelf was dropped")
        self.assertNotIn("Course number 3", html, "the oldest courses belong behind See all")

    def mask(self, scroll_left: float, client_width: float, scroll_width: float) -> dict:
        payload = json.loads(
            self.run_node(
                "static.mjs",
                {
                    "kind": "shelf-mask",
                    "scrollLeft": scroll_left,
                    "clientWidth": client_width,
                    "scrollWidth": scroll_width,
                },
            )
        )
        return payload["mask"]

    def test_shelf_edge_mask_marks_overflow_on_the_right(self) -> None:
        # GM-VISUAL-SPEC §2.5: a shelf that overflows draws a 24px paper→transparent mask at the
        # edge with content behind it, so a clipped card reads "the shelf continues" rather than
        # a hard cut. matrix.json's overflow cell asserts this affordance.
        mask = self.mask(0, 938, 1496)
        self.assertEqual(mask["state"], "right")
        self.assertIn("calc(100% - 24px)", mask["style"]["maskImage"])
        self.assertIn("transparent 100%", mask["style"]["maskImage"])
        self.assertEqual(mask["style"]["WebkitMaskImage"], mask["style"]["maskImage"])
        self.assertEqual(mask["style"]["maskRepeat"], "no-repeat")

    def test_shelf_edge_mask_tracks_both_edges_and_the_end(self) -> None:
        middle = self.mask(300, 938, 1496)
        self.assertEqual(middle["state"], "both", "a mid-scroll shelf has content behind both edges")
        self.assertIn("transparent 0", middle["style"]["maskImage"])
        end = self.mask(558, 938, 1496)
        self.assertEqual(end["state"], "left", "at the end only the left edge has more content")
        self.assertNotIn("transparent 100%", end["style"]["maskImage"])

    def test_shelf_edge_mask_is_absent_when_the_shelf_fits(self) -> None:
        mask = self.mask(0, 938, 900)
        self.assertEqual(mask["state"], "none")
        self.assertEqual(mask["style"], {})

    def test_shelf_row_declares_its_mask_state(self) -> None:
        # Static render cannot measure layout, so the row starts honest at `none`; the live
        # capture asserts the measured `right`/`both` state and the painted fade.
        html = self.home(rows=[row(index) for index in range(1, 4)])
        self.assertRegex(html, r'data-cb-home-shelf-row=""[^>]*data-cb-shelf-mask="none"')

    def test_card_does_not_repeat_the_next_step_as_a_goal(self) -> None:
        # A shelf row with no stored goal or subtitle must print the next-step sentence once, not
        # once in the meta row and again in the goal paragraph (the fallback duplicated it).
        html = self.home(rows=[row(1, title="Engine diagnostics", subtitle=None,
                                   next_step={"kind": "review_plan", "label": "Review the plan"})])
        self.assertEqual(html.count("Review the plan"), 1,
                         "the shelf card printed its next step twice")

    def test_card_does_not_repeat_its_title_as_the_goal(self) -> None:
        # GM-002's card built a goal paragraph from `subtitle`, which repainted the title when the
        # two were equal. SPEC-V3 §3.6 replaces that with one metadata pattern — title, one subject
        # chip, one evidence line, the backend's next step — so the v3 card has no goal element and
        # no render path for `subtitle`. The claim survives as three assertions: the retired marker
        # never returns, a title-equal subtitle cannot repaint the title, and a real subject prints
        # exactly once.
        repeated = self.home(rows=[row(1, title="Engine diagnostics", subtitle="Engine diagnostics")])
        self.assertNotIn("data-cb-home-card-goal", repeated,
                         "the retired v2 goal paragraph returned to the v3 card")
        painted = re.sub(r"<[^>]*>", " ", repeated)
        self.assertEqual(painted.count("Engine diagnostics"), 1,
                         "the v3 card painted its title twice")
        distinct = self.home(rows=[row(1, title="Engine diagnostics", subtitle="Find the misfire fast")])
        self.assertNotIn("data-cb-home-card-goal", distinct, "the v3 card has no goal paragraph")
        self.assertNotIn("Find the misfire fast", distinct,
                         "the v3 card must not paint `subtitle`; the subject chip is `subject_label`")
        subject = self.home(rows=[row(1, title="Engine diagnostics", subject_label="Small engines")])
        self.assertEqual(subject.count('data-cb3-chip="subject"'), 1,
                         "the card must carry exactly one subject chip")
        self.assertIn("Small engines", subject)

    def test_card_prints_its_title_once(self) -> None:
        # The card paints its title as an <h3>. The typographic paper cover used to print the same
        # string again above it, so every shelf card read as title → title. Count painted text
        # only (strip tags, so the `Open <title>` aria-label is not counted).
        title = "Small-engine maintenance"
        html = self.home(rows=[row(1, title=title)])
        painted = re.sub(r"<[^>]*>", " ", html)
        self.assertEqual(painted.count(title), 1,
                         f"the shelf card printed its title {painted.count(title)} times in painted text")

    def test_card_shows_real_next_step_and_mode_badge(self) -> None:
        html = self.home(
            rows=[row(1, title="Small-engine maintenance", next_step={"kind": "resume_lesson", "label": "Resume this lesson"})],
            modes={"crs_0000000000000001": {"state": "ready", "mode": "game"}},
        )
        self.assertIn("Small-engine maintenance", html)
        self.assertIn("Resume this lesson", html)
        self.assertIn("Game", html)

    def test_a_failed_read_is_not_an_empty_library(self) -> None:
        html = self.home(status="error", rows=[], error={"code": "HOST_UNAVAILABLE", "message": "backend is down"})
        self.assertIn('data-cb-home="error"', html)
        self.assertNotIn("No courses yet.", html, "a failed read was painted as an empty library")
        self.assertIn("could not be read", html)
        self.assertIn("Try again", html)

    def test_loading_keeps_the_shelf_geometry(self) -> None:
        html = self.home(status="loading", rows=[])
        self.assertIn('data-cb-home="loading"', html)
        self.assertIn("data-cb-home-shelf", html)
        self.assertNotIn("No courses yet.", html)

    def test_offline_says_so_without_inventing_courses(self) -> None:
        # SPEC-V3 §4: the banner speaks the copy deck's `home.offline.title` ("You are offline"),
        # not the v2 literal "Offline". The marker and the word are both pinned: the strip must
        # exist, and it must carry the deck's own sentence rather than a bare adjective.
        html = self.home(online=False, rows=[row(1)])
        self.assertIn("data-cb-home-offline", html)
        self.assertIn('data-cb-home-offline-word=""', html)
        self.assertIn("You are offline", html)
        self.assertIn("Your shelf is here. New lessons wait until you reconnect.", html)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class CourseHomeTest(Base):
    def test_course_home_retains_continue(self) -> None:
        outline = {
            "enrollment_id": "enr_0000000000000001",
            "plan": {"plan_id": "pln_1", "version": 1, "state": "approved", "plan_hash": "sha256:" + "b" * 64},
            "objectives": [
                {
                    "objective_id": "obj_0000000000000001",
                    "ordinal": 1,
                    "title": "Name the three things an engine needs",
                    "evidence_target": "recall",
                    "state": "introduced",
                    "check_state": "none",
                    "attempt_count": 0,
                    "independent": False,
                    "last_opened_at": None,
                }
            ],
            "total": 1,
            "truncated": False,
        }
        html = self.run_node(
            "static.mjs",
            {"kind": "course-home", "rows": [row(1)], "outline": outline},
        )
        self.assertIn("data-cb-continue", html)
        self.assertIn("data-cb-trailhead", html)
        self.assertIn("data-cb-desk-course", html)
        self.assertIn("Course number 1", html)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class HomeSplitRouteTest(Base):
    def test_home_course_back_walkthrough(self) -> None:
        outline = {
            "enrollment_id": "enr_0000000000000001",
            "plan": {"plan_id": "pln_1", "version": 1, "state": "approved", "plan_hash": "sha256:" + "b" * 64},
            "objectives": [
                {
                    "objective_id": "obj_0000000000000001",
                    "ordinal": 1,
                    "title": "Name the three things an engine needs",
                    "evidence_target": "recall",
                    "state": "introduced",
                    "check_state": "none",
                    "attempt_count": 0,
                    "independent": False,
                    "last_opened_at": None,
                }
            ],
            "total": 1,
            "truncated": False,
        }
        first = row(1, title="Small-engine maintenance")
        second = row(2, title="Japanese for the field")
        rows = {"items": [first, second], "next_cursor": None, "total": 2, "empty_reason": None, "applied_filter": "all"}
        facts = json.loads(
            self.run_node(
                "route.mjs",
                {
                    "width": 1049,
                    "responses": {
                        "library.list": rows,
                        "course.outline": outline,
                        "notebook.list": {"entries": [], "total": 0},
                        "world.read": {"course_id": first["course_id"], "presentation_mode": "game", "world": None, "fallback": None, "revision": 1},
                    },
                },
            )
        )
        fresh, opened, back = facts["fresh"], facts["opened"], facts["back"]
        self.assertTrue(fresh["home"], "global Home did not mount the library launcher")
        self.assertFalse(fresh["courseHome"], "global Home mounted a course home")
        self.assertFalse(fresh["continuePlate"], "global Home carried a Continue plate")
        self.assertEqual(fresh["createButtons"], 1, "the empty home must carry exactly one create action")
        self.assertGreaterEqual(len(fresh["cards"]), 2, fresh["cards"])

        self.assertFalse(opened["home"], "opening a course left the global shelf mounted")
        self.assertTrue(opened["courseHome"], "opening a course did not mount the course home")
        self.assertTrue(opened["continuePlate"], f"the course home lost its Continue plate: {opened}")
        self.assertIn(opened["clickedTitle"], opened["courseTitle"])
        self.assertTrue(opened["clickedTitle"], "the shelf card had no title")
        self.assertTrue(opened["back"], "the course home has no way back to Home")

        self.assertTrue(back["home"], "Back to Home did not restore the library launcher")
        self.assertFalse(back["courseHome"], "Back to Home left the course home mounted")
        self.assertFalse(back["continuePlate"], "Back to Home kept the Continue plate")

    def test_primary_action_paints_the_authored_focus_ring(self) -> None:
        # README §1 rule 6: the keyboard focus capture must show the 2px accent ring on the
        # primary control. That ring is authored in CbAction, not left to the UA default.
        first = row(1, title="Small-engine maintenance")
        rows = {"items": [first], "next_cursor": None, "total": 1, "empty_reason": None, "applied_filter": "all"}
        facts = json.loads(
            self.run_node(
                "route.mjs",
                {
                    "width": 1049,
                    "responses": {
                        "library.list": rows,
                        "world.read": {"course_id": first["course_id"], "presentation_mode": "textbook",
                                       "world": None, "fallback": None, "revision": 1},
                    },
                },
            )
        )
        focus = facts.get("focus")
        self.assertTrue(focus, "global Home had no primary action to focus")
        self.assertEqual(focus["ring"], "visible", focus)
        self.assertTrue(focus["outline"].startswith("solid 2px"), focus["outline"])
