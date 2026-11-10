# GM-003 — world generation cost and latency note

Scope: `visual.world.generate` (`kind=media`, `brief.stage=world_concepts|world_kit`). This note
records the **call accounting** the code enforces and a labelled latency/price estimate. No
provider key, account id or secret appears here, and no live provider call was made to produce
this card's evidence.

## Calls per world

The backend enforces the budget (`coursebook/world.py`: `MAX_CONCEPTS`, `MAX_KIT_SECTIONS`,
`world` role limits in `coursebook/gm_contract.py`):

| Stage | Plates | Provider calls (cold cache) | Provider calls (warm cache) |
|---|---|---|---|
| `world_concepts` | 3 style boards | 3 | 0 |
| `world_kit` | 1 hero + 1 cover + 1 per section (≤ 6) | 2 + sections | 0 for plates already cached |
| Retry of a failed kit | only the missing roles | `missing count` | 0 for the surviving roles |

A retry never pays twice for the same `style_hash + course_hash + role + section_id + prompt
version`: the cache key is `world.cache_key(...)` stored as `artifacts.provenance.spec_hash`, and
`ArtifactStore.lookup(kind="visual", spec_fingerprint=key)` runs before any provider call.

Measured in `tests.test_world.WorldMediaJobTest.test_world_cache_prevents_duplicate_spend`
with a provider-shaped fake that counts calls:

- first `stage=concepts`: **3 calls**, 3 concept boards, 3 distinct `style_hash` values;
- second identical `stage=concepts`: **0 additional calls** (3 total after two jobs);
- a 2-section kit: **4 calls** (hero, cover, section `s1`, section `s2`); a 1-section kit: 3.

## Latency and price (estimate, not a measurement)

The host owns the provider (`media.HostMedia.image` → `ctx.dispatch_tool("image_generate")`). The
plugin does not see a price list, so the numbers below are an **operator estimate** to be replaced
by `usage_events` once a live Game course is generated:

| Quantity | Assumption | 3 boards + 2-section kit |
|---|---|---|
| Wall clock per plate | 8–20 s (typical hosted image model) | 32–80 s (4 plates, sequential) |
| Price per plate | $0.02–$0.06 | $0.08–$0.24 |
| Identical retry | 0 provider calls | $0.00 |

These are deliberately ranges; a single hard-coded price would be a fabricated fact. `usage_events`
records the real `duration_ms`, provider and `artifact_count` for every call the job makes, so the
first live run replaces this table with measured values.

## Failure honesty

- Provider unavailable at any stage: world state `unavailable` or `failed`, job error
  `HOST_UNAVAILABLE`, no asset row and no placeholder. The course stays readable in Textbook
  fallback.
- Concept-stage provider failure (all three boards refused): the world is terminal `failed` with
  `error_json = {'reason': 'provider_unavailable', 'missing_roles': ['style_board:<direction>', …]}`,
  `concepts` holds only the boards that really succeeded, and the job re-raises the provider
  failure. No concept is fabricated and no asset row is written for a refused plate.
- Partial provider failure: the plates that succeeded remain real `world_assets` rows (retry
  reuses them); the world state is `failed`, `error_json.missing_roles` names the exact roles, and
  the job checkpoint carries the same list. Final approval refuses a partial world with
  `POLICY_VIOLATION reason=partial_world`.
- A Textbook course queues no world job at creation
  (`world.world_job_on_create("textbook") is False`): no spend, no assets.

## Round-6 content fence cost

Round 6 extends the same pure local validation to the two free-text paths that reach a plate
prompt: caller `brief_patch.motifs`, and derived objective titles promoted into motifs. A caller
motif that names a number, unit, part number or answer instruction is refused before any world
row, job or provider call (**0** image calls). A derived course title/goal is not refused: the
prompt substitutes the grammar label and omits the capability clause, so a successful request
still costs exactly the 3 boards + kit in the table above, with no extra model call.

A bare-string `forbidden` patch is a `VALIDATION_FAILED` before spend; it is no longer exploded
per character into eleven nonsense negatives.

## Round-7 content fence cost

Round 7 closes the same rule for procedure phrasing and spelled-out values, and for course text
that reaches a prompt outside `brief_patch`: a caller motif such as `remove the intake manifold`
or `tighten to seventy five` is refused before any world row, job or provider call (**0** image
calls). Section titles and course `title`/`goal` are never a reason to refuse the course:

- an unsafe section title is dropped from the plate prompt (the UI supplies the real typed
  title), and
- an unsafe or foreign-scene course subject/capability falls back to the grammar label/clause.

Both are prompt-local sanitisation, so a successful request still costs exactly the 3 boards +
kit in the table above, with **0** extra model calls. The scans are pure local token checks; no
provider round-trip is added on either the accept or the refuse path.

## Round-8 class fence cost

Round 8 replaces the per-field checks with one predicate (`_plate_text_problems`) applied at every
interpolation site (subject, capability, motif, tone, audience, section title, forbidden). It
adds **0** model calls on either path: a hostile value is substituted or dropped while building
the prompt string, and a caller patch that fails the same predicate is refused before any world
row, job or provider call. The cost of a successful request is unchanged (3 boards + kit), and
the stored brief/cache key are untouched, so no new spend identity is created.


## Round-9 hyphen fence cost

Round 9 narrows the `four-cylinder` carve-out so hyphenation cannot shelter a value or a sequence
step (`spec is seventy-five`, `hand tight plus a quarter-turn`, a course titled `Seventy-five`).
The check is the same local predicate, re-run over hyphen-aware units; it adds **0** model calls
on the accept path and refuses a hostile caller patch before any world row, job or provider call
(**0** image calls). Function words in `tone`/`audience` (`calm and precise`) are now neutral, so a
legal mood patch still costs exactly the 3 boards + kit from the table above. No cache-key or
`prompt_hash` change: the fence remains prompt-local.

## Round-10 leading-word / fraction fence cost

Round 10 skips leading discourse words before the procedure-verb test, extends the imperative verb
set, and singularises hyphenated fraction tails. The check is the same local predicate, so it adds
**0** model calls on the accept path and refuses a hostile caller patch before any world row, job
or provider call (**0** image calls). Legal patches (`four-cylinder block`, `car on a lift`) still
cost exactly the 3 boards + kit from the table above. No cache-key or `prompt_hash` change: the
fence remains prompt-local.

## Round-11 frozen-verb fence cost

Round 11 completes the procedure vocabulary: `disconnect` joins the unambiguous set and
`clean`/`break`/`polish`/`refill` are refused when they take an object — verb-initial with a bare
object or anywhere with a determiner (round 12 corrected the round-11 implementation, which
required a determiner) — so a caller motif such as `Clean the head` or `Clean head` is refused
before any world row, job or provider call (**0** image calls) while the native scene
`clean service bay` still succeeds at exactly the 3 boards + kit cost. A course titled `Clean
head` is not refused: the prompt falls back to the grammar label and omits the unsafe capability
clause, so it costs the same 3 boards + kit with **0** extra model calls. No cache-key or
`prompt_hash` change.

## Round-12 bare-object fence cost

Round 12 closes the imperative *shape*: a determiner-only scene verb that opens the phrase takes a
bare object (`Clean head`, `Refill coolant`, `Polish lens`, `Break seal`, `Then clean head`) and is
refused before any world row, job or provider call (**0** image calls), unless the phrase names a
selected-grammar scene cue (`clean service bay`). The check is the same local predicate — no extra
model call on the accept path — and it is shared by the patch refusal and every prompt
interpolation site, so a title-only or goal-only leak costs 3 boards with **0** extra model calls
(the prompt falls back / omits; the stored brief stays verbatim). No cache-key or `prompt_hash`
change: the fence remains prompt-local.
