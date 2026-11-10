"""Build ``contracts/rpc.v24.json``: GM-005's v23 plus exactly the four frozen homework methods.

The v23 document is read-only history and is copied byte-for-byte except for the additive
amendment: the four names already frozen in ``coursebook/gm_contract.py::GM_RPC_METHODS`` are
appended, their payload schemas are added, one shared ``homework_task`` definition is added, and
the document identity moves to v24. No method, required key, $defs entry or vocabulary value is
removed or retyped.

Run from the repository root:

    python3 scripts/gm007_rpc_v24.py
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
SOURCE = CONTRACTS / "rpc.v23.json"
TARGET = CONTRACTS / "rpc.v24.json"

IDENT = "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/identifier"
SHA = "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/sha256_hash"
REVISION = "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/revision"

NEW_METHODS = ("homework.create", "homework.read", "homework.complete", "homework.skip")

DESCRIPTION = (
    "v24 is v23 with one additive amendment (GM-007, away-from-screen homework): four methods are "
    "appended, `homework.create`, `homework.read`, `homework.complete` and `homework.skip`. "
    "`homework.create` proposes one task with one target, one context, one observable success "
    "criterion and 3-10 minutes, sourced from the lesson's authored away-from-screen block; it "
    "refuses a generic duration card, multiple targets, surveillance and graded completion with "
    "`POLICY_VIOLATION` and a named `details.reason`. `homework.read` returns the task, its "
    "append-only event trail and a one-page sheet with its cited sources. `homework.complete` "
    "records `self_reported_done` or `parent_reported_done` and `homework.skip` records an honest "
    "skip; neither writes an attempt, transition, evidence, engagement or mastery row, and a "
    "parent-reported task is never independent verification. Homework is not a course, not a "
    "chat thread and never an external send. No v1-v23 method, request shape, required key, "
    "error code, job kind, answer kind, verdict, evidence class or vocabulary value moves; "
    "`rpc.v23.json` stays byte-identical history and `x-supersedes` names it. v23 is v22 with "
    "GM-005's take-home family. "
)


def _object(required, properties, *, max_items=None):
    node = OrderedDict()
    if max_items is not None:
        node["type"] = "array"
        node["maxItems"] = max_items
        node["items"] = properties
        return node
    node["type"] = "object"
    node["additionalProperties"] = False
    node["required"] = list(required)
    node["properties"] = properties
    return node


def _properties(pairs):
    return OrderedDict(pairs)


def homework_task_schema():
    target = _object(
        ("display", "reading", "romaji", "meaning", "register", "kind"),
        _properties(
            [
                ("display", {"type": "string", "minLength": 1, "maxLength": 200}),
                ("reading", {"type": "string", "minLength": 1, "maxLength": 200}),
                ("romaji", {"type": "string", "maxLength": 200}),
                ("meaning", {"type": "string", "maxLength": 400}),
                ("register", {"type": "string", "maxLength": 200}),
                ("kind", {"enum": ["single", "label_set"]}),
                ("label_ids", {"type": "array", "maxItems": 12,
                               "items": {"$ref": IDENT}}),
                ("source_ids", {"type": "array", "maxItems": 12,
                                "items": {"$ref": IDENT}}),
                ("completion_record", {"type": "array", "maxItems": 4,
                                       "items": {"type": "string", "minLength": 1,
                                                 "maxLength": 40}}),
            ]
        ),
    )
    completion = _object(
        ("basis", "completed_at", "note", "independent_verification"),
        _properties(
            [
                ("basis", {"enum": [None, "self_reported", "parent_reported"]}),
                ("completed_at", {"type": ["string", "null"], "maxLength": 40}),
                ("note", {"type": ["string", "null"], "maxLength": 500}),
                ("independent_verification", {"const": False}),
            ]
        ),
    )
    sheet = _object(
        ("paper", "pages", "html", "text"),
        _properties(
            [
                ("paper", {"const": "A4"}),
                ("pages", {"const": 1}),
                ("html", {"type": "string", "maxLength": 200000}),
                ("text", {"type": "string", "maxLength": 200000}),
            ]
        ),
    )
    source = _object(
        ("source_id", "title", "url", "accessed"),
        _properties(
            [
                ("source_id", {"$ref": IDENT}),
                ("title", {"type": "string", "minLength": 1, "maxLength": 300}),
                ("url", {"type": "string", "minLength": 8, "maxLength": 1000}),
                ("accessed", {"type": "string", "maxLength": 40}),
            ]
        ),
    )
    return _object(
        (
            "task_id", "course_id", "enrollment_id", "objective_id", "source_lesson_version",
            "content_hash", "audience", "task_kind", "state", "revision", "title", "target",
            "context", "steps", "success_criterion", "estimated_minutes", "completion", "sources",
            "sheet", "created_at",
        ),
        _properties(
            [
                ("task_id", {"$ref": IDENT}),
                ("course_id", {"$ref": IDENT}),
                ("enrollment_id", {"$ref": IDENT}),
                ("objective_id", {"$ref": IDENT}),
                ("source_lesson_version", {"type": "string", "maxLength": 160}),
                ("content_hash", {"$ref": SHA}),
                ("audience", {"enum": ["learner", "parent"]}),
                ("task_kind", {"enum": ["real_world_use", "observe", "label", "practice", "make",
                                        "teach_back"]}),
                ("state", {"enum": ["proposed", "assigned", "self_reported_done",
                                    "parent_reported_done", "skipped", "expired"]}),
                ("revision", {"$ref": REVISION}),
                ("title", {"type": "string", "minLength": 1, "maxLength": 200}),
                ("target", target),
                ("context", {"type": "string", "minLength": 1, "maxLength": 400}),
                ("steps", _object(None, {"type": "string", "minLength": 1, "maxLength": 200},
                                  max_items=3)),
                ("success_criterion", {"type": "string", "minLength": 1, "maxLength": 400}),
                ("estimated_minutes", {"type": "integer", "minimum": 3, "maximum": 10}),
                ("completion", completion),
                ("sources", _object(None, source, max_items=50)),
                ("sheet", sheet),
                ("created_at", {"type": "string", "maxLength": 40}),
            ]
        ),
    )


def homework_event_schema():
    return _object(
        ("event_id", "ordinal", "kind", "actor", "note", "created_at"),
        _properties(
            [
                ("event_id", {"$ref": IDENT}),
                ("ordinal", {"type": "integer", "minimum": 0, "maximum": 63}),
                ("kind", {"enum": ["proposed", "assigned", "edited", "self_reported",
                                   "parent_reported", "skipped", "expired"]}),
                ("actor", {"enum": ["learner", "parent"]}),
                ("note", {"type": ["string", "null"], "maxLength": 500}),
                ("created_at", {"type": "string", "maxLength": 40}),
            ]
        ),
    )


def methods():
    task_ref = {"$ref": "#/$defs/homework_task"}
    event_array = OrderedDict([("type", "array"), ("maxItems", 64),
                               ("items", homework_event_schema())])
    create = _object(
        ("course_id", "enrollment_id", "objective_id", "audience", "source_lesson_version",
         "context"),
        _properties(
            [
                ("course_id", {"$ref": IDENT}),
                ("enrollment_id", {"$ref": IDENT}),
                ("objective_id", {"$ref": IDENT}),
                ("audience", {"enum": ["learner", "parent"]}),
                ("source_lesson_version", {"type": "string", "maxLength": 160}),
                ("context", {"type": "string", "minLength": 1, "maxLength": 400}),
            ]
        ),
    )
    create_response = _object(
        ("task_id", "task", "state", "revision"),
        _properties(
            [
                ("task_id", {"$ref": IDENT}),
                ("task", task_ref),
                ("state", {"enum": ["proposed", "assigned"]}),
                ("revision", {"$ref": REVISION}),
            ]
        ),
    )
    read = _object(("task_id",), _properties([("task_id", {"$ref": IDENT})]))
    read_response = _object(
        ("task", "events"),
        _properties([("task", task_ref), ("events", event_array)]),
    )
    complete = _object(
        ("task_id", "actor", "note"),
        _properties(
            [
                ("task_id", {"$ref": IDENT}),
                ("actor", {"enum": ["learner", "parent"]}),
                ("note", {"type": "string", "maxLength": 500}),
            ]
        ),
    )
    complete_response = _object(
        ("task", "state", "completed_at"),
        _properties(
            [
                ("task", task_ref),
                ("state", {"enum": ["self_reported_done", "parent_reported_done"]}),
                ("completed_at", {"type": "string", "maxLength": 40}),
            ]
        ),
    )
    skip = _object(
        ("task_id", "actor"),
        _properties(
            [
                ("task_id", {"$ref": IDENT}),
                ("actor", {"enum": ["learner", "parent"]}),
            ]
        ),
    )
    skip_response = _object(
        ("task", "state"),
        _properties([("task", task_ref), ("state", {"const": "skipped"})]),
    )
    return OrderedDict(
        [
            ("homework.create", _method_entry(create, create_response)),
            ("homework.read", _method_entry(read, read_response)),
            ("homework.complete", _method_entry(complete, complete_response)),
            ("homework.skip", _method_entry(skip, skip_response)),
        ]
    )


def _method_entry(request, response):
    node = OrderedDict()
    node["type"] = "object"
    node["request"] = request
    node["response"] = response
    return node


def build() -> dict:
    v23 = json.loads(SOURCE.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    document = OrderedDict()
    document["$schema"] = v23["$schema"]
    document["$id"] = "https://contracts.coursebook.hermes/rpc/v24"
    document["title"] = "Coursebook backend RPC v24"
    document["description"] = DESCRIPTION + v23["description"]
    document["x-contract-id"] = "cb.rpc"
    document["x-contract-version"] = 24
    document["x-owner"] = v23["x-owner"]
    document["x-supersedes"] = v23["$id"]
    document["x-status"] = "frozen"
    document["$ref"] = v23["$ref"]
    defs = OrderedDict()
    for key, value in v23["$defs"].items():
        defs[key] = value
    # additive: one shared task object and one event object
    defs["homework_task"] = homework_task_schema()
    patterns = defs["method"]["enum"]
    assert patterns[-1] == "takehome.read", patterns[-1]
    defs["method"]["enum"] = list(patterns) + list(NEW_METHODS)
    for name, entry in methods().items():
        defs["methods"]["properties"][name] = entry
    document["$defs"] = defs
    _bump_echoes(document)
    return document


def _bump_echoes(node) -> None:
    """Every ``contract_version`` echo in the copied body moves with the document identity."""
    if isinstance(node, dict):
        version = node.get("contract_version")
        if isinstance(version, dict) and "const" in version:
            version["const"] = 24
        for value in node.values():
            _bump_echoes(value)
    elif isinstance(node, list):
        for value in node:
            _bump_echoes(value)


def main() -> None:
    document = build()
    TARGET.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    methods_count = len(document["$defs"]["method"]["enum"])
    print(f"wrote {TARGET.relative_to(ROOT)}: {methods_count} declared methods")


if __name__ == "__main__":
    main()
