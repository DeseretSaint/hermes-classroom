"""H-127: a failed ``/packs/intake`` probe is not a missing capability.

The runtime plugin is one ESM file with no build step, so this test loads the shipped module. It
mounts the exported ``PackImportFlow`` in jsdom through a stub ``@hermes/plugin-sdk`` and a fake
``ctx.rest``, and drives the only two facts that matter here:

* the probe throws (transport error, timeout, 500) -> the flow says it could not check, offers
  Retry, and never claims "this backend build cannot receive a local pack";
* the probe answers ``{can_grant: false}`` -> the capability copy is shown, because that answer is
  a real answer from the host.

What this proves: the two cases render differently and a retry re-asks the host. What it does NOT
prove: that a real backend ever answers either way — that is the live rig's evidence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

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
const responses = payload.responses || {}

const calls = []
let intakeAttempts = 0

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  calls.push({ path: base, method: (options && options.method) || 'GET' })
  if (base === '/packs/intake') {
    intakeAttempts += 1
    const plan = responses['/packs/intake']
    const value = plan && plan.__sequence
      ? plan.__sequence[Math.min(intakeAttempts - 1, plan.__sequence.length - 1)]
      : plan
    if (value && value.__throw) throw new Error(value.__throw)
    return value
  }
  if (base === '/runtime') {
    return {
      wire_version: 9,
      implemented_methods: ['pack.preview', 'pack.import', 'library.list'],
      single_home_host: false
    }
  }
  if (base === '/rpc') return { ok: true, result: { items: [] } }
  throw new Error('unexpected rest path ' + path)
}

const mod = await import('./plugin.js')
mod.default.register({ rest: fakeRest, register: () => {}, onDispose: () => {} })

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))

const flush = async (ms = 40) => {
  await act(async () => { await new Promise((done) => setTimeout(done, ms)) })
}
const byText = (text) =>
  [...document.querySelectorAll('button')].find((node) => (node.textContent || '').trim() === text) || null
// The product's word for this action is the deck's one word for it, "Try again"; "Retry" is
// accepted too so the assertion is about a real control, not a particular spelling.
const retryButton = () =>
  [...document.querySelectorAll('button')].find((node) => /^(try again|retry)$/i.test((node.textContent || '').trim())) || null
const click = async (node) => {
  if (!node) throw new Error('button not found')
  await act(async () => { node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await flush()
}

const read = () => {
  const rootEl = document.getElementById('root')
  const intakeNode = document.querySelector('[data-cb-pack-intake]')
  const flow = document.querySelector('[data-cb-pack-intake-status]')
  const text = (rootEl.textContent || '').replace(/\s+/g, ' ').trim()
  return {
    html: rootEl.innerHTML,
    intake: intakeNode ? intakeNode.getAttribute('data-cb-pack-intake') : null,
    status: flow ? flow.getAttribute('data-cb-pack-intake-status') : null,
    text,
    retry: Boolean(retryButton()),
    choseFolder: Boolean(byText('Choose folder…')),
    claimsMissingCapability: text.includes('cannot receive a local pack')
  }
}

await act(async () => {
  root.render(
    React.createElement(mod.PackImportFlow, {
      implemented: new Set(['pack.preview', 'pack.import', 'library.list']),
      onCancel: () => {},
      onImported: () => {}
    })
  )
})
await flush()
await flush()

const observed = { steps: [], calls }
observed.steps.push({ step: 'probe', ...read() })

if (payload.script === 'retry') {
  await click(retryButton())
  observed.steps.push({ step: 'retried', ...read(), intakeAttempts })
}

process.stdout.write(JSON.stringify(observed))
"""


class PackIntakeCopyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-pack-intake-")
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

    def run_dom(self, *, responses: dict, script: str = "none") -> dict:
        import subprocess

        case = self.root / "case.json"
        case.write_text(json.dumps({"responses": responses, "script": script}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "dom.mjs"), str(case)],
            cwd=self.root, capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_a_failed_probe_is_never_rendered_as_a_missing_capability(self) -> None:
        data = self.run_dom(responses={"/packs/intake": {"__throw": "backend offline"}})
        probe = data["steps"][0]
        self.assertEqual(probe["status"], "unavailable")
        self.assertEqual(probe["intake"], "unavailable")
        self.assertIn("Coursebook could not ask the host whether packs can be imported", probe["text"])
        self.assertFalse(probe["claimsMissingCapability"], probe["text"])
        self.assertFalse(probe["choseFolder"], probe["text"])
        self.assertTrue(probe["retry"], probe["html"])

    def test_a_real_false_answer_keeps_the_capability_copy(self) -> None:
        data = self.run_dom(
            responses={"/packs/intake": {"ok": True, "available": False, "can_grant": False}}
        )
        probe = data["steps"][0]
        self.assertEqual(probe["intake"], "unsupported")
        self.assertIn("cannot receive a local pack", probe["text"])
        self.assertNotIn("could not ask the host whether packs can be imported", probe["text"])
        self.assertFalse(probe["retry"], probe["html"])

    def test_retry_re_asks_the_host_and_paints_the_answer(self) -> None:
        data = self.run_dom(
            responses={
                "/packs/intake": {
                    "__sequence": [
                        {"__throw": "backend offline"},
                        {"ok": True, "available": True, "can_grant": True},
                    ]
                }
            },
            script="retry",
        )
        self.assertEqual(data["steps"][0]["status"], "unavailable")
        retried = data["steps"][1]
        self.assertEqual(retried["status"], "available")
        self.assertTrue(retried["choseFolder"], retried["html"])
        intake_calls = [call for call in data["calls"] if call["path"] == "/packs/intake"]
        self.assertGreaterEqual(len(intake_calls), 2)


if __name__ == "__main__":
    unittest.main()
