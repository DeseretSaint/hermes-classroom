"""The Coursebook kernel: every command, one transaction each.

Authority order is ``contracts/*.json`` -> :mod:`coursebook.contracts` -> this module. No enum,
error code or payload field is declared here; handler names, verdicts, evidence classes, next
actions and job states all come from the contracts. Registration is registry-driven
(:func:`ensure_registered`) so a contract amendment that adds a method does not require editing
anything in this file — only a new handler.

Transaction shape for a mutation::

    ensure_schema()                  # migrations are their own transactions
    with db.transaction():           # BEGIN IMMEDIATE
        idempotency lookup (replay / conflict)
        compare-and-swap on the aggregate revision
        write rows + one transitions row
        remember the idempotency key with the response it produced

Grading is the one thing that happens **outside** that transaction: the answer is read, graded,
and only then is a second short transaction opened to commit or to persist ``needs_retry``.
:func:`coursebook.db.active_transactions` is the proof that no provider work runs fenced.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

from . import (
    api,
    bindings,
    db,
    evidence,
    generation,
    grading,
    job_service,
    jobs as jobs_contract,
    lesson_document,
    parent_authoring as authoring,
    review,
    sources as source_ledger,
    validators,
)
from .api import RpcError
from .contracts import method_names
# Importing the pronunciation module registers its two commands (it reads the live contract, so a
# build without the v9 methods stays NOT_IMPLEMENTED instead of inventing a method).
from . import pronunciation  # noqa: E402,F401  (registration side effect)
# The student-syllabus commands are registered by their own module for the same reason: a build
# whose contract lacks the v11 methods stays NOT_IMPLEMENTED instead of inventing a method.
from . import syllabus  # noqa: E402,F401  (registration side effect)

#: ``method -> handler(payload, envelope) -> (revision, result)``
HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], tuple[int, dict[str, Any]]]] = {}
# The pronunciation commands are registered by their own module (so they can be imported without
# the kernel) but are still kernel commands: expose them on the kernel registry the tests and
# `ensure_registered` inspect.
HANDLERS.update(pronunciation.HANDLERS)

#: Methods this module owns. Registration is filtered by the live contract, never by this list.
KERNEL_METHODS: tuple[str, ...] = (
    "course.create",
    "course.get",
    "enrollment.create",
    "plan.approve",
    "plan.replan",
    "check.open",
    "attempt.submit",
    "attempt.override",
    "attempt.dispute",
    "progression.challenge_out",
    "notebook.save",
    "notebook.list",
    "notebook.delete",
    "quiz.history",
    "jobs.create",
    "jobs.get",
    "jobs.cancel",
    "usage.summary",
    "library.list",
    "lesson.page",
    "lesson.begin",
    "enrollment.update",
    "enrollment.delete",
    "pack.delete",
    "artifact.get",
    "jobs.list",
    "notebook.update",
    "binding.abandon",
    "review.queue",
    "review.action",
    "evidence.inspect",
    "evidence.disputes",
    "course.outline",
    "check.get",
    "lesson.assist",
    "observation.record",
    "source.revalidate",
    "pronunciation.attempt",
    "pronunciation.dispute",
)

MAX_PAGE = 500


# ── small helpers ───────────────────────────────────────────────────────────


def _handler(method: str):
    def decorator(fn):
        HANDLERS[method] = fn
        return fn

    return decorator


def _new_id(prefix: str) -> str:
    """Random, Coursebook-minted id. Titles and chat ids are never identity (AUDIT.md R1)."""
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return db.utcnow()


def _named_input(value: Any) -> str | None:
    """A declared plan-brief input as stored: trimmed, with blank collapsed to NULL.

    ``NULL`` is the honest value for "the brief did not name this input". It is never filled in
    from another field, so a course row cannot claim a level or subject domain nobody supplied.
    """
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _json_load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json_dump(value).encode("utf-8")).hexdigest()


def _payload_hash(method: str, payload: dict[str, Any]) -> str:
    return _canonical_hash({"method": method, "payload": payload})


def _require_revision(envelope: dict[str, Any]) -> int:
    """Every lesson mutation is revision-fenced (``docs/CONTRACTS.md`` §State rules)."""
    expected = envelope.get("expected_revision")
    if expected is None:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "this command requires expected_revision in the envelope.",
            field="expected_revision",
        )
    return int(expected)


def _stale(message: str, current: int, **details: Any) -> RpcError:
    error = RpcError.of("STALE_REVISION", message, current_revision=current, **details)
    error.error["current_revision"] = current
    return error


def _check_stale(message: str, current_revision: int, **details: Any) -> RpcError:
    error = RpcError.of("CHECK_STALE", message, current_revision=current_revision, **details)
    error.error["current_revision"] = current_revision
    return error


def _not_found(what: str, identifier: str) -> RpcError:
    return RpcError.of("NOT_FOUND", f"{what} {identifier} does not exist in this scope.", id=identifier)


def _row(connection, sql: str, params: tuple = ()) -> Any:
    return connection.execute(sql, params).fetchone()


def _one(connection, sql: str, params: tuple = ()) -> dict[str, Any]:
    row = connection.execute(sql, params).fetchone()
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


# ── idempotency ─────────────────────────────────────────────────────────────


def _idempotent_lookup(
    connection, key: str | None, method: str, payload_hash: str
) -> tuple[int, dict[str, Any]] | None:
    """Return the persisted original result for a replayed key, or ``None``.

    Same key + different payload hash is a conflict, never a silent second execution.
    """
    if not key:
        return None
    row = _row(connection, "SELECT payload_hash, method, response_json FROM idempotency_keys WHERE key = ?", (key,))
    if row is None:
        return None
    if row["payload_hash"] != payload_hash or row["method"] != method:
        raise RpcError.of(
            "IDEMPOTENCY_CONFLICT",
            "this idempotency key was already used with a different payload.",
            key=key,
            method=row["method"],
        )
    stored = _json_load(row["response_json"], {})
    return int(stored.get("revision", 0)), dict(stored.get("result") or {})


def _remember(connection, key: str | None, method: str, payload_hash: str, operation_id: str,
              revision: int, result: dict[str, Any]) -> None:
    if not key:
        return
    connection.execute(
        "INSERT INTO idempotency_keys (key, payload_hash, method, operation_id, response_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (key, payload_hash, method, operation_id, _json_dump({"revision": revision, "result": result}), _now()),
    )


# ── revision and transition fences ──────────────────────────────────────────


def _bump_enrollment(connection, enrollment_id: str, expected: int) -> int:
    cursor = connection.execute(
        "UPDATE enrollments SET revision = revision + 1, updated_at = ? WHERE id = ? AND revision = ?",
        (_now(), enrollment_id, expected),
    )
    if cursor.rowcount == 1:
        return expected + 1
    row = _row(connection, "SELECT revision, status FROM enrollments WHERE id = ?", (enrollment_id,))
    if row is None:
        raise _not_found("enrollment", enrollment_id)
    raise _stale("the enrollment moved on; reconcile against current_revision.", int(row["revision"]),
                 enrollment_id=enrollment_id)


def _transition(connection, enrollment_id: str, from_revision: int, to_revision: int,
                next_action: str, attempt_id: str | None = None) -> None:
    connection.execute(
        "INSERT INTO transitions (id, enrollment_id, attempt_id, from_revision, to_revision, next_action, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_new_id("trn"), enrollment_id, attempt_id, from_revision, to_revision, next_action, _now()),
    )


def _enrollment(connection, enrollment_id: str) -> Any:
    row = _row(connection, "SELECT * FROM enrollments WHERE id = ?", (enrollment_id,))
    if row is None:
        raise _not_found("enrollment", enrollment_id)
    return row


def _course_of_enrollment(connection, enrollment) -> Any:
    course = _row(connection, "SELECT * FROM courses WHERE id = ?", (enrollment["course_id"],))
    if course is None:
        raise _not_found("course", enrollment["course_id"])
    return course


def _approved_plan(connection, course_id: str) -> Any:
    return _row(
        connection,
        "SELECT * FROM plans WHERE course_id = ? AND state = 'approved' ORDER BY version DESC LIMIT 1",
        (course_id,),
    )


def _objective_in_plan(connection, objective_id: str, plan_id: str) -> Any:
    row = _row(connection, "SELECT * FROM objectives WHERE id = ? AND plan_id = ?", (objective_id, plan_id))
    if row is None:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "that objective is not part of the enrollment's approved plan.",
            field="objective_id",
            reason="objective_not_in_approved_plan",
        )
    return row


# ── plan content and check specs ────────────────────────────────────────────


def _plan_hash(connection, plan) -> str:
    """The plan's content hash. One implementation lives in ``parent_authoring``."""
    return authoring.plan_hash(connection, plan)


def _check_spec(objective) -> dict[str, Any] | None:
    """The gradable spec for an objective, or ``None`` when the objective is not checkable.

    Convention (kernel-owned, inside ``objectives.evidence_criteria_json``): a criteria list where
    the first entry carrying a ``check_spec`` object supplies the check. A spec is::

        {"audit_state": "passed" | "pending" | "failed",
         "reference": {"kind": ...},
         "stimulus": {...},
         "rubric": {"construct": ..., "criteria": [...], "pass_rule": "all"},
         "variants": [{"stimulus": {...}, "reference": {...}, "audit_state": "passed"}]}
    """
    criteria = _json_load(objective["evidence_criteria_json"], [])
    if not isinstance(criteria, list):
        return None
    for criterion in criteria:
        if isinstance(criterion, dict) and isinstance(criterion.get("check_spec"), dict):
            spec = dict(criterion["check_spec"])
            spec.setdefault("criterion_id", str(criterion.get("id") or "c1"))
            return spec
    return None


def _audit_ok(spec: dict[str, Any]) -> bool:
    return str(spec.get("audit_state") or "pending") == "passed"


def _spec_content(spec: dict[str, Any]) -> tuple[dict, dict, dict]:
    stimulus = spec.get("stimulus") or {}
    reference = spec.get("reference") or {}
    rubric = spec.get("rubric") or {}
    return stimulus, reference, rubric


# ── reads ───────────────────────────────────────────────────────────────────


@_handler("course.get")
def course_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    with db.read() as connection:
        course = _row(connection, "SELECT * FROM courses WHERE id = ?", (payload["course_id"],))
        if course is None or course["status"] == "deleted":
            raise _not_found("course", payload["course_id"])
        plans = connection.execute(
            "SELECT id, version, state, plan_hash, created_at, approved_at FROM plans"
            " WHERE course_id = ? ORDER BY version DESC",
            (course["id"],),
        ).fetchall()
        binding = _row(connection, "SELECT * FROM course_syllabi WHERE course_id = ?", (course["id"],))
        syllabus = None
        if binding is not None:
            bound = _row(connection, "SELECT * FROM syllabi WHERE id = ?", (binding["syllabus_id"],))
            counts: dict[str, int] = {}
            if bound is not None:
                for row in connection.execute(
                    "SELECT state, COUNT(*) AS n FROM syllabus_alignments WHERE course_id = ?"
                    " AND syllabus_revision = ? GROUP BY state",
                    (course["id"], binding["syllabus_revision"]),
                ):
                    counts[str(row["state"])] = int(row["n"])
            syllabus = {
                "syllabus_id": binding["syllabus_id"],
                "revision": int(binding["syllabus_revision"]),
                "content_sha256": bound["content_sha256"] if bound is not None else None,
                "alignment_revision": int(binding["alignment_revision"]),
                "reviewed_revision": binding["reviewed_revision"],
                "alignment_counts": counts,
                "stale": bool(bound is None or bound["superseded_at"] is not None
                              or int(binding["syllabus_revision"]) != int(bound["revision"] or 0)),
            }
    result = {
        "course": {
            "course_id": course["id"],
            "title": course["title"],
            "recipe": course["recipe"],
            "goal": course["goal"],
            "locale": course["locale"],
            "level": course["level"],
            "subject_domain": course["subject_domain"],
            "scope": course["scope"],
            "dials": _json_load(course["dials_json"], {}),
            "status": course["status"],
            "pack_id": course["pack_id"],
            "created_at": course["created_at"],
            "updated_at": course["updated_at"],
            "plans": [
                {
                    "plan_id": plan["id"],
                    "version": int(plan["version"]),
                    "state": plan["state"],
                    "plan_hash": plan["plan_hash"],
                }
                for plan in plans
            ],
            "active_plan_id": next((plan["id"] for plan in plans if plan["state"] == "approved"), None),
            "syllabus": syllabus,
        },
        "revision": int(course["revision"]),
    }
    return int(course["revision"]), result


@_handler("notebook.list")
def notebook_list(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    enrollment_id = payload.get("enrollment_id")
    with db.read() as connection:
        clauses: list[str] = []
        params: list[Any] = []
        if enrollment_id:
            _enrollment(connection, enrollment_id)
            clauses.append("enrollment_id = ?")
            params.append(enrollment_id)
        if payload.get("tag"):
            clauses.append("EXISTS (SELECT 1 FROM json_each(tags_json) WHERE value = ?)")
            params.append(payload["tag"])
        if payload.get("query"):
            escaped = payload["query"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("(note LIKE ? ESCAPE '\\' OR excerpt LIKE ? ESCAPE '\\')")
            params.extend([f"%{escaped}%", f"%{escaped}%"])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"SELECT * FROM notebook_entries{where} ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (*params, MAX_PAGE),
        ).fetchall()
    entries = [
        {
            "entry_id": row["id"],
            "enrollment_id": row["enrollment_id"],
            "objective_id": row["objective_id"],
            "lesson_run_id": row["lesson_run_id"],
            "kind": row["kind"],
            "excerpt": row["excerpt"],
            "note": row["note"],
            "tags": _json_load(row["tags_json"], []),
            "source_ref": row["source_ref"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "revision": int(row["revision"]),
        }
        for row in rows
    ]
    return 0, {"entries": entries}


@_handler("quiz.history")
def quiz_history(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Past attempts, newest first. Never includes a reference answer or rubric key."""
    db.ensure_schema()
    with db.read() as connection:
        enrollment = _enrollment(connection, payload["enrollment_id"])
        clauses = ["a.enrollment_id = ?"]
        params: list[Any] = [enrollment["id"]]
        if payload.get("objective_id"):
            clauses.append("c.objective_id = ?")
            params.append(payload["objective_id"])
        rows = connection.execute(
            "SELECT a.*, c.objective_id AS objective_id FROM attempts a"
            " JOIN checks c ON c.id = a.check_id"
            f" WHERE {' AND '.join(clauses)}"
            " ORDER BY a.created_at DESC, a.rowid DESC LIMIT ?",
            (*params, MAX_PAGE),
        ).fetchall()
    attempts = []
    for row in rows:
        provenance = _json_load(row["grading_provenance_json"], {})
        disputes = provenance.pop("disputes", []) if isinstance(provenance, dict) else []
        attempts.append(
            {
                "attempt_id": row["id"],
                "check_id": row["check_id"],
                "check_version": int(row["check_version"]),
                "objective_id": row["objective_id"],
                "answer_kind": row["answer_kind"],
                "answer": _json_load(row["answer_json"], {}),
                "verdict": row["verdict"],
                "evidence_class": row["evidence_class"],
                "criteria": _json_load(row["criteria_json"], []),
                "state": row["state"],
                "grading_provenance": provenance,
                "disputes": disputes,
                "created_at": row["created_at"],
                "committed_at": row["committed_at"],
            }
        )
    return int(enrollment["revision"]), {"attempts": attempts}


@_handler("binding.get")
def binding_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Resolve a binding by stored session id or enrollment id — never by recency.

    A binding carries both ids (``cb.db`` -> bindings): ``runtime_session_id`` is the id the
    gateway uses for the live chat, ``stored_session_id`` is the durable id that survives
    compression/rotation. They are never interchangeable (``AUDIT.md`` R1), so this handler
    matches ``stored_session_id`` only and reports which column matched. A caller holding only
    a runtime id resolves it on the Desktop half first.
    """
    db.ensure_schema()
    session_id = payload.get("session_id")
    enrollment_id = payload.get("enrollment_id")
    if bool(session_id) == bool(enrollment_id):
        # Ambiguity is refused rather than resolved by precedence: a caller that sends two
        # identifiers cannot prove which one the answer came from.
        raise RpcError.of(
            "VALIDATION_FAILED",
            "binding.get takes exactly one of session_id (stored session id) or enrollment_id.",
            field="session_id" if session_id else "enrollment_id",
        )
    column = "enrollment_id" if enrollment_id else "stored_session_id"
    value = str(enrollment_id if enrollment_id else session_id)
    with db.read() as connection:
        row = _row(
            connection,
            f"SELECT * FROM bindings WHERE {column} = ?"
            " ORDER BY (status = 'active') DESC, revision DESC, updated_at DESC LIMIT 1",
            (value,),
        )
    if row is None:
        return 0, {"binding": None}
    # `cb.db` v2 stores the section a chat is bound to. Emitting it is what lets the pane scope to
    # the bound section instead of the enrollment's current one (a chat bound to section 3 was
    # rendering section 1's page and section 1's detached run). The `bindings` object in
    # `cb.rpc` v5 is an open object, so these two additive fields need no version bump; `status`
    # stays the row's own status, never derived from the section.
    section_columns = row.keys()
    lesson_run_id = row["lesson_run_id"] if "lesson_run_id" in section_columns else None
    # A teaching snapshot that could not be written is durable evidence loss (`cb.db` v10
    # `hook_errors`). The pane needs to see *that* — this is the read it already makes on open, and
    # the `bindings` object in `cb.rpc` is open, so no version bump is needed for the field.
    from . import turn

    failures = turn.snapshot_failures(lesson_run_id=lesson_run_id)
    return int(row["revision"]), {
        "binding": {
            "binding_id": row["id"],
            "id": row["id"],
            "enrollment_id": row["enrollment_id"],
            "profile": row["profile"],
            "connection_id": row["connection_id"],
            "runtime_session_id": row["runtime_session_id"],
            "stored_session_id": row["stored_session_id"],
            "lesson_run_id": lesson_run_id,
            "objective_id": row["objective_id"] if "objective_id" in section_columns else None,
            "snapshot_failures": failures,
            "cwd_fingerprint": row["cwd_fingerprint"],
            "compression_tip": row["compression_tip"],
            "status": row["status"],
            "revision": int(row["revision"]),
            "updated_at": row["updated_at"],
            "matched_column": column,
        }
    }


# ── courses, plans, enrollments ─────────────────────────────────────────────


@_handler("course.create")
def course_create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    method = "course.create"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    now = _now()
    course_id = _new_id("crs")
    plan_id = _new_id("pln")
    syllabus_id = payload.get("syllabus_id")
    syllabus_revision = payload.get("syllabus_revision")
    if (syllabus_id is None) != (syllabus_revision is None):
        raise RpcError.of(
            "VALIDATION_FAILED",
            "course.create takes syllabus_id and syllabus_revision together or not at all.",
            field="syllabus_id" if syllabus_id is None else "syllabus_revision",
        )
    if syllabus_id is not None:
        if payload["recipe"] != "companion":
            raise RpcError.of(
                "VALIDATION_FAILED",
                "a syllabus-backed course is a companion course; recipe must be 'companion'.",
                field="recipe", recipe=payload["recipe"],
            )
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        if syllabus_id is not None:
            bound = _row(
                connection, "SELECT * FROM syllabi WHERE id = ? AND revision = ?",
                (syllabus_id, int(syllabus_revision)),
            )
            if bound is None or bound["deleted_at"] is not None:
                raise _not_found("syllabus", str(syllabus_id))
            if bound["superseded_at"] is not None:
                raise RpcError.of(
                    "SYLLABUS_STALE",
                    "that syllabus revision is superseded; re-align and review the current revision.",
                    syllabus_id=syllabus_id, revision=int(syllabus_revision),
                )
            latest_run = _row(
                connection,
                "SELECT state FROM syllabus_parse_runs WHERE syllabus_id = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (bound["id"],),
            )
            if latest_run is None:
                raise RpcError.of(
                    "SYLLABUS_UNREVIEWED",
                    "the syllabus has not been parsed; run syllabus.parse first.",
                    reason="not_parsed",
                )
            if str(latest_run["state"]) == "needs_review":
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    "this parse needs review (anchor verification failed); re-parse or upload a cleaner file.",
                    reason="needs_review",
                )
        connection.execute(
            "INSERT INTO courses (id, title, recipe, goal, locale, level, subject_domain, scope,"
            " dials_json, status, pack_id, revision, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', NULL, 0, ?, ?)",
            (course_id, payload["title"], payload["recipe"], payload["goal"], payload.get("locale"),
             _named_input(payload.get("level")), _named_input(payload.get("subject_domain")),
             _named_input(payload.get("scope")), _json_dump(payload.get("dials") or {}), now, now),
        )
        connection.execute(
            "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json, created_at, approved_at)"
            " VALUES (?, ?, 1, 'draft', NULL, '{}', ?, NULL)",
            (plan_id, course_id, now),
        )
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (plan_id,))
        connection.execute(
            "UPDATE plans SET plan_hash = ? WHERE id = ?", (_plan_hash(connection, plan), plan_id)
        )
        if syllabus_id is not None:
            connection.execute(
                "INSERT INTO course_syllabi (course_id, syllabus_id, syllabus_revision,"
                " alignment_revision, reviewed_revision, reviewed_at, created_at)"
                " VALUES (?, ?, ?, 0, NULL, NULL, ?)",
                (course_id, syllabus_id, int(syllabus_revision), now),
            )
        result = {"course_id": course_id, "plan_id": plan_id, "revision": 0}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


@_handler("enrollment.create")
def enrollment_create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    method = "enrollment.create"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    now = _now()
    enrollment_id = _new_id("enr")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        course = _row(connection, "SELECT id, status FROM courses WHERE id = ?", (payload["course_id"],))
        if course is None or course["status"] == "deleted":
            raise _not_found("course", payload["course_id"])
        connection.execute(
            "INSERT INTO enrollments (id, course_id, learner_label, status, revision, created_at, updated_at)"
            " VALUES (?, ?, ?, 'active', 0, ?, ?)",
            (enrollment_id, course["id"], payload.get("learner_label"), now, now),
        )
        result = {"enrollment_id": enrollment_id, "revision": 0}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


#: Provenance a ``plan.approve`` caller can receive. Approval never invents a validation pass:
#: ``generated_validated`` means a durable generation record binds this exact kernel content hash
#: to a ``pass`` verdict; ``manual`` means an authored non-empty outline with no validation claim.
PLAN_VALIDATION_GENERATED = "generated_validated"
#: ``model_assessed_pass`` means a durable, passing generation record exists, but its validator was
#: not an independent model. A human may approve it (plan approval is a human event, not a
#: factual-verification claim); it is never recorded or described as independently validated.
PLAN_VALIDATION_MODEL_ASSESSED = "model_assessed_pass"
PLAN_VALIDATION_MANUAL = "manual"


def _table_exists(connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def _syllabus_approval_gate(connection, course_id: str) -> None:
    """Additive ``plan.approve`` precondition for a companion course only.

    A legacy course has no ``course_syllabi`` row and is unaffected. A companion course may only
    be approved against the current syllabus revision, after an alignment review, with no pending
    conflict/stale row, and with the content hash the alignment was built against still current.
    """
    binding = _row(connection, "SELECT * FROM course_syllabi WHERE course_id = ?", (course_id,))
    if binding is None:
        return
    bound = _row(connection, "SELECT * FROM syllabi WHERE id = ?", (binding["syllabus_id"],))
    if (bound is None or bound["deleted_at"] is not None or bound["superseded_at"] is not None
            or int(bound["revision"]) != int(binding["syllabus_revision"])):
        raise RpcError.of(
            "SYLLABUS_STALE",
            "the bound syllabus revision is stale; re-parse, re-align and review before approving.",
            syllabus_id=binding["syllabus_id"],
            syllabus_revision=int(binding["syllabus_revision"]),
        )
    current = _row(
        connection,
        "SELECT id FROM syllabi WHERE series_id = ? AND deleted_at IS NULL"
        " ORDER BY revision DESC LIMIT 1",
        (bound["series_id"],),
    )
    if current is None or current["id"] != bound["id"]:
        raise RpcError.of(
            "SYLLABUS_STALE", "a newer syllabus revision exists; re-align and review it first.",
            syllabus_id=binding["syllabus_id"],
        )
    if binding["reviewed_revision"] is None or int(binding["reviewed_revision"]) != int(bound["revision"]):
        raise RpcError.of(
            "SYLLABUS_UNREVIEWED",
            "the alignment for this syllabus revision has not been reviewed.",
            syllabus_revision=int(bound["revision"]),
        )
    blocking = _row(
        connection,
        "SELECT COUNT(*) AS n FROM syllabus_alignments WHERE course_id = ? AND syllabus_revision = ?"
        " AND stale = 0 AND state IN ('conflict', 'stale') AND review_state = 'pending'",
        (course_id, int(bound["revision"])),
    )
    if blocking is not None and int(blocking["n"]) > 0:
        raise RpcError.of(
            "SYLLABUS_STALE",
            "a syllabus conflict is unresolved; accept the divergence or replan before approving.",
            conflicts=int(blocking["n"]),
        )
    hashes = set()
    for row in connection.execute(
        "SELECT evidence_json FROM syllabus_alignments WHERE course_id = ? AND syllabus_revision = ?",
        (course_id, int(bound["revision"])),
    ):
        evidence = _json_load(row["evidence_json"], {})
        if isinstance(evidence, dict) and evidence.get("syllabus_sha256"):
            hashes.add(str(evidence["syllabus_sha256"]))
    if not hashes:
        raise RpcError.of(
            "SYLLABUS_UNREVIEWED",
            "this course has no alignment rows for its syllabus revision.",
            syllabus_revision=int(bound["revision"]),
        )
    if hashes != {str(bound["content_sha256"])}:
        raise RpcError.of(
            "SYLLABUS_STALE",
            "the syllabus content changed after the plan was aligned; re-align and review.",
            syllabus_revision=int(bound["revision"]),
        )


def _plan_outline_ready(connection, plan_id: str) -> bool:
    """Whether the plan carries at least one usable authored objective.

    A manual plan's outline is its objectives: a title and an evidence target the learner can be
    assessed against. This is deliberately *not* a validation claim.
    """
    row = connection.execute(
        "SELECT COUNT(*) AS n FROM objectives WHERE plan_id = ?"
        " AND TRIM(COALESCE(title, '')) <> '' AND TRIM(COALESCE(evidence_target, '')) <> ''",
        (plan_id,),
    ).fetchone()
    return row is not None and int(row["n"]) > 0


def _plan_validation_source(connection, plan, actual_hash: str) -> str:
    """Resolve the approval provenance or refuse with a typed, fail-closed error.

    A generated plan is approvable only when the *latest* generation document for this plan
    records the independent validation pass **and** carries a durable snapshot of the kernel
    content hash it validated. ``gen_plan_documents.plan_hash`` is the generation digest (a
    different function), so it is never compared to the kernel hash directly.

    H-15 union: the refusal is for a *rejected* or unvalidated plan. A pass whose validator was
    the author's own model is stored as ``needs_review`` / ``model_assessed``: the parent may
    still approve it, because plan approval is the human review that state names, and the
    ``facts unverified`` / ``model assessed`` warning travels with the document. It is not
    described as independently validated either way.

    A plan with no generation document is manually authored: it may approve on a real outline,
    and it is never described as validated. An invalidation performed by an authoring command
    leaves ``manual_authoring = true`` on the generation record, which is the durable manual
    decision; a carried/replanned record without it stays unvalidated.
    """
    if not _table_exists(connection, "gen_plan_documents"):
        return PLAN_VALIDATION_MANUAL
    row = connection.execute(
        "SELECT * FROM gen_plan_documents WHERE plan_id = ?"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (str(plan["id"]),),
    ).fetchone()
    if row is None:
        return PLAN_VALIDATION_MANUAL
    result = _json_load(row["result_json"], {})
    if not isinstance(result, dict):
        result = {}
    if result.get("manual_authoring") is True:
        return PLAN_VALIDATION_MANUAL
    state = str(row["generation_state"])
    verdict = str(result.get("validation_verdict") or "")
    validation_raw = result.get("validation")
    validation: dict[str, Any] = validation_raw if isinstance(validation_raw, dict) else {}
    outcome = str(validation.get("outcome") or result.get("outcome") or "")
    if state not in ("draft", "needs_review") or verdict != "pass" or outcome == "rejected":
        raise RpcError.of(
            "VALIDATION_FAILED",
            "the plan has no passing validation record; it cannot be approved.",
            reason="plan_not_validated",
            plan_id=str(plan["id"]),
            generation_state=state,
            validation_verdict=verdict or None,
        )
    snapshot = result.get("plan_content_hash")
    if not isinstance(snapshot, str) or not snapshot:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "the plan has no durable validation binding; revalidate before approving.",
            reason="plan_not_validated",
            plan_id=str(plan["id"]),
            detail="validation passed without a bound content hash",
        )
    if snapshot != actual_hash:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "the plan changed after it was validated; the recorded pass is stale.",
            reason="plan_validation_stale",
            plan_id=str(plan["id"]),
            validated_plan_hash=snapshot,
            current_plan_hash=actual_hash,
        )
    return PLAN_VALIDATION_MODEL_ASSESSED if (outcome == "model_assessed" or state == "needs_review") else PLAN_VALIDATION_GENERATED


@_handler("plan.approve")
def plan_approve(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Approve the exact plan content the caller saw, and only when it is approvable.

    Fail closed: an empty plan is never approved; a generated plan needs a durable passing
    validation record bound to this exact content hash; a manually authored plan needs a real
    outline. A model-assessed pass (the author's own model) is approvable as the human review its
    ``needs_review`` state names, and is never described as independently validated. A refusal
    writes no transition, no revision and no approval timestamp.
    """
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "plan.approve"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (payload["plan_id"],))
        if plan is None or plan["course_id"] != enrollment["course_id"]:
            raise _not_found("plan", payload["plan_id"])
        actual_hash = _plan_hash(connection, plan)
        if payload["plan_hash"] != actual_hash:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "the approved hash does not match the current plan content; re-read the plan.",
                field="plan_hash",
                current_plan_hash=actual_hash,
            )
        if int(enrollment["revision"]) != expected:
            # Revision fencing wins before approval semantics: a stale caller must reconcile, and
            # this check writes nothing.
            raise _stale(
                "the enrollment moved on; reconcile against current_revision.",
                int(enrollment["revision"]),
                enrollment_id=enrollment["id"],
            )
        if plan["state"] == "approved":
            raise RpcError.of("POLICY_VIOLATION", "this plan version is already approved.", plan_id=plan["id"])
        objectives = int(_row(
            connection, "SELECT COUNT(*) AS n FROM objectives WHERE plan_id = ?", (plan["id"],)
        )["n"])
        if objectives == 0:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "an empty plan cannot be approved; it has no objectives.",
                reason="plan_empty",
                plan_id=str(plan["id"]),
            )
        validation_source = _plan_validation_source(connection, plan, actual_hash)
        _syllabus_approval_gate(connection, enrollment["course_id"])
        if validation_source == PLAN_VALIDATION_MANUAL and not _plan_outline_ready(connection, plan["id"]):
            raise RpcError.of(
                "VALIDATION_FAILED",
                "a manually authored plan needs at least one objective with a title and evidence target.",
                reason="plan_not_validated",
                plan_id=str(plan["id"]),
                detail="manual outline is empty",
            )
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        connection.execute(
            "UPDATE plans SET state = 'superseded' WHERE course_id = ? AND state = 'approved'",
            (enrollment["course_id"],),
        )
        connection.execute(
            "UPDATE plans SET state = 'approved', plan_hash = ?, approved_at = ? WHERE id = ?",
            (actual_hash, _now(), plan["id"]),
        )
        _transition(connection, enrollment["id"], expected, to_revision, "continue")
        result = {"plan_hash": actual_hash, "revision": to_revision}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


def _carry_plan_units(
    connection,
    *,
    source_plan_id: str,
    target_plan_id: str,
    ordinal_map: dict[int, int],
    added_ordinals: Sequence[int],
    now: str,
) -> None:
    """Copy a replanned version's unit structure and re-point its objectives (R3).

    ``plan.replan`` writes new ``plans`` and ``objectives`` rows; without this carry every
    blueprint plan loses its units — and with them every edge the learner approved — the moment
    it is replanned. Mapping is structural, never guessed:

    * a unit whose every source objective is removed from the new version is dropped, and the
      surviving units are renumbered contiguously;
    * a surviving unit that still names a dropped unit is **refused**: an edge may not outlive
      its target (§14.2 R3), and the whole replan rolls back because the refusal is raised inside
      the transaction;
    * added objectives join the last surviving unit, so they still project into a unit rather
      than becoming invisible in ``course.outline``.
    """
    source_units = _plan_unit_rows(connection, source_plan_id)
    if not source_units:
        return
    members: dict[str, list[int]] = {}
    for row in connection.execute(
        "SELECT ordinal, unit_id FROM objectives WHERE plan_id = ? ORDER BY ordinal",
        (str(source_plan_id),),
    ).fetchall():
        if row["unit_id"] is not None and int(row["ordinal"]) in ordinal_map:
            members.setdefault(str(row["unit_id"]), []).append(int(row["ordinal"]))
    surviving = [unit for unit in source_units if members.get(str(unit["id"]))]
    dropped = {
        int(unit["ordinal"]) for unit in source_units if not members.get(str(unit["id"]))
    }
    new_ordinal = {
        int(unit["ordinal"]): index for index, unit in enumerate(surviving, start=1)
    }
    rebuilt: list[tuple[Any, int, list[int]]] = []
    for unit in surviving:
        old_ordinal = int(unit["ordinal"])
        refs: list[int] = []
        for ref in _unit_prereqs(unit):
            if ref not in new_ordinal:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    f"the replan drops unit {ref}, which unit {old_ordinal} still requires.",
                    reason="prerequisite_missing_unit",
                    unit_ordinal=old_ordinal,
                    prerequisite_ordinal=ref,
                    removed_unit_ordinals=sorted(dropped),
                )
            refs.append(new_ordinal[ref])
        rebuilt.append((unit, new_ordinal[old_ordinal], refs))
    target_objective_ids = {
        int(row["ordinal"]): str(row["id"])
        for row in connection.execute(
            "SELECT id, ordinal FROM objectives WHERE plan_id = ?", (str(target_plan_id),)
        ).fetchall()
    }
    unit_ids: dict[int, str] = {}
    for unit, ordinal, refs in rebuilt:
        unit_ids[ordinal] = _new_id("unt")
        connection.execute(
            "INSERT INTO plan_units (id, plan_id, ordinal, title, goal, prereq_unit_ordinals_json,"
            " target_lessons, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                unit_ids[ordinal], str(target_plan_id), ordinal, unit["title"], unit["goal"],
                _json_dump(refs), int(unit["target_lessons"]), now,
            ),
        )
    for unit in surviving:
        for source_ordinal in members.get(str(unit["id"]), []):
            target_ordinal = ordinal_map[source_ordinal]
            objective_id = target_objective_ids.get(target_ordinal)
            if objective_id is None:
                continue
            connection.execute(
                "UPDATE objectives SET unit_id = ? WHERE id = ?",
                (unit_ids[new_ordinal[int(unit["ordinal"])]], objective_id),
            )
    if unit_ids and added_ordinals:
        last_unit_id = unit_ids[max(unit_ids)]
        for ordinal in added_ordinals:
            objective_id = target_objective_ids.get(int(ordinal))
            if objective_id is not None:
                connection.execute(
                    "UPDATE objectives SET unit_id = ? WHERE id = ?", (last_unit_id, objective_id)
                )


@_handler("plan.replan")
def plan_replan(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Create a new draft plan version. The approved plan is superseded, so checks pause until
    the new version is approved — a replan is never silently effective."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "plan.replan"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    now = _now()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        current = _approved_plan(connection, enrollment["course_id"])
        if current is None:
            raise RpcError.of(
                "VALIDATION_FAILED", "there is no approved plan to replan from.", reason="plan_not_approved"
            )
        objectives = connection.execute(
            "SELECT * FROM objectives WHERE plan_id = ? ORDER BY ordinal", (current["id"],)
        ).fetchall()
        by_id = {row["id"]: row for row in objectives}
        for change in payload["objective_changes"]:
            if change["objective_id"] not in by_id:
                raise _not_found("objective", change["objective_id"])
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        new_plan_id = _new_id("pln")
        connection.execute(
            "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json, created_at, approved_at)"
            " VALUES (?, ?, ?, 'draft', NULL, ?, ?, NULL)",
            (new_plan_id, enrollment["course_id"], int(current["version"]) + 1,
             current["schedule_json"], now),
        )
        ordinals: list[tuple[str, str, str]] = []
        for change in payload["objective_changes"]:
            source = by_id[change["objective_id"]]
            if change["change"] == "remove":
                continue
            title = change.get("title") or source["title"] if change["change"] == "retitle" else source["title"]
            ordinals.append((source["id"], title, change["change"]))
        for index, (source_id, title, change_kind) in enumerate(ordinals, start=1):
            source = by_id[source_id]
            state = "not_started" if change_kind == "defer" else source["state"]
            connection.execute(
                "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target, evidence_criteria_json,"
                " state, version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (_new_id("obj"), new_plan_id, index, title, source["evidence_target"],
                 source["evidence_criteria_json"], state, int(source["version"]), now),
            )
        added = [change for change in payload["objective_changes"] if change["change"] == "add"]
        for offset, change in enumerate(added, start=len(ordinals) + 1):
            connection.execute(
                "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target, evidence_criteria_json,"
                " state, version, created_at) VALUES (?, ?, ?, ?, 'recall', '[]', 'not_started', 1, ?)",
                (_new_id("obj"), new_plan_id, offset, change.get("title") or "Untitled objective", now),
            )
        # R3: the new version carries the approved unit structure, or every edge the learner
        # approved would point at a unit the replanned version does not have. The carry refuses a
        # structure the change set cannot preserve and rolls the whole replan back.
        _carry_plan_units(
            connection,
            source_plan_id=str(current["id"]),
            target_plan_id=new_plan_id,
            ordinal_map={
                int(by_id[source_id]["ordinal"]): index
                for index, (source_id, _title, _change) in enumerate(ordinals, start=1)
            },
            added_ordinals=list(range(len(ordinals) + 1, len(ordinals) + len(added) + 1)),
            now=now,
        )
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (new_plan_id,))
        connection.execute("UPDATE plans SET plan_hash = ? WHERE id = ?", (_plan_hash(connection, plan), new_plan_id))
        # A replan edits the plan, not the authored outline. Without carrying the outline the new
        # version can never produce lessons (``run_lesson_job`` loads the document by ``plan_id``)
        # and the course is stuck one approval short of export forever. The carry refuses whenever
        # the change set is not a faithful remap (a structural add has no authored section to copy).
        section_targets = {
            int(by_id[source_id]["ordinal"]): index
            for index, (source_id, _title, _change) in enumerate(ordinals, start=1)
        }
        generation.carry_plan_outline(
            connection,
            new_plan_id,
            source_plan_id=str(current["id"]),
            section_targets=section_targets,
            now=None,
        )
        connection.execute(
            "UPDATE plans SET state = 'superseded' WHERE course_id = ? AND state = 'approved'",
            (enrollment["course_id"],),
        )
        _transition(connection, enrollment["id"], expected, to_revision, "review_objective")
        result = {"plan_version": int(current["version"]) + 1, "revision": to_revision}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


# ── checks ──────────────────────────────────────────────────────────────────


def _insert_check(connection, objective, spec: dict[str, Any], stimulus: dict, reference: dict,
                  rubric: dict, version: int) -> str:
    check_id = _new_id("chk")
    connection.execute(
        "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json, rubric_json,"
        " reference_json, locale, audit_state, state, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
        (check_id, objective["id"], version, objective["evidence_target"],
         _json_dump(stimulus), _json_dump(rubric), _json_dump(reference), spec.get("locale"), "passed", _now()),
    )
    return check_id


# ── §14.2 prerequisite edges: reader fence and disclosure ───────────────────

#: The only objective states that satisfy a prerequisite edge (§14.2 R5a). ``overridden``
#: satisfies access only and is still described as *not independently demonstrated*.
_PREREQUISITE_SATISFIED = ("independent_evidence", "delayed_evidence", "overridden")


def _plan_unit_rows(connection, plan_id: str) -> list[Any]:
    """The plan's ``plan_units`` rows, or ``[]`` on a legacy database without the table."""
    try:
        return connection.execute(
            "SELECT * FROM plan_units WHERE plan_id = ? ORDER BY ordinal", (str(plan_id),)
        ).fetchall()
    except sqlite3.OperationalError:  # a v6 database has no plan_units table yet
        return []


def _unit_prereqs(row: Any) -> list[int]:
    return [int(value) for value in _json_load(row["prereq_unit_ordinals_json"], [])]


def _validated_unit_rows(connection, plan_id: str) -> list[Any]:
    """Read a stored plan's units and refuse a document the writer could not have produced.

    The writer refuses forward references, so a cycle cannot be authored; unrepresentability is
    a property of the writer, not of the reader (§14.2 R2). A hand-edited, imported or
    future-extension document is refused here with a typed reason and nothing else is read from
    it. A cycle is named first, because the backwards rule would otherwise report only its
    forward half.
    """
    rows = _plan_unit_rows(connection, plan_id)
    if not rows:
        return rows
    edges = {int(row["ordinal"]): _unit_prereqs(row) for row in rows}
    # A self reference is named as such before cycle detection: it *is* a one-node cycle, and
    # "unit N names itself" is the more useful refusal for a hand-edited row.
    for ordinal, refs in edges.items():
        if ordinal in refs:
            raise RpcError.of(
                "VALIDATION_FAILED",
                f"unit {ordinal} names itself as a prerequisite.",
                reason="prerequisite_self_ref",
                unit_ordinal=ordinal,
            )
    cycle = generation.find_unit_cycle(edges)
    if cycle is not None:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "the plan's unit prerequisites form a cycle; the plan cannot be sequenced.",
            reason="prerequisite_cycle",
            cycle=cycle,
        )
    known = set(edges)
    for ordinal, refs in edges.items():
        for ref in refs:
            if ref == ordinal:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    f"unit {ordinal} names itself as a prerequisite.",
                    reason="prerequisite_self_ref",
                    unit_ordinal=ordinal,
                )
            if refs.count(ref) > 1:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    f"unit {ordinal} names prerequisite unit {ref} more than once.",
                    reason="prerequisite_duplicate_ref",
                    unit_ordinal=ordinal,
                    prerequisite_ordinal=ref,
                )
            if ref not in known:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    f"unit {ordinal} names missing prerequisite unit {ref}.",
                    reason="prerequisite_missing_unit",
                    unit_ordinal=ordinal,
                    prerequisite_ordinal=ref,
                )
            if ref > ordinal:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    f"unit {ordinal} names prerequisite {ref}; every prerequisite must be a "
                    "lower unit.",
                    reason="prerequisite_forward_ref",
                    unit_ordinal=ordinal,
                    prerequisite_ordinal=ref,
                )
    return rows


def _prerequisite_state(connection, plan, objective) -> dict[str, Any] | None:
    """R5's disclosure for one objective: ``None`` when the plan has no edges into its unit.

    ``no_edges`` is a legacy or flat plan and returns ``None`` so the command response is
    unchanged. ``satisfied`` and ``unmet`` are computed only from the seven objective-state
    labels the kernel already has — never from criteria, timing, attempt count, model opinion or
    a score (R5a, R7).
    """
    rows = _validated_unit_rows(connection, plan["id"])
    if not rows:
        return None
    unit_id = dict(objective).get("unit_id")
    if unit_id is None:
        return None
    unit = next((row for row in rows if str(row["id"]) == str(unit_id)), None)
    if unit is None:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "this objective names a unit the plan does not have.",
            reason="prerequisite_missing_unit",
            objective_id=str(objective["id"]),
            unit_id=str(unit_id),
        )
    prereqs = _unit_prereqs(unit)
    if not prereqs:
        return None
    unmet: list[dict[str, Any]] = []
    totals = 0
    for ref in prereqs:
        members = connection.execute(
            "SELECT id, ordinal, title, state FROM objectives WHERE plan_id = ? AND unit_id IN"
            " (SELECT id FROM plan_units WHERE plan_id = ? AND ordinal = ?) ORDER BY ordinal",
            (str(plan["id"]), str(plan["id"]), ref),
        ).fetchall()
        for row in members:
            totals += 1
            if str(row["state"]) not in _PREREQUISITE_SATISFIED:
                unmet.append(
                    {
                        "objective_id": str(row["id"]),
                        "ordinal": int(row["ordinal"]),
                        "title": str(row["title"]),
                        "state": str(row["state"]),
                    }
                )
    state = "unmet" if unmet else "satisfied"
    return {"state": state, "unmet": unmet, "_totals": totals, "_unit": unit,
            "_prereq_units": [row for row in rows if int(row["ordinal"]) in prereqs]}


def prerequisite_unmet_error(state: dict[str, Any]) -> RpcError:
    """The §14.3 refusal: the disclosure is the message, and it names the learner's choice."""
    unit = state["_unit"]
    prereq_units = state["_prereq_units"]
    goal = " and ".join(str(row["goal"]) for row in prereq_units if str(row["goal"]).strip())
    count = len(state["unmet"])
    total = int(state["_totals"])
    noun = "objective" if total == 1 else "objectives"
    titles = "; ".join(str(item["title"]) for item in state["unmet"])
    message = (
        f"Unit {int(unit['ordinal'])} assumes you can {goal or 'the prerequisite unit'}. "
        f"{count} of {total} {noun} there have not been shown independently yet: {titles}. "
        "You can start now; the course will not count the prerequisite as met."
    )
    return RpcError.of(
        "PREREQUISITE_UNMET",
        message,
        prerequisite_state={"state": "unmet", "unmet": list(state["unmet"])},
        unit_ordinal=int(unit["ordinal"]),
        prerequisite_unit_ordinals=[
            int(row["ordinal"]) for row in prereq_units
        ],
    )


def _gated_prerequisite_state(connection, plan, objective, *, acknowledge: bool) -> dict[str, Any] | None:
    """Compute R5's state and apply R6: refuse an unacknowledged unmet edge, write nothing."""
    state = _prerequisite_state(connection, plan, objective)
    if state is None or state["state"] != "unmet":
        return state
    if not acknowledge:
        raise prerequisite_unmet_error(state)
    return {"state": "unmet_acknowledged", "unmet": list(state["unmet"])}


@_handler("check.open")
def check_open(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Open the objective's audited check, or return the one that is already open.

    A check is created only from an audited spec: a flawed or unaudited question never reaches a
    learner (``PREBUILD_SPEC.md`` §8).
    """
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "check.open"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        plan = _approved_plan(connection, enrollment["course_id"])
        if plan is None:
            raise RpcError.of(
                "VALIDATION_FAILED", "the course plan is not approved.", reason="plan_not_approved"
            )
        objective = _objective_in_plan(connection, payload["objective_id"], plan["id"])
        prerequisite_state = _gated_prerequisite_state(
            connection, plan, objective,
            acknowledge=bool(payload.get("acknowledge_prerequisites")),
        )
        existing = _row(
            connection,
            "SELECT * FROM checks WHERE objective_id = ? AND state = 'open' ORDER BY version DESC LIMIT 1",
            (objective["id"],),
        )
        if existing is not None:
            result = {
                "check_id": existing["id"],
                "check_version": int(existing["version"]),
                "evidence_target": existing["evidence_target"],
                "revision": int(enrollment["revision"]),
            }
            if prerequisite_state is not None:
                result["prerequisite_state"] = prerequisite_state
            return int(enrollment["revision"]), result
        spec = _check_spec(objective)
        if spec is None:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "this objective has no check specification; it cannot be assessed.",
                reason="objective_not_checkable",
                objective_id=objective["id"],
            )
        if not _audit_ok(spec):
            raise RpcError.of(
                "VALIDATION_FAILED",
                "this check did not pass its pre-lesson audit and cannot be used for grading.",
                reason="check_not_audited",
                audit_state=str(spec.get("audit_state") or "pending"),
            )
        stimulus, reference, rubric = _spec_content(spec)
        if not reference:
            raise RpcError.of(
                "VALIDATION_FAILED", "the check has no reference answer.", reason="objective_not_checkable"
            )
        try:
            validators.reference_kind(reference)
        except validators.ReferenceSpecError:
            # A stored reference must name its grading lane before it can reach a learner. This is
            # the write gate that makes "no kind" impossible by construction, not by convention
            # (docs/GRADING-LANES.md).
            raise RpcError.of(
                "VALIDATION_FAILED",
                "this check does not declare a grading lane and cannot be assessed.",
                reason="check_not_gradable",
                objective_id=objective["id"],
            )
        current = _row(
            connection, "SELECT MAX(version) AS version FROM checks WHERE objective_id = ?", (objective["id"],)
        )
        version = int(current["version"] or 0) + 1
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        connection.execute(
            "UPDATE checks SET state = 'superseded' WHERE objective_id = ? AND state = 'open'", (objective["id"],)
        )
        check_id = _insert_check(connection, objective, spec, stimulus, reference, rubric, version)
        _transition(connection, enrollment["id"], expected, to_revision, "continue")
        result = {
            "check_id": check_id,
            "check_version": version,
            "evidence_target": objective["evidence_target"],
            "revision": to_revision,
        }
        if prerequisite_state is not None:
            result["prerequisite_state"] = prerequisite_state
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


@_handler("progression.challenge_out")
def progression_challenge_out(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """A challenge-out check is a *different* audited item, never a replay of one already seen."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "progression.challenge_out"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        plan = _approved_plan(connection, enrollment["course_id"])
        if plan is None:
            raise RpcError.of("VALIDATION_FAILED", "the course plan is not approved.", reason="plan_not_approved")
        objective = _objective_in_plan(connection, payload["objective_id"], plan["id"])
        spec = _check_spec(objective)
        if spec is None:
            raise RpcError.of(
                "VALIDATION_FAILED", "this objective has no check specification.",
                reason="objective_not_checkable",
            )
        used = {
            row["stimulus_json"]
            for row in connection.execute(
                "SELECT stimulus_json FROM checks WHERE objective_id = ?", (objective["id"],)
            )
        }
        variant = None
        for candidate in spec.get("variants") or []:
            if not isinstance(candidate, dict):
                continue
            stimulus = candidate.get("stimulus") or {}
            if _json_dump(stimulus) in used:
                continue
            if str(candidate.get("audit_state") or "pending") != "passed":
                continue
            variant = candidate
            break
        if variant is None:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "no unused, audited variant of this check exists; a replay would not be a challenge.",
                reason="no_varied_challenge_available",
                objective_id=objective["id"],
            )
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        current = _row(
            connection, "SELECT MAX(version) AS version FROM checks WHERE objective_id = ?", (objective["id"],)
        )
        version = int(current["version"] or 0) + 1
        connection.execute(
            "UPDATE checks SET state = 'superseded' WHERE objective_id = ? AND state = 'open'", (objective["id"],)
        )
        _, reference, rubric = _spec_content(spec)
        variant_reference = variant.get("reference") or reference
        try:
            validators.reference_kind(variant_reference)
        except validators.ReferenceSpecError:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "this challenge does not declare a grading lane and cannot be assessed.",
                reason="check_not_gradable",
                objective_id=objective["id"],
            )
        check_id = _insert_check(
            connection, objective, spec, variant.get("stimulus") or {},
            variant_reference, variant.get("rubric") or rubric, version,
        )
        _transition(connection, enrollment["id"], expected, to_revision, "continue")
        result = {"check_id": check_id, "check_version": version, "revision": to_revision}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


# ── attempts: the grading gate ──────────────────────────────────────────────


def _attempt_rows_before(connection, enrollment_id: str, check_id: str) -> int:
    row = _row(
        connection,
        "SELECT COUNT(*) AS n FROM attempts WHERE enrollment_id = ? AND check_id = ? AND state = 'committed'",
        (enrollment_id, check_id),
    )
    return int(row["n"] if row else 0)


def _classify_evidence(connection, enrollment_id: str, check_id: str) -> str:
    """How this answer was produced.

    Cold is the default. A hint or a shown answer is a durable event recorded *before* the next
    answer (``AUDIT.md`` R10/R12): an answer produced after scaffolding is never independent
    evidence, and a shown answer is stronger contamination than a hint. A second answer to the
    same check also follows feedback, so it is at least ``hinted``.
    """
    objective_row = _row(
        connection, "SELECT objective_id FROM checks WHERE id = ?", (check_id,)
    )
    assist = None
    if objective_row is not None:
        assist = _row(
            connection,
            "SELECT kind FROM evidence WHERE enrollment_id = ? AND objective_id = ?"
            " AND kind IN ('answer_shown', 'hint_request') AND attempt_id IS NULL"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (enrollment_id, objective_row["objective_id"]),
        )
    if assist is not None and assist["kind"] == "answer_shown":
        return "answer_shown"
    if assist is not None or _attempt_rows_before(connection, enrollment_id, check_id):
        return "hinted"
    return "cold"



def _next_action_for(verdict: str) -> str:
    if verdict == "pass":
        return "complete_objective"
    if verdict in ("partial", "not_yet"):
        return "retry_attempt"
    if verdict == "clarification":
        return "explain"
    return "retry_grading"


def _attempt_result(row, revision: int) -> dict[str, Any]:
    verdict = row["verdict"]
    return {
        "attempt_id": row["id"],
        "verdict": verdict,
        "evidence_class": row["evidence_class"],
        "criteria": _json_load(row["criteria_json"], []),
        "next_action": _next_action_for(str(verdict)),
        "revision": int(revision),
    }


def _binding_refusal(connection, enrollment_id: str) -> None:
    """Only an ``active`` binding may accept a submit. No binding means no chat is bound yet."""
    row = _row(
        connection,
        "SELECT status FROM bindings WHERE enrollment_id = ?"
        + bindings.GOVERNING_ORDER,
        (enrollment_id,),
    )
    if row is not None and row["status"] != "active":
        raise RpcError.of(
            "BINDING_NOT_ACTIVE",
            f"the lesson session is {row['status']}; rebind before submitting.",
            status=row["status"],
        )


def _load_submit_context(connection, payload: dict[str, Any]):
    enrollment = _enrollment(connection, payload["enrollment_id"])
    check = _row(connection, "SELECT * FROM checks WHERE id = ?", (payload["check_id"],))
    if check is None:
        raise _not_found("check", payload["check_id"])
    objective = _row(connection, "SELECT * FROM objectives WHERE id = ?", (check["objective_id"],))
    plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (objective["plan_id"],))
    if plan is None or plan["course_id"] != enrollment["course_id"]:
        raise RpcError.of(
            "VALIDATION_FAILED", "that check does not belong to this enrollment's course.",
            field="check_id", reason="check_not_in_enrollment_course",
        )
    return enrollment, check, objective, plan


@_handler("attempt.submit")
def attempt_submit(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Grade one answer and commit exactly one transition.

    Order of operations is the contract:

    1. replay an idempotency key (original result, no re-grade);
    2. replay an already-seen attempt nonce (late/duplicate callback → ignored);
    3. verify binding, check version, check state, audit and revision;
    4. grade **outside** any transaction;
    5. one ``BEGIN IMMEDIATE`` transaction re-checks the revision, writes the attempt, the single
       transitions row, the evidence rows, the objective state and the idempotency key.

    A grader failure persists ``needs_retry`` and advances nothing.
    """
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "attempt.submit"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")

    with db.read() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment, check, objective, _plan = _load_submit_context(connection, payload)
        prior = _row(
            connection,
            "SELECT * FROM attempts WHERE enrollment_id = ? AND check_id = ? AND attempt_nonce = ?",
            (enrollment["id"], check["id"], payload["attempt_nonce"]),
        )
        if prior is not None:
            return int(enrollment["revision"]), _attempt_result(prior, int(enrollment["revision"]))
        # A parent-recipe course records observations through ``observation.record``, never through
        # a child-operated checklist; the confirmation lane is disabled for it.
        recipe = str(_course_of_enrollment(connection, enrollment)["recipe"] or "")
        if int(check["version"]) != int(payload["check_version"]):
            raise _check_stale(
                "the open check has been superseded; no attempt was created.",
                int(enrollment["revision"]),
                check_version=int(check["version"]),
            )
        if check["state"] != "open":
            raise _check_stale(
                "that check is closed; no attempt was created.", int(enrollment["revision"]),
                check_state=check["state"],
            )
        if check["audit_state"] != "passed":
            raise RpcError.of(
                "POLICY_VIOLATION", "this check did not pass its pre-lesson audit and cannot be graded.",
                reason="check_not_audited", audit_state=check["audit_state"],
            )
        # A source update pauses dependent generated checks pending review; grading against
        # changed content would manufacture evidence the plan no longer supports.
        source_ledger.assert_check_current(connection, str(check["id"]))
        _binding_refusal(connection, enrollment["id"])
        if int(enrollment["revision"]) != expected:
            raise _stale("the enrollment moved on before this answer was graded.", int(enrollment["revision"]))
        evidence_class = _classify_evidence(connection, enrollment["id"], check["id"])
        reference = _json_load(check["reference_json"], {})
        rubric = _json_load(check["rubric_json"], {})
        stimulus = _json_load(check["stimulus_json"], {})
        locale = check["locale"]

    attempt_id = _new_id("att")
    answer = payload["answer"]
    answer_hash = _canonical_hash(answer)
    try:
        graded = grading.grade(
            reference=reference, rubric=rubric, stimulus=stimulus, answer=answer,
            attempt_id=attempt_id, locale=locale,
            allow_confirmation=recipe != "parent",
        )
    except grading.ConfirmationAnswerError as exc:
        # A refusal, not a failed attempt: no attempt row, no evidence, no revision bump. Raised
        # before the write transaction opens.
        raise RpcError.of(
            "VALIDATION_FAILED",
            "that checklist answer is not a confirmation of declared items.",
            field="answer",
            reason=exc.reason,
        )
    except Exception as exc:  # noqa: BLE001 - a grader that cannot finish is needs_retry, never a pass
        graded = None
        failure = f"{type(exc).__name__}: {exc}"[:300]
    else:
        failure = ""

    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment, check, objective, _plan = _load_submit_context(connection, payload)
        prior = _row(
            connection,
            "SELECT * FROM attempts WHERE enrollment_id = ? AND check_id = ? AND attempt_nonce = ?",
            (enrollment["id"], check["id"], payload["attempt_nonce"]),
        )
        if prior is not None:
            return int(enrollment["revision"]), _attempt_result(prior, int(enrollment["revision"]))
        if int(enrollment["revision"]) != expected:
            raise _stale("the enrollment moved on while this answer was being graded.", int(enrollment["revision"]))
        if int(check["version"]) != int(payload["check_version"]) or check["state"] != "open":
            raise _check_stale(
                "the check changed while this answer was being graded; no attempt was created.",
                int(enrollment["revision"]), check_version=int(check["version"]),
            )
        # The pre-grade read checked this too, but a revalidation can land while the answer is
        # being graded. Re-check inside the write transaction so a cold attempt is never committed
        # against a source the user has since been told changed.
        source_ledger.assert_check_current(connection, str(check["id"]))

        if graded is None:
            connection.execute(
                "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce, answer_kind,"
                " answer_json, answer_hash, verdict, evidence_class, criteria_json, grading_provenance_json,"
                " state, created_at, committed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'needs_retry', ?, '[]', ?, 'failed', ?, NULL)",
                (attempt_id, enrollment["id"], check["id"], int(check["version"]), payload["attempt_nonce"],
                 answer["kind"], _json_dump(answer), answer_hash, evidence_class,
                 _json_dump({"grader": "unavailable", "failure": failure}), _now()),
            )
            result = {
                "attempt_id": attempt_id,
                "verdict": "needs_retry",
                "evidence_class": evidence_class,
                "criteria": [],
                "next_action": "retry_grading",
                "revision": int(enrollment["revision"]),
            }
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                      int(enrollment["revision"]), result)
            return int(enrollment["revision"]), result

        verdict = graded.verdict
        # Only the confirmation lane may name an evidence class, and only its own constant. A
        # future aux adapter cannot return ``cold`` through this channel.
        if graded.evidence_class == grading.CONFIRMATION_EVIDENCE_CLASS:
            evidence_class = graded.evidence_class
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        connection.execute(
            "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce, answer_kind,"
            " answer_json, answer_hash, verdict, evidence_class, criteria_json, grading_provenance_json,"
            " state, created_at, committed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'committed', ?, ?)",
            (attempt_id, enrollment["id"], check["id"], int(check["version"]), payload["attempt_nonce"],
             answer["kind"], _json_dump(answer), answer_hash, verdict, evidence_class,
             _json_dump(graded.criteria), _json_dump(graded.provenance), _now(), _now()),
        )
        next_action = _next_action_for(verdict)
        # A hint is consumed by the answer it contaminated: it stays linked to that attempt and
        # cannot keep marking later, independent answers as hinted (R10/R12).
        connection.execute(
            "UPDATE evidence SET attempt_id = ? WHERE enrollment_id = ? AND objective_id = ?"
            " AND kind IN ('hint_request', 'answer_shown') AND attempt_id IS NULL",
            (attempt_id, enrollment["id"], objective["id"]),
        )
        if verdict == "pass" and evidence_class != "cold":
            # Access may advance, but the record must not claim independent evidence.
            next_action = "review_objective"
        _transition(connection, enrollment["id"], expected, to_revision, next_action, attempt_id)
        connection.execute(
            "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind, evidence_class, created_at)"
            " VALUES (?, ?, ?, ?, 1, 'attempt', ?, ?)",
            (_new_id("evd"), enrollment["id"], objective["id"], attempt_id, evidence_class, _now()),
        )
        if verdict == "pass" and evidence_class == "cold":
            connection.execute(
                "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind, evidence_class, created_at)"
                " VALUES (?, ?, ?, ?, 2, ?, ?, ?)",
                (_new_id("evd"), enrollment["id"], objective["id"], attempt_id,
                 "delayed_retrieval" if objective["state"] == "review_due" else "independent_evidence",
                 evidence_class, _now()),
            )
        connection.execute(
            "UPDATE objectives SET state = ? WHERE id = ?",
            (_objective_state_after(verdict, evidence_class, objective["state"]), objective["id"]),
        )
        if verdict == "pass":
            connection.execute("UPDATE checks SET state = 'closed' WHERE id = ?", (check["id"],))
        result = {
            "attempt_id": attempt_id,
            "verdict": verdict,
            "evidence_class": evidence_class,
            "criteria": graded.criteria,
            "next_action": next_action,
            "revision": to_revision,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


def _objective_state_after(verdict: str, evidence_class: str, current: str) -> str:
    """Evidence states stay distinct: only a cold pass reaches ``independent_evidence``.

    A cold pass on an item that was scheduled for review is *delayed* evidence, not a repeat of
    the same-session result (``AUDIT.md`` R10).
    """
    if evidence_class == "override":
        return "overridden"
    if verdict == "pass":
        if evidence_class != "cold":
            return "introduced" if current == "not_started" else current
        return "delayed_evidence" if current == "review_due" else "independent_evidence"
    if verdict in ("partial", "not_yet"):
        return "needs_review"
    return current


@_handler("attempt.override")
def attempt_override(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Grant access without evidence. The attempt is recorded as ``override`` and never as a pass."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "attempt.override"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    now = _now()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        check = _row(connection, "SELECT * FROM checks WHERE id = ?", (payload["check_id"],))
        if check is None:
            raise _not_found("check", payload["check_id"])
        objective = _row(connection, "SELECT * FROM objectives WHERE id = ?", (check["objective_id"],))
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (objective["plan_id"],))
        if plan is None or plan["course_id"] != enrollment["course_id"]:
            raise RpcError.of(
                "VALIDATION_FAILED", "that check does not belong to this enrollment's course.",
                field="check_id", reason="check_not_in_enrollment_course",
            )
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        attempt_id = _new_id("att")
        connection.execute(
            "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce, answer_kind,"
            " answer_json, answer_hash, verdict, evidence_class, criteria_json, grading_provenance_json,"
            " state, created_at, committed_at)"
            " VALUES (?, ?, ?, ?, ?, 'text', ?, ?, 'not_yet', 'override', '[]', ?, 'committed', ?, ?)",
            (attempt_id, enrollment["id"], check["id"], int(check["version"]), _new_id("n"),
             _json_dump({"reason": payload["reason"]}), _canonical_hash({"reason": payload["reason"]}),
             _json_dump({"grader": "override", "reason_hash": _canonical_hash({"reason": payload["reason"]})}),
             now, now),
        )
        _transition(connection, enrollment["id"], expected, to_revision, "complete_objective", attempt_id)
        connection.execute(
            "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind, evidence_class, created_at)"
            " VALUES (?, ?, ?, ?, 1, 'override', 'override', ?)",
            (_new_id("evd"), enrollment["id"], objective["id"], attempt_id, now),
        )
        connection.execute("UPDATE objectives SET state = 'overridden' WHERE id = ?", (objective["id"],))
        connection.execute("UPDATE checks SET state = 'closed' WHERE id = ?", (check["id"],))
        result = {
            "attempt_id": attempt_id,
            "evidence_class": "override",
            "next_action": "complete_objective",
            "revision": to_revision,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


@_handler("attempt.dispute")
def attempt_dispute(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Record a dispute on the attempt's own provenance; it never rewrites the verdict.

    ``cb.db`` v1 has no disputes table, so a dispute is appended to
    ``attempts.grading_provenance_json`` (the attempt aggregate it is about). Flagged to Atlas.
    """
    db.ensure_schema()
    with db.transaction() as connection:
        attempt = _row(connection, "SELECT * FROM attempts WHERE id = ?", (payload["attempt_id"],))
        if attempt is None:
            raise _not_found("attempt", payload["attempt_id"])
        enrollment = _enrollment(connection, attempt["enrollment_id"])
        provenance = _json_load(attempt["grading_provenance_json"], {})
        if not isinstance(provenance, dict):
            provenance = {}
        disputes = provenance.get("disputes")
        if not isinstance(disputes, list):
            disputes = []
        dispute_id = _new_id("dsp")
        disputes.append({"id": dispute_id, "state": "open", "note": payload["note"], "created_at": _now()})
        provenance["disputes"] = disputes
        connection.execute(
            "UPDATE attempts SET grading_provenance_json = ? WHERE id = ?", (_json_dump(provenance), attempt["id"])
        )
        result = {"dispute_id": dispute_id, "state": "open", "revision": int(enrollment["revision"])}
    return int(enrollment["revision"]), result


# ── notebook ────────────────────────────────────────────────────────────────


@_handler("notebook.save")
def notebook_save(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    method = "notebook.save"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    now = _now()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        objective = _row(connection, "SELECT id, plan_id FROM objectives WHERE id = ?", (payload["objective_id"],))
        if objective is None:
            raise _not_found("objective", payload["objective_id"])
        plan = _row(connection, "SELECT course_id FROM plans WHERE id = ?", (objective["plan_id"],))
        if plan is None or plan["course_id"] != enrollment["course_id"]:
            raise RpcError.of(
                "VALIDATION_FAILED", "that objective does not belong to this enrollment's course.",
                field="objective_id", reason="objective_not_in_enrollment_course",
            )
        entry_id = _new_id("nbt")
        connection.execute(
            "INSERT INTO notebook_entries (id, enrollment_id, objective_id, lesson_run_id, kind, excerpt, note,"
            " tags_json, source_ref, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, enrollment["id"], objective["id"], payload.get("lesson_run_id"), payload["kind"],
             payload.get("excerpt"), payload.get("note"), _json_dump(payload.get("tags") or []),
             payload.get("source_ref"), now, now),
        )
        result = {"entry_id": entry_id, "revision": 0}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


@_handler("notebook.delete")
def notebook_delete(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    with db.transaction() as connection:
        entry = _row(connection, "SELECT * FROM notebook_entries WHERE id = ?", (payload["entry_id"],))
        if entry is None:
            raise _not_found("notebook entry", payload["entry_id"])
        enrollment = _enrollment(connection, entry["enrollment_id"])
        connection.execute("DELETE FROM notebook_entries WHERE id = ?", (entry["id"],))
        result = {"deleted": True, "revision": 0}
    return 0, result


# ── jobs ────────────────────────────────────────────────────────────────────


def _job_view(row) -> dict[str, Any]:
    progress = _json_load(row["progress_json"], {})
    if not isinstance(progress, dict):
        progress = {}
    # ``cb.jobs`` allows only these progress keys and a real error object. Anything else in the
    # JSON columns is dropped rather than smuggled into a typed field.
    artifact_ids = [str(item) for item in (progress.get("artifact_ids") or [])][:200]
    progress = {key: progress[key] for key in ("stage", "steps_done", "steps_total", "message") if key in progress}
    error = _json_load(row["error_json"], {})
    if not (isinstance(error, dict) and {"code", "category", "message", "retryable"} <= set(error)):
        error = None
    lease = None
    if row["lease_owner"] and row["lease_expires_at"]:
        lease = {"owner": str(row["lease_owner"])[:120], "expires_at": row["lease_expires_at"]}
    return {
        "job_id": row["id"],
        "kind": row["kind"],
        "state": row["state"],
        "operation_id": row["operation_id"],
        "attempt_id": row["attempt_id"] or "unassigned",
        "brief": _json_load(row["brief_json"], {}),
        "checkpoint": _json_load(row["checkpoint_json"], {}),
        "progress": progress,
        "lease": lease,
        "artifact_ids": artifact_ids,
        "error": error,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "cancel_requested_at": row["updated_at"] if row["state"] in ("cancel_requested", "cancelling") else None,
    }


@_handler("jobs.create")
def jobs_create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Create a durable queued job. Same operation id never mints a second job."""
    db.ensure_schema()
    method = "jobs.create"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        # A lessons job is preflighted against the plan it names *before* it is queued: a job whose
        # minimum cannot fit the configured ceiling would otherwise start and half-fail, which is
        # the audit's P1-6 recovery trap. The refusal spends nothing and creates no row.
        try:
            preflight = generation.preflight_lesson_brief(connection, dict(payload.get("brief") or {}))
        except generation.GenerationRejected as exc:
            raise RpcError.of("VALIDATION_FAILED", str(exc), field="brief.budget_usd") from exc
        if preflight is not None and not preflight.fits_minimum:
            raise RpcError.of(
                "POLICY_VIOLATION",
                preflight.refusal_message(),
                reason="cost_preflight_insufficient",
                **preflight.to_dict(),
            )
        result = job_service.create(
            payload["kind"],
            payload["brief"],
            operation_id=envelope.get("operation_id"),
            idempotency_key=None,
            now=datetime.now(timezone.utc),
            connection=connection,
        )
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


@_handler("jobs.get")
def jobs_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    with db.read() as connection:
        job = _row(connection, "SELECT * FROM jobs WHERE id = ?", (payload["job_id"],))
    if job is None:
        raise _not_found("job", payload["job_id"])
    return 0, {"job": _job_view(job)}


@_handler("jobs.cancel")
def jobs_cancel(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Cancellation is a state machine move, not a claim that a provider call stopped."""
    db.ensure_schema()
    with db.transaction() as connection:
        job = _row(connection, "SELECT * FROM jobs WHERE id = ?", (payload["job_id"],))
        if job is None:
            raise _not_found("job", payload["job_id"])
        state = str(job["state"])
        if state == "queued":
            target = "cancelled"
        elif state == "running":
            target = "cancel_requested"
        elif state == "interrupted_requires_retry":
            target = "cancelled"
        else:
            raise RpcError.of(
                "JOB_NOT_CANCELLABLE", f"job is {state} and cannot be cancelled.", state=state
            )
        try:
            jobs_contract.assert_transition(state, target)
        except RpcError as exc:
            raise RpcError.of("JOB_STATE_INVALID", exc.error["message"], state=state, target=target) from exc
        connection.execute(
            "UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?", (target, _now(), job["id"])
        )
        result = {"job_id": job["id"], "state": target}
    return 0, result


# ── usage ───────────────────────────────────────────────────────────────────


@_handler("usage.summary")
def usage_summary(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Report recorded usage only. A missing token count stays ``null`` — never zero-filled."""
    db.ensure_schema()
    with db.read() as connection:
        clauses: list[str] = []
        params: list[Any] = []
        if payload.get("enrollment_id"):
            clauses.append("enrollment_id = ?")
            params.append(payload["enrollment_id"])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"SELECT tokens_json, artifact_count FROM usage_events{where}", tuple(params)
        ).fetchall()
    fields = ("input", "output", "cache_read", "cache_write")
    tokens: dict[str, int | None] = {}
    unknown: set[str] = set()
    for field in fields:
        total = 0
        seen = False
        for row in rows:
            values = _json_load(row["tokens_json"], {})
            value = values.get(field) if isinstance(values, dict) else None
            if isinstance(value, int) and not isinstance(value, bool):
                total += value
                seen = True
            else:
                unknown.add(field)
        if not seen:
            unknown.add(field)
        tokens[field] = total if seen else None
    return 0, {
        "calls": len(rows),
        "tokens": tokens,
        "artifacts": sum(int(row["artifact_count"] or 0) for row in rows),
        "unknown_fields": sorted(unknown),
    }


# ── v2 reads: library, lesson page/runtime, artifact handle, jobs list ──────


def _current_plan_sql(alias: str = "pl") -> str:
    # Correlated on the plan row itself, so the fragment works wherever `pl` is in scope.
    return (
        f"{alias}.id = (SELECT id FROM plans WHERE course_id = {alias}.course_id"
        " ORDER BY (state = 'approved') DESC, version DESC LIMIT 1)"
    )


def _encode_cursor(offset: int) -> str:
    import base64

    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> int:
    import base64

    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = int(base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii"))
    except Exception as exc:  # noqa: BLE001 - a bad cursor is caller input, not a crash
        raise RpcError.of("VALIDATION_FAILED", "the cursor is not one this backend issued.", field="cursor") from exc
    if value < 0:
        raise RpcError.of("VALIDATION_FAILED", "the cursor is out of range.", field="cursor")
    return value


def _latest_binding(connection, enrollment_id: str, lesson_run_id: str | None = None) -> Any:
    if lesson_run_id:
        return _row(
            connection,
            "SELECT * FROM bindings WHERE enrollment_id = ? AND lesson_run_id = ?"
            + bindings.GOVERNING_ORDER,
            (enrollment_id, lesson_run_id),
        )
    return _row(
        connection,
        "SELECT * FROM bindings WHERE enrollment_id = ?" + bindings.GOVERNING_ORDER,
        (enrollment_id,),
    )


def _library_next_step(connection, enrollment, course) -> dict[str, str]:
    review_due = _row(
        connection,
        "SELECT COUNT(*) AS n FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
        f" WHERE pl.course_id = ? AND {_current_plan_sql()}"
        " AND o.state IN ('review_due', 'needs_review')",
        (course["id"],),
    )
    if review_due and int(review_due["n"]) > 0:
        return {"kind": "resolve_review_due", "label": f"Review {int(review_due['n'])} objective(s)"}
    run = _row(
        connection,
        "SELECT r.*, o.title AS objective_title FROM lesson_runs r"
        " JOIN objectives o ON o.id = r.objective_id"
        " WHERE r.enrollment_id = ? AND r.state IN ('active', 'paused')"
        " ORDER BY r.updated_at DESC, r.rowid DESC LIMIT 1",
        (enrollment["id"],),
    )
    if run is not None:
        binding = _latest_binding(connection, enrollment["id"], run["id"])
        if binding is not None and binding["status"] in ("detached", "branched", "orphaned"):
            return {"kind": "rebind_session", "label": f"Rebind the chat for {run['objective_title']}"}
        if binding is None or binding["status"] != "active":
            return {"kind": "resume_lesson", "label": f"Resume {run['objective_title']}"}
        return {"kind": "resume_lesson", "label": f"Continue {run['objective_title']}"}
    if _approved_plan(connection, course["id"]) is None:
        return {"kind": "review_plan", "label": "Review and approve the plan"}
    pack = _row(connection, "SELECT state FROM packs WHERE id = ?", (course["pack_id"],)) if course["pack_id"] else None
    if pack is not None and pack["state"] == "frozen":
        return {"kind": "review_pack", "label": "Review the frozen imported pack"}
    nxt = _row(
        connection,
        "SELECT title FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
        f" WHERE pl.course_id = ? AND {_current_plan_sql()}"
        " AND o.state = 'not_started' ORDER BY o.ordinal LIMIT 1",
        (course["id"],),
    )
    if nxt is None:
        return {"kind": "review_plan", "label": "All sections have evidence; review the plan"}
    return {"kind": "start_lesson", "label": f"Start {nxt['title']}"}


def _library_warning(connection, enrollment, course, pack_row) -> str | None:
    binding = _latest_binding(connection, enrollment["id"])
    if binding is not None and binding["status"] in ("detached", "branched", "orphaned"):
        return "detached_chat"
    if pack_row is not None and pack_row["state"] == "frozen":
        return "pack_frozen"
    stale = _row(connection, "SELECT 1 AS hit FROM sources WHERE course_id = ? AND support_status = 'stale' LIMIT 1",
                 (course["id"],))
    if stale is not None:
        return "stale_source"
    draft = _row(
        connection,
        "SELECT 1 AS hit FROM plans p WHERE p.course_id = ? AND p.state = 'draft'"
        " AND p.version > COALESCE((SELECT MAX(version) FROM plans WHERE course_id = ? AND state = 'approved'), 0)"
        " LIMIT 1",
        (course["id"], course["id"]),
    )
    if draft is not None:
        return "plan_update"
    return None


def _library_unit_label(
    connection, *, course_id: str, current_objective_id: str | None
) -> str | None:
    """The card's unit label for a blueprint course, or ``None`` for a legacy/pack course.

    Display only: it reads ``plan_units`` and the current objective's ``unit_id``. It never
    derives readiness and never labels a legacy plan as multi-unit — a plan with no unit rows
    keeps the learner label it already had.
    """
    plan = _approved_plan(connection, course_id)
    if plan is None:
        plan = _row(
            connection,
            "SELECT * FROM plans WHERE course_id = ? ORDER BY version DESC LIMIT 1",
            (course_id,),
        )
    if plan is None:
        return None
    try:
        unit_rows = connection.execute(
            "SELECT ordinal, title FROM plan_units WHERE plan_id = ? ORDER BY ordinal",
            (plan["id"],),
        ).fetchall()
    except Exception:  # noqa: BLE001 - schema v6 has no plan_units table
        return None
    if not unit_rows:
        return None
    current_unit = None
    if current_objective_id:
        row = connection.execute(
            "SELECT unit_id FROM objectives WHERE id = ?", (current_objective_id,)
        ).fetchone()
        current_unit = row["unit_id"] if row is not None else None
    unit = connection.execute(
        "SELECT ordinal, title FROM plan_units WHERE plan_id = ? AND id = ?",
        (plan["id"], current_unit),
    ).fetchone() if current_unit else None
    if unit is None:
        unit = unit_rows[0]
    label = f"Unit {int(unit['ordinal'])} of {len(unit_rows)} · {unit['title']}"
    return label[:300]


@_handler("library.list")
def library_list(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The library survives a restart: it is rebuilt from enrollments/courses, never from UI state."""
    db.ensure_schema()
    # Scheduler tick: due reviews become `review_due` before anything is counted or displayed, so
    # an overdue queue can never look empty. Idempotent, and it only writes contracted state.
    with db.transaction() as connection:
        for row in connection.execute("SELECT id FROM enrollments WHERE status = 'active'").fetchall():
            review.refresh_due(connection, row["id"])
    filter_name = payload.get("filter") or "all"
    limit = min(int(payload.get("limit") or 50), 100)
    offset = _decode_cursor(payload.get("cursor"))
    clauses = ["c.status != 'deleted'"]
    params: list[Any] = []
    if filter_name == "archived":
        clauses.append("(e.status = 'archived' OR c.status = 'archived')")
    else:
        clauses.append("e.status != 'archived' AND c.status != 'archived'")
        if filter_name == "in_progress":
            clauses.append("e.status IN ('active', 'paused')")
        elif filter_name == "review_due":
            clauses.append(
                "EXISTS (SELECT 1 FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
                f" WHERE pl.course_id = c.id AND {_current_plan_sql()}"
                " AND o.state IN ('review_due', 'needs_review'))"
            )
    if payload.get("recipe"):
        clauses.append("c.recipe = ?")
        params.append(payload["recipe"])
    if payload.get("query"):
        escaped = payload["query"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("(c.title LIKE ? ESCAPE '\\' OR e.learner_label LIKE ? ESCAPE '\\')")
        params.extend([f"%{escaped}%", f"%{escaped}%"])
    where = " AND ".join(clauses)
    order = {
        "title": "c.title COLLATE NOCASE ASC, e.id ASC",
        "next_step": (
            "(SELECT COUNT(*) FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
            f" WHERE pl.course_id = c.id AND {_current_plan_sql()}"
            " AND o.state IN ('review_due','needs_review')) DESC, e.updated_at DESC, e.rowid DESC"
        ),
        "recent": "e.updated_at DESC, e.rowid DESC",
    }.get(payload.get("sort") or "recent", "e.updated_at DESC, e.rowid DESC")
    with db.read() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) AS n FROM enrollments e JOIN courses c ON c.id = e.course_id WHERE {where}",
            tuple(params),
        ).fetchone()["n"]
        rows = connection.execute(
            "SELECT e.id AS enrollment_id, e.status AS enrollment_status, e.revision AS revision,"
            " e.updated_at AS updated_at, e.learner_label AS learner_label, c.id AS course_id,"
            " c.title AS title, c.recipe AS recipe, c.locale AS locale, c.status AS course_status,"
            " c.pack_id AS course_pack_id, p.pack_id AS pack_stable_id, p.version AS pack_version,"
            " p.source AS pack_source, p.state AS pack_state"
            " FROM enrollments e JOIN courses c ON c.id = e.course_id"
            " LEFT JOIN packs p ON p.id = c.pack_id"
            f" WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        items = []
        for row in rows:
            enrollment = {"id": row["enrollment_id"]}
            course = {"id": row["course_id"], "pack_id": row["course_pack_id"]}
            pack_row = {"state": row["pack_state"]} if row["pack_state"] else None
            release = None
            if row["pack_stable_id"]:
                release = (row["pack_stable_id"], row["pack_version"])
            summary = connection.execute(
                "SELECT"
                " SUM(CASE WHEN o.state IN ('independent_evidence','delayed_evidence') THEN 1 ELSE 0 END) AS independent,"
                " SUM(CASE WHEN o.state IN ('review_due','needs_review') THEN 1 ELSE 0 END) AS review_due,"
                " COUNT(*) AS total"
                " FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
                f" WHERE pl.course_id = ? AND {_current_plan_sql()}",
                (row["course_id"],),
            ).fetchone()
            current = connection.execute(
                "SELECT o.id FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
                f" WHERE pl.course_id = ? AND {_current_plan_sql()}"
                " AND o.state IN ('introduced', 'needs_review', 'review_due', 'not_started')"
                " ORDER BY o.ordinal LIMIT 1",
                (row["course_id"],),
            ).fetchone()
            current_unit_label = _library_unit_label(
                connection,
                course_id=row["course_id"],
                current_objective_id=current["id"] if current else None,
            )
            items.append({
                "enrollment_id": row["enrollment_id"],
                "course_id": row["course_id"],
                "title": row["title"],
                # The library label for a blueprint course names which unit the learner is on.
                # It reuses the existing nullable subtitle field, so no contract addition and no
                # second authority: a legacy plan keeps the learner label exactly as before.
                "subtitle": current_unit_label or row["learner_label"],
                "recipe": row["recipe"],
                "level_label": None,
                "locale": row["locale"],
                "learner_label": row["learner_label"],
                "enrollment_status": row["enrollment_status"],
                "course_status": row["course_status"],
                "provenance": {
                    "source": (row["pack_source"] or "authored"),
                    "pack_id": release[0] if release else None,
                    "pack_version": release[1] if release and re.match(r"^\d+\.\d+\.\d+", str(release[1])) else None,
                },
                "next_step": _library_next_step(connection, enrollment, course),
                "evidence_summary": {
                    "independent": int(summary["independent"] or 0),
                    "review_due": int(summary["review_due"] or 0),
                    "total_objectives": int(summary["total"] or 0),
                    "current_objective_id": current["id"] if current else None,
                },
                "warning": _library_warning(connection, enrollment, course, pack_row),
                "updated_at": row["updated_at"],
                "revision": int(row["revision"]),
            })
        courses_any = connection.execute("SELECT COUNT(*) AS n FROM courses WHERE status != 'deleted'").fetchone()["n"]
        archived_any = connection.execute(
            "SELECT COUNT(*) AS n FROM enrollments e JOIN courses c ON c.id = e.course_id"
            " WHERE e.status = 'archived' OR c.status = 'archived'"
        ).fetchone()["n"]
    empty_reason = None
    if total == 0:
        if int(courses_any) == 0:
            empty_reason = "no_courses"
        elif int(archived_any) > 0 and filter_name == "all":
            empty_reason = "all_archived"
        else:
            empty_reason = "no_matches"
    next_cursor = _encode_cursor(offset + limit) if offset + limit < int(total) else None
    return 0, {
        "items": items,
        "next_cursor": next_cursor,
        "total": int(total),
        "empty_reason": empty_reason,
        "applied_filter": filter_name,
    }


def _lesson_binding_view(row) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "binding_id": row["id"],
        "status": row["status"],
        "runtime_session_id": row["runtime_session_id"],
        "stored_session_id": row["stored_session_id"],
        "reattachable": bool(row["status"] == "active" and (row["runtime_session_id"] or row["stored_session_id"])),
        "updated_at": row["updated_at"],
    }


def _session_state(row) -> str:
    if row is None:
        return "missing"
    if row["runtime_session_id"]:
        return "live"
    if row["stored_session_id"]:
        return "stored_only"
    return "missing"


@_handler("lesson.begin")
def lesson_begin(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Start or resume a durable lesson run. Titles and recency never decide which chat resumes."""
    db.ensure_schema()
    method = "lesson.begin"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    now = _now()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        objective = _row(connection, "SELECT * FROM objectives WHERE id = ?", (payload["objective_id"],))
        if objective is None:
            raise _not_found("objective", payload["objective_id"])
        plan = _row(connection, "SELECT course_id FROM plans WHERE id = ?", (objective["plan_id"],))
        if plan is None or plan["course_id"] != enrollment["course_id"]:
            raise RpcError.of(
                "VALIDATION_FAILED", "that objective does not belong to this enrollment's course.",
                field="objective_id", reason="objective_not_in_enrollment_course",
            )
        # R5/R6: the gate lives here and on ``check.open`` because they are the two commands that
        # start learner work. An unacknowledged unmet edge refuses **before** any row is written;
        # an acknowledged one proceeds and the response records the learner's decision. The
        # acknowledgment is never evidence and never moves an objective.
        approved_plan = _approved_plan(connection, enrollment["course_id"])
        prerequisite_state = (
            _gated_prerequisite_state(
                connection, approved_plan, objective,
                acknowledge=bool(payload.get("acknowledge_prerequisites")),
            )
            if approved_plan is not None and str(approved_plan["id"]) == str(objective["plan_id"])
            else None
        )
        run = _row(
            connection,
            "SELECT * FROM lesson_runs WHERE enrollment_id = ? AND objective_id = ?"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (enrollment["id"], objective["id"]),
        )
        if payload["mode"] == "fresh" and run is not None and run["state"] in ("active", "paused"):
            connection.execute(
                "UPDATE lesson_runs SET state = 'abandoned', revision = revision + 1, updated_at = ? WHERE id = ?",
                (now, run["id"]),
            )
            run = None
        if run is not None and run["state"] in ("active", "paused"):
            binding = _latest_binding(connection, enrollment["id"], run["id"])
            connection.execute("UPDATE lesson_runs SET last_opened_at = ? WHERE id = ?", (now, run["id"]))
            if binding is not None and binding["status"] == "active":
                run_state = "resumed"
                resume = {"available": True, "reason": None}
            else:
                run_state = "needs_fresh_run"
                reason = "no_binding" if binding is None else str(binding["status"])
                if reason not in ("no_binding", "detached", "branched", "orphaned", "completed", "session_missing"):
                    reason = "no_binding"
                resume = {"available": False, "reason": reason}
            result = {
                "lesson_run_id": run["id"],
                "run_state": run_state,
                "binding": _lesson_binding_view(binding),
                "resume": resume,
                "revision": int(run["revision"]),
            }
            if prerequisite_state is not None:
                result["prerequisite_state"] = prerequisite_state
        else:
            run_id = _new_id("run")
            connection.execute(
                "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
                " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, ?, ?, ?)",
                (run_id, enrollment["id"], objective["id"], now, now, now),
            )
            # Authored media (when the plan/lesson pipeline produced it) is projected into the
            # durable page before the chat writes its own teaching segments. The text equivalent
            # is kept even when an artifact is absent, so a provider failure is visible, not silent.
            from . import media as coursebook_media

            coursebook_media.seed_authored_media(
                connection, lesson_run_id=run_id, objective_id=str(objective["id"]), now=now
            )
            result = {
                "lesson_run_id": run_id,
                "run_state": "created",
                "binding": None,
                "resume": {"available": False, "reason": "no_binding"},
                "revision": 0,
            }
        if prerequisite_state is not None:
            result["prerequisite_state"] = prerequisite_state
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                  result["revision"], result)
    return int(result["revision"]), result


def _authored_lesson_page(connection, objective) -> dict[str, Any] | None:
    """The validated authored page for this objective, if the generation pipeline wrote one.

    ``gen_lessons`` is keyed by ``(section, plan_hash, version)`` and the section names its
    objective refs, so the objective is the only join key the kernel has. A profile that has never
    run the pipeline has no ``gen_*`` tables: that is a normal course built from packs or chat
    segments, not an error, and it stays on the segment projection.
    """
    try:
        document = connection.execute(
            "SELECT plan_hash FROM gen_plan_documents WHERE plan_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (str(objective["plan_id"]),),
        ).fetchone()
        if document is None:
            return None
        section = connection.execute(
            "SELECT id FROM gen_plan_sections WHERE plan_id = ? AND plan_hash = ?"
            " AND json_extract(objective_refs_json, '$[0]') = ? ORDER BY ordinal LIMIT 1",
            (str(objective["plan_id"]), str(document["plan_hash"]), int(objective["ordinal"])),
        ).fetchone()
        if section is None:
            return None
        lesson = connection.execute(
            "SELECT page_json FROM gen_lessons WHERE section_id = ? AND plan_hash = ?"
            " AND state = 'validated' ORDER BY version DESC, rowid DESC LIMIT 1",
            (str(section["id"]), str(document["plan_hash"])),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if lesson is None:
        return None
    page = _json_load(lesson["page_json"], None)
    return page if isinstance(page, dict) and page else None


@_handler("lesson.page")
def lesson_page(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The durable textbook page. Read-only: opening a section changes no evidence."""
    db.ensure_schema()
    with db.read() as connection:
        enrollment = _enrollment(connection, payload["enrollment_id"])
        course = _course_of_enrollment(connection, enrollment)
        objective = _row(connection, "SELECT * FROM objectives WHERE id = ?", (payload["objective_id"],))
        if objective is None:
            raise _not_found("objective", payload["objective_id"])
        plan = _row(connection, "SELECT course_id FROM plans WHERE id = ?", (objective["plan_id"],))
        if plan is None or plan["course_id"] != course["id"]:
            raise RpcError.of(
                "VALIDATION_FAILED", "that objective does not belong to this enrollment's course.",
                field="objective_id", reason="objective_not_in_enrollment_course",
            )
        run = _row(
            connection,
            "SELECT * FROM lesson_runs WHERE enrollment_id = ? AND objective_id = ?"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (enrollment["id"], objective["id"]),
        )
        binding = _latest_binding(connection, enrollment["id"], run["id"]) if run else None
        segments = connection.execute(
            "SELECT * FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal LIMIT 500",
            (run["id"],),
        ).fetchall() if run else []
        sources = connection.execute(
            "SELECT * FROM sources WHERE course_id = ? ORDER BY fetched_at DESC LIMIT 200", (course["id"],)
        ).fetchall()
        artifacts = connection.execute(
            "SELECT * FROM artifacts WHERE course_id = ? ORDER BY created_at DESC LIMIT 200", (course["id"],)
        ).fetchall()
        checks = connection.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM attempts a WHERE a.check_id = c.id) AS attempt_count"
            " FROM checks c WHERE c.objective_id = ? ORDER BY c.version DESC LIMIT 100",
            (objective["id"],),
        ).fetchall()
        notebooks = connection.execute(
            "SELECT * FROM notebook_entries WHERE enrollment_id = ? AND objective_id = ?"
            " ORDER BY created_at DESC, rowid DESC LIMIT 200",
            (enrollment["id"], objective["id"]),
        ).fetchall()
        attempts = connection.execute(
            "SELECT a.* FROM attempts a JOIN checks c ON c.id = a.check_id"
            " WHERE a.enrollment_id = ? AND c.objective_id = ?"
            " ORDER BY a.created_at DESC, a.rowid DESC LIMIT 200",
            (enrollment["id"], objective["id"]),
        ).fetchall()
        # v8 read projection. The blocks are derived from the same durable rows the page already
        # returned: no column, no rewrite, and an older section gains a document on read instead
        # of needing a migration. The check attaches to one block, never to a view.
        #
        # A section authored by the lesson pipeline has a validated page in `gen_lessons`, and that
        # page carries the authored `short` beside each `deep`. Project it with
        # `document_from_page`, which publishes only shorts the author wrote. Everything else (a
        # pack/composed section, a chat-written transcript, or a page whose stored document no
        # longer validates) keeps the segment projection and therefore stays `textbook_only`.
        #
        # H-18: the projection is deliberately *not* handed the course locale. A page authored
        # after H-18 recorded its own `lang`/`direction` (generation._build_learner_page), and
        # document_from_page reads them from the page; a page authored before H-18 carries
        # neither, so handing it the course locale would invent a direction and change a stored
        # document's bytes, hash and id. Additive means the old document reads exactly as it did.
        active_check = next((row for row in checks if row["state"] == "open"), checks[0] if checks else None)
        check_id = active_check["id"] if active_check is not None else None
        document = None
        authored = _authored_lesson_page(connection, objective)
        if authored is not None:
            try:
                document = lesson_document.document_from_page(authored, check_id=check_id)
            except lesson_document.LessonDocumentError:
                # A stored page that no longer validates is refused, not repaired: the learner
                # still gets the durable segment text, and the failure is visible in the document
                # state rather than in a half-built Guided view.
                document = None
        if document is None:
            document = lesson_document.document_from_segments(
                [dict(row) for row in segments],
                section_title=objective["title"],
                objective_id=objective["id"],
                check_id=check_id,
                artifacts={
                    row["id"]: {"kind": row["kind"], "mime": row["mime"]} for row in artifacts
                },
            )
    result = {
        "enrollment_id": enrollment["id"],
        "course": {"course_id": course["id"], "title": course["title"]},
        "section": {
            "objective_id": objective["id"],
            "title": objective["title"],
            "ordinal": int(objective["ordinal"]),
            "state": objective["state"],
            "evidence_target": objective["evidence_target"],
            "last_opened_at": run["last_opened_at"] if run else None,
        },
        "runtime": {
            "lesson_run_id": run["id"],
            "binding_id": binding["id"] if binding else None,
            "binding_status": binding["status"] if binding else "detached",
            "session_state": _session_state(binding),
            "last_active_at": binding["updated_at"] if binding else None,
        } if run else None,
        "segments": [
            {
                "segment_id": row["id"],
                "ordinal": int(row["ordinal"]),
                "kind": row["kind"],
                "text": row["text"],
                "artifact_id": row["artifact_id"],
                "source_id": row["source_id"],
                "created_at": row["created_at"],
            }
            for row in segments
        ],
        "document": document,
        "sources": [
            {
                "source_id": row["id"],
                "title": row["title"],
                "url": row["url"],
                "publisher": None,
                "source_type": row["source_type"],
                "support_status": row["support_status"],
                "published_at": row["published_at"],
                "fetched_at": row["fetched_at"],
            }
            for row in sources
        ],
        "artifacts": [
            {
                "artifact_id": row["id"],
                "kind": row["kind"],
                "mime": row["mime"],
                "bytes": int(row["bytes"]),
                "content_hash": row["content_hash"],
            }
            for row in artifacts
        ],
        "checks": [
            {
                "check_id": row["id"],
                "version": int(row["version"]),
                "evidence_target": row["evidence_target"],
                "state": row["state"],
                "audit_state": row["audit_state"],
                "attempt_count": int(row["attempt_count"]),
            }
            for row in checks
        ],
        "notebook_entries": [
            {
                "entry_id": row["id"],
                "kind": row["kind"],
                "excerpt": row["excerpt"],
                "note": row["note"],
                "tags": _json_load(row["tags_json"], []),
                "source_ref": row["source_ref"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "revision": int(row["revision"]),
            }
            for row in notebooks
        ],
        "attempts": [
            {
                "attempt_id": row["id"],
                "check_id": row["check_id"],
                "check_version": int(row["check_version"]),
                "verdict": row["verdict"],
                "evidence_class": row["evidence_class"],
                "state": row["state"],
                "created_at": row["created_at"],
                "committed_at": row["committed_at"],
            }
            for row in attempts
        ],
        "state": objective["state"],
        "revision": int(enrollment["revision"]),
    }
    return int(enrollment["revision"]), result


@_handler("artifact.get")
def artifact_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Artifact metadata plus a short-lived, session-bound download handle.

    The filesystem path stays in the database: the contract forbids returning one, and the
    gateway route resolves the handle against the authenticated session (Sable's route).
    """
    db.ensure_schema()
    with db.read() as connection:
        artifact = _row(connection, "SELECT * FROM artifacts WHERE id = ?", (payload["artifact_id"],))
    if artifact is None:
        raise _not_found("artifact", payload["artifact_id"])
    provenance = _json_load(artifact["provenance_json"], {})
    if not isinstance(provenance, dict):
        provenance = {}
    mime = str(artifact["mime"] or "")
    if not re.match(r"^[a-z]+/[A-Za-z0-9.+-]+$", mime):
        mime = "application/octet-stream"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="microseconds")
    handle = f"{artifact['id']}_{int(datetime.now(timezone.utc).timestamp()) + 300}"
    source_ids = provenance.get("source_ids")
    result = {
        "artifact_id": artifact["id"],
        "course_id": artifact["course_id"],
        "kind": artifact["kind"],
        "mime": mime,
        "bytes": int(artifact["bytes"]),
        "content_hash": artifact["content_hash"],
        "provenance": {
            "generator": provenance.get("generator"),
            "model": provenance.get("model"),
            "prompt_hash": provenance.get("prompt_hash"),
            "source_ids": [str(item) for item in (source_ids or [])][:50],
            "notes": provenance.get("notes"),
        },
        "download": {
            "handle": handle,
            "url": f"/api/plugins/coursebook/artifacts/{handle}",
            "method": "GET",
            "expires_at": expires_at,
            "requires_session": True,
            "single_use": False,
        },
    }
    return 0, result


@_handler("jobs.list")
def jobs_list(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Activity/recovery list. Bounded, filterable, and honest about interrupted work."""
    db.ensure_schema()
    limit = min(int(payload.get("limit") or 50), 100)
    offset = _decode_cursor(payload.get("cursor"))
    clauses: list[str] = ["1=1"]
    params: list[Any] = []
    if payload.get("kind"):
        clauses.append(f"kind IN ({','.join('?' for _ in payload['kind'])})")
        params.extend(payload["kind"])
    if payload.get("enrollment_id"):
        clauses.append("json_extract(brief_json, '$.enrollment_id') = ?")
        params.append(payload["enrollment_id"])
    if payload.get("since"):
        clauses.append("created_at >= ?")
        params.append(payload["since"])
    base_where = " AND ".join(clauses)
    state_clause = ""
    state_params: list[Any] = []
    if payload.get("state"):
        state_clause = f" AND state IN ({','.join('?' for _ in payload['state'])})"
        state_params = list(payload["state"])
    with db.read() as connection:
        rows = connection.execute(
            f"SELECT * FROM jobs WHERE {base_where}{state_clause}"
            " ORDER BY updated_at DESC, rowid DESC LIMIT ? OFFSET ?",
            (*params, *state_params, limit, offset),
        ).fetchall()
        counts_row = connection.execute(
            "SELECT"
            " SUM(CASE WHEN state = 'queued' THEN 1 ELSE 0 END) AS queued,"
            " SUM(CASE WHEN state IN ('running','cancel_requested','cancelling') THEN 1 ELSE 0 END) AS running,"
            " SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) AS failed,"
            " SUM(CASE WHEN state = 'interrupted_requires_retry' THEN 1 ELSE 0 END) AS interrupted,"
            " COUNT(*) AS total"
            f" FROM jobs WHERE {base_where}",
            tuple(params),
        ).fetchone()
    total = int(counts_row["total"] or 0)
    return 0, {
        "jobs": [_job_view(row) for row in rows],
        "next_cursor": _encode_cursor(offset + limit) if offset + limit < total else None,
        "counts": {
            "queued": int(counts_row["queued"] or 0),
            "running": int(counts_row["running"] or 0),
            "failed": int(counts_row["failed"] or 0),
            "interrupted": int(counts_row["interrupted"] or 0),
        },
    }


# ── v2 mutations: enrollment lifecycle, notebook edit, binding abandon, deletes ──


_ENROLLMENT_ACTIONS = {"archive": "archived", "unarchive": "active", "pause": "paused", "resume": "active"}


@_handler("enrollment.update")
def enrollment_update(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "enrollment.update"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        target = _ENROLLMENT_ACTIONS[payload["action"]]
        if int(enrollment["revision"]) != expected:
            raise _stale("the enrollment moved on.", int(enrollment["revision"]))
        if enrollment["status"] == target:
            result = {"enrollment_id": enrollment["id"], "status": target, "revision": int(enrollment["revision"])}
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                      result["revision"], result)
            return result["revision"], result
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        connection.execute("UPDATE enrollments SET status = ? WHERE id = ?", (target, enrollment["id"]))
        result = {"enrollment_id": enrollment["id"], "status": target, "revision": to_revision}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


def _enrollment_scope(connection, enrollment) -> dict[str, Any]:
    enrollment_id = enrollment["id"]
    course_id = enrollment["course_id"]
    counts = {
        "attempts": int(connection.execute(
            "SELECT COUNT(*) AS n FROM attempts WHERE enrollment_id = ?", (enrollment_id,)
        ).fetchone()["n"]),
        "pronunciation_attempts": int(connection.execute(
            "SELECT COUNT(*) AS n FROM pronunciation_attempts WHERE enrollment_id = ?", (enrollment_id,)
        ).fetchone()["n"]),
        "transitions": int(connection.execute(
            "SELECT COUNT(*) AS n FROM transitions WHERE enrollment_id = ?", (enrollment_id,)
        ).fetchone()["n"]),
        "notebook_entries": int(connection.execute(
            "SELECT COUNT(*) AS n FROM notebook_entries WHERE enrollment_id = ?", (enrollment_id,)
        ).fetchone()["n"]),
        "lesson_runs": int(connection.execute(
            "SELECT COUNT(*) AS n FROM lesson_runs WHERE enrollment_id = ?", (enrollment_id,)
        ).fetchone()["n"]),
        "artifacts_owned": int(connection.execute(
            "SELECT COUNT(*) AS n FROM artifacts WHERE course_id = ?", (course_id,)
        ).fetchone()["n"]),
        "jobs": int(connection.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE json_extract(brief_json, '$.enrollment_id') = ?",
            (enrollment_id,),
        ).fetchone()["n"]),
    }
    scope_hash = _canonical_hash({"scope": "enrollment", "enrollment_id": enrollment_id, "counts": counts})
    summary = (
        f"Deletes {counts['attempts']} attempt(s), {counts['pronunciation_attempts']} pronunciation "
        f"attempt(s), {counts['transitions']} transition(s), {counts['notebook_entries']} notebook "
        f"entr(ies) and {counts['lesson_runs']} lesson run(s). "
        "Keeps the course, plan and objectives, pack provenance, shared artifacts, Hermes transcripts "
        "and already exported files."
    )
    return {
        "scope_id": enrollment_id,
        "counts": counts,
        "preserved": {
            "course": True,
            "plan_and_objectives": True,
            "pack_provenance": True,
            "shared_artifacts": True,
            "hermes_transcripts": True,
            "exported_files": True,
        },
        "scope_hash": scope_hash,
        "summary": summary,
    }


@_handler("enrollment.delete")
def enrollment_delete(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Explicit destructive scope, previewed by hash. Deleting chat never reaches this command."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "enrollment.delete"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        if int(enrollment["revision"]) != expected:
            raise _stale("the enrollment moved on; re-preview the data scope.", int(enrollment["revision"]))
        scope = _enrollment_scope(connection, enrollment)
        if payload.get("dry_run"):
            result = {"deleted": False, "data_scope": scope, "revision": int(enrollment["revision"])}
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                      result["revision"], result)
            return result["revision"], result
        if payload.get("data_scope_hash") != scope["scope_hash"]:
            error = RpcError.of(
                "DELETE_SCOPE_STALE",
                "the deletion scope changed since it was previewed; nothing was deleted.",
                current_data_scope_hash=scope["scope_hash"],
            )
            error.error["current_revision"] = int(enrollment["revision"])
            raise error
        enrollment_id = enrollment["id"]
        connection.execute(
            "DELETE FROM lesson_segments WHERE lesson_run_id IN"
            " (SELECT id FROM lesson_runs WHERE enrollment_id = ?)", (enrollment_id,)
        )
        connection.execute("DELETE FROM evidence WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM transitions WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM attempts WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM pronunciation_attempts WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM notebook_entries WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM lesson_runs WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM bindings WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM usage_events WHERE enrollment_id = ?", (enrollment_id,))
        connection.execute("DELETE FROM enrollments WHERE id = ?", (enrollment_id,))
        result = {"deleted": True, "data_scope": scope, "revision": 0}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


def _pack_scope(connection, pack_id: str) -> dict[str, Any]:
    ids = [row["id"] for row in connection.execute("SELECT id FROM packs WHERE pack_id = ?", (pack_id,))]
    if not ids:
        raise _not_found("pack", pack_id)
    placeholders = ",".join("?" for _ in ids)
    course_ids = [row["id"] for row in connection.execute(
        f"SELECT id FROM courses WHERE pack_id IN ({placeholders})", tuple(ids)
    )]
    course_placeholders = ",".join("?" for _ in course_ids) or "''"
    counts = {
        "courses": len(course_ids),
        "enrollments": int(connection.execute(
            f"SELECT COUNT(*) AS n FROM enrollments WHERE course_id IN ({course_placeholders})",
            tuple(course_ids),
        ).fetchone()["n"]) if course_ids else 0,
        "artifacts": int(connection.execute(
            f"SELECT COUNT(*) AS n FROM artifacts WHERE course_id IN ({course_placeholders})",
            tuple(course_ids),
        ).fetchone()["n"]) if course_ids else 0,
        "sources": int(connection.execute(
            f"SELECT COUNT(*) AS n FROM sources WHERE course_id IN ({course_placeholders})",
            tuple(course_ids),
        ).fetchone()["n"]) if course_ids else 0,
        "jobs": int(connection.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE json_extract(brief_json, '$.pack_id') = ?", (pack_id,)
        ).fetchone()["n"]),
    }
    scope_hash = _canonical_hash({"scope": "pack", "pack_id": pack_id, "counts": counts})
    summary = (
        f"Removes {counts['courses']} course(s) imported from this pack and freezes its content. "
        "Evidence, attempts, notebook entries, the source ledger and exported files are kept."
    )
    return {
        "scope_id": f"pack_{pack_id}"[:128],
        "pack_id": pack_id,
        "counts": counts,
        "preserved": {
            "evidence": True,
            "attempts": True,
            "notebook_entries": True,
            "source_ledger": True,
            "exported_files": True,
        },
        "scope_hash": scope_hash,
        "summary": summary,
    }


@_handler("pack.delete")
def pack_delete(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Freeze imported pack content. Evidence and attempts are never cascaded away."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "pack.delete"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        rows = connection.execute("SELECT * FROM packs WHERE pack_id = ?", (payload["pack_id"],)).fetchall()
        if not rows:
            raise _not_found("pack", payload["pack_id"])
        revision = max(int(row["revision"]) for row in rows)
        if revision != expected:
            raise _stale("the pack record moved on.", revision)
        scope = _pack_scope(connection, payload["pack_id"])
        if payload.get("dry_run"):
            result = {"deleted": False, "data_scope": scope, "revision": revision}
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
            return revision, result
        if payload.get("data_scope_hash") != scope["scope_hash"]:
            error = RpcError.of(
                "DELETE_SCOPE_STALE",
                "the deletion scope changed since it was previewed; nothing was deleted.",
                current_data_scope_hash=scope["scope_hash"],
            )
            error.error["current_revision"] = revision
            raise error
        connection.execute(
            "UPDATE packs SET state = 'frozen', revision = revision + 1 WHERE pack_id = ?", (payload["pack_id"],)
        )
        result = {"deleted": True, "data_scope": scope, "revision": revision + 1}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision + 1, result)
    return revision + 1, result


@_handler("notebook.update")
def notebook_update(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Edit note/tags under the entry's own revision fence. Provenance is immutable here."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "notebook.update"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        entry = _row(connection, "SELECT * FROM notebook_entries WHERE id = ?", (payload["entry_id"],))
        if entry is None:
            raise _not_found("notebook entry", payload["entry_id"])
        if int(entry["revision"]) != expected:
            raise _stale("the notebook entry changed; re-read before editing.", int(entry["revision"]))
        note = payload["note"] if "note" in payload else entry["note"]
        tags = payload["tags"] if "tags" in payload else _json_load(entry["tags_json"], [])
        connection.execute(
            "UPDATE notebook_entries SET note = ?, tags_json = ?, revision = revision + 1, updated_at = ?"
            " WHERE id = ?",
            (note, _json_dump(tags), _now(), entry["id"]),
        )
        revision = int(entry["revision"]) + 1
        result = {"entry_id": entry["id"], "revision": revision}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
    return revision, result


@_handler("binding.abandon")
def binding_abandon(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Detach a binding deliberately. Evidence stays; the next turn must rebind."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "binding.abandon"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        binding = _row(connection, "SELECT * FROM bindings WHERE id = ?", (payload["binding_id"],))
        if binding is None:
            raise _not_found("binding", payload["binding_id"])
        if int(binding["revision"]) != expected:
            raise _stale("the binding moved on.", int(binding["revision"]))
        revision = int(binding["revision"]) + 1
        connection.execute(
            "UPDATE bindings SET status = 'orphaned', revision = ?, updated_at = ? WHERE id = ?",
            (revision, _now(), binding["id"]),
        )
        result = {"binding_id": binding["id"], "status": "orphaned", "revision": revision}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
    return revision, result


# ── Learning loop: review queue and evidence (cb.rpc v3, CB-022) ────────────
#
# The semantics live in ``review.py`` and ``evidence.py``; these handlers are registration plus the
# response-shape mapping the freeze documented. Read paths never advance a revision; the one
# mutation (``review.action``) is fenced exactly like every other learner command.

#: ``evidence.inspect`` reuses the contract's bounded dispute view; keep the row list inside it.
MAX_INSPECT_DISPUTES = 200


@_handler("review.queue")
def review_queue(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Derived queue. The clock is the backend's and the cap bounds rows, never the counts."""
    db.ensure_schema()
    enrollment_id = payload["enrollment_id"]
    with db.read() as connection:
        enrollment = _enrollment(connection, enrollment_id)
        result = review.queue(
            connection,
            enrollment_id,
            cap=int(payload.get("cap", 10)),
            include_upcoming=bool(payload.get("include_upcoming", True)),
        )
    return int(enrollment["revision"]), result


@_handler("review.action")
def review_action(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Record a learner scheduling preference as layer-1 self-reported evidence.

    One transaction: fence, bump, write the event, then re-read the post-action truth. ``state``
    and ``due_at`` are the values the queue must re-render from; the revision stays in the
    envelope (the contract forbids a payload copy).
    """
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "review.action"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    enrollment_id = payload["enrollment_id"]
    objective_id = payload["objective_id"]
    action = payload["action"]
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, enrollment_id)
        plan = _approved_plan(connection, enrollment["course_id"])
        if plan is None:
            raise RpcError.of(
                "VALIDATION_FAILED", "the course plan is not approved.", reason="plan_not_approved"
            )
        # A scheduling action on an objective outside the approved plan would write an event no
        # queue can ever read; refuse it rather than persist orphan evidence.
        _objective_in_plan(connection, objective_id, plan["id"])
        to_revision = _bump_enrollment(connection, enrollment_id, expected)
        now = datetime.now(timezone.utc)
        outcome = review.apply_action(
            connection, enrollment_id=enrollment_id, objective_id=objective_id, action=action, now=now
        )
        state = str(_row(connection, "SELECT state FROM objectives WHERE id = ?", (objective_id,))["state"])
        item = review.item(connection, enrollment_id, objective_id, now=now)
        result = {**outcome, "state": state, "due_at": item["due_at"] if item is not None else None}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result)
    return to_revision, result


@_handler("evidence.inspect")
def evidence_inspect(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """L1 + L2 + L3 + disputes in one read, with the bounded dispute view the contract requires."""
    db.ensure_schema()
    enrollment_id = payload["enrollment_id"]
    objective_id = payload.get("objective_id")
    limit = int(payload.get("limit", 50))
    with db.read() as connection:
        enrollment = _enrollment(connection, enrollment_id)
        bundle = evidence.bundle(connection, enrollment_id, objective_id=objective_id, limit=limit)
    recorded = bundle["disputes"]
    bounded = recorded["disputes"][:MAX_INSPECT_DISPUTES]
    result = {
        **bundle,
        "disputes": {
            "enrollment_id": recorded["enrollment_id"],
            "disputes": bounded,
            "count": recorded["count"],
            "truncated": recorded["count"] > len(bounded),
        },
    }
    return int(enrollment["revision"]), result


@_handler("evidence.disputes")
def evidence_disputes(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Bounded dispute view; ``count`` is the full match count, not the returned slice."""
    db.ensure_schema()
    enrollment_id = payload["enrollment_id"]
    limit = int(payload.get("limit", 50))
    with db.read() as connection:
        enrollment = _enrollment(connection, enrollment_id)
        recorded = evidence.disputes(connection, enrollment_id, attempt_id=payload.get("attempt_id"))
    count = int(recorded["count"])
    result = {
        "enrollment_id": recorded["enrollment_id"],
        "disputes": recorded["disputes"][:limit],
        "count": count,
        "truncated": count > limit,
    }
    return int(enrollment["revision"]), result


# ── v5: outline and check stimulus (read-only views) ────────────────────────

#: The closed allowlist `check.get` may project from ``checks.stimulus_json``. Anything else the
#: importer or generator stored is dropped rather than echoed: a smuggled answer key must not
#: reach the pane through a read.
STIMULUS_FORMATS: tuple[str, ...] = ("text", "selection", "verification")
OUTLINE_OBJECTIVE_LIMIT = 400
STIMULUS_PROMPT_LIMIT = 8000
STIMULUS_ITEM_LIMIT = 24
STIMULUS_ITEM_ID_LIMIT = 64
STIMULUS_ITEM_LABEL_LIMIT = 200
STIMULUS_ITEM_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")


def _check_label_key(value: str) -> str:
    """Normalise a check label for comparison: case, spacing and punctuation are ignored.

    The Desktop renderer applies the same rule before dropping a prose line whose only content is
    a check item's label, so the reject-on-read rule and the print-once rule cannot disagree.
    """
    cleaned = "".join(
        " " if unicodedata.category(character)[0] in {"P", "S"} else character
        for character in value.lower()
    )
    return " ".join(cleaned.split())


def _stimulus_items(stored: dict[str, Any]) -> list[dict[str, str]]:
    """Project a stored checklist onto ``items[]``, refusing a label the learner would read twice.

    The stimulus is the learner-facing form of the check. Two items whose labels read the same
    (case, spacing or punctuation aside) are not two verification steps, and an item list that
    repeats itself is a broken check: it is refused on read rather than rendered twice.
    """
    raw = stored.get("items")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RpcError.of(
            "VALIDATION_FAILED", "the check's items must be a list.", field="items",
            reason="stimulus_items_not_a_list",
        )
    if len(raw) > STIMULUS_ITEM_LIMIT:
        raise RpcError.of(
            "VALIDATION_FAILED", f"a check may carry at most {STIMULUS_ITEM_LIMIT} items.",
            field="items", reason="too_many_check_items",
        )
    items: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for index, item in enumerate(raw):
        field = f"items[{index}]"
        if not isinstance(item, dict):
            raise RpcError.of(
                "VALIDATION_FAILED", "each check item must be an object with an id and a label.",
                field=field, reason="stimulus_item_not_an_object",
            )
        item_id = item.get("id")
        label = item.get("label")
        if (
            not isinstance(item_id, str)
            or len(item_id) > STIMULUS_ITEM_ID_LIMIT
            or not STIMULUS_ITEM_ID_RE.match(item_id)
        ):
            raise RpcError.of(
                "VALIDATION_FAILED", "a check item needs an id of letters, digits, dot, colon, dash or underscore.",
                field=f"{field}.id", reason="invalid_check_item_id",
            )
        if not isinstance(label, str) or not label.strip():
            raise RpcError.of(
                "VALIDATION_FAILED", "a check item needs a non-empty label.",
                field=f"{field}.label", reason="check_item_missing_label",
            )
        if len(label) > STIMULUS_ITEM_LABEL_LIMIT:
            raise RpcError.of(
                "VALIDATION_FAILED",
                f"a check item label may be at most {STIMULUS_ITEM_LABEL_LIMIT} characters.",
                field=f"{field}.label", reason="check_item_label_too_long",
            )
        if item_id in seen_ids:
            raise RpcError.of(
                "VALIDATION_FAILED", "two checklist items carry the same id.",
                field=f"{field}.id", reason="duplicate_check_item_id",
            )
        key = _check_label_key(label)
        if key in seen_labels:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "two checklist items carry the same label once case, spacing and punctuation are ignored.",
                field=f"{field}.label", reason="duplicate_check_item_label",
            )
        seen_ids.add(item_id)
        seen_labels.add(key)
        items.append({"id": item_id, "label": label})
    return items


def _stimulus_view(stored: Any) -> dict[str, Any]:
    """Project a stored stimulus onto the contracted keys (+ optional instructions and items).

    The allowlist is still closed: an unrecognised stored key is dropped rather than echoed,
    because a smuggled answer key must never reach the pane through a read. ``items[]`` is the one
    addition: it is structured check data, not prose, and it is validated on the way out.
    """
    if not isinstance(stored, dict):
        raise RpcError.of(
            "VALIDATION_FAILED", "the stored check has no stimulus.", reason="stimulus_missing_prompt"
        )
    prompt = stored.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RpcError.of(
            "VALIDATION_FAILED",
            "the stored check has no stimulus prompt.",
            reason="stimulus_missing_prompt",
        )
    declared_format = stored.get("format")
    choices = stored.get("choices")
    instructions = stored.get("learner_instructions")
    items = _stimulus_items(stored)
    if (
        isinstance(instructions, str)
        and _check_label_key(instructions)
        and _check_label_key(instructions) == _check_label_key(prompt)
    ):
        raise RpcError.of(
            "VALIDATION_FAILED",
            "the learner instructions only repeat the prompt; the check would ask the same thing twice.",
            field="learner_instructions",
            reason="instructions_repeat_prompt",
        )
    return {
        "prompt": prompt[:STIMULUS_PROMPT_LIMIT],
        # An imported pack check declares no format; an open answer is the honest reading.
        "format": declared_format if declared_format in STIMULUS_FORMATS else "text",
        "choices": [str(choice)[:200] for choice in (choices if isinstance(choices, list) else [])][:8],
        "learner_instructions": str(instructions)[:400] if isinstance(instructions, str) else None,
        "items": items,
    }


@_handler("course.outline")
def course_outline(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The Textbook section index and the Plan tab: one read, every field derived, revision 0.

    The plan rule is ``library.list``'s: approved first, else the highest version, which is the
    draft the Plan tab asks the learner to approve. No revision bump and no transitions row —
    opening the outline cannot change evidence.
    """
    db.ensure_schema()
    enrollment_id = payload["enrollment_id"]
    limit = int(payload.get("limit", OUTLINE_OBJECTIVE_LIMIT))
    with db.read() as connection:
        enrollment = _enrollment(connection, enrollment_id)
        plan = _approved_plan(connection, enrollment["course_id"])
        if plan is None:
            plan = _row(
                connection,
                "SELECT * FROM plans WHERE course_id = ? ORDER BY version DESC LIMIT 1",
                (enrollment["course_id"],),
            )
        if plan is None:
            return 0, {
                "enrollment_id": enrollment_id,
                "plan": None,
                "objectives": [],
                "total": 0,
                "truncated": False,
            }
        total = int(
            _row(connection, "SELECT COUNT(*) AS n FROM objectives WHERE plan_id = ?", (plan["id"],))["n"]
        )
        course_row = _row(
            connection, "SELECT title FROM courses WHERE id = ?", (enrollment["course_id"],)
        )
        rows = connection.execute(
            "SELECT o.*,"
            " (SELECT c.state FROM checks c WHERE c.objective_id = o.id"
            "   ORDER BY c.version DESC LIMIT 1) AS check_state,"
            " (SELECT COUNT(*) FROM attempts a JOIN checks c ON c.id = a.check_id"
            "   WHERE c.objective_id = o.id AND a.enrollment_id = ? AND a.state = 'committed')"
            "   AS attempt_count,"
            " (SELECT MAX(r.last_opened_at) FROM lesson_runs r"
            "   WHERE r.objective_id = o.id AND r.enrollment_id = ?) AS last_opened_at"
            " FROM objectives o WHERE o.plan_id = ? ORDER BY o.ordinal LIMIT ?",
            (enrollment_id, enrollment_id, plan["id"], limit),
        ).fetchall()
    objectives = [
        {
            "objective_id": row["id"],
            "ordinal": int(row["ordinal"]),
            "title": row["title"],
            "evidence_target": row["evidence_target"],
            "state": row["state"],
            "check_state": row["check_state"] or "none",
            "attempt_count": int(row["attempt_count"]),
            # A view of the state, not a second claim: independence is what the row says.
            "independent": row["state"] in ("independent_evidence", "delayed_evidence"),
            "last_opened_at": row["last_opened_at"],
        }
        for row in rows
    ]
    with db.read() as connection:
        units = _outline_units(
            connection,
            plan=plan,
            enrollment_id=enrollment_id,
            objectives=objectives,
            course_title=course_row["title"] if course_row is not None else None,
        )
    return 0, {
        "enrollment_id": enrollment_id,
        "plan": {
            "plan_id": plan["id"],
            "version": int(plan["version"]),
            "state": plan["state"],
            "plan_hash": plan["plan_hash"],
            # Additive in cb.rpc v11 (§14.2 R9). A legacy plan projects exactly one implicit
            # unit titled with the plan title, so every client can rely on the array.
            "units": units,
        },
        "objectives": objectives,
        "total": total,
        "truncated": total > len(objectives),
    }


def _outline_units(
    connection,
    *,
    plan,
    enrollment_id: str,
    objectives: list[dict[str, Any]],
    course_title: str | None,
) -> list[dict[str, Any]]:
    """R9's unit projection, built from ``plan_units`` or from the implicit legacy unit.

    The kernel stores ``unit_id`` on objectives and ``plan_units`` rows on the plan. A plan with
    no unit rows is one unit whose title is the plan title (§10): no backfill, no rewritten row.
    """
    by_ordinal = {int(item["ordinal"]): item for item in objectives}
    # A stored document that carries a cycle (imported, hand-edited or a future forward-ref
    # extension) is refused here with ``prerequisite_cycle``; the writer's backwards rule is not
    # a property of a reader (R2).
    unit_rows = _validated_unit_rows(connection, plan["id"])
    if not unit_rows:
        return [
            {
                "ordinal": 1,
                "title": course_title or "Course",
                "goal": "",
                "prereq_unit_ordinals": [],
                "prerequisite_state": "no_edges",
                "unmet": [],
                "objectives": list(objectives),
            }
        ]
    unit_by_id = {str(row["id"]): int(row["ordinal"]) for row in unit_rows}
    state_by_ordinal: dict[int, dict[str, Any]] = {}
    membership: dict[int, int | None] = {}
    for row in connection.execute(
        "SELECT id, ordinal, title, state, unit_id FROM objectives WHERE plan_id = ? ORDER BY ordinal",
        (plan["id"],),
    ).fetchall():
        state_by_ordinal[int(row["ordinal"])] = dict(row)
        membership[int(row["ordinal"])] = unit_by_id.get(str(row["unit_id"]))
    units: list[dict[str, Any]] = []
    for row in unit_rows:
        ordinal = int(row["ordinal"])
        unit_objectives = [
            by_ordinal[objective_ordinal]
            for objective_ordinal, unit_ordinal in sorted(membership.items())
            if unit_ordinal == ordinal and objective_ordinal in by_ordinal
        ]
        prereqs = [
            int(value) for value in json.loads(row["prereq_unit_ordinals_json"] or "[]")
        ]
        unmet: list[dict[str, Any]] = []
        if not prereqs:
            prerequisite_state = "no_edges"
        else:
            for prereq in prereqs:
                for objective_ordinal, unit_ordinal in sorted(membership.items()):
                    if unit_ordinal != prereq:
                        continue
                    objective_row = state_by_ordinal.get(objective_ordinal)
                    if objective_row is None:
                        continue
                    if objective_row["state"] not in (
                        "independent_evidence",
                        "delayed_evidence",
                        "overridden",
                    ):
                        unmet.append(
                            {
                                "objective_id": objective_row["id"],
                                "ordinal": objective_ordinal,
                                "title": objective_row["title"],
                                "state": objective_row["state"],
                            }
                        )
            prerequisite_state = "unmet" if unmet else "satisfied"
        units.append(
            {
                "ordinal": ordinal,
                "title": row["title"],
                "goal": row["goal"],
                "prereq_unit_ordinals": prereqs,
                "prerequisite_state": prerequisite_state,
                "unmet": unmet,
                "objectives": unit_objectives,
            }
        )
    return units


@_handler("check.get")
def check_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The question, never the key: resolve, authorise, then project the closed allowlist.

    Membership mirrors ``check.open`` / ``attempt.submit``: the approved plan must exist for the
    enrollment's course and the check must belong to that course. Read-only, revision 0.
    """
    db.ensure_schema()
    enrollment_id = payload["enrollment_id"]
    with db.read() as connection:
        enrollment = _enrollment(connection, enrollment_id)
        plan = _approved_plan(connection, enrollment["course_id"])
        if plan is None:
            raise RpcError.of(
                "VALIDATION_FAILED", "the course plan is not approved.", reason="plan_not_approved"
            )
        if payload.get("check_id") is not None:
            check = _row(connection, "SELECT * FROM checks WHERE id = ?", (payload["check_id"],))
            if check is None:
                raise _not_found("check", payload["check_id"])
            objective = _row(
                connection, "SELECT * FROM objectives WHERE id = ?", (check["objective_id"],)
            )
            if objective is None:
                raise _not_found("objective", check["objective_id"])
            owner = _row(
                connection, "SELECT course_id FROM plans WHERE id = ?", (objective["plan_id"],)
            )
            if owner is None or owner["course_id"] != enrollment["course_id"]:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    "that check does not belong to this enrollment's course.",
                    field="check_id",
                    reason="check_not_in_enrollment_course",
                )
        else:
            objective = _objective_in_plan(connection, payload["objective_id"], plan["id"])
            check = _row(
                connection,
                "SELECT * FROM checks WHERE objective_id = ? ORDER BY (state = 'open') DESC,"
                " version DESC LIMIT 1",
                (objective["id"],),
            )
            if check is None:
                raise RpcError.of("NOT_FOUND", "that objective has no check.", entity="check")
        attempt_count = int(
            _row(
                connection,
                "SELECT COUNT(*) AS n FROM attempts WHERE enrollment_id = ? AND check_id = ?"
                " AND state = 'committed'",
                (enrollment_id, check["id"]),
            )["n"]
        )
    return 0, {
        "check_id": check["id"],
        "objective_id": objective["id"],
        "check_version": int(check["version"]),
        "evidence_target": check["evidence_target"],
        "state": check["state"],
        "audit_state": check["audit_state"],
        "stimulus": _stimulus_view(_json_load(check["stimulus_json"], {})),
        "attempt_count": attempt_count,
    }


@_handler("lesson.assist")
def lesson_assist(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Pane Hint / Show answer: the same layer-1 event the chat hook writes, revision-fenced.

    The bump is not ceremony. ``attempt.submit`` classifies evidence inside its read transaction
    and grades outside any transaction, so a hint recorded mid-grade would be invisible to that
    classification and the answer would commit ``cold``. Bumping makes the in-flight submit lose
    the fence. No transitions row: an assist is an action, not a learner transition.
    """
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "lesson.assist"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    enrollment_id = payload["enrollment_id"]
    objective_id = payload["objective_id"]
    kind = payload["kind"]
    evidence_class = evidence.ASSIST_CLASSES[kind]
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, enrollment_id)
        plan = _approved_plan(connection, enrollment["course_id"])
        if plan is None:
            raise RpcError.of(
                "VALIDATION_FAILED", "the course plan is not approved.", reason="plan_not_approved"
            )
        _objective_in_plan(connection, objective_id, plan["id"])
        open_check = _row(
            connection,
            "SELECT id FROM checks WHERE objective_id = ? AND state = 'open'"
            " ORDER BY version DESC LIMIT 1",
            (objective_id,),
        )
        if open_check is None:
            raise RpcError.of(
                "VALIDATION_FAILED", "there is no open check to assist.", reason="no_open_check"
            )
        _binding_refusal(connection, enrollment["id"])
        to_revision = _bump_enrollment(connection, enrollment_id, expected)
        event_id = evidence.record_assist(
            connection,
            enrollment_id=enrollment["id"],
            objective_id=objective_id,
            attempt_id=None,
            kind=kind,
            evidence_class=evidence_class,
        )
        result = {
            "event_id": event_id,
            "kind": kind,
            "evidence_class": evidence_class,
            "revision": to_revision,
        }
        _remember(
            connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result
        )
    return to_revision, result


# ── write paths used by the plan job and by Parent mode ─────────────────────


def plan_hash(plan_id: str) -> str:
    """Hash of a plan's current content, for an approval flow that shows the hash it binds."""
    db.ensure_schema()
    with db.read() as connection:
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (plan_id,))
        if plan is None:
            raise _not_found("plan", plan_id)
        return _plan_hash(connection, plan)


def _insert_objective(connection, plan_id: str, *, title: str, evidence_target: str,
                      criteria: list[dict[str, Any]], ordinal: int | None = None) -> str:
    """Insert one drafted objective on the caller's connection.

    Shared by :func:`record_objective` (own transaction) and ``parent.plan.edit`` (one fenced
    transaction for the whole edit): two row-insertion paths would let ordinals or hashes drift.
    """
    plan = _row(connection, "SELECT id, state FROM plans WHERE id = ?", (plan_id,))
    if plan is None:
        raise _not_found("plan", plan_id)
    if plan["state"] != "draft":
        raise RpcError.of(
            "POLICY_VIOLATION", "objectives can only be authored on a draft plan.", plan_id=plan_id
        )
    if ordinal is None:
        row = _row(connection, "SELECT COALESCE(MAX(ordinal), 0) AS ordinal FROM objectives WHERE plan_id = ?",
                   (plan_id,))
        ordinal = int(row["ordinal"]) + 1
    objective_id = _new_id("obj")
    connection.execute(
        "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target, evidence_criteria_json,"
        " state, version, created_at) VALUES (?, ?, ?, ?, ?, ?, 'not_started', 1, ?)",
        (objective_id, plan_id, ordinal, title, evidence_target, _json_dump(criteria), _now()),
    )
    # Direct authoring changes the plan, so any recorded validation pass no longer describes this
    # content. The authoring act is the explicit manual decision, and approval will report manual
    # provenance rather than claiming the old pass.
    generation.invalidate_plan_validation(
        connection, plan_id, reason="objective_authored", manual_authoring=True
    )
    return objective_id


def record_objective(plan_id: str, *, title: str, evidence_target: str, criteria: list[dict[str, Any]],
                     ordinal: int | None = None) -> str:
    """Write one planned objective (draft plans only).

    The plan job (``jobs.kind = 'plan'``) and Parent Studio call this instead of inserting rows
    themselves, so the hash and the ordinal sequence stay consistent. Draft edits have no approval
    to invalidate yet (``PREBUILD_SPEC.md`` §10).
    """
    db.ensure_schema()
    with db.transaction() as connection:
        return _insert_objective(connection, plan_id, title=title, evidence_target=evidence_target,
                                 criteria=criteria, ordinal=ordinal)


#: Evidence classes a non-attempt observation may carry. A model or a learner cannot self-assert
#: independent evidence (``AUDIT.md`` R10/R12).
_OBSERVATION_CLASSES = ("self_reported", "parent_reported")

#: The kernel-side bound on ``evidence.note``. ``cb.rpc`` v14 declares the same 1000-character cap on
#: the wire, but the bound is enforced here too: a handler is not the only caller of
#: :func:`record_observation`, and the column itself has no CHECK to lean on. An over-long note is
#: **refused**, never truncated — a silently shortened note would be prose the author did not write.
OBSERVATION_NOTE_LIMIT = 1000


def _record_observation(connection, enrollment_id: str, objective_id: str, *, evidence_class: str,
                        kind: str = "observation", note: str | None = None) -> str:
    """Validate and insert one layer-1 observation row on the caller's connection.

    Shared by :func:`record_observation` (own transaction) and ``observation.record`` (one fenced
    transaction that also remembers the idempotency key): two insertion paths would let one of them
    drop the note again, or write a row the other's policy would refuse.
    """
    if evidence_class not in _OBSERVATION_CLASSES:
        raise RpcError.of(
            "POLICY_VIOLATION",
            "only self_reported or parent_reported observations can be recorded here.",
            evidence_class=evidence_class,
        )
    if note is not None:
        if not isinstance(note, str):
            raise RpcError.of(
                "VALIDATION_FAILED", "a note must be text or null.", field="note", reason="note_not_text",
            )
        if len(note) > OBSERVATION_NOTE_LIMIT:
            raise RpcError.of(
                "VALIDATION_FAILED",
                f"a note may not be longer than {OBSERVATION_NOTE_LIMIT} characters.",
                field="note",
                reason="note_too_long",
                max_length=OBSERVATION_NOTE_LIMIT,
                length=len(note),
            )
    enrollment = _enrollment(connection, enrollment_id)
    objective = _row(connection, "SELECT id, plan_id FROM objectives WHERE id = ?", (objective_id,))
    if objective is None:
        raise _not_found("objective", objective_id)
    plan = _row(connection, "SELECT course_id FROM plans WHERE id = ?", (objective["plan_id"],))
    if plan is None or plan["course_id"] != enrollment["course_id"]:
        raise RpcError.of(
            "VALIDATION_FAILED", "that objective does not belong to this enrollment's course.",
            field="objective_id", reason="objective_not_in_enrollment_course",
        )
    evidence_id = _new_id("evd")
    connection.execute(
        "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind, evidence_class,"
        " note, created_at) VALUES (?, ?, ?, NULL, 1, ?, ?, ?, ?)",
        (evidence_id, enrollment["id"], objective["id"], kind, evidence_class, note, _now()),
    )
    return evidence_id


def record_observation(enrollment_id: str, objective_id: str, *, evidence_class: str,
                       kind: str = "observation", note: str | None = None) -> str:
    """Record a self/parent-reported observation. Layer 1 only — never independent evidence.

    ``note`` is the author's prose about the observation and is stored verbatim in
    ``evidence.note`` (``cb.db`` v9). It never changes the row's layer, class or ``attempt_id``.
    """
    db.ensure_schema()
    with db.transaction() as connection:
        return _record_observation(connection, enrollment_id, objective_id,
                                   evidence_class=evidence_class, kind=kind, note=note)


@_handler("observation.record")
def observation_record(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Append one layer-1 observation: the one client-reachable way to write evidence.

    The fence here is the **idempotency key**, not a revision. Recording an observation writes no
    attempt, no transition, no objective state and no verdict, and bumps nothing, so
    ``cb.rpc`` v14 declares no ``expected_revision`` for this method; the response ``revision`` is
    the enrollment revision read inside this transaction and echoed unchanged. A client that sends
    ``expected_revision`` anyway is describing a contract that does not exist, and this handler
    neither requires it nor checks it.

    There is no second insertion path: the row is written by ``_record_observation``, the same
    function :func:`record_observation` calls.
    """
    db.ensure_schema()
    method = "observation.record"
    key = envelope.get("idempotency_key")
    payload_hash = _payload_hash(method, payload)
    enrollment_id = payload["enrollment_id"]
    evidence_class = payload["evidence_class"]
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        evidence_id = _record_observation(
            connection,
            enrollment_id,
            payload["objective_id"],
            evidence_class=evidence_class,
            note=payload.get("note"),
        )
        enrollment = _enrollment(connection, enrollment_id)
        revision = int(enrollment["revision"])
        result = {
            "evidence_id": evidence_id,
            "evidence_class": evidence_class,
            "revision": revision,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
    return revision, result


# ── Parent Studio: authored courses (cb.rpc v6, CB-011) ─────────────────────
#
# The parent authoring surface is one aggregate: a course, its enrollment, the plan job that
# authors the plan, the final approval that binds an exact content set, and the export that
# refuses anything the approval does not cover. The hashes are computed by
# :mod:`coursebook.parent_authoring` so the three commands that read them cannot disagree.

#: The typed brief keys of ``cb.rpc#/$defs/parent_brief``. Internal routing keys
#: (``course_id``, ``enrollment_id``, ``plan_id``, ``stage``, ``recipe``, ``dials``) are stored in
#: the same JSON row but never returned as part of the typed brief.
BRIEF_KEYS: tuple[str, ...] = (
    "title", "goal", "starting_point", "age_band", "reading_level", "duration_minutes",
    "setting", "materials", "exclusions", "supervision", "desired_pages", "desired_visuals",
    "narration", "locale", "egress_acknowledged", "redaction_requested",
)

#: Bounded generated-content probes for objective removal. An objective with any of these rows is
#: in use by generated content or learning state and cannot be deleted from a plan.
_OBJECTIVE_USE_TABLES: tuple[str, ...] = (
    "checks", "evidence", "lesson_runs", "notebook_entries",
)


def _parent_brief_view(brief: dict[str, Any]) -> dict[str, Any]:
    return {key: brief[key] for key in BRIEF_KEYS if key in brief}


def _course_row(connection, course_id: str) -> Any:
    course = _row(connection, "SELECT * FROM courses WHERE id = ?", (course_id,))
    if course is None or course["status"] == "deleted":
        raise _not_found("course", course_id)
    return course


def _parent_approval(connection, course_id: str) -> Any:
    return _row(
        connection,
        "SELECT * FROM final_approvals WHERE course_id = ?"
        " ORDER BY (state = 'active') DESC, approved_at DESC LIMIT 1",
        (course_id,),
    )


def _supersede_active_approval(connection, course_id: str, reason: str) -> None:
    """Mark the active approval stale. Rows are superseded, never deleted (v6 invariant)."""
    connection.execute(
        "UPDATE final_approvals SET state = 'superseded', invalidation_reason = ?, superseded_at = ?"
        " WHERE course_id = ? AND state = 'active'",
        (reason, _now(), course_id),
    )


def _derived_content(connection, course, plan: Any) -> tuple[list[dict[str, Any]], str]:
    """Compose the current authored content and its hash. Empty plan → empty content."""
    if plan is None:
        return [], authoring.content_hash(str(course["id"]), "", "", [])
    composed = authoring.sections(connection, course, plan)
    current_hash = _plan_hash(connection, plan)
    return composed, authoring.content_hash(str(course["id"]), str(plan["id"]), current_hash, composed)


def _approval_view(row: Any) -> dict[str, Any]:
    if row is None:
        return {
            "state": "none",
            "plan_hash": None,
            "content_hash": None,
            "approved_at": None,
            "invalidated_reason": None,
        }
    return {
        "state": str(row["state"]),
        "plan_hash": row["plan_hash"],
        "content_hash": row["content_hash"],
        "approved_at": row["approved_at"],
        "invalidated_reason": row["invalidation_reason"],
    }


def _export_status(plan: Any, composed: Sequence[dict[str, Any]], approval: Any, content_hash: str,
                   *, has_content: bool | None = None) -> dict[str, Any]:
    """Derive `parent_export_status`. Ready means every blocker is absent; one reason otherwise."""
    if plan is None or str(plan["state"]) != "approved":
        return {"ready": False, "blocked_reason": "plan_not_approved"}
    content_ready = authoring.ready_sections(composed) if has_content is None else has_content
    if not content_ready:
        return {"ready": False, "blocked_reason": "no_generated_content"}
    if approval is None or str(approval["state"]) != "active":
        return {"ready": False, "blocked_reason": "no_final_approval"}
    if str(approval["content_hash"]) != str(content_hash):
        return {"ready": False, "blocked_reason": "changes_need_review"}
    return {"ready": True, "blocked_reason": None}


def _blueprint_sources(connection, course_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT id, title, url, support_status, fetched_at FROM sources"
        " WHERE course_id = ? ORDER BY created_at LIMIT 200",
        (course_id,),
    ).fetchall()
    return [
        {
            "source_id": str(row["id"]),
            "title": str(row["title"])[:500] or "Source",
            "url": row["url"],
            "support_status": str(row["support_status"]),
            "fetched_at": row["fetched_at"],
        }
        for row in rows
    ]


def _pack_backed_blueprint(course) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], str]:
    """Tabs for an imported pack course: its declared text files, grouped by role.

    No path crosses the wire; the text is read from the already-validated library directory. The
    content hash binds the pack's own manifest hash plus the course, because an imported pack's
    bytes — not generated staging — are what the parent would approve.
    """
    from . import pack_flow

    pack_row = None
    with db.read() as connection:
        pack_row = _row(connection, "SELECT * FROM packs WHERE id = ?", (course["pack_id"],))
    if pack_row is None:
        raise _not_found("pack", str(course["pack_id"]))
    manifest, files = pack_flow.library().read(str(pack_row["pack_id"]), str(pack_row["version"]))
    tabs: dict[str, list[dict[str, Any]]] = {
        "parent_guide": [], "learner_pages": [], "answers": [], "narration": [],
    }
    role_tab = {
        "parent_guide": "parent_guide",
        "learner_page": "learner_pages",
        "answer_guide": "answers",
        "narration": "narration",
    }
    for record in manifest.get("files") or []:
        role = str(record.get("role"))
        tab = role_tab.get(role)
        if tab is None:
            continue
        path = str(record.get("path"))
        data = files.get(path)
        if data is None:
            continue
        mime = str(record.get("mime"))
        if mime.startswith("text/"):
            text = data.decode("utf-8", "replace")
        elif record.get("text_equivalent"):
            text = str(record["text_equivalent"])
        else:
            continue
        tabs[tab].append(
            authoring.blueprint_file(role, path, text, None, limit=authoring.MAX_BLUEPRINT_CHARS)
        )
    sources = []
    for source in manifest.get("sources") or []:
        sources.append(
            {
                "source_id": str(source["source_id"]),
                "title": str(source["title"])[:500],
                "url": source.get("url"),
                "publisher": source.get("publisher"),
                "support_status": str(source.get("support_status") or "unassessed"),
                "fetched_at": source.get("fetched_at") or "1970-01-01T00:00:00Z",
            }
        )
    current_hash = authoring.content_hash(str(course["id"]), "", str(manifest["content_hash"]), [])
    return tabs, sources[:200], current_hash


@_handler("parent.brief.create")
def parent_brief_create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Create the course, its enrollment and the queued ``plan`` job in one fenced call."""
    db.ensure_schema()
    method = "parent.brief.create"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    if not key:
        raise RpcError.of("VALIDATION_FAILED", "parent.brief.create requires an idempotency_key.",
                          field="idempotency_key")
    brief = dict(payload["brief"])
    if not brief.get("egress_acknowledged"):
        raise RpcError.of(
            "VALIDATION_FAILED",
            "the provider/egress disclosure must be acknowledged before a course is created.",
            field="egress_acknowledged",
        )
    now = _now()
    course_id = _new_id("crs")
    enrollment_id = _new_id("enr")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        connection.execute(
            "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status, pack_id, revision,"
            " created_at, updated_at) VALUES (?, ?, 'parent', ?, ?, '{}', 'draft', NULL, 0, ?, ?)",
            (course_id, brief["title"], brief["goal"], brief.get("locale"), now, now),
        )
        connection.execute(
            "INSERT INTO enrollments (id, course_id, learner_label, status, revision, created_at, updated_at)"
            " VALUES (?, ?, NULL, 'active', 0, ?, ?)",
            (enrollment_id, course_id, now, now),
        )
        stored_brief = {
            **brief,
            "recipe": "parent",
            "dials": {},
            "course_id": course_id,
            "enrollment_id": enrollment_id,
            "stage": "plan",
        }
        job = job_service.create(
            "plan",
            stored_brief,
            operation_id=envelope.get("operation_id"),
            idempotency_key=None,
            now=datetime.now(timezone.utc),
            connection=connection,
        )
        result = {
            "course_id": course_id,
            "enrollment_id": enrollment_id,
            "job_id": str(job["job_id"]),
            "state": str(job.get("state") or "queued"),
            "revision": 0,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


@_handler("parent.brief.get")
def parent_brief_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The typed brief, read back from the job row that the executor will consume."""
    db.ensure_schema()
    with db.read() as connection:
        course = _course_row(connection, payload["course_id"])
        job = _row(
            connection,
            "SELECT * FROM jobs WHERE kind = 'plan'"
            " AND json_extract(brief_json, '$.course_id') = ? ORDER BY created_at DESC LIMIT 1",
            (course["id"],),
        )
        if job is None:
            raise RpcError.of(
                "NOT_FOUND",
                "this course has no parent brief; it was not created by parent.brief.create.",
                course_id=course["id"],
            )
        brief = _json_load(job["brief_json"], {})
        enrollment_id = brief.get("enrollment_id")
        if not enrollment_id:
            row = _row(
                connection,
                "SELECT id FROM enrollments WHERE course_id = ? ORDER BY created_at DESC LIMIT 1",
                (course["id"],),
            )
            enrollment_id = row["id"] if row is not None else None
    return 0, {
        "course_id": str(course["id"]),
        "enrollment_id": enrollment_id,
        "brief": _parent_brief_view(brief),
        "plan_job": {
            "job_id": str(job["id"]),
            "kind": str(job["kind"]),
            "state": str(job["state"]),
            "submitted_at": job["created_at"],
        },
        "created_at": course["created_at"],
    }


@_handler("parent.plan.edit")
def parent_plan_edit(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Draft-only plan edits, fenced on the hash the parent saw *then* on the revision."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "parent.plan.edit"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    edits = [name for name in (
        "course_title", "goal", "objective_edits", "add_objectives",
        "remove_objective_ids", "order",
    ) if payload.get(name) is not None]
    if not edits:
        raise RpcError.of("VALIDATION_FAILED", "parent.plan.edit needs at least one edit.", field="objective_edits")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (payload["plan_id"],))
        if plan is None or plan["course_id"] != enrollment["course_id"]:
            raise _not_found("plan", payload["plan_id"])
        if plan["state"] != "draft":
            raise RpcError.of(
                "POLICY_VIOLATION",
                "only a draft plan can be edited; use plan.replan for an approved plan.",
                reason="plan_not_draft",
                plan_id=plan["id"],
                state=plan["state"],
            )
        actual_hash = _plan_hash(connection, plan)
        if str(payload["expected_plan_hash"]) != actual_hash:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "the plan changed since it was read; re-read before editing.",
                field="expected_plan_hash",
                current_plan_hash=actual_hash,
            )
        objectives = list(
            connection.execute(
                "SELECT * FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan["id"],)
            ).fetchall()
        )
        by_id = {str(row["id"]): row for row in objectives}
        course = _row(connection, "SELECT * FROM courses WHERE id = ?", (enrollment["course_id"],))
        now = _now()

        if payload.get("course_title") is not None:
            connection.execute(
                "UPDATE courses SET title = ?, updated_at = ? WHERE id = ?",
                (payload["course_title"], now, course["id"]),
            )
        if payload.get("goal") is not None:
            connection.execute(
                "UPDATE courses SET goal = ?, updated_at = ? WHERE id = ?",
                (payload["goal"], now, course["id"]),
            )

        for edit in payload.get("objective_edits") or []:
            objective = by_id.get(str(edit["objective_id"]))
            if objective is None:
                raise _not_found("objective", str(edit["objective_id"]))
            title = edit.get("title") or objective["title"]
            target = edit.get("evidence_target") or objective["evidence_target"]
            criteria = (
                _json_dump(edit["criteria"])
                if edit.get("criteria") is not None
                else objective["evidence_criteria_json"]
            )
            connection.execute(
                "UPDATE objectives SET title = ?, evidence_target = ?, evidence_criteria_json = ?,"
                " version = version + 1 WHERE id = ?",
                (title, target, criteria, objective["id"]),
            )

        removed: set[str] = set()
        for objective_id in payload.get("remove_objective_ids") or []:
            objective = by_id.get(str(objective_id))
            if objective is None:
                raise _not_found("objective", str(objective_id))
            for table in _OBJECTIVE_USE_TABLES:
                used = _row(connection, f"SELECT 1 AS used FROM {table} WHERE objective_id = ? LIMIT 1",
                            (objective["id"],))
                if used is not None:
                    raise RpcError.of(
                        "POLICY_VIOLATION",
                        "that objective already has generated content or learning state; it cannot be removed.",
                        reason="objective_in_use",
                        objective_id=str(objective["id"]),
                        table=table,
                    )
            connection.execute("DELETE FROM objectives WHERE id = ?", (objective["id"],))
            removed.add(str(objective["id"]))

        next_ordinal = max([int(row["ordinal"]) for row in objectives if str(row["id"]) not in removed] or [0]) + 1
        for offset, addition in enumerate(payload.get("add_objectives") or []):
            _insert_objective(
                connection,
                str(plan["id"]),
                title=str(addition["title"]),
                evidence_target=str(addition["evidence_target"]),
                criteria=list(addition.get("criteria") or []),
                ordinal=next_ordinal + offset,
            )

        surviving = list(
            connection.execute(
                "SELECT id, ordinal FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan["id"],)
            ).fetchall()
        )
        if payload.get("order") is not None:
            requested = [str(item) for item in payload["order"]]
            if len(requested) != len(set(requested)) or set(requested) != {str(row["id"]) for row in surviving}:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    "order must be a permutation of the plan's surviving objective ids.",
                    field="order",
                )
            for index, objective_id in enumerate(requested, start=1):
                connection.execute(
                    "UPDATE objectives SET ordinal = ? WHERE id = ?", (index, objective_id)
                )
        else:
            # Keep the surviving sequence gapless after removals.
            for index, row in enumerate(sorted(surviving, key=lambda item: int(item["ordinal"])), start=1):
                connection.execute("UPDATE objectives SET ordinal = ? WHERE id = ?", (index, row["id"]))

        revision = _bump_enrollment(connection, enrollment["id"], expected)
        connection.execute(
            "UPDATE plans SET version = version + 1 WHERE id = ?", (plan["id"],)
        )
        refreshed = _row(connection, "SELECT * FROM plans WHERE id = ?", (plan["id"],))
        new_hash = _plan_hash(connection, refreshed)
        connection.execute("UPDATE plans SET plan_hash = ? WHERE id = ?", (new_hash, plan["id"]))
        # The edit changed the plan version/hash and any generated outline no longer matches a
        # recorded pass. Invalidate durably and record the parent's explicit manual decision.
        generation.invalidate_plan_validation(
            connection, str(plan["id"]), reason="plan_edited", manual_authoring=True
        )
        reason = "plan_edited" if any(
            payload.get(name) is not None
            for name in ("objective_edits", "add_objectives", "remove_objective_ids", "order")
        ) else "course_edited"
        _supersede_active_approval(connection, str(enrollment["course_id"]), reason)
        ordered = [
            str(row["id"])
            for row in connection.execute(
                "SELECT id FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan["id"],)
            ).fetchall()
        ]
        result = {
            "plan_id": str(plan["id"]),
            "plan_version": int(refreshed["version"]),
            "plan_hash": new_hash,
            "objective_ids": ordered,
            "changes_need_review": True,
            "revision": revision,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
    return revision, result


@_handler("parent.final.approve")
def parent_final_approve(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Approve the exact generated content set by hash. Distinct from ``plan.approve``."""
    db.ensure_schema()
    expected = _require_revision(envelope)
    method = "parent.final.approve"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _enrollment(connection, payload["enrollment_id"])
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (payload["plan_id"],))
        if plan is None or plan["course_id"] != enrollment["course_id"]:
            raise _not_found("plan", payload["plan_id"])
        if plan["state"] != "approved":
            raise RpcError.of(
                "POLICY_VIOLATION",
                "the plan must be approved before the generated lessons can be approved.",
                reason="plan_not_approved",
                plan_id=str(plan["id"]),
                state=str(plan["state"]),
            )
        actual_hash = _plan_hash(connection, plan)
        if str(payload["plan_hash"]) != actual_hash:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "the approved plan hash is stale; re-read the plan.",
                field="plan_hash",
                current_plan_hash=actual_hash,
            )
        course = _row(connection, "SELECT * FROM courses WHERE id = ?", (enrollment["course_id"],))
        composed = authoring.sections(connection, course, plan)
        if not authoring.ready_sections(composed):
            raise RpcError.of(
                "POLICY_VIOLATION",
                "there is no generated lesson content to approve yet.",
                reason="no_generated_content",
            )
        current_content = authoring.content_hash(
            str(course["id"]), str(plan["id"]), actual_hash, composed
        )
        if str(payload["content_hash"]) != current_content:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "the content changed since it was read; re-read the blueprint.",
                field="content_hash",
                current_content_hash=current_content,
            )
        revision = _bump_enrollment(connection, enrollment["id"], expected)
        now = _now()
        _supersede_active_approval(connection, str(course["id"]), "replaced")
        approval_id = _new_id("apr")
        connection.execute(
            "INSERT INTO final_approvals (id, course_id, plan_id, plan_hash, content_hash, state,"
            " invalidation_reason, approved_at, superseded_at)"
            " VALUES (?, ?, ?, ?, ?, 'active', NULL, ?, NULL)",
            (approval_id, course["id"], plan["id"], actual_hash, current_content, now),
        )
        result = {
            "approval_id": approval_id,
            "state": "active",
            "plan_hash": actual_hash,
            "content_hash": current_content,
            "approved_at": now,
            "revision": revision,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
    return revision, result


@_handler("parent.blueprint.read")
def parent_blueprint_read(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The five tabs as declared text. Read-only, unfenced, and it never emits a path."""
    db.ensure_schema()
    limit = int(payload.get("limit") or 100)
    with db.read() as connection:
        course = _course_row(connection, payload["course_id"])
        plan = authoring.current_plan(connection, str(course["id"]))
        approval = _parent_approval(connection, str(course["id"]))
        if course["pack_id"] is not None:
            tabs, sources, current_hash = _pack_backed_blueprint(course)
            plan_view = None
            if plan is not None:
                plan_view = {
                    "plan_id": str(plan["id"]),
                    "version": int(plan["version"]),
                    "state": str(plan["state"]),
                    "plan_hash": _plan_hash(connection, plan),
                }
            status = _export_status(plan, [], approval, current_hash,
                                    has_content=any(tabs.values()))
            return 0, {
                "course_id": str(course["id"]),
                "recipe": str(course["recipe"]),
                "plan": plan_view,
                "approval": _approval_view(approval),
                "content_hash": current_hash,
                "export": status,
                "tabs": tabs,
                "sources": sources,
            }
        composed, current_hash = _derived_content(connection, course, plan)
        sources = _blueprint_sources(connection, str(course["id"]))
        status = _export_status(plan, composed, approval, current_hash)
        plan_view = None
        if plan is not None:
            plan_view = {
                "plan_id": str(plan["id"]),
                "version": int(plan["version"]),
                "state": str(plan["state"]),
                "plan_hash": _plan_hash(connection, plan),
            }
        tabs = authoring.blueprint_tabs(composed, limit=min(limit, authoring.MAX_BLUEPRINT_CHARS))
    return 0, {
        "course_id": str(course["id"]),
        "recipe": str(course["recipe"]),
        "plan": plan_view,
        "approval": _approval_view(approval),
        "content_hash": current_hash,
        "export": status,
        "tabs": tabs,
        "sources": sources,
    }


@_handler("parent.export")
def parent_export(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Authored pack + selectable-text PDF, only when the active approval covers the bytes."""
    from . import pack_flow

    return pack_flow.parent_export(payload, envelope)


@_handler("parent.reflection.record")
def parent_reflection_record(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Parent-reported difficulty. It has no evidence class and never becomes evidence."""
    db.ensure_schema()
    key = envelope.get("idempotency_key")
    method = "parent.reflection.record"
    payload_hash = _payload_hash(method, payload)
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        course = _course_row(connection, payload["course_id"])
        plan = authoring.current_plan(connection, str(course["id"]))
        plan_hash = _plan_hash(connection, plan) if plan is not None else None
        content_hash_value = None
        if plan is not None:
            composed, content_hash_value = _derived_content(connection, course, plan)
            if not authoring.ready_sections(composed):
                content_hash_value = None
        now = _now()
        reflection_id = _new_id("rfl")
        connection.execute(
            "INSERT INTO parent_reflections (id, course_id, enrollment_id, plan_id, difficulty,"
            " revisit_note, apply_to_next_draft, plan_hash, content_hash, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reflection_id,
                course["id"],
                payload.get("enrollment_id"),
                payload.get("plan_id") or (str(plan["id"]) if plan is not None else None),
                str(payload["difficulty"]),
                payload.get("revisit_note"),
                1 if payload.get("apply_to_next_draft", True) else 0,
                plan_hash,
                content_hash_value,
                now,
            ),
        )
        result = {
            "reflection_id": reflection_id,
            "difficulty": str(payload["difficulty"]),
            "plan_hash": plan_hash,
            "content_hash": content_hash_value,
            "created_at": now,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


@_handler("parent.reflection.list")
def parent_reflection_list(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Bounded read of the reflections that seed the next brief."""
    db.ensure_schema()
    limit = min(int(payload.get("limit") or 50), 200)
    with db.read() as connection:
        course = _course_row(connection, payload["course_id"])
        rows = connection.execute(
            "SELECT * FROM parent_reflections WHERE course_id = ? ORDER BY created_at DESC LIMIT ?",
            (course["id"], limit),
        ).fetchall()
        total = connection.execute(
            "SELECT COUNT(*) AS n FROM parent_reflections WHERE course_id = ?", (course["id"],)
        ).fetchone()["n"]
    return 0, {
        "reflections": [
            {
                "reflection_id": str(row["id"]),
                "difficulty": str(row["difficulty"]),
                "revisit_note": row["revisit_note"],
                "apply_to_next_draft": bool(row["apply_to_next_draft"]),
                "plan_hash": row["plan_hash"],
                "content_hash": row["content_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ],
        "total": int(total),
    }


# ── source revalidation ─────────────────────────────────────────────────────


@_handler("source.revalidate")
def source_revalidate(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Record one re-fetch of a source and report the staleness it caused.

    Detection only: a changed content hash marks the row ``stale`` and the existing grading gate
    refuses dependent checks with ``CHECK_STALE``. Learner evidence is never rewritten. There is no
    aggregate revision on a course-scoped source row, so the content-hash comparison is the fence
    and the envelope's ``revision`` stays 0 (it is not an enrollment revision).
    """
    db.ensure_schema()
    method = "source.revalidate"
    key = envelope.get("idempotency_key")
    payload_hash = _payload_hash(method, payload)
    fetched = payload["fetched"]
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        result = source_ledger.refresh(connection, str(payload["source_id"]), fetched).to_dict()
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


# ── registration ────────────────────────────────────────────────────────────


def ensure_registered() -> tuple[str, ...]:
    """Bind every handler whose method name exists in the live contract.

    Registry-driven on purpose: a contract amendment adds methods without editing this module,
    and a handler for a method the contract does not have is simply not registered (so dispatch
    answers ``NOT_IMPLEMENTED`` rather than inventing a method).
    """
    available = set(method_names())
    registered = []
    for method, handler in HANDLERS.items():
        if method in available:
            api.register_handler(method, handler)
            registered.append(method)
    return tuple(sorted(registered))


ensure_registered()
