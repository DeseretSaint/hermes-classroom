"""H-27: the Desktop syllabus payloads against the real H-26a handlers.

The sibling `test_desktop_syllabus_ui.py` proves the shipped components and payload builders with a
recording transport. This file closes the seam: every payload it sends is produced by the shipped
Desktop module (real JS, real React module under Node), dispatched through the real
`coursebook.api.dispatch` path on a real migrated SQLite database, and every view it asserts on is
produced by the shipped adapter from the backend's own response.

No provider is involved. The one plan job runs on the repository's scripted offline provider
(`FakeLLM`) and the plan fixture used to satisfy it is labelled where it appears.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import api, db, domain, executor

from tests.kernel_support import request
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.test_syllabus_import import CS_TITLES, FIXTURES, SyllabusCase, cs_plan, validation_from_fixture
from tests.test_generation import FakeLLM, FakeSearch

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import {
  syllabusAlignmentView,
  syllabusAlignPayload,
  syllabusCoursePayload,
  syllabusIntakePayload,
  syllabusParseView,
  syllabusPlanBrief,
  syllabusReviewPayload
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

let output
if (payload.kind === 'intake') output = syllabusIntakePayload(payload.input)
else if (payload.kind === 'parse-view') output = syllabusParseView(payload.view)
else if (payload.kind === 'course-payload')
  output = syllabusCoursePayload({ parsed: payload.parsed, scope: payload.scope, goal: payload.goal, learnerLabel: payload.learnerLabel })
else if (payload.kind === 'plan-brief')
  output = syllabusPlanBrief(payload.input)
else if (payload.kind === 'align-payload') output = syllabusAlignPayload(payload.input)
else if (payload.kind === 'alignment-view') output = syllabusAlignmentView(payload.alignment)
else if (payload.kind === 'review-payload') output = syllabusReviewPayload(payload.input)
else throw new Error(`unknown case ${payload.kind}`)
process.stdout.write(JSON.stringify(output))
"""


class DesktopPayloadHarness:
    """Runs the shipped plugin module under Node and returns its JSON output."""

    tmp = None
    root = None

    @classmethod
    def build(cls) -> bool:
        if shutil.which("node") is None:
            return False
        modules = _desktop_node_modules()
        if modules is None:
            return False
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-syllabus-live-")
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
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        return True

    @classmethod
    def cleanup(cls) -> None:
        if cls.tmp is not None:
            cls.tmp.cleanup()

    def js(self, case: dict) -> dict:
        root = self.root
        if root is None:
            raise AssertionError("the desktop payload harness was not built")
        path = root / "case.json"
        path.write_text(json.dumps(case), encoding="utf-8")
        result = subprocess.run(
            ["node", str(root / "harness.mjs"), str(path)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-3000:])
        return json.loads(result.stdout)


class DesktopLiveSequenceTest(SyllabusCase):
    """Intake payload → parse → adapter view → companion course → plan → align → review → approve."""

    @classmethod
    def setUpClass(cls) -> None:
        if not DesktopPayloadHarness.build():
            raise unittest.SkipTest("node and the desktop node_modules are required for the live seam")

    @classmethod
    def tearDownClass(cls) -> None:
        DesktopPayloadHarness.cleanup()

    def js(self, case: dict) -> dict:
        return DesktopPayloadHarness().js(case)

    def test_the_shipped_payloads_drive_a_real_companion_course_to_an_approved_plan(self) -> None:
        text = (FIXTURES / "cs340-databases.md").read_text(encoding="utf-8")

        # ── intake: the builder ships a real payload, the backend accepts it ──
        built = self.js({"kind": "intake", "input": {"fileName": "cs340-databases.md", "text": text}})
        self.assertTrue(built["ok"], built)
        payload = built["payload"]
        self.assertEqual(payload["file_name"], "cs340-databases.md")
        self.assertEqual(payload["mime_hint"], "text/markdown")
        self.assertEqual(base64.b64decode(payload["content_base64"]).decode("utf-8"), text)
        created = self.ok(
            "syllabus.intake.create", payload, idempotency_key="cb-syllabus-intake-live-1"
        )["result"]
        self.assertEqual(created["extraction"]["source_kind"], "markdown")
        syllabus_id, revision = created["syllabus_id"], created["revision"]

        parse_job = self.ok(
            "syllabus.parse",
            {"syllabus_id": syllabus_id, "revision": revision, "egress_acknowledged": True},
            idempotency_key=f"cb-syllabus-parse-{syllabus_id}-{revision}-{created['content_sha256']}",
        )["result"]
        views = executor.pump_once()
        self.assertEqual(next(v["state"] for v in views if v["job_id"] == parse_job["job_id"]), "completed")

        # ── the shipped adapter turns the backend's flat item list into the review document ──
        fetched = self.ok(
            "syllabus.get", {"syllabus_id": syllabus_id, "revision": revision, "include_blocks": True}
        )["result"]
        self.assertGreater(len(fetched["items"]), 0)
        self.assertIsNotNone(fetched["parse_run"])
        parsed = self.js({"kind": "parse-view", "view": fetched})
        self.assertEqual(parsed["parse_state"], "parsed")
        document = parsed["document"]
        self.assertEqual(document["course"]["code"]["value"], "CS 340")
        self.assertEqual(document["course"]["title"]["state"], "extracted")
        self.assertGreaterEqual(len(document["weeks"]), 4)
        for week in document["weeks"]:
            self.assertEqual(week["ordinal"]["state"], "extracted")
            self.assertIn("label", week)
        # The H-26a item projection stores an assessment's title and, only when the date is
        # missing, a separate "(due)" row: a stated date and a stated weight are not projected.
        # The adapter therefore reports both as unknown. It never recovers them by re-parsing the
        # block text — that would be a second parser in the UI. The gap is named in the H-27 card.
        dues = [row["due"]["state"] for row in document["assessments"]]
        self.assertEqual(set(dues), {"unknown"})
        self.assertTrue(all(row["weight"]["state"] == "unknown" for row in document["assessments"]))
        # The file's own dates are still readable through the anchored block text.
        self.assertTrue(
            any("2026-09-01" in str(block.get("text") or "") for block in parsed["blocks"]),
            "the backend's blocks must still carry the line the anchor quotes",
        )
        # Every extracted assessment has a page/line anchor from the file.
        self.assertTrue(
            all(row["anchors"] for row in document["assessments"] if row["title"]["state"] == "extracted")
        )
        self.assertTrue(parsed["blocks"])

        # ── course.create with the companion payload ──
        course_payload = self.js(
            {"kind": "course-payload", "parsed": parsed, "scope": "short", "goal": "", "learnerLabel": "CS 340"}
        )
        self.assertEqual(course_payload["recipe"], "companion")
        self.assertNotIn("pack_id", course_payload)
        self.assertEqual(course_payload["syllabus_id"], syllabus_id)
        self.assertEqual(course_payload["syllabus_revision"], revision)
        course = self.ok("course.create", course_payload, idempotency_key="cb-companion-live-1")["result"]
        enrollment = self.ok(
            "enrollment.create",
            {"course_id": course["course_id"], "learner_label": "CS 340"},
            idempotency_key="cb-companion-live-1-enroll",
        )["result"]["enrollment_id"]

        # ── the plan brief the UI sends, with its syllabus fields ──
        brief = self.js(
            {
                "kind": "plan-brief",
                "input": {
                    "courseId": course["course_id"],
                    "enrollmentId": enrollment,
                    "goal": course_payload["goal"],
                    "scope": "short",
                    "syllabusId": syllabus_id,
                    "syllabusRevision": revision,
                },
            }
        )
        self.assertEqual(brief["recipe"], "companion")
        self.assertEqual(brief["syllabus_revision"], revision)
        plan_job = self.ok(
            "jobs.create", {"kind": "plan", "brief": brief}, idempotency_key="cb-companion-live-1-plan"
        )["result"]
        llm = FakeLLM({"coursebook.plan.generate": cs_plan(CS_TITLES), "coursebook.plan.validate": validation_from_fixture()})
        views = executor.pump_once(llm=llm, search=FakeSearch())
        self.assertEqual(next(v["state"] for v in views if v["job_id"] == plan_job["job_id"]), "completed")
        outline = self.ok("course.outline", {"enrollment_id": enrollment})["result"]
        plan_id = outline["plan"]["plan_id"]
        self.assertEqual(outline["plan"]["state"], "draft")

        # ── align with the shipped payload, then read it back through the shipped view ──
        align_payload = self.js(
            {
                "kind": "align-payload",
                "input": {"syllabusId": syllabus_id, "revision": revision, "courseId": course["course_id"], "planId": plan_id},
            }
        )
        align_job = self.ok(
            "syllabus.align", align_payload, idempotency_key=f"cb-syllabus-align-{syllabus_id}-{revision}-{plan_id}"
        )["result"]
        views = executor.pump_once()
        self.assertEqual(next(v["state"] for v in views if v["job_id"] == align_job["job_id"]), "completed")
        alignment = self.ok(
            "syllabus.alignment.get",
            {"syllabus_id": syllabus_id, "revision": revision, "course_id": course["course_id"]},
        )["result"]
        self.assertGreater(len(alignment["items"]), 0)
        view = self.js({"kind": "alignment-view", "alignment": alignment})
        self.assertFalse(view["approveReady"])
        self.assertTrue(view["rows"])
        for row in view["rows"]:
            # No learner-facing row prints a raw reason code; the copy map covers every state.
            self.assertNotIn("_", row["reason"])
            self.assertTrue(row["stateLabel"][0].isupper(), row["stateLabel"])

        # ── the backend refuses an unreviewed mapping, and the UI's gate predicts it ──
        refused = self.err(
            "plan.approve",
            {"enrollment_id": enrollment, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
            expected_revision=0,
        )
        self.assertEqual(refused["code"], "SYLLABUS_UNREVIEWED")

        # ── decisions through the shipped review payload ──
        decisions = [
            {"item_id": row["itemId"], "action": row["actions"][0]["action"]}
            for row in view["rows"]
            if row["actions"]
        ]
        self.assertTrue(decisions)
        review_payload = self.js(
            {
                "kind": "review-payload",
                "input": {
                    "syllabusId": syllabus_id,
                    "revision": revision,
                    "courseId": course["course_id"],
                    "alignmentRevision": alignment["alignment_revision"],
                    "decisions": decisions + [{"item_id": "not-a-row", "action": "delete_row"}],
                },
            }
        )
        self.assertEqual(len(review_payload["decisions"]), len(decisions))
        reviewed = self.ok(
            "syllabus.alignment.review", review_payload, idempotency_key="cb-syllabus-review-live-1"
        )["result"]
        self.assertEqual(reviewed["reviewed_revision"], revision)

        # ── the plan now approves through the existing fence and the existing hash ──
        approved = self.ok(
            "plan.approve",
            {"enrollment_id": enrollment, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
            expected_revision=0,
        )
        self.assertTrue(approved["ok"])
        self.assertEqual(
            self.ok("course.get", {"course_id": course["course_id"]})["result"]["course"]["active_plan_id"],
            plan_id,
        )
        library = self.ok("library.list", {})["result"]["items"]
        row = next(item for item in library if item["course_id"] == course["course_id"])
        self.assertEqual(row["provenance"]["source"], "authored")
        self.assertIsNone(row["provenance"]["pack_id"])

    def test_a_new_revision_makes_the_mapping_stale_and_the_ui_says_so(self) -> None:
        text = (FIXTURES / "bio150l-general-biology-lab.md").read_text(encoding="utf-8")
        built = self.js({"kind": "intake", "input": {"fileName": "bio150l-general-biology-lab.md", "text": text}})
        created = self.ok("syllabus.intake.create", built["payload"], idempotency_key="cb-rev-live-1")["result"]
        syllabus_id, revision = created["syllabus_id"], created["revision"]
        self.ok(
            "syllabus.parse",
            {"syllabus_id": syllabus_id, "revision": revision, "egress_acknowledged": True},
        )
        executor.pump_once()
        fetched = self.ok(
            "syllabus.get", {"syllabus_id": syllabus_id, "revision": revision, "include_blocks": True}
        )["result"]
        parsed = self.js({"kind": "parse-view", "view": fetched})
        course_payload = self.js({"kind": "course-payload", "parsed": parsed, "scope": "short", "goal": ""})
        course = self.ok("course.create", course_payload, idempotency_key="cb-rev-live-course")["result"]
        enrollment = self.ok(
            "enrollment.create", {"course_id": course["course_id"], "learner_label": "Bio 150L"}
        )["result"]["enrollment_id"]
        brief = self.js(
            {
                "kind": "plan-brief",
                "input": {"courseId": course["course_id"], "enrollmentId": enrollment, "goal": course_payload["goal"], "scope": "short", "syllabusId": syllabus_id, "syllabusRevision": revision},
            }
        )
        self.ok("jobs.create", {"kind": "plan", "brief": brief}, idempotency_key="cb-rev-live-plan")
        executor.pump_once(
            llm=FakeLLM({"coursebook.plan.generate": cs_plan(CS_TITLES), "coursebook.plan.validate": validation_from_fixture()}),
            search=FakeSearch(),
        )
        plan_id = self.ok("course.outline", {"enrollment_id": enrollment})["result"]["plan"]["plan_id"]
        align_payload = self.js(
            {"kind": "align-payload", "input": {"syllabusId": syllabus_id, "revision": revision, "courseId": course["course_id"], "planId": plan_id}}
        )
        self.ok("syllabus.align", align_payload)
        executor.pump_once()
        alignment = self.ok(
            "syllabus.alignment.get",
            {"syllabus_id": syllabus_id, "revision": revision, "course_id": course["course_id"]},
        )["result"]
        decisions = [
            {"item_id": row["item_id"], "action": {"partial": "accept_partial", "unmatched": "accept_unmatched", "conflict": "accept_divergence"}[row["state"]]}
            for row in alignment["items"]
            if row["state"] in ("partial", "unmatched", "conflict")
        ]
        if decisions:
            self.ok(
                "syllabus.alignment.review",
                {
                    "syllabus_id": syllabus_id,
                    "revision": revision,
                    "course_id": course["course_id"],
                    "alignment_revision": alignment["alignment_revision"],
                    "decisions": decisions,
                },
            )

        # The learner uploads the next revision through the same shipped intake payload, with the
        # supersede id the panel passes it.
        revised = text.replace("### Lab 14: Practical exam", "### Lab 13: Practical exam")
        superseding = self.js(
            {
                "kind": "intake",
                "input": {"fileName": "bio150l-general-biology-lab.md", "text": revised, "supersedesSyllabusId": syllabus_id},
            }
        )
        self.assertEqual(superseding["payload"]["supersedes_syllabus_id"], syllabus_id)
        next_revision = self.ok(
            "syllabus.intake.create", superseding["payload"], idempotency_key="cb-rev-live-2"
        )["result"]
        self.assertEqual(next_revision["revision"], revision + 1)

        stale_get = self.ok(
            "syllabus.alignment.get",
            {"syllabus_id": syllabus_id, "revision": revision, "course_id": course["course_id"]},
        )["result"]
        self.assertTrue(stale_get["stale"])
        view = self.js({"kind": "alignment-view", "alignment": stale_get})
        self.assertTrue(view["stale"])
        self.assertFalse(view["approveReady"])
        # The approved plan path is refused as stale, and the UI gate reports the same thing.
        self.assertEqual(
            self.err(
                "plan.approve",
                {"enrollment_id": enrollment, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
                expected_revision=0,
            )["code"],
            "SYLLABUS_STALE",
        )

    def test_a_cancelled_parse_job_leaves_no_parsed_document(self) -> None:
        text = (FIXTURES / "cs340-databases.md").read_text(encoding="utf-8")
        built = self.js({"kind": "intake", "input": {"fileName": "cs340-databases.md", "text": text}})
        created = self.ok("syllabus.intake.create", built["payload"], idempotency_key="cb-cancel-live-1")["result"]
        job = self.ok(
            "syllabus.parse",
            {"syllabus_id": created["syllabus_id"], "revision": created["revision"], "egress_acknowledged": True},
        )["result"]
        # The Desktop cancel action sends `jobs.cancel`; it is a real cancel, not a hidden poller.
        self.ok("jobs.cancel", {"job_id": job["job_id"]}, idempotency_key=f"cb-syllabus-parse-cancel-{job['job_id']}")
        executor.pump_once()
        fetched = self.ok(
            "syllabus.get",
            {"syllabus_id": created["syllabus_id"], "revision": created["revision"], "include_blocks": True},
        )["result"]
        self.assertIsNone(fetched["parse_run"])
        view = self.js({"kind": "parse-view", "view": fetched})
        self.assertIsNone(view["parse_state"])


if __name__ == "__main__":
    unittest.main()
