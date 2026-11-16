# Relevance floors, measured on the text production scores

`coursebook/relevance.py` gates the research ledger with two floors — `MIN_COVERAGE = 0.5` and
`RELATIVE_MARGIN = 0.35`. Its docstring quoted figures measured on **unbounded** fetched bodies,
while `research.run_research` scores `content[:max_page_chars]` (`ResearchBudget.max_page_chars`,
default **6000**). This directory is the measurement that says how the same floors behave at the
length production actually feeds them.

Re-derive with:

```
python3 audit/relevance-floors/measure_relevance_floors.py
```

`measure.json` is the committed artifact; it is written by that script and carries every page, both
scores, the verdict, the kept/dropped flag and the reason string, plus a per-pass distribution.

## Packets

| packet | source | pages |
| --- | --- | --- |
| H-40 soldering pass | `audit/adversarial/harness-e2e/transcripts/soldering_full.json` (real fetched bodies) | 6 |
| fig-tree pass | the short reconstruction in `tests/test_cp015g_relevance_gate.py` (the fetched bodies were never committed) | 3 |

## H-40 soldering pass — goal "prepare for a first soldering repair on a through-hole PCB: …"

Full fetched body (unbounded):

| page | score | of best | verdict |
| --- | --- | --- | --- |
| st.com THD mounting note (39,670 chars) | 1.000 | 1.00 | on_topic, kept |
| ifixit "Soldering Simplified" | 0.889 | 0.89 | on_topic, kept |
| Purdue ECE 477 lecture | 0.714 | 0.71 | on_topic, kept |
| ifixit glossary | 0.696 | 0.70 | on_topic, kept |
| instructables | 0.522 | 0.52 | on_topic, kept |
| CU Boulder soldering resources (2,981 chars) | 0.382 | 0.38 | on_topic, kept (relative half) |

best 1.000, relative line 0.350, 0 dropped.

`content[:6000]` — what production scores:

| page | score | of best | verdict |
| --- | --- | --- | --- |
| Purdue ECE 477 lecture | 0.685 | 1.00 | on_topic, kept (absolute) |
| ifixit glossary | 0.588 | 0.86 | on_topic, kept (absolute) |
| ifixit "Soldering Simplified" | 0.545 | 0.80 | on_topic, kept (absolute) |
| instructables | 0.453 | 0.66 | on_topic, kept (relative half) |
| CU Boulder soldering resources | 0.353 | 0.52 | on_topic, kept (relative half) |
| st.com THD mounting note | 0.275 | **0.40** | on_topic, kept (relative half) |

best 0.685, relative line 0.240, 0 dropped. Distribution: 3 pages clear `MIN_COVERAGE` on their own,
3 more sit between the relative line and `MIN_COVERAGE` (0.240–0.500), 0 below both. All 13 goal terms
survive tokenisation and are matched by at least one page at both lengths.

## fig-tree pass — goal "prune a fig tree"

| page | score | of best | verdict |
| --- | --- | --- | --- |
| RHS fig-pruning guide (250 chars) | 1.000 | 1.00 | on_topic, kept |
| forestry tree-identification (109 chars) | 0.276 | 0.28 | off_topic, dropped |
| FAO meat guidelines (118 chars) | 0.000 | 0.00 | off_topic, dropped |

best 1.000, relative line 0.350. **The two columns are identical**: every body is far under 6000, so
truncation never applies to this packet. The two off-topic pages are refused because a short body
uses one goal term (forestry: `tree` of `prun`/`fig`/`tree`) or none, not because a long body was cut.

## Controls (synthetic, labelled)

| control | finding |
| --- | --- |
| fig-tree bodies padded past 6000 (`(body + " ") * 40`) | scores unchanged (1.000 / 0.276 / 0.000) — padding adds no term, so the drop is term coverage, not length |
| FAO meat page appended to the bounded H-40 pass | scores 0.092 against a 0.240 relative line and is **dropped**: the gate does refuse a stranger at 6000 chars |

## What this says about the floors

* Both floors discriminate on bounded text where there is something to refuse: the forestry page
  (0.276 vs 0.350) and the injected stranger (0.092 vs 0.240) both fall below both lines at 6000.
* "Nothing dropped" on the recorded H-40 pass is not inertness — that pass carried six genuine
  pages and no stranger, at either length.
* The constant's real headroom is on **bounded** text: st.com is admitted at 0.40 of the best page,
  ~0.05 above `RELATIVE_MARGIN`. Raising the margin to 0.40 would refuse a manufacturer's own
  through-hole mounting note at 6000 chars. Lowering it is not needed by these packets.
* Unmeasured, and unmeasurable from what is committed: how a *long* real forestry-style page would
  score at 6000 (its body was never committed), and per-page term survival for a packet whose pages
  all exceed the bound in a way that removes a goal term — none of these pages lose a term to the cut.
