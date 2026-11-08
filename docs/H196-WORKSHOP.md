# H-196 — the Workshop destination

Card: H-196 (`t_0a2eb476`), completed as H-196a (`t_5ef6be7f`). Branch `wt/h193-workshop` carried
into `wt/t_5ef6be7f`; the H-196 commits were not rewritten.

| commit | what it holds |
| --- | --- |
| `f2c312b` | the local Workshop storefront, `catalog/workshop.v1.json`, the detail surfaces, `coursebook/workshop.py`, the technical demo pack, the 18-frame evidence set |
| `0e46f38` | checkpoint: state headings as `h2` regions rather than competing display plates; `data-cb-workshop-empty` / `data-cb-workshop-error` hooks |
| this branch's tip | H-196a: the three residual red gates closed, the motion/rule treatment corrected, the M4 evidence re-pinned, and the two provenance documents |

## What the surface is

One top-level destination — **Workshop** — over packs that already exist in this profile:

- **Discover** — a featured plate and shelves, each card one real button plus a separate action;
- **Library** — the packs this profile already holds, with the import flow the destination had;
- **Provenance** — one ledger row per recorded import: version, source, the hash that was verified
  at import, and a re-hash on inspection.

`catalog/workshop.v1.json` is **editorial only**: categories, one outcome sentence, a creator note,
what the course will not teach, a changelog and the cover choice. Identity, version, content hash,
file/structure counts and trust labels are re-derived from each pack's own manifest at read time,
and an entry whose declared `content_hash` differs from the manifest is **refused, never rendered**
(`coursebook/workshop.py`; `tests/test_workshop.py::CatalogueTest::test_a_catalogue_hash_that_drifted_is_refused_not_rendered`).

One write path: `POST /workshop/install` takes a catalogue `pack_id` — never a path — and reuses the
atomic `pack.import` gate, so a second press returns the existing course rather than importing twice.

Trust is stated, not implied. `Validated` means two machine checks passed — every file matches its
manifest hash, and the automated pack checks passed. It is **not** a human review and **not** a claim
that the teaching is right; that sentence is printed on the surface rather than hidden in a tooltip
(`WorkshopTrustNote`).

## The three red gates, closed

### 1. Shadow as depth (H-152)

The card and the hero cover painted `boxShadow` for hover and for the featured plate. The identity
forbids shadow-as-depth, so both were replaced with tokens the identity already has:

- the hero cover plate now carries the **lamp underline** (`borderBottom: 2px solid var(--cb-lamp)`);
  every other cover keeps the hairline `--cb-rule`;
- a card's hover/focus is a **rule change**, not a lift: the side rules take `--cb-ink-soft` and the
  base rule turns to `--cb-lamp`, over `--cb-paper-raised`. No shadow, no translate, no second
  transition source — the mount settle is the only thing that moves.

The cover image also lost its `opacity`/`transition` fade. A decoded image now paints at rest; the
route beat that already frames the plate is not duplicated by a per-image one.

### 2. A second duration source (H-152)

The Workshop called `motion.transition(...)` directly in two places (the cover image and the card
hover), which made four literal call sites where the contract allows two. Both call sites are gone:
the card's motion is the shared `useCbSettle(...)` → `cbSettleFrame(...)` path, and the image no
longer authors a transition at all. `source.count("motion.transition(")` is back to **2**, both
inside the one table's consumers, and `transition: '...'` literals are still only `"none"`.

### 3. Stale M4 evidence

`audit/visual/m4-visual/audit.json` is regenerated last, from the final module, by the script that
produced it — never hand-edited. See the command block below for the pinned module hash.

## The heading decision — a deliberate choice

**A pack title sits at `CB_TYPE.heading`, never at `CB_TYPE.display`.**

The identity permits **one display plate per route**, and on every Workshop route that plate is the
route header's own `h1` (`data-cb-page-title`, `CB_TYPE.display` — "Workshop", "Course", "Home").
A hero or detail title at `display` would therefore be a second display plate competing with the
page title, and the page would have two beginnings.

So the trade-off is taken and recorded:

- the **route header owns `display`**;
- the **storefront/hero/detail pack title owns `heading`** — it is a plate inside the page, not the
  page title;
- the state frames ("The Workshop could not be read", "No packs in this build") are `h2` regions at
  the same `heading` step, not plates.

The decision is written in the code at the place it is made (`desktop/plugin.js`,
`WorkshopCover` → typographic title; `WorkshopHero` and `WorkshopDetail` → their `h2`), and here.
No second display plate was created, and no cover or review was invented to stand in for one.

## Provenance

- [ASSET-PROVENANCE.md](ASSET-PROVENANCE.md) — every asset the surface can show, its producer, its
  licence, whether it is bundled, and its sha256; plus the six sources the Japanese pack cites by
  URL and does not bundle.
- [THIRD-PARTY.md](THIRD-PARTY.md) — **ported patterns: none**, and the honest list of host-provided
  code, the Kokoro-82M model output that produced one audio fixture, and harness-only tools.
- `catalog/workshop.v1.json` is editorial-only and hash-verified (above). Its own sha256 on this
  tip: `13300bab9dd81b7341e66b2b45184d4733bca94544cb2c4f38288830588039fb`.

Nothing in this surface claims a native-speaker review, a human pack review or a rights verdict from
a hash.

## Gates run on the tip

```
node --check desktop/plugin.js                     # parses as ESM
python3 scripts/m4v-audit.py                       # 15 claims PASS; plugin_sha256 c8e98f29…93e0
bash scripts/validate-plugin.sh                    # clean `git archive` export of the commit
python3 -m unittest discover -s tests -t .         # Ran 2459 tests in 503.805s — OK (skipped=1)
```

The three gates that were red are now green individually as well:

```
tests.test_desktop_h152_motion.MotionSourceTest::test_no_keyframes_no_animation_no_shadow_no_gradient  ok
tests.test_desktop_h152_motion.MotionSourceTest::test_one_motion_table_and_one_hook_supply_every_duration  ok
tests.test_m4_visual_audit.VisualMediaAuditTest::test_evidence_is_not_stale_against_the_shipped_module  ok
```

## What this record does not claim

- **No native-speaker review** of the Japanese teaching text or pronunciation exists, and none is
  claimed anywhere on the surface. The narration is synthetic model output.
- **The frames are renders, not the installed app.** `audit/visual/h196-workshop/` mounts the shipped
  module in jsdom with recorded backend payloads, then paints it in headless Chromium; that proves
  the component tree and the painted layout, not the pixels inside a sideloaded Hermes Desktop window.
- **A matching hash is integrity, not truth.** It says the bytes are the bytes the manifest declared.
- **The catalogue is not a marketplace.** No ratings, no learner counts, no prices, no publication
  state — and no review badge standing in for one.
