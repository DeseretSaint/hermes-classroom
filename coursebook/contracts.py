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
    "cb.errors": "errors.v2.json",
    "cb.rpc": "rpc.v10.json",
    "cb.db": "db.v6.json",
    "cb.jobs": "jobs.v2.json",
    "cb.pack": "pack-manifest.v1.json",
    "cb.projection": "projection.v1.json",
}

#: The contract whose version the plugin speaks on the wire.
WIRE_CONTRACT_ID = "cb.rpc"
WIRE_CONTRACT_VERSION = 10


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
    """Cross-document resolver for the absolute ``$ref`` targets the contracts use."""
    resources: list[tuple[str, Resource]] = []
    for contract_id in CONTRACT_FILES:
        document = contract(contract_id)
        resources.append((str(document["$id"]), Resource.from_contents(document, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def _validator(contract_id: str) -> Draft202012Validator:
    return Draft202012Validator(contract(contract_id), registry=registry())


def validate(contract_id: str, instance: Any, *, what: str = "value") -> None:
    """Validate *instance* against a contract, raising :class:`ContractError` on the first error."""
    errors = sorted(_validator(contract_id).iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise ContractError(
            f"{what} violates {contract_id} at {location}: {first.message}",
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
    unique ids, ``$id`` agreeing with the declared version, every ``$ref`` resolving to the
    *current* version of its target contract, the error-code enum matching the catalog, and the
    RPC method enum matching the payload schemas one-for-one.
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

    # Cross-document references must target the version currently in the inventory.
    current_version: dict[str, int] = {}
    for contract_id, uri in uri_by_contract.items():
        base, _, version = uri.rpartition("/v")
        current_version[base] = int(version)
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
                elif ref_version != expected:
                    problems.append(
                        f"{contract_id}: $ref {ref} targets v{ref_version} but {base} is at v{expected}"
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
