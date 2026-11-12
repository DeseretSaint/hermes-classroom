"""The Share-to-store confirmation: nothing is published before the author confirms.

The store route accepts ``confirm: true`` and then forks/pushes under the author's GitHub login.
A client that always sends ``confirm: true`` makes the server's confirmation check dead code, so
this harness drives the shipped ``WorkshopShare`` component in jsdom and proves the ordering:

* the first "Share to store" click opens a dialog and sends **no** request;
* cancel sends **no** request;
* only the dialog's publish control sends one request, and its body carries ``confirm: true``;
* the dialog names the course title, the public pull request and the fork under the author's
  GitHub account before that control is reachable.

What this does NOT prove: how the host paints the dialog. It is the ordering/copy half.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

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
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const ITEM = {
  enrollment_id: 'enr_spanish_market',
  title: 'Spanish at the market',
  recipe: 'one_off',
  locale: 'es-ES',
  course_status: 'active'
}
const requests = []
const rest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return { wire_version: 24, implemented_methods: ['library.list'], single_home_host: false }
  }
  if (base === '/rpc') {
    return {
      ok: true,
      contract_version: 24,
      operation_id: 'op-library-list',
      result: { items: [ITEM], total: 1 }
    }
  }
  if (base === '/workshop/share') {
    requests.push(options && options.body)
    return {
      ok: true,
      status: 'new',
      pack_id: 'spanish-at-the-market',
      pack_version: '1.0.0',
      mode: 'textbook',
      objectives: 3,
      media: 0,
      world_plates: 0,
      content_hash: 'sha256:1111111111111111111111111111111111111111111111111111111111111111',
      pull_request: 'https://github.com/Coursebook/coursebook/pull/7'
    }
  }
  return { ok: true, result: {} }
}

const mod = await import('./plugin.js')
mod.default.register({
  rest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => { const handle = window.setTimeout(fn, ms); return () => window.clearTimeout(handle) },
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 40) => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
const click = async (node) => {
  if (!node) throw new Error('click target is missing')
  await act(async () => {
    node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  await flush(60)
}
const text = (node) => (node ? (node.textContent || '').replace(/\s+/g, ' ').trim() : null)

await act(async () => { root.render(React.createElement(mod.WorkshopShare)) })
await flush(120)

const beforeClickRequests = requests.length
const shareButton = document.querySelector('[data-cb-workshop-share="ready"] li button')
if (!shareButton) throw new Error('the authored course row has no share control')
if (text(shareButton) !== 'Share to store') throw new Error(`unexpected share label: ${text(shareButton)}`)

await click(shareButton)
const dialog = document.querySelector('[data-cb-workshop-share-confirm]')
const firstClickRequests = requests.length
const dialogText = dialog ? text(dialog) : null
const courseLine = dialog ? text(dialog.querySelector('[data-cb-workshop-share-confirm-course]')) : null
const consequences = dialog
  ? [...dialog.querySelectorAll('[data-cb-workshop-share-confirm-consequences] li')].map(text)
  : []

await click(document.querySelector('[data-cb-workshop-share-confirm-cancel]'))
const cancelledRequests = requests.length
const dialogAfterCancel = Boolean(document.querySelector('[data-cb-workshop-share-confirm]'))

await click(document.querySelector('[data-cb-workshop-share="ready"] li button'))
await click(document.querySelector('[data-cb-workshop-share-confirm-publish]'))
await flush(120)

process.stdout.write(JSON.stringify({
  beforeClickRequests,
  firstClickRequests,
  dialogPresent: Boolean(dialog),
  dialogText,
  courseLine,
  consequences,
  cancelledRequests,
  dialogAfterCancel,
  requests,
  dialogAfterPublish: Boolean(document.querySelector('[data-cb-workshop-share-confirm]')),
  outcome: text(document.querySelector('[data-cb-workshop-share-result="ok"]'))
}))
"""


class WorkshopShareConfirmTest(unittest.TestCase):
    """One jsdom render of the shipped module; the report is cached per class."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        if _desktop_node_modules() is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-share-confirm-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        write_sdk_stub(cls.root, SDK_STUB)
        # stage_desktop_node_modules needs the host tree; write_sdk_stub above already made the
        # local package, so only the symlinks are staged here.
        modules = _desktop_node_modules()
        assert modules is not None
        node_modules = cls.root / "node_modules"
        node_modules.mkdir(exist_ok=True)
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs")],
            cwd=cls.root, capture_output=True, text=True, timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-6000:])
        cls.report = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_first_click_opens_confirm_and_sends_nothing(self) -> None:
        self.assertEqual(self.report["beforeClickRequests"], 0)
        self.assertTrue(self.report["dialogPresent"], "the share control published without asking")
        self.assertEqual(self.report["firstClickRequests"], 0, "a request left before confirmation")

    def test_confirmation_names_title_pull_request_and_fork(self) -> None:
        text = self.report["dialogText"] or ""
        self.assertIn("Spanish at the market", self.report["courseLine"] or "")
        self.assertIn("public GitHub pull request", text)
        self.assertIn("Coursebook repository", text)
        self.assertIn("fork", text.lower())
        self.assertIn("under your GitHub account", text)
        self.assertIn("Publish course", text)
        self.assertIn("Cancel", text)
        self.assertEqual(len(self.report["consequences"]), 3, self.report["consequences"])

    def test_cancel_publishes_nothing(self) -> None:
        self.assertEqual(self.report["cancelledRequests"], 0)
        self.assertFalse(self.report["dialogAfterCancel"], "Cancel left the dialog open")

    def test_confirm_true_is_sent_only_after_publishing(self) -> None:
        requests = self.report["requests"]
        self.assertEqual(len(requests), 1, requests)
        self.assertEqual(requests[0].get("enrollment_id"), "enr_spanish_market")
        self.assertIs(requests[0].get("confirm"), True)
        self.assertFalse(self.report["dialogAfterPublish"], "the dialog survived its publish action")
        self.assertIn("Pull request opened", self.report["outcome"] or "")


if __name__ == "__main__":
    unittest.main()
