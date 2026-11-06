"""CB-015 residual proof: ``source.revalidate`` and cb.db v4 against the real kernel.

``tests/test_contracts.py`` proves the v7/v4 contract set is coherent; it cannot prove that

* a pack-imported source with no ``gen_research_runs`` snapshot establishes a real baseline and is
  *not* reported changed on its first revalidation,
* an identical re-fetch keeps grading available, a changed one marks the row ``stale`` and the real
  ``attempt.submit`` handler then refuses it with ``CHECK_STALE`` without writing an attempt,
* the impact lists exactly the objectives, checks, artifacts and lessons the section citations give,
* idempotent replay returns the stored original and the same key with different content conflicts,
* learner evidence row counts are unchanged across the whole sequence, and
* the library row emits ``warning: "stale_source"`` without a second query by the client.

This module drives the shipped commands through ``api.dispatch`` — the same handlers the Desktop
calls — against a real database created by the real migrations, and validates every result against
``rpc.v7.json``.

Run it in a worktree that contains the backend kernel:

    python3 -m unittest scripts.proof_contract_v7 -v

It is a proof, not a gate: ``tests/test_contracts.py`` is the gate that must pass everywhere.
"""

from __future__ import annotations

# This module is branch-dependent by design: it imports the Python kernel, so static analysis on a
# branch without it reports unresolved imports.
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportPossiblyUnboundVariable=false, reportGeneralTypeIssues=false, reportAssignmentType=false, reportArgumentType=false

import json
import os
import unittest

from coursebook import contracts

try:  # The kernel and its fixtures live on Cinder's backend branches.
    from coursebook import api, db, generation, research
    from coursebook.api import RpcError
    from tests.kernel_support import KernelCase, request

    _KERNEL_AVAILABLE = True
    _KERNEL_WHY = ""
except ImportError as exc:  # pragma: no cover - depends on the branch being checked out
    _KERNEL_AVAILABLE = False
    _KERNEL_WHY = f"needs the Python kernel (coursebook/domain.py, tests/kernel_support.py): {exc}"

    class KernelCase(unittest.TestCase):  # type: ignore[no-redef]
        """Placeholder so the module imports (and skips honestly) where the kernel is absent."""


def _dispatch(method: str, payload: dict, **kwargs) -> dict:
    """Run the shipped handler through the real dispatch seam, not a local re-derivation."""
    response = api.dispatch(request(method, payload, **kwargs))
    if not response["ok"]:
        raise RpcError(response["error"])
    return response


@unittest.skipUnless(_KERNEL_AVAILABLE, _KERNEL_WHY)
class V7SourceRevalidateProof(KernelCase):
    def assert_valid(self, method: str, result: dict) -> None:
        contracts.validate_response_payload(method, result)

    # ── fixtures ────────────────────────────────────────────────────────────

    def seed_pack_source(self, lesson: dict) -> tuple[str, str, str]:
        """Seed a pack-style source: a ledger row, one citing section, one artifact and one lesson.

        No ``gen_research_runs`` row is written. That is the demo course's shape (pack import writes
        sources through ``pack_flow._write_sources``), and it is exactly the case where the old
        snapshot-only comparison had no baseline.
        """
        source_id = "src_proof_v7"
        artifact_id = "art_proof_v7"
        lesson_id = "lsn_proof_v7"
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at,"
                " support_status, claim_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, lesson["course_id"], "https://example.test/proof", "Proof page", "web",
                 "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "model_assessed", 2,
                 "2026-02-01T00:00:00Z"),
            )
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
                " objective_refs_json, context_needs_json, source_ids_json) VALUES (?,?,?,?,?,?,?,?,?)",
                ("sec_proof_v7", lesson["plan_id"], 1, "planhash", "Proof section", "Learn",
                 json.dumps([1]), "[]", json.dumps([source_id])),
            )
            connection.execute(
                "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
                " provenance_json, ref_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (artifact_id, lesson["course_id"], "visual", research.sha256_of_text("proof visual"),
                 "artifacts/proof.txt", 13, "text/plain",
                 json.dumps({"source_id": source_id, "origin": "research"}), 1,
                 "2026-02-01T00:00:00Z"),
            )
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
                " media_json, rejection_reasons_json, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (lesson_id, lesson["plan_id"], "sec_proof_v7", "planhash", 1, "ok", "{}",
                 "[]", "[]", "2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z"),
            )
        return source_id, artifact_id, lesson_id

    def revalidate(self, source_id: str, content: str | None, *, key: str | None = None) -> dict:
        fetched = None if content is None else {"content": content}
        return _dispatch(
            "source.revalidate",
            {"source_id": source_id, "fetched": fetched},
            idempotency_key=key or f"proof-revalidate-{os.urandom(6).hex()}",
        )

    def counts(self) -> dict[str, int]:
        return {
            table: int(self.scalar(f"SELECT COUNT(*) FROM {table}"))
            for table in ("attempts", "transitions", "evidence")
        }

    # ── proofs ──────────────────────────────────────────────────────────────

    def test_contract_and_storage_versions(self) -> None:
        self.assertEqual(contracts.audit_contracts(), [])
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 7)
        self.assertEqual(contracts.contract_version("cb.rpc"), 7)
        self.assertEqual(contracts.contract_version("cb.db"), 4)
        self.assertEqual(api.implemented_methods().count("source.revalidate"), 1)
        self.assertEqual(int(self.scalar("PRAGMA user_version") or 0), 0,
                         "schema version lives in schema_migrations, not PRAGMA user_version")
        self.assertEqual(int(self.scalar("SELECT MAX(version) FROM schema_migrations")), 4)

    def test_baseline_identical_change_impact_and_gate(self) -> None:
        lesson = self.prepare_lesson()
        source_id, artifact_id, lesson_id = self.seed_pack_source(lesson)
        revision_before = int(self.scalar(
            "SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],)
        ))
        counts_before = self.counts()

        first = self.revalidate(source_id, "captured page text")
        self.assertEqual(first["revision"], 0)
        self.assert_valid("source.revalidate", first["result"])
        baseline_hash = research.sha256_of_text("captured page text")
        self.assertIsNone(first["result"]["previous_hash"], "a pack source starts with no baseline")
        self.assertFalse(first["result"]["changed"], "recording a baseline is not a change")
        self.assertEqual(first["result"]["content_hash"], baseline_hash)
        self.assertEqual(first["result"]["support_status"], "model_assessed")
        self.assertFalse(first["result"]["review_required"])
        self.assertEqual(
            self.scalar("SELECT content_hash FROM sources WHERE id = ?", (source_id,)), baseline_hash
        )

        identical = self.revalidate(source_id, "captured page text")
        self.assertFalse(identical["result"]["changed"])
        self.assertEqual(identical["result"]["previous_hash"], baseline_hash)
        self.assertEqual(identical["result"]["support_status"], "model_assessed")
        self.assertFalse(identical["result"]["review_required"])
        # Identical re-fetch keeps grading available: an attempt commits normally.
        graded = self.submit(lesson, {"kind": "text", "text": "4"})
        self.assertTrue(graded["ok"], graded)

        after_identical = self.counts()
        changed = self.revalidate(source_id, "a materially revised page")
        self.assertTrue(changed["result"]["changed"])
        self.assertEqual(changed["result"]["previous_hash"], baseline_hash)
        self.assertEqual(changed["result"]["content_hash"],
                         research.sha256_of_text("a materially revised page"))
        self.assertEqual(changed["result"]["support_status"], "stale")
        self.assertTrue(changed["result"]["review_required"])
        self.assert_valid("source.revalidate", changed["result"])

        impact = changed["result"]["impact"]
        self.assertEqual(impact["objective_ids"], [lesson["objective_id"]])
        self.assertEqual(impact["check_ids"], [lesson["check_id"]])
        self.assertEqual(impact["artifact_ids"], [artifact_id])
        self.assertEqual(impact["lesson_ids"], [lesson_id])
        self.assertEqual(impact["course_id"], lesson["course_id"])
        self.assertEqual(impact["support_status"], "stale")

        counts_before_gate = self.counts()
        refused = self.submit(lesson, {"kind": "text", "text": "4"})
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["error"]["code"], "CHECK_STALE")
        self.assertEqual(self.counts(), counts_before_gate)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM attempts WHERE enrollment_id = ?", (lesson["enrollment_id"],)
            ),
            1,
            "only the pre-change attempt exists; the stale submit wrote nothing",
        )
        self.assertEqual(
            int(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (lesson["enrollment_id"],))),
            revision_before + 1,
            "the source transition moved no enrollment revision",
        )
        self.assertEqual(
            self.counts()["attempts"] - counts_before["attempts"], 1,
            "exactly the identical-fetch attempt was written across the whole sequence",
        )

        library = _dispatch("library.list", {"filter": "all"})["result"]
        row = next(item for item in library["items"]
                   if item["enrollment_id"] == lesson["enrollment_id"])
        self.assertEqual(row["warning"], "stale_source")

    def test_idempotent_replay_and_payload_conflict(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _, _ = self.seed_pack_source(lesson)
        self.revalidate(source_id, "baseline text", key="proof-baseline")

        first = self.revalidate(source_id, "first revision", key="proof-replay")
        self.assertTrue(first["result"]["changed"])
        replay = self.revalidate(source_id, "first revision", key="proof-replay")
        self.assertEqual(replay["result"], first["result"])
        self.assertEqual(replay["revision"], 0)

        response = api.dispatch(request(
            "source.revalidate",
            {"source_id": source_id, "fetched": {"content": "a different revision"}},
            idempotency_key="proof-replay",
        ))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(
            self.scalar("SELECT support_status FROM sources WHERE id = ?", (source_id,)), "stale"
        )

    def test_unreachable_keeps_history_and_last_baseline(self) -> None:
        lesson = self.prepare_lesson()
        source_id, _, _ = self.seed_pack_source(lesson)
        baseline = self.revalidate(source_id, "last reachable text")["result"]

        unreachable = self.revalidate(source_id, None)["result"]
        self.assertFalse(unreachable["changed"])
        self.assertEqual(unreachable["support_status"], "unreachable")
        self.assertTrue(unreachable["review_required"])
        self.assertEqual(unreachable["fetched_at"], baseline["fetched_at"],
                         "an unreachable fetch is not a fetch")
        self.assertEqual(
            self.scalar("SELECT content_hash FROM sources WHERE id = ?", (source_id,)),
            baseline["content_hash"],
            "the last known baseline survives an unreachable fetch",
        )


if __name__ == "__main__":
    unittest.main()
