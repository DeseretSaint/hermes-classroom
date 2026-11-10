"""Build ``contracts/rpc.v24.json``: the GM-004 World Studio amendment as part of cb.rpc v24.

``cb.rpc`` v24 is **one document** composed of three independent additive amendments over GM-005's
v23: GM-007's away-from-screen homework family, GM-018's ``takehome.html``, and this one, GM-004's
World Studio family. The composition order is fixed:

    python3 scripts/gm007_rpc_v24.py   # v23 + four homework.* (rebuilds the document)
    python3 scripts/gm018_rpc_v24.py   # + takehome.html (composes onto the existing v24)
    python3 scripts/gm004_rpc_v24.py   # + world.read/style.preview/generate/approve + course.mode.set

Like ``gm018_rpc_v24.py`` this script **composes** rather than overwrites: every method and
``$defs`` entry already in ``rpc.v24.json`` is kept and this amendment is appended. Re-running it
is idempotent, so an integration merge can regenerate the contract once without re-deciding a
schema. The additive fragment itself is ``scripts/gm004_world_fragment.json``, lifted verbatim from
GM-004's reviewed document (``wt/gm-004-world-ui`` @ ``bf3c4c2``).

No v23 method, request shape, required key, error code, job kind, answer kind, verdict, evidence
class or vocabulary value moves; ``rpc.v23.json`` stays byte-identical history (sha256
``b8988994d36cf7e422da0010ed157d3c4ff7dd69b5f8453e9bd7da8b8b4d3182``) and ``x-supersedes`` names it.

Run from the repository root:

    python3 scripts/gm004_rpc_v24.py
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
V23 = CONTRACTS / "rpc.v23.json"
TARGET = CONTRACTS / "rpc.v24.json"
FRAGMENT = Path(__file__).resolve().parent / "gm004_world_fragment.json"

METHODS = (
    "world.read",
    "world.style.preview",
    "world.generate",
    "world.approve",
    "course.mode.set",
)

DESCRIPTION = (
    "v24 is one composed additive amendment over v23: GM-007's four away-from-screen `homework.*` "
    "methods, GM-018's `takehome.html`, and this GM-004 World Studio part. GM-004 appends the four "
    "`world.*` methods frozen by GM-001 in `coursebook/gm_contract.py` (world.read, "
    "world.style.preview, world.generate, world.approve) together with the documented extra "
    "`course.mode.set`, and `course.create` gains one optional `presentation_mode` field so a new "
    "course records Game intent at creation. World plates are textless orientation art; the read "
    "never generates art and never writes the mode. A style choice and a final kit approval are two "
    "separate hash-fenced facts. The composed document declares 93 methods. No v1-v23 method, "
    "request shape, required key, error code, job kind or vocabulary value moves; "
    "`contracts/rpc.v23.json` stays byte-identical. "
)


def build() -> dict:
    source = TARGET if TARGET.exists() else V23
    base = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    fragment = json.loads(FRAGMENT.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    document: OrderedDict = OrderedDict()
    for key, value in base.items():
        document[key] = value
    document["$id"] = "https://contracts.coursebook.hermes/rpc/v24"
    document["title"] = "Coursebook backend RPC v24"
    document["x-contract-version"] = 24
    document["x-supersedes"] = "https://contracts.coursebook.hermes/rpc/v23"
    defs = document["$defs"]
    already = all(method in defs["method"]["enum"] for method in METHODS)
    if not already:
        if "GM-004" not in str(base.get("description") or ""):
            document["description"] = DESCRIPTION + str(base.get("description") or "")
        defs["method"]["enum"] = list(defs["method"]["enum"]) + list(METHODS)
        for name in METHODS:
            if name not in defs["methods"]["properties"]:
                defs["methods"]["properties"][name] = fragment["methods"][name]
        for name, value in fragment["defs"].items():
            if name not in defs:
                defs[name] = value
        create = defs["methods"]["properties"]["course.create"]["request"]["properties"]
        if "presentation_mode" not in create:
            create["presentation_mode"] = fragment["course_create_presentation_mode"]
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
