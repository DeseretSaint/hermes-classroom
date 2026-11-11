#!/usr/bin/env python3
"""CP-044 evidence capture: does a *job* deadline cancel a hanging provider request?

Offline and bounded: the provider is a local socket that accepts the connection and never answers,
so nothing is spent and the script always terminates. Two scenarios run against the same stub:

A. ``job deadline`` unset, purpose deadline 8 s — the call's own bound cancels the request.
B. ``job deadline`` 1.5 s, purpose deadline 8 s — the *job attempt* must cancel first.

On the pre-fix tree both scenarios end at the purpose deadline (8 s): there was no job-level
budget at all, which is the CP-015 checkpoint 4 observation ("still running at 648 s"). After the
fix, B ends at ~1.5 s. The output records, per scenario: wall clock, the job row's state, lease,
error code/details and the liveness row, plus whether the stub saw the socket close.

Run from the repository root:

    python3 probes/cp044-job-deadline.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import db, executor, generation as gen, job_service  # noqa: E402
from tests.test_cp044_job_deadline_hanging_provider import (  # noqa: E402
    CLOSE_GRACE_SECONDS,
    HungHostSeam,
    HungProviderStub,
    NOW,
)
from tests.test_generation import FakeSearch  # noqa: E402

PURPOSE_DEADLINE_S = 8.0


def _scenario(name: str, *, job_deadline_s: float | None) -> dict:
    stub = HungProviderStub()
    seam = HungHostSeam(stub.port)
    brief = {
        "stage": "plan",
        "goal": "Order coffee in Japanese",
        "recipe": "committed",
        "dials": {},
        "locale": "ja-JP",
        "level": "L0",
    }
    job_id = job_service.create("plan", brief, now=NOW)["job_id"]
    stages = executor.resolvers(
        llm=gen.PluginLLMAdapter(seam), search=FakeSearch(), now=NOW
    )[executor.JOB_KIND](brief)
    env = {"COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS": str(PURPOSE_DEADLINE_S)}
    if job_deadline_s is not None:
        env["COURSEBOOK_JOB_DEADLINE_SECONDS"] = str(job_deadline_s)
    started = time.monotonic()
    try:
        with mock.patch.dict(os.environ, env):
            view = job_service.execute(job_id, stages, now=NOW)
        elapsed = round(time.monotonic() - started, 2)
        with db.read() as connection:
            row = connection.execute(
                "SELECT state, lease_owner, lease_expires_at, updated_at, error_json FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            waits = gen.call_waits(connection, job_id)
        socket_closed = stub.wait_closed(CLOSE_GRACE_SECONDS)
    finally:
        stub.stop()
    return {
        "scenario": name,
        "job_deadline_env": job_deadline_s,
        "purpose_deadline_s": PURPOSE_DEADLINE_S,
        "job_id": job_id,
        "elapsed_s": elapsed,
        "left_running": view["state"] != "running",
        "view_state": view["state"],
        "view_lease": view["lease"],
        "row_state": row["state"],
        "row_lease_owner": row["lease_owner"],
        "row_lease_expires_at": row["lease_expires_at"],
        "error_code": (view.get("error") or {}).get("code"),
        "error_details": (view.get("error") or {}).get("details"),
        "error_message": (view.get("error") or {}).get("message"),
        "stub_connection_accepted": stub.accepted_at is not None,
        "stub_socket_closed": socket_closed,
        "coroutine_cancelled": seam.cancelled,
        "liveness_rows": waits,
    }


def main() -> int:
    home = tempfile.mkdtemp(prefix="cp044-probe-")
    previous_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = home
    try:
        db.migrate()
        report = {
            "base_commit": os.popen("git -C %s rev-parse --short HEAD" % ROOT).read().strip(),
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scenarios": [
                _scenario("A: purpose deadline only (no job budget)", job_deadline_s=None),
                _scenario("B: job deadline 1.5 s beats a 8 s purpose deadline", job_deadline_s=1.5),
            ],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        if previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous_home
        shutil.rmtree(home, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
