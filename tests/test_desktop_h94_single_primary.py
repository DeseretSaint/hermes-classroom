"""H-94: one primary action per surface, and one facts line on the Field Desk.

H-85 V2-4 measured two "New lesson plan" primary buttons on Parent Studio (route header 108x24
and in-page 112x28) and V2-5 measured the desk's three-cell same-size stat strip. The header
button is gone (H-91 P2-4); this file guards it from returning, and pins the desk to the single
facts line course detail already speaks in.

These are static renders of the shipped module through React with a stub SDK, plus source
assertions for the route header (which is not a pure component). The live frame evidence is
separate: audit/ux/round3/h94/.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_field_desk import OUTLINE, library, library_row
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

STUB = SDK_STUB.replace(
    "export const ListRow = () => null",
    "export const ListRow = (props) =>\n"
    "  el('div', { className: 'list-row' }, [\n"
    "    el('div', { key: 't', className: 'list-title' }, props.title),\n"
    "    el('div', { key: 'd', className: 'list-desc' }, props.description),\n"
    "    props.action\n"
    "  ])",
)

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { FieldDeskHome, StudioLanding, buildDeskModel } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

let html = null
if (payload.kind === 'studio') {
  html = renderToStaticMarkup(
    React.createElement('div', { 'data-cb-scope': 'light' },
      React.createElement(StudioLanding, {
        rows: payload.rows,
        onCreate: () => {},
        onOpen: () => {}
      })
    )
  )
} else if (payload.kind === 'desk') {
  const desk = buildDeskModel({ library: payload.library, outline: payload.outline, estimate: payload.estimate })
  html = renderToStaticMarkup(
    React.createElement('div', { 'data-cb-scope': 'light' },
      React.createElement(FieldDeskHome, {
        desk,
        libraryStatus: 'ready',
        libraryError: null,
        stale: false,
        busy: false,
        notice: null,
        onRetry: () => {},
        onCreate: () => {},
        onPrimary: () => {},
        onOpenSection: () => {},
        onOpen: () => {},
        onShowAll: () => {},
        sourcesOpen: false,
        onToggleSources: () => {},
        sourcesStatus: 'idle',
        sourcesError: null,
        sources: null,
        onRetrySources: () => {},
        implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'parent.brief.get'])
      })
    )
  )
}

process.stdout.write(JSON.stringify({ html }))
"""

STUDIO_ROW = {
    "enrollment_id": "enr_0123456789abcdef",
    "course_id": "crs_0123456789abcdef",
    "title": "Kitchen fractions for a 9-year-old",
    "recipe": "parent",
    "enrollment_status": "active",
    "updated_at": "2026-11-06T18:00:00.000000+00:00",
    "revision": 3,
}


def _render(payload: dict) -> str:
    modules = _desktop_node_modules()
    if modules is None:
        raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
    with tempfile.TemporaryDirectory(prefix="coursebook-h94-") as tmp:
        root = Path(tmp)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        (root / "node_modules").symlink_to(modules, target_is_directory=True)
        sdk_dir = root / "node_modules" / "@hermes" / "plugin-sdk"
        sdk_dir.mkdir(parents=True, exist_ok=True)
        index_js = sdk_dir / "index.js"
        index_js_original = index_js.read_text(encoding="utf-8") if index_js.exists() else None
        index_js.write_text(STUB, encoding="utf-8")
        payload_path = root / "payload.json"
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            completed = subprocess.run(
                ["node", "harness.mjs", str(payload_path)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=180,
            )
        finally:
            if index_js_original is None:
                index_js.unlink(missing_ok=True)
            else:
                index_js.write_text(index_js_original, encoding="utf-8")
        if completed.returncode != 0:
            raise AssertionError(f"node harness failed:\n{completed.stdout}\n{completed.stderr}")
        return json.loads(completed.stdout)["html"]


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class ParentStudioPrimaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = _render({"kind": "studio", "rows": [STUDIO_ROW]})

    def test_the_landing_plate_carries_exactly_one_primary(self) -> None:
        self.assertEqual(self.html.count('data-variant="default"'), 1, self.html)
        self.assertEqual(self.html.count("New lesson plan"), 1, self.html)

    def test_the_row_action_stays_secondary(self) -> None:
        self.assertEqual(self.html.count('data-variant="secondary"'), 1, self.html)
        self.assertIn("Open plan", self.html)

    def test_the_route_header_has_no_studio_create_action(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        header = source[source.index("'data-cb-route': ROUTE_PATH") :]
        header = header[: header.index("PageBody")]
        self.assertNotIn("children: 'New lesson plan'", header)
        self.assertNotIn("setStudioSeed", header)
        # The plate and the empty-state welcome are the only two in-page create labels.
        self.assertEqual(source.count("children: 'New lesson plan'"), 2, source)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class DeskFactsLineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = _render(
            {"kind": "desk", "library": library(library_row()), "outline": OUTLINE, "estimate": None}
        )

    def test_the_desk_has_exactly_one_primary(self) -> None:
        self.assertEqual(self.html.count('data-variant="default"'), 1, self.html)

    def test_the_desk_has_one_facts_line_not_three_cards(self) -> None:
        # H-189 removed the plate's own facts line: it repeated the route's evidence count and the
        # current stop's state word inside the plate, so the route was said twice. The one count
        # now lives in the route header and the plate carries no stat strip at all.
        self.assertNotIn("data-cb-desk-facts=", self.html)
        self.assertNotIn("data-cb-desk-stats", self.html)
        self.assertNotIn("data-cb-desk-stat=", self.html)
        self.assertNotRegex(self.html, r"grid-template-columns:\s*repeat\(3")

    def test_the_route_header_carries_the_one_evidence_count(self) -> None:
        self.assertEqual(self.html.count("with evidence"), 1, self.html)
        self.assertIn("1 of 4 sections with evidence", self.html)
        self.assertEqual(self.html.count("data-cb-tally-caption"), 1, self.html)


if __name__ == "__main__":
    unittest.main()
