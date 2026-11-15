"""Derive ``contracts/rpc.v29.json`` — the upgrade-7 plan-exclusions delta.

Run from the repository root::

    python3 probes/derive_rpc_v29_plan_exclusions.py

The amendment is written **onto a parsed document**, never typed as a second copy of a
13,000-line contract: every record this delta does not name is carried, so a hand-copy cannot
silently drop one.

The delta is additive and has two parts:

* ``course.outline``'s ``outline_plan`` may carry one optional ``exclusions`` array — the plan's
  own declaration of what this course will not cover, including a capability research could not
  support. Entries are bounded (eight sentences of at most 240 characters). The array is optional
  and absent from a server that does not project it, so every v28 payload keeps its exact shape.
* the four places the wire version is echoed move to 29.

One contract version carries every additive change shipped together, so this script **composes**:
``probes/derive_rpc_v29.py`` writes the base deltas first and applies this one on top (and applies
it again on every re-run, which rewrites identical bytes). Running it directly on a tree whose
``contracts/rpc.v29.json`` already declares 29 composes over that document instead of forking it.
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
    "every v28 record keeps its exact bytes."
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


def _source_document() -> tuple[dict, bool]:
    """``(document, composed)`` — the v29 already on disk when a sibling derived one, else v28."""
    if TARGET.exists():
        existing = json.loads(TARGET.read_text(encoding="utf-8"))
        if int(existing.get("x-contract-version", 0)) == 29:
            return existing, True
        raise SystemExit(f"{TARGET.name} exists but is not version 29; refusing to overwrite it")
    return json.loads(SOURCE.read_text(encoding="utf-8")), False


def derive(source: dict, *, composed: bool = False) -> dict:
    """The upgrade-7 delta applied to v28 (or to a v29 being composed), and nothing else."""
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
    elif DELTA not in str(document.get("description", "")):
        # Composing over a sibling's v29 keeps its delta text, then carries this one. Test the
        # whole description, not its prefix: siblings are folded in name order and each prepends
        # its own banner, so on the union this delta no longer sits first and a prefix test
        # would prepend it a second time on every re-run.
        document["description"] = f"{DELTA} {document['description']}"

    plan = document["$defs"]["outline_plan"]
    # Set, not add: a composed v29 may already carry this delta, and re-running the derivation
    # must leave these exact bytes rather than refusing a second time.
    plan["properties"]["exclusions"] = EXCLUSIONS

    echoes = [
        document["$defs"]["envelope_request"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_ok"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_error"]["properties"]["contract_version"],
        document["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"]
        ["contract_version"],
    ]
    for echo in echoes:
        if echo.get("const") not in (28, 29):
            raise SystemExit(f"unexpected wire echo {echo!r}")
        echo["const"] = 29
    return document


def main() -> int:
    base_document, composed = _source_document()
    # Guard whichever document is actually being re-serialised: a v29 that does not round-trip
    # would otherwise be rewritten as a diff of every line, and a v28 that does not is the
    # fork this probe exists to refuse.
    source_path = TARGET if composed else SOURCE
    raw = source_path.read_text(encoding="utf-8")
    source = json.loads(raw)
    if serialise(source) != raw:
        raise SystemExit(
            f"{source_path.name} does not round-trip under this serialiser; refusing to write a "
            "v29 whose diff would be every line"
        )
    target = serialise(derive(base_document, composed=composed))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
