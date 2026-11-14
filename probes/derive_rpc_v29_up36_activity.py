"""Derive ``contracts/rpc.v29.json`` — the Upgrade 36 job-reference delta over v28.

Run from the repository root::

    python3 probes/derive_rpc_v29_up36_activity.py

Upgrade 36 makes a refused lesson section readable while it is still being repaired. A section
that a deterministic rule or the independent validator refuses is re-authored up to
``LESSON_ATTEMPTS`` (3) times; nothing durable marked a refusal, so a run that would end on a
repair screen looked identical to one that was going well. ``cb.jobs`` **v6** adds one required,
nullable ``activity.retry`` object (the last failed lesson-section attempt) and this wire refresh
points at it.

This amendment is a *reference refresh*, and it is additive:

* every ``cb.jobs/v5`` reference in the document moves to ``cb.jobs/v6`` — the ``jobs.list`` item
  ``$ref`` and the two ``$defs/job_state`` refs that name the same document version. ``jobs.get``'s
  ``job`` is the documented open object, so the read itself needs no retype.
* the four places the wire version is echoed move to 29.

No method, request or response field, error code, job kind, state, transition or progress value
moves; every v28 record that names no ``cb.jobs`` reference keeps its exact v28 shape and bytes, and
``contracts/rpc.v28.json`` stays byte-identical history with ``x-supersedes`` naming it.

One contract version must carry every additive change shipped together, so this script *composes*:
if ``contracts/rpc.v29.json`` is already on the tree and declares version 29, it is the source and
only this card's delta is applied on top. ``probes/derive_rpc_v29.py`` also loads this file as a
sibling delta (``derive(document, composed=True)``), so the shipped document is the union of the
wave rather than a second, forked v29.
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
    "v29 also refreshes the job reference (Upgrade 36, a repair attempt is visible while it "
    "happens): `cb.jobs` v6 adds one nullable `retry` object to `job.activity`, the last failed "
    "lesson-section authoring attempt recorded against the job — section ordinal, the attempt that "
    "failed and the total, a bounded reason with the answer key withheld, and the prompt version. "
    "The lesson stage re-authors a refused section up to its attempt limit, so a run that will end "
    "on a repair screen can be named while it waits instead of looking identical to a run going "
    "well. Every `cb.jobs/v5` reference moves to `cb.jobs/v6` (`jobs.list`'s item `$ref` and the "
    "two `job_state` refs); `retry` is null when no attempt has failed. No method is added, no "
    "request or response field is retyped, no error code, job kind, state, transition or progress "
    "value moves, and `contracts/rpc.v28.json` stays byte-identical history (`x-supersedes` names "
    "it)."
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


def _source_document() -> tuple[dict, bool]:
    """``(document, composed)`` — the v29 already on disk when a sibling derived one, else v28."""
    if TARGET.exists():
        existing = json.loads(TARGET.read_text(encoding="utf-8"))
        if int(existing.get("x-contract-version", 0)) == 29:
            return existing, True
        raise SystemExit(f"{TARGET.name} exists but is not version 29; refusing to overwrite it")
    return json.loads(SOURCE.read_text(encoding="utf-8")), False


def derive(source: dict, *, composed: bool = False) -> dict:
    version = int(source["x-contract-version"])
    if version not in (28, 29):
        raise SystemExit(f"expected rpc v28 (or a v29 to compose with), found v{version}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    if version == 28:
        document["$id"] = f"{base}/v29"
        document["title"] = "Coursebook backend RPC v29"
        document["x-contract-version"] = 29
        document["x-supersedes"] = f"{base}/v28"
        document["description"] = f"{DELTA} {source['description']}"
    elif not str(document.get("description", "")).startswith(DELTA):
        # Composing over a sibling's v29 keeps its delta text, then carries this one.
        document["description"] = f"{DELTA} {document['description']}"

    # Set, not add: a composed v29 may already carry a sibling's delta, and re-running this
    # derivation must leave these exact bytes rather than a second refresh.
    moved = _move_refs(document)
    if moved == 0 and not composed and version == 28:
        raise SystemExit("no cb.jobs/v5 reference found; v29 would be a no-op refresh")
    if moved not in (0, 3):
        raise SystemExit(f"expected three cb.jobs/v5 references to refresh, moved {moved}")

    echoes = [
        document["$defs"]["envelope_request"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_ok"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_error"]["properties"]["contract_version"],
        document["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"][
            "contract_version"
        ],
    ]
    for echo in echoes:
        if echo.get("const") not in (28, 29):
            raise SystemExit(f"unexpected wire echo {echo!r}")
        echo["const"] = 29
    return document


def main() -> int:
    raw = SOURCE.read_text(encoding="utf-8")
    source = json.loads(raw)
    if serialise(source) != raw:
        raise SystemExit(
            "rpc.v28.json does not round-trip under this serialiser; refusing to write a v29 "
            "whose diff would be every line"
        )
    base_document, composed = _source_document()
    document = derive(base_document, composed=composed)
    target = serialise(document)
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
