"""Source ledger, refresh staleness and the grading gate that refuses stale checks."""

from __future__ import annotations

import json
import unittest

from coursebook import db, generation, research, sources
from tests.kernel_support import KernelCase


def bounded(text: str) -> str:
    return " ".join(text.split())[:40000]


class SourceCase(KernelCase):
    def link_source(self, lesson: dict, *, cited: bool = True, content: str = "old body",
                    status: str = "model_assessed") -> tuple[str, str]:
        """Seed one ledger row, one plan section citing it, and the prior run snapshot."""
        source_id = "src_ledger_1"
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at,"
                " support_status, claim_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, lesson["course_id"], "https://example.test/page", "Example page",
                 "web", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", status, 1,
                 "2026-02-01T00:00:00Z"),
            )
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
                " objective_refs_json, context_needs_json, source_ids_json) VALUES (?,?,?,?,?,?,?,?,?)",
                ("sec_1", lesson["plan_id"], 1, "planhash", "Section", "Learn",
                 json.dumps([1]), "[]", json.dumps([source_id] if cited else [])),
            )
            connection.execute(
                "INSERT INTO gen_research_runs (id, course_id, job_id, status, queries_json,"
                " sources_json, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
                ("run_1", lesson["course_id"], None, "ok", "[]",
                 json.dumps([{"source_id": source_id, "url": "https://example.test/page",
                              "content_hash": research.sha256_of_text(bounded(content))}]),
                 None, "2026-02-01T00:00:00Z"),
            )
        return source_id, content

    def refresh(self, source_id: str, content: str | None):
        with db.transaction() as connection:
            return sources.refresh(
                connection, source_id,
                {"content": content, "title": "Example page"} if content is not None else None,
            )


class LedgerTest(SourceCase):
    def test_ledger_reports_dates_and_support_status(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson)
        with db.read() as connection:
            rows = sources.ledger(connection, lesson["course_id"])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["source_id"], source_id)
        self.assertEqual(row["url"], "https://example.test/page")
        self.assertEqual(row["fetched_at"], "2026-02-01T00:00:00Z")
        self.assertEqual(row["published_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(row["support_status"], "model_assessed")
        self.assertFalse(row["stale"])

    def test_unreachable_source_stays_historical_and_needs_review(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson)
        result = self.refresh(source_id, None)
        self.assertEqual(result.support_status, "unreachable")
        self.assertFalse(result.changed)
        self.assertTrue(result.review_required)
        with db.read() as connection:
            rows = sources.ledger(connection, lesson["course_id"])
        self.assertTrue(rows[0]["stale"])
        self.assertEqual(rows[0]["fetched_at"], "2026-02-01T00:00:00Z", "an unreachable fetch is not a fetch")


class StalenessTest(SourceCase):
    def test_changed_source_marks_dependent_check_stale(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, content="the old procedure")
        result = self.refresh(source_id, "a completely revised procedure")
        self.assertTrue(result.changed)
        self.assertEqual(result.support_status, "stale")
        self.assertIn(lesson["check_id"], result.impact["check_ids"])
        self.assertIn(lesson["objective_id"], result.impact["objective_ids"])

    def test_stale_check_refuses_grading_and_creates_no_attempt(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, content="old")
        transitions_before = self.scalar("SELECT COUNT(*) FROM transitions")
        self.refresh(source_id, "new")
        error = self.submit(lesson, {"kind": "text", "text": "4"})
        self.assertFalse(error["ok"])
        self.assertEqual(error["error"]["code"], "CHECK_STALE")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions"), transitions_before)

    def test_unchanged_source_keeps_grading_available(self) -> None:
        lesson = self.prepare_lesson()
        source_id, content = self.link_source(lesson, content="stable body")
        result = self.refresh(source_id, content)
        self.assertFalse(result.changed)
        self.assertTrue(result.to_dict()["review_required"] is False)
        response = self.submit(lesson, {"kind": "text", "text": "4"})
        self.assertTrue(response["ok"], response)

    def test_a_source_no_section_cites_does_not_pause_the_check(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, cited=False, content="old")
        self.refresh(source_id, "new")
        response = self.submit(lesson, {"kind": "text", "text": "4"})
        self.assertTrue(response["ok"], response)

    def test_apply_run_marks_changed_sources_stale(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, content="old")
        run = research.ResearchRun(
            status="ok",
            queries=[],
            sources=[
                research.SourceRecord(
                    source_id=source_id,
                    url="https://example.test/page",
                    title="Example page",
                    publisher="example.test",
                    source_type="web",
                    fetched_at="2026-03-01T00:00:00Z",
                    published_at=None,
                    content_hash=research.sha256_of_text(bounded("changed body")),
                )
            ],
        )
        with db.transaction() as connection:
            marked = sources.apply_run(connection, lesson["course_id"], run)
        self.assertEqual(len(marked["stale"]), 1)
        self.assertIn(lesson["check_id"], marked["stale"][0]["impact"]["check_ids"])
        with db.read() as connection:
            status = connection.execute("SELECT support_status FROM sources WHERE id = ?", (source_id,)).fetchone()[0]
        self.assertEqual(status, "stale")


if __name__ == "__main__":
    unittest.main()
