"""H-27: the student syllabus surface — intake, anchors, alignment, companion course.

The plugin is one uncompiled ESM file, so this file imports the shipped functions and runs them
with a recording transport, and renders the shipped components through real React. The syllabus
document used here is a FIXTURE built to the frozen `syllabus.parse.v1` shape in
`docs/STUDENT-MODE.md` §3.2 — it is labelled as a fixture everywhere it appears and is never
presented as a backend response.

What this does NOT prove: that H-26a's handlers exist. `syllabus.intake.create`, `syllabus.get`,
`syllabus.parse`, `syllabus.align`, `syllabus.alignment.get`, `syllabus.alignment.review` and
`syllabus.delete` are not in the backend on this base; the sequence below is the exact call
sequence the UI emits, not a live parse.
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


def _source() -> str:
    return PLUGIN_JS.read_text(encoding="utf-8")


HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  ALIGNMENT_STATE_COPY,
  SYLLABUS_ACCEPT,
  SYLLABUS_COPY,
  SYLLABUS_LIMITS,
  SyllabusAlignmentReview,
  SyllabusIntakeFlow,
  SyllabusParseReview,
  queueSyllabusAlignment,
  startCompanionCourse,
  syllabusAlignmentView,
  syllabusAssessmentRows,
  syllabusCoursePayload,
  syllabusIntakePayload,
  syllabusItemView,
  syllabusParseView,
  syllabusPlanGate,
  syllabusReviewPayload,
  syllabusScopeProposal,
  syllabusStaleNotice
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

/** A recording transport; `fail` names a method that answers with a typed refusal instead. */
function transport({ fail = null, failCode = 'SYLLABUS_STALE' } = {}) {
  const calls = []
  const call = async (method, body, options = {}) => {
    calls.push({ method, payload: body, options })
    if (fail === method) {
      return { ok: false, error: { code: failCode, message: 'the syllabus changed after this plan was made' } }
    }
    if (method === 'course.create') return { ok: true, result: { course_id: 'course_c1', plan_id: 'plan_p1' } }
    if (method === 'enrollment.create') return { ok: true, result: { enrollment_id: 'enr_e1' } }
    if (method === 'jobs.create') return { ok: true, result: { job_id: 'job_j1', state: 'queued' } }
    if (method === 'syllabus.align') return { ok: true, result: { job_id: 'job_a1', state: 'queued', alignment_revision: 3 } }
    throw new Error(`unexpected method ${method}`)
  }
  return { call, calls }
}

const FIXTURE_REVISION = 2
const FIXTURE_SYLLABUS_ID = 'syl_0123456789abcdef'

let output
if (payload.kind === 'intake') {
  output = syllabusIntakePayload(payload.input)
} else if (payload.kind === 'parse') {
  output = {
    unknown: syllabusItemView({ state: 'unknown', value: null }),
    ambiguous: syllabusItemView({ state: 'ambiguous', value: null, candidates: ['10%', '15%'] }),
    extracted: syllabusItemView({ state: 'extracted', value: 'CS 340', anchors: [{ block_id: 'b3', quote: 'CS 340', page: 3 }] }),
    forged: syllabusItemView({ state: 'extracted', value: null }),
    assessments: syllabusAssessmentRows(payload.assessments || [])
  }
} else if (payload.kind === 'scope') {
  output = { proposal: syllabusScopeProposal({ weeks: payload.weeks || [] }) }
} else if (payload.kind === 'alignment') {
  output = syllabusAlignmentView(payload.alignment)
} else if (payload.kind === 'review') {
  output = syllabusReviewPayload(payload.input)
} else if (payload.kind === 'stale') {
  output = syllabusStaleNotice(payload.input)
} else if (payload.kind === 'course') {
  output = {
    payload: syllabusCoursePayload({ parsed: payload.parsed, scope: payload.scope, goal: payload.goal, learnerLabel: payload.learnerLabel }),
    copy: SYLLABUS_COPY,
    states: ALIGNMENT_STATE_COPY,
    accept: SYLLABUS_ACCEPT,
    limits: SYLLABUS_LIMITS
  }
} else if (payload.kind === 'sequence') {
  const t = transport({ fail: payload.fail || null })
  const created = await startCompanionCourse({
    call: t.call,
    key: 'cb-companion-key1',
    parsed: payload.parsed,
    scope: payload.scope || 'short',
    goal: payload.goal === undefined ? 'Keep up with the labs' : payload.goal,
    level: payload.level,
    subjectDomain: payload.subjectDomain,
    locale: payload.locale,
    presentationMode: payload.presentationMode,
    learnerLabel: 'CS 340'
  })
  const aligned = created.ok
    ? await queueSyllabusAlignment({
        call: t.call,
        syllabusId: payload.parsed.syllabus_id,
        revision: payload.parsed.revision,
        courseId: created.courseId,
        planId: created.planId
      })
    : null
  output = { created, aligned, calls: t.calls }
} else if (payload.kind === 'parse-view') {
  output = syllabusParseView(payload.view)
} else if (payload.kind === 'gate') {
  output = syllabusPlanGate(payload.input)
} else if (payload.kind === 'render-parse') {
  output = {
    html: renderToStaticMarkup(
      React.createElement(SyllabusParseReview, {
        parsed: payload.parsed,
        blocks: payload.parsed.blocks || [],
        busy: false,
        onBack: () => {},
        onContinue: () => {},
        onReparse: () => {}
      })
    )
  }
} else if (payload.kind === 'render-alignment') {
  output = {
    html: renderToStaticMarkup(
      React.createElement(SyllabusAlignmentReview, {
        alignment: payload.alignment,
        busy: false,
        onDecision: () => {},
        onApprove: () => {},
        onRealign: () => {}
      })
    )
  }
} else if (payload.kind === 'render-intake') {
  output = {
    html: renderToStaticMarkup(React.createElement(SyllabusIntakeFlow, { onCancel: () => {}, onCreated: () => {} }))
  }
} else {
  throw new Error(`unknown case ${payload.kind}`)
}
process.stdout.write(JSON.stringify(output))
"""

# A fixture document, not a backend response. Unknowns are deliberate: no due date and no weight
# for the final, because a syllabus that does not state them must not produce them.
FIXTURE_PARSE = {
    "syllabus_id": "syl_0123456789abcdef",
    "revision": 2,
    "content_sha256": "b" * 64,
    "parse_state": "parsed",
    "document": {
        "course": {
            "code": {"value": "CS 340", "state": "extracted", "anchors": [{"block_id": "b3", "quote": "CS 340 — Introduction to Databases", "page": 1}], "derivation": "explicit"},
            "title": {"value": "Introduction to Databases", "state": "extracted", "anchors": [{"block_id": "b3", "quote": "CS 340 — Introduction to Databases", "page": 1}], "derivation": "explicit"},
        },
        "institution": {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"},
        "instructor": {"value": "Dr. A. Rivera", "state": "extracted", "anchors": [{"block_id": "b4", "quote": "Instructor: Dr. A. Rivera", "page": 1}], "derivation": "explicit"},
        "meeting_pattern": {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"},
        "term": {
            "label": {"value": "Fall 2026", "state": "extracted", "anchors": [{"block_id": "b4", "quote": "Fall 2026", "page": 1}], "derivation": "explicit"},
            "start_date": {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"},
            "end_date": {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"},
        },
        "learning_outcomes": [
            {"value": "Design a normalized schema for a small application.", "state": "extracted", "anchors": [{"block_id": "b7", "quote": "Design a normalized schema for a small application.", "page": 2}], "derivation": "explicit"}
        ],
        "weeks": [
            {
                "ordinal": 1,
                "label": "Week 1",
                "topic": {"value": "Relational model", "state": "extracted", "anchors": [{"block_id": "b9", "quote": "Week 1 — Relational model", "page": 3}], "derivation": "explicit"},
                "readings": [{"value": "Ch. 1–2", "state": "extracted", "anchors": [{"block_id": "b9", "quote": "Ch. 1–2", "page": 3}], "derivation": "explicit"}],
                "assessments": [],
                "anchors": [{"block_id": "b9", "quote": "Week 1 — Relational model", "page": 3}],
            },
            {
                "ordinal": 2,
                "label": "Week 2",
                "topic": {"value": "SQL basics", "state": "extracted", "anchors": [{"block_id": "b10", "quote": "Week 2 — SQL basics", "page": 3}], "derivation": "explicit"},
                "readings": [],
                "assessments": [],
                "anchors": [{"block_id": "b10", "quote": "Week 2 — SQL basics", "page": 3}],
            },
        ],
        "assessments": [
            {
                "id": "as_1",
                "title": "Midterm",
                "kind": "exam",
                "due": {"value": "2026-10-15", "state": "extracted", "anchors": [{"block_id": "b12", "quote": "Midterm — October 15", "page": 4}], "derivation": "explicit"},
                "weight": {"value": 30, "state": "extracted", "anchors": [{"block_id": "b12", "quote": "30%", "page": 4}], "derivation": "explicit"},
                "weight_unit": "percent",
                "week_ordinal": 7,
                "anchors": [{"block_id": "b12", "quote": "Midterm — October 15 (30%)", "page": 4}],
            },
            {
                "id": "as_2",
                "title": "Final project",
                "kind": "project",
                "due": {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"},
                "weight": {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"},
                "weight_unit": "unknown",
                "week_ordinal": None,
                "anchors": [{"block_id": "b13", "quote": "Final project", "page": 4}],
            },
        ],
        "policies": [{"value": "Late work loses 10% per day.", "state": "extracted", "anchors": [{"block_id": "b14", "quote": "Late work loses 10% per day.", "page": 4}], "derivation": "explicit"}],
        "unknowns": ["institution", "meeting_pattern", "term.start_date", "term.end_date"],
        "coverage": {"pages": 4, "blocks": 14, "extracted_chars": 5120, "items_total": 18, "items_extracted": 15},
    },
    "blocks": [
        {"block_id": "b3", "page": 1, "text": "CS 340 — Introduction to Databases"},
        {"block_id": "b9", "page": 3, "text": "Week 1 — Relational model\nCh. 1–2"},
        {"block_id": "b12", "page": 4, "text": "Midterm — October 15 (30%)"},
    ],
}


def _fixture_alignment() -> dict:
    return {
        "alignment_revision": 3,
        "reviewed_revision": 0,
        "stale": False,
        "counts": {"aligned": 1, "partial": 0, "unmatched": 1, "conflict": 1, "unknown": 0, "stale": 0},
        "items": [
            {
                "item_id": "it_1",
                "kind": "outcome",
                "title": "Design a normalized schema",
                "state": "aligned",
                "value_state": "extracted",
                "target": {"kind": "objective", "target_id": "obj_1", "title": "Normalize a schema"},
                "reason_code": "title_tokens",
                "anchors": [{"block_id": "b7", "quote": "Design a normalized schema for a small application.", "page": 2}],
            },
            {
                "item_id": "it_2",
                "kind": "reading",
                "title": "Ch. 9 replication",
                "state": "unmatched",
                "value_state": "extracted",
                "target": None,
                "reason_code": "no_target",
                "anchors": [{"block_id": "b20", "quote": "Ch. 9 replication", "page": 6}],
            },
            {
                "item_id": "it_3",
                "kind": "assessment",
                "title": "Midterm",
                "state": "conflict",
                "value_state": "extracted",
                "target": {"kind": "unit", "target_id": "unit_2", "title": "Query writing"},
                "reason_code": "week_mismatch",
                "anchors": [{"block_id": "b12", "quote": "Midterm — October 15 (30%)", "page": 4}],
            },
        ],
    }


def _fixture_syllabus_get() -> dict:
    """A `syllabus.get`-shaped response: the flat item list the backend serves (not a document)."""

    def item(kind, title, value, state, anchors, *, week=None, item_id="sit_0", derivation="explicit"):
        return {
            "item_id": item_id,
            "kind": kind,
            "title": title,
            "value": value,
            "state": state,
            "anchors": anchors,
            "derivation": derivation,
            "ordinal": 0,
            "week_ordinal": week,
        }

    return {
        "syllabus": {
            "syllabus_id": "syl_getfixture01",
            "series_id": "sys_getfixture01",
            "revision": 3,
            "supersedes_id": None,
            "content_sha256": "c" * 64,
            "file_name": "cs340-databases.md",
            "mime": "text/markdown",
            "source_kind": "markdown",
            "state": "parsed",
            "created_at": "2026-11-07T00:00:00Z",
            "superseded_at": None,
            "bytes": 1726,
        },
        "blocks": [
            {"block_id": "blk_1", "ordinal": 1, "kind": "section", "label": "CS 340 — Introduction to Databases", "page": None, "line_start": 1, "line_end": 1, "text": "# CS 340 — Introduction to Databases"},
            {"block_id": "blk_2", "ordinal": 2, "kind": "section", "label": "Week 1: Relational model", "page": None, "line_start": 19, "line_end": 21, "text": "### Week 1: Relational model\nReading: Chapter 1\nQuiz 1 due 2026-09-01 (5%)"},
        ],
        "items": [
            item("course_code", None, "CS 340", "extracted", [{"block_id": "blk_1", "quote": "CS 340"}]),
            item("course_title", None, "Introduction to Databases", "extracted", [{"block_id": "blk_1", "quote": "Introduction to Databases"}]),
            item("institution", None, None, "unknown", [], derivation="unknown"),
            item("week", "Week 1: Relational model", 1, "extracted", [{"block_id": "blk_2", "quote": "Week 1"}], week=1),
            item("reading", "Chapter 1", "Chapter 1", "extracted", [{"block_id": "blk_2", "quote": "Chapter 1"}], week=1),
            item("assessment", "Quiz 1", "Quiz 1", "extracted", [{"block_id": "blk_2", "quote": "Quiz 1"}], week=1),
            item("assessment", "Quiz 1 (due)", None, "unknown", [], week=1, derivation="unknown"),
            item("learning_outcome", "Explain relational algebra", None, "unknown", [], derivation="unknown"),
        ],
        "parse_run": {
            "parse_run_id": "spr_getfixture01",
            "schema": "syllabus.parse.v1",
            "state": "parsed",
            "provider": None,
            "model": None,
            "created_at": "2026-11-07T00:00:00Z",
            "validation": {"items_total": 8, "items_checked": 6, "anchor_mismatches": 1, "state": "parsed"},
        },
        "coverage": {"pages": None, "blocks": 2, "extracted_chars": 120, "items_total": 8, "items_extracted": 5},
        "unknowns": ["institution", "reading", "learning_outcome"],
    }


class SyllabusDesktopTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-syllabus-ui-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(_source(), encoding="utf-8")
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

    def run_case(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    # ── intake ──────────────────────────────────────────────────────────────

    def test_a_markdown_file_becomes_base64_with_its_display_name(self) -> None:
        out = self.run_case({"kind": "intake", "input": {"fileName": "syllabus.md", "text": "# CS 340\n\nWeek 1"}})
        self.assertTrue(out["ok"], out)
        payload = out["payload"]
        self.assertEqual(payload["file_name"], "syllabus.md")
        self.assertEqual(payload["mime_hint"], "text/markdown")
        import base64

        self.assertEqual(base64.b64decode(payload["content_base64"]).decode("utf-8"), "# CS 340\n\nWeek 1")

    def test_pasted_text_is_a_first_class_document(self) -> None:
        out = self.run_case({"kind": "intake", "input": {"pastedText": "CS 340 syllabus\nWeek 1"}})
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["payload"]["pasted_text"], "CS 340 syllabus\nWeek 1")
        self.assertNotIn("content_base64", out["payload"])

    def test_both_inputs_at_once_is_refused(self) -> None:
        out = self.run_case({"kind": "intake", "input": {"pastedText": "x", "fileName": "a.md", "text": "x"}})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "VALIDATION_FAILED")

    def test_an_oversized_paste_names_the_measured_size(self) -> None:
        out = self.run_case({"kind": "intake", "input": {"pastedText": "x" * 200001}})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "SYLLABUS_REJECTED")
        self.assertIn("200,000", out["error"]["message"])

    def test_an_unsupported_extension_is_refused_not_offered(self) -> None:
        out = self.run_case({"kind": "intake", "input": {"fileName": "syllabus.docm", "dataUrl": "data:application/octet-stream;base64,UEsDBA=="}})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "SYLLABUS_REJECTED")
        self.assertIn("Word (.docx)", out["error"]["message"])

    def test_a_pdf_data_url_keeps_the_host_label_and_display_name(self) -> None:
        # The host labels a PDF/DOCX read as application/octet-stream; the hint is display-only and
        # the backend decides the format from magic bytes (§2.1), so the UI passes it through.
        out = self.run_case({"kind": "intake", "input": {"fileName": "bio150l.pdf", "dataUrl": "data:application/octet-stream;base64,JVBERi0xLjQK"}})
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["payload"]["mime_hint"], "application/octet-stream")
        self.assertEqual(out["payload"]["file_name"], "bio150l.pdf")

    def test_a_text_file_sent_as_bytes_is_refused(self) -> None:
        out = self.run_case({"kind": "intake", "input": {"fileName": "notes.txt", "dataUrl": "data:text/plain;base64,aGk="}})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "SYLLABUS_REJECTED")

    # ── parse review: unknown is a word, never a guess ──────────────────────

    def test_an_unknown_item_and_a_forged_extracted_item_both_render_unknown(self) -> None:
        out = self.run_case({"kind": "parse"})
        self.assertEqual(out["unknown"]["text"], "Not in your file")
        self.assertTrue(out["unknown"]["unknown"])
        # `extracted` with a null value is not a value: it must not render as empty text.
        self.assertEqual(out["forged"]["text"], "Not in your file")
        self.assertTrue(out["forged"]["unknown"])
        self.assertEqual(out["extracted"]["text"], "CS 340")
        self.assertEqual(out["extracted"]["anchorLabels"], ["p. 3"])

    def test_an_ambiguous_item_lists_its_readings_and_picks_none(self) -> None:
        out = self.run_case({"kind": "parse"})
        self.assertEqual(out["ambiguous"]["text"], "Two readings in your file")
        self.assertEqual(out["ambiguous"]["candidates"], ["10%", "15%"])
        self.assertTrue(out["ambiguous"]["unknown"])

    def test_a_missing_due_date_and_weight_are_stated_as_missing(self) -> None:
        out = self.run_case({"kind": "parse", "assessments": FIXTURE_PARSE["document"]["assessments"]})
        rows = {row["title"]: row for row in out["assessments"]}
        self.assertEqual(rows["Midterm"]["due"], "2026-10-15")
        self.assertEqual(rows["Midterm"]["weight"], "30%")
        self.assertEqual(rows["Final project"]["due"], "Due date not in your file")
        self.assertEqual(rows["Final project"]["weight"], "Weight not in your file")
        self.assertTrue(rows["Final project"]["dueUnknown"])
        self.assertTrue(rows["Final project"]["weightUnknown"])

    def test_scope_proposal_follows_the_week_count_and_proposes_nothing_when_unknown(self) -> None:
        single = self.run_case({"kind": "scope", "weeks": [{}]})
        short = self.run_case({"kind": "scope", "weeks": [{}, {}, {}, {}, {}]})
        full = self.run_case({"kind": "scope", "weeks": [{} for _ in range(12)]})
        none = self.run_case({"kind": "scope", "weeks": []})
        self.assertEqual(single["proposal"]["proposal"], "single")
        self.assertEqual(short["proposal"]["proposal"], "short")
        self.assertEqual(full["proposal"]["proposal"], "full")
        self.assertIsNone(none["proposal"]["proposal"])
        self.assertIn("cannot propose", none["proposal"]["reason"])

    # ── alignment ───────────────────────────────────────────────────────────

    def test_alignment_rows_carry_state_reason_and_anchor(self) -> None:
        out = self.run_case({"kind": "alignment", "alignment": _fixture_alignment()})
        rows = {row["itemId"]: row for row in out["rows"]}
        self.assertEqual(rows["it_1"]["stateLabel"], "Aligned")
        self.assertFalse(rows["it_1"]["blocks"])
        self.assertEqual(rows["it_2"]["stateLabel"], "Not covered")
        self.assertIn("No row in the course plan matched", rows["it_2"]["reason"])
        self.assertEqual(rows["it_3"]["stateLabel"], "Conflicts")
        self.assertTrue(rows["it_3"]["blocks"])
        self.assertEqual(rows["it_3"]["anchorLabels"], ["p. 4"])
        self.assertEqual([action["action"] for action in rows["it_3"]["actions"]], ["accept_divergence", "request_replan"])

    def test_a_conflict_blocks_approval_until_it_is_reviewed(self) -> None:
        out = self.run_case({"kind": "alignment", "alignment": _fixture_alignment()})
        self.assertFalse(out["approveReady"])
        self.assertEqual(len(out["blocking"]), 1)
        self.assertIn("must be resolved", out["approveBlockedReason"])

    def test_a_reviewed_revision_with_no_conflict_is_approvable(self) -> None:
        alignment = _fixture_alignment()
        alignment["items"] = [alignment["items"][0]]
        alignment["reviewed_revision"] = 3
        alignment["counts"] = {"aligned": 1, "partial": 0, "unmatched": 0, "conflict": 0, "unknown": 0, "stale": 0}
        out = self.run_case({"kind": "alignment", "alignment": alignment})
        self.assertTrue(out["approveReady"], out["approveBlockedReason"])
        self.assertEqual(out["blocking"], [])

    def test_a_stale_mapping_is_never_approvable(self) -> None:
        alignment = _fixture_alignment()
        alignment["stale"] = True
        out = self.run_case({"kind": "alignment", "alignment": alignment})
        self.assertTrue(out["stale"])
        self.assertFalse(out["approveReady"])
        self.assertIn("changed", out["approveBlockedReason"])

    def test_an_unknown_valued_item_does_not_block(self) -> None:
        alignment = {
            "alignment_revision": 1,
            "reviewed_revision": 1,
            "items": [{"item_id": "it_x", "title": "Final project", "state": "unknown", "value_state": "unknown", "anchors": []}],
        }
        out = self.run_case({"kind": "alignment", "alignment": alignment})
        self.assertEqual(out["blocking"], [])
        self.assertTrue(out["approveReady"])

    def test_only_contract_actions_reach_the_review_payload(self) -> None:
        out = self.run_case({
            "kind": "review",
            "input": {
                "syllabusId": "syl_1",
                "revision": 2,
                "courseId": "course_1",
                "alignmentRevision": 3,
                "decisions": [
                    {"item_id": "it_3", "action": "accept_divergence"},
                    {"item_id": "it_2", "action": "request_replan"},
                    {"item_id": "it_1", "action": "delete_row"},
                ],
            },
        })
        self.assertEqual(out["syllabus_id"], "syl_1")
        self.assertEqual(out["alignment_revision"], 3)
        self.assertEqual([row["item_id"] for row in out["decisions"]], ["it_3", "it_2"])

    def test_a_new_revision_is_announced_as_stale_and_keeps_the_old_plan(self) -> None:
        out = self.run_case({"kind": "stale", "input": {"revision": 3, "counts": {"conflict": 1, "stale": 1}, "planRevision": 2}})
        text = " ".join(out["lines"])
        self.assertIn("marked stale", text)
        self.assertIn("version 2 of your syllabus", text)
        self.assertEqual(out["pending"], 2)
        self.assertNotIn("regenerat", text.lower())

    # ── the backend's flat item list, read by the shipped adapter ───────────

    def test_the_backend_item_list_becomes_the_review_document(self) -> None:
        out = self.run_case({"kind": "parse-view", "view": _fixture_syllabus_get()})
        document = out["document"]
        self.assertEqual(out["parse_state"], "parsed")
        self.assertEqual(out["syllabus_id"], "syl_getfixture01")
        self.assertEqual(document["course"]["code"]["value"], "CS 340")
        self.assertEqual(document["course"]["title"]["value"], "Introduction to Databases")
        self.assertEqual(document["institution"]["state"], "unknown")
        self.assertEqual(len(document["weeks"]), 1)
        week = document["weeks"][0]
        self.assertEqual(week["ordinal"]["value"], 1)
        self.assertEqual(week["topic"]["value"], "Relational model")
        self.assertEqual(week["readings"][0]["value"], "Chapter 1")
        # The `(due)` companion row folds into its assessment; it is not a second assessment and
        # it never turns an unstated date into one.
        self.assertEqual(len(document["assessments"]), 1)
        self.assertEqual(document["assessments"][0]["title"]["value"], "Quiz 1")
        self.assertEqual(document["assessments"][0]["due"]["state"], "unknown")
        self.assertEqual(document["assessments"][0]["weight"]["state"], "unknown")
        self.assertIn("institution", document["unknowns"])
        self.assertNotIn("course_code", document["unknowns"])
        self.assertTrue(any("could not be tied to a quote" in line for line in out["warnings"]))

    def test_the_adapted_document_renders_through_the_real_parse_review(self) -> None:
        adapted = self.run_case({"kind": "parse-view", "view": _fixture_syllabus_get()})
        rendered = self.run_case({"kind": "render-parse", "parsed": adapted})
        html = rendered["html"]
        self.assertIn("What Coursebook read from your syllabus", html)
        self.assertIn("CS 340", html)
        self.assertIn("Relational model", html)
        self.assertIn("Week 1", html)
        self.assertIn("Not in your file", html)
        self.assertIn("Not official course material", html)
        self.assertNotIn("syllabus_item", html)
        self.assertNotIn("week_ordinal", html)

    # ── the plan-tab gate ───────────────────────────────────────────────────

    def test_the_plan_gate_waits_for_the_mapping_and_the_review(self) -> None:
        unmapped = self.run_case({
            "kind": "gate",
            "input": {"binding": {"syllabus_id": "syl_1", "revision": 3, "reviewed_revision": None, "alignment_revision": 0}, "planState": "draft", "rowsReady": False},
        })
        self.assertTrue(unmapped["required"])
        self.assertFalse(unmapped["ready"])
        self.assertIn("Map the draft plan", unmapped["reason"])
        mapped = self.run_case({
            "kind": "gate",
            "input": {"binding": {"syllabus_id": "syl_1", "revision": 3, "reviewed_revision": None, "alignment_revision": 2, "stale": False}, "planState": "draft", "rowsReady": True},
        })
        self.assertFalse(mapped["ready"])
        self.assertIn("Review the mapping", mapped["reason"])
        reviewed = self.run_case({
            "kind": "gate",
            "input": {"binding": {"syllabus_id": "syl_1", "revision": 3, "reviewed_revision": 3, "alignment_revision": 2, "stale": False}, "planState": "draft", "rowsReady": True},
        })
        self.assertTrue(reviewed["ready"])
        self.assertIsNone(reviewed["reason"])
        stale = self.run_case({
            "kind": "gate",
            "input": {"binding": {"syllabus_id": "syl_1", "revision": 3, "reviewed_revision": 3, "alignment_revision": 2, "stale": True}, "planState": "draft", "rowsReady": True},
        })
        self.assertFalse(stale["ready"])
        self.assertTrue(stale["stale"])
        self.assertIn("changed", stale["reason"])
        plain = self.run_case({"kind": "gate", "input": {"binding": None, "planState": "draft", "rowsReady": False}})
        self.assertFalse(plain["required"])
        self.assertTrue(plain["ready"])

    # ── the companion course sequence ───────────────────────────────────────

    def test_the_sequence_is_course_enrollment_plan_then_align(self) -> None:
        out = self.run_case({"kind": "sequence", "parsed": FIXTURE_PARSE})
        methods = [call["method"] for call in out["calls"]]
        self.assertEqual(methods, ["course.create", "enrollment.create", "jobs.create", "syllabus.align"])
        self.assertTrue(out["created"]["ok"], out["created"])
        self.assertTrue(out["aligned"]["ok"], out["aligned"])
        keys = [call["options"].get("idempotencyKey") for call in out["calls"]]
        self.assertEqual(keys[0], "cb-companion-key1")
        self.assertEqual(keys[3], f"cb-syllabus-align-{FIXTURE_PARSE['syllabus_id']}-2-plan_p1")

    def test_the_course_create_payload_is_a_companion_with_the_syllabus_binding(self) -> None:
        out = self.run_case({"kind": "sequence", "parsed": FIXTURE_PARSE})
        course = out["calls"][0]["payload"]
        self.assertEqual(course["recipe"], "companion")
        self.assertEqual(course["title"], "Introduction to Databases")
        self.assertEqual(course["syllabus_id"], FIXTURE_PARSE["syllabus_id"])
        self.assertEqual(course["syllabus_revision"], 2)
        self.assertNotIn("pack_id", course)
        brief = out["calls"][2]["payload"]["brief"]
        self.assertEqual(brief["recipe"], "companion")
        self.assertEqual(brief["syllabus_id"], FIXTURE_PARSE["syllabus_id"])
        self.assertEqual(brief["syllabus_revision"], 2)

    def test_the_learner_answers_travel_with_the_companion_course(self) -> None:
        out = self.run_case({
            "kind": "sequence",
            "parsed": FIXTURE_PARSE,
            "goal": "Keep up with the labs",
            "level": "none",
            "subjectDomain": "computer science",
            "locale": "en-US",
            "presentationMode": "game",
        })
        course = out["calls"][0]["payload"]
        self.assertEqual(course["goal"], "Keep up with the labs")
        self.assertEqual(course["level"], "none")
        self.assertEqual(course["subject_domain"], "computer science")
        self.assertEqual(course["locale"], "en-US")
        self.assertEqual(course["presentation_mode"], "game")
        self.assertEqual(course["recipe"], "companion")
        brief = out["calls"][2]["payload"]["brief"]
        self.assertEqual(brief["goal"], course["goal"])
        self.assertEqual(brief["level"], "none")
        self.assertEqual(brief["subject_domain"], "computer science")
        self.assertEqual(brief["locale"], "en-US")

    def test_a_blank_sheet_uses_the_syllabus_title_and_sends_no_blank_field(self) -> None:
        out = self.run_case({
            "kind": "sequence",
            "parsed": FIXTURE_PARSE,
            "goal": "",
            "level": None,
            "presentationMode": "textbook",
        })
        course = out["calls"][0]["payload"]
        self.assertEqual(course["goal"], "Support the class on Introduction to Databases.")
        self.assertEqual(course["presentation_mode"], "textbook")
        for absent in ("level", "locale", "subject_domain"):
            self.assertNotIn(absent, course)
        brief = out["calls"][2]["payload"]["brief"]
        self.assertEqual(brief["goal"], course["goal"])
        self.assertNotIn("level", brief)

    def test_a_typed_refusal_stops_the_sequence_and_names_the_stage(self) -> None:
        out = self.run_case({"kind": "sequence", "parsed": FIXTURE_PARSE, "fail": "course.create"})
        self.assertFalse(out["created"]["ok"])
        self.assertEqual(out["created"]["stage"], "course.create")
        self.assertEqual(out["created"]["error"]["code"], "SYLLABUS_STALE")
        self.assertEqual([call["method"] for call in out["calls"]], ["course.create"])
        self.assertIsNone(out["aligned"])

    # ── copy ────────────────────────────────────────────────────────────────

    def test_the_surface_makes_no_official_enrollment_or_grade_claim(self) -> None:
        out = self.run_case({"kind": "course", "parsed": FIXTURE_PARSE, "scope": "short"})
        # The required disclaimer is a negation, so its phrase is cut before scanning for claims.
        blob = json.dumps(out).lower().replace("not official course material", "")
        for banned in [
            "enrolled",
            "enrollment confirmed",
            "official course",
            "official lesson",
            "your professor",
            "required by your course",
            "counts toward your grade",
            "accredited",
            "verified with your institution",
            "import your grades",
            "gradebook",
            "canvas",
            "moodle",
        ]:
            self.assertNotIn(banned, blob, banned)
        self.assertIn("authority", out["copy"]["authority"].lower())
        self.assertIn("not official course material", out["copy"]["notOfficial"].lower())

    # ── rendered surfaces ───────────────────────────────────────────────────

    def test_the_parse_review_renders_anchors_and_never_fills_a_missing_date(self) -> None:
        out = self.run_case({"kind": "render-parse", "parsed": FIXTURE_PARSE})
        html = out["html"]
        self.assertIn("What Coursebook read from your syllabus", html)
        self.assertIn("Due date not in your file", html)
        self.assertIn("Weight not in your file", html)
        self.assertIn("p. 4", html)
        self.assertIn("Not in your file", html)
        self.assertIn("Not official course material", html)
        self.assertIn('data-cb-syllabus-state="unknown"', html)
        self.assertEqual(html.lower().count("official"), html.lower().count("not official course material"))
        self.assertNotIn("verified with your institution", html.lower())

    def test_the_alignment_review_states_the_authority_and_gates_approval(self) -> None:
        out = self.run_case({"kind": "render-alignment", "alignment": _fixture_alignment()})
        html = out["html"]
        self.assertIn("Your syllabus is the authority", html)
        self.assertIn("Coursebook is a companion", html)
        self.assertIn("Not covered", html)
        self.assertIn("Conflicts", html)
        self.assertIn('data-cb-syllabus-approve="blocked"', html)
        self.assertIn("must be resolved", html)
        self.assertIn("Replan to match my syllabus", html)

    def test_the_intake_names_the_missing_file_door_and_offers_paste(self) -> None:
        out = self.run_case({"kind": "render-intake"})
        html = out["html"]
        self.assertIn("Use my college syllabus", html)
        self.assertIn("Markdown, plain text, PDF or Word", html)
        self.assertIn("Cancel", html)
        # No picker is rendered when the door is not known to exist.
        self.assertNotIn("Choose a syllabus file", html)


class SyllabusSourceAssertions(unittest.TestCase):
    """Source-level assertions that do not need Node."""

    def test_the_surface_does_not_reuse_raw_enum_names_as_copy(self) -> None:
        source = _source()
        # The state names may exist as keys/values inside the module; they may not be user copy.
        for needle in [
            "children: 'aligned'",
            "children: 'partial'",
            "children: 'unmatched'",
            "children: 'syllabus_item'",
            "children: 'alignment_state'",
        ]:
            self.assertNotIn(needle, source)
        self.assertIn("Partly covered", source)
        self.assertIn("Not covered", source)

    def test_no_path_or_url_is_sent_as_a_syllabus_source(self) -> None:
        source = _source()
        self.assertNotIn("syllabus_path", source)
        self.assertNotIn("/syllabus/fetch", source)
        # The intake payload builder never emits a path key.
        self.assertNotIn("payload.path", source)

    def test_the_alignment_panel_is_wired_to_the_plan_tab_and_names_the_revision_action(self) -> None:
        source = _source()
        # The panel is rendered by the learner plan tab, not a bespoke job screen.
        self.assertIn("jsx(SyllabusAlignmentPanel, {", source)
        self.assertIn("'data-cb-syllabus-gate': 'blocked'", source)
        self.assertIn("Upload the new syllabus", source)
        self.assertIn("syllabusPlanGate", source)
        # The panel's own copy makes no official-enrollment, grade or integration claim.
        start = source.index("function SyllabusAlignmentPanel")
        end = source.index("function SyllabusIntakeFlow")
        panel = source[start:end].lower()
        for banned in ("enrolled", "enrollment confirmed", "gradebook", "canvas", "moodle",
                       "counts toward your grade", "official course", "your professor"):
            self.assertNotIn(banned, panel, banned)
        # Revision changes never trigger a silent re-map or regeneration.
        self.assertIn("onRealign: stale ? null : mapPlan", source)

    def test_the_sheet_asks_the_same_level_and_mode_questions_as_create(self) -> None:
        source = _source()
        self.assertIn("const SYLLABUS_LEVEL_OPTIONS = Object.freeze([", source)
        for option in ("{ id: 'none', label: 'None' }", "{ id: 'some', label: 'Some' }", "{ id: 'confident', label: 'Confident' }"):
            self.assertIn(option, source)
        # The tokens mean what the planner's beginner rule reads them as.
        from coursebook import generation

        self.assertTrue(generation.is_beginner_level("none"))
        self.assertFalse(generation.is_beginner_level("some"))
        self.assertFalse(generation.is_beginner_level("confident"))
        start = source.index("function SyllabusParseStage")
        end = source.index("function SyllabusEntry")
        stage = source[start:end]
        for needle in (
            "SYLLABUS_COPY.goalQuestion",
            "SYLLABUS_COPY.levelQuestion",
            "SYLLABUS_COPY.modeQuestion",
            "createModeCard(mode, presentationMode, setPresentationMode)",
            "level: level || null",
            "subjectDomain: subjectDomain.trim() || null",
            "locale: locale.trim() || null",
            "presentationMode,",
        ):
            self.assertIn(needle, stage)
        # One sheet: the answers are on the scope step, and no second wizard step was added.
        self.assertIn("if (step === 'scope')", stage)
        self.assertNotIn("setStep('answers')", stage)

    def test_the_one_job_engine_is_reused(self) -> None:
        source = _source()
        self.assertIn("kind: 'plan'", source)
        self.assertNotIn("kind: 'syllabus_author'", source)
        self.assertNotIn("kind: 'companion_plan'", source)


if __name__ == "__main__":
    unittest.main()
