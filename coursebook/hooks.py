"""Hermes hook adapters — the boundary between a chat turn and the Coursebook backend.

These three functions are the *only* place Coursebook touches Hermes chat lifecycle. They are
thin by design and currently intentional no-ops: the skeleton must load, be declared in
``plugin.yaml`` and pass admission without pretending that governance exists yet.

Frozen invariants for whoever fills them in (``PREBUILD_SPEC.md`` §8, ``AUDIT.md`` R2):

``pre_llm_call``
    Validate the session binding, grade a pending answer through
    :func:`coursebook.api.dispatch` (``attempt.submit``), commit the transition, and only then
    return the policy delta as ``{"context": "..."}``. It must finish inside a deadline strictly
    below the Hermes hook timeout; on failure it returns ``{"action": "block", "message": ...}``
    with a local retry message so no inference runs against ungraded state. A timeout never
    grants a pass.

``post_llm_call``
    Observer only: record the assistant snapshot. It is skipped on failed turns, so it can never
    be the gate.

``post_tool_call``
    Capture real tool provenance and usage correlation. Web/source text is untrusted content and
    must never be able to change policy, rubrics, tools, state, reminders or exports.

A late callback carries a turn nonce and a compare-and-swap fence; it may not modify a newer
revision.
"""

from __future__ import annotations

from typing import Any

#: Imported by callers that need the ceiling without importing Hermes internals.
GRADING_DEADLINE_MS = 8000


def pre_llm_call(
    session_id: str = "",
    user_message: str = "",
    conversation_history: Any = None,
    is_first_turn: bool = False,
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> None:
    """Coursebook pre-turn gate. Returns ``None``: no injection and no block yet."""
    return None


def post_llm_call(
    session_id: str = "",
    user_message: str = "",
    assistant_response: str = "",
    conversation_history: Any = None,
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> None:
    """Coursebook post-turn observer. Returns ``None``; its return value is ignored by Hermes."""
    return None


def post_tool_call(
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    task_id: str = "",
    duration_ms: int = 0,
    **kwargs: Any,
) -> None:
    """Coursebook tool-provenance observer. Returns ``None``; never alters the tool result."""
    return None


#: What ``plugin.yaml`` declares. Kept here so a rename cannot drift from the manifest silently.
PROVIDED_HOOKS: tuple[str, ...] = ("pre_llm_call", "post_llm_call", "post_tool_call")

# Importing the package imports this module, so this is where the kernel's RPC handlers get bound.
# Registration reads the live contract (``coursebook.domain.ensure_registered``), so a contract
# amendment adds methods without a second wiring point and cannot drift from ``cb.rpc``.
from . import domain as _domain  # noqa: E402  (import after the hook constants on purpose)

_domain.ensure_registered()


# Startup reconciliation runs once per process, at plugin load: a crashed worker's jobs become
# `interrupted_requires_retry`, cancel-in-progress jobs become `cancelled`, and orphaned artifact
# staging/objects are reconciled. Guarded so tests and an unmigrated install are never mutated by
# merely importing the package.
def reconcile_on_startup() -> dict[str, Any]:
    try:
        from . import job_service

        return job_service.ensure_startup_reconciled()
    except Exception as exc:  # noqa: BLE001 - a load-time recovery failure must not break the plugin
        return {"error": type(exc).__name__, "message": str(exc)[:300]}


STARTUP_RECONCILIATION = reconcile_on_startup()
