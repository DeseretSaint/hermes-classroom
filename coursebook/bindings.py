"""The write half of a session binding — the missing seam between a chat and a lesson.

``binding.get`` (``cb.rpc`` v5) resolves a binding by stored session id or enrollment id, and
``binding.abandon`` detaches one, but nothing in the backend ever *created* a binding row. Every
test that exercises the gate, the pane or the chat reconciliation inserted the row by hand
(``tests/test_kernel_commands.py``, ``tests/test_turn.py``, ``tests/test_kernel_v2.py``), so the
whole governed loop was unreachable from a real Desktop: the pane answered "Not a Coursebook
lesson" no matter how many runs were started, and ``pre_llm_call`` always saw an unbound chat.

Why this is a host seam and not a new RPC method
------------------------------------------------
``cb.rpc`` is frozen at v5 and ``lesson.begin`` cannot carry a session id: the pane starts a
*fresh* chat, and a fresh chat has no stored id until its first turn (the Desktop half says so in
the "fresh run" notice: "Its chat binds after your first message."). The durable id therefore
arrives *after* the run exists, from the host, which is exactly what the other host seams
(``/packs/grant``, ``/artifacts/{handle}``) are for. This module holds the transactional rule so
the HTTP route stays a thin adapter and the same rule is unit-testable without FastAPI.

What this refuses, and why refusing is the point
------------------------------------------------
* a stored session id that is already bound to another enrollment — a chat never migrates
  silently between courses (``AUDIT.md`` R1: no recency, no "most recent chat");
* a second *active* binding for one enrollment — one lesson has one authoritative chat;
* a run that is not ``active`` or does not match the enrollment/objective it claims;
* an empty stored id — a runtime id is never a stand-in for the durable one.

Repeating the exact same bind (same stored id, enrollment and run) is idempotent and returns the
existing row, because the Desktop retries a seam call after a reload.
"""

from __future__ import annotations

import uuid
from typing import Any

from . import api, db

#: Statuses that mean "this chat still governs the lesson".
LIVE_STATUSES = ("active", "paused")

#: Ordering for "the binding that governs this enrollment/chat".
#:
#: ``bindings.revision`` counts edits to ONE row, not edits to the enrollment, so ordering rows by
#: ``revision DESC`` across an enrollment can surface a superseded row: moving a lesson to a new
#: section detaches the old row (revision + 1) and inserts the new active row at revision 0. Picking
#: by revision then read the detached row and refused a submit with ``BINDING_NOT_ACTIVE`` even
#: though a live binding existed. Prefer a live row; fall back to the most recently touched one so a
#: refusal can still name the real status.
GOVERNING_ORDER = " ORDER BY (status IN ('active', 'paused')) DESC, updated_at DESC LIMIT 1"

_BINDING_FIELDS = (
    "id",
    "enrollment_id",
    "profile",
    "connection_id",
    "runtime_session_id",
    "stored_session_id",
    "lesson_run_id",
    "objective_id",
    "status",
    "revision",
    "updated_at",
)


def _new_id() -> str:
    return f"bind_{uuid.uuid4().hex}"


def _view(row: Any) -> dict[str, Any]:
    binding = {key: row[key] for key in _BINDING_FIELDS if key in row.keys()}
    binding["matched_column"] = "stored_session_id"
    return binding


def bind_session(
    *,
    stored_session_id: Any,
    enrollment_id: Any,
    objective_id: Any,
    lesson_run_id: Any,
    profile: Any = None,
    runtime_session_id: Any = None,
    connection_id: Any = None,
    cwd_fingerprint: Any = None,
) -> dict[str, Any]:
    """Create (or return) the active binding that makes one chat the lesson's authoritative chat.

    Raises :class:`coursebook.api.RpcError` for every refusal, carrying a contract error code, so
    the HTTP seam can answer ``{ok: false, code, message}`` without inventing a second vocabulary.
    Returns ``{"binding": {...}, "created": bool}``.
    """
    for name, value in (
        ("stored_session_id", stored_session_id),
        ("enrollment_id", enrollment_id),
        ("objective_id", objective_id),
        ("lesson_run_id", lesson_run_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise api.RpcError.of(
                "VALIDATION_FAILED",
                f"binding a lesson chat needs {name}",
                field=name,
            )
    stored = stored_session_id.strip()
    profile_name = str(profile or "").strip() or "default"

    db.ensure_schema()
    with db.transaction() as connection:
        enrollment = connection.execute(
            "SELECT * FROM enrollments WHERE id = ?", (enrollment_id,)
        ).fetchone()
        if enrollment is None:
            raise api.RpcError.of("NOT_FOUND", "that enrollment does not exist", field="enrollment_id")

        run = connection.execute(
            "SELECT * FROM lesson_runs WHERE id = ?", (lesson_run_id,)
        ).fetchone()
        if run is None:
            raise api.RpcError.of("NOT_FOUND", "that lesson run does not exist", field="lesson_run_id")
        if str(run["enrollment_id"]) != str(enrollment["id"]):
            raise api.RpcError.of(
                "VALIDATION_FAILED",
                "that lesson run belongs to a different enrollment.",
                field="lesson_run_id",
                reason="lesson_run_mismatch",
            )
        if str(run["objective_id"]) != str(objective_id):
            raise api.RpcError.of(
                "VALIDATION_FAILED",
                "that lesson run teaches a different objective.",
                field="objective_id",
                reason="lesson_run_mismatch",
            )
        if str(run["state"]) != "active":
            raise api.RpcError.of(
                "VALIDATION_FAILED",
                f"lesson run is {run['state']}; bind a fresh run.",
                field="lesson_run_id",
                reason="lesson_run_not_active",
            )

        existing = connection.execute(
            "SELECT * FROM bindings WHERE stored_session_id = ?"
            " ORDER BY (status = 'active') DESC, revision DESC, updated_at DESC LIMIT 1",
            (stored,),
        ).fetchone()
        if existing is not None:
            same_lesson = (
                str(existing["enrollment_id"]) == str(enrollment["id"])
                and str(existing["lesson_run_id"] or "") == str(run["id"])
            )
            if same_lesson:
                return {"binding": _view(existing), "created": False}
            if str(existing["enrollment_id"]) == str(enrollment["id"]):
                # The same chat moving to another section of the same course is the Reattach
                # flow: move the binding with it (one row per chat, history kept by revision)
                # instead of demanding a second row the enrollment-wide rule would refuse.
                connection.execute(
                    "UPDATE bindings SET lesson_run_id = ?, objective_id = ?, profile = ?,"
                    " status = 'active', revision = revision + 1, updated_at = ? WHERE id = ?",
                    (run["id"], objective_id, profile_name, db.utcnow(), existing["id"]),
                )
                row = connection.execute(
                    "SELECT * FROM bindings WHERE id = ?", (existing["id"],)
                ).fetchone()
                return {"binding": _view(row), "created": False}
            raise api.RpcError.of(
                "VALIDATION_FAILED",
                "this chat is already bound to another lesson; use the chat that owns it, or abandon it first.",
                field="stored_session_id",
                reason="session_already_bound",
                binding_id=str(existing["id"]),
            )

        active = connection.execute(
            "SELECT * FROM bindings WHERE enrollment_id = ? AND status IN ('active', 'paused')"
            " ORDER BY revision DESC, updated_at DESC LIMIT 1",
            (enrollment["id"],),
        ).fetchone()
        if active is not None:
            same_section = str(active["objective_id"] or "") == str(objective_id)
            if same_section:
                raise api.RpcError.of(
                    "VALIDATION_FAILED",
                    "this lesson already has an active chat; resume it or abandon it before binding another.",
                    field="enrollment_id",
                    reason="enrollment_already_bound",
                    binding_id=str(active["id"]),
                )
            # A different section of the same course: the learner moved on. One section keeps one
            # authoritative chat, so the superseded section's binding is detached — never deleted —
            # and the new run keeps the new chat. Cross-course migration stays refused above.
            connection.execute(
                "UPDATE bindings SET status = 'detached', revision = revision + 1, updated_at = ?"
                " WHERE id = ?",
                (db.utcnow(), active["id"]),
            )

        now = db.utcnow()
        binding_id = _new_id()
        connection.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, connection_id, runtime_session_id,"
            " stored_session_id, lesson_run_id, objective_id, cwd_fingerprint, compression_tip,"
            " status, revision, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'active', 0, ?)",
            (
                binding_id,
                enrollment["id"],
                profile_name,
                str(connection_id).strip() if connection_id else None,
                str(runtime_session_id).strip() if runtime_session_id else None,
                stored,
                run["id"],
                objective_id,
                str(cwd_fingerprint).strip() if cwd_fingerprint else None,
                now,
            ),
        )
        connection.execute(
            "UPDATE lesson_runs SET last_opened_at = ? WHERE id = ?", (now, run["id"])
        )
        row = connection.execute("SELECT * FROM bindings WHERE id = ?", (binding_id,)).fetchone()
    return {"binding": _view(row), "created": True}
