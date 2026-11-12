"""W2-5 — item 37 (a figure is big enough to teach) and item 41 (a lesson prints).

These tests exercise the shipped module ``desktop/plugin.js`` — the file the Desktop runtime
loads — not a copy:

* the media frame draws a figure at up to 70 vh and carries no fixed 380 px cap;
* the figure is a real click target, and activating it opens the same artifact at its natural
  size in a modal dialog, with Escape closing it and focus returning to the figure;
* the player renders a block's first visual media child above the concept text, and promotes
  nothing when the block has no figure;
* the lesson header offers "Print this lesson", and the printed document carries the section
  title, each block's headline and `deep` prose, the media captions and the check prompt — and
  never the reference answer.

The media render mounts the real component in jsdom against a stub `ctx.rest` that serves the
media route, so the click is a real DOM activation. What this does NOT prove: that Chromium lays
the figure out at these pixels or that its print engine applies the sheet's `@page` rules; those
are the platform's, and the print path itself is the already-shipped hidden-frame door
(``cbPrintHomeworkSheet``).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB, block, document

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
globalThis.__CB_TEST_WIDTH__ = String((process.env.CB_TEST_WIDTH || '1100'))
const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const { JSDOM } = await import('jsdom')
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
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')

const IMAGE = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
const runtime = { wire_version: 6, implemented_methods: ['artifact.get'], single_home_host: false }
const fakeRest = async (path) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') return runtime
  if (base.startsWith('/media/')) {
    return { ok: true, data_url: IMAGE, mime: 'image/png', bytes: 68 }
  }
  return { ok: false, message: 'not stubbed in this harness' }
}
mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => window.setTimeout(fn, ms),
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const { act } = React
const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 60) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}

const facts = {}

// ── item 37: the media frame ──────────────────────────────────────────────────────────────────
await act(async () => {
  root.render(React.createElement(mod.MediaSegment, { segment: payload.segment }))
})
await flush(90)
const frame = document.querySelector('[data-cb-media-frame]')
const thumb = frame && frame.querySelector('img')
facts.thumbnailStyle = thumb ? thumb.getAttribute('style') : null
const trigger = document.querySelector('[data-cb-media-open]')
facts.hasTrigger = Boolean(trigger)
facts.triggerRole = trigger ? trigger.tagName.toLowerCase() : null
facts.triggerLabel = trigger ? trigger.getAttribute('aria-label') : null

if (trigger) {
  await act(async () => { trigger.click() })
  await flush(20)
}
const viewer = document.querySelector('[data-cb-media-viewer]')
const natural = document.querySelector('[data-cb-media-natural]')
const close = document.querySelector('[data-cb-media-close]')
facts.viewer = viewer
  ? { role: viewer.getAttribute('role'), modal: viewer.getAttribute('aria-modal'), label: viewer.getAttribute('aria-label') }
  : null
facts.naturalStyle = natural ? natural.getAttribute('style') : null
facts.naturalSrc = natural ? natural.getAttribute('src') : null
facts.closeFocused = Boolean(close) && document.activeElement === close

await act(async () => {
  document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
})
await flush(20)
facts.viewerClosedByEscape = !document.querySelector('[data-cb-media-viewer]')
facts.focusReturned = Boolean(trigger) && document.activeElement === trigger

// ── item 37: the player's order ──────────────────────────────────────────────────────────────
facts.playerHtml = renderToStaticMarkup(
  React.createElement(mod.LessonPlayer, {
    document: payload.document,
    sources: {},
    checkSlot: null,
    checkLabels: [],
    section: {
      objective_id: payload.document.objective_id,
      title: payload.document.section_title,
      ordinal: 2,
      evidence_target: 'discrimination'
    },
    progress: { total_objectives: 4 },
    playerState: { phase: 'awaiting_input', canCheck: false, verdict: null },
    playerController: { current: null },
    onExit: () => {}
  })
)
facts.leadVisual = mod.playerMediaLead({ media: [{ kind: 'audio', artifact_id: 'art_a' }, { kind: 'visual', artifact_id: 'art_v' }] })
facts.leadAudioOnly = mod.playerMediaLead({ media: [{ kind: 'audio', artifact_id: 'art_a' }] })
facts.leadEmpty = mod.playerMediaLead({ media: [] })

// ── items 41: the header control and the sheet ───────────────────────────────────────────────
facts.sectionHtml = renderToStaticMarkup(
  React.createElement(mod.SectionPage, {
    row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default' },
    objectiveId: payload.document.objective_id,
    page: payload.page,
    pageStatus: 'ready',
    pageError: null,
    onRetryPage: () => {},
    implemented: new Set(['check.open', 'artifact.get', 'notebook.save']),
    onBack: () => {},
    onChanged: () => {},
    review: null
  })
)
facts.printHtml = mod.cbLessonPrintHtml(payload.document, payload.printOptions || {})

process.stdout.write(JSON.stringify(facts))
"""


def _media_child(kind: str, artifact_id: str, caption: str) -> dict:
    return {
        "kind": kind,
        "role": "illustration" if kind == "visual" else "narration",
        "artifact_id": artifact_id,
        "purpose": caption,
        "text_equivalent": caption,
        "label": "Figure" if kind == "visual" else "Narration",
    }


PROSE = "The diagram shows where the jaws clamp the workpiece."
PROMPT = "Which register would you use with a teacher?"
ANSWER = "the polite form, kudasai"


def lesson() -> dict:
    orient = block(
        "blk_orient0001",
        "orient",
        "Start here",
        short=PROSE,
        deep=PROSE,
        media=[_media_child("visual", "art_0123456789abcdef", "Jaws clamp the workpiece.")],
    )
    explain = block(
        "blk_explain001",
        "explain",
        "The mechanism",
        short="The screw closes the jaws.",
        deep="The screw closes the jaws.\n\nA second paragraph of the mechanism.",
        media=[_media_child("audio", "art_fedcba9876543210", "Read the mechanism aloud.")],
    )
    practice = block(
        "blk_practice01",
        "practice",
        "Try it <script>alert(1)</script>",
        short=PROMPT,
        deep=PROMPT,
        check_id="chk_0123456789abcdef",
    )
    # The answer key is not part of the contract's block shape. It is injected here anyway: the
    # builder must not print it even if a caller hands it over.
    practice["reference_answer"] = ANSWER
    practice["accepted_answers"] = [ANSWER]
    return document(guided=True, blocks=[orient, explain, practice], check_id="chk_0123456789abcdef")


def page(doc: dict) -> dict:
    return {
        "revision": 4,
        "section": {
            "objective_id": doc["objective_id"],
            "title": doc["section_title"],
            "ordinal": 2,
            "state": "needs_review",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        "runtime": {"lesson_run_id": "run_1", "binding_id": None, "binding_status": "detached", "session_state": "stored_only"},
        "segments": [],
        "attempts": [],
        "notebook_entries": [],
        "sources": [],
        "document": doc,
    }


class FiguresAndPrintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-w2-5-")
        root = Path(cls.tmp.name)
        if stage_desktop_node_modules(root) is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        write_sdk_stub(root, SDK_STUB)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        cls.root = root
        cls.doc = lesson()
        cls.payload = {
            "segment": {
                "artifact_id": "art_0123456789abcdef",
                "kind": "visual",
                "text": "Jaws clamp the workpiece.",
                "label": "Figure",
                "labels": [],
            },
            "document": cls.doc,
            "page": page(cls.doc),
            "printOptions": {"checkLabels": []},
        }
        cls.facts = cls.run_harness(cls.payload)

    @classmethod
    def run_harness(cls, payload: dict) -> dict:
        case = cls.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(case)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-3000:])
        return json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── item 37: size and the natural-size door ──────────────────────────────────────────────
    def test_the_media_frame_no_longer_caps_a_figure_at_380px(self) -> None:
        style = self.facts["thumbnailStyle"]
        self.assertIsNotNone(style)
        self.assertNotIn("380px", style, style)
        self.assertIn("70vh", style, style)

    def test_the_figure_is_a_click_target_that_opens_at_natural_size(self) -> None:
        self.assertTrue(self.facts["hasTrigger"])
        self.assertEqual(self.facts["triggerRole"], "button")
        self.assertIn("at full size", self.facts["triggerLabel"] or "")
        viewer = self.facts["viewer"]
        self.assertIsNotNone(viewer)
        self.assertEqual(viewer["role"], "dialog")
        self.assertEqual(viewer["modal"], "true")
        natural = self.facts["naturalStyle"] or ""
        self.assertIn("max-width:none", natural.replace(" ", ""))
        self.assertIn("max-height:none", natural.replace(" ", ""))
        self.assertTrue((self.facts["naturalSrc"] or "").startswith("data:image/png"))
        self.assertTrue(self.facts["closeFocused"], "the close control takes focus when the viewer opens")
        self.assertTrue(self.facts["viewerClosedByEscape"], "Escape closes the figure")
        self.assertTrue(self.facts["focusReturned"], "closing returns focus to the figure")

    # ── item 37: placement in the player ────────────────────────────────────────────────────
    def test_the_first_image_precedes_the_concept_text(self) -> None:
        html = self.facts["playerHtml"]
        figure = html.find("data-cb-player-figure")
        concept = html.find("data-cb-play-concept")
        self.assertGreaterEqual(figure, 0, "the step with a figure renders it")
        self.assertGreaterEqual(concept, 0)
        self.assertLess(figure, concept, "the figure is above the concept paragraph")
        self.assertEqual(html.count("data-cb-player-figure"), 1)
        # The promoted child is the visual, and it is not printed twice below the prose.
        self.assertEqual(html.count('data-cb-block-media="art_0123456789abcdef"'), 1)
        self.assertIn("Jaws clamp the workpiece.", html)

    def test_audio_is_not_promoted_above_the_prose(self) -> None:
        lead = self.facts["leadVisual"]
        self.assertEqual(lead["lead"]["artifact_id"], "art_v")
        self.assertEqual(lead["leadOrdinal"], 1)
        self.assertEqual([entry["ordinal"] for entry in lead["rest"]], [0])
        self.assertIsNone(self.facts["leadAudioOnly"]["lead"])
        self.assertIsNone(self.facts["leadEmpty"]["lead"])

    # ── item 41: print ───────────────────────────────────────────────────────────────────────
    def test_the_lesson_header_offers_print_this_lesson(self) -> None:
        html = self.facts["sectionHtml"]
        self.assertIn("data-cb-print-lesson", html)
        self.assertIn("Print this lesson", html)
        self.assertEqual(html.count("data-cb-print-lesson"), 1)

    def test_the_printed_lesson_carries_prose_prompt_and_captions(self) -> None:
        html = self.facts["printHtml"]
        self.assertIn("<h1>Affection and register</h1>", html)
        self.assertIn(PROSE, html)
        self.assertIn("A second paragraph of the mechanism.", html)
        self.assertIn("Jaws clamp the workpiece.", html)
        self.assertIn("Read the mechanism aloud.", html)
        self.assertIn(PROMPT, html)
        self.assertIn("Your turn", html)
        self.assertIn("answer key is not printed", html)

    def test_the_printed_lesson_never_carries_the_answer(self) -> None:
        html = self.facts["printHtml"]
        self.assertNotIn(ANSWER, html)
        self.assertNotIn("reference_answer", html)
        self.assertNotIn("accepted_answers", html)
        self.assertNotIn("rubric", html)
        # The check prompt is printed once, as the learner reads it — not twice.
        self.assertEqual(html.count(PROMPT), 1)

    def test_print_escapes_authored_markup(self) -> None:
        html = self.facts["printHtml"]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
