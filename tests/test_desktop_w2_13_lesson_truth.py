"""W2-13 regression: the lesson surface stops claiming more than it did.

The card measures three small lies on the surface a learner reads most (``docs/CREATE-
EXPERIENCE-SPEC.md`` items 39, 40 and 42):

39. a close with no recorded evidence still said "The result is recorded on this profile";
40. pressing Enter on a link also advanced the lesson step, because the keydown exclusion list
    named buttons, textareas, inputs, selects and contenteditables but not ``a[href]``,
    ``summary`` or ``[role="button"]``;
42. the MIME type and byte count of a media artifact were printed on the learner's line, and two
    different denominators were rendered for the same session, and the lesson title had to be a
    heading.

Every test here mounts the *shipped* runtime module (``desktop/plugin.js`` — the same file the
Desktop loads) with the shared SDK stub, so what it asserts is the component, not a description of
it. Behavioural tests (Enter, the live close) run in jsdom; render-only tests use
``react-dom/server``.

The learner-facing definition used for the provenance test is explicit on purpose: text a learner
can see on the figure is the figure's text **minus** any text inside a collapsed disclosure
(``details:not([open])``), a ``[hidden]`` subtree, or an ``aria-hidden="true"`` subtree. MIME and
byte count must not survive that subtraction; the ``data-cb-media-provenance`` surface must still
carry both. Before the fix the provenance string is a bare span in the visible label row, so the
test is red; a provenance disclosure makes it green.
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
from tests.test_desktop_lesson_views import COMPLETE_BLOCKS, SDK_STUB, block, document

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import React, { act } from 'react'
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
globalThis.KeyboardEvent = dom.window.KeyboardEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const media = payload.media || null
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base.startsWith('/media/')) {
    if (!media) return { ok: false, message: 'no media in this case' }
    return { ok: true, ...media }
  }
  if (base === '/runtime') {
    return { wire_version: 27, implemented_methods: ['artifact.get'], single_home_host: false }
  }
  if (base === '/health') {
    return { ok: true, contract_version: 27, result: { db: { ready: true }, plugin_version: 'test', contract_version: 27 } }
  }
  return { ok: true, result: {} }
}

const contributions = []
mod.default.register({
  rest: fakeRest,
  register: (entry) => contributions.push(entry),
  onDispose: () => {},
  setTimeout: (fn, ms) => {
    const handle = window.setTimeout(fn, ms)
    return () => window.clearTimeout(handle)
  },
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const flush = async (ms = 60) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}
const qs = (selector) => document.querySelector(selector)

const probe = React.createElement(
  'div',
  { id: 'cb-check-probe' },
  React.createElement('a', { href: '#cb-anchor', id: 'probe-anchor' }, 'A link'),
  React.createElement(
    'details',
    { id: 'probe-details' },
    React.createElement('summary', { id: 'probe-summary' }, 'More detail'),
    React.createElement('p', {}, 'Collapsed detail')
  ),
  React.createElement('div', { id: 'probe-role-button', role: 'button', tabIndex: 0 }, 'A button-shaped div'),
  React.createElement('div', { id: 'probe-neutral' }, 'Ordinary step text')
)

const playerElement = () =>
  React.createElement(mod.LessonPlayer, {
    document: payload.document,
    sources: {},
    checkSlot: probe,
    checkLabels: payload.checkLabels || [],
    section: payload.section,
    progress: payload.progress || {},
    playerState: payload.playerState || { phase: 'awaiting_input', canCheck: false, verdict: null },
    playerController: { current: null },
    onExit: () => {},
    onReload: () => {},
    onReadSection: null,
    onSaveBlock: null,
    pronunciation: null,
    takeHome: null
  })

const mount = async (element, ms = 120) => {
  const { createRoot } = await import('react-dom/client')
  const root = createRoot(document.getElementById('root'))
  await act(async () => { root.render(element) })
  await flush(ms)
  return root
}

let out
if (payload.kind === 'player-html') {
  out = renderToStaticMarkup(playerElement())
} else if (payload.kind === 'close') {
  out = renderToStaticMarkup(
    React.createElement(mod.PlayerClose, {
      section: payload.section,
      progress: payload.progress,
      evidenceClass: payload.evidenceClass === undefined ? null : payload.evidenceClass,
      recorded: payload.recorded === undefined ? null : payload.recorded,
      onBack: () => {}
    })
  )
} else if (payload.kind === 'player-dom') {
  await mount(playerElement())
  const stop = qs('[data-cb-player-stop]')
  const step = qs('[data-cb-player-step]')
  const bar = qs('[data-cb-player-bar]')
  const title = qs('[data-cb-player-title]')
  out = JSON.stringify({
    stop: stop ? stop.getAttribute('data-cb-player-stop') : null,
    step: step ? step.getAttribute('data-cb-player-step') : null,
    barText: text(bar),
    titleTag: title ? title.tagName.toLowerCase() : null,
    titleText: text(title)
  })
} else if (payload.kind === 'enter') {
  await mount(playerElement(), 150)
  const before = text(qs('[data-cb-player-step]'))
  const target = qs(payload.selector)
  if (!target) throw new Error('no element matched ' + payload.selector)
  await act(async () => {
    target.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
  })
  await flush(120)
  out = JSON.stringify({
    before,
    after: text(qs('[data-cb-player-step]')),
    targetTag: target.tagName.toLowerCase(),
    html: document.getElementById('root').innerHTML
  })
} else if (payload.kind === 'close-live') {
  await mount(playerElement(), 150)
  const primary = qs('[data-cb-player-primary]')
  if (!primary) throw new Error('the player rendered no footer primary')
  await act(async () => { primary.click() })
  await flush(150)
  out = document.getElementById('root').innerHTML
} else if (payload.kind === 'media') {
  await mount(React.createElement(mod.MediaSegment, { segment: payload.segment }), 200)
  const figure = qs('[data-cb-media]')
  if (!figure) throw new Error('MediaSegment rendered no figure')
  const provenance = qs('[data-cb-media-provenance]')
  const clone = figure.cloneNode(true)
  for (const node of clone.querySelectorAll('details:not([open]), [hidden], [aria-hidden="true"]')) {
    node.remove()
  }
  out = JSON.stringify({
    figureText: text(figure),
    learnerText: text(clone),
    provenanceText: provenance ? text(provenance) : null,
    provenanceInDisclosure: Boolean(provenance && provenance.closest('details'))
  })
} else {
  throw new Error('unknown case kind ' + payload.kind)
}
process.stdout.write(out)
"""


def _stop() -> dict:
    return {
        "objective_id": "obj_0123456789abcdef",
        "title": "Affection and register",
        "ordinal": 2,
        "state": "needs_review",
        "evidence_target": "discrimination",
        "last_opened_at": None,
    }


def _two_step_doc() -> dict:
    """A first step that carries the section's one check (so the probe slot renders) and a
    graded pass (so the footer action is Continue/advance rather than Check)."""
    blocks = [
        block("blk_practice01", "practice", "Try it", short="Short practice.",
              deep="Deep practice prose.", check_id="chk_0123456789abcdef"),
        block("blk_recap00001", "recap", "Recap", short="Short recap.", deep="Deep recap prose."),
    ]
    return document(guided=True, blocks=blocks, check_id="chk_0123456789abcdef")


class W213RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        cls.modules_tmp = tempfile.TemporaryDirectory(prefix="cb-w213-modules-")
        staged = stage_desktop_node_modules(cls.modules_tmp.name)
        if staged is None:
            cls.modules_tmp.cleanup()
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-w213-")
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

    def run_case(self, payload: dict) -> str:
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
        return result.stdout


class Item39CloseClaimsNothingRecordedTest(W213RenderTest):
    """Item 39: no evidence, no claim that something was recorded."""

    #: The close must communicate absence. Any of these shapes is accepted; the point is that the
    #: surface says nothing was recorded instead of asserting a result exists.
    NOTHING_RECORDED = re.compile(
        r"(?i)(?:\bnothing\b[^.]{0,45}\brecord|\bno\b[^.]{0,45}\brecord|\bnot\b[^.]{0,25}\brecord"
        r"|\bwithout\b[^.]{0,25}\brecord|\bnever\b[^.]{0,25}\brecord)"
    )

    def assert_no_recorded_claim(self, html: str) -> None:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        self.assertNotIn("The result is recorded on this profile.", text)
        self.assertNotRegex(text, r"(?i)the trail shows this stop as recorded")
        self.assertRegex(
            text,
            self.NOTHING_RECORDED,
            "the close neither claims nor denies a record; it must say nothing was recorded: " + text,
        )

    def test_close_mounted_with_recorded_false_and_null_evidence_claims_no_result(self) -> None:
        html = self.run_case({
            "kind": "close",
            "section": {"ordinal": 2},
            "progress": None,
            "evidenceClass": None,
            "recorded": False,
        })
        self.assert_no_recorded_claim(html)

    def test_close_mounted_with_empty_progress_claims_no_result(self) -> None:
        html = self.run_case({
            "kind": "close",
            "section": {"ordinal": 2},
            "progress": {},
            "evidenceClass": None,
            "recorded": False,
        })
        self.assert_no_recorded_claim(html)

    def test_a_live_session_closed_without_evidence_claims_no_result(self) -> None:
        """The real path: a stop with no check, finished, reaches the close with no evidence."""
        doc = document(
            guided=True,
            blocks=[block("blk_recap00001", "recap", "Recap", short="Short recap.", deep="Deep recap prose.")],
            check_id=None,
        )
        html = self.run_case({
            "kind": "close-live",
            "document": doc,
            "section": _stop(),
            "progress": {},
            "playerState": {"phase": "awaiting_input", "canCheck": False, "verdict": None},
        })
        self.assertIn("You finished", html)
        self.assert_no_recorded_claim(html)


class Item40EnterDoesNotAdvanceTest(W213RenderTest):
    """Item 40: Enter on an interactive descendant keeps its own meaning."""

    PLAYER_CASE = {
        "kind": "enter",
        "section": _stop(),
        "progress": {"total_objectives": 4, "independent": 2, "review_due": 1},
        "playerState": {"phase": "graded", "canCheck": False, "verdict": "pass"},
    }

    def advance(self, selector: str) -> dict:
        payload = dict(self.PLAYER_CASE)
        payload["document"] = _two_step_doc()
        payload["selector"] = selector
        return json.loads(self.run_case(payload))

    def test_the_probe_is_inside_the_step_it_claims_to_test(self) -> None:
        case = self.advance("#probe-neutral")
        self.assertEqual(case["before"], "Step 1 of 2", case)
        self.assertEqual(case["after"], "Step 2 of 2", case)

    def test_enter_on_a_link_does_not_advance_the_step(self) -> None:
        case = self.advance("#probe-anchor")
        self.assertEqual(case["targetTag"], "a")
        self.assertEqual(case["before"], "Step 1 of 2")
        self.assertEqual(case["after"], "Step 1 of 2", "Enter on a[href] advanced the lesson step")

    def test_enter_on_a_summary_does_not_advance_the_step(self) -> None:
        case = self.advance("#probe-summary")
        self.assertEqual(case["targetTag"], "summary")
        self.assertEqual(case["before"], "Step 1 of 2")
        self.assertEqual(case["after"], "Step 1 of 2", "Enter on summary advanced the lesson step")

    def test_enter_on_a_role_button_does_not_advance_the_step(self) -> None:
        case = self.advance("#probe-role-button")
        self.assertEqual(case["targetTag"], "div")
        self.assertEqual(case["before"], "Step 1 of 2")
        self.assertEqual(case["after"], "Step 1 of 2", "Enter on [role=button] advanced the lesson step")


class Item42OneDenominatorTest(W213RenderTest):
    """Item 42: the stop label and the step label share one denominator."""

    def test_the_two_denominators_agree_when_the_objective_count_differs(self) -> None:
        # Four authored steps, five objectives: the two surfaces used to print /5 and /4.
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        case = json.loads(self.run_case({
            "kind": "player-dom",
            "document": doc,
            "section": _stop(),
            "progress": {"total_objectives": 5, "independent": 2, "review_due": 1},
        }))
        self.assertIsNotNone(case["stop"], case)
        self.assertIsNotNone(case["step"], case)
        stop_denominator = case["stop"].split("/")[-1]
        step_denominator = case["step"].split("/")[-1]
        self.assertTrue(stop_denominator.isdigit() and step_denominator.isdigit(), case)
        self.assertEqual(
            stop_denominator,
            step_denominator,
            f"the stop and the step still disagree: {case['stop']} vs {case['step']} ({case['barText']})",
        )
        mentioned = set(re.findall(r"(?:OF|of)\s+(\d+)", case["barText"]))
        self.assertEqual(
            mentioned,
            {stop_denominator},
            f"a second, disagreeing denominator remains on the player bar: {case['barText']}",
        )


class Item42ProvenanceTest(W213RenderTest):
    """Item 42: MIME type and byte count belong to provenance, not the learner's line."""

    MEDIA = {
        "mime": "image/png",
        "bytes": 48123,
        "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
        "text_equivalent": None,
        "label": None,
        "review": {"state": "approved", "reasons": ["the picture matches the prompt"]},
    }

    def test_learner_line_omits_mime_and_bytes_while_provenance_keeps_them(self) -> None:
        case = json.loads(self.run_case({
            "kind": "media",
            "segment": {
                "artifact_id": "art_caliper_1",
                "kind": "visual",
                "text": "A brake caliper rests on a workshop bench.",
                "label": "Illustration (context only)",
                "degraded": False,
                "reason": None,
            },
            "media": self.MEDIA,
        }))
        provenance = case["provenanceText"]
        self.assertIsNotNone(provenance, f"no provenance surface was rendered: {case['figureText']}")
        self.assertIn("image/png", provenance)
        self.assertIn("48123", provenance)
        self.assertIn("bytes", provenance)
        learner = case["learnerText"]
        self.assertNotIn("image/png", learner, f"MIME type is on the learner's line: {learner}")
        self.assertNotIn("48123", learner, f"the byte count is on the learner's line: {learner}")
        self.assertNotRegex(learner, r"(?i)\bbytes\b", f"a byte count is on the learner's line: {learner}")
        self.assertIn("A brake caliper rests on a workshop bench.", learner)


class Item42TitleHeadingTest(W213RenderTest):
    """Item 42: the lesson title is a heading, not styled text."""

    def test_the_lesson_title_is_a_heading(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        case = json.loads(self.run_case({
            "kind": "player-dom",
            "document": doc,
            "section": _stop(),
            "progress": {"total_objectives": 4, "independent": 2, "review_due": 1},
        }))
        self.assertIn(case["titleTag"], {"h1", "h2", "h3", "h4", "h5", "h6"},
                      f"the lesson title is not a heading: <{case['titleTag']}>")
        self.assertEqual(case["titleText"], "Affection and register")


if __name__ == "__main__":
    unittest.main()
