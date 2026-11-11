"""CP-025a — the GM-008 and GM-010 surfaces rebuilt on the v3 contract.

Two kinds of proof:

* source scope: the Game header/journal region of `desktop/src/30-home.js` and the homework region
  of `desktop/src/95-studio.js` read the v3 contract only (`cb3Role`/`cb3Type`/`cb3Lead`/`cb3Radius`
  or `var(--cb3-*)`), call no v2 token variable, no v2 reader, no host `sdk.Button`/`CbAction`/
  `sdk.Badge`, and carry no raw colour, gradient, shadow or `vw` value;
* rendered DOM: the shipped module paints the same honest markers the GM-008/GM-010 contracts pin
  (`data-cb-game*`, `data-cb-homework*`) from the v3 card/action primitives, with one quiet action
  on the homework panel, one progress bar in the Game band, one paper object for the journal, and
  stamps only where `objective.independent` is true.

Pixels: this card carries eleven live frames in `docs/visual-review/cp-025a/`, each with its
`scripts/cp-capture.mjs` stamp pinning the module sha under review, and the cells they prove are
listed in that folder's `MANIFEST.md`. They are the Game band/journal and the homework studio,
sheet and narrow sheet — not the full parity matrix: the union capture across every route and
state still belongs to CP-040.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_gm010_engagement_ui import GM010_SDK_STUB
from tests.test_desktop_lesson_views import _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
HOME_SRC = ROOT / "desktop" / "src" / "30-home.js"
STUDIO_SRC = ROOT / "desktop" / "src" / "95-studio.js"
SCOPE_SRC = ROOT / "desktop" / "src" / "76-v3-scope.js"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import {
  GameHeader,
  GameJournal,
  TakeThisWithYou,
  HomeworkSheetCard,
  HomeworkRecordList
} from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const quiet = () => {}
const out = (node) => process.stdout.write(renderToStaticMarkup(node))
const methods = new Set([
  'homework.create', 'homework.read', 'homework.complete', 'homework.skip', 'notebook.save'
])

if (payload.kind === 'header') {
  out(React.createElement(GameHeader, {
    engagement: payload.engagement,
    status: payload.status || 'ready',
    error: payload.error || null,
    prefs: payload.prefs || {},
    onRetry: quiet
  }))
} else if (payload.kind === 'journal') {
  out(React.createElement(GameJournal, { objectives: payload.objectives || [] }))
} else if (payload.kind === 'action') {
  out(React.createElement(TakeThisWithYou, {
    enrollmentId: 'enr_1',
    courseId: 'crs_1',
    objectiveId: 'obj_1',
    sectionTitle: 'Say the before-meal greeting',
    implemented: methods,
    onChanged: quiet
  }))
} else if (payload.kind === 'sheet') {
  out(React.createElement(HomeworkSheetCard, { task: payload.task }))
} else if (payload.kind === 'list') {
  out(React.createElement(HomeworkRecordList, {
    rows: payload.rows || [],
    actor: 'learner',
    canSave: false,
    emptyTitle: 'No homework yet',
    emptyDescription: 'A task you take with you is listed here.'
  }))
}
"""


def engagement() -> dict:
    return {
        "xp_total": 245,
        "level": {
            "level": 3,
            "title": "Pathfinder",
            "xp_into_level": 45,
            "xp_for_next_level": 100,
            "is_cosmetic": True,
        },
        "progress": {
            "label": "Game progress",
            "is_play_progress": True,
            "assigned_steps": 8,
            "completed_steps": 5,
            "feedback_visible": True,
        },
        "recent_events": [],
    }


def objective(objective_id: str, ordinal: int, state: str, independent: bool) -> dict:
    return {
        "objective_id": objective_id,
        "title": f"Section {ordinal} title",
        "ordinal": ordinal,
        "state": state,
        "independent": independent,
    }


OBJECTIVES = [
    objective("obj_0000000000000001", 1, "independent_evidence", True),
    objective("obj_0000000000000002", 2, "independent_evidence", True),
    objective("obj_0000000000000003", 3, "introduced", False),
    objective("obj_0000000000000004", 4, "not_started", False),
]

TASK = {
    "task_id": "hwt_cp025a",
    "revision": 2,
    "state": "proposed",
    "title": "Say it before dinner",
    "task_kind": "practice",
    "estimated_minutes": 5,
    "context": "At your own table, just before you eat today.",
    "success_criterion": "You say it once and someone answers.",
    "steps": ["Look at the line.", "Say it out loud.", "Notice the answer."],
    "target": {
        "kind": "single",
        "display": "いただきます",
        "reading": "いただきます",
        "romaji": "itadakimasu",
        "meaning": "I receive this meal.",
        "completion_record": [],
    },
    "sources": [],
    "completion": {"basis": None, "completed_at": None, "independent_verification": False},
    "sheet": {"pages": 1, "html": "<article class=\"sheet\">x</article>", "text": ""},
}


class _Rig:
    def __init__(self) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        self.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp025a-")
        self.root = Path(self.tmp.name)
        (self.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "static.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = self.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(GM010_SDK_STUB, encoding="utf-8")

    def render(self, payload: dict) -> str:
        import subprocess

        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "static.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-4000:])
        return result.stdout


_RIG: _Rig | None = None


def render(payload: dict) -> str:
    global _RIG
    if _RIG is None:
        _RIG = _Rig()
    return _RIG.render(payload)


def flat(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def slice_between(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    stop = text.index(end, begin)
    return text[begin:stop]


# The two regions this card rebuilt, named by the functions they own.


class Cp025aV3SurfacesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")
        cls.home = HOME_SRC.read_text(encoding="utf-8")
        cls.studio = STUDIO_SRC.read_text(encoding="utf-8")
        cls.scope = SCOPE_SRC.read_text(encoding="utf-8")
        cls.game_region = slice_between(cls.home, "function GameHeader(", "\n/**\n * Collectible section cards")
        cls.game_journal = cls.home[cls.home.index("function GameJournal("):]
        cls.homework_region = slice_between(cls.studio, "function HomeworkSheetCard(", "function StudioBriefForm(")
        role_block = re.search(r"CB3_V3_ROLES = Object\.freeze\(\[(.*?)\]\)", cls.scope, re.S)
        step_block = re.search(r"CB3_V3_TYPE_STEPS = Object\.freeze\(\[(.*?)\]\)", cls.scope)
        assert role_block is not None and step_block is not None, "v3 scope constants not found"
        cls.roles = set(re.findall(r'"([a-z-]+)"', role_block.group(1)))
        cls.steps = set(re.findall(r"'([a-z]+)'", step_block.group(1)))

    # ── source scope ───────────────────────────────────────────────────────────

    def assert_v3_only(self, region: str, label: str, *, action: bool = True) -> None:
        v2_readers = ("CB_TYPE.", "CB_SANS", "CB_SERIF", "CB_MONO", "CB_MEASURE")
        for reader in v2_readers:
            # CB_MEASURE is a reading width, not a token: it is allowed and deliberately excluded.
            if reader == "CB_MEASURE":
                continue
            self.assertNotIn(reader, region, f"{label} reads a v2 type token: {reader}")
        for host in ("sdk.Button", "CbAction", "sdk.Badge", "sdk.SegmentedControl"):
            self.assertNotIn(host, region, f"{label} uses the v2 host control: {host}")
        self.assertIsNone(re.search(r"var\(--cb-(?!3)", region), f"{label} reads a v2 token variable")
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", region), f"{label} carries a raw colour")
        self.assertIsNone(re.search(r"rgba?\(", region), f"{label} carries a raw colour function")
        for banned in ("gradient(", "boxShadow", "textShadow", "backdropFilter", "vw"):
            self.assertNotIn(banned, region, f"{label} carries {banned}")
        self.assertIn("cb3Role(", region, f"{label} paints no v3 role")
        self.assertIn("cb3Type(", region, f"{label} uses no v3 type step")
        if action:
            self.assertIn("PillAction", region, f"{label} does not use the v3 action primitive")

    def test_game_surfaces_read_the_v3_contract_only(self) -> None:
        self.assert_v3_only(self.game_region, "GameHeader")
        self.assert_v3_only(self.game_journal, "GameJournal", action=False)
        self.assertIn("PaperCard", self.game_journal, "the journal must be one paper object")
        self.assertIsNone(re.search(r"engagement\.award", self.game_region))

        # Every role and step it names exists in the v3 contract; nothing is invented locally.
        named_roles = set(re.findall(r"cb3Role\('([a-z-]+)'\)", self.game_region + self.game_journal))
        self.assertTrue(named_roles, "the game surfaces name no role")
        self.assertTrue(named_roles <= self.roles, f"unknown roles: {sorted(named_roles - self.roles)}")
        named_steps = set(re.findall(r"cb3Type\('([a-z]+)'\)", self.game_region + self.game_journal))
        self.assertTrue(named_steps and named_steps <= self.steps, f"unknown steps: {sorted(named_steps - self.steps)}")

    def test_homework_surfaces_read_the_v3_contract_only(self) -> None:
        self.assert_v3_only(self.homework_region, "the homework surfaces")
        for marker in (
            "'data-cb3-homework': 'sheet'",
            "'data-cb3-homework': 'actions'",
            "'data-cb3-homework': 'action'",
            "'data-cb3-homework': 'record'",
            "'data-cb3-homework': 'list'",
            "'data-cb3-homework': 'studio'",
        ):
            self.assertIn(marker, self.homework_region, f"missing v3 marker {marker}")
        named_roles = set(re.findall(r"cb3Role\('([a-z-]+)'\)", self.homework_region))
        self.assertTrue(named_roles <= self.roles, f"unknown roles: {sorted(named_roles - self.roles)}")
        named_steps = set(re.findall(r"cb3Type\('([a-z]+)'\)", self.homework_region))
        self.assertTrue(named_steps <= self.steps, f"unknown steps: {sorted(named_steps - self.steps)}")
        # The sheet's actions are the three quiet doors, never a filled control.
        actions = slice_between(self.homework_region, "function HomeworkSheetActions(", "/**\n * The quiet `Take this with you`")
        self.assertEqual(actions.count("variant: 'quiet'"), 3)
        self.assertNotIn("'primary'", actions)

    # ── the rendered Game band ─────────────────────────────────────────────────

    def test_game_header_keeps_the_honesty_contract(self) -> None:
        html = render({"kind": "header", "engagement": engagement()})
        self.assertIn('data-cb-game="ready"', html)
        self.assertIn('data-cb3-game="header"', html)
        self.assertIn('data-cb3-chip="xp"', html)
        self.assertIn("245 XP", html)
        self.assertIn("Game progress", html)
        self.assertIn("Play progress, not evidence.", html)
        self.assertIn("cosmetic", html)
        self.assertIn("5 of 8 steps", html)
        self.assertEqual(html.count('role="progressbar"'), 1)
        self.assertIn('aria-valuenow="5"', html)
        self.assertIn('aria-valuemax="8"', html)
        # The band owns no primary: the surface's one filled control lives with Continue.
        self.assertNotIn('data-cb3-pill="primary"', html)
        lowered = html.lower()
        for forbidden in ("mastery", "mastered", "proficien", "verified skill", "skill level", "grade", "score", "star"):
            self.assertNotIn(forbidden, lowered, f"the play layer must not claim {forbidden!r}")
        self.assertIsNone(re.search(r"var\(--cb-(?!3)", html), "the header painted a v2 token")

        zero = engagement()
        zero["progress"] = {**zero["progress"], "assigned_steps": 0, "completed_steps": 0}
        empty = render({"kind": "header", "engagement": zero})
        self.assertIn("No steps assigned yet", empty)
        self.assertNotIn("progressbar", empty)

        over = engagement()
        over["progress"] = {**over["progress"], "assigned_steps": 3, "completed_steps": 7}
        capped = render({"kind": "header", "engagement": over})
        self.assertIn('aria-valuenow="3"', capped)
        self.assertIn("3 of 3 steps", capped)

    def test_game_header_states_keep_the_band(self) -> None:
        loading = render({"kind": "header", "engagement": None, "status": "loading"})
        self.assertIn('data-cb3-game="loading"', loading)
        self.assertIn("Reading the field journal", loading)
        error = render({"kind": "header", "engagement": None, "status": "error", "error": {"message": "offline"}})
        self.assertIn('data-cb3-game="error"', error)
        self.assertIn("Try again", error)
        self.assertIn('data-cb3-pill="quiet"', error)

    def test_game_journal_is_one_paper_object_with_real_stamps(self) -> None:
        html = render({"kind": "journal", "objectives": OBJECTIVES})
        self.assertIn('data-cb3-game="journal"', html)
        self.assertEqual(html.count('data-cb3-card="paper"'), 1, "the journal is one paper object")
        self.assertEqual(html.count("data-cb-game-card="), len(OBJECTIVES))
        self.assertEqual(html.count('data-cb-game-card="earned"'), 2)
        self.assertEqual(html.count('data-cb3-chip="stamped"'), 2)
        self.assertEqual(html.count(">Stamped<"), 2)
        self.assertIn('data-cb-game-journal="2"', html)
        self.assertIn("2 of 4 sections stamped by recorded evidence.", html)
        self.assertIn("Started", html)
        self.assertIn("Not started", html)
        self.assertNotIn("★", html)
        self.assertNotIn("☆", html)

    # ── the rendered homework surfaces ────────────────────────────────────────

    def test_homework_action_is_one_quiet_control(self) -> None:
        html = render({"kind": "action"})
        self.assertIn('data-cb3-homework="action"', html)
        self.assertIn('data-cb-homework-action="take-this-with-you"', html)
        self.assertIn('data-cb3-pill="quiet"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('data-variant="text"', html)
        self.assertNotIn('role="dialog"', html)
        self.assertNotIn('data-cb3-pill="primary"', html)
        self.assertIn("Take this with you", html)

    def test_homework_sheet_keeps_one_task_and_the_v3_material(self) -> None:
        html = render({"kind": "sheet", "task": TASK})
        self.assertIn('data-cb3-homework="sheet"', html)
        self.assertEqual(html.count("data-cb-homework-target="), 1)
        self.assertEqual(html.count("data-cb-homework-context="), 1)
        self.assertEqual(html.count("<ol"), 1)
        self.assertLessEqual(html.count("<li"), 3)
        self.assertEqual(html.count("Done when"), 1)
        self.assertIn("Coursebook field card", html)
        self.assertIn("About 5 minutes", html)
        self.assertIn('lang="ja"', html)
        self.assertIn("itadakimasu", html)
        self.assertNotIn('data-cb3-pill="primary"', html)
        self.assertIsNone(re.search(r"var\(--cb-(?!3)", html), "the sheet painted a v2 token")
        self.assertIn("data-cb-homework-state=\"proposed\"", html)
        # Nothing in a take-home card is graded or played: no XP, no score, no mastery claim.
        lowered = html.lower()
        for forbidden in (" xp", "xp ", ">xp<", "grade", "score", "mastery", "mastered", "star"):
            self.assertNotIn(forbidden, lowered, f"the sheet leaked {forbidden!r}")

    def test_homework_list_empty_state_is_authored(self) -> None:
        html = render({"kind": "list", "rows": []})
        self.assertIn('data-cb-homework-list="empty"', html)
        self.assertIn('data-cb3-homework="list-empty"', html)
        self.assertIn("No homework yet", html)

    def test_studio_and_notebook_lists_carry_v3_markers(self) -> None:
        # HomeworkStudio is mounted from the page segment; its marker and the list's are pinned in
        # source because both read backend state through rpc (no fixture stands in for it here).
        self.assertIn("'data-cb-homework-studio': String(rows.length)", self.homework_region)
        self.assertIn("'data-cb-homework-list': 'empty'", self.homework_region)
        self.assertIn("'data-cb-homework-record-state': task.state", self.homework_region)


if __name__ == "__main__":
    unittest.main()
