"""H-149: the lesson is a player, not a document.

One concept, one response, one footer, one close. These tests render the shipped runtime module with
``react-dom/server`` and the same SDK stub the other desktop render suites use, so what they assert
is the component the Desktop actually mounts — not a description of it.

What they do not prove: that a live backend authors a section with more than one block, or that a
graded verdict is reachable without a check service. The live capture (``scripts/h149-capture.mjs``)
proves the mounted surface and its geometry; this suite proves the states.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import (
    COMPLETE_BLOCKS,
    SDK_STUB,
    _desktop_node_modules,
    block,
    document,
)

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { LessonPlayer, PlayerVerdict, PlayerClose, SectionPage, playerSteps, playerCheckCount, playerConcept } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source
const checkNode = React.createElement('div', { id: 'cb-check-node' }, 'CHECK-NODE')

let out
if (payload.kind === 'section') {
  const page = {
    revision: 4,
    section: {
      objective_id: payload.document.objective_id,
      title: payload.document.section_title,
      ordinal: 2,
      state: 'needs_review',
      evidence_target: 'discrimination',
      last_opened_at: null
    },
    runtime: { lesson_run_id: 'run_1', binding_id: null, binding_status: 'detached', session_state: 'stored_only' },
    segments: [],
    attempts: [],
    notebook_entries: [],
    sources: payload.sources || [],
    document: payload.document
  }
  out = renderToStaticMarkup(
    React.createElement(SectionPage, {
      row: {
        enrollment_id: 'enr_0123456789abcdef',
        profile: 'default',
        title: 'Japanese L0',
        evidence_summary: { total_objectives: 4, independent: 2, review_due: 1 }
      },
      objectiveId: payload.document.objective_id,
      page,
      pageStatus: 'ready',
      pageError: null,
      onRetryPage: () => {},
      implemented: new Set(['check.open', 'artifact.get', 'notebook.save']),
      onBack: () => {},
      onChanged: () => {},
      review: null
    })
  )
} else if (payload.kind === 'player') {
  out = renderToStaticMarkup(
    React.createElement(LessonPlayer, {
      document: payload.document,
      sources: index,
      checkSlot: checkNode,
      checkLabels: payload.checkLabels || [],
      section: { objective_id: payload.document.objective_id, title: payload.document.section_title, ordinal: 2, evidence_target: 'discrimination' },
      progress: payload.progress || { total_objectives: 4, independent: 2, review_due: 1 },
      playerState: payload.playerState || { phase: 'awaiting_input', canCheck: false, verdict: null },
      playerController: { current: null },
      onExit: () => {},
      onSaveBlock: null,
      pronunciation: null
    })
  )
} else if (payload.kind === 'verdict') {
  out = renderToStaticMarkup(
    React.createElement(PlayerVerdict, {
      result: payload.result,
      criteria: payload.criteria || [],
      checklist: payload.checklist || [],
      answer: payload.answer || ''
    })
  )
} else if (payload.kind === 'close') {
  out = renderToStaticMarkup(
    React.createElement(PlayerClose, {
      section: { ordinal: payload.ordinal === undefined ? 2 : payload.ordinal },
      progress: payload.progress || {},
      onBack: () => {}
    })
  )
} else {
  out = JSON.stringify({
    steps: playerSteps(payload.document).map((step) => ({ id: step.block.id, check: step.check })),
    checks: playerCheckCount(payload.document),
    concept: playerConcept(payload.document.blocks[0], payload.checkLabels || [])
  })
}
process.stdout.write(out)
"""


class H149RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h149-")
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

    def render(self, payload: dict) -> str:
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

    def sources(self) -> list[dict]:
        return [{"source_id": "src_affection01", "title": "Affection and register — field notes"}]

    def section(self, doc: dict) -> str:
        return self.render({"kind": "section", "document": doc, "sources": self.sources()})

    def player(self, doc: dict, **extra) -> str:
        payload = {"kind": "player", "document": doc, "sources": self.sources()}
        payload.update(extra)
        return self.render(payload)


class PlayerSurfaceTest(H149RenderTest):
    """Q1/Q2: the section opens on a session with one obvious next move and a named place."""

    def test_the_section_page_defaults_to_the_player(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        html = self.section(doc)
        self.assertIn('data-cb-lesson-view="player"', html)
        self.assertIn('data-cb-player-bar', html)

    def test_the_field_stop_header_names_the_stop_the_title_and_the_step(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        # U6: four blocks in this lesson, six sections in the course. The header counts sections
        # (the course total), the readout counts this lesson's blocks; the two must not collide,
        # so this fixture keeps them different.
        html = self.player(doc, progress={"total_objectives": 6, "independent": 2, "review_due": 1})
        self.assertIn('data-cb-player-stop="2/6"', html)
        self.assertIn("Section 2 of 6", html)
        self.assertNotIn("Section 2 of 4", html, "the section label used the lesson's block count")
        self.assertIn('data-cb-player-title=""', html)
        self.assertIn("Affection and register", html)
        self.assertIn('data-cb-player-objective=""', html)
        self.assertIn("By the end of this stop you can show: tell the difference.", html)
        # H-178: the course metadata strip and the check-count strip are gone from the stop.
        self.assertNotIn("1 check in this section", html)
        self.assertNotIn("data-cb-player-check-count", html)
        self.assertIn('data-cb-player-mode="game"', html)
        self.assertIn("Step 1 of 4", html)
        self.assertIn('data-cb-player-exit=""', html)
        self.assertIn(">Exit<", html)

    def test_one_concept_per_step(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        html = self.player(doc)
        self.assertIn("Short orient.", html)
        for other in ("Short explain.", "Short practice.", "Short recap.",
                      "Deep orient prose.", "Deep explain prose."):
            self.assertNotIn(other, html)
        self.assertEqual(html.count("data-cb-player-step-block="), 1)

    def test_the_step_says_which_check_it_carries(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        model = json.loads(self.render({"kind": "model", "document": doc}))
        self.assertEqual(model["checks"], 1)
        self.assertEqual([step["id"] for step in model["steps"] if step["check"]], ["blk_practice01"])
        self.assertEqual(len(model["steps"]), 4)

    def test_the_concept_is_the_authored_short_prose_whole(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        model = json.loads(self.render({"kind": "model", "document": doc}))
        self.assertEqual(model["concept"], {"text": "Short orient.", "clipped": False})

    def test_deep_only_prose_is_clipped_and_the_clip_is_declared(self) -> None:
        blocks = [
            block("blk_orient0001", "orient", "Start here", short=None,
                  deep="First paragraph of the concept.\n\nSecond paragraph that must not fill the step."),
        ]
        doc = document(guided=False, blocks=blocks, check_id=None, state="textbook_only")
        model = json.loads(self.render({"kind": "model", "document": doc}))
        self.assertEqual(model["concept"]["text"], "First paragraph of the concept.")
        self.assertTrue(model["concept"]["clipped"])
        html = self.player(doc)
        self.assertIn("The full text is in Textbook.", html)
        self.assertNotIn("Second paragraph", html)

    def test_the_unattached_check_still_lands_on_the_last_step(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_not_on_a_block")
        model = json.loads(self.render({"kind": "model", "document": doc}))
        self.assertEqual([step["id"] for step in model["steps"] if step["check"]], ["blk_recap00001"])


class PlayerFooterTest(H149RenderTest):
    """Q1: one primary, one footer, Check becoming Continue."""

    def test_the_player_has_exactly_one_footer_primary(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        html = self.section(doc)
        self.assertEqual(html.count("data-cb-player-footer"), 1)
        self.assertEqual(html.count("data-cb-section-footer"), 0)
        primaries = re.findall(r"<button[^>]*data-variant=\"default\"", html)
        self.assertEqual(len(primaries), 1, primaries)
        self.assertIn('data-cb-player-primary="Continue"', html)

    def test_the_chat_action_is_demoted_while_the_player_is_on_screen(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        html = self.section(doc)
        self.assertIn('data-cb-section-primary="secondary"', html)

    def test_the_check_step_labels_the_primary_check(self) -> None:
        blocks = [COMPLETE_BLOCKS[2], COMPLETE_BLOCKS[0]]
        doc = document(guided=True, blocks=blocks, check_id="chk_0123456789abcdef")
        html = self.player(doc)
        self.assertIn('data-cb-player-primary="Check"', html)
        self.assertIn('disabled=""', html)  # nothing typed yet

    def test_a_graded_pass_turns_the_primary_into_continue(self) -> None:
        blocks = [COMPLETE_BLOCKS[2], COMPLETE_BLOCKS[0]]
        doc = document(guided=True, blocks=blocks, check_id="chk_0123456789abcdef")
        html = self.player(doc, playerState={"phase": "graded", "canCheck": False, "verdict": "pass"})
        self.assertIn('data-cb-player-primary="Continue"', html)

    def test_a_miss_offers_a_free_retry(self) -> None:
        blocks = [COMPLETE_BLOCKS[2], COMPLETE_BLOCKS[0]]
        doc = document(guided=True, blocks=blocks, check_id="chk_0123456789abcdef")
        html = self.player(doc, playerState={"phase": "graded", "canCheck": False, "verdict": "fail"})
        self.assertIn('data-cb-player-primary="Try again"', html)

    def test_enter_runs_the_footer_action_and_textareas_keep_enter(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        player = source.split("function LessonPlayer(", 1)[1].split("\nfunction LessonDocumentView(", 1)[0]
        self.assertIn("event.key !== 'Enter'", player)
        # Item 40: the exclusion list also keeps Enter for links, summaries and role-buttons.
        self.assertIn("'button, a[href], summary, [role=\"button\"], textarea, input, select, [contenteditable=\"true\"]'", player)


class PlayerVerdictTest(H149RenderTest):
    """Q6: immediate corrective feedback as words, with the learner's answer in context."""

    def verdict(self, result: dict, criteria: list[dict], answer: str = "") -> str:
        return self.render({"kind": "verdict", "result": result, "criteria": criteria, "answer": answer})

    def test_correct_prints_the_word_the_answer_and_the_reason(self) -> None:
        html = self.verdict(
            {"verdict": "pass", "evidence_class": "independent", "next_action": "complete_objective"},
            [{"id": "c1", "met": True, "observed": "chose the plain form"}],
            answer="plain form",
        )
        self.assertIn("Correct", html)
        self.assertIn("You answered:", html)
        self.assertIn("plain form", html)
        self.assertIn("What you showed: chose the plain form.", html)
        self.assertIn('data-cb-player-feedback="correct"', html)

    def test_not_quite_names_the_rule_that_did_not_hold(self) -> None:
        html = self.verdict(
            {"verdict": "fail", "evidence_class": "independent", "next_action": "retry_attempt"},
            [
                {"id": "c1", "met": True, "observed": "used the right register"},
                {"id": "c2", "met": False, "observed": "the polite form was applied to a casual question"},
            ],
            answer="kudasai",
        )
        self.assertIn("Not quite", html)
        self.assertIn("kudasai", html)
        self.assertIn("The part that did not hold: the polite form was applied to a casual question", html)
        self.assertIn("What you did show: used the right register.", html)
        self.assertIn("retry is free", html)
        self.assertIn('data-cb-player-feedback="not_quite"', html)

    def test_a_verdict_never_prints_a_score_or_a_percentage(self) -> None:
        html = self.verdict(
            {"verdict": "fail", "evidence_class": "independent", "next_action": "retry_attempt"},
            [{"id": "c1", "met": False, "observed": "the rule was reversed"}],
            answer="x",
        )
        for word in ("%", "XP", "streak", "score", "level", "mastered"):
            self.assertNotIn(word, html)


class PlayerCloseTest(H149RenderTest):
    """Q12: the session ends on the real recorded count, one next action, no reward."""

    def test_close_names_the_section_and_the_real_counts(self) -> None:
        html = self.render({"kind": "close", "ordinal": 2,
                            "progress": {"total_objectives": 4, "independent": 2, "review_due": 1}})
        self.assertIn("You finished Section 2", html)
        self.assertIn("2 of 4 with independent evidence", html)
        self.assertIn("1 to review", html)
        self.assertIn("Return to the trail", html)
        self.assertEqual(html.count('data-variant="default"'), 1)
        for word in ("%", "XP", "streak", "confetti", "score"):
            self.assertNotIn(word, html)

    def test_close_says_nothing_due_rather_than_inventing_a_review(self) -> None:
        html = self.render({"kind": "close", "ordinal": 3,
                            "progress": {"total_objectives": 3, "independent": 3, "review_due": 0}})
        self.assertIn("Nothing due for review", html)
        self.assertNotIn("0 due", html)

    def test_close_without_a_recorded_total_claims_no_count(self) -> None:
        html = self.render({"kind": "close", "ordinal": 1, "progress": {}})
        # Item 39: a close with no recorded evidence says so instead of claiming a result.
        self.assertIn("Nothing was recorded for this stop.", html)
        self.assertNotIn("The result is recorded on this profile.", html)
        self.assertNotIn("with evidence", html)


class PlayerHonestyTest(unittest.TestCase):
    """Source-level invariants the render cannot see."""

    def setUp(self) -> None:
        self.source = PLUGIN_JS.read_text(encoding="utf-8")

    def player_source(self) -> str:
        return self.source.split("H-149 · the lesson player", 1)[1].split("\nfunction LessonDocumentView(", 1)[0]

    def test_the_player_invents_no_gamified_mechanic(self) -> None:
        player = self.player_source()
        for word in ("XP", "streak", "percent", "confetti", "mastery", "league", "score"):
            self.assertNotIn(word, player, word)

    def test_the_player_carries_no_animation_of_its_own(self) -> None:
        player = self.player_source()
        self.assertNotIn("animation", player)
        self.assertNotIn("transition", player)
        self.assertNotIn("@keyframes", player)

    def test_the_textbook_view_stays_available(self) -> None:
        self.assertIn("{ id: 'textbook', label: 'Textbook' }", self.source)
        self.assertIn("{ id: 'player', label: 'Game' }", self.source)


if __name__ == "__main__":
    unittest.main()
