"""Derive ``contracts/rpc.v29.json`` — the review-interval delta over v28.

Run from the repository root::

    python3 probes/derive_rpc_v29_review_interval.py

The card (UP-18) changes one learner surface: the due date of a review item is still arithmetic
over the target's declared ladder, but the *starting* rung is now read from the attempt record
(a pass that needed two tries, a hint or a shown answer starts lower, and a shown answer or a miss
returns on the short beat). A learner can only see why if the wire carries the explanation, and
``review_item`` was a closed object with no slot for it.

This amendment is additive and has two parts:

* ``review_item.interval_reason`` — an optional, learner-worded sentence naming what the learner
  did and when the item comes back ("You needed two tries, so this comes back tomorrow."). It is
  never a reason code, a stage name or an evidence class; the scheduler builds it
  (``coursebook.review._interval_reason``) and the pane renders it as prose.
* the four places the wire version is echoed move to 29.

No method, required key, error code, job kind, answer kind, verdict, evidence class or vocabulary
value moves; every response that omits the key keeps its exact v28 shape and bytes, and
``contracts/rpc.v28.json`` stays byte-identical history with ``x-supersedes`` naming it.

A sibling card may derive its own v29 from the same v28 (UP-14, the authored hint ladder). One
contract version must carry every additive change shipped together, so this script *composes*: if
``contracts/rpc.v29.json`` is already on the tree and declares version 29, it is the source and
only this card's delta is applied on top. Running it twice is a no-op that rewrites identical
bytes.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v28.json"
TARGET = ROOT / "contracts" / "rpc.v29.json"

DELTA = (
    "v29 is one additive amendment over v28 (UP-18, how a review interval was earned): "
    "`review_item` may carry `interval_reason` — one short sentence in the learner's own words "
    "saying which part of their attempt record set the date (a first try with no help, a hint, "
    "more than one try, a miss, or a shown answer) and when the item returns. The key is optional: "
    "an item with no attempt record behind it omits it, and every response that omits it keeps its "
    "exact v28 shape and bytes. The interval itself stays arithmetic over the target's declared "
    "ladder and is still never an attainment prediction; the reason is prose, never a reason code, "
    "stage name or evidence class. No method, required key, error code, job kind, answer kind, "
    "verdict, evidence class or vocabulary value moves; `contracts/rpc.v28.json` stays "
    "byte-identical history and `x-supersedes` names it."
)

INTERVAL_REASON = {
    "oneOf": [
        {"type": "string", "minLength": 1, "maxLength": 200},
        {"type": "null"},
    ],
    "description": (
        "Why this date, in the learner's words: what the attempt record shows (a first try with "
        "no help, a hint, two or more tries, a miss, a shown answer) and when the item returns. "
        "Prose only — never a reason code, a stage name or an evidence class. Null when no "
        "committed attempt stands behind the date, because then there is nothing to explain."
    ),
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


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

    item = document["$defs"]["review_item"]
    # Set, not add: a composed v29 may already carry a sibling's delta, and re-running this
    # derivation must leave these exact bytes rather than a second definition.
    item["properties"]["interval_reason"] = INTERVAL_REASON

    methods = document["$defs"]["methods"]["properties"]
    echoes = [
        document["$defs"]["envelope_request"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_ok"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_error"]["properties"]["contract_version"],
        methods["health.get"]["response"]["properties"]["contract_version"],
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
