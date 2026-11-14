"""Derive ``contracts/rpc.v29.json`` from the frozen v28 document.

Run from the repository root::

    python3 probes/derive_rpc_v29.py

The amendment is written **onto a parsed v28**, never typed as a second copy of a 13,000-line
document: every record this delta does not name survives by being carried, so a hand-copy cannot
silently drop one.

The output is byte-identical to the repository's own serialisation (``json.dumps`` with
``indent=2`` and ``ensure_ascii=False`` plus a trailing newline), which the script asserts against
v28 first: if the round trip of the input document is not byte-exact, the formatting contract has
changed and the script refuses to write a v29 that would diff in every line.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v28.json"
TARGET = ROOT / "contracts" / "rpc.v29.json"

#: The v29 header. It states the delta, then carries v28's own description verbatim, which is how
#: every earlier amendment recorded its ancestry in the same field.
DELTA = (
    "v29 is one additive amendment over v28 (the plan gate carries its own time estimate): "
    "`outline_plan` gains one optional nullable `time_estimate` object, projected from the "
    "plan's stored `schedule_json`, so the review screen can say 'About N weeks' beside the plan "
    "state instead of promising an estimate the read never served. The object carries the "
    "authored `weeks`, `sessions_per_week`, `minutes_per_session`, `basis` and `confidence`; a "
    "plan whose schedule declares no usable weeks projects `null`, and no figure is invented. "
    "Every new key is optional, every response that omits it keeps its exact v28 shape, and no "
    "method, required key, error code, job kind, answer kind, verdict, evidence class or "
    "vocabulary value moves. `contracts/rpc.v28.json` stays byte-identical history and "
    "`x-supersedes` names it."
)

#: The plan's authored estimate, narrowed to the facts the review gate renders. It is closed:
#: an older or hand-edited schedule cannot leak an unbounded field through this read.
TIME_ESTIMATE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["weeks", "sessions_per_week", "minutes_per_session", "basis", "confidence"],
    "properties": {
        "weeks": {
            "type": "integer",
            "minimum": 1,
            "maximum": 104,
            "description": "The plan's authored `time_estimate.weeks`: a planning estimate, never an attainment claim.",
        },
        "sessions_per_week": {
            "oneOf": [
                {"type": "integer", "minimum": 1, "maximum": 14},
                {"type": "null"},
            ],
            "description": "The authored sessions per week, or null when the stored estimate does not declare a usable integer.",
        },
        "minutes_per_session": {
            "oneOf": [
                {"type": "integer", "minimum": 5, "maximum": 240},
                {"type": "null"},
            ],
            "description": "The authored minutes per session, or null when the stored estimate does not declare a usable integer.",
        },
        "basis": {
            "oneOf": [
                {"type": "string", "enum": ["fsi", "derived", "model", "none"]},
                {"type": "null"},
            ],
            "description": "How the estimate was reached, in the plan's own vocabulary.",
        },
        "confidence": {
            "oneOf": [
                {"type": "string", "enum": ["low", "medium", "high"]},
                {"type": "null"},
            ],
            "description": "The plan's own confidence in the estimate.",
        },
    },
    "description": (
        "The plan's stored schedule estimate, projected for the approval gate. `weeks` is the "
        "only figure the screen promises; every other field is the author's own declared context "
        "and is null when absent. The object is not a readiness, mastery or attainment claim."
    ),
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def derive(source: dict) -> dict:
    """v28 plus the plan time estimate and the four wire echoes, and nothing else."""
    if int(source["x-contract-version"]) != 28:
        raise SystemExit(f"expected rpc.v28.json, found v{source['x-contract-version']}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    document["$id"] = f"{base}/v29"
    document["title"] = "Coursebook backend RPC v29"
    document["x-contract-version"] = 29
    document["x-supersedes"] = f"{base}/v28"
    document["description"] = f"{DELTA} {source['description']}"

    definitions = document["$defs"]
    if "outline_time_estimate" in definitions:
        raise SystemExit("$defs/outline_time_estimate already exists")
    definitions["outline_time_estimate"] = TIME_ESTIMATE
    plan = definitions["outline_plan"]
    if "time_estimate" in plan["properties"]:
        raise SystemExit("outline_plan already carries time_estimate")
    plan["properties"]["time_estimate"] = {
        "oneOf": [
            {"$ref": "#/$defs/outline_time_estimate"},
            {"type": "null"},
        ],
        "description": (
            "The plan's own estimate, or null when its schedule declares none. Additive in v29; "
            "a v28 client that never reads it keeps its exact shape."
        ),
    }

    # The four places the wire version is echoed: the request envelope and the two response
    # envelopes of the transport, plus health.get's own result.
    echoes = [
        document["$defs"]["envelope_request"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_ok"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_error"]["properties"]["contract_version"],
        document["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"]
        ["contract_version"],
    ]
    for echo in echoes:
        if echo.get("const") != 28:
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
    target = serialise(derive(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
