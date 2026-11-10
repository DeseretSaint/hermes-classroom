"""GM-007: the away-from-screen homework domain, its policy and the Japanese fixtures.

These tests drive the real dispatcher against a real migrated SQLite database, and the real
print path (Chromium) where the runner has one. They pin the card's named behaviours:

* one task, one target, one context, 3-10 minutes, one observable success criterion;
* the generator refuses a generic "practise for ten minutes" card, multiple targets,
  surveillance, photo/geolocation and graded completion;
* completion is ``self_reported`` or ``parent_reported`` and never a pass, score or mastery;
* the one-page sheet carries no answer key and prints in black and white;
* every Japanese phrase, reading and register comes from the reviewed L0 lesson fixture;
* completing homework writes no attempt, evidence or engagement row.

The tests are named exactly as the GM-007 card names them.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from coursebook import db, domain, generation, homework as hw, homework_print as hp
from tests.kernel_support import KernelCase, criteria_with, numeric_spec

GEN_HASH = "sha256:" + "b" * 64
NOW = "2026-11-07T09:00:00Z"

#: An answer that exists only in the lesson's check reference. It must never reach the sheet.
ANSWER_MARKER = "REFERENCE-ONLY: you say itadakimasu before the first bite"
RUBRIC_MARKER = "RUBRIC-ONLY: the greeting is said at the table"

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS_PATH = ROOT / "bundled" / "homework" / "japanese-l0-mealtime" / "proposals.v1.json"


def lesson_page_sources(block: dict) -> list[dict]:
    """The lesson page's cited sources, in the shape ``generation`` writes.

    A real lesson page carries the ledger rows its target cites; homework resolves the target's
    ``source_ids`` against exactly this array, so the test page must carry it too.
    """
    ledger = hw.demo_proposals()["sources"]
    out: list[dict] = []
    for source_id in block["target"].get("source_ids") or []:
        source = ledger[source_id]
        out.append(
            {
                "source_id": source_id,
                "title": source["title"],
                "url": source["url"],
                "accessed": source["accessed"],
                "quote": source["quote"],
            }
        )
    return out


def japanese_page(title: str, proposal_id: str = "hw_premeal") -> dict:
    """A validated lesson page shaped the way ``generation`` writes ``gen_lessons.page_json``."""
    block = hw.demo_lesson_block(proposal_id)
    return {
        "section_title": title,
        "lesson_intent": "Say one meal greeting at your own table today.",
        "segments": [
            {
                "kind": "explain",
                "heading": "When the greeting is said",
                "body": "The greeting is said at the table, out loud, at the start of a meal.",
            }
        ],
        "check": {
            "kind": "short_answer",
            "stimulus": {"prompt": "Say the before-meal greeting.", "format": "short_text"},
            "learner_instructions": "Say it out loud.",
            "evidence_target": "production",
        },
        "sources": lesson_page_sources(block),
        "media": [],
        "homework": block,
    }


def plain_page(title: str, homework_block: dict | None = None) -> dict:
    page = {
        "section_title": title,
        "lesson_intent": "Sear the meat hard before the liquid goes in.",
        "segments": [{"kind": "explain", "heading": "Why", "body": "Browning builds flavour."}],
        "check": {
            "kind": "short_answer",
            "stimulus": {"prompt": "Describe the moment the ribs go in.", "format": "short_text"},
            "learner_instructions": "Write one sentence.",
            "evidence_target": "production",
        },
        "sources": [],
        "media": [],
    }
    if homework_block is not None:
        page["homework"] = homework_block
    return page


class HomeworkCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        with db.read() as connection:
            generation.ensure_schema(connection)

    # ── fixtures ────────────────────────────────────────────────────────────
    def seed(
        self,
        *,
        evidence_target: str = "production",
        locale: str = "ja-JP",
        page_factory=japanese_page,
        title: str = "Mealtime greetings",
    ) -> dict:
        created = self.ok(
            "course.create",
            {
                "title": "Japanese at home",
                "recipe": "committed",
                "goal": "Use one Japanese greeting at a real meal.",
                "locale": locale,
            },
        )["result"]
        course_id, plan_id = created["course_id"], created["plan_id"]
        objective_id = domain.record_objective(
            plan_id,
            title="Say the before-meal greeting",
            evidence_target=evidence_target,
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
                (lesson_id, plan_id, section_id, GEN_HASH, json.dumps(page_factory(title)), NOW, NOW),
            )
            connection.execute(
                "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
                " rubric_json, reference_json, locale, audit_state, state, created_at)"
                " VALUES (?, ?, 1, ?, ?, ?, ?, ?, 'passed', 'open', ?)",
                (
                    check_id,
                    objective_id,
                    evidence_target,
                    json.dumps({"prompt": "Say the greeting.", "format": "short_text"}),
                    json.dumps({"criteria": [{"criterion": "a", "description": RUBRIC_MARKER}]}),
                    json.dumps({"reference_answer": ANSWER_MARKER, "accepted_answers": []}),
                    locale,
                    NOW,
                ),
            )
            connection.execute(
                "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref)"
                " VALUES (?, ?, 1)",
                (lesson_id, check_id),
            )
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "lesson_version": f"{lesson_id}:v1",
        }

    def create(self, seeded: dict, *, context: str | None = None, audience: str = "learner",
               expected: int = 0, key: str | None = None) -> dict:
        payload = {
            "course_id": seeded["course_id"],
            "enrollment_id": seeded["enrollment_id"],
            "objective_id": seeded["objective_id"],
            "audience": audience,
            "source_lesson_version": seeded["lesson_version"],
            "context": context if context is not None else "At your own table, just before you eat today.",
        }
        return self.ok(
            "homework.create", payload, expected_revision=expected,
            idempotency_key=key or f"key-hw-{seeded['course_id']}-{audience}",
        )["result"]

    def counts(self) -> dict[str, int]:
        names = ("attempts", "evidence", "game_engagement", "notebook_entries", "transitions")
        out: dict[str, int] = {}
        with db.read() as connection:
            for table in names:
                try:
                    row = connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
                    out[table] = int(row["n"])
                except Exception:  # noqa: BLE001 - a table this build does not have counts as absent
                    out[table] = -1
        return out


class HomeworkCompletionTest(HomeworkCase):
    def test_homework_completion_is_self_reported(self) -> None:
        seeded = self.seed()
        made = self.create(seeded)
        self.assertEqual(made["state"], "proposed")

        done = self.ok(
            "homework.complete",
            {"task_id": made["task_id"], "actor": "learner", "note": "said it before dinner"},
            expected_revision=made["revision"],
        )["result"]
        self.assertEqual(done["state"], "self_reported_done")
        self.assertEqual(done["task"]["completion"]["basis"], "self_reported")
        self.assertFalse(done["task"]["completion"]["independent_verification"])
        self.assertTrue(done["task"]["completion"]["completed_at"])
        # Nothing about the completion is a grade or a mastery claim.
        flat = json.dumps(done["task"]).lower()
        for banned in ("pass", "mastery", "score", "grade", "verdict"):
            self.assertNotIn(banned, flat)
        self.assertEqual(done["task"]["state"], "self_reported_done")

        parent = self.ok(
            "homework.complete",
            {"task_id": made["task_id"], "actor": "parent", "note": ""},
            expected_revision=done["task"]["revision"],
        )
        # A second report is an idempotent read of the same honest state, never a second basis.
        self.assertEqual(parent["result"]["state"], "self_reported_done")

        other = self.create(seeded, audience="parent", key="key-hw-parent")
        reported = self.ok(
            "homework.complete",
            {"task_id": other["task_id"], "actor": "parent", "note": "did it at lunch"},
            expected_revision=other["revision"],
        )["result"]
        self.assertEqual(reported["state"], "parent_reported_done")
        self.assertEqual(reported["task"]["completion"]["basis"], "parent_reported")
        self.assertFalse(reported["task"]["completion"]["independent_verification"])


class HomeworkPolicyTest(HomeworkCase):
    def test_homework_rejects_generic_time_only_task(self) -> None:
        generic = {
            "task_kind": "practice",
            "title": "Practice Japanese",
            "target": {"display": "いただきます", "reading": "いただきます", "romaji": "itadakimasu",
                       "meaning": "thank you for the meal", "register": "polite (ます form)",
                       "source_ids": ["src_jisho_itadakimasu"]},
            "context": "Practise for ten minutes.",
            "steps": ["Practise for ten minutes."],
            "success_criterion": "Practise for ten minutes.",
            "estimated_minutes": 10,
        }
        seeded = self.seed(page_factory=lambda title: plain_page(title, generic))
        error = self.err(
            "homework.create",
            {
                "course_id": seeded["course_id"],
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_id"],
                "audience": "learner",
                "source_lesson_version": seeded["lesson_version"],
                "context": "Practise for ten minutes.",
            },
            expected_revision=0,
            idempotency_key="key-hw-generic",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "generic_task")
        # Nothing was written: a refused proposal leaves no task residue.
        with db.read() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM homework_tasks").fetchone()
        self.assertEqual(int(row["n"]), 0)

        # A lesson with no away-from-screen use at all is refused, not given a generic card.
        naive = self.seed(page_factory=lambda title: plain_page(title), title="Braising")
        refused = self.err(
            "homework.create",
            {
                "course_id": naive["course_id"],
                "enrollment_id": naive["enrollment_id"],
                "objective_id": naive["objective_id"],
                "audience": "learner",
                "source_lesson_version": naive["lesson_version"],
                "context": "At your own table.",
            },
            expected_revision=0,
            idempotency_key="key-hw-none",
        )
        self.assertEqual(refused["code"], "POLICY_VIOLATION")
        self.assertIn(refused["details"]["reason"], {"no_homework_proposal", "generic_task"})

        # A recall objective does not earn transfer homework.
        recall = self.seed(evidence_target="recall", title="Recall the greeting",
                           page_factory=lambda title: plain_page(
                               title, hw.demo_lesson_block("hw_premeal")))
        no_transfer = self.err(
            "homework.create",
            {
                "course_id": recall["course_id"],
                "enrollment_id": recall["enrollment_id"],
                "objective_id": recall["objective_id"],
                "audience": "learner",
                "source_lesson_version": recall["lesson_version"],
                "context": "At your own table.",
            },
            expected_revision=0,
            idempotency_key="key-hw-recall",
        )
        self.assertEqual(no_transfer["code"], "POLICY_VIOLATION")
        self.assertEqual(no_transfer["details"]["reason"], "no_transfer_target")

    def test_homework_has_one_target_and_context(self) -> None:
        seeded = self.seed()
        made = self.create(seeded)
        task = made["task"]
        self.assertEqual(task["state"], "proposed")
        self.assertTrue(task["target"]["display"])
        self.assertIsInstance(task["target"], dict)
        self.assertTrue(2 <= len(task["context"].split()) <= 40)
        self.assertNotIn(" and also ", task["context"].lower())
        self.assertTrue(1 <= len(task["steps"]) <= 3)
        self.assertTrue(3 <= int(task["estimated_minutes"]) <= 10)
        # One observable success criterion: a full sentence naming what was done.
        self.assertGreaterEqual(len(task["success_criterion"].split()), 6)

        two = {
            "task_kind": "real_world_use",
            "title": "Two greetings at once",
            "target": [
                {"display": "いただきます", "reading": "いただきます", "romaji": "itadakimasu",
                 "meaning": "before the meal", "register": "polite", "source_ids": []},
                {"display": "ごちそうさまでした", "reading": "ごちそうさまでした",
                 "romaji": "gochisōsamadeshita", "meaning": "after the meal", "register": "polite",
                 "source_ids": []},
            ],
            "context": "At your own table at one meal today.",
            "steps": ["Say both greetings."],
            "success_criterion": "You said both greetings at one meal today.",
            "estimated_minutes": 3,
        }
        multi = self.seed(page_factory=lambda title: plain_page(title, two), title="Two targets")
        error = self.err(
            "homework.create",
            {
                "course_id": multi["course_id"],
                "enrollment_id": multi["enrollment_id"],
                "objective_id": multi["objective_id"],
                "audience": "learner",
                "source_lesson_version": multi["lesson_version"],
                "context": "At your own table.",
            },
            expected_revision=0,
            idempotency_key="key-hw-multi",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "multiple_targets")


class HomeworkSheetTest(HomeworkCase):
    def sheet(self) -> tuple[dict, dict, str]:
        seeded = self.seed()
        made = self.create(seeded)
        task = self.ok("homework.read", {"task_id": made["task_id"]})["result"]["task"]
        return seeded, task, hw.sheet_html(task)

    def test_homework_sheet_has_no_answer_key(self) -> None:
        _seeded, task, html_text = self.sheet()
        text = hw.sheet_text(html_text)
        lowered = text.lower()
        self.assertIn(task["target"]["display"], text)
        self.assertIn(task["target"]["romaji"], text)
        self.assertIn(task["success_criterion"], text)
        # The lesson's reference answer and rubric must not reach the sheet.
        self.assertNotIn(ANSWER_MARKER, text)
        self.assertNotIn(RUBRIC_MARKER, text)
        self.assertNotIn("REFERENCE-ONLY", text)
        self.assertNotIn("RUBRIC-ONLY", text)
        for banned in ("answer guide", "expected response", "common error", "parent only",
                       "reference answer", "answer key"):
            self.assertNotIn(banned, lowered)
        self.assertNotIn("answers", lowered)
        # And the read view carries the same separation: no reference value anywhere.
        self.assertNotIn(ANSWER_MARKER, json.dumps(task))

    def test_homework_print_is_black_and_white_legible(self) -> None:
        _seeded, task, html_text = self.sheet()
        # Every colour the sheet can print is a grey value: no hue can carry meaning.
        colours = set(re.findall(r"#[0-9a-fA-F]{3,6}\b", html_text))
        self.assertTrue(colours)
        for value in colours:
            digits = value[1:]
            if len(digits) == 3:
                digits = "".join(digit * 2 for digit in digits)
            self.assertEqual(len(digits), 6, value)
            red, green, blue = (int(digits[index:index + 2], 16) for index in (0, 2, 4))
            self.assertEqual((red, green, blue), (red, red, red), f"{value} is not a grey value")
        for word in ("green", "red", "blue", "amber", "gold", "colour-coded", "color-coded"):
            self.assertNotIn(word, html_text.lower())

        self.assertTrue(hw.sheet_is_single_page(html_text), "the sheet must be one page")

        if not shutil.which("pdftoppm"):
            self.skipTest("pdftoppm is not installed")
        try:
            hp.chromium_binary()
        except hp.PrintUnavailable:
            self.skipTest("Chromium is not installed")
        with tempfile.TemporaryDirectory(prefix="gm007-print-") as tmp:
            pdf = hp.write_pdf(html_text, Path(tmp) / "sheet.pdf")
            info = hp.pdf_info(pdf)
            self.assertEqual(str(info["Pages"]), "1")
            text = hp.pdf_text(pdf)
            for needle in (task["target"]["display"], task["target"]["romaji"],
                           task["success_criterion"], "3 minutes", "Date"):
                self.assertIn(needle, text)
            prefix = Path(tmp) / "sheet"
            subprocess.run(
                ["pdftoppm", "-gray", "-r", "150", str(pdf), str(prefix)],
                check=True, capture_output=True, timeout=120,
            )
            page = sorted(Path(tmp).glob("sheet-*.pgm"))[0]
            coverage = dark_fraction(page)
            self.assertGreater(coverage, 0.001, "the page carries no ink")
            self.assertLess(coverage, 0.12, "the sheet is a low-ink field card, not a slab of ink")

    def test_homework_sheet_marks_every_japanese_run(self) -> None:
        """Every Japanese text run on every printed card sits inside ``lang="ja"``."""
        for proposal in hw.demo_proposals()["proposals"]:
            proposal_id = proposal["proposal_id"]
            html_text = hw.sheet_html(demo_task(proposal_id))
            scanner = JapaneseRunScanner()
            scanner.feed(html_text)
            with self.subTest(proposal=proposal_id):
                self.assertTrue(scanner.marked, "the card carries no marked Japanese at all")
                self.assertEqual(scanner.unmarked, [], f"{proposal_id}: unmarked Japanese runs")

    def test_homework_sheet_completion_line_matches_the_report(self) -> None:
        """The tick line says what actually happened, and the future tense only before a report."""
        base = demo_task("hw_cafe")
        base["completion_record"] = []
        cases = (
            ({"completion": {"basis": None}, "audience": "parent"},
             "A parent will record this", ("recorded this", "recorded by the learner")),
            ({"completion": {"basis": "parent_reported"}, "audience": "parent"},
             "A parent recorded this", ("will record", "recorded by the learner")),
            ({"completion": {"basis": "self_reported"}, "audience": "learner"},
             "recorded by the learner", ("will record", "A parent recorded this")),
        )
        for extra, expected, forbidden in cases:
            task = {**base, **extra}
            text = hw.sheet_text(hw.sheet_html(task))
            with self.subTest(extra=extra):
                self.assertIn(expected, text)
                for absent in forbidden:
                    self.assertNotIn(absent, text)


class HomeworkProvenanceTest(HomeworkCase):
    def test_homework_source_phrase_is_sourced(self) -> None:
        data = hw.demo_proposals()
        self.assertEqual(hw.validate_proposals(data), [])
        reviewed = hp.load_fixture()
        targets = hp.target_index(reviewed)
        labels = hp.label_index(reviewed)

        by_id = {proposal["proposal_id"]: proposal for proposal in data["proposals"]}
        # The three lesson tasks are the reviewed L0 lesson's own tasks, verbatim.
        for proposal_id, fixture_task_id in (
            ("hw_premeal", "hw_premeal"),
            ("hw_postmeal", "hw_postmeal"),
            ("hw_labels", "hw_labels"),
        ):
            original = hp.task_by_id(reviewed, fixture_task_id)
            proposal = by_id[proposal_id]
            for field in ("task_kind", "title", "context", "steps", "success_criterion",
                          "estimated_minutes"):
                self.assertEqual(proposal[field], original[field], (proposal_id, field))

        # A greeting's display/reading/romaji/register are the reviewed lesson's values.
        for proposal_id, target_id in (("hw_premeal", "tgt_itadakimasu"),
                                       ("hw_postmeal", "tgt_gochisousama")):
            target = by_id[proposal_id]["target"]
            source = targets[target_id]
            for field in ("display", "reading", "romaji", "meaning", "register", "source_ids"):
                self.assertEqual(target[field], source[field], (proposal_id, field))

        # The label task resolves to the lesson's own label words, not invented prose.
        labels_proposal = by_id["hw_labels"]
        self.assertEqual(labels_proposal["target"]["label_ids"],
                         ["lbl_doa", "lbl_mado", "lbl_isu"])
        for label_id in labels_proposal["target"]["label_ids"]:
            self.assertEqual(label_index_display(data, label_id), labels[label_id]["display"])

        # The optional cafe question is its own sourced entry, and it says so.
        cafe = by_id["hw_cafe"]
        self.assertTrue(cafe["optional"])
        self.assertEqual(cafe["target"]["display"], "これはいくらですか")
        sources = data["sources"]
        for source_id in cafe["target"]["source_ids"]:
            with self.subTest(source=source_id):
                source = sources[source_id]
                self.assertTrue(source["url"].startswith("https://"))
                self.assertRegex(source["accessed"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(source["quote"].strip())
        quotes = " ".join(sources[source_id]["quote"] for source_id in cafe["target"]["source_ids"])
        self.assertIn("how much", quotes.lower())
        self.assertIn("this", quotes.lower())

        # Every proposal target resolves to at least one cited source.
        for proposal in data["proposals"]:
            with self.subTest(proposal=proposal["proposal_id"]):
                self.assertTrue(proposal["target"]["source_ids"])
                for source_id in proposal["target"]["source_ids"]:
                    self.assertIn(source_id, sources)

    def test_homework_does_not_create_attempt_or_evidence(self) -> None:
        seeded = self.seed()
        before = self.counts()
        made = self.create(seeded)
        read = self.ok("homework.read", {"task_id": made["task_id"]})["result"]
        self.assertTrue(read["events"])
        self.assertEqual(read["events"][0]["kind"], "proposed")
        done = self.ok(
            "homework.complete",
            {"task_id": made["task_id"], "actor": "learner", "note": "at dinner"},
            expected_revision=made["revision"],
        )["result"]
        skipped_source = self.create(seeded, audience="parent", key="key-hw-skip")
        self.ok(
            "homework.skip",
            {"task_id": skipped_source["task_id"], "actor": "parent"},
            expected_revision=skipped_source["revision"],
        )
        after = self.counts()
        self.assertEqual(before, after, "homework wrote a private learning row")
        self.assertNotEqual(done["state"], "proposed")

        read_after = self.ok("homework.read", {"task_id": made["task_id"]})["result"]
        kinds = [event["kind"] for event in read_after["events"]]
        self.assertEqual(kinds, ["proposed", "self_reported"])
        self.assertTrue(all(event["actor"] in ("learner", "parent")
                            for event in read_after["events"]))
        # The read view is the notebook/Parent Studio view: one page, no chat, no course.
        self.assertEqual(read_after["task"]["sheet"]["pages"], 1)
        self.assertNotIn("thread", json.dumps(read_after).lower())


class HomeworkDemoRoundTripTest(HomeworkCase):
    """Every required demo card is creatable, readable, sourced and free of an orphan row."""

    def test_homework_creates_and_reads_every_demo_proposal(self) -> None:
        for proposal in hw.demo_proposals()["proposals"]:
            proposal_id = proposal["proposal_id"]
            seeded = self.seed(page_factory=lambda title, pid=proposal_id: japanese_page(title, pid),
                               title=f"Card {proposal_id}")
            created = self.create(seeded, key=f"key-{proposal_id}")
            self.assertEqual(created["state"], "proposed", proposal_id)
            read = self.ok("homework.read", {"task_id": created["task_id"]})["result"]
            task = read["task"]
            with self.subTest(proposal=proposal_id):
                self.assertEqual(task["target"]["display"], proposal["target"]["display"])
                # The read view resolves the target's cited sources from the lesson page.
                self.assertTrue(task["sources"], f"{proposal_id}: read view has no sources")
                cited = {source["source_id"] for source in task["sources"]}
                self.assertEqual(cited, set(proposal["target"]["source_ids"]))
                self.assertIn("Source:", task["sheet"]["text"])
                for source in task["sources"]:
                    self.assertTrue(source["url"].startswith("https://"))
                    self.assertIn(source["title"], task["sheet"]["text"])
                if proposal["target"].get("label_ids"):
                    self.assertEqual(task["target"]["label_ids"],
                                     proposal["target"]["label_ids"])

    def test_homework_rejects_unsourced_phrase(self) -> None:
        """A target citing an id the lesson page does not carry is refused, not printed."""
        block = hw.demo_lesson_block("hw_premeal")
        block["target"]["display"] = "でたらめなことば"
        block["target"]["reading"] = "でたらめなことば"
        block["target"]["source_ids"] = ["src_not_in_any_ledger"]
        page = japanese_page("Unsourced")
        page["homework"] = block
        page["sources"] = []
        seeded = self.seed(page_factory=lambda title: page, title="Unsourced card")
        error = self.err(
            "homework.create",
            {
                "course_id": seeded["course_id"],
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_id"],
                "audience": "learner",
                "source_lesson_version": seeded["lesson_version"],
                "context": "At your own table, just before you eat today.",
            },
            expected_revision=0,
            idempotency_key="key-hw-unsourced",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "unsourced_target")
        with db.read() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM homework_tasks").fetchone()
        self.assertEqual(int(row["n"]), 0, "an unsourced target left a task row")

    def test_homework_contract_refusal_commits_nothing(self) -> None:
        """A result the wire contract would reject must not be committed first."""
        block = hw.demo_lesson_block("hw_premeal")
        block["title"] = "Say the before-meal greeting at one meal " + "x" * 240
        page = japanese_page("Long title")
        page["homework"] = block
        seeded = self.seed(page_factory=lambda title: page, title="Long title card")
        response = self.dispatch(
            "homework.create",
            {
                "course_id": seeded["course_id"],
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_id"],
                "audience": "learner",
                "source_lesson_version": seeded["lesson_version"],
                "context": "At your own table, just before you eat today.",
            },
            expected_revision=0,
            idempotency_key="key-hw-long-title",
        )
        self.assertFalse(response["ok"])
        with db.read() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM homework_tasks").fetchone()
        self.assertEqual(int(row["n"]), 0, "a contract-refused create left a task row")


class JapaneseRunScanner(HTMLParser):
    """Collect text nodes carrying Japanese, split by whether an ancestor carries ``lang="ja"``."""

    _VOID = {"meta", "link", "br", "hr", "img", "input", "source"}
    _JP = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[bool] = []
        self.marked = 0
        self.unmarked: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001 - stdlib signature
        if tag in self._VOID:
            return
        inside = bool(self.stack and self.stack[-1]) or dict(attrs).get("lang") == "ja"
        self.stack.append(inside)

    def handle_endtag(self, tag):  # noqa: ANN001 - stdlib signature
        if tag not in self._VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data):  # noqa: ANN001 - stdlib signature
        if not self._JP.search(data):
            return
        if self.stack and self.stack[-1]:
            self.marked += 1
        else:
            self.unmarked.append(data.strip())


def demo_task(proposal_id: str) -> dict:
    """The printable task for one demo proposal, the way the sheet and proof build it."""
    block = hw.demo_lesson_block(proposal_id)
    return {
        "title": block["title"],
        "target": block["target"],
        "context": block["context"],
        "steps": block["steps"],
        "success_criterion": block["success_criterion"],
        "estimated_minutes": block["estimated_minutes"],
        "completion_record": block.get("completion_record") or [],
        "sources": [
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "url": source["url"],
                "accessed": source["accessed"],
            }
            for source in lesson_page_sources(block)
        ],
        "completion": {"basis": None},
    }


def label_index_display(data: dict, label_id: str) -> str:
    for label in data["labels"]:
        if label["label_id"] == label_id:
            return label["display"]
    raise AssertionError(label_id)


def dark_fraction(pgm: Path) -> float:
    """Fraction of pixels darker than mid-grey in a binary PGM page."""
    raw = pgm.read_bytes()
    if not raw.startswith(b"P5"):
        raise AssertionError("not a P5 PGM")
    # header: P5 <width> <height> <maxval>\n
    parts = raw.split(maxsplit=4)
    width, height, maxval = int(parts[1]), int(parts[2]), int(parts[3])
    body = parts[4]
    if body[:1] == b"\n":
        body = body[1:]
    threshold = maxval // 2
    dark = sum(1 for value in body[: width * height] if value < threshold)
    return dark / float(width * height)


if __name__ == "__main__":
    unittest.main()
