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

from .coursebook import __version__, hooks, tools

logger = logging.getLogger("coursebook")

PLUGIN_ID = "coursebook"
TOOLSET = "coursebook"


def register(ctx: Any) -> None:
    """Wire the agent half. Called once by the Hermes plugin loader."""
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
    logger.debug("coursebook %s registered (1 tool, %d hooks)", __version__, len(hooks.PROVIDED_HOOKS))
