"""H-147 — the Home settings sheet and the default learning view.

The owner's shape is: open Coursebook on Home, hit Continue, change a few things if wanted, and get
on with learning. Settings therefore live on Home as one compact sheet — not a route, not a second
profile, not a settings tab inside Courses — and every toggle applies the moment it moves.

These tests mount the shipped route in jsdom against the host's own `ctx.storage` contract (a
namespaced JSON store). The store here is file-backed on purpose: a second Node process re-reads the
same file, so "a change survives a reload" is proved by re-importing the module rather than by
reusing an in-memory cache. Nothing here proves a live backend; the card's live frames do.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The SDK stub is the shared one, with three additive differences this card needs: a segmented
# control that actually fires its onChange, a ToggleRow that renders the same on/off row the real
# SDK does, and a Button that keeps its inline style so the 44 px target is measurable.
SEGMENTED_OLD = """export const SegmentedControl = (props) =>
  el('div', { className: 'segmented' }, (props.options || []).map((option) =>
    el('button', { key: option.id, 'aria-pressed': option.id === props.value, type: 'button' }, option.label)))"""

SEGMENTED_NEW = """export const SegmentedControl = (props) =>
  el(
    'div',
    {
      className: props.className ? 'segmented ' + props.className : 'segmented',
      'data-disabled': props.disabled ? 'true' : null
    },
    (props.options || []).map((option) =>
      el(
        'button',
        {
          key: option.id,
          type: 'button',
          'aria-pressed': option.id === props.value,
          'data-option': option.id,
          disabled: Boolean(props.disabled),
          onClick: () => {
            if (!props.disabled && props.onChange) props.onChange(option.id)
          }
        },
        option.label
      )
    )
  )"""

TOGGLE_ANCHOR = "export const SandboxedFrame = () => null"
TOGGLE_NEW = """export const ToggleRow = (props) =>
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
export const SandboxedFrame = () => null"""

SETTINGS_SDK_STUB = SDK_STUB.replace(SEGMENTED_OLD, SEGMENTED_NEW).replace(
    "  if (props.title) attrs.title = props.title",
    "  if (props.title) attrs.title = props.title\n  if (props.style) attrs.style = props.style",
).replace(TOGGLE_ANCHOR, TOGGLE_NEW)
assert SEGMENTED_NEW in SETTINGS_SDK_STUB and "ToggleRow" in SETTINGS_SDK_STUB
assert "attrs.style = props.style" in SETTINGS_SDK_STUB

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
globalThis.__CB_TEST_MODE__ = payload.hostMode || 'light'
const systemReduced = Boolean(payload.systemReduced)
window.matchMedia = () => ({
  matches: systemReduced,
  addEventListener() {},
  removeEventListener() {}
})

const mod = await import('./plugin.js')

// The host's namespaced JSON store, standing in for `hermes.plugin.coursebook.<key>`: the real one
// is window.localStorage, so a file keeps it across two separate Node processes.
const storagePath = payload.storagePath
const readStore = () => {
  try {
    return JSON.parse(fs.readFileSync(storagePath, 'utf8'))
  } catch (error) {
    return {}
  }
}
const writeStore = (all) => fs.writeFileSync(storagePath, JSON.stringify(all))
const storageWrites = []
const storage = {
  get(key, fallback) {
    const all = readStore()
    return Object.prototype.hasOwnProperty.call(all, key) ? all[key] : fallback
  },
  set(key, value) {
    storageWrites.push(key)
    const all = readStore()
    all[key] = value
    writeStore(all)
  },
  remove(key) {
    const all = readStore()
    delete all[key]
    writeStore(all)
  }
}

const rows = payload.rows || []
const runtime = {
  wire_version: 6,
  implemented_methods: ['library.list', 'course.outline', 'lesson.page', 'notebook.list'],
  single_home_host: false
}
const outlineFor = (enrollmentId) => {
  const row = rows.find((item) => item.enrollment_id === enrollmentId)
  return {
    enrollment_id: enrollmentId,
    revision: 0,
    plan: { plan_id: 'pln_x', version: 1, state: 'approved', plan_hash: 'sha256:' + 'b'.repeat(64) },
    objectives: [
      {
        objective_id: 'obj_aaaaaaaaaaaaaa02',
        ordinal: 1,
        title: (row && row.title) || 'Section',
        state: 'introduced',
        check_state: 'open',
        attempt_count: 0,
        independent: false,
        last_opened_at: null
      }
    ]
  }
}
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const body = options && options.body
  if (base === '/rpc') {
    const method = body && body.method
    if (method === 'library.list') {
      return { ok: true, result: { items: rows, total: rows.length, empty_reason: null, applied_filter: 'all' }, contract_version: 6 }
    }
    if (method === 'course.outline') {
      return { ok: true, result: outlineFor(body.payload.enrollment_id), contract_version: 6 }
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
  storage,
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
    text: text(node).slice(0, 60),
    inSheet: Boolean(node.closest && node.closest('[data-cb-settings-sheet]'))
  }
}
const buttonNamed = (name) =>
  [...document.querySelectorAll('button')].find((node) => text(node) === name) || null

const snapshot = () => {
  const root = q('[data-cb-route]')
  const sheet = q('[data-cb-settings-sheet]')
  const controls = {}
  for (const node of document.querySelectorAll('[data-cb-settings-control]')) {
    controls[node.getAttribute('data-cb-settings-control')] = node.getAttribute('data-cb-settings-value')
  }
  const toggles = {}
  for (const node of document.querySelectorAll('[data-cb-settings-toggle]')) {
    const box = node.querySelector('input, [role="switch"]')
    toggles[node.getAttribute('data-cb-settings-toggle')] = box ? (box.checked ? 'true' : 'false') : null
  }
  const trigger = q('[data-cb-settings-open]')
  return {
    sheetOpen: Boolean(sheet),
    sheetRole: sheet ? sheet.getAttribute('role') : null,
    sheetModal: sheet ? sheet.getAttribute('aria-modal') : null,
    sheetLabelledBy: sheet ? sheet.getAttribute('aria-labelledby') : null,
    sheetTitleId: sheet ? (sheet.querySelector('h2') || {}).id || null : null,
    sheetWidth: sheet ? sheet.getAttribute('style') : null,
    sheetMaxWidth: sheet ? sheet.getAttribute('style') : null,
    sections: [...document.querySelectorAll('[data-cb-settings-section]')].map((node) =>
      node.getAttribute('data-cb-settings-section')
    ),
    sectionLabels: [...document.querySelectorAll('[data-cb-settings-section]')].map((node) => {
      const heading = node.querySelector('h3')
      return { id: node.getAttribute('aria-labelledby'), text: text(heading), headingId: heading ? heading.id : null }
    }),
    scopeLabel: text(q('[data-cb-settings-scope]')),
    // H-156 — the child-safe floor, its four rules, and the parent-set session length.
    childSafe: q('[data-cb-child-safe]') ? q('[data-cb-child-safe]').getAttribute('data-cb-child-safe') : null,
    childSafeText: text(q('[data-cb-child-safe]')),
    sessionMinutes: q('[data-cb-session-minutes]') ? q('[data-cb-session-minutes]').getAttribute('data-cb-session-minutes') : null,
    childSafeRules: [...document.querySelectorAll('[data-cb-child-safe-rule]')].map((node) => ({
      id: node.getAttribute('data-cb-child-safe-rule'),
      state: node.getAttribute('data-cb-child-safe-state'),
      text: text(node)
    })),
    parentEvidence: text(q('[data-cb-parent-evidence]')),
    bodyText: text(q('[data-cb-main]')),
    destination: q('[data-cb-destination]') ? q('[data-cb-destination]').getAttribute('data-cb-destination') : null,
    homeDefaults: q('[data-cb-home-defaults]') ? q('[data-cb-home-defaults]').getAttribute('data-cb-home-defaults') : null,
    homeEffective: q('[data-cb-home-defaults]') ? q('[data-cb-home-defaults]').getAttribute('data-cb-home-effective') : null,
    homeOverride: q('[data-cb-home-override]') ? q('[data-cb-home-override]').getAttribute('data-cb-home-override') : null,
    homeDefaultsText: text(q('[data-cb-home-defaults]')),
    scope: root ? root.getAttribute('data-cb-scope') : null,
    motion: root ? root.getAttribute('data-cb-motion') : null,
    controls,
    toggles,
    trigger: trigger
      ? {
          label: trigger.getAttribute('aria-label'),
          haspopup: trigger.getAttribute('aria-haspopup'),
          minHeight: trigger.style.minHeight,
          text: text(trigger)
        }
      : null,
    resetButtons: [...document.querySelectorAll('[data-cb-settings-reset]')].map((node) => ({
      section: node.getAttribute('data-cb-settings-reset'),
      label: node.getAttribute('aria-label'),
      disabled: Boolean(node.disabled),
      minHeight: node.style.minHeight
    })),
    buttons: [...document.querySelectorAll('button')].map((node) => text(node)).filter(Boolean),
    focus: active()
  }
}

await act(async () => {
  root.render(route.render())
})
await flush(220)

// GM-002: the classroom override is a course-home setting now; the harness opens the first
// library card so the route is on a course home before its steps run.
const shelfCard = document.querySelector('[data-cb-home-card] button')
if (shelfCard) {
  await act(async () => { shelfCard.click() })
  await flush(220)
}

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
  if (action.kind === 'destination') {
    await click(q('[data-cb-nav-item="' + action.value + '"]'), 'destination ' + action.value)
    steps.push({ step: 'destination ' + action.value, ...snapshot() })
  } else if (action.kind === 'text-click') {
    await click(buttonNamed(action.text), action.text)
    steps.push({ step: 'click ' + action.text, ...snapshot() })
  } else if (action.kind === 'open') {
    await click(q('[data-cb-settings-open]'), 'settings trigger')
    steps.push({ step: 'open', ...snapshot() })
  } else if (action.kind === 'option') {
    await click(q('[data-cb-settings-control="' + action.section + '"] [data-option="' + action.value + '"]'), action.section + '=' + action.value)
    steps.push({ step: action.section + '=' + action.value, ...snapshot() })
  } else if (action.kind === 'reset') {
    await click(q('[data-cb-settings-reset="' + action.section + '"]'), 'reset ' + action.section)
    steps.push({ step: 'reset ' + action.section, ...snapshot() })
  } else if (action.kind === 'toggle') {
    await click(q('[data-cb-settings-toggle="' + action.toggle + '"] input'), 'toggle ' + action.toggle)
    steps.push({ step: 'toggle ' + action.toggle, ...snapshot() })
  } else if (action.kind === 'close') {
    await click(q('[data-cb-settings-close]'), 'close')
    steps.push({ step: 'close', ...snapshot() })
  } else if (action.kind === 'escape') {
    await act(async () => {
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })
    await flush(160)
    steps.push({ step: 'escape', ...snapshot() })
  } else if (action.kind === 'tab-from-last') {
    const focusables = [...document.querySelectorAll('[data-cb-settings-sheet] button, [data-cb-settings-sheet] input')].filter(
      (node) => !node.disabled
    )
    const last = focusables[focusables.length - 1]
    last.focus()
    await act(async () => {
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    })
    await flush(40)
    steps.push({
      step: 'tab-from-last',
      focusables: focusables.length,
      landedOnFirst: document.activeElement === focusables[0],
      focus: active()
    })
  } else if (action.kind === 'shift-tab-from-first') {
    const focusables = [...document.querySelectorAll('[data-cb-settings-sheet] button, [data-cb-settings-sheet] input')].filter(
      (node) => !node.disabled
    )
    const first = focusables[0]
    first.focus()
    await act(async () => {
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }))
    })
    await flush(40)
    steps.push({
      step: 'shift-tab-from-first',
      landedOnLast: document.activeElement === focusables[focusables.length - 1],
      focus: active()
    })
  }
}

const sheetHtml = q('[data-cb-settings-sheet]') ? q('[data-cb-settings-sheet]').outerHTML : ''
process.stdout.write(
  JSON.stringify({
    steps,
    storageWrites,
    stored: readStore(),
    sheetHtml,
    saveButtons: [...document.querySelectorAll('button')].filter((node) => /^save$/i.test(text(node))).length
  })
)
"""


def row(**overrides) -> dict:
    base = {
        "enrollment_id": "enr_aaaaaaaaaaaaaaaa",
        "course_id": "crs_aaaaaaaaaaaaaaaa",
        "title": "Small-engine maintenance",
        "subtitle": None,
        "recipe": "committed",
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "start_lesson", "label": "Start the next section"},
        "evidence_summary": {
            "independent": 0,
            "review_due": 0,
            "total_objectives": 1,
            "current_objective_id": "obj_aaaaaaaaaaaaaa02",
        },
        "warning": None,
        "updated_at": "2026-11-06T18:00:00.000000+00:00",
        "revision": 7,
    }
    base.update(overrides)
    return base


class Harness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h147-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        # Private node_modules: the SDK stub must never be written through a
        # symlink into the host's shared install (H-208 cross-suite flake).
        stage_desktop_node_modules(cls.root)
        write_sdk_stub(cls.root, SETTINGS_SDK_STUB)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_harness(self, payload: dict, storage_name: str = "store.json") -> dict:
        storage = self.root / storage_name
        payload = dict(payload)
        payload["storagePath"] = str(storage)
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        env = dict(os.environ)
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)


    def mount(self, actions: list[dict], rows: list[dict] | None = None, storage_name: str = "store.json", **extra) -> dict:
        payload = {
            "rows": rows if rows is not None else [row()],
            "actions": actions,
            "hostMode": "light",
        }
        payload.update(extra)
        return self.run_harness(payload, storage_name=storage_name)


class HomeSettingsSheetTest(Harness):
    def test_home_names_the_default_before_anything_is_opened(self):
        result = self.mount([])
        first = result["steps"][0]
        self.assertEqual(first["homeDefaults"], "game")
        self.assertIn("Default view · Game", first["homeDefaultsText"])
        self.assertIsNone(first["homeOverride"])
        self.assertFalse(first["sheetOpen"])
        self.assertEqual(first["trigger"]["label"], "Open Coursebook settings")
        self.assertEqual(first["trigger"]["haspopup"], "dialog")
        self.assertEqual(first["trigger"]["minHeight"], "44px")
        self.assertNotIn("Save", first["buttons"])

    def test_one_interaction_opens_the_sheet_with_every_section(self):
        result = self.mount([{"kind": "open"}])
        opened = result["steps"][1]
        self.assertTrue(opened["sheetOpen"])
        self.assertEqual(opened["sheetRole"], "dialog")
        self.assertEqual(opened["sheetModal"], "true")
        self.assertEqual(opened["sheetTitleId"], opened["sheetLabelledBy"])
        self.assertIn("width: 28.75rem", opened["sheetWidth"])
        self.assertIn("max-width: 100%", opened["sheetWidth"])
        self.assertEqual(opened["scopeLabel"], "On this device")
        self.assertEqual(
            opened["sections"],
            [
                "appearance",
                "default-view",
                "classroom",
                "child-safe",
                "sound",
                "companion",
                "haptics",
                "reduced-motion",
                "game-feedback",
                # UI-K13: the generation-usage read-out closes the sheet. It is a record, not a
                # preference, so it carries no reset control.
                "usage",
            ],
        )
        for label in opened["sectionLabels"]:
            self.assertEqual(label["id"], label["headingId"])
        self.assertTrue(opened["focus"]["inSheet"], opened["focus"])
        # H-183: Haptics is an availability note, not a switch. The learner sees no control there.
        self.assertNotIn("haptics", opened["toggles"])
        self.assertIn('data-cb-settings-unavailable="haptics"', result["sheetHtml"])
        self.assertEqual(opened["toggles"]["sound"], "false")
        # Both the trigger and every section reset meet the 44 px target.
        self.assertEqual({reset["minHeight"] for reset in opened["resetButtons"]}, {"44px"})
        self.assertNotIn("Save", opened["buttons"])
        self.assertEqual(result["saveButtons"], 0)

    def test_a_change_applies_immediately_and_is_written_to_the_profile_store(self):
        result = self.mount(
            [
                {"kind": "open"},
                {"kind": "option", "section": "default-view", "value": "textbook"},
                {"kind": "toggle", "toggle": "sound"},
                {"kind": "option", "section": "appearance", "value": "dark"},
                {"kind": "option", "section": "reduced-motion", "value": "reduce"},
            ],
            storage_name="apply.json",
        )
        opened, after_view, after_sound, after_dark, after_motion = result["steps"][1:6]
        self.assertEqual(opened["controls"]["default-view"], "game")
        self.assertEqual(after_view["controls"]["default-view"], "textbook")
        self.assertEqual(after_view["homeDefaults"], "textbook")
        # No Save: the same render that moved the control already carries the new default.
        self.assertEqual(after_view["toggles"]["sound"], "false")
        self.assertEqual(after_sound["toggles"]["sound"], "true")
        self.assertEqual(after_dark["scope"], "dark")
        self.assertEqual(after_motion["motion"], "reduced")
        stored = result["stored"]
        key = "home-preferences.default"
        self.assertIn(key, stored)
        self.assertEqual(stored[key]["defaultMode"], "textbook")
        self.assertEqual(stored[key]["appearance"], "dark")
        self.assertTrue(stored[key]["sound"])
        self.assertEqual(stored[key]["reducedMotion"], "reduce")
        self.assertGreaterEqual(len(result["storageWrites"]), 4)

    def test_classroom_override_wins_and_clearing_restores_the_home_default(self):
        result = self.mount(
            [
                {"kind": "open"},
                {"kind": "option", "section": "default-view", "value": "textbook"},
                {"kind": "option", "section": "classroom", "value": "guided"},
                {"kind": "reset", "section": "classroom"},
            ],
            storage_name="override.json",
        )
        opened, after_view, after_override, after_reset = result["steps"][1:5]
        self.assertIsNone(opened["homeOverride"])
        self.assertEqual(after_view["homeEffective"], "textbook")
        self.assertEqual(after_override["homeOverride"], "guided")
        self.assertEqual(after_override["homeEffective"], "guided")
        self.assertEqual(after_override["controls"]["classroom"], "guided")
        self.assertEqual(after_reset["homeOverride"], None)
        self.assertEqual(after_reset["homeEffective"], "textbook")
        self.assertEqual(after_reset["controls"]["classroom"], "default")
        stored = result["stored"]["home-preferences.default"]
        self.assertEqual(stored["defaultMode"], "textbook")
        self.assertEqual(stored["classrooms"], {})

    def test_sections_reset_independently(self):
        result = self.mount(
            [
                {"kind": "open"},
                {"kind": "option", "section": "appearance", "value": "dark"},
                {"kind": "option", "section": "default-view", "value": "guided"},
                {"kind": "reset", "section": "appearance"},
            ],
            storage_name="reset.json",
        )
        after_reset = result["steps"][-1]
        self.assertEqual(after_reset["controls"]["appearance"], "system")
        self.assertEqual(after_reset["scope"], "light")
        self.assertEqual(after_reset["controls"]["default-view"], "guided")
        self.assertEqual(result["stored"]["home-preferences.default"]["defaultMode"], "guided")

    def test_escape_closes_and_returns_focus_to_the_invoking_control(self):
        result = self.mount([{"kind": "open"}, {"kind": "escape"}], storage_name="escape.json")
        opened, closed = result["steps"][1], result["steps"][2]
        self.assertTrue(opened["sheetOpen"])
        self.assertFalse(closed["sheetOpen"])
        self.assertEqual(closed["focus"]["label"], "Open Coursebook settings")
        self.assertEqual(closed["focus"]["text"], "Settings")

    def test_close_button_also_returns_focus(self):
        result = self.mount([{"kind": "open"}, {"kind": "close"}], storage_name="close.json")
        closed = result["steps"][2]
        self.assertFalse(closed["sheetOpen"])
        self.assertEqual(closed["focus"]["label"], "Open Coursebook settings")

    def test_tab_is_held_inside_the_sheet(self):
        result = self.mount(
            [{"kind": "open"}, {"kind": "tab-from-last"}, {"kind": "shift-tab-from-first"}],
            storage_name="tab.json",
        )
        tabbed = result["steps"][2]
        self.assertGreater(tabbed["focusables"], 4)
        self.assertTrue(tabbed["landedOnFirst"], tabbed)
        back = result["steps"][3]
        self.assertTrue(back["landedOnLast"], back)

    def test_reduced_motion_follows_the_system_until_the_learner_says_otherwise(self):
        result = self.mount([], storage_name="motion-system.json", systemReduced=True)
        self.assertEqual(result["steps"][0]["motion"], "reduced")
        # An explicit "follow system" is still the system; there is no third state.
        result = self.mount(
            [{"kind": "open"}, {"kind": "option", "section": "reduced-motion", "value": "reduce"}],
            storage_name="motion-explicit.json",
            systemReduced=False,
        )
        self.assertEqual(result["steps"][0]["motion"], "full")
        self.assertEqual(result["steps"][2]["motion"], "reduced")

    def test_a_change_survives_a_reload_in_a_fresh_process(self):
        first = self.mount(
            [
                {"kind": "open"},
                {"kind": "option", "section": "default-view", "value": "textbook"},
                {"kind": "option", "section": "appearance", "value": "dark"},
                {"kind": "option", "section": "classroom", "value": "guided"},
            ],
            storage_name="reload.json",
        )
        self.assertIn("home-preferences.default", first["stored"])
        second = self.run_harness(
            {"rows": [row()], "actions": [], "hostMode": "light"},
            storage_name="reload.json",
        )
        fresh = second["steps"][0]
        self.assertEqual(fresh["homeDefaults"], "textbook")
        self.assertEqual(fresh["scope"], "dark")
        self.assertEqual(fresh["homeOverride"], "guided")
        self.assertEqual(fresh["homeEffective"], "guided")

    def test_settings_are_keyed_by_hermes_profile(self):
        # The same device, two profiles: each profile's document is its own store key.
        first = self.mount(
            [{"kind": "open"}, {"kind": "option", "section": "default-view", "value": "guided"}],
            storage_name="profiles.json",
        )
        self.assertIn("home-preferences.default", first["stored"])
        self.assertNotIn("home-preferences.other", first["stored"])


class HomeSettingsCopyTest(Harness):
    def test_no_sync_claim_and_no_save_button_anywhere(self):
        result = self.mount([{"kind": "open"}], storage_name="copy.json")
        opened = result["steps"][1]
        html = result["sheetHtml"].lower()
        self.assertIn("on this device", opened["scopeLabel"].lower())
        self.assertIn("does not sync", html)
        for claim in ("synced", "sync across", "syncs to your", "cloud"):
            self.assertNotIn(claim, html)
        self.assertEqual(result["saveButtons"], 0)
        self.assertNotIn("save", [button.lower() for button in opened["buttons"]])

    def test_home_copy_names_no_internal_machinery(self):
        """H-183: the default Home desk never speaks in jobs, queues or revisions."""
        import re

        result = self.mount([])
        text = result["steps"][0]["bodyText"] or ""
        for pattern in (
            r"lessons job",
            r"\bjobs?\b",
            r"\bqueued\b",
            r"\bqueue\b",
            r"\brevision\b",
            r"\breconcile\b",
            r"JOB_FAILED",
        ):
            self.assertIsNone(re.search(pattern, text, re.I), f"Home shows {pattern!r}: {text}")

    def test_haptics_is_an_availability_note_not_a_switch(self):
        result = self.mount([{"kind": "open"}], storage_name="haptics.json")
        html = result["sheetHtml"]
        self.assertIn("Not available on desktop", html)
        self.assertIn("never offers a vibration response", html)
        # H-183: no disabled switch either. The honest desktop default is a sentence, not a control.
        self.assertNotIn("haptics", result["steps"][1]["toggles"])
        self.assertIn('data-cb-settings-unavailable="haptics"', html)
        unavailable = html.split('data-cb-settings-unavailable="haptics"')[1].split("</section>")[0]
        self.assertNotIn("<input", unavailable)
        self.assertNotIn('role="switch"', unavailable)

    def test_every_settings_control_has_a_reader_outside_the_sheet(self):
        """H-183: a preference with no reader is a defect, not a setting."""
        source = PLUGIN_JS.read_text(encoding="utf-8")
        start = source.index("function HomeSettingsSheet(")
        end = source.index("function HomeDefaultsLine(")
        sheet = source[start:end]
        outside = source[:start] + source[end:]
        readers = {
            "appearance": "homePrefs.appearance",
            "default-view": "prefs.defaultMode",
            "classroom": "prefs.classrooms",
            "session-length": "prefs.sessionMinutes",
            "sound": "prefs.sound",
            "companion": "prefs.companion",
            "reduced-motion": "homePrefs.reducedMotion",
        }
        for control, reader in readers.items():
            with self.subTest(control=control):
                self.assertIn(f"'{control}'", sheet, f"{control} is not rendered")
                self.assertIn(reader, outside, f"{control} has no reader outside the sheet: {reader}")
        # Haptics emits no control key at all, so it can never be counted as a setting.
        self.assertIn("'data-cb-settings-unavailable': 'haptics'", sheet)
        self.assertNotIn("'data-cb-settings-toggle': 'haptics'", source)
        self.assertNotIn("'data-cb-settings-control': 'haptics'", source)

    def test_session_length_setting_reaches_the_home_line_it_claims_to_change(self):
        result = self.mount(
            [{"kind": "open"}, {"kind": "option", "section": "session-length", "value": "20"}],
            storage_name="session-length.json",
        )
        self.assertEqual(result["steps"][0]["sessionMinutes"], "15")
        self.assertEqual(result["steps"][2]["sessionMinutes"], "20")
        self.assertIn("Session", result["steps"][0]["homeDefaultsText"] or "")

    def test_companion_setting_reaches_the_surfaces_that_draw_the_companion(self):
        source = PLUGIN_JS.read_text(encoding="utf-8")
        # The stored choice is read by the route and handed to the plates that draw a pet.
        self.assertIn("companionEnabled: !prefs || prefs.companion !== false", source)
        self.assertIn("useStudyCompanion(companionEnabled === true)", source)
        self.assertIn("useStudyCompanion(companionEnabled !== false)", source)


class SectionDefaultViewTest(Harness):
    """The chosen default is not just a stored string: a section opens in it."""

    def run_section(self, default_view: str) -> str:
        payload = {
            "rows": [row()],
            "actions": [],
            "section": True,
            "defaultView": default_view,
        }
        case = self.root / "section.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "section.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=dict(os.environ),
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return result.stdout

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        (cls.root / "section.mjs").write_text(SECTION_HARNESS, encoding="utf-8")

    def test_default_view_game_opens_the_section_in_field_quest(self):
        html = self.run_section("field_quest")
        self.assertIn('data-cb-lesson-view="field_quest"', html)

    def test_default_view_textbook_opens_the_section_in_textbook(self):
        html = self.run_section("textbook")
        self.assertIn('data-cb-lesson-view="textbook"', html)

    def test_default_view_guided_opens_the_section_in_guided(self):
        html = self.run_section("guided")
        self.assertIn('data-cb-lesson-view="guided"', html)


SECTION_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const mod = await import('./plugin.js')

const block = (id, role, headline, short, deep, checkId) => ({
  id,
  role,
  headline,
  short,
  deep,
  check_id: checkId || null,
  media: [],
  source_ids: []
})
const document = {
  schema_version: 1,
  document_id: 'doc_0123456789abcdef0123',
  content_hash: 'sha256:' + 'a'.repeat(64),
  section_title: 'Affection and register',
  objective_id: 'obj_0123456789abcdef',
  state: 'complete',
  view_note: null,
  views: { textbook: true, guided: true, field_quest: true, field_notes: false },
  blocks: [
    block('blk_orient0001', 'orient', 'Start here', 'Short orient.', 'Deep orient prose.'),
    block('blk_practice01', 'practice', 'Try it', 'Short practice.', 'Deep practice prose.', 'chk_0123456789abcdef'),
    block('blk_recap00001', 'recap', 'Recap', 'Short recap.', 'Deep recap prose.')
  ],
  check_id: 'chk_0123456789abcdef',
  source_ids: []
}
const page = {
  revision: 4,
  section: {
    objective_id: document.objective_id,
    title: document.section_title,
    state: 'in_progress',
    evidence_target: 'discrimination',
    last_opened_at: null
  },
  runtime: { lesson_run_id: 'run_1', binding_id: null, binding_status: 'detached', session_state: 'stored_only' },
  segments: [],
  attempts: [],
  notebook_entries: [],
  sources: [],
  document
}
process.stdout.write(
  renderToStaticMarkup(
    React.createElement(mod.SectionPage, {
      row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default' },
      objectiveId: document.objective_id,
      page,
      pageStatus: 'ready',
      pageError: null,
      onRetryPage: () => {},
      implemented: new Set(['check.open', 'artifact.get', 'notebook.save']),
      onBack: () => {},
      onChanged: () => {},
      review: null,
      defaultLessonView: payload.defaultView
    })
  )
)
"""


class SettingsModelTest(Harness):
    """The stored document is sanitized, and the override rule is one function."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        (cls.root / "model.mjs").write_text(MODEL_HARNESS, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_model(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "model.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=dict(os.environ),
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    def test_defaults_and_sanitizing(self):
        out = self.run_model({"raw": None})
        self.assertEqual(
            out["defaults"],
            {
                "appearance": "system",
                "defaultMode": "game",
                "sound": False,
                "reducedMotion": "system",
                "sessionMinutes": 15,
                "companion": True,
                # GM-010: the Game feedback switch is device state like the rest of this sheet.
                "gameFeedback": True,
                "classrooms": {},
            },
        )
        dirty = self.run_model(
            {
                "raw": {
                    "appearance": "sepia",
                    "defaultMode": "video",
                    "sound": "yes",
                    "reducedMotion": "sometimes",
                    "classrooms": {"crs_a": "guided", "crs_b": "cinema", "": "game"},
                }
            }
        )
        self.assertEqual(dirty["clean"]["appearance"], "system")
        self.assertEqual(dirty["clean"]["defaultMode"], "game")
        self.assertFalse(dirty["clean"]["sound"])
        self.assertEqual(dirty["clean"]["reducedMotion"], "system")
        self.assertEqual(dirty["clean"]["classrooms"], {"crs_a": "guided"})

    def test_override_resolution_and_section_reset(self):
        out = self.run_model({"raw": {"defaultMode": "textbook", "classrooms": {"crs_a": "guided"}}})
        self.assertEqual(out["effectiveDefault"], "textbook")
        self.assertEqual(out["effectiveA"], "guided")
        self.assertEqual(out["effectiveB"], "textbook")
        self.assertEqual(out["afterClassroomReset"]["classrooms"], {})
        self.assertEqual(out["classroomResetEffectiveA"], "textbook")


MODEL_HARNESS = r"""
import fs from 'node:fs'
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const mod = await import('./plugin.js')
const raw = payload.raw
const clean = mod.sanitizeCbHomePrefs(raw)
const out = { clean }
if (raw === null || raw === undefined) out.defaults = clean
if (raw && raw.defaultMode === 'textbook') {
  const reset = mod.sanitizeCbHomePrefs({ ...clean, classrooms: {} })
  out.effectiveDefault = mod.cbEffectiveMode(clean, 'crs_none')
  out.effectiveA = mod.cbEffectiveMode(clean, 'crs_a')
  out.effectiveB = mod.cbEffectiveMode(clean, 'crs_b')
  out.afterClassroomReset = reset
  out.classroomResetEffectiveA = mod.cbEffectiveMode(reset, 'crs_a')
}
process.stdout.write(JSON.stringify(out))
"""


if __name__ == "__main__":
    unittest.main()
