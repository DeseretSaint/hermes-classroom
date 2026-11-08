"""A lost teaching snapshot is rendered as an integrity notice, not a silent zero.

H-124 made the backend durable: a teaching turn whose ``lesson_segments`` row could not be written
after one retry leaves a ``hook_errors`` row, and ``binding.get`` — the read the lesson pane already
makes on open — answers ``binding.snapshot_failures = {recorded, last_at}`` for that lesson run.

This test mounts the shipped module in jsdom and proves the three states stay distinct:

* ``recorded = 1``  — the count line names the loss and the chat that still has the turn;
* ``recorded = 0``  — nothing is rendered (the normal case stays silent);
* ``recorded = null`` — the unknown line, never the count line and never a zero.

The reservation deliberately absent: no dialog, no disabled control and no retry, because a retry
writes a new turn and cannot recover the lost one. The pane-level case mounts the real
``LessonPaneBody`` with a scripted ``ctx.rest`` so the notice is proven wired into the surface, not
just exported beside it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

COUNT_COPY = "1 teaching turn could not be saved to this lesson. The chat has them; this page does not."
PLURAL_COPY = "2 teaching turns could not be saved to this lesson. The chat has them; this page does not."
UNKNOWN_COPY = "Coursebook could not check whether any teaching turn was lost."

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

const IMPLEMENTED = payload.implemented || ['library.list', 'lesson.page', 'review.queue']
const rpcMethods = []

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') return { wire_version: 14, implemented_methods: IMPLEMENTED }
  if (base === '/health') return { ok: true, db: { ready: true } }
  if (base !== '/rpc') throw new Error('unexpected rest path ' + path)
  const body = typeof options.body === 'string' ? JSON.parse(options.body) : options.body
  rpcMethods.push(body.method)
  const entry = (payload.responses || {})[body.method]
  if (entry === undefined) throw new Error('unexpected rpc ' + body.method)
  return {
    ok: true,
    contract_version: 14,
    operation_id: body.operation_id,
    result: entry.result || {}
  }
}

const mod = await import('./plugin.js')
mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => setTimeout(fn, ms)
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))

let element
if (payload.kind === 'notice') {
  element = React.createElement(mod.SnapshotLossNotice, { failures: payload.failures })
} else {
  element = React.createElement(mod.LessonPaneBody, {
    binding: payload.binding,
    storedId: payload.binding.stored_session_id
  })
}

const flush = async (ms = 60) => {
  await act(async () => { await new Promise((done) => setTimeout(done, ms)) })
}

await act(async () => { root.render(element) })
await flush()

const notice = document.querySelector('[data-cb-snapshot-loss]')
const buttons = [...document.querySelectorAll('button')]
process.stdout.write(JSON.stringify({
  text: document.getElementById('root').textContent || '',
  loss: notice ? notice.getAttribute('data-cb-snapshot-loss') : null,
  count: notice ? notice.getAttribute('data-cb-snapshot-count') : null,
  role: notice ? notice.getAttribute('role') : null,
  dialogs: document.querySelectorAll('[role="dialog"], dialog').length,
  disabled: buttons.filter((button) => button.disabled).length,
  retryLabels: buttons.map((button) => (button.textContent || '').trim()).filter((text) => text === 'Retry'),
  rpcMethods
}))
"""

SDK_STUB = """
import React from 'react'

const atom = (value) => ({ get: () => value })
const el = (tag, props, children) => React.createElement(tag, props, children)
const textOf = (props) => (props && props.children !== undefined ? props.children : null)

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const useValue = (a) => a.get()
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })

export const Button = (props) =>
  el('button', { type: 'button', disabled: Boolean(props.disabled), onClick: props.onClick }, textOf(props))
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const ListRow = (props) => el('div', { className: 'list-row' }, props.title)
export const SegmentedControl = (props) =>
  el('div', { className: 'segmented' }, (props.options || []).map((option) =>
    el('button', { key: option.id, 'aria-pressed': option.id === props.value, type: 'button' }, option.label)))
export const Input = () => null
export const Textarea = () => null
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const Checkbox = () => null
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
export const MessageTextContent = (props) => el('div', { className: 'md' }, props.text)

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom('sess_0123456789abcdef'),
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


def _desktop_node_modules() -> Path | None:
    candidates = [
        os.environ.get("HERMES_DESKTOP_APP"),
        str(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop"),
        str(Path.home() / ".hermes" / "hermes-agent"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        react = Path(candidate) / "node_modules" / "react"
        server = Path(candidate) / "node_modules" / "react-dom" / "server.js"
        if react.is_dir() and server.is_file():
            return Path(candidate) / "node_modules"
    return None


def binding(**overrides) -> dict:
    payload = {
        "binding_id": "bnd_0123456789abcdef",
        "id": "bnd_0123456789abcdef",
        "enrollment_id": "enr_0123456789abcdef",
        "profile": "default",
        "connection_id": "local",
        "runtime_session_id": "run_live_1",
        "stored_session_id": "sess_0123456789abcdef",
        "lesson_run_id": "run_0123456789abcdef",
        "objective_id": "obj_0000000000000003",
        "snapshot_failures": {"recorded": 0, "last_at": None},
        "status": "active",
        "revision": 3,
        "updated_at": "2026-11-07T18:00:00.000000+00:00",
    }
    payload.update(overrides)
    return payload


def library_row() -> dict:
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "course_id": "crs_0123456789abcdef",
        "title": "Small-engine maintenance",
        "subtitle": None,
        "recipe": "committed",
        "level_label": None,
        "locale": None,
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "continue_lesson", "label": "Continue the ignition lesson"},
        "evidence_summary": {
            "independent": 0,
            "review_due": 0,
            "total_objectives": 4,
            "current_objective_id": "obj_0000000000000003",
        },
        "warning": None,
        "revision": 3,
    }


def lesson_page() -> dict:
    return {
        "revision": 3,
        "section": {
            "objective_id": "obj_0000000000000003",
            "title": "Check the spark",
            "state": "in_progress",
            "evidence_target": "procedure",
            "last_opened_at": None,
        },
        "runtime": {
            "lesson_run_id": "run_0123456789abcdef",
            "binding_id": "bnd_0123456789abcdef",
            "binding_status": "active",
            "session_state": "stored_only",
        },
        "segments": [],
        "attempts": [],
        "notebook_entries": [],
        "sources": [],
        "document": None,
    }


class SnapshotLossNoticeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-snapshot-loss-")
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
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
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
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    def notice(self, failures) -> dict:
        return self.run_dom({"kind": "notice", "failures": failures})

    # --- the three distinguished states -------------------------------------------------

    def test_a_recorded_loss_names_the_count_and_the_chat(self) -> None:
        observed = self.notice({"recorded": 1, "last_at": None})
        self.assertEqual(observed["loss"], "recorded")
        self.assertEqual(observed["count"], "1")
        self.assertEqual(observed["role"], "status")
        self.assertIn(COUNT_COPY, observed["text"])

    def test_the_plural_is_handled(self) -> None:
        observed = self.notice({"recorded": 2, "last_at": None})
        self.assertEqual(observed["count"], "2")
        self.assertIn(PLURAL_COPY, observed["text"])
        self.assertNotIn("2 teaching turn could", observed["text"])

    def test_last_at_is_shown_as_a_relative_time_in_the_secondary_line(self) -> None:
        last_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        observed = self.notice({"recorded": 1, "last_at": last_at})
        self.assertIn(COUNT_COPY, observed["text"])
        self.assertIn("Last recorded 5 min ago.", observed["text"])

    def test_a_healthy_lesson_renders_no_notice_at_all(self) -> None:
        observed = self.notice({"recorded": 0, "last_at": None})
        self.assertIsNone(observed["loss"])
        self.assertNotIn("could not be saved", observed["text"])
        self.assertNotIn("could not check", observed["text"])

    def test_an_unknown_count_is_not_a_zero(self) -> None:
        observed = self.notice({"recorded": None, "last_at": None})
        self.assertEqual(observed["loss"], "unknown")
        self.assertIn(UNKNOWN_COPY, observed["text"])
        self.assertNotIn("could not be saved to this lesson", observed["text"])
        self.assertNotIn("The chat has them; this page does not.", observed["text"])
        self.assertNotIn("0 teaching", observed["text"])

    def test_an_unreadable_answer_is_unknown_not_silent(self) -> None:
        observed = self.notice(None)
        self.assertEqual(observed["loss"], "unknown")
        self.assertIn(UNKNOWN_COPY, observed["text"])

    # --- it is a notice, never a blocking error -----------------------------------------

    def test_the_notice_offers_no_dialog_no_disabled_control_and_no_retry(self) -> None:
        observed = self.notice({"recorded": 3, "last_at": None})
        self.assertEqual(observed["dialogs"], 0)
        self.assertEqual(observed["retryLabels"], [])
        self.assertEqual(observed["disabled"], 0)

    # --- wired into the real lesson pane ------------------------------------------------

    def pane(self, failures) -> dict:
        return self.run_dom(
            {
                "kind": "pane",
                "binding": binding(snapshot_failures=failures),
                "responses": {
                    "library.list": {"result": {"items": [library_row()], "total": 1}},
                    "lesson.page": {"result": lesson_page()},
                    "review.queue": {"result": {"total_overdue": 0, "items": []}},
                },
            }
        )

    def test_the_bound_lesson_pane_renders_the_recorded_loss(self) -> None:
        observed = self.pane({"recorded": 1, "last_at": None})
        self.assertEqual(observed["loss"], "recorded")
        self.assertEqual(observed["count"], "1")
        self.assertIn(COUNT_COPY, observed["text"])
        self.assertIn("Check the spark", observed["text"])

    def test_the_bound_lesson_pane_stays_silent_when_nothing_was_lost(self) -> None:
        observed = self.pane({"recorded": 0, "last_at": None})
        self.assertIsNone(observed["loss"])
        self.assertIn("Check the spark", observed["text"])
        self.assertNotIn("could not be saved to this lesson", observed["text"])

    def test_the_bound_lesson_pane_says_unknown_when_the_count_could_not_be_read(self) -> None:
        observed = self.pane({"recorded": None, "last_at": None})
        self.assertEqual(observed["loss"], "unknown")
        self.assertIn(UNKNOWN_COPY, observed["text"])
        self.assertNotIn("could not be saved to this lesson", observed["text"])


if __name__ == "__main__":
    unittest.main()
