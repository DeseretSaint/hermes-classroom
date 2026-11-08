"""Source ledger and staleness propagation.

``PREBUILD_SPEC.md`` §9, §12 and ``AUDIT.md`` R6 draw the line this module keeps: provenance is not
support, a fetched page is untrusted content, and an updated source marks dependent generated
checks stale pending review instead of silently rewriting evidence.

Staleness is *derived*, never a second source of truth: the ``sources`` row keeps the
contract vocabulary (``model_assessed``/``conflicting``/``stale``/...), and dependent
objectives/checks/artifacts are resolved from the recorded research runs, plan sections and
artifact provenance. That is why no extra table or column was invented for it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from . import research
from .api import RpcError

#: Statuses that mean "a learner-facing check must not silently grade against this".
REVIEW_REQUIRED = ("stale", "unreachable")


def _now(moment: datetime | None = None) -> datetime:
    return moment or datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class DependencyStateUnknown(RuntimeError):
    """A dependency table exists but its contents could not be read.

    "Nothing depends on this source" and "the dependencies could not be read" are different
    facts, and only the first may be reported as an empty list. The grading gate treats this
    exception as a refusal, never as "current": a ledger that cannot be read must not let a
    stale-source check grade.
    """


def _dependency_json(value: str | None, default: Any) -> Any:
    """Parse a recorded dependency list; a value that cannot be parsed is *unknown*, not empty."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        raise DependencyStateUnknown(f"dependency JSON could not be parsed: {exc}") from exc


def _has_table(connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _dependency_rows(
    connection,
    sql: str,
    params: tuple,
    *,
    optional_tables: tuple[str, ...] = (),
    what: str,
):
    """Rows for a dependency query, where "the table predates this plan" is an honest empty.

    ``optional_tables`` are the staging tables a generation stage creates lazily. Empty is honest
    only when every one of them is genuinely absent from the schema; if one exists and the read
    still fails, the dependency set is unknowable, so this raises
    :class:`DependencyStateUnknown` instead of reporting "nothing depends on this". A query with
    no optional tables (core records) always runs, so a schema that lost one fails closed.
    """
    if optional_tables and not any(_has_table(connection, table) for table in optional_tables):
        return []
    try:
        return connection.execute(sql, params).fetchall()
    except Exception as exc:  # noqa: BLE001 - re-raised as "unknown", never mapped to empty
        raise DependencyStateUnknown(f"{what} could not be read: {exc}") from exc


def ledger(connection, course_id: str) -> list[dict[str, Any]]:
    """The ledger as the UI may show it: URL/title/fetch/publication dates + support status."""
    rows = connection.execute(
        "SELECT * FROM sources WHERE course_id = ? ORDER BY fetched_at DESC, id", (course_id,)
    ).fetchall()
    stale_ids = {item["source_id"] for item in stale_sources(connection, course_id)}
    return [
        {
            "source_id": row["id"],
            "url": row["url"],
            "title": row["title"],
            "source_type": row["source_type"],
            "fetched_at": row["fetched_at"],
            "published_at": row["published_at"],
            "support_status": row["support_status"],
            "claim_count": int(row["claim_count"] or 0),
            "stale": row["support_status"] in REVIEW_REQUIRED or row["id"] in stale_ids,
        }
        for row in rows
    ]


def stale_sources(connection, course_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT id AS source_id, url, title, support_status FROM sources"
        " WHERE course_id = ? AND support_status IN ('stale', 'unreachable')",
        (course_id,),
    ).fetchall()
    return [dict(row) for row in rows]


# ── dependency resolution ──────────────────────────────────────────────────


def _latest_run_sources(connection, course_id: str) -> dict[str, dict[str, Any]]:
    """Latest recorded hash per source URL/ID, from the immutable research-run snapshots."""
    rows = _dependency_rows(
        connection,
        "SELECT sources_json FROM gen_research_runs WHERE course_id = ? ORDER BY created_at DESC",
        (course_id,),
        optional_tables=("gen_research_runs",),
        what="the recorded research runs",
    )
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        for entry in _dependency_json(row["sources_json"], []):
            if not isinstance(entry, dict):
                continue
            for key in (entry.get("source_id"), entry.get("url")):
                if key and key not in latest:
                    latest[str(key)] = entry
    return latest


def _plan_objective_ordinals(connection, course_id: str) -> dict[str, dict[int, str]]:
    """plan_id -> {ordinal: objective_id} for the course's current plans."""
    rows = _dependency_rows(
        connection,
        "SELECT pl.id AS plan_id, o.ordinal, o.id AS objective_id FROM plans pl"
        " JOIN objectives o ON o.plan_id = pl.id WHERE pl.course_id = ?",
        (course_id,),
        what="the plan objective ordinals",
    )
    mapping: dict[str, dict[int, str]] = {}
    for row in rows:
        mapping.setdefault(str(row["plan_id"]), {})[int(row["ordinal"])] = str(row["objective_id"])
    return mapping


def _sections_citing(connection, course_id: str, source_id: str, url: str | None) -> list[dict[str, Any]]:
    keys = {source_id, url or ""} - {""}
    rows = _dependency_rows(
        connection,
        "SELECT plan_id, objective_refs_json, source_ids_json FROM gen_plan_sections"
        " WHERE plan_id IN (SELECT id FROM plans WHERE course_id = ?)",
        (course_id,),
        optional_tables=("gen_plan_sections",),
        what="the plan sections citing this source",
    )
    citing = []
    for row in rows:
        source_ids = {str(item) for item in _dependency_json(row["source_ids_json"], [])}
        if source_ids & keys:
            citing.append(
                {
                    "plan_id": row["plan_id"],
                    "objective_refs": _dependency_json(row["objective_refs_json"], []),
                }
            )
    return citing


def impact(connection, source_id: str) -> dict[str, Any]:
    """Everything that depends on this source: objectives, open checks, artifacts, lessons.

    Raises :class:`DependencyStateUnknown` when a dependency table exists but cannot be read;
    an under-reported impact list is a false answer, not a smaller one.
    """
    row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if row is None:
        raise RpcError.of("NOT_FOUND", f"source {source_id} does not exist.", source_id=source_id)
    course_id = str(row["course_id"])
    ordinals = _plan_objective_ordinals(connection, course_id)
    objective_ids: set[str] = set()
    for section in _sections_citing(connection, course_id, source_id, row["url"]):
        plan_map = ordinals.get(str(section["plan_id"]), {})
        for ref in section["objective_refs"]:
            if isinstance(ref, int) and ref in plan_map:
                objective_ids.add(plan_map[ref])
            elif isinstance(ref, str):
                objective_ids.add(ref)
    check_ids: list[str] = []
    if objective_ids:
        placeholders = ",".join("?" for _ in objective_ids)
        checks = connection.execute(
            f"SELECT id FROM checks WHERE objective_id IN ({placeholders}) AND state != 'superseded'",
            tuple(objective_ids),
        ).fetchall()
        check_ids = [str(item["id"]) for item in checks]
    lessons = _dependency_rows(
        connection,
        "SELECT id FROM gen_lessons WHERE plan_id IN (SELECT id FROM plans WHERE course_id = ?)",
        (course_id,),
        optional_tables=("gen_lessons",),
        what="the dependent lessons",
    )
    artifacts = connection.execute(
        "SELECT id FROM artifacts WHERE course_id = ? AND provenance_json LIKE ?",
        (course_id, f'%"{source_id}"%'),
    ).fetchall()
    return {
        "source_id": source_id,
        "course_id": course_id,
        "objective_ids": sorted(objective_ids),
        "check_ids": check_ids,
        "artifact_ids": [str(item["id"]) for item in artifacts],
        "lesson_ids": [str(item["id"]) for item in lessons],
        "support_status": row["support_status"],
    }


# ── refresh / update ────────────────────────────────────────────────────────


@dataclass
class RefreshResult:
    source_id: str
    changed: bool
    fetched_at: str
    support_status: str
    previous_hash: str | None
    content_hash: str | None
    impact: dict[str, Any]
    review_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "changed": self.changed,
            "fetched_at": self.fetched_at,
            "support_status": self.support_status,
            "previous_hash": self.previous_hash,
            "content_hash": self.content_hash,
            "impact": self.impact,
            "review_required": self.review_required,
        }


def _recorded_baseline(row, latest: dict[str, dict[str, Any]]) -> str | None:
    """The hash this source row was last adopted at, or ``None`` when it has no baseline yet.

    ``sources.content_hash`` (cb.db v4) is the row's own record, so pack-imported sources that
    never had a research run still get a baseline on their first revalidation. The immutable
    research-run snapshot stays the fallback for rows written before the column existed.
    """
    try:
        stored = row["content_hash"]
    except (IndexError, KeyError):
        stored = None
    if stored:
        return str(stored)
    prior = latest.get(str(row["id"])) or latest.get(str(row["url"] or "")) or None
    if prior and prior.get("content_hash"):
        return str(prior["content_hash"])
    return None


def refresh(
    connection,
    source_id: str,
    fetched: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    reason: str | None = None,
) -> RefreshResult:
    """Record a re-fetch of an existing source and propagate staleness.

    ``fetched`` is the seam's return shape (``content``…). ``None`` means the source was
    unreachable: it stays historical evidence but is marked ``unreachable`` so reuse triggers
    review. A changed content hash marks the row ``stale``; dependent checks are then refused for
    grading until re-audited. The first successful fetch of a row with no baseline records the
    baseline and is *not* a change. Nothing migrates learner evidence.
    """
    moment = _now(now)
    row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if row is None:
        raise RpcError.of("NOT_FOUND", f"source {source_id} does not exist.", source_id=source_id)
    previous_hash = _recorded_baseline(row, _latest_run_sources(connection, str(row["course_id"])))

    if fetched is None:
        connection.execute(
            "UPDATE sources SET support_status = 'unreachable' WHERE id = ?", (source_id,)
        )
        return RefreshResult(
            source_id=source_id,
            changed=False,
            fetched_at=str(row["fetched_at"]),
            support_status="unreachable",
            previous_hash=previous_hash,
            content_hash=None,
            impact=impact(connection, source_id),
            review_required=True,
        )

    text = str(fetched.get("content") or "")
    bounded = " ".join(text.split())[:40000]
    content_hash = research.sha256_of_text(bounded) if bounded else None
    changed = bool(previous_hash and content_hash and previous_hash != content_hash)
    stamp = _iso(moment)
    if changed:
        status = "stale"
    elif str(row["support_status"]) == "stale":
        # Re-fetched and identical: the row is historical again, but a human still reviews the
        # impact list before the dependent checks are re-audited.
        status = "stale"
    else:
        status = str(row["support_status"])
    connection.execute(
        "UPDATE sources SET fetched_at = ?, title = COALESCE(?, title), support_status = ?,"
        " content_hash = COALESCE(?, content_hash) WHERE id = ?",
        (stamp, fetched.get("title"), status, content_hash, source_id),
    )
    return RefreshResult(
        source_id=source_id,
        changed=changed,
        fetched_at=stamp,
        support_status=status,
        previous_hash=previous_hash,
        content_hash=content_hash,
        impact=impact(connection, source_id),
        review_required=status in REVIEW_REQUIRED,
    )


def apply_run(connection, course_id: str, run: research.ResearchRun) -> dict[str, Any]:
    """Upsert a research run's sources and mark changed ones stale.

    Called from the generation pipeline *after* it persists the immutable run snapshot, so the
    previous content hash is always available for comparison. The row's own ``content_hash``
    baseline (cb.db v4) is written for every source the run saw, so a later ``source.revalidate``
    compares against the same hash the run recorded instead of drifting from the snapshot.
    """
    marked: list[dict[str, Any]] = []
    previous = _latest_run_sources(connection, course_id)
    for source in run.sources:
        existing = connection.execute(
            "SELECT * FROM sources WHERE course_id = ? AND url = ?", (course_id, source.url)
        ).fetchone()
        if existing is None:
            continue
        prior_hash = _recorded_baseline(existing, previous)
        if source.content_hash:
            connection.execute(
                "UPDATE sources SET content_hash = ? WHERE id = ?",
                (source.content_hash, existing["id"]),
            )
        if prior_hash and source.content_hash and prior_hash != source.content_hash:
            connection.execute(
                "UPDATE sources SET support_status = 'stale', fetched_at = ? WHERE id = ?",
                (source.fetched_at, existing["id"]),
            )
            marked.append(
                {
                    "source_id": existing["id"],
                    "previous_hash": prior_hash,
                    "content_hash": source.content_hash,
                    "impact": impact(connection, str(existing["id"])),
                }
            )
    return {"stale": marked}


# ── grading gate ────────────────────────────────────────────────────────────


def check_staleness(connection, check_id: str) -> dict[str, Any] | None:
    """Return the stale-source impact for a check's objective, or ``None`` when current.

    Raises :class:`DependencyStateUnknown` when a dependency read fails: unknown is not
    "current", and the caller must refuse rather than grade.
    """
    row = connection.execute(
        "SELECT o.id AS objective_id, pl.course_id AS course_id FROM checks c"
        " JOIN objectives o ON o.id = c.objective_id JOIN plans pl ON pl.id = o.plan_id WHERE c.id = ?",
        (check_id,),
    ).fetchone()
    if row is None:
        return None
    course_id = str(row["course_id"])
    for source in stale_sources(connection, course_id):
        affected = impact(connection, str(source["source_id"]))
        if str(row["objective_id"]) in affected["objective_ids"]:
            return {
                "source_id": source["source_id"],
                "source_title": source["title"],
                "support_status": source["support_status"],
                "objective_id": row["objective_id"],
            }
    return None


def assert_check_current(connection, check_id: str) -> None:
    """Refuse grading a check whose objective depends on a stale/unreachable source.

    A dependency read that fails is refused too: grading against a ledger whose state cannot be
    established would be grading blind. The refusal is an ``INTERNAL_ERROR`` (retryable) rather
    than ``CHECK_STALE``, because the honest complaint is "could not verify", not "the source
    changed".
    """
    try:
        stale = check_staleness(connection, check_id)
    except DependencyStateUnknown as exc:
        raise RpcError.of(
            "INTERNAL_ERROR",
            "the source ledger could not be read, so this check's sources cannot be verified;"
            " grading is refused and nothing was graded.",
            reason="source_dependencies_unknown",
            retryable=True,
        ) from exc
    if stale is None:
        return
    raise RpcError.of(
        "CHECK_STALE",
        "This check's source changed; it is paused for review instead of grading against stale content.",
        check_id=check_id,
        **stale,
    )
