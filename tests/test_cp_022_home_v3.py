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

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
// CP-053: the route width must be pinned before the plugin module (and the SDK stub it imports)
// evaluates, or the stub's 1280 px default mounts the wide room scene instead of the hub. The
// import is dynamic on purpose: a static import is hoisted above this line.
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
const { CoursebookHome } = await import('./plugin.js')

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
class HomeSceneWideTest(Base):
    """CP-053 — the wide Home scene paints the binding reference's own copy.

    The scene is the `route >= 1200` branch only. Its six visible strings are the owner's reference
    frame (typos corrected); the hub below 1200 keeps the v3 hub copy untouched.
    """

    def test_scene_paints_the_reference_strings(self) -> None:
        html = self.home(width=1344, rows=[row(1), row(2)])
        self.assertIn('data-cb-home-scene=""', html)
        text = painted(html)
        self.assertIn("Your field library", text)
        self.assertIn("Choose a course or start a new expedition.", text)
        self.assertIn("Start a new course", text)
        self.assertIn("Browse library", text)
        self.assertIn("New course", text)

    def test_scene_keeps_one_filled_primary(self) -> None:
        html = self.home(width=1344, rows=[row(1), row(2)])
        self.assertEqual(html.count("data-cb-home-scene-primary"), 1, "the scene repeated the create action")
        self.assertEqual(html.count("data-cb-home-scene-secondary"), 1)

    def test_narrow_home_does_not_paint_the_scene_copy(self) -> None:
        html = self.home(width=1049, rows=[row(1), row(2)])
        self.assertNotIn("data-cb-home-scene", html)
        self.assertIn('data-cb-home-card=""', html, "the narrow Home keeps its hub shelf")
        self.assertIn("Your courses", painted(html))


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
        self.assertIn("You are offline", painted(html), "the banner speaks the deck's own sentence")
        self.assertIn('data-cb-home-shelf="ready"', html, "an offline shelf keeps the courses already read")

    def test_overflow_marks_the_scroll_and_keeps_the_measure(self) -> None:
        html = self.home(rows=[row(index) for index in range(1, 7)])
        self.assertIn("More courses to the right", painted(html))
        self.assertIn('data-cb-home-see-all=""', html)
        self.assertIn('data-cb-home-shelf-overflow="true"', html)
        self.assertNotIn("behind See all", painted(html), "the invented hidden-count sentence is gone")

    def test_home_v3_copy_has_an_id(self) -> None:
        """SPEC-V3 §4 — a screen may not render a string with no `COPY.md` id.

        Every visible Home string must be a `home.*` deck row, a value the backend state actually
        carries, or one of the enumerated CP-031 pendings below. The pendings are frozen here so a
        new invented sentence fails instead of shipping; `docs/visual-review/cp-022/MANIFEST.md`
        gap 3 names each one and the card body/COPY conflict it carries.

        The oracle is deliberately narrow: deck rows with a text placeholder (`{subject label}`,
        `{next step}`) are field values, not deck copy, so they are matched against the payload's
        own state string rather than a `. +` wildcard, and a negative control asserts an invented
        sentence is rejected.
        """
        deck = self._deck_patterns()
        deck_strings = self._deck_strings()
        pending = {
            # CP-031 — learner-visible with no `COPY.md` §2 id. Frozen so a new string fails here.
            # `Start a new course` is the card body's own label (the deck ships `Start a course` /
            # `Start your first course`); `See all` has no COPY.md §2 row at all.
            "Start a new course",
            "See all",
            "This is a failed read, not an empty library",
            "Parent Studio holds your lesson plans",
            "This profile has parent-led lesson plans, not a learner course",
            "Start a learner course here, or open Parent Studio",
            "Open Parent Studio",
            "No courses yet",
            "Every course here is archived",
            "Unarchive one in Courses to continue it",
            "Untitled course",
        }

        def state_values(payload: dict) -> set[str]:
            """Every string the test itself put into backend state, plus the fact pairs it composes."""
            values: set[str] = set()

            def walk(node) -> None:
                if isinstance(node, dict):
                    for item in node.values():
                        walk(item)
                elif isinstance(node, (list, tuple)):
                    for item in node:
                        walk(item)
                elif isinstance(node, str):
                    values.add(node.strip().rstrip("."))
                elif isinstance(node, (int, float)) and not isinstance(node, bool):
                    values.add(str(node))

            walk(payload)
            error = payload.get("error") or {}
            if isinstance(error.get("code"), str) and isinstance(error.get("message"), str):
                values.add(f"{error['code']}: {error['message']}")
            for item in payload.get("rows") or []:
                evidence = item.get("evidence_summary") or {}
                for done, total in (
                    (item.get("sections_done"), item.get("sections_total")),
                    (evidence.get("independent"), evidence.get("total_objectives")),
                ):
                    if isinstance(done, int) and isinstance(total, int):
                        values.add(f"{done} of {total} sections done")
                # The cover's two-letter mark is a projection of the title the state carries
                # (`cbCourseMonogram`), not invented copy; UI-K9 made it the printed plate's only
                # painted text, so the oracle has to know it is derived.
                title = item.get("title")
                if isinstance(title, str) and title.strip():
                    words = title.split()
                    values.add((words[0][:2] if len(words) == 1 else f"{words[0][0]}{words[1][0]}").upper())
            return values

        def allowed(text: str, values: set[str]) -> bool:
            value = text.strip().rstrip(".")
            if not value:
                return True
            if value in pending or value in values or value in deck_strings:
                return True
            return any(re.fullmatch(pattern, value) for pattern in deck)

        def composable(text: str, values: set[str]) -> bool:
            """True when the whole segment is a concatenation of frozen units and punctuation.

            The error state composes the backend read, the failed-read word and the deck's body into
            one paragraph, so the oracle cannot simply split on sentence stops: it must consume every
            character from a unit it already accepts. An invented sentence cannot be consumed.
            """
            units = sorted(
                {unit.strip().rstrip(".") for unit in (*deck_strings, *pending, *values)} - {""},
                key=len,
                reverse=True,
            )
            rest = text.strip()
            while rest:
                for unit in units:
                    if rest.startswith(unit):
                        tail = rest[len(unit):]
                        if not tail or tail[0] in " .!?…":
                            rest = tail.lstrip(" .!?…")
                            break
                else:
                    return False
            return True

        invented = "A sentence nobody wrote in COPY.md"
        self.assertFalse(allowed(invented, set()), "the oracle accepted an invented sentence")
        self.assertFalse(composable(invented, set()), "the oracle composed an invented sentence")
        sample = state_values(dict(rows=[row(1)]))
        self.assertFalse(
            allowed("You have 7 unfinished lessons", sample),
            "the oracle accepted a sentence built outside the deck and the state",
        )
        self.assertFalse(
            composable("You have 7 unfinished lessons", sample),
            "the oracle composed a sentence built outside the deck and the state",
        )

        payloads = [
            dict(rows=[row(1), row(2)]),
            dict(rows=[row(1, title="Harbour navigation", is_new=True, updated_at=stamp(1))]),
            dict(rows=[row(1, sections_done=None, sections_total=None, next_step=None)]),
            dict(status="ready", rows=[]),
            dict(status="ready", rows=[], libraryOverrides={"empty_reason": "all_archived"}),
            dict(status="loading", rows=[]),
            dict(status="error", rows=[], error={"code": "HOST_UNAVAILABLE", "message": "backend is down"}),
            dict(status="error", rows=[row(1)], error={"code": "HOST_UNAVAILABLE", "message": "backend is down"}),
            dict(online=False, rows=[row(1)]),
            dict(rows=[row(1, recipe="parent")]),
            dict(rows=[row(1, title=None, learner_label=None)]),
            # An overflowing shelf: `See all` is only visible with a fifth course, so the matrix
            # must render it or the string is never checked.
            dict(rows=[row(index) for index in range(1, 7)]),
            # CP-053 — the wide scene band paints its own reference copy; it is part of Home.
            dict(width=1344, rows=[row(1), row(2)]),
        ]
        rendered: list[str] = []
        for payload in payloads:
            html = self.home(**payload)
            rendered.append(painted(html))
            values = state_values(payload)
            for segment in re.findall(r">([^<>]+)<", html):
                text = segment.strip()
                if not text:
                    continue
                # A single capital is the deterministic typographic cover mark, not copy.
                if len(text) == 1:
                    continue
                # A composed paragraph is allowed when every unit it is built from is.
                if allowed(text, values) or composable(text, values):
                    continue
                if ": " in text and all(part.strip() in values for part in text.split(": ")):
                    continue
                for part in re.split(r"(?<=[.!?])\s+", text):
                    if not part.strip():
                        continue
                    self.assertTrue(
                        allowed(part, values) or composable(part, values),
                        f"Home rendered a string with no COPY.md id or state source: {part!r} in {payload}",
                    )
        # A frozen pending that never renders is dead weight: prove the matrix exercises both.
        painted_text = " ".join(rendered)
        for required in ("Start a new course", "See all"):
            self.assertIn(required, painted_text, f"{required!r} is frozen pending but never rendered")

    @staticmethod
    def _deck_cells() -> list[str]:
        path = ROOT / "docs" / "concept-parity" / "COPY.md"
        cells: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\|\s*`(home\.[a-z0-9.]+)`\s*\|\s*([^|]+?)\s*\|", line)
            if match:
                cells.append(match.group(2).strip().rstrip("."))
        return cells

    @classmethod
    def _deck_strings(cls) -> list[str]:
        """The deck rows without a placeholder — real copy lines, usable as composition units."""
        return [cell for cell in cls._deck_cells() if "{" not in cell]

    @staticmethod
    def _deck_patterns() -> list[str]:
        """The `home.*` copy deck's own strings, from `docs/concept-parity/COPY.md` §2.

        A text placeholder (`{subject label}`, `{next step}`) is a field value, not deck copy: those
        rows are skipped so the oracle tests the payload state instead of accepting any sentence
        with `. +`. Only numeric placeholders keep a shape (`\\d+`).
        """
        numeric = {"done", "total", "independent"}
        patterns: list[str] = []
        for cell in HomeV3StatesTest._deck_cells():
            pieces = re.split(r"\{([^}]*)\}", cell)
            pattern: list[str] = []
            for index, piece in enumerate(pieces):
                if index % 2 == 0:
                    pattern.append(re.escape(piece))
                elif piece.strip() in numeric:
                    pattern.append(r"\d+")
                else:
                    pattern = []
                    break
            if pattern:
                patterns.append("".join(pattern))
        return patterns


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
