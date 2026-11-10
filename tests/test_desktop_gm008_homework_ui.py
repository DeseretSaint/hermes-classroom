"""GM-008 — homework the learner takes with them: the desktop surface over `homework.*`.

Two kinds of proof, both real:

* the backend half drives the shipped ``homework.create/read/complete/skip`` handlers through
  ``api.dispatch`` against a real migrated SQLite database, from a Game course and a Textbook
  course, and reads the one-page sheet the backend renders;
* the desktop half renders the shipped module through React (``renderToStaticMarkup``, the same
  jsdom-free harness the GM-006 card uses) and asserts the composed DOM: the quiet action, the
  field card with one target / one context / at most three steps, the honest completion line, no
  XP or grade, and a coherent skip.

What this does not prove: pixels against the approved concept frames, or a live print dialog. The
isolated rig and ``docs/visual-review/gm-008/`` carry those.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from coursebook import db, domain, generation
from tests.kernel_support import KernelCase, criteria_with, numeric_spec
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.test_gm_homework import ANSWER_MARKER, GEN_HASH, NOW, RUBRIC_MARKER, japanese_page

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import {
  TakeThisWithYou,
  HomeworkSheetCard,
  HomeworkRecordList,
  HomeworkStudio,
  cbHomeworkSheetGuard,
  cbHomeworkRefTaskId,
  cbHomeworkSourceRef,
  cbHomeworkExcerpt,
  cbHomeworkFilename,
  cbHasJapanese,
  CB_HOMEWORK_STATE_WORD
} from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const quiet = () => {}
const out = (node) => process.stdout.write(renderToStaticMarkup(node))
const methods = new Set([
  'homework.create', 'homework.read', 'homework.complete', 'homework.skip',
  'notebook.save', 'takehome.sources', 'library.list'
])

if (payload.kind === 'action') {
  out(React.createElement(TakeThisWithYou, {
    enrollmentId: payload.enrollmentId || 'enr_1',
    courseId: payload.courseId || 'crs_1',
    objectiveId: payload.objectiveId || 'obj_1',
    sectionTitle: payload.sectionTitle || 'Say the before-meal greeting',
    implemented: methods,
    onChanged: quiet
  }))
} else if (payload.kind === 'sheet') {
  out(React.createElement(HomeworkSheetCard, { task: payload.task }))
} else if (payload.kind === 'list') {
  out(React.createElement(HomeworkRecordList, {
    rows: payload.rows, actor: payload.actor || 'learner', canSave: false,
    emptyTitle: payload.emptyTitle || 'No homework yet',
    emptyDescription: payload.emptyDescription || 'A task you take with you is listed here.'
  }))
} else if (payload.kind === 'studio') {
  out(React.createElement(HomeworkStudio, { implemented: methods }))
} else if (payload.kind === 'helpers') {
  out(React.createElement('div', {
    'data-guard': cbHomeworkSheetGuard(payload.task) || '',
    'data-ref-id': cbHomeworkRefTaskId(payload.sourceRef) || '',
    'data-source-ref': cbHomeworkSourceRef(payload.task),
    'data-excerpt': cbHomeworkExcerpt(payload.task),
    'data-filename': cbHomeworkFilename(payload.task),
    'data-jp': String(cbHasJapanese(payload.task.target.display)),
    'data-word': CB_HOMEWORK_STATE_WORD[payload.task.state] || ''
  }))
}
"""


class _Rig:
    def __init__(self) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        self.tmp = tempfile.TemporaryDirectory(prefix="coursebook-gm008-")
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
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    def render(self, payload: dict) -> str:
        import subprocess

        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "static.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=240,
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
    """The visible copy of a rendered node, lower-cased, tags dropped."""
    import re

    return re.sub(r"<[^>]+>", " ", html).lower()


class HomeworkUiCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        with db.read() as connection:
            generation.ensure_schema(connection)

    def seed(self, *, presentation_mode: str | None = None, title: str = "Mealtime greetings") -> dict:
        payload = {
            "title": "Japanese at home",
            "recipe": "committed",
            "goal": "Use one Japanese greeting at a real meal.",
            "locale": "ja-JP",
        }
        if presentation_mode:
            payload["presentation_mode"] = presentation_mode
        created = self.ok("course.create", payload)["result"]
        course_id, plan_id = created["course_id"], created["plan_id"]
        objective_id = domain.record_objective(
            plan_id,
            title="Say the before-meal greeting",
            evidence_target="production",
            criteria=criteria_with(numeric_spec()),
        )
        enrollment_id = self.new_enrollment(course_id)
        self.approve(enrollment_id, plan_id, 0)
        with db.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO gen_plan_documents (id, plan_id, course_id,"
                " request_fingerprint, plan_hash, document_json, research_json, generation_state,"
                " validation_id, result_json, created_at)"
                " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
                (f"gpd_{plan_id}", plan_id, course_id, GEN_HASH, NOW),
            )
            section_id = f"sec_{plan_id}"
            lesson_id = f"lsn_{plan_id}"
            check_id = f"chk_{plan_id}"
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                " VALUES (?, ?, 1, ?, ?, 'Say one greeting at the table.', '[1]', '[]', '[]')",
                (section_id, plan_id, GEN_HASH, title),
            )
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, media_json, parent_notes_json, rejection_reasons_json,"
                " validation_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', '{}', '[]', NULL, ?, ?)",
                (lesson_id, plan_id, section_id, GEN_HASH, json.dumps(japanese_page(title)), NOW, NOW),
            )
            connection.execute(
                "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
                " rubric_json, reference_json, locale, audit_state, state, created_at)"
                " VALUES (?, ?, 1, 'production', ?, ?, ?, 'ja-JP', 'passed', 'open', ?)",
                (
                    check_id,
                    objective_id,
                    json.dumps({"prompt": "Say the greeting.", "format": "short_text"}),
                    json.dumps({"criteria": [{"criterion": "a", "description": RUBRIC_MARKER}]}),
                    json.dumps({"reference_answer": ANSWER_MARKER, "accepted_answers": []}),
                    NOW,
                ),
            )
            connection.execute(
                "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, 1)",
                (lesson_id, check_id),
            )
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "lesson_version": f"{lesson_id}:v1",
        }

    def create(self, seeded: dict, *, context: str = "At your own table, just before you eat today.",
               audience: str = "learner", expected: int = 0) -> dict:
        return self.ok(
            "homework.create",
            {
                "course_id": seeded["course_id"],
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_id"],
                "audience": audience,
                "source_lesson_version": seeded["lesson_version"],
                "context": context,
            },
            expected_revision=expected,
            idempotency_key=f"gm008-{seeded['course_id']}-{audience}",
        )["result"]


# ── the action ────────────────────────────────────────────────────────────────


class HomeworkActionTest(HomeworkUiCase):
    def test_homework_action_available_in_all_modes(self) -> None:
        game = self.seed(presentation_mode="game", title="Game: the meal greeting")
        textbook = self.seed(presentation_mode="textbook", title="Textbook: the meal greeting")

        # One generator, two presentation modes: the task is not a Game-only surface.
        made_game = self.create(game)
        made_textbook = self.create(textbook)
        self.assertEqual(made_game["state"], "proposed")
        self.assertEqual(made_textbook["state"], "proposed")
        self.assertNotEqual(made_game["task_id"], made_textbook["task_id"])

        # `takehome.sources` still reports the mode, and both are readable sources for a task.
        for seeded, mode in ((game, "game"), (textbook, "textbook")):
            source = self.ok("takehome.sources", {"course_id": seeded["course_id"]})["result"]
            self.assertEqual(source["presentation_mode"], mode)
            self.assertTrue(source["objectives"][0]["available"])
            self.assertEqual(source["objectives"][0]["lesson_version"], seeded["lesson_version"])

        # The rendered action is the quiet text button, not a dialog and not a second filled control.
        html = render({"kind": "action"})
        self.assertIn('data-cb-homework-action="take-this-with-you"', html)
        self.assertIn("Take this with you", html)
        self.assertIn('aria-expanded="false"', html)
        self.assertNotIn('role="dialog"', html)
        self.assertIn('data-variant="text"', html)

        # It is a child of the section footer, whose only gate is a readable page — the footer is
        # composed once per section, for every lesson view (Textbook, Guided and the player).
        module = PLUGIN_JS.read_text(encoding="utf-8")
        anchor = module.index("'data-cb-section-footer': ''")
        window = module[anchor - 400 : anchor + 1800]
        self.assertIn("page && pageReadable", window)
        self.assertIn("jsx(TakeThisWithYou", window)
        for view in ("textbook", "guided", "field_quest", "player"):
            self.assertIn(f"id: '{view}'", module)
        self.assertIsNone(
            __import__("re").search(r"lessonView\s*===\s*'textbook'[^\n]*TakeThisWithYou", module)
        )


# ── the sheet ─────────────────────────────────────────────────────────────────


class HomeworkSheetTest(HomeworkUiCase):
    def test_homework_sheet_has_one_task_and_one_page(self) -> None:
        seeded = self.seed()
        made = self.create(seeded)
        task = self.ok("homework.read", {"task_id": made["task_id"]})["result"]["task"]

        # One page, structurally: the backend renders exactly one sheet article and no page break.
        self.assertEqual(task["sheet"]["pages"], 1)
        self.assertEqual(task["sheet"]["html"].count('<article class="sheet"'), 1)
        self.assertNotIn("page-break-after", task["sheet"]["html"])

        # One task, one target, one context, at most three steps, one observable done-when.
        self.assertEqual(len(task["steps"]), 3)
        self.assertLessEqual(len(task["steps"]), 3)
        self.assertTrue(task["success_criterion"])
        self.assertTrue(task["context"])
        self.assertEqual(task["target"]["kind"], "single")

        html = render({"kind": "sheet", "task": task})
        self.assertEqual(html.count("data-cb-homework-target="), 1)
        self.assertEqual(html.count("data-cb-homework-context="), 1)
        self.assertEqual(html.count("<ol"), 1)
        self.assertLessEqual(html.count("<li"), 3)
        self.assertEqual(html.count("Done when"), 1)
        self.assertIn("Coursebook field card", html)
        self.assertIn(f"About {task['estimated_minutes']} minutes", html)
        for heading in ("Where and when", "Do this", "Done when"):
            self.assertIn(heading, html)
        # The Japanese target is marked as Japanese for a reader, and carries its romaji scaffold.
        self.assertIn('lang="ja"', html)
        self.assertIn("itadakimasu", html)
        self.assertIn("Source", html)

        # The print artifact is the backend's own sheet, not a second template.
        self.assertEqual(flat(html).count("coursebook field card"), 1)
        self.assertIn(task["title"], html)


# ── completion ────────────────────────────────────────────────────────────────


class HomeworkCompletionTest(HomeworkUiCase):
    def test_homework_completion_is_self_reported(self) -> None:
        seeded = self.seed()
        made = self.create(seeded)
        with db.read() as connection:
            before = {}
            for table in ("attempts", "evidence", "game_engagement"):
                try:
                    before[table] = int(connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
                except Exception:  # noqa: BLE001 - a table this build lacks counts as absent
                    before[table] = -1

        done = self.ok(
            "homework.complete",
            {"task_id": made["task_id"], "actor": "learner", "note": "said it before dinner"},
            expected_revision=made["revision"],
        )["result"]
        self.assertEqual(done["state"], "self_reported_done")
        self.assertEqual(done["task"]["completion"]["basis"], "self_reported")
        self.assertFalse(done["task"]["completion"]["independent_verification"])
        self.assertTrue(done["task"]["completion"]["completed_at"])

        after = self.ok("homework.read", {"task_id": made["task_id"]})["result"]
        kinds = [event["kind"] for event in after["events"]]
        self.assertEqual(kinds, ["proposed", "self_reported"])

        # Completing homework writes no attempt, no evidence and no engagement row.
        with db.read() as connection:
            for table, count in before.items():
                if count < 0:
                    continue
                row = connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
                self.assertEqual(int(row["n"]), count, f"{table} gained a row from a report")

        html = render({"kind": "sheet", "task": done["task"]})
        self.assertIn("data-cb-homework-completion=\"reported\"", html)
        self.assertIn("You recorded this as done", html)
        self.assertIn("A report, not a verdict.", html)
        self.assertNotIn("mastery", flat(html))
        self.assertNotIn("passed", flat(html))

        # A parent report is its own honest basis, and is not verification either.
        parent_seeded = self.seed(title="Parent-led: the meal greeting")
        parent_made = self.create(parent_seeded, audience="parent")
        parent_done = self.ok(
            "homework.complete",
            {"task_id": parent_made["task_id"], "actor": "parent", "note": ""},
            expected_revision=parent_made["revision"],
        )["result"]
        self.assertEqual(parent_done["state"], "parent_reported_done")
        self.assertEqual(parent_done["task"]["completion"]["basis"], "parent_reported")
        self.assertFalse(parent_done["task"]["completion"]["independent_verification"])
        parent_html = render({"kind": "sheet", "task": parent_done["task"]})
        self.assertIn("A parent recorded this as done", parent_html)


# ── no XP, no grade ───────────────────────────────────────────────────────────


class HomeworkSheetPolicyTest(HomeworkUiCase):
    def test_homework_sheet_has_no_xp_or_grade(self) -> None:
        seeded = self.seed()
        made = self.create(seeded)
        task = self.ok("homework.read", {"task_id": made["task_id"]})["result"]["task"]

        banned = ("xp", "grade", "graded", "score", "scored", "mastery", "streak", "answer", "photo")
        text = task["sheet"]["text"].lower()
        for word in banned:
            self.assertNotIn(word, text, f"the printed sheet carries {word!r}")
        html = render({"kind": "sheet", "task": task})
        copy = flat(html)
        for word in banned:
            self.assertNotIn(word, copy, f"the rendered card carries {word!r}")
        # The answer marker from the lesson's check must not reach the card either.
        self.assertNotIn("reference-only", copy)
        self.assertNotIn("rubric-only", copy)

        # The desk refuses a task whose copy would carry one, rather than printing it.
        dirty = json.loads(json.dumps(task))
        dirty["success_criterion"] = "Earn 10 XP when you say it at the table."
        helpers = render({"kind": "helpers", "task": dirty, "sourceRef": cb_source_ref(task)})
        self.assertIn("data-guard=\"This task would print a word", helpers)
        clean = render({"kind": "helpers", "task": task, "sourceRef": cb_source_ref(task)})
        self.assertIn('data-guard=""', clean)


def cb_source_ref(task: dict) -> str:
    return json.dumps({"homework_task_id": task["task_id"], "objective_id": task["objective_id"]})


# ── skip ──────────────────────────────────────────────────────────────────────


class HomeworkSkipTest(HomeworkUiCase):
    def test_homework_skip_is_honest(self) -> None:
        seeded = self.seed()
        made = self.create(seeded)

        skipped = self.ok(
            "homework.skip",
            {"task_id": made["task_id"], "actor": "learner"},
            expected_revision=made["revision"],
        )["result"]
        self.assertEqual(skipped["state"], "skipped")
        self.assertIsNone(skipped["task"]["completion"]["basis"])
        self.assertIsNone(skipped["task"]["completion"]["completed_at"])

        read = self.ok("homework.read", {"task_id": made["task_id"]})["result"]
        self.assertEqual([event["kind"] for event in read["events"]], ["proposed", "skipped"])
        self.assertIn("Skipped", render({"kind": "sheet", "task": read["task"]}))
        copy = flat(render({"kind": "sheet", "task": read["task"]}))
        self.assertIn("nothing is owed and nothing is lost", copy)
        for word in ("punish", "penalty", "streak", "failed", "xp"):
            self.assertNotIn(word, copy)

        # A skipped task cannot later be reported done: the report would be a lie about the day.
        late = self.err(
            "homework.complete",
            {"task_id": made["task_id"], "actor": "learner", "note": ""},
            expected_revision=skipped["task"]["revision"],
        )
        self.assertEqual(late["code"], "POLICY_VIOLATION")
        self.assertEqual(late["details"]["reason"], "task_closed")

        # The list renders the empty state honestly rather than a placeholder row.
        empty = render({"kind": "list", "rows": []})
        self.assertIn('data-cb-homework-list="empty"', empty)
        self.assertIn("No homework yet", empty)
        # Parent Studio starts from the same honest empty state and never a fabricated task.
        studio = render({"kind": "studio"})
        self.assertIn('data-cb-homework-studio="0"', studio)
        self.assertIn("A task starts on a lesson page", studio)


if __name__ == "__main__":
    unittest.main()
