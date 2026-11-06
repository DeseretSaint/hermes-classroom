#!/usr/bin/env python3
"""Sentinel performance fixture generator.

Builds two REAL Coursebook packs through ``coursebook.packs.build_manifest`` so the schema,
content hash and teaching minima are the backend's own rules, not a hand-written guess:

  * ``sentinel-long-55``     — 55 objectives. Sections 1 and 55 are multi-thousand-word bodies with
                               long code blocks, long ordered lists and long tables. Every other
                               section is a normal-length lesson. 12 sources.
  * ``sentinel-baseline-3``  — 3 objectives, short sections, no code. The apples-to-apples baseline
                               measured in the same harness on the same machine.

Output: one directory plus one .zip per pack under --out (the shape /packs/grant expects).

    python3 docs/sentinel-perf/make-stress-pack.py --out /home/deseretsaint/.hermes/sentinel-perf/packs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from coursebook import archive as pack_archive  # noqa: E402 - path first
from coursebook import packs  # noqa: E402 - path first

LONG_OBJECTIVES = 55
BASE_OBJECTIVES = 3

PARA_POOL = [
    "A register is a promise about the relationship. The same proposition can be warm, neutral or cold "
    "depending on the ending you attach to it, and the listener reads that choice before they read the "
    "content. This paragraph exists to give the markdown renderer a realistic run of prose: no markup, "
    "no unusual characters, just the kind of dense explanation a learner would actually meet in a "
    "textbook section, repeated with enough variation that line breaking and scroll height stay honest.",
    "When you choose a form you are also choosing who is allowed to disagree with you. Informal speech "
    "invites correction; formal speech postpones it. That asymmetry is the whole reason a course cannot "
    "teach vocabulary in isolation and call the job done. The section below walks through three settings, "
    "then asks you to name the addressee, the place and the relationship before you answer anything.",
    "The practical test is simple. Say the line out loud and ask whether you would say it to the person "
    "in front of you, in this room, at this hour. If the answer is no, the grammar may still be correct "
    "and the sentence is still wrong. Learners who memorise only the polite column tend to sound distant "
    "with friends; learners who memorise only the casual column tend to sound careless in meetings.",
    "Reading is slower than recognition. A learner can pick the right line from four options long before "
    "they can produce it under time pressure, and a course that only tests recognition will report "
    "progress the learner does not have. That is why every objective here carries a production check as "
    "well as a comprehension check, and why the evidence target changes from section to section.",
    "Feedback has to arrive while the choice is still fresh. A correction delivered a week later teaches "
    "the rule but not the habit. The lesson page therefore puts the check immediately under the teaching "
    "segment, and the notebook sits one pane away so a learner can capture the exact sentence that "
    "surprised them without losing their place in the text.",
]

CODE_BLOCK = """```python
# A deliberately long block: the renderer has to lay out real code, not a one-line snippet.
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Register:
    name: str
    addressee: str
    setting: str
    distance: int
    examples: tuple[str, ...] = field(default_factory=tuple)

    def acceptable(self, *, addressee: str, setting: str) -> bool:
        if addressee != self.addressee:
            return False
        if setting != self.setting:
            return False
        return True


REGISTERS = (
    Register("casual", "friend", "home", 1, ("またね", "お願い")),
    Register("polite", "colleague", "office", 3, ("お願いします", "失礼します")),
    Register("formal", "client", "meeting", 5, ("よろしくお願いいたします",)),
)


def choose(addressee: str, setting: str) -> Register | None:
    for register in REGISTERS:
        if register.acceptable(addressee=addressee, setting=setting):
            return register
    return None


def explain(register: Register) -> str:
    return (
        f"{register.name}: addressed to a {register.addressee} in a {register.setting}; "
        f"social distance {register.distance}."
    )


def audit(rows: Iterable[dict]) -> list[str]:
    problems: list[str] = []
    for row in rows:
        register = choose(row.get("addressee", ""), row.get("setting", ""))
        if register is None:
            problems.append(f"no register for {row!r}")
            continue
        if row.get("line") not in register.examples:
            problems.append(f"{row['line']!r} is not an example of {register.name}")
    return problems


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, list):
        raise ValueError("expected a list of rows")
    return document


def main() -> int:
    rows = load(Path("rows.json"))
    problems = audit(rows)
    if problems:
        for problem in problems:
            print(problem)
        return 1
    for row in rows:
        register = choose(row["addressee"], row["setting"])
        print(explain(register))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```"""


def long_list() -> str:
    lines = ["### Checklist — every item must be named before you answer", ""]
    for index in range(1, 121):
        lines.append(
            f"{index}. Item {index}: name the addressee, name the setting, then choose one register "
            f"and say in one sentence why the other two registers would be wrong here."
        )
    return "\n".join(lines)


def long_table() -> str:
    lines = [
        "### Register matrix",
        "",
        "| # | 言い方 | romaji | addressee | setting | distance |",
        "|---|---|---|---|---|---|",
    ]
    for index in range(1, 41):
        lines.append(
            f"| {index} | お願いします {index} | onegai shimasu {index} | colleague {index} "
            f"| office {index} | {index % 5 + 1} |"
        )
    return "\n".join(lines)


def long_body(title: str, ordinal: int) -> str:
    """~5,000 words of prose plus a long code block, a 120-item list and a 40-row table."""
    chunks = [f"## {title}", ""]
    paragraphs = 52
    for index in range(paragraphs):
        chunks.append(PARA_POOL[index % len(PARA_POOL)])
        chunks.append("")
        if index == 6:
            chunks.append(CODE_BLOCK)
            chunks.append("")
        if index == 20:
            chunks.append(long_list())
            chunks.append("")
        if index == 34:
            chunks.append(long_table())
            chunks.append("")
        if index % 8 == 7:
            chunks.append(f"### Checkpoint {index // 8 + 1} — section {ordinal}")
            chunks.append("")
            chunks.append(
                "Before continuing, write one sentence that names the addressee and the relationship, "
                "and one sentence that would be correct for a different addressee. Keep both."
            )
            chunks.append("")
    chunks.append(
        "> 言葉は、相手との距離を決める。 (kotoba wa, aite to no kyori o kimeru.)\n"
        "> Words decide the distance between you and the other person."
    )
    return "\n".join(chunks)


def normal_body(title: str, ordinal: int) -> str:
    chunks = [f"## {title}", ""]
    for index in range(4):
        chunks.append(PARA_POOL[(index + ordinal) % len(PARA_POOL)])
        chunks.append("")
    chunks.append("### Practice")
    chunks.append("")
    for index in range(1, 7):
        chunks.append(f"{index}. Say the line for situation {ordinal}.{index} and name the addressee.")
    chunks.append("")
    chunks.append("```text\naddressee: ______   setting: ______   register: ______\n```")
    chunks.append("")
    chunks.append("> 言葉は、相手との距離を決める。 (kotoba wa, aite to no kyori o kimeru.)")
    return "\n".join(chunks)


# cb.rpc v6 caps a single lesson segment at 8000 characters. A pack section file becomes ONE
# teaching segment on import, so a legal long section must stay under that cap.
SEGMENT_SAFE_CHARS = 7800


def capped_long_section(title: str, part: int) -> str:
    """A ~7,700-character section that still carries a code block, a list and a table."""
    chunks = [f"## {title} — part {part}", ""]
    pool_index = part
    while True:
        candidate = "\n".join(chunks)
        if len(candidate) > SEGMENT_SAFE_CHARS - 2400:
            break
        chunks.append(PARA_POOL[pool_index % len(PARA_POOL)])
        chunks.append("")
        pool_index += 1
        if pool_index % 5 == 0:
            chunks.append(
                f"> Part {part}, checkpoint {pool_index // 5}: name the addressee before you choose a register."
            )
            chunks.append("")
    if part == 1:
        chunks.append(CODE_BLOCK)
        chunks.append("")
    if part == 2:
        chunks.append(long_list()[:900])
        chunks.append("")
    if part == 3:
        chunks.append(long_table()[:1200])
        chunks.append("")
    chunks.append("> 言葉は、相手との距離を決める。 (kotoba wa, aite to no kyori o kimeru.)")
    body = "\n".join(chunks)
    if len(body) > SEGMENT_SAFE_CHARS:
        # Trim on a paragraph boundary until the section fits the contract cap.
        paragraphs = body.split("\n\n")
        while len("\n\n".join(paragraphs)) > SEGMENT_SAFE_CHARS and len(paragraphs) > 2:
            paragraphs.pop(-2)
        body = "\n\n".join(paragraphs)
    assert len(body) <= SEGMENT_SAFE_CHARS, f"section {len(body)} chars exceeds {SEGMENT_SAFE_CHARS}"
    return body



def build_pack(
    *,
    pack_id: str,
    title: str,
    count: int,
    long_sections: set[int],
    with_sources: int,
    capped_parts: int = 0,
    capped_ordinals: tuple[int, ...] = (),
) -> tuple[dict, dict[str, bytes]]:
    files: dict[str, bytes] = {}
    meta: dict[str, dict] = {}
    objectives: list[dict] = []

    for ordinal in range(1, count + 1):
        heading = f"Objective {ordinal}: register in context {ordinal}"
        if ordinal == count and count > 10:
            heading = (
                f"Objective {ordinal}: register in context {ordinal} — a deliberately long title that "
                "must wrap without clipping the row or the objective header at 200% text"
            )
        sections: list[dict] = []
        if capped_parts and ordinal in capped_ordinals:
            for part in range(1, capped_parts + 1):
                path = f"content/section-{ordinal:02d}-{part}.md"
                part_title = f"{heading} (part {part} of {capped_parts})"
                data = capped_long_section(heading, part).encode("utf-8")
                files[path] = data
                meta[path] = {"mime": "text/markdown", "role": "section"}
                sections.append({"section_id": f"sec-perf-{ordinal:02d}-{part}", "title": part_title, "path": path})
        else:
            path = f"content/section-{ordinal:02d}.md"
            body = long_body(heading, ordinal) if ordinal in long_sections else normal_body(heading, ordinal)
            data = body.encode("utf-8")
            files[path] = data
            meta[path] = {"mime": "text/markdown", "role": "section"}
            sections.append({"section_id": f"sec-perf-{ordinal:02d}", "title": heading, "path": path})
        objectives.append(
            {
                "objective_id": f"obj-perf-{ordinal:02d}",
                "ordinal": ordinal,
                "title": heading,
                "evidence_target": ["discrimination", "comprehension", "recall", "transfer"][ordinal % 4],
                "evidence_criteria": [
                    "Names the addressee and the relationship",
                    "Chooses a register and says why",
                    "Transfers the reasoning to one new setting",
                ],
                "estimated_minutes": 8,
                "sections": sections,
                "checks": [
                    {
                        "check_id": f"chk-perf-{ordinal:02d}",
                        "version": 1,
                        "locale": "ja-JP",
                        "evidence_target": ["discrimination", "comprehension", "recall", "transfer"][ordinal % 4],
                        "stimulus": (
                            f"Objective {ordinal}. 初対面の取引先に、自分の会社を紹介してください。 "
                            "Which register do you choose, and which word carries the politeness? Answer in one line."
                        ),
                        "reference_answer": "よろしくお願いいたします (yoroshiku onegai itashimasu)",
                        "accepted_alternatives": ["よろしくお願いいたします", "yoroshiku onegai itashimasu"],
                        "rubric": [
                            "Chooses the formal business register",
                            "Names the addressee and the relationship",
                            "Does not use the casual form for a first meeting",
                        ],
                        "audit_state": "unreviewed",
                    }
                ],
            }
        )

    sources = [
        {
            "source_id": f"src-perf-{index:02d}",
            "title": f"Reference {index}: Japanese register and honorific speech in context",
            "url": f"https://example.org/coursebook/reference-{index:02d}",
            "publisher": "Coursebook perf fixture",
            "source_type": "reference",
            "support_status": "model_assessed",
            "fetched_at": "2026-11-06",
            "bundled": False,
            "license_note": "Linked, not bundled; no third-party text is copied.",
        }
        for index in range(1, with_sources + 1)
    ]

    manifest = packs.build_manifest(
        pack_id=pack_id,
        pack_version="1.0.0",
        title=title,
        recipe="casual",
        minimum_coursebook_version="0.1.0",
        license={
            "id": "unspecified",
            "note": "Sentinel performance fixture; not for redistribution.",
            "redistribution": "local_only",
        },
        attribution="Original text generated for the Sentinel performance proof.",
        objectives=objectives,
        files=files,
        file_metadata=meta,
        sources=sources,
        subtitle=f"{count} objectives — a width and length stress fixture.",
        locale="ja-JP",
        level_label="CEFR A1 · ab initio (L0)",
        content_notes=["Fixture text is original and repetitive by design; it is not teaching material."],
        safety_notes=["Adult self-study framing; no audio, so no listening evidence is claimed."],
        accessibility_notes=["Every Japanese line carries romaji and an English meaning."],
    )
    return manifest, files


def write_pack(out: Path, pack_id: str, manifest: dict, files: dict[str, bytes]) -> dict:
    staging = out / pack_id
    if staging.exists():
        import shutil

        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    (staging / packs.root_file()).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for path, data in files.items():
        target = staging / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    archive = out / f"{pack_id}.zip"
    pack_archive.write_archive(archive, manifest, files)
    return {
        "pack_id": pack_id,
        "directory": str(staging),
        "archive": str(archive),
        "archive_bytes": archive.stat().st_size,
        "objectives": len(manifest["objectives"]),
        "files": len(manifest["files"]),
        "sources": len(manifest.get("sources") or []),
        "content_hash": manifest["content_hash"],
        "expanded_bytes": sum(entry["bytes"] for entry in manifest["files"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path.home() / ".hermes" / "sentinel-perf" / "packs"))
    args = parser.parse_args()
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    long_manifest, long_files = build_pack(
        pack_id="sentinel-long-55",
        title="Japanese register across fifty-five situations — a deliberately long course title used to "
        "prove the route stays readable at 200% text and in a 460px window",
        count=LONG_OBJECTIVES,
        long_sections={1, LONG_OBJECTIVES},
        with_sources=12,
    )
    base_manifest, base_files = build_pack(
        pack_id="sentinel-baseline-3",
        title="Japanese register: three-situation baseline",
        count=BASE_OBJECTIVES,
        long_sections=set(),
        with_sources=2,
    )
    legal_manifest, legal_files = build_pack(
        pack_id="sentinel-long-60-legal",
        title="Japanese register across sixty situations — maximum legal section length, three-part lessons",
        count=60,
        long_sections=set(),
        with_sources=12,
        capped_parts=3,
        capped_ordinals=(1, 60),
    )

    result = {
        "long": write_pack(out, "sentinel-long-55", long_manifest, long_files),
        "baseline": write_pack(out, "sentinel-baseline-3", base_manifest, base_files),
        "legal": write_pack(out, "sentinel-long-60-legal", legal_manifest, legal_files),
        "long_section_word_counts": {
            "section-01": len(long_files["content/section-01.md"].decode().split()),
            "section-55": len(long_files[f"content/section-{LONG_OBJECTIVES:02d}.md"].decode().split()),
            "section-02": len(long_files["content/section-02.md"].decode().split()),
        },
        "legal_section_chars": {
            path: len(legal_files[path].decode())
            for path in sorted(legal_files)
            if path.startswith(("content/section-01-", "content/section-60-", "content/section-02."))
        },
        "legal_lesson_word_counts": {
            "objective-01": sum(len(legal_files[f"content/section-01-{part}.md"].decode().split()) for part in (1, 2, 3)),
            "objective-60": sum(len(legal_files[f"content/section-60-{part}.md"].decode().split()) for part in (1, 2, 3)),
            "objective-02": len(legal_files["content/section-02.md"].decode().split()),
        },
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
