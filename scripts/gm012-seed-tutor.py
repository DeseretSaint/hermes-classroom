#!/usr/bin/env python3
"""Seed one REAL tutor.ask turn through the in-process host-LLM seam.

Why in-process: `hermes serve` loads the plugin's dashboard API half only, so
`coursebook.generation._HOST_LLM` is never bound there (defect class D-H63-1).
The agent process binds it from `register(ctx)` via `bind_host_llm(ctx.llm)`.
This script performs the identical binding and calls the identical handler
(`coursebook.tutor.ask` through `coursebook.api.dispatch`), against the same
isolated home/DB the Desktop window is reading.

No fixture, no stub: the answer and citations are produced by the real provider.
"""
from __future__ import annotations

import json
import os
import sys
import time

HOME = os.environ["HERMES_HOME"]
AGENT_ROOT = "/home/deseretsaint/.hermes/hermes-agent"
SRC = os.environ.get("COURSEBOOK_SOURCE", "/home/deseretsaint/Projects/hermes-classroom")

sys.path.insert(0, AGENT_ROOT)
sys.path.insert(0, SRC)

import hermes_bootstrap  # noqa: E402,F401  (same dependency path setup the `hermes` launcher uses)

from agent.plugin_llm import PluginLlm  # noqa: E402

import coursebook.generation as generation  # noqa: E402
from coursebook import api  # noqa: E402
import coursebook.tutor  # noqa: E402,F401  (module import registers tutor.ask/history)

payload = json.loads(sys.argv[1])
revision = int(sys.argv[2])

generation.bind_host_llm(PluginLlm(plugin_id="coursebook"))
print("llm bound:", type(generation._HOST_LLM).__name__ if hasattr(generation, "_HOST_LLM") else "?", file=sys.stderr)

envelope = {
    "contract": "cb.rpc",
    "contract_version": 24,
    "method": "tutor.ask",
    "operation_id": f"gm012-seed-{int(time.time() * 1000)}",
    "idempotency_key": f"gm012-seed-{time.time_ns()}",
    "expected_revision": revision,
    "payload": payload,
}
answer = api.dispatch(envelope)
print(json.dumps(answer, ensure_ascii=False, indent=2))
