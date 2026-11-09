"""H-174: the empty textbook names the lessons job, not the learner's chat.

When a course is approved but its lesson pages are not written, the section surface used to offer
`Open the textbook` / `Start a fresh run` as the primary and then print "Coursebook does not write
it for you." The harness does write lesson pages (``run_lesson_job`` -> ``_enforce_lesson_document``,
served by ``lesson.page``), so the old copy told the learner the product does not do the one thing it
was built to do, and the primary pointed at a page that did not exist.

These tests pin the replacement:

* ``lessonReadiness`` resolves one state from the page, the plan and the lessons job;
* ``lessonHeroPlan`` gives the hero at most one primary, and only when the page is readable;
* the rendered section names the plan or the lessons job as the owner of the missing page, offers
  one next action, and never renders the false sentence.
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

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { lessonReadiness, lessonHeroPlan, SectionPage } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const out = { states: {}, html: {} }
for (const one of payload.cases) {
  const readiness = lessonReadiness({
    outline: one.outline,
    page: one.page,
    jobs: one.jobs,
    pageStatus: one.pageStatus,
    planStatus: one.planStatus
  })
  out.states[one.name] = {
    state: readiness.state,
    headline: readiness.headline,
    detail: readiness.detail,
    technical: readiness.technical,
    action: readiness.action,
    secondary: readiness.secondary,
    jobState: readiness.jobState,
    blockCount: readiness.blockCount,
    heroClosed: lessonHeroPlan(readiness, { overview: false, sectionOpen: false }),
    heroOpen: lessonHeroPlan(readiness, { overview: false, sectionOpen: true }),
    heroOverview: lessonHeroPlan(readiness, { overview: true, sectionOpen: false })
  }
  if (one.render) {
    out.html[one.name] = renderToStaticMarkup(
      React.createElement(SectionPage, {
        row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default', title: 'Order at a counter' },
        objectiveId: 'obj_0123456789abcdef',
        page: one.page,
        pageStatus: one.pageStatus,
        pageError: null,
        onRetryPage: () => {},
        implemented: new Set(['check.open', 'notebook.save']),
        onBack: () => {},
        onChanged: () => {},
        review: null,
        outline: one.outline,
        planStatus: one.planStatus,
        jobs: one.jobs,
        onOpenPlan: () => {},
        onRetryLessonsJob: () => {},
        embedded: false
      })
    )
  }
}
process.stdout.write(JSON.stringify(out))
"""


def outline(*, plan_state: str | None, objectives: int = 1) -> dict:
    """The `course.outline` projection this surface reads: a plan and its objectives."""
    return {
        "plan": None if plan_state is None else {
            "plan_id": "pln_0123456789abcdef",
            "state": plan_state,
            "version": 1,
            "units": [],
        },
        "objectives": [
            {
                "objective_id": "obj_0123456789abcdef",
                "title": "Order at a counter",
                "state": "not_started",
                "ordinal": 1,
            }
            for _ in range(objectives)
        ],
    }


def page_document(*, blocks: list[dict] | None = None) -> dict:
    return {
        "revision": 4,
        "section": {
            "objective_id": "obj_0123456789abcdef",
            "title": "Order at a counter",
            "state": "not_started",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        "runtime": {"lesson_run_id": None, "binding_id": None, "binding_status": "detached",
                    "session_state": "stored_only"},
        "segments": [],
        "attempts": [],
        "notebook_entries": [],
        "sources": [],
        "document": {
            "schema_version": 1,
            "document_id": "doc_0123456789abcdef0123",
            "content_hash": "sha256:" + "a" * 64,
            "section_title": "Order at a counter",
            "objective_id": "obj_0123456789abcdef",
            "state": "textbook_only",
            "view_note": None,
            "views": {"textbook": True, "guided": False, "field_quest": False, "field_notes": False},
            "blocks": blocks or [],
            "check_id": None,
            "source_ids": [],
        },
    }


READABLE_BLOCKS = [
    {
        "id": "blk_orient0001",
        "role": "orient",
        "headline": "Start here",
        "short": "Say the greeting before you order.",
        "deep": "Say the greeting before you order, then ask for one item.",
        "check_id": None,
        "media": [],
        "source_ids": [],
    },
    {
        "id": "blk_practice01",
        "role": "practice",
        "headline": "Try it",
        "short": "Order one item out loud.",
        "deep": "Order one item out loud, then repeat the answer.",
        "check_id": None,
        "media": [],
        "source_ids": [],
    },
]


def lessons_job(*, state: str, error: dict | None = None, lessons: int = 0) -> dict:
    return {
        "job_id": "job_0123456789abcdef",
        "kind": "plan",
        "state": state,
        "brief": {
            "stage": "lessons",
            "plan_id": "pln_0123456789abcdef",
            "enrollment_id": "enr_0123456789abcdef",
        },
        "checkpoint": {"lessons": lessons},
        "error": error,
        "updated_at": "2026-11-08T00:00:00Z",
    }


def case(name: str, *, plan_state: str | None, page: dict | None, jobs: list[dict] | None,
         plan_status: str = "ready", page_status: str = "ready", render: bool = True) -> dict:
    return {
        "name": name,
        "outline": outline(plan_state=plan_state) if plan_state != "__absent__" else None,
        "page": page,
        "jobs": {"jobs": jobs or []},
        "planStatus": plan_status,
        "pageStatus": page_status,
        "render": render,
    }


CASES = [
    # The four rendered states the card names.
    case("absent", plan_state="approved", page=None, jobs=[]),
    case("running", plan_state="approved", page=None,
         jobs=[lessons_job(state="running")]),
    case("failed", plan_state="approved", page=None,
         jobs=[lessons_job(state="failed", error={"code": "JOB_FAILED", "message": "the model stopped"})]),
    case("present", plan_state="approved", page=page_document(blocks=READABLE_BLOCKS), jobs=[]),
    # The two states that make the job's ownership explicit before it starts.
    case("unapproved", plan_state="draft", page=None, jobs=[]),
    case("not_started", plan_state="approved", page=None, jobs=[]),
    case("no_plan", plan_state=None, page=None, jobs=[]),
    case("incomplete", plan_state="approved", page=page_document(blocks=[]),
         jobs=[lessons_job(state="completed", lessons=0)]),
    # A read that has not settled yet must not claim the plan's state.
    case("reading", plan_state="approved", page=None, jobs=[], plan_status="loading"),
]


class H174ReadinessModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h174-")
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
        cls.model = cls.run_cases(CASES)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def run_cases(cls, cases: list[dict]) -> dict:
        case_file = cls.root / "case.json"
        case_file.write_text(json.dumps({"cases": cases}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(case_file)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-2000:])
        return json.loads(result.stdout)

    # -- the model ---------------------------------------------------------------------------
    def test_the_four_states_the_card_names(self) -> None:
        states = {name: value["state"] for name, value in self.model["states"].items()}
        self.assertEqual(states["absent"], "not_started")
        self.assertEqual(states["running"], "running")
        self.assertEqual(states["failed"], "failed")
        self.assertEqual(states["present"], "readable")

    def test_the_plan_and_document_states_are_distinct(self) -> None:
        states = {name: value["state"] for name, value in self.model["states"].items()}
        self.assertEqual(states["unapproved"], "unapproved")
        self.assertEqual(states["no_plan"], "unapproved")
        self.assertEqual(states["incomplete"], "incomplete")
        self.assertEqual(states["reading"], "reading")

    def test_every_missing_page_names_the_plan_that_owns_it(self) -> None:
        for name in ("absent", "running", "failed", "incomplete", "unapproved", "not_started", "no_plan"):
            with self.subTest(case=name):
                detail = self.model["states"][name]["detail"] or ""
                self.assertRegex(
                    detail,
                    r"(approved plan|Plan|Coursebook)",
                    f"{name} must name the plan that owns the page, not the chat",
                )
                for banned in (
                    "lesson chat",
                    "lesson turn",
                    "Send the first message",
                    "does not write",
                    # H-183: backend machinery is not learner copy.
                    "lessons job",
                    "job",
                    "queued",
                    "revision",
                ):
                    self.assertNotIn(banned, detail.lower(), f"{name} still says {banned!r}: {detail}")

    def test_a_failed_page_keeps_its_typed_error_behind_technical_detail(self) -> None:
        failed = self.model["states"]["failed"]
        self.assertNotIn("JOB_FAILED", failed["detail"])
        self.assertEqual(failed["technical"], "JOB_FAILED: the model stopped")
        self.assertEqual(failed["action"]["label"], "Write this page again")

    def test_a_running_page_offers_check_again_and_the_plan_not_a_start(self) -> None:
        running = self.model["states"]["running"]
        self.assertEqual(running["action"], {"kind": "check", "label": "Check again"})
        self.assertEqual(running["secondary"], {"kind": "plan", "label": "View the plan"})
        self.assertEqual(running["jobState"], "running")
        self.assertIn("being written", running["headline"])

    def test_an_unapproved_plan_points_at_the_plan(self) -> None:
        unapproved = self.model["states"]["unapproved"]
        self.assertEqual(unapproved["action"], {"kind": "plan", "label": "Open the plan"})
        self.assertIn("not approved", unapproved["headline"])

    def test_a_plan_that_was_never_written_says_so(self) -> None:
        self.assertIn("has not been written", self.model["states"]["no_plan"]["headline"])

    # -- the hero ----------------------------------------------------------------------------
    def assert_at_most_one_primary(self, hero: list[dict], case: str) -> None:
        primaries = [action for action in hero if action["variant"] == "primary"]
        self.assertLessEqual(len(primaries), 1, f"{case}: {hero}")
        for primary in primaries:
            self.assertEqual(primary["id"], "start", f"{case}: only the lesson run may be primary")

    def test_the_hero_has_at_most_one_primary_in_each_state(self) -> None:
        for name, value in self.model["states"].items():
            for placement in ("heroClosed", "heroOpen", "heroOverview"):
                with self.subTest(case=name, placement=placement):
                    self.assert_at_most_one_primary(value[placement], f"{name}/{placement}")

    def test_the_hero_only_offers_a_primary_when_the_page_is_readable(self) -> None:
        for name, value in self.model["states"].items():
            readable = value["state"] == "readable"
            primaries = [a for a in value["heroClosed"] if a["variant"] == "primary"]
            self.assertEqual(bool(primaries), readable, f"{name}: primary presence must follow the page")
            labels = [a["label"] for a in value["heroClosed"]]
            if readable:
                self.assertEqual(labels[0], "Start the lesson")
                self.assertIn("Open the textbook", labels)
            else:
                self.assertEqual(value["heroClosed"], [], f"{name}: nothing to point at as a primary")

    def test_the_hero_never_offers_open_the_textbook_without_a_page(self) -> None:
        for name, value in self.model["states"].items():
            if value["state"] == "readable":
                continue
            labels = [a["label"] for a in value["heroClosed"] + value["heroOpen"]]
            self.assertNotIn("Open the textbook", labels, name)
            self.assertNotIn("Start the lesson", labels, name)

    # -- rendered surfaces -------------------------------------------------------------------
    def html(self, name: str) -> str:
        return self.model["html"][name]

    def test_the_absent_page_renders_the_plan_as_the_owner(self) -> None:
        html = self.html("absent")
        self.assertIn('data-cb-lesson-readiness="not_started"', html)
        self.assertIn("This lesson page is not written yet", html)
        self.assertIn("View the plan", html)
        self.assertNotIn("Start a fresh run", html)
        self.assertNotIn("Open the textbook", html)
        self.assertNotIn("Continue in the lesson chat", html)
        self.assertNotIn("lessons job", html)

    def test_a_running_page_renders_a_status_line_not_a_primary(self) -> None:
        html = self.html("running")
        self.assertIn('data-cb-lesson-readiness="running"', html)
        self.assertIn("This lesson page is being written", html)
        self.assertIn("Check again", html)
        self.assertIn("View the plan", html)
        self.assertNotIn('data-cb-action="primary"', html)
        self.assertNotIn("Start a fresh run", html)

    def test_a_failed_page_renders_a_plain_sentence_and_the_error_behind_detail(self) -> None:
        html = self.html("failed")
        self.assertIn('data-cb-lesson-readiness="failed"', html)
        self.assertIn("This lesson page could not be written", html)
        self.assertIn("Technical detail", html)
        self.assertIn("JOB_FAILED: the model stopped", html)
        self.assertIn("Write this page again", html)
        self.assertNotIn('data-cb-action="primary"', html)
        for chat in ("Send the first message", "lesson turn", "does not write"):
            self.assertNotIn(chat, html)
        # The typed code is inside the disclosure, never in the sentence the learner reads first.
        head = html.split("Technical detail")[0]
        self.assertNotIn("JOB_FAILED", head)

    def test_a_readable_page_renders_the_player_and_its_one_primary(self) -> None:
        html = self.html("present")
        self.assertNotIn("data-cb-lesson-readiness", html)
        self.assertEqual(html.count('data-cb-action="primary"'), 1, html[:4000])
        self.assertIn("Start here", html)

    def test_an_incomplete_page_is_named_not_blamed_on_the_learner(self) -> None:
        html = self.html("incomplete")
        self.assertIn("This lesson page is incomplete", html)
        self.assertNotIn("Coursebook does not write it for you", html)

    def test_no_rendered_state_ships_the_false_sentence(self) -> None:
        for name, html in self.model["html"].items():
            with self.subTest(case=name):
                self.assertNotIn("Coursebook does not write it for you", html)
                self.assertNotIn("Teaching content appears here after a lesson turn", html)

    def test_an_unapproved_plan_renders_one_secondary_plan_action(self) -> None:
        html = self.html("unapproved")
        self.assertIn('data-cb-lesson-readiness="unapproved"', html)
        self.assertIn("The plan is not approved yet", html)
        self.assertEqual(html.count("data-cb-readiness-action"), 1, html[:4000])
        self.assertNotIn('data-cb-action="primary"', html)


class H174SourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")
        cls.shipped = "\n".join(
            line for line in cls.source.splitlines()
            if not line.lstrip().startswith(("*", "//", "/*"))
        )

    def test_the_false_sentence_is_gone_from_the_shipped_module(self) -> None:
        self.assertNotIn("Coursebook does not write it for you", self.shipped)
        self.assertNotIn("This section has no teaching content yet", self.shipped)

    def test_the_empty_state_speaks_in_the_learner_outcome(self) -> None:
        for sentence in (
            "This lesson page is not written yet",
            "This lesson page is being written",
            "This lesson page could not be written",
            "This lesson page is incomplete",
            "The plan is not approved yet",
        ):
            self.assertIn(sentence, self.shipped, sentence)
        # H-183: the module may name the harness internally, but no shipped learner sentence does.
        self.assertNotIn("The lessons job has not run yet", self.shipped)
        self.assertNotIn("The lessons job is writing lesson pages", self.shipped)
        self.assertNotIn("The lessons job stopped", self.shipped)

    def test_the_section_start_action_is_gated_on_a_readable_page(self) -> None:
        # The chat run is the section's primary only after the approved page exists (H-174).
        self.assertIn("pageReadable\n          ? jsxs('div', {", self.shipped)
        self.assertIn("!bindingActive && pageReadable", self.shipped)

    def test_the_hero_primary_is_gated_on_the_readiness_model(self) -> None:
        self.assertIn("const heroPlan = lessonHeroPlan(heroReadiness, {", self.shipped)
        self.assertIn("if (overview || !readable) return []", self.shipped)

    def test_the_readiness_model_is_exported_for_this_test(self) -> None:
        self.assertIn("lessonReadiness,", self.shipped)
        self.assertIn("lessonHeroPlan,", self.shipped)


if __name__ == "__main__":
    unittest.main()
