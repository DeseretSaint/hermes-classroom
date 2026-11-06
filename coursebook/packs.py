"""Pack manifest seam.

``cb.pack`` is the authority for the pack document. This module validates a manifest and
exposes the bounded limits; archive staging, MIME/hash verification, atomic adopt and export
allowlisting belong to the pack work package (implementer: Lattice).

Security posture (``PREBUILD_SPEC.md`` §11, ``AUDIT.md`` R6/H6/H7): a pack is untrusted data.
Its prose never becomes ``AGENTS.md`` policy, never carries executable code or tool calls, and
never contains learning history. Validation is allowlist-first: unknown fields are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import ContractError, contract, validate

CONTRACT_ID = "cb.pack"

#: Fields that must never appear in an exported or imported pack, by construction.
EXCLUDED_BY_CONSTRUCTION: tuple[str, ...] = tuple(contract(CONTRACT_ID)["excluded_by_construction"])


class PackRejected(ValueError):
    """A pack failed contract validation. Maps to ``PACK_REJECTED``; nothing was adopted."""


def limits() -> dict[str, int]:
    return {key: int(value) for key, value in contract(CONTRACT_ID)["limits"].items()}


def root_file() -> str:
    return str(contract(CONTRACT_ID)["root_file"])


def validate_manifest(document: Any) -> None:
    """Validate a parsed pack manifest against ``cb.pack``.

    Raises :class:`PackRejected` with the failing location. Callers must not adopt any content
    until this returns cleanly.
    """
    try:
        validate(CONTRACT_ID, document, what="pack manifest")
    except ContractError as exc:
        raise PackRejected(str(exc)) from exc


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Read and validate ``pack.json`` from disk. JSON only — never YAML, never executable."""
    manifest_path = Path(path)
    if manifest_path.name != root_file():
        raise PackRejected(f"pack manifest must be named {root_file()!r}, got {manifest_path.name!r}")
    size = manifest_path.stat().st_size
    maximum = limits()["max_manifest_bytes"]
    if size > maximum:
        raise PackRejected(f"pack manifest is {size} bytes, over the {maximum}-byte limit")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackRejected(f"pack manifest is unreadable: {exc}") from exc
    validate_manifest(document)
    return document


def export_allowlist() -> tuple[str, ...]:
    """Top-level manifest fields permitted in an exported pack.

    Export builds a fresh document from these fields; it never copies a stored manifest, which is
    how personal notes, attempts and notebook text stay out by construction.
    """
    return tuple(contract(CONTRACT_ID)["properties"].keys())
