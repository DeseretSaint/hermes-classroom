"""Coursebook — Hermes Agent plugin entry point.

Unified package layout (verified against the live SDK, ``website/docs/developer-guide/
desktop-plugin-sdk.md`` §"One package, both SDKs"):

    plugin.yaml                  agent half: declared tools/hooks
    __init__.py                  this file — ``register(ctx)``
    coursebook/                  backend package (contracts, db, jobs, packs, hooks)
    dashboard/manifest.json      mounts plugin_api.py at /api/plugins/coursebook/
    dashboard/plugin_api.py      FastAPI backend the Desktop half reaches with ``ctx.rest``
    desktop/plugin.js            Desktop half: route, sidebar nav, pane, palette
    contracts/                   frozen JSON contracts (the authority)

The skeleton registers exactly what it implements: one read-only status tool and the three
chat-lifecycle adapter hooks. Nothing here claims a capability the backend does not have yet.
"""

from __future__ import annotations

import logging
from typing import Any

from .coursebook import __version__, executor, hooks, tools
from .coursebook import media as media_mod
from .coursebook import research
from .coursebook.generation import bind_host_llm, bind_validator_llm

logger = logging.getLogger("coursebook")

PLUGIN_ID = "coursebook"
TOOLSET = "coursebook"


def register(ctx: Any) -> None:
    """Wire the agent half. Called once by the Hermes plugin loader."""
    # A declared config_schema key is only honest when its reader is wired here, at register.
    tools.configure(getattr(ctx, "get_config", None))
    # Generation jobs run in the agent process; bind the host-owned LLM once so the pipeline
    # never reaches for a raw provider key. Unbound calls fail loudly in generation.host_llm().
    bind_host_llm(getattr(ctx, "llm", None))
    # The independent validator is a *different model*, not a different prompt. Both settings are
    # read here and nowhere else; empty means no cross-model path exists and the pipeline records
    # a model-assessed pass instead of calling the author model "independent". The host's own
    # per-plugin llm trust gate still decides whether the override is permitted.
    read_setting = getattr(ctx, "get_config", None)
    validator_provider = str(read_setting("validator_provider", "") or "") if callable(read_setting) else ""
    validator_model = str(read_setting("validator_model", "") or "") if callable(read_setting) else ""
    bind_validator_llm(
        getattr(ctx, "llm", None), provider=validator_provider, model=validator_model
    )
    # Media uses the host's own image_generate/text_to_speech tools through ctx.dispatch_tool:
    # no provider key enters the plugin, and an old/bare host leaves media as a complete text
    # lesson instead of fabricating a file.
    media_mod.bind_host_seam(ctx)
    # Research uses the host's own web_search/web_extract tools through ctx.dispatch_tool, so it
    # inherits the user's provider, egress rules and SSRF checks. An unusable host is recorded as
    # "research unavailable" by the pipeline, never replaced with an invented source.
    research.bind_host_seam(ctx)
    ctx.register_tool(
        name=tools.STATUS_TOOL_NAME,
        toolset=TOOLSET,
        schema=tools.status_schema(),
        handler=tools.status_handler,
        description=tools.STATUS_TOOL_DESCRIPTION,
        emoji="📘",
    )
    for hook_name in hooks.PROVIDED_HOOKS:
        ctx.register_hook(hook_name, getattr(hooks, hook_name))
    # The job tick: queued `plan` jobs (and their `brief.stage = lessons` variant) become real
    # work. Bounded per tick, driven on the host's own asyncio loop, stopped on unload. A host
    # without spawn_task (bare tests, dashboard-only process) simply does not start one.
    executor.start_tick(ctx)
    logger.debug("coursebook %s registered (1 tool, %d hooks)", __version__, len(hooks.PROVIDED_HOOKS))
