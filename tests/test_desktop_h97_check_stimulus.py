"""H-97: a check is never rendered without its question.

``check.open`` carries identity only; the learner-facing prompt, choices and checklist items come
from a second ``check.get`` read. That read used to end in ``.catch(() => {})``, so a rejection left
the card saying "The question and any choices are shown above" with no question anywhere and an
active Submit button. These cases render the shipped module two ways:

* ``react-dom/server`` for the four stimulus states, so the card's copy and controls are asserted
  directly (identity retained, exactly one Retry, no answer form while unavailable);
* a live ``jsdom`` mount of the real ``useOpenCheck`` hook over a stubbed ``ctx.rest``, so a
  rejected read, an empty result, a build without ``check.get``, and a Retry that succeeds are all
  exercised as the component actually runs them.
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

# Textarea is drawn as nothing in the shared stub; these cases must see whether an answer field
# exists, so the stub is extended in place rather than forked.
STUB = SDK_STUB.replace(
    "export const Textarea = () => null",
    "export const Textarea = (props) =>\n"
    "  el('textarea', { id: props.id || null, rows: props.rows || null, 'data-cb-textarea': 'true' }, props.value || null)",
)

STATIC_HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { AttemptControls } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const html = renderToStaticMarkup(
  React.createElement(AttemptControls, {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    check: payload.check,
    revision: 3,
    implemented: new Set(payload.implemented || []),
    bindingState: payload.bindingState || 'active',
    stimulusStatus: payload.stimulusStatus,
    stimulusError: payload.stimulusError || null,
    onRetryStimulus: payload.retry === false ? null : () => {},
    onCommitted: () => {}
  })
)
process.stdout.write(html)
"""

LIVE_HARNESS = """
import React from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import plugin, { AttemptControls, useOpenCheck } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/'
})
globalThis.window = dom.window
globalThis.document = dom.window.document
for (const name of ['HTMLElement', 'Node', 'Event', 'MouseEvent']) {
  if (globalThis[name] === undefined) globalThis[name] = dom.window[name]
}
globalThis.IS_REACT_ACT_ENVIRONMENT = false

const calls = []
let getAttempts = 0
const checkId = 'chk_0123456789abcdef'

const ctx = {
  register: () => {},
  onDispose: () => {},
  rest: async (path, options = {}) => {
    if (String(path).startsWith('/runtime')) {
      return {
        wire_version: 16,
        implemented_methods: payload.runtimeMethods || [],
        single_home_host: false
      }
    }
    const body = options.body || {}
    calls.push(body.method)
    if (body.method === 'check.open') {
      return {
        ok: true,
        contract_version: 16,
        operation_id: body.operation_id,
        result: { check_id: checkId, check_version: 1, evidence_target: 'discrimination' }
      }
    }
    if (body.method === 'check.get') {
      getAttempts += 1
      if (payload.mode === 'reject') throw new Error('socket closed while reading the check')
      if (payload.mode === 'retry' && getAttempts === 1) throw new Error('socket closed while reading the check')
      if (payload.mode === 'empty') {
        return { ok: true, contract_version: 16, operation_id: body.operation_id, result: {} }
      }
      return {
        ok: true,
        contract_version: 16,
        operation_id: body.operation_id,
        result: { stimulus: payload.stimulus }
      }
    }
    return {
      ok: false,
      contract_version: 16,
      operation_id: body.operation_id,
      error: { code: 'UNKNOWN', category: 'internal', message: 'unexpected method ' + body.method }
    }
  }
}

plugin.register(ctx)

const implemented = new Set(payload.implemented || [])

function Probe() {
  const check = useOpenCheck({
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    revision: 3,
    enabled: true,
    implemented
  })
  const attrs = {
    id: 'cb-probe',
    'data-check-status': check.status,
    'data-stimulus': check.stimulusStatus
  }
  const surface = check.check
    ? React.createElement(AttemptControls, {
        enrollmentId: 'enr_0123456789abcdef',
        objectiveId: 'obj_0123456789abcdef',
        check: check.check,
        revision: 3,
        implemented,
        bindingState: 'active',
        stimulusStatus: check.stimulusStatus,
        stimulusError: check.stimulusError,
        onRetryStimulus: check.reload,
        onCommitted: () => {}
      })
    : React.createElement('div', { id: 'cb-probe-wait' }, check.status)
  return React.createElement('div', attrs, surface)
}

const root = createRoot(document.getElementById('root'))
root.render(React.createElement(Probe))

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const waitFor = async (predicate, timeout = 5000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (predicate()) return true
    await sleep(20)
  }
  return false
}
const probe = () => document.getElementById('cb-probe')
const stimulusState = () => (probe() ? probe().getAttribute('data-stimulus') : null)
const checkStatus = () => (probe() ? probe().getAttribute('data-check-status') : null)

const retryButton = () =>
  Array.from(document.querySelectorAll('button')).find((button) => button.textContent.trim() === 'Retry')

if (payload.mode === 'reject' || payload.mode === 'empty') {
  await waitFor(() => stimulusState() === 'unavailable')
} else if (payload.mode === 'unsupported') {
  await waitFor(() => checkStatus() === 'ready' && stimulusState() === 'unsupported')
} else if (payload.mode === 'ready') {
  await waitFor(() => stimulusState() === 'ready')
} else if (payload.mode === 'retry') {
  await waitFor(() => stimulusState() === 'unavailable')
  const button = retryButton()
  if (button) button.click()
  await waitFor(() => stimulusState() === 'ready')
}

const text = document.body.textContent.replace(/\\s+/g, ' ').trim()
process.stdout.write(
  JSON.stringify({
    status: checkStatus(),
    stimulus: stimulusState(),
    text,
    html: document.body.innerHTML,
    calls,
    getAttempts
  })
)
"""


class CheckStimulusRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h97-stimulus-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "static.mjs").write_text(STATIC_HARNESS, encoding="utf-8")
        (root / "live.mjs").write_text(LIVE_HARNESS, encoding="utf-8")
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
        (sdk / "index.js").write_text(STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def _run(self, harness: str, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / harness), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return result.stdout

    def render(self, payload: dict) -> str:
        return self._run("static.mjs", payload)

    def live(self, payload: dict) -> dict:
        return json.loads(self._run("live.mjs", payload))

    # -- fixtures ----------------------------------------------------------------------------
    def check(self, **stimulus) -> dict:
        base = {
            "check_id": "chk_0123456789abcdef",
            "check_version": 1,
            "evidence_target": "discrimination",
        }
        if stimulus:
            base["stimulus"] = stimulus
        return base

    WRITTEN_STIMULUS = {
        "prompt": "Which register does おつかれさま belong to?",
        "choices": ["casual", "workplace", "ceremonial"],
        "format": "short_answer",
    }

    # -- static states -----------------------------------------------------------------------
    def test_a_failed_read_names_the_question_and_offers_one_retry(self) -> None:
        html = self.render(
            {
                "check": self.check(),
                "implemented": ["check.get"],
                "stimulusStatus": "unavailable",
                "stimulusError": {"code": "HOST_UNAVAILABLE", "message": "socket closed while reading the check"},
            }
        )
        self.assertIn("The question could not be loaded", html)
        self.assertIn("HOST_UNAVAILABLE", html)
        self.assertIn("socket closed while reading the check", html)
        # The check itself survives the failed detail read.
        self.assertIn("Check v1", html)
        self.assertIn("discrimination", html)
        # Exactly one action, and it is a Retry.
        self.assertEqual(html.count(">Retry</button>"), 1, html)
        # No blind answer surface and no false claim about a prompt above it.
        self.assertNotIn("cb-attempt-answer", html)
        self.assertNotIn("Submit answer", html)
        self.assertNotIn("shown above", html)

    def test_b_an_empty_result_is_the_same_named_failure(self) -> None:
        html = self.render(
            {
                "check": self.check(),
                "implemented": ["check.get"],
                "stimulusStatus": "unavailable",
                "stimulusError": None,
            }
        )
        self.assertIn("The question could not be loaded", html)
        self.assertIn("returned no question", html)
        self.assertEqual(html.count(">Retry</button>"), 1, html)
        self.assertNotIn("cb-attempt-answer", html)
        self.assertNotIn("Submit answer", html)
        self.assertNotIn("shown above", html)

    def test_c_a_build_without_check_get_never_claims_the_question_is_above(self) -> None:
        html = self.render(
            {
                "check": self.check(),
                "implemented": [],
                "stimulusStatus": "unsupported",
            }
        )
        # The legacy surface stays usable, but it points at the teaching chat instead of inventing
        # a prompt that this build cannot read.
        self.assertIn("in the teaching chat", html)
        self.assertNotIn("shown above", html)
        self.assertIn("cb-attempt-answer", html)
        self.assertNotIn("The question could not be loaded", html)

    def test_d_a_loading_read_holds_the_form_back(self) -> None:
        html = self.render(
            {
                "check": self.check(),
                "implemented": ["check.get"],
                "stimulusStatus": "loading",
            }
        )
        self.assertIn("Loading the question", html)
        self.assertNotIn("cb-attempt-answer", html)
        self.assertNotIn("Submit answer", html)
        self.assertNotIn("shown above", html)

    def test_e_a_ready_stimulus_renders_the_prompt_and_the_form(self) -> None:
        html = self.render(
            {
                "check": self.check(**self.WRITTEN_STIMULUS),
                "implemented": ["check.get"],
                "stimulusStatus": "ready",
            }
        )
        self.assertIn("Which register does おつかれさま belong to?", html)
        self.assertIn("workplace", html)
        self.assertIn("shown above", html)
        self.assertIn("cb-attempt-answer", html)
        self.assertNotIn("The question could not be loaded", html)
        self.assertNotIn(">Retry</button>", html)

    # -- the live hook -----------------------------------------------------------------------
    def test_f_a_rejected_check_get_is_visible_and_retryable(self) -> None:
        out = self.live(
            {
                "mode": "reject",
                "implemented": ["check.get"],
                "runtimeMethods": ["check.open", "check.get"],
            }
        )
        self.assertEqual(out["status"], "ready", out)
        self.assertEqual(out["stimulus"], "unavailable", out)
        self.assertIn("The question could not be loaded", out["text"])
        self.assertIn("HOST_UNAVAILABLE", out["text"])
        self.assertIn(">Retry</button>", out["html"])
        self.assertNotIn("shown above", out["text"])
        self.assertNotIn("cb-attempt-answer", out["html"])
        self.assertNotIn("Submit answer", out["text"])
        self.assertEqual(out["calls"], ["check.open", "check.get"], out["calls"])

    def test_g_an_empty_check_get_result_is_named_not_answered(self) -> None:
        out = self.live(
            {
                "mode": "empty",
                "implemented": ["check.get"],
                "runtimeMethods": ["check.open", "check.get"],
            }
        )
        self.assertEqual(out["stimulus"], "unavailable", out)
        self.assertIn("The question could not be loaded", out["text"])
        self.assertIn("returned no question", out["text"])
        self.assertNotIn("shown above", out["text"])
        self.assertNotIn("cb-attempt-answer", out["html"])
        self.assertNotIn("Submit answer", out["text"])

    def test_h_a_build_without_check_get_does_not_read_or_claim_a_question(self) -> None:
        out = self.live({"mode": "unsupported", "implemented": [], "runtimeMethods": ["check.open"]})
        self.assertEqual(out["stimulus"], "unsupported", out)
        self.assertEqual(out["calls"], ["check.open"], out["calls"])
        self.assertNotIn("shown above", out["text"])
        self.assertIn("in the teaching chat", out["text"])
        self.assertIn("cb-attempt-answer", out["html"])
        self.assertNotIn("The question could not be loaded", out["text"])

    def test_i_a_ready_read_shows_the_real_question(self) -> None:
        out = self.live(
            {
                "mode": "ready",
                "implemented": ["check.get"],
                "runtimeMethods": ["check.open", "check.get"],
                "stimulus": self.WRITTEN_STIMULUS,
            }
        )
        self.assertEqual(out["stimulus"], "ready", out)
        self.assertIn("Which register does おつかれさま belong to?", out["text"])
        self.assertIn("shown above", out["text"])
        self.assertIn("cb-attempt-answer", out["html"])
        self.assertNotIn("The question could not be loaded", out["text"])

    def test_j_retry_recovers_the_question_after_a_failed_read(self) -> None:
        out = self.live(
            {
                "mode": "retry",
                "implemented": ["check.get"],
                "runtimeMethods": ["check.open", "check.get"],
                "stimulus": self.WRITTEN_STIMULUS,
            }
        )
        self.assertEqual(out["stimulus"], "ready", out)
        self.assertGreaterEqual(out["getAttempts"], 2, out)
        self.assertIn("Which register does おつかれさま belong to?", out["text"])
        self.assertNotIn("The question could not be loaded", out["text"])
        self.assertNotIn(">Retry</button>", out["html"])

    # -- the silent catch is gone ------------------------------------------------------------
    def test_k_no_silent_catch_on_the_stimulus_read(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        hook = source[source.index("function useOpenCheck") : source.index("const SELECTION_MAX_CHARS")]
        self.assertNotIn(".catch(() => {})", hook)
        self.assertIn("stimulusStatus: 'unavailable'", hook)
        self.assertIsNotNone(re.search(r"\.catch\(\(error\) => \{", hook))


if __name__ == "__main__":
    unittest.main()
