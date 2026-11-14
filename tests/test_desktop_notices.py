"""A2 -- the in-app Third-party notices surface.

Coursebook ships third-party typefaces and brand assets. Their manifests declare a licence, and
``docs/launch/NOTICES.md`` is the machine-generated inventory of those declarations (A1). This card
adds the screen that shows that inventory, reachable from the one Home settings sheet.

These tests pin three separate things, because each can fail on its own:

1. **Data fidelity.** ``CB_NOTICE_ROWS`` in ``desktop/src/31-notices.js`` is byte-for-byte the
   generator's rows, so no licence id was typed by hand. The row count is asserted against the
   generator, never eyeballed from a screenshot.
2. **The surface.** A real dialog: labelled heading, ``aria-modal``, focus moved in, Tab held
   inside, Escape closes notices before the settings sheet, focus returns to the launcher, and
   every row is DOM text (no image, canvas or SVG lettering).
3. **Honesty about UNKNOWN.** The shipped ``cbNoticeLicence`` never turns an unresolved row into
   a plausible-looking id; it prints UNKNOWN. A blank beats a lie.

The render half runs the shipped ``desktop/plugin.js`` in jsdom with the shared private SDK stub,
the same harness shape H-147 uses for the settings sheet.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

#: The shared stub already carries Button, SegmentedControl and the rest of the sheet's imports.
#: H-147's stub adds ToggleRow because the real SDK has one; without it the settings sheet throws
#: "element type is invalid" before the notices launcher can even render.
NOTICES_SDK_STUB = SDK_STUB + """
export const ToggleRow = (props) =>
  el('div', { 'data-cb-settings-toggle-row': props.checked ? 'on' : 'off' }, [
    el('span', { key: 'label' }, props.label),
    el('span', { key: 'description' }, props.description || null),
    el('input', {
      key: 'switch',
      type: 'checkbox',
      checked: Boolean(props.checked),
      disabled: Boolean(props.disabled),
      'aria-label': props.label,
      onChange: () => props.onChange && props.onChange(!props.checked)
    })
  ])
"""

ROOT = Path(__file__).resolve().parent.parent
SEGMENT = ROOT / "desktop" / "src" / "31-notices.js"
HOME_SEGMENT = ROOT / "desktop" / "src" / "30-home.js"
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
GENERATOR = ROOT / "scripts" / "gen-notices.py"
BUILDER = ROOT / "scripts" / "build_notices_rows.py"

BEGIN = "// BEGIN GENERATED NOTICE ROWS"
END = "// END GENERATED NOTICE ROWS"
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
ROW_RE = re.compile(r"const CB_NOTICE_ROWS = Object\.freeze\((.*?)\)\n" + re.escape(END), re.S)

#: SPDX-shaped licences. The regex is deliberately broader than the two ids in the inventory: a
#: future hand-typed MIT row must fail this test, not slip through because the test only knew CC0.
LICENCE_RE = re.compile(
    r"\b(?:CC0|CC-BY|OFL|MIT|Apache|BSD|ISC|GPL|LGPL|AGPL|MPL|Unlicense|WTFPL)[A-Za-z0-9.+-]*"
)


def load_generator():
    """Load ``scripts/gen-notices.py`` without making ``scripts`` a package."""
    spec = importlib.util.spec_from_file_location("cb_gen_notices_for_desktop", GENERATOR)
    if spec is None or spec.loader is None:  # pragma: no cover - a missing generator is fatal
        raise unittest.SkipTest("scripts/gen-notices.py is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def generated_rows() -> list[dict]:
    """The generator's rows, in its own order, as plain dicts."""
    return [asdict(row) for row in load_generator().collect_rows(ROOT)]


def segment_source() -> str:
    return SEGMENT.read_text(encoding="utf-8")


def shipped_rows() -> list[dict]:
    """The rows the shipped segment actually carries."""
    match = ROW_RE.search(segment_source())
    if match is None:
        raise AssertionError("31-notices.js has no marked CB_NOTICE_ROWS block")
    return json.loads(match.group(1))


def rendered_licence(row: dict) -> str:
    """What the surface must show for a generated row."""
    return row["licence"] if row["resolved"] is True and row["licence"] != "UNKNOWN" else "UNKNOWN"


class NoticeDataTest(unittest.TestCase):
    """The screen cannot outlive the generated inventory."""

    def test_rendered_notice_count_equals_the_generator_row_count(self):
        rows = generated_rows()
        self.assertEqual(len(rows), 82, "the generator moved: 81 A1 rows + the adopted Home ground")
        self.assertEqual(len(shipped_rows()), len(rows))
        self.assertEqual(len(rows), len({row["asset_id"] for row in rows}), "duplicate asset id")

    def test_shipped_rows_are_exactly_the_generator_rows_in_order(self):
        # Equality, not containment: a dropped row, an extra row, a reordered row, or a licence id
        # changed by one character all fail here.
        self.assertEqual(shipped_rows(), generated_rows())

    def test_the_block_is_generated_not_hand_written(self):
        result = subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("82 rows", result.stdout)

    def test_no_licence_string_outside_the_generated_data(self):
        source = segment_source()
        generated = generated_rows()
        hand_written = BLOCK_RE.sub("", source)
        allowed = {row["licence"] for row in generated} | {"UNKNOWN"}
        tokens = set(LICENCE_RE.findall(hand_written))
        # The component may name UNKNOWN (the honest fallback). It may not name a licence id the
        # inventory does not carry, and it may not carry a second copy of one it does.
        self.assertEqual(tokens - allowed, set())
        self.assertNotIn("CC0-1.0", hand_written)
        self.assertNotIn("OFL-1.1", hand_written)

    def test_docs_inventory_and_segment_agree_on_the_row_count(self):
        notices = (ROOT / "docs" / "launch" / "NOTICES.md").read_text(encoding="utf-8")
        inventory = notices.split("## Asset inventory", 1)[1]
        table_rows = [
            line
            for line in inventory.splitlines()
            if line.startswith("| `") and line.count("|") >= 5
        ]
        self.assertEqual(len(table_rows), len(generated_rows()))

    def test_unresolved_licence_renders_unknown_not_a_guess(self):
        """Run the shipped function text, not a Python re-implementation of it."""
        if shutil.which("node") is None:
            self.skipTest("node is required to execute the shipped licence predicate")
        source = segment_source()
        match = re.search(r"function cbNoticeLicence\(row\) \{.*?\n\}", source, re.S)
        self.assertIsNotNone(match, "cbNoticeLicence is no longer a named function")
        assert match is not None
        probe = (
            match.group(0)
            + "\nconst rows = ["
            + "{licence: 'UNKNOWN', resolved: true},"
            + "{licence: 'MIT', resolved: false},"
            + "{licence: 'CC0-1.0', resolved: true},"
            + "{licence: 'OFL-1.1', resolved: false},"
            + "null];\n"
            + "process.stdout.write(JSON.stringify(rows.map(cbNoticeLicence)));\n"
        )
        result = subprocess.run(
            ["node", "-e", probe], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(
            json.loads(result.stdout), ["UNKNOWN", "UNKNOWN", "CC0-1.0", "UNKNOWN", "UNKNOWN"]
        )


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
globalThis.__CB_TEST_WIDTH__ = '1049'
globalThis.__CB_TEST_MODE__ = 'light'
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const row = {
  enrollment_id: 'enr_aaaaaaaaaaaaaaaa',
  course_id: 'crs_aaaaaaaaaaaaaaaa',
  title: 'Small-engine maintenance',
  subtitle: null,
  recipe: 'committed',
  learner_label: null,
  enrollment_status: 'active',
  course_status: 'active',
  provenance: { source: 'authored', pack_id: null, pack_version: null },
  next_step: { kind: 'start_lesson', label: 'Start the next section' },
  evidence_summary: { independent: 0, review_due: 0, total_objectives: 1, current_objective_id: 'obj_aaaaaaaaaaaaaa02' },
  warning: null,
  updated_at: '2026-11-06T18:00:00.000000+00:00',
  revision: 7
}
const runtime = {
  wire_version: 6,
  implemented_methods: ['library.list', 'course.outline', 'lesson.page', 'notebook.list'],
  single_home_host: false
}
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const body = options && options.body
  if (base === '/rpc') {
    const method = body && body.method
    if (method === 'library.list') {
      return { ok: true, result: { items: [row], total: 1, empty_reason: null, applied_filter: 'all' }, contract_version: 6 }
    }
    if (method === 'course.outline') {
      return {
        ok: true,
        result: {
          enrollment_id: body.payload.enrollment_id,
          revision: 0,
          plan: { plan_id: 'pln_x', version: 1, state: 'approved', plan_hash: 'sha256:' + 'b'.repeat(64) },
          objectives: []
        },
        contract_version: 6
      }
    }
    return { ok: true, result: { items: [], entries: [], objectives: [], total: 0 }, contract_version: 6 }
  }
  if (base === '/runtime') return runtime
  if (base === '/health') {
    return { ok: true, contract_version: 6, result: { db: { ready: true }, plugin_version: 'test', contract_version: 6 } }
  }
  if (base === '/sessions/skill') return { ok: true, skill: null }
  return { ok: true, result: {} }
}

const contributions = []
mod.default.register({
  rest: fakeRest,
  register: (entry) => contributions.push(entry),
  storage: { get: (key, fallback) => fallback, set() {}, remove() {} },
  onDispose: () => {},
  setTimeout: (fn, ms) => window.setTimeout(fn, ms),
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const route = contributions.find((entry) => entry.area === 'routes')
if (!route) throw new Error('the plugin registered no route')

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 90) => {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms))
  })
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const q = (selector) => document.querySelector(selector)
const active = () => {
  const node = document.activeElement
  if (!node) return null
  return {
    tag: node.tagName ? node.tagName.toLowerCase() : null,
    label: node.getAttribute && node.getAttribute('aria-label'),
    text: text(node).slice(0, 60)
  }
}
const inside = (container) => Boolean(container && document.activeElement && container.contains(document.activeElement))
const buttonNamed = (name) =>
  [...document.querySelectorAll('button')].find((node) => text(node) === name) || null

const snapshot = () => {
  const sheet = q('[data-cb-settings-sheet]')
  const dialog = q('[data-cb-notices]')
  const heading = dialog ? dialog.querySelector('h2') : null
  const noticesRows = dialog
    ? [...dialog.querySelectorAll('[data-cb-notice-row]')].map((node) => {
        const header = node.children[0]
        return {
          id: node.getAttribute('data-cb-notice-row'),
          licence: node.getAttribute('data-cb-notice-licence'),
          resolved: node.getAttribute('data-cb-notice-resolved'),
          label: text(node.querySelector('[data-cb-notice-licence-label]')),
          kind: text(header.children[1]),
          evidence: text(node.children[1]),
          manifest: text(node.children[2]),
          text: text(node)
        }
      })
    : []
  const panel = dialog || sheet
  const focusables = panel
    ? [...panel.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter(
        (node) => !node.disabled && node.getAttribute('aria-hidden') !== 'true'
      )
    : []
  const launcher = q('[data-cb-notices-open]')
  const settingsTrigger = q('[data-cb-settings-open]')
  return {
    sheetOpen: Boolean(sheet),
    sheetAriaHidden: sheet ? sheet.getAttribute('aria-hidden') : null,
    settingsFocusInside: inside(sheet),
    noticesOpen: Boolean(dialog),
    notices: dialog
      ? {
          role: dialog.getAttribute('role'),
          ariaModal: dialog.getAttribute('aria-modal'),
          labelledBy: dialog.getAttribute('aria-labelledby'),
          titleId: heading ? heading.id : null,
          titleTag: heading ? heading.tagName.toLowerCase() : null,
          headingText: text(heading),
          count: dialog.getAttribute('data-cb-notice-count'),
          rows: noticesRows,
          text: text(dialog),
          images: dialog.querySelectorAll('img, canvas, svg, picture').length,
          focusables: focusables.length,
          focusInside: inside(dialog),
          focus: active()
        }
      : null,
    launcher: launcher
      ? {
          label: launcher.getAttribute('aria-label'),
          haspopup: launcher.getAttribute('aria-haspopup'),
          text: text(launcher),
          minHeight: launcher.style.minHeight
        }
      : null,
    settingsTrigger: settingsTrigger
      ? { label: settingsTrigger.getAttribute('aria-label'), text: text(settingsTrigger) }
      : null,
    focus: active()
  }
}

await act(async () => {
  root.render(route.render())
})
await flush(240)

const steps = []
steps.push({ step: 'initial', ...snapshot() })

const click = async (node, label) => {
  if (!node) throw new Error('missing control: ' + label)
  await act(async () => {
    node.click()
  })
  await flush(160)
}

for (const action of payload.actions || []) {
  if (action.kind === 'open-settings') {
    await click(q('[data-cb-settings-open]'), 'settings trigger')
    steps.push({ step: 'open-settings', ...snapshot() })
  } else if (action.kind === 'open-notices') {
    await click(q('[data-cb-notices-open]'), 'notices launcher')
    steps.push({ step: 'open-notices', ...snapshot() })
  } else if (action.kind === 'escape') {
    await act(async () => {
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })
    await flush(160)
    steps.push({ step: 'escape', ...snapshot() })
  } else if (action.kind === 'close-notices') {
    await click(q('[data-cb-notices-close]'), 'notices close')
    steps.push({ step: 'close-notices', ...snapshot() })
  } else if (action.kind === 'tab-from-last') {
    const dialog = q('[data-cb-notices]')
    const items = [...dialog.querySelectorAll('button, [href], input, select, textarea')].filter((node) => !node.disabled)
    const last = items[items.length - 1]
    last.focus()
    await act(async () => {
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    })
    await flush(60)
    steps.push({
      step: 'tab-from-last',
      count: items.length,
      landedOnFirst: document.activeElement === items[0],
      focusInside: inside(dialog),
      focus: active()
    })
  } else if (action.kind === 'shift-tab-from-first') {
    const dialog = q('[data-cb-notices]')
    const items = [...dialog.querySelectorAll('button, [href], input, select, textarea')].filter((node) => !node.disabled)
    const first = items[0]
    first.focus()
    await act(async () => {
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }))
    })
    await flush(60)
    steps.push({
      step: 'shift-tab-from-first',
      count: items.length,
      landedOnLast: document.activeElement === items[items.length - 1],
      focusInside: inside(dialog),
      focus: active()
    })
  }
}

process.stdout.write(JSON.stringify({ steps }))
"""


class NoticesRenderHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        if _desktop_node_modules() is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-notices-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        stage_desktop_node_modules(cls.root)
        write_sdk_stub(cls.root, NOTICES_SDK_STUB)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def mount(self, actions: list[dict]) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps({"actions": actions}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=dict(os.environ),
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)


class NoticesSurfaceTest(NoticesRenderHarness):
    def opened(self) -> dict:
        result = self.mount([{"kind": "open-settings"}, {"kind": "open-notices"}])
        return result["steps"][2]

    def test_the_settings_sheet_has_a_launcher_for_the_notices_dialog(self):
        result = self.mount([{"kind": "open-settings"}])
        opened = result["steps"][1]
        self.assertTrue(opened["sheetOpen"])
        self.assertIsNotNone(opened["launcher"])
        self.assertEqual(opened["launcher"]["label"], "Open third-party notices")
        self.assertEqual(opened["launcher"]["haspopup"], "dialog")
        self.assertEqual(opened["launcher"]["text"], "View notices")
        self.assertEqual(opened["launcher"]["minHeight"], "44px")
        self.assertIsNone(opened["notices"])
        self.assertIsNone(opened["sheetAriaHidden"])

    def test_it_is_a_real_labelled_modal_dialog(self):
        opened = self.opened()
        notices = opened["notices"]
        self.assertTrue(opened["sheetOpen"])
        self.assertIsNotNone(notices, "the launcher did not open a notices surface")
        self.assertEqual(notices["role"], "dialog")
        self.assertEqual(notices["ariaModal"], "true")
        self.assertEqual(notices["titleTag"], "h2")
        self.assertEqual(notices["headingText"], "Third-party notices")
        self.assertEqual(notices["labelledBy"], notices["titleId"])
        # The sheet behind it is inert to assistive tech while the dialog is up.
        self.assertEqual(opened["sheetAriaHidden"], "true")
        self.assertTrue(notices["focusInside"], notices["focus"])

    def test_every_generated_row_is_rendered_once_as_dom_text(self):
        opened = self.opened()
        notices = opened["notices"]
        rows = generated_rows()
        self.assertEqual(notices["count"], str(len(rows)))
        self.assertEqual(len(notices["rows"]), len(rows), "the surface dropped or added a row")
        self.assertEqual([row["id"] for row in notices["rows"]], [row["asset_id"] for row in rows])
        # No image, canvas or SVG lettering: the whole inventory is text a screen reader can read.
        self.assertEqual(notices["images"], 0)
        for shown, expected in zip(notices["rows"], rows):
            with self.subTest(asset=expected["asset_id"]):
                self.assertEqual(shown["licence"], rendered_licence(expected))
                self.assertEqual(shown["label"], rendered_licence(expected))
                self.assertEqual(shown["kind"], expected["kind"])
                self.assertEqual(shown["evidence"], expected["evidence"])
                self.assertEqual(shown["manifest"], expected["manifest"])
                self.assertIn(expected["asset_id"], notices["text"])
                self.assertIn(expected["evidence"], notices["text"])

    def test_escape_closes_notices_first_and_returns_focus_to_the_launcher(self):
        result = self.mount(
            [{"kind": "open-settings"}, {"kind": "open-notices"}, {"kind": "escape"}]
        )
        closed = result["steps"][3]
        self.assertFalse(closed["noticesOpen"], "notices stayed open after Escape")
        self.assertTrue(closed["sheetOpen"], "Escape closed both surfaces at once")
        self.assertIsNone(closed["sheetAriaHidden"])
        self.assertEqual(closed["focus"]["label"], "Open third-party notices")

    def test_a_second_escape_then_closes_the_settings_sheet(self):
        result = self.mount(
            [
                {"kind": "open-settings"},
                {"kind": "open-notices"},
                {"kind": "escape"},
                {"kind": "escape"},
            ]
        )
        first, second = result["steps"][3], result["steps"][4]
        self.assertFalse(first["noticesOpen"])
        self.assertTrue(first["sheetOpen"])
        self.assertFalse(second["sheetOpen"])
        self.assertEqual(second["focus"]["label"], "Open Coursebook settings")

    def test_close_button_closes_only_the_notices_dialog(self):
        result = self.mount(
            [{"kind": "open-settings"}, {"kind": "open-notices"}, {"kind": "close-notices"}]
        )
        closed = result["steps"][3]
        self.assertFalse(closed["noticesOpen"])
        self.assertTrue(closed["sheetOpen"])
        self.assertEqual(closed["focus"]["label"], "Open third-party notices")

    def test_tab_is_held_inside_the_notices_dialog(self):
        result = self.mount(
            [
                {"kind": "open-settings"},
                {"kind": "open-notices"},
                {"kind": "tab-from-last"},
                {"kind": "shift-tab-from-first"},
            ]
        )
        tabbed, back = result["steps"][3], result["steps"][4]
        self.assertGreaterEqual(tabbed["count"], 1)
        self.assertTrue(tabbed["focusInside"], tabbed["focus"])
        self.assertTrue(tabbed["landedOnFirst"], tabbed["focus"])
        self.assertTrue(back["focusInside"], back["focus"])
        self.assertTrue(back["landedOnLast"], back["focus"])


if __name__ == "__main__":
    unittest.main()
