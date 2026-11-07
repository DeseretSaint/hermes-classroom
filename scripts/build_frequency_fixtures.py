#!/usr/bin/env python3
"""Rebuild the synthetic H-89 frequency fixtures and stamp their canonical rows hash.

The fixture rows are hand-authored teaching examples. They are **not** a corpus frequency count
and must never be presented as one; each document says so in ``scope_note`` and ``attribution``.
This builder exists so ``content_hash`` is derived from the shipped rows instead of typed by
hand. Run it from the repository root:

    python3 scripts/build_frequency_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures" / "frequency"


def rows_hash(rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def row(rank, lemma, reading, pos, band):
    return {
        "rank": rank,
        "lemma": lemma,
        "reading": reading,
        "part_of_speech": pos,
        "band": band,
    }


JA_ROWS = [
    row(1, "は", "は", "particle", "band-core"),
    row(2, "です", "です", "copula", "band-core"),
    row(3, "水", "みず", "noun", "band-core"),
    row(4, "これ", "これ", "pronoun", "band-core"),
    row(5, "食べる", "たべる", "verb", "band-core"),
    row(6, "私", "わたし", "pronoun", "band-core"),
    row(7, "行く", "いく", "verb", "band-core"),
    row(8, "大きい", "おおきい", "adjective", "band-core"),
    row(9, "今日", "きょう", "noun", "band-core"),
    row(10, "とても", "とても", "adverb", "band-core"),
    row(11, "電車", "でんしゃ", "noun", "band-core"),
    row(12, "ありがとう", "ありがとう", "expression", "band-core"),
    row(13, "新幹線", "しんかんせん", "noun", "band-extension"),
    row(14, "予約", "よやく", "noun", "band-extension"),
    row(15, "確認", "かくにん", "noun", "band-extension"),
]

ES_ROWS = [
    row(1, "agua", "agua", "noun", "band-core"),
    row(2, "comer", "comer", "verb", "band-core"),
    row(3, "casa", "casa", "noun", "band-core"),
    row(4, "grande", "grande", "adjective", "band-core"),
    row(5, "hoy", "hoy", "adverb", "band-core"),
    row(6, "gracias", "gracias", "expression", "band-core"),
]


def document(*, inventory_id, language, source_id, rows, bands, scope_note):
    return {
        "contract": "cb.frequency_inventory",
        "contract_version": 1,
        "inventory_id": inventory_id,
        "language": language,
        "source_id": source_id,
        "source_url": f"https://example.invalid/coursebook/{source_id}",
        "licence": "CC0-1.0",
        "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": (
            "Synthetic H-89 test fixture authored for Coursebook. No corpus was consulted and "
            "no frequency was measured."
        ),
        "redistribution": "allowed",
        "modality": "mixed",
        "tokenization": (
            "Hand-authored fixture rows, one row per short unit; ranks are the fixture's own "
            "teaching order, not a corpus count."
        ),
        "scope_note": scope_note,
        "published_at": "2026-11-07T00:00:00Z",
        "fetched_at": "2026-11-07T00:00:00Z",
        "content_hash": rows_hash(rows),
        "bands": bands,
        "rows": rows,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ja = document(
        inventory_id="fixture-ja-core-v1",
        language="ja",
        source_id="coursebook-fixture-ja-v1",
        rows=JA_ROWS,
        bands=[
            {"id": "band-core", "label": "fixture core", "from_rank": 1, "to_rank": 12},
            {
                "id": "band-extension",
                "label": "fixture extension",
                "from_rank": 13,
                "to_rank": 15,
            },
        ],
        scope_note=(
            "Synthetic teaching fixture. The ranks order this fixture's own rows for the H-89 "
            "sequence tests; they are not measured corpus frequencies and say nothing about "
            "coverage or comprehension."
        ),
    )
    es = document(
        inventory_id="fixture-es-core-v1",
        language="es",
        source_id="coursebook-fixture-es-v1",
        rows=ES_ROWS,
        bands=[{"id": "band-core", "label": "fixture core", "from_rank": 1, "to_rank": 6}],
        scope_note=(
            "Synthetic teaching fixture for the non-Japanese seam test. The ranks order this "
            "fixture's own rows; they are not measured corpus frequencies and say nothing about "
            "coverage or comprehension."
        ),
    )
    for name, doc in (("ja-core-v1.json", ja), ("es-core-v1.json", es)):
        (OUT / name).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(name, doc["content_hash"])


if __name__ == "__main__":
    main()
