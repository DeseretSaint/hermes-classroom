"""Measure ``coursebook.relevance``'s floors on the text production actually scores.

Production (``research.run_research``) scores ``content[:6000]`` — the raw fetched content clipped to
``ResearchBudget.max_page_chars`` — while the module docstring's figures were measured on unbounded
content. This probe recomputes every page of every committed packet both ways, through the same
``gate_pages`` production calls, and writes ``measure.json`` beside itself.

Run: ``python3 audit/relevance-floors/measure_relevance_floors.py``
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from coursebook import relevance, research  # noqa: E402
from coursebook.research import ResearchBudget  # noqa: E402

TRANSCRIPT = ROOT / "audit" / "adversarial" / "harness-e2e" / "transcripts" / "soldering_full.json"
BOUND = ResearchBudget().max_page_chars  # 6000 — what run_research slices content to


def _verdict_rows(gate: dict[str, Any]) -> list[dict[str, Any]]:
    kept = set(gate["kept"])
    rows = []
    for entry in gate["verdicts"]:
        rows.append(
            {
                "index": entry["index"],
                "url": entry["url"],
                "title": entry["title"],
                "score": entry["score"],
                "verdict": entry["verdict"],
                "kept": entry["index"] in kept,
                "matched": list(entry["matched"]),
                "reason": entry["reason"],
            }
        )
    return rows


def _distribution(
    gate: dict[str, Any],
    rows: list[dict[str, Any]],
    texts: list[str],
    source_texts: list[str] | None = None,
) -> dict[str, Any]:
    """Summarise one gate pass.

    ``texts`` are the strings the gate actually scored; ``source_texts`` are the fetched bodies they
    were cut from. Clipping must be measured against the source, never against the already-bounded
    text — ``len(text[:BOUND]) > BOUND`` is false by construction and would report "nothing clipped"
    in the very block whose job is length honesty.
    """

    clipped_check = texts if source_texts is None else source_texts
    best = gate["best_score"]
    floor = relevance.MIN_COVERAGE
    margin = relevance.RELATIVE_MARGIN * best
    terms = gate["terms"]
    matched_anywhere = sorted({term for row in rows for term in row["matched"]})
    return {
        "best_score": best,
        "min_coverage": floor,
        "relative_line": round(margin, 4),
        "pages_at_or_above_min_coverage": sum(1 for r in rows if r["score"] >= floor),
        "pages_admitted_by_relative_margin_only": sum(
            1 for r in rows if margin <= r["score"] < floor
        ),
        "pages_below_both_lines": sum(1 for r in rows if r["score"] < floor and r["score"] < margin),
        "kept": len(gate["kept"]),
        "dropped": len(gate["dropped"]),
        "floor_tripped": gate["floor_tripped"],
        "goal_terms": terms,
        "goal_term_count": len(terms),
        "goal_terms_matched_by_any_page": matched_anywhere,
        "goal_terms_matched_by_any_page_count": len(matched_anywhere),
        "goal_terms_matched_by_no_page": [t for t in terms if t not in matched_anywhere],
        "text_chars": [len(t) for t in texts],
        "texts_clipped": [len(t) > BOUND for t in clipped_check],
    }


def _gate(goal: str, pages: list[dict[str, Any]], bound: int | None) -> tuple[dict, list[str]]:
    texts = [
        (page.get("text") or "") if bound is None else (page.get("text") or "")[:bound]
        for page in pages
    ]
    gate = relevance.gate_pages(
        goal,
        [
            {"title": page.get("title") or "", "url": page.get("url") or "", "text": text}
            for page, text in zip(pages, texts)
        ],
    )
    return gate, texts


def _measure_packet(name: str, goal: str, pages: list[dict[str, Any]], notes: list[str]) -> dict[str, Any]:
    full_gate, full_texts = _gate(goal, pages, None)
    bounded_gate, bounded_texts = _gate(goal, pages, BOUND)
    fetched_texts = [page.get("text") or "" for page in pages]
    return {
        "packet": name,
        "goal": goal,
        "bound_chars": BOUND,
        "pages": [
            {
                "url": page.get("url"),
                "title": page.get("title"),
                "body_chars_fetched": len(page.get("text") or ""),
                "body_chars_scored_full": len(full_texts[index]),
                "body_chars_scored_bounded": len(bounded_texts[index]),
                "clipped_by_bound": len(page.get("text") or "") > BOUND,
            }
            for index, page in enumerate(pages)
        ],
        "unbounded": {
            "table": _verdict_rows(full_gate),
            "distribution": _distribution(full_gate, _verdict_rows(full_gate), full_texts),
        },
        "bounded_6000": {
            "table": _verdict_rows(bounded_gate),
            "distribution": _distribution(
                bounded_gate, _verdict_rows(bounded_gate), bounded_texts, fetched_texts
            ),
        },
        "notes": notes,
    }


class _ReplaySearch:
    """Replay the committed pages through the real ``run_research`` fetch path."""

    def __init__(self, pages: list[dict[str, Any]], batch: int = 4) -> None:
        self.pages = pages
        self.batch = batch
        self.calls = 0

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        start = self.calls * self.batch
        self.calls += 1
        rows = self.pages[start : start + self.batch]
        return [{"url": p["url"], "title": p["title"], "description": ""} for p in rows][:limit]

    def fetch(self, url: str, max_chars: int) -> dict[str, Any]:
        page = next(p for p in self.pages if p["url"] == url)
        return {
            "url": url,
            "title": page["title"],
            "content": page["content"],
            "published_at": None,
        }


def _production_run(goal: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    budget = ResearchBudget(
        max_queries=2,
        max_results_per_query=4,
        max_pages=len(pages),
        max_sources=len(pages),
    )
    run = research.run_research(
        goal,
        recipe="committed",
        dials={"depth": "working"},
        scope="short",
        search=_ReplaySearch(pages),
        budget=budget,
    )
    return {
        "status": run.status,
        "terms": run.relevance.get("terms"),
        "best_score": run.relevance.get("best_score"),
        "min_coverage": run.relevance.get("min_coverage"),
        "relative_margin": run.relevance.get("relative_margin"),
        "floor_tripped": run.relevance.get("floor_tripped"),
        "admitted": [
            {"url": s.url, "title": s.title, "relevance_score": s.relevance_score}
            for s in run.sources
        ],
        "dropped": run.dropped,
        "note": run.relevance.get("note"),
    }


def _margin_probe(goal: str, pages: list[dict[str, Any]], margins: tuple[float, ...]) -> dict[str, Any]:
    """Re-gate the bounded packet at a range of ``RELATIVE_MARGIN`` values.

    The module docstring claims the constant's headroom is small; this records where the tightest
    admission (st.com, the manufacturer note) actually flips, so the claim is measured rather than
    inferred from a rounded ratio. The constant is patched only for the duration of the probe.
    """
    bounded = [
        {"title": page.get("title") or "", "url": page.get("url") or "", "text": (page.get("text") or "")[:BOUND]}
        for page in pages
    ]
    base = relevance.gate_pages(goal, bounded)
    best = base["best_score"]
    tightest = min(
        (row for row in base["verdicts"] if row["verdict"] == relevance.ON_TOPIC),
        key=lambda row: row["score"],
    )  # type: ignore[arg-type]
    exact_ratio = tightest["score"] / best if best else 0.0

    saved = relevance.RELATIVE_MARGIN
    probes: list[dict[str, Any]] = []
    try:
        for margin in margins:
            relevance.RELATIVE_MARGIN = margin
            gate = relevance.gate_pages(goal, bounded)
            row = next(
                item for item in gate["verdicts"] if item["url"] == tightest["url"]
            )
            probes.append(
                {
                    "relative_margin": margin,
                    "relative_line": round(margin * best, 6),
                    "tightest_page_score": row["score"],
                    "tightest_page_verdict": row["verdict"],
                    "kept": len(gate["kept"]),
                    "dropped": len(gate["dropped"]),
                }
            )
    finally:
        relevance.RELATIVE_MARGIN = saved

    return {
        "text": f"content[:{BOUND}]",
        "best_score": best,
        "tightest_admitted_page": {"url": tightest["url"], "title": tightest["title"], "score": tightest["score"]},
        "flip_ratio": exact_ratio,
        "flip_note": (
            "a page is admitted when score >= RELATIVE_MARGIN * best, so this page is refused by any "
            "margin strictly above flip_ratio and admitted at or below it"
        ),
        "probes": probes,
    }


def main() -> None:
    transcript = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
    h40_goal = transcript["scenario"]["goal"]
    h40_pages = [
        {"url": p["url"], "title": p["title"], "text": p["content"]}
        for p in transcript["research"]["pages"]
    ]

    # The fig-tree packet's committed pages are the fixture strings in the gate's own test file:
    # the real fetched bodies were never committed, so these short strings are the whole packet.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cp015g_gate_fixture", ROOT / "tests" / "test_cp015g_relevance_gate.py"
    )
    assert spec and spec.loader
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    fig_goal = fixture.GOAL
    fig_pages = [
        {
            "url": "https://www.rhs.org.uk/fig-pruning/1",
            "title": "Pruning fig trees: a practical guide",
            "text": fixture.ON_TOPIC_BODY,
        }
    ] + [
        {"url": url, "title": title, "text": body}
        for url, (title, body) in fixture.OFF_TOPIC_PAGES.items()
    ]

    h40 = _measure_packet(
        "H-40 soldering_full",
        h40_goal,
        h40_pages,
        notes=[
            "six real fetched pages, verbatim from audit/adversarial/harness-e2e/transcripts/"
            "soldering_full.json",
            "the docstring's '0.38 against a best page at 1.00' is the unbounded column of the "
            "physicslabs.colorado.edu row",
        ],
    )

    fig = _measure_packet(
        "fig-tree prune pass",
        fig_goal,
        fig_pages,
        notes=[
            "the pages the floors were set from are NOT committed as fetched bodies; the packet "
            "committed in tests/test_cp015g_relevance_gate.py is a short reconstruction of three "
            "pages (on-topic RHS page plus the FAO and forestry pages)",
            "every body here is far below the 6000 bound, so the unbounded and bounded columns are "
            "identical by construction and the truncation path is not exercised by this packet",
        ],
    )

    # Control 1: pad the fig-tree bodies past the bound and re-score. Repetition adds no term, so a
    # padding-insensitive result shows the drop is a term-coverage fact, not a length artefact.
    padded_pages = [
        {"url": p["url"], "title": p["title"], "text": (p["text"] + " ") * 40}
        for p in fig_pages
    ]
    fig_padded = _measure_packet(
        "fig-tree prune pass (bodies padded past 6000 — synthetic control)",
        fig_goal,
        padded_pages,
        notes=["synthetic control only: the same three fixture bodies repeated past the bound"],
    )

    # Control 2: inject a known stranger into the bounded H-40 pass and see whether it is refused.
    stranger_pages = copy.deepcopy(h40_pages) + [
        {
            "url": "https://www.fao.org/meat-guidelines",
            "title": "Guidelines for slaughtering, meat cutting and further processing",
            "text": "Slaughtering hygiene, carcass dressing, meat cutting lines and further "
            "processing of animal products under inspection.",
        }
    ]
    h40_stranger = _measure_packet(
        "H-40 soldering_full + one off-topic page (synthetic control)",
        h40_goal,
        stranger_pages,
        notes=[
            "synthetic control only: the fig packet's FAO meat page appended to the H-40 pass, so "
            "the pass contains a page that cannot speak to the goal at either text length"
        ],
    )

    production = {
        "H-40 soldering_full": _production_run(h40_goal, transcript["research"]["pages"]),
        "fig-tree prune pass": _production_run(
            fig_goal,
            [
                {"url": p["url"], "title": p["title"], "content": p["text"]}
                for p in fig_pages
            ],
        ),
    }

    # Where the bounded pass's tightest admission actually flips, with the real gate. The docstring
    # used to round 0.275/0.685 to "0.40" and claim a 0.40 margin would refuse the note; it does not —
    # 0.40 x 0.685 = 0.274, below the note's 0.275. The constant is patched only inside the probe.
    margin_probe = _margin_probe(h40_goal, h40_pages, (0.35, 0.40, 0.4014, 0.40146, 0.41))

    payload = {
        "what": "coursebook.relevance floors measured on unbounded content and on content[:6000]",
        "why": "production scores content[:max_page_chars] (6000); the module docstring quotes "
        "unbounded figures",
        "source_commit": "5b173a86",
        "min_coverage": relevance.MIN_COVERAGE,
        "relative_margin": relevance.RELATIVE_MARGIN,
        "production_bound_chars": BOUND,
        "gate_call": "relevance.gate_pages(goal, [{title, url, text}]) as research.run_research calls it",
        "packets": {
            "H-40 soldering_full": h40,
            "fig-tree prune pass": fig,
            "fig-tree padded control": fig_padded,
            "H-40 plus one off-topic page control": h40_stranger,
        },
        "production_path": production,
        "relative_margin_probe": margin_probe,
    }
    (HERE / "measure.json").write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    for name, packet in payload["packets"].items():
        print("=" * 78)
        print(name)
        for column in ("unbounded", "bounded_6000"):
            dist = packet[column]["distribution"]
            print(
                f"  {column:13s} best={dist['best_score']:.3f} line={dist['relative_line']:.3f} "
                f"kept={dist['kept']} dropped={dist['dropped']} "
                f"abs>={dist['pages_at_or_above_min_coverage']} rel-only={dist['pages_admitted_by_relative_margin_only']} "
                f"below-both={dist['pages_below_both_lines']} terms={dist['goal_terms_matched_by_any_page_count']}/{dist['goal_term_count']}"
            )
        for column in ("unbounded", "bounded_6000"):
            for row in packet[column]["table"]:
                print(
                    f"    {column:13s} {row['score']:.3f} {row['verdict']:9s} "
                    f"kept={row['kept']!s:5s} {row['url'][:78]}"
                )
    print("=" * 78)
    print(json.dumps(production, indent=2)[:4000])
    print("=" * 78)
    print(json.dumps(margin_probe, indent=2))


if __name__ == "__main__":
    main()
