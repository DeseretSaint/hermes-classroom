"""Derive ``contracts/rpc.v29.json`` — the upgrade-7 plan-exclusions delta over v28.

Run from the repository root::

    python3 probes/derive_rpc_v29.py

The amendment is written **onto a parsed v28**, never typed as a second copy of a 13,000-line
document: every record this delta does not name is carried, so a hand-copy cannot silently drop
one.

The delta is additive and has two parts:

* ``course.outline``'s ``outline_plan`` may carry one optional ``exclusions`` array — the plan's
  own declaration of what this course will not cover, including a capability research could not
  support. Entries are bounded (eight sentences of at most 240 characters). The array is optional
  and absent from a server that does not project it, so every v28 payload keeps its exact shape.
* the four places the wire version is echoed move to 29.

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

DELTA = (
    "v29 is one additive amendment over v28 (upgrade 7, plan review declares its exclusions): "
    "`outline_plan` gains one optional `exclusions` array — the plan's own statement of what this "
    "course will not cover, including a capability the research could not support. The plan stage "
    "already records those sentences in `plans.schedule_json`; this read carries them to the "
    "review that approves the plan, so a learner cannot approve a course narrower than the goal "
    "without being told. Entries are bounded to eight sentences of at most 240 characters, and "
    "two pipeline-authored prefixes (`Not covered — no supporting source:` and `Scope shortfall — "
    "fewer supporting capabilities:`) are stripped by the review before it shows the sentence, "
    "with the raw entry kept behind a disclosure. A plan that declared none omits the array, so "
    "every v28 record keeps its exact bytes. No method, required key, error code, job kind, "
    "answer kind, verdict, evidence class or vocabulary value moves; `contracts/rpc.v28.json` "
    "stays byte-identical history and `x-supersedes` names it."
)

EXCLUSIONS = {
    "type": "array",
    "maxItems": 8,
    "description": (
        "The plan's own declaration of what this course will not cover, including a goal "
        "capability the research could not support. Bounded: eight entries of at most 240 "
        "characters. The entries may carry the authoring rules' own prefixes; a review strips "
        "the two known prefixes for the sentence it shows and keeps the raw entry behind a "
        "disclosure. A plan that declared no exclusions omits this key."
    ),
    "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 240,
    },
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def derive(source: dict) -> dict:
    """The upgrade-7 delta applied to v28, and nothing else."""
    version = int(source["x-contract-version"])
    if version != 28:
        raise SystemExit(f"expected rpc.v28.json, found v{version}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    document["$id"] = f"{base}/v29"
    document["title"] = "Coursebook backend RPC v29"
    document["x-contract-version"] = 29
    document["x-supersedes"] = f"{base}/v28"
    document["description"] = f"{DELTA} {source['description']}"

    plan = document["$defs"]["outline_plan"]
    if "exclusions" in plan["properties"]:
        raise SystemExit("outline_plan.exclusions is already present")
    plan["properties"]["exclusions"] = EXCLUSIONS

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
