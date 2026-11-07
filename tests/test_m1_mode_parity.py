"""M1 mode parity, answer-leak and repeated-checklist proof.

`docs/VISUAL_MEDIA_PLAN.md` §5 makes one validated ``LessonDocument`` the only authority and every
view a lens over it. This module tries to break that claim three ways:

* **Parity** — a real ``lesson.page`` document is rendered through the *shipped* ``desktop/plugin.js``
  (React + ``react-dom/server``, hooks included) in Textbook and in Guided. The block ids, the one
  attached check id, the source ids and the objective id must be identical across the view switch.
* **Attempt state** — the real kernel is read before and after a view switch; no render may bump a
  revision, create an attempt or move a check.
* **Answer leak** — a check whose reference answer and rubric carry a unique token is read through
  ``check.get`` and ``lesson.page`` and rendered in both views. The token must appear nowhere.

The repeated-checklist regression is the red/green pair at the bottom of this file: the old
fixture puts the same checklist labels in the section prose and in the check prompt, so the
Textbook view prints each label twice. The structured fixture keeps the labels on the check
surface only and every label is printed once.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import api, lesson_document
from tests.kernel_support import KernelCase, numeric_spec
from tests.test_desktop_lesson_views import PLUGIN_JS, SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "audit" / "visual" / "m1-mode-parity" / "evidence.json"

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { LessonDocumentView } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source
const labels = payload.checkLabels || []
const checkSlot = labels.length
  ? React.createElement(
      'div',
      { 'data-cb-check-surface': 'true' },
      labels.map((label, i) => React.createElement('p', { key: i }, label))
    )
  : null
const html = renderToStaticMarkup(
  React.createElement(LessonDocumentView, {
    document: payload.document,
    view: payload.view,
    sources: index,
    checkSlot
  })
)
process.stdout.write(html)
"""

CHECKLIST = ["Check the heat", "Check sharp objects", "Check small parts", "Check allergies"]


def record(**facts) -> None:
    """Merge measured facts into the evidence JSON so the artifact is written by the run."""
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    current = {}
    if EVIDENCE.is_file():
        current = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    current.update(facts)
    EVIDENCE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")


class RenderCase(KernelCase):
    """A kernel database plus the shipped plugin rendered by real React."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-mode-parity-")
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
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, document: dict, view: str, *, check_labels=None) -> str:
        case = self.root / "case.json"
        case.write_text(
            json.dumps(
                {
                    "document": document,
                    "view": view,
                    "checkLabels": check_labels or [],
                    "sources": [
                        {"source_id": "src_heat0001", "title": "Workshop field notes"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    # -- real page fixtures ---------------------------------------------------------------
    def seed_page(self, lesson: dict, segments: list[tuple[str, str]], *, source_id="src_heat0001"):
        """Insert the durable lesson_run/segments a real ``lesson.page`` reads."""
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES ('run_parity01', ?, ?, 'active', 0,"
            " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL)",
            (lesson["enrollment_id"], lesson["objective_id"]),
        )
        self.execute(
            "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at,"
            " support_status, claim_count, created_at) VALUES (?, ?, NULL, 'Workshop field notes',"
            " 'course_material', NULL, '2026-01-01T00:00:00+00:00', 'unassessed', 0,"
            " '2026-01-01T00:00:00+00:00')",
            (source_id, lesson["course_id"]),
        )
        for ordinal, (kind, text) in enumerate(segments, start=1):
            self.execute(
                "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at,"
                " source_id) VALUES (?, 'run_parity01', ?, ?, ?,"
                " '2026-01-01T00:00:00+00:00', ?)",
                (f"seg_parity{ordinal:04d}", ordinal, kind, text, source_id),
            )

    def page(self, lesson: dict) -> dict:
        return self.ok(
            "lesson.page",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]

    def revision(self, lesson: dict) -> int:
        return int(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)))  # type: ignore[arg-type]


class ParityTest(RenderCase):
    def test_textbook_and_guided_keep_the_same_blocks_check_and_sources(self) -> None:
        lesson = self.prepare_lesson()
        self.seed_page(
            lesson,
            [
                ("teaching", "Heat the pan until a drop of water beads."),
                ("teaching", "Arrange the parts in the order you will fit them."),
                ("check_prompt", "Walk the checklist and record each item you verified."),
            ],
        )
        page = self.page(lesson)
        document = page["document"]
        self.assertEqual(document["check_id"], lesson["check_id"])
        self.assertEqual(document["objective_id"], lesson["objective_id"])
        ids = [block["id"] for block in document["blocks"]]
        self.assertEqual(len(ids), 3)
        self.assertTrue(document["views"]["textbook"])
        # No writer authors `short` yet, so this honest page is textbook_only; parity between the
        # two views is proven below over the authored v8 path where Guided is reachable.
        self.assertEqual(document["state"], "textbook_only")

        authored = lesson_document.document_from_blocks(
            [
                {
                    "id": "blk_practice0001",
                    "role": "practice",
                    "headline": "Try it",
                    "short": "Walk the checklist.",
                    "deep": "Walk the checklist and record each item you verified.",
                    "check_id": lesson["check_id"],
                    "media": [],
                    "source_ids": ["src_heat0001"],
                },
                {
                    "id": "blk_orient000001",
                    "role": "orient",
                    "headline": "Start here",
                    "short": "A short orient.",
                    "deep": "A deep orient paragraph that sets the workshop scene.",
                    "check_id": None,
                    "media": [],
                    "source_ids": ["src_heat0001"],
                },
                {
                    "id": "blk_explain00001",
                    "role": "explain",
                    "headline": "Why it works",
                    "short": "A short explanation.",
                    "deep": "A deep explanation of the mechanism behind the checklist.",
                    "check_id": None,
                    "media": [],
                    "source_ids": [],
                },
                {
                    "id": "blk_recap0000001",
                    "role": "recap",
                    "headline": "Recap",
                    "short": "A short recap.",
                    "deep": "A deep recap of what the learner just did.",
                    "check_id": None,
                    "media": [],
                    "source_ids": [],
                },
            ],
            section_title="Workshop checklist",
            objective_id=lesson["objective_id"],
            check_id=lesson["check_id"],
            source_ids=["src_heat0001"],
        )
        self.assertEqual(authored["state"], "complete")
        self.assertTrue(authored["views"]["guided"])

        textbook = self.render(authored, "textbook", check_labels=["Check the heat"])
        guided = self.render(authored, "guided", check_labels=["Check the heat"])

        # Same document, same blocks, same single check, same source in both views.
        self.assertIn(f'data-cb-document="{authored["document_id"]}"', textbook)
        self.assertIn(f'data-cb-document="{authored["document_id"]}"', guided)
        textbook_ids = re.findall(r'data-cb-block="(blk_[^"]+)"', textbook)
        self.assertEqual(textbook_ids, [b["id"] for b in authored["blocks"]])
        self.assertEqual(textbook.count("data-cb-check-surface"), 1)
        self.assertEqual(guided.count("data-cb-check-surface"), 1)
        self.assertIn(f'data-cb-block-check="{authored["blocks"][0]["id"]}"', textbook)
        self.assertIn(f'data-cb-block-check="{authored["blocks"][0]["id"]}"', guided)
        for html in (textbook, guided):
            self.assertEqual(html.count('data-cb-block-check="'), 1)
        self.assertIn("Step 1 of 4", guided)
        # Every block that cites the source prints its chip; Guided prints only the current step.
        self.assertEqual(textbook.count("Workshop field notes"), 2)
        self.assertEqual(guided.count("Workshop field notes"), 1)
        for html in (textbook, guided):
            self.assertIn('data-cb-role="practice"', html)

        record(
            parity={
                    "objective_id": lesson["objective_id"],
                    "check_id": lesson["check_id"],
                    "lesson_page_document_id": document["document_id"],
                    "lesson_page_state": document["state"],
                    "authored_document_id": authored["document_id"],
                    "authored_state": authored["state"],
                    "block_ids": [b["id"] for b in authored["blocks"]],
                    "role_order": [b["role"] for b in authored["blocks"]],
                    "source_ids": authored["source_ids"],
                    "textbook": {
                        "view": "textbook",
                        "document_id": authored["document_id"],
                        "block_ids": textbook_ids,
                        "check_surfaces": textbook.count("data-cb-check-surface"),
                        "check_attached_to": authored["blocks"][0]["id"],
                        "source_title_occurrences": textbook.count("Workshop field notes"),
                    },
                    "guided": {
                        "view": "guided",
                        "document_id": authored["document_id"],
                        "block_ids": re.findall(r'data-cb-block="(blk_[^"]+)"', guided),
                        "check_surfaces": guided.count("data-cb-check-surface"),
                        "check_attached_to": authored["blocks"][0]["id"],
                        "step": "Step 1 of 4",
                        "source_title_occurrences": guided.count("Workshop field notes"),
                    },
                    "not_measured": [
                        "A live Guided page: no writer authors block short, so lesson.page is always textbook_only (t_7890cf1f).",
                        "Live rig frames: no isolated backend was mounted on this branch.",
                    ],
            }
        )

    def test_a_view_switch_changes_no_revision_or_attempt(self) -> None:
        lesson = self.prepare_lesson(numeric_spec("42.7"))
        self.seed_page(
            lesson,
            [
                ("teaching", "Heat the pan until a drop of water beads."),
                ("check_prompt", "Compute the answer."),
            ],
        )
        self.assertTrue(self.submit(lesson, "42.7")["ok"])
        before_check = self.ok(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]},
        )["result"]
        before_page = self.page(lesson)
        before_revision = self.revision(lesson)
        self.assertGreaterEqual(before_check["attempt_count"], 1)

        document = lesson_document.document_from_blocks(
            [
                {
                    "id": "blk_practice0001",
                    "role": "practice",
                    "headline": "Try it",
                    "short": "Answer the check.",
                    "deep": "Answer the check in your own words.",
                    "check_id": lesson["check_id"],
                    "media": [],
                    "source_ids": ["src_heat0001"],
                },
                {
                    "id": "blk_orient000001",
                    "role": "orient",
                    "headline": "Start here",
                    "short": "Orient.",
                    "deep": "Set the scene in a deep orient paragraph.",
                    "check_id": None,
                    "media": [],
                    "source_ids": ["src_heat0001"],
                },
            ],
            section_title="Answer the check",
            objective_id=lesson["objective_id"],
            check_id=lesson["check_id"],
            source_ids=["src_heat0001"],
        )
        self.render(document, "textbook", check_labels=["Compute the answer."])
        self.render(document, "guided", check_labels=["Compute the answer."])

        after_check = self.ok(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]},
        )["result"]
        after_page = self.page(lesson)
        self.assertEqual(self.revision(lesson), before_revision)
        self.assertEqual(after_check["attempt_count"], before_check["attempt_count"])
        self.assertEqual(after_check["state"], before_check["state"])
        self.assertEqual(after_check["check_version"], before_check["check_version"])
        self.assertEqual(len(after_page["attempts"]), len(before_page["attempts"]))
        self.assertEqual(after_page["revision"], before_page["revision"])
        record(
            attempt_state={
                "check_id": lesson["check_id"],
                "check_version": before_check["check_version"],
                "state": before_check["state"],
                "attempt_count_before": before_check["attempt_count"],
                "attempt_count_after": after_check["attempt_count"],
                "revision_before": before_revision,
                "revision_after": self.revision(lesson),
                "lesson_page_attempts_before": len(before_page["attempts"]),
                "lesson_page_attempts_after": len(after_page["attempts"]),
                "view_switch": ["textbook", "guided"],
            }
        )


class AnswerLeakTest(RenderCase):
    SECRET = "AZURE-OTTER-9174"

    def leaking_spec(self) -> dict:
        return {
            "audit_state": "passed",
            "stimulus": {"prompt": "State the workshop rule in one sentence."},
            "reference": {"kind": "exact", "answers": [self.SECRET]},
            "rubric": {
                "construct": "recall_accuracy",
                "pass_rule": "all",
                "criteria": [{"id": "c1", "description": f"States {self.SECRET} exactly"}],
            },
        }

    def test_no_reference_or_rubric_key_reaches_a_learner_view(self) -> None:
        lesson = self.prepare_lesson(self.leaking_spec())
        self.seed_page(
            lesson,
            [
                ("teaching", "The workshop rule is written on the wall in your own words."),
                ("check_prompt", "State the workshop rule in one sentence."),
            ],
        )
        page = self.page(lesson)
        opened = self.ok(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]

        for payload, label in ((page, "lesson.page"), (opened, "check.get")):
            blob = json.dumps(payload)
            self.assertNotIn(self.SECRET, blob, label)
            self.assertNotIn("reference_answer", blob, label)
            self.assertNotIn("rubric_json", blob, label)

        document = page["document"]
        self.assertEqual(lesson_document.leaks_answer(document, [self.SECRET]), [])
        self.assertEqual(lesson_document.answer_material(document), [])

        textbook = self.render(document, "textbook", check_labels=[opened["stimulus"]["prompt"]])
        guided = self.render(document, "guided", check_labels=[opened["stimulus"]["prompt"]])
        for html, view in ((textbook, "textbook"), (guided, "guided")):
            self.assertNotIn(self.SECRET, html, view)
            self.assertNotIn("reference", html.lower(), view)
            self.assertNotIn("rubric", html.lower(), view)
            self.assertNotIn("accepted answer", html.lower(), view)

        # Negative control: the detector is not vacuous.
        leaky = dict(document)
        leaky["blocks"] = [dict(document["blocks"][0], deep=f"Remember {self.SECRET}.")] + list(
            document["blocks"][1:]
        )
        self.assertEqual(lesson_document.leaks_answer(leaky, [self.SECRET]), [self.SECRET])

    def test_switching_views_never_reveals_the_key(self) -> None:
        lesson = self.prepare_lesson(self.leaking_spec())
        self.seed_page(lesson, [("check_prompt", "State the workshop rule in one sentence.")])
        document = self.page(lesson)["document"]
        seen: list[str] = []
        for view in ("textbook", "guided", "textbook"):
            html = self.render(document, view, check_labels=["State the workshop rule in one sentence."])
            seen.append(html)
            self.assertNotIn(self.SECRET, html, view)
        self.assertTrue(all(self.SECRET not in html for html in seen))


class RepeatedChecklistRegressionTest(RenderCase):
    """The old defect: the same checklist labels are printed twice in one view.

    A verification checklist authored into the section prose *and* into the check prompt reaches
    ``lesson.page`` as two blocks with the same text (the teaching segment and the ``check_prompt``
    practice block), so Textbook prints every label twice. A structured check keeps its labels on
    the single check surface, and each label is printed once.
    """

    def test_old_fixture_duplicates_labels_today(self) -> None:
        """Characterisation of the open defect: the double print is real, not hypothetical."""
        lesson = self.prepare_lesson()
        self.seed_page(
            lesson,
            [
                ("teaching", "Before you start, walk the list:\n" + "\n".join(CHECKLIST)),
                ("check_prompt", "Verify each item:\n" + "\n".join(CHECKLIST)),
            ],
        )
        document = self.page(lesson)["document"]
        html = self.render(document, "textbook", check_labels=CHECKLIST)
        counts = {label: html.count(label) for label in CHECKLIST}
        self.assertEqual(counts, {label: 3 for label in CHECKLIST})
        record(
            duplicate_checklist={
                "fixture": "teaching segment + check_prompt segment + check surface",
                "view": "textbook",
                "label_counts": counts,
                "expected": {label: 1 for label in CHECKLIST},
                "verdict": "FAIL",
            }
        )

    @unittest.expectedFailure
    def test_old_fixture_prints_each_label_once(self) -> None:
        """DEFECT (t_ff6ce87a): this must flip green when checklist labels are structured.

        Today the same labels reach the Textbook view three times: once in the teaching segment,
        once in the ``check_prompt`` practice block and once on the check surface. The card's
        contract is one print per label.
        """
        lesson = self.prepare_lesson()
        self.seed_page(
            lesson,
            [
                ("teaching", "Before you start, walk the list:\n" + "\n".join(CHECKLIST)),
                ("check_prompt", "Verify each item:\n" + "\n".join(CHECKLIST)),
            ],
        )
        document = self.page(lesson)["document"]
        html = self.render(document, "textbook", check_labels=CHECKLIST)
        counts = {label: html.count(label) for label in CHECKLIST}
        # The contract is one print per label. The old fixture prints each twice (section prose and
        # the practice block), which is the repeated-checklist defect named on this card.
        self.assertEqual(
            counts,
            {label: 1 for label in CHECKLIST},
            f"repeated checklist labels in the Textbook view: {counts}",
        )

    def test_structured_fixture_prints_each_label_once(self) -> None:
        lesson = self.prepare_lesson()
        blocks = [
            {
                "id": "blk_practice0001",
                "role": "practice",
                "headline": "Verify the workshop",
                "short": "Work the checklist.",
                "deep": "Work the checklist on the check surface and record each verified item.",
                "check_id": lesson["check_id"],
                "media": [],
                "source_ids": ["src_heat0001"],
            },
            {
                "id": "blk_orient000001",
                "role": "orient",
                "headline": "Before you start",
                "short": "Read the checklist, then verify each item on the check.",
                "deep": "The checklist is the check: verify each item there and record what you saw.",
                "check_id": None,
                "media": [],
                "source_ids": ["src_heat0001"],
            },
        ]
        document = lesson_document.document_from_blocks(
            blocks,
            section_title="Workshop checklist",
            objective_id=lesson["objective_id"],
            check_id=lesson["check_id"],
            source_ids=["src_heat0001"],
        )
        textbook = self.render(document, "textbook", check_labels=CHECKLIST)
        guided = self.render(document, "guided", check_labels=CHECKLIST)
        for html, view in ((textbook, "textbook"), (guided, "guided")):
            counts = {label: html.count(label) for label in CHECKLIST}
            self.assertEqual(counts, {label: 1 for label in CHECKLIST}, f"{view}: {counts}")


class StructuredCheckItemsSeamTest(RenderCase):
    """The card's second requirement: ``stimulus.items[]`` is the structured checklist.

    Contract v8's ``check_stimulus`` (``contracts/rpc.v8.json#/$defs/check_stimulus``) has exactly
    ``prompt``, ``format``, ``choices`` and ``learner_instructions``; ``domain._stimulus_view``
    projects that closed allowlist. A stored ``items[]`` is therefore dropped before any view can
    render it. These two tests state the requirement and stay red until the seam exists.
    """

    def store_stimulus(self, lesson: dict, stimulus: dict) -> None:
        self.execute(
            "UPDATE checks SET stimulus_json = ? WHERE id = ?",
            (json.dumps(stimulus), lesson["check_id"]),
        )

    def read_stimulus(self, lesson: dict) -> dict:
        return self.ok(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )["result"]["stimulus"]

    def test_closed_allowlist_drops_stored_items_today(self) -> None:
        """Characterisation: the seam is absent, measured through the shipped ``check.get``."""
        lesson = self.prepare_lesson()
        self.store_stimulus(
            lesson,
            {
                "prompt": "Verify each item in the workshop.",
                "format": "verification",
                "items": [
                    {"id": f"item_{index}", "label": label}
                    for index, label in enumerate(CHECKLIST, start=1)
                ],
            },
        )
        stimulus = self.read_stimulus(lesson)
        record(
            structured_items_seam={
                "stored_keys": ["prompt", "format", "items"],
                "served_keys": sorted(stimulus),
                "items_served": stimulus.get("items"),
                "expected_served_keys": [
                    "choices",
                    "format",
                    "items",
                    "learner_instructions",
                    "prompt",
                ],
                "verdict": "FAIL: contract v8 check_stimulus has no items[] and _stimulus_view drops it",
            }
        )
        self.assertEqual(sorted(stimulus), ["choices", "format", "learner_instructions", "prompt"])
        self.assertIsNone(stimulus.get("items"))

    @unittest.expectedFailure
    def test_check_get_serves_each_structured_item_label_once(self) -> None:
        lesson = self.prepare_lesson()
        self.store_stimulus(
            lesson,
            {
                "prompt": "Verify each item in the workshop.",
                "format": "verification",
                "items": [
                    {"id": f"item_{index}", "label": label}
                    for index, label in enumerate(CHECKLIST, start=1)
                ],
            },
        )
        stimulus = self.read_stimulus(lesson)
        labels = [item["label"] for item in stimulus.get("items") or []]
        self.assertEqual(labels, CHECKLIST)
        self.assertEqual(len(labels), len(set(labels)))

    @unittest.expectedFailure
    def test_duplicate_or_repeated_instructions_are_rejected(self) -> None:
        lesson = self.prepare_lesson()
        self.store_stimulus(
            lesson,
            {
                "prompt": "Verify each item in the workshop.",
                "format": "verification",
                "learner_instructions": "Verify each item in the workshop.",
                "items": [
                    {"id": "item_1", "label": "Check the heat"},
                    {"id": "item_2", "label": "check  the heat."},
                    {"id": "item_3", "label": "Check sharp objects"},
                ],
            },
        )
        error = self.err(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "objective_id": lesson["objective_id"]},
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
