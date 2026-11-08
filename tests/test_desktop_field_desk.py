"""The Field Desk home answers "what do I do next?" from reads the contract already has.

The plugin is one ESM file with no build step, so the test renders the shipped module through
React and checks the DOM it produces. The fixtures are shaped like the contract's own responses
(`library.list` row, `course.outline` objectives, `lesson.page` sources) — they are *input*, and
the assertions are that the desk never invents an estimate, a next step, a source or a course.

What this does not prove: that a live backend currently returns these rows. It proves the view is
honest about whatever it is served, including the empty, loading, failed and not-recorded cases.
"""

from __future__ import annotations

import json
import os
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
import { FieldDeskHome, buildDeskModel, deskEstimateLabel, mainlineObjective } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

if (payload.kind === 'model') {
  const desk = buildDeskModel({ library: payload.library, outline: payload.outline, estimate: payload.estimate })
  process.stdout.write(JSON.stringify({
    desk,
    label: deskEstimateLabel(payload.estimate),
    mainline: mainlineObjective(payload.row, payload.outline ? payload.outline.objectives : [])
  }))
} else {
  const desk = buildDeskModel({ library: payload.library, outline: payload.outline, estimate: payload.estimate })
  const html = renderToStaticMarkup(
    React.createElement('div', { 'data-cb-scope': payload.mode || 'light', style: { color: 'var(--cb-ink)' } },
      React.createElement(FieldDeskHome, {
        desk,
        libraryStatus: payload.libraryStatus || 'ready',
        libraryError: payload.libraryError || null,
        stale: Boolean(payload.stale),
        busy: false,
        notice: null,
        onRetry: () => {},
        onCreate: () => {},
        onPrimary: () => {},
        onOpenSection: () => {},
        onOpen: () => {},
        onShowAll: () => {},
        sourcesOpen: Boolean(payload.sourcesOpen),
        onToggleSources: () => {},
        sourcesStatus: payload.sourcesStatus || 'idle',
        sourcesError: payload.sourcesError || null,
        sources: payload.sources || null,
        onRetrySources: () => {},
        implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'parent.brief.get'])
      })
    )
  )
  process.stdout.write(html)
}
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
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })

const pass = (props) => {
  const out = { type: 'button', onClick: props.onClick, disabled: Boolean(props.disabled) }
  for (const key of ['className', 'aria-expanded', 'aria-controls', 'aria-current', 'id', 'role', 'title']) {
    if (props[key] !== undefined) out[key] = props[key]
  }
  return out
}

export const Button = (props) => el('button', pass(props), textOf(props))
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const ListRow = (props) =>
  el('div', { className: 'list-row' }, [
    el('div', { key: 'title', className: 'list-row-title' }, props.title),
    el('div', { key: 'description', className: 'list-row-description' }, props.description),
    el('div', { key: 'action', className: 'list-row-action' }, props.action)
  ])
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
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = () => null
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null
export const MessageTextContent = () => null

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: Number(process.env.CB_TEST_WIDTH || 1280), height: 900, narrow: false })
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


def library_row(**overrides) -> dict:
    """One `library.list` item, in the contract's own field names."""
    row = {
        "enrollment_id": "enr_0123456789abcdef",
        "course_id": "crs_0123456789abcdef",
        "title": "Small-engine maintenance",
        "subtitle": None,
        "recipe": "committed",
        "level_label": None,
        "locale": None,
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
        "evidence_summary": {
            "independent": 1,
            "review_due": 1,
            "total_objectives": 4,
            "current_objective_id": "obj_0000000000000003",
        },
        "warning": None,
        "updated_at": "2026-11-06T18:00:00.000000+00:00",
        "revision": 7,
    }
    row.update(overrides)
    return row


def library(*rows: dict) -> dict:
    return {
        "items": list(rows),
        "next_cursor": None,
        "total": len(rows),
        "empty_reason": None,
        "applied_filter": "all",
    }


OUTLINE = {
    "enrollment_id": "enr_0123456789abcdef",
    "plan": {"plan_id": "pln_0123456789abcdef", "version": 1, "state": "approved", "plan_hash": "sha256:" + "b" * 64},
    "objectives": [
        {
            "objective_id": "obj_0000000000000001",
            "ordinal": 1,
            "title": "Name the three things an engine needs",
            "evidence_target": "recall",
            "state": "independent_evidence",
            "check_state": "closed",
            "attempt_count": 1,
            "independent": True,
            "last_opened_at": "2026-11-05T10:00:00.000000+00:00",
        },
        {
            "objective_id": "obj_0000000000000002",
            "ordinal": 2,
            "title": "Diagnose a no-start",
            "evidence_target": "procedure",
            "state": "review_due",
            "check_state": "open",
            "attempt_count": 1,
            "independent": False,
            "last_opened_at": "2026-11-06T17:30:00.000000+00:00",
        },
        {
            "objective_id": "obj_0000000000000003",
            "ordinal": 3,
            "title": "Replace a fouled plug",
            "evidence_target": "procedure",
            "state": "introduced",
            "check_state": "none",
            "attempt_count": 0,
            "independent": False,
            "last_opened_at": None,
        },
        {
            "objective_id": "obj_0000000000000004",
            "ordinal": 4,
            "title": "Check compression safely",
            "evidence_target": "procedure",
            "state": "not_started",
            "check_state": "none",
            "attempt_count": 0,
            "independent": False,
            "last_opened_at": None,
        },
    ],
    "total": 4,
    "truncated": False,
}

SOURCES = [
    {"source_id": "src_manual001", "title": "Shop manual §4 — ignition", "support_status": "supported", "fetched_at": "2026-11-01T00:00:00.000000+00:00"},
    {"source_id": "src_forum0002", "title": "Field notes — spark inspection", "support_status": "stale", "fetched_at": "2026-10-20T00:00:00.000000+00:00"},
]


class FieldDeskRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-field-desk-")
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

    def run_harness(self, payload: dict) -> str:
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
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    def render(self, **overrides) -> str:
        payload = {
            "kind": "render",
            "library": library(library_row()),
            "outline": OUTLINE,
            "estimate": {"status": "ready", "minutes": 20, "source": "parent_brief", "error": None},
            "sourcesOpen": False,
            "sourcesStatus": "idle",
        }
        payload.update(overrides)
        return self.run_harness(payload)

    def model(self, **overrides) -> dict:
        payload = {
            "kind": "model",
            "library": library(library_row()),
            "outline": OUTLINE,
            "estimate": {"status": "ready", "minutes": 20, "source": "parent_brief", "error": None},
        }
        payload.update(overrides)
        return json.loads(self.run_harness(payload))

    # -- the Continue card ------------------------------------------------------------------
    def test_continue_names_the_section_the_next_action_and_the_position(self) -> None:
        html = self.render()
        self.assertIn('data-cb-desk="ready"', html)
        self.assertIn('data-cb-continue-section', html)
        # `resolve_review_due` in the row's next_step makes the due review the section to continue.
        self.assertIn("Diagnose a no-start", html)
        self.assertIn("Review 1 objective(s)", html)
        self.assertIn("Next · ", html)
        self.assertIn("Section 2 of 4", html)

    def test_a_narrow_desk_stacks_and_drops_the_course_stamp(self) -> None:
        html = self.render(width=460)
        self.assertIn('data-cb-desk-layout="stacked"', html)
        self.assertIn('data-cb-continue-compact="true"', html)
        self.assertNotIn("data-cb-course-stamp", html)
        # The title is not being squeezed into a term-per-line column; the full row remains.
        self.assertIn("Diagnose a no-start", html)
        self.assertIn("Open the section", html)

    def test_a_wide_desk_keeps_the_course_stamp(self) -> None:
        html = self.render(width=1280)
        self.assertIn('data-cb-desk-layout="wide"', html)
        self.assertIn('data-cb-continue-compact="false"', html)
        self.assertIn("data-cb-course-stamp", html)

    def test_continue_shows_the_recorded_estimate_and_last_touched(self) -> None:
        html = self.render()
        self.assertIn("≈ 20 min", html)
        self.assertIn("Last touched", html)
        self.assertIn('data-cb-continue-touched="section"', html)

    def test_a_course_with_no_recorded_estimate_says_so_instead_of_guessing(self) -> None:
        html = self.render(estimate={"status": "none", "minutes": None, "source": None, "error": None})
        self.assertIn("Session length not recorded", html)
        self.assertNotRegex(html, r"≈ \d+ min")

    def test_estimate_label_never_derives_minutes(self) -> None:
        self.assertEqual(self.model(estimate={"status": "none"})["label"], "Session length not recorded")
        self.assertEqual(self.model(estimate={"status": "loading"})["label"], "Reading the estimate")
        self.assertEqual(self.model(estimate={"status": "ready", "minutes": 0})["label"], "Session length not recorded")
        self.assertEqual(
            self.model(estimate={"status": "ready", "minutes": 15, "source": "pack_manifest"})["label"], "≈ 15 min"
        )

    # -- the path ---------------------------------------------------------------------------
    def test_path_lists_every_objective_with_its_state_word(self) -> None:
        html = self.render()
        for title in ("Name the three things an engine needs", "Diagnose a no-start",
                      "Replace a fouled plug", "Check compression safely"):
            self.assertIn(title, html)
        for state in ("independent_evidence", "review_due", "introduced", "not_started"):
            self.assertIn(f'data-cb-path-state="{state}"', html)
        # State is text, never colour alone.
        for word in ("Evidence", "Review due", "Started", "Not started"):
            self.assertIn(word, html)

    def test_path_marks_exactly_one_current_step(self) -> None:
        html = self.render()
        self.assertEqual(html.count('data-cb-path-current="true"'), 1)
        self.assertEqual(html.count('aria-current="step"'), 1)

    def test_path_summary_counts_real_states_not_vanity(self) -> None:
        html = self.render()
        self.assertIn("1 of 4 sections have evidence", html)
        self.assertIn("1 due", html)

    def test_path_is_not_a_table(self) -> None:
        html = self.render()
        self.assertNotIn("<table", html)

    # -- sources ----------------------------------------------------------------------------
    def test_sources_are_collapsed_by_default_and_read_nothing(self) -> None:
        html = self.render()
        self.assertIn('data-cb-sources-drawer="closed"', html)
        self.assertNotIn("Shop manual §4 — ignition", html)
        self.assertIn('aria-expanded="false"', html)

    def test_open_sources_name_the_section_and_its_real_rows(self) -> None:
        html = self.render(sourcesOpen=True, sourcesStatus="ready", sources=SOURCES)
        self.assertIn('data-cb-sources-drawer="open"', html)
        self.assertIn("Sources for “Diagnose a no-start”", html)
        self.assertIn("Shop manual §4 — ignition", html)
        self.assertIn("supported", html)
        self.assertIn("stale", html)
        self.assertIn('aria-expanded="true"', html)

    def test_a_failed_source_read_is_shown_with_no_source_rows(self) -> None:
        html = self.render(
            sourcesOpen=True,
            sourcesStatus="error",
            sourcesError={"code": "NOT_IMPLEMENTED", "message": "no handler"},
            sources=None,
        )
        self.assertIn("The sources were not read.", html)
        self.assertIn("Try again", html)
        self.assertNotIn("data-cb-desk-source", html)

    def test_empty_sources_say_the_backend_recorded_none(self) -> None:
        html = self.render(sourcesOpen=True, sourcesStatus="ready", sources=[])
        self.assertIn("No sources are recorded for this section yet.", html)

    # -- course selection -------------------------------------------------------------------
    def test_model_continues_the_due_review_when_the_next_step_says_so(self) -> None:
        desk = self.model()["desk"]
        self.assertEqual(desk["current"]["objective_id"], "obj_0000000000000002")
        self.assertEqual(desk["primaryKind"], "resolve_review_due")
        self.assertEqual(desk["primaryLabel"], "Start the review")

    def test_model_labels_a_resume_from_the_backends_next_step(self) -> None:
        row = library_row(
            next_step={"kind": "resume_lesson", "label": "Continue Diagnosing a no-start"},
            evidence_summary={
                "independent": 1,
                "review_due": 0,
                "total_objectives": 4,
                "current_objective_id": "obj_0000000000000002",
            },
        )
        desk = self.model(library=library(row))["desk"]
        self.assertEqual(desk["current"]["objective_id"], "obj_0000000000000002")
        self.assertEqual(desk["primaryKind"], "resume_lesson")
        self.assertEqual(desk["primaryLabel"], "Resume the lesson")

    def test_model_falls_back_to_the_rows_own_current_objective(self) -> None:
        row = library_row(next_step={"kind": "start_lesson", "label": "Start Replace a fouled plug"})
        desk = self.model(library=library(row))["desk"]
        self.assertEqual(desk["current"]["objective_id"], "obj_0000000000000003")
        self.assertEqual(desk["primaryLabel"], "Start a fresh run")

    def test_mainline_objective_never_matches_on_title(self) -> None:
        row = library_row(
            next_step={"kind": "start_lesson", "label": "Start"},
            evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 4, "current_objective_id": None},
        )
        mainline = self.model(library=library(row), outline=OUTLINE)["mainline"]
        self.assertEqual(mainline["objective_id"], "obj_0000000000000002")
        self.assertFalse(mainline["independent"])

    def test_mainline_objective_prefers_the_section_open_over_the_course_write(self) -> None:
        desk = self.model()["desk"]
        self.assertEqual(desk["touchedSource"], "section")
        self.assertEqual(desk["lastTouched"], "2026-11-06T17:30:00.000000+00:00")

    def test_last_touched_falls_back_to_the_course_write_and_says_which(self) -> None:
        outline = json.loads(json.dumps(OUTLINE))
        for objective in outline["objectives"]:
            objective["last_opened_at"] = None
        desk = self.model(outline=outline)["desk"]
        self.assertEqual(desk["touchedSource"], "course")
        self.assertEqual(desk["lastTouched"], "2026-11-06T18:00:00.000000+00:00")

    # -- the other states -------------------------------------------------------------------
    def test_no_courses_renders_first_run_not_a_sample_course(self) -> None:
        html = self.render(library=library(), outline=None)
        self.assertIn('data-cb-desk="empty"', html)
        self.assertNotIn("data-cb-continue", html)
        self.assertNotIn("Small-engine maintenance", html)

    def test_loading_renders_a_loader_and_no_course(self) -> None:
        html = self.render(library=None, libraryStatus="loading")
        self.assertIn('data-cb-desk="loading"', html)
        self.assertIn("Reading your courses", html)
        self.assertNotIn("data-cb-continue", html)

    def test_a_failed_read_keeps_its_code_and_retry(self) -> None:
        html = self.render(
            library=None,
            libraryStatus="error",
            libraryError={"code": "HOST_UNAVAILABLE", "message": "the backend did not answer"},
        )
        self.assertIn('data-cb-desk="error"', html)
        self.assertIn("HOST_UNAVAILABLE", html)
        self.assertIn("Try again", html)
        self.assertNotIn("data-cb-desk=\"empty\"", html)

    def test_a_stale_read_says_it_is_reconnecting(self) -> None:
        html = self.render(stale=True)
        self.assertIn("Reconnecting", html)
        self.assertIn("Retry now", html)

    def test_all_courses_is_secondary_and_lists_the_other_rows(self) -> None:
        second = library_row(
            enrollment_id="enr_ffffffffffffffff",
            course_id="crs_ffffffffffffffff",
            title="Japanese greetings",
            next_step={"kind": "start_lesson", "label": "Start あいさつ"},
        )
        html = self.render(library=library(library_row(), second))
        self.assertIn("All courses · 2", html)
        self.assertIn("Japanese greetings", html)
        self.assertIn("Start あいさつ", html)
        self.assertIn("Search and manage courses", html)

    def test_a_single_course_says_so_rather_than_padding_the_list(self) -> None:
        html = self.render()
        self.assertIn("This is the only course on this profile.", html)

    def test_the_secondary_list_stays_compact_and_counts_the_rest(self) -> None:
        rows = [library_row()]
        for index in range(5):
            rows.append(
                library_row(
                    enrollment_id=f"enr_{index:016d}",
                    course_id=f"crs_{index:016d}",
                    title=f"Other course {index}",
                )
            )
        html = self.render(library=library(*rows))
        self.assertIn("All courses · 6", html)
        self.assertEqual(html.count("data-cb-all-courses-row"), 3)
        self.assertIn("+2 more courses on this profile", html)

    def test_the_wide_desk_is_a_two_column_reading_surface(self) -> None:
        html = self.render()
        self.assertIn("minmax(0, 1.2fr)", html)
        self.assertIn("minmax(19rem, 0.8fr)", html)
        # H-94 V2-5: the desk carries one facts line, not a three-cell stat strip.
        self.assertEqual(html.count('data-cb-desk-facts='), 1, html)
        self.assertNotIn('data-cb-desk-stats', html)
        self.assertNotIn('data-cb-desk-stat=', html)
        self.assertIn('data-cb-course-stamp', html)
        # The next move and the path come before the secondary course shelf in reading order.
        self.assertLess(html.index('data-cb-continue'), html.index('data-cb-all-courses'))

    def test_resume_without_a_binding_opens_the_section_instead_of_a_blank_chat(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("reason: 'no-binding'", source)
        self.assertIn("else if (outcome.reason === 'no-binding') openSection(target)", source)
        self.assertNotIn("if (mode === 'resume') {\n      armPendingBind", source)

    # -- the module's shape -----------------------------------------------------------------
    def test_path_titles_wrap_without_colliding_with_the_state_label(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        path = source.split("function PathPreview(", 1)[1].split("function SourcesDrawer(", 1)[0]
        self.assertIn("whiteSpace: 'normal'", path)
        self.assertIn("flex: '1 1 8rem'", path)

    def test_the_field_desk_return_is_on_the_courses_list_not_the_library(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        courses = source.split("function CoursesView(", 1)[1].split("\nfunction sourceLabel(", 1)[0]
        library = source.split("function LibraryView(", 1)[1].split("\nfunction planTimingCopy(", 1)[0]
        self.assertIn("Back to the Field Desk", courses)
        self.assertNotIn("Back to the Field Desk", library)
        self.assertNotIn("onShowDesk", library)

    def test_the_desk_arms_the_exact_run_before_opening_a_chat(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        desk = source.split("// ══ M2 — the Field Desk home", 1)[1].split("function CoursesView(", 1)[0]
        self.assertNotIn("MessageTextContent", desk)
        self.assertNotIn("Composer", desk)
        # The desk arms the run first, then delegates the new-chat seam to the named helper. It
        # still never calls host.newChat inline, so the Field Desk itself has no second chat.
        self.assertIn("openArmedLessonChat(", desk)
        self.assertNotIn("host.newChat(", desk)

    def test_the_desk_paints_only_from_the_token_layer(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        desk = source.split("// ══ M2 — the Field Desk home", 1)[1].split("function CoursesView(", 1)[0]
        self.assertNotRegex(desk, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotIn("gradient", desk)
        self.assertNotIn("boxShadow", desk)


if __name__ == "__main__":
    unittest.main()
