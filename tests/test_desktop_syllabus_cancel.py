"""Syllabus cancel must render the backend's answer, not assume it (H-134, from H-114 F16).

The runtime plugin is one ESM file with no build step, so this test mounts the shipped
``SyllabusIntakeFlow`` in jsdom with a stub ``@hermes/plugin-sdk`` and a per-method ``ctx.rest``.
It drives the real controls: paste -> acknowledge -> ``Use this text`` -> the parse stage -> ``Stop
watching this parse``. ``jobs.cancel`` is answered by the test, which is the whole point — the old
code fired it and immediately claimed the work had stopped.

What this proves:

* ``jobs.cancel`` answers ``{ok:false, ...}`` ⇒ ``data-cb-syllabus="cancel-failed"`` renders with
  the backend's own code and message, and the string ``Cancelled. Nothing further was sent.`` is
  absent. ``Retry cancel`` sends a second cancel and renders the accepted state.
* ``jobs.cancel`` answers ``{ok:true, result:{state:"cancelled"}}`` ⇒ the accepted copy.
* ``jobs.cancel`` answers ``{ok:true, result:{state:"cancel_requested"}}`` ⇒ the "may still be
  finishing" copy, never the accepted one.
* Cancelling before any parse job exists keeps ``nothing further was sent`` but names the reason
  (no job was recorded) and sends no ``jobs.cancel``.

What it does NOT prove: a live Desktop paint. These are the DOM facts of the shipped module.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import _desktop_node_modules

# A local SDK stub: this test must stand alone on a clean checkout. Buttons keep their text so
# the driver can click them; the textarea and checkbox are real inputs.
SDK_STUB = r"""
import React from 'react'

// A mutable host atom: the harness sets the focused chat before mounting, exactly like the host.
const atom = (value) => {
  let current = value
  const listeners = new Set()
  return {
    get: () => current,
    set: (next) => { current = next; for (const fn of listeners) fn(next) },
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn) }
  }
}
const el = (tag, props, children) => React.createElement(tag, props, children)
const textOf = (props) => (props && props.children !== undefined ? props.children : null)

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const SIDEBAR = 'sidebar'
export const ROUTES = 'routes'
export const PANES = 'panes'
export const PALETTE = 'palette'
export const KEYBINDS = 'keybinds'
export const useValue = (a) => a.get()
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })

export const Button = (props) =>
  el('button', {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }, textOf(props))
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) =>
  el('div', { className: 'panel-empty' }, [
    el('div', { key: 't', className: 'panel-empty-title' }, props.title || null),
    el('div', { key: 'd' }, props.description || null),
    props.action || null
  ])
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const MessageTextContent = (props) => el('div', { className: 'md' }, props.text)
export const SegmentedControl = () => null
export const Input = (props) =>
  el('input', { id: props.id || null, value: props.value, onChange: (e) => props.onChange && props.onChange(e) })
export const Textarea = (props) =>
  el('textarea', {
    id: props.id || null,
    rows: props.rows || null,
    value: props.value || '',
    disabled: Boolean(props.disabled),
    onChange: (e) => props.onChange && props.onChange(e)
  })
export const Checkbox = (props) =>
  el('input', { type: 'checkbox', checked: Boolean(props.checked), onChange: () => props.onCheckedChange && props.onCheckedChange(!props.checked) })
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const ListRow = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = () => null
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: 1280, height: 900, narrow: false })
  },
  profileRoutes: async () => [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }],
  navigate: () => {},
  notify: () => {},
  openSession: async () => ({ ok: true }),
  newChat: async () => ({ ok: true })
}
"""

ROOT = Path(__file__).resolve().parent.parent
# `COURSEBOOK_PLUGIN_JS` lets a clean checkout be verified from a shared, dirty working tree.
PLUGIN_JS = Path(os.environ.get("COURSEBOOK_PLUGIN_JS") or (ROOT / "desktop" / "plugin.js"))

ACCEPTED_COPY = "Cancelled. Nothing further was sent."
REQUESTED_COPY = (
    "Asked the backend to stop; it will not start new work. "
    "The course will not be created until you review it."
)
NO_JOB_COPY = (
    "Cancelled. Nothing further was sent — no parse job had been recorded here, "
    "so there was nothing to stop."
)

DOM_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const mod = await import('./plugin.js')

const calls = []
const routes = payload.routes || {}

function lookup(key) {
  const entry = routes[key]
  if (entry === undefined) throw new Error('unexpected rest call: ' + key)
  if (Array.isArray(entry)) {
    const next = entry.length > 1 ? entry.shift() : entry[0]
    return next
  }
  if (entry && entry.__throw) throw new Error(entry.__throw)
  return entry
}

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/rpc') {
    const method = options && options.body && options.body.method
    calls.push({ kind: 'rpc', method, payload: options.body.payload, key: options.body.idempotency_key })
    return lookup('rpc:' + method)
  }
  calls.push({ kind: 'rest', path: base })
  return lookup(base)
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {}
})

const flush = async (ms = 40) => {
  await act(async () => { await new Promise((done) => setTimeout(done, ms)) })
}
const byText = (text) =>
  [...document.querySelectorAll('button')].find((node) => (node.textContent || '').trim() === text) || null
const click = async (node) => {
  if (!node) {
    process.stderr.write('HTML-AT-FAILURE:' + document.getElementById('root').innerHTML)
    throw new Error('control not found')
  }
  await act(async () => { node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await flush()
}
const typeInto = async (node, value) => {
  const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, 'value').set
  await act(async () => {
    setter.call(node, value)
    node.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  })
  await flush()
}

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))

let cancelled = 0
await act(async () => {
  root.render(React.createElement(mod.SyllabusIntakeFlow, {
    onCancel: () => { cancelled += 1 },
    onCreated: () => {}
  }))
})
await flush()

const read = () => {
  const rootNode = document.getElementById('root')
  const marks = [...document.querySelectorAll('[data-cb-syllabus]')]
    .map((node) => node.getAttribute('data-cb-syllabus'))
  return {
    html: rootNode.innerHTML,
    text: (rootNode.textContent || '').replace(/\s+/g, ' ').trim(),
    marks,
    stage: marks.length ? marks[marks.length - 1] : null,
    cancelCalls: calls.filter((entry) => entry.method === 'jobs.cancel')
  }
}

let observed = { before: read() }

if (payload.mode === 'cancel-before-job') {
  await click(byText('Cancel'))
  observed.after = read()
  observed.cancelledCalls = cancelled
} else {
  await typeInto(document.querySelector('textarea'), 'CS 340 syllabus\nWeek 1')
  await click(document.querySelector('input[type="checkbox"]'))
  observed.beforeSubmit = read()
  await click(byText('Use this text'))
  await flush(60)
  await flush(60)
  observed.parsing = read()
  await click(byText('Stop watching this parse'))
  await flush(60)
  observed.after = read()
  if (payload.retry) {
    await click(byText('Retry cancel'))
    await flush(60)
    observed.retried = read()
  }
}

process.stdout.write(JSON.stringify(observed))
process.exit(0)
"""


def _routes(cancel_answer) -> dict:
    return {
        "/runtime": {
            "wire_version": 6,
            "implemented_methods": ["syllabus.intake.create", "syllabus.parse", "jobs.cancel"],
            "single_home_host": False,
        },
        "rpc:syllabus.intake.create": {
            "ok": True,
            "result": {"syllabus_id": "syl_cancel0001", "revision": 2, "content_sha256": "a" * 64},
        },
        "rpc:syllabus.parse": {
            "ok": True,
            "result": {"job_id": "job_parse0001", "state": "queued"},
        },
        "rpc:jobs.cancel": cancel_answer,
    }


class SyllabusCancelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-syllabus-cancel-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "dom.mjs").write_text(DOM_HARNESS, encoding="utf-8")
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
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_dom(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "dom.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_a_refused_cancel_renders_the_real_error_and_not_the_cancelled_claim(self) -> None:
        data = self.run_dom({
            "mode": "cancel-parse",
            "routes": _routes({
                "ok": False,
                "error": {"code": "JOB_NOT_CANCELLABLE", "message": "job is cancelled and cannot be cancelled."},
            }),
        })
        self.assertEqual(data["parsing"]["stage"], "parsing")
        after = data["after"]
        self.assertEqual(after["stage"], "cancel-failed")
        self.assertIn("JOB_NOT_CANCELLABLE", after["text"])
        self.assertIn("job is cancelled and cannot be cancelled.", after["text"])
        self.assertIn("may still be running", after["text"])
        self.assertNotIn(ACCEPTED_COPY, after["text"])
        self.assertNotIn(REQUESTED_COPY, after["text"])
        # The cancel really was asked for, once, with the minted job id.
        self.assertEqual(len(after["cancelCalls"]), 1)
        self.assertEqual(after["cancelCalls"][0]["payload"]["job_id"], "job_parse0001")

    def test_retry_after_a_refusal_renders_the_accepted_state(self) -> None:
        data = self.run_dom({
            "mode": "cancel-parse",
            "retry": True,
            "routes": _routes([
                {"ok": False, "error": {"code": "HOST_UNAVAILABLE", "message": "the backend did not answer"}},
                {"ok": True, "result": {"job_id": "job_parse0001", "state": "cancelled"}},
            ]),
        })
        self.assertEqual(data["after"]["stage"], "cancel-failed")
        self.assertNotIn(ACCEPTED_COPY, data["after"]["text"])
        self.assertEqual(data["retried"]["stage"], "cancel-accepted")
        self.assertIn(ACCEPTED_COPY, data["retried"]["text"])
        self.assertEqual(len(data["retried"]["cancelCalls"]), 2)

    def test_an_accepted_cancel_renders_the_cancelled_copy(self) -> None:
        data = self.run_dom({
            "mode": "cancel-parse",
            "routes": _routes({"ok": True, "result": {"job_id": "job_parse0001", "state": "cancelled"}}),
        })
        after = data["after"]
        self.assertEqual(after["stage"], "cancel-accepted")
        self.assertIn(ACCEPTED_COPY, after["text"])
        self.assertNotIn(REQUESTED_COPY, after["text"])

    def test_a_running_job_renders_the_may_still_be_finishing_copy(self) -> None:
        data = self.run_dom({
            "mode": "cancel-parse",
            "routes": _routes({"ok": True, "result": {"job_id": "job_parse0001", "state": "cancel_requested"}}),
        })
        after = data["after"]
        self.assertEqual(after["stage"], "cancel-requested")
        self.assertIn(REQUESTED_COPY, after["text"])
        self.assertNotIn(ACCEPTED_COPY, after["text"])

    def test_cancelling_before_any_job_keeps_the_honest_sentence_and_says_why(self) -> None:
        data = self.run_dom({"mode": "cancel-before-job", "routes": _routes({"ok": True, "result": {}})})
        after = data["after"]
        self.assertIn("cancelled-before-job", after["marks"])
        self.assertIn(NO_JOB_COPY, after["text"])
        self.assertIn("nothing to stop", after["text"])
        self.assertEqual(after["cancelCalls"], [], "no job id means no jobs.cancel may be sent")
        self.assertEqual(data["cancelledCalls"], 0, "the flow stays mounted so the copy is visible")


if __name__ == "__main__":
    unittest.main()
