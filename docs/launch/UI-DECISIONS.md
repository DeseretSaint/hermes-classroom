# UI decisions — Coursebook

Director's log. A decision here binds every UI card until the owner overrides it. Each row names
the evidence. References: A1 = `docs/concept-parity/refs/home.png` (sha256 `fd75bed3…`),
A2 = `docs/concept-parity/art/fox-signoff-2up.png` (`549d37b0…`), A3 = `docs/concept-parity/refs/board.png`
(`11387b3f…`). Full hashes: `docs/concept-parity/refs/REFS.md`.

## Gate 0 defaults (adopted 2026-11-11)

| id | decision | evidence / reason |
|---|---|---|
| G0-1 | **Surface.** Parity is scored on the full-window plugin route at 1344×768, which owns the 86 px header band shown in A1. The docked ~560 px pane keeps the compact composition and never imitates host chrome. | A1 draws a header; the docked pane is a different breakpoint (`coursebook-visual-production` §3). |
| G0-2 | **Type.** Reference sizes map onto the six v3 steps; no seventh step, no literal sizes. See D-004 for the resolved px at 1344. | `test_desktop_type_scale` "six steps and no seventh". |
| G0-3 | **Character.** The painted A1 set in `assets/art/fox/` is canonical (owner approval 2026-11-10, `FOX-SIGNOFF.md`). `assets/fox/*.webp` and `assets/masters/fox/*.svg` are the procedural placeholder and cannot pass a Home gate. | `FOX-ASSET-AUDIT.md`. |
| G0-4 | **Assets.** Shipped pack covers, clock and object kit are canonical only where they match the ratified frame; every mismatch is a ledger row. Characters and covers are assets, never drawings. | Handoff §3b. |
| G0-5 | **Data.** The bar under a card title is `sections_done/sections_total`. No ratings, counts or learners. | Handoff §5. |

## Decisions

### D-001 — Home fox pose (owner ruling 2026-11-11)

- **Reference:** A1 shows a **seated** fox with one paw on a separate **brass desk clock**.
- **Approved set:** A2 has only a **standing** `clock` pose holding a **pocket watch**; there is no
  seated clock variant.
- **Options:** (a) accept the approved standing `clock` pose for Home; (b) authorise a separate
  derived-pose art card later.
- **Ruling:** (a), now. No seated pose is invented or derived in this program. Home renders
  `FoxPose pose="clock"` from the painted 256 export at 208 px. Option (b) stays open as a later
  art card; it does not block Home. Ledger row L-04.

### D-002 — the desk clock beside the fox

The object kit's `assets/art/objects/clock.png` (256×256) is a twin-bell alarm clock; A1's is a
round brass desk clock with a top ring and small feet. The shipped clock keeps A1's slot (1042/588,
118 px) because the composition needs the object and no approved brass desk clock exists. No CSS or
hand-drawn substitute. Ledger row L-05. A brass desk-clock plate would be an art card, not a UI fix.

### D-003 — CP-053 is not Home evidence

CP-053 (`t_5e22c918`) is the Home card and is still running, but its frames are not acceptable and
are not evidence for any Home gate:

- `docs/concept-parity/cp053/pass7-shipped.json`: **sim_grey 0.8064** (cards band 0.7623) on
  `home-scene-1344.png`. The latest pass (`home-1344.json`, 00:25) is 0.8089. `PASSES.md`'s 0.8303
  was measured on an earlier render and is stale.
- The latest capture is visibly broken: four letter-plate covers instead of art, flat canvas with
  no grain or vignette, both planks painted as a repeated diagonal hatch with no lip, brackets or
  cast shadow, the procedural placeholder fox, the alarm clock, and a plain ruled box for the tag.

The Home quality card `t_831137dd` (parented to CP-053, `t_7803e3d1` and the type-mapping card
`t_c4bfc678`) owns the fix. No
second Home card exists.

### D-004 — resolved type mapping at the 1344 route

The v3 clamps resolve against the route container (`cqi` = 13.44 px at 1344). The handoff's 36/24
targets assumed static steps; at 1344 the heading step is 32.64 px. Nearest step, no seventh:

| A1 role | A1 px | v3 step | px at 1344 | Δ |
|---|---|---|---|---|
| hero h1 | 72 | display | 64 (ceiling) | −8 (ledger L-03) |
| subline | 32 | heading | 32.64 | +0.6 |
| brand | 34 | heading | 32.64 | −1.4 |
| tag | 23 | lead | 20 | −3 |
| nav, Studio | 17 | body | 16 | −1 |
| button | 16 | body | 16 | 0 |
| card title | 15 | meta | 14 | −1 |
| card meta | — | caption | 12 | — |

If the hero reads weak, adjust measure, leading and tracking within the tokens, never the size.
The type-mapping card turns this table into `visual/spec/type-map.json` and a test.

### D-005 — lane

Writer `deepseek/deepseek-v4.1-flash-1017` (`--provider nous`), vision-native, reviewing 600×600+
crops. Region critic Qwen3-VL-235B or Gemini 3.8 Flash, JSON only. Verifier atlas or cbqa. Fable 5.2
tie-break only. Cards are created unassigned in `todo`; the cron supervisor `85d2218453f7` assigns,
dispatches and merges.

## Divergence ledger

| row | concept | product | reason / evidence |
|---|---|---|---|
| L-01 | star ratings | `sections_done/sections_total` bar | G0-5; no invented data |
| L-02 | painted concept covers with baked, misspelled titles | the course's own text-free cover artifact; titles are DOM | G0-4; `tesseract` must return no words |
| L-03 | 72 px hero | 64 px display ceiling | G0-2, D-004 |
| L-04 | seated fox, paw on clock | approved standing `clock` pose, pocket watch | D-001 |
| L-05 | brass desk clock | object-kit alarm clock | D-002 |
| L-06 | two filled terracotta pills | one filled primary, one quiet secondary | SPEC-V3 D1, one primary per surface |
| L-07 | header in the docked pane | host chrome; compact composition | G0-1 |

### D-006 — display plates and generated Game courses

Owner decision 2026-11-11. Product surfaces use Display Plates, not Press Plate pack covers.
Press Plate remains the pack-management lane only. Display covers are textless, painted, and
mapped to real courses; a pack cover is never a substitute.

Game mode uses the visual kit for the selected grammar. The kit is curated once and can be used
without an image provider; generation adds subject-specific plates when available. A
user-generated Game course uses the same `world_assets`, `world.read`, display cover, and
lesson-scene resolver as a built-in course. There is no branch on course origin and no flat Game
fallback. See `docs/launch/VISUAL-QUALITY-PROGRAM.md` and
`docs/launch/GAME-MODE-VISUAL-KIT.md`; the asset audit is
`docs/launch/VISUAL-ASSET-AUDIT.md`.
