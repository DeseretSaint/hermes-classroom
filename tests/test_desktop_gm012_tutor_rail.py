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
from coursebook import lesson_skills

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
  tutorRailLayout,
  skillDisplayName,
  skillNoteCopy
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
} else if (payload.kind === 'skill-note') {
  json({
    lesson: skillNoteCopy({ skill: 'coursebook:lesson-tutoring', reason: 'lesson_binding' }),
    coach: skillNoteCopy({ skill: 'coursebook:learner-coach', reason: 'coursebook_chat_without_live_binding' }),
    boundObjective: skillNoteCopy({ skill: 'coursebook:lesson-tutoring', reason: 'bound_objective_not_in_store' }),
    unknown: skillNoteCopy({ skill: 'coursebook:lesson-tutoring', reason: 'unreadable' }),
    bare: skillNoteCopy({ skill: 'lesson_tutoring', reason: 'lesson_binding' }),
    none: skillNoteCopy(null),
    emptySkill: skillNoteCopy({ skill: '', reason: 'lesson_binding' }),
    name: skillDisplayName('coursebook:lesson-tutoring')
  })
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

    # -- E2E U8: the pane names the skill, and never prints its identifier --------------------
    def test_the_skill_note_names_the_skill_and_never_prints_a_slug(self) -> None:
        """The backend answers with `coursebook:lesson-tutoring`; a learner must not read that.

        The two sentences are asserted literally, the anchored slug pattern the card names is
        refused, and the pane is shown to render this function's answer rather than the id.
        """
        out = json.loads(self.run_case({"kind": "skill-note"}))
        self.assertEqual(out["name"], "Lesson Tutoring")
        self.assertEqual(
            out["lesson"],
            "Tutor: Lesson Tutoring — it reads this chat’s section from your next message on.",
        )
        self.assertEqual(
            out["coach"],
            "Coach: Learner Coach — no lesson is open for this chat, so it coaches in general terms.",
        )
        # A live binding whose lesson row is missing from this store still loads the tutor. The
        # line must not call it an open chat: the lesson is bound, only its saved content is gone.
        self.assertEqual(
            out["boundObjective"],
            "Tutor: Lesson Tutoring — this chat’s lesson has no saved content here. Reopen it from the course pane.",
        )
        self.assertIn("Tutor", out["boundObjective"])
        self.assertNotIn("Coach", out["boundObjective"])
        self.assertNotIn("no lesson is open", out["boundObjective"])
        self.assertIn("Reopen it from the course pane", out["boundObjective"])
        # An unknown reason names the skill and claims nothing about the lesson.
        self.assertEqual(out["unknown"], "Lesson Tutoring — this chat will use this skill.")
        self.assertFalse(out["unknown"].startswith("Tutor:"))
        self.assertFalse(out["unknown"].startswith("Coach:"))
        # The pane branches on the backend's own reason strings, not on a copy that can drift.
        for reason in (
            lesson_skills.REASON_LIVE_BINDING,
            lesson_skills.REASON_NO_LIVE_BINDING,
            lesson_skills.REASON_BOUND_OBJECTIVE_MISSING,
        ):
            self.assertIn(f"case '{reason}':", self.source, reason)
        # The words after the last colon are title-cased, so an underscored id reads as words.
        self.assertEqual(out["bare"], "Tutor: Lesson Tutoring — it reads this chat’s section from your next message on.")
        # Nothing to say, nothing printed.
        self.assertIsNone(out["none"])
        self.assertIsNone(out["emptySkill"])
        slug = re.compile(r"^[a-z0-9]+_[a-z0-9_]+$")
        for key in ("lesson", "coach", "bare"):
            text = out[key]
            self.assertIsNone(slug.match(text), text)
            self.assertNotIn("coursebook:", text)
            self.assertNotIn("lesson-tutoring", text)
            self.assertNotIn("learner-coach", text)
        # No routing apology reaches the learner: the pane's status line names what may not work
        # and the one action, not the connection plumbing.
        pane = function_body(self.source, "function CoursebookPane(")
        self.assertIn("children: skillNoteCopy(skillNote)", pane)
        self.assertNotIn("skillNote.skill}`", pane)
        self.assertIn("Reopen the pane", pane)
        self.assertNotIn("Routing unavailable", pane)
        self.assertNotIn("profile routes", pane)

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

    def test_lesson_prose_is_selectable_in_a_non_selecting_host(self) -> None:
        # The Desktop session surface sets `user-select: none` on its chrome, and the lesson is
        # rendered inside it. Without an explicit `text` the learner cannot select a word at all,
        # so the pill can never fire — the rail's whole selection path is dead in the real window.
        # A render harness has no host CSS, so this is asserted on the shipped source.
        source = PLUGIN_JS.read_text(encoding="utf-8")
        for label, signature in (
            ("the reading column", "jsx('div', {\n            'data-cb-reading-column'"),
            ("the textbook block", "function TextbookBlock("),
            ("the guided block", "function GuidedBlock("),
        ):
            if signature.startswith("function"):
                body = function_body(source, signature)
            else:
                body = source[source.index(signature) : source.index(signature) + 700]
            self.assertIn("userSelect: 'text'", body, label)
            self.assertIn("WebkitUserSelect: 'text'", body, label)
        # Every authored block is a selection target, including the procedure list items.
        self.assertGreaterEqual(
            source.count("data-cb-block'"),
            3,
            "block renderers changed shape — re-check the selectable surface",
        )
        self.assertGreaterEqual(
            source.count("userSelect: 'text'"),
            4,
            "a block renderer lost its selectable prose",
        )


class TutorRailModeChoiceTest(unittest.TestCase):
    """The rail never moves a learner who has already chosen a mode.

    quill's GM-012a nit: the auto-open effect depends on `check.open`/`check.get` landing, and it
    only records its own one-shot flag. If the learner picks Ask while that read is still in
    flight, the late practice declaration used to flip the rail to Practice anyway. The guard is
    armed by `modeChange`, so this mounts the real pane against a fake backend whose check reads
    are released on demand and asserts the chosen Ask mode survives them.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-tutor-mode-choice-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "mode-choice.mjs").write_text(MODE_CHOICE_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
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

    def test_ask_chosen_before_the_practice_check_arrives_stays_ask(self) -> None:
        result = subprocess.run(
            ["node", str(self.root / "mode-choice.mjs")],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        case = json.loads(result.stdout)
        self.assertEqual(case["error"], None, case)
        # The practice tabs were on screen and the practice mode was genuinely reachable: this is
        # not a pass because the auto-open never had a chance to fire.
        self.assertTrue(case["practiceTab"], "the practice tab was missing; the race was not set up")
        self.assertTrue(case["modeControls"], "the Ask control was missing; the choice was never made")
        self.assertEqual(case["chosenMode"], "ask")
        self.assertEqual(
            case["finalMode"],
            "ask",
            "the rail flipped to Practice after the learner had already chosen Ask",
        )


MODE_CHOICE_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const mod = await import('./plugin.js')

const IMPLEMENTED = [
  'library.list',
  'lesson.page',
  'check.open',
  'check.get',
  'practice.state',
  'practice.start',
  'practice.end',
  'tutor.history'
]

const deferred = () => {
  let release = null
  const promise = new Promise((resolve) => {
    release = resolve
  })
  return { promise, release }
}

const checkOpen = deferred()
const checkGet = deferred()

const fakeRest = (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return Promise.resolve({ wire_version: 25, implemented_methods: IMPLEMENTED, single_home_host: false })
  }
  if (base === '/rpc') {
    const method = options && options.body ? options.body.method : null
    if (method === 'check.open') return checkOpen.promise
    if (method === 'check.get') return checkGet.promise
    if (method === 'library.list') {
      return Promise.resolve({
        ok: true,
        result: {
          items: [
            {
              enrollment_id: 'enr_1',
              course_id: 'crs_1',
              title: 'Japanese, first steps',
              revision: 3,
              evidence_summary: { current_objective_id: 'obj_1' }
            }
          ]
        }
      })
    }
    if (method === 'lesson.page') {
      return Promise.resolve({
        ok: true,
        result: {
          revision: 3,
          course: { title: 'Japanese, first steps' },
          section: { title: 'Affection and register', ordinal: 2 },
          sources: []
        }
      })
    }
    if (method === 'practice.state') return Promise.resolve({ ok: true, result: { state: 'none' } })
    if (method === 'tutor.history') return Promise.resolve({ ok: true, result: { turns: [] } })
    return Promise.resolve({ ok: true, result: {} })
  }
  return Promise.resolve({})
}

mod.default.register({ rest: fakeRest, register: () => {}, onDispose: () => {} })

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const binding = (runId) => ({
  enrollment_id: 'enr_1',
  objective_id: 'obj_1',
  lesson_run_id: runId,
  profile: 'default',
  status: 'active',
  stored_session_id: 'sess_1'
})
const settle = async (ms = 60) => {
  await act(async () => {
    await new Promise((done) => setTimeout(done, ms))
  })
}
const modeNow = () => {
  const nav = document.querySelector('[data-cb-learning-tabs]')
  return nav ? nav.getAttribute('data-cb-learning-tabs') : null
}
const practiceDeclaration = { prompt: 'Say the line to the shopkeeper.', sentences: [] }

const out = { error: null, initialMode: null, chosenMode: null, finalMode: null, practiceTab: false, modeControls: false }
try {
  // 1. Mount on a bound run. The check reads are held, so no practice control can have opened yet.
  await act(async () => {
    root.render(React.createElement(mod.TutorRailPane, { binding: binding('run_1') }))
  })
  await settle()
  out.initialMode = modeNow()

  // 2. `check.open` lands with the practice declaration. A bound run suppresses the auto-open, so
  //    the learner sees the Ask/Practice tabs while `check.get` is still in flight.
  await act(async () => {
    checkOpen.release({ ok: true, result: { check_id: 'chk_1', stimulus: { practice: practiceDeclaration } } })
    await new Promise((done) => setTimeout(done, 30))
  })
  await settle()
  const askTab = document.querySelector('[data-cb-tab="ask"]')
  out.practiceTab = Boolean(document.querySelector('[data-cb-tab="practice"]'))
  out.modeControls = Boolean(askTab)

  // 3. The learner picks Ask before the check detail resolves.
  await act(async () => {
    if (askTab) askTab.click()
  })
  out.chosenMode = modeNow()

  // 4. The run ends and the check detail lands after the choice. The rail must stay on Ask.
  await act(async () => {
    root.render(React.createElement(mod.TutorRailPane, { binding: binding(null) }))
  })
  await act(async () => {
    checkGet.release({ ok: true, result: { check_id: 'chk_1', state: 'open', stimulus: { practice: practiceDeclaration } } })
    await new Promise((done) => setTimeout(done, 60))
  })
  await settle()
  out.finalMode = modeNow()
} catch (error) {
  out.error = { name: error.name, message: String(error.message || error), stack: String(error.stack || '').split('\n').slice(0, 5) }
}
process.stdout.write(JSON.stringify(out))
"""


# -- U8-follow: the unavailable panels speak to the learner, not about the pipeline -------------

NOT_IMPLEMENTED_TITLE = "Lessons cannot start here yet"
NOT_IMPLEMENTED_BODY = (
    "You cannot start or continue a lesson from this chat yet. Open Coursebook to read "
    "what is already there; nothing on this panel is guessed."
)
UNAVAILABLE_TITLE = "The tutor cannot answer here right now"
UNAVAILABLE_BODY = (
    "Something went wrong reading this chat’s lesson, so you cannot ask the tutor here right now. "
    "Open Coursebook and reopen the section to try again."
)

# The stub SDK's PanelEmpty renders only `children`, so a test that wants the real panel copy has
# to give it the title/description shape the shipped SDK already uses for `EmptyState`/`ErrorState`
# (both stubs below pin it). Everything else in the stub is the shared one, unmodified.
PANEL_EMPTY_WITH_COPY = (
    "export const PanelEmpty = (props) =>\n"
    "  el('div', { className: 'panel-empty' }, [\n"
    "    el('div', { key: 't', className: 'panel-title' }, props.title || null),\n"
    "    el('div', { key: 'd', className: 'panel-desc' }, props.description || null),\n"
    "    props.action || null\n"
    "  ])\n"
)

UNAVAILABLE_HARNESS = r"""
import React, { act } from 'react'
import fs from 'node:fs'
import { JSDOM } from 'jsdom'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

// The focused chat is durable and on screen; the SDK stub reads this atom through the pane.
globalThis.__CB_STORED_ATOM__ = { get: () => 'sess_1', subscribe: () => () => {} }

const mod = await import('./plugin.js')

const rest = (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return Promise.resolve({ wire_version: 25, implemented_methods: [], single_home_host: false })
  }
  if (base === '/rpc') {
    const method = options && options.body ? options.body.method : null
    if (method === 'binding.get') {
      return Promise.resolve({
        ok: false,
        error: { code: payload.code, message: payload.message }
      })
    }
    return Promise.resolve({ ok: true, result: {} })
  }
  if (base === '/sessions/skill') return Promise.resolve({})
  return Promise.resolve({ ok: true, result: {} })
}

const registered = []
mod.default.register({ rest, register: (contribution) => registered.push(contribution), onDispose: () => {} })
const pane = registered.find((contribution) => contribution && contribution.id === 'pane')
if (!pane || typeof pane.render !== 'function') {
  process.stdout.write(JSON.stringify({ error: 'the plugin registered no pane contribution' }))
  process.exit(0)
}

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const out = { error: null }
try {
  await act(async () => {
    root.render(React.createElement(pane.render))
  })
  await act(async () => {
    await new Promise((done) => setTimeout(done, 120))
  })
  const host = document.getElementById('root')
  const wrapper = host.querySelector('[data-cb-binding-panel]')
  const title = wrapper ? wrapper.querySelector('.panel-title') : null
  const desc = wrapper ? wrapper.querySelector('.panel-desc') : null
  const detail = wrapper ? wrapper.querySelector('[data-cb-binding-detail]') : null
  out.panel = wrapper ? wrapper.getAttribute('data-cb-binding-panel') : null
  out.title = title ? title.textContent : null
  out.description = desc ? desc.textContent : null
  // Everything a learner can read in the panel itself: the title, the sentence and the button.
  out.panelText = [title ? title.textContent : '', desc ? desc.textContent : '', wrapper ? (wrapper.querySelector('button') || {}).textContent || '' : ''].join(' ')
  out.detailText = detail ? detail.textContent : null
  out.detailOpen = detail ? detail.hasAttribute('open') : null
  out.hasOpenCoursebook = Boolean(wrapper && wrapper.querySelector('button'))
} catch (error) {
  out.error = { name: error.name, message: String(error.message || error), stack: String(error.stack || '').split('\n').slice(0, 5) }
}
process.stdout.write(JSON.stringify(out))
"""


class TutorPaneUnavailableCopyTest(unittest.TestCase):
    """A failed binding read is said in the learner's words, never in the pipeline's.

    U8-follow: the NOT_IMPLEMENTED panel used to name a backend, a kernel schema and a session
    binding, and the generic panel printed the raw error code in front of its sentence. Both are
    rendered here through the registered pane contribution so the assertion is on the DOM a learner
    gets, not on a source-scan proxy for it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-tutor-unavailable-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "unavailable.mjs").write_text(UNAVAILABLE_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        stub = SDK_STUB.replace(
            "focusedStoredSessionId: atom(null),",
            "focusedStoredSessionId: (globalThis.__CB_STORED_ATOM__ || atom(null)),",
        )
        panel_empty_shape = "export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))"
        if panel_empty_shape not in stub:
            raise AssertionError("the shared SDK stub's PanelEmpty changed shape; re-check this test's local stub")
        stub = stub.replace(panel_empty_shape, PANEL_EMPTY_WITH_COPY.rstrip("\n"))
        (sdk / "index.js").write_text(stub, encoding="utf-8")
        cls.root = root
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, code: str, message: str = "the read did not complete") -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps({"code": code, "message": message}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "unavailable.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    # -- the contract -----------------------------------------------------------------------
    def test_not_implemented_says_what_the_learner_cannot_do(self) -> None:
        out = self.render("NOT_IMPLEMENTED", "binding.get is not implemented")
        self.assertIsNone(out["error"], out)
        self.assertEqual(out["panel"], "not-implemented", "the state marker must single out this branch")
        self.assertEqual(out["title"], NOT_IMPLEMENTED_TITLE)
        self.assertEqual(out["description"], NOT_IMPLEMENTED_BODY)
        self.assertTrue(out["hasOpenCoursebook"], "the panel must still offer the one open action")

    def test_generic_unavailable_never_prints_the_code(self) -> None:
        out = self.render("HOST_UNAVAILABLE", "The host did not answer")
        self.assertIsNone(out["error"], out)
        self.assertEqual(out["panel"], "unavailable")
        self.assertEqual(out["title"], UNAVAILABLE_TITLE)
        self.assertEqual(out["description"], UNAVAILABLE_BODY)
        # The code and the message survive for diagnosis, closed, in the disclosure.
        self.assertIn("HOST_UNAVAILABLE", out["detailText"])
        self.assertIn("The host did not answer", out["detailText"])
        self.assertFalse(out["detailOpen"], "the technical detail must not be expanded by default")

    def test_no_pipeline_noun_or_error_code_reaches_the_panel_text(self) -> None:
        banned = ("backend", "kernel schema", "session binding", "NOT_IMPLEMENTED", "HOST_UNAVAILABLE")
        for code in ("NOT_IMPLEMENTED", "HOST_UNAVAILABLE", "E_BINDING_READ", "VALIDATION_FAILED"):
            out = self.render(code, "the read did not complete")
            self.assertIsNone(out["error"], out)
            text = out["panelText"]
            self.assertTrue(out["description"], f"{code}: the panel rendered no sentence")
            lowered = text.lower()
            for word in banned:
                self.assertNotIn(word.lower(), lowered, f"{code}: '{word}' reached the learner")
            self.assertNotIn(code, text, f"{code}: the raw code is in the panel sentence")
            self.assertIsNone(re.search(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b", text), text)
        # An E_-style code is never part of the visible sentence, wherever it is spelled.
        out = self.render("E_BINDING_READ", "the read did not complete")
        self.assertIn("E_BINDING_READ", out["detailText"])
        self.assertNotIn("E_BINDING_READ", out["panelText"])

    # -- the same two strings, pinned in source -----------------------------------------------
    def test_the_panel_source_carries_the_words_and_not_the_plumbing(self) -> None:
        pane = function_body(self.source, "function CoursebookPane(")
        self.assertIn(f"title: '{NOT_IMPLEMENTED_TITLE}'", pane)
        self.assertIn(f"title: '{UNAVAILABLE_TITLE}'", pane)
        self.assertIn(NOT_IMPLEMENTED_BODY, pane)
        self.assertIn(UNAVAILABLE_BODY, pane)
        self.assertIn("data-cb-binding-panel", pane)
        self.assertIn("Technical detail", pane)
        # The old speech and the code-in-the-sentence shape are gone.
        self.assertNotIn("Lessons arrive with the learning kernel", pane)
        self.assertNotIn("kernel schema", pane)
        self.assertNotIn("Cannot read this chat", pane)
        self.assertNotIn("`${code}: ", pane)
        self.assertNotIn("description: code ?", pane)


# -- U8-follow2: a failed hint, start or bind says it in the learner's words ----------------------
#
# U8-follow fixed the two *binding-panel* sentences. The three action notices next door still put the
# pipeline's code in front of the learner's sentence, and the practice one was not even rendered in
# the practice body. Both are proved here by driving the real pane: click the control, let the fake
# backend refuse, then read the DOM a learner gets.

HINT_FAILURE_SENTENCE = "Your hint could not be recorded. Try again."
PRACTICE_FAILURE_SENTENCE = "Your practice could not start. Try again."
BIND_FAILURE_SENTENCE = (
    "This chat could not be linked to your lesson. Open Coursebook and choose the section again."
)

ACTION_FAILURE_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const mod = await import('./plugin.js')

const IMPLEMENTED = [
  'library.list',
  'lesson.page',
  'check.open',
  'check.get',
  'practice.state',
  'practice.start',
  'practice.end',
  'tutor.history',
  'lesson.assist'
]

const declaration = {
  prompt: 'Say the line to the shopkeeper.',
  sentences: [],
  scenario: 'A small shop in Kyoto.',
  tutor_role: 'shopkeeper',
  learner_role: 'customer'
}
const stimulus = { assistance_policy: { hint: 'available' }, practice: declaration }
const ok = (result) => Promise.resolve({ ok: true, result })

const fakeRest = (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return Promise.resolve({ wire_version: 25, implemented_methods: IMPLEMENTED, single_home_host: false })
  }
  if (base === '/rpc') {
    const method = options && options.body ? options.body.method : null
    if (method === 'library.list') {
      return ok({
        items: [
          {
            enrollment_id: 'enr_1',
            course_id: 'crs_1',
            title: 'Japanese, first steps',
            revision: 3,
            evidence_summary: { current_objective_id: 'obj_1' }
          }
        ]
      })
    }
    if (method === 'lesson.page') {
      return ok({
        revision: 3,
        course: { title: 'Japanese, first steps' },
        section: { title: 'Affection and register', ordinal: 2 },
        sources: []
      })
    }
    if (method === 'tutor.history') return ok({ turns: [] })
    if (method === 'check.open') return ok({ check_id: 'chk_1', stimulus })
    if (method === 'check.get') return ok({ check_id: 'chk_1', state: 'open', stimulus })
    if (method === 'practice.state') return ok({ state: 'none' })
    if (method === 'lesson.assist') {
      return Promise.resolve({ ok: false, error: payload.hintError })
    }
    if (method === 'practice.start') {
      return Promise.resolve({ ok: false, error: payload.practiceError })
    }
    return ok({})
  }
  return Promise.resolve({})
}

mod.default.register({ rest: fakeRest, register: () => {}, onDispose: () => {} })

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const binding = {
  enrollment_id: 'enr_1',
  objective_id: 'obj_1',
  lesson_run_id: 'run_1',
  profile: 'default',
  status: 'active',
  stored_session_id: 'sess_1'
}
const settle = async (ms = 80) => {
  await act(async () => {
    await new Promise((done) => setTimeout(done, ms))
  })
}
const readNotice = () => {
  const card = document.querySelector('[data-cb-tutor-notice]')
  if (!card) return null
  const line = card.querySelector('[data-cb-tutor-notice-line]')
  const detail = card.querySelector('[data-cb-tutor-notice-detail]')
  return {
    full: card.textContent,
    // What the learner reads before opening anything: the sentence only.
    sentence: line ? line.textContent : '',
    roleStatus: line ? line.getAttribute('role') : null,
    detail: detail ? detail.textContent : null,
    detailOpen: detail ? detail.hasAttribute('open') : null
  }
}

const out = { error: null, hint: null, practice: null, hintButton: false, startButton: false, hintMode: null, practiceMode: null, practiceBody: null }
try {
  await act(async () => {
    root.render(React.createElement(mod.TutorRailPane, { binding }))
  })
  await settle(200)

  const modeNow = () => {
    const rail = document.querySelector('[data-cb-tutor-mode]')
    return rail ? rail.getAttribute('data-cb-tutor-mode') : null
  }
  const bodyNow = () => {
    const body = document.querySelector('[data-cb-tutor-body]')
    return body ? body.getAttribute('data-cb-tutor-body') : null
  }

  const hintButton = document.querySelector('[data-cb-tutor-hint="available"]')
  out.hintButton = Boolean(hintButton)
  if (hintButton) {
    await act(async () => {
      hintButton.click()
    })
    await settle(120)
    out.hintMode = modeNow()
    out.hint = readNotice()
  }

  const practiceTab = document.querySelector('[data-cb-tab="practice"]')
  if (practiceTab) {
    await act(async () => {
      practiceTab.click()
    })
    await settle(120)
  }
  const start = document.querySelector('[data-cb-tutor-practice-start]')
  out.startButton = Boolean(start)
  if (start) {
    await act(async () => {
      start.click()
    })
    await settle(120)
    out.practiceMode = modeNow()
    out.practiceBody = bodyNow()
    out.practice = readNotice()
  }
} catch (error) {
  out.error = { name: error.name, message: String(error.message || error), stack: String(error.stack || '').split('\n').slice(0, 6) }
}
process.stdout.write(JSON.stringify(out))
"""

BIND_FAILURE_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

// The focused chat is durable and on screen; the SDK stub reads this atom through the pane.
globalThis.__CB_STORED_ATOM__ = { get: () => 'sess_1', subscribe: () => () => {} }

const mod = await import('./plugin.js')

const rest = (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return Promise.resolve({ wire_version: 25, implemented_methods: [], single_home_host: false })
  }
  if (base === '/rpc') {
    const method = options && options.body ? options.body.method : null
    if (method === 'binding.get') {
      // A ready read with no binding for this chat: the pane is free to bind the armed run.
      return Promise.resolve({ ok: true, result: { binding: null } })
    }
    return Promise.resolve({ ok: true, result: {} })
  }
  if (base === '/sessions/skill') return Promise.resolve({})
  if (base === '/sessions/bind') {
    return Promise.resolve({ ok: false, code: payload.code, message: payload.message })
  }
  return Promise.resolve({ ok: true, result: {} })
}

// The run this Desktop opened, armed by the click that started it, before the pane mounts.
mod.armPendingBind({
  enrollmentId: 'enr_1',
  objectiveId: 'obj_1',
  objectiveTitle: 'Affection and register',
  lessonRunId: 'run_1',
  profile: null
})

const registered = []
mod.default.register({ rest, register: (contribution) => registered.push(contribution), onDispose: () => {} })
const pane = registered.find((contribution) => contribution && contribution.id === 'pane')
if (!pane || typeof pane.render !== 'function') {
  process.stdout.write(JSON.stringify({ error: 'the plugin registered no pane contribution' }))
  process.exit(0)
}

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const out = { error: null }
try {
  await act(async () => {
    root.render(React.createElement(pane.render))
  })
  await act(async () => {
    await new Promise((done) => setTimeout(done, 200))
  })
  const note = document.querySelector('[data-cb-tutor-bind-note]')
  const detail = document.querySelector('[data-cb-tutor-bind-detail]')
  out.noteText = note ? note.textContent : null
  out.sentence = note ? (note.querySelector('span') || {}).textContent || null : null
  out.detail = detail ? detail.textContent : null
  out.detailOpen = detail ? detail.hasAttribute('open') : null
} catch (error) {
  out.error = { name: error.name, message: String(error.message || error), stack: String(error.stack || '').split('\n').slice(0, 6) }
}
process.stdout.write(JSON.stringify(out))
"""

# Every code shape the backend can answer with: an E_-style catalogue code, the two host constants,
# and a plain validation code. None of them may reach the sentence.
FAILURE_CODES = ("E_ASSIST_RECORD", "HOST_UNAVAILABLE", "NOT_IMPLEMENTED", "VALIDATION_FAILED")
CODE_SHAPE = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")


class TutorActionNoticeCopyTest(unittest.TestCase):
    """A failed Hint, Start practice or automatic bind is said to the learner, not about the API.

    The pane is mounted for real and the control is clicked; the assertions are on the rendered
    notice and bind note. The raw code and message have to survive inside the closed Technical
    detail disclosure, so the failure stays diagnosable without becoming the sentence.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-tutor-action-notice-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "action-failure.mjs").write_text(ACTION_FAILURE_HARNESS, encoding="utf-8")
        (root / "bind-failure.mjs").write_text(BIND_FAILURE_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        stub = SDK_STUB.replace(
            "focusedStoredSessionId: atom(null),",
            "focusedStoredSessionId: (globalThis.__CB_STORED_ATOM__ || atom(null)),",
        )
        if stub == SDK_STUB:
            raise AssertionError("the shared SDK stub's focused-session atom changed shape; re-check this test")
        (sdk / "index.js").write_text(stub, encoding="utf-8")
        cls.root = root
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")
        # The acceptance grep is scoped to this segment, not the whole built module: the same
        # concatenation still exists in unrelated segments that this card does not own.
        cls.tutor_source = (ROOT / "desktop" / "src" / "99-tutor.js").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def _run(self, harness: str, case: dict) -> dict:
        path = self.root / "case.json"
        path.write_text(json.dumps(case), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / harness), str(path)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        out = json.loads(result.stdout)
        self.assertIsNone(out.get("error"), out)
        return out

    def action_failure(self, code: str = "E_ASSIST_RECORD", practice_code: str = "E_PRACTICE_START") -> dict:
        return self._run(
            "action-failure.mjs",
            {
                "hintError": {"code": code, "message": "the assist write was refused"},
                "practiceError": {"code": practice_code, "message": "practice could not be opened"},
            },
        )

    def bind_failure(self, code: str = "BIND_REFUSED") -> dict:
        return self._run(
            "bind-failure.mjs",
            {"code": code, "message": "the run already belongs to another chat"},
        )

    # -- the three sentences ------------------------------------------------------------------
    def test_failed_hint_says_what_happened_and_what_is_open(self) -> None:
        out = self.action_failure()
        self.assertTrue(out["hintButton"], "the Hint control was never reachable; the path was not rendered")
        hint = out["hint"]
        self.assertIsNotNone(hint, "a refused hint rendered no notice at all")
        self.assertEqual(out["hintMode"], "ask")
        self.assertEqual(hint["sentence"], HINT_FAILURE_SENTENCE)
        self.assertEqual(hint["roleStatus"], "status", "the sentence must stay the live-region text")
        # The code and message survive, closed, for diagnosis.
        self.assertIn("E_ASSIST_RECORD", hint["detail"])
        self.assertIn("the assist write was refused", hint["detail"])
        self.assertFalse(hint["detailOpen"], "the technical detail must not be expanded by default")
        self.assertNotIn("E_ASSIST_RECORD", hint["sentence"])

    def test_failed_practice_start_is_rendered_in_the_practice_body(self) -> None:
        out = self.action_failure()
        self.assertTrue(out["startButton"], "Start practice was never reachable; the path was not rendered")
        practice = out["practice"]
        self.assertIsNotNone(practice, "a refused practice start rendered no notice at all")
        self.assertEqual(out["practiceMode"], "practice")
        self.assertEqual(
            out["practiceBody"], "practice", "the notice has to live in the body the learner is looking at"
        )
        self.assertEqual(practice["sentence"], PRACTICE_FAILURE_SENTENCE)
        self.assertIn("E_PRACTICE_START", practice["detail"])
        self.assertIn("practice could not be opened", practice["detail"])
        self.assertFalse(practice["detailOpen"])
        self.assertNotIn("E_PRACTICE_START", practice["sentence"])

    def test_refused_bind_says_what_happened_and_where_to_go(self) -> None:
        out = self.bind_failure()
        self.assertIsNotNone(out["noteText"], "a refused bind rendered no note at all")
        self.assertEqual(out["sentence"], BIND_FAILURE_SENTENCE)
        self.assertIn("BIND_REFUSED", out["detail"])
        self.assertIn("the run already belongs to another chat", out["detail"])
        self.assertFalse(out["detailOpen"], "the technical detail must not be expanded by default")
        self.assertNotIn("BIND_REFUSED", out["sentence"])

    # -- and no code shape reaches the sentence, whatever the backend answered -------------------
    def test_no_raw_code_reaches_any_action_sentence(self) -> None:
        banned = ("NOT_IMPLEMENTED", "HOST_UNAVAILABLE")
        for code in FAILURE_CODES:
            out = self.action_failure(code, code)
            for stage in ("hint", "practice"):
                sentence = out[stage]["sentence"]
                self.assertTrue(sentence, f"{code}/{stage}: no sentence was rendered")
                self.assertNotIn(code, sentence, f"{code}/{stage}: the raw code is in the sentence")
                for word in banned:
                    self.assertNotIn(word, sentence, f"{code}/{stage}: '{word}' reached the learner")
                self.assertIsNone(CODE_SHAPE.search(sentence), f"{code}/{stage}: {sentence!r}")
                self.assertIn(code, out[stage]["detail"], f"{code}/{stage}: the code must survive for diagnosis")
            out = self.bind_failure(code)
            self.assertEqual(out["sentence"], BIND_FAILURE_SENTENCE)
            self.assertNotIn(code, out["sentence"])
            self.assertIn(code, out["detail"])
        self.assertNotIn("ERROR:", out["sentence"])

    # -- the same shapes, pinned in source ------------------------------------------------------
    def test_the_source_no_longer_concatenates_a_code_in_front_of_a_sentence(self) -> None:
        # The card's acceptance grep, as a test: each old concatenation is named so a regression is
        # reported by the exact string someone re-introduced. Scoped to this segment, which is what
        # `git grep … desktop/src/99-tutor.js` covers.
        for old in (
            "`${recorded.error.code}: ",
            "`${response.error.code}: ",
            "`${response.code}: ",
            "`${code || 'ERROR'}: ",
        ):
            self.assertNotIn(old, self.tutor_source, f"a raw code is concatenated in front of a sentence: {old}")
        pane = function_body(self.tutor_source, "function TutorRailPane(")
        self.assertIn("showNotice(TUTOR_FAILURE_COPY.hint, tutorFailureDetail(recorded.error))", pane)
        self.assertIn("showNotice(TUTOR_FAILURE_COPY.practice, tutorFailureDetail(response.error))", pane)
        self.assertIn("showNotice(TUTOR_FAILURE_COPY.ask, tutorFailureDetail(response.error))", pane)
        self.assertIn("data-cb-tutor-notice-detail", self.tutor_source)
        coursebook_pane = function_body(self.tutor_source, "function CoursebookPane(")
        self.assertIn("setBindNote(TUTOR_FAILURE_COPY.bind)", coursebook_pane)
        self.assertIn("setBindDetail(tutorFailureDetail(response))", coursebook_pane)
        self.assertIn("data-cb-tutor-bind-detail", coursebook_pane)
        self.assertNotIn("this chat could not be bound.'", coursebook_pane)


if __name__ == "__main__":
    unittest.main()
