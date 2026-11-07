# Frequency inventories and vocabulary sequencing (H-89)

Status: implemented on `wt/h89-frequency-inventory`. Owner: Atlas. Contract:
`contracts/frequency-inventory.v1.json` (`cb.frequency_inventory` v1).

## Decision

**Coursebook bundles no third-party frequency list.** A language course may only name
vocabulary from a declared, hash-pinned inventory supplied by the user or a pack, or from the
explicitly synthetic fixture under `tests/fixtures/frequency/`. When no inventory is declared,
the plan still authors from research, but the vocabulary set is labelled unverified, no
`target_items` are allowed, and the result carries the typed reason
`frequency_inventory_unavailable`. The plugin never scrapes, estimates or invents a list, a
rank or a coverage percentage.

Two facts force this decision, and both are verifiable in the tree:

1. **No candidate list can be shipped under acceptable terms.** See the audit below.
2. **This repository carries no outbound licence.** `README.md` says: *"No license file is
   present yet. Do not redistribute this repository until one is added."* Bundling CC BY-SA
   data into an unlicensed repository cannot satisfy the share-alike obligation, so even the
   best open candidate is an import, not a bundled asset.

The user-facing consequence is honest: a Japanese demo proves the *seam* and the sequencing
rules, not the premise that a few hundred words buy a measured share of comprehension. No
learner-facing "you know 80%" claim exists anywhere in this work.

## Source audit (2026-11-07)

| Candidate | Corpus named? | Licence / terms found | Rows usable as-is? | Verdict |
|---|---|---|---|---|
| BCCWJ Word List (NINJAL, CLRD) — <https://clrd.ninjal.ac.jp/bccwj/en/freq-list.html> | Yes: Balanced Corpus of Contemporary Written Japanese (written, 1986–2005 books/magazines/newspapers/blogs) | Site: "free for use for research or educational purposes"; the word-list manual record is licensed **CC BY-NC-SA 3.0**; commercial use is considered case by case; the paid-edition contract forbids providing derivative works to third parties | Yes (UniDic short/long units with lemma, reading, POS) | **Rejected for bundling.** The NC term and the derivative-distribution limit cannot be met by a shippable plugin. A user with their own BCCWJ agreement may import a conforming file. |
| Matsushita, *General Learners' Vocabulary List* (2012, PhD thesis supplementary data) | Yes: derived from BCCWJ | No open licence found; it is BCCWJ-derived supplementary data, so the BCCWJ terms govern | Yes (20,000 ranked words) | **Rejected for bundling.** No licence grants redistribution. |
| `wordfreq` — <https://github.com/rspeer/wordfreq> | Yes, and it lists them: Google Books Ngrams, Leeds Internet Corpus, Wikipedia, ParaCrawl, OPUS OpenSubtitles 2018, SUBTLEX lists | Code Apache-2.0; **data files CC BY-SA 4.0** | No: Japanese tokenization is MeCab + IPADIC but the published API returns surface tokens and frequencies, with **no reading and no part of speech per row**, and the data is a **mixed-modality aggregate** | **Rejected as a bundled primary source.** It cannot fill `reading`/`part_of_speech` without inventing metadata, and its aggregated modality cannot be declared as one corpus. Still importable by a user who produces conforming rows. |
| `hermitdave/FrequencyWords` — <https://github.com/hermitdave/FrequencyWords> | Yes: OpenSubtitles 2016/2018 | Code MIT; **content CC BY-SA 4.0** | No: rows are `surface count` from subtitle text; no lemma, reading or POS, and the Japanese rows are not morphological (UniDic-style) units | **Rejected for bundling.** Share-alike into an unlicensed repo plus missing metadata. |
| JMdict / EDRDG — <https://www.edrdg.org/edrdg/licence.html> | Partly: `nfXX` and `news1/2` come from Alexandre Girardi's *wordfreq* file compiled from the **Mainichi Shimbun** | **CC BY-SA 4.0** (EDRDG general dictionary licence) | Readings and POS yes; frequency no: `nfXX` is a coarse bucket of 500 words, the EDRDG documentation calls the priority markings "only a crude indication", and the source is one newspaper | **Rejected for bundling.** Newspaper-only skew, coarse buckets, share-alike into an unlicensed repo. |

What the plugin therefore does **not** claim:

- that any rank, band or row count measures comprehension;
- that a corpus-specific order transfers to another modality (spoken vs written);
- that the top-N items are content words — the highest-frequency Japanese items are particles,
  copulas and auxiliaries, and H-89 treats them as grammar, not vocabulary cards;
- that kanji frequency is word frequency. It is not, and this contract does not model it.

## Contract: `cb.frequency_inventory` v1

`contracts/frequency-inventory.v1.json` freezes one document shape. It is an inventory, not a
lesson vocabulary list. Required metadata: `language`, `source_id`, `source_url`, `licence`,
`licence_url`, `attribution`, `redistribution`, `modality` (`spoken`/`written`/`mixed`),
`tokenization`, `scope_note`, `published_at`, `fetched_at`, `content_hash`, `bands`, `rows`.
Rows carry `rank`, `lemma`, `reading`, `part_of_speech`, `band`, optional `frequency` and
`notes`.

`content_hash` is `sha256` over the canonical JSON of the `rows` array exactly as shipped
(UTF-8, sorted keys, no insignificant whitespace). The description, `x-frequency-note` and the
required `scope_note` all state the same rule: frequency is corpus- and modality-specific and
is not a comprehension percentage.

Beyond the schema, `coursebook/frequency.py` refuses, as typed reasons:

- non-contiguous or duplicate ranks;
- bands that do not partition ranks `1..N` in order, or a row whose rank sits outside its
  declared band;
- a `content_hash` that no longer matches the rows;
- an inventory whose language does not match the course locale.

`bundle_eligible()` is the licence gate for a future bundled list: `redistribution: allowed`
and a licence in CC0-1.0, public-domain, CC-BY-4.0 or CC-BY-SA-4.0. It is a necessary
condition; the repository still has no outbound licence of its own.

## Brief shape (import seam)

A plan brief may declare:

```json
"frequency_inventory": {
  "path": "inventories/ja-core.json",
  "root": "/home/learner/coursebook-data",
  "band": "band-core"
}
```

or, for packs and tests, an inline `document` with the same shape plus `"band"`. A relative
`path` requires an explicit `root`; there is no implicit search path. `band` is optional only
when the inventory declares exactly one band.

Resolution outcomes are typed:

- course is not a language course → `vocabulary.status = "not_applicable"`;
- no declaration, or the declared file does not exist → `status = "unverified"`,
  `reason = "frequency_inventory_unavailable"`, `items = []`;
- declaration exists but is malformed, mismatched or hash-broken → the job is **rejected**
  with `GenerationRejected("frequency inventory: ...")`. Absence is a warning; a corrupt
  declared artifact is not silently downgraded.

## Planner behaviour

The author and the independent validator both receive the same `vocabulary_inventory` block:
source id, URL, licence, modality, tokenization, content hash, band, the band's `content_items`
in rank order, and its `grammar_items`. The prompt instructs the author to:

- set `target_items` on vocabulary objectives by copying lemmas exactly from `content_items`;
- keep the declared items a **prefix** of that ordered list across objectives — no skipped
  rank, no duplicate, no reordering (utility decides grouping into objectives, not whether a
  rank may be skipped);
- never put a `grammar_items` lemma in `target_items`; particles, copulas, auxiliaries and
  conjunctions are grammar objectives;
- never present a rank or band as a comprehension percentage.

Deterministic checks (`frequency.plan_vocabulary_reasons`) then refuse duplicate items,
out-of-band items, function words used as vocabulary, non-ascending order, a non-prefix set,
and — when a band is declared — a language plan with no vocabulary target at all. They run
before the independent validator on both plan schemas (v1 and v2) and are cheap on purpose:
they prove mechanical properties, not pedagogical quality. The LLM validator is not treated as
a frequency proof.

Existing H-88 rules are untouched and still run first: contiguous unit/objective ordinals,
backward-only prerequisite edges, one check per objective, scope caps, and the curriculum
brief's sequence directives.

## Fixture and evidence

`tests/fixtures/frequency/ja-core-v1.json` and `es-core-v1.json` are **synthetic** inventories:
CC0-1.0, `source_url` on `example.invalid`, `attribution` and `scope_note` stating that no
corpus was consulted and no frequency was measured. The Japanese fixture has 15 rows in two
bands (`band-core` 1–12, `band-extension` 13–15); ranks 1–2 are `は` (particle) and `です`
(copula), so the content list starts at rank 3.

| Fixture | `content_hash` |
|---|---|
| `ja-core-v1.json` | `sha256:956c42bb07ed17493a0b5696d58054f36b3fb668ffdb0d6d9a3a23e2afa3687e` |
| `es-core-v1.json` | `sha256:1569344b30b90f1963b3e53ebfe1fcd6fd8c9ae7bec709f7bfc70bc59bbe58df` |

`tests/test_frequency.py` proves: the fixture satisfies the frozen contract; the hash, rank
contiguity, band partition and language mismatch are enforced; a Japanese plan takes ranks
3–7 into objectives 1–3 in order and the stored plan document carries the same `target_items`;
a missing inventory produces the typed warning, empty items and no fabricated lemmas; a
missing declared file is unavailable, a corrupt one is rejected; Spanish uses the same seam;
duplicate, out-of-band, skipped-rank and function-word plans are parked with the reason; and
H-88's brief and sequence lines still reach the author.

Run it:

```sh
python3 -m unittest tests.test_frequency -v
python3 -m unittest discover -s tests -t .          # full suite
python3 audit/adversarial/harness-e2e/harness_e2e.py # only after a plan-prompt version bump
```

## Not in this card

No desktop UI row for source/licence (H-84/H-86 own the plugin surface; a plan-review row
would be a follow-up card), no automatic crawling, no corpus dump, no adaptive replan, and no
change to H-88's policy or the evidence loop.
