"""Derive ``contracts/rpc.v27.json`` from the frozen v26 document.

Run from the repository root::

    python3 probes/derive_rpc_v27.py

The amendment (item 28b, the figure's own drawn labels) is written **onto a parsed v26**, never
typed as a second copy of a 13,000-line document: every record this delta does not name — the
method enum, ``world_brief.route_anchors``, the error and job references — survives by being
carried, so a hand-copy cannot silently drop one.

The output is byte-identical to the repository's own serialisation (``json.dumps`` with
``indent=2`` and ``ensure_ascii=False`` plus a trailing newline), which the script asserts against
v26 first: if the round trip of the input document is not byte-exact, the formatting contract has
changed and the script refuses to write a v27 that would diff in every line.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "contracts" / "rpc.v26.json"
TARGET = ROOT / "contracts" / "rpc.v27.json"

#: The v27 header. It states the delta, then carries v26's own description verbatim, which is how
#: every earlier amendment recorded its ancestry in the same field.
DELTA = (
    "v27 is one additive amendment over v26 (item 28b, the figure's own drawn labels): the "
    "$defs/lesson_document_media record gains one optional `labels` array — at most eight entries "
    "of `{text, x, y, anchor}`, where `text` is 1–40 characters a learner reads, `x` and `y` are "
    "normalised 0–1 coordinates inside the figure box, and `anchor` places that point at the "
    "label's `start`, `center` or `end` — so a lesson figure can carry a readable annotation "
    "without the image model ever painting text. The array is page text the product UI draws over "
    "a textless raster: it carries no check, answer key, rubric, attempt, artifact id or artifact "
    "byte, it never enters an image prompt or a content-addressed cache key, and a media child "
    "that omits it keeps its exact v26 shape and bytes, so every stored v26 lesson document reads "
    "unchanged. A malformed label (more than eight, empty or over-long text, a fraction outside "
    "0–1, an unknown anchor) is refused at the field, never by a generic internal error. No "
    "method, request shape, required key, error code, job kind, answer kind, verdict, evidence "
    "class or vocabulary value moves; `contracts/rpc.v26.json` stays byte-identical history and "
    "`x-supersedes` names it."
)

LABELS = {
    "type": "array",
    "description": (
        "Text the product UI draws over the figure, in the figure's own box. Absent means the "
        "figure carries no drawn label. It is presentation of readable text, never instruction: "
        "it holds no answer key and it never travels into the image request."
    ),
    "maxItems": 8,
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "x", "y", "anchor"],
        "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 40},
            "x": {"type": "number", "minimum": 0, "maximum": 1},
            "y": {"type": "number", "minimum": 0, "maximum": 1},
            "anchor": {"type": "string", "enum": ["start", "center", "end"]},
        },
    },
}


def serialise(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def derive(source: dict) -> dict:
    """v26 plus the labels delta and the four wire echoes, and nothing else."""
    if int(source["x-contract-version"]) != 26:
        raise SystemExit(f"expected rpc.v26.json, found v{source['x-contract-version']}")
    document = json.loads(json.dumps(source))  # deep copy; the source file is never edited
    base = "https://contracts.coursebook.hermes/rpc"
    document["$id"] = f"{base}/v27"
    document["title"] = "Coursebook backend RPC v27"
    document["x-contract-version"] = 27
    document["x-supersedes"] = f"{base}/v26"
    document["description"] = f"{DELTA} {source['description']}"

    media = document["$defs"]["lesson_document_media"]
    if "labels" in media["properties"]:
        raise SystemExit("lesson_document_media already carries labels")
    media["properties"]["labels"] = LABELS

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
        if echo.get("const") != 26:
            raise SystemExit(f"unexpected wire echo {echo!r}")
        echo["const"] = 27
    return document


def main() -> int:
    raw = SOURCE.read_text(encoding="utf-8")
    source = json.loads(raw)
    if serialise(source) != raw:
        raise SystemExit(
            "rpc.v26.json does not round-trip under this serialiser; refusing to write a v27 "
            "whose diff would be every line"
        )
    target = serialise(derive(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
