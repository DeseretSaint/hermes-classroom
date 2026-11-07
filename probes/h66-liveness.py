#!/usr/bin/env python3
"""H-66 liveness reproduction — bounded, offline, no network, no real profile touched.

Three independent stalls are reproduced here, each with a *finite* probe (a thread that is
watched for two seconds and then declared stalled), so this script always terminates:

A. host research seam — ``HermesToolSearch.search`` calls ``ctx.dispatch_tool`` with no
   deadline. A host tool that blocks blocks the whole job stage.
B. provider seam — ``generation._call_llm`` hands ``timeout=...`` to the host and only
   checks the elapsed time *after* the call returns. A host model call that blocks blocks
   the stage forever; the declared deadline is post-hoc.
C. heartbeat — ``job_service._run_with_heartbeat`` renews the lease on a bare
   ``threading.Thread``. That thread starts with an empty ``contextvars.Context``, so a
   gateway that carries the active profile as a context-local override (not ``HERMES_HOME``)
   makes every renew resolve a *different* database, where the job does not exist. The renew
   exception is swallowed, the lease is never extended, and the job sits ``running`` with an
   expired lease while the stage is still blocked.

Run from the repository root:

    python3 probes/h66-liveness.py

Exit status 0 always: this is evidence capture, not an assertion suite. The regression
assertions live in ``tests/test_h66_liveness.py``.
"""

from __future__ import annotations

import contextvars
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import db, generation, job_service, research  # noqa: E402


def _json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


# ── A. stalled host research seam ───────────────────────────────────────────


def probe_host_tool() -> bool:
    release = threading.Event()

    class StallingHost:
        calls = 0

        def dispatch_tool(self, name: str, args: dict, **kwargs) -> str:  # noqa: ANN001
            StallingHost.calls += 1
            release.wait()  # no deadline anywhere in the adapter
            return '{"success": true, "data": {"web": []}}'

    seam = research.HermesToolSearch(StallingHost(), timeout_s=0.5)
    outcome: dict[str, object] = {}
    started = time.monotonic()
    try:
        seam.search("braise short ribs", 3)
        outcome["returned"] = True
    except Exception as exc:  # noqa: BLE001 - the probe records the typed failure
        outcome["error"] = f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - started
    stalled = elapsed > 2.0
    print("A. host tool: dispatch_tool calls =", StallingHost.calls)
    print("A. host tool: declared deadline_s = 0.5, elapsed = %.2fs" % elapsed)
    print("A. host tool: unbounded (elapsed > 2s) =", stalled)
    print("A. host tool: outcome =", _json(outcome))
    release.set()
    return stalled


# ── B. stalled provider call ────────────────────────────────────────────────


def probe_provider() -> bool:
    release = threading.Event()

    class StallingLLM:
        def complete_structured(self, **kwargs: Any) -> Any:  # mirrors PluginLlm
            release.wait()  # the host ignores request.timeout_s entirely
            return generation.LLMResponse(text="{}", parsed={})

    request = generation.LLMRequest(
        purpose="coursebook.plan.generate",
        prompt_version="probe",
        system_prompt="probe",
        instructions="probe",
        input_text="probe",
        schema={"type": "object"},
        schema_name="probe",
        max_tokens=16,
        timeout_s=0.5,  # a real deadline after the fix
    )
    usage = generation._Usage(generation.default_cost_budget())
    outcome: dict[str, object] = {}
    adapter = generation.PluginLLMAdapter(StallingLLM())
    started = time.monotonic()
    try:
        generation._call_llm(adapter, request, usage)
        outcome["returned"] = True
    except Exception as exc:  # noqa: BLE001
        outcome["error"] = f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - started
    stalled = elapsed > 2.0
    print("B. provider: declared deadline_s =", request.timeout_s)
    print("B. provider: _call_llm elapsed = %.2fs, unbounded = %s" % (elapsed, stalled))
    print("B. provider: outcome =", _json(outcome))
    release.set()
    return stalled


# ── C. heartbeat on a bare thread loses the profile context ─────────────────


def _job_row(home: Path) -> dict[str, object] | None:
    with db.read() as connection:
        row = connection.execute(
            "SELECT id, state, attempt_id, lease_owner, lease_expires_at, updated_at,"
            " progress_json FROM jobs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return None if row is None else dict(row)


def probe_heartbeat() -> bool:
    """A live stage must keep renewing its lease; with the current bare thread it cannot."""
    try:
        import hermes_constants
    except Exception as exc:  # noqa: BLE001 - bare environment without the host
        print("C. heartbeat: SKIP (hermes_constants unavailable:", exc, ")")
        return False

    active_home = Path(tempfile.mkdtemp(prefix="h66-active-"))
    fallback_home = Path(tempfile.mkdtemp(prefix="h66-fallback-"))
    previous_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(fallback_home)  # what a bare thread resolves
    token = hermes_constants.set_hermes_home_override(active_home)  # what the gateway uses
    previous_lease = job_service.LEASE_SECONDS
    job_service.LEASE_SECONDS = 2  # keep the probe fast: 2s lease, ~0.7s heartbeat
    started = threading.Event()
    release = threading.Event()

    class BlockingStage:
        def __call__(self, lease: job_service.Lease) -> job_service.StageResult:
            started.set()
            release.wait(5.0)
            return job_service.StageResult(checkpoint={"probe": True})

    try:
        db.migrate()
        created = job_service.create("plan", {"goal": "probe", "stage": "plan"})
        job_id = str(created["job_id"])
        context = contextvars.copy_context()  # what ``asyncio.to_thread`` does for the pump

        def run_stage() -> None:
            job_service.execute(job_id, [job_service.Stage("probe", BlockingStage())])

        # ``asyncio.to_thread`` copies the *current* context into the worker; model that.
        worker = threading.Thread(
            target=context.run, args=(run_stage,), name="coursebook-job-tick", daemon=True
        )
        worker.start()
        started.wait(2.0)
        first = _job_row(active_home)
        time.sleep(1.8)  # > one heartbeat interval
        second = _job_row(active_home)
        live = [t.name for t in threading.enumerate() if t.is_alive()]
        print("C. heartbeat: threads alive =", sorted(live))
        print("C. heartbeat: lease at stage start =", first and first["lease_expires_at"])
        print("C. heartbeat: lease after 1.8s     =", second and second["lease_expires_at"])
        renewed = bool(
            first and second and str(second["lease_expires_at"]) > str(first["lease_expires_at"])
        )
        print("C. heartbeat: lease renewed during the stage =", renewed)
        print("C. heartbeat: row at stage start =", _json(first))
        release.set()
        worker.join(6.0)
        return not renewed
    finally:
        release.set()
        job_service.LEASE_SECONDS = previous_lease
        hermes_constants.reset_hermes_home_override(token)
        if previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous_home
        shutil.rmtree(active_home, ignore_errors=True)
        shutil.rmtree(fallback_home, ignore_errors=True)


def main() -> int:
    print(f"H-66 liveness probe — python {sys.version.split()[0]}")
    host_stalled = probe_host_tool()
    provider_stalled = probe_provider()
    heartbeat_missing = probe_heartbeat()
    print()
    print(
        "RESULT host_seam_stall=%s provider_stall=%s heartbeat_not_renewed=%s"
        % (host_stalled, provider_stalled, heartbeat_missing)
    )
    print("(True on each line above is the defect being fixed; a fixed tree reports False.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
