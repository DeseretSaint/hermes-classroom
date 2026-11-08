"""Textbook and Guided are two lenses over one validated lesson document.

The runtime plugin is one ESM file with no build step, so the honest test is to render the real
module: React and ``react-dom/server`` render the shipped components (hooks included), and a stub
``@hermes/plugin-sdk`` supplies the SDK components the tree reaches. The document below is a
contract v8 ``lesson_document`` (``contracts/rpc.v8.json``): the same block ids, the same single
check, the same source ids in both views.

What this does NOT prove: that a backend authors ``short`` today. It proves the renderer honours
the document it is served, including the honest ``textbook_only`` refusal.
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

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { LessonDocumentView, SectionPage } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source
const checkNode = React.createElement('div', { id: 'cb-check-node' }, 'CHECK-NODE')
let html
if (payload.kind === 'section') {
  const page = {
    revision: 4,
    section: {
      objective_id: payload.document.objective_id,
      title: payload.document.section_title,
      state: 'needs_review',
      evidence_target: 'discrimination',
      last_opened_at: null
    },
    runtime: payload.runtimeNull
      ? null
      : { lesson_run_id: 'run_1', binding_id: null, binding_status: 'detached', session_state: 'stored_only' },
    segments: [],
    attempts: [],
    notebook_entries: [],
    sources: payload.sources || [],
    document: payload.document
  }
  html = renderToStaticMarkup(
    React.createElement(SectionPage, {
      row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default' },
      objectiveId: payload.document.objective_id,
      page,
      pageStatus: 'ready',
      pageError: null,
      onRetryPage: () => {},
      implemented: new Set(['check.open', 'artifact.get', 'notebook.save']),
      onBack: () => {},
      onChanged: () => {},
      review: null
    })
  )
} else {
  html = renderToStaticMarkup(
    React.createElement(LessonDocumentView, {
      document: payload.document,
      view: payload.view,
      sources: index,
      checkSlot: payload.withCheck === false ? null : checkNode
    })
  )
}
process.stdout.write(html)
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
export const useTheme = () => ({
  renderedMode: globalThis.__CB_TEST_MODE__ === 'dark' ? 'dark' : 'light',
  resolvedMode: globalThis.__CB_TEST_MODE__ === 'dark' ? 'dark' : 'light'
})

export const Button = (props) => {
  const attrs = {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }
  if (props.className) attrs.className = props.className
  if (props.title) attrs.title = props.title
  for (const [name, value] of Object.entries(props)) {
    if ((name.startsWith('data-') || name.startsWith('aria-')) && value !== undefined && !(name in attrs)) {
      attrs[name] = value
    }
  }
  return el('button', attrs, textOf(props))
}
export const RowButton = (props) => {
  // The real RowButton is a bare `<button>` that spreads every prop, so a caller's style, focus
  // handlers and key handler reach the DOM. A stub that only forwarded aria-/data- made the shelf's
  // focus ring and its Enter/Space path invisible to a jsdom test.
  const attrs = { type: 'button' }
  for (const [name, value] of Object.entries(props)) {
    if (name === 'children' || value === undefined) continue
    attrs[name] = value
  }
  return el('button', attrs, textOf(props))
}
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't', className: 'empty-title' }, props.title), el('div', { key: 'd' }, props.description)])
export const MessageTextContent = (props) => el('div', { className: 'md' }, props.text)
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
export const ListRow = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = () => null
export const Checkbox = (props) =>
  el('input', {
    type: 'checkbox',
    checked: Boolean(props.checked),
    disabled: Boolean(props.disabled),
    id: props.id || null,
    'aria-label': props['aria-label'] || null,
    'data-cb-check-tick': props['data-cb-check-tick'] || null,
    onChange: () => props.onCheckedChange && props.onCheckedChange(!props.checked)
  })
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null

export const SIDEBAR = 'sidebar'
export const ROUTES = 'routes'
export const PANES = 'panes'
export const PALETTE = 'palette'
export const KEYBINDS = 'keybinds'

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: Number(globalThis.__CB_TEST_WIDTH__ || 1280), height: 900, narrow: false })
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


def document(*, guided: bool, blocks: list[dict], check_id: str | None, state: str | None = None,
             note: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "document_id": "doc_0123456789abcdef0123",
        "content_hash": "sha256:" + "a" * 64,
        "section_title": "Affection and register",
        "objective_id": "obj_0123456789abcdef",
        "state": state or ("complete" if guided else "textbook_only"),
        "view_note": note,
        "views": {"textbook": True, "guided": guided, "field_quest": False, "field_notes": False},
        "blocks": blocks,
        "check_id": check_id,
        "source_ids": ["src_affection01"],
    }


def block(block_id: str, role: str, headline: str, *, short: str | None, deep: str,
          check_id: str | None = None, media: list[dict] | None = None,
          source_ids: list[str] | None = None) -> dict:
    return {
        "id": block_id,
        "role": role,
        "headline": headline,
        "short": short,
        "deep": deep,
        "check_id": check_id,
        "media": media or [],
        "source_ids": source_ids or [],
    }


COMPLETE_BLOCKS = [
    block("blk_orient0001", "orient", "Start here", short="Short orient.", deep="Deep orient prose.",
          source_ids=["src_affection01"]),
    block("blk_explain001", "explain", "The mechanism", short="Short explain.", deep="Deep explain prose."),
    block("blk_practice01", "practice", "Try it", short="Short practice.", deep="Deep practice prose.",
          check_id="chk_0123456789abcdef"),
    block("blk_recap00001", "recap", "Recap", short="Short recap.", deep="Deep recap prose."),
]


class LessonViewRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-lesson-views-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
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

    def render(self, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    def payload(self, doc: dict, view: str, *, with_check: bool = True) -> dict:
        return {
            "kind": "document",
            "document": doc,
            "view": view,
            "withCheck": with_check,
            "sources": [
                {"source_id": "src_affection01", "title": "Affection and register — field notes"}
            ],
        }

    def section_payload(self, doc: dict) -> dict:
        return {
            "kind": "section",
            "document": doc,
            "sources": [
                {"source_id": "src_affection01", "title": "Affection and register — field notes"}
            ],
        }

    # -- Textbook ---------------------------------------------------------------------------
    def test_textbook_renders_every_block_with_deep_prose(self) -> None:
        html = self.render(self.payload(document(guided=True, blocks=COMPLETE_BLOCKS,
                                                  check_id="chk_0123456789abcdef"), "textbook"))
        self.assertIn('data-cb-lesson-view="textbook"', html)
        for expected in ("Deep orient prose.", "Deep explain prose.", "Deep practice prose.", "Deep recap prose."):
            self.assertEqual(html.count(expected), 1, expected)
        for short in ("Short orient.", "Short explain.", "Short practice.", "Short recap."):
            self.assertNotIn(short, html)

    def test_textbook_renders_headlines_and_roles(self) -> None:
        html = self.render(self.payload(document(guided=True, blocks=COMPLETE_BLOCKS,
                                                  check_id="chk_0123456789abcdef"), "textbook"))
        for headline in ("Start here", "The mechanism", "Try it", "Recap"):
            self.assertIn(headline, html)
        for role in ("Orient", "Explain", "Practice"):
            self.assertIn(role, html)
        self.assertEqual(html.count('data-cb-role="practice"'), 1)

    def test_textbook_prints_the_course_source_title_as_a_chip(self) -> None:
        html = self.render(self.payload(document(guided=True, blocks=COMPLETE_BLOCKS,
                                                  check_id="chk_0123456789abcdef"), "textbook"))
        self.assertIn("Affection and register — field notes", html)

    def test_the_check_is_attached_to_the_practice_block_exactly_once(self) -> None:
        html = self.render(self.payload(document(guided=True, blocks=COMPLETE_BLOCKS,
                                                  check_id="chk_0123456789abcdef"), "textbook"))
        self.assertEqual(html.count("CHECK-NODE"), 1)
        self.assertIn('data-cb-block-check="blk_practice01"', html)

    def test_a_page_without_a_check_renders_none(self) -> None:
        html = self.render(self.payload(document(guided=True, blocks=COMPLETE_BLOCKS, check_id=None),
                                        "textbook", with_check=False))
        self.assertNotIn("CHECK-NODE", html)

    # -- Guided -----------------------------------------------------------------------------
    def test_guided_shows_one_block_and_its_short_text(self) -> None:
        html = self.render(self.payload(document(guided=True, blocks=COMPLETE_BLOCKS,
                                                  check_id="chk_0123456789abcdef"), "guided"))
        self.assertIn('data-cb-lesson-view="guided"', html)
        self.assertIn("Short orient.", html)
        self.assertIn("Step 1 of 4", html)
        for other in ("Deep orient prose.", "Short explain.", "Short practice.", "Short recap."):
            self.assertNotIn(other, html)
        self.assertEqual(html.count("data-cb-block=") , 1)
        self.assertNotIn("CHECK-NODE", html)

    def test_guided_attaches_the_check_to_its_practice_step(self) -> None:
        practice_first = [COMPLETE_BLOCKS[2], COMPLETE_BLOCKS[0], COMPLETE_BLOCKS[3]]
        html = self.render(self.payload(document(guided=True, blocks=practice_first,
                                                  check_id="chk_0123456789abcdef"), "guided"))
        self.assertEqual(html.count("CHECK-NODE"), 1)
        self.assertIn('data-cb-block-check="blk_practice01"', html)
        self.assertIn("Step 1 of 3", html)
        self.assertIn('disabled="', html)  # Back is disabled on the first step

    def test_guided_keeps_the_block_ids_of_the_document(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        textbook = self.render(self.payload(doc, "textbook"))
        guided = self.render(self.payload(doc, "guided"))
        ids = re.findall(r'data-cb-block="(blk_[^"]+)"', textbook)
        self.assertEqual(ids, [b["id"] for b in COMPLETE_BLOCKS])
        self.assertTrue(set(re.findall(r'data-cb-block="(blk_[^"]+)"', guided)) <= set(ids))
        self.assertIn(doc["document_id"], textbook)
        self.assertIn(doc["document_id"], guided)

    # -- Honest refusal ---------------------------------------------------------------------
    def test_a_textbook_only_document_never_renders_guided(self) -> None:
        doc = document(
            guided=False,
            blocks=COMPLETE_BLOCKS,
            check_id="chk_0123456789abcdef",
            state="textbook_only",
            note="This lesson was authored before the block document existed, so it has no short-text view.",
        )
        html = self.render(self.payload(doc, "guided"))
        self.assertIn('data-cb-lesson-view="textbook"', html)
        self.assertNotIn("Step 1 of 4", html)
        self.assertNotIn("Short orient.", html)
        self.assertIn("Deep orient prose.", html)

    def test_an_empty_document_states_it_has_no_teaching_content(self) -> None:
        doc = document(guided=False, blocks=[], check_id=None, state="empty",
                       note="This section has no teaching content yet.")
        html = self.render(self.payload(doc, "textbook"))
        self.assertIn("no teaching content yet", html)

    # -- The switcher on the section page -------------------------------------------------
    def test_the_section_page_offers_both_views_when_guided_exists(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        html = self.render(self.section_payload(doc))
        self.assertIn('data-cb-view-switcher="available"', html)
        self.assertIn('data-cb-view-options="textbook guided"', html)
        self.assertIn('data-cb-view-unavailable="field_quest"', html)
        self.assertIn('aria-pressed="true"', html)
        self.assertIn("Textbook", html)
        self.assertIn("Guided", html)
        # H-96: the third name stays on screen even when this document has no quest.
        self.assertIn("Field Quest", html)
        self.assertIn('data-cb-view-choice="field_quest"', html)
        self.assertIn('data-cb-view-choice-state="unavailable"', html)
        self.assertIn('data-cb-lesson-view="textbook"', html)

    def test_a_document_without_guided_or_quest_still_shows_three_named_choices(self) -> None:
        """H-96: an absent view is a disabled choice with a reason, never a vanished control.

        H-80 F3 saw `Textbook · Guided · Field Quest` become `View · Textbook` on the same
        section with no explanation. The switcher now always prints all three names and says why
        a view cannot render.
        """
        doc = document(
            guided=False,
            blocks=COMPLETE_BLOCKS,
            check_id="chk_0123456789abcdef",
            state="textbook_only",
            note="This older lesson has no guided view.",
        )
        doc["views"]["field_quest"] = False
        html = self.render(self.section_payload(doc))
        self.assertIn('data-cb-view-switcher="textbook-only"', html)
        self.assertIn('data-cb-view-options="textbook"', html)
        self.assertIn('data-cb-view-unavailable="guided field_quest"', html)
        self.assertEqual(html.count('data-cb-view-choice="'), 3)
        for view_id, label in (("textbook", "Textbook"), ("guided", "Guided"), ("field_quest", "Field Quest")):
            self.assertIn(f'data-cb-view-choice="{view_id}"', html)
            self.assertIn(label, html)
        self.assertIn('data-cb-view-choice-state="available"', html)
        self.assertEqual(html.count('data-cb-view-choice-state="unavailable"'), 2)
        self.assertIn("This lesson has no guided version.", html)
        self.assertIn("This lesson has no Field Quest version.", html)
        self.assertIn('data-cb-view-reason="guided"', html)
        self.assertIn('data-cb-view-reason="field_quest"', html)
        # The active view is still Textbook, and the old badge is gone: the reasons replace it.
        self.assertEqual(html.count('aria-pressed="true"'), 1)
        self.assertNotIn("Textbook only", html)
        self.assertNotIn("<select", html.lower())
        self.assertIn("This older lesson has no guided view.", html)

    def test_an_older_stored_page_without_a_views_object_shows_all_three_choices(self) -> None:
        """A page written before block documents has no `views` key at all (v7 rows)."""
        doc = document(
            guided=False,
            blocks=COMPLETE_BLOCKS,
            check_id="chk_0123456789abcdef",
            state="textbook_only",
            note="This lesson was authored before the block document existed, so it has no short-text view.",
        )
        doc.pop("views")
        html = self.render(self.section_payload(doc))
        self.assertIn('data-cb-view-choice="textbook"', html)
        self.assertIn('data-cb-view-choice="guided"', html)
        self.assertIn('data-cb-view-choice="field_quest"', html)
        self.assertIn('data-cb-view-unavailable="guided field_quest"', html)
        self.assertIn("This lesson has no guided version.", html)
        self.assertIn("This lesson has no Field Quest version.", html)
        self.assertIn("authored before the block document existed", html)
        self.assertNotIn("<select", html.lower())

    # -- H-91 regression: a section with no runtime read at all ------------------------------
    def test_a_section_with_a_null_runtime_renders_instead_of_throwing(self) -> None:
        """H-85 V2-1: `page.runtime` is null in the no-chat case.

        H-86 made the no-chat sentence unconditional but left `data-cb-detached` reading
        `runtime.binding_status`, which threw during render and replaced the whole route with the
        host error boundary. The harness renders the real module with react-dom/server, so a throw
        here is a non-zero exit (asserted in render()) — the test cannot pass on broken code.
        """
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        payload = self.section_payload(doc)
        payload["runtimeNull"] = True
        html = self.render(payload)

        # The sentence is still unconditional, and the attribute degrades to its detached default.
        self.assertIn("This section has no lesson chat yet.", html)
        self.assertIn('data-cb-detached="detached"', html)
        # The one live action for a section with no chat is "start", never "resume".
        self.assertIn('data-cb-section-actions="start"', html)
        self.assertNotIn('data-cb-section-actions="resume"', html)
        # The section itself rendered.
        self.assertIn('data-cb-lesson-view="textbook"', html)


if __name__ == "__main__":
    unittest.main()
