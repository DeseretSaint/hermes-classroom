"""H-150: the Library shelf is a browsing surface, not a debug panel.

The shelf had three page labels, a lead that contradicted the source badges, a dead title, and
inspector facts (`revision 12`, `pack_id`) printed as if they were learner facts. These gates
render the shipped row and preview with React and read the route source for the parts a static
render cannot mount (filters, overflow menu, one lead, one h1).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
SOURCE = PLUGIN_JS.read_text(encoding="utf-8")

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { PackShelfRow, PackFacts, ShelfDisclosure } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const render = (node) => renderToStaticMarkup(React.createElement('div', null, node))

const row = {
  enrollment_id: 'enr_0123456789abcdef',
  course_id: 'crs_0123456789abcdef',
  title: payload.title || 'Conversational Japanese',
  revision: 7,
  enrollment_status: 'active',
  recipe: 'learner',
  provenance: { source: payload.source || 'community', pack_id: 'pack_0123456789ab', pack_version: '1.0.0' },
  next_step: { kind: payload.kind === 'facts' ? 'start_lesson' : 'resume_lesson', label: payload.nextLabel || 'Continue: Register and affection' },
  evidence_summary: { total_objectives: payload.total === undefined ? 3 : payload.total, independent: 1, review_due: 0 },
  updated_at: '2026-11-01T10:00:00Z'
}

let html = ''
if (payload.kind === 'row') {
  html = render(React.createElement(PackShelfRow, {
    row,
    selected: Boolean(payload.selected),
    onPreview: () => {},
    onOpenMember: () => {}
  }))
} else if (payload.kind === 'facts') {
  html = render(React.createElement(PackFacts, {
    row,
    implemented: new Set(['binding.get', 'enrollment.update', 'enrollment.delete', 'pack.export', 'pack.delete']),
    onOpen: () => {},
    onResume: () => {},
    onArchive: () => {},
    onDelete: () => {},
    onExportPack: () => {},
    onDeletePack: () => {},
    onBack: () => {},
    showBack: true
  }))
} else if (payload.kind === 'disclosure') {
  html = render(React.createElement(ShelfDisclosure, {
    group: { key: 'pack:x', label: '2 enrollments', primary: row, members: [row, { ...row, enrollment_id: 'enr_b' }] },
    onOpen: () => {}
  }))
}
process.stdout.write(html)
"""


FOCUS_HARNESS = r"""
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true
})
for (const key of [
  'window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'Event', 'FocusEvent',
  'KeyboardEvent', 'MouseEvent', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame'
]) {
  // Node ≥ 21 exposes some of these as getter-only globals, so a plain assignment throws.
  Object.defineProperty(globalThis, key, {
    value: dom.window[key],
    configurable: true,
    writable: true
  })
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const React = await import('react')
const { createRoot } = await import('react-dom/client')
const { PackShelfRow, PackFacts, PackShelfSplit, shelfFocusTarget } = await import('./plugin.js')

const row = {
  enrollment_id: 'enr_0123456789abcdef',
  course_id: 'crs_0123456789abcdef',
  title: 'Conversational Japanese',
  revision: 7,
  enrollment_status: 'active',
  recipe: 'learner',
  provenance: { source: 'community', pack_id: 'pack_0123456789ab', pack_version: '1.0.0' },
  next_step: { kind: 'resume_lesson', label: 'Continue: Register and affection' },
  evidence_summary: { total_objectives: 3, independent: 1, review_due: 0 },
  updated_at: '2026-11-01T10:00:00Z'
}

// The product's own shelf region: the layout rule, the focus intent and the real row/preview
// controls. `compact` is the route-column rule the shelf itself uses (list hidden once a pack is
// open); it is not a test-only switch.
function Shelf({ compact }) {
  const [selected, setSelected] = React.useState(null)
  const [intent, setIntent] = React.useState(null)
  const open = (target) => {
    setSelected(target.enrollment_id)
    setIntent({ target: shelfFocusTarget(compact, true), key: target.enrollment_id })
  }
  const close = () => {
    setSelected(null)
    setIntent({ target: 'list', key: row.enrollment_id })
  }
  const detailRow = selected ? row : null
  return React.createElement(PackShelfSplit, {
    compact,
    detailOpen: Boolean(detailRow),
    focus: intent,
    list: React.createElement(PackShelfRow, {
      row,
      selected: selected === row.enrollment_id,
      onPreview: open,
      onOpenMember: open
    }),
    detail: detailRow
      ? React.createElement(PackFacts, {
          row,
          implemented: new Set(['binding.get', 'enrollment.update', 'enrollment.delete', 'pack.export', 'pack.delete']),
          onBack: close,
          onDelete: () => {},
          onDeletePack: () => {},
          onExportPack: () => {},
          onOpen: () => {},
          onArchive: () => {},
          onResume: () => {},
          showBack: true
        })
      : null
  })
}

const root = createRoot(document.getElementById('root'))
let mountId = 0
// jsdom cannot answer `:focus-visible` (it has no focus-visible heuristic), so answer it the way the
// live renderer does: true for a keyboard stop, false for a pointer press. The product's own branch
// — ask the engine, ring only when it says yes — is still the code under test.
let focusVisibleAnswer = true
const realMatches = dom.window.Element.prototype.matches
dom.window.Element.prototype.matches = function (selector) {
  if (selector === ':focus-visible') return focusVisibleAnswer
  return realMatches.call(this, selector)
}
// A remount per scenario: the point of each case is the state after a fresh key press, so leftover
// selection from the previous case must not make the second press a no-op.
const render = async (compact) => {
  await React.act(async () => { root.render(React.createElement(Shelf, { compact, key: ++mountId })) })
}
const describe = () => {
  const el = document.activeElement
  const listPane = document.querySelector('[data-cb-pack-list-pane]')
  return {
    tag: el ? el.tagName.toLowerCase() : null,
    label: el && el.getAttribute ? el.getAttribute('aria-label') : null,
    text: el ? (el.textContent || '').trim().slice(0, 40) : null,
    isBody: el === document.body,
    isRowAction: Boolean(el && el.matches && el.matches('[data-cb-pack-row-action]')),
    insidePreview: Boolean(el && el.closest && el.closest('[data-cb-pack-preview]')),
    previewOpen: Boolean(document.querySelector('[data-cb-pack-preview]')),
    backExists: Boolean(document.querySelector('[data-cb-pack-back]')),
    listPaneDisplay: listPane ? listPane.style.display : null,
    split: document.querySelector('[data-cb-pack-split]') && document.querySelector('[data-cb-pack-split]').getAttribute('data-cb-pack-split')
  }
}
const focusRow = async () => {
  const button = document.querySelector('[data-cb-pack-row-action]')
  await React.act(async () => {
    button.focus()
    button.dispatchEvent(new dom.window.FocusEvent('focusin', { bubbles: true }))
  })
  return button
}
const press = async (button, key) => {
  await React.act(async () => {
    button.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
  })
}

const scenarios = {}
for (const compact of [false, true]) {
  const bucket = {}
  for (const [name, key] of [['enter', 'Enter'], ['space', ' ']]) {
    await render(compact)
    const button = await focusRow()
    bucket[name + 'Before'] = describe()
    bucket[name + 'Ring'] = {
      state: button.getAttribute('data-cb-focus-ring'),
      outline: button.style.outline,
      offset: button.style.outlineOffset
    }
    await press(button, key)
    bucket[name + 'After'] = describe()
  }
  // Ring clears on blur, and the preview's own control returns focus to the row it came from.
  await render(compact)
  focusVisibleAnswer = true
  const button = await focusRow()
  await React.act(async () => {
    button.blur()
    button.dispatchEvent(new dom.window.FocusEvent('focusout', { bubbles: true }))
  })
  bucket.blurredRing = button.getAttribute('data-cb-focus-ring')
  // A pointer press focuses the row but must not paint the identity ring.
  focusVisibleAnswer = false
  await render(compact)
  const pointerButton = await focusRow()
  bucket.pointerRing = pointerButton.getAttribute('data-cb-focus-ring')
  focusVisibleAnswer = true
  bucket.shelfFocusTarget = { compact, target: shelfFocusTarget(compact, true) }
  scenarios[compact ? 'compact' : 'stacked'] = bucket
}
process.stdout.write(JSON.stringify(scenarios))
"""


def _function(name: str, end: str) -> str:
    return SOURCE[SOURCE.index(f"function {name}") : SOURCE.index(f"function {end}")]


def _function_body(name: str) -> str:
    """The body of `name`, up to the next top-level function — order-independent.

    Anchoring on a neighbouring function's name silently yields an empty slice when the two
    are declared in the other order, which is a false pass waiting to happen.
    """
    start = SOURCE.index(f"function {name}")
    end = SOURCE.find("\nfunction ", start + len(f"function {name}"))
    return SOURCE[start:] if end == -1 else SOURCE[start:end]


class LibraryShelfRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h150-")
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

    # -- the row is the target ---------------------------------------------------------------
    def test_the_whole_row_is_one_button_and_selection_is_spelled_out(self) -> None:
        html = self.render({"kind": "row", "selected": True})
        self.assertIn('data-cb-pack-row="', html)
        self.assertIn('data-cb-pack-selected="true"', html)
        self.assertIn('aria-pressed="true"', html)
        self.assertIn('aria-label="Preview Conversational Japanese"', html)
        self.assertIn(">Selected<", html)
        # One full-row target plus the one explicit Preview affordance; never a nested control.
        self.assertEqual(html.count("<button"), 2, html)
        self.assertEqual(html.count('data-variant="secondary"'), 1, "selected Preview reads as raised")

    def test_a_selected_row_keeps_a_text_cue_not_colour_alone(self) -> None:
        html = self.render({"kind": "row", "selected": True})
        self.assertIn("data-cb-pack-selected-cue", html)
        self.assertIn("Selected", html)

    def test_an_empty_pack_says_no_sections_once_and_shows_no_path_or_seal(self) -> None:
        html = self.render({"kind": "row", "total": 0})
        self.assertIn('data-cb-pack-empty="true"', html)
        self.assertEqual(html.count("No sections yet"), 1, html)
        self.assertNotIn("data-cb-course-path", html)
        self.assertNotIn("data-cb-seal", html)
        self.assertNotIn("data-cb-cover-field", html)
        self.assertIn("Nothing to open yet. Preview it to see the manifest.", html)

    # -- the shelf never prints a backend contract placeholder -------------------------------
    def test_the_row_resolves_the_backend_plural_placeholder(self) -> None:
        html = self.render({"kind": "row", "nextLabel": "Review 2 objective(s)"})
        self.assertIn("Review 2 objectives", html)
        self.assertNotIn("objective(s)", html)

    def test_a_label_outside_the_review_form_is_still_scrubbed(self) -> None:
        # The backend's placeholder is a contract string, not a template: any sentence that
        # carries it must read as a plural count on the shelf.
        html = self.render({"kind": "row", "nextLabel": "2 objective(s) remain in this unit"})
        self.assertIn("2 objectives remain in this unit", html)
        self.assertNotIn("objective(s)", html)

    # -- the preview is not an inspector -----------------------------------------------------
    def test_pack_preview_moves_identifiers_under_closed_technical_details(self) -> None:
        html = self.render({"kind": "facts"})
        self.assertIn("data-cb-pack-technical", html)
        self.assertIn("Technical details", html)
        self.assertIn("Pack ID", html)
        self.assertIn("Record version", html)
        self.assertNotIn("revision 7", html)
        technical = html[html.index("data-cb-pack-technical") :]
        self.assertIn("pack_0123456789ab", technical)
        self.assertLess(html.index("Open course"), html.index("Technical details"))

    def test_pack_preview_has_one_primary_one_secondary_and_no_inline_destructive(self) -> None:
        html = self.render({"kind": "facts"})
        self.assertEqual(html.count('data-variant="default"'), 1, html)
        self.assertEqual(html.count('data-variant="secondary"'), 1, "Archive is the one secondary")
        self.assertNotIn("Delete enrollment", html)
        self.assertNotIn("Remove pack", html)

    def test_the_member_disclosure_names_records_without_a_hash(self) -> None:
        html = self.render({"kind": "disclosure"})
        self.assertIn("2 enrollments", html)
        self.assertIn("Conversational Japanese", html)
        # No eight-hex fingerprint and no raw identifier in the visible disclosure text.
        self.assertNotRegex(html, r">\s*[0-9a-f]{8}\s*<")
        self.assertNotIn("pack_0123456789ab", html)


class LibraryShelfFocusTest(unittest.TestCase):
    """H-150c: after Enter or Space, focus stays where the user can see it.

    The measured defect was not an event bug: the list column carried a `hidden
    min-[47.5rem]:flex` toggle, so at a 460 px window opening a pack set the column to
    `display: none` and took the focused row button with it — which is why
    `document.activeElement` fell to `body`. These gates mount the shipped shelf region in jsdom
    and read `document.activeElement` after a real key event.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        for needed in ("react", "react-dom", "scheduler", "jsdom"):
            if not (modules / needed).is_dir():
                raise unittest.SkipTest(f"{needed} is not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h150-focus-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "focus-harness.mjs").write_text(FOCUS_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            (node_modules / name).symlink_to(modules / name, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root
        cls.result = None

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def scenarios(self) -> dict:
        if type(self).result is None:
            run = subprocess.run(
                ["node", str(self.root / "focus-harness.mjs")],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            type(self).result = json.loads(run.stdout)
        return type(self).result

    def test_enter_and_space_leave_focus_on_a_visible_control(self) -> None:
        scenarios = self.scenarios()
        for pane, compact in (("stacked", False), ("compact", True)):
            bucket = scenarios[pane]
            self.assertEqual(bucket["shelfFocusTarget"], {"compact": compact, "target": "detail" if compact else "list"})
            for key in ("enter", "space"):
                after = bucket[key + "After"]
                with self.subTest(pane=pane, key=key):
                    self.assertTrue(after["previewOpen"], "the key opens the preview")
                    self.assertFalse(after["isBody"], f"focus fell to body: {after}")
                    if not compact:
                        # The row the user pressed is still on screen: it keeps focus.
                        self.assertTrue(after["isRowAction"], after)
                        self.assertEqual(after["listPaneDisplay"], "flex", "the list pane stays rendered")
                    else:
                        # One pane: the list is hidden, so focus moves into the preview.
                        self.assertTrue(after["insidePreview"], after)
                        self.assertEqual(after["text"], "All packs", after)
                        self.assertEqual(after["listPaneDisplay"], "none", "the hidden pane holds no focus")

    def test_enter_and_space_are_the_same_path(self) -> None:
        bucket = self.scenarios()["compact"]
        self.assertEqual(bucket["enterAfter"], bucket["spaceAfter"])
        two = self.scenarios()["stacked"]
        self.assertEqual(two["enterAfter"], two["spaceAfter"])

    def test_the_focused_row_paints_the_identity_ring_and_clears_it(self) -> None:
        for pane in ("stacked", "compact"):
            bucket = self.scenarios()[pane]
            for key in ("enter", "space"):
                ring = bucket[key + "Ring"]
                with self.subTest(pane=pane, key=key):
                    self.assertEqual(ring["state"], "visible")
                    self.assertEqual(ring["offset"], "-2px")
                    self.assertIn("2px", ring["outline"])
                    self.assertIn("var(--cb-accent)", ring["outline"])
            self.assertEqual(bucket["blurredRing"], "none", "the ring is focus state, not a permanent border")
            self.assertEqual(bucket["pointerRing"], "none", "a pointer press must not paint the ring")

    def test_the_preview_offers_the_back_control_focus_lands_on(self) -> None:
        for pane in ("stacked", "compact"):
            bucket = self.scenarios()[pane]
            self.assertTrue(bucket["enterAfter"]["backExists"], f"{pane}: preview has no back control")
            self.assertTrue(bucket["spaceAfter"]["backExists"], f"{pane}: preview has no back control")


class LibraryShelfSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.library = _function("LibraryView", "planTimingCopy")
        self.row = _function("PackShelfRow", "DeskProgress")
        self.facts = _function("PackMenu", "formatWhen")

    def test_one_page_lead_and_no_repeated_library_label(self) -> None:
        self.assertNotIn("label: 'Library'", self.library)
        self.assertEqual(self.library.count("LIBRARY_COPY.lead"), 1, "the empty state must not repeat the lead")
        self.assertIn("jsx(PlateHead, {\n        title: 'Packs on this profile',", self.library)

    def test_filters_name_the_rows_they_return(self) -> None:
        self.assertIn("{ id: 'all', label: 'All packs' }", self.library)
        self.assertIn("{ id: 'bundled', label: 'Bundled' }", self.library)
        self.assertIn("{ id: 'other', label: 'From someone else' }", self.library)
        self.assertNotIn("{ id: 'local'", self.library)
        self.assertNotIn("label: 'Local'", self.library)
        self.assertIn("view === 'other'", self.library)
        self.assertIn("return source === 'community' || source === 'local'", self.library)
        # The filter resets the preview so a hidden row never stays selected behind a filter.
        self.assertIn("setSelected(null)", self.library)

    def test_trust_is_read_below_the_shelf(self) -> None:
        trust = self.library.index("data-cb-pack-trust")
        columns = self.library.index("PackShelfSplit")
        self.assertGreater(trust, columns, "trust must sit below the list")

    def test_the_shelf_layout_is_decided_from_the_route_column(self) -> None:
        # H-150c: the list column's `hidden min-[47.5rem]:flex` toggle made visibility depend on the
        # window, not the route pane the shelf is actually drawn in (a 900 px window leaves
        # Coursebook 257 px). One measured rule now decides both which pane is shown and where
        # focus goes, so they cannot disagree.
        self.assertIn("useCbViewportWidth()", self.library)
        self.assertIn("CB_SHELF_COMPACT_WIDTH", self.library)
        self.assertIn("shelfFocusTarget(compactShelf, true)", self.library)
        self.assertIn("compact: compactShelf", self.library)
        for dead in ("min-[47.5rem]:flex", "min-[47.5rem]:w-72", "narrowDetailOnly"):
            self.assertNotIn(dead, self.library, f"{dead} made visibility a window question")

    def test_the_row_is_a_whole_row_button_with_one_preview_affordance(self) -> None:
        self.assertIn("sdk.RowButton", self.row)
        self.assertIn("absolute inset-0", self.row)
        self.assertIn("'aria-pressed': selected ? 'true' : 'false'", self.row)
        self.assertIn("pointer-events-none", self.row)
        self.assertIn("event.key === 'Enter' || event.key === ' '", self.row)
        # The identity ring, drawn inside the row so the scroll container cannot clip its sides.
        self.assertIn("outline: keyboardFocus ? '2px solid var(--cb-accent)' : 'none'", self.row)
        self.assertIn("outlineOffset: '-2px'", self.row)
        self.assertIn("'data-cb-pack-row-action': row.enrollment_id", self.row)
        self.assertEqual(self.row.count("children: 'Preview'"), 1)

    def test_pack_menu_puts_destructive_actions_under_overflow(self) -> None:
        self.assertIn("sdk.DropdownMenuItem", self.facts)
        self.assertIn("variant: 'destructive'", self.facts)
        self.assertIn("children: 'Delete enrollment…'", self.facts)
        self.assertIn("children: 'Remove pack…'", self.facts)
        self.assertNotIn("variant: 'default', children: 'Delete", self.facts)

    def test_technical_fields_are_named_and_closed(self) -> None:
        self.assertIn("'data-cb-pack-technical': ''", self.facts)
        self.assertIn("children: 'Technical details'", self.facts)
        self.assertIn("label: 'Pack ID'", self.facts)
        self.assertIn("label: 'Record version'", self.facts)
        self.assertNotIn("detail: `revision ${row.revision}`", self.facts)
        self.assertNotIn("children: row.provenance.pack_id", self.facts)

    def test_counts_use_the_shared_plural_helper(self) -> None:
        self.assertIn("plural(total, 'section', 'sections')", self.row)
        self.assertIn("plural(due, 'review', 'reviews')", self.facts)
        self.assertNotIn("check(s)", SOURCE)
        self.assertNotIn("file(s)", SOURCE)

    def test_backend_plural_placeholder_never_reaches_the_shelf(self) -> None:
        placeholder = _function_body("learnerNextLabel")
        self.assertIn(r"objective\(s\)", placeholder)
        self.assertIn("plural(Number(match[1]), 'objective', 'objectives')", placeholder)
        self.assertIn("learnerNextLabel(row && row.next_step", SOURCE)
        self.assertIn("learnerNextLabel(next.label)", self.facts)


if __name__ == "__main__":
    unittest.main()
