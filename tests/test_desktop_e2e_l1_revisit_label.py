"""E2E L1: the lesson page labels a reopened check "Review", never "Start".

A revisit is a check the learner already passed, served again for spaced review. The backend
projects ``revisit: true`` on ``check.get``/``lesson.page.checks`` (proven in
``tests/test_e2e_l1_revisit.py``); this file proves the shipped Desktop module renders that flag
as the word a learner reads. It mounts ``ClassroomCheckCard`` from ``desktop/plugin.js`` — the
same file the Desktop loads — through React and asserts the rendered DOM.

Two cases, the same component:

* a check carrying ``revisit: true`` renders a ``[data-cb-check-revisit]`` badge whose text is
  "Review";
* an ordinary first-pass check renders no such badge, so the word is never invented for a check
  the backend did not mark.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { JSDOM } from 'jsdom'

const fs = await import('node:fs')
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
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')
const fakeRest = async (path) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return { wire_version: 28, implemented_methods: [], single_home_host: false }
  }
  if (base === '/health') {
    return { ok: true, contract_version: 28, result: { db: { ready: true }, plugin_version: 'test', contract_version: 28 } }
  }
  return { ok: true, result: {} }
}
mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => window.setTimeout(fn, ms),
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const html = renderToStaticMarkup(
  React.createElement('div', { id: 'cb-check-probe' },
    React.createElement(mod.ClassroomCheckCard, {
      check: payload.check,
      stimulusStatus: 'ready',
      stimulusError: null,
      enrollmentId: 'enr_0000000000000001',
      objectiveId: 'obj_0123456789abcdef',
      revision: 7,
      onRevision: () => {},
      onRetryStimulus: () => {},
      onCommitted: () => {},
      onNextSection: () => {},
      busyLabel: 'Opening'
    })
  )
)

const badge = html.match(/<span[^>]*class="[^"]*badge[^"]*"[^>]*>\s*Review\s*</)
process.stdout.write(JSON.stringify({
  html,
  badgePresent: Boolean(badge),
  badgeText: badge ? 'Review' : null,
  text: html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}))
"""


def _check(*, revisit: bool) -> dict:
    check = {
        "check_id": "chk_0123456789abcdef",
        "check_version": 3,
        "evidence_target": "recall",
        "stimulus": {"prompt": "What is 2 + 2?", "format": "text"},
    }
    if revisit:
        check["revisit"] = True
    return check


class ClassroomRevisitLabelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        cls.modules_tmp = tempfile.TemporaryDirectory(prefix="cb-l1-modules-")
        staged = stage_desktop_node_modules(cls.modules_tmp.name)
        if staged is None:
            cls.modules_tmp.cleanup()
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-l1-revisit-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        staged_modules = Path(cls.modules_tmp.name) / "node_modules"
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = staged_modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        write_sdk_stub(root, SDK_STUB)
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()
        if hasattr(cls, "modules_tmp"):
            cls.modules_tmp.cleanup()

    def run_case(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    def test_a_revisit_check_says_review_and_never_start(self) -> None:
        out = self.run_case({"check": _check(revisit=True)})
        self.assertTrue(out["badgePresent"], out["html"][:2000])
        self.assertEqual(out["badgeText"], "Review")
        self.assertNotRegex(out["text"], r"(?i)\bstart\b")

    def test_a_first_pass_check_carries_no_review_badge(self) -> None:
        out = self.run_case({"check": _check(revisit=False)})
        self.assertFalse(out["badgePresent"], out["html"][:2000])
        self.assertNotIn("Review", out["text"])
