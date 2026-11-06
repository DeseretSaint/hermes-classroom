"""Coursebook-owned tools exposed to the agent.

Only one tool exists in the skeleton: ``coursebook_status``. It is read-only introspection, so
it can be honest before the kernel exists. Governed research and media tools are added by the
research/media work package together with the code that actually enforces their budgets — a tool
that claims a ceiling it cannot enforce is worse than no tool.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from . import __version__
from . import api, db

STATUS_TOOL_NAME = "coursebook_status"
STATUS_TOOL_DESCRIPTION = (
    "Report Coursebook backend health: plugin version, wire contract version and SQLite schema "
    "state for the active profile. Read-only; use it to diagnose why the Coursebook pane is "
    "degraded instead of guessing."
)

#: Manifest ``config_schema`` keys this module actually reads. Declaring a setting nothing
#: consumes is a partially wired control, so the schema and this table move together.
CONFIG_KEYS: tuple[str, ...] = ("status_include_contracts",)
DEFAULT_STATUS_INCLUDE_CONTRACTS = True

_read_setting: Callable[[str, Any], Any] | None = None


def configure(read_setting: Callable[[str, Any], Any] | None) -> None:
    """Bind the plugin's settings reader (``ctx.get_config``) once, at register time.

    The reader is the documented agent-half API for ``plugins.entries.coursebook.settings.*``.
    Tool handlers receive only their own kwargs, so this is how a declared setting reaches them.
    """
    global _read_setting
    _read_setting = read_setting


def _setting(key: str, default: Any) -> Any:
    if _read_setting is None:
        return default
    try:
        value = _read_setting(key, default)
    except Exception:  # noqa: BLE001 - a broken settings file must not break a status read
        return default
    return default if value is None else value


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
    """Return a JSON string; the shape is the ``health.get`` response body plus diagnostics."""
    payload = {
        "plugin_version": __version__,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "db": _db_health(),
        "implemented_methods": list(api.implemented_methods()),
    }
    if bool(_setting("status_include_contracts", DEFAULT_STATUS_INCLUDE_CONTRACTS)):
        payload["contracts"] = api.contract_summary()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _db_health() -> dict[str, Any]:
    try:
        return db.health()
    except Exception as exc:  # noqa: BLE001 - a status tool reports failure, it never raises
        return {"ready": False, "schema_version": None, "error": type(exc).__name__}
