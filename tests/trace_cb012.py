"""Produce the CB-012 review trace: real job rows, artifact hashes, usage and fallbacks.

Run from the repo root:
    python3 -m tests.trace_cb012

Writes ``docs/REVIEW_CB012-trace.json``. Everything in it comes from a real migrated SQLite
database under a throwaway ``HERMES_HOME``; nothing is copied from a test assertion.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from coursebook import artifacts, db, job_service, research, sources, workers


class TraceSeam:
    def search(self, query: str, limit: int) -> list[dict]:
        return [{"url": f"https://example.test/source-{index}", "title": f"Source {index}",
                 "description": "bounded"} for index in range(1)]

    def fetch(self, url: str, max_chars: int) -> dict:
        return {
            "url": url,
            "title": "Authoritative reference",
            "publisher": "example.test",
            "published_at": "2025-05-01",
            "content": "A bounded, deterministic source body used for the trace. " * 12,
        }


def main() -> int:
    home = tempfile.mkdtemp(prefix="cb012-trace-")
    previous = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = home
    try:
        db.migrate()
        from coursebook import domain

        course_id = domain.course_create(
            {"title": "Trace course", "recipe": "casual", "goal": "Braise safely"}, {}
        )[1]["course_id"]

        research_request = workers.ResearchRequest(goal="braise short ribs safely", course_id=course_id)
        research_job = workers.run_research_job(research_request, lambda _lease: TraceSeam())

        def schematic() -> bytes:
            return artifacts.make_schematic_svg(
                "Braising temperatures", [{"label": "Oven", "value": "150 C", "row": 1},
                                          {"label": "Internal", "value": "95 C", "row": 2}]
            )

        store = artifacts.ArtifactStore(Path(home) / "artifacts")
        spec = artifacts.MediaSpec(kind="visual", role="schematic",
                                   text_equivalent="Oven 150 C; internal 95 C",
                                   facts={"rows": 2})
        media_job = workers.run_media_job(
            workers.MediaRequest(spec=spec, producer=schematic, mime="image/svg+xml",
                                 course_id=course_id, source_texts=("facts-v1",),
                                 provenance={"provider": "deterministic.schematic"}),
            store=store,
        )

        voice = artifacts.MediaSpec(kind="audio", role="narration", text_equivalent="Transcript text",
                                    voice="ja-voice-a", language="ja-JP", transcript="Transcript text")

        def no_voice() -> bytes:
            raise artifacts.MediaUnavailable("voice ja-voice-a is not installed")

        fallback = artifacts.produce_with_fallback(store, voice, no_voice, course_id=course_id,
                                                   mime="audio/wav")

        # ── cb.rpc dispatcher trace: jobs.create -> queued -> claimed -> completed ──────
        # Every mutation below goes through the frozen envelope and the same dispatcher the
        # Desktop pane uses, so the trace proves the handler wiring, not just the service.
        from coursebook import api

        def dispatch(method: str, payload: dict, *, expected_revision: int | None = None,
                     idempotency_key: str | None = None) -> dict:
            body = {
                "contract": api.RPC_CONTRACT,
                "contract_version": api.RPC_CONTRACT_VERSION,
                "method": method,
                "operation_id": f"trace-{method.replace('.', '-')}",
                "payload": payload,
            }
            if expected_revision is not None:
                body["expected_revision"] = expected_revision
            if idempotency_key is not None:
                body["idempotency_key"] = idempotency_key
            return api.dispatch(body)

        created = dispatch("jobs.create", {"kind": "research", "brief": {"goal": "trace dispatcher job"}})
        assert created["ok"], created
        trace_job_id = created["result"]["job_id"]
        lifecycle = [{"step": "jobs.create", "state": created["result"]["state"],
                      "revision": created["revision"]}]
        lease = job_service.claim(trace_job_id, owner="trace-worker")
        lifecycle.append({"step": "claim", "state": "running", "attempt_id": lease.attempt_id})
        lifecycle.append({"step": "finish", "state": job_service.finish(lease)})
        fetched = dispatch("jobs.get", {"job_id": trace_job_id})
        lifecycle.append({"step": "jobs.get", "state": fetched["result"]["job"]["state"]})
        assert fetched["result"]["job"]["state"] == "completed", fetched

        # ── cb.rpc dispatcher trace: a stale source refuses grading with CHECK_STALE ────
        trace_course = dispatch(
            "course.create", {"title": "Trace stale course", "recipe": "committed", "goal": "Braise"}
        )["result"]
        trace_plan_id = trace_course["plan_id"]
        trace_spec = {
            "audit_state": "passed",
            "stimulus": {"prompt": "Compute the answer."},
            "reference": {"kind": "numeric", "value": "4", "tolerance": {"abs": "0"}},
            "rubric": {"construct": "procedure", "pass_rule": "all",
                       "criteria": [{"id": "c1", "description": "Correct value"}]},
        }
        objective_id = domain.record_objective(
            trace_plan_id, title="Compute", evidence_target="procedure",
            criteria=[{"id": "c1", "description": "graded criterion", "check_spec": trace_spec}],
        )
        enrollment_id = dispatch(
            "enrollment.create", {"course_id": trace_course["course_id"], "learner_label": "Trace"}
        )["result"]["enrollment_id"]
        approved_revision = dispatch(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": trace_plan_id,
             "plan_hash": domain.plan_hash(trace_plan_id)},
            expected_revision=0,
        )["result"]["revision"]
        opened = dispatch(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=approved_revision,
        )["result"]

        from coursebook import generation
        from coursebook import sources as source_ledger

        source_id = "src_trace_stale_1"
        with db.transaction() as connection:
            generation.ensure_schema(connection)
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at,"
                " support_status, claim_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, trace_course["course_id"], "https://example.test/trace", "Trace source",
                 "web", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "model_assessed", 1,
                 "2026-02-01T00:00:00Z"),
            )
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
                " objective_refs_json, context_needs_json, source_ids_json) VALUES (?,?,?,?,?,?,?,?,?)",
                ("sec_trace_1", trace_plan_id, 1, domain.plan_hash(trace_plan_id), "Trace section",
                 "Learn", "[1]", "[]", json.dumps([source_id])),
            )
            connection.execute(
                "INSERT INTO gen_research_runs (id, course_id, job_id, status, queries_json,"
                " sources_json, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
                ("run_trace_1", trace_course["course_id"], None, "ok", "[]",
                 json.dumps([{"source_id": source_id, "url": "https://example.test/trace",
                              "content_hash": research.sha256_of_text("old body")}]),
                 None, "2026-02-01T00:00:00Z"),
            )
        with db.transaction() as connection:
            refreshed = source_ledger.refresh(
                connection, source_id, {"content": "new body", "title": "Trace source"}
            )
        stale = dispatch(
            "attempt.submit",
            {"enrollment_id": enrollment_id, "check_id": opened["check_id"],
             "check_version": opened["check_version"], "attempt_nonce": "trace-stale-nonce",
             "answer": {"kind": "text", "text": "4"}},
            expected_revision=opened["revision"],
            idempotency_key="trace-stale-key",
        )
        assert stale["ok"] is False and stale["error"]["code"] == "CHECK_STALE", stale
        with db.read() as connection:
            attempts_after_stale = connection.execute("SELECT COUNT(*) AS n FROM attempts").fetchone()["n"]
        assert attempts_after_stale == 0, attempts_after_stale

        # Restart reconciliation against a job left running by a dead worker.
        dead = job_service.create("export", {"goal": "trace"})["job_id"]
        job_service.claim(dead, owner="dead-worker")
        reconciliation = job_service.reconcile_startup(artifact_store=store)

        with db.read() as connection:
            artifact_rows = [dict(row) for row in connection.execute(
                "SELECT * FROM artifacts ORDER BY created_at")]
            usage_rows = [dict(row) for row in connection.execute(
                "SELECT provider, model, tokens_json, duration_ms, artifact_count, operation_id"
                " FROM usage_events ORDER BY recorded_at")]
            source_rows = [dict(row) for row in connection.execute("SELECT * FROM sources")]
            job_rows = [dict(row) for row in connection.execute("SELECT * FROM jobs ORDER BY created_at")]

        artifact_report = []
        for row in artifact_rows:
            path = Path(str(row["path"]))
            data = path.read_bytes() if path.exists() else b""
            artifact_report.append(
                {
                    "artifact_id": row["id"],
                    "kind": row["kind"],
                    "mime": row["mime"],
                    "bytes": len(data),
                    "content_hash": f"sha256:{hashlib.sha256(data).hexdigest()}",
                    "db_content_hash": row["content_hash"],
                    "path_name": path.name,
                    "provenance": json.loads(row["provenance_json"]),
                }
            )

        payload = {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "schema_version": db.applied_schema_version(),
            "jobs": [
                {
                    "job_id": row["id"], "kind": row["kind"], "state": row["state"],
                    "attempt_id": row["attempt_id"], "operation_id": row["operation_id"],
                    "checkpoint": json.loads(row["checkpoint_json"] or "{}"),
                    "progress": json.loads(row["progress_json"] or "{}"),
                    "error": json.loads(row["error_json"] or "{}"),
                }
                for row in job_rows
            ],
            "research_job": research_job,
            "media_job": media_job,
            "artifact_hashes_match_db": all(
                item["content_hash"] == f"sha256:{item['db_content_hash']}" for item in artifact_report
            ),
            "artifacts": artifact_report,
            "usage_ledger": usage_rows,
            "source_ledger": [
                {"source_id": row["id"], "url": row["url"], "title": row["title"],
                 "fetched_at": row["fetched_at"], "published_at": row["published_at"],
                 "support_status": row["support_status"]}
                for row in source_rows
            ],
            "fallback": fallback.to_dict(),
            "restart_reconciliation": reconciliation,
            "dispatcher_job_lifecycle": {
                "job_id": trace_job_id,
                "steps": lifecycle,
                "final_state": fetched["result"]["job"]["state"],
            },
            "dispatcher_stale_refusal": {
                "refresh": {
                    "source_id": refreshed.source_id,
                    "support_status": refreshed.support_status,
                    "changed": refreshed.changed,
                    "review_required": refreshed.review_required,
                },
                "error": stale["error"],
                "attempts_written": attempts_after_stale,
            },
            "dead_job_state": next(
                (row["state"] for row in job_rows if row["id"] == dead), None
            ),
        }
        target = Path(__file__).resolve().parent.parent / "docs" / "REVIEW_CB012-trace.json"
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {target}")
        print(f"jobs={len(payload['jobs'])} artifacts={len(artifact_report)} usage={len(usage_rows)}")
        print(f"research_state={research_job['state']} media_state={media_job['state']} "
              f"fallback_degraded={fallback.degraded}")
        return 0
    finally:
        if previous is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
