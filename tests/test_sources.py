"""Source ledger, refresh staleness and the grading gate that refuses stale checks."""

from __future__ import annotations

import json
import os
import sqlite3
import unittest
from unittest import mock

from coursebook import db, generation, research, sources
from tests.kernel_support import KernelCase


def bounded(text: str) -> str:
    return " ".join(text.split())[:40000]


class SourceCase(KernelCase):
    def link_source(self, lesson: dict, *, cited: bool = True, content: str = "old body",
                    status: str = "model_assessed", run_snapshot: bool = True) -> tuple[str, str]:
        """Seed one ledger row, one plan section citing it, and optionally the prior run snapshot."""
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
            if run_snapshot:
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


class SourceRevalidateRpcTest(SourceCase):
    """``source.revalidate`` is the wire surface that makes staleness reachable.

    The ledger's internal ``sources.refresh`` existed but no cb.rpc method called it, so neither the
    Desktop nor a reviewer could produce the state that ``CHECK_STALE`` guards. These tests drive
    the shipped handler through ``api.dispatch`` — never the helper directly.
    """

    def revalidate(self, source_id: str, content: str | None, *, key: str | None = None,
                   title: str | None = None) -> dict:
        fetched = None if content is None else {"content": content}
        if fetched is not None and title is not None:
            fetched["title"] = title
        return self.dispatch(
            "source.revalidate",
            {"source_id": source_id, "fetched": fetched},
            idempotency_key=key or f"reval-{os.urandom(6).hex()}",
        )

    def evidence_counts(self) -> tuple[int, int, int]:
        return (
            int(self.scalar("SELECT COUNT(*) FROM attempts")),  # type: ignore[arg-type]
            int(self.scalar("SELECT COUNT(*) FROM transitions")),  # type: ignore[arg-type]
            int(self.scalar("SELECT COUNT(*) FROM evidence")),  # type: ignore[arg-type]
        )

    def test_pack_source_baseline_then_change_stales_through_cb_rpc(self) -> None:
        lesson = self.prepare_lesson()
        # Pack-imported sources have no gen_research_runs snapshot: their baseline is the new column.
        source_id, _ = self.link_source(lesson, run_snapshot=False)

        first = self.revalidate(source_id, "first capture")
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["revision"], 0, "a source is course-scoped; no enrollment revision moves")
        body = first["result"]
        baseline_hash = research.sha256_of_text("first capture")
        self.assertIsNone(body["previous_hash"])
        self.assertFalse(body["changed"])
        self.assertEqual(body["content_hash"], baseline_hash)
        self.assertEqual(body["support_status"], "model_assessed")
        self.assertFalse(body["review_required"])
        self.assertEqual(body["impact"]["objective_ids"], [lesson["objective_id"]])
        self.assertEqual(body["impact"]["check_ids"], [lesson["check_id"]])
        self.assertEqual(body["impact"]["artifact_ids"], [])
        self.assertEqual(
            self.scalar("SELECT content_hash FROM sources WHERE id = ?", (source_id,)), baseline_hash
        )

        identical = self.revalidate(source_id, "first capture")["result"]
        self.assertFalse(identical["changed"])
        self.assertEqual(identical["previous_hash"], baseline_hash)
        self.assertEqual(identical["support_status"], "model_assessed")

        changed = self.revalidate(source_id, "a revised capture")["result"]
        self.assertTrue(changed["changed"])
        self.assertEqual(changed["previous_hash"], baseline_hash)
        self.assertEqual(changed["content_hash"], research.sha256_of_text("a revised capture"))
        self.assertEqual(changed["support_status"], "stale")
        self.assertTrue(changed["review_required"])
        self.assertEqual(
            self.scalar("SELECT support_status FROM sources WHERE id = ?", (source_id,)), "stale"
        )

        before = self.evidence_counts()
        refused = self.submit(lesson, {"kind": "text", "text": "4"})
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["error"]["code"], "CHECK_STALE")
        self.assertEqual(self.evidence_counts(), before, "stale detection must not rewrite learner evidence")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)

        library = self.ok("library.list", {"filter": "all"})["result"]
        row = next(item for item in library["items"] if item["enrollment_id"] == lesson["enrollment_id"])
        self.assertEqual(row["warning"], "stale_source")

    def test_replay_returns_the_original_and_a_different_payload_conflicts(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, run_snapshot=False, content="baseline")
        self.revalidate(source_id, "baseline", key="baseline-key")

        first = self.revalidate(source_id, "changed body", key="replay-key")
        self.assertTrue(first["ok"], first)
        self.assertTrue(first["result"]["changed"])
        replay = self.revalidate(source_id, "changed body", key="replay-key")
        self.assertEqual(replay["result"], first["result"])
        self.assertEqual(replay["revision"], first["revision"])

        conflict = self.revalidate(source_id, "different body", key="replay-key")
        self.assertFalse(conflict["ok"])
        self.assertEqual(conflict["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(
            self.scalar("SELECT support_status FROM sources WHERE id = ?", (source_id,)), "stale"
        )

    def test_unreachable_keeps_the_recorded_baseline_and_needs_review(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, run_snapshot=False)
        baseline = self.revalidate(source_id, "still here")["result"]
        fetched_at = baseline["fetched_at"]

        unreachable = self.revalidate(source_id, None)["result"]
        self.assertFalse(unreachable["changed"])
        self.assertEqual(unreachable["support_status"], "unreachable")
        self.assertTrue(unreachable["review_required"])
        self.assertEqual(unreachable["fetched_at"], fetched_at, "an unreachable fetch is not a fetch")
        self.assertEqual(unreachable["content_hash"], None)
        self.assertEqual(
            self.scalar("SELECT content_hash FROM sources WHERE id = ?", (source_id,)),
            baseline["content_hash"],
            "the last known baseline is not erased by an unreachable fetch",
        )

    def test_revalidation_racing_a_grade_is_refused_at_commit(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, run_snapshot=False)
        self.revalidate(source_id, "old procedure", key="race-baseline")

        original = __import__("coursebook.grading", fromlist=["grade"]).grade

        def revalidate_while_grading(*args, **kwargs):
            # The realistic race: the parent revalidates after the answer was read but before the
            # attempt commits. The commit re-check must refuse, not write a cold attempt.
            self.ok(
                "source.revalidate",
                {"source_id": source_id, "fetched": {"content": "revised procedure"}},
                idempotency_key="race-revalidate",
            )
            return original(*args, **kwargs)

        with mock.patch("coursebook.grading.grade", side_effect=revalidate_while_grading):
            response = self.submit(lesson, {"kind": "text", "text": "4"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "CHECK_STALE")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)


class _UnreadableTable:
    """A connection proxy that fails reads of exactly one table, like a corrupt database page.

    Every other statement reaches the real short-lived connection, so the rest of the kernel
    behaves normally and the test isolates the one dependency read.
    """

    def __init__(self, connection: sqlite3.Connection, table: str, error: Exception) -> None:
        self._connection = connection
        self._table = table
        self._error = error

    def execute(self, sql: str, parameters: tuple = ()):
        if self._table in sql:
            raise self._error
        return self._connection.execute(sql, parameters)

    def __getattr__(self, name: str):
        return getattr(self._connection, name)


class UnknownDependencyTest(SourceCase):
    """H-123: a dependency read that fails is *unknown*, never "nothing depends on this"."""

    def broken_table(self, table: str):
        """Patch the connection seam so only ``table`` is unreadable."""
        real_connect = db.connect
        error = sqlite3.DatabaseError("database disk image is malformed")

        def connect():
            return _UnreadableTable(real_connect(), table, error)

        return mock.patch.object(db, "connect", side_effect=connect)

    def test_unreadable_plan_sections_refuse_grading_instead_of_passing(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, content="old")
        self.refresh(source_id, "revised")
        # Baseline: the same store refuses grading while the section table is readable.
        self.assertEqual(self.submit(lesson, {"kind": "text", "text": "4"})["error"]["code"], "CHECK_STALE")

        before = (self.scalar("SELECT COUNT(*) FROM attempts"),
                  self.scalar("SELECT COUNT(*) FROM evidence"),
                  self.scalar("SELECT COUNT(*) FROM transitions"))
        with self.broken_table("gen_plan_sections"):
            response = self.submit(lesson, {"kind": "text", "text": "4"})

        self.assertFalse(response["ok"], "an unverifiable stale-source gate must not grade")
        self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")
        self.assertEqual(response["error"]["details"]["reason"], "source_dependencies_unknown")
        self.assertTrue(response["error"]["retryable"])
        self.assertEqual(
            (self.scalar("SELECT COUNT(*) FROM attempts"),
             self.scalar("SELECT COUNT(*) FROM evidence"),
             self.scalar("SELECT COUNT(*) FROM transitions")),
            before,
            "the refusal must write no attempt, evidence or transition",
        )

    def test_unreadable_lessons_never_shorten_the_impact_list(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _ = self.link_source(lesson, content="old")
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                " page_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ("les_h123_1", lesson["plan_id"], "sec_1", "planhash", 1, "draft", "{}",
                 "2026-02-02T00:00:00Z", "2026-02-02T00:00:00Z"),
            )

        with db.read() as connection:
            self.assertIn("les_h123_1", sources.impact(connection, source_id)["lesson_ids"])

        with self.broken_table("gen_lessons"), db.read() as connection:
            with self.assertRaises(sources.DependencyStateUnknown):
                sources.impact(connection, source_id)

    def test_a_table_the_schema_never_had_is_honestly_empty(self) -> None:
        """A store that never ran generation has no ``gen_lessons``: that absence is a fact."""
        course_id, plan_id = self.new_course()
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute("DROP TABLE gen_lessons")  # simulate a pre-generation store
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at,"
                " fetched_at, support_status, claim_count, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("src_h123_bare", course_id, "https://example.test/bare", "Bare", "web", None,
                 "2026-02-01T00:00:00Z", "model_assessed", 0, "2026-02-01T00:00:00Z"),
            )
        with db.read() as connection:
            result = sources.impact(connection, "src_h123_bare")
        self.assertEqual(result["lesson_ids"], [])
        self.assertEqual(result["objective_ids"], [])
        self.assertEqual(result["course_id"], course_id)


if __name__ == "__main__":
    unittest.main()
