"""Hermes hook adapters — the boundary between a chat turn and the Coursebook backend.

These three functions are the *only* place Coursebook touches Hermes chat lifecycle
(``PREBUILD_SPEC.md`` §8, ``AUDIT.md`` R2):

``pre_llm_call``
    Reconciles the session binding, classifies the inbound message, grades a real answer through
    ``attempt.submit`` on the same dispatcher the UI uses, commits the transition, and only then
    returns the teaching context. A grading failure or a refusal returns a local block message so
    no inference runs against ungraded state. A clarification or ordinary conversation returns
    ``None`` — it creates no attempt and consumes no retry.

``post_llm_call``
    Observer only: records the assistant snapshot as a lesson segment, fenced by the revision and
    turn nonce captured before the turn. Late callbacks are discarded, never written.

``post_tool_call``
    Captures tool provenance/usage correlation. Source text stays untrusted content and can never
    change policy, rubrics, tools, state, reminders or exports.

A late callback carries a turn nonce and a compare-and-swap fence; it may not modify a newer
revision.
"""

from __future__ import annotations

import uuid
from typing import Any

#: Imported by callers that need the ceiling without importing Hermes internals.
GRADING_DEADLINE_MS = 8000

#: Pre-turn fence per session: what the post-turn observer is allowed to write against.
_TURNS: dict[str, dict[str, Any]] = {}


def _session_key(session_id: str) -> str:
    return str(session_id or "")


def _fingerprint(value: Any) -> str | None:
    if value is None or value == "":
        return None
    import hashlib

    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:32]


def pre_llm_call(
    session_id: str = "",
    user_message: str = "",
    conversation_history: Any = None,
    is_first_turn: bool = False,
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Coursebook pre-turn gate.

    Returns ``{"context": ...}`` only after a transition is committed, or a fail-closed
    ``{"action": "block", "message": ...}``. Returns ``None`` when this chat is not governed.
    """
    from . import turn

    try:
        reconcile = turn.reconcile_binding(
            session_id,
            cwd_fingerprint=_fingerprint(kwargs.get("cwd") or kwargs.get("cwd_fingerprint")),
            compression_tip=_fingerprint(kwargs.get("compression_tip") or kwargs.get("conversation_tip")),
        )
        if reconcile.get("status") in ("detached", "branched", "orphaned"):
            # A cwd change detaches governance; the chat continues without Coursebook state.
            _TURNS.pop(_session_key(session_id), None)
            return None
        outcome = turn.pre_turn(session_id, user_message, deadline_ms=GRADING_DEADLINE_MS)
        if outcome.nonce:
            _TURNS[_session_key(session_id)] = {
                "nonce": outcome.nonce,
                "revision": outcome.revision,
                "verdict": outcome.verdict,
                "attempt_id": outcome.attempt_id,
            }
        return outcome.hook
    except Exception:  # noqa: BLE001 - a hook that cannot finish must never grant a pass
        _TURNS.pop(_session_key(session_id), None)
        return {
            "action": "block",
            "message": (
                "Coursebook could not read this lesson's state, so the turn was stopped. "
                "Nothing was graded and no pass was granted. Retry from the course pane."
            ),
        }


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
    from . import turn

    pending = _TURNS.pop(_session_key(session_id), None)
    if not pending:
        # No gate ran for this turn (ungoverned chat or a failed pre-turn). Nothing to record.
        return None
    try:
        turn.record_assistant_snapshot(
            session_id=session_id,
            assistant_response=str(assistant_response or ""),
            nonce=pending.get("nonce"),
            revision=pending.get("revision"),
        )
    except Exception:  # noqa: BLE001 - the observer is never the gate
        return None
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
    from . import db

    try:
        with db.transaction() as connection:
            binding = connection.execute(
                "SELECT enrollment_id FROM bindings WHERE connection_id = ? OR stored_session_id = ?"
                " ORDER BY revision DESC, updated_at DESC LIMIT 1",
                (task_id or "", kwargs.get("session_id") or ""),
            ).fetchone()
            connection.execute(
                "INSERT INTO usage_events (id, operation_id, enrollment_id, provider, model, tokens_json,"
                " duration_ms, artifact_count, recorded_at) VALUES (?, ?, ?, ?, NULL, '{}', ?, 0, ?)",
                (
                    f"use_{uuid.uuid4().hex}",
                    (task_id or None),
                    binding["enrollment_id"] if binding else None,
                    f"tool:{str(tool_name)[:120]}",
                    int(duration_ms) if duration_ms else None,
                    db.utcnow(),
                ),
            )
    except Exception:  # noqa: BLE001 - provenance capture must never break a tool call
        return None
    return None


#: What ``plugin.yaml`` declares. Kept here so a rename cannot drift from the manifest silently.
PROVIDED_HOOKS: tuple[str, ...] = ("pre_llm_call", "post_llm_call", "post_tool_call")

# Importing the package imports this module, so this is where the kernel's RPC handlers get bound.
# Registration reads the live contract (``coursebook.domain.ensure_registered``), so a contract
# amendment adds methods without a second wiring point and cannot drift from ``cb.rpc``.
from . import domain as _domain  # noqa: E402  (import after the hook constants on purpose)

_domain.ensure_registered()
