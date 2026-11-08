"""H-177 — the trail's companion and its motion posture, mounted, not described.

The static frame harness cannot run effects, so it cannot show the companion or the route-settle
posture. This suite mounts the shipped `CheckpointPath` in jsdom with the same SDK stub the field
desk uses (including its `CB_TEST_PET` pet seam) and reads:

* one 32 px companion at the current stop, at wide, with a name and no second position marker;
* no companion below 620 px and none under `prefers-reduced-motion: reduce`;
* the current stop keeps `aria-current="step"` and its state word whether or not the companion
  renders;
* reduced motion leaves every route node static;
* a gate diamond exists only where the backend recorded a check.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_h152_motion import STUB
from tests.test_desktop_lesson_views import _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The H-152 button stub forwards pointer handlers but not `focus`, and this card's ring is a
# `focusin` state. Forward it too, so the mounted ring is the shipped one, not a test-only branch.
STUB = STUB.replace("'onPointerCancel', 'onBlur']", "'onPointerCancel', 'onBlur', 'onFocus']")

HARNESS = r"""
import { JSDOM } from 'jsdom'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
const reduced = process.env.CB_TEST_REDUCED === '1'
const width = Number(process.env.CB_TEST_WIDTH || 1049)
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  pretendToBeVisual: true,
  url: 'http://localhost/'
})
const { window } = dom
for (const key of ['window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'Event', 'FocusEvent', 'MouseEvent', 'getComputedStyle']) {
  if (!(key in globalThis) || key === 'window' || key === 'document') {
    globalThis[key] = key === 'window' ? window : key === 'document' ? window.document : window[key]
  }
}
window.matchMedia = (query) => ({
  matches: reduced && query.includes('prefers-reduced-motion'),
  media: query,
  onchange: null,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {}
})
globalThis.matchMedia = window.matchMedia
// The route pane is what useCbViewportWidth measures; jsdom paints no layout.
window.Element.prototype.getBoundingClientRect = function () {
  if (this.hasAttribute && this.hasAttribute('data-cb-route')) {
    return { width, height: 900, top: 0, left: 0, right: width, bottom: 900, x: 0, y: 0 }
  }
  return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0, x: 0, y: 0 }
}

const React = (await import('react')).default
const { createRoot } = await import('react-dom/client')
const { act } = await import('react')
const mod = await import('./plugin.js')

const objectives = [
  { objective_id: 'obj_01', ordinal: 1, title: 'Name the three things an engine needs', evidence_target: 'recall', state: 'independent_evidence', check_state: 'closed', attempt_count: 2, independent: true, last_opened_at: '2026-11-05T09:00:00.000000+00:00' },
  { objective_id: 'obj_02', ordinal: 2, title: 'Diagnose a no-start', evidence_target: 'procedure', state: 'review_due', check_state: 'open', attempt_count: 1, independent: false, last_opened_at: null },
  { objective_id: 'obj_03', ordinal: 3, title: 'Replace a fouled plug', evidence_target: 'production', state: 'introduced', check_state: 'open', attempt_count: 0, independent: false, last_opened_at: null },
  { objective_id: 'obj_04', ordinal: 4, title: 'Check compression safely', evidence_target: 'comprehension', state: 'not_started', check_state: 'none', attempt_count: 0, independent: false, last_opened_at: null }
]
const outline = { enrollment_id: 'enr_h177', objectives }
const library = {
  items: [{
    enrollment_id: 'enr_h177',
    course_id: 'crs_h177',
    title: 'Small-engine maintenance',
    recipe: 'committed',
    revision: 3,
    evidence_summary: { total_objectives: 4, independent: 1, review_due: 1, current_objective_id: 'obj_02' },
    next_step: { kind: 'resolve_review_due', label: 'Review 1 objective(s)' }
  }]
}
const desk = mod.buildDeskModel({ library, outline, estimate: { status: 'ready', minutes: 6 } })
const root = createRoot(document.getElementById('root'))
await act(async () => {
  root.render(
    React.createElement('div', { 'data-cb-scope': 'light', style: mod.cbScopeStyle('light') },
      React.createElement('div', { 'data-cb-route': '/coursebook' },
        React.createElement(mod.CheckpointPath, {
          desk,
          onOpenSection: () => {},
          outlineStatus: 'ready',
          outlineError: null,
          onRetryOutline: () => {},
          companionEnabled: true
        })))
  )
})
await act(async () => { await new Promise((done) => setTimeout(done, 80)) })

// Keyboard focus: React's onFocus is driven by focusin, which a real Tab press dispatches.
if (process.env.CB_TEST_FOCUS === '1') {
  const button = document.querySelector('[data-cb-path-current="true"]')
  await act(async () => {
    const node = button ? button.closest('button') : null
    if (node) node.focus()
  })
  await act(async () => { await new Promise((done) => setTimeout(done, 40)) })
}

const focusedRow = document.querySelector('[data-cb-path-focused="true"]')

const path = document.querySelector('[data-cb-path]')
const companion = document.querySelector('[data-cb-path-companion]')
const current = document.querySelector('[data-cb-path-current="true"]')
const companionCanvas = companion ? companion.querySelector('canvas') : null
const nodes = [...document.querySelectorAll('[data-cb-path-node]')].map((node) => {
  const style = window.getComputedStyle(node)
  return {
    id: node.getAttribute('data-cb-path-node'),
    motion: node.getAttribute('data-cb-path-node-motion'),
    transitionDuration: style.transitionDuration,
    transform: style.transform || 'none'
  }
})
process.stdout.write(JSON.stringify({
  layout: path ? path.getAttribute('data-cb-path-layout') : null,
  companion: companion ? {
    canvas: Boolean(companionCanvas),
    canvasWidth: companionCanvas ? companionCanvas.getAttribute('width') : null,
    name: companion.querySelector('[data-cb-companion-name]') ? companion.querySelector('[data-cb-companion-name]').textContent : null,
    motion: companion.querySelector('[data-cb-companion]') ? companion.querySelector('[data-cb-companion]').getAttribute('data-cb-companion-motion') : null
  } : null,
  companionCount: document.querySelectorAll('[data-cb-path-companion]').length,
  companionInsideCurrent: current ? Boolean(current.closest('[data-cb-path-node]').querySelector('[data-cb-path-companion]')) : false,
  current: current ? {
    id: current.getAttribute('data-cb-path-item'),
    state: current.getAttribute('data-cb-path-state'),
    word: (current.querySelector('[data-cb-path-word]') || {}).textContent || null
  } : null,
  ariaCurrentCount: document.querySelectorAll('[aria-current="step"]').length,
  nodes,
  gateCount: document.querySelectorAll('[data-cb-path-gate]').length,
  gateStates: [...document.querySelectorAll('[data-cb-path-gate]')].map((node) => node.getAttribute('data-cb-path-gate')),
  detailIds: [...document.querySelectorAll('[data-cb-path-detail]')].map((node) => node.getAttribute('data-cb-path-detail')),
  svgCount: document.querySelectorAll('[data-cb-path-node] svg').length,
  svgAllAriaHidden: [...document.querySelectorAll('[data-cb-path-node] svg')].every((node) => node.getAttribute('aria-hidden') === 'true'),
  placeLabels: [...document.querySelectorAll('[data-cb-path-place]')].map((node) => node.textContent.trim()),
  focus: focusedRow ? {
    id: focusedRow.getAttribute('data-cb-path-node'),
    outline: focusedRow.style.outline,
    outlineOffset: focusedRow.style.outlineOffset
  } : null,
  reduced
}))
"""


class TrailHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom/jsdom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h177-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if not source.is_dir():
                source = modules.parent / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(STUB, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def mount(self, *, width: int = 1049, reduced: bool = False, focus: bool = False) -> dict:
        env = dict(os.environ)
        env["CB_TEST_WIDTH"] = str(width)
        env["CB_TEST_PET"] = "1"
        env["CB_TEST_REDUCED"] = "1" if reduced else "0"
        env["CB_TEST_FOCUS"] = "1" if focus else "0"
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs")],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)


class CompanionTest(TrailHarness):
    def test_wide_trail_carries_one_32px_companion_at_the_current_stop(self) -> None:
        data = self.mount(width=1049)
        self.assertEqual(data["layout"], "full")
        self.assertEqual(data["companionCount"], 1)
        self.assertTrue(data["companion"]["canvas"])
        self.assertEqual(data["companion"]["canvasWidth"], "32")
        self.assertEqual(data["companion"]["name"], "Ada")
        self.assertTrue(data["companionInsideCurrent"])
        # The companion is never the only position marker.
        self.assertEqual(data["ariaCurrentCount"], 1)
        self.assertEqual(data["current"]["id"], "obj_02")
        self.assertEqual(data["current"]["word"], "Review due")

    def test_below_620px_the_companion_is_hidden_and_the_spine_is_straight(self) -> None:
        data = self.mount(width=460)
        self.assertEqual(data["layout"], "compact")
        self.assertIsNone(data["companion"])
        self.assertEqual(data["ariaCurrentCount"], 1)
        self.assertEqual(data["current"]["id"], "obj_02")

    def test_reduced_motion_hides_the_companion_and_settles_every_node(self) -> None:
        data = self.mount(width=1049, reduced=True)
        self.assertTrue(data["reduced"])
        self.assertIsNone(data["companion"])
        self.assertEqual({node["motion"] for node in data["nodes"]}, {"static"})
        for node in data["nodes"]:
            self.assertEqual(node["transitionDuration"], "0s", node)
            self.assertEqual(node["transform"], "none", node)
        self.assertEqual(data["ariaCurrentCount"], 1)


class StructureTest(TrailHarness):
    def test_every_stop_is_a_list_item_and_the_route_is_decorative(self) -> None:
        data = self.mount()
        self.assertEqual(len(data["nodes"]), 4)
        self.assertEqual(data["svgCount"], 8)
        self.assertTrue(data["svgAllAriaHidden"])
        self.assertEqual(data["placeLabels"], ["Start", "Course end"])

    def test_gates_exist_only_where_a_check_is_recorded(self) -> None:
        data = self.mount()
        self.assertEqual(data["gateCount"], 3)
        self.assertEqual(data["gateStates"], ["closed", "open", "open"])
        self.assertNotIn("none", data["gateStates"])

    def test_only_current_and_next_carry_a_detail_line(self) -> None:
        data = self.mount()
        self.assertEqual(data["detailIds"], ["obj_02", "obj_03"])

    def test_keyboard_focus_paints_a_visible_ring_on_the_stop(self) -> None:
        data = self.mount(focus=True)
        self.assertIsNotNone(data["focus"])
        self.assertEqual(data["focus"]["id"], "obj_02")
        self.assertEqual(data["focus"]["outline"], "2px solid var(--cb-accent)")
        self.assertEqual(data["focus"]["outlineOffset"], "2px")
        # The ring is not a beat: no node carries a running transition for it.
        for node in data["nodes"]:
            self.assertEqual(node["transitionDuration"], "0s", node)


if __name__ == "__main__":
    unittest.main()
