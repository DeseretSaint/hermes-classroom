"""CP-023 — the v3 classroom (R-CLASS), rendered rather than read.

The card's contract, in executable form (`docs/concept-parity/SPEC-V3.md` §5.3):

* one filled control: `Check answer` in the check card, and **never** a second fill (the served
  options are radios/checkboxes, `Play the line` is a quiet text action, the back path is quiet);
* XP and the Field Challenge exist in Game mode only — Textbook and Guided print neither;
* the stepper is the plan's real outline: one `StampNode` per objective, `aria-current="step"` and
  the word `Now` on the current one, `done` from recorded independent/delayed evidence, and
  `disabled` only where the plan itself records the gate;
* the Japanese line is the pack's own authored line with the deck's ruby as `<rt>` over kanji and a
  separate romaji line, and a line with no deck reading renders plain (a reading is never derived
  from kana);
* evidence is counted from `lesson.page.checks[]`, and the recorded integrity classes stay visible.

The module's single `export {}` seam lives in its last segment, which this card may not edit, so
the harness imports a **copy** of the built module. CP-040 (the merge seam) added every name the
harness imports to that seam and mounted `ClassroomV3Surface` in the route composition, so the
copy no longer needs an extra export; `_export_line_for` only appends a name the shipped module
does not already export. `tests.test_plugin_build` stays the authority on `desktop/plugin.js`.

What this does NOT prove: that a browser paints the composition (the captures do).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import desktop_node_modules, stage_desktop_node_modules
from tests.test_desktop_lesson_views import SDK_STUB

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
SEGMENT = ROOT / "desktop" / "src" / "70-learning.js"
COPY = ROOT / "docs" / "concept-parity" / "COPY.md"

#: The two authored lines the bundled L0 pack actually contains (`section-01-two-ways.md`).
PACK_LINE = (
    'Aoi: 好きです。付き合ってください。 (suki desu. tsukiatte kudasai.) — '
    '"I like you. Please go out with me."'
)
KANA_ONLY_LINE = 'Mika: たのしかったね。 (tanoshikatta ne.) — "That was fun, wasn\'t it?"'

EXPORT_LINE = (
    "\nexport { ClassroomV3, ClassroomCheckCard, classroomStepNodes, classroomLineFromPage, "
    "classroomEvidence, classroomSceneFromWorld, CB3_CLASSROOM_COPY };\n"
)

#: The names this render harness imports from the copy. CP-023 could not edit the module's export
#: seam, so it appended them; CP-040 (the merge seam) added every one of them to the shipped
#: `export {}` block. Re-declaring a binding the module already exports is a SyntaxError
#: ("Duplicate export"), so the copy only appends the names that are still missing.
HARNESS_IMPORTS = (
    "ClassroomV3",
    "ClassroomCheckCard",
    "classroomStepNodes",
    "classroomLineFromPage",
    "classroomEvidence",
    "classroomSceneFromWorld",
    "classroomSceneSource",
    "CB3_CLASSROOM_COPY",
)


def _export_line_for(source: str) -> str:
    missing = [
        name
        for name in HARNESS_IMPORTS
        if f"\n  {name},\n" not in source and f"\n  {name}\n" not in source
    ]
    if not missing:
        return ""
    return "\nexport { " + ", ".join(missing) + " };\n"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
globalThis.__CB_TEST_MODE__ = payload.mode || 'light'

const {
  ClassroomV3, classroomStepNodes, classroomLineFromPage, classroomEvidence,
  classroomSceneFromWorld, classroomSceneSource, cb3KitSource, CB3_CLASSROOM_COPY
} = await import('./plugin.js')

const h = React.createElement
const render = (props) => renderToStaticMarkup(h(ClassroomV3, props))

const base = payload.base
// JSON cannot carry a function: a truthy flag in the fixture means "this surface has the door".
if (base.onPlayLine) base.onPlayLine = () => {}
if (base.onAskTutor) base.onAskTutor = () => {}
if (base.onStartChallenge) base.onStartChallenge = () => {}
const cases = {}
for (const entry of payload.cases) {
  cases[entry.name] = render({ ...base, ...entry.props })
}

process.stdout.write(JSON.stringify({
  cases,
  steps: classroomStepNodes(payload.outline, payload.page),
  line: classroomLineFromPage(payload.page),
  kanaLine: classroomLineFromPage(payload.kanaPage),
  plainLine: classroomLineFromPage(payload.plainPage),
  evidence: classroomEvidence(payload.page),
  emptyEvidence: classroomEvidence({ checks: [], attempts: [] }),
  sceneSection: classroomSceneFromWorld(
    { world: { kit: { plates: [
      { section_id: 'obj_1', kind: 'section', artifact_id: 'art_other' },
      { section_id: 'obj_2', kind: 'section', artifact_id: 'art_this' }
    ] } } },
    'obj_2',
    'Japanese affection and register'
  ),
  sceneNone: classroomSceneFromWorld(null, 'obj_2', 'Japanese affection and register'),
  // D-007 (UI-K3) fallback chain, driven through the pure resolver: a real plate, then the kit
  // room, and the typographic field only for a build whose asset segment carries no kit row.
  sceneArt: classroomSceneSource(
    { artifactId: 'art_this' },
    { state: 'ready', data_url: 'data:image/webp;base64,ART' },
    'data:image/webp;base64,KIT'
  ),
  sceneArtLoading: classroomSceneSource(
    { artifactId: 'art_this' },
    { state: 'loading' },
    'data:image/webp;base64,KIT'
  ),
  sceneArtUnavailable: classroomSceneSource(
    { artifactId: 'art_this' },
    { state: 'text', message: 'could not be previewed' },
    'data:image/webp;base64,KIT'
  ),
  sceneKit: classroomSceneSource(
    { artifactId: null },
    { state: 'text', message: 'No generated artifact is attached' },
    'data:image/webp;base64,KIT'
  ),
  sceneNoKit: classroomSceneSource({ artifactId: null }, { state: 'text' }, null),
  sceneNoKitWithArtifact: classroomSceneSource({ artifactId: 'art_this' }, { state: 'text' }, null),
  sceneNoScene: classroomSceneSource(null, { state: 'text' }, null),
  kitRow: cb3KitSource('field-atlas-lesson-room') ? 'present' : null,
  copy: CB3_CLASSROOM_COPY
}))
"""


def outline() -> dict:
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "plan": None,
        "total": 5,
        "truncated": False,
        "objectives": [
            {
                "objective_id": "obj_1",
                "ordinal": 1,
                "title": "Hear both ways of saying it",
                "evidence_target": "discrimination",
                "state": "independent_evidence",
                "check_state": "closed",
                "attempt_count": 2,
                "independent": True,
                "last_opened_at": None,
            },
            {
                "objective_id": "obj_2",
                "ordinal": 2,
                "title": "Tell affection from a confession",
                "evidence_target": "discrimination",
                "state": "not_started",
                "check_state": "open",
                "attempt_count": 0,
                "independent": False,
                "last_opened_at": None,
            },
            {
                "objective_id": "obj_3",
                "ordinal": 3,
                "title": "Say it politely",
                "evidence_target": "production",
                "state": "not_started",
                "check_state": "none",
                "attempt_count": 0,
                "independent": False,
                "last_opened_at": None,
            },
            {
                "objective_id": "obj_4",
                "ordinal": 4,
                "title": "Say it casually",
                "evidence_target": "production",
                "state": "not_started",
                "check_state": "none",
                "attempt_count": 0,
                "independent": False,
                "last_opened_at": None,
            },
            {
                "objective_id": "obj_5",
                "ordinal": 5,
                "title": "Open after the check",
                "evidence_target": "production",
                "state": "not_started",
                "check_state": "none",
                "attempt_count": 0,
                "independent": False,
                "last_opened_at": None,
                "locked": True,
            },
        ],
    }


def page() -> dict:
    checks = [
        {
            "check_id": "chk_0001",
            "version": 1,
            "evidence_target": "discrimination",
            "state": "closed",
            "audit_state": "passed",
            "attempt_count": 1,
        },
        {
            "check_id": "chk_0002",
            "version": 1,
            "evidence_target": "discrimination",
            "state": "open",
            "audit_state": "passed",
            "attempt_count": 2,
        },
        {
            "check_id": "chk_0003",
            "version": 1,
            "evidence_target": "production",
            "state": "open",
            "audit_state": "passed",
            "attempt_count": 0,
        },
        {
            "check_id": "chk_0004",
            "version": 1,
            "evidence_target": "production",
            "state": "open",
            "audit_state": "passed",
            "attempt_count": 0,
        },
        {
            "check_id": "chk_0005",
            "version": 1,
            "evidence_target": "production",
            "state": "open",
            "audit_state": "passed",
            "attempt_count": 0,
        },
    ]
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "course": {"course_id": "crs_0123456789abcdef", "title": "Japanese affection and register"},
        "section": {
            "objective_id": "obj_2",
            "title": "Tell everyday affection from a direct romantic declaration",
            "ordinal": 2,
            "state": "not_started",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        "runtime": {
            "lesson_run_id": "run_0123456789abcdef",
            "binding_id": None,
            "binding_status": "detached",
            "session_state": "missing",
            "last_active_at": None,
        },
        "segments": [{"segment_id": "seg_1", "ordinal": 1, "kind": "teaching", "text": payload_text()}],
        "document": None,
        "sources": [],
        "artifacts": [],
        "checks": checks,
        "notebook_entries": [],
        "attempts": [
            {"attempt_id": "att_1", "check_id": "chk_0001", "verdict": "pass", "evidence_class": "cold"},
            {"attempt_id": "att_2", "check_id": "chk_0002", "verdict": "not_yet", "evidence_class": "hinted"},
        ],
        "state": "not_started",
        "revision": 7,
        "provenance": None,
    }


def payload_text() -> str:
    return "\n".join(
        [
            "# Lesson 1 — two ways of saying it",
            "",
            "## Dialogue A — two friends, after a film",
            "",
            KANA_ONLY_LINE,
            "",
            "## Dialogue B — a confession",
            "",
            PACK_LINE,
            "",
            "This is the shape of a confession.",
        ]
    )


def row() -> dict:
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "course_id": "crs_0123456789abcdef",
        "title": "Japanese affection and register",
        "recipe": "learner",
        "revision": 7,
        "next_step": {"kind": "continue_lesson", "label": "Continue section 3"},
        "evidence_summary": {"independent": 1, "total_objectives": 5, "current_objective_id": "obj_2"},
    }


def check() -> dict:
    return {
        "check_id": "chk_0002",
        "objective_id": "obj_2",
        "check_version": 1,
        "evidence_target": "discrimination",
        "state": "open",
        "audit_state": "passed",
        "attempt_count": 0,
        "stimulus": {
            "prompt": "Which line is the romantic confession?",
            "format": "selection",
            "choices": ["A: うん、好きだよ。", "B: 好きです。付き合ってください。"],
            "items": [],
        },
    }


def base_props() -> dict:
    return {
        "row": row(),
        "outline": outline(),
        "page": page(),
        "check": check(),
        "stimulusStatus": "ready",
        "mode": "guided",
        "engagement": None,
        "scene": {"artifactId": None, "title": "Japanese affection and register", "credit": None},
        "state": "default",
        "chatAvailable": True,
        "enrollmentId": "enr_0123456789abcdef",
        "objectiveId": "obj_2",
        "revision": 7,
        "onPlayLine": "play",
        "onAskTutor": "tutor",
        "onStartChallenge": "start",
    }


def cases() -> list[dict]:
    plain_page = {
        "enrollment_id": "enr_0123456789abcdef",
        "course": {"course_id": "crs_0123456789abcdef", "title": "Japanese affection and register"},
        "section": {
            "objective_id": "obj_2",
            "title": "A section with no authored line",
            "ordinal": 2,
            "state": "not_started",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        "runtime": None,
        "segments": [{"segment_id": "seg_2", "ordinal": 1, "kind": "teaching", "text": "Nothing authored here."}],
        "document": None,
        "sources": [],
        "artifacts": [],
        "checks": [],
        "notebook_entries": [],
        "attempts": [],
        "state": "not_started",
        "revision": 8,
        "provenance": None,
    }
    return [
        {"name": "guided", "props": {}},
        {
            "name": "game",
            "props": {
                "mode": "game",
                "engagement": {
                    "xp_total": 120,
                    "level": {"level": 2, "title": "Apprentice", "xp_into_level": 20, "xp_for_next_level": 100, "is_cosmetic": True},
                    "progress": {"label": "Game progress", "is_play_progress": True, "assigned_steps": 9, "completed_steps": 3, "feedback_visible": True},
                    "recent_events": [],
                },
                "gameRows": [{"label": "Practice the polite form out loud"}],
            },
        },
        {"name": "textbook", "props": {"mode": "textbook"}},
        {"name": "error", "props": {"state": "error", "page": None, "check": None, "stimulusStatus": "idle"}},
        {"name": "offline", "props": {"state": "offline", "page": None, "check": None, "stimulusStatus": "idle"}},
        {"name": "nochat", "props": {"chatAvailable": False}},
        {"name": "complete", "props": {"state": "complete", "check": None, "stimulusStatus": "idle"}},
        {"name": "plain", "props": {"page": plain_page, "check": None, "stimulusStatus": "idle"}},
        {"name": "verification", "props": {"check": {
            "check_id": "chk_0003",
            "objective_id": "obj_3",
            "check_version": 1,
            "evidence_target": "production",
            "state": "open",
            "audit_state": "passed",
            "attempt_count": 0,
            "stimulus": {
                "prompt": "Tick the steps you did.",
                "format": "verification",
                "choices": [],
                "items": [{"id": "said_it", "label": "Said the line out loud"}, {"id": "heard_it", "label": "Heard the line once"}],
            },
        }}},
        {"name": "text", "props": {"check": {
            "check_id": "chk_0004",
            "objective_id": "obj_4",
            "check_version": 1,
            "evidence_target": "production",
            "state": "open",
            "audit_state": "passed",
            "attempt_count": 0,
            "stimulus": {"prompt": "Write the polite form.", "format": "text", "choices": [], "items": []},
        }}},
    ]


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


class ClassroomV3RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp023-")
        cls.root = Path(cls.tmp.name)
        source = PLUGIN_JS.read_text(encoding="utf-8")
        (cls.root / "plugin.js").write_text(source + _export_line_for(source), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        stage_desktop_node_modules(cls.root)
        sdk = cls.root / "node_modules" / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True, exist_ok=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

        kana_page = page()
        kana_page["segments"] = [{"segment_id": "seg_k", "ordinal": 1, "kind": "teaching", "text": KANA_ONLY_LINE}]
        bare_page = page()
        bare_page["segments"] = [{"segment_id": "seg_b", "ordinal": 1, "kind": "teaching", "text": "No Japanese here."}]

        payload = {
            "width": 1049,
            "mode": "light",
            "base": base_props(),
            "cases": cases(),
            "outline": outline(),
            "page": page(),
            "kanaPage": kana_page,
            "plainPage": bare_page,
        }
        case_file = cls.root / "case.json"
        case_file.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(case_file)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-6000:])
        cls.report = json.loads(result.stdout)
        cls.html = cls.report["cases"]

        # One narrow pass, because the mascot and the stacked layout are width decisions.
        narrow = dict(payload)
        narrow["width"] = 460
        narrow["cases"] = [{"name": "narrow", "props": {}}]
        narrow_file = cls.root / "case-460.json"
        narrow_file.write_text(json.dumps(narrow), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(narrow_file)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-6000:])
        cls.narrow = json.loads(result.stdout)["cases"]["narrow"]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── the card's named tests ───────────────────────────────────────────────────────────────

    def test_classroom_v3_answer_is_primary(self) -> None:
        html = self.html["guided"]
        # Exactly one filled control, and it is the check's own primary.
        self.assertEqual(html.count('data-cb3-pill="primary"'), 1,
                         "the classroom carries more than one filled control")
        primary = re.search(r'<button[^>]*data-cb3-pill="primary"[^>]*>(.*?)</button>', html, flags=re.S)
        self.assertIsNotNone(primary, "the check card has no filled primary")
        assert primary is not None
        self.assertIn("Check answer", strip_tags(primary.group(1)))
        # The served choices are radio rows, never filled answer buttons.
        self.assertEqual(html.count("data-cb3-choice="), 2, "the selection choices did not render as rows")
        for row_html in re.findall(r"<label data-cb3-choice=[^>]*>(.*?)</label>", html, flags=re.S):
            self.assertNotIn("<button", row_html, "an answer option is painted as a control")
            self.assertNotIn('data-cb3-pill="primary"', row_html)
        for choice in ("A: うん、好きだよ。", "B: 好きです。付き合ってください。"):
            self.assertIn(choice, html)
        # Play the line is a quiet text action, not a second filled button.
        self.assertIn("Play the line", html)
        self.assertIn('data-cb3-pill="quiet"', html)
        # The other surface formats keep the same single primary.
        for name in ("verification", "text"):
            self.assertEqual(self.html[name].count('data-cb3-pill="primary"'), 1, f"{name} minted a second primary")

    def test_classroom_v3_no_xp_outside_game(self) -> None:
        for name in ("guided", "textbook"):
            html = self.html[name]
            self.assertNotIn("data-cb3-xp", html, f"{name} renders the XP chip")
            self.assertNotIn(" XP", strip_tags(html), f"{name} prints an XP count")
            self.assertNotIn("data-cb3-challenge", html, f"{name} renders the Field Challenge")
            self.assertNotIn("Field Challenge", html, f"{name} prints the challenge title")
        game = self.html["game"]
        self.assertIn('data-cb3-xp="120"', game, "Game mode did not read the real XP total")
        self.assertIn("120 XP", strip_tags(game))
        self.assertIn("data-cb3-challenge", game, "Game mode has no Field Challenge")
        self.assertIn("Field Challenge", game)
        self.assertIn("Try it yourself", game)
        # WIRE-8: the challenge is a different served question, not the check already on screen.
        # Isolate the challenge card from the rest of the aside and prove it does not repeat the
        # visible prompt (the prompt also appears once as the answer group's own aria-label).
        challenge_html = game.split("data-cb3-challenge", 1)[1].split('data-cb3-surface="evidence"', 1)[0]
        self.assertNotIn(
            "Which line is the romantic confession?",
            challenge_html,
            "the Field Challenge repeats the visible check as its prompt",
        )
        self.assertIn("A fresh, unseen question", challenge_html, "the challenge card does not describe a fresh check")
        # The challenge's action is quiet: the check keeps the screen's only fill.
        self.assertEqual(game.count('data-cb3-pill="primary"'), 1,
                         "the Game layer added a second filled control")
        self.assertIn("Practice the polite form out loud", game, "a real practice row was dropped")

    def test_classroom_v3_stepper_matches_outline(self) -> None:
        steps = self.report["steps"]
        self.assertEqual(len(steps), 5, "the stepper does not follow the plan's five objectives")
        self.assertEqual(
            [step["state"] for step in steps],
            ["done", "current", "upcoming", "upcoming", "locked"],
            "stepper states do not match recorded evidence and the plan's own gate",
        )
        self.assertEqual(
            [step["label"] for step in steps],
            [objective["title"] for objective in outline()["objectives"]],
            "a stamp label was invented instead of read from the outline",
        )
        html = self.html["guided"]
        self.assertEqual(html.count("data-cb3-stamp="), 5, "the stepper is not one button per section")
        current = re.search(r'<button[^>]*data-cb3-stamp="current"[^>]*>', html)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertIn('aria-current="step"', current.group(0))
        self.assertIn("Now", strip_tags(html), "the current step is marked by colour alone")
        locked = re.search(r'<button[^>]*data-cb3-stamp="locked"[^>]*>', html)
        self.assertIsNotNone(locked)
        assert locked is not None
        self.assertIn("disabled", locked.group(0), "a plan-gated section is a live button")
        self.assertEqual(sum(1 for step in steps if step["state"] == "locked"), 1,
                         "a section is locked without a recorded plan gate")

    def test_classroom_v3_ruby_on_japanese_line(self) -> None:
        line = self.report["line"]
        self.assertIsNotNone(line, "the pack's authored line was not read")
        assert line is not None
        self.assertEqual(line["kana"], "好きです。付き合ってください。")
        self.assertEqual(line["romaji"], "suki desu. tsukiatte kudasai.")
        self.assertEqual(line["english"], "I like you. Please go out with me.")
        ruby = {part["text"]: part["ruby"] for part in line["segments"] if part.get("ruby")}
        self.assertEqual(ruby, {"好き": "すき", "付き合って": "つきあって"},
                         "the deck's ruby is not over the kanji it authored")
        html = self.html["guided"]
        self.assertIn("<ruby>", html)
        self.assertIn("<rt", html)
        self.assertIn("すき", html)
        self.assertIn("つきあって", html)
        self.assertIn('lang="ja-Latn"', html, "the romaji line is not marked as romanised Japanese")
        self.assertIn("suki desu. tsukiatte kudasai.", html)
        self.assertIn("I like you. Please go out with me.", html)
        # A kana-only authored line has no deck reading, so it renders plain — never a derived one.
        kana = self.report["kanaLine"]
        self.assertIsNotNone(kana)
        assert kana is not None
        self.assertTrue(all("ruby" not in part for part in kana["segments"]),
                        "a reading was derived from kana")
        # A page with no authored line renders no bubble at all.
        self.assertIsNone(self.report["plainLine"])
        self.assertNotIn("data-cb3-bubble", self.html["plain"])

    # ── the rest of the card's state contract ────────────────────────────────────────────────

    def test_classroom_v3_evidence_counts_real_checks(self) -> None:
        evidence = self.report["evidence"]
        self.assertEqual((evidence["recorded"], evidence["total"]), (2, 5))
        self.assertEqual(evidence["countLabel"], "2 of 5 checks recorded")
        self.assertEqual(evidence["events"], ["First try, no hints", "Hinted"],
                         "the recorded integrity classes are not visible")
        self.assertIn("2 of 5 checks recorded", self.html["guided"])
        empty = self.report["emptyEvidence"]
        self.assertEqual((empty["recorded"], empty["total"]), (0, 0))
        self.assertIn("No checks recorded yet.", self.html["plain"])

    def test_classroom_v3_states_keep_geometry_and_one_action(self) -> None:
        error = self.html["error"]
        self.assertIn("This section could not be read", error)
        self.assertIn("Your attempt is unchanged. Try again.", error)
        self.assertEqual(error.count('data-cb3-pill="primary"'), 0,
                         "the error state invented a second primary")
        self.assertIn("Try again", error)
        self.assertNotIn('data-cb3-surface="check"', error)
        self.assertIn("You are offline", self.html["offline"])
        nochat = self.html["nochat"]
        self.assertIn("This section has no chat yet", nochat)
        self.assertIn("Start a fresh run", nochat)
        complete = self.html["complete"]
        self.assertIn("Section finished", complete)
        self.assertIn("Back to the path", complete)
        self.assertEqual(complete.count('data-cb3-pill="primary"'), 1)

    def test_classroom_v3_narrow_hides_the_mascot_and_stacks(self) -> None:
        self.assertNotIn("data-cb3-fox=", self.narrow, "the mascot renders below a 620 px route")
        self.assertIn('data-cb3-stepper="strip"', self.narrow)
        self.assertIn('data-cb3-stepper-column="flow"', self.narrow)

    def test_classroom_v3_scene_uses_only_this_sections_plate(self) -> None:
        scene = self.report["sceneSection"]
        self.assertEqual(scene["artifactId"], "art_this", "the scene borrowed another section's plate")
        self.assertIsNone(self.report["sceneNone"]["artifactId"])
        self.assertIn('data-cb3-scene="kit"', self.html["guided"],
                      "a missing world plate did not fall back to the approved kit lesson room")

    def test_classroom_v3_scene_falls_back_artifact_then_kit(self) -> None:
        """D-007 (UI-K3): artifact, then the kit room; type-only only when no kit row exists."""
        self.assertEqual(self.report["kitRow"], "present",
                         "the shipped asset segment carries no field-atlas-lesson-room plate")
        art = self.report["sceneArt"]
        self.assertEqual((art["kind"], art["artifactId"]), ("art", "art_this"),
                         "a ready per-section plate did not win the scene")
        self.assertEqual(art["src"], "data:image/webp;base64,ART")
        # A plate still loading, or one that never became ready, stands in the kit room.
        for name in ("sceneArtLoading", "sceneArtUnavailable"):
            row = self.report[name]
            self.assertEqual(row["kind"], "kit", f"{name} did not fall back to the kit room")
            self.assertEqual(row["artifactId"], "field-atlas-lesson-room")
            self.assertEqual(row["src"], "data:image/webp;base64,KIT")
        kit = self.report["sceneKit"]
        self.assertEqual((kit["kind"], kit["artifactId"]), ("kit", "field-atlas-lesson-room"))
        # The typographic field survives only for a build whose segment never carried a kit row.
        self.assertEqual(self.report["sceneNoKit"]["kind"], "type")
        self.assertEqual(self.report["sceneNoKit"]["artifactId"], "none")
        self.assertEqual(self.report["sceneNoKitWithArtifact"]["kind"], "type")
        self.assertEqual(self.report["sceneNoKitWithArtifact"]["artifactId"], "art_this")
        self.assertEqual(self.report["sceneNoScene"]["kind"], "type")

    def test_classroom_v3_lesson_room_is_the_kit_plate(self) -> None:
        html = self.html["guided"]
        self.assertIn('data-cb3-scene="kit"', html)
        self.assertIn('data-cb3-scene-artifact="field-atlas-lesson-room"', html)
        self.assertIn('data-cb3-scene-kit="field-atlas-lesson-room"', html)
        self.assertNotIn('data-cb3-scene-plate="type"', html,
                         "the typographic field is still painted where the kit exists")
        img = re.search(r'<img[^>]*data-cb3-scene-kit="[^"]*"[^>]*>', html)
        self.assertIsNotNone(img, "the kit room is not an image asset")
        assert img is not None
        # A shipped plate: a WebP data URL from the asset segment, decorative and cover-cropped.
        self.assertIn('src="data:image/webp;base64,', img.group(0))
        self.assertIn('alt=""', img.group(0))
        self.assertIn('aria-hidden="true"', img.group(0))
        self.assertIn('object-fit:cover', img.group(0))
        # No lesson text sits on the plate: only the decorative image is inside the frame.
        frame = re.search(r'<div data-cb3-scene="kit"[^>]*>(.*?)</div>', html, flags=re.S)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertNotIn("<span", frame.group(1), "text was laid over the plate without a scrim")

    def test_classroom_v3_lesson_surface_reads_as_a_room(self) -> None:
        html = self.html["guided"]
        scene = re.search(r'<div data-cb3-scene="kit"[^>]*>', html)
        self.assertIsNotNone(scene)
        assert scene is not None
        self.assertIn("height:16rem", scene.group(0),
                      "the wide lesson scene is shorter than a room (needs >= 16rem at 1344)")
        # The mascot that is already on the lesson surface reads; no second fox was added.
        self.assertEqual(html.count("data-cb3-fox="), 1,
                         "the lesson surface grew a second mascot")
        self.assertIn('data-cb3-fox="read"', html)
        # The compact pane keeps its own height.
        self.assertIn("height:8.95rem", self.narrow)
        self.assertNotIn("height:16rem", self.narrow)

    def test_classroom_v3_copy_is_the_deck(self) -> None:
        deck = {}
        for line in COPY.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\| `(classroom\.[a-z0-9._]+)` \| (.*?) \|", line)
            if match:
                deck[match.group(1)] = match.group(2)
        copy = self.report["copy"]
        expected = {
            "stepper": "classroom.stepper.label",
            "stepCurrent": "classroom.step.current",
            "stepDone": "classroom.step.done",
            "stepNext": "classroom.step.next",
            "stepLocked": "classroom.step.locked",
            "play": "classroom.line.play",
            "checkPrimary": "classroom.check.primary",
            "checkEdit": "classroom.check.edit",
            "clearChoice": "classroom.check.clear_choice",
            "clearTicks": "classroom.check.clear_ticks",
            "checkChoices": "classroom.check.choices",
            "checkChecklist": "classroom.check.checklist",
            "checkAnswers": "classroom.check.answers",
            "checkCriteria": "classroom.check.criteria",
            "practiceExpressions": "classroom.practice.expressions",
            "practiceTranscript": "classroom.practice.transcript",
            "retry": "classroom.check.retry",
            "next": "classroom.check.next",
            "evidenceTitle": "classroom.evidence.title",
            "evidenceCount": "classroom.evidence.count",
            "evidenceEmpty": "classroom.evidence.empty",
            "asideTutor": "classroom.aside.tutor",
            "nochatTitle": "classroom.nochat.title",
            "nochatBody": "classroom.nochat.body",
            "nochatAction": "classroom.nochat.action",
            "completeTitle": "classroom.complete.title",
            "completeBody": "classroom.complete.body",
            "completeAction": "classroom.complete.action",
            "loading": "classroom.loading",
            "errorTitle": "classroom.error.title",
            "errorBody": "classroom.error.body",
            "errorAction": "classroom.error.action",
            "offlineTitle": "classroom.offline.title",
            "offlineBody": "classroom.offline.body",
            "gameXp": "classroom.game.xp",
            "challengeTitle": "classroom.challenge.title",
            "challengeStart": "classroom.challenge.primary",
        }
        for key, row in expected.items():
            self.assertIn(row, deck, f"COPY.md has no row {row}")
            self.assertEqual(copy[key], deck[row], f"{key} does not match {row}")

        # The six group labels are deck rows, not literals: no answer surface may name its own
        # group again in the source (a second copy source is how two spellings drift apart).
        source = SEGMENT.read_text(encoding="utf-8")
        for literal in (
            "'aria-label': 'Choices'",
            "'aria-label': 'Checklist'",
            "'aria-label': 'Answers'",
            "'aria-label': 'Grading criteria'",
            "'aria-label': 'Expressions to practise'",
            "'aria-label': 'Practice transcript'",
            "children: 'Choices'",
            "children: 'Checklist'",
            "children: 'Answers'",
            "children: 'Grading criteria'",
            "children: 'Expressions to practise'",
        ):
            self.assertNotIn(literal, source, f"the segment still hard-codes {literal}")

    def test_classroom_v3_paints_only_v3_tokens(self) -> None:
        source = SEGMENT.read_text(encoding="utf-8")
        start = source.index("// CB-V3-BEGIN — CP-023")
        end = source.index("// CB-V3-END — CP-023")
        region = source[start:end]
        for pattern, label in (
            (r"#[0-9a-fA-F]{3,8}\b", "a raw hex colour"),
            (r"(?<![\w.-])[+-]?(?:\d+(?:\.\d+)?|\.\d+)vw\b", "a viewport unit"),
            (r"box-?shadow", "a shadow recipe"),
            (r"[a-z-]*gradient\(", "a gradient"),
            (r"backdrop-?filter|blur\(", "glass paint"),
            (r"@keyframes|animation\s*:|infinite", "a loop"),
        ):
            self.assertIsNone(re.search(pattern, region, re.I), f"the classroom block carries {label}")


if __name__ == "__main__":
    unittest.main()
