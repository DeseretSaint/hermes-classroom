#!/usr/bin/env python3
"""H-187 live-generation worker — one scope, one isolated home, the real product path.

Runs, in a fresh ``HERMES_HOME`` with no demo pack and no recorded transcripts:

    course.create -> enrollment.create -> jobs.create(stage=plan)
        -> executor.pump_once (real bounded tick) -> plan rows
        -> plan.approve (kernel hash fence)
        -> jobs.create(stage=lessons) x N units -> executor.pump_once
        -> lesson.page

Nothing is faked: ``ctx.llm`` is the host ``agent.plugin_llm.PluginLlm``, the validator is a
second host route bound through ``generation.bind_validator_llm``, and research is the host's own
``web_search``/``web_extract`` through ``coursebook.research.HermesToolSearch``. No transcript is
edited and no fixture model is used.

The result file records stored rows only (plus the RPC answers the kernel returned).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone

AGENT_ROOT = os.environ.get("HERMES_AGENT_ROOT", os.path.expanduser("~/.hermes/hermes-agent"))
sys.path.insert(0, AGENT_ROOT)
sys.path.insert(0, os.environ.get("COURSEBOOK_SOURCE", str(__import__("pathlib").Path(__file__).resolve().parents[3])))

from coursebook import api, db, domain, executor, generation, job_service, research  # noqa: E402,F401
from coursebook.contracts import WIRE_CONTRACT_VERSION as RPC_CONTRACT_VERSION  # noqa: E402

TERMINAL = {"completed", "completed_late", "failed", "cancelled"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def dispatch(method: str, payload: dict, *, expected_revision=None, key=None) -> dict:
    request = {
        "contract": "cb.rpc",
        "contract_version": RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"h187-{method.replace('.', '-')}-{time.time_ns()}",
        "payload": payload,
    }
    if key:
        request["idempotency_key"] = key
    if expected_revision is not None:
        request["expected_revision"] = expected_revision
    response = api.dispatch(request)
    if not response.get("ok"):
        raise RuntimeError(f"{method} refused: {json.dumps(response.get('error'))}")
    return response["result"]


class SearchHost:
    """The host context's tool dispatcher, the same object ``register(ctx)`` hands the plugin."""

    @staticmethod
    def dispatch_tool(name: str, args: dict, **_kwargs):
        import asyncio

        from tools.web_tools import web_extract_tool, web_search_tool

        if name == "web_search":
            return web_search_tool(str(args.get("query") or ""), int(args.get("limit") or 5))
        if name == "web_extract":
            urls = args.get("urls") or []
            return asyncio.run(web_extract_tool(urls, char_limit=int(args.get("char_limit") or 15000)))
        raise RuntimeError(f"search host does not serve tool {name!r}")


def load_seams() -> dict:
    from agent.plugin_llm import PluginLlm

    llm = PluginLlm(plugin_id="coursebook")
    generation.bind_host_llm(llm)
    generation.bind_validator_llm(
        llm,
        provider=os.environ.get("H187_VALIDATOR_PROVIDER") or None,
        model=os.environ.get("H187_VALIDATOR_MODEL") or None,
    )
    research.bind_host_seam(SearchHost())
    return generation.validator_config()


def job_row(job_id: str) -> dict | None:
    with db.read() as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return None if row is None else job_service.job_view(row)


def run_job(job_id: str, *, max_seconds: float, label: str) -> dict:
    """Drive one real ``executor.pump_once`` and follow the job to a terminal state."""
    started = time.time()
    holder: dict = {}

    def _pump() -> None:
        try:
            holder["finished"] = [str(item.get("job_id")) for item in executor.pump_once(limit=1)]
        except Exception as exc:  # noqa: BLE001
            holder["error"] = f"{type(exc).__name__}: {exc}"
            holder["traceback"] = traceback.format_exc()
        holder["done_at_s"] = round(time.time() - started, 1)

    thread = threading.Thread(target=_pump, name=f"h187-pump-{label}", daemon=True)
    thread.start()
    timeline = []
    last_state = None
    terminal = None
    while True:
        elapsed = round(time.time() - started, 1)
        view = job_row(job_id)
        state = (view or {}).get("state")
        progress = (view or {}).get("progress") or {}
        if state != last_state:
            timeline.append({
                "elapsed_s": elapsed, "state": state,
                "stage": progress.get("stage"), "message": progress.get("message"),
            })
            log(f"{label}: state -> {state} at {elapsed}s (stage={progress.get('stage')} msg={progress.get('message')})")
            last_state = state
        if state in TERMINAL:
            terminal = view
            break
        if elapsed >= max_seconds:
            terminal = view
            holder["bound_exceeded"] = True
            log(f"{label}: bound {max_seconds}s exceeded; state={state}")
            try:
                holder["cancel"] = dispatch("jobs.cancel", {"job_id": job_id})
            except Exception as exc:  # noqa: BLE001
                holder["cancel_error"] = f"{type(exc).__name__}: {exc}"
            deadline = time.time() + 30
            while time.time() < deadline:
                view = job_row(job_id)
                if (view or {}).get("state") in TERMINAL:
                    terminal = view
                    break
                time.sleep(1)
            break
        time.sleep(2)
    thread.join(timeout=15)
    return {
        "label": label,
        "job_id": job_id,
        "pump": holder,
        "thread_alive": thread.is_alive(),
        "timeline": timeline,
        "elapsed_s": round(time.time() - started, 1),
        "terminal_state": (terminal or {}).get("state"),
        "final_job": terminal,
    }


def plan_facts(plan_id: str) -> dict:
    """Every plan fact this worker reports, read from stored rows."""
    facts: dict = {"plan_id": plan_id}
    with db.read() as connection:
        plan = connection.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if plan is None:
            facts["error"] = "plan row missing"
            return facts
        facts["plan_state"] = plan["state"]
        facts["plan_hash"] = plan["plan_hash"]
        facts["approved_at"] = plan["approved_at"]
        doc = connection.execute(
            "SELECT * FROM gen_plan_documents WHERE plan_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (plan_id,),
        ).fetchone()
        objectives = connection.execute(
            "SELECT id, ordinal, title, unit_id FROM objectives WHERE plan_id = ? ORDER BY ordinal",
            (plan_id,),
        ).fetchall()
        facts["objectives"] = [
            {"objective_id": row["id"], "ordinal": int(row["ordinal"]), "title": row["title"],
             "unit_id": row["unit_id"]}
            for row in objectives
        ]
        try:
            units = connection.execute(
                "SELECT * FROM plan_units WHERE plan_id = ? ORDER BY ordinal", (plan_id,)
            ).fetchall()
        except Exception:  # noqa: BLE001 - table may not exist on a non-blueprint plan
            units = []
        unit_rows = []
        for unit in units:
            row = {key: unit[key] for key in unit.keys() if key != "prereq_unit_ordinals_json"}
            refs = unit["prereq_unit_ordinals_json"] if "prereq_unit_ordinals_json" in unit.keys() else None
            row["prerequisite_refs"] = json.loads(refs or "[]") if refs is not None else []
            unit_rows.append(row)
        facts["units"] = unit_rows
        if doc is None:
            facts["generation"] = None
            return facts
        stored = json.loads(doc["document_json"] or "{}")
        plan_doc = stored.get("plan") if isinstance(stored.get("plan"), dict) else stored
        research_doc = json.loads(doc["research_json"] or "{}")
        result = json.loads(doc["result_json"] or "{}")
        record = generation.validation_record(connection, doc["validation_id"]) if doc["validation_id"] else None
        facts["generation"] = {
            "generation_state": doc["generation_state"],
            "plan_hash": doc["plan_hash"],
            "plan_schema": plan_doc.get("plan_schema"),
            "document_plan_state": plan_doc.get("state"),
            "status": result.get("status"),
            "validation_verdict": result.get("validation_verdict"),
            "validation": result.get("validation"),
            "validation_record": record,
            "rejection_reasons": result.get("rejection_reasons") or [],
            "approval_provenance": result.get("approval_provenance"),
            "budget": result.get("budget"),
            "domain_provenance": result.get("domain_provenance"),
            "title": plan_doc.get("title"),
            "goal": plan_doc.get("goal"),
            "learner_outcome": plan_doc.get("learner_outcome"),
            "delivery": plan_doc.get("delivery"),
            "spaced_review": plan_doc.get("spaced_review"),
            "time_estimate": plan_doc.get("time_estimate"),
            "objective_titles": [o.get("title") for o in plan_doc.get("objectives") or []],
            "units_in_document": [
                {"ordinal": u.get("ordinal"), "title": u.get("title"),
                 "prerequisites": u.get("prerequisite_ordinals") or u.get("prerequisites") or []}
                for u in plan_doc.get("units") or []
            ],
            "check_plan": plan_doc.get("check_plan") or [],
            "section_count": len(plan_doc.get("sections") or []),
        }
        facts["research"] = {
            "status": research_doc.get("status"),
            "reason": research_doc.get("reason"),
            "queries": [q.get("query") if isinstance(q, dict) else q for q in research_doc.get("queries") or []],
            "query_count": len(research_doc.get("queries") or []),
            "sources": [
                {"source_id": s.get("source_id"), "title": s.get("title"), "url": s.get("url"),
                 "fetched_at": s.get("fetched_at"), "excerpt_chars": len(s.get("excerpt") or ""),
                 "support": s.get("support")}
                for s in research_doc.get("sources") or []
            ],
            "source_count": len(research_doc.get("sources") or []),
            "failures": research_doc.get("failures") or [],
            "failure_count": len(research_doc.get("failures") or []),
        }
    return facts


def usage_facts(job_ids: list[str]) -> dict:
    rows = []
    with db.read() as connection:
        for job_id in job_ids:
            for row in connection.execute(
                "SELECT provider, model, tokens_json, duration_ms, recorded_at FROM usage_events"
                " WHERE operation_id = ? ORDER BY recorded_at",
                (job_id,),
            ).fetchall():
                tokens = json.loads(row["tokens_json"] or "{}")
                rows.append({
                    "job_id": job_id,
                    "provider": row["provider"],
                    "model": row["model"],
                    "tokens": tokens,
                    "duration_ms": row["duration_ms"],
                    "recorded_at": row["recorded_at"],
                })
    totals: dict = {"calls": len(rows), "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    by_model: dict = {}
    for row in rows:
        tokens = row["tokens"] or {}
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            totals[key] += int(tokens.get(key) or 0)
        identity = f"{row['provider']}/{row['model']}"
        bucket = by_model.setdefault(identity, {"calls": 0, "total_tokens": 0})
        bucket["calls"] += 1
        bucket["total_tokens"] += int(tokens.get("total_tokens") or 0)
    totals["by_model"] = by_model
    return {"totals": totals, "events": rows}


def lesson_facts(plan_id: str, enrollment_id: str) -> dict:
    with db.read() as connection:
        lessons = connection.execute(
            "SELECT id, section_id, state, plan_hash, version, validation_id, rejection_reasons_json"
            " FROM gen_lessons WHERE plan_id = ? ORDER BY created_at, rowid",
            (plan_id,),
        ).fetchall()
        rows = []
        for row in lessons:
            record = generation.validation_record(connection, row["validation_id"]) if row["validation_id"] else None
            rows.append({
                "lesson_id": row["id"],
                "section_id": row["section_id"],
                "state": row["state"],
                "plan_hash": row["plan_hash"],
                "version": int(row["version"]),
                "validation_id": row["validation_id"],
                "validation_outcome": (record or {}).get("outcome"),
                "validation_independence": (record or {}).get("independence"),
                "rejection_reasons": json.loads(row["rejection_reasons_json"] or "[]"),
            })
        # The first objective that has a servable page, resolved by the same join lesson.page uses.
        page_objective = connection.execute(
            "SELECT o.id AS objective_id, o.ordinal, o.title, l.state"
            " FROM gen_plan_sections s"
            " JOIN objectives o ON o.plan_id = s.plan_id"
            "   AND o.ordinal = json_extract(s.objective_refs_json, '$[0]')"
            " JOIN gen_lessons l ON l.section_id = s.id AND l.plan_hash = s.plan_hash"
            " WHERE s.plan_id = ? AND l.state IN ('validated', 'model_assessed')"
            " ORDER BY o.ordinal",
            (plan_id,),
        ).fetchall()
    return {
        "rows": rows,
        "states": sorted({row["state"] for row in rows}),
        "servable_objectives": [
            {"objective_id": row["objective_id"], "ordinal": int(row["ordinal"]),
             "title": row["title"], "lesson_state": row["state"]}
            for row in page_objective
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--subject-domain", default=None)
    parser.add_argument("--depth", default="working")
    parser.add_argument("--pace", default="light")
    parser.add_argument("--assessment", default="none")
    parser.add_argument("--autonomy", default="guided")
    parser.add_argument("--units", type=int, default=1, help="units to author via lessons jobs")
    parser.add_argument("--max-seconds", type=float, default=900)
    parser.add_argument("--result", required=True)
    parser.add_argument("--job-id", default=None,
                        help="resume an already-created plan job (its brief supplies the ids)")
    args = parser.parse_args()

    started = time.time()
    result: dict = {
        "tag": args.tag,
        "scope": args.scope,
        "recipe": args.recipe,
        "goal": args.goal,
        "title": args.title,
        "dial_s": {"depth": args.depth, "pace": args.pace,
                   "assessment": args.assessment, "autonomy": args.autonomy},
        "subject_domain": args.subject_domain,
        "wire_contract_version": RPC_CONTRACT_VERSION,
        "started_at": now_iso(),
        "phases": {},
    }

    def save() -> None:
        with open(args.result, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)

    def phase(name: str) -> dict:
        block = {"started_at": now_iso()}
        result["phases"][name] = block
        return block

    try:
        result["validator_config"] = load_seams()
        log(f"seams bound; validator={json.dumps(result['validator_config'])}")
        db.ensure_schema()
        result["schema_version"] = db.applied_schema_version()

        dials = dict(result["dial_s"])
        if args.job_id:
            with db.read() as connection:
                row = connection.execute("SELECT brief_json, checkpoint_json FROM jobs WHERE id = ?",
                                         (args.job_id,)).fetchone()
            existing = json.loads(row["brief_json"] or "{}")
            checkpoint = json.loads(row["checkpoint_json"] or "{}") if row else {}
            course = {"course_id": existing.get("course_id"), "plan_id": checkpoint.get("plan_id")}
            enrollment = {"enrollment_id": existing.get("enrollment_id")}
            job = {"job_id": args.job_id, "state": "existing"}
            plan_id = course["plan_id"]
            result["course"] = course
            result["enrollment"] = enrollment
            result["plan_job"] = job
            log(f"resuming existing job {args.job_id}: course={course['course_id']} plan={plan_id}")
        else:
            payload = {"title": args.title, "recipe": args.recipe, "goal": args.goal,
                       "dials": dials, "scope": args.scope}
            if args.subject_domain:
                payload["subject_domain"] = args.subject_domain
            course = dispatch("course.create", payload, key=f"h187-{args.tag}-course")
            enrollment = dispatch("enrollment.create",
                                  {"course_id": course["course_id"], "learner_label": args.title},
                                  key=f"h187-{args.tag}-enroll")
            brief = {"stage": "plan", "course_id": course["course_id"],
                     "enrollment_id": enrollment["enrollment_id"], "goal": args.goal,
                     "recipe": args.recipe, "dials": dials, "scope": args.scope}
            if args.subject_domain:
                brief["subject_domain"] = args.subject_domain
            job = dispatch("jobs.create", {"kind": "plan", "brief": brief}, key=f"h187-{args.tag}-plan")
            result["course"] = course
            result["enrollment"] = enrollment
            result["plan_job"] = job
            plan_id = course["plan_id"]
            log(f"course={course['course_id']} plan={plan_id} job={job['job_id']}")

        plan_block = phase("plan")
        plan_block.update(run_job(job["job_id"], max_seconds=args.max_seconds, label="plan"))
        plan_block["facts"] = plan_facts(plan_id)

        # Plan approval, the same kernel fence the learner surface uses. The desktop reads
        # `parent.blueprint.read` at approve time because `plan.approve` fences on the digest
        # recomputed from the plan rows, NOT on the generation digest in `plans.plan_hash`
        # (desktop/plugin.js approvePlan). Using the stored generation digest here is a harness
        # bug and is refused VALIDATION_FAILED, so the same read the UI makes is the one used.
        approve_block = phase("approve")
        facts = plan_block["facts"]
        with db.read() as connection:
            revision = int(connection.execute(
                "SELECT revision FROM enrollments WHERE id = ?", (enrollment["enrollment_id"],)
            ).fetchone()["revision"])
        kernel_hash = None
        kernel_hash_source = None
        try:
            blueprint = dispatch("parent.blueprint.read", {"course_id": course["course_id"]})
            kernel_hash = ((blueprint or {}).get("plan") or {}).get("plan_hash")
            kernel_hash_source = "parent.blueprint.read"
        except Exception as exc:  # noqa: BLE001 - fall back to the same function the kernel uses
            approve_block["blueprint_read_error"] = str(exc)
        if not kernel_hash:
            with db.read() as connection:
                kernel_hash = generation.plan_content_hash(connection, plan_id)
            kernel_hash_source = "generation.plan_content_hash"
        approve_block["generation_digest"] = facts.get("plan_hash")
        approve_block["kernel_digest"] = kernel_hash
        approve_block["kernel_digest_source"] = kernel_hash_source
        approve_payload = {"enrollment_id": enrollment["enrollment_id"], "plan_id": plan_id,
                           "plan_hash": kernel_hash}
        try:
            approve_block["result"] = dispatch(
                "plan.approve", approve_payload,
                expected_revision=revision, key=f"h187-{args.tag}-approve",
            )
            approve_block["ok"] = True
        except Exception as exc:  # noqa: BLE001 - a refusal is an outcome, not a crash
            approve_block["ok"] = False
            approve_block["error"] = str(exc)
        log(f"plan.approve ok={approve_block['ok']} {json.dumps(approve_block.get('result') or approve_block.get('error'))}")
        approve_block["plan_state_after"] = plan_facts(plan_id).get("plan_state")

        # Lessons: one job per unit, exactly the payload generateLessons posts.
        lessons_block = phase("lessons")
        lessons_block["jobs"] = []
        if approve_block["ok"]:
            for index in range(args.units):
                lesson_job = dispatch(
                    "jobs.create",
                    {"kind": "plan", "brief": {"stage": "lessons", "plan_id": plan_id,
                                               "enrollment_id": enrollment["enrollment_id"]}},
                    key=f"h187-{args.tag}-lessons-{index}",
                )
                run = run_job(lesson_job["job_id"], max_seconds=args.max_seconds,
                              label=f"lessons-{index}")
                run["facts"] = lesson_facts(plan_id, enrollment["enrollment_id"])
                lessons_block["jobs"].append(run)
        lessons_block["facts"] = lesson_facts(plan_id, enrollment["enrollment_id"])

        # Serve one page from the durable rows.
        page_block = phase("page")
        served = None
        for candidate in lessons_block["facts"]["servable_objectives"]:
            try:
                page = dispatch("lesson.page", {"enrollment_id": enrollment["enrollment_id"],
                                                "objective_id": candidate["objective_id"]})
            except Exception as exc:  # noqa: BLE001
                page_block.setdefault("refused", []).append(
                    {"objective_id": candidate["objective_id"], "error": str(exc)}
                )
                continue
            document = page.get("document") or {}
            served = {
                "objective_id": candidate["objective_id"],
                "objective_title": page.get("section", {}).get("title"),
                "lesson_state": candidate["lesson_state"],
                "view": document.get("view"),
                "block_count": len(document.get("blocks") or []),
                "block_kinds": [block.get("kind") for block in document.get("blocks") or []],
                "provenance": document.get("provenance"),
                "check_id": next((c.get("check_id") for c in page.get("checks") or []), None),
                "source_count": len(page.get("sources") or []),
                "first_block_text": ((document.get("blocks") or [{}])[0]).get("text", "")[:400],
            }
            break
        page_block["served"] = served

        usage_ids = [job["job_id"]] + [run["job_id"] for run in lessons_block.get("jobs") or []]
        result["usage"] = usage_facts(usage_ids)
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        log(f"worker failed: {result['error']}")
    finally:
        result["finished_at"] = now_iso()
        result["total_elapsed_s"] = round(time.time() - started, 1)
        save()
        log(f"result -> {args.result}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
