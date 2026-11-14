"""Derive ``contracts/rpc.v29.json`` — the UP-19 recognition-label delta, composed over UP-14.

Run from the repository root::

    python3 probes/derive_rpc_v29_pronunciation.py

**Merge hazard (t_92039128 / UP-14).** UP-14 owns ``probes/derive_rpc_v29.py``: v29 = v28 plus the
authored hint ladder. This file owns the pronunciation-assessment delta. One contract version must
carry every additive change shipped together — two ``rpc.v29.json`` files cannot both exist — so
this script does not fork the version: it applies the sibling derivation to the parsed v28 first
and then writes its own delta onto the union. Run the sibling, then this script, on the merged tree
and ``tests.test_contracts`` proves the shipped file is byte-identical to the derivation.

The amendment is written **onto a parsed document**, never typed as a second copy of a
13,000-line file: every record this delta does not name is carried, so a hand-copy cannot silently
drop one.

The delta is additive and has four parts on ``$defs/pronunciation_assessment``:

* ``measure`` — ``word_recognition`` when a take was compared, ``none`` when it was not. It is the
  machine-readable half of the label: this result compares the words the recogniser heard with the
  target phrase and never claims to have measured pronunciation.
* ``caveat`` — the learner-facing sentence that names what was measured and what was not. It is the
  backend's own words so no surface composes a promise the pipeline did not make; null on a take
  that was not assessed.
* ``gated`` and ``min_word_confidence`` — the gate on the strongest verdict. ``meets_target`` is
  refused when the weakest matched word carried less than the floor (or no confidence at all), the
  verdict falls to ``close``, and ``gated`` says why the number cannot be read as a result.
* the four places the wire version is echoed already read 29 from the sibling derivation and are
  asserted, not moved again.

Every ``pronunciation_word`` row already carries ``confidence``; it now carries the recogniser's
probability for a *missed* word too, which the schema always allowed. No method, required key
outside this one record, error code, job kind, answer kind, verdict, evidence class or vocabulary
value moves; ``contracts/rpc.v28.json`` stays byte-identical history and ``x-supersedes`` names it.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from typing import Any, Callable, cast

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v28.json"
TARGET = ROOT / "contracts" / "rpc.v29.json"
#: UP-14's own derivation. Required: this delta composes onto it rather than replacing it.
SIBLING = ROOT / "probes" / "derive_rpc_v29.py"

DELTA = (
    "v29 also carries one additive amendment over v28 (UP-19, pronunciation is word recognition): "
    "the `pronunciation_assessment` record gains four required properties — `measure` "
    "(`word_recognition` when a take was compared, `none` when it was not), the learner-facing "
    "`caveat` that names what was and was not measured, `gated`, and `min_word_confidence`, the "
    "weakest per-word recogniser probability among the matched words. The strongest verdict, "
    "`meets_target`, is refused when that weakest confidence is under the floor or absent: the "
    "verdict falls to `close` and `gated` is true, because a match the recogniser was unsure of "
    "cannot be reported as meeting the target. `phoneme_accuracy` stays null — no phoneme is "
    "assessed in this build — and each `pronunciation_word` row now carries the recogniser's "
    "probability for a missed word as well, which the record always allowed. Nothing here claims "
    "pronunciation: the record states that it compares the words the recogniser heard with the "
    "target phrase. No method, error code, job kind, answer kind, verdict value, evidence class or "
    "vocabulary value moves, and every v28 producer that omits the new keys keeps its exact v28 "
    "shape. `contracts/rpc.v28.json` stays byte-identical history and `x-supersedes` names it."
)

MEASURE = {
    "type": "string",
    "enum": ["word_recognition", "none"],
    "description": (
        "What was actually compared. `word_recognition` means the recogniser's words were "
        "diffed against the target phrase; `none` means the take was not assessed. There is no "
        "`pronunciation` value: this build never measures a phoneme."
    ),
}

CAVEAT = {
    "oneOf": [
        {"type": "string", "minLength": 1, "maxLength": 400},
        {"type": "null"},
    ],
    "description": (
        "The backend's own sentence saying what this result measures and what it does not. A "
        "surface prints it verbatim and never composes its own. Null when no take was compared."
    ),
}

MIN_WORD_CONFIDENCE = {
    "oneOf": [
        {"type": "number", "minimum": 0, "maximum": 1},
        {"type": "null"},
    ],
    "description": (
        "The lowest recogniser probability among the matched words, or null when no matched word "
        "carried one. It is the gate the strongest verdict was tested against, not a score the "
        "learner earned."
    ),
}

GATED = {
    "type": "boolean",
    "description": (
        "True when the words matched strongly enough for `meets_target` on paper but the "
        "recogniser's own confidence was under the floor (or absent), so the verdict was held at "
        "`close`. A gated result is not a near miss by the learner; it is an unconfident "
        "recognition."
    ),
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _sibling_derive() -> Callable[[dict], dict]:
    if not SIBLING.exists():
        raise SystemExit(
            f"{SIBLING.relative_to(ROOT)} is missing: v29 already carries UP-14's hint ladder, and "
            "writing this delta over a bare v28 would drop it"
        )
    spec = importlib.util.spec_from_file_location("derive_rpc_v29_ladder", SIBLING)
    if spec is None or spec.loader is None:
        raise SystemExit("the sibling derivation could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    derive = getattr(module, "derive", None)
    if not callable(derive):
        raise SystemExit("the sibling derivation exposes no derive()")
    typed = cast(Callable[[dict], dict], derive)
    return typed


def derive(source: dict, *, composed: bool = False) -> dict:
    """v28 → the base v29 deltas → this recognition label. Returns the v29 document.

    ``composed=True`` (or a source that already declares 29) applies only this delta to the
    document in hand, which is how ``probes/derive_rpc_v29.py`` folds the sibling cards in; the
    application is idempotent, so re-running the derivation rewrites identical bytes.
    """
    version = int(source["x-contract-version"])
    if version == 28:
        document: dict[str, Any] = _sibling_derive()(source)
    elif version == 29:
        document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    else:
        raise SystemExit(f"expected rpc v28 (or a v29 to compose with), found v{version}")
    if int(document["x-contract-version"]) != 29:
        raise SystemExit("the sibling derivation did not produce a v29 document")

    assessment: dict[str, Any] = document["$defs"]["pronunciation_assessment"]
    properties: dict[str, Any] = assessment["properties"]
    # Set, not add: a composed v29 may already carry this delta.
    properties["measure"] = MEASURE
    properties["min_word_confidence"] = MIN_WORD_CONFIDENCE
    properties["gated"] = GATED
    properties["caveat"] = CAVEAT

    required = [key for key in assessment["required"]
                if key not in ("measure", "min_word_confidence", "gated", "caveat")]
    at = required.index("unit") + 1
    required.insert(at, "measure")
    at = required.index("phoneme_accuracy") + 1
    required[at:at] = ["min_word_confidence", "gated", "caveat"]
    assessment["required"] = required

    if not str(document.get("description", "")).startswith(DELTA):
        document["description"] = f"{DELTA} {document['description']}"

    # The four places the wire version is echoed. The sibling already moved them to 29; this script
    # asserts rather than re-moves, so a composed tree cannot carry a half-bumped envelope.
    echoes = [
        document["$defs"]["envelope_request"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_ok"]["properties"]["contract_version"],
        document["$defs"]["envelope_response_error"]["properties"]["contract_version"],
        document["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"][
            "contract_version"
        ],
    ]
    for echo in echoes:
        if echo.get("const") != 29:
            raise SystemExit(f"unexpected wire echo {echo!r}")
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
