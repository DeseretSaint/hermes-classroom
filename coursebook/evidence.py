"""Evidence inspection: L1 raw events, L2 objective evidence, L3 plan recommendations, disputes.

Three layers, three different claims (``PREBUILD_SPEC.md`` §6):

* **L1** is the raw record: attempts, hints, shown answers, overrides, review actions. It is what
  happened, including what was *not* independent.
* **L2** is the per-objective claim that is actually linked to an L1 row: only a cold, committed
  pass reaches it. It is never inferred from a review action or a self-report.
* **L3** is a short, revisable recommendation derived from L2. It is explicitly **not** a learner
  persona, a psychological diagnosis, or a mastery label.

Nothing here returns a reference answer, rubric internals, or the grader's raw output. Attempt
criteria/provenance are included because they were committed to the attempt row and the learner is
entitled to inspect and dispute them (``AUDIT.md`` R11/R12).
"""

from __future__ import annotations

from typing import Any

#: L1 kinds that are learner *actions*, never evidence of knowing something.
ACTION_KINDS = (
    "hint_request",
    "answer_shown",
    "review_snooze",
    "review_stretch",
    "review_drop",
    "review_resume",
)

#: L1 kinds that record a graded result.
ATTEMPT_KINDS = ("attempt", "override")


def _json(value: Any, default: Any) -> Any:
    import json

    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _attempt_view(row) -> dict[str, Any]:
    provenance = _json(row["grading_provenance_json"], {})
    if not isinstance(provenance, dict):
        provenance = {}
    # A dispute lives inside provenance; expose it as a list, not a nested implementation detail.
    disputes = provenance.get("disputes") if isinstance(provenance.get("disputes"), list) else []
    public_provenance = {
        key: provenance.get(key)
        for key in ("grader", "rubric_id", "rubric_version", "model", "provider", "construct", "failure")
        if key in provenance
    }
    return {
        "attempt_id": row["id"],
        "check_id": row["check_id"],
        "check_version": int(row["check_version"]),
        "answer": _json(row["answer_json"], {}),
        "answer_hash": row["answer_hash"],
        "verdict": row["verdict"],
        "evidence_class": row["evidence_class"],
        "criteria": _json(row["criteria_json"], []),
        "state": row["state"],
        "provenance": public_provenance,
        "dispute_count": len(disputes),
        "created_at": row["created_at"],
        "committed_at": row["committed_at"],
    }


def layer1(connection, enrollment_id: str, *, objective_id: str | None = None,
           limit: int = 200) -> dict[str, Any]:
    """Raw attempts plus the assist/review events that changed how they count."""
    clause = " AND a.enrollment_id = ?"
    params: list[Any] = [enrollment_id]
    if objective_id:
        clause += " AND c.objective_id = ?"
        params.append(objective_id)
    attempts = connection.execute(
        "SELECT a.* FROM attempts a JOIN checks c ON c.id = a.check_id"
        f" WHERE a.enrollment_id IS NOT NULL{clause}"
        " ORDER BY a.created_at DESC, a.rowid DESC LIMIT ?",
        (*params, int(limit)),
    ).fetchall()
    ev_clause = " WHERE enrollment_id = ?"
    ev_params: list[Any] = [enrollment_id]
    if objective_id:
        ev_clause += " AND objective_id = ?"
        ev_params.append(objective_id)
    events = connection.execute(
        "SELECT * FROM evidence" + ev_clause + " ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (*ev_params, int(limit)),
    ).fetchall()
    return {
        "enrollment_id": enrollment_id,
        "objective_id": objective_id,
        "attempts": [_attempt_view(row) for row in attempts],
        "events": [
            {
                "evidence_id": row["id"],
                "objective_id": row["objective_id"],
                "attempt_id": row["attempt_id"],
                "layer": int(row["layer"]),
                "kind": row["kind"],
                "evidence_class": row["evidence_class"],
                "is_action": row["kind"] in ACTION_KINDS,
                "created_at": row["created_at"],
            }
            for row in events
        ],
    }


def layer2(connection, enrollment_id: str, *, objective_id: str | None = None) -> dict[str, Any]:
    """Per-objective evidence state, linked down to the L1 rows that justify it."""
    enrollment = connection.execute("SELECT * FROM enrollments WHERE id = ?", (enrollment_id,)).fetchone()
    if enrollment is None:
        raise LookupError(f"enrollment {enrollment_id} does not exist")
    clause = ""
    params: list[Any] = [enrollment["course_id"]]
    if objective_id:
        clause = " AND o.id = ?"
        params.append(objective_id)
    objectives = connection.execute(
        "SELECT o.* FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
        " WHERE pl.course_id = ? AND pl.state = 'approved'" + clause + " ORDER BY o.ordinal",
        tuple(params),
    ).fetchall()
    items = []
    for objective in objectives:
        linked = connection.execute(
            "SELECT * FROM evidence WHERE enrollment_id = ? AND objective_id = ? AND layer = 2"
            " ORDER BY created_at DESC, rowid DESC",
            (enrollment_id, objective["id"]),
        ).fetchall()
        classes = connection.execute(
            "SELECT evidence_class, COUNT(*) AS n FROM evidence WHERE enrollment_id = ? AND objective_id = ?"
            " AND layer = 1 AND kind = 'attempt' GROUP BY evidence_class",
            (enrollment_id, objective["id"]),
        ).fetchall()
        items.append({
            "objective_id": objective["id"],
            "title": objective["title"],
            "ordinal": int(objective["ordinal"]),
            "evidence_target": objective["evidence_target"],
            "state": objective["state"],
            "independent": len(linked) > 0,
            "delayed": any(row["kind"] == "delayed_retrieval" for row in linked),
            "L2_evidence_ids": [row["id"] for row in linked],
            "independent_at": linked[0]["created_at"] if linked else None,
            "attempt_classes": {row["evidence_class"]: int(row["n"]) for row in classes},
            "criteria": _json(objective["evidence_criteria_json"], []),
        })
    return {"enrollment_id": enrollment_id, "objective_id": objective_id, "objectives": items}


def layer3(connection, enrollment_id: str, *, cap: int = 3) -> dict[str, Any]:
    """Short, revisable recommendations derived from L2. Not a persona; not a diagnosis."""
    l2 = layer2(connection, enrollment_id)
    recommendations: list[dict[str, Any]] = []
    unproven = [o for o in l2["objectives"] if not o["independent"]]
    if unproven:
        recommendations.append({
            "kind": "needs_independent_evidence",
            "text": f"{len(unproven)} objective(s) have no cold independent evidence yet.",
            "objective_ids": [o["objective_id"] for o in unproven][:10],
            "basis": "layer2.independent == false",
        })
    hinted_only = [
        o for o in l2["objectives"]
        if o["independent"] and o["attempt_classes"].get("hinted") and not o["attempt_classes"].get("cold")
    ]
    if hinted_only:
        recommendations.append({
            "kind": "hint_contamination",
            "text": "Some objectives advanced only after hints; a fresh cold check would separate access from mastery.",
            "objective_ids": [o["objective_id"] for o in hinted_only][:10],
            "basis": "layer2.attempt_classes has hinted and no cold",
        })
    if not recommendations:
        recommendations.append({
            "kind": "on_track",
            "text": "Every objective has at least one cold independent result. Keep the review queue honest.",
            "objective_ids": [],
            "basis": "layer2.independent == true for all objectives",
        })
    return {
        "enrollment_id": enrollment_id,
        "recommendations": recommendations[: max(0, int(cap))],
        "as_of": connection.execute("SELECT MAX(created_at) AS at FROM evidence WHERE enrollment_id = ?",
                                    (enrollment_id,)).fetchone()["at"],
        "is_persona": False,
    }


def disputes(connection, enrollment_id: str, *, attempt_id: str | None = None) -> dict[str, Any]:
    """Every dispute recorded against this enrollment's attempts, newest first.

    Disputes are stored inside the attempt's provenance JSON in ``cb.db`` v2 (there is no disputes
    table). They are returned as first-class records here so the pane and the review packet do not
    have to know that storage detail.
    """
    clause = " AND a.id = ?" if attempt_id else ""
    params: list[Any] = [enrollment_id]
    if attempt_id:
        params.append(attempt_id)
    rows = connection.execute(
        "SELECT a.* FROM attempts a JOIN checks c ON c.id = a.check_id"
        " WHERE a.enrollment_id = ?" + clause + " ORDER BY a.created_at DESC",
        tuple(params),
    ).fetchall()
    items = []
    for row in rows:
        provenance = _json(row["grading_provenance_json"], {})
        stored = provenance.get("disputes") if isinstance(provenance, dict) else None
        for dispute in stored or []:
            if not isinstance(dispute, dict):
                continue
            items.append({
                "dispute_id": dispute.get("id"),
                "attempt_id": row["id"],
                "check_id": row["check_id"],
                "verdict": row["verdict"],
                "evidence_class": row["evidence_class"],
                "state": dispute.get("state", "open"),
                "note": dispute.get("note"),
                "created_at": dispute.get("created_at"),
            })
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"enrollment_id": enrollment_id, "disputes": items, "count": len(items)}


def bundle(connection, enrollment_id: str, *, objective_id: str | None = None,
           limit: int = 200) -> dict[str, Any]:
    """The whole inspectable evidence view the pane needs, in one read.

    ``limit`` bounds the layer-1 attempt/event lists only (the contract's ``evidence.inspect``
    ``limit``); L2 is per-objective and L3 is already capped.
    """
    return {
        "l1": layer1(connection, enrollment_id, objective_id=objective_id, limit=limit),
        "l2": layer2(connection, enrollment_id, objective_id=objective_id),
        "l3": layer3(connection, enrollment_id),
        "disputes": disputes(connection, enrollment_id),
    }
