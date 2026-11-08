#!/usr/bin/env python3
"""H-190 live worker — plan identity on the real product path, one isolated home.

Runs, in a fresh ``HERMES_HOME`` with no demo pack and no recorded transcripts:

    course.create -> enrollment.create -> jobs.create(stage=plan)
        -> real executor.pump_once (real bounded tick)
        -> plan identity facts (course.plan_id vs the authored plan id)
        -> plan.approve(plan_id=<the id course.create returned>)
        -> the authored document read back for that id

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

from coursebook import api, db, domain, executor, generation, research  # noqa: E402,F401
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
        "operation_id": f"h190-{method.replace('.', '-')}-{time.time_ns()}",
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
        provider=os.environ.get("H190_VALIDATOR_PROVIDER") or None,
        model=os.environ.get("H190_VALIDATOR_MODEL") or None,
    )
    research.bind_host_seam(SearchHost())
    return generation.validator_config()


def job_row(job_id: str) -> dict | None:
    from coursebook import job_service

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

    thread = threading.Thread(target=_pump, name=f"h190-pump-{label}", daemon=True)
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


def identity_facts(course_id: str, course_plan_id: str) -> dict:
    """Every plan row the course holds, and what the authored document is bound to."""
    facts: dict = {"course_id": course_id, "course_returned_plan_id": course_plan_id}
    with db.read() as connection:
        plans = connection.execute(
            "SELECT id, version, state, plan_hash, created_at, approved_at FROM plans"
            " WHERE course_id = ? ORDER BY version",
            (course_id,),
        ).fetchall()
        facts["plans"] = [
            {
                "plan_id": str(row["id"]),
                "version": int(row["version"]),
                "state": str(row["state"]),
                "plan_hash": row["plan_hash"],
                "created_at": row["created_at"],
                "approved_at": row["approved_at"],
                "is_course_returned_id": str(row["id"]) == course_plan_id,
            }
            for row in plans
        ]
        documents = connection.execute(
            "SELECT plan_id, generation_state, plan_hash, validation_id, created_at"
            " FROM gen_plan_documents WHERE course_id = ? ORDER BY rowid",
            (course_id,),
        ).fetchall()
        facts["gen_plan_documents"] = [
            {
                "plan_id": str(row["plan_id"]),
                "generation_state": str(row["generation_state"]),
                "plan_hash": row["plan_hash"],
                "validation_id": row["validation_id"],
                "created_at": row["created_at"],
                "is_course_returned_id": str(row["plan_id"]) == course_plan_id,
            }
            for row in documents
        ]
        objectives = connection.execute(
            "SELECT plan_id, COUNT(*) AS n FROM objectives WHERE plan_id IN"
            " (SELECT id FROM plans WHERE course_id = ?) GROUP BY plan_id",
            (course_id,),
        ).fetchall()
        facts["objectives_per_plan"] = {str(row["plan_id"]): int(row["n"]) for row in objectives}
        # The same read the approval surface performs on the id it holds.
        try:
            document = generation.plan_document(connection, course_plan_id)
        except Exception as exc:  # noqa: BLE001 - a missing document is an outcome
            facts["authored_document"] = {"error": f"{type(exc).__name__}: {exc}"}
        else:
            facts["authored_document"] = {
                "plan_id": document.get("plan_id"),
                "generation_state": document.get("generation_state"),
                "objectives": len(document.get("objectives") or []),
                "objective_titles": [item.get("title") for item in document.get("objectives") or []],
                "validation_verdict": (document.get("validation") or {}).get("verdict")
                if isinstance(document.get("validation"), dict) else None,
                "approval_warning": (document.get("approval") or {}).get("warning")
                if isinstance(document.get("approval"), dict) else None,
            }
    facts["identity_holds"] = bool(
        facts["authored_document"].get("plan_id") == course_plan_id
        and facts["objectives_per_plan"].get(course_plan_id, 0) > 0
        and [row for row in facts["plans"] if row["is_course_returned_id"]]
        and [row for row in facts["gen_plan_documents"] if row["is_course_returned_id"]]
    )
    return facts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--subject-domain", default=None)
    parser.add_argument("--level", default=None)
    parser.add_argument("--locale", default=None)
    parser.add_argument("--depth", default="working")
    parser.add_argument("--pace", default="light")
    parser.add_argument("--assessment", default="none")
    parser.add_argument("--autonomy", default="guided")
    parser.add_argument("--max-seconds", type=float, default=900)
    parser.add_argument("--result", required=True)
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
        payload = {"title": args.title, "recipe": args.recipe, "goal": args.goal,
                   "dials": dials, "scope": args.scope}
        for key in ("subject_domain", "level", "locale"):
            value = getattr(args, key)
            if value:
                payload[key] = value
        course = dispatch("course.create", payload, key=f"h190-{args.tag}-course")
        enrollment = dispatch("enrollment.create",
                              {"course_id": course["course_id"], "learner_label": args.title},
                              key=f"h190-{args.tag}-enroll")
        brief = {"stage": "plan", "course_id": course["course_id"],
                 "enrollment_id": enrollment["enrollment_id"], "goal": args.goal,
                 "recipe": args.recipe, "dials": dials, "scope": args.scope}
        for key in ("subject_domain", "level", "locale"):
            value = getattr(args, key)
            if value:
                brief[key] = value
        job = dispatch("jobs.create", {"kind": "plan", "brief": brief}, key=f"h190-{args.tag}-plan")
        result["course"] = course
        result["enrollment"] = enrollment
        result["plan_job"] = job
        result["plan_id_before_job"] = course["plan_id"]
        log(f"course={course['course_id']} course.plan_id={course['plan_id']} job={job['job_id']}")

        plan_block = phase("plan")
        plan_block.update(run_job(job["job_id"], max_seconds=args.max_seconds, label="plan"))
        checkpoint = (plan_block.get("final_job") or {}).get("checkpoint") or {}
        plan_block["checkpoint_plan_id"] = checkpoint.get("plan_id")
        plan_block["facts"] = identity_facts(course["course_id"], course["plan_id"])
        result["plan_id_after_job"] = plan_block["checkpoint_plan_id"]
        result["identity_holds"] = plan_block["facts"]["identity_holds"]
        log(f"after job: checkpoint plan_id={checkpoint.get('plan_id')} identity_holds={result['identity_holds']}")

        # Plan approval, the same kernel fence the learner surface uses: the id course.create
        # returned, and the hash computed from those rows.
        approve_block = phase("approve")
        with db.read() as connection:
            revision = int(connection.execute(
                "SELECT revision FROM enrollments WHERE id = ?", (enrollment["enrollment_id"],)
            ).fetchone()["revision"])
        plan_hash = None
        with db.read() as connection:
            plan_hash = generation.plan_content_hash(connection, course["plan_id"])
        approve_payload = {"enrollment_id": enrollment["enrollment_id"],
                           "plan_id": course["plan_id"], "plan_hash": plan_hash}
        try:
            approve_block["result"] = dispatch(
                "plan.approve", approve_payload,
                expected_revision=revision, key=f"h190-{args.tag}-approve",
            )
            approve_block["ok"] = True
        except Exception as exc:  # noqa: BLE001 - a refusal is an outcome, not a crash
            approve_block["ok"] = False
            approve_block["error"] = str(exc)
        log(f"plan.approve(plan_id=course.plan_id) ok={approve_block['ok']} "
            f"{json.dumps(approve_block.get('result') or approve_block.get('error'))}")
        approve_block["facts_after"] = identity_facts(course["course_id"], course["plan_id"])

        result["ok"] = bool(approve_block["ok"] and result["identity_holds"])
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
