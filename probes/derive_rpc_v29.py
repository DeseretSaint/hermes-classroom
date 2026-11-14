"""Derive ``contracts/rpc.v29.json`` — the composed additive delta over v28.

Run from the repository root::

    python3 probes/derive_rpc_v29.py

One contract version must carry every additive change that ships together, so this script is the
**composition point** for the v29 wave: it applies each card's delta to a parsed v28 in one pass.
A sibling card that derived its own v29 from the same v28 did not fork the version; its delta is
folded in here and re-run, so the written document is byte-identical to the union of the cards.

Deltas carried by this script:

* UP-14 (t_92039128), the authored hint ladder: ``check_stimulus.assistance_policy`` may carry the
  authored policy (the ``hint`` gate, the evidence class an answer inherits, and the ladder's rung
  kinds and labels), ``check.get`` may carry ``assistance`` (the authored rungs, how many were
  recorded, which rung is next), and ``lesson.assist`` accepts an optional ``rung`` index and
  answers with the one revealed rung. Rung *text* is deliberately not projected on the read: a rung
  is revealed by a recorded press, not by opening the check. A non-final rung records the existing
  ``hint_request`` kind and ``hinted`` class; the final rung records ``answer_shown``, so the ladder
  never invents a new evidence class.
* UP-6 (t_76953421), the plan gate's own time estimate: ``outline_plan.time_estimate`` may carry the
  plan's stored schedule estimate (``weeks``, ``sessions_per_week``, ``minutes_per_session``,
  ``basis``, ``confidence``), or null when no usable estimate is stored. The weeks figure is a
  planning estimate and never an attainment claim.

The amendment is written **onto a parsed v28**, never typed as a second copy of a 13,000-line
document: every record this delta does not name survives by being carried, so a hand-copy cannot
silently drop one.

The output is byte-identical to the repository's own serialisation (``json.dumps`` with
``indent=2`` and ``ensure_ascii=False`` plus a trailing newline), which the script asserts against
v28 first: if the round trip of the input document is not byte-exact, the formatting contract has
changed and the script refuses to write a v29 that would diff in every line.

No method, required key, error code, job kind, answer kind, verdict, evidence class or vocabulary
value moves; ``contracts/rpc.v28.json`` stays byte-identical history and ``x-supersedes`` names it.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v28.json"
TARGET = ROOT / "contracts" / "rpc.v29.json"

DELTA = (
    "v29 is one additive amendment over v28, composed of the cards that ship together. "
    "UP-14, the authored hint ladder: `check_stimulus` may carry `assistance_policy` — the "
    "authored `hint` gate, the `answer_marks_evidence_class` an answer inherits, and a ladder of "
    "at most three rungs whose kinds are `nudge`, `cue` and `worked_step`, each with a short "
    "learner-facing label but no rung text; `check.get` may carry `assistance` — the gate, the "
    "number of authored rungs, how many were already recorded against this attempt, and which "
    "rung is next; and `lesson.assist` accepts an optional `rung` index and answers with the one "
    "revealed rung (index, kind, label, text, and whether it was the last). A non-final rung "
    "records the existing `hint_request` kind and `hinted` class; the final rung records "
    "`answer_shown`, so the ladder never invents a new evidence class and the full independence "
    "penalty still lands on the strongest rung. Rung text is never projected by `check.get`: a "
    "rung is revealed by a recorded press. "
    "UP-6: `outline_plan` may carry `time_estimate` — the plan's own stored schedule estimate "
    "(weeks and the author's declared sessions per week, minutes per session, basis and "
    "confidence), or null when no usable estimate is stored. `weeks` is a planning estimate, not "
    "an attainment claim. "
    "Every v28 record that omits the new keys keeps its exact v28 shape and bytes. No method, "
    "required key, error code, job kind, answer kind, verdict, evidence class or vocabulary value "
    "moves; `contracts/rpc.v28.json` stays byte-identical history and `x-supersedes` names it."
)

POLICY = {
    "type": "string",
    "enum": ["available", "after_attempt", "none"],
    "description": (
        "When an authored hint exists at all. `none` means the check offers no assistance control; "
        "`after_attempt` means the first rung opens only after a committed attempt on this check."
    ),
}

RUNG_KINDS = ["nudge", "cue", "worked_step"]

HINT_RUNG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "label"],
    "properties": {
        "kind": {"type": "string", "enum": RUNG_KINDS},
        "label": {"type": "string", "minLength": 1, "maxLength": 40},
    },
}

ASSISTANCE_POLICY = {
    "oneOf": [
        {"type": "null"},
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["hint", "answer_marks_evidence_class"],
            "properties": {
                "hint": POLICY,
                "answer_marks_evidence_class": {
                    "type": "string",
                    "enum": ["answer_shown", "hinted", "none"],
                },
                "ladder": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {"$ref": "#/$defs/hint_rung"},
                    "description": (
                        "The authored rungs in reveal order. A rung's text is withheld from this "
                        "read; `lesson.assist` returns the one rung a recorded press reveals."
                    ),
                },
            },
        },
    ],
    "description": (
        "The assistance policy the check authored, projected for the pane. Missing on a v28 check "
        "and null when no policy was authored; an undeclared policy means no hint."
    ),
}

CHECK_ASSISTANCE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["policy", "available", "rungs", "used", "next_rung", "total"],
    "properties": {
        "policy": POLICY,
        "available": {"type": "boolean"},
        "rungs": {"type": "array", "maxItems": 3, "items": {"$ref": "#/$defs/hint_rung"}},
        "used": {"type": "integer", "minimum": 0, "maximum": 3},
        "next_rung": {
            "oneOf": [{"type": "integer", "minimum": 0, "maximum": 2}, {"type": "null"}]
        },
        "total": {"type": "integer", "minimum": 0, "maximum": 3},
    },
    "description": (
        "The check's authored assistance, as of this read: the gate, the authored rungs, how many "
        "rungs this attempt has already recorded, and which rung the next recorded press reveals. "
        "`next_rung` is null when the gate is closed, no ladder is authored, or every rung is used."
    ),
}

ASSIST_RUNG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["index", "kind", "label", "text", "last"],
    "properties": {
        "index": {"type": "integer", "minimum": 0, "maximum": 2},
        "kind": {"type": "string", "enum": RUNG_KINDS},
        "label": {"type": "string", "minLength": 1, "maxLength": 40},
        "text": {"type": "string", "minLength": 1, "maxLength": 400},
        "last": {"type": "boolean"},
    },
    "description": (
        "The one rung a recorded `lesson.assist` press revealed, in the author's words. The last "
        "rung is the strongest assistance and records `answer_shown`, the existing full penalty."
    ),
}

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


def _add(properties: dict, key: str, schema: dict) -> None:
    if key in properties:
        raise SystemExit(f"{key} already present")
    properties[key] = schema


def derive(source: dict) -> dict:
    """v28 plus the composed v29 deltas and the four wire echoes, and nothing else."""
    if int(source["x-contract-version"]) != 28:
        raise SystemExit(f"expected rpc.v28.json, found v{source['x-contract-version']}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    document["$id"] = f"{base}/v29"
    document["title"] = "Coursebook backend RPC v29"
    document["x-contract-version"] = 29
    document["x-supersedes"] = f"{base}/v28"
    document["description"] = f"{DELTA} {source['description']}"

    # UP-14 (t_92039128): the authored hint ladder.
    defs = document["$defs"]
    for name, schema in (
        ("hint_rung", HINT_RUNG),
        ("check_assistance", CHECK_ASSISTANCE),
        ("assist_rung", ASSIST_RUNG),
    ):
        if name in defs:
            raise SystemExit(f"$defs.{name} already present")
        defs[name] = schema

    _add(defs["check_stimulus"]["properties"], "assistance_policy", ASSISTANCE_POLICY)

    methods = document["$defs"]["methods"]["properties"]
    _add(methods["check.get"]["response"]["properties"], "assistance", CHECK_ASSISTANCE)
    _add(methods["lesson.assist"]["request"]["properties"], "rung",
         {
             "type": "integer",
             "minimum": 0,
             "maximum": 2,
             "description": (
                 "The rung this press reveals, as `check.get.assistance.next_rung` reported it. "
                 "The backend refuses a rung out of order, beyond the authored ladder, or when the "
                 "authored policy is `none`. Omit it for the legacy binary hint."
             ),
         })
    _add(methods["lesson.assist"]["response"]["properties"], "rung",
         {"oneOf": [{"$ref": "#/$defs/assist_rung"}, {"type": "null"}]})

    # UP-6 (t_76953421): the plan gate's own time estimate.
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
        methods["health.get"]["response"]["properties"]["contract_version"],
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
