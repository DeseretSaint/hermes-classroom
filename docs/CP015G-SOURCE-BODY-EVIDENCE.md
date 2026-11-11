# CP-015g — source excerpts are page furniture (fixed)

Card: `t_41f23b3e`. Branch: `wt/cp-015g-source-body`, based on `wt/cp-015g-d1-f1-authoring`
(`e728fbe9`). Not pushed.

## The defect

Every source excerpt was the first 600 characters of the host extractor's markdown, and the host
extractor returns the page's navigation before the article. In the CP-015g live run
(`job_c3a5f5ca512a4d518e7b06c924e53eed`, home `~/.hermes/coursebook-test-cp015g-f1`) three of eight
`gen_plan_documents.research_json` excerpts began with a skip link, a subject menu, or a logo:

| source | old excerpt prefix |
| --- | --- |
| ESA — Hello Jupiter! | `[Skip to content](https://www.esa.int/...)` |
| NASA Science — Spot the King of Planets | `Search ## Suggested Searches - [Artemis](...)...` |
| EarthSky — Jupiter's moons | `[![](https://earthsky.org/.../earthskylogo.svg)` |

D1-F1 requires a `sourced` objective to quote verbatim from the cited excerpt, so those sources
could not support a claim at all. The two most authoritative sources in the ledger were unusable.

## The fix

`coursebook/research.py`:

* `_extract_main_body(text, limit) -> (body, excerpt_state, clipped)`. It splits the extract into
  markdown blocks and starts the body at the first block that reads as prose: at least 60
  characters and 8 words, sentence punctuation, link density ≤ 0.35, and no furniture phrase
  (skip link, suggested searches, cookie notice, share rail, survey form, …). Furniture inside the
  body window is dropped. Image alt text is dropped with its image; link targets are dropped and
  labels kept; paired emphasis markers are removed, so the excerpt is the rendered sentence a
  human would quote (`As ESA's Jupiter Icy Moons Explorer (Juice) prepares…`, not a markdown link).
* A page with no prose block records `excerpt_state: "no_body"` and an empty excerpt. The source
  still carries its URL/title/publisher/hash, but offers nothing quotable: `claim_verdict_link_problem`
  refuses every quote against it, and the plan brief carries the state beside the empty excerpt.
* `SourceRecord` gained `excerpt_state` (`recorded` / `no_body`); `__post_init__` refuses an unknown
  value and types an empty `recorded` excerpt as `no_body`.
* The seam is asked for `EXTRACT_WINDOW_CHARS` (40 000) of text *before* extraction, because the
  NASA article starts past the 6 000-character `max_page_chars` bound. Only the extracted body is
  stored and hashed, bounded by `max_page_chars`.
* `_MAX_EXCERPT` 600 → 1200: the claim's sentence is usually 150–250 characters and 600 was often
  one paragraph without it.

`coursebook/generation.py`: `_source_brief` passes `excerpt_state` with the ledger row.

`docs/GENERATION.md`: documents body extraction, the `no_body` state and the 1200-character ceiling.

## Proof

New module `tests/test_cp015g_source_body.py` (8 tests) pins the card's four fixtures:

* a body preceded by more than 1 200 characters of menu yields the body (no chrome in the excerpt);
* the same with a menu longer than the 6 000-character page bound — the seam is recorded as asked
  for 40 000 characters and the body is still found;
* a PDF whose text starts with a document header yields the prose under it;
* a page with no extractable body yields `excerpt_state="no_body"`, an empty excerpt, and no quote
  (chrome or invented body text) can link a claim to it;
* a normal page is unchanged;
* the 1200-character budget keeps the later sentence that states the claim, and a quote of it links;
* `_source_brief` states the absence.

`tests/test_generation.py` updated: the bounded-text test now uses prose (a run of `x` is not a
page), asserts the hash covers the kept body, and a new test covers an all-chrome page.

### Real pages from the live run

Fetched with the host's own `web_extract` (the seam's production adapter) and run through
`_extract_main_body(..., 1200)`:

```
esa            state=recorded chars=1199  As ESA's Jupiter Icy Moons Explorer (Juice) prepares to explore…
nasa           state=recorded chars=1200  Jupiter is our solar system's undisputed king of the planets!…
earthsky       state=recorded chars=1199  All you need is a good pair of binoculars (or a telescope) to see…
cesar_students state=recorded chars=1200  The scientist that first used the telescope and observed the night sky…
weber          state=recorded chars=1200  In this project you'll follow in Galileo's footsteps…
```

All three previously unusable sources now offer real prose; the two already-usable PDFs are
unchanged in substance.

### Suite

`python3 -m unittest` over the 218 test modules in slices (`tests/_run_chunk.py`, a local runner,
not committed):

| slice | tests | result |
| --- | --- | --- |
| 0–30 | 723 | OK (7 skipped) |
| 30–60 | 538 | OK (2 skipped) on re-run; one install-check subprocess flaked 0≠2 on the first run |
| 60–90 | 436 | OK |
| 90–120 | 464 | OK |
| 120–150 | 449 | 3 failures: `test_harness_e2e` packet freshness — fixed by regenerating the packet |
| 150–185 | 527 | 4 failures: `tests.test_platform_binding` `SchemaDrift` — **pre-existing**: reproduces at base `e728fbe9` in a detached worktree |
| 185–218 | 634 | 1 error `test_workshop` `SchemaDrift` (shared on-disk DB, see below); 1 failure `test_vq_capture_harness` clean-tree assertion, which sees this uncommitted diff |

Harness: `PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py` → **3/3 scenarios
PASS**, packet regenerated, `--verify` → **FRESH** (8 evidence files, 3 transcript inputs). The
committed packet changes because the plan/lesson request now carries `excerpt_state` and the
excerpts are body prose.

`test_workshop`'s `SchemaDrift` is an environment artifact of the shared
`plugin-data/coursebook/data.db`: migration 7 was applied by a different checksum before this
worktree ran. It is not touched by this change (no `db.py` or migration edit) and is re-checked
after the commit.
