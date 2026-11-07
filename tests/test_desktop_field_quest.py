"""Field Quest is the same lesson document drawn as a path of missions.

Field Quest changes the *frame*, never the teaching truth (``docs/VISUAL_MEDIA_PLAN.md`` §2, §5,
§10 Phase M2). These tests render the shipped module through React and compare it, block for
block, with Textbook and Guided: the same block ids, the same single check, the same source ids
and the same attempt surface. The mission list must not lock content, duplicate a check, invent a
badge or turn an evidence count into a mastery claim.

What this does NOT prove: that a live backend currently serves a ``field_quest`` document. It
proves the view honours whatever document it is served, including the unavailable, no-media,
unattached-check and failed-check cases.
"""

from __future__ import annotations

import copy
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

# The shared stub drops `aria-label` and `className` on Button. This suite asserts the quest's
# keyboard affordances by name, so it renders against the same stub with those two attributes
# forwarded — the real SDK passes both through.
QUEST_SDK_STUB = SDK_STUB.replace(
    """export const Button = (props) =>
  el('button', {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }, textOf(props))""",
    """export const Button = (props) =>
  el('button', {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    className: props.className || null,
    'aria-label': props['aria-label'] || null,
    'aria-expanded': props['aria-expanded'] || null,
    onClick: props.onClick
  }, textOf(props))""",
)

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  FieldQuestView,
  LessonDocumentView,
  SectionPage,
  lessonViewOptions,
  questMissions,
  questProgressLabel
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source

function checkNode(error) {
  if (error) {
    return React.createElement('div', { id: 'cb-check-node', 'data-cb-check-error': 'true' },
      'CHECK_UNAVAILABLE: The current check could not be opened.')
  }
  return React.createElement('div', { id: 'cb-check-node' }, 'CHECK-NODE')
}

let html = null
if (payload.kind === 'model') {
  const doc = payload.document
  process.stdout.write(JSON.stringify({
    missions: questMissions(doc).map((mission) => ({
      id: mission.block.id,
      index: mission.index,
      checkpoint: mission.checkpoint
    })),
    views: lessonViewOptions(doc).map((view) => view.id),
    progress: payload.summaries.map((summary) => questProgressLabel(summary))
  }))
} else if (payload.kind === 'section') {
  const row = {
    enrollment_id: 'enr_0123456789abcdef',
    profile: 'default',
    evidence_summary: payload.evidence || null
  }
  const page = {
    revision: 4,
    section: {
      objective_id: payload.document.objective_id,
      title: payload.document.section_title,
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
  html = renderToStaticMarkup(
    React.createElement(SectionPage, {
      row,
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
} else if (payload.view === 'field_quest' && payload.directQuest) {
  html = renderToStaticMarkup(
    React.createElement(FieldQuestView, {
      document: payload.document,
      sources: index,
      checkSlot: payload.withCheck === false ? null : checkNode(Boolean(payload.checkError)),
      checkLabels: payload.checkLabels || [],
      progress: payload.evidence || null,
      unattached: null,
      onOpenBlock: () => {}
    })
  )
} else {
  html = renderToStaticMarkup(
    React.createElement(LessonDocumentView, {
      document: payload.document,
      view: payload.view,
      sources: index,
      checkSlot: payload.withCheck === false ? null : checkNode(Boolean(payload.checkError)),
      checkLabels: payload.checkLabels || [],
      progress: payload.evidence || null,
      focusBlockId: payload.focusBlockId || null,
      onOpenBlock: () => {}
    })
  )
}
if (html !== null) process.stdout.write(html)
"""


def quest_document(state: str = "complete") -> dict:
    """A fresh v8 document per test.

    ``document()`` in the sibling suite hands back its ``blocks`` list by reference, so a test that
    edits a block (an unattached check, a media child) must not edit the shared fixture every other
    test renders. Deep-copying here keeps the fixture honest.
    """
    doc = document(
        guided=True,
        blocks=copy.deepcopy(COMPLETE_BLOCKS),
        check_id="chk_0123456789abcdef",
        state=state,
    )
    doc["views"] = {
        "textbook": True,
        "guided": state == "complete",
        "field_quest": state == "complete",
        "field_notes": state == "complete",
    }
    return doc


EVIDENCE = {"independent": 2, "review_due": 1, "total_objectives": 5,
            "current_objective_id": "obj_0123456789abcdef"}


class FieldQuestRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-field-quest-")
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
        (sdk / "index.js").write_text(QUEST_SDK_STUB, encoding="utf-8")
        assert "aria-label" in QUEST_SDK_STUB, "the quest suite must render against a stub that forwards aria-label"
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

    def quest(self, doc: dict | None = None, *, check_error: bool = False,
              direct: bool = False, evidence=EVIDENCE, with_check: bool = True) -> str:
        return self.render({
            "kind": "document",
            "view": "field_quest",
            "directQuest": direct,
            "withCheck": with_check,
            "checkError": check_error,
            "document": doc or quest_document(),
            "evidence": evidence,
            "sources": [
                {"source_id": "src_affection01", "title": "Affection and register — field notes"}
            ],
        })

    def other_view(self, view: str, doc: dict | None = None) -> str:
        return self.render({
            "kind": "document",
            "view": view,
            "document": doc or quest_document(),
            "sources": [
                {"source_id": "src_affection01", "title": "Affection and register — field notes"}
            ],
        })

    def section(self, doc: dict | None = None, evidence: dict | None = EVIDENCE) -> str:
        return self.render({
            "kind": "section",
            "document": doc or quest_document(),
            "evidence": evidence,
            "sources": [
                {"source_id": "src_affection01", "title": "Affection and register — field notes"}
            ],
        })

    # -- missions ------------------------------------------------------------------------------
    def test_every_block_becomes_exactly_one_mission_in_authored_order(self) -> None:
        html = self.quest()
        ids = re.findall(r'data-cb-mission="([^"]+)"', html)
        self.assertEqual(ids, [block["id"] for block in COMPLETE_BLOCKS])
        self.assertIn('data-cb-quest-missions="4"', html)
        self.assertNotIn('data-cb-mission="blk_extra', html)

    def test_missions_are_numbered_and_use_the_short_authored_prose(self) -> None:
        html = self.quest()
        self.assertIn(">01<", html)
        self.assertIn(">04<", html)
        for short in ("Short orient.", "Short explain.", "Short practice.", "Short recap."):
            self.assertEqual(html.count(short), 1, short)
        for deep in ("Deep orient prose.", "Deep explain prose.", "Deep practice prose.", "Deep recap prose."):
            self.assertNotIn(deep, html)

    def test_only_the_practice_block_is_a_checkpoint(self) -> None:
        html = self.quest()
        self.assertEqual(html.count('data-cb-mission-checkpoint="true"'), 1)
        practice = re.search(
            r'data-cb-mission="blk_practice01"[^>]*data-cb-mission-checkpoint="true"', html
        )
        self.assertIsNotNone(practice, "the checkpoint marker must sit on the practice block")
        self.assertEqual(html.count('data-cb-mission-checkpoint="false"'), 3)
        self.assertIn('data-cb-quest-checkpoints="1"', html)

    def test_the_checkpoint_carries_the_documents_own_check_id(self) -> None:
        html = self.quest()
        self.assertIn('data-cb-mission-check="chk_0123456789abcdef"', html)

    def test_the_check_node_sits_on_the_checkpoint_once(self) -> None:
        html = self.quest()
        self.assertEqual(html.count('id="cb-check-node"'), 1)
        gate = html.index('data-cb-mission-gate=')
        check = html.index('id="cb-check-node"')
        self.assertLess(gate, check)
        self.assertGreater(check, html.index('data-cb-mission="blk_practice01"'))

    # -- parity with Textbook and Guided --------------------------------------------------------
    def test_quest_and_textbook_render_the_same_block_id_set(self) -> None:
        textbook = set(re.findall(r'data-cb-block="([^"]+)"', self.other_view("textbook")))
        quest = set(re.findall(r'data-cb-mission="([^"]+)"', self.quest()))
        expected = {entry["id"] for entry in COMPLETE_BLOCKS}
        self.assertEqual(textbook, expected)
        self.assertEqual(quest, expected)

    def test_guided_renders_the_same_document_from_its_first_step(self) -> None:
        html = self.other_view("guided")
        self.assertIn("Step 1 of 4", html)
        current = re.findall(r'data-cb-block="([^"]+)"', html)
        self.assertEqual(current, [COMPLETE_BLOCKS[0]["id"]])
        self.assertIn("Short orient.", html)
        self.assertNotIn("Short explain.", html)

    def test_textbook_and_quest_render_exactly_one_check_node(self) -> None:
        for view in ("textbook", "field_quest"):
            html = self.quest() if view == "field_quest" else self.other_view(view)
            self.assertEqual(html.count('id="cb-check-node"'), 1, view)

    def test_guided_holds_the_check_only_on_the_checkpoint_step(self) -> None:
        # Guided renders one block at a time; its first step is the orient block, which carries no
        # check, so the single check node is not on screen yet. The checkpoint step is exercised
        # live by scripts/m2fq-frames.py.
        html = self.other_view("guided")
        self.assertNotIn('id="cb-check-node"', html)
        doc = quest_document()
        self.assertEqual([b["id"] for b in doc["blocks"] if b["check_id"]], ["blk_practice01"])

    def test_the_quest_keeps_the_documents_source_id(self) -> None:
        html = self.quest()
        self.assertIn("Affection and register — field notes", html)
        self.assertEqual(html.count("Affection and register — field notes"), 1)

    def test_the_same_document_id_and_view_marker_ship_in_quest(self) -> None:
        html = self.quest()
        self.assertIn('data-cb-lesson-view="field_quest"', html)
        self.assertIn('data-cb-document="doc_0123456789abcdef0123"', html)

    # -- no evidence game ----------------------------------------------------------------------
    def test_progress_is_a_descriptive_count_not_a_mastery_claim(self) -> None:
        html = self.quest()
        self.assertIn('data-cb-quest-progress="2 independent · 1 due"', html)
        self.assertIn("2 independent · 1 due", html)
        lowered = html.lower()
        for banned in ("mastery", "mastered", "streak", "level up", " xp", "points earned"):
            self.assertNotIn(banned, lowered, banned)

    def test_no_mission_is_locked_or_disabled(self) -> None:
        html = self.quest()
        self.assertNotIn("disabled", html)
        self.assertEqual(html.count("Read in Textbook"), len(COMPLETE_BLOCKS))

    def test_a_course_without_recorded_objectives_says_so(self) -> None:
        html = self.quest(evidence={"independent": 0, "review_due": 0, "total_objectives": 0})
        self.assertIn("No objectives recorded yet", html)
        self.assertNotIn("0 independent", html)

    def test_missing_evidence_summary_is_not_rendered_as_zero(self) -> None:
        html = self.quest(evidence=None)
        self.assertIn("Progress not recorded", html)
        self.assertNotIn("0 independent", html)

    # -- honest gates --------------------------------------------------------------------------
    def test_a_failed_check_keeps_every_mission_readable(self) -> None:
        html = self.quest(check_error=True)
        self.assertIn("CHECK_UNAVAILABLE", html)
        for short in ("Short orient.", "Short explain.", "Short practice.", "Short recap."):
            self.assertIn(short, html)
        self.assertNotIn("disabled", html)

    def test_an_unattached_check_says_the_checkpoint_is_ungated(self) -> None:
        # The document declares a checkpoint, but the check read produced no node for it: the
        # mission stays fully readable and says the gate is missing rather than locking itself.
        html = self.quest(direct=True, with_check=False)
        self.assertIn("stays readable and ungated", html)
        self.assertIn('data-cb-quest-checkpoints="1"', html)
        for short in ("Short orient.", "Short explain.", "Short practice.", "Short recap."):
            self.assertIn(short, html)

    # -- media and motion ----------------------------------------------------------------------
    def test_no_media_blocks_still_render_the_mission_text(self) -> None:
        html = self.quest()
        self.assertNotIn("data-cb-block-media", html)
        self.assertIn("Short explain.", html)

    def test_a_media_child_keeps_its_text_equivalent(self) -> None:
        doc = quest_document()
        doc["blocks"][1]["media"] = [{
            "kind": "visual",
            "role": "illustration",
            "artifact_id": "art_0123456789abcdef",
            "purpose": "A shelf with two labelled jars.",
            "text_equivalent": "A shelf with two labelled jars, warm on the left.",
            "label": "Kitchen shelf",
            "degraded": False,
            "reason": None,
        }]
        html = self.quest(doc)
        self.assertEqual(html.count("data-cb-block-media"), 1)
        self.assertIn("A shelf with two labelled jars, warm on the left.", html)

    def test_the_quest_ships_static_motion_and_says_which_preference_it_read(self) -> None:
        html = self.quest()
        self.assertIn('data-cb-motion="full"', html)
        self.assertNotIn("transition", html.lower())
        self.assertNotIn("animation", html.lower())

    # -- keyboard ------------------------------------------------------------------------------
    def test_each_mission_offers_a_named_keyboard_target(self) -> None:
        html = self.quest()
        labels = re.findall(r'aria-label="(Read mission [^"]+)"', html)
        self.assertEqual(len(labels), len(COMPLETE_BLOCKS))
        self.assertIn("Read mission 3, Try it, in Textbook", labels)
        for label in labels:
            self.assertIn("in Textbook", label)

    def test_the_textbook_block_is_focusable_for_the_handoff(self) -> None:
        html = self.other_view("textbook")
        self.assertEqual(html.count('tabindex="-1"'), len(COMPLETE_BLOCKS))

    # -- the switcher ---------------------------------------------------------------------------
    def test_the_section_page_offers_all_three_views_when_quest_is_available(self) -> None:
        html = self.section()
        self.assertIn('data-cb-view-options="textbook guided field_quest"', html)
        self.assertIn('data-cb-view-switcher="available"', html)
        self.assertIn("Field Quest", html)

    def test_a_textbook_only_section_never_offers_quest(self) -> None:
        doc = quest_document(state="textbook_only")
        doc["blocks"] = [
            block("blk_orient0001", "orient", "Start here", short=None, deep="Deep orient prose.")
        ]
        html = self.section(doc)
        self.assertIn('data-cb-view-options="textbook"', html)
        self.assertIn("Textbook only", html)
        self.assertNotIn("Field Quest", html)

    def test_asking_for_quest_without_quest_falls_back_to_textbook(self) -> None:
        doc = quest_document(state="textbook_only")
        html = self.quest(doc, evidence=None)
        self.assertIn('data-cb-lesson-view="textbook"', html)
        self.assertNotIn('data-cb-lesson-view="field_quest"', html)

    def test_a_guided_only_document_offers_two_views_and_no_quest(self) -> None:
        doc = quest_document()
        doc["views"]["field_quest"] = False
        html = self.section(doc)
        self.assertIn('data-cb-view-options="textbook guided"', html)
        self.assertNotIn("field_quest", html)


class FieldQuestModelTest(FieldQuestRenderTest):
    """The pure projection: what a mission is, and what a progress string may say."""

    def model(self, doc: dict | None = None) -> dict:
        return json.loads(self.render({
            "kind": "model",
            "document": doc or quest_document(),
            "summaries": [
                {"independent": 2, "review_due": 1, "total_objectives": 5},
                {"independent": 0, "review_due": 0, "total_objectives": 0},
                None,
                {"independent": 3, "review_due": 0, "total_objectives": 3},
            ],
        }))

    def test_mission_brief_is_a_pointer_and_keyboard_target(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        mission = source.split("function QuestMission(", 1)[1].split("\nfunction FieldQuestView(", 1)[0]
        self.assertIn("onClick: openMission", mission)
        self.assertIn("onKeyDown: openMissionOnKey", mission)
        self.assertIn("role: 'link'", mission)
        self.assertIn("target.closest('button, a, input, textarea, select", mission)

    def test_model_lists_one_mission_per_block(self) -> None:
        model = self.model()
        self.assertEqual([mission["id"] for mission in model["missions"]],
                         [entry["id"] for entry in COMPLETE_BLOCKS])
        self.assertEqual([mission["index"] for mission in model["missions"]], [0, 1, 2, 3])

    def test_model_marks_only_the_check_attached_block(self) -> None:
        model = self.model()
        self.assertEqual([m["id"] for m in model["missions"] if m["checkpoint"]], ["blk_practice01"])

    def test_model_reports_the_views_the_document_supports(self) -> None:
        self.assertEqual(self.model()["views"], ["textbook", "guided", "field_quest"])
        doc = quest_document(state="textbook_only")
        doc["blocks"] = [block("blk_orient0001", "orient", "Start", short=None, deep="Deep.")]
        self.assertEqual(self.model(doc)["views"], ["textbook"])

    def test_progress_strings_are_descriptive_and_never_invented(self) -> None:
        self.assertEqual(
            self.model()["progress"],
            ["2 independent · 1 due", "No objectives recorded yet", "Progress not recorded",
             "3 independent · 0 due"],
        )


if __name__ == "__main__":
    unittest.main()
