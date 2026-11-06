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
import uuid
from typing import Any, Callable

from . import api, db, grading, jobs as jobs_contract
from .api import RpcError
from .contracts import method_names

#: ``method -> handler(payload, envelope) -> (revision, result)``
HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], tuple[int, dict[str, Any]]]] = {}

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
    "binding.get",
    "jobs.create",
    "jobs.get",
    "jobs.cancel",
    "usage.summary",
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
    objectives = connection.execute(
        "SELECT id, ordinal, title, evidence_target, evidence_criteria_json, version"
        " FROM objectives WHERE plan_id = ? ORDER BY ordinal",
        (plan["id"],),
    ).fetchall()
    payload = {
        "course_id": plan["course_id"],
        "version": plan["version"],
        "schedule": _json_load(plan["schedule_json"], {}),
        "objectives": [
            {
                "id": row["id"],
                "ordinal": row["ordinal"],
                "title": row["title"],
                "evidence_target": row["evidence_target"],
                "evidence_criteria": _json_load(row["evidence_criteria_json"], []),
                "version": row["version"],
            }
            for row in objectives
        ],
    }
    return _canonical_hash(payload)


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
    result = {
        "course": {
            "course_id": course["id"],
            "title": course["title"],
            "recipe": course["recipe"],
            "goal": course["goal"],
            "locale": course["locale"],
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
    """Resolve a binding by stored/runtime session id or enrollment id — never by recency."""
    db.ensure_schema()
    session_id = payload.get("session_id")
    enrollment_id = payload.get("enrollment_id")
    if not session_id and not enrollment_id:
        raise RpcError.of("VALIDATION_FAILED", "provide session_id or enrollment_id.", field="session_id")
    with db.read() as connection:
        row = None
        if enrollment_id:
            row = _row(
                connection,
                "SELECT * FROM bindings WHERE enrollment_id = ? ORDER BY revision DESC, updated_at DESC LIMIT 1",
                (enrollment_id,),
            )
        if row is None and session_id:
            row = _row(
                connection,
                "SELECT * FROM bindings WHERE stored_session_id = ? OR runtime_session_id = ? LIMIT 1",
                (session_id, session_id),
            )
    if row is None:
        return 0, {"binding": None}
    return int(row["revision"]), {
        "binding": {
            "binding_id": row["id"],
            "enrollment_id": row["enrollment_id"],
            "profile": row["profile"],
            "connection_id": row["connection_id"],
            "runtime_session_id": row["runtime_session_id"],
            "stored_session_id": row["stored_session_id"],
            "cwd_fingerprint": row["cwd_fingerprint"],
            "compression_tip": row["compression_tip"],
            "status": row["status"],
            "revision": int(row["revision"]),
            "updated_at": row["updated_at"],
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
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        connection.execute(
            "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status, pack_id, revision, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'draft', NULL, 0, ?, ?)",
            (course_id, payload["title"], payload["recipe"], payload["goal"], payload.get("locale"),
             _json_dump(payload.get("dials") or {}), now, now),
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


@_handler("plan.approve")
def plan_approve(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Approve the exact plan content the caller saw: the hash must still match."""
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
        to_revision = _bump_enrollment(connection, enrollment["id"], expected)
        if plan["state"] == "approved":
            raise RpcError.of("POLICY_VIOLATION", "this plan version is already approved.", plan_id=plan["id"])
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
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (new_plan_id,))
        connection.execute("UPDATE plans SET plan_hash = ? WHERE id = ?", (_plan_hash(connection, plan), new_plan_id))
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
        existing = _row(
            connection,
            "SELECT * FROM checks WHERE objective_id = ? AND state = 'open' ORDER BY version DESC LIMIT 1",
            (objective["id"],),
        )
        if existing is not None:
            return int(enrollment["revision"]), {
                "check_id": existing["id"],
                "check_version": int(existing["version"]),
                "evidence_target": existing["evidence_target"],
                "revision": int(enrollment["revision"]),
            }
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
        check_id = _insert_check(
            connection, objective, spec, variant.get("stimulus") or {},
            variant.get("reference") or reference, variant.get("rubric") or rubric, version,
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

    Cold is the default. A second answer to the same check follows feedback that was shown, so it
    is ``hinted`` — recognition after scaffolding cannot become independent evidence
    (``AUDIT.md`` R10/R12).
    """
    return "hinted" if _attempt_rows_before(connection, enrollment_id, check_id) else "cold"


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
        "SELECT status FROM bindings WHERE enrollment_id = ? ORDER BY revision DESC, updated_at DESC LIMIT 1",
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
                " VALUES (?, ?, ?, ?, 2, 'independent_evidence', ?, ?)",
                (_new_id("evd"), enrollment["id"], objective["id"], attempt_id, evidence_class, _now()),
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
    """Evidence states stay distinct: only a cold pass reaches ``independent_evidence``."""
    if evidence_class == "override":
        return "overridden"
    if verdict == "pass":
        return "independent_evidence" if evidence_class == "cold" else (
            "introduced" if current == "not_started" else current
        )
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
        result = {"entry_id": entry_id, "revision": int(enrollment["revision"])}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                  int(enrollment["revision"]), result)
    return int(enrollment["revision"]), result


@_handler("notebook.delete")
def notebook_delete(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    with db.transaction() as connection:
        entry = _row(connection, "SELECT * FROM notebook_entries WHERE id = ?", (payload["entry_id"],))
        if entry is None:
            raise _not_found("notebook entry", payload["entry_id"])
        enrollment = _enrollment(connection, entry["enrollment_id"])
        connection.execute("DELETE FROM notebook_entries WHERE id = ?", (entry["id"],))
        result = {"deleted": True, "revision": int(enrollment["revision"])}
    return int(enrollment["revision"]), result


# ── jobs ────────────────────────────────────────────────────────────────────


def _job_view(row) -> dict[str, Any]:
    progress = _json_load(row["progress_json"], {})
    error = _json_load(row["error_json"], {})
    lease = None
    if row["lease_owner"] or row["lease_expires_at"]:
        lease = {"owner": row["lease_owner"] or "", "expires_at": row["lease_expires_at"]}
    return {
        "job_id": row["id"],
        "kind": row["kind"],
        "state": row["state"],
        "operation_id": row["operation_id"],
        "attempt_id": row["attempt_id"] or "",
        "brief": _json_load(row["brief_json"], {}),
        "checkpoint": _json_load(row["checkpoint_json"], {}),
        "progress": progress if isinstance(progress, dict) else {},
        "lease": lease,
        "artifact_ids": list(progress.get("artifact_ids") or []) if isinstance(progress, dict) else [],
        "error": error or None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "cancel_requested_at": row["updated_at"] if row["state"] in ("cancel_requested", "cancelling") else None,
    }


@_handler("jobs.create")
def jobs_create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    method = "jobs.create"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    now = _now()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        job_id = _new_id("job")
        connection.execute(
            "INSERT INTO jobs (id, kind, state, operation_id, brief_json, checkpoint_json, attempt_id,"
            " lease_owner, lease_expires_at, progress_json, error_json, created_at, updated_at)"
            " VALUES (?, ?, 'queued', ?, ?, '{}', ?, NULL, NULL, '{}', '{}', ?, ?)",
            (job_id, payload["kind"], envelope.get("operation_id"), _json_dump(payload["brief"]),
             _new_id("jat"), now, now),
        )
        result = {"job_id": job_id, "state": "queued"}
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


# ── write paths used by the plan job and by Parent mode ─────────────────────


def plan_hash(plan_id: str) -> str:
    """Hash of a plan's current content, for an approval flow that shows the hash it binds."""
    db.ensure_schema()
    with db.read() as connection:
        plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (plan_id,))
        if plan is None:
            raise _not_found("plan", plan_id)
        return _plan_hash(connection, plan)


def record_objective(plan_id: str, *, title: str, evidence_target: str, criteria: list[dict[str, Any]],
                     ordinal: int | None = None) -> str:
    """Write one planned objective (draft plans only).

    The plan job (``jobs.kind = 'plan'``) and Parent Studio call this instead of inserting rows
    themselves, so the hash and the ordinal sequence stay consistent. Draft edits have no approval
    to invalidate yet (``PREBUILD_SPEC.md`` §10).
    """
    db.ensure_schema()
    with db.transaction() as connection:
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
    return objective_id


#: Evidence classes a non-attempt observation may carry. A model or a learner cannot self-assert
#: independent evidence (``AUDIT.md`` R10/R12).
_OBSERVATION_CLASSES = ("self_reported", "parent_reported")


def record_observation(enrollment_id: str, objective_id: str, *, evidence_class: str,
                       kind: str = "observation", note: str | None = None) -> str:
    """Record a self/parent-reported observation. Layer 1 only — never independent evidence."""
    db.ensure_schema()
    if evidence_class not in _OBSERVATION_CLASSES:
        raise RpcError.of(
            "POLICY_VIOLATION",
            "only self_reported or parent_reported observations can be recorded here.",
            evidence_class=evidence_class,
        )
    with db.transaction() as connection:
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
            "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind, evidence_class, created_at)"
            " VALUES (?, ?, ?, NULL, 1, ?, ?, ?)",
            (evidence_id, enrollment["id"], objective["id"], kind, evidence_class, _now()),
        )
    return evidence_id


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
