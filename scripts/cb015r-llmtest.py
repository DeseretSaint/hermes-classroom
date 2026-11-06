#!/usr/bin/env python3
"""One small host-LLM call through the same PluginLlm seam the job tick uses.

Proves whether the isolated home can reach a provider at all, without touching a coursebook row.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.environ.get("HERMES_AGENT_ROOT", os.path.expanduser("~/.hermes/hermes-agent")))
from agent.plugin_llm import PluginLlm  # noqa: E402

print("hermes home:", os.environ.get("HERMES_HOME"), flush=True)
llm = PluginLlm(plugin_id="coursebook")
started = time.time()
result = llm.complete(
    [{"role": "user", "content": "Say OK."}],
    timeout=60,
)
print("elapsed_s:", round(time.time() - started, 2))
print("text:", (result.text or "").strip()[:200])
print("provider:", result.provider, "model:", result.model)
