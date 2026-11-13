"""Loader, validator and single access point for the frozen Coursebook contracts.

Nothing else in the plugin may hardcode a contract enum, payload shape or error code. Callers
read them here, so a contract bump is one file change plus a version decision in
``docs/CONTRACTS.md`` instead of a search across the tree.

The contracts are JSON Schema 2020-12 documents that reference each other by absolute ``$id``;
:func:`registry` builds the cross-document resolver so ``$ref`` targets in another file work.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

#: ``coursebook/contracts.py`` -> plugin root -> ``contracts/``.
CONTRACT_DIR = Path(__file__).resolve().parent.parent / "contracts"

#: Contract id -> file name. Order is the inventory order reported by ``schema.get``.
#: The v1 files stay on disk as immutable history; only the current version is in the inventory.
CONTRACT_FILES: dict[str, str] = {
    "cb.vocabulary": "vocabulary.v1.json",
    "cb.errors": "errors.v4.json",
    # E2E L1 (t_1b7cab16): v28 is a *composed* additive amendment over v27. This branch adds the
    # revisit lane — `revisit` on check.open, check.get and lesson.page.checks, and
    # `next_step.kind` = review_lesson. The same v28 also carries the E2E L4/L5 amendment
    # (course completion + unstorable lesson) built in wt/t_6f613fef, and it freezes
    # lesson.page.section.sections_total, which the base commit already projected. One contract
    # version must carry every additive change shipped together: two rpc.v28.json files cannot
    # both exist, so these cards compose rather than fork the version.
    "cb.rpc": "rpc.v28.json",
    # E2E L1: v15 is additive over v14 — one column, `checks.revisit INTEGER NOT NULL DEFAULT 0`.
    # No row is rewritten; every check written before v15 reads as an ordinary (non-revisit) check.
    "cb.db": "db.v15.json",
    "cb.jobs": "jobs.v5.json",
    # H-137 (H-73 §4): ``cb.pack`` is the one contract that accepts more than one document
    # version. v2 adds the optional root ``media[]`` link; v1 stays byte-identical and is still
    # the inventory current, because every frozen ``cb.rpc`` file (v4…v16) and ``cb.projection``
    # v1 resolve ``$ref`` targets to ``pack-manifest/v1``. Bumping the inventory would either
    # break those refs or require editing a frozen wire contract, so v2 is an *accepted document
    # version* (``CONTRACT_VERSION_FILES``) while cross-document refs keep pointing at v1.
    # PRINT-2 (t_6418b9dd): v4 is accepted the same way, additively over v3 — the file role enum
    # gains ``coloring_page`` and the MIME enum gains ``text/html``, the byte form of the print
    # documents this build renders. The inventory current stays v3 so no existing builder's
    # output moves; a pack that declares ``coloring_page`` declares ``contract_version: 4``.
    "cb.pack": "pack-manifest.v3.json",
    # t_d33984eb: v2 changes no projection rule or output. It corrects the one sentence that
    # let a pack's own `trust.reviewed_by` become a `human_review_recorded` label. v1 stays on
    # disk, and `CONTRACT_VERSION_FILES` keeps it loadable by explicit version.
    "cb.projection": "projection.v2.json",
    # H-89: declared, hash-pinned frequency inventories for language courses. Describes an
    # imported (or synthetic-fixture) document; the plugin bundles no third-party list.
    "cb.frequency_inventory": "frequency-inventory.v1.json",
}

#: The contract whose version the plugin speaks on the wire.
WIRE_CONTRACT_ID = "cb.rpc"
WIRE_CONTRACT_VERSION = 28


#: Version -> file name for every contract that accepts more than one document version.
#: ``CONTRACT_FILES`` names the current one; the older file is immutable history, kept on disk and
#: reachable only by an explicit version. A document that declares ``contract_version`` selects the
#: schema it is validated against, so a v1 pack keeps the v1 allowlist and never inherits v2 fields.
CONTRACT_VERSION_FILES: dict[str, dict[int, str]] = {
    "cb.pack": {1: "pack-manifest.v1.json", 2: "pack-manifest.v2.json", 3: "pack-manifest.v3.json",
                4: "pack-manifest.v4.json"},
    # GM-005: v23 appends the take-home family to GM-011's v22. v22 stays readable so a client
    # that pinned the tutor wire can still validate; v21 and older remain on disk as history but
    # are not offered by the loader.
    # v24 is one composed document: GM-007 appends the four away-from-screen homework methods,
    # GM-018 appends `takehome.html`, and GM-004 appends the four `world.*` methods plus the
    # documented `course.mode.set` extra and one optional `presentation_mode` on `course.create`.
    # v23 stays readable so a client that pinned the take-home wire can still validate.
    # CP-005: v25 is additive over v24 — the seven `library_item` shelf facts and nothing else.
    # v24 stays readable so a client that pinned the World Studio wire can still validate.
    # CP-052: v26 is additive over v25 — `world_brief.route_anchors`, the plate's own normalised
    # route geometry, optional and absent by default. v25 stays readable so a client that pinned
    # the shelf wire can still validate.
    # Item 28b: v27 is additive over v26 — `lesson_document_media.labels`, the text the product UI
    # draws over a textless figure, optional and absent by default. v26 stays readable so a client
    # that pinned the plate-geometry wire can still validate.
    # E2E L1: v28 is additive over v27 — the optional `revisit` flag on `check.open`, `check.get`
    # and each `lesson.page.checks` row, plus one `next_step.kind` enum value, `review_lesson`. A
    # revisit is a clone of the newest closed authored check; it never moves the objective again
    # and never pays XP twice. v27 stays readable so a client that pinned the drawn-label wire can
    # still validate.
    "cb.rpc": {22: "rpc.v22.json", 23: "rpc.v23.json", 24: "rpc.v24.json", 25: "rpc.v25.json",
               26: "rpc.v26.json", 27: "rpc.v27.json", 28: "rpc.v28.json"},
    # t_d33984eb: the v1 projection stays readable by explicit version as immutable history; v2
    # is the inventory current (one trust-label sentence corrected, no rule or output moved).
    "cb.projection": {1: "projection.v1.json", 2: "projection.v2.json"},
}


def version_files(contract_id: str) -> dict[int, str]:
    """Known versions for *contract_id*; exactly one entry for a single-version contract."""
    known = CONTRACT_VERSION_FILES.get(contract_id)
    if known is not None:
        return dict(known)
    if contract_id not in CONTRACT_FILES:
        raise ContractError(f"unknown contract id {contract_id!r}", contract_id=contract_id)
    return {contract_version(contract_id): CONTRACT_FILES[contract_id]}


def contract_as(contract_id: str, version: int) -> dict[str, Any]:
    """The parsed document for one explicit *version* of a contract."""
    known = version_files(contract_id)
    filename = known.get(int(version))
    if filename is None:
        raise ContractError(
            f"{contract_id} has no version {version!r}; known versions are {sorted(known)}",
            contract_id=contract_id,
        )
    document = _read_file(contract_id, filename)
    if int(document["x-contract-version"]) != int(version):
        raise ContractError(
            f"{filename} declares x-contract-version {document['x-contract-version']!r}, expected {version!r}",
            contract_id=contract_id,
        )
    return document


class ContractError(Exception):
    """A contract file is missing, malformed or does not match a payload.

    This is a programming/configuration failure, not a user-facing error. Callers translate it
    into an ``INTERNAL_ERROR`` (or ``VALIDATION_FAILED`` for caller input) envelope.
    """

    def __init__(self, message: str, *, contract_id: str | None = None, path: str = "") -> None:
        self.contract_id = contract_id
        self.path = path
        super().__init__(message)


def _read(contract_id: str) -> dict[str, Any]:
    filename = CONTRACT_FILES.get(contract_id)
    if filename is None:
        raise ContractError(f"unknown contract id {contract_id!r}", contract_id=contract_id)
    return _read_file(contract_id, filename)


def _read_file(contract_id: str, filename: str) -> dict[str, Any]:
    path = CONTRACT_DIR / filename
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"contract file missing: {path}", contract_id=contract_id) from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"contract file is not valid JSON: {path}: {exc}", contract_id=contract_id) from exc
    if not isinstance(document, dict):
        raise ContractError(f"contract root must be an object: {path}", contract_id=contract_id)
    for key in ("$schema", "$id", "x-contract-id", "x-contract-version"):
        if key not in document:
            raise ContractError(f"contract {filename} is missing {key!r}", contract_id=contract_id)
    if document["x-contract-id"] != contract_id:
        raise ContractError(
            f"contract {filename} declares x-contract-id {document['x-contract-id']!r}, expected {contract_id!r}",
            contract_id=contract_id,
        )
    return document


@lru_cache(maxsize=None)
def contract(contract_id: str) -> dict[str, Any]:
    """Return the parsed contract document. Cached for the process lifetime."""
    return _read(contract_id)


def contract_ids() -> tuple[str, ...]:
    return tuple(CONTRACT_FILES)


def contract_version(contract_id: str) -> int:
    return int(contract(contract_id)["x-contract-version"])


def contract_uri(contract_id: str) -> str:
    return str(contract(contract_id)["$id"])


def contract_sha256(contract_id: str) -> str:
    """``sha256:<hex>`` over the exact file bytes, for ``schema.get`` and drift detection."""
    filename = CONTRACT_FILES[contract_id]
    digest = hashlib.sha256((CONTRACT_DIR / filename).read_bytes()).hexdigest()
    return f"sha256:{digest}"


@lru_cache(maxsize=1)
def registry() -> Registry:
    """Cross-document resolver for the absolute ``$ref`` targets the contracts use.

    Every accepted *version* is registered, not only the current document: a frozen wire contract
    (``cb.rpc``) may point at an older pack-manifest's property (``pack-manifest/v1#/properties/
    pack_id``), and that pointer must keep resolving after a newer pack version becomes current.
    """
    resources: list[tuple[str, Resource]] = []
    seen: set[str] = set()
    for contract_id in CONTRACT_FILES:
        candidates = [contract(contract_id)]
        if contract_id in CONTRACT_VERSION_FILES:
            candidates = [
                contract_as(contract_id, version) for version in sorted(version_files(contract_id))
            ]
        for document in candidates:
            uri = str(document["$id"])
            if uri in seen:
                continue
            seen.add(uri)
            resources.append((uri, Resource.from_contents(document, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def _validator(contract_id: str) -> Draft202012Validator:
    return Draft202012Validator(contract(contract_id), registry=registry())


def validate(contract_id: str, instance: Any, *, what: str = "value") -> None:
    """Validate *instance* against a contract, raising :class:`ContractError` on the first error."""
    _validate_document(_validator(contract_id), contract_id, instance, what=what)


def validate_as(contract_id: str, version: int, instance: Any, *, what: str = "value") -> None:
    """Validate *instance* against one explicit contract *version*.

    Used by a versioned contract (``cb.pack`` v1/v2) so an older document keeps its own frozen
    schema instead of being judged by the current one.
    """
    document = contract_as(contract_id, version)
    validator = Draft202012Validator(document, registry=registry())
    _validate_document(validator, contract_id, instance, what=what, version=version)


def _validate_document(
    validator: Draft202012Validator,
    contract_id: str,
    instance: Any,
    *,
    what: str,
    version: int | None = None,
) -> None:
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        label = contract_id if version is None else f"{contract_id} v{version}"
        raise ContractError(
            f"{what} violates {label} at {location}: {first.message}",
            contract_id=contract_id,
            path=location,
        )


def method_names() -> tuple[str, ...]:
    """Every frozen RPC method name."""
    return tuple(contract("cb.rpc")["$defs"]["method"]["enum"])


def method_schema(method: str) -> dict[str, Any]:
    """``{"request": ..., "response": ...}`` payload schemas for one method."""
    methods = contract("cb.rpc")["$defs"]["methods"]["properties"]
    if method not in methods:
        raise ContractError(f"method {method!r} is not in cb.rpc", contract_id="cb.rpc")
    entry = {k: v for k, v in methods[method].items() if k in ("request", "response")}
    missing = {"request", "response"} - set(entry)
    if missing:
        raise ContractError(
            f"method {method!r} is missing payload schema(s): {', '.join(sorted(missing))}",
            contract_id="cb.rpc",
        )
    return entry


def validate_request_payload(method: str, payload: Any) -> None:
    schema = {**method_schema(method)["request"], "$defs": contract("cb.rpc")["$defs"]}
    validator = Draft202012Validator(schema, registry=registry())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<payload>"
        raise ContractError(
            f"{method} request payload invalid at {location}: {first.message}",
            contract_id="cb.rpc",
            path=location,
        )


def validate_response_payload(method: str, result: Any) -> None:
    schema = {**method_schema(method)["response"], "$defs": contract("cb.rpc")["$defs"]}
    validator = Draft202012Validator(schema, registry=registry())
    try:
        validator.validate(result)
    except ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "<result>"
        raise ContractError(
            f"{method} handler returned a result outside the contract at {location}: {exc.message}",
            contract_id="cb.rpc",
            path=location,
        ) from exc


def definition_schema(contract_id: str, name: str) -> dict[str, Any]:
    """One ``$defs`` entry as a standalone schema, with its contract's definitions reachable.

    ``$defs`` entries are not independently addressable through :func:`validate`, so a consumer
    that validates a sub-record (a projection output, one list item) would otherwise restate the
    schema. ``$ref`` targets resolve against the merged document, which carries the same ``$id``
    and ``$defs`` as the contract file.
    """
    document = contract(contract_id)
    definitions = document.get("$defs") or {}
    if name not in definitions:
        raise ContractError(
            f"{contract_id} has no $defs/{name}", contract_id=contract_id, path=f"$defs/{name}"
        )
    return {**document, "$ref": f"#/$defs/{name}"}


def validate_definition(contract_id: str, name: str, instance: Any, *, what: str = "value") -> None:
    """Validate *instance* against one ``$defs`` entry, raising :class:`ContractError`."""
    validator = Draft202012Validator(definition_schema(contract_id, name), registry=registry())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise ContractError(
            f"{what} violates {contract_id}#/$defs/{name} at {location}: {first.message}",
            contract_id=contract_id,
            path=location,
        )


def error_catalog() -> dict[str, dict[str, Any]]:
    """Code -> ``{category, retryable, http, summary}``, straight from ``cb.errors``."""
    return dict(contract("cb.errors")["code_catalog"])


def error_codes() -> tuple[str, ...]:
    return tuple(contract("cb.errors")["$defs"]["error"]["properties"]["code"]["enum"])


def is_retryable(code: str) -> bool:
    return bool(error_catalog()[code]["retryable"])


def build_error(code: str, message: str, *, retryable: bool | None = None, **details: Any) -> dict[str, Any]:
    """Build a contract-legal error object; raises ``ContractError`` for an unknown code.

    ``retryable`` defaults to the code's catalogue value. A caller that knows *this* failure is
    deterministic (a constraint violation, a non-contract handler result) passes ``False``: the
    catalogue describes the code in general, not the specific failure.
    """
    catalog = error_catalog()
    if code not in catalog:
        raise ContractError(f"unknown error code {code!r}", contract_id="cb.errors")
    error: dict[str, Any] = {
        "code": code,
        "category": catalog[code]["category"],
        "message": message,
        "retryable": bool(catalog[code]["retryable"]) if retryable is None else bool(retryable),
    }
    if details:
        error["details"] = {k: v for k, v in details.items() if v is not None}
    return error


def schema_inventory() -> list[dict[str, Any]]:
    """The ``schema.get`` result body: id, version, file and hash per contract."""
    return [
        {
            "id": contract_id,
            "version": contract_version(contract_id),
            "file": CONTRACT_FILES[contract_id],
            "sha256": contract_sha256(contract_id),
        }
        for contract_id in sorted(CONTRACT_FILES)
    ]


def audit_contracts() -> list[str]:
    """Return human-readable problems; an empty list means the contract set is coherent.

    Checks the invariants that a JSON Schema alone cannot express across documents:
    unique ids, ``$id`` agreeing with the declared version, every ``$ref`` resolving to an
    *accepted* version of its target contract (current, or a frozen version still on disk and in
    ``CONTRACT_VERSION_FILES`` — a frozen wire contract may legitimately point at an older pack
    manifest), the error-code enum matching the catalog, and the RPC method enum matching the
    payload schemas one-for-one.
    """
    problems: list[str] = []
    seen_ids: set[str] = set()
    uri_by_contract: dict[str, str] = {}
    for contract_id in CONTRACT_FILES:
        document = contract(contract_id)
        uri = str(document["$id"])
        if uri in seen_ids:
            problems.append(f"duplicate $id {uri}")
        seen_ids.add(uri)
        uri_by_contract[contract_id] = uri
        version = document.get("x-contract-version")
        if not isinstance(version, int) or version < 1:
            problems.append(f"{contract_id}: x-contract-version must be a positive integer")
        elif not uri.endswith(f"/v{version}"):
            problems.append(f"{contract_id}: $id {uri} does not end with /v{version}")

    codes = set(error_codes())
    catalog = set(error_catalog())
    if codes != catalog:
        problems.append(
            "cb.errors code enum and code_catalog disagree: "
            f"enum-only={sorted(codes - catalog)} catalog-only={sorted(catalog - codes)}"
        )

    method_enum = list(contract("cb.rpc")["$defs"]["method"]["enum"])
    if len(method_enum) != len(set(method_enum)):
        problems.append("cb.rpc method enum contains duplicates")
    payload_schemas = contract("cb.rpc")["$defs"]["methods"]["properties"]
    if set(method_enum) != set(payload_schemas):
        problems.append(
            "cb.rpc method enum and $defs.methods disagree: "
            f"enum-only={sorted(set(method_enum) - set(payload_schemas))} "
            f"schema-only={sorted(set(payload_schemas) - set(method_enum))}"
        )
    for method in method_enum:
        entry = payload_schemas.get(method) or {}
        missing = {"request", "response"} - set(entry)
        if missing:
            problems.append(f"cb.rpc method {method!r} is missing payload schema(s): {', '.join(sorted(missing))}")

    # Cross-document references must target a version this build can resolve: the current one, or
    # a frozen version registered in CONTRACT_VERSION_FILES. A frozen wire contract is never
    # rewritten, so requiring the newest version here would force a byte change to `cb.rpc`.
    current_version: dict[str, int] = {}
    accepted_versions: dict[str, set[int]] = {}
    contract_by_base: dict[str, str] = {}
    for contract_id, uri in uri_by_contract.items():
        base, _, version = uri.rpartition("/v")
        current_version[base] = int(version)
        contract_by_base[base] = contract_id
        accepted_versions[base] = set(version_files(contract_id))
    vocabulary_prefix = uri_by_contract["cb.vocabulary"] + "#/$defs/"
    vocabulary_ids = set(contract("cb.vocabulary").get("$defs", {}))
    for contract_id in CONTRACT_FILES:
        for ref in _collect_refs(contract(contract_id)):
            if ref.startswith(vocabulary_prefix):
                name = ref[len(vocabulary_prefix):].split("/")[0]
                if name not in vocabulary_ids:
                    problems.append(
                        f"{contract_id}: references undefined vocabulary definition {name!r}"
                    )
            match = _CONTRACT_REF.match(ref)
            if match:
                base = f"https://contracts.coursebook.hermes/{match.group(1)}"
                ref_version = int(match.group(2))
                expected = current_version.get(base)
                if expected is None:
                    problems.append(f"{contract_id}: $ref targets unknown contract {ref}")
                elif ref_version not in accepted_versions[base]:
                    problems.append(
                        f"{contract_id}: $ref {ref} targets v{ref_version}, which this build does "
                        f"not accept (accepted: {sorted(accepted_versions[base])})"
                    )

    if WIRE_CONTRACT_ID not in CONTRACT_FILES:
        problems.append(f"wire contract {WIRE_CONTRACT_ID} is not in the inventory")
    elif contract_version(WIRE_CONTRACT_ID) != WIRE_CONTRACT_VERSION:
        problems.append(
            f"wire contract constant is v{WIRE_CONTRACT_VERSION} but {WIRE_CONTRACT_ID} is at "
            f"v{contract_version(WIRE_CONTRACT_ID)}"
        )
    return problems


_CONTRACT_REF = re.compile(r"^https://contracts\.coursebook\.hermes/([a-z0-9-]+)/v(\d+)(?:#|$)")


def _collect_refs(node: Any) -> Iterable[str]:
    """Every ``$ref`` string in a parsed contract document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _collect_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _collect_refs(item)
