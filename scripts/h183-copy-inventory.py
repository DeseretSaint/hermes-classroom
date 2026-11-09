#!/usr/bin/env python3
"""H-183 copy inventory: scan the rendered learner surfaces and the shipped prose literals.

    python3 scripts/h183-copy-inventory.py

Reads the frames this card rendered (audit/visual/h183-copy/html and check-after/html), strips
`<details>` disclosures and markup exactly as a reader sees them, and reports every banned token.
Then scans the shipped module's prose string literals (comment lines removed) for the same tokens.
Writes `audit/visual/h183-copy/copy-inventory.json`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "audit" / "visual" / "h183-copy"

BANNED = (
    (r"lessons job", "backend machinery"),
    (r"\bjobs?\b", "backend machinery"),
    (r"\bqueued\b", "backend machinery"),
    (r"\bqueue\b", "backend machinery"),
    (r"\bnext tick\b", "scheduler machinery"),
    (r"\brevision\b", "backend machinery"),
    (r"\breconcile\b", "backend machinery"),
    (r"plan-pending", "backend machinery"),
    (r"JOB_FAILED", "typed error code in default copy"),
    (r"not registered", "build-registration machinery"),
    (r"\bH-?1\d{2}\b", "internal ticket label"),
    (r"\b(?:job|enr|obj|pln|crs|doc|blk)_[0-9a-f]{6,}\b", "raw id"),
)

DETAILS = re.compile(r"<details\b.*?</details>", re.S | re.I)
TAGS = re.compile(r"<[^>]+>")


def visible_text(html: str) -> str:
    return re.sub(r"\s+", " ", TAGS.sub(" ", DETAILS.sub(" ", html))).strip()


def scan(text: str) -> list[dict]:
    hits = []
    for pattern, kind in BANNED:
        for match in re.finditer(pattern, text, re.I):
            hits.append({"pattern": pattern, "kind": kind, "found": match.group(0)})
    return hits


def scan_source(path: Path) -> tuple[list[dict], list[dict]]:
    """Return (learner_copy_hits, technical_context_hits).

    A literal that is a thrown internal message, a Tailwind class, the operator-only surface, or a
    row inside the create receipt's Technical detail is context, not learner copy. Those are
    reported separately so the pass/fail line is about what a person can read.
    """
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    kept = [
        line for line in source.split("\n")
        if not line.lstrip().startswith("//") and not line.lstrip().startswith("*")
    ]
    literal = re.compile(
        r"'([^'\\\n]*(?:\\.[^'\\\n]*)*)'|\"([^\"\\\n]*(?:\\.[^\"\\\n]*)*)\"|`([^`\\\n]*(?:\\.[^`\\\n]*)*)`"
    )
    technical_markers = (
        "new Error(",
        "min-h-",
        "items-stretch",
        "You are the operator",
        "job.error.code",
        "job.error.message",
        "label: 'Plan job'",
    )
    learner, technical = [], []
    for number, line in enumerate(kept, start=1):
        for match in literal.finditer(line):
            text = match.group(1) or match.group(2) or match.group(3) or ""
            if " " not in text:
                continue
            hits = scan(text)
            if not hits:
                continue
            bucket = technical if any(marker in line for marker in technical_markers) else learner
            for item in hits:
                bucket.append({**item, "line": number, "text": text})
    return learner, technical


def main() -> int:
    report = {"surfaces": {}, "source": {}}
    html_root = OUT / "html"
    for path in sorted(html_root.glob("*.html")):
        if not path.name.startswith("after-"):
            continue
        report["surfaces"][path.name] = scan(visible_text(path.read_text(encoding="utf-8")))
    check_root = OUT / "check-after" / "html"
    for path in sorted(check_root.glob("*.html")):
        report["surfaces"][f"check-after/{path.name}"] = scan(
            visible_text(path.read_text(encoding="utf-8"))
        )
    learner, technical = scan_source(ROOT / "desktop" / "plugin.js")
    report["source"]["desktop/plugin.js"] = {"learner_copy": learner, "technical_context": technical}
    (OUT / "copy-inventory.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    bad = 0
    for name, hits in report["surfaces"].items():
        status = "CLEAN" if not hits else f"{len(hits)} HITS"
        print(f"{status:>8}  {name}")
        bad += len(hits)
    print(f"{'CLEAN' if not learner else 'HITS':>8}  shipped learner-copy literals")
    for hit in learner:
        print(f"          line {hit['line']}: {hit['pattern']} in {hit['text']!r}")
    bad += len(learner)
    for hit in technical:
        print(f"   note  line {hit['line']}: {hit['pattern']} in technical context {hit['text']!r}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
