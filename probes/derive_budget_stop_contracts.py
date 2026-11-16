"""Compose the BUDGET_EXHAUSTED + health.get deltas into today's shipped contract set.

Run from the repository root::

    python3 probes/derive_budget_stop_contracts.py

Two freeze-stranded cards, re-derived onto the contracts trunk this branch actually sits on
(t_34f65fe5). Trunk has already issued ``cb.rpc`` v29 and ``cb.jobs`` v6 by other cards, so this
probe **composes into the current versions** — a second ``rpc.v29.json`` or ``jobs.v6.json`` cannot
exist, and ``coursebook/contracts.py`` forbids forking a shipped version. Each step is a fixpoint:
re-running it changes nothing.

* ``contracts/errors.v5.json`` — derived from the frozen ``errors.v4.json``: v4 plus exactly one
  catalogue code, ``BUDGET_EXHAUSTED`` (``state``, ``retryable: false``, HTTP 409). No v1-v4 code,
  category, retryability or status mapping is retyped; ``errors.v4.json`` stays byte-identical.
* ``contracts/jobs.v6.json`` — trunk's v6 with its one failed-job ``error`` ``$ref`` folded onto
  ``errors/v5``. v6 is not re-issued: no job kind, state, transition, field, ``activity`` key or
  progress percentage moves, and every v5 payload validates unchanged.
* ``contracts/rpc.v29.json`` — trunk's v29 with the shared error ``$ref`` folded onto ``errors/v5``
  plus H-131's additive ``health.get`` amendment: the ``db`` block gains required ``state``
  (``ready|unmigrated|failed``) and ``target_schema_version``, an optional bounded ``error``, and
  the response gains a required bounded ``reconciliation`` block. No other method, payload, enum
  value or vocabulary value moves, and no wire echo moves (v29 was already the wire).

Every document is written **onto a parsed source** and refuses to write unless the source
round-trips through the repository's serialisation byte-exactly (``json.dumps`` with ``indent=2``,
``ensure_ascii=False``, trailing newline), so a fold cannot diff in every line. Predecessors
(``errors.v4.json``, ``jobs.v5.json``, ``rpc.v28.json``) stay byte-identical history.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT_DIR = ROOT / "contracts"

ERRORS_SOURCE = CONTRACT_DIR / "errors.v4.json"
ERRORS_TARGET = CONTRACT_DIR / "errors.v5.json"
JOBS_FILE = CONTRACT_DIR / "jobs.v6.json"
RPC_FILE = CONTRACT_DIR / "rpc.v29.json"

ERROR_URI = "https://contracts.coursebook.hermes/errors"
JOBS_URI = "https://contracts.coursebook.hermes/jobs"
RPC_URI = "https://contracts.coursebook.hermes/rpc"

CODE = "BUDGET_EXHAUSTED"

ERRORS_DELTA = (
    "Every failure the backend reports, in HTTP or inside an RPC response, uses this object. The "
    "catalog below is the single authority for codes, categories, retryability and status mapping; "
    "coursebook.contracts reads it rather than duplicating it. "
    "v5 is additive over v4: it adds exactly one code, BUDGET_EXHAUSTED (category state, retryable "
    "false, HTTP 409), the typed stop for a declared spend ceiling. Two shapes reach it, "
    "distinguished by details.reason: cost_preflight_insufficient (the ceiling cannot pay the "
    "minimum calls a request needs, refused before any job row exists) and cost_ceiling_exceeded "
    "(the ceiling was reached mid-course). A spend stop is arithmetic, not a verdict: nothing was "
    "validated and nothing was rejected, so it must never be rendered as a content refusal. The "
    "error names the refused purpose, the budget source and the spend arithmetic, and the job "
    "checkpoint carries the resume brief. No v1-v4 code, category, retryability or status mapping "
    "changes; errors.v4.json stays byte-identical history."
)

ERRORS_SUMMARY = (
    "A declared spend ceiling does not permit this work: it cannot pay the calls the request needs "
    "(details.reason = cost_preflight_insufficient) or it was reached mid-course "
    "(details.reason = cost_ceiling_exceeded). No provider call was made after the refusal and "
    "nothing was validated or rejected. details name the refused purpose, the budget source, the "
    "spend arithmetic and the recovery actions; jobs.checkpoint carries the resume brief."
)

#: Appended to the *current* jobs/rpc description, once. The documents belong to other cards; this
#: names only what this probe folded into them.
JOBS_NOTE = (
    "Folded in place by t_891d90e7: the failed-job `error` envelope resolves cb.errors v5, because "
    "v5 adds BUDGET_EXHAUSTED (a declared spend ceiling is a state stop, not a content refusal) and "
    "a v4 reference would reject the very failure that code exists for. One `$ref` moved; no job "
    "kind, state, transition, field, `activity` key or progress percentage moved."
)

RPC_NOTE = (
    "Folded in place by t_891d90e7 and H-131: (1) the shared error envelope resolves cb.errors v5 "
    "(one added code, BUDGET_EXHAUSTED — a declared spend ceiling is a state stop, not a content "
    "refusal), a reference-only move; (2) `health.get`'s `db` block gains required `state` "
    "(ready|unmigrated|failed) and `target_schema_version`, plus an optional bounded `error` "
    "{type<=80, message<=300, target_schema_version} present only when the migration attempt "
    "raised, and the response gains a required bounded `reconciliation` block {state ok|failed, "
    "error|null, message|null} carrying the plugin-load recovery report. `ready: false` is no "
    "longer one fact: a never-migrated profile and a store whose migration failed are different "
    "answers, and the pane must stop telling a user their course tables do not exist when the "
    "truth is that preparing them failed. No other method, payload, error code, job kind, answer "
    "kind, verdict, evidence class or vocabulary value moves."
)

#: H-131: the ``health.get`` ``db`` block. ``ready`` alone could not distinguish a profile that was
#: never migrated from a store whose migration raised; the two now have different states and only
#: the second carries a bounded error.
HEALTH_DB = {
    "type": "object",
    "description": (
        "Profile-scoped store state. `state` distinguishes a never-migrated profile "
        "(`unmigrated`) from a store whose migration actually failed (`failed`); `error` is "
        "present only for the latter, and the GET still answers ok:true."
    ),
    "additionalProperties": False,
    "required": ["ready", "schema_version", "state", "target_schema_version"],
    "properties": {
        "ready": {"type": "boolean"},
        "schema_version": {"type": ["integer", "null"], "minimum": 0},
        "state": {"type": "string", "enum": ["ready", "unmigrated", "failed"]},
        "target_schema_version": {"type": "integer", "minimum": 0},
        "error": {
            "type": "object",
            "description": (
                "Why `ensure_schema` could not prepare the store. Present only when the migration "
                "attempt raised; absent on a healthy or simply unmigrated profile."
            ),
            "additionalProperties": False,
            "required": ["type", "message", "target_schema_version"],
            "properties": {
                "type": {"type": "string", "maxLength": 80},
                "message": {"type": "string", "maxLength": 300},
                "target_schema_version": {"type": "integer", "minimum": 0},
            },
        },
    },
}

#: H-131: the plugin-load recovery report, so a failed reconcile is not computed-and-ignored.
RECONCILIATION = {
    "type": "object",
    "description": (
        "Plugin-load startup reconciliation. `failed` carries the bounded error the plugin also "
        "logs at WARNING; `ok` means the load-time recovery ran."
    ),
    "additionalProperties": False,
    "required": ["state"],
    "properties": {
        "state": {"type": "string", "enum": ["ok", "failed"]},
        "error": {"type": ["string", "null"], "maxLength": 80},
        "message": {"type": ["string", "null"], "maxLength": 300},
    },
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _load(path: pathlib.Path, expected_version: int) -> dict:
    raw = path.read_text(encoding="utf-8")
    document = json.loads(raw)
    if serialise(document) != raw:
        raise SystemExit(
            f"{path.name} does not round-trip under this serialiser; refusing to derive a "
            "document whose diff would be every line"
        )
    if int(document["x-contract-version"]) != expected_version:
        raise SystemExit(f"expected {path.name} at v{expected_version}, found v{document['x-contract-version']}")
    return document


def _append_once(document: dict, note: str) -> None:
    if note in document["description"]:
        return
    document["description"] = f"{document['description']} {note}"


def derive_errors(source: dict) -> dict:
    """v4 plus one code in the enum, the catalog schema and the catalog, and nothing else."""
    document = json.loads(json.dumps(source))
    document["$id"] = f"{ERROR_URI}/v5"
    document["title"] = "Coursebook error envelope v5"
    document["x-contract-version"] = 5
    # ``cb.errors`` replaces its description each version (v2-v4 all do), unlike the wire contracts
    # which carry their ancestor verbatim; the text names the delta and the invariant it keeps.
    document["description"] = ERRORS_DELTA
    document["x-supersedes"] = f"{ERROR_URI}/v4"

    error = document["$defs"]["error"]["properties"]
    enum = error["code"]["enum"]
    if CODE in enum:
        raise SystemExit(f"{CODE} is already in the v4 code enum")
    enum.append(CODE)
    # ``$defs.code_catalog`` is the schema-side map (one ``{"type": "object"}`` per catalogue code);
    # the root ``code_catalog`` carries the facts. Both are appended, never retyped.
    catalog_schema = document["$defs"]["code_catalog"]["properties"]
    if CODE in catalog_schema:
        raise SystemExit(f"{CODE} is already in the v4 catalog schema")
    catalog_schema[CODE] = {"type": "object"}
    catalog = document["code_catalog"]
    if CODE in catalog:
        raise SystemExit(f"{CODE} is already in the v4 catalog")
    catalog[CODE] = {
        "category": "state",
        "retryable": False,
        "http": 409,
        "summary": ERRORS_SUMMARY,
    }
    return document


def _fold_error_ref(document: dict, *, expected: int) -> int:
    """Move every ``errors/v4`` envelope ``$ref`` to v5; refuse to invent or lose one."""
    moved = 0
    seen_v5 = 0

    def walk(node):
        nonlocal moved, seen_v5
        if isinstance(node, dict):
            ref = node.get("$ref")
            if ref == f"{ERROR_URI}/v4#/$defs/error":
                node["$ref"] = f"{ERROR_URI}/v5#/$defs/error"
                moved += 1
            elif ref == f"{ERROR_URI}/v5#/$defs/error":
                seen_v5 += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(document)
    if moved and seen_v5:
        raise SystemExit("document resolves both errors/v4 and errors/v5")
    if moved != expected and seen_v5 != expected:
        raise SystemExit(f"expected {expected} error envelope ref(s), moved {moved}, already v5 {seen_v5}")
    return moved


def fold_jobs(source: dict) -> dict:
    """Trunk's jobs v6 with its one error `$ref` folded onto errors/v5. Idempotent."""
    document = json.loads(json.dumps(source))
    _fold_error_ref(document, expected=1)
    _append_once(document, JOBS_NOTE)
    return document


def fold_rpc(source: dict) -> dict:
    """Trunk's rpc v29 with the error `$ref` folded onto v5 and H-131's health amendment. Idempotent."""
    document = json.loads(json.dumps(source))
    _fold_error_ref(document, expected=1)
    _append_once(document, RPC_NOTE)

    health = document["$defs"]["methods"]["properties"]["health.get"]["response"]
    db = health["properties"]["db"]
    if "reconciliation" in health["properties"] and "state" in db["properties"]:
        if health["properties"]["db"] != HEALTH_DB or health["properties"]["reconciliation"] != RECONCILIATION:
            raise SystemExit("health.get already carries a different health shape; refusing to overwrite it")
        return document
    if db["required"] != ["ready", "schema_version"]:
        raise SystemExit(f"health.get db block carries an unexpected shape: {db['required']}")
    if "reconciliation" in health["properties"]:
        raise SystemExit("health.get already carries reconciliation without the db states")
    health["properties"]["db"] = json.loads(json.dumps(HEALTH_DB))
    health["properties"]["reconciliation"] = json.loads(json.dumps(RECONCILIATION))
    health["required"] = list(health["required"]) + ["reconciliation"]
    return document


def _write(target: pathlib.Path, document: dict) -> None:
    text = serialise(document)
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)} ({len(text)} bytes)")


def _sibling(filename: str):
    """Load a sibling derivation the way its own tests do (spec from the file, no sys.path)."""
    import importlib.util

    path = ROOT / "probes" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _from_source(filename: str, version: int) -> dict:
    return _load(CONTRACT_DIR / filename, version)


def main() -> int:
    # errors v5 is a real derivation from the frozen v4.
    _write(ERRORS_TARGET, derive_errors(_from_source("errors.v4.json", 4)))
    # The wire documents belong to other cards: their own probe composes every sibling delta,
    # including the one this probe contributes, so re-deriving through the chain is the same
    # operation as folding — and it cannot drift from the chain.
    jobs_probe = _sibling("derive_jobs_v6.py")
    _write(JOBS_FILE, jobs_probe.derive(_from_source("jobs.v5.json", 5)))
    rpc_probe = _sibling("derive_rpc_v29.py")
    _write(RPC_FILE, rpc_probe.derive(_from_source("rpc.v28.json", 28)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
