#!/usr/bin/env python
"""H-63R live-generation worker.

Runs the real Coursebook backend in one process, as an agent process would:

* loads the plugin through the real Hermes plugin loader (which calls ``register(ctx)`` and
  binds the host-owned ``ctx.llm``, the transport-backed research seam, and the job tick),
* migrates the isolated home's SQLite store,
* creates a non-demo course + enrollment + plan job over the real ``cb.rpc`` dispatcher,
* lets the real bounded job tick execute the plan stage (live provider + live web research),
* bounds the wait, records the exact job state timeline, research ledger, validation verdict and
  thread names, and cancels a job that will not terminate.

No credentials are read by this script; provider access is ``agent.plugin_llm.PluginLlm`` only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback

AGENT_ROOT = os.environ.get("HERMES_AGENT_ROOT", os.path.expanduser("~/.hermes/hermes-agent"))
sys.path.insert(0, AGENT_ROOT)
sys.path.insert(0, os.environ.get("COURSEBOOK_SOURCE", "/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_af57b886"))

from coursebook import api, db, executor, generation, job_service, research  # noqa: E402
from coursebook import domain  # noqa: E402,F401  (registers the cb.rpc command handlers)
from coursebook.contracts import WIRE_CONTRACT_VERSION as RPC_CONTRACT_VERSION  # noqa: E402

TERMINAL = {"completed", "completed_late", "failed", "cancelled"}


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def dispatch(method: str, payload: dict, *, expected_revision=None, key=None) -> dict:
    request = {
        "contract": "cb.rpc",
        "contract_version": RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"h63-{method.replace('.', '-')}-{time.time_ns()}",
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


def load_plugin() -> None:
    """Bind the same host seams ``register(ctx)`` binds in an agent process.

    The standalone loader in this host hands the plugin a context without ``ctx.llm`` or
    ``ctx.dispatch_tool`` (observed: ``host llm bound=False``), so a bare ``discover_plugins``
    starts a tick that could never call a provider. An agent process supplies both; here we
    supply the same objects through the same binding functions ``register`` calls.
    """
    from agent.plugin_llm import PluginLlm

    llm = PluginLlm(plugin_id="coursebook")
    generation.bind_host_llm(llm)
    generation.bind_validator_llm(
        llm,
        provider=os.environ.get("H63_VALIDATOR_PROVIDER") or None,
        model=os.environ.get("H63_VALIDATOR_MODEL") or None,
    )
    research.bind_host_seam(SearchHost())
    log(f"seams bound; validator_config={json.dumps(generation.validator_config())}")


class SearchHost:
    """Minimal host context exposing ``dispatch_tool`` for the real research adapter."""

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


def job_snapshot(job_id: str) -> dict:
    with db.read() as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return {"job_id": job_id, "state": "missing"}
        return job_service.job_view(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", default="(existing job)")
    parser.add_argument("--title", default="(existing job)")
    parser.add_argument("--recipe", default="one_off")
    parser.add_argument("--scope", default="single")
    parser.add_argument("--subject-domain", default=None)
    parser.add_argument("--depth", default="working")
    parser.add_argument("--pace", default="light")
    parser.add_argument("--assessment", default="none")
    parser.add_argument("--autonomy", default="guided")
    parser.add_argument("--max-seconds", type=float, default=600)
    parser.add_argument("--cancel-after", type=float, default=None,
                        help="request cancellation after N seconds of running")
    parser.add_argument("--result", required=True)
    parser.add_argument("--tag", default="run")
    parser.add_argument("--job-id", default=None,
                        help="run an already-created job (created over HTTP) instead of creating one")
    args = parser.parse_args()

    started = time.time()
    result: dict = {
        "tag": args.tag,
        "isolated_home": os.environ.get("HERMES_HOME"),
        "source_commit": os.environ.get("COURSEBOOK_COMMIT"),
        "wire_contract_version": RPC_CONTRACT_VERSION,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "timeline": [],
    }

    def save() -> None:
        with open(args.result, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)

    try:
        load_plugin()
        log(f"schema before ensure: {db.applied_schema_version()}")
        db.ensure_schema()
        log(f"schema after ensure: {db.applied_schema_version()}  store={db.store_root()}")
        result["schema_version"] = db.applied_schema_version()
        result["store_root"] = str(db.store_root())

        dials = {"depth": args.depth, "pace": args.pace,
                 "assessment": args.assessment, "autonomy": args.autonomy}
        if args.job_id:
            job_id = args.job_id
            with db.read() as connection:
                row = connection.execute("SELECT brief_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
            brief = json.loads(row["brief_json"]) if row is not None else {}
            course = {"course_id": brief.get("course_id"), "plan_id": None}
            enrollment = {"enrollment_id": brief.get("enrollment_id")}
            result["course"] = course
            result["enrollment"] = enrollment
            result["job"] = {"job_id": job_id, "state": "existing"}
            result["job_id"] = job_id
            log(f"using pre-created job {job_id} (brief from HTTP jobs.create)")
        else:
            create_payload = {"title": args.title, "recipe": args.recipe, "goal": args.goal, "dials": dials,
                              "scope": args.scope}
            if args.subject_domain:
                create_payload["subject_domain"] = args.subject_domain
            course = dispatch("course.create", create_payload, key=f"h63-{args.tag}-course")
            log(f"course.create: {json.dumps(course)}")
            result["course"] = course

            enrollment = dispatch("enrollment.create",
                                  {"course_id": course["course_id"], "learner_label": args.title},
                                  key=f"h63-{args.tag}-enroll")
            log(f"enrollment.create: {json.dumps(enrollment)}")
            result["enrollment"] = enrollment

            brief = {"stage": "plan", "course_id": course["course_id"],
                     "enrollment_id": enrollment["enrollment_id"], "goal": args.goal,
                     "recipe": args.recipe, "dials": dials, "scope": args.scope}
            if args.subject_domain:
                brief["subject_domain"] = args.subject_domain
            job = dispatch("jobs.create", {"kind": "plan", "brief": brief}, key=f"h63-{args.tag}-plan")
            job_id = job["job_id"]
            log(f"jobs.create: {json.dumps(job)}")
            result["job"] = job
            result["job_id"] = job_id

        # The real bounded pump, exactly the function the agent tick calls, on its own thread so
        # the main thread can observe state and request cancellation the way the Desktop does.
        pump_holder: dict = {}

        def _pump() -> None:
            try:
                pump_holder["finished"] = executor.pump_once(limit=1)
            except Exception as exc:  # noqa: BLE001
                pump_holder["error"] = f"{type(exc).__name__}: {exc}"
                pump_holder["traceback"] = traceback.format_exc()
            pump_holder["done_at_s"] = round(time.time() - started, 1)

        pump_thread = threading.Thread(target=_pump, name="h63-pump", daemon=True)
        pump_thread.start()
        result["pump_thread"] = pump_thread.name
        log("real executor.pump_once started (limit=1)")

        last_state = None
        cancel_sent = False
        while True:
            elapsed = round(time.time() - started, 1)
            view = job_snapshot(job_id)
            state = view.get("state")
            progress = view.get("progress") or {}
            if state != last_state or elapsed < 5:
                result["timeline"].append({
                    "elapsed_s": elapsed, "state": state,
                    "stage": progress.get("stage"), "message": progress.get("message"),
                    "lease": view.get("lease"),
                })
            if state != last_state:
                log(f"job state -> {state} at {elapsed}s (stage={progress.get('stage')} msg={progress.get('message')})")
            last_state = state

            if args.cancel_after is not None and not cancel_sent and elapsed >= args.cancel_after:
                cancel_sent = True
                log(f"requesting cancel at {elapsed}s")
                try:
                    result["cancel_request"] = dispatch("jobs.cancel", {"job_id": job_id})
                    log(f"jobs.cancel -> {json.dumps(result['cancel_request'])}")
                except Exception as exc:  # noqa: BLE001
                    result["cancel_request"] = {"error": f"{type(exc).__name__}: {exc}"}
                    log(f"jobs.cancel failed: {exc}")
                result["cancel_requested_at_s"] = elapsed

            if state in TERMINAL:
                result["terminal_state"] = state
                result["elapsed_to_terminal_s"] = elapsed
                break
            if elapsed >= args.max_seconds:
                result["terminal_state"] = "BOUND_EXCEEDED"
                result["elapsed_to_terminal_s"] = elapsed
                log(f"BOUND EXCEEDED at {elapsed}s; requesting cancel")
                try:
                    result["cancel_request"] = dispatch("jobs.cancel", {"job_id": job_id})
                except Exception as exc:  # noqa: BLE001
                    result["cancel_request"] = {"error": f"{type(exc).__name__}: {exc}"}
                # Give the executor 30s to observe the boundary.
                deadline = time.time() + 30
                while time.time() < deadline:
                    view = job_snapshot(job_id)
                    if view.get("state") in TERMINAL:
                        result["terminal_state_after_cancel"] = view["state"]
                        break
                    time.sleep(1)
                break
            time.sleep(2)

        final = job_snapshot(job_id)
        result["final_job"] = final
        pump_thread.join(timeout=10)
        result["pump"] = pump_holder
        result["threads"] = [thread.name for thread in threading.enumerate()]
        result["worker_id"] = job_service.WORKER_ID

        checkpoint = final.get("checkpoint") or {}
        plan_id = checkpoint.get("plan_id") or (course.get("plan_id"))
        result["plan_id"] = plan_id
        if plan_id:
            try:
                with db.read() as connection:
                    row = connection.execute(
                        "SELECT document_json, research_json, result_json, validation_id"
                        " FROM gen_plan_documents WHERE plan_id = ?", (plan_id,)
                    ).fetchone()
                    record = None
                    if row is not None and row["validation_id"]:
                        record = generation.validation_record(connection, row["validation_id"])
                if row is not None:
                    stored = json.loads(row["document_json"] or "{}")
                    plan = stored.get("plan") if isinstance(stored.get("plan"), dict) else stored
                    result["plan"] = {
                        "plan_schema": plan.get("plan_schema"),
                        "objectives": plan.get("objectives") or [],
                        "units": plan.get("units") or [],
                        "check_plan": plan.get("check_plan") or [],
                        "title": plan.get("title"),
                        "goal": plan.get("goal"),
                        "learner_outcome": plan.get("learner_outcome"),
                        "document": plan,
                    }
                    result["research"] = json.loads(row["research_json"] or "{}")
                    generation_result = json.loads(row["result_json"] or "{}")
                    result["generation_result"] = generation_result
                    result["validation_record"] = record
                    result["validation_verdict"] = generation_result.get("validation_verdict")
                    result["generation_status"] = generation_result.get("status")
                    result["rejection_reasons"] = generation_result.get("rejection_reasons")
                    result["validation"] = generation_result.get("validation")
                    result["research_status"] = (result["research"] or {}).get("status")
            except Exception as exc:  # noqa: BLE001
                result["plan_error"] = f"{type(exc).__name__}: {exc}"

        # usage events are the real spend record for the job id
        try:
            with db.read() as connection:
                rows = connection.execute(
                    "SELECT provider, model, tokens_json, duration_ms, recorded_at FROM usage_events"
                    " WHERE operation_id = ? ORDER BY recorded_at", (job_id,)
                ).fetchall()
            result["usage_events"] = [dict(row) for row in rows]
        except Exception as exc:  # noqa: BLE001
            result["usage_error"] = f"{type(exc).__name__}: {exc}"

        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        log(f"worker failed: {result['error']}")
    finally:
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result["total_elapsed_s"] = round(time.time() - started, 1)
        save()
        log(f"result written to {args.result}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
