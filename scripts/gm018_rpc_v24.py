"""Build ``contracts/rpc.v24.json``: the take-home HTML document as cb.rpc v24.

GM-018 appends exactly one method to the frozen v23 surface — ``takehome.html``, which returns
the pack's self-contained HTML document (the learner page and, for a parent pack, the parent
guide and the separate answer guide) with the same page composition as the PDF. No v23 method,
request shape, required key, error code, job kind or vocabulary value moves, and ``rpc.v23.json``
stays byte-identical history.

The script **composes** rather than overwrites: if a ``rpc.v24.json`` already exists (another
in-flight amendment, e.g. GM-007's homework family), every one of its methods and ``$defs`` is
kept and this amendment is appended. Re-running it is idempotent, so the integration card can
regenerate the contract once after any merge without re-deciding a schema.

Run from the repository root:

    python3 scripts/gm018_rpc_v24.py
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
V23 = CONTRACTS / "rpc.v23.json"
TARGET = CONTRACTS / "rpc.v24.json"

IDENT = "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/identifier"
SHA = "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/sha256_hash"

METHOD = "takehome.html"

DESCRIPTION = (
    "v24 appends one additive method (GM-018, take-home print follow-ups): `takehome.html` "
    "returns the stored take-home pack as a self-contained, selectable-text HTML document that "
    "shares the PDF page composition — the learner page for a learner pack, plus the parent guide "
    "and the separate parent-only answer guide for a parent pack. The document carries the "
    "document title, its language, escaped text, no scripts, no images and no external fetch; a "
    "captioned plate keeps its text alternative as an accessible region label. It is returned as "
    "content, not as a second download handle: `artifact.get` remains the only download handle, "
    "and HTML is never adopted into the artifact store. No method, request shape, required key, "
    "error code, job kind, answer kind, verdict, evidence class or vocabulary value moves; "
    "`rpc.v23.json` stays byte-identical history and `x-supersedes` names it. "
)


def _object(required, properties) -> OrderedDict:
    node: OrderedDict = OrderedDict()
    node["type"] = "object"
    node["additionalProperties"] = False
    node["required"] = list(required)
    node["properties"] = OrderedDict(properties)
    return node


def method_entry() -> OrderedDict:
    request = _object(
        ("pack_id",),
        [("pack_id", {"$ref": IDENT})],
    )
    response = _object(
        ("pack_id", "title", "language", "mime", "pages", "html", "document_hash"),
        [
            ("pack_id", {"$ref": IDENT}),
            ("title", {"type": "string", "minLength": 1, "maxLength": 300}),
            ("language", {"type": "string", "minLength": 2, "maxLength": 35}),
            ("mime", {"const": "text/html"}),
            ("pages", {"type": "integer", "minimum": 1, "maximum": 12}),
            ("html", {"type": "string", "minLength": 1, "maxLength": 400000}),
            ("document_hash", {"$ref": SHA}),
        ],
    )
    entry: OrderedDict = OrderedDict()
    entry["type"] = "object"
    entry["request"] = request
    entry["response"] = response
    return entry


def build() -> dict:
    source = TARGET if TARGET.exists() else V23
    base = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    document: OrderedDict = OrderedDict()
    for key, value in base.items():
        document[key] = value
    already = METHOD in base["$defs"]["method"]["enum"]
    document["$id"] = "https://contracts.coursebook.hermes/rpc/v24"
    document["title"] = "Coursebook backend RPC v24"
    if not already:
        document["description"] = DESCRIPTION + str(base.get("description") or "")
    document["x-contract-version"] = 24
    document["x-supersedes"] = "https://contracts.coursebook.hermes/rpc/v23"
    defs = document["$defs"]
    if not already:
        defs["method"]["enum"] = list(defs["method"]["enum"]) + [METHOD]
        defs["methods"]["properties"][METHOD] = method_entry()
    _bump_echoes(document)
    return document


def _bump_echoes(node) -> None:
    """Every ``contract_version`` echo in the copied body moves with the document identity."""
    if isinstance(node, dict):
        version = node.get("contract_version")
        if isinstance(version, dict) and "const" in version:
            version["const"] = 24
        for value in node.values():
            _bump_echoes(value)
    elif isinstance(node, list):
        for value in node:
            _bump_echoes(value)


def main() -> None:
    document = build()
    TARGET.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    methods_count = len(document["$defs"]["method"]["enum"])
    print(f"wrote {TARGET.relative_to(ROOT)}: {methods_count} declared methods")


if __name__ == "__main__":
    main()
