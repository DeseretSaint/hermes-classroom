# UI program — Coursebook

Director: Opus (default profile). Decisions: `docs/launch/UI-DECISIONS.md`. Board: `coursebook`.
Dispatch and merge: cron supervisor `85d2218453f7` only. New cards are unassigned `todo`.

## Order (one screen at a time; none starts before the previous one is installed)

| # | screen | authority | signature elements |
|---|---|---|---|
| 1 | Home | A1 + `design/home-scene.html` @ `a07b99ea` + generated pack | fox, clock, shelf, planks, tag, four covers |
| 2 | Discover / Workshop | A3 top-right | collectible cards, banner/map, `point` fox |
| 3 | Classroom lesson | A3 bottom-left | lesson furniture, stamp stepper, challenge card, `read` fox |
| 4 | Design System consolidation | A3 bottom-right + A2 | card anatomy, badges, palette, pose map |
| 5 | Course home | `docs/concept-parity/refs/map.png` | map, stops, trail |
| 6 | Parent Studio | system-derived, no frame | composed from the system; never scored as parity |

## Home cards

| card | id | state | scope |
|---|---|---|---|
| CP-053 Home scene | `t_5e22c918` | running (cinder) | the Home card. Not acceptable: 0.8064 (D-003). Let it finish. |
| CP-005f fox adoption | `t_7803e3d1` | blocked (easel) | existing adoption card. Source/registry only: `build_cb_assets.py`, `assets/fox/manifest.json`, `cb-assets.generated.js`, `plugin.js` rebuild, `cb3FoxSource`/`FoxPose` 512/256/128/64 + srcSet, `test_cp010_fox_assets.py`. No `30-home.js`. |
| Type mapping + Home spec + audit | `t_c4bfc678` | todo, unassigned; parent CP-053 | `visual/spec/type-map.json`, `visual/spec/home.json`, `scripts/audit-screen.mjs`, tests. No product source. |
| Home quality pass | `t_831137dd` | todo, unassigned; parents CP-053, `t_7803e3d1`, `t_c4bfc678` | covers, paper/grain, type, shelf, fox/clock composition, tag. The only writer on Home files after CP-053. |

At most two cards in flight; only one touches Home's files. No other screen card is created until
Home is installed.

## Per-screen loop

Gate 1 spec (director) → build card (writer: spec + `audit-screen.mjs` diff + 600×600 crops) →
Gate 2 mechanical audit (1344×768 ±2 px, computed styles, token gates, axe 0 serious/critical, both
fonts) → Gate 3 region critic JSON, then director delta list → at most three fix passes, each naming
its top three deltas → Gate 4 verdict (rubric ≥4 average, character/typography/material each ≥4,
masked SSIM ≥0.85, anti-cheat clean) → land (rebase, full suite, merge, build, install, relaunch,
installed capture vs branch capture, rollback commit named).

## Caps and stops

Per screen: writer $5, critic $1, director $3. Program $60. Two failed passes on one dimension:
rewrite the card once. Third: one Sonnet 5.5 pass. Still short: stop the screen and report. Two
failed character crops: export from the painted master; nobody redraws the fox.

## Report

One report at the end or at a stop rule: screens landed with scores and SSIM, fox hash/source/size
with an A2 crop comparison, gate results, installed capture, ledger, spend, three risks.
