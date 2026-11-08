"""H-148 — the path and its checkpoints tell the truth.

The path is the learning product. This suite renders the shipped `CheckpointPath` through React and
executes its pure projections, so every claim below is about the module the Desktop loads:

* a zero-evidence course paints no reached segment on `CoursePath` (ENG-D1);
* `CheckpointPath` sizes current / next / done / future nodes from the measured route;
* every node is an openable destination with `aria-current="step"` on exactly the current one;
* the marker carries the backend's own `check_state`, and the detail names the evidence target in
  learner words, the committed attempt count and the last opened time;
* `overridden` is its own word and is never counted as evidence;
* no lock, star, percentage, XP, streak or fake cumulative checkpoint appears.
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

from tests.test_desktop_field_desk import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  CheckpointPath,
  buildDeskModel,
  cbCoursePathCaption,
  cbCoursePathSegments,
  cbPathEvidenceCaption,
  cbPathNodeKind,
  cbPathNodeSize
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

if (payload.kind === 'pure') {
  process.stdout.write(JSON.stringify({
    segments: payload.row ? cbCoursePathSegments(payload.row) : null,
    shelfCaption: payload.row ? cbCoursePathCaption(payload.row) : null,
    caption: cbPathEvidenceCaption(payload.settled, payload.total, payload.due),
    sizes: {
      current: cbPathNodeSize('current', false),
      next: cbPathNodeSize('next', false),
      done: cbPathNodeSize('done', false),
      future: cbPathNodeSize('future', false),
      currentCompact: cbPathNodeSize('current', true),
      nextCompact: cbPathNodeSize('next', true),
      doneCompact: cbPathNodeSize('done', true),
      futureCompact: cbPathNodeSize('future', true)
    },
    kinds: (payload.objectives || []).map((objective) =>
      cbPathNodeKind(objective, payload.currentId, payload.nextId))
  }))
} else {
  const desk = buildDeskModel({
    library: payload.library,
    outline: payload.outline,
    estimate: { status: 'ready', minutes: 20 }
  })
  const html = renderToStaticMarkup(
    React.createElement('div', { 'data-cb-scope': 'light' },
      React.createElement(CheckpointPath, { desk, onOpenSection: () => {} }))
  )
  process.stdout.write(JSON.stringify({ html, desk }))
}
"""


def objective(
    objective_id: str,
    ordinal: int,
    title: str,
    *,
    state: str = "not_started",
    check_state: str = "none",
    attempt_count: int = 0,
    evidence_target: str = "recall",
    independent: bool = False,
    last_opened_at: str | None = None,
) -> dict:
    return {
        "objective_id": objective_id,
        "ordinal": ordinal,
        "title": title,
        "evidence_target": evidence_target,
        "state": state,
        "check_state": check_state,
        "attempt_count": attempt_count,
        "independent": independent,
        "last_opened_at": last_opened_at,
    }


OUTLINE = {
    "enrollment_id": "enr_h148",
    "objectives": [
        objective(
            "obj_01",
            1,
            "Name the three things an engine needs",
            state="independent_evidence",
            check_state="closed",
            attempt_count=2,
            evidence_target="recall",
            independent=True,
            last_opened_at="2026-11-05T09:00:00.000000+00:00",
        ),
        objective(
            "obj_02",
            2,
            "Diagnose a no-start",
            state="review_due",
            check_state="open",
            attempt_count=1,
            evidence_target="procedure",
        ),
        objective(
            "obj_03",
            3,
            "Replace a fouled plug",
            state="introduced",
            check_state="open",
            evidence_target="production",
        ),
        objective(
            "obj_04",
            4,
            "Check compression safely",
            state="not_started",
            check_state="none",
            evidence_target="comprehension",
        ),
    ],
}

OVERRODE_OUTLINE = {
    "enrollment_id": "enr_h148_overridden",
    "objectives": [
        objective("obj_a", 1, "Handled without a grade", state="overridden", check_state="superseded"),
        objective("obj_b", 2, "First real section", state="not_started", check_state="none"),
    ],
}


def library_row(outline: dict) -> dict:
    return {
        "enrollment_id": outline["enrollment_id"],
        "course_id": "crs_h148",
        "title": "Small-engine maintenance",
        "recipe": "committed",
        "revision": 3,
        "evidence_summary": {
            "total_objectives": len(outline["objectives"]),
            "independent": len([entry for entry in outline["objectives"] if entry["independent"]]),
            "review_due": len(
                [entry for entry in outline["objectives"] if entry["state"] in ("review_due", "needs_review")]
            ),
            "current_objective_id": "obj_02",
        },
        "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
    }


class PathHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h148-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
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

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_harness(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        env = dict(os.environ)
        env["CB_TEST_WIDTH"] = str(payload.get("width", 1280))
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    def render(self, outline: dict = OUTLINE, width: int = 1280) -> dict:
        return self.run_harness(
            {
                "kind": "render",
                "library": {"items": [library_row(outline)]},
                "outline": outline,
                "width": width,
            }
        )

    def pure(self, **payload) -> dict:
        payload.setdefault("kind", "pure")
        return self.run_harness(payload)


class CoursePathTruthTest(PathHarness):
    def test_zero_evidence_paints_no_reached_segment(self) -> None:
        row = {"evidence_summary": {"independent": 0, "review_due": 0, "total_objectives": 4}}
        result = self.pure(row=row)
        self.assertEqual([segment["state"] for segment in result["segments"]], ["quiet"] * 4)
        self.assertNotIn("current", [segment["state"] for segment in result["segments"]])
        self.assertNotIn("done", [segment["state"] for segment in result["segments"]])
        self.assertEqual(result["shelfCaption"], "0 of 4 with evidence")

    def test_one_evidence_paints_one_segment_not_half_the_bar(self) -> None:
        row = {"evidence_summary": {"independent": 1, "review_due": 0, "total_objectives": 4}}
        result = self.pure(row=row)
        self.assertEqual([segment["state"] for segment in result["segments"]], ["done", "quiet", "quiet", "quiet"])

    def test_one_segment_per_objective_and_none_for_zero_objectives(self) -> None:
        four = self.pure(row={"evidence_summary": {"independent": 0, "review_due": 1, "total_objectives": 4}})
        self.assertEqual(len(four["segments"]), 4)
        self.assertEqual(four["segments"][0]["state"], "due")
        nought = self.pure(row={"evidence_summary": {"independent": 0, "review_due": 0, "total_objectives": 0}})
        self.assertEqual(nought["segments"], [])
        self.assertEqual(nought["shelfCaption"], "No sections yet")


class CheckpointPathRenderTest(PathHarness):
    def test_current_next_done_and_future_have_the_measured_sizes(self) -> None:
        html = self.render()["html"]
        self.assertEqual(html.count('data-cb-path-node-size="56"'), 1, html)
        self.assertEqual(html.count('data-cb-path-node-size="40"'), 1, html)
        self.assertEqual(html.count('data-cb-path-node-size="28"'), 2, html)
        compact = self.render(width=460)["html"]
        self.assertEqual(compact.count('data-cb-path-node-size="44"'), 1, compact)
        self.assertEqual(compact.count('data-cb-path-node-size="32"'), 1, compact)
        self.assertEqual(compact.count('data-cb-path-node-size="24"'), 2, compact)

    def test_sizes_are_a_pure_measured_route_decision(self) -> None:
        sizes = self.pure()["sizes"]
        self.assertEqual(
            sizes,
            {
                "current": 56,
                "next": 40,
                "done": 28,
                "future": 28,
                "currentCompact": 44,
                "nextCompact": 32,
                "doneCompact": 24,
                "futureCompact": 24,
            },
        )

    def test_position_is_geometry_not_evidence(self) -> None:
        result = self.pure(
            objectives=OUTLINE["objectives"], currentId="obj_02", nextId="obj_03"
        )
        self.assertEqual(result["kinds"], ["done", "current", "next", "future"])

    def test_every_node_is_a_real_destination_and_exactly_one_is_current(self) -> None:
        html = self.render()["html"]
        for objective_id in ("obj_01", "obj_02", "obj_03", "obj_04"):
            self.assertIn(f'data-cb-path-open="{objective_id}"', html)
        # One openable button per node, plus the details disclosure that is not a navigation.
        self.assertEqual(html.count('aria-label="Checkpoint '), 4, html)
        self.assertEqual(html.count('data-cb-path-current="true"'), 1, html)
        self.assertEqual(html.count('aria-current="step"'), 1, html)
        self.assertIn('data-cb-path-current="true"', html)

    def test_the_marker_reads_check_state_and_every_node_carries_its_state_word(self) -> None:
        html = self.render()["html"]
        self.assertIn('data-cb-path-marker-check="closed"', html)
        self.assertEqual(html.count('data-cb-path-marker-check="open"'), 2, html)
        self.assertIn('data-cb-path-marker-check="none"', html)
        for word in ("Check closed", "Check open", "No check yet"):
            self.assertIn(word, html)
        # The objective's own state word is present for every node.
        for word in ("Evidence", "Review due", "Started", "Not started"):
            self.assertIn(word, html)

    def test_current_and_next_are_expanded_and_show_the_real_detail(self) -> None:
        html = self.render()["html"]
        open_details = html.count('open=""')
        self.assertEqual(open_details, 2, html)
        self.assertIn('data-cb-path-detail="obj_02"', html)
        self.assertIn('data-cb-path-detail="obj_03"', html)
        self.assertIn("Do the steps", html)
        self.assertIn("2 committed attempts", html)
        self.assertIn("No committed attempts yet", html)
        self.assertIn("Last opened", html)
        self.assertIn("Not opened yet", html)

    def test_there_is_exactly_one_evidence_count_on_the_path(self) -> None:
        html = self.render()["html"]
        self.assertEqual(html.count("with evidence"), 1, html)
        self.assertIn("1 of 4 sections with evidence", html)
        self.assertEqual(html.count("data-cb-tally-caption"), 1, html)

    def test_overridden_is_its_own_word_and_never_evidence(self) -> None:
        rendered = self.render(OVERRODE_OUTLINE)
        html = rendered["html"]
        self.assertEqual(rendered["desk"]["settled"], 0)
        self.assertIn("Overridden", html)
        # H-155 owns the caption rule: a zero count is said as a count, never as a slogan.
        self.assertIn("0 of 2 sections with evidence", html)

    def test_no_lock_star_percentage_xp_streak_or_cumulative_checkpoint(self) -> None:
        html = self.render()["html"]
        text = re.sub(r"<[^>]+>", " ", html).lower()
        for forbidden in (r"\block(ed)?\b", "%", r"\bxp\b", r"\bstreak\b", r"\bstars?\b", r"\bcumulative\b", r"\bpoints?\b", r"\blevel up\b"):
            self.assertNotRegex(text, forbidden)
        self.assertNotIn('aria-disabled="true"', html)
        self.assertNotIn('disabled=""', html)

    def test_empty_course_says_there_is_no_path_yet(self) -> None:
        empty = {"enrollment_id": "enr_empty", "objectives": []}
        html = self.render(empty)["html"]
        self.assertIn("no objectives yet", html)
        self.assertNotIn('data-cb-path-node=', html)


if __name__ == "__main__":
    unittest.main()
