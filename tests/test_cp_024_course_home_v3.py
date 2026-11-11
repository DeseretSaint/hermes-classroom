"""CP-024 — the v3 course home (R-MAP), executed rather than read.

The card's contract, in executable form:

* the route nodes are **real DOM buttons** placed on the normalised anchors the plate's manifest
  declares, each with its section's own title, its state word, and `aria-current="step"` on the
  current one — never an ornament, never a position the renderer invented;
* a plate with **no usable anchors** (none at all, a malformed entry, or an anchor set that leaves
  a section unplaced) and every route narrower than **900 px** fall back to the complete vertical
  `StampNode` route, so no section becomes unreachable;
* the surface carries **exactly one filled control**, and its label is the backend's own
  `next_step.label` — including the plan-review and course-complete steps.

What this does NOT prove: that a browser paints the composition, that the plate's art reads as
paper, that the 268 px aside holds its measure at 1049, or that a learner understands the route.
Those are the card's live captures and the reviewer's rubric (``docs/concept-parity/gate/RUBRIC-V3.md``).
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
SEGMENT = ROOT / "desktop" / "src" / "90-course.js"
COPY = ROOT / "docs" / "concept-parity" / "COPY.md"

#: The deck rows this surface may render. A literal in the segment that is not one of these (or a
#: backend field the deck names for it) is copy the screen does not own.
DECK_ARCHETYPES = (
    "Back to {parent}",
    "Your route",
    "You are here",
    "Done",
    "Next",
    "Opens after the section before it",
    "Continue",
    "Evidence",
    "{n} of {total} sections have evidence",
    "Your other courses",
    "No scene yet",
    "The lesson works without art.",
)

#: The two state-specific rows are asserted in `test_course_home_v3_one_primary`, on the case that
#: renders them: a plan in review and a completed course.
STATE_DECK_ROWS = (
    "The plan is waiting for you",
    "Read it, then approve it so lessons can start.",
    "Course complete",
    "Every section has evidence.",
)

#: What the surface may never print. Each one is a concept-frame artefact or a fabricated metric.
BANNED = ("xp", "streak", "★", "☆", "rating", "review_count", "%", "proofs", "learner_count")

#: Test-only export block appended to the *staged copy* of `desktop/plugin.js`. CP-024 owns
#: `desktop/src/90-course.js` only. **CP-040's seam now exports the course-home names itself**, so
#: re-exporting them here is a `SyntaxError: Duplicate export` at module evaluation (which is what
#: this shim used to do after the union). Only a name the module does *not* export may be added;
#: importing a name the module does not define still fails at evaluation, so the shim cannot hide a
#: missing symbol.
EXPORT_SHIM = """

// --- CP-024 test export shim (staged copy only; the repo module is not edited) ---
// CP-040 moved CourseHomeV3, CourseRouteList, CourseRouteMapNode, CB3_COURSE_COPY, cb3CourseNodes,
// cb3CourseRoutePlan, cb3CoursePlateAnchors, cb3CourseHeroPlate, cb3CourseWorldPosture and
// cb3CourseEvidenceLine into the module's single export block. `CourseDetail` is the one name the
// composite screen mounts that the seam does not export, so it is the only one staged here.
export {
  CourseDetail
};
"""

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
// Set BEFORE the module import: the SDK stub reads the viewport atom at module evaluation, and a
// static import would hoist above this assignment. The primitives read that atom, not a prop.
globalThis.__CB_TEST_WIDTH__ = String(payload.width)
const mod = await import('./plugin.js')
const h = React.createElement

const width = payload.width
const out = { width, cases: {}, logic: {} }

for (const [name, fixture] of Object.entries(payload.cases)) {
  const html = renderToStaticMarkup(
    h(mod.CourseHomeV3, {
      row: fixture.row,
      objectives: fixture.objectives,
      page: fixture.page,
      plate: fixture.plate,
      anchors: fixture.anchors,
      others: fixture.others,
      sectionsDone: fixture.row.sections_done,
      sectionsTotal: fixture.row.sections_total,
      parentLabel: 'Home',
      width,
      busy: false,
      worldState: fixture.worldState || null,
      readState: fixture.readState || 'ready',
      onBack: () => {},
      onContinue: () => {},
      onOpenPlan: () => {},
      onOpenSection: () => {},
      onOpenStudio: fixture.studio ? () => {} : undefined
    })
  )
  out.cases[name] = html
  // DOM order, as the markup emits it: plate → route → aside. Read from the string so the order
  // is checked on every case, at every width, not only on the one a screenshot happened to show.
  const at = (needle) => html.indexOf(needle)
  out.order = out.order || {}
  out.order[name] = {
    plate: at('data-cb-course-plate="'),
    route: at('data-cb-course-route="list"'),
    aside: at('data-cb-course-aside')
  }
}

// Negative control: the one-primary counter must read two when a composition really has two.
out.logic.twoPrimaries = renderToStaticMarkup(
  h('div', null, [
    h(mod.PillAction, { key: 'a', variant: 'primary', label: 'One', onClick: () => {} }),
    h(mod.PillAction, { key: 'b', variant: 'primary', label: 'Two', onClick: () => {} })
  ])
)

// The pure helpers, called directly: the fallback decision is a function of the plate, not of a
// screenshot.
const objectives = payload.probe.objectives
const nodes = mod.cb3CourseNodes({ objectives, row: payload.probe.row, page: payload.probe.page })
out.logic.nodes = nodes
out.logic.states = nodes.map((node) => node.state)
out.logic.planFull = mod.cb3CourseRoutePlan({ nodes, anchors: payload.probe.anchors, width: 1049 })
out.logic.planNarrow = mod.cb3CourseRoutePlan({ nodes, anchors: payload.probe.anchors, width: 899 })
out.logic.planNone = mod.cb3CourseRoutePlan({ nodes, anchors: [], width: 1049 })
out.logic.planPartial = mod.cb3CourseRoutePlan({
  nodes,
  anchors: payload.probe.anchors.slice(0, 3),
  width: 1049
})
out.logic.planFarAnchor = mod.cb3CourseRoutePlan({
  nodes,
  anchors: payload.probe.anchors.concat([{ key: 'obj-not-here', x: 0.5, y: 0.5 }]),
  width: 1049
})
out.logic.anchorsFromManifest = mod.cb3CoursePlateAnchors(
  { manifest: { route_anchors: payload.probe.anchors } },
  null
)
out.logic.anchorsMalformed = mod.cb3CoursePlateAnchors(
  {
    manifest: {
      route_anchors: [
        { x: 0.2, y: 0.2 },
        { objective_id: 'obj-1', x: 1.4, y: 0.2 },
        { objective_id: 'obj-2', x: 'left', y: 0.3 },
        { objective_id: 'obj-3', x: 0.5, y: -0.1 }
      ]
    }
  },
  null
)
// The live carrier: `world.read` returns the world brief, and the brief is where a plate's
// anchors travel today. Same shape, same normalisation, same refusal on a malformed entry.
out.logic.anchorsFromBrief = mod.cb3CoursePlateAnchors(
  { manifest: null, artifactId: null },
  { brief: { route_anchors: payload.probe.anchors } }
)
out.logic.anchorsFromBriefPlate = mod.cb3CoursePlateAnchors(
  null,
  { brief: { plate: { route_anchors: payload.probe.anchors } } }
)
out.logic.posture = [
  'approved',
  'kit_ready',
  'kit_generating',
  'concepts_generating',
  'failed',
  'not_requested',
  'unavailable',
  'stale',
  null
].map((state) => mod.cb3CourseWorldPosture(state))
out.logic.evidence = [
  mod.cb3CourseEvidenceLine(2, 4),
  mod.cb3CourseEvidenceLine(0, 0),
  mod.cb3CourseEvidenceLine(NaN, 5)
]
out.logic.copy = mod.CB3_COURSE_COPY

process.stdout.write(JSON.stringify(out))
"""


def _objectives():
    return [
        {
            "objective_id": "obj-1",
            "title": "Order at the counter",
            "ordinal": 1,
            "independent": True,
            "state": "completed",
        },
        {
            "objective_id": "obj-2",
            "title": "Ask the price",
            "ordinal": 2,
            "independent": True,
            "state": "completed",
        },
        {"objective_id": "obj-3", "title": "Say what you want", "ordinal": 3, "state": "introduced"},
        {
            "objective_id": "obj-4",
            "title": "Thank the shopkeeper",
            "ordinal": 4,
            "state": "not_started",
        },
        {
            "objective_id": "obj-5",
            "title": "Ask for the bill",
            "ordinal": 5,
            "state": "not_started",
            "locked": True,
        },
    ]


def _anchors():
    return [
        {"objective_id": "obj-1", "x": 0.125, "y": 0.75},
        {"objective_id": "obj-2", "x": 0.375, "y": 0.5},
        {"objective_id": "obj-3", "x": 0.625, "y": 0.625},
        {"objective_id": "obj-4", "x": 0.775, "y": 0.375},
        {"section_id": "obj-5", "x": 0.925, "y": 0.625},
    ]


def _row(**overrides):
    row = {
        "course_id": "crs-1",
        "enrollment_id": "enr-1",
        "title": "Japanese Lantern District",
        "subject_label": "Language",
        "sections_done": 2,
        "sections_total": 5,
        "next_step": {"kind": "resume_lesson", "label": "Continue Say what you want"},
    }
    row.update(overrides)
    return row


def _page():
    return {"section": {"objective_id": "obj-3", "title": "Say what you want", "ordinal": 3}}


def _others():
    return [
        {"course_id": "crs-2", "title": "Braise like a kitchen", "next_step": {"label": "Start Section 1"}},
        {"course_id": "crs-3", "title": "Read a tide table", "next_step": {"label": "Continue Section 4"}},
        {"course_id": "crs-4", "title": "Splice a rope", "next_step": {"label": "Start Section 2"}},
        {"course_id": "crs-5", "title": "A fourth course", "next_step": {"label": "Start Section 1"}},
    ]


def _plate(anchors=None, src=None, credit=None):
    return {
        "artifactId": None,
        "src": src,
        "credit": credit,
        "anchors": _anchors() if anchors is None else anchors,
    }


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


class CourseHomeV3RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp024-")
        root = Path(cls.tmp.name)
        # CP-024 owns `desktop/src/90-course.js` only; the module export seam in `99-tutor.js` is
        # CP-040's step 2. So the names this test mounts are reached from the *staged copy* only —
        # an appended export block, never a repo edit. A name that does not exist in the module
        # throws at import time, so the shim cannot silently pass a missing symbol.
        (root / "plugin.js").write_text(
            PLUGIN_JS.read_text(encoding="utf-8") + EXPORT_SHIM, encoding="utf-8"
        )
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
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

        cases = {
            "default": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": _plate(),
                "anchors": None,
                "others": _others(),
            },
            "art": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": _plate(src="data:image/png;base64,AAAA", credit="Plate: the course's own studio"),
                "anchors": None,
                "others": _others(),
            },
            "noanchors": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": _plate(anchors=[]),
                "anchors": None,
                "others": _others(),
            },
            "malformed": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": {
                    "artifactId": None,
                    "src": None,
                    "credit": None,
                    "manifest": {
                        "route_anchors": [
                            {"x": 0.2, "y": 0.2},
                            {"objective_id": "obj-1", "x": 2.5, "y": 0.2},
                        ]
                    },
                },
                "anchors": None,
                "others": _others(),
            },
            "review": {
                "row": _row(
                    sections_done=0,
                    next_step={"kind": "review_plan", "label": "Review and approve the plan"},
                ),
                "objectives": _objectives(),
                "page": None,
                "plate": _plate(),
                "anchors": None,
                "others": [],
            },
            "complete": {
                "row": _row(
                    sections_done=5,
                    next_step={
                        "kind": "review_plan",
                        "label": "All sections have evidence; review the plan",
                    },
                ),
                "objectives": [
                    dict(item, independent=True, state="completed", locked=False)
                    for item in _objectives()
                ],
                # The last opened section is still named by the page; at the close it must still
                # read `Done`, not `You are here` (SPEC-V3 §5.4 course-end).
                "page": _page(),
                "plate": _plate(),
                "anchors": None,
                "others": [],
            },
            "noworld": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": _plate(anchors=[]),
                "anchors": [],
                "others": [],
            },
            "worldrunning": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": _plate(),
                "anchors": None,
                "others": [],
                "worldState": "kit_generating",
            },
            "worldrejected": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": _plate(),
                "anchors": None,
                "others": [],
                "worldState": "failed",
                "studio": True,
            },
            "loading": {
                "row": _row(),
                "objectives": [],
                "page": None,
                "plate": _plate(anchors=[]),
                "anchors": [],
                "others": [],
                "readState": "loading",
            },
            "readerror": {
                "row": _row(),
                "objectives": _objectives(),
                "page": _page(),
                "plate": _plate(anchors=[]),
                "anchors": [],
                "others": [],
                "readState": "error",
            },
        }
        probe = {
            "objectives": _objectives(),
            "row": _row(),
            "page": _page(),
            "anchors": _anchors(),
        }
        cls.reports = {}
        for width in (1049, 900, 460):
            case = root / f"case-{width}.json"
            case.write_text(
                json.dumps({"width": width, "cases": cases, "probe": probe}), encoding="utf-8"
            )
            result = subprocess.run(
                ["node", str(root / "harness.mjs"), str(case)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=240,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr[-6000:])
            cls.reports[width] = json.loads(result.stdout)
        cls.report = cls.reports[1049]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── 1. the nodes are DOM buttons on the declared anchors ──────────────────────────────────

    def test_course_home_v3_nodes_are_dom_buttons(self) -> None:
        html = self.report["cases"]["default"]
        self.assertIn('data-cb-course-home-v3="map"', html, "the wide course home is not in map mode")
        buttons = re.findall(r"<button[^>]*data-cb-course-node=\"[^\"]+\"[^>]*>", html)
        self.assertEqual(len(buttons), 5, f"the route rendered {len(buttons)} node buttons, not five")
        # Every node is a button with its own section title, and the state word is DOM text.
        for objective in _objectives():
            self.assertIn(f'data-cb-course-node="{objective["objective_id"]}"', html)
            self.assertIn(objective["title"], strip_tags(html), "a node lost its section title")
        # The route's deck row is the group's accessible name, in both modes.
        self.assertIn('aria-label="Your route"', html)
        self.assertIn('aria-label="Your route"', self.reports[900]["cases"]["default"])
        # The current node is marked by `aria-current` *and* by the deck's word.
        current = re.search(r"<button[^>]*data-cb-course-node=\"obj-3\"[^>]*>", html)
        self.assertIsNotNone(current, "the current section has no node")
        assert current is not None
        self.assertIn('data-cb-course-node-state="current"', current.group(0))
        self.assertIn('aria-current="step"', current.group(0))
        self.assertIn("You are here", html, "the current node is marked by colour alone")
        # The gated section is a disabled button, not a live link to a locked page.
        locked = re.search(r"<button[^>]*data-cb-course-node=\"obj-5\"[^>]*>", html)
        self.assertIsNotNone(locked)
        assert locked is not None
        self.assertIn("disabled", locked.group(0))
        self.assertIn("Opens after the section before it", html)
        # The upcoming section carries the deck's `Next` word, so the fourth state is never
        # conveyed by the icon alone.
        upcoming = re.search(r"<button[^>]*data-cb-course-node=\"obj-4\"[^>]*>(.*?)</button>", html, flags=re.S)
        self.assertIsNotNone(upcoming)
        assert upcoming is not None
        self.assertIn('data-cb-course-node-state="upcoming"', upcoming.group(0))
        self.assertIn("Next", strip_tags(upcoming.group(1)))
        # Position comes from the anchor, in percent of the plate — never a computed layout guess.
        self.assertIn('data-cb-course-anchor="0.1250,0.7500"', html)
        self.assertIn("left:12.500%", html)
        self.assertIn("top:75.000%", html)
        # The anchors of the fifth section still place it: a section is never dropped.
        self.assertIn('data-cb-course-anchor="0.9250,0.6250"', html)
        # Map mode draws no second route: the vertical list is the fallback alone.
        self.assertNotIn("data-cb3-stamp=", html, "map mode also rendered the fallback route")
        # The plate is a mounted mat: 8 px mat, 1 px ink rule, and the art is textless.
        self.assertIn('data-cb-course-plate="art"', self.report["cases"]["art"])
        art = self.report["cases"]["art"]
        self.assertIn('alt=""', art)
        self.assertIn('aria-hidden="true"', art)
        self.assertIn("Plate: the course&#x27;s own studio", art, "the art credit was dropped")

    # ── 2. the fallback is complete, not partial ──────────────────────────────────────────────

    def test_course_home_v3_anchor_fallback(self) -> None:
        logic = self.report["logic"]
        self.assertEqual(logic["planFull"]["mode"], "map")
        self.assertEqual(logic["planNarrow"]["mode"], "list", "a route under 900 px drew a map")
        self.assertEqual(logic["planNone"]["mode"], "list", "no anchors drew a map")
        self.assertEqual(logic["planPartial"]["mode"], "list", "a partial anchor set hid a section")
        self.assertEqual(
            logic["planFarAnchor"]["mode"], "map", "an anchor for another course's section broke the map"
        )
        self.assertEqual(
            logic["anchorsMalformed"], [], "a malformed anchor was clamped into a position"
        )
        self.assertEqual(len(logic["anchorsFromManifest"]), 5)
        # The carrier `world.read` actually returns: the world brief. The same normalisation runs,
        # so an anchored plate is a data question, not a rendering one.
        self.assertEqual(len(logic["anchorsFromBrief"]), 5)
        self.assertEqual(len(logic["anchorsFromBriefPlate"]), 5)
        self.assertEqual(
            logic["posture"],
            [
                "ready",
                "ready",
                "running",
                "running",
                "rejected",
                "none",
                "none",
                "running",
                "none",
            ],
            "a world state was mapped to the wrong plate posture",
        )

        for name in ("noanchors", "malformed"):
            html = self.report["cases"][name]
            self.assertIn(
                'data-cb-course-home-v3="list"', html, f"{name} kept the map instead of the fallback"
            )
            self.assertNotIn("data-cb-course-node=", html, f"{name} still placed a node on the art")
            stamps = re.findall(r"<button[^>]*data-cb3-stamp=\"[^\"]+\"[^>]*>", html)
            self.assertEqual(len(stamps), 5, f"{name} rendered {len(stamps)} route buttons, not five")
            self.assertIn("data-cb-course-route=\"list\"", html)
            for objective in _objectives():
                self.assertIn(objective["title"], strip_tags(html))

        # 900 is the boundary the card names: the map holds at exactly 900, and the vertical route
        # takes over one pixel below it (the pure plan above proves the 899 case).
        boundary = self.reports[900]["cases"]["default"]
        self.assertIn('data-cb-course-home-v3="map"', boundary)
        self.assertEqual(
            len(re.findall(r"<button[^>]*data-cb-course-node=\"[^\"]+\"[^>]*>", boundary)), 5
        )
        # And 460 keeps the complete vertical route.
        compact = self.reports[460]["cases"]["default"]
        self.assertIn('data-cb-course-home-v3="list"', compact)
        self.assertNotIn("data-cb-course-node=", compact)
        self.assertEqual(
            len(re.findall(r"<button[^>]*data-cb3-stamp=\"[^\"]+\"[^>]*>", compact)), 5
        )
        # SPEC-V3 §5.4 order, on every rendered case at every width: the plate first, the aside
        # last, and in list mode the route between them (a route that trails the aside puts M6
        # under M7–M9, which round 2 found at 460 and 900).
        for width, report in self.reports.items():
            order = report.get("order") or {}
            self.assertTrue(order, f"the {width} harness reported no DOM order")
            for name, marks in order.items():
                with self.subTest(width=width, case=name):
                    self.assertGreaterEqual(marks["plate"], 0)
                    self.assertGreater(marks["aside"], marks["plate"], marks)
                    if marks["route"] >= 0:
                        self.assertGreater(marks["route"], marks["plate"], marks)
                        self.assertLess(marks["route"], marks["aside"], marks)

    # ── 3. one primary, and it is the backend's own next step ─────────────────────────────────

    def test_course_home_v3_one_primary(self) -> None:
        # The counter is load-bearing: two filled controls in one composition must read as two.
        self.assertEqual(self.report["logic"]["twoPrimaries"].count('data-cb3-pill="primary"'), 2)

        for width, report in self.reports.items():
            for name in ("default", "art", "review", "complete", "noworld", "noanchors"):
                html = report["cases"][name]
                filled = re.findall(r"<button[^>]*data-cb3-pill=\"primary\"[^>]*>", html)
                self.assertEqual(
                    len(filled), 1, f"{name}@{width} carries {len(filled)} filled controls"
                )
                self.assertEqual(
                    html.count("cb3-primary"), 1, f"{name}@{width} painted a second filled control"
                )
                # It is the Continue plate, and its label is the backend's own next-step label.
                self.assertIn("data-cb-continue-action", filled[0])
                label = re.search(
                    r"<button[^>]*data-cb-continue-action[^>]*>.*?</button>", html, flags=re.S
                )
                self.assertIsNotNone(label)
                assert label is not None
                expected = {
                    "default": "Continue Say what you want",
                    "art": "Continue Say what you want",
                    "noanchors": "Continue Say what you want",
                    "noworld": "Continue Say what you want",
                    "review": "Review and approve the plan",
                    "complete": "All sections have evidence; review the plan",
                }[name]
                self.assertIn(expected, strip_tags(label.group(0)))

        # The review and completion steps swap the heading, not the action count.
        review = self.report["cases"]["review"]
        self.assertIn("The plan is waiting for you", review)
        self.assertIn("Read it, then approve it so lessons can start.", review)
        complete = self.report["cases"]["complete"]
        self.assertIn("Course complete", complete)
        self.assertIn("Every section has evidence.", complete)
        # At the close no node is left as the current step: every section reads Done, even the one
        # the page still names as last opened (SPEC-V3 §5.4 course-end).
        self.assertNotIn("You are here", complete, "a completed course still marks a current step")
        self.assertNotIn('data-cb-course-node-state="current"', complete)
        self.assertNotIn('aria-current="step"', complete)
        self.assertEqual(
            complete.count('data-cb-course-node-state="done"'), 5, "a completed node is not marked done"
        )
        self.assertNotIn("You are here", self.reports[460]["cases"]["complete"])

    # ── 4. the rest of the surface's honesty rules ────────────────────────────────────────────

    def test_course_home_v3_world_and_read_states(self) -> None:
        # world-running keeps the plate underneath and says what is happening; it never disables
        # Continue and never invents a second action.
        running = self.report["cases"]["worldrunning"]
        self.assertIn('data-cb-course-world-state="running"', running)
        self.assertIn("Painting the scene.", strip_tags(running))
        self.assertEqual(len(re.findall(r'data-cb3-pill="primary"', running)), 1)

        # world-rejected falls back to the typographic field, says so, and offers the deck's one
        # quiet way into the studio — never a filled control.
        rejected = self.report["cases"]["worldrejected"]
        self.assertIn('data-cb-course-world-state="rejected"', rejected)
        self.assertIn('data-cb-course-plate="type"', rejected)
        self.assertIn("This scene was not approved", strip_tags(rejected))
        self.assertIn('data-cb-course-world-studio', rejected)
        self.assertIn("Open World Studio", strip_tags(rejected))
        self.assertEqual(len(re.findall(r'data-cb3-pill="primary"', rejected)), 1)

        # Loading and a failed read each say their deck line and name one next action; neither
        # renders an empty course or a fabricated route.
        loading = self.report["cases"]["loading"]
        self.assertIn("Opening this course.", strip_tags(loading))
        self.assertNotIn("data-cb-course-node=", loading)
        error = self.report["cases"]["readerror"]
        self.assertIn("This course could not be read", strip_tags(error))
        self.assertIn("The route shows what was saved last. Try again.", strip_tags(error))
        self.assertEqual(len(re.findall(r'data-cb3-pill="primary"', error)), 1)
        # The error head does not eat the last recorded route: the sections are still listable.
        self.assertIn('data-cb-course-route="list"', error)

    def test_course_home_v3_copy_and_facts_only(self) -> None:
        html = self.report["cases"]["default"]
        text = strip_tags(html)
        for row in DECK_ARCHETYPES:
            literal = row.replace("{parent}", "Home").replace("{n} of {total} sections", "2 of 5 sections")
            if row == "Your route":
                # A screen-reader group name, not a visible line (SPEC-V3 §5.4 M5).
                self.assertIn('aria-label="Your route"', html, "the route lost its group name")
                continue
            self.assertIn(literal, text, f"the deck row `{row}` is missing from the screen")
        self.assertIn("Your other courses", text)
        # Three rows, each `{title} · {next step}` — the fourth course is not rendered.
        self.assertIn("Braise like a kitchen · Start Section 1", text)
        self.assertIn("Read a tide table · Continue Section 4", text)
        self.assertIn("Splice a rope · Start Section 2", text)
        self.assertNotIn("A fourth course", text, "the aside rendered more than three rows")
        self.assertIn("Language", text, "the course's subject line is missing")
        self.assertIn("2 of 5 sections have evidence", text)

        lowered = text.lower()
        for banned in BANNED:
            self.assertNotIn(banned, lowered, f"the course home prints a banned field: {banned}")

        # The no-world state names what is missing and does not pretend to have a plate.
        noworld = strip_tags(self.report["cases"]["noworld"])
        self.assertIn("No scene yet", noworld)
        self.assertIn("The lesson works without art.", noworld)

        # The fox is the course-home pose, inside its safe area, and absent below 620 px.
        self.assertIn('data-cb3-fox="point"', html)
        self.assertIn('aria-hidden="true"', re.search(r"<div[^>]*data-cb3-fox[^>]*>", html).group(0))
        self.assertEqual(self.reports[900]["cases"]["default"].count('data-cb3-fox="point"'), 1)
        self.assertNotIn(
            "data-cb3-fox=", self.reports[460]["cases"]["default"], "the fox renders below 620 px"
        )

        # No colour, unit or shadow recipe of its own: every value is a contract custom property.
        # Inline `data:` media is stripped first — base64 uses the same characters as CSS units.
        for report in self.reports.values():
            for name, case in report["cases"].items():
                markup = re.sub(r"data:[a-z/+.-]+;base64,[A-Za-z0-9+/=]+", "", case)
                self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", markup), f"{name} carries a hex")
                self.assertIsNone(
                    re.search(r"\d(?:\.\d+)?vw\b", markup), f"{name} carries a viewport unit"
                )
                self.assertNotIn("box-shadow", markup, f"{name} carries an inline shadow recipe")

    def test_course_home_v3_segment_carries_the_card_contract(self) -> None:
        source = SEGMENT.read_text(encoding="utf-8")
        start = source.index("CP-024 — the v3 course home")
        block = source[start:]
        # The block ends where the next documented function begins.
        block = block[: block.index("Course detail — the durable page for one enrollment")]
        self.assertNotIn("vw", block, "a viewport unit on a v3 surface ignores the route width")
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{6}\b", block), "a raw hex in the segment")
        self.assertNotIn("box-shadow", block, "a shadow recipe outside the stylesheet")
        self.assertNotIn("fontSize: '", block, "a type size outside the six contract steps")
        # The three decisions the tests above measure are the ones the code names.
        for marker in (
            "route_anchors",
            "900",
            "CB3_COURSE_COPY.nodeLocked",
            "data-cb-course-node",
            "data-cb-course-route",
        ):
            self.assertIn(marker, block)


#: The assembled-screen harness: it mounts **`CourseDetail` on `view: 'overview'`** in jsdom against
#: a stubbed `ctx.rest`, which is the only way to see what the shipped route really composes. The
#: pure-render harness above mounts `CourseHomeV3` alone and therefore cannot see a second body
#: mounted beside it — exactly the defect review round 1 found by driving the live rig.
COMPOSITION_HARNESS = r"""
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
globalThis.__CB_TEST_WIDTH__ = String(payload.width)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const calls = []
const responses = payload.responses || {}
const implemented = payload.implemented || []
const runtime = { wire_version: 25, implemented_methods: implemented, single_home_host: false }
const generic = { items: [], entries: [], objectives: [], total: 0 }

const fakeRest = async (path, options) => {
  const method = options && options.body && options.body.method
  calls.push(method || String(path))
  const base = String(path).split('?')[0]
  if (base === '/rpc') {
    const result = Object.prototype.hasOwnProperty.call(responses, method) ? responses[method] : generic
    return { ok: true, contract_version: 25, operation_id: 'test', result }
  }
  if (base === '/runtime') return runtime
  if (base === '/health') {
    return { ok: true, contract_version: 25, result: { db: { ready: true }, plugin_version: 'test', contract_version: 25 } }
  }
  return { ok: true, result: {} }
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => {
    const handle = window.setTimeout(fn, ms)
    return () => window.clearTimeout(handle)
  },
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 80) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()

await act(async () => {
  root.render(React.createElement(mod.CourseDetail, {
    row: payload.row,
    implemented: new Set(implemented),
    profile: 'default',
    prefs: { ...mod.CB_HOME_PREF_DEFAULTS },
    onBack: () => {},
    onChanged: () => {},
    focusObjectiveId: null,
    focusBlockId: null,
    focusView: 'overview',
    defaultLessonView: 'textbook',
    reloadSignal: 0,
    onChangeGoal: () => {},
    onNewSyllabus: () => {},
    onOpenLibrary: () => {}
  }))
})
await flush(300)

const home = document.querySelector('[data-cb-course-home-v3]')
const nodes = [...document.querySelectorAll('[data-cb-course-node]')]
const plate = document.querySelector('[data-cb-course-plate]')
const slot = plate ? plate.firstElementChild : null
const title = payload.row.title

const out = {
  width: payload.width,
  // Both filled-control dialects the shipped module uses: the v3 `PillAction` and the legacy
  // `CbAction`. A screen with one of each is two primaries, whatever their names.
  primaries: [
    ...document.querySelectorAll('[data-cb3-pill="primary"],[data-cb-action="primary"]')
  ].map((el) => ({
    kind: el.getAttribute('data-cb3-pill') ? 'pill' : 'action',
    text: text(el),
    top: Math.round(el.getBoundingClientRect().top)
  })),
  homeCount: document.querySelectorAll('[data-cb-course-home-v3]').length,
  homeMode: home ? home.getAttribute('data-cb-course-home-v3') : null,
  bodyMode: (document.querySelector('[data-cb-course-body]') || { getAttribute: () => null }).getAttribute('data-cb-course-body'),
  listRoutes: document.querySelectorAll('[data-cb-course-route="list"]').length,
  overviewRoutes: document.querySelectorAll('[data-cb-overview-route]').length,
  overviewNext: document.querySelectorAll('[data-cb-overview-next]').length,
  asideCount: document.querySelectorAll('[data-cb-course-aside]').length,
  // The assembled DOM order, measured with the DOM's own document-position comparison: the route
  // must sit between the plate and the aside (SPEC-V3 §5.4: M6 below M5, the aside under the
  // route), not trail the whole body.
  domOrder: [
    ...document.querySelectorAll(
      '[data-cb-course-plate],[data-cb-course-route="list"],[data-cb-course-aside]'
    )
  ].map((el) =>
    el.hasAttribute('data-cb-course-aside')
      ? 'aside'
      : el.hasAttribute('data-cb-course-route')
        ? 'route'
        : 'plate'
  ),
  plateTitleStyle: (() => {
    const title = document.querySelector('[data-cb-course-plate-title]')
    return title ? title.getAttribute('style') : null
  })(),
  courseTitleStyle: (() => {
    const title = document.querySelector('[data-cb-course-title]')
    return title ? title.getAttribute('style') : null
  })(),
  nodeCount: nodes.length,
  nodeDotWidths: nodes.map((node) => {
    const dot = node.querySelector('span[aria-hidden="true"]')
    return dot ? dot.style.width : null
  }),
  courseTitles: [...document.querySelectorAll('[data-cb-course-title]')].map(text),
  titleHeadings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter((node) => text(node) === title).length,
  plateAspect: slot ? slot.style.aspectRatio : null,
  plateMinHeight: slot ? slot.style.minHeight : null,
  continueText: text(document.querySelector('[data-cb-continue-action]') || null),
  elements: document.querySelectorAll('[data-cb-course-detail] *').length
}

process.stdout.write(JSON.stringify(out))
"""


def _composition_responses(row: dict, others: list[dict]) -> dict:
    objectives = [
        {
            "objective_id": "obj-1",
            "title": "Order at the counter",
            "ordinal": 1,
            "state": "completed",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        {
            "objective_id": "obj-2",
            "title": "Ask the price",
            "ordinal": 2,
            "state": "completed",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        {
            "objective_id": "obj-3",
            "title": "Say what you want",
            "ordinal": 3,
            "state": "introduced",
            "evidence_target": "production",
            "last_opened_at": None,
        },
        {
            "objective_id": "obj-4",
            "title": "Thank the shopkeeper",
            "ordinal": 4,
            "state": "not_started",
            "evidence_target": "production",
            "last_opened_at": None,
        },
        {
            "objective_id": "obj-5",
            "title": "Ask for the bill",
            "ordinal": 5,
            "state": "not_started",
            "evidence_target": "production",
            "last_opened_at": None,
        },
    ]
    return {
        "library.list": {"items": [row] + others, "total": 1 + len(others), "applied_filter": "all"},
        "course.outline": {"revision": 7, "objectives": objectives, "plan": {"units": []}},
        "review.queue": {"items": [], "total_overdue": 0},
        "notebook.list": {"entries": []},
        "quiz.history": {"items": []},
        "evidence.inspect": {"items": []},
        "jobs.list": {"items": []},
        "lesson.page": {
            "revision": 4,
            "section": {
                "objective_id": "obj-3",
                "title": "Say what you want",
                "ordinal": 3,
                "state": "introduced",
                "evidence_target": "production",
                "last_opened_at": None,
            },
            "runtime": {
                "lesson_run_id": "run_1",
                "binding_id": None,
                "binding_status": "detached",
                "session_state": "stored_only",
            },
            "segments": [],
            "attempts": [],
            "notebook_entries": [],
            "sources": [],
        },
        # The carrier the map needs: the course world's brief declares the plate's anchors. No
        # asset row is present, so the plate is the typographic field and the nodes are what makes
        # the route a route.
        "world.read": {
            "world": {"state": "approved", "presentation_mode": "textbook"},
            "assets": [],
            "brief": {"route_anchors": _anchors()},
        },
    }


COMPOSITION_METHODS = [
    "library.list",
    "course.outline",
    "review.queue",
    "notebook.list",
    "quiz.history",
    "evidence.inspect",
    "jobs.list",
    "lesson.page",
    "world.read",
    "engagement.read",
]


class CourseDetailOverviewCompositionTest(unittest.TestCase):
    """The assembled course home, not the fragment: what `CourseDetail` on overview ships.

    Review round 1 drove the live rig and found the legacy `OverviewView` still mounted under the
    v3 home — two filled primaries, two route containers, the title twice. The pure-render test
    above never mounts `CourseDetail`, so it could not fail on that. This one does.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp024-composed-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(
            PLUGIN_JS.read_text(encoding="utf-8") + EXPORT_SHIM, encoding="utf-8"
        )
        (root / "harness.mjs").write_text(COMPOSITION_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
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
        row = _row()
        others = [item for item in _others() if item["course_id"] != row["course_id"]]
        cls.responses = _composition_responses(row, others)
        cls.reports = {}
        for width in (1049, 900, 460):
            case = root / f"composed-{width}.json"
            case.write_text(
                json.dumps(
                    {
                        "width": width,
                        "row": row,
                        "responses": cls.responses,
                        "implemented": COMPOSITION_METHODS,
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                ["node", str(root / "harness.mjs"), str(case)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=240,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr[-6000:])
            cls.reports[width] = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_course_home_v3_overview_composes_one_primary(self) -> None:
        # The harness must actually have mounted the assembled home, not an empty shell.
        for width, report in self.reports.items():
            with self.subTest(width=width):
                self.assertEqual(report["homeCount"], 1, report)
                self.assertGreater(report["elements"], 40, "the composed screen is an empty shell")

        for width, report in self.reports.items():
            with self.subTest(width=width):
                # Exactly one filled control across the whole route, in both control dialects.
                self.assertEqual(
                    len(report["primaries"]),
                    1,
                    f"the assembled {width} overview carries {report['primaries']}",
                )
                self.assertEqual(report["primaries"][0]["kind"], "pill", report["primaries"])
                self.assertEqual(report["continueText"], "Continue Say what you want")

                # One route container, one course title: no second head, route or CTA.
                self.assertEqual(report["overviewRoutes"], 0, "the legacy route is still mounted")
                self.assertEqual(report["overviewNext"], 0, "the legacy next-move block is still mounted")
                self.assertEqual(report["listRoutes"] + (1 if report["homeMode"] == "map" else 0), 1)
                self.assertEqual(len(report["courseTitles"]), 1, report["courseTitles"])
                self.assertEqual(
                    report["titleHeadings"], 1, "the course title is a heading more than once"
                )
                self.assertEqual(report["asideCount"], 1)

        # The route really is the map at both cells, and its nodes carry the spec's dot sizes:
        # 56 at the wide route and 48 at 900 (SPEC-V3 §5.4 M5).
        wide = self.reports[1049]
        self.assertEqual(wide["homeMode"], "map")
        self.assertEqual(wide["nodeCount"], 5)
        self.assertEqual(set(wide["nodeDotWidths"]), {"56px"}, wide["nodeDotWidths"])
        at900 = self.reports[900]
        self.assertEqual(at900["homeMode"], "map")
        self.assertEqual(set(at900["nodeDotWidths"]), {"48px"}, at900["nodeDotWidths"])

        # The aside is a right column only at ≥ 1000 route px; at 900 it stacks under the route
        # while the plate keeps its M4 minimum height (SPEC-V3 §5.4). The typographic field's
        # ratio is a minimum, not a fixed box: it grows with its title so 200 % text never clips.
        self.assertEqual(wide["bodyMode"], "split")
        self.assertEqual(wide["plateMinHeight"], "204px")
        self.assertEqual(at900["bodyMode"], "stacked")
        self.assertEqual(at900["plateMinHeight"], "204px")
        self.assertEqual(self.reports[460]["plateMinHeight"], "214px")

    def test_course_home_v3_route_sits_between_plate_and_aside(self) -> None:
        """SPEC-V3 §5.4: M6 is below M5, and the aside moves under the route.

        Round 2 found the list route trailing the whole body, so at 460/900 the DOM order was
        plate → aside → route. In list mode the route now lives in the main column directly under
        the plate; in map mode it is inside the plate, so only plate and aside are siblings.
        """
        wide = self.reports[1049]
        at900 = self.reports[900]
        compact = self.reports[460]
        self.assertEqual(wide["homeMode"], "map")
        self.assertEqual(wide["domOrder"], ["plate", "aside"], wide["domOrder"])
        self.assertEqual(at900["homeMode"], "map")
        self.assertEqual(at900["domOrder"], ["plate", "aside"], at900["domOrder"])
        self.assertEqual(compact["homeMode"], "list")
        self.assertEqual(
            compact["domOrder"],
            ["plate", "route", "aside"],
            f"the 460 course home emits {compact['domOrder']}, not plate → route → aside",
        )
        self.assertEqual(compact["listRoutes"], 1, "the 460 route is not the vertical list")
        self.assertEqual(compact["asideCount"], 1)

    def test_course_home_v3_titles_wrap_between_words(self) -> None:
        """A course title wraps between words; it is never split mid-word (round 2, 460/200 %).

        jsdom has no layout, so this asserts the rule the renderer sets; the live 460/200 % cell
        measures the painted line boxes (``capture.sh`` runs the word-split probe in the driver).
        """
        for width, report in self.reports.items():
            with self.subTest(width=width):
                for field, label in (
                    ("courseTitleStyle", "the course title"),
                    ("plateTitleStyle", "the plate's type field"),
                ):
                    style = report.get(field)
                    if style is None:
                        continue  # a map cell paints a plate, so there is no type field
                    self.assertNotIn("anywhere", style, f"{label} may split a word: {style}")
                    self.assertNotIn("break-all", style, f"{label} may split a word: {style}")
                    flat = style.replace(" ", "")
                    self.assertIn("word-break:normal", flat, f"{label}: {style}")
                    self.assertIn("overflow-wrap:break-word", flat, f"{label}: {style}")
        # The plate's type field is the case round 2 saw: no art at 460, so the title is on paper.
        self.assertIsNotNone(self.reports[460].get("plateTitleStyle"))
        # And the fixed-height plate uses the body step at compact widths (a heading step in a
        # 214 px field clipped the title's opening lines at 200 % text) and the heading step wide.
        self.assertIn("font-size:var(--cb3-text-body)", self.reports[460]["plateTitleStyle"].replace(" ", ""))
        self.assertIn("font-size:var(--cb3-text-heading)", self.reports[1049]["plateTitleStyle"].replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
