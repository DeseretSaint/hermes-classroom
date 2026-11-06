#!/usr/bin/env python3
"""Run the Coursebook job executor as a standalone worker, exactly as an agent process would.

``hermes serve`` mounts the dashboard half only; the agent half (``__init__.register``) — and
therefore ``executor.start_tick`` — only exists inside an agent process. For an isolated backend
capture there is no agent process, so this script is that process: it loads the plugin package,
starts the same bounded tick, and stops on Ctrl-C.

    set -a; . ~/.hermes/coursebook-test/home/coursebook-single-home.env; set +a
    HERMES_HOME=~/.hermes/coursebook-test/home python3 scripts/cb011-tick-loop.py

It is a development/test harness, not a second engine: every job goes through
``job_service.run_pending`` with the same resolver table, lease and checkpoint rules.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A supervisor may restart this script under an interpreter that lacks the host's packages
# (`referencing`, `agent.*`). Re-exec into the venv that has them instead of dying mid-run.
try:  # noqa: SIM105
    import referencing  # noqa: F401
    import agent.plugin_llm  # noqa: F401
except ModuleNotFoundError:
    venv_python = os.environ.get("COURSEBOOK_VENV_PYTHON")
    if venv_python and os.path.realpath(sys.executable) != os.path.realpath(venv_python):
        os.execv(venv_python, [venv_python, *sys.argv])
    raise

from coursebook import db, executor, generation, hooks  # noqa: E402,F401 - hooks runs startup reconciliation


def _host_llm():
    """The host-owned PluginLlm an agent process passes as ``ctx.llm``.

    Same object, same trust gate and same credentials — this process is standing in for the agent
    process that ``hermes serve`` does not start. Nothing here reaches for a provider key.
    """
    sys.path.insert(0, os.environ.get("HERMES_AGENT_ROOT", os.path.expanduser("~/.hermes/hermes-agent")))
    from agent.plugin_llm import PluginLlm

    return PluginLlm(plugin_id="coursebook")


class _Host:
    """The minimal host a tick needs; mirrors the attributes ``register`` uses."""

    def __init__(self) -> None:
        self.spawned = None

    def spawn_task(self, coro, *, name=None):  # noqa: ANN001 - mirrors ctx.spawn_task
        self.spawned = asyncio.ensure_future(coro)
        return self.spawned

    def on_unload(self, callback) -> None:  # noqa: ANN001 - mirrors ctx.on_unload
        self.unload = callback


async def main() -> int:
    interval = float(os.environ.get("COURSEBOOK_JOB_TICK_SECONDS", "2"))
    if db.applied_schema_version() is None:
        print("no migrated coursebook store under", db.store_root(), file=sys.stderr)
        return 1
    print("store", db.store_root(), "schema", db.applied_schema_version(), flush=True)
    try:
        generation.bind_host_llm(_host_llm())
        print("host llm bound (PluginLlm, trust-gated)", flush=True)
    except Exception as exc:  # noqa: BLE001 - say exactly why, never fall back to a raw provider
        print("could not bind the host llm:", type(exc).__name__, exc, file=sys.stderr)
        return 1
    host = _Host()
    task = executor.start_tick(host, interval=interval)
    if task is None:
        print("the tick did not start", file=sys.stderr)
        return 1
    print("tick running every", interval, "s", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        executor.stop()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        executor.stop()
