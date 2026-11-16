"""Deterministic relevance gating for the research ledger.

``PREBUILD_SPEC.md`` §9 and ``AUDIT.md`` R6/R7: the plan author is handed the research digest and
may cite only what the ledger carries, so the digest is a *selection*, not a transcript of whatever
a search provider returned. A measured real-provider pass for "prune a fig tree" fetched seven
pages, two of them unrelated to the goal (an FAO meat-processing page and a forestry tree-
identification page). Both happened to bind zero claims, so the plan was honest — but the guard was
luck, not a rule: had the author quoted either page, an objective's evidence criteria would have
rested on text about slaughtering.

This module is the rule. It scores every fetched page against the goal's own content words and
gives an explicit verdict:

* the goal is reduced to its content words (function words removed, a light suffix stem, a
  four-character comparison key so ``prune``/``pruning``/``pruned`` are one term);
* each term is weighted by how rare it is *inside this pass's fetched pages* (inverse document
  frequency). No model call, no topic lexicon, no per-subject table: an unseen topic is scored by
  the same arithmetic as a known one;
* a page's score is the weighted share of the goal's terms it actually uses, in title, URL or
  fetched text;
* a page is ``off_topic`` when it both falls below :data:`MIN_COVERAGE` *and* reaches less than
  :data:`RELATIVE_MARGIN` of the best page this pass fetched. Both halves are needed: a long,
  compound goal ("prepare for a first soldering repair …: safety, component placement, joints,
  inspection and desoldering") names more terms than any one good page covers, so an honest
  soldering resource scored 0.382 against a best page of 1.000 **on the full fetched bodies** —
  an absolute floor alone called that expert resource off-topic. A page the pass itself shows to be
  far less relevant than what it already found is the defensible refusal.

Measured floors, by text length
-------------------------------
Every figure in this section except the stranger control was measured twice on the committed packets:
once on the **full fetched body** and once on ``content[:6000]`` — the slice
``research.run_research`` actually scores
(``ResearchBudget.max_page_chars``, default 6000). Evidence:
``audit/relevance-floors/measure.json``, re-derivable with
``audit/relevance-floors/measure_relevance_floors.py``. Same verdicts at both lengths on both
packets; the arithmetic moves, because five of the soldering packet's six bodies are longer than
the bound.

* **H-40 soldering pass** (``audit/adversarial/harness-e2e/transcripts/soldering_full.json``; goal
  "prepare for a first soldering repair on a through-hole PCB: safety, component placement, joints,
  inspection and desoldering"; six pages, every one genuine):

  - full body: best 1.000 (st.com THD mounting note), CU Boulder soldering resources 0.382
    (0.38 of the best), the other four 0.522–0.889. Nothing dropped.
  - ``content[:6000]``: best 0.685 (Purdue ECE 477 lecture), CU Boulder 0.353 (0.52 of the best),
    st.com 0.275 (0.40146 of the best — the tightest admission), the other three 0.453–0.588.
    Nothing dropped either, and only three of six clear :data:`MIN_COVERAGE` on their own — the
    other three are admitted by the relative half, so the headroom this constant relies on is
    *bounded-text* headroom: 0.40146 is only ~0.05 above :data:`RELATIVE_MARGIN`. Measured with the
    real gate, a margin of 0.40 still admits that manufacturer's own through-hole note (line 0.274,
    score 0.275, kept 6). The flip ratio is ``0.275 / 0.685 = 0.40146``; the probe's ``0.40146``
    row already refuses it (line 0.275, kept 5, dropped 1), as does 0.41.

* **Fig-tree pass** ("prune a fig tree"; the RHS on-topic page plus the FAO meat page and a forestry
  tree-identification page): best 1.000, forestry 0.276 (one of three goal terms — ``tree``), FAO
  0.000; both off-topic pages refused at *both* lengths. Every body in this packet is under 300
  characters, so the two columns are identical and the packet does not exercise truncation at all:
  its off-topic pages drop because a short body uses one goal term, not because a long body was cut.
  The committed fig-tree packet is a short reconstruction of the three pages — the fetched bodies
  were never committed — so how a long real forestry page would score is unmeasured here.

* **A stranger inside a bounded pass** (*synthetic* — a constructed pass, not a recorded one):
  appending the FAO meat page from the fig pass to the H-40 pages and scoring
  ``content[:6000]`` gives it 0.092 against a 0.240 relative line, and it is dropped. The gate does
  refuse a stranger at 6000 chars; the recorded soldering pass simply carried none to refuse.

Two honest escapes:

* a goal with no content word (or a single letter, or only punctuation) cannot be scored, so every
  page is admitted and the verdict says the goal carried nothing to judge by;
* when *no* page scores above zero the profile itself is untrustworthy — a vague goal, a provider
  that returned nothing usable — so the whole pass is kept and the gate reports ``floor_tripped``
  instead of emptying a ledger it cannot justify emptying.

Scoring never upgrades support. A kept page still starts ``unverified``; only an independent
validator that quotes the fetched text moves it (``research.apply_support_verdicts``).
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Sequence

__all__ = [
    "ON_TOPIC",
    "OFF_TOPIC",
    "MIN_COVERAGE",
    "RELATIVE_MARGIN",
    "goal_terms",
    "score_page",
    "gate_pages",
]

ON_TOPIC = "on_topic"
OFF_TOPIC = "off_topic"

#: The weighted share of the goal's own terms a page must use to enter the plan digest on its own
#: merits. Half is the rule of thumb the measured pass supports: the two on-topic fig pages used the
#: goal's terms; the tree-identification page used one of three (``tree``) and the meat page used
#: none — the same at full body length and at ``content[:6000]``, because those bodies are short.
#: On the bounded soldering pass only three of six genuine pages clear it on their own, which is
#: what the relative half below is for.
MIN_COVERAGE = 0.5

#: The second half of the refusal: a page below :data:`MIN_COVERAGE` is still admitted when it
#: reaches this share of the best page in the same pass. A compound goal names more terms than one
#: honest page covers, so "a manufacturer note at 0.275 against a 0.685 best" is a resource, not a
#: stranger. Measured on the committed fig-tree packet — a short reconstruction whose bodies are all
#: under 300 chars, so full body and ``content[:6000]`` are the same — the forestry page sits at 0.28
#: of its best page; measured on the H-40 soldering pass's full fetched bodies, a genuine CU Boulder
#: soldering resource is 0.38 of 1.00;
#: measured on ``content[:6000]``, the same CU Boulder page is 0.35 against 0.69 (0.52 of the best)
#: and the manufacturer note is 0.275 against 0.685 — 0.40146 of the best. So 0.35 holds at both
#: lengths, and the bounded headroom is only ~0.05: patching this constant to 0.40 still admits the
#: note (line 0.274, score 0.275), and only a margin above the flip ratio 0.40146 refuses it (the
#: probe's 0.40146 row and 0.41 both do). The line sits at 0.35.
RELATIVE_MARGIN = 0.35

#: Function words carry no subject. Deliberately a closed, short list: it removes the words that
#: appear in *every* goal ("a", "how", "the", "in") and nothing else. A word not on it is scored,
#: including a common verb — the IDF weight, not a hand-written list, decides how much it counts.
_STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those there here it its it's of for from to
    in on at by with without into onto over under about as is are was were be been being am do does
    did doing done have has had having i me my we our you your he she they them their his her him
    not no nor so such very too also just only own same other more most much many few some any all
    each every both either neither one two how what when where which who whom why can could should
    would will shall may might must need needs needed want wants wanted like get gets got make makes
    made use uses used using into per via vs etc please
    """.split()
)

#: A word is a run of letters/digits. Hyphens split the compound (``open-crumb`` → two words), which
#: keeps "crumb" available to the scorer instead of hiding it inside one opaque token.
_WORD = re.compile(r"[a-z0-9]+")

#: Keys shorter than this are compared exactly, never by prefix: a three-letter prefix ("fig")
#: would match "fight", "figure" and "figment", which are different subjects.
_KEY_PREFIX = 4


def _stem(word: str) -> str:
    """A light, deterministic suffix stem. Not linguistics — just enough to compare one word."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed"):
        if len(word) >= len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    if len(word) >= 5 and word.endswith("es"):
        return word[:-2]
    if len(word) >= 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _key(word: str) -> str:
    """The comparison key for one content word: a stem, then its four-character prefix."""
    stem = _stem(word)
    return stem[:_KEY_PREFIX] if len(stem) >= _KEY_PREFIX else stem


def goal_terms(goal: Any) -> list[str]:
    """The goal's ordered, de-duplicated content keys. An unscoreable goal yields ``[]``."""
    terms: list[str] = []
    seen: set[str] = set()
    for word in _WORD.findall(str(goal or "").casefold()):
        if len(word) < 3 or word in _STOPWORDS:
            continue
        key = _key(word)
        if not key or key in seen:
            continue
        seen.add(key)
        terms.append(key)
    return terms


def _page_keys(texts: Iterable[Any]) -> set[str]:
    keys: set[str] = set()
    for text in texts:
        for word in _WORD.findall(str(text or "").casefold()):
            if len(word) < 3 or word in _STOPWORDS:
                continue
            key = _key(word)
            if key:
                keys.add(key)
    return keys


def _weights(terms: Sequence[str], pages: Sequence[set[str]]) -> dict[str, float]:
    """Inverse-document-frequency weight per goal term, over this pass's own fetched pages.

    A term nearly every page uses (a word like "guide") is worth little; a term only the on-topic
    page uses is worth a lot. ``1 + log((N+1)/(df+1))`` keeps every weight >= 1 so a page that
    matches nothing still scores exactly 0, and a term no page matched keeps its full weight — a
    goal term the pass never saw is a reason to doubt the page, not a free pass.
    """
    total = max(1, len(pages))
    weights: dict[str, float] = {}
    for term in terms:
        df = sum(1 for keys in pages if term in keys)
        weights[term] = 1.0 + math.log((total + 1) / (df + 1))
    return weights


def _reason(
    verdict: str,
    matched: Sequence[str],
    terms: Sequence[str],
    score: float,
    best: float,
) -> str:
    if not terms:
        return "the goal carries no content word to score against, so the page is admitted unscored"
    use = (
        f"uses {len(matched)} of the goal's {len(terms)} content terms"
        f" ({', '.join(matched) or 'none'}); weighted coverage {score:.2f}"
    )
    if verdict == ON_TOPIC and score >= MIN_COVERAGE:
        return f"{use} meets the {MIN_COVERAGE:.2f} floor"
    if verdict == ON_TOPIC:
        return (
            f"{use} is below the {MIN_COVERAGE:.2f} floor but reaches"
            f" {RELATIVE_MARGIN:.2f} of this pass's best page ({best:.2f}), so it is admitted"
        )
    return (
        f"{use} is below the {MIN_COVERAGE:.2f} floor and below {RELATIVE_MARGIN:.2f} of this"
        f" pass's best page ({best:.2f})"
    )


def score_page(goal: Any, *, title: Any = "", url: Any = "", text: Any = "") -> dict[str, Any]:
    """One page's relevance to the goal, with the terms it matched. Deterministic, no I/O.

    The same arithmetic :func:`gate_pages` uses, over a single page. It exists for callers that
    need the verdict for one page (a probe, a test, a re-check) without a candidate set.
    """
    result = gate_pages(goal, [{"title": title, "url": url, "text": text}])
    entry = dict(result["verdicts"][0])
    entry.pop("index", None)
    return entry


def gate_pages(
    goal: Any,
    pages: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Score every fetched page and decide which enter the digest.

    ``pages`` is one dict per fetched page with ``title``, ``url`` and ``text`` (the fetched body).
    The return value is the ledger record the caller persists:

    * ``verdicts`` — one entry per input page, in input order: ``verdict``, ``score``, ``matched``
      and ``reason``, plus the page's own ``title``/``url`` so a reader can identify it;
    * ``terms``, ``min_coverage`` and ``best_score`` — what the gate scored against, so the loss is
      reproducible;
    * ``floor_tripped`` — true when no page matched any goal term and the pass was kept whole;
    * ``kept``/``dropped`` — indices into ``verdicts``.
    """
    terms = goal_terms(goal)
    keyed = [_page_keys((page.get("title"), page.get("url"), page.get("text"))) for page in pages]
    weights = _weights(terms, keyed)
    total_weight = sum(weights.values())

    scores: list[float] = []
    matched_by_page: list[list[str]] = []
    for keys in keyed:
        matched = [term for term in terms if term in keys]
        matched_by_page.append(matched)
        if terms:
            matched_weight = sum(weights[term] for term in matched)
            scores.append(round(matched_weight / total_weight, 3) if total_weight else 0.0)
        else:
            scores.append(1.0)
    best = max(scores) if scores else 0.0

    verdicts: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        matched = matched_by_page[index]
        score = scores[index]
        relative = bool(terms) and best > 0 and score >= RELATIVE_MARGIN * best
        verdict = ON_TOPIC if (not terms or score >= MIN_COVERAGE or relative) else OFF_TOPIC
        verdicts.append(
            {
                "index": index,
                "url": str(page.get("url") or ""),
                "title": str(page.get("title") or ""),
                "verdict": verdict,
                "score": score,
                "matched": matched,
                "reason": _reason(verdict, matched, terms, score, best),
            }
        )

    kept = [item["index"] for item in verdicts if item["verdict"] == ON_TOPIC]
    dropped = [item["index"] for item in verdicts if item["verdict"] == OFF_TOPIC]
    floor_tripped = False
    if terms and verdicts and not kept:
        # No page used a single goal term: the profile, not the pages, is what cannot be trusted.
        # Keep the pass whole and say so; an empty digest would be a silent loss of every source
        # the job actually paid for.
        floor_tripped = True
        for item in verdicts:
            item["verdict"] = ON_TOPIC
            item["reason"] = (
                "no page used any of the goal's content terms, so this pass is kept whole"
                f" rather than emptied (best score {best:.2f})"
            )
        kept = [item["index"] for item in verdicts]
        dropped = []

    return {
        "terms": terms,
        "min_coverage": MIN_COVERAGE,
        "relative_margin": RELATIVE_MARGIN,
        "best_score": best,
        "floor_tripped": floor_tripped,
        "verdicts": verdicts,
        "kept": kept,
        "dropped": dropped,
    }
