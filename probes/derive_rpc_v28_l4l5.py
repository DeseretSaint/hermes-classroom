"""Derive ``contracts/rpc.v28.json`` — the E2E L4/L5 delta, composed over the E2E L1 delta.

Run from the repository root::

    python3 probes/derive_rpc_v28_l4l5.py

**Merge hazard (t_1b7cab16 / E2E L1).** Two branches independently produce an rpc v28. L1 owns
``probes/derive_rpc_v28.py`` (revisit flags, ``sections_total``, ``review_lesson``); this file owns
the completion/repair delta (``complete``, ``repair_lesson``, ``reasons``, parked section identity).
The two amendments are disjoint, so this script composes rather than overwrites: when
``probes/derive_rpc_v28.py`` is present it is applied to the parsed v27 first, then this delta is
applied on top of the union. Never hand-edit ``contracts/rpc.v28.json`` and never let one branch's
generated file replace the other's — regenerate here on the merged tree and run
``tests.test_contracts``.

The amendment (E2E L4/L5) is written **onto a parsed v27**, never typed as a second copy of a
13,000-line document: every record this delta does not name is carried, so a hand-copy cannot
silently drop one.

The delta is additive and has three parts:

* ``library_item.next_step.kind`` gains the terminal ``complete`` and the repair-only
  ``repair_lesson``; ``next_step`` may carry the ``objective_id``, ``section_id`` and the
  validator ``reasons`` a repair is aimed at. Every v27 next step keeps its exact shape.
* ``outline_objective`` may carry the section identity and the authored lesson's state and
  rejection reasons, so a section index can say a page could not be written without inventing
  a state the backend did not record.
* the ``lesson.page`` section record may carry the same three fields, and ``lesson.regenerate``
  accepts the reasons the caller displayed so the kernel can fence the repair on the parked
  revision the parent actually saw.

The output is byte-identical to the repository's own serialisation (``json.dumps`` with
``indent=2`` and ``ensure_ascii=False`` plus a trailing newline), which the script asserts against
v27 first: if the round trip of the input document is not byte-exact, the formatting contract has
changed and the script refuses to write a v28 that would diff in every line.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v27.json"
TARGET = ROOT / "contracts" / "rpc.v28.json"
# The E2E L1 branch's own derivation, if it is present on this tree.
SIBLING = ROOT / "probes" / "derive_rpc_v28.py"

DELTA = (
    "v28 is one additive amendment over v27 (E2E L4/L5, a finished course and a lesson that "
    "could not be written): `library_item.next_step.kind` gains the terminal `complete` and the "
    "repair-only `repair_lesson`, and `next_step` may carry the `objective_id`, `section_id` and "
    "the validator `reasons` the repair is aimed at; `outline_objective` and the `lesson.page` "
    "section record may carry `section_id`, `lesson_state` and `lesson_rejection_reasons`, so a "
    "section index names a parked authored page instead of calling it a spaced review; "
    "`lesson.regenerate` accepts the optional `reasons` the caller displayed, and the kernel "
    "refuses a repair whose reasons do not match the parked revision it would replace. "
    "`needs_review` is no longer counted as a spaced review due: only an objective whose own "
    "state is `review_due` is. Every v27 record that omits the new keys keeps its exact v27 "
    "shape and bytes. No method, required key, error code, job kind, answer kind, verdict, "
    "evidence class or vocabulary value moves; `contracts/rpc.v27.json` stays byte-identical "
    "history and `x-supersedes` names it."
)

REASONS = {
    "type": "array",
    "description": (
        "The validator's own refusals for the authored page, in the words it recorded. They are "
        "evidence a repair is aimed at, never learner grading criteria and never an answer key."
    ),
    "maxItems": 20,
    "items": {"type": "string", "minLength": 1, "maxLength": 500},
}

NULLABLE_IDENTIFIER = {
    "oneOf": [
        {"$ref": "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/identifier"},
        {"type": "null"},
    ]
}

NULLABLE_SECTION_ID = {
    "type": ["string", "null"],
    "maxLength": 128,
    "description": (
        "The authored section id `lesson.regenerate` is keyed on, or null when this objective has "
        "no authored section (a pack-composed or chat-only course). A client never derives it."
    ),
}

LESSON_STATE = {
    "oneOf": [
        {
            "type": "string",
            "enum": ["validated", "model_assessed", "parent_approved", "needs_review"],
        },
        {"type": "null"},
    ],
    "description": (
        "The newest `gen_lessons` state for the section, or null when no authored page exists. "
        "`needs_review` means the page could not be written; it is not a spaced-review state."
    ),
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _add(properties: dict, key: str, schema: dict) -> None:
    if key in properties:
        raise SystemExit(f"{key} already present")
    properties[key] = schema


def derive(source: dict) -> dict:
    """The E2E L4/L5 delta applied to v27 or to the v27+L1 union, and nothing else."""
    version = int(source["x-contract-version"])
    if version not in (27, 28):
        raise SystemExit(f"expected rpc.v27.json (or an L1-composed v28), found v{version}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    if version == 27:
        document["$id"] = f"{base}/v28"
        document["title"] = "Coursebook backend RPC v28"
        document["x-contract-version"] = 28
        document["x-supersedes"] = f"{base}/v27"
        document["description"] = f"{DELTA} {source['description']}"
    elif not document.get("description", "").startswith(DELTA):
        document["description"] = f"{DELTA} {source['description']}"

    library_item = document["$defs"]["library_item"]
    next_step = library_item["properties"]["next_step"]
    kinds = next_step["properties"]["kind"]["enum"]
    if "complete" in kinds or "repair_lesson" in kinds:
        raise SystemExit("next_step.kind already carries the v28 kinds")
    kinds.extend(["complete", "repair_lesson"])
    _add(next_step["properties"], "objective_id", NULLABLE_IDENTIFIER)
    _add(next_step["properties"], "section_id", NULLABLE_SECTION_ID)
    _add(next_step["properties"], "reasons", REASONS)

    outline = document["$defs"]["outline_objective"]
    _add(outline["properties"], "section_id", NULLABLE_SECTION_ID)
    _add(outline["properties"], "lesson_state", LESSON_STATE)
    _add(outline["properties"], "lesson_rejection_reasons", REASONS)

    page_section = document["$defs"]["methods"]["properties"]["lesson.page"]["response"][
        "properties"
    ]["section"]
    _add(page_section["properties"], "section_id", NULLABLE_SECTION_ID)
    _add(page_section["properties"], "lesson_state", LESSON_STATE)
    _add(page_section["properties"], "rejection_reasons", REASONS)

    regenerate = document["$defs"]["methods"]["properties"]["lesson.regenerate"]["request"]
    _add(regenerate["properties"], "reasons", REASONS)

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
        if echo.get("const") not in (27, 28):
            raise SystemExit(f"unexpected wire echo {echo!r}")
        echo["const"] = 28
    return document


def _sibling_derive() -> object | None:
    """The E2E L1 branch's ``derive``, when that branch's script is on this tree."""
    if not SIBLING.exists():
        return None
    spec = importlib.util.spec_from_file_location("derive_rpc_v28_l1", SIBLING)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "derive", None)


def build(source: dict) -> dict:
    """v27 → (E2E L1 delta, if present) → E2E L4/L5 delta. Order matters only for the description."""
    sibling = _sibling_derive()
    document = sibling(source) if callable(sibling) else source
    if not isinstance(document, dict):
        raise SystemExit("the sibling derivation did not return a contract document")
    return derive(document)


def main() -> int:
    raw = SOURCE.read_text(encoding="utf-8")
    source = json.loads(raw)
    if serialise(source) != raw:
        raise SystemExit(
            "rpc.v27.json does not round-trip under this serialiser; refusing to write a v28 "
            "whose diff would be every line"
        )
    target = serialise(build(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
