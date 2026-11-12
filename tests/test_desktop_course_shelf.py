"""The course shelf: one object per course, deterministic cover, honest grouping (H-99).

Three surfaces render `library.list` rows — Library, All Courses and Parent Studio — and the
store can hold many enrollments or plans that describe the same course. This module imports the
shipped plugin through Node and *executes* the grouping and cover helpers, then renders the cover
with React, so "same course, one row" and "same cover on reload" are proven rather than asserted
as source strings.

The second half is a source check for the parts that are JSX-composed inside a hook-heavy view
(Library's route header actions and its trust disclosure), which a static render cannot mount.
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

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  CourseCover,
  cb3KitSource,
  cbCourseGoalLine,
  cbCourseMonogram,
  cbCoursePathCaption,
  cbCoursePathSegments,
  cbSealStation,
  cbShelfFingerprint,
  cbShelfGroupKey,
  groupShelfRows
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const describe = (row) => ({
  fingerprint: cbShelfFingerprint(row),
  key: cbShelfGroupKey(row),
  monogram: cbCourseMonogram(row.title),
  station: cbSealStation(row.course_id),
  goal: cbCourseGoalLine(row),
  path: cbCoursePathSegments(row),
  caption: cbCoursePathCaption(row)
})

const groups = groupShelfRows(payload.rows)
const summary = {
  groups: groups.map((group) => ({
    key: group.key,
    count: group.count,
    versions: group.versions,
    courses: group.courses,
    label: group.label,
    primary: group.primary.enrollment_id,
    members: group.members.map((member) => member.enrollment_id),
    fingerprint: cbShelfFingerprint(group.primary)
  })),
  rows: payload.rows.map(describe)
}

if (payload.mode === 'pure') {
  process.stdout.write(JSON.stringify(summary))
} else {
  const html = renderToStaticMarkup(
    React.createElement(
      'div',
      { 'data-cb-scope': 'light' },
      groups.map((group) =>
        React.createElement(CourseCover, {
          key: group.key,
          row: group.primary,
          group,
          identity: payload.identity || undefined,
          onOpenMember: () => {},
          action: React.createElement('button', { type: 'button' }, 'Open')
        })
      )
    )
  )
  process.stdout.write(JSON.stringify({
    ...summary,
    html,
    kit: {
      japanese: cb3KitSource('japanese-cover-3x2'),
      parent: cb3KitSource('parent-cover-3x2'),
      technical: cb3KitSource('technical-cover-3x2'),
      lessonRoom: cb3KitSource('field-atlas-lesson-room')
    }
  }))
}
"""

SDK_STUB = """
import React from 'react'

const el = (tag, props, children) => React.createElement(tag, props, children)

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const useValue = (atom) => atom.get()
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })

export const Button = (props) => el('button', { type: 'button', 'aria-label': props['aria-label'], onClick: props.onClick }, props.children)
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, props.children)
export const Codicon = (props) => el('span', { className: 'codicon', 'data-icon': props.name }, null)
export const ListRow = (props) => el('div', { className: 'list-row' }, [props.title, props.description, props.action])
export const SegmentedControl = () => null
export const SearchField = () => null
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const EmptyState = (props) => el('div', { className: 'empty-state' }, [props.title, props.description])
export const ErrorState = (props) => el('div', { className: 'error-state' }, [props.title, props.description, props.children])
export const PanelEmpty = () => null
export const PanelSectionLabel = () => null
export const Input = () => null
export const Textarea = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const Tabs = () => null
export const Tip = () => null
export const SandboxedFrame = () => null
export const MessageTextContent = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null

const atom = (value) => ({ get: () => value })
export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: 1280, height: 900, narrow: false })
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


def shelf_row(**overrides) -> dict:
    """One `library.list` item in the contract's own field names."""
    row = {
        "enrollment_id": "enr_0000000000000001",
        "course_id": "crs_0000000000000001",
        "title": "Kitchen fractions for a 9-year-old",
        "subtitle": None,
        "recipe": "parent",
        "level_label": None,
        "locale": None,
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "review_plan", "label": "Review and approve the plan"},
        "evidence_summary": {
            "independent": 0,
            "review_due": 0,
            "total_objectives": 4,
            "current_objective_id": None,
        },
        "warning": None,
        "updated_at": "2026-11-06T18:00:00.000000+00:00",
        "revision": 1,
    }
    row.update(overrides)
    return row


def duplicate_rows(count: int, **overrides) -> list[dict]:
    rows = []
    for index in range(count):
        row = shelf_row(
            enrollment_id=f"enr_{index:016d}",
            course_id=f"crs_{index:016d}",
            updated_at=f"2026-11-{index % 5 + 1:02d}T18:00:00.000000+00:00",
            revision=index + 1,
        )
        row.update(overrides)
        rows.append(row)
    return rows


class CourseShelfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to execute the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-shelf-")
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
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_harness(self, payload: dict) -> dict:
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
        return json.loads(result.stdout)

    # ── grouping ─────────────────────────────────────────────────────────────────────────

    def test_fourteen_identical_parent_plans_become_one_object(self) -> None:
        result = self.run_harness({"mode": "pure", "rows": duplicate_rows(14)})
        self.assertEqual(len(result["groups"]), 1, "fourteen copies of one plan must be one shelf object")
        group = result["groups"][0]
        self.assertEqual(group["count"], 14)
        self.assertEqual(group["versions"], 1)
        self.assertEqual(group["label"], "14 copies of this plan")

    def test_one_pack_is_one_row_with_its_enrollment_count(self) -> None:
        rows = duplicate_rows(
            3,
            title="Conversational Japanese",
            recipe="casual",
            provenance={"source": "bundled", "pack_id": "jp-affection-l0", "pack_version": "1.0.0"},
        )
        result = self.run_harness({"mode": "pure", "rows": rows})
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["label"], "3 enrollments")

    def test_distinct_courses_stay_distinct(self) -> None:
        rows = [
            shelf_row(enrollment_id="enr_a", course_id="crs_a", title="Washer setup", recipe="one_off"),
            shelf_row(enrollment_id="enr_b", course_id="crs_b", title="Conversational Japanese", recipe="casual"),
        ]
        result = self.run_harness({"mode": "pure", "rows": rows})
        self.assertEqual(len(result["groups"]), 2)
        self.assertEqual({group["label"] for group in result["groups"]}, {""})

    def test_grouping_is_order_independent(self) -> None:
        rows = duplicate_rows(5) + [
            shelf_row(enrollment_id="enr_x", course_id="crs_x", title="Washer setup", recipe="one_off")
        ]
        forward = self.run_harness({"mode": "pure", "rows": rows})
        backward = self.run_harness({"mode": "pure", "rows": list(reversed(rows))})
        self.assertEqual([group["key"] for group in forward["groups"]], [group["key"] for group in backward["groups"]])
        self.assertEqual(
            [group["primary"] for group in forward["groups"]],
            [group["primary"] for group in backward["groups"]],
            "the primary enrollment of a group must not depend on the read order",
        )

    def test_primary_is_the_active_newest_record(self) -> None:
        rows = duplicate_rows(4)
        rows[2]["enrollment_status"] = "archived"
        rows[2]["updated_at"] = "2026-12-01T00:00:00.000000+00:00"
        result = self.run_harness({"mode": "pure", "rows": rows})
        self.assertEqual(result["groups"][0]["primary"], "enr_0000000000000003", "an archived plan must not lead")

    def test_different_objective_counts_are_reported_as_versions(self) -> None:
        rows = duplicate_rows(2)
        rows[1]["evidence_summary"] = {**rows[1]["evidence_summary"], "total_objectives": 6}
        result = self.run_harness({"mode": "pure", "rows": rows})
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["versions"], 2)
        self.assertIn("2 versions", result["groups"][0]["label"])

    def test_no_rows_group_to_empty_shelf(self) -> None:
        result = self.run_harness({"mode": "pure", "rows": []})
        self.assertEqual(result["groups"], [])

    # ── covers ───────────────────────────────────────────────────────────────────────────

    def test_cover_is_identical_across_runs(self) -> None:
        rows = [shelf_row()]
        first = self.run_harness({"mode": "pure", "rows": rows})["rows"][0]
        second = self.run_harness({"mode": "pure", "rows": rows})["rows"][0]
        self.assertEqual(first, second, "a reload must paint the same cover")
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{8}$")

    def test_cover_station_and_monogram_are_derived_not_random(self) -> None:
        result = self.run_harness(
            {
                "mode": "pure",
                "rows": [
                    shelf_row(enrollment_id="enr_a", course_id="crs_a", title="Washer setup"),
                    shelf_row(enrollment_id="enr_b", course_id="crs_b", title="Conversational Japanese"),
                ],
            }
        )
        stations = [row["station"] for row in result["rows"]]
        self.assertTrue(all(0 <= station <= 3 for station in stations))
        self.assertEqual([row["monogram"] for row in result["rows"]], ["WS", "CJ"])

    def test_one_segment_per_objective_and_only_real_evidence_is_painted(self) -> None:
        cases = [
            (0, 0, 0, []),
            (0, 0, 4, ["quiet", "quiet", "quiet", "quiet"]),
            (0, 2, 4, ["due", "due", "quiet", "quiet"]),
            (2, 0, 6, ["done", "done", "quiet", "quiet", "quiet", "quiet"]),
            (6, 0, 6, ["done", "done", "done", "done", "done", "done"]),
            (1, 2, 4, ["done", "due", "due", "quiet"]),
        ]
        for independent, due, total, expected in cases:
            row = shelf_row(evidence_summary={"independent": independent, "review_due": due, "total_objectives": total})
            result = self.run_harness({"mode": "pure", "rows": [row]})["rows"][0]
            self.assertEqual(len(result["path"]), total, f"path for {total} objectives must be one segment each")
            self.assertEqual([segment["state"] for segment in result["path"]], expected)
            self.assertNotIn("current", [segment["state"] for segment in result["path"]])

    def test_a_course_too_large_to_draw_honestly_shows_the_count_only(self) -> None:
        row = shelf_row(evidence_summary={"independent": 4, "review_due": 0, "total_objectives": 20})
        result = self.run_harness({"mode": "pure", "rows": [row]})["rows"][0]
        self.assertEqual(result["path"], [])
        self.assertEqual(result["caption"], "4 of 20 with evidence")

    def test_path_caption_carries_exact_counts(self) -> None:
        row = shelf_row(evidence_summary={"independent": 2, "review_due": 1, "total_objectives": 6})
        result = self.run_harness({"mode": "pure", "rows": [row]})["rows"][0]
        self.assertEqual(result["caption"], "2 of 6 with evidence · 1 due")
        empty = self.run_harness(
            {"mode": "pure", "rows": [shelf_row(evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 0})]}
        )["rows"][0]
        self.assertEqual(empty["caption"], "No sections yet")
        zero = self.run_harness(
            {"mode": "pure", "rows": [shelf_row(evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 4})]}
        )["rows"][0]
        self.assertEqual(zero["caption"], "0 of 4 with evidence")

    def test_goal_line_is_real_or_says_it_is_missing(self) -> None:
        with_goal = self.run_harness({"mode": "pure", "rows": [shelf_row(goal="Cut a sandwich into eighths.")]})["rows"][0]
        self.assertEqual(with_goal["goal"], "Cut a sandwich into eighths.")
        fallback = self.run_harness({"mode": "pure", "rows": [shelf_row(next_step={"kind": None, "label": None})]})["rows"][0]
        self.assertEqual(fallback["goal"], "No next step recorded")

    # ── rendering ────────────────────────────────────────────────────────────────────────

    def test_rendered_shelf_has_one_cover_and_one_disclosure_per_group(self) -> None:
        result = self.run_harness({"mode": "render", "rows": duplicate_rows(14)})
        html = result["html"]
        self.assertEqual(html.count('data-cb-course-cover="'), 1, "fourteen plans must render one cover")
        self.assertEqual(html.count('data-cb-shelf-versions="'), 1)
        self.assertEqual(html.count('data-cb-course-path="4"'), 1)
        self.assertIn("14 copies of this plan", html)
        self.assertNotIn("Preview", html)

    def test_rendered_cover_keeps_a_single_primary_action(self) -> None:
        result = self.run_harness(
            {
                "mode": "render",
                "rows": [
                    shelf_row(enrollment_id="enr_a", course_id="crs_a", title="Washer setup"),
                    shelf_row(enrollment_id="enr_b", course_id="crs_b", title="Conversational Japanese"),
                ],
            }
        )
        html = result["html"]
        self.assertEqual(html.count('data-cb-course-cover="'), 2)
        self.assertEqual(html.count("<button"), 2, "one action per shelf object, never a duplicate primary")

    # ── D-007: the Courses card reads the approved display cover ─────────────────────────

    @staticmethod
    def cover_block(html: str, title: str) -> str:
        """The cover field of the article whose title is `title` (the field precedes the heading)."""
        article = html.rindex("<article", 0, html.index(title))
        return html[article : html.index(title)]

    def test_courses_card_serves_the_seeded_packs_own_plate(self) -> None:
        rows = [
            shelf_row(
                enrollment_id="enr_jp",
                course_id="crs_jp",
                title="Japanese: the two ways to say it",
                provenance={"source": "bundled", "pack_id": "japanese-affection-context-l0", "pack_version": "2.2.0"},
            ),
            shelf_row(
                enrollment_id="enr_parent",
                course_id="crs_parent",
                title="Measuring at the kitchen table",
                provenance={"source": "bundled", "pack_id": "parent-measurement-practice", "pack_version": "2.0.0"},
            ),
            shelf_row(
                enrollment_id="enr_tech",
                course_id="crs_tech",
                title="What a pack manifest declares",
                provenance={"source": "bundled", "pack_id": "technical-pack-literacy", "pack_version": "2.1.0"},
            ),
        ]
        result = self.run_harness({"mode": "render", "rows": rows})
        html = result["html"]
        expected = {
            "Japanese: the two ways to say it": ("japanese-cover-3x2", result["kit"]["japanese"]),
            "Measuring at the kitchen table": ("parent-cover-3x2", result["kit"]["parent"]),
            "What a pack manifest declares": ("technical-cover-3x2", result["kit"]["technical"]),
        }
        for title, (plate_id, plate_src) in expected.items():
            block = self.cover_block(html, title)
            with self.subTest(title=title):
                self.assertIn('data-cb-cover-kind="kit"', block, "the course card rendered no kit cover")
                self.assertIn(f'src="{plate_src}"', block, "the card does not serve the pack's own approved plate")
                self.assertIn(f'data-cb-cover-plate="{plate_id}"', block)
                self.assertIn("object-fit:cover", block)
        self.assertNotIn('data-cb-cover-kind="letter"', html, "a letter plate stands in for the cover")

    def test_courses_card_without_a_mapped_plate_wears_the_printed_cover(self) -> None:
        # UI-K9: the lesson room is painted as a cafe study room, so an unmapped course may not wear
        # it. The card falls back to its own title printed on kit paper behind a measured rule.
        result = self.run_harness(
            {
                "mode": "render",
                "rows": [shelf_row(title="Sourdough starter", provenance={"source": "authored", "pack_id": None})],
            }
        )
        html = result["html"]
        block = self.cover_block(html, "Sourdough starter")
        self.assertIn('data-cb-cover-kind="letter"', block)
        self.assertIn('data-cb-cover-letter=""', block, "the printed cover is not dressed as kit paper")
        printed = re.search(r'data-cb-cover-letter=""(.*?)<h3', html, re.S)
        printed_text = printed.group(1) if printed else ""
        # GM-002: the cover carries the course's mark alongside (or instead of) a first title.
        self.assertIn(">SS<", printed_text, "the printed cover lost its mark")
        self.assertNotIn('src="' + result["kit"]["lessonRoom"] + '"', html,
                         "an unmapped course still wears the painted lesson room")
        self.assertNotIn('data-cb-cover-plate="field-atlas-lesson-room"', html)


class LibraryActionTest(unittest.TestCase):
    """The parts Library composes inside a hook-heavy view are checked as source."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")
        start = cls.source.index("function LibraryView(")
        cls.library = cls.source[start : start + 20000]

    def test_library_body_does_not_repeat_the_import_actions(self) -> None:
        self.assertNotIn("jsx(SyllabusEntry", self.library, "the library body must not restate the header's two import paths")
        self.assertEqual(self.source.count("jsx(SyllabusEntry"), 0)

    def test_route_header_has_one_primary_and_one_secondary_for_library(self) -> None:
        # H-196: the two import paths now sit in the Workshop's Library surface, one primary
        # (Import pack) and one secondary (syllabus), instead of the route header.
        header = self.source[self.source.index("'data-cb-workshop-library-actions'") :]
        header = header[: header.index("jsx(LibraryView")]
        self.assertIn("SYLLABUS_COPY.action", header)
        self.assertIn("children: 'Import pack'", header)
        # H-151: the header's one filed action is the Coursebook primary, not the host default.
        self.assertIn("variant: 'primary'", header)
        self.assertIn("variant: 'secondary'", header)

    def test_trust_copy_is_a_real_disclosure(self) -> None:
        self.assertIn("'data-cb-affordance': 'disclosure'", self.library)
        self.assertIn("sdk.Codicon", self.library)
        self.assertIn("data-cb-pack-trust", self.library)


if __name__ == "__main__":
    unittest.main()
