"""Upgrade 26 — the host-variable remap must not depend on an explicit appearance.

What this proves, against the shipped module (`desktop/plugin.js`, built from `desktop/src`):

* with prefs.appearance left at its default (`system`), the Coursebook route root carries the same
  host-variable remap it carries when the learner picks Light or Dark explicitly — every SDK
  button, input and textarea on the route reads `--background`/`--primary`/`--ui-*` from the
  scoped `--cb-*` table either way;
* every remapped value is a `var(--cb-…)` reference to a token the route root actually declares,
  so no host accent survives on the surface;
* `system` resolves to the mode *painted*: a dark host paints the dark table, a light host the
  light one, and the remap follows without the learner naming a mode;
* every `button`, `input` and `textarea` inside `[data-cb-route]` resolves its chrome background
  to `transparent` or to an exact value from the `--cb-*`/`--cb3-*` tables the root declares.

What this does not prove: that a live host paints these variables (no live window, rig backend or
CDP probe — owner directive 2026-11-12), or that the still-v2 Courses/Studio surfaces consume
them; those are the full-migration program card, not this one. The seam is asserted, not assumed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_h147_home_settings import SETTINGS_SDK_STUB
from tests.test_desktop_lesson_views import _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
PAGE_SRC = ROOT / "desktop" / "src" / "98-page.js"
TUTOR_SRC = ROOT / "desktop" / "src" / "99-tutor.js"

#: The host variables `cbHostVars` owns. Named here so a key silently dropped from the map is a
#: test failure rather than a surface that quietly falls back to the host's own accent.
HOST_VAR_NAMES = (
    "--background",
    "--foreground",
    "--card",
    "--card-foreground",
    "--popover",
    "--popover-foreground",
    "--muted",
    "--muted-foreground",
    "--border",
    "--input",
    "--accent",
    "--accent-foreground",
    "--primary",
    "--primary-foreground",
    "--ui-text-primary",
    "--ui-text-secondary",
    "--ui-text-tertiary",
    "--ui-bg-primary",
    "--ui-bg-secondary",
    "--ui-bg-tertiary",
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
globalThis.__CB_TEST_MODE__ = payload.hostMode === 'dark' ? 'dark' : 'light'
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

// The host's namespaced JSON store. `prefs` is what the learner already saved; when it is absent
// nothing is stored at all, which is the default install (`appearance: 'system'`).
const prefsKey = payload.prefsKey || 'home-preferences.default'
const storage = {
  get(key, fallback) {
    if (key === prefsKey && payload.prefs) return payload.prefs
    return fallback
  },
  set() {},
  remove() {}
}

const rows = payload.rows || []
const runtime = {
  wire_version: 6,
  implemented_methods: ['library.list', 'course.outline', 'lesson.page', 'notebook.list'],
  single_home_host: false
}
const outlineFor = (enrollmentId) => {
  const row = rows.find((item) => item.enrollment_id === enrollmentId) || {}
  return {
    enrollment_id: enrollmentId,
    revision: 0,
    plan: { plan_id: 'pln_x', version: 1, state: 'approved', plan_hash: 'sha256:' + 'b'.repeat(64) },
    objectives: [
      {
        objective_id: 'obj_aaaaaaaaaaaaaa02',
        ordinal: 1,
        title: row.title || 'Section',
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
const flush = async (ms = 120) => {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms))
  })
}

await act(async () => {
  root.render(route.render())
})
await flush(260)

// Open the Home settings sheet so the route also paints its option buttons and switch inputs.
const trigger = document.querySelector('[data-cb-settings-open]')
if (trigger) {
  await act(async () => {
    trigger.click()
  })
  await flush(200)
}

// Inline declarations, parsed from the attribute: React writes CSS custom properties through
// setProperty, and jsdom does not enumerate them from `style`.
const inline = (node) => {
  const raw = (node && node.getAttribute && node.getAttribute('style')) || ''
  const out = {}
  for (const part of raw.split(';')) {
    const at = part.indexOf(':')
    if (at < 0) continue
    out[part.slice(0, at).trim()] = part.slice(at + 1).trim()
  }
  return out
}

const routeRoot = document.querySelector('[data-cb-route]')
if (!routeRoot) throw new Error('the route painted no [data-cb-route]')

const rootDeclared = inline(routeRoot)
const controls = []
for (const node of document.querySelectorAll('[data-cb-route] button, [data-cb-route] input, [data-cb-route] textarea')) {
  controls.push({
    tag: node.tagName.toLowerCase(),
    text: ((node.textContent || '').replace(/\s+/g, ' ').trim() || node.getAttribute('aria-label') || '').slice(0, 40),
    declared: inline(node)
  })
}

process.stdout.write(
  JSON.stringify({
    scope: routeRoot.getAttribute('data-cb-scope'),
    root: rootDeclared,
    controls,
    settingsOpen: Boolean(document.querySelector('[data-cb-settings-sheet]'))
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


def resolve(value: str, declared: dict[str, str], depth: int = 8) -> str | None:
    """Follow `var(--token)` references through the declarations on one root."""
    current = value
    for _ in range(depth):
        match = re.fullmatch(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)", current or "")
        if not match:
            return current
        if match.group(1) not in declared:
            return None
        current = declared[match.group(1)]
    return None


class HostVarsHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        if _desktop_node_modules() is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-upgrade26-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        # Private node_modules: never write the SDK stub through a symlink into the host's shared
        # install (H-208 cross-suite flake).
        stage_desktop_node_modules(cls.root)
        write_sdk_stub(cls.root, SETTINGS_SDK_STUB)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def mount(self, host_mode: str = "light", prefs: dict | None = None) -> dict:
        case = self.root / "case.json"
        payload = {"rows": [row()], "hostMode": host_mode}
        if prefs is not None:
            payload["prefs"] = prefs
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def host_map(self, snapshot: dict) -> dict[str, str]:
        return {
            name: snapshot["root"][name]
            for name in HOST_VAR_NAMES
            if name in snapshot["root"]
        }


class SystemAppearanceTest(HostVarsHarness):
    """The default install (`appearance: 'system'`) is the case the remap used to skip."""

    def test_default_appearance_carries_the_same_remap_as_an_explicit_light(self):
        # No stored preference at all: the default document, appearance='system'.
        system = self.mount("light")
        explicit = self.mount("light", prefs={"appearance": "light"})

        self.assertTrue(
            system["settingsOpen"],
            "the Home settings sheet did not open; the route sweep would prove nothing",
        )
        self.assertEqual(system["scope"], "light")
        self.assertEqual(set(self.host_map(system)), set(HOST_VAR_NAMES))
        self.assertEqual(self.host_map(system), self.host_map(explicit))

    def test_every_remapped_value_points_at_a_token_the_route_declares(self):
        snapshot = self.mount("light")
        declared = snapshot["root"]
        for name, value in self.host_map(snapshot).items():
            self.assertRegex(value, r"^var\(--cb-[a-z0-9-]+\)$", f"{name} = {value!r}")
            token = value[len("var("):-1]
            self.assertIn(token, declared, f"{name} points at {token}, which the route does not declare")
            self.assertNotEqual(
                declared[token].strip(),
                "",
                f"{name} resolves to an empty {token}",
            )

    def test_system_follows_the_host_mode_and_paints_that_table(self):
        light = self.mount("light")
        dark = self.mount("dark", prefs={"appearance": "dark"})
        system_dark = self.mount("dark")

        self.assertEqual(system_dark["scope"], "dark")
        self.assertEqual(self.host_map(system_dark), self.host_map(dark))

        light_paper = resolve(light["root"]["--background"], light["root"])
        dark_paper = resolve(system_dark["root"]["--background"], system_dark["root"])
        self.assertIsNotNone(light_paper)
        self.assertIsNotNone(dark_paper)
        self.assertNotEqual(
            light_paper,
            dark_paper,
            "a dark host painted the light table: `system` did not follow the host mode",
        )


class RouteControlSweepTest(HostVarsHarness):
    """The acceptance sweep: every route control's chrome resolves into the cb tables."""

    def test_every_route_control_background_is_transparent_or_a_cb_token_value(self):
        snapshot = self.mount("light")
        declared = snapshot["root"]
        cb_values = {
            value
            for name, value in declared.items()
            if name.startswith("--cb-") or name.startswith("--cb3-")
        }
        self.assertTrue(cb_values, "the route declared no --cb-*/--cb3-* values")

        controls = snapshot["controls"]
        self.assertTrue(controls, "the route painted no button, input or textarea")
        self.assertIn(
            "button",
            {control["tag"] for control in controls},
            "the sweep saw no button on the route",
        )
        self.assertIn(
            "input",
            {control["tag"] for control in controls},
            "the sweep saw no input on the route",
        )

        offenders = []
        for control in controls:
            # An SDK control that paints its own fill names it inline; the rest inherit the host
            # `--background` the remap re-points. Both paths are resolved through the same root.
            raw = control["declared"].get("background-color") or control["declared"].get("background") or "var(--background)"
            value = resolve(raw, declared)
            if value in {"none", "initial", "unset", "transparent", "rgba(0, 0, 0, 0)"}:
                # No fill at all is the acceptance's `transparent`: the page shows through.
                value = "transparent"
            if value is None:
                offenders.append((control, raw, "unresolved"))
            elif value != "transparent" and value not in cb_values:
                offenders.append((control, raw, value))
        self.assertEqual(offenders, [], f"host chrome survived on the route: {offenders[:5]}")


class ShippedSourceTest(unittest.TestCase):
    """The card's `git grep` evidence, as a named unittest over what ships."""

    def test_the_shipped_module_no_longer_short_circuits_a_default_appearance(self):
        shipped = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertNotIn("if (appearance !== 'light' && appearance !== 'dark') return {}", shipped)
        self.assertNotIn("cbHostVars(homePrefs.appearance)", shipped)
        self.assertNotIn("cbHostVars(panePrefs.appearance)", shipped)
        self.assertEqual(shipped.count("cbHostVars(cbMode)"), 2)
        self.assertIn("function cbHostVars(mode)", shipped)

    def test_both_scoped_roots_pass_the_painted_mode(self):
        for path in (PAGE_SRC, TUTOR_SRC):
            source = path.read_text(encoding="utf-8")
            self.assertIn(
                "...cbScopeStyle(cbMode), ...cbHostVars(cbMode)",
                source,
                f"{path.name} no longer hands the canvas and the chrome the same mode",
            )


if __name__ == "__main__":
    unittest.main()
