"""Pack lifecycle integration: preview → import → learn → export → delete.

:mod:`coursebook.packs` owns the pack *document*; :mod:`coursebook.archive` owns bounded
archive reading and staging. This module is the seam that connects both to the kernel
(:mod:`coursebook.domain`, ``cb.db``) so a pack becomes a real course a learner can open, and so
an exported pack is provably the content that was reviewed.

Three frozen constraints shape every function here:

* **A pack is untrusted data.** Nothing from a manifest reaches ``courses``/``objectives``
  without passing :func:`coursebook.archive.extract_archive` (schema, bounds, MIME, hashes,
  teaching audit) and :func:`validate_and_audit` below. Refusal happens *before* the first
  database write, so a rejected pack leaves no course residue.
* **Pack identity and enrollment identity are separate.** ``pack_id`` + immutable
  ``pack_version`` + ``content_hash`` identify content; ``course_id``/``enrollment_id`` identify
  one learner's progress. Re-importing the same content adds no rows; ``mode: "fresh"`` cuts a
  new course over the same immutable content; ``mode: "resume"`` re-opens the existing one.
* **The pack's recipe is the course's recipe.** There is no request field that can change it, so
  a ``parent`` pack cannot silently become an adult graded course. A parent pack's checks are
  never copied as gradable specs; cross-recipe conversion is a separate, explicit authoring act
  (:func:`build_conversion`) that produces a *new* pack with ``derived_from`` recorded.

Host seams this module exposes but does not own (``dashboard/plugin_api.py`` is Sable's file):

* :func:`grant_local_file` — the only way a filesystem path enters the pack pipeline.
* :func:`open_artifact` — resolves an ``artifact.get`` handle to bounded bytes for the
  authenticated download route.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sqlite3
import uuid
import warnings
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import PACKAGE_ID, __version__, api, db
from . import archive, artifacts, packs, segments, validators
from . import parent_authoring as authoring
from .api import RpcError
from .archive import PackRejected, PackLibrary, StagingArea

#: Methods this module owns. ``pack.delete`` stays with the kernel: it owns data-scope previews.
PACK_METHODS: tuple[str, ...] = (
    "pack.preview",
    "pack.import",
    "pack.export",
    "pack.list",
    "pack.inspect",
    "course.export.read",
    "course.export",
)

#: Roles whose content may be rendered as a lesson segment on import.
TEACHING_ROLES = ("section", "learner_page", "parent_guide")


# ── paths ──────────────────────────────────────────────────────────────────


def data_root() -> Path:
    """``<plugin data>/`` for the active profile, resolved per call (never cached).

    ``db.data_root`` owns the single-home pin (CB-013), so the pack library, the staging area and
    the sqlite file always agree on one home.
    """
    return db.data_root()


def library_root() -> Path:
    return data_root() / "pack-library"


def staging_root() -> Path:
    return data_root() / "pack-staging"


def export_root() -> Path:
    """``<plugin data>/pack-exports/`` — resolved without creating anything.

    Writers call ``mkdir`` themselves before writing; the download route uses the same definition
    for containment, and a refused download must not leave a directory behind. Same path
    ``data_root()`` resolves to.
    """
    return db.store_root() / "pack-exports"


#: Process-level staging registry, keyed by resolved root. A grant lives in this object only,
#: which is why a restart turns an unknown ``staged_id`` into an explicit refusal rather than a
#: guessed file.
_STAGING: dict[str, StagingArea] = {}


def staging() -> StagingArea:
    root = staging_root().resolve()
    key = str(root)
    area = _STAGING.get(key)
    if area is None:
        area = StagingArea(root)
        _STAGING[key] = area
    return area


def library() -> PackLibrary:
    return PackLibrary(library_root())


def grant_local_file(path: str | Path) -> str:
    """Register a host-held local archive and return the ``staged_id``.

    Called by the host adapter (native picker / bundled installer / CLI), never over the wire.
    """
    return staging().grant_local_file(path)


# ── small helpers ──────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _payload_hash(method: str, payload: Mapping[str, Any]) -> str:
    return _canonical_hash({"method": method, "payload": dict(payload)})


def _rejected(message: str, reason: str, **details: Any) -> RpcError:
    return RpcError.of("PACK_REJECTED", message, reason=reason, **details)


def _row(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return connection.execute(sql, params).fetchone()


def _idempotent_lookup(
    connection: sqlite3.Connection, key: str | None, method: str, payload_hash: str
) -> tuple[int, dict[str, Any]] | None:
    if not key:
        return None
    row = _row(
        connection,
        "SELECT payload_hash, method, response_json FROM idempotency_keys WHERE key = ?",
        (key,),
    )
    if row is None:
        return None
    if row["payload_hash"] != payload_hash or row["method"] != method:
        raise RpcError.of(
            "IDEMPOTENCY_CONFLICT",
            "this idempotency key was already used with a different payload.",
            key=key,
            method=row["method"],
        )
    stored = json.loads(row["response_json"] or "{}")
    return int(stored.get("revision", 0)), dict(stored.get("result") or {})


def _remember(
    connection: sqlite3.Connection,
    key: str | None,
    method: str,
    payload_hash: str,
    operation_id: str,
    revision: int,
    result: dict[str, Any],
) -> None:
    if not key:
        return
    connection.execute(
        "INSERT INTO idempotency_keys (key, payload_hash, method, operation_id, response_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            key,
            payload_hash,
            method,
            operation_id,
            json.dumps({"revision": revision, "result": result}, sort_keys=True),
            _now(),
        ),
    )


# ── pack → course projection ───────────────────────────────────────────────


def _stimulus_text(check: Mapping[str, Any]) -> str:
    return str(check.get("stimulus") or "").strip()


def audit_check_for_import(check: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Deterministic pre-import audit of one manifest check. Never a human review.

    A check becomes gradable only when *this* audit passes, which includes the author's own
    ``audit_state`` never being ``failed``. The declared state is preserved alongside the
    automated one, so a caller can see that no human review was claimed (``trust.labels`` still
    has no ``human_review_recorded``).
    """
    problems: list[str] = []
    stimulus = _stimulus_text(check)
    reference = str(check.get("reference_answer") or "").strip()
    rubric = [str(item).strip() for item in check.get("rubric") or [] if str(item).strip()]
    if not stimulus:
        problems.append("empty stimulus")
    if not reference:
        problems.append("empty reference answer")
    if not rubric:
        problems.append("empty rubric")
    if reference and stimulus and reference.casefold() in stimulus.casefold():
        problems.append("reference answer appears in the stimulus")
    alternatives = [str(item) for item in check.get("accepted_alternatives") or []]
    # cb.projection R5: the reference answer is already an accepted form, so declaring no
    # alternative is not a flaw. Fail only when non-empty alternatives all repeat it.
    non_empty_alternatives = [alternative for alternative in alternatives if alternative.strip()]
    if reference and non_empty_alternatives and not any(
        alternative.strip().casefold() != reference.casefold()
        for alternative in non_empty_alternatives
    ):
        problems.append("accepted alternatives do not add an accepted form")
    # cb.projection R6: an author's declaration can never grant gradability and may always
    # refuse it. Grading an item its own author marked failed would make the stored spec
    # contradict its provenance.
    if str(check.get("audit_state") or "unreviewed") == "failed":
        problems.append("the pack declares this check failed its own audit")
    return (not problems), problems


def check_spec_from_pack_check(
    check: Mapping[str, Any], *, recipe: str
) -> dict[str, Any] | None:
    """Project a manifest check into the kernel's ``check_spec`` shape.

    ``None`` means "not gradable here": a parent pack never yields a gradable spec (a parent
    observes, the harness does not grade a child), and a check that fails the deterministic
    audit stays ungraded instead of shipping a flawed item.
    """
    if recipe == "parent":
        return None
    passed, _problems = audit_check_for_import(check)
    if not passed:
        return None
    reference_answer = str(check["reference_answer"]).strip()
    alternatives = [str(item) for item in check.get("accepted_alternatives") or []]
    evidence_target = str(check.get("evidence_target") or "recall")
    open_targets = {"production", "transfer"}
    # Every imported check declares its lane here, explicitly. A production or transfer check is
    # not assumed closed-form: its reference answer is one model answer, not the accepted set a
    # deterministic comparison needs, so it declares the open lane and waits behind the same gate
    # as any other model assessment (docs/GRADING-LANES.md, CB-QA-11).
    if evidence_target in open_targets:
        reference = validators.seal_reference({"kind": "rubric_only"})
    else:
        answers = [reference_answer] + [item for item in alternatives if item not in (reference_answer,)]
        reference = validators.seal_reference({"kind": "exact", "answers": answers})
    rubric_items = [
        {"id": f"c{index}", "description": str(text)}
        for index, text in enumerate(check.get("rubric") or [], start=1)
    ]
    return {
        "audit_state": "passed",
        "audit_source": "import_automated_audit",
        "declared_audit_state": str(check.get("audit_state") or "unreviewed"),
        "stimulus": {"prompt": _stimulus_text(check)},
        "reference": reference,
        "rubric": {
            "construct": evidence_target,
            "pass_rule": "all",
            "criteria": rubric_items,
        },
        "locale": check.get("locale"),
    }


def objective_criteria(objective: Mapping[str, Any], *, recipe: str) -> list[dict[str, Any]]:
    """Criteria list for ``objectives.evidence_criteria_json`` (kernel-owned convention)."""
    criteria: list[dict[str, Any]] = [
        {
            "id": "pack_objective",
            "description": str(objective["objective_id"]),
            "pack_objective_id": str(objective["objective_id"]),
        }
    ]
    for index, text in enumerate(objective.get("evidence_criteria") or [], start=1):
        criteria.append({"id": f"target{index}", "description": str(text)})
    for check in objective.get("checks") or []:
        spec = check_spec_from_pack_check(check, recipe=recipe)
        if spec is None:
            criteria.append(
                {
                    "id": str(check.get("check_id") or "check"),
                    "description": "parent observation: not machine-graded"
                    if recipe == "parent"
                    else "check withheld: failed the import audit",
                    "check_id": str(check.get("check_id")),
                    "check_spec_withheld": True,
                }
            )
            continue
        criteria.append(
            {
                "id": str(check["check_id"]),
                "description": f"automated audit of {check['check_id']}",
                "check_spec": spec,
            }
        )
    return criteria


def course_goal(manifest: Mapping[str, Any]) -> str:
    """A goal derived from the pack itself; never invented prose about the learner."""
    objectives = manifest.get("objectives") or []
    first = str(objectives[0]["title"]) if objectives else str(manifest["title"])
    return (
        f"Work through the published pack {manifest['pack_id']} {manifest['pack_version']}: "
        f"{first} (and {max(len(objectives) - 1, 0)} more objective(s))."
    )


def course_dials(manifest: Mapping[str, Any]) -> dict[str, Any]:
    dials = copy.deepcopy(dict(manifest.get("default_dials") or {}))
    if manifest["recipe"] == "parent":
        # A parent pack is a lesson blueprint. The harness never grades a child, so the recipe's
        # assessment dial is pinned off here instead of trusting a manifest value.
        dials["assessment"] = "none"
        dials.setdefault("autonomy", "guided")
    dials["recipe_source"] = "pack_manifest"
    return dials


def _plan_hash(connection: sqlite3.Connection, plan_id: str) -> str:
    """Same canonical plan hash the kernel computes (``coursebook.domain._plan_hash``)."""
    plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (plan_id,))
    if plan is None:
        raise RpcError.of("NOT_FOUND", "plan not found", plan_id=plan_id)
    objectives = connection.execute(
        "SELECT id, ordinal, title, evidence_target, evidence_criteria_json, version"
        " FROM objectives WHERE plan_id = ? ORDER BY ordinal",
        (plan_id,),
    ).fetchall()
    payload = {
        "course_id": plan["course_id"],
        "version": plan["version"],
        "schedule": json.loads(plan["schedule_json"] or "{}"),
        "objectives": [
            {
                "id": row["id"],
                "ordinal": row["ordinal"],
                "title": row["title"],
                "evidence_target": row["evidence_target"],
                "evidence_criteria": json.loads(row["evidence_criteria_json"] or "[]"),
                "version": row["version"],
            }
            for row in objectives
        ],
    }
    return _canonical_hash(payload)


# ── validation and audit before any write ──────────────────────────────────


def validate_and_audit(staged: archive.StagedPack) -> dict[str, Any]:
    """Full pre-write gate for a staged pack. Raises :class:`PackRejected`."""
    manifest = staged.manifest
    packs.validate_manifest(manifest)
    packs.validate_minima(manifest)
    packs.verify_content_hash(manifest)
    packs.require_minimum_version(manifest, __version__)
    if str(manifest.get("recipe")) not in _RECIPES:
        raise PackRejected(f"unknown recipe {manifest.get('recipe')!r}")
    problems = packs.audit_bundle(staged.directory)
    if problems:
        raise PackRejected("pack content audit failed: " + "; ".join(problems))
    # Authoring bound: not a refusal. A lesson section above the contract-derived 4,000,000
    # characters would never render; warn with the file and its measured length so the failure is
    # legible, then let ``segments.audit_objective_texts`` below make the actual refusal.
    for message in packs.audit_warnings(staged.directory, manifest=manifest):
        warnings.warn(message, packs.PackAuthoringWarning, stacklevel=2)
    # A lesson page returns segments of at most 8,000 characters (cb.rpc v6). Long section files
    # are split at import; a lesson that could never fit the page's segment budget is refused here,
    # before the first database write, naming the file and its length (D1).
    segments.audit_objective_texts(manifest, staged.directory)
    # A pack may not hold content for a role it does not declare, and no manifest may carry a
    # private field. Both are checked on the document itself, not only on the archive.
    leaked = packs.contains_private_fields(manifest)
    if leaked:
        raise PackRejected(f"pack manifest carries private fields: {sorted(set(leaked))}")
    return manifest


_RECIPES = ("one_off", "casual", "committed", "companion", "parent")


def _pack_row_id(pack_id: str, version: str) -> str:
    digest = hashlib.sha256(f"{pack_id}\x00{version}".encode("utf-8")).hexdigest()[:24]
    return f"pck_{digest}"


def _installed_record(pack_id: str, version: str) -> dict[str, Any] | None:
    for record in library().list():
        if record.get("pack_id") == pack_id and record.get("version") == version:
            return record
    return None


def _frozen(connection: sqlite3.Connection, pack_id: str) -> bool:
    row = connection.execute(
        "SELECT state FROM packs WHERE pack_id = ? ORDER BY installed_at DESC LIMIT 1", (pack_id,)
    ).fetchone()
    return row is not None and str(row["state"]) == "frozen"


# ── import ─────────────────────────────────────────────────────────────────


def _import_job_start(manifest: Mapping[str, Any], mode: str) -> str | None:
    """Journal the import so an interruption is visible in ``jobs.list`` (never silent)."""
    try:
        with db.transaction() as connection:
            job_id = _new_id("job")
            now = _now()
            brief = json.dumps(
                {
                    "kind": "import",
                    "pack_id": manifest["pack_id"],
                    "pack_version": manifest["pack_version"],
                    "mode": mode,
                },
                sort_keys=True,
            )
            connection.execute(
                "INSERT INTO jobs (id, kind, state, operation_id, brief_json, checkpoint_json,"
                " attempt_id, lease_owner, lease_expires_at, progress_json, error_json, created_at,"
                " updated_at) VALUES (?, 'import', 'running', ?, ?, '{}', ?, NULL, NULL, '{}', '{}', ?, ?)",
                (job_id, f"pack-import-{job_id}", brief, f"jat_{job_id[-12:]}", now, now),
            )
            return job_id
    except Exception:  # noqa: BLE001 - journaling must not block a legitimate import
        return None


def _import_job_finish(job_id: str | None, state: str, error: str | None = None) -> None:
    if not job_id:
        return
    try:
        with db.transaction() as connection:
            if error is None:
                connection.execute(
                    "UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?", (state, _now(), job_id)
                )
            else:
                connection.execute(
                    "UPDATE jobs SET state = ?, error_json = ?, updated_at = ? WHERE id = ?",
                    (state, json.dumps({"message": error[:500]}), _now(), job_id),
                )
    except Exception:  # noqa: BLE001
        pass


def _write_lesson_page(
    connection: sqlite3.Connection,
    *,
    enrollment_id: str,
    objective_row_id: str,
    objective: Mapping[str, Any],
    staged_directory: Path,
) -> None:
    """Materialize the pack's own section text as a durable lesson page.

    The learner reads the authored content; nothing is generated or paraphrased on import. A
    section file longer than the ``cb.rpc`` per-segment cap is cut into ordered pieces at paragraph
    (then line, then word) boundaries — see :mod:`coursebook.segments` — because one segment over
    the cap made the whole lesson page unreadable.
    """
    run_id = _new_id("run")
    now = _now()
    connection.execute(
        "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
        " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, ?, ?, ?)",
        (run_id, enrollment_id, objective_row_id, now, now, now),
    )
    limit = segments.max_segment_chars()
    ordinal = 0
    for section in objective.get("sections") or []:
        path = str(section.get("path") or "")
        if not path:
            continue
        candidate = staged_directory / path
        if not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8")
        for piece in segments.split_text(text, limit):
            ordinal += 1
            connection.execute(
                "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
                " VALUES (?, ?, ?, 'teaching', ?, ?)",
                (_new_id("seg"), run_id, ordinal, piece, now),
            )
    for check in objective.get("checks") or []:
        ordinal += 1
        connection.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
            " VALUES (?, ?, ?, 'check_prompt', ?, ?)",
            (_new_id("seg"), run_id, ordinal, _stimulus_text(check), now),
        )


def _write_sources(connection: sqlite3.Connection, course_id: str, manifest: Mapping[str, Any]) -> None:
    now = _now()
    for index, source in enumerate(manifest.get("sources") or [], start=1):
        connection.execute(
            "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at,"
            " support_status, claim_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (
                _new_id("src"),
                course_id,
                source.get("url"),
                str(source["title"]),
                str(source["source_type"]),
                source.get("published_at"),
                source.get("fetched_at") or now,
                str(source.get("support_status") or "unassessed"),
                now,
            ),
        )


def pack_preview(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``pack.preview``: manifest + integrity + the four separate trust labels.

    Nothing is summarised away: author, outcomes, checks, sources/support, licence, notes and
    media size all travel inside ``manifest``/``integrity``. The response carries no verdict.
    """
    try:
        staged = staging().stage(payload["staged_id"])
        manifest = validate_and_audit(staged)
    except PackRejected as exc:
        raise _rejected(str(exc), "pack_not_importable") from exc
    document = packs.preview(
        manifest,
        integrity=staged.integrity,
        automated_checks_passed=True,
    )
    return 0, document


def pack_import(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``pack.import``: adopt immutable content and cut (or resume) one learner's course."""
    db.ensure_schema()
    method = "pack.import"
    mode = str(payload["mode"])
    key = envelope.get("idempotency_key")
    payload_hash = _payload_hash(method, payload)

    # A double-submitted import must not touch staging twice: the first call consumed the grant.
    if key:
        with db.read() as connection:
            replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay

    try:
        staged = staging().stage(payload["staged_id"])
        manifest = validate_and_audit(staged)
    except PackRejected as exc:
        raise _rejected(str(exc), "pack_not_importable") from exc

    pack_id = str(manifest["pack_id"])
    version = str(manifest["pack_version"])
    recipe = str(manifest["recipe"])

    installed = _installed_record(pack_id, version)
    if installed is not None and installed.get("manifest_hash") not in (None, str(manifest["content_hash"])):
        raise _rejected(
            "this version is already installed with different content; a published version is immutable",
            "version_immutable",
            pack_id=pack_id,
            pack_version=version,
        )

    with db.read() as connection:
        if _frozen(connection, pack_id):
            raise RpcError.of(
                "POLICY_VIOLATION",
                "this pack was deleted (frozen); its evidence is kept but it cannot be imported again.",
                pack_id=pack_id,
            )

    job_id = _import_job_start(manifest, mode)
    try:
        # Filesystem first (never inside a transaction): adopt is atomic and idempotent.
        record = library().adopt(staged, source="local")
        adopted_directory = Path(str(record["directory"]))
        with db.transaction() as connection:
            replay = _idempotent_lookup(connection, key, method, payload_hash)
            if replay is not None:
                _import_job_finish(job_id, "completed")
                return replay

            pack_row_id = _pack_row_id(pack_id, version)
            now = _now()
            pack_row = _row(connection, "SELECT * FROM packs WHERE id = ?", (pack_row_id,))
            if pack_row is None:
                connection.execute(
                    "INSERT INTO packs (id, pack_id, version, manifest_hash, license_json, derived_from,"
                    " source, installed_at, revision, state) VALUES (?, ?, ?, ?, ?, ?, 'local', ?, 0, 'installed')",
                    (
                        pack_row_id,
                        pack_id,
                        version,
                        str(manifest["content_hash"]),
                        json.dumps(manifest.get("license") or {}, sort_keys=True),
                        (manifest.get("derived_from") or {}).get("pack_id") if manifest.get("derived_from") else None,
                        now,
                    ),
                )

            if mode == "resume":
                existing = connection.execute(
                    "SELECT e.id AS enrollment_id, e.revision AS revision, c.id AS course_id"
                    " FROM enrollments e JOIN courses c ON c.id = e.course_id"
                    " JOIN packs p ON p.id = c.pack_id"
                    " WHERE p.pack_id = ? AND e.status != 'archived'"
                    " ORDER BY e.created_at DESC, e.rowid DESC LIMIT 1",
                    (pack_id,),
                ).fetchone()
                if existing is not None:
                    result = {
                        "pack_id": pack_id,
                        "course_id": existing["course_id"],
                        "enrollment_id": existing["enrollment_id"],
                        "revision": int(existing["revision"]),
                    }
                    _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), result["revision"], result)
                    _import_job_finish(job_id, "completed")
                    return result["revision"], result

            course_id = _new_id("crs")
            connection.execute(
                "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status, pack_id,"
                " revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, 0, ?, ?)",
                (
                    course_id,
                    str(manifest["title"]),
                    recipe,
                    course_goal(manifest),
                    manifest.get("locale"),
                    json.dumps(course_dials(manifest), sort_keys=True),
                    pack_row_id,
                    now,
                    now,
                ),
            )
            _write_sources(connection, course_id, manifest)

            plan_id = _new_id("pln")
            connection.execute(
                "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json, created_at,"
                " approved_at) VALUES (?, ?, 1, 'approved', NULL, ?, ?, ?)",
                (plan_id, course_id, json.dumps({"source": "pack", "pack_version": version}, sort_keys=True), now, now),
            )
            objective_rows: list[tuple[str, Mapping[str, Any]]] = []
            for objective in sorted(manifest["objectives"], key=lambda item: int(item["ordinal"])):
                objective_row_id = _new_id("obj")
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target,"
                    " evidence_criteria_json, state, version, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, 'not_started', 1, ?)",
                    (
                        objective_row_id,
                        plan_id,
                        int(objective["ordinal"]),
                        str(objective["title"]),
                        str(objective["evidence_target"]),
                        json.dumps(objective_criteria(objective, recipe=recipe), sort_keys=True),
                        now,
                    ),
                )
                objective_rows.append((objective_row_id, objective))
            plan_hash = _plan_hash(connection, plan_id)
            connection.execute("UPDATE plans SET plan_hash = ? WHERE id = ?", (plan_hash, plan_id))

            enrollment_id = _new_id("enr")
            connection.execute(
                "INSERT INTO enrollments (id, course_id, learner_label, status, revision, created_at,"
                " updated_at) VALUES (?, ?, NULL, 'active', 0, ?, ?)",
                (enrollment_id, course_id, now, now),
            )
            for objective_row_id, objective in objective_rows:
                _write_lesson_page(
                    connection,
                    enrollment_id=enrollment_id,
                    objective_row_id=objective_row_id,
                    objective=objective,
                    staged_directory=adopted_directory,
                )

            result = {
                "pack_id": pack_id,
                "course_id": course_id,
                "enrollment_id": enrollment_id,
                "revision": 0,
            }
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
        _import_job_finish(job_id, "completed")
        return 0, result
    except RpcError:
        _import_job_finish(job_id, "failed", "refused before completion")
        raise
    except PackRejected as exc:
        _import_job_finish(job_id, "failed", str(exc))
        raise _rejected(str(exc), "pack_not_importable") from exc
    except Exception as exc:  # noqa: BLE001 - journal it, then let the dispatcher shape the error
        _import_job_finish(job_id, "failed", type(exc).__name__)
        raise


# ── export ─────────────────────────────────────────────────────────────────


def export_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    """Allowlisted export options. Anything else is refused, never ignored."""
    allowed = {"expected_content_hash"}
    supplied = dict(options or {})
    unknown = sorted(set(supplied) - allowed)
    if unknown:
        raise _rejected(f"unknown export option(s): {unknown}", "unknown_option")
    expected = supplied.get("expected_content_hash")
    if expected is not None and not re.match(r"^sha256:[a-f0-9]{64}$", str(expected)):
        raise _rejected("expected_content_hash must be sha256:<64 hex>", "bad_option")
    return {"expected_content_hash": expected}


def _rehash_written_archive(path: Path) -> dict[str, Any]:
    """Read an exported archive back and verify its own manifest hash. Never trust the writer."""
    with zipfile.ZipFile(path) as bundle:
        names = bundle.namelist()
        manifests = [name for name in names if name.count("/") == 1 and name.endswith("/pack.json")]
        if len(manifests) != 1:
            raise RpcError.of("INTERNAL_ERROR", "exported archive does not hold exactly one manifest")
        manifest = json.loads(bundle.read(manifests[0]).decode("utf-8"))
        for name in names:
            if name in manifests:
                continue
            if name.count("/") < 2:
                raise RpcError.of("INTERNAL_ERROR", "exported archive has an entry outside its content set")
    packs.verify_content_hash(manifest)
    return manifest


def review_export_tree(manifest: Mapping[str, Any], files: Mapping[str, bytes]) -> list[dict[str, Any]]:
    """The complete file/content review: every included file, its role, size, hash and notes."""
    entries = []
    for record in manifest["files"]:
        path = str(record["path"])
        entries.append(
            {
                "path": path,
                "role": str(record["role"]),
                "mime": str(record["mime"]),
                "bytes": int(record["bytes"]),
                "sha256": str(record["sha256"]),
                "description": record.get("description"),
                "text_equivalent": record.get("text_equivalent"),
                "present": path in files,
            }
        )
    return entries


def pack_export(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``pack.export``: rebuild the pack from its stored content and record an export artifact.

    The exported document is assembled field-by-field from :func:`coursebook.packs.export_allowlist`,
    so no transcript, attempt, notebook entry, provider setting or path can ride along. The
    returned ``content_hash`` is recomputed from the written archive.
    """
    db.ensure_schema()
    options = export_options(payload.get("options"))
    with db.read() as connection:
        enrollment = _row(connection, "SELECT * FROM enrollments WHERE id = ?", (payload["enrollment_id"],))
        if enrollment is None:
            raise RpcError.of("NOT_FOUND", "enrollment not found", enrollment_id=payload["enrollment_id"])
        course = _row(connection, "SELECT * FROM courses WHERE id = ?", (enrollment["course_id"],))
        if course is None or course["pack_id"] is None:
            raise RpcError.of(
                "POLICY_VIOLATION",
                "this course was not imported from a pack; package it from an authored export instead.",
                reason="course_not_pack_backed",
            )
        pack_row = _row(connection, "SELECT * FROM packs WHERE id = ?", (course["pack_id"],))
        if pack_row is None:
            raise RpcError.of("NOT_FOUND", "the pack record for this course is missing", pack_id=course["pack_id"])

    pack_id = str(pack_row["pack_id"])
    version = str(pack_row["version"])
    try:
        manifest, files = library().read(pack_id, version)
    except PackRejected as exc:
        raise _rejected(str(exc), "pack_content_missing", pack_id=pack_id, pack_version=version) from exc

    if str(manifest["content_hash"]) != str(pack_row["manifest_hash"]):
        raise _rejected(
            "the installed pack content no longer matches the hash recorded at import",
            "content_hash_drift",
            pack_id=pack_id,
            pack_version=version,
        )
    problems = packs.audit_bundle(library().path_for(pack_id, version))
    if problems:
        raise _rejected("pack content audit failed before export: " + "; ".join(problems), "content_audit_failed")

    try:
        document, exported = packs.build_export(manifest, files)
    except PackRejected as exc:
        raise _rejected(f"export refused: {exc}", "export_not_exportable") from exc
    review = review_export_tree(document, exported)
    expected = options["expected_content_hash"]
    if expected is not None and expected != str(document["content_hash"]):
        raise RpcError.of(
            "DELETE_SCOPE_STALE",
            "the installed pack content changed since it was reviewed; nothing was exported.",
            current_data_scope_hash=str(document["content_hash"]),
        )

    export_dir = export_root()
    export_dir.mkdir(parents=True, exist_ok=True)
    digest = str(document["content_hash"]).split(":", 1)[1]
    destination = export_dir / f"{pack_id}-{version}-{digest[:16]}.zip"
    temporary = destination.with_name(destination.stem + ".partial.zip")
    try:
        archive.write_archive(temporary, document, exported)
    except PackRejected as exc:
        temporary.unlink(missing_ok=True)
        raise _rejected(f"the export archive could not be written: {exc}", "export_write_failed") from exc
    os.replace(temporary, destination)

    # Verify the bytes that will be downloaded, not the bytes we think we wrote.
    try:
        written_manifest = _rehash_written_archive(destination)
    except PackRejected as exc:
        destination.unlink(missing_ok=True)
        raise _rejected(f"the exported archive failed verification: {exc}", "export_verification_failed") from exc
    if str(written_manifest["content_hash"]) != str(document["content_hash"]):
        destination.unlink(missing_ok=True)
        raise RpcError.of("INTERNAL_ERROR", "the exported archive does not re-hash to its manifest")

    leaked = packs.contains_private_fields(document)
    if leaked:  # defence in depth: build_export already refuses
        destination.unlink(missing_ok=True)
        raise RpcError.of("INTERNAL_ERROR", "export carried a private field and was discarded")

    size = destination.stat().st_size
    file_digest = "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest()
    with db.transaction() as connection:
        # ``artifacts`` is unique on (content_hash, kind): a second export of unchanged bytes is
        # the same artifact, not a new one. Reuse the row and count the reference; only content
        # that actually changed produces a new digest and therefore a new row.
        existing = _row(
            connection,
            "SELECT * FROM artifacts WHERE content_hash = ? AND kind = 'export'",
            (file_digest,),
        )
        if existing is not None:
            artifact_id = str(existing["id"])
            recorded = Path(str(existing["path"]))
            if not recorded.is_file() or recorded.stat().st_size != size:
                # The row outlived its file (reconciliation, manual cleanup): repoint it at the
                # archive just verified, so a reused artifact always resolves to real bytes.
                connection.execute(
                    "UPDATE artifacts SET path = ?, bytes = ?, ref_count = ref_count + 1 WHERE id = ?",
                    (str(destination), size, artifact_id),
                )
            else:
                connection.execute(
                    "UPDATE artifacts SET ref_count = ref_count + 1 WHERE id = ?", (artifact_id,)
                )
        else:
            artifact_id = _new_id("art")
            connection.execute(
                "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime, provenance_json,"
                " ref_count, created_at) VALUES (?, ?, 'export', ?, ?, ?, 'application/zip', ?, 1, ?)",
                (
                    artifact_id,
                    course["id"],
                    file_digest,
                    str(destination),
                    size,
                    json.dumps(
                        {
                            "generator": "coursebook.pack_flow",
                            "model": None,
                            "prompt_hash": None,
                            "source_ids": [],
                            "notes": (
                                f"export of {pack_id} {version} from enrollment {enrollment['id']}; "
                                f"pack content_hash {document['content_hash']}"
                            ),
                        },
                        sort_keys=True,
                    ),
                    _now(),
                ),
            )
    return 0, {
        "artifact_id": artifact_id,
        "content_hash": str(document["content_hash"]),
        "file_count": len(review),
        "bytes": size,
    }


# ── authored parent export (cb.rpc v6) ────────────────────────────────────


def _blocked(reason: str, message: str, **details: Any) -> RpcError:
    """A policy refusal the studio renders as an export blocker."""
    return RpcError.of("POLICY_VIOLATION", message, reason=reason, **details)


def _adopt_artifact(
    connection,
    *,
    course_id: str,
    kind: str,
    mime: str,
    path: Path,
    data_hash: str,
    size: int,
    notes: str,
    generator: str = "coursebook.parent_export",
) -> str:
    """Record (or reuse) one artifact row for bytes that already exist on disk.

    ``artifacts`` is unique on ``(content_hash, kind)``, so exporting unchanged bytes twice
    reuses the row and only bumps ``ref_count``. Same rule as ``pack.export`` (CB-013).
    """
    existing = _row(
        connection,
        "SELECT * FROM artifacts WHERE content_hash = ? AND kind = ?",
        (data_hash, kind),
    )
    if existing is not None:
        artifact_id = str(existing["id"])
        recorded = Path(str(existing["path"]))
        if not recorded.is_file() or recorded.stat().st_size != size:
            connection.execute(
                "UPDATE artifacts SET path = ?, bytes = ?, ref_count = ref_count + 1 WHERE id = ?",
                (str(path), size, artifact_id),
            )
        else:
            connection.execute(
                "UPDATE artifacts SET ref_count = ref_count + 1 WHERE id = ?", (artifact_id,)
            )
        return artifact_id
    artifact_id = _new_id("art")
    connection.execute(
        "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime, provenance_json,"
        " ref_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
        (
            artifact_id,
            course_id,
            kind,
            data_hash,
            str(path),
            size,
            mime,
            json.dumps(
                {
                    "generator": generator,
                    "model": None,
                    "prompt_hash": None,
                    "source_ids": [],
                    "notes": notes,
                },
                sort_keys=True,
            ),
            _now(),
        ),
    )
    return artifact_id


def _artifact_ref(connection, artifact_id: str) -> dict[str, Any]:
    row = _row(connection, "SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    if row is None:
        raise RpcError.of("INTERNAL_ERROR", "an exported artifact row disappeared inside its own transaction")
    return {
        "artifact_id": str(row["id"]),
        "kind": str(row["kind"]),
        "mime": str(row["mime"]),
        "bytes": int(row["bytes"]),
        "content_hash": str(row["content_hash"]),
    }


def parent_export(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``parent.export``: authored pack + low-ink selectable-text PDF.

    Refusal is the feature. The export runs only while the **active** ``final_approvals`` row's
    ``content_hash`` equals the recomputed one; otherwise nothing is written and the caller gets
    ``POLICY_VIOLATION`` with the same reason the blueprint's ``export.blocked_reason`` shows.

    Work order (PREBUILD_SPEC §12 / AUDIT R2): short read → build bytes with **no transaction
    open** → short write transaction that re-checks the hash and adopts the artifacts. A content
    change between the two re-checks discards the files and refuses.
    """
    db.ensure_schema()
    method = "parent.export"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    if not key:
        raise RpcError.of("VALIDATION_FAILED", "parent.export requires an idempotency_key.",
                          field="idempotency_key")
    formats = [str(item) for item in (payload.get("formats") or ["pack", "pdf"])]
    want_pdf = "pdf" in formats
    enrollment_id = str(payload["enrollment_id"])

    with db.read() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment = _row(connection, "SELECT * FROM enrollments WHERE id = ?", (enrollment_id,))
        if enrollment is None:
            raise RpcError.of("NOT_FOUND", "enrollment not found", enrollment_id=enrollment_id)
        course = _row(connection, "SELECT * FROM courses WHERE id = ?", (enrollment["course_id"],))
        if course is None or course["status"] == "deleted":
            raise RpcError.of("NOT_FOUND", "course not found", course_id=enrollment["course_id"])
        if course["pack_id"] is not None:
            raise _blocked(
                "course_pack_backed",
                "this course was imported from a pack; use pack.export for its stored content.",
                course_id=str(course["id"]),
            )
        plan = authoring.current_plan(connection, str(course["id"]))
        if plan is None or str(plan["state"]) != "approved":
            raise _blocked(
                "plan_not_approved",
                "the plan must be approved before the authored course can be exported.",
                course_id=str(course["id"]),
            )
        approval = _row(
            connection,
            "SELECT * FROM final_approvals WHERE course_id = ? AND state = 'active'"
            " ORDER BY approved_at DESC LIMIT 1",
            (course["id"],),
        )
        if approval is None:
            raise _blocked(
                "no_final_approval",
                "the generated lessons have not been approved; approve them before exporting.",
                course_id=str(course["id"]),
            )
        plan_digest = authoring.plan_hash(connection, plan)
        composed = authoring.sections(connection, course, plan)
        if not authoring.ready_sections(composed):
            raise _blocked(
                "no_generated_content",
                "this course has no generated lesson content to export.",
                course_id=str(course["id"]),
            )
        current_content = authoring.content_hash(
            str(course["id"]), str(plan["id"]), plan_digest, composed
        )
        if str(approval["content_hash"]) != current_content:
            raise _blocked(
                "changes_need_review",
                "the authored content changed since it was approved; re-approve before exporting.",
                current_content_hash=current_content,
                approved_content_hash=str(approval["content_hash"]),
            )
        course_id = str(course["id"])
        plan_id = str(plan["id"])

    # Build and stage the bytes with no transaction open.
    try:
        with db.read() as build_connection:
            course = _row(build_connection, "SELECT * FROM courses WHERE id = ?", (course_id,))
            plan = _row(build_connection, "SELECT * FROM plans WHERE id = ?", (plan_id,))
            composed = authoring.sections(build_connection, course, plan)
            manifest, files = authoring.build_pack(build_connection, course, plan, composed)
    except authoring.AuthoredExportBlocked as exc:
        raise _blocked(exc.reason, str(exc), problems=exc.problems) from exc
    except PackRejected as exc:
        raise _blocked("export_not_exportable", f"the authored pack is not exportable: {exc}") from exc

    root = export_root()
    root.mkdir(parents=True, exist_ok=True)
    # Authoring bound, before the bytes are archived: an over-long lesson section warns here and
    # is still exported; import owns the refusal.
    packs.warn_authoring_bound(manifest, files)
    digest = str(manifest["content_hash"]).split(":", 1)[1]
    destination = root / f"{manifest['pack_id']}-{manifest['pack_version']}-{digest[:16]}.zip"
    temporary = destination.with_name(destination.stem + ".partial.zip")
    try:
        archive.write_archive(temporary, manifest, files)
        os.replace(temporary, destination)
        written = _rehash_written_archive(destination)
    except (PackRejected, OSError) as exc:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise _blocked("export_write_failed", f"the authored pack could not be written: {exc}") from exc
    if str(written["content_hash"]) != str(manifest["content_hash"]):
        destination.unlink(missing_ok=True)
        raise RpcError.of("INTERNAL_ERROR", "the exported archive does not re-hash to its manifest")

    pdf_path: Path | None = None
    if want_pdf:
        pdf_path = root / f"{manifest['pack_id']}-{manifest['pack_version']}-{digest[:16]}.pdf"
        temporary_pdf = pdf_path.with_name(pdf_path.stem + ".partial.pdf")
        try:
            temporary_pdf.write_bytes(authoring.pdf_bytes(course, plan, composed))
            os.replace(temporary_pdf, pdf_path)
        except OSError as exc:
            destination.unlink(missing_ok=True)
            temporary_pdf.unlink(missing_ok=True)
            raise _blocked("export_write_failed", f"the handout PDF could not be written: {exc}") from exc

    # Read the written bytes and digest them with no transaction open: the adopt transaction must
    # stay short (no file I/O under BEGIN IMMEDIATE).
    zip_bytes = destination.read_bytes()
    pack_hash = packs.file_sha256(zip_bytes)
    pdf_data: bytes | None = None
    if pdf_path is not None:
        pdf_data = pdf_path.read_bytes()

    now = _now()
    export_id = _new_id("exp")
    try:
        with db.transaction() as connection:
            replay = _idempotent_lookup(connection, key, method, payload_hash)
            if replay is not None:
                # A racing retry already adopted this export; drop our staged duplicate path only.
                return replay
            # Re-check against storage: the approval may have been superseded while we wrote bytes.
            enrollment = _row(connection, "SELECT * FROM enrollments WHERE id = ?", (enrollment_id,))
            course_row = _row(connection, "SELECT * FROM courses WHERE id = ?", (enrollment["course_id"],))
            plan_row = _row(connection, "SELECT * FROM plans WHERE id = ?", (plan_id,))
            active = _row(
                connection,
                "SELECT * FROM final_approvals WHERE course_id = ? AND state = 'active'"
                " ORDER BY approved_at DESC LIMIT 1",
                (course_row["id"],),
            )
            fresh = authoring.sections(connection, course_row, plan_row)
            fresh_hash = authoring.content_hash(
                str(course_row["id"]), str(plan_row["id"]),
                authoring.plan_hash(connection, plan_row), fresh,
            )
            if active is None or str(active["content_hash"]) != fresh_hash:
                raise _blocked(
                    "changes_need_review",
                    "the authored content changed while exporting; nothing was adopted.",
                    current_content_hash=fresh_hash,
                )
            pack_artifact = _adopt_artifact(
                connection,
                course_id=str(course_row["id"]),
                kind="pack",
                mime="application/zip",
                path=destination,
                data_hash=pack_hash,
                size=len(zip_bytes),
                notes=f"authored parent pack for course {course_row['id']}; manifest {manifest['content_hash']}",
            )
            artifact_ids = [pack_artifact]
            if pdf_path is not None:
                pdf_bytes_written = pdf_data or b""
                artifact_ids.append(
                    _adopt_artifact(
                        connection,
                        course_id=str(course_row["id"]),
                        kind="pdf",
                        mime="application/pdf",
                        path=pdf_path,
                        data_hash=packs.file_sha256(pdf_bytes_written),
                        size=len(pdf_bytes_written),
                        notes=(
                            "selectable-text low-ink handout for course "
                            f"{course_row['id']}; manifest {manifest['content_hash']}"
                        ),
                    )
                )
            export_artifact = _adopt_artifact(
                connection,
                course_id=str(course_row["id"]),
                kind="export",
                mime="application/zip",
                path=destination,
                data_hash=pack_hash,
                size=len(zip_bytes),
                notes=(
                    f"parent.export of course {course_row['id']} from enrollment {enrollment['id']}; "
                    f"content_hash {fresh_hash}"
                ),
            )
            artifact_ids.append(export_artifact)
            result = {
                "export_id": export_id,
                "pack": {
                    "pack_id": str(manifest["pack_id"]),
                    "pack_version": str(manifest["pack_version"]),
                    "manifest_hash": str(manifest["content_hash"]),
                },
                "files": [
                    {
                        "role": str(record["role"]),
                        "name": str(record["path"]),
                        "sha256": str(record["sha256"]),
                        "bytes": int(record["bytes"]),
                        "mime": str(record["mime"]),
                    }
                    for record in manifest["files"]
                ],
                "artifacts": [_artifact_ref(connection, artifact_id) for artifact_id in artifact_ids],
                "content_hash": fresh_hash,
                "exported_at": now,
            }
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    except RpcError:
        destination.unlink(missing_ok=True)
        if pdf_path is not None:
            pdf_path.unlink(missing_ok=True)
        raise
    return 0, result


# ── general authored export (cb.rpc v13) ──────────────────────────────────

#: Rights statement paired with :data:`coursebook.parent_authoring.AUTHORED_LICENSE`. The surface
#: prints it verbatim next to the content hash, so a reader never has to infer what the file is.
AUTHORED_RIGHTS = (
    "All rights reserved by the author. This archive is a local copy for reuse; it is not a "
    "publication and it grants no redistribution right."
)

#: The no-upload statement. ``course.export`` opens no socket: it writes one file under this
#: profile's data directory and records the artifact row.
AUTHORED_NO_UPLOAD = (
    "Nothing was uploaded. The archive was written to a local file in this profile's data "
    "directory; export made no network call and recorded no telemetry."
)


def _authored_export_plan(connection, enrollment_id: str) -> dict[str, Any]:
    """Read-only: what ``course.export`` would package, or the one reason it cannot.

    The gate is exactly four questions, asked in this order and answered with one typed reason:

    1. is this a course a learner authored (not an imported pack, which has ``pack.export``)?
    2. is its current plan approved?
    3. is every lesson section generated **and** in the ``validated`` state?
    4. does the lesson text still hash to what an existing final approval bound?

    Question 4 is the hash fence for a course a parent approved in Parent Studio. Final approval
    is **not required** for ``course.export`` — the approved plan plus validated pages is the
    authority — but a stored active approval is honoured: once an adult approved this exact text,
    a changed page blocks instead of quietly shipping under the old decision. The caller's own
    reviewed hash is the second fence, enforced by ``course_export``.

    Nothing here writes: the manifest and file bytes are composed in memory so the read can show
    the exact files, hashes and content hash the export will produce.
    """
    enrollment = _row(connection, "SELECT * FROM enrollments WHERE id = ?", (enrollment_id,))
    if enrollment is None:
        raise RpcError.of("NOT_FOUND", "enrollment not found", enrollment_id=enrollment_id)
    course = _row(connection, "SELECT * FROM courses WHERE id = ?", (enrollment["course_id"],))
    if course is None or str(course["status"]) == "deleted":
        raise RpcError.of("NOT_FOUND", "course not found", course_id=enrollment["course_id"])

    plan_record: dict[str, Any] = {
        "enrollment": enrollment,
        "course": course,
        "plan": None,
        "manifest": None,
        "files": {},
        "content_hash": None,
        "sections": {"total": 0, "validated": 0},
        "blocked_reason": None,
        "blocked_message": None,
        "problems": [],
        "pack_backed": course["pack_id"] is not None,
    }

    if course["pack_id"] is not None:
        plan_record.update(
            blocked_reason="course_pack_backed",
            blocked_message=(
                "this course was imported from a pack; use pack.export for its stored content."
            ),
        )
        return plan_record

    plan = authoring.current_plan(connection, str(course["id"]))
    if plan is None or str(plan["state"]) != "approved":
        plan_record.update(
            blocked_reason="plan_not_approved",
            blocked_message="the plan must be approved before this course can be packaged.",
        )
        return plan_record
    plan_record["plan"] = plan

    composed = authoring.sections(connection, course, plan)
    plan_record["sections"] = {"total": len(composed), "validated": 0}
    if not composed:
        plan_record.update(
            blocked_reason="no_generated_content",
            blocked_message="this course has no lesson sections to package.",
        )
        return plan_record

    validated, problems = authoring.validated_sections(composed)
    plan_record["sections"]["validated"] = len(validated)
    if problems:
        plan_record.update(
            blocked_reason="lessons_not_validated",
            blocked_message=(
                "every lesson page must be in a validated state before this course can be packaged."
            ),
            problems=problems,
        )
        return plan_record

    digest = authoring.content_hash(
        str(course["id"]), str(plan["id"]), authoring.plan_hash(connection, plan), composed
    )
    plan_record["content_hash"] = digest

    approval = _row(
        connection,
        "SELECT * FROM final_approvals WHERE course_id = ? AND state = 'active'"
        " ORDER BY approved_at DESC LIMIT 1",
        (course["id"],),
    )
    if approval is not None and str(approval["content_hash"]) != digest:
        plan_record.update(
            blocked_reason="changes_need_review",
            blocked_message=(
                "the lesson text changed after it was approved; review it again before packaging."
            ),
            approved_content_hash=str(approval["content_hash"]),
        )
        return plan_record

    try:
        manifest, files = authoring.build_pack(
            connection,
            course,
            plan,
            composed,
            pack_prefix="authored",
            attribution=f"{course['title']} — authored in Coursebook.",
            contributors=[{"name": "Course author", "role": "author"}],
        )
        # Readiness must be honest about import minima: a pack that cannot be imported is not a
        # package for reuse, so the read reports the same refusal the writer would hit.
        packs.validate_minima(manifest)
    except authoring.AuthoredExportBlocked as exc:
        plan_record.update(
            blocked_reason=exc.reason, blocked_message=str(exc), problems=exc.problems
        )
        return plan_record
    except PackRejected as exc:
        plan_record.update(
            blocked_reason="export_not_exportable",
            blocked_message=f"the authored pack is not exportable: {exc}",
        )
        return plan_record

    leaked = packs.contains_private_fields(manifest)
    if leaked:  # build_manifest is allowlisted; a hit is a programming error, never a user refusal
        raise RpcError.of("INTERNAL_ERROR", f"authored pack carried private fields {leaked}")

    plan_record.update(manifest=manifest, files=files, ready=True)
    return plan_record


def _authored_file_rows(manifest: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if manifest is None:
        return []
    return [
        {
            "role": str(record["role"]),
            "name": str(record["path"]),
            "sha256": str(record["sha256"]),
            "bytes": int(record["bytes"]),
            "mime": str(record["mime"]),
        }
        for record in manifest["files"]
    ]


def _authored_plan_summary(plan: Any) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "plan_id": str(plan["id"]),
        "version": int(plan["version"]),
        "plan_hash": str(plan["plan_hash"] or ""),
        "state": str(plan["state"]),
    }


def course_export_read(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``course.export.read``: the exact files, hash, rights and blockers of a possible export.

    This is the review half of the fence. It returns the same content hash ``course.export`` will
    demand back, so the caller cannot export text it did not see.
    """
    db.ensure_schema()
    enrollment_id = str(payload["enrollment_id"])
    with db.read() as connection:
        plan_record = _authored_export_plan(connection, enrollment_id)
    manifest = plan_record.get("manifest")
    result = {
        "ready": bool(plan_record.get("ready")),
        "blocked_reason": plan_record["blocked_reason"],
        "blocked_message": plan_record["blocked_message"],
        "problems": list(plan_record["problems"])[:50],
        "pack_backed": bool(plan_record["pack_backed"]),
        "content_hash": plan_record["content_hash"],
        "files": _authored_file_rows(manifest),
        "license": dict(authoring.AUTHORED_LICENSE),
        "rights": AUTHORED_RIGHTS,
        "no_upload": AUTHORED_NO_UPLOAD,
        "plan": _authored_plan_summary(plan_record.get("plan")),
        "sections": {
            "total": int(plan_record["sections"]["total"]),
            "validated": int(plan_record["sections"]["validated"]),
        },
    }
    return 0, result


def course_export(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``course.export``: package a learner-authored course as a fresh, allowlisted pack.

    Same work order as ``parent.export`` (PREBUILD_SPEC §12): short read → build and archive the
    bytes with **no transaction open** → short write transaction that re-asks every gate question
    and adopts the artifact. A page that changed between the two reads discards the file and
    refuses with ``changes_need_review``; a reviewed hash that no longer matches refuses with
    ``DELETE_SCOPE_STALE`` before a byte is written.

    The response is built from the manifest this call produced. A stored manifest, attempt,
    notebook entry, transcript, provider setting, path or telemetry value has no route into it.
    """
    db.ensure_schema()
    method = "course.export"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    if not key:
        raise RpcError.of(
            "VALIDATION_FAILED", "course.export requires an idempotency_key.", field="idempotency_key"
        )
    enrollment_id = str(payload["enrollment_id"])
    expected = str(payload["expected_content_hash"])
    if not re.match(r"^sha256:[a-f0-9]{64}$", expected):
        raise RpcError.of(
            "VALIDATION_FAILED",
            "expected_content_hash must be sha256:<64 hex>",
            field="expected_content_hash",
        )

    with db.read() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
    if replay is not None:
        return replay

    with db.read() as connection:
        plan_record = _authored_export_plan(connection, enrollment_id)
    if not plan_record.get("ready"):
        details = {"problems": list(plan_record["problems"])} if plan_record["problems"] else {}
        raise _blocked(
            str(plan_record["blocked_reason"]),
            str(plan_record["blocked_message"]),
            **details,
        )
    # The course-text digest is the reviewed identity of the export; the pack's own manifest hash
    # is a different function and is reported separately as ``pack.manifest_hash``.
    reviewed_hash = str(plan_record["content_hash"])
    if reviewed_hash != expected:
        raise RpcError.of(
            "DELETE_SCOPE_STALE",
            "the authored content changed since it was reviewed; nothing was exported.",
            current_data_scope_hash=str(plan_record["content_hash"]),
        )

    manifest = plan_record["manifest"]
    files = plan_record["files"]
    course = plan_record["course"]
    packs.warn_authoring_bound(manifest, files)

    root = export_root()
    root.mkdir(parents=True, exist_ok=True)
    digest = str(manifest["content_hash"]).split(":", 1)[1]
    destination = root / f"{manifest['pack_id']}-{manifest['pack_version']}-{digest[:16]}.zip"
    temporary = destination.with_name(destination.stem + ".partial.zip")
    try:
        archive.write_archive(temporary, manifest, files)
        os.replace(temporary, destination)
        written = _rehash_written_archive(destination)
    except (PackRejected, OSError) as exc:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise _blocked("export_write_failed", f"the authored pack could not be written: {exc}") from exc
    if str(written["content_hash"]) != str(manifest["content_hash"]):
        destination.unlink(missing_ok=True)
        raise RpcError.of("INTERNAL_ERROR", "the exported archive does not re-hash to its manifest")

    # Digest the bytes that exist, with no transaction open; the adopt transaction stays short.
    zip_bytes = destination.read_bytes()
    file_digest = packs.file_sha256(zip_bytes)
    now = _now()
    export_id = _new_id("exp")
    try:
        with db.transaction() as connection:
            replay = _idempotent_lookup(connection, key, method, payload_hash)
            if replay is not None:
                return replay
            # Re-ask every gate question against storage: the page may have changed while the
            # archive was being written, and the file must not outlive that answer.
            fresh = _authored_export_plan(connection, enrollment_id)
            if (
                not fresh.get("ready")
                or str(fresh.get("content_hash")) != reviewed_hash
            ):
                raise _blocked(
                    "changes_need_review",
                    "the authored content changed while exporting; nothing was adopted.",
                    current_content_hash=fresh.get("content_hash"),
                )
            artifact_id = _adopt_artifact(
                connection,
                course_id=str(course["id"]),
                kind="export",
                mime="application/zip",
                path=destination,
                data_hash=file_digest,
                size=len(zip_bytes),
                notes=(
                    f"course.export of course {course['id']} from enrollment {enrollment_id}; "
                    f"manifest {manifest['content_hash']}"
                ),
                generator="coursebook.course_export",
            )
            result = {
                "export_id": export_id,
                "pack": {
                    "pack_id": str(manifest["pack_id"]),
                    "pack_version": str(manifest["pack_version"]),
                    "manifest_hash": str(manifest["content_hash"]),
                },
                "files": _authored_file_rows(manifest),
                "artifacts": [_artifact_ref(connection, artifact_id)],
                "content_hash": reviewed_hash,
                "exported_at": now,
                "license": dict(authoring.AUTHORED_LICENSE),
                "rights": AUTHORED_RIGHTS,
                "no_upload": AUTHORED_NO_UPLOAD,
            }
            _remember(
                connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result
            )
    except RpcError:
        destination.unlink(missing_ok=True)
        raise
    return 0, result


# ── installed-pack reads (cb.rpc v4) ───────────────────────────────────────


def _pack_rows() -> dict[tuple[str, str], Mapping[str, Any]]:
    """Kernel ``packs`` rows keyed by ``(pack_id, version)``.

    A library read can be the first thing a fresh profile asks for, before anything ran
    ``ensure_schema``; a missing table therefore means "no kernel rows", not an error.
    """
    try:
        with db.read() as connection:
            rows = connection.execute(
                "SELECT pack_id, version, state, revision FROM packs"
            ).fetchall()
    except sqlite3.Error:
        return {}
    return {(str(row["pack_id"]), str(row["version"])): row for row in rows}


def _adopted_manifest(record: Mapping[str, Any]) -> dict[str, Any]:
    """Read the stored manifest of an adopted pack for its declared counts and recipe."""
    directory = Path(str(record["directory"]))
    return packs.load_manifest(directory / packs.root_file())


def _pack_list_item(
    record: Mapping[str, Any],
    manifest: Mapping[str, Any],
    rows: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    """One ``pack.list`` row: the library index joined to the kernel row on identity.

    The kernel row wins for ``state``/``revision`` (``pack.delete`` fences on the revision);
    the index's own copy is the fallback adoption writes. Neither the index's absolute
    ``directory`` nor the manifest itself is part of the row: a path is storage, and
    ``pack.inspect`` is the read that returns the manifest.
    """
    pack_id = str(record["pack_id"])
    version = str(record["version"])
    row = rows.get((pack_id, version))
    return {
        "pack_id": pack_id,
        "pack_version": version,
        "content_hash": str(record["manifest_hash"]),
        "recipe": str(manifest["recipe"]),
        "source": str(record.get("source") or "local"),
        "state": str(row["state"]) if row is not None else str(record.get("state") or "installed"),
        "revision": int(row["revision"]) if row is not None else int(record.get("revision") or 0),
        "installed_at": str(record["installed_at"]),
        "file_count": len(manifest["files"]),
        "expanded_bytes": sum(int(entry["bytes"]) for entry in manifest["files"]),
        "license": copy.deepcopy(manifest["license"]),
    }


def pack_list(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``pack.list``: every adopted identity, enrolled or not, with its deletion revision.

    ``library.list`` answers "what is enrolled"; this answers "what is installed". Ordering is
    ``installed_at`` descending, then ``pack_id``, then ``pack_version`` ascending, so two
    renders of the same library agree. ``limit`` slices the response; ``total`` always counts
    every matching identity and ``truncated`` says whether the slice omitted rows.
    """
    rows = _pack_rows()
    wanted_id = payload.get("pack_id")
    wanted_version = payload.get("pack_version")
    applied_filter = str(payload.get("filter") or "all")
    limit = int(payload.get("limit") or 100)

    matched: list[dict[str, Any]] = []
    for record in library().list():
        if wanted_id is not None and str(record.get("pack_id")) != str(wanted_id):
            continue
        if wanted_version is not None and str(record.get("version")) != str(wanted_version):
            continue
        try:
            manifest = _adopted_manifest(record)
        except PackRejected as exc:
            # The library index points at content this build cannot read back. Refuse with the
            # contract's PACK_REJECTED rather than letting a ValueError become INTERNAL_ERROR.
            raise _rejected(
                f"installed pack {record.get('pack_id')} {record.get('version')} cannot be read: {exc}",
                "pack_unreadable",
                pack_id=str(record.get("pack_id")),
                pack_version=str(record.get("version")),
            ) from exc
        item = _pack_list_item(record, manifest, rows)
        if applied_filter != "all" and item["state"] != applied_filter:
            continue
        matched.append(item)

    # Stable sorts: identity ascending first, then the primary key descending.
    matched.sort(key=lambda item: (item["pack_id"], item["pack_version"]))
    matched.sort(key=lambda item: item["installed_at"], reverse=True)

    return 0, {
        "items": matched[:limit],
        "total": len(matched),
        "truncated": len(matched) > limit,
        "applied_filter": applied_filter,
    }


def pack_inspect(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``pack.inspect``: one installed pack read from the library, no upload grant.

    The adopted directory is read back through :meth:`PackLibrary.read`, which re-validates
    the manifest and re-hashes every declared file. Drifted or missing content is *reported*
    (``integrity.hashes_match: false``) so a review screen can refuse the export instead of
    the pane dying; only an identity absent from the library (or an unreadable manifest) is an
    error. The response carries the same four independent trust labels as ``pack.preview`` —
    never a ``safe``/``verified`` verdict.
    """
    pack_id = str(payload["pack_id"])
    pack_version = str(payload["pack_version"])
    record = _installed_record(pack_id, pack_version)
    if record is None:
        raise RpcError.of(
            "NOT_FOUND",
            f"pack {pack_id} {pack_version} is not in the installed pack library.",
            pack_id=pack_id,
            pack_version=pack_version,
        )

    directory = Path(str(record["directory"]))
    hashes_match = True
    try:
        manifest, files = library().read(pack_id, pack_version)
    except PackRejected as exc:
        if not directory.is_dir():
            raise RpcError.of(
                "NOT_FOUND",
                f"pack {pack_id} {pack_version} has no adopted directory to inspect.",
                pack_id=pack_id,
                pack_version=pack_version,
            ) from exc
        try:
            manifest = _adopted_manifest(record)
        except PackRejected as unreadable:
            raise _rejected(
                f"installed pack {pack_id} {pack_version} cannot be read: {unreadable}",
                "pack_unreadable",
                pack_id=pack_id,
                pack_version=pack_version,
            ) from unreadable
        # Content drifted from the manifest; read what is on disk and let hashes_match say so.
        files = {}
        hashes_match = False
        for entry in manifest["files"]:
            target = directory / str(entry["path"])
            files[str(entry["path"])] = target.read_bytes() if target.is_file() else b""

    declared = {str(entry["path"]): entry for entry in manifest["files"]}
    hashes_match = (
        hashes_match
        and packs.content_hash(manifest) == str(record["manifest_hash"])
        and set(files) == set(declared)
        and all(
            packs.file_sha256(files[path]) == str(entry["sha256"])
            and len(files[path]) == int(entry["bytes"])
            for path, entry in declared.items()
        )
    )
    document = packs.preview(
        manifest,
        integrity={
            "hashes_match": hashes_match,
            "file_count": len(manifest["files"]),
            "expanded_bytes": sum(int(entry["bytes"]) for entry in manifest["files"]),
        },
        automated_checks_passed=True,
    )
    return 0, {
        "pack": _pack_list_item(record, manifest, _pack_rows()),
        "manifest": document["manifest"],
        "integrity": document["integrity"],
        "trust": document["trust"],
    }


# ── download seam (route owner: Sable) ─────────────────────────────────────


_HANDLE = re.compile(r"^(?P<artifact_id>art_[a-f0-9]{32})_(?P<expires>\d{9,12})$")


def open_artifact(handle: str) -> tuple[Path, str, int]:
    """Resolve an ``artifact.get`` handle to ``(path, mime, bytes)``.

    The route calls this *after* the host authenticated the session (``requires_session: true``).
    A path never crosses the wire; the handle is expiring and refers only to a stored export.
    """
    match = _HANDLE.match(str(handle))
    if match is None:
        raise RpcError.of("NOT_FOUND", "unknown artifact handle")
    if int(match.group("expires")) < int(datetime.now(timezone.utc).timestamp()):
        raise RpcError.of("NOT_FOUND", "this download handle expired; ask artifact.get again")
    with db.read() as connection:
        row = _row(connection, "SELECT * FROM artifacts WHERE id = ?", (match.group("artifact_id"),))
    if row is None:
        raise RpcError.of("NOT_FOUND", "artifact not found")
    path = Path(str(row["path"]))
    # An ``artifacts`` row is a record, not a warrant: only files the plugin itself writes may
    # leave through this handle. Exports live under ``pack-exports/`` and stored media under
    # ``artifacts/``; a row naming anything else (another profile, /etc, a hand-edited path) is
    # refused before a byte is opened. Symlinks are resolved, so a link escaping either root is
    # refused too.
    if not any(db.within(path, root) for root in (export_root(), artifacts.read_root())):
        raise RpcError.of("NOT_FOUND", "artifact file is outside this profile's store")
    if not path.is_file():
        raise RpcError.of("NOT_FOUND", "artifact file is missing on disk")
    if path.stat().st_size != int(row["bytes"]):
        raise RpcError.of("INTERNAL_ERROR", "artifact file size does not match its record")
    digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != str(row["content_hash"]):
        raise RpcError.of("INTERNAL_ERROR", "artifact file hash does not match its record")
    return path, str(row["mime"]), int(row["bytes"])


# ── deletion / tombstone reconciliation ────────────────────────────────────


def sync_tombstones() -> list[str]:
    """Mark library records frozen when the kernel froze their pack row.

    ``pack.delete`` (kernel) freezes the pack and keeps evidence; this keeps the *library index*
    honest too, so a deleted pack cannot look installed in the file list.
    """
    frozen: set[str] = set()
    try:
        with db.read() as connection:
            for row in connection.execute("SELECT pack_id, state FROM packs WHERE state = 'frozen'"):
                frozen.add(str(row["pack_id"]))
    except Exception:  # noqa: BLE001 - no schema yet: nothing can be frozen
        return []
    if not frozen:
        return []
    store = library()
    records = store.list()
    changed = []
    for record in records:
        if str(record.get("pack_id")) in frozen and record.get("state") != "frozen":
            record["state"] = "frozen"
            changed.append(str(record.get("pack_id")))
    if changed:
        store._write_records(records)  # noqa: SLF001 - same package, single writer of index.json
    return changed


def recover_interrupted_imports() -> list[str]:
    """Startup reconciliation: staged trees, library state, and journaled import jobs.

    Returns the ids of import jobs that were running when the process died. Those imports wrote
    no course: the database transaction is all-or-nothing and adoption happens before it. The
    UI shows them through ``jobs.list`` so a user is told rather than left guessing.
    """
    recovered = staging().reconcile()
    sync_tombstones()
    interrupted: list[str] = []
    try:
        with db.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM jobs WHERE kind = 'import' AND state = 'running'"
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE jobs SET state = 'interrupted_requires_retry', updated_at = ? WHERE id = ?",
                    (_now(), row["id"]),
                )
                interrupted.append(str(row["id"]))
    except Exception:  # noqa: BLE001
        return recovered
    return recovered + interrupted


def reconcile() -> dict[str, Any]:
    """Startup entry point: reconcile staging, tombstones and interrupted imports."""
    recovered = recover_interrupted_imports()
    return {"recovered": recovered, "installed": len(library().list())}


# ── explicit cross-recipe conversion ───────────────────────────────────────


def build_conversion(
    manifest: Mapping[str, Any],
    files: Mapping[str, bytes],
    *,
    pack_id: str,
    pack_version: str,
    recipe: str,
    license: Mapping[str, Any] | None = None,
    confirm: bool = False,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Turn a pack into a *new* pack under a chosen recipe — never silently, never in place.

    Cross-recipe conversion is an authoring act with three visible facts: a new ``pack_id``, a new
    ``pack_version``, and ``derived_from`` naming the original. Without ``confirm=True`` it
    refuses, so no UI path can convert a parent blueprint into a graded adult course by accident.
    """
    if not confirm:
        raise PackRejected("conversion needs explicit confirmation and a new pack identity")
    if recipe not in _RECIPES:
        raise PackRejected(f"unknown recipe {recipe!r}")
    if recipe == str(manifest.get("recipe")):
        raise PackRejected("conversion must change the recipe; re-export the same recipe unchanged instead")
    if pack_id == str(manifest.get("pack_id")) or pack_version == str(manifest.get("pack_version")):
        raise PackRejected("a conversion is a new pack: both pack_id and pack_version must change")
    document, exported = packs.build_export(
        manifest,
        files,
        pack_id=pack_id,
        pack_version=pack_version,
        license=license,
    )
    # ``build_export`` rebuilds the allowlisted fields but keeps the source recipe; a conversion
    # is precisely the act of changing it, so it is set here, explicitly, then re-hashed.
    document = {key: value for key, value in document.items() if key != "content_hash"}
    document["recipe"] = recipe
    document = packs.with_content_hash(document)
    packs.validate_manifest(document)
    packs.validate_minima(document)
    return document, exported


# ── registration ───────────────────────────────────────────────────────────


def ensure_registered() -> tuple[str, ...]:
    """Bind the pack methods. Called at import; safe to call again."""
    registered = []
    for method, handler in (
        ("pack.preview", pack_preview),
        ("pack.import", pack_import),
        ("pack.export", pack_export),
        ("pack.list", pack_list),
        ("pack.inspect", pack_inspect),
        ("course.export.read", course_export_read),
        ("course.export", course_export),
    ):
        api.register_handler(method, handler)
        registered.append(method)
    return tuple(registered)


ensure_registered()
