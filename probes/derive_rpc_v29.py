"""Derive ``contracts/rpc.v29.json`` from the frozen v28 document.

Run from the repository root::

    python3 probes/derive_rpc_v29.py

The amendment (UP-3, Home no longer offers Start on a section with no authored page) is written
**onto a parsed v28**, never typed as a second copy of a 15,000-line document: every record this
delta does not name survives by being carried, so a hand-copy cannot silently drop one.

The delta is one enum value and nothing else: ``library_item.next_step.kind`` gains
``write_lesson``, the kind the kernel returns when an approved plan's section has no authored page
yet. The step names the learner's own work (write the page) instead of claiming a lesson is ready
to start. It carries no job id, stage name or reason code: the surface opens the course's Plan tab
and those are the pipeline's words.

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

#: The v29 header. It states the delta, then carries v28's own description verbatim, which is how
#: every earlier amendment recorded its ancestry in the same field.
DELTA = (
    "v29 is one additive amendment over v28 (UP-3, a section with no authored page): "
    "`library_item.next_step.kind` gains one enum value, `write_lesson`. An approved plan whose "
    "section has no `gen_lessons` page yet is not a lesson to start — Start opened a classroom "
    "with nothing authored — so the kernel names the work that can produce the page and carries "
    "the `objective_id` it belongs to. The label is learner copy and carries no job id, stage "
    "name or reason code. Every v28 record that omits the new kind keeps its exact v28 shape and "
    "bytes. No method, required key, error code, job kind, answer kind, verdict, evidence class "
    "or vocabulary value moves; `contracts/rpc.v28.json` stays byte-identical history and "
    "`x-supersedes` names it."
)

WRITE_KIND = "write_lesson"


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def derive(source: dict) -> dict:
    """v28 plus the `write_lesson` kind and the four wire echoes, and nothing else."""
    if int(source["x-contract-version"]) != 28:
        raise SystemExit(f"expected rpc.v28.json, found v{source['x-contract-version']}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    document["$id"] = f"{base}/v29"
    document["title"] = "Coursebook backend RPC v29"
    document["x-contract-version"] = 29
    document["x-supersedes"] = f"{base}/v28"
    document["description"] = f"{DELTA} {source['description']}"

    kind = document["$defs"]["library_item"]["properties"]["next_step"]["properties"]["kind"]
    if WRITE_KIND in kind["enum"]:
        raise SystemExit("next_step.kind already carries write_lesson")
    kind["enum"].insert(kind["enum"].index("start_lesson") + 1, WRITE_KIND)

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
