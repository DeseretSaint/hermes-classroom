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

- Provider unavailable: world state `unavailable`, job error `HOST_UNAVAILABLE`, no asset row and
  no placeholder. The course stays readable in Textbook fallback.
- Partial provider failure: the plates that succeeded remain real `world_assets` rows (retry
  reuses them); the world state is `failed`, `error_json.missing_roles` names the exact roles, and
  the job checkpoint carries the same list. Final approval refuses a partial world with
  `POLICY_VIOLATION reason=partial_world`.
- A Textbook course queues no world job at creation
  (`world.world_job_on_create("textbook") is False`): no spend, no assets.
