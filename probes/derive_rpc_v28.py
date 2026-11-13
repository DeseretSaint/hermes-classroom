"""Derive ``contracts/rpc.v28.json`` from the frozen v27 document.

Run from the repository root::

    python3 probes/derive_rpc_v28.py

The amendment (E2E L1, a passed generated section can be checked again) is written **onto a parsed
v27**, never typed as a second copy of a 13,000-line document: every record this delta does not
name — the method enum, the E2E L4/L5 lesson fields another card holds, the error and job
references — survives by being carried, so a hand-copy cannot silently drop one.

The output is byte-identical to the repository's own serialisation (``json.dumps`` with
``indent=2`` and ``ensure_ascii=False`` plus a trailing newline), which the script asserts against
v27 first: if the round trip of the input document is not byte-exact, the formatting contract has
changed and the script refuses to write a v28 that would diff in every line.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v27.json"
TARGET = ROOT / "contracts" / "rpc.v28.json"

#: The v28 header. It states the delta, then carries v27's own description verbatim, which is how
#: every earlier amendment recorded its ancestry in the same field.
DELTA = (
    "v28 is one additive amendment over v27 (E2E L1, a passed generated section can be checked "
    "again): `check.open`, `check.get` and `progression.challenge_out` responses gain one optional "
    "boolean, `revisit`; each `lesson.page.checks` row gains the same optional key; "
    "`lesson.page.section` gains `sections_total`, the count the handler already projected; and "
    "`library_item.next_step.kind` gains one enum value, `review_lesson`. A revisit is a clone of "
    "the newest closed authored check at the next version, served when the objective has no "
    "hand-written `check_spec` (a generated lesson stores its real check in the `checks` table, "
    "not in `evidence_criteria_json`). The pass is recorded as an attempt and its layer-1 evidence "
    "row, but it never moves `objectives.state` again, never writes a second layer-2 row and never "
    "pays XP twice: `engagement.award` refuses a revisit with details.reason = revisit_pays_no_xp. "
    "Every new key is optional, every response that omits it keeps its exact v27 shape, and no "
    "method, required key, error code, job kind, answer kind, verdict, evidence class or "
    "vocabulary value moves. `contracts/rpc.v27.json` stays byte-identical history and "
    "`x-supersedes` names it."
)

#: The check responses. `revisit` is optional everywhere: a v27 server never sent it and a v27
#: client never asked for it.
REVISIT = {
    "type": "boolean",
    "default": False,
    "description": (
        "True when this check is a revisit — a clone of the newest closed authored check at the "
        "next version, served because the objective was already checked and the learner is "
        "reviewing rather than starting. A revisit pass records an attempt but never moves the "
        "objective again and never pays XP a second time."
    ),
}

REVISIT_CHALLENGE = {
    "type": "boolean",
    "default": False,
    "description": (
        "True when the challenge is the authored check served again as a review (a generated "
        "objective has one authored item, so a challenge over it is a revisit rather than a "
        "fabricated variant)."
    ),
}

REVISIT_STORED = {
    "type": "boolean",
    "default": False,
    "description": (
        "True when this stored check is a revisit clone. A closed original reads false, and every "
        "check written before v28 reads false."
    ),
}

SECTIONS_TOTAL = {
    "type": "integer",
    "minimum": 1,
    "maximum": 400,
    "description": (
        "The number of sections in the current plan (E2E U3 already projected this number; v28 "
        "freezes it so the record the handler emits validates)."
    ),
}

REVIEW_KIND = "review_lesson"


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _properties(document: dict, method: str) -> dict:
    return document["$defs"]["methods"]["properties"][method]["response"]["properties"]


def derive(source: dict) -> dict:
    """v27 plus the revisit delta and the four wire echoes, and nothing else."""
    if int(source["x-contract-version"]) != 27:
        raise SystemExit(f"expected rpc.v27.json, found v{source['x-contract-version']}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    document["$id"] = f"{base}/v28"
    document["title"] = "Coursebook backend RPC v28"
    document["x-contract-version"] = 28
    document["x-supersedes"] = f"{base}/v27"
    document["description"] = f"{DELTA} {source['description']}"

    for method, field in (
        ("check.open", REVISIT),
        ("check.get", REVISIT),
        ("progression.challenge_out", REVISIT_CHALLENGE),
    ):
        properties = _properties(document, method)
        if "revisit" in properties:
            raise SystemExit(f"{method} already carries revisit")
        properties["revisit"] = field

    page = _properties(document, "lesson.page")
    if "sections_total" in page["section"]["properties"]:
        raise SystemExit("lesson.page.section already carries sections_total")
    page["section"]["properties"]["sections_total"] = SECTIONS_TOTAL
    if "revisit" in page["checks"]["items"]["properties"]:
        raise SystemExit("lesson.page.checks already carries revisit")
    page["checks"]["items"]["properties"]["revisit"] = REVISIT_STORED

    kind = document["$defs"]["library_item"]["properties"]["next_step"]["properties"]["kind"]
    if REVIEW_KIND in kind["enum"]:
        raise SystemExit("next_step.kind already carries review_lesson")
    kind["enum"].insert(kind["enum"].index("start_lesson") + 1, REVIEW_KIND)

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
        if echo.get("const") != 27:
            raise SystemExit(f"unexpected wire echo {echo!r}")
        echo["const"] = 28
    return document


def main() -> int:
    raw = SOURCE.read_text(encoding="utf-8")
    source = json.loads(raw)
    if serialise(source) != raw:
        raise SystemExit(
            "rpc.v27.json does not round-trip under this serialiser; refusing to write a v28 "
            "whose diff would be every line"
        )
    target = serialise(derive(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
