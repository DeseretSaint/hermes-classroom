"""RPC dispatch seam.

Every caller — the Desktop half over ``POST /api/plugins/coursebook/rpc``, a Coursebook-owned
tool, and the ``pre_llm_call`` adapter — goes through :func:`dispatch`. That is deliberate: the
chat hook is an adapter for free-text submissions, never the sole correctness boundary
(``PREBUILD_SPEC.md`` §8). A handler that is not registered yet produces ``NOT_IMPLEMENTED``
rather than a silent success.
"""

from __future__ import annotations

from typing import Any, Callable

from . import __version__
from . import db
from .contracts import (
    WIRE_CONTRACT_ID,
    WIRE_CONTRACT_VERSION,
    ContractError,
    build_error,
    error_catalog,
    method_names,
    schema_inventory,
    validate,
    validate_request_payload,
    validate_response_payload,
)

RPC_CONTRACT = WIRE_CONTRACT_ID
RPC_CONTRACT_VERSION = WIRE_CONTRACT_VERSION

#: ``method -> handler(payload, envelope) -> (revision, result)``
Handler = Callable[[dict[str, Any], dict[str, Any]], "tuple[int, dict[str, Any]]"]
METHOD_HANDLERS: dict[str, Handler] = {}


class RpcError(Exception):
    """A command refused by policy or state, carrying a contract error object."""

    def __init__(self, error: dict[str, Any]) -> None:
        self.error = error
        super().__init__(error.get("message", error.get("code", "error")))

    @classmethod
    def of(cls, code: str, message: str, **details: Any) -> "RpcError":
        return cls(build_error(code, message, **details))


def register_handler(method: str, handler: Handler) -> None:
    """Bind a method to its implementation. Rejects names that are not in ``cb.rpc``."""
    if method not in method_names():
        raise ContractError(f"cannot register handler for unknown method {method!r}", contract_id=RPC_CONTRACT)
    METHOD_HANDLERS[method] = handler


def implemented_methods() -> tuple[str, ...]:
    return tuple(sorted(METHOD_HANDLERS))


# ── Handlers that are real in the skeleton ──────────────────────────────────


def _health_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return 0, {
        "plugin_version": __version__,
        "contract_version": RPC_CONTRACT_VERSION,
        "db": db.health(),
        "backend": "python",
    }


def _schema_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return 0, {
        "contracts": schema_inventory(),
        "db_schema_version": db.target_schema_version(),
    }


register_handler("health.get", _health_get)
register_handler("schema.get", _schema_get)


# ── Envelope construction ───────────────────────────────────────────────────


def error_response(operation_id: str, error: dict[str, Any]) -> dict[str, Any]:
    response = {
        "ok": False,
        "contract_version": RPC_CONTRACT_VERSION,
        "operation_id": operation_id,
        "error": error,
    }
    return response


def ok_response(operation_id: str, revision: int, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "contract_version": RPC_CONTRACT_VERSION,
        "operation_id": operation_id,
        "revision": int(revision),
        "result": result,
    }


def dispatch(request: Any) -> dict[str, Any]:
    """Validate, run, and answer one command.

    Always returns a contract-shaped envelope; never raises for a caller error. A programmer
    error inside a handler becomes ``INTERNAL_ERROR`` so one bad method cannot take down the
    HTTP surface.
    """
    operation_id = "unknown-operation"
    try:
        validate("cb.rpc", request, what="RPC request")
        operation_id = str(request.get("operation_id", operation_id))
        method = str(request["method"])
        payload = request.get("payload") or {}
        validate_request_payload(method, payload)
    except ContractError as exc:
        # A malformed envelope may not carry a usable operation id; the contract requires one,
        # so echo a placeholder rather than emitting an unvalidatable response.
        return error_response(
            operation_id,
            build_error("VALIDATION_FAILED", str(exc), path=exc.path or None),
        )

    handler = METHOD_HANDLERS.get(method)
    if handler is None:
        return error_response(
            operation_id,
            build_error("NOT_IMPLEMENTED", f"{method} is frozen in cb.rpc but has no handler in this build."),
        )

    try:
        revision, result = handler(payload, request)
        validate_response_payload(method, result)
    except RpcError as exc:
        return error_response(operation_id, exc.error)
    except ContractError as exc:
        return error_response(
            operation_id,
            build_error("INTERNAL_ERROR", f"{method} produced a non-contract result: {exc}", path=exc.path or None),
        )
    except Exception as exc:  # noqa: BLE001 - one handler must not break the surface
        return error_response(
            operation_id,
            build_error("INTERNAL_ERROR", f"{method} failed: {type(exc).__name__}"),
        )
    return ok_response(operation_id, revision, result)


def contract_summary() -> dict[str, Any]:
    """Small, serialisable description of what this backend speaks (used by health copy)."""
    return {
        "wire_contract": RPC_CONTRACT,
        "wire_version": RPC_CONTRACT_VERSION,
        "methods": len(method_names()),
        "implemented": len(METHOD_HANDLERS),
        "error_codes": len(error_catalog()),
    }
