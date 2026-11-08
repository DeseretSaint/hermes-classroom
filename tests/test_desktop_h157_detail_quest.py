"""H-157: Course Detail is four primary surfaces, and Field Quest is a path, not a dashboard.

Two composition contracts are pinned here:

* course detail offers **four** primary surfaces (Overview, Learn, Notebook, Evidence) and keeps
  Plan, Sources, Export and the graded-attempt record one click away behind `More`; every legacy
  view id still resolves, so direct links keep working;
* the Evidence surface names what it shows in the learner's words, and every plural count the
  learner reads comes from one ``plural`` helper.

The Field Quest composition (title as h2, counts as caption, one-line mission) is proven in
``tests/test_desktop_field_quest.py`` against the rendered view. This file proves the tab set, the
direct-link mapping and the copy that the audit named as defects.
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

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  COURSE_PRIMARY_TABS,
  courseMoreTabs,
  primarySurfaceFor,
  plural,
  EvidenceView
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

let html = null
if (payload.kind === 'evidence' && payload.evidence) {
  html = renderToStaticMarkup(
    React.createElement(EvidenceView, {
      evidence: payload.evidence,
      implemented: new Set(['notebook.save']),
      onOpenSection: () => {}
    })
  )
}

process.stdout.write(JSON.stringify({
  tabs: COURSE_PRIMARY_TABS,
  moreWithExport: courseMoreTabs((method) => method === 'course.export.read'),
  moreWithoutExport: courseMoreTabs(() => false),
  mapping: Object.fromEntries(
    ['overview', 'learn', 'textbook', 'guided', 'field_quest', 'notebook', 'evidence', 'quizzes', 'plan', 'sources', 'export']
      .map((view) => [view, primarySurfaceFor(view)])
  ),
  plurals: [
    plural(0, 'objective', 'objectives'),
    plural(1, 'objective', 'objectives'),
    plural(2, 'objective', 'objectives'),
    plural(1, 'check', 'checks')
  ],
  html
}))
"""

EVIDENCE = {
    "l1": {
        "attempts": [
            {
                "attempt_id": "att_1",
                "verdict": "pass",
                "evidence_class": "independent",
                "committed_at": "2026-11-01T10:00:00Z",
            }
        ],
        "events": [{"evidence_id": "ev_1", "kind": "lesson_open", "is_action": True, "created_at": "2026-11-01T09:59:00Z"}],
    },
    "l2": {
        "objectives": [
            {"objective_id": "obj_1", "title": "Order at a counter", "independent": True},
        ]
    },
    "l3": {
        "recommendations": [
            {"kind": "review", "text": "Review ordering once more.", "basis": "layer2.independent == false"}
        ],
        "as_of": "2026-11-01T10:00:00Z",
        "is_persona": False,
    },
    "disputes": {"disputes": []},
}


class H157CompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h157-")
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
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def model(self, *, evidence: dict | None = None) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps({"kind": "evidence", "evidence": evidence}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    # -- the tab set ---------------------------------------------------------------------------
    def test_course_detail_has_exactly_four_primary_surfaces(self) -> None:
        tabs = self.model()["tabs"]
        self.assertEqual([tab["id"] for tab in tabs], ["overview", "learn", "notebook", "evidence"])
        self.assertEqual([tab["label"] for tab in tabs], ["Overview", "Learn", "Notebook", "Evidence"])

    def test_learn_is_one_surface_not_three_peer_tabs(self) -> None:
        ids = [tab["id"] for tab in self.model()["tabs"]]
        for reading in ("textbook", "guided", "field_quest"):
            self.assertNotIn(reading, ids)

    def test_plan_sources_export_and_attempts_live_under_more(self) -> None:
        more = self.model()["moreWithExport"]
        self.assertEqual([tab["id"] for tab in more], ["quizzes", "plan", "sources", "export"])
        self.assertEqual([tab["label"] for tab in more][1:], ["Plan", "Sources", "Export"])

    def test_export_only_appears_when_the_backend_advertises_it(self) -> None:
        ids = [tab["id"] for tab in self.model()["moreWithoutExport"]]
        self.assertNotIn("export", ids)
        self.assertEqual(ids, ["quizzes", "plan", "sources"])

    def test_every_legacy_view_id_still_maps_to_a_primary_surface(self) -> None:
        mapping = self.model()["mapping"]
        self.assertEqual(mapping["overview"], "overview")
        self.assertEqual(mapping["notebook"], "notebook")
        self.assertEqual(mapping["evidence"], "evidence")
        for reading in ("learn", "textbook", "guided", "field_quest"):
            self.assertEqual(mapping[reading], "learn", reading)
        for admin in ("quizzes", "plan", "sources", "export"):
            self.assertNotIn(mapping[admin], ("overview", "learn", "notebook", "evidence"), admin)

    # -- one plural helper ---------------------------------------------------------------------
    def test_plural_has_a_singular_branch(self) -> None:
        self.assertEqual(
            self.model()["plurals"],
            ["0 objectives", "1 objective", "2 objectives", "1 check"],
        )

    def test_no_plural_placeholder_survives_in_the_shipped_copy(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        shipped = [
            line for line in source.splitlines()
            if not line.lstrip().startswith(("*", "//", "/*"))
        ]
        body = "\n".join(shipped)
        for placeholder in ("file(s)", "check(s)", "page(s)", "command(s)", "objective(s)"):
            self.assertFalse(placeholder in body, f"plural placeholder {placeholder} still shipped")

    def test_the_syllabus_decision_count_has_a_singular_branch(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertNotIn("items have a decision", source)
        self.assertIn("? 'item has' : 'items have'", source)

    # -- the Evidence surface speaks the learner's language -------------------------------------
    def test_evidence_labels_are_plain_words(self) -> None:
        html = self.model(evidence=EVIDENCE)["html"]
        self.assertIn("What to do next", html)
        self.assertIn("What the evidence shows", html)
        self.assertIn("Your attempts", html)
        for jargon in ("L3 ·", "L2 ·", "L1 ·", "layer 2", "layer 1", "layer 3", "persona claim"):
            self.assertNotIn(jargon, html, jargon)

    def test_the_raw_basis_lives_in_the_closed_technical_panel(self) -> None:
        html = self.model(evidence=EVIDENCE)["html"]
        self.assertIn("Technical detail", html)
        technical = html.index("data-cb-evidence-technical")
        basis = html.index("basis: layer2.independent == false")
        self.assertGreater(basis, technical)
        close = html.index("</details>", technical)
        self.assertLess(basis, close, "basis must be inside the closed technical panel")
        details_open = html.rindex("<details", 0, technical)
        self.assertNotIn("open", html[details_open:technical].split(">")[0])

    def test_the_evidence_surface_keeps_one_plain_summary_line(self) -> None:
        html = self.model(evidence=EVIDENCE)["html"]
        self.assertIn("it describes that evidence rather than judging you", html)
        self.assertEqual(html.count("Technical detail"), 1)


if __name__ == "__main__":
    unittest.main()
