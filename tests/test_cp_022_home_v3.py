"""CP-022 — the v3 global Home (R-HOME).

The v3 Home is a field library and a threshold: one threshold band of type, one filled terracotta
primary plus one quiet outline pill, one wooden shelf holding up to four real courses, the fox at
the plank's right end, and a kraft tag only for a course that is genuinely new.

These tests render the shipped module (`desktop/plugin.js`) through React and assert:

  * `test_home_v3_one_primary` — exactly one filled `PillAction` on the surface;
  * `test_home_v3_cards_use_card_facts_only` — every card string is a CP-005 `library_item` field,
    and no percentage, rating, star or XP claim appears anywhere;
  * `test_home_v3_no_course_hero_on_global_home` — the global Home never mounts a course hero,
    Continue plate or trailhead;
  * `test_home_v3_fox_tag_rule` — the O5 tag rule (newest course, under fourteen days, no attempts);
  * the named states: first use, loading, error, offline and overflow.

What this does not prove: the pixels. The capture matrix and the live rig carry that, and the
review packet in `docs/visual-review/cp-022/` records which cells are still open.
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

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import { CoursebookHome } from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const lib = (rows, overrides = {}) => ({
  items: rows,
  next_cursor: null,
  total: rows.length,
  empty_reason: rows.length ? null : 'no_courses',
  applied_filter: 'all',
  ...overrides
})
const html = renderToStaticMarkup(
  React.createElement('div', null,
    React.createElement(CoursebookHome, {
      library: {
        status: payload.status || 'ready',
        data: payload.status === 'idle' ? null : lib(payload.rows || [], payload.libraryOverrides || {}),
        error: payload.error || null,
        stale: Boolean(payload.stale)
      },
      modes: payload.modes || {},
      modesSupported: payload.modesSupported !== false,
      online: payload.online !== false,
      canCreate: payload.canCreate !== false,
      onStartCreate: () => {},
      onBrowseLibrary: () => {},
      onOpenCourse: () => {},
      onShowAll: () => {},
      onOpenStudio: () => {},
      onRetry: () => {}
    })
  )
)
process.stdout.write(html)
"""

DAY_MS = 24 * 60 * 60 * 1000


def stamp(days_ago: float) -> str:
    """An ISO stamp `days_ago` days before now, in the backend's own shape."""
    import datetime as _dt

    moment = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def row(index: int, **overrides) -> dict:
    value = {
        "enrollment_id": f"enr_{index:016x}",
        "course_id": f"crs_{index:016x}",
        "title": f"Course number {index}",
        "subtitle": None,
        "recipe": "committed",
        "level_label": None,
        "locale": None,
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "resume_lesson", "label": "Resume this lesson"},
        "evidence_summary": {
            "independent": 1,
            "review_due": 0,
            "total_objectives": 4,
            "current_objective_id": f"obj_{index:016x}",
        },
        "sections_done": 1,
        "sections_total": 4,
        "checks_recorded": 1,
        "is_new": False,
        "subject_label": "Small engines",
        "cover_artifact_id": None,
        "last_studied_at": None,
        "warning": None,
        "updated_at": stamp(index),
        "revision": 1,
    }
    value.update(overrides)
    return value


def painted(html: str) -> str:
    """Visible text only: tags stripped, entities kept as-is."""
    return re.sub(r"<[^>]*>", " ", html)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp022-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "render.mjs").write_text(HARNESS, encoding="utf-8")
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

    def home(self, **payload) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "render.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertNotIn("Warning:", result.stderr, result.stderr[-2000:])
        return result.stdout


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class HomeV3SurfaceTest(Base):
    def test_home_v3_one_primary(self) -> None:
        html = self.home(rows=[row(1), row(2)])
        self.assertEqual(html.count('data-cb3-pill="primary"'), 1, "the v3 Home carried more than one filled pill")
        self.assertEqual(html.count('data-cb-action="primary"'), 1)
        self.assertEqual(html.count('data-cb3-pill="quiet"'), 1, "the secondary path is one quiet outline pill")
        self.assertIn("Start a new course", painted(html))
        self.assertIn("Browse library", painted(html))

    def test_home_v3_cards_use_card_facts_only(self) -> None:
        html = self.home(
            rows=[
                row(
                    1,
                    title="Small-engine maintenance",
                    sections_done=2,
                    sections_total=5,
                    checks_recorded=2,
                    subject_label="Small engines",
                    is_new=True,
                    updated_at=stamp(30),
                    next_step={"kind": "resume_lesson", "label": "Resume this lesson"},
                )
            ]
        )
        text = painted(html)
        self.assertIn("2 of 5 sections done", text, "the evidence line must be the CP-005 section pair")
        self.assertIn("Small engines", text, "the subject chip must be the recorded subject label")
        self.assertIn("Resume this lesson", text, "the next step is the backend's own label")
        self.assertIn("New", text, "a course with no attempt reads New")
        # No invented metric of any kind, and no percentage anywhere.
        for banned in (r"\bstars?\b", r"\brating", r"\bxp\b", "streak", "mastery", "%"):
            self.assertIsNone(re.search(banned, text.lower()), f"the v3 Home invented {banned!r}")
        self.assertEqual(text.count("Small-engine maintenance"), 1, "the card printed its title twice")

    def test_home_v3_card_omits_a_fact_the_read_did_not_carry(self) -> None:
        html = self.home(
            rows=[
                row(
                    1,
                    sections_done=None,
                    sections_total=None,
                    subject_label=None,
                    is_new=False,
                    evidence_summary={"independent": None, "total_objectives": None},
                )
            ]
        )
        text = painted(html)
        self.assertNotIn("sections done", text, "a missing section pair must be omitted, never guessed")
        self.assertNotIn("of 4 sections", text)

    def test_home_v3_card_falls_back_to_the_evidence_pair(self) -> None:
        # Deck `home.card.meta`: the CP-005 section pair first, else the evidence summary pair.
        html = self.home(
            rows=[
                row(
                    1,
                    sections_done=None,
                    sections_total=None,
                    evidence_summary={"independent": 3, "total_objectives": 7},
                )
            ]
        )
        self.assertIn("3 of 7 sections done", painted(html))

    def test_home_v3_no_course_hero_on_global_home(self) -> None:
        html = self.home(rows=[row(1), row(2)])
        self.assertIn('data-cb-home-shelf="ready"', html)
        for forbidden in ("data-cb-continue", "data-cb-trailhead", "data-cb-desk", "data-cb-course-home"):
            self.assertNotIn(forbidden, html, f"the global Home mounted {forbidden}")
        self.assertNotIn(">Continue<", html)

    def test_home_v3_shelf_holds_four_and_scrolls_instead_of_shrinking(self) -> None:
        html = self.home(rows=[row(index) for index in range(1, 8)])
        self.assertEqual(html.count('data-cb-home-card=""'), 4, "the v3 shelf holds four courses")
        self.assertIn('data-cb-home-see-all=""', html, "a fifth course must not shrink the shelf")
        self.assertIn("Course number 1", html, "the newest course leads the shelf")
        self.assertNotIn("Course number 6", html, "the fifth course belongs behind See all")
        self.assertIn('data-cb-home-shelf-row=""', html)
        self.assertRegex(html, r'data-cb-home-shelf-row=""[^>]*data-cb-shelf-mask="none"')

    def test_home_v3_fox_tag_rule(self) -> None:
        # A course written yesterday with no attempt carries the kraft tag, pointing at its title.
        fresh = self.home(rows=[row(1, title="Harbour navigation", is_new=True, updated_at=stamp(1))])
        self.assertIn('data-cb-home-tag=""', fresh, "a genuinely new course must carry the tag")
        self.assertIn("Harbour navigation", painted(fresh))
        self.assertIn("New course", painted(fresh))
        # Fourteen days is the boundary: older than that, no tag.
        old = self.home(rows=[row(1, title="Harbour navigation", is_new=True, updated_at=stamp(15))])
        self.assertNotIn('data-cb-home-tag=""', old, "a course older than fourteen days must not carry the tag")
        # A course with an attempt is not new, even when it is the newest row.
        tried = self.home(
            rows=[row(1, title="Harbour navigation", is_new=False, updated_at=stamp(1))]
        )
        self.assertNotIn('data-cb-home-tag=""', tried, "a course with an attempt is not new")
        # The tag follows the newest course only: an older new course does not inherit it.
        ordered = self.home(
            rows=[
                row(1, title="Fresh but attempted", is_new=False, updated_at=stamp(1)),
                row(2, title="Newer", is_new=False, updated_at=stamp(2)),
            ]
        )
        self.assertNotIn('data-cb-home-tag=""', ordered, "the tag must not move to an older course")


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class HomeV3StatesTest(Base):
    def test_first_run_is_the_start_plate_on_the_plank(self) -> None:
        html = self.home(status="ready", rows=[])
        self.assertIn('data-cb-home="empty"', html)
        self.assertIn('data-cb-home-shelf="empty"', html)
        self.assertIn("data-cb-home-start-plate", html, "first run is a start plate on the plank")
        self.assertIn('data-cb3-fox="wave"', html, "first run carries the waving fox")
        self.assertIn("Start a new course", painted(html))
        self.assertIn("No courses yet.", painted(html))
        self.assertEqual(html.count("data-cb-home-start-plate"), 1)
        self.assertNotIn("data-cb-home-tag", html)

    def test_first_run_has_one_create_action(self) -> None:
        html = self.home(status="ready", rows=[])
        self.assertEqual(html.count('data-cb3-pill="primary"'), 1, "first run repeated the create action")

    def test_loading_paints_silhouettes_and_no_shimmer(self) -> None:
        html = self.home(status="loading", rows=[])
        self.assertIn('data-cb-home="loading"', html)
        self.assertIn('data-cb-home-shelf="loading"', html)
        self.assertEqual(html.count("data-cb-home-skeleton"), 4, "loading keeps the shelf's own boxes")
        self.assertIn("Reading your courses", painted(html))
        for banned in ("animation", "keyframes", "shimmer", "pulse"):
            self.assertNotIn(banned, html.lower(), f"loading introduced {banned}")

    def test_error_names_the_failed_read_and_offers_one_retry(self) -> None:
        html = self.home(status="error", rows=[], error={"code": "HOST_UNAVAILABLE", "message": "backend is down"})
        self.assertIn('data-cb-home="error"', html)
        self.assertIn('data-cb-home-shelf="error"', html)
        self.assertIn("HOST_UNAVAILABLE", painted(html), "the failed read is named")
        self.assertIn("Your courses could not be read", painted(html))
        self.assertIn("data-cb-home-retry", html)
        self.assertEqual(html.count('data-cb-home-retry=""'), 1, "an error offers exactly one retry")
        self.assertNotIn("Nothing here yet", painted(html), "a failed read was painted as an empty shelf")

    def test_offline_names_the_connection_and_keeps_the_shelf(self) -> None:
        html = self.home(online=False, rows=[row(1)])
        self.assertIn("data-cb-home-offline", html)
        self.assertIn("Offline", painted(html))
        self.assertIn('data-cb-home-shelf="ready"', html, "an offline shelf keeps the courses already read")

    def test_overflow_marks_the_scroll_and_keeps_the_measure(self) -> None:
        html = self.home(rows=[row(index) for index in range(1, 7)])
        self.assertIn("More courses to the right", painted(html))
        self.assertIn('data-cb-home-see-all=""', html)
        self.assertIn("2 more courses behind See all.", painted(html))

    def test_parent_only_profile_points_at_parent_studio(self) -> None:
        html = self.home(rows=[row(1, recipe="parent")])
        self.assertIn('data-cb-home-shelf="parent-only"', html)
        self.assertIn("Open Parent Studio", painted(html))

    def test_archived_shelf_names_the_archive_path(self) -> None:
        html = self.home(status="ready", rows=[], libraryOverrides={"empty_reason": "all_archived"})
        self.assertIn('data-cb-home-empty-reason="all_archived"', html)
        self.assertIn("See archived courses", painted(html))


if __name__ == "__main__":
    unittest.main()
