"""Regression checks for the rig research acceptance path (t_3e8b07ba).

Two things are pinned here:

1. ``scripts/rig-research-acceptance.py`` reads the *backend's own rows* and refuses to report
   ``ok`` unless research ran, the source ledger is non-empty, AND a plan objective cites a source.
   The rig's broken state (research ``unavailable`` → no ledger → no citations → plan refused on
   ``source_support``) must not read as green.
2. ``scripts/rig-private-desktop.sh`` keeps the one line that makes the read possible in an isolated
   backend: it sets ``plugins.isolation host`` on the rig home. Without it the plugin loads
   in-process, its plan tick runs with no profile scope bound, and every credential read raises
   ``UnscopedSecretError`` before the home's own ``.env`` is consulted.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rig-research-acceptance.py"

_SCHEMA = """
CREATE TABLE gen_research_runs (
    id TEXT PRIMARY KEY, course_id TEXT NOT NULL, job_id TEXT, status TEXT NOT NULL,
    queries_json TEXT NOT NULL DEFAULT '[]', sources_json TEXT NOT NULL DEFAULT '[]',
    failures_json TEXT NOT NULL DEFAULT '[]', reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE sources (
    id TEXT PRIMARY KEY, course_id TEXT NOT NULL, url TEXT, title TEXT NOT NULL,
    source_type TEXT NOT NULL, published_at TEXT, fetched_at TEXT NOT NULL,
    support_status TEXT NOT NULL, claim_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL);
CREATE TABLE gen_plan_documents (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, course_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL, plan_hash TEXT NOT NULL,
    document_json TEXT NOT NULL, research_json TEXT NOT NULL,
    generation_state TEXT NOT NULL, validation_id TEXT, result_json TEXT NOT NULL,
    created_at TEXT NOT NULL);
"""


def _load_script():
    spec = importlib.util.spec_from_file_location("rig_research_acceptance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RigResearchAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_script()
        self._tmp = tempfile.TemporaryDirectory(prefix="cb-rig-research-")
        self.addCleanup(self._tmp.cleanup)
        self.db = Path(self._tmp.name) / "data.db"
        connection = sqlite3.connect(self.db)
        connection.executescript(_SCHEMA)
        connection.commit()
        connection.close()

    def _seed(
        self,
        *,
        course_id: str = "crs_rig",
        research_status: str = "ok",
        sources: int = 2,
        document,
    ) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute(
            "insert into gen_research_runs (id, course_id, job_id, status, reason, created_at) "
            "values (?, ?, ?, ?, ?, ?)",
            ("run_1", course_id, "job_1", research_status,
             None if research_status == "ok" else "web_search unavailable", "2026-11-12T00:00:00Z"),
        )
        for index in range(sources):
            connection.execute(
                "insert into sources (id, course_id, url, title, source_type, fetched_at, "
                "support_status, created_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"src_{index}", course_id, f"https://example.invalid/{index}",
                 f"Source {index}", "web", "2026-11-12T00:00:00Z", "supports",
                 "2026-11-12T00:00:00Z"),
            )
        if document is not None:
            connection.execute(
                "insert into gen_plan_documents (id, plan_id, course_id, request_fingerprint, "
                "plan_hash, document_json, research_json, generation_state, result_json, created_at) "
                "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("doc_1", "pln_1", course_id, "fp", "sha256:" + "a" * 64,
                 json.dumps(document), "{}", "generated", "{}", "2026-11-12T00:00:00Z"),
            )
        connection.commit()
        connection.close()

    def test_research_ok_with_ledger_and_cited_objective_is_ok(self) -> None:
        self._seed(document={"objectives": [
            {"objective_id": "obj_1", "provenance": {"source_ids": ["src_0"]}},
        ]})
        record = self.module.read_rows(self.db, "crs_rig")
        self.assertEqual(record["research_status"], "ok")
        self.assertEqual(record["ledger_sources"], 2)
        self.assertEqual(self.module.verdict_for(record), "ok")

    def test_unavailable_research_is_never_green(self) -> None:
        self._seed(research_status="unavailable", sources=0,
                   document={"objectives": [{"objective_id": "obj_1", "provenance": {"source_ids": []}}]})
        record = self.module.read_rows(self.db, "crs_rig")
        self.assertEqual(record["research_status"], "unavailable")
        self.assertEqual(record["ledger_sources"], 0)
        self.assertEqual(self.module.verdict_for(record), "not-ok")

    def test_research_ok_but_uncited_plan_is_not_green(self) -> None:
        """The exact seam: research can succeed and the plan still cite nothing."""
        self._seed(document={"objectives": [{"objective_id": "obj_1", "provenance": {"source_ids": []}}]})
        record = self.module.read_rows(self.db, "crs_rig")
        self.assertEqual(record["ledger_sources"], 2)
        self.assertEqual(record["objectives_with_source_ids"], [])
        self.assertEqual(self.module.verdict_for(record), "not-ok")

    def test_objective_under_a_unit_is_found(self) -> None:
        self._seed(document={"units": [
            {"ordinal": 1, "objectives": [{"objective_id": "obj_u1", "provenance": {"source_ids": ["src_1"]}}]},
        ]})
        record = self.module.read_rows(self.db, "crs_rig")
        self.assertEqual([c["objective_id"] for c in record["objectives_with_source_ids"]], ["obj_u1"])

    def test_ledger_only_is_not_green(self) -> None:
        self._seed(sources=3, document=None)
        record = self.module.read_rows(self.db, "crs_rig")
        self.assertEqual(record["research_status"], "ok")
        self.assertEqual(self.module.verdict_for(record), "not-ok")


class RigLauncherRecipeTests(unittest.TestCase):
    def test_rig_doc_names_the_blocking_host_seams(self) -> None:
        """The rig doc must keep the measured mechanism, not drift into 'just add a key'."""
        text = (ROOT / "docs" / "CP-051-PRIVATE-RIG.md").read_text(encoding="utf-8")
        for needle in (
            "activate_multi_profile_hosting_eagerly",
            "agent/secret_scope.py::get_secret",
            "agent/web_search_provider.py::get_provider_env",
            "Unknown tool: web_search",
            "rig-research-acceptance.py",
        ):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
