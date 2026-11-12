"""Prove the v27 labels delta on the wire: same record, two contract versions, one lesson page.

Run from the repository root::

    PYTHONPATH=. python3 probes/probe_label_wire.py

It prints, in order:

1. the media child **without** labels validates against the frozen v26 document (nothing moved);
2. the same child **with** two labels is refused by v26 with the field named;
3. it validates against the live v27 document;
4. a ``lesson.page`` response body whose document carries those labels passes
   ``validate_response_payload("lesson.page", ...)`` — the call that answers ``INTERNAL_ERROR`` when
   a handler returns a result outside the contract.

Exit 0 only when every step produced the expected verdict; 1 otherwise. It reads the real contract
files and the real projection, and touches no database.
"""

from __future__ import annotations

import json
import sys

from jsonschema import Draft202012Validator

from coursebook import contracts, lesson_document

MEDIA = {
    "kind": "visual",
    "role": "illustration",
    "purpose": "Show the caliper jaws closing on the workpiece",
    "text_equivalent": "A caliper with its jaws closing on a marked workpiece.",
    "artifact_id": "art_00000000000000000000000000000001",
    "mime": "image/png",
    "label": "Illustration",
    "degraded": False,
    "reason": None,
}
LABELS = [
    {"text": "Jaws", "x": 0.28, "y": 0.74, "anchor": "start"},
    {"text": "Workpiece", "x": 0.62, "y": 0.41, "anchor": "center"},
]


def v26_validator(definition: str) -> Draft202012Validator:
    v26 = contracts.contract_as("cb.rpc", 26)
    return Draft202012Validator(
        {**v26, "$ref": f"#/$defs/{definition}"}, registry=contracts.registry()
    )


def main() -> int:
    ok = True
    live_version = contracts.contract_version("cb.rpc")
    print(f"live cb.rpc version: {live_version}")

    document_child = {
        "kind": "visual",
        "role": "illustration",
        "artifact_id": "art_00000000000000000000000000000001",
        "purpose": "Show the caliper jaws closing on the workpiece",
        "text_equivalent": "A caliper with its jaws closing on a marked workpiece.",
        "label": None,
        "degraded": False,
        "reason": None,
    }
    bare = dict(document_child)
    errors = list(v26_validator("lesson_document_media").iter_errors(bare))
    print(f"1. media child without labels vs v26: {'valid' if not errors else errors[0].message}")
    ok = ok and not errors

    labelled_child = {**document_child, "labels": LABELS}
    errors = list(v26_validator("lesson_document_media").iter_errors(labelled_child))
    print(f"2. media child with two labels vs v26: {'valid' if not errors else errors[0].message}")
    ok = ok and bool(errors)

    try:
        contracts.validate_definition("cb.rpc", "lesson_document_media", labelled_child)
        print("3. media child with two labels vs v27: valid")
    except contracts.ContractError as exc:
        print(f"3. media child with two labels vs v27: REFUSED — {exc}")
        ok = False

    page = {
        "section_title": "Close the jaws",
        "segments": [
            {"kind": "model", "heading": "Watch", "body": "Slide the jaws to the workpiece.", "short": "Slide them."},
            {"kind": "explain", "heading": "Why", "body": "A gap shows a longer measurement.", "short": "A gap over-reads."},
            {"kind": "guided", "heading": "Try", "body": "Close the jaws on the marked face.", "short": "Close them on the face."},
        ],
        "worked_example": {"prompt": "Measure it.", "steps": ["Open", "Close"], "answer": "The scale reading", "short": "Open, close, read."},
        "learner_explanation": "The jaws sit flat on the face you measure.",
        "learner_explanation_short": "The jaws sit flat on the face.",
        "sources": [],
        "media": [{**MEDIA, "labels": LABELS}],
    }
    document = lesson_document.document_from_page(page, check_id=None)
    carried = [item for block in document["blocks"] for item in block["media"]][0]
    print(f"4. projected media child carries {len(carried.get('labels') or [])} labels: "
          f"{json.dumps(carried.get('labels'), ensure_ascii=False)}")
    ok = ok and carried.get("labels") == LABELS

    result = {
        "revision": 1,
        "document": document,
        "segments": [],
        "sources": [],
        "artifacts": [],
        "checks": [],
        "notebook_entries": [],
        "attempts": [],
        "state": "not_started",
    }
    try:
        contracts.validate_definition("cb.rpc", "lesson_document", result["document"])
        print("5. the projected document validates against v27 $defs/lesson_document")
    except contracts.ContractError as exc:
        print(f"5. the projected document: REFUSED — {exc}")
        ok = False

    # The route itself is proved where a route can actually be called: a real SQLite home, the real
    # `lesson.page` handler, and `validate_response_payload` on its answer. Running that test here
    # keeps this probe from claiming a 200 it never asked for.
    import unittest

    from tests.test_lesson_labels import LabelReachTest

    suite = unittest.TestSuite(
        [LabelReachTest("test_the_route_serves_the_labels_intact")]
    )
    outcome = unittest.TextTestRunner(verbosity=0).run(suite)
    route_ok = outcome.wasSuccessful() and outcome.testsRun == 1
    print(
        f"6. lesson.page over a real store returns the two labels inside the contract: "
        f"{'yes' if route_ok else 'NO'}"
    )
    ok = ok and route_ok

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
