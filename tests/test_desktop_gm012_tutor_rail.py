"""GM-012 — the lesson-bound tutor rail: selection, citations, glossary and practice.

Two kinds of proof:

* the shipped module's rail is rendered through React (``renderToStaticMarkup``, the same jsdom-free
  harness the GM-006/GM-008/GM-010 cards use) and the composed DOM is asserted: the quote chip is a
  chip and not a turn, glossary terms are real buttons while prose is not a target, citations are
  buttons that name a served block, practice marks learner turns as graded and tutor turns as not,
  and the rail is a side column at 1049 and a bottom sheet at 460;
* the module source is scanned for the invariants a static render cannot show: selecting arms a
  quote and never calls ``tutor.ask``, the rail body never opens a host chat or a host composer, the
  pane renders the rail instead of the old lesson-context body, and hint/practice go through the
  existing ``lesson.assist`` / ``practice.write`` contracts.

What this does not prove: pixels against the approved concept frames, or a live provider answer.
The isolated rig, the walkthrough and ``docs/visual-review/gm-012/`` carry those.
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
import {
  TutorRail,
  tutorAskPayload,
  cbTutorCitations,
  cbTutorGlossary,
  cbTutorTurns,
  cbTutorLearnerTurnCount,
  tutorRailLayout
} from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const out = (value) => process.stdout.write(typeof value === 'string' ? value : JSON.stringify(value))
const json = (value) => process.stdout.write(JSON.stringify(value))

if (payload.kind === 'rail') {
  out(renderToStaticMarkup(React.createElement(TutorRail, payload.props || {})))
} else if (payload.kind === 'ask-payload') {
  json(tutorAskPayload(payload.input || {}))
} else if (payload.kind === 'citations') {
  json(cbTutorCitations(payload.turn || {}, payload.blockIndex || {}, payload.sourceIndex || {}))
} else if (payload.kind === 'glossary') {
  json(cbTutorGlossary(payload.page || {}))
} else if (payload.kind === 'turns') {
  json(cbTutorTurns(payload.history || {}))
} else if (payload.kind === 'learners') {
  json(cbTutorLearnerTurnCount(payload.transcript || []))
} else if (payload.kind === 'layout') {
  json(tutorRailLayout(payload.width))
} else {
  throw new Error(`unknown case ${payload.kind}`)
}
"""


def function_body(source: str, signature: str) -> str:
    """The body of one column-0 function, by brace matching. Test-local, no parser."""
    match = re.search(re.escape(signature) + r"[\s\S]*?\)\s*\{", source)
    if not match:
        raise AssertionError(f"no body for {signature}")
    opened = match.end() - 1
    depth = 0
    for index in range(opened, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opened : index + 1]
    raise AssertionError(f"unbalanced body for {signature}")


BLOCK_INDEX = {
    "blk_explain001": {"id": "blk_explain001", "role": "explain", "headline": "The mechanism"},
    "blk_orient0001": {"id": "blk_orient0001", "role": "orient", "headline": "Start here"},
}
SOURCE_INDEX = {"src_affection01": {"source_id": "src_affection01", "title": "Affection and register — field notes"}}
GLOSSARY = [
    {"term": "ですか", "gloss": "Question particle: turns a statement into a question.", "reading": "desu ka"},
    {"term": "敬語", "gloss": "Polite register.", "reading": "keigo", "pronunciation": "kei-go"},
]
TURNS = [
    {
        "id": "ttr_learner01",
        "ordinal": 1,
        "role": "learner",
        "text": "Why is です used here?",
        "block_id": "blk_orient0001",
        "selected_text": "Affection and register",
        "citations": [],
    },
    {
        "id": "ttr_tutor01",
        "ordinal": 2,
        "role": "tutor",
        "text": "です marks the polite register of the statement.",
        "block_id": None,
        "selected_text": None,
        "citations": [
            {"kind": "block", "id": "blk_explain001", "label": "The mechanism"},
            {"kind": "block", "id": "blk_ghost", "label": "An invented block"},
        ],
    },
]


class TutorRailRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-tutor-rail-")
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
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_case(self, payload: dict) -> str:
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
        return result.stdout

    def rail(self, **props) -> str:
        base = {
            "state": "ready",
            "width": 900,
            "courseTitle": "Japanese, first steps",
            "objectiveTitle": "Affection and register",
            "contextChip": "Section 2",
            "turns": [],
            "blockIndex": BLOCK_INDEX,
            "sourceIndex": SOURCE_INDEX,
            "glossary": [],
            "checkOpen": False,
            "mode": "ask",
            "quote": None,
            "draft": "",
            "busy": False,
            "practiceAvailable": False,
        }
        base.update(props)
        return self.run_case({"kind": "rail", "props": base})

    # -- selection ---------------------------------------------------------------------------
    def test_selection_does_not_auto_send(self) -> None:
        # Arming a quote paints a chip and no turn: selecting is not speaking.
        html = self.rail(quote={"text": "Affection and register", "blockId": "blk_orient0001"})
        self.assertIn('data-cb-tutor-quote="blk_orient0001"', html)
        self.assertIn('data-cb-tutor-thread="0"', html)
        self.assertNotIn("data-cb-tutor-turn=", html)

        # The payload builder refuses an empty question even when a quote is attached.
        empty = json.loads(
            self.run_case(
                {
                    "kind": "ask-payload",
                    "input": {
                        "courseId": "crs_1",
                        "enrollmentId": "enr_1",
                        "objectiveId": "obj_1",
                        "lessonRunId": "run_1",
                        "question": "   ",
                        "quote": {"text": "Affection and register", "blockId": "blk_orient0001"},
                        "mode": "ask",
                    },
                }
            )
        )
        self.assertIsNone(empty, "a quote with no question must not build a tutor.ask payload")

        full = json.loads(
            self.run_case(
                {
                    "kind": "ask-payload",
                    "input": {
                        "courseId": "crs_1",
                        "enrollmentId": "enr_1",
                        "objectiveId": "obj_1",
                        "lessonRunId": "run_1",
                        "question": "Why です?",
                        "quote": {"text": "Affection and register", "blockId": "blk_orient0001"},
                        "mode": "ask",
                    },
                }
            )
        )
        self.assertEqual(full["block_id"], "blk_orient0001")
        self.assertEqual(full["selected_text"], "Affection and register")
        self.assertEqual(full["mode"], "ask")

        # The pill's own body arms a quote and focuses the rail; it never calls the ask path.
        body = function_body(self.source, "function TutorSelectionPill(")
        self.assertIn("armTutorQuote", body)
        self.assertIn("requestTutorFocus", body)
        self.assertNotIn("tutor.ask", body)
        self.assertNotIn("performAsk", body)
        self.assertNotIn("onSend", body)

    def test_quote_chip_is_removable(self) -> None:
        html = self.rail(quote={"text": "敬語 is polite register.", "blockId": "blk_explain001"})
        self.assertIn('data-cb-tutor-quote="blk_explain001"', html)
        self.assertIn('data-cb-tutor-quote-text=""', html)
        self.assertIn("敬語 is polite register.", html)
        self.assertIn("data-cb-tutor-quote-remove", html)
        self.assertIn('aria-label="Remove the selected excerpt"', html)
        body = function_body(self.source, "function TutorRail(")
        self.assertIn("onClick: onRemoveQuote", body)

    # -- glossary ----------------------------------------------------------------------------
    def test_glossary_terms_are_buttons(self) -> None:
        html = self.rail(glossary=GLOSSARY)
        self.assertIn('data-cb-tutor-glossary="2"', html)
        for term in ("ですか", "敬語"):
            self.assertIn(f'data-cb-tutor-term="{term}"', html)
        # Each term is a real <button>, not a span with a click handler.
        for found in re.finditer(r"<button[^>]*data-cb-tutor-term=\"([^\"]+)\"", html):
            self.assertIn(found.group(1), ("ですか", "敬語"))
        self.assertGreaterEqual(len(re.findall(r"<button[^>]*data-cb-tutor-term=", html)), 2)
        # Authored prose is not clickable: a block headline never becomes a target.
        self.assertNotIn('data-cb-tutor-term="The mechanism"', html)
        self.assertNotIn("The mechanism", html)
        # A term without a gloss is not a glossary entry at all.
        entries = json.loads(
            self.run_case(
                {
                    "kind": "glossary",
                    "page": {"document": {"glossary": [{"term": "だけ"}, {"term": "です", "gloss": "copula"}]}},
                }
            )
        )
        self.assertEqual([entry["term"] for entry in entries], ["です"])

    # -- citations ---------------------------------------------------------------------------
    def test_tutor_citation_links_to_block(self) -> None:
        html = self.rail(turns=TURNS)
        self.assertIn('data-cb-tutor-citation="block"', html)
        self.assertIn('data-cb-tutor-citation-target="blk_explain001"', html)
        self.assertIn('aria-label="Go to The mechanism"', html)
        # A citation the served page does not carry is omitted, never rendered as a link.
        self.assertNotIn("blk_ghost", html)
        citations = json.loads(
            self.run_case(
                {
                    "kind": "citations",
                    "turn": TURNS[1],
                    "blockIndex": BLOCK_INDEX,
                    "sourceIndex": SOURCE_INDEX,
                }
            )
        )
        self.assertEqual([(c["kind"], c["id"]) for c in citations], [("block", "blk_explain001")])

    # -- no host chat ------------------------------------------------------------------------
    def test_tutor_rail_has_no_host_chat(self) -> None:
        html = self.rail(turns=TURNS, glossary=GLOSSARY)
        self.assertIn('data-cb-tutor-rail="side"', html)
        self.assertNotIn("data-cb-host-chat", html)
        for signature in ("function TutorRail(", "function TutorRailPane("):
            body = function_body(self.source, signature)
            for forbidden in (
                "host.newChat",
                "host.openSession",
                "host.composer",
                "startBoundLessonChat",
                "host.chat",
                "LessonPaneBody",
            ):
                self.assertNotIn(forbidden, body, f"{signature} must not reach the host chat ({forbidden})")
        pane = function_body(self.source, "function CoursebookPane(")
        self.assertIn("jsx(TutorRailPane, { binding: state.binding })", pane)
        self.assertNotIn("jsx(LessonPaneBody,", pane)

    # -- practice ----------------------------------------------------------------------------
    def test_practice_mode_only_grades_learner_turns(self) -> None:
        practice = {
            "declaration": {"scenario": "You ask a colleague for help.", "learner_role": "student", "tutor_role": "colleague"},
            "state": "active",
            "transcript": [
                {"ordinal": 1, "speaker": "tutor", "text": "こんにちは。何が必要ですか。"},
                {"ordinal": 2, "speaker": "learner", "text": "ペンをお願いします。"},
                {"ordinal": 3, "speaker": "tutor", "text": "はい、どうぞ。"},
            ],
            "remaining": 2,
            "verdict": "not_yet",
            "criteria": [{"id": "t1", "met": False}],
            "feedback": "Not yet: 0 of 2 target expressions used, over 1 learner turn.",
        }
        html = self.rail(mode="practice", practiceAvailable=True, practice=practice)
        self.assertIn('data-cb-tutor-practice="active"', html)
        self.assertIn("Only your turns are graded", html)
        self.assertEqual(html.count('data-cb-tutor-graded="true"'), 1, "only the learner turn is graded")
        self.assertEqual(html.count('data-cb-tutor-graded="false"'), 2, "tutor turns are never graded")
        self.assertIn('data-cb-tutor-verdict="not_yet"', html)
        learners = json.loads(
            self.run_case({"kind": "learners", "transcript": practice["transcript"]})
        )
        self.assertEqual(learners, 1)
        # Practice writes go through the existing commands, never through a second grader.
        pane = function_body(self.source, "function TutorRailPane(")
        self.assertIn("'practice.start'", pane)
        self.assertIn("'practice.end'", pane)
        self.assertIn("'tutor.ask'", pane)
        self.assertNotIn("'attempt.submit'", pane)

    # -- layout ------------------------------------------------------------------------------
    def test_tutor_rail_bottom_sheet_460(self) -> None:
        sheet = self.rail(width=460, glossary=GLOSSARY, turns=TURNS)
        self.assertIn('data-cb-tutor-rail="sheet"', sheet)
        self.assertIn("data-cb-tutor-send", sheet)
        self.assertIn('data-cb-tutor-composer="ask"', sheet)
        wide = self.rail(width=1049)
        self.assertIn('data-cb-tutor-rail="side"', wide)
        layouts = json.loads(
            self.run_case({"kind": "layout", "width": 460})
        )
        self.assertEqual(layouts, "sheet")
        layouts = json.loads(self.run_case({"kind": "layout", "width": 900}))
        self.assertEqual(layouts, "side")
        # No fixed height and no horizontal scroll: the sheet is the same hierarchy, stacked.
        self.assertNotIn("overflowX", sheet)
        body = function_body(self.source, "function TutorRail(")
        self.assertIn("TUTOR_SHEET_BREAKPOINT", body.replace("tutorRailLayout(width)", "tutorRailLayout(width)") + function_body(self.source, "function tutorRailLayout("))


class TutorRailStatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        TutorRailRenderTest.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        TutorRailRenderTest.tearDownClass.__func__(cls)

    run_case = TutorRailRenderTest.run_case
    rail = TutorRailRenderTest.rail

    def test_every_rail_state_is_named(self) -> None:
        for state, marker in (
            ("no-lesson", "Open a lesson to ask the tutor."),
            ("loading", "Reading this lesson…"),
            ("unavailable", "The tutor is unavailable. The lesson is still readable."),
            ("provider-failure", "The tutor could not answer. Nothing was graded."),
            ("lesson-changed", "This thread belongs to the previous section."),
        ):
            html = self.rail(state=state)
            self.assertIn(f'data-cb-tutor-state="{state}"', html)
            self.assertIn(marker, html, state)

    def test_hint_is_labelled_and_never_an_answer_key(self) -> None:
        with_hint = self.rail(
            checkOpen=True,
            hint={"available": True, "used": False},
            draft="",
        )
        self.assertIn("Ask for a hint", with_hint)
        self.assertIn("does not show the answer", with_hint)
        used = self.rail(checkOpen=True, hint={"available": False, "used": True})
        self.assertIn('data-cb-tutor-assist="hinted"', used)
        self.assertIn("marked hinted", used)
        # The hint path records the assist event; the answer itself comes from the tutor call.
        pane = function_body(PLUGIN_JS.read_text(encoding="utf-8"), "function TutorRailPane(")
        self.assertIn("'lesson.assist'", pane)
        self.assertIn("kind: 'hint_request'", pane)


if __name__ == "__main__":
    unittest.main()
