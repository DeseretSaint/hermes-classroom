# UI program — Coursebook

Director: Opus (default profile). Decisions: `docs/launch/UI-DECISIONS.md`. Board: `coursebook`.
Dispatch and merge: cron supervisor `85d2218453f7` only. New cards are unassigned `todo`.

> **Owner decision 2026-11-11.** Product surfaces use Display Plates, not Press Plate pack
> covers. The visual program and the generated-lesson path are in
> `docs/launch/VISUAL-QUALITY-PROGRAM.md` and `docs/launch/GAME-MODE-VISUAL-KIT.md`. The asset
> audit is `docs/launch/VISUAL-ASSET-AUDIT.md`. `design/home-scene.html` is a composition
> reference only, never course truth; its fictional titles and mismatched covers are not evidence.
> The Home quality card `t_831137dd` uses display covers and the 86 px header band. Game-mode
> courses use the same visual kit as built-in courses, including when the user generated the
> lesson.
>
> **Frame tooling 2026-11-13.** `scripts/cb-frame.py` needs the renderer deps in `visual/node_modules`,
> which is gitignored: on a fresh checkout run `cd visual && npm ci` before any frame
> (`python3 scripts/cb-frame.py --preflight` refuses and names that fix if it is missing).

## Order — parallel lanes (amended 2026-11-11, decision D-008)

The serial rule ("one screen at a time; none starts before the previous one is installed") is
retired. It was correct while every screen needed its own bespoke scene design; with
`field_atlas@2` merged it only spends the deadline on app relaunches. The rule that replaces it:

> **One writer per file, not one screen at a time.** `desktop/plugin.js` is generated from
> `desktop/src/NN-*.js`, so screens that own different segment files are parallel-safe; the merge
> is `python3 scripts/build_plugin.py`, not a hunk conflict. Serialize only where two cards write
> the same segment.

| screen | authority | segment files | signature elements |
|---|---|---|---|
| Home | A1 + `design/home-scene.html` @ `a07b99ea` + generated pack | `30-home.js`, `32-desk.js` | fox, clock, shelf, planks, tag, four covers |
| Discover / Workshop / Courses | A3 top-right + `refs/discover.png` | `96-workshop.js`, `40-courses.js`, `20-packs.js` | collectible cards, banner/map, `point` fox |
| Classroom lesson | A3 bottom-left + `refs/classroom.png` | `70-learning.js` | lesson furniture, stamp stepper, challenge card, `read` fox |
| Design System consolidation | A3 bottom-right + A2 | `85-v3-primitives.js`, `76-v3-scope.js` | card anatomy, badges, palette, pose map |
| Course home | `refs/map.png` | `90-course.js`, `30-home.js` (course branch) | map, stops, trail |
| Parent Studio | system-derived, no frame | `95-studio.js`, `62-syllabus-surfaces.js` | composed from the system; never scored as parity |

Shared, single-owner files: `85-v3-primitives.js` and `75-tokens.js` belong to the kernel card
(VQ-003) and the kit-segment card (UI-K1). A screen card consumes their accessors; it does not add
a primitive there. If a screen needs one, it stops and asks the kernel card.

### Lane order

1. **Lane A — kit segment (UI-K1, running).** Adds `cb3KitSource` / `cb3KitCoverFor`. Every screen
   card in every other lane is blocked only on this one file, so it lands first and alone.
2. **Lane B — assets, fully parallel, no product source.** VQ-007 (Discover banner, eight
   collectibles, classroom section plates, course-map base) and VQ-008 (seven remaining grammars)
   both run now. Asset cards are the real Gate 0 constraint; they are disjoint directories and
   must not queue behind a screen.
3. **Lane C — screens, fan out the moment Lane A merges.** Classroom (UI-K3), Workshop/Courses
   (UI-K4), Course home (UI-K5), Parent Studio (UI-K6) start together on disjoint segments.
4. **Lane D — Design System (VQ-003).** Specimen consolidation. It does not gate a screen; it
   records the kernel the screens already use. Run it beside Lane C.
5. **Lane E — Home quality pass.** The only writer on `30-home.js` once CP-053 is in, so it takes
   the Home slot after UI-K1; course-home's `30-home.js` branch waits for it or is split to
   `90-course.js` alone.

A screen card created before its asset exists is a Gate 0 violation; a screen card queued behind a
sibling it shares no file with is a throughput violation. Both are defects.

The parent edge means "it writes my file first", never "it is the next screen".

### One capture per wave

`scripts/vq-capture.sh` walks six destinations × four widths in one rig. It is the wave gate: one
rebuild, one relaunch, one matrix, one contact sheet for every screen that landed in the wave, then
critics score crops in parallel. A per-card capture run is spend with no new evidence; a card whose
only claim is a branch capture has not landed.

## Home cards

| card | id | state | scope |
|---|---|---|---|
| CP-053 Home scene | `t_5e22c918` | done | the Home card. Not acceptable was 0.8064 (D-003). |
| CP-005f fox adoption | `t_7803e3d1` | done | brand-asset segment, `cb3FoxSource`/`FoxPose` 512/256/128/64 + srcSet. No `30-home.js`. |
| Type mapping + Home spec + audit | `t_c4bfc678` | todo, unassigned; parent CP-053 | `visual/spec/type-map.json`, `visual/spec/home.json`, `scripts/audit-screen.mjs`, tests. No product source. |
| Home quality pass | `t_831137dd` | todo, unassigned; parents CP-053, `t_7803e3d1`, `t_c4bfc678`, UI-K1 | covers, paper/grain, type, shelf, fox/clock composition, tag. The only writer on Home files after CP-053. |

Home keeps one writer; the other lanes run beside it. No other screen waits on Home.

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
