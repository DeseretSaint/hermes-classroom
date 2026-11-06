"""Hermes hook adapters — the boundary between a chat turn and the Coursebook backend.

These three functions are the *only* place Coursebook touches Hermes chat lifecycle
(``PREBUILD_SPEC.md`` §8, ``AUDIT.md`` R2):

``pre_llm_call``
    Reconciles the session binding, classifies the inbound message, grades a real answer through
    ``attempt.submit`` on the same dispatcher the UI uses, commits the transition, and only then
    returns the teaching context. A grading failure or a refusal returns a local block message so
    no inference runs against ungraded state. A clarification or ordinary conversation returns
    ``None`` — it creates no attempt and consumes no retry. When no Coursebook store exists at all
    it returns ``None`` before touching anything: a chat turn is not Coursebook use, so an
    unprovisioned profile stays ungoverned rather than blocked, and the hook provisions nothing
    (CB-014-R1 R1/R2). An *unreadable* store still fails closed.

``post_llm_call``
    Observer only: records the assistant snapshot as a lesson segment, fenced by the revision and
    turn nonce captured before the turn. Late callbacks are discarded, never written.

``post_tool_call``
    Captures tool provenance/usage correlation **for a bound lesson chat only**. A session that
    never passed the gate is not attributable to an enrollment, so it writes nothing and opens no
    database — an unbound chat must not grow the store it is not a part of. Source text stays
    untrusted content and can never change policy, rubrics, tools, state, reminders or exports.

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

#: Sessions this process has *decided* are bound lesson chats (``pre_llm_call`` records them,
#: detach/unbind/error forgets them). Tool telemetry is written only for these: an unattributed
#: usage row is not attributable to an enrollment and ``cb.db`` ``usage_events.enrollment_id``
#: exists precisely to attribute one. Bounded so a long-lived gateway cannot grow it without limit.
_GOVERNED: dict[str, dict[str, Any]] = {}
_MAX_GOVERNED = 1024


def _session_key(session_id: str) -> str:
    return str(session_id or "")


def _remember_governed(session_key: str, binding_id: Any) -> None:
    if not session_key:
        return
    if session_key not in _GOVERNED and len(_GOVERNED) >= _MAX_GOVERNED:
        _GOVERNED.pop(next(iter(_GOVERNED)), None)
    _GOVERNED[session_key] = {"binding_id": str(binding_id) if binding_id else None}


def _forget_governed(session_key: str) -> None:
    _GOVERNED.pop(session_key, None)


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
    ``{"action": "block", "message": ...}``. Returns ``None`` when this chat is not governed —
    including when this profile has no Coursebook store at all, which is the ordinary state of an
    install nobody has opened yet. Absent is not unreadable: a store that exists and cannot be read
    still fails closed below.
    """
    from . import db, turn

    key = _session_key(session_id)
    if not db.store_exists():
        # Nothing is provisioned, so nothing here can be governed. Clear any stale in-process
        # decision for this key and leave the filesystem untouched (no directory, no file).
        _TURNS.pop(key, None)
        _forget_governed(key)
        return None
    try:
        reconcile = turn.reconcile_binding(
            session_id,
            cwd_fingerprint=_fingerprint(kwargs.get("cwd") or kwargs.get("cwd_fingerprint")),
            compression_tip=_fingerprint(kwargs.get("compression_tip") or kwargs.get("conversation_tip")),
        )
        if reconcile.get("status") in ("detached", "branched", "orphaned"):
            # A cwd change detaches governance; the chat continues without Coursebook state.
            _TURNS.pop(key, None)
            _forget_governed(key)
            return None
        if session_id and reconcile.get("status") != "unbound":
            # This chat governs an enrollment, so its tool usage is attributable. Recorded here,
            # before the turn, because ``post_tool_call`` runs mid-turn and must not re-derive
            # governance from a database an unbound chat has no business opening.
            _remember_governed(key, reconcile.get("binding_id"))
        else:
            _forget_governed(key)
        outcome = turn.pre_turn(session_id, user_message, deadline_ms=GRADING_DEADLINE_MS)
        if outcome.nonce:
            _TURNS[key] = {
                "nonce": outcome.nonce,
                "revision": outcome.revision,
                "verdict": outcome.verdict,
                "attempt_id": outcome.attempt_id,
            }
        return outcome.hook
    except Exception:  # noqa: BLE001 - a hook that cannot finish must never grant a pass
        _TURNS.pop(key, None)
        _forget_governed(key)
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
    """Coursebook tool-provenance observer. Returns ``None``; never alters the tool result.

    Records a ``usage_events`` row **only** for a session this process observed as a bound lesson
    chat. An unbound session's tool call has no ``enrollment_id`` to attribute, and ``cb.db``
    ``usage_events`` is an attribution table: the row would be noise in the operator's store, so
    nothing is written and no connection is opened for it. Governance is re-confirmed against the
    live binding inside the fence, so a chat detached mid-turn stops being recorded immediately
    (``AUDIT.md`` R1: no recency, no inference — a live binding row is the only authority).
    """
    from . import db

    session_id = str(kwargs.get("session_id") or "")
    key = _session_key(session_id)
    if not session_id or key not in _GOVERNED:
        # Ungoverned chat: nothing to attribute. Deliberately before the storage seam so an
        # unbound session can never create or grow a Coursebook database.
        return None
    try:
        with db.transaction() as connection:
            binding = connection.execute(
                "SELECT id, enrollment_id FROM bindings"
                " WHERE stored_session_id = ? AND status IN ('active', 'paused')"
                " ORDER BY updated_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if binding is None or not binding["enrollment_id"]:
                # Detached (or the row moved) after the gate decided: stop attributing this chat.
                _forget_governed(key)
                return None
            enrollment = connection.execute(
                "SELECT 1 FROM enrollments WHERE id = ?", (binding["enrollment_id"],)
            ).fetchone()
            if enrollment is None:
                return None
            connection.execute(
                "INSERT INTO usage_events (id, operation_id, enrollment_id, provider, model, tokens_json,"
                " duration_ms, artifact_count, recorded_at) VALUES (?, ?, ?, ?, NULL, '{}', ?, 0, ?)",
                (
                    f"use_{uuid.uuid4().hex}",
                    (task_id or None),
                    binding["enrollment_id"],
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

# Pack lifecycle handlers (CB-010). They are not kernel commands: preview/import/export touch the
# archive and the pack library, and ``pack.delete`` stays with the kernel data-scope path.
from . import pack_flow as _pack_flow  # noqa: E402  (same single wiring point)

_pack_flow.ensure_registered()

# Startup reconciliation runs once per process, at plugin load: a crashed worker's jobs become
# `interrupted_requires_retry`, cancel-in-progress jobs become `cancelled`, and orphaned artifact
# staging/objects are reconciled. Guarded so tests and an unmigrated install are never mutated by
# merely importing the package — and because its guard is `db.applied_schema_version()`, which is a
# non-creating read, importing this module does not create `plugin-data/` either (CB-014-R1 R1).
def reconcile_on_startup() -> dict[str, Any]:
    try:
        from . import job_service

        return job_service.ensure_startup_reconciled()
    except Exception as exc:  # noqa: BLE001 - a load-time recovery failure must not break the plugin
        return {"error": type(exc).__name__, "message": str(exc)[:300]}


STARTUP_RECONCILIATION = reconcile_on_startup()
