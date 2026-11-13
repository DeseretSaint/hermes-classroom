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


if __name__ == "__main__":
    unittest.main()
