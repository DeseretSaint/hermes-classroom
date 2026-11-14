"""Derive ``contracts/jobs.v6.json`` from the frozen v5 document.

Run from the repository root::

    python3 probes/derive_jobs_v6.py

Upgrade 36: a lesson section that a rule or the independent validator refuses is re-authored up
to ``LESSON_ATTEMPTS`` times, and until now nothing durable marked a refusal. A run that would
end on a repair screen therefore looked exactly like a run that was going well. The authoring
loop now writes one bounded row per failed attempt at the attempt boundary, and
``job.activity`` reads the newest one as ``retry`` so the waiting pane can say
"section 3, attempt 2 of 3: <reason>".

The amendment is written **onto a parsed v5**, never typed as a second copy: every record this
delta does not name — states, transitions, the progress and usage objects — survives by being
carried. The output is byte-identical to the repository's own serialisation (``json.dumps`` with
``indent=2`` and ``ensure_ascii=False`` plus a trailing newline), which the script asserts against
v5 first.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "jobs.v5.json"
TARGET = ROOT / "contracts" / "jobs.v6.json"

DELTA = (
    "v6 is additive over v5: `job.activity` gains one `retry` object (nullable), the last "
    "*failed* section authoring attempt recorded against this job. The lesson stage re-authors a "
    "refused section up to its attempt limit, and a refusal was previously invisible until the "
    "section parked; the retry names only facts a durable row already holds — the section "
    "ordinal, the attempt that failed and the total, a bounded reason with any answer key "
    "withheld, and the prompt version — so a waiting pane can say where the repair cycle stands. "
    "No state, transition, progress field, usage field or method is added, `retry` is null when "
    "no attempt has failed, and nothing about a job's lifecycle moves."
)

RETRY = {
    "oneOf": [
        {"type": "null"},
        {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "kind",
                "section_ordinal",
                "attempt",
                "attempts_total",
                "reason",
                "prompt_version",
                "at",
            ],
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["lesson_section"],
                    "description": "What was retried. A section is the only retrying unit today.",
                },
                "section_ordinal": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "The plan section's own ordinal (1-based), the number a review pane names.",
                },
                "attempt": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "The attempt that *failed* (1-based), not the attempt about to run.",
                },
                "attempts_total": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "The stage's bounded attempt limit (`LESSON_ATTEMPTS`).",
                },
                "reason": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 240,
                    "description": "The first refusal reason, bounded to the validation reason bound and scrubbed of the check's answer key.",
                },
                "prompt_version": {
                    "type": "string",
                    "maxLength": 80,
                    "description": "The authoring prompt label the refused draft was written under.",
                },
                "at": {
                    "oneOf": [
                        {"$ref": "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/timestamp"},
                        {"type": "null"},
                    ],
                    "description": "When the refusal was recorded; null only when the stored stamp is unparseable.",
                },
            },
        },
    ],
    "description": (
        "The last failed lesson-section attempt recorded against this job, read from the durable "
        "attempt row the authoring loop writes at the attempt boundary. Null when no attempt has "
        "failed — a job that is progressing is not a job that is retrying."
    ),
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def derive(source: dict) -> dict:
    if int(source["x-contract-version"]) != 5:
        raise SystemExit(f"expected jobs.v5.json, found v{source['x-contract-version']}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/jobs"
    document["$id"] = f"{base}/v6"
    document["title"] = "Coursebook job lifecycle v6"
    document["x-contract-version"] = 6
    document["x-supersedes"] = f"{base}/v5"
    document["description"] = f"{DELTA} {source['description']}"
    activity = document["job"]["properties"]["activity"]
    if "retry" in activity["properties"]:
        raise SystemExit("activity already carries retry")
    activity["properties"]["retry"] = RETRY
    if "retry" in activity["required"]:
        raise SystemExit("activity.required already names retry")
    activity["required"] = list(activity["required"]) + ["retry"]
    return document


def main() -> int:
    raw = SOURCE.read_text(encoding="utf-8")
    source = json.loads(raw)
    if serialise(source) != raw:
        raise SystemExit(
            "jobs.v5.json does not round-trip under this serialiser; refusing to write a v6 "
            "whose diff would be every line"
        )
    target = serialise(derive(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
