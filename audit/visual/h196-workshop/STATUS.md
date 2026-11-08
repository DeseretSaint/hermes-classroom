# H-196b — Workshop evidence record

Card `t_ec21948a` (H-196b), branch `wt/h196-workshop-evidence`. Evidence only: no product behaviour,
no pack, no review, no merge was changed by this card.

## Base and commit

| what | value |
| --- | --- |
| base | `e3d01f7` — H-196a tip (`wt/t_5ef6be7f`), carried over `ce5014b` / `0e46f38` / `f2c312b` |
| H-196a merged to master? | **no** — master was `179880d` when this card started; the card's fallback ("shoot the green branch") applies and the parent card `t_5ef6be7f` was completed green |
| commit the gates ran on | `9980a5c425c2a15cbf6045d1501d5d9afbd5e3d0` (frames + scripts), then `c3c0839659e64ba08392a2df4c9f961323f81d11` (adds this record; re-run below) |
| module under test | `desktop/plugin.js` sha256 `c8e98f29b6ac2270a379a4bbc2dbd39a798c70189d4e77bb067a7953a99793e0` |

This record is committed as a doc-only commit immediately after `c3c0839`. `git diff --stat
c3c0839..HEAD` shows one file, `audit/visual/h196-workshop/STATUS.md`, so the tree the gates ran on
is the tree in this branch with no code difference.

## Commands, exactly as run

```
python3 scripts/h196-workshop-frames.py
H196_PLUGIN_SHA=$(sha256sum desktop/plugin.js | cut -d' ' -f1) H196_CDP_PORT=9522 \
  node scripts/h196-workshop-shot.mjs
bash scripts/validate-plugin.sh
python3 -m unittest discover -s tests -t .
```

### Gate output on `9980a5c`

```
== 4/4 runtime contracts: PASS ==
Release gate passed: 4/4 checks on 9980a5c425c2a15cbf6045d1501d5d9afbd5e3d0 (2416 files).
```

```
Ran 2459 tests in 416.697s

OK (skipped=1)
```

The frame builder exits 0 with `{"frames": 27, ...}`; the shot script exits 0 with
`{"frames":27,...}` and Chromium `Chrome/155.0.8059.84`.

### Both gates re-run on `c3c0839` (the record commit's parent, same code)

```
== 4/4 runtime contracts: PASS ==
Release gate passed: 4/4 checks on c3c0839659e64ba08392a2df4c9f961323f81d11 (2417 files).
```

```
Ran 2459 tests in 411.367s

OK (skipped=1)
```

The file count differs (2416 → 2417) only because this record file is in `c3c0839`.

## What the captures are

`scripts/h196-workshop-frames.py` calls the shipped Python half on a throwaway migrated profile:
`workshop.catalog_view()` (which re-hashes every bundled pack from disk), the real
`workshop.install()` → `pack.import` gate, the real `library.list` / `pack.list` envelopes, and the
real `media.preview_artifact` route for the cover. `scripts/h196-workshop-render.mjs` mounts the
shipped `desktop/plugin.js` in jsdom (effects and clicks run), replaying those payloads through
`ctx.rest`; `scripts/h196-workshop-shot.mjs` paints the serialised subtree in headless Chromium at
each width, mode, text scale and motion posture, and reads back the painted DOM.

Transport is stubbed. Data, components and interactions are not.

## Frames: 27 on disk

Eighteen PNGs already existed in this directory from `f2c312b`; all eighteen were re-shot on
`e3d01f7`'s module. **Nine are new on this card:** `19`–`27` (Provenance 1049 light and 460 dark,
empty catalogue 1049/460, refused catalogue 1049/460, detail at 200 % text, Library at 200 % text,
Provenance under reduced motion).

CSS width and painted height are the layout box; PNG size is the file on disk (device scale factor
2). "Cover" is the `data-cb-workshop-cover-kind` values in document order.

| frame | CSS box | PNG | root font | motion | mode | cover kinds | painted evidence | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `01-discover-light-1049` | 1049×1944 | 2098×3888 | 16px | full | light | typographic/typographic/typographic/typographic | — | PASS |
| `02-discover-dark-1049` | 1049×1944 | 2098×3888 | 16px | full | dark | typographic/typographic/typographic/typographic | — | PASS |
| `03-discover-light-900` | 900×1978 | 1800×3956 | 16px | full | light | typographic/typographic/typographic/typographic | — | PASS |
| `04-discover-light-460` | 460×2485 | 920×4970 | 16px | full | light | typographic/typographic/typographic/typographic | — | PASS |
| `05-discover-dark-460` | 460×2485 | 920×4970 | 16px | full | dark | typographic/typographic/typographic/typographic | — | PASS |
| `06-discover-200pct-460` | 460×4732 | 920×9464 | 32px | full | light | typographic/typographic/typographic/typographic | — | PASS |
| `07-discover-reduced-motion-1049` | 1049×1944 | 2098×3888 | 16px | reduced | light | typographic/typographic/typographic/typographic | — | PASS |
| `08-discover-installed-light-1049` | 1049×1988 | 2098×3976 | 16px | full | light | artifact/artifact/typographic/typographic | img loaded | PASS |
| `09-detail-light-1049` | 1049×2362 | 2098×4724 | 16px | full | light | artifact | img loaded | PASS |
| `10-detail-dark-900` | 900×2296 | 1800×4592 | 16px | full | dark | artifact | img loaded | PASS |
| `11-detail-light-460` | 460×2600 | 920×5200 | 16px | full | light | artifact | img loaded | PASS |
| `12-no-media-fallback-light-1049` | 1049×1833 | 2098×3666 | 16px | full | light | typographic | — | PASS |
| `13-no-media-fallback-light-460` | 460×2400 | 920×4800 | 16px | full | light | typographic | — | PASS |
| `14-card-opens-detail-1049` | 1049×2380 | 2098×4760 | 16px | full | light | typographic | — | PASS |
| `15-library-light-1049` | 1049×1100 | 2098×2200 | 16px | full | light | — | library:1 | PASS |
| `16-library-dark-460` | 460×1400 | 920×2800 | 16px | full | dark | — | library:1 | PASS |
| `17-library-empty-light-1049` | 1049×900 | 2098×1800 | 16px | full | light | — | empty state text | PASS |
| `18-add-to-library-result-1049` | 1049×2494 | 2098×4988 | 16px | full | light | artifact | img loaded, success notice | PASS |
| `19-provenance-light-1049` | 1049×1000 | 2098×2000 | 16px | full | light | — | ledger:1 | PASS |
| `20-provenance-dark-460` | 460×1500 | 920×3000 | 16px | full | dark | — | ledger:1 | PASS |
| `21-empty-catalogue-light-1049` | 1049×900 | 2098×1800 | 16px | full | light | — | state hook: empty | PASS |
| `22-empty-catalogue-light-460` | 460×900 | 920×1800 | 16px | full | light | — | state hook: empty | PASS |
| `23-error-catalogue-light-1049` | 1049×900 | 2098×1800 | 16px | full | light | — | state hook: error:WORKSHOP_UNAVAILABLE | PASS |
| `24-error-catalogue-dark-460` | 460×900 | 920×1800 | 16px | full | dark | — | state hook: error:WORKSHOP_UNAVAILABLE | PASS |
| `25-detail-200pct-1049` | 1049×4495 | 2098×8990 | 32px | full | light | artifact | img loaded | PASS |
| `26-library-200pct-460` | 460×1800 | 920×3600 | 32px | full | light | — | library:1 | PASS |
| `27-provenance-reduced-motion-1049` | 1049×1000 | 2098×2000 | 16px | reduced | light | — | ledger:1 | PASS |

`evidence.json` carries every measurement above (`frames[]`, plus `plugin_sha256`, `packs`,
`chromium`), produced by the shot run — nothing in this table was typed by hand.

### Invariants across all 27 frames

- `horizontal_overflow` false and `scroll_width == client_width` in every frame (jq count of frames
  that violate either: **0**).
- `empty_alt_images` **0** in every frame; the only `<img>` elements are the real pack schematic
  with the catalogue's full alt sentence, `natural 1080×470`, `loaded true`.
- Currency, rating, learner-count and price sweep over the serialised frames (`\$[0-9]+`,
  `[0-9]+ (learners|students|ratings|reviews)`, `★`, `rating`, `price`, `best ?seller`): **no hits**.
  The only "review" strings are the surface's own negation ("It is not a human review…") and the
  detail fact `Human review → None recorded`.
- One primary action per interactive frame; the state frames (Provenance, empty, refused) have none
  by design — a state is not a call to action and carries no fabricated primary button.

## The storefront, first impression

The two frames the card asks for as the first impression are `01-discover-light-1049` and
`04-discover-light-460` — the shipped Discover surface with the catalogue read from disk, not a
mock:

| frame | CSS viewport | scrollWidth / clientWidth | document height | PNG |
| --- | --- | --- | --- | --- |
| `01-discover-light-1049` | 1049 | 1049 / 1049 | 1944 | 2098×3888 |
| `04-discover-light-460` | 460 | 460 / 460 | 2485 | 920×4970 |

No horizontal overflow at either width, including the 460 frame with the hero plate, the filter row,
the three shelves and every card action.

## Packs actually shown

`evidence.json.packs`, read from the same catalogue the frames rendered (identity, version and
content hash re-derived from each bundled `pack.json` at read time, never from editorial JSON):

| pack_id | version | content_hash (manifest) | cover shown | installed in the frame | `pack.json` sha256 |
| --- | --- | --- | --- | --- | --- |
| `japanese-affection-context-l0` | 2.0.0 | `sha256:ad6f5432ba9873f1cb0e1f0ec2a5e3a87231246c11560937846a73146db51210` | artifact — `content/relationship-map.png` | yes (08, 09–11, 15–16, 18–20, 25–27) | `8e21dd2201d9eebeaab8462c1b0757e809cb327b98e0d2a89dd66744013e8822` |
| `parent-measurement-practice` | 1.0.0 | `sha256:92ee4a79c2ea469c6567ccadbe9fc55290fdd576f28091546372aa87ac36db3d` | typographic (catalogue `cover: null`) | no | `22e65dadcf0a6e686df9e2c0a2bb68910fe8e97b0c289ed9d5e87f08de0036be` |
| `technical-demo-pack` | 1.0.0 | `sha256:603c0b7de57110ff31ec58f8e7d1dab7211c3312e369f880000deac7fda66174` | typographic (catalogue `cover: null`) | no | `b94250cb2c9dbb89b31de36337ce0457f8be8de0211b257b49ad40214dd3411e` |

Editorial catalogue: `catalog/workshop.v1.json`, sha256
`13300bab9dd81b7341e66b2b45184d4733bca94544cb2c4f38288830588039fb`.

## For H-182 (`t_421e0163`) — is the store convincing at first glance?

Honestly: it reads as a **small curated shelf, not a marketplace**, and that is the right first
impression for what the code can prove. At 1049 the first screen is a tab row (Discover / Library /
Provenance), one featured plate with a real pack schematic, a one-sentence outcome ("Choose the
Japanese expression that fits the person you are speaking to, and say why it fits"), a `Validated`
badge immediately followed by the sentence that says what it is not, and two clearly-ranked actions
(Add to library, Read the pack page). Below that a filter row and three shelves labelled Languages /
For parents / Technical, each reading "1 pack". Three packs is thin — a browser expecting a
catalogue will notice the sameness of the shelf size and that two of the three covers are
typographic rather than pictorial — but nothing on the page pretends otherwise: version, level
(CEFR A1 · L0 · ja-JP), duration, locale and the hash-backed trust sentence are on the card, and
there is no price, no rating, no learner count and no review badge to fill the space. The store is
convincing as an inventory of real packs; it is not, and does not claim to be, a place with
selection pressure. The weakest first-glance moment is the two typographic covers sitting under a
pictorial hero — they are deliberate (the packs have no visual) and they look deliberate, not
broken, because they carry category, title and rule rather than an empty image box.

## Limits of this evidence (stated, not hidden)

- **These are renders of the shipped module, not screenshots of the installed app.** The harness
  mounts `WorkshopView` / `WorkshopDetail` inside the route body, so the route's own `h1`
  (`data-cb-page-title`) is outside the captured subtree: `h1_count` is 0 in every frame. No frame
  therefore shows the route display plate, and no frame contradicts the H-196a heading decision.
  Pixels inside a sideloaded Hermes Desktop window are not proven by this record.
- **State frames are state frames.** The build bundles three packs, so an empty catalogue cannot be
  produced by a real read; `catalog_empty` is the real envelope with `items` emptied, and
  `catalog_error` is the shape the route returns when it cannot answer. Both exercise the shipped
  `data-cb-workshop-empty` / `data-cb-workshop-error` branches; neither invents a pack fact.
- **Reduced motion is checked at rest.** `07` and `27` are pixel-identical to their full-motion
  counterparts because the settle has completed by screenshot time; the evidence of the posture is
  `scope_motion: reduced` captured in `evidence.json`, not a difference in the still.
- **A matching hash is integrity, not truth.** The frames repeat the surface's own sentence; no
  native-speaker review, human pack review or rights verdict is claimed here.
