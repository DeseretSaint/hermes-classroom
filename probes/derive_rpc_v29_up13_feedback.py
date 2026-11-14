"""Derive ``contracts/rpc.v29.json`` — the upgrade-13 miss-feedback delta over v28.

Run from the repository root::

    python3 probes/derive_rpc_v29_up13_feedback.py

A non-pass used to be a bare grader sentence with no way to say which authored rule the learner
missed. The amendment is additive and has three parts:

* the ``attempt.submit`` response may carry one optional ``feedback`` object — ``rule``,
  ``observed``, ``answer`` and ``next_action`` — naming the rule a non-pass missed, the learner's
  own answer and the one action the miss permits. It is authored on the check's stored reference,
  never generated at grading time, and never carries the reference answer.
* each ``criteria`` row may carry the same three facts (``rule``, ``next_action``, ``answer``), so
  a replayed or re-read attempt rebuilds the block from the row it was stored on.
* the four places the wire version is echoed move to 29.

A response from a check that authored no rule omits ``feedback`` and keeps its exact v28 shape and
bytes, which is why nothing here is required. One rule per check: a per-group rule is refused at
seal time, because a wrong answer says nothing about which accepted form the learner aimed at.

One contract version must carry every additive change shipped together, so this script *composes*:
if ``contracts/rpc.v29.json`` is already on the tree and declares version 29, it is the source and
only this card's delta is applied on top. ``probes/derive_rpc_v29.py`` loads this file as a sibling
delta (``derive(document, composed=True)``), so the shipped document is the union of the wave.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v28.json"
TARGET = ROOT / "contracts" / "rpc.v29.json"

DELTA = (
    "v29 is one additive amendment over v28 (upgrade 13, a miss names the rule): the "
    "`attempt.submit` response gains one optional `feedback` object — `rule`, `observed`, "
    "`next_action` and the learner's own `answer` — and each `criteria` row gains the same "
    "optional `rule`, `next_action` and `answer` facts, so a non-pass names the authored rule it "
    "missed instead of only a deterministic grader sentence, and the teaching turn is told the "
    "same rule. The rule is authored on the check's stored reference (`reference_json.feedback`, "
    "one rule per check: a per-group rule is refused at seal time because a wrong answer says "
    "nothing about which accepted form the learner aimed at) and never generated at "
    "grading time; it may not restate an accepted answer, and a miss may name only "
    "`retry_attempt`, `explain` or `select_alternative`, never a pass action. A response from a "
    "check that authored no rule omits `feedback` and keeps its exact v28 shape and bytes, and a "
    "`needs_retry` names no rule at all because the grader does not know which one was missed. No "
    "method, required key, error code, job kind, answer kind, verdict, evidence class or "
    "vocabulary value moves; `contracts/rpc.v28.json` stays byte-identical history and "
    "`x-supersedes` names it."
)

MISS_NEXT_ACTION = {
    "type": "string",
    "enum": ["retry_attempt", "explain", "select_alternative"],
    "description": (
        "The one action a miss permits. A wrong answer never grants access, so the pass actions "
        "are not in this enum."
    ),
}

RULE = {
    "type": "string",
    "maxLength": 240,
    "description": (
        "The rule the check tests, authored with the check. One sentence a learner can act on. It "
        "may not restate an accepted answer: a learner who reads the answer can copy it and the "
        "retry becomes a copying task."
    ),
}

LEARNER_ANSWER = {
    "type": "string",
    "maxLength": 300,
    "description": "The learner's own answer, quoted back as evidence of what was read.",
}

OBSERVED = {
    "type": "string",
    "maxLength": 300,
    "description": "The deterministic grader's own sentence, kept as detail under the rule.",
}

FEEDBACK = {
    "type": "object",
    "additionalProperties": False,
    "required": ["rule", "next_action"],
    "properties": {
        "rule": RULE,
        "observed": OBSERVED,
        "answer": LEARNER_ANSWER,
        "next_action": MISS_NEXT_ACTION,
    },
    "description": (
        "The authored rule a non-pass missed. Authored on the check's stored reference, never "
        "generated at grading time, and never carrying the reference answer. A response from a "
        "check that authored no rule omits this key."
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

    # Set, not add: a composed v29 may already carry a sibling's delta, and re-running this
    # derivation must leave these exact bytes rather than a second definition.
    response = document["$defs"]["methods"]["properties"]["attempt.submit"]["response"]
    response["properties"]["feedback"] = FEEDBACK
    criteria_properties = response["properties"]["criteria"]["items"]["properties"]
    criteria_properties["rule"] = RULE
    criteria_properties["next_action"] = MISS_NEXT_ACTION
    criteria_properties["answer"] = LEARNER_ANSWER

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
