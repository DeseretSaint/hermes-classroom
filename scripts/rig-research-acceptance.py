#!/usr/bin/env python3
"""Acceptance probe: an isolated rig backend can research, so a live plan is measurable.

One ``course.create`` → one ``jobs.create(kind=plan)`` over the product's own ``cb.rpc`` wire,
then the *backend's own rows* are read back to prove the result is real:

  * ``gen_research_runs.status`` for the course is ``ok`` (not ``unavailable``),
  * the ``sources`` ledger for the course is non-empty,
  * the generated plan document carries at least one objective with a non-empty
    ``provenance.source_ids`` link.

That is acceptance item 3 of t_3e8b07ba. The script writes a JSON record and exits non-zero when
any of the three does not hold — it never substitutes a fabricated verdict for a missing one.

    CB_RIG_BASE=http://127.0.0.1:44719 CB_RIG_TOKEN=t3e8-rig-token \\
      python3 scripts/rig-research-acceptance.py --db ~/.hermes/coursebook-test-t3e8b07ba/home/plugin-data/coursebook/data.db \\
        --out /tmp/rig-research.json

The rig home must already be running (``scripts/rig-private-desktop.sh --install-only`` then a
backend start). ``--no-create`` re-reads the newest course in the rig DB instead of authoring a
new one, which makes a re-check after a restart cheap.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SPEC = {
    "title": "Japanese Cafe Rig Check",
    "goal": (
        "Order a drink and a snack at a Japanese cafe, ask for the bill, and understand the "
        "reply, politely, at a beginner level."
    ),
    "recipe": "committed",
    "locale": "ja-JP",
    "level": "L0",
    "subject_domain": "language",
    "scope": "short",
    "dials": {"pace": "steady", "depth": "deep", "assessment": "graded", "autonomy": "guided"},
    "presentation_mode": "game",
}

SUCCESS_JOB_STATES = {"completed", "succeeded"}


class Backend:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token
        self._wire: int | None = None

    def _request(self, path: str, body: dict | None = None, timeout: float = 120.0) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"{self.base}/api/plugins/coursebook{path}",
            data=data,
            method="POST" if data is not None else "GET",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.URLError as exc:
            raise SystemExit(
                f"backend not reachable at {self.base} ({exc.reason}); start the rig backend first:\n"
                f"  HERMES_HOME=<rig home> hermes serve --isolated --port <port>"
            ) from exc

    def wire_version(self) -> int:
        if self._wire is None:
            runtime = self._request("/runtime?profile=")
            self._wire = int(runtime.get("wire_version") or 0)
            if not self._wire:
                raise SystemExit(f"backend reported no wire_version: {runtime}")
        return self._wire

    def call(self, method: str, payload: dict) -> dict:
        body = {
            "contract": "cb.rpc",
            "contract_version": self.wire_version(),
            "method": method,
            "operation_id": f"rig-research-{method.replace('.', '-')}-{uuid.uuid4().hex[:10]}",
            "payload": payload,
        }
        return self._request("/rpc?profile=", body)

    def ok(self, method: str, payload: dict) -> dict:
        response = self.call(method, payload)
        if not response.get("ok"):
            raise RuntimeError(f"{method} refused: {json.dumps(response.get('error'), indent=2)}")
        return response["result"]


def wait_for_job(backend: Backend, job_id: str, *, timeout: float) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        job = backend.ok("jobs.get", {"job_id": job_id})["job"]
        state = str(job.get("state") or "")
        if state != last:
            print(f"[rig] job {job_id}: {state}", flush=True)
            last = state
        if state in SUCCESS_JOB_STATES or state in {"failed", "cancelled", "canceled"}:
            return job
        time.sleep(5.0)
    raise TimeoutError(f"job {job_id} still {last or 'unknown'} after {timeout:.0f}s")


def warm_gateway_tools(base: str, token: str) -> str:
    """Make the backend's own tool registry carry ``web_search`` before a job dispatches it.

    ``hermes serve`` never builds the agent's tool list, so on a fresh backend the parent process's
    registry has no ``web_search`` handler and a hosted plugin's ``ctx.dispatch_tool`` answers
    ``Unknown tool: web_search`` (measured: research came back ``unavailable`` with exactly that
    reason). Patient zero is the tool list a Desktop client asks for on connect; one ``tools.list``
    RPC imports ``model_tools`` in that process and registers the handlers. Best effort and
    reported: returns a one-line status, never raises.
    """
    try:
        import asyncio
        import json as _json

        import websockets
    except Exception as exc:  # noqa: BLE001 - a missing client is reported, not fatal
        return f"skipped ({type(exc).__name__}: {exc}); dispatch may answer Unknown tool"

    url = base.replace("http://", "ws://").replace("https://", "wss://") + f"/api/ws?token={token}"

    async def _call() -> str:
        async with websockets.connect(url, open_timeout=20, max_size=None) as socket:
            await asyncio.wait_for(socket.recv(), timeout=20)  # server hello
            await socket.send(_json.dumps({"id": "warm-tools", "method": "tools.show", "params": {}}))
            for _ in range(40):
                raw = await asyncio.wait_for(socket.recv(), timeout=45)
                try:
                    message = _json.loads(raw)
                except Exception:  # noqa: BLE001 - non-JSON frames are not the answer
                    continue
                if message.get("id") == "warm-tools":
                    if message.get("error"):
                        return f"failed: {message['error']}"
                    toolsets = (message.get("result") or {}).get("toolsets") or []
                    return f"ok ({len(toolsets)} toolset(s) listed)"
            return "failed: no reply to tools.list"

    try:
        return asyncio.run(_call())
    except Exception as exc:  # noqa: BLE001 - reported, not fatal
        return f"failed ({type(exc).__name__}: {exc})"



def read_rows(db: Path, course_id: str) -> dict:
    """The backend's own rows for *course_id*: research status, ledger size, cited objectives."""
    if not db.is_file():
        raise SystemExit(f"no rig database at {db}")
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        run = connection.execute(
            "select id, status, reason, sources_json from gen_research_runs "
            "where course_id = ? order by created_at desc limit 1",
            (course_id,),
        ).fetchone()
        source_count = connection.execute(
            "select count(*) from sources where course_id = ?", (course_id,)
        ).fetchone()[0]
        document = connection.execute(
            "select document_json, research_json from gen_plan_documents "
            "where course_id = ? order by created_at desc limit 1",
            (course_id,),
        ).fetchone()
    finally:
        connection.close()

    cited: list[dict] = []
    objectives = 0
    if document is not None:
        document_json = json.loads(document["document_json"] or "{}")
        for objective in _iter_objectives(document_json):
            objectives += 1
            ids = _source_ids(objective)
            cited.append({"objective_id": objective.get("objective_id") or objective.get("id"),
                          "source_ids": ids})
    return {
        "research_run_id": run["id"] if run is not None else None,
        "research_status": run["status"] if run is not None else None,
        "research_reason": run["reason"] if run is not None else None,
        "ledger_sources": int(source_count),
        "objectives": objectives,
        "objectives_with_source_ids": [c for c in cited if c["source_ids"]],
        "objective_source_ids": cited,
    }


def _iter_objectives(document: dict):
    for objective in document.get("objectives") or []:
        yield objective
    for unit in document.get("units") or []:
        for objective in unit.get("objectives") or []:
            yield objective


def _source_ids(objective: dict) -> list[str]:
    provenance = objective.get("provenance") or {}
    ids = provenance.get("source_ids")
    if ids is None:
        ids = objective.get("source_ids")
    return [str(item) for item in (ids or []) if str(item)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rig research acceptance probe (t_3e8b07ba)")
    parser.add_argument("--base", default=os.environ.get("CB_RIG_BASE", "http://127.0.0.1:44719"))
    parser.add_argument("--token", default=os.environ.get("CB_RIG_TOKEN", ""))
    parser.add_argument("--db", required=True, type=Path, help="the rig home's coursebook data.db")
    parser.add_argument("--out", type=Path, default=None, help="write the JSON record here")
    parser.add_argument("--timeout", type=float, default=900.0, help="plan job wall clock")
    parser.add_argument("--course-id", default="", help="skip creating a course; check this one")
    parser.add_argument(
        "--no-warm",
        action="store_true",
        help="do not ask the backend for its tool list first (a fresh `hermes serve` has no "
             "web_search handler until something imports model_tools; see warm_gateway_tools)",
    )
    parser.add_argument(
        "--no-create",
        action="store_true",
        help="do not author a course; check the newest course in the rig DB",
    )
    args = parser.parse_args(argv)
    if not args.token:
        raise SystemExit("a backend token is required: --token or CB_RIG_TOKEN")

    backend = Backend(args.base, args.token)
    record: dict = {"base": args.base, "wire_version": backend.wire_version(), "created": False}

    if not args.no_warm:
        warm = warm_gateway_tools(args.base, args.token)
        record["tool_registry_warm"] = warm
        print(f"[rig] tool registry warm: {warm}", flush=True)

    course_id = args.course_id
    if not course_id and args.no_create:
        connection = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "select id from courses order by created_at desc limit 1"
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise SystemExit(f"no course in {args.db}")
        course_id = str(row[0])
        print(f"[rig] checking existing course {course_id}", flush=True)

    if not course_id:
        created = backend.ok("course.create", dict(SPEC))
        course_id = str(created["course_id"])
        record["created"] = True
        enrollment = backend.ok(
            "enrollment.create", {"course_id": course_id, "learner_label": SPEC["title"]}
        )
        brief = {
            "stage": "plan",
            "course_id": course_id,
            "enrollment_id": enrollment["enrollment_id"],
            "goal": SPEC["goal"],
            "recipe": SPEC["recipe"],
            "dials": SPEC["dials"],
            "locale": SPEC["locale"],
            "level": SPEC["level"],
            "subject_domain": SPEC["subject_domain"],
            "scope": SPEC["scope"],
        }
        job = backend.ok("jobs.create", {"kind": "plan", "brief": brief})
        job_id = str(job["job_id"])
        print(f"[rig] course {course_id} — plan job {job_id} queued", flush=True)
        final = wait_for_job(backend, job_id, timeout=args.timeout)
        record["job"] = {"job_id": job_id, "state": final.get("state"), "error": final.get("error")}
        if final.get("state") not in SUCCESS_JOB_STATES:
            record["course_id"] = course_id
            _write(record, args.out)
            return 1

    record["course_id"] = course_id
    record.update(read_rows(args.db, course_id))
    record["cited_objectives"] = len(record["objectives_with_source_ids"])
    record["verdict"] = verdict_for(record)
    _write(record, args.out)
    print(json.dumps({k: v for k, v in record.items() if k != "objective_source_ids"}, indent=2))
    return 0 if record["verdict"] == "ok" else 1


def verdict_for(record: dict) -> str:
    """``"ok"`` only when research ran, the ledger has rows, AND an objective cites a source.

    The three are separate facts and all three matter: a run that says ``ok`` with an empty ledger,
    or a ledger with an uncited plan, is exactly the state the old rig produced (research
    ``unavailable`` → no ledger → no citations). A check that passes on any two of them would call a
    refused plan green, so this is the single place the verdict is decided.
    """
    research_ok = record.get("research_status") == "ok"
    ledger_ok = int(record.get("ledger_sources") or 0) > 0
    cited_ok = bool(record.get("objectives_with_source_ids"))
    return "ok" if research_ok and ledger_ok and cited_ok else "not-ok"


def _write(record: dict, out: Path | None) -> None:
    if out is None:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
