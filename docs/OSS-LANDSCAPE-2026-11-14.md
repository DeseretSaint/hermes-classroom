# OSS landscape for Coursebook — what to adopt, what to refuse

*Surveyed 2026-11-14. Every licence, star count and push date below was read from the GitHub API in
this session (`gh api repos/OWNER/REPO`), not from memory. Verdicts are adversarial: a library is
recommended only when it removes code we own, and every recommendation carries the argument against
it.*

The question was not "what is popular" but "what can replace something we wrote badly, or prove
something we currently assert". Thirty-eight candidates came back; ten survive. The refusals matter
as much as the adoptions, because most of the popular answers are wrong for a plugin that runs on a
learner's laptop with no server, no telemetry and a 4 MB bundle budget.

## Verdicts

| Verdict | Count | Meaning |
|---|---|---|
| **ADOPT** | 7 | removes code we own, permissive licence, fits an existing seam |
| **PILOT** | 3 | worth a spike behind a flag, not a gate |
| **DEV-ONLY** | 3 | never in the shipped module; may run in the audit harness |
| **REFUSE** | 25 | wrong data, wrong licence, wrong layer, or it duplicates the host |

---

## ADOPT

### 1. `tldextract` — BSD-3, 2,031★, pushed 2026-11-01

**The defect it fixes is a spoofable input.** `_classify_source` (`coursebook/research.py:1569`) tests
`host.endswith('.gov') or '.gov.' in host`. A host like `foo.gov.attacker.example` passes, is labelled
*government*, and ranks first in `SOURCE_TYPE_RANK` (`research.py:136`) — which decides what gets
fetched and quoted.

**Change.** Classify on the registrable domain from the Public Suffix List, not substrings.
**Acceptance.** A test that `https://foo.gov.attacker.example/x` classifies as `web`, and
`https://www.nasa.gov/x` as `government`.
**Against.** Its default config fetches a fresh PSL snapshot over HTTP on first use — pass
`suffix_list_urls=()` so the plugin stays offline-hermetic. It changes stored `source_type` values, so
existing ledgers need re-derivation.

### 2. `json_repair` — MIT, 5,136★, pushed 2026-11-12

`_parse_structured` (`coursebook/generation.py:8755`) falls back to `json.loads` and then dies with
`GenerationRejected`, killing a unit job after earlier sections were already paid for.

**Change.** Repair after the truncation gate has passed, record that a repair happened, then send the
document through the same schema and rule gates.
**Acceptance.** A fixture with a trailing comma parses; a fixture that was cut mid-value is still
refused as truncated, not repaired.
**Against.** The README advertises repairing "truncated values" — calling it before the byte-bound
check would convert a cut answer into a legal-looking one and defeat the truncation lane
(`generation.py:9103`).

### 3. `networkx` — BSD-3, 17,392★, pushed 2026-11-12

Prerequisite edges are authored ordinals (`mastery_path.py:302`, `curriculum.py:528`) and validated
only as "a list of ints" (`mastery_path.py:329`). A cycle or a dangling ordinal is stored, not
refused.

**Change.** Build the unit DAG at plan validation; refuse a cycle, a dangling ordinal, and a
transitive edge that is already implied.
**Acceptance.** A plan with `unit 2 requires 3, unit 3 requires 2` is refused with a typed reason
naming the cycle.
**Against.** It cannot *infer* prerequisites — this makes refusals precise, not the plan smarter. 3.7
declares `requires-python >=3.12,!=3.14.1`; pin accordingly.

### 4. `Pillow` — HPND (GitHub reports NOASSERTION), 13,980★, pushed 2026-11-14

`HostMedia.image` stores provider bytes verbatim (`coursebook/media.py:442`) up to an 8 MiB cap
(`artifacts.py:246`), including EXIF and whatever dimensions the provider returned.

**Change.** Decode, strip metadata, downscale to the role's declared ratio, re-encode; set
`MAX_IMAGE_PIXELS` and a hard byte cap first.
**Acceptance.** A 6000×4000 PNG with EXIF arrives ≤ the pixel floor and with no EXIF keys.
**Against.** Not machine-identified as a permissive licence — confirm the HPND text before shipping.
Re-encoding changes `content_hash`, so the `(content_hash, kind)` dedupe rows
(`artifacts.py:183`) must be re-derived rather than reused.

### 5. `pdfplumber` — MIT, 10,896★, pushed 2026-10-15

Two proofs are asserted, not measured: the print sheet has margins in `@page`
(`desktop/src/95-studio.js:2122`) with no glyph-level check, and syllabus PDFs go through pypdf's
flat `extract_text` (`coursebook/syllabus.py:172`), so a weekly-schedule table arrives as run-on
lines.

**Change.** Assert every glyph sits inside the declared box in `scripts/gm014_print_proof.py`; read
table geometry in the syllabus parser.
**Acceptance.** A print proof whose caption overflows the bottom margin fails with the offending
word's bbox.
**Against.** Two PDF parsers become two attack surfaces for uploaded files; exact pins
(`pdfminer.six==…`, `Pillow>=12.2`) can collide with the host's resolution.

### 6. `axe-core` widening — MPL-2.0, 7,818★, pushed 2026-11-13 (already in the lockfile)

`visual/audit.mjs:259` runs `axe.run('[data-cb-route]')`, so every page-level rule
(`html-has-lang`, `landmark-one-main`, `page-has-heading-one`) is skipped, and the `catch` at `:262`
turns a crashed injection into `{violations: []}` — a green report that measured nothing.

**Change.** Audit the whole document; let a crashed run fail the audit.
**Acceptance.** Deleting `lang` from the fixture makes the audit fail; a throwing injection exits
non-zero.
**Against.** Nothing new is installed — the honest claim is coverage, not capability.

### 7. `colorjs.io` (measured contrast) — MIT, 2,322★, pushed 2026-11-09

`tests/test_desktop_tokens.py:113` computes WCAG contrast by hand from the token table, over hex, not
over what the host paints (alpha, `color-mix`, hover states).

**Change.** A dev-only probe that reads `getComputedStyle` for every token pair and computes WCAG +
APCA with color.js.
**Acceptance.** The probe reports a ratio for a `color-mix` surface that the hex-only gate cannot see.
**Against.** Two contrast implementations can disagree; keep the Python gate as the shipping arbiter
and use color.js only for measured values. APCA stays informational — its constants are a draft.

---

## PILOT (behind a flag, never a gate)

- **`datasketch`** (MIT, 2,981★) — mirror/syndication dedupe. `research.py:1048` dedupes exact URLs
  only, so one article on three mirrors counts as three independent sources. Adds numpy+scipy;
  shingling must be per-locale (character n-grams for Japanese). Store the Jaccard score, never a
  boolean, or genuinely distinct sources silently merge.
- **`model2vec`** (MIT, 2,281★) — paraphrase detection for `_duplicate_performance_reasons`
  (`generation.py:7450`), which today catches only exact or relabelled duplicates. Static embeddings
  are weak on negation: cluster and flag for review, never pass/fail. Model weights download on first
  use — pre-fetch at install or the first lesson stalls offline.
- **`habanero`** (MIT, 254★) — DOI resolution for cited works. A new capability, not a repair: the
  identifier must be carried through `SourceRecord` (`research.py:383`), the contract and the pack
  first. Rate-limited service call; never on the lesson critical path.

## DEV-ONLY

- **`promptfoo`** (MIT, 27,154★) — CI harness for grader/rubric drift. TypeScript 0.x; can never grade
  a live attempt inside the Python backend, and its judges need keys the plugin deliberately does not
  own.
- **`Playwright`** (Apache-2.0, 100,134★) — already used at `visual/audit.mjs:118`. The remaining work
  is retiring 121 raw-CDP scripts, which is a rewrite-risk decision, not a dependency decision. It
  must never enter the shipped module.
- **`pa11y`** (LGPL-3.0, 4,599★) — a second WCAG opinion. LGPL is acceptable for a dev CLI only, it
  downloads a second Chromium, and it audits a re-render rather than the live product.

---

## REFUSE, and why

**Wrong data for this product.** `py-fsrs` and `FSRS-Optimizer` need a four-grade rating and
thousands of reviews; Coursebook records `pass/partial/not_yet/needs_retry` and a 20-objective course
yields dozens of reviews, so 21 weights are unidentified. `pyBKT`, `py-irt` and `pgmpy` need many
subjects per item; one enrollment cannot fit them, and a surfaced probability contradicts
`mastery_path.py:424` ("do not promise mastery percentages"). `tiktoken` counts an OpenAI vocabulary
while the measured route runs near one token per character — using it to size `max_tokens` truncates
in the unsafe direction. `lingua-py` is 170 MB of n-gram models for a flag that can only warn.

**Wrong layer.** `instructor` and `outlines` need a raw provider client or logit access; `ctx.llm` is
the seam and `generation.py:2238` exists precisely to stop a plugin calling a provider directly. The
one real gain — feeding a rejected draft back for repair — is already expressible as a revision
request. `deepeval` and `openevals` pull a test runner or a tracing client (and posthog/langsmith)
into a plugin whose data is a child's; their output shape (`{score, comment}`) does not match
`GradingResult` (`grading.py:62`). `langfuse` is a Postgres/ClickHouse/Redis control plane for a
desktop plugin that already records its own prompt versions and usage, and unredacted learner text in
a trace store is a privacy regression.

**Wrong licence.** `apca-w3` is not open source by any OSI reading — "All Rights Reserved", patents
pending, use restricted to WCAG-conformant content. Compute APCA through color.js instead.
`piper-tts` is GPL-3.0-or-later, which is a distribution decision before it is a technical one, for a
narration lane that already has a working host path. `PyMuPDF` is AGPL and must not appear in
`pdfplumber`'s place.

**Wrong economics.** `trafilatura` and `jusText` duplicate the host `web_extract` tool, and switching
extractor changes `content_hash` (`research.py:1158`) — every stored source hash would change and the
whole ledger would re-fetch. `WeasyPrint` and `Paged.js` are a second print engine that can never be
authoritative over the shipped `win.print()` path; the shipped sheet needs print CSS and the faces we
already ship, not a polyfill. `Style Dictionary` inserts a compiler between the token contract and
the shipped bytes, weakening the byte-equality gate at `tests/test_desktop_tokens.py:184`. `Source
Serif 4` and `IBM Plex Sans` add ~1 MB masters and an inlined subset to a 4.2 MB module for a print
sheet that can use `var(--cb3-font-ui)` for free.

---

## What this changes about the 50

Ten of the upgrade candidates in `docs/UPGRADES-50-2026-11-14.md` are now "adopt X at this seam"
rather than "write this". The rule applied there: if the OSS item removes code we own and its refusal
argument is about configuration rather than capability, it becomes the card; if the argument is about
data, licence or layer, the card stays "write it ourselves, smaller".
