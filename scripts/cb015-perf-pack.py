#!/usr/bin/env python3
"""Generate a long, real Coursebook pack for the CB-015 performance proof.

55 objectives, 55 long bilingual sections (CJK + English + romaji), 9 sources and a long course
title. The manifest is built through ``coursebook.packs.build_manifest`` so the content hash,
schema and teaching minima are the backend's own — not a hand-written JSON guess.

    python3 scripts/cb015-perf-pack.py --out ~/.hermes/cb015-test/perf-pack
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import packs  # noqa: E402 - path first

OBJECTIVES = 55
SOURCES = 9

LONG_BODY = """
## {title}

あなたは毎日、少しずつ言葉を覚えています。今日の目標は「{title}」を、自分の言葉で説明できるようになることです。
(anata wa mainichi, sukoshi zutsu kotoba o oboete imasu. kyō no mokuhyō wa ... o, jibun no kotoba de
setsumei dekiru yō ni naru koto desu.) — You learn a little every day. Today's goal is to be able to
explain "{title}" in your own words.

### 場面 (bamen) — the situation

公司の同僚と、初めて会う取引先。敬語を使うべきか、くだけた言い方でよいか、迷う場面です。
The register decision depends on three things: who is listening, how close you are, and where the
conversation happens. A line that is warm between friends can sound careless in a first meeting,
and a line that is correct in a meeting can sound distant at a family table.

| 言い方 | romaji | 使う相手 | effect |
|---|---|---|---|
| お願いします | onegai shimasu | 初対面・上司 | polite request |
| お願い | onegai | 友人・家族 | casual request |
| よろしくお願いいたします | yoroshiku onegai itashimasu | 取引先 | formal, business |

### 練習 (renshū) — practice

1. 友だちに「またね」と言ってください。 (tomodachi ni "mata ne" to itte kudasai.)
2. 先生に「失礼します」と言ってください。 (sensei ni "shitsurei shimasu" to itte kudasai.)
3. 取引先に、自分の名前と会社を紹介してください。 (torihikisaki ni, jibun no namae to kaisha o
   shōkai shite kudasai.)

### なぜ大切か (naze taisetsu ka) — why it matters

Politeness is not decoration. It tells the listener what relationship you think you have with
them. Choosing the wrong register is not a grammar error; it is a claim about the relationship.
That is why this course asks you to name the addressee, the setting and the relationship before
you choose a line, and why a romaji-only answer is accepted as a scaffold but not as evidence of
reading Japanese.

> 言葉は、相手との距離を決める。 (kotoba wa, aite to no kyori o kimeru.)
> Words decide the distance between you and the other person.
""".strip()


def build(out: Path) -> dict:
    files: dict[str, bytes] = {}
    meta: dict[str, dict] = {}
    objectives: list[dict] = []

    for ordinal in range(1, OBJECTIVES + 1):
        section_path = f"content/section-{ordinal:02d}.md"
        title = f"Objective {ordinal}: register in context {ordinal}"
        body = LONG_BODY.format(title=title) + "\n\n" + (LONG_BODY.format(title=title) + "\n")
        data = body.encode("utf-8")
        files[section_path] = data
        meta[section_path] = {"mime": "text/markdown", "role": "section"}
        objectives.append(
            {
                "objective_id": f"obj-perf-{ordinal:02d}",
                "ordinal": ordinal,
                "title": title if ordinal < 40 else f"{title} — with a deliberately long title that must wrap without clipping the row or the objective header at 200% text",
                "evidence_target": ["discrimination", "comprehension", "recall", "transfer"][ordinal % 4],
                "evidence_criteria": [
                    "Names the addressee and the relationship",
                    "Chooses a register and says why",
                    "Transfers the reasoning to one new setting",
                ],
                "estimated_minutes": 8,
                "sections": [
                    {"section_id": f"sec-perf-{ordinal:02d}", "title": title, "path": section_path}
                ],
                "checks": [
                    {
                        "check_id": f"chk-perf-{ordinal:02d}",
                        "version": 1,
                        "locale": "ja-JP",
                        "evidence_target": ["discrimination", "comprehension", "recall", "transfer"][ordinal % 4],
                        "stimulus": (
                            f"Objective {ordinal}. 初対面の取引先に、自分の会社を紹介してください。"
                            " Which register do you choose, and which word carries the politeness? "
                            "Answer in one line."
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
        for index in range(1, SOURCES + 1)
    ]

    manifest = packs.build_manifest(
        pack_id="cb015-perf-long-l0",
        pack_version="1.0.0",
        title=(
            "Japanese register across fifty-five situations — a deliberately long course title "
            "used to prove the route stays readable at 200% text and in a 460px window"
        ),
        recipe="casual",
        minimum_coursebook_version="0.1.0",
        license={
            "id": "unspecified",
            "note": "Performance fixture authored for CB-015; not for redistribution.",
            "redistribution": "local_only",
        },
        attribution="Original text generated for the CB-015 performance proof.",
        objectives=objectives,
        files=files,
        file_metadata=meta,
        sources=sources,
        subtitle="55 objectives, 55 long bilingual sections, 9 sources — a width and length stress fixture.",
        locale="ja-JP",
        level_label="CEFR A1 · ab initio (L0)",
        content_notes=["Fixture text is original and repetitive by design; it is not teaching material."],
        safety_notes=["Adult self-study framing; no audio, so no listening evidence is claimed."],
        accessibility_notes=["Every Japanese line carries romaji and an English meaning."],
    )

    out.mkdir(parents=True, exist_ok=True)
    (out / packs.root_file()).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for path, data in files.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path.home() / ".hermes" / "cb015-test" / "perf-pack"))
    args = parser.parse_args()
    manifest = build(Path(args.out))
    print(json.dumps({
        "out": args.out,
        "pack_id": manifest["pack_id"],
        "objectives": len(manifest["objectives"]),
        "files": len(manifest["files"]),
        "sources": len(manifest.get("sources") or []),
        "content_hash": manifest["content_hash"],
        "bytes": sum(entry["bytes"] for entry in manifest["files"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
