"""Coursebook-owned tools exposed to the agent.

Only one tool exists in the skeleton: ``coursebook_status``. It is read-only introspection, so
it can be honest before the kernel exists. Governed research and media tools are added by the
research/media work package together with the code that actually enforces their budgets — a tool
that claims a ceiling it cannot enforce is worse than no tool.
"""

from __future__ import annotations

import json
from typing import Any

from . import __version__
from . import api, db

STATUS_TOOL_NAME = "coursebook_status"
STATUS_TOOL_DESCRIPTION = (
    "Report Coursebook backend health: plugin version, wire contract version and SQLite schema "
    "state for the active profile. Read-only; use it to diagnose why the Coursebook pane is "
    "degraded instead of guessing."
)


def status_schema() -> dict[str, Any]:
    return {
        "name": STATUS_TOOL_NAME,
        "description": STATUS_TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    }


def status_handler(**_kwargs: Any) -> str:
    """Return a JSON string; the shape is the ``health.get`` response body."""
    payload = {
        "plugin_version": __version__,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "db": _db_health(),
        "contracts": api.contract_summary(),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _db_health() -> dict[str, Any]:
    try:
        return db.health()
    except Exception as exc:  # noqa: BLE001 - a status tool reports failure, it never raises
        return {"ready": False, "schema_version": None, "error": type(exc).__name__}
