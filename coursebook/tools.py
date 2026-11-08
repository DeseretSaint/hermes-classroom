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
    "Report Coursebook backend health: plugin version, wire contract version, SQLite schema "
    "state for the active profile, and whether a cross-model validator route is configured. "
    "Read-only; use it to diagnose why the Coursebook pane is degraded or whether a generated "
    "course can be checked by a different model instead of guessing."
)

#: Manifest ``config_schema`` keys this build actually reads. Declaring a setting nothing
#: consumes is a partially wired control, so the schema and this table move together.
#: ``validator_model`` / ``validator_provider`` are read by ``__init__.py::register`` (they bind the
#: validation route before ``coursebook.tools`` is ever invoked), not by this module.
CONFIG_KEYS: tuple[str, ...] = (
    "status_include_contracts",
    "validator_model",
    "validator_provider",
)
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


def status_handler(args: dict[str, Any] | None = None, **_kwargs: Any) -> str:
    """Return a JSON string; the shape is the ``health.get`` response body plus diagnostics.

    The host dispatches every registered tool as ``entry.handler(args, **kwargs)`` — the model's
    argument dict arrives **positionally** (``tools/registry.py::dispatch``), and only the
    context kwargs the signature names are forwarded. ``args`` is accepted here because the tool
    schema declares no parameters; naming it positionally, rather than only as ``**kwargs``, is
    what keeps ``coursebook_status`` callable through the registry at all.
    """
    payload = {
        "plugin_version": __version__,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "db": _db_health(),
        "validator": _validator_status(),
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


def _validator_status() -> dict[str, Any]:
    """Report whether a cross-model validator route is *declared*, and never more than that.

    The values come from ``generation.validator_config()`` — the same settings ``register`` used
    to bind the route. This says nothing about whether the provider answered; a configured route
    still fails loudly at call time if the host trust gate refuses the override. Read locally: no
    secret is involved, and the block is exactly ``{configured, provider, model, reason}``.
    """
    try:
        from . import generation

        config = generation.validator_config()
        return {
            "configured": bool(config.get("configured")),
            "provider": config.get("provider"),
            "model": config.get("model"),
            "reason": str(config.get("reason") or ""),
        }
    except Exception as exc:  # noqa: BLE001 - a status read must never take the tool down
        return {
            "configured": False,
            "provider": None,
            "model": None,
            "reason": (
                "the validator configuration could not be read "
                f"({type(exc).__name__}); treat the route as unconfigured"
            ),
        }
