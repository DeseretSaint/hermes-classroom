"""H-183: the learner-visible copy inventory.

The lesson surface used to speak like an evidence console: an empty section said "the lessons job has
not run yet", a failed authoring attempt printed `JOB_FAILED: …` in the sentence a learner reads, and a
build without `lesson.assist` offered a caption about a method that was "not registered". These tests
render the shipped components and scan the text a person actually sees.

The rule is not "never say the word". The rule is:

* the default Home / lesson / section / check / first-run / error sentence never names a job, a queue,
  a tick, a revision, a raw id or a typed error code;
* the typed code is still there for evidence inspection, behind the existing `Technical detail`
  disclosure, which this file strips before it scans.

The check card itself is mounted through the route in other suites; here the check's limitation copy is
pinned in source because the card is not an exported component.
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
import { FirstRun, SectionPage, lessonReadiness } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const out = { firstRun: null, states: {}, firstRunNoTools: null }
out.firstRun = renderToStaticMarkup(
  React.createElement(FirstRun, {
    implemented: new Set(['course.create', 'pack.import', 'syllabus.intake.create']),
    onCreate: () => {},
    onSyllabus: () => {},
    onBrowseLibrary: () => {},
    onRetry: () => {}
  })
)
out.firstRunNoTools = renderToStaticMarkup(
  React.createElement(FirstRun, {
    implemented: new Set(['course.create']),
    onCreate: () => {},
    onBrowseLibrary: () => {},
    onRetry: () => {}
  })
)

for (const one of payload.cases) {
  const readiness = lessonReadiness({
    outline: one.outline,
    page: one.page,
    jobs: one.jobs,
    pageStatus: one.pageStatus,
    planStatus: one.planStatus
  })
  out.states[one.name] = {
    headline: readiness.headline,
    detail: readiness.detail,
    technical: readiness.technical,
    html: renderToStaticMarkup(
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

BANNED = (
    r"lessons job",
    r"\bjobs?\b",
    r"\bqueued\b",
    r"\bqueue\b",
    r"\bnext tick\b",
    r"\brevision\b",
    r"\breconcile\b",
    r"plan-pending",
    r"JOB_FAILED",
    r"not registered",
)

RAW_IDS = re.compile(r"\b(?:job|enr|obj|pln|crs|doc|blk)_[0-9a-f]{6,}\b")
TICKET_LABEL = re.compile(r"\bH-?\d{2,3}\b")

DETAILS = re.compile(r"<details\b.*?</details>", re.S | re.I)
TAGS = re.compile(r"<[^>]+>")


def visible_text(html: str) -> str:
    """The page as a person reads it: no disclosure contents, no markup."""
    without_details = DETAILS.sub(" ", html or "")
    return re.sub(r"\s+", " ", TAGS.sub(" ", without_details)).strip()


def outline(*, plan_state: str | None) -> dict:
    return {
        "plan": None if plan_state is None else {
            "plan_id": "pln_0123456789abcdef",
            "state": plan_state,
            "version": 1,
            "units": [],
        },
        "objectives": [{
            "objective_id": "obj_0123456789abcdef",
            "title": "Order at a counter",
            "state": "not_started",
            "ordinal": 1,
        }],
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
    }
]


def lessons_job(*, state: str, error: dict | None = None) -> dict:
    return {
        "job_id": "job_0123456789abcdef",
        "kind": "plan",
        "state": state,
        "brief": {
            "stage": "lessons",
            "plan_id": "pln_0123456789abcdef",
            "enrollment_id": "enr_0123456789abcdef",
        },
        "checkpoint": {"lessons": 0},
        "error": error,
        "updated_at": "2026-11-08T00:00:00Z",
    }


CASES = [
    {"name": "absent", "outline": outline(plan_state="approved"), "page": None, "jobs": {"jobs": []},
     "planStatus": "ready", "pageStatus": "ready"},
    {"name": "running", "outline": outline(plan_state="approved"), "page": None,
     "jobs": {"jobs": [lessons_job(state="running")]}, "planStatus": "ready", "pageStatus": "ready"},
    {"name": "failed", "outline": outline(plan_state="approved"), "page": None,
     "jobs": {"jobs": [lessons_job(state="failed", error={"code": "JOB_FAILED", "message": "the model stopped"})]},
     "planStatus": "ready", "pageStatus": "ready"},
    {"name": "incomplete", "outline": outline(plan_state="approved"), "page": page_document(blocks=[]),
     "jobs": {"jobs": []}, "planStatus": "ready", "pageStatus": "ready"},
    {"name": "unapproved", "outline": outline(plan_state="draft"), "page": None, "jobs": {"jobs": []},
     "planStatus": "ready", "pageStatus": "ready"},
    {"name": "unreadable", "outline": outline(plan_state="approved"), "page": None, "jobs": {"jobs": []},
     "planStatus": "ready", "pageStatus": "error"},
    {"name": "readable", "outline": outline(plan_state="approved"),
     "page": page_document(blocks=READABLE_BLOCKS), "jobs": {"jobs": []},
     "planStatus": "ready", "pageStatus": "ready"},
]


class CopyInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h183-")
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
        case_file = root / "case.json"
        case_file.write_text(json.dumps({"cases": CASES}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(root / "harness.mjs"), str(case_file)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-2000:])
        cls.out = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def assert_clean(self, text: str, surface: str) -> None:
        for pattern in BANNED:
            self.assertIsNone(
                re.search(pattern, text, re.I),
                f"{surface} shows internal machinery {pattern!r}: {text}",
            )
        self.assertIsNone(RAW_IDS.search(text), f"{surface} shows a raw id: {text}")
        self.assertIsNone(TICKET_LABEL.search(text), f"{surface} shows a ticket label: {text}")

    # -- first run ---------------------------------------------------------------------------
    def test_first_run_plates_are_clean(self) -> None:
        self.assert_clean(visible_text(self.out["firstRun"]), "first run")
        self.assert_clean(visible_text(self.out["firstRunNoTools"]), "first run without tools")

    # -- lesson / section / error states -----------------------------------------------------
    def test_every_readiness_state_is_clean_when_read(self) -> None:
        for name, value in self.out["states"].items():
            with self.subTest(case=name):
                text = visible_text(value["html"])
                self.assert_clean(text, f"lesson section ({name})")
                self.assert_clean(value["headline"] or "", f"lesson headline ({name})")
                self.assert_clean(value["detail"] or "", f"lesson detail ({name})")

    def test_the_failed_state_keeps_its_code_behind_technical_detail(self) -> None:
        failed = self.out["states"]["failed"]
        self.assertEqual(failed["technical"], "JOB_FAILED: the model stopped")
        self.assertIn("Technical detail", failed["html"])
        self.assertIn("JOB_FAILED: the model stopped", failed["html"])
        self.assertNotIn("JOB_FAILED", visible_text(failed["html"]))
        self.assertIn("Write this page again", visible_text(failed["html"]))

    def test_no_state_turns_a_failed_read_into_an_empty_page(self) -> None:
        unreadable = visible_text(self.out["states"]["unreadable"]["html"])
        self.assertIn("could not be read", unreadable)
        self.assertIn("Nothing was lost", unreadable)

    # -- check copy --------------------------------------------------------------------------
    def test_the_check_offers_no_dead_assist_control(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn(
            "No hint and no shown answer are offered on this check. Work it out from the section text.",
            source,
        )
        self.assertNotIn("not registered by this build", source)
        self.assertNotIn("Hint and Show answer", source)
        # The assist controls themselves only exist when the method is implemented.
        self.assertIn("supports('lesson.assist') && !detached", source)

    def test_the_notebook_limitation_is_plain(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("Saving to the notebook is not available in this build.", source)
        self.assertNotIn("notebook.save is not registered", source)


if __name__ == "__main__":
    unittest.main()
