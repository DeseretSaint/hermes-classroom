"""Derive ``contracts/rpc.v29.json`` from the frozen v28 document.

Run from the repository root::

    python3 probes/derive_rpc_v29.py

Upgrade 36 adds one nullable object to ``cb.jobs`` — ``job.activity.retry``, the last failed
lesson-section authoring attempt. Every job item on the wire is a reference to the current
``cb.jobs`` document, so the amendment is a reference refresh: v29 is v28 byte-for-byte apart
from ``$id``, ``x-contract-version``, ``x-supersedes``, the description, the four wire-version
echoes and every ``cb.jobs/v5`` reference, which moves to ``/v6``. No method, request, response
field, error code, job kind or state moves.

Derived onto a parsed v28, never typed as a second copy of a 13,000-line document. The output is
byte-identical to the repository's own serialisation, which the script asserts against v28 first.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v28.json"
TARGET = ROOT / "contracts" / "rpc.v29.json"

JOBS_V5 = "https://contracts.coursebook.hermes/jobs/v5"
JOBS_V6 = "https://contracts.coursebook.hermes/jobs/v6"

DELTA = (
    "v29 is one reference refresh over v28 (Upgrade 36, a repair attempt is visible while it "
    "happens): `cb.jobs` v6 adds one nullable `retry` object to `job.activity`, the last failed "
    "lesson-section authoring attempt recorded against the job — section ordinal, the attempt "
    "that failed and the total, a bounded reason with the answer key withheld, and the prompt "
    "version. The lesson stage re-authors a refused section up to its attempt limit, so a run "
    "that will end on a repair screen can be named while it waits instead of looking identical to "
    "a run going well. `jobs.list`'s item `$ref` moves from `cb.jobs/v5#/job` to "
    "`cb.jobs/v6#/job` (`jobs.get`'s `job` is the documented open object, so the read itself "
    "needs no retype); `retry` is null when no attempt has failed. No method is added, no "
    "request or response field is retyped, no error code, job kind, state, transition or progress "
    "value moves, and `contracts/rpc.v28.json` stays byte-identical history (`x-supersedes` names "
    "it)."
)

ECHO_PATHS = (
    ("$defs", "envelope_request", "properties", "contract_version"),
    ("$defs", "envelope_response_ok", "properties", "contract_version"),
    ("$defs", "envelope_response_error", "properties", "contract_version"),
    ("$defs", "methods", "properties", "health.get", "response", "properties", "contract_version"),
)


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _move_refs(node: object) -> int:
    """Replace every ``cb.jobs/v5`` reference with ``cb.jobs/v6``; return how many moved."""
    moved = 0
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if isinstance(value, str) and JOBS_V5 in value:
                node[key] = value.replace(JOBS_V5, JOBS_V6)
                moved += 1
            else:
                moved += _move_refs(value)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, str) and JOBS_V5 in value:
                node[index] = value.replace(JOBS_V5, JOBS_V6)
                moved += 1
            else:
                moved += _move_refs(value)
    return moved


def derive(source: dict) -> dict:
    if int(source["x-contract-version"]) != 28:
        raise SystemExit(f"expected rpc.v28.json, found v{source['x-contract-version']}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    document["$id"] = f"{base}/v29"
    document["title"] = "Coursebook backend RPC v29"
    document["x-contract-version"] = 29
    document["x-supersedes"] = f"{base}/v28"
    document["description"] = f"{DELTA} {source['description']}"

    moved = _move_refs(document)
    if moved == 0:
        raise SystemExit("no cb.jobs/v5 reference found; v29 would be a no-op refresh")

    for path in ECHO_PATHS:
        node: object = document
        for part in path:
            node = node[part]  # type: ignore[index]
        if node.get("const") != 28:  # type: ignore[union-attr]
            raise SystemExit(f"unexpected wire echo at {'.'.join(path)}: {node!r}")
        node["const"] = 29  # type: ignore[index]
    return document


def main() -> int:
    raw = SOURCE.read_text(encoding="utf-8")
    source = json.loads(raw)
    if serialise(source) != raw:
        raise SystemExit(
            "rpc.v28.json does not round-trip under this serialiser; refusing to write a v29 "
            "whose diff would be every line"
        )
    target = serialise(derive(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
