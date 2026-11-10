# Coursebook concept parity: delegation plan for the Coursebook bots

Status: approved and executing from 2026-11-10 03:05 MST. The owner accepted the recommended answer
to every decision (D1 to D10) and asked for the cards to be built and run. This file is committed
to the repo as `docs/concept-parity/PLAN.md`, which is the copy every worktree can read.
Date: 2026-11-10 01:50 MST. Submission deadline: 2026-11-11 17:00 EST (15:00 MST), about 37 h away.
Base: `origin/master` `00751f0` (cb.rpc v24; GM-006 merged). The installed Desktop module
(`~/.hermes/desktop-plugins/coursebook/plugin.js`) has the same sha256 as master (`7802e3ca...`).
Board at 01:48: done 429; running 2 (GM-010 `t_ebf058fa` in review by quill; GM-020 `t_ff09c89e`,
vellum, repairing three guard failures GM-008 introduced); todo 4 (GM-012, GM-015, GM-016, GM-017);
blocked 2 (licence, CB-017 demo gate). GM-008 is done on the board but not merged: its merge gate
went red (`Ran 3005 tests ... failures=3`), and GM-020 carries the fix with the GM-010 merge.

## 0. Goal and quality bar

Make the shipped Coursebook route look like the owner-ratified concept images, or better, while
everything on screen is real: real DOM text, real course state, real evidence, accessible.

"Better than the concept" has a precise meaning here. The concepts are AI stills with garbled
labels, fake stars, invented XP, a misaligned grid, a dead rail and a cropped fox. The product must
match their material quality (paper, light, illustration, type, collectible objects, fox) and beat
them on legibility, truth, alignment, state coverage, responsiveness and motion.

## 1. Reference pack (the spec inputs)

| Id | File | sha256 prefix | Size | Role |
|---|---|---|---|---|
| R-HOME | `native-inputs/fd75bed3.../dashboard_20261109_231118_016672b2_*.png` | fd75bed31cd773ab | 1344x768 | Home: "Your field library", shelf, fox with clock |
| R-BOARD | `native-inputs/11387b3f.../dashboard_20261109_231118_a1363800_image.png` | 11387b3fe89bb9b1 | 2400x1700 | four-panel board; identical to `~/Pictures/coursebook-direction-a/coursebook-refined-contact-sheet.png` |
| R-DISC | `~/Pictures/coursebook-direction-a/refined-discover.png` | f9ce940f4a0434a6 | 1344x768 | Discover / Workshop |
| R-CLASS | `~/Pictures/coursebook-direction-a/refined-classroom.png` | ee0c1a664a7317ae | 1344x768 | Classroom lesson |
| R-SYS | `~/Pictures/coursebook-direction-a/refined-system.png` | 98a79124ea35b614 | 1344x768 | fox poses, card anatomy, badges, palette |
| R-MAP | `~/Pictures/coursebook-direction-a/refined-home.png` | a834b27bb365e8dd | 1344x768 | the board's Home panel ("What do you want to learn?" over a route map); same bytes as `japanese-classroom-reference.png` (F2) |

Ratification scope, in the owner's words: "outside of the home page, these images were ratified."
So R-DISC, R-CLASS and R-SYS are binding spec. The board's Home panel (R-MAP) is not the Home
target; it is used only for course home, where the same image is already ratified as F2. Home is
R-HOME, the separate image the owner sent as "this was supposed to be the home page."

R-HOME is not F1 (`home-generic-first-open.png`, mean pixel difference 32.1/255, measured). F1 says "What
will you learn next?" with a top nav; R-HOME says "Your field library" with two pill buttons, a
wooden shelf, four illustrated cards and a fox with an alarm clock and a "New course" tag. The
shipped GM-002 Home follows F1 under the v2 contract. See decision D1.

## 2. What was measured before writing this plan

The gap is a material and asset gap, not a layout gap. Facts from the current tree:

1. `contracts/cb.tokens.v2.json` and `docs/GM-VISUAL-SPEC.md` forbid exactly what the concepts are
   made of: shadows, gradients, grain, wood, pills, 10px radius, custom fonts. GM-VISUAL-SPEC 2.4
   replaces the wooden shelf with "2px ink ledge + 1px rule". Tests that enforce the bans:
   `test_desktop_tokens.py`, `test_desktop_type_scale.py`, `test_desktop_h152_motion.py`,
   `test_desktop_field_desk.py`, `test_desktop_h150_library_shelf.py`, `test_h197_covers.py`,
   `test_gm_visual_spec.py`, `test_desktop_home_hub.py`.
2. `desktop/plugin.js` on `origin/master` is one 1.34 MB, 32,022-line module (sha256 `7802e3ca...`).
   It has 0 `boxShadow`, 0 `@font-face`, 0 `<style>` elements, 884 inline `style:` objects and no
   `assets/`. Type uses OS stacks (`CB_SERIF` is ui-serif/Georgia, `CB_SANS` is system-ui). There is
   no fox anywhere in the module.
3. The host loader reads plugin source through `readPluginSource` with a 16 MiB cap, so embedded
   WOFF2 and small texture tiles fit. Another installed plugin (`hermes-security`) already renders a
   scoped `jsx('style', { children: CSS })`, so a scoped stylesheet is a proven seam.
4. Images reach the route as `data_url` from the backend (`/media/{artifact_id}`,
   `/artifacts/{handle}`); covers, workshop covers and world plates already use that path.
5. Current covers are deterministic flat SVG/Press Plates; `docs/gm-visual/boards/*.svg` are
   2 KB host-drawn shapes. The concept needs painted gouache art. That is the largest gap.
6. Real data exists for an honest card system: `library_item` has `title`, `subtitle`,
   `level_label`, `next_step`, `evidence_summary`, `updated_at`; `course_world` has assets per role
   (`hero`, `cover`, `section`); `engagement.read` returns `xp_total`, `level`, `xp_into_level`,
   recent events (XP 5/20/15/25/10 per real action, Game mode only).
7. Contrast of the concept palette: white on concept terracotta `#db6c45` is 3.36:1 (fails AA for
   body text). Ink `#1a1713` on it is 5.31:1; white on `#b4532f` is 4.98:1. Cream on the forest rail
   `#0d281b` is 15:1. The v3 palette must deepen the CTA or use dark text.
8. Toolchain: no profile has the `image_gen` toolset enabled; only `vellum` has
   `coursebook-desktop-rig`, and its copy is stale (16 KB against the current 50 KB with the v3 and
   concept rules); no worker has `coursebook-course-generation` or `impeccable`. `kanban.failure_limit` is 1, so one crash blocks
   a card. ImageMagick (PNG/WEBP/AVIF), tesseract, PIL and numpy are present; Inkscape, Krita and
   fontTools are not.
9. The "generic text on a blank background" screenshots are not fully explained. Ruled out: a stale
   operator install (installed sha equals master). Strong candidates: `scripts/gm002-shot.mjs`
   declares itself a "static render of the shipped Desktop module in Chromium (no backend, no chat,
   no RPC)", so frames from it carry no host CSS, no data and no art; and the v2 contract itself
   renders as flat type on a flat ground. CP-000 must separate the two with evidence. No visual card
   may be trusted until that is closed.

## 3. Decisions the owner must make before dispatch

Each has a recommended answer. Cards that depend on an open decision are created `blocked`.

| Id | Decision | Recommended |
|---|---|---|
| D1 | Is R-HOME the ratified Home, replacing F1? (Accepted: yes.) | Yes. Ratify R-HOME as Home v3 ("Your field library"). Keep one filled primary; "Browse library" becomes a quiet pill outline, not a second filled pill. |
| D2 | Adopt visual contract v3 (shadow, grain, wood, custom fonts, pills, larger radii) as a versioned contract beside v2? | Yes. New `cb.tokens.v3.json`; v2 tests are versioned, not weakened. |
| D3 | Navigation: R-HOME has a top header; R-DISC, R-CLASS and R-SYS have a forest-green left rail. | Forest rail inside the route at wide widths, collapsing to a top tab strip below 900 px. One system for every screen. |
| D4 | Art source | Generated art plates (host `image_generate`, textless) selected by an art bot, owner approves each family, optional human vector/texture cleanup. No code-drawn illustration. |
| D5 | Stars, review counts, "NEW"/"Life" badges, "240 XP" outside Game | Removed. Replaced by real fields (section 6). XP only in Game mode, as already ratified. |
| D6 | The GM chain is still moving: GM-020 repairs GM-008's regressions and rides with the GM-010 merge; GM-012 waits on GM-010. | Let GM-010, GM-020 and GM-012 finish on v2 and merge. Make GM-020 a parent of GM-012 so two vellum plugin writers never run at once (section 10, step 0). Hold GM-015 so the final gates cannot start before the v3 screens exist. |
| D7 | Fonts | OFL faces embedded as subset WOFF2: Fraunces (display) and Source Sans 3 (UI), plus Noto Serif JP subset for Japanese lesson text. Licence notices in `docs/THIRD-PARTY.md`. |
| D8 | Image budget | Cap per art family (section 5) and record spend per card. |
| D9 | Split `desktop/plugin.js` into ordered source segments built into the one shipped module (CP-006)? | Yes, right after GM-012 merges, while no other plugin writer runs. It is the only way to run screen cards in parallel without a lost-update race, and it saves about 5 h on the critical path (section 11). |
| D10 | Submission cut line | Vertical slice for the submission: v3 base, lab, Discover, Home, Classroom (CP-020a to CP-023) plus the gates. CP-024, CP-025a and CP-025b are scheduled roadmap, not dropped: if they are not merged by 2026-11-11 06:00 MST, the supervisor moves them after the submission and the gates run on the slice. |

## 4. Toolchain prep (operator or manager, before any bot runs)

These are setup actions, not cards. Each has a check.

1. Install the missing design authority: `hermes skills install official/creative/impeccable --yes`
   into the default home, then for `quill`, `cbqa`, `vellum` and the new art profile
   (`hermes -p <profile> skills install official/creative/impeccable --yes`). Check:
   `hermes -p vellum skills list | grep impeccable`.
2. Copy the current `coursebook-desktop-rig` (default `SKILL.md` sha `2bdc72af...`, with
   `references/`) into every worker profile; today only vellum has it, at sha `3c7a5823...`:
   ```bash
   S=~/.hermes/skills/software-development
   for p in atlas cbqa cinder harbor lattice quill sable sentinel vellum easel; do
     mkdir -p ~/.hermes/profiles/$p/skills/software-development
     rsync -a --delete $S/coursebook-desktop-rig/ ~/.hermes/profiles/$p/skills/software-development/coursebook-desktop-rig/
   done
   sha256sum ~/.hermes/profiles/*/skills/software-development/coursebook-desktop-rig/SKILL.md
   ```
   Every line must show the same sha as the default copy.
3. Copy `coursebook-course-generation` the same way into `quill`, `cinder`, `lattice` and `sable`.
4. Create an art specialist profile so art has real tools, not a renamed persona:
   `hermes profile create easel --clone-from quill`, write its SOUL.md (art director and
   illustration producer for Coursebook; owns textless plates, provenance and OCR checks; never
   edits `desktop/plugin.js`), then `hermes -p easel tools enable image_gen vision` and
   `hermes profile describe easel --text "Coursebook art director: textless art plates, fox poses, provenance"`.
5. Optional audit plugin: `hardlight-ui` for `cbqa` (contrast, navigation, source inspection) after
   reading its source. Defer `mock-review` until art contact sheets exist (CP-012).
6. Keep the global `kanban.failure_limit: 1`, and give every CP card `--max-retries 3` at creation
   (the breaker then trips on the third consecutive failure), so one crashed run does not block a
   long art or UI card.
7. Copy the reference pack into the repo so cards cite stable paths:
   `docs/concept-parity/refs/{home,board,discover,classroom,system,map}.png` plus `REFS.md` with the
   sha256 table from section 1. Committed by the manager on master.
8. No global Python installs. CP-004 builds its own font venv (`uv venv`), and CP-010 adds `rembg`
   to a private venv only if keyed mattes fringe.

## 5. Art families and budget (owned by `easel`)

No plugin supplies illustration. The art is the critical path, so it starts first and runs in
parallel with the contract and engineering cards. Every plate is textless, carries a provenance row
(`docs/ASSET-PROVENANCE.md`, `docs/GM-ART-PLATES.md` section 4), passes an OCR text check, and has a
typographic fallback. Art never carries procedure, measurement or safety content.

| Family | Pieces | Format | Generation cap | Notes |
|---|---|---|---|---|
| A1 Fox pose sheet | 7 poses: wave (Home), point (Discover), clock (Home "New course"), read (Classroom), cheer (check correct), think (wrong answer, kind), sleep (empty/offline) | transparent PNG/WebP, 512 px tall master, 128 and 64 px exports | 3 rounds x 7 | one character model sheet first; every later pose uses it as a reference image; consistent dark-brown outline, cream bib, dark socks |
| A2 Material textures | paper grain tile, parchment vignette, wood plank tile, card-stock fibre | 256-512 px seamless tiles, under 60 KB each | 2 rounds | light and dark variants; tiles proven seamless by a 3x3 composite |
| A3 Workshop pack covers | 3 covers for the bundled packs; the four demo course covers are made by the product's own world job in CP-015 under CP-016's prompts | 3:2 master 1200x800, 4:5 crop | 3 rounds x 3 | one painted gouache kit, same light (upper left) and line weight; subject motifs from `docs/GM-SUBJECT-WORLDS.md` |
| A4 Scene headers | Japanese Lantern District banner (Discover feature), cafe interior (Classroom), expedition map ground (course home only) | 16:9 and 4.4:1 crops | 3 rounds x 3 | quiet field reserved for DOM type; no lettering anywhere |
| A5 Object kit | stamp node rim, medallion rims (5 events), passport tray, ticket, brass alarm clock, kraft "tag" blank | transparent PNG, 256 px | 2 rounds | blanks only; every label is DOM text laid over them |

Process per family: easel writes prompts from the v3 contract, generates, runs OCR and a vision
self-critique against the matching reference crop, builds a labelled contact sheet, then submits to
`quill` (visual review). The owner approves A1 and A3 from the contact sheet before engineering
consumes them. Rejected plates are deleted, never shipped as fallbacks.

## 6. Honesty substitution table (binding for every card)

| Concept element | Ship instead | Source field |
|---|---|---|
| Star ratings, review counts | nothing, or "Validated pack" trust label in Workshop | `pack.inspect` trust state |
| "NEW" badge on cards | "New" only when the course has no attempts yet | `library_item.evidence_summary` empty and `next_step` = first section |
| "Life" / random coloured badges | subject chip from the course | `world_brief.subject_domain` or `recipe` |
| Progress bar on every card | evidence tally: "2 of 5 sections done" | `library_item.next_step`, `evidence_summary` |
| "240 XP", flames, streak (Game) | XP chip and Game progress bar, Game mode only; no streak in this slice | `engagement.read` |
| "215 proofs collected" / "2 of 5 proofs" | "2 of 5 checks recorded" | evidence classes from `evidence.inspect` |
| Gold seals and rosettes | one medallion per real named event (first check, first review, first take-home task, course complete) | engagement recent events |
| Padlock on proofs | "Opens after the check" only where the plan really gates it | course plan |
| Japanese speech bubble text | the lesson's real Japanese line, kana plus romaji | `lesson_block` |
| "Audio Play" as an answer option | speaker button on the dialogue bubble; answers are the real check options | `lesson.page` check |
| Garbled headings | product copy fixed in `docs/concept-parity/COPY.md` (CP-001) | not data |

## 7. Card graph

Who does what in this plan:

| Profile | Role here |
|---|---|
| atlas | manager and integrator; reviews CP-001; owns GM-017 and every merge |
| quill | writes the spec and the v3 contract (CP-001, CP-002); visual reviewer for every art and UI card |
| easel (new) | art director and producer (CP-010 to CP-013); judges CP-016's generated worlds |
| vellum | the only `desktop/plugin.js` writer (GM-012, CP-020a to CP-025b) |
| sable | platform: asset pipeline (CP-004), module split (CP-006), world prompts (CP-016) |
| cinder | backend card facts (CP-005) |
| lattice | pack media and the four real demo courses (CP-014, CP-015) |
| sentinel | render forensics (CP-000), gate migration (CP-003), behavioural QA (GM-015); reviews backend and platform cards |
| cbqa | reviews the contract and gates (CP-002, CP-003); runs the final parity gate (GM-016) |
| harbor | README, demo script and submission shots (CP-026) |

Labels use the free prefix `CP-` (checked: no collisions on the board). Owners follow the existing
specialist split. Every card names an independent reviewer; makers never `complete`.

### Wave 0: unblock and freeze (all parallel, start immediately)

| Card | Work | Owner | Reviewer | Parents | Writes |
|---|---|---|---|---|---|
| CP-000 | Render-path forensics: why screenshots showed plain text on a blank page; fix the capture rig | sentinel | cbqa | none | `scripts/cp-capture.mjs`, `docs/concept-parity/CP-000-RENDER.md` |
| CP-001 | Concept parity spec v3: per-screen region maps, copy deck, state lists, honesty table, nav decision | quill | atlas | D1-D5 | `docs/concept-parity/SPEC-V3.md`, `COPY.md` |
| CP-002 | Visual contract v3: tokens, type scale, materials, elevation, radii, motion; contrast pairs | quill | cbqa | D2, D7 | `contracts/cb.tokens.v3.json`, `docs/COURSEBOOK-VISUAL-IDENTITY-V3.md` |
| CP-003 | Gate migration: version every v2 material test, add v3 tests, keep v2 tests for v2 surfaces | sentinel | cbqa | CP-002 | `tests/test_desktop_tokens_v3.py` and versioned edits to the eight v2 test files |
| CP-010 | Fox character sheet and pose set (A1) | easel | quill | D4 | `assets/art/fox/*`, provenance rows |
| CP-011 | Material textures (A2) | easel | quill | D4 | `assets/art/material/*` |
| CP-004 | Asset pipeline: `scripts/build_cb_assets.py` (optimise to WebP/AVIF, subset fonts, embed as base64 into a generated `desktop/cb-assets.generated.js` segment, size budget test) | sable | sentinel | CP-002 | `scripts/build_cb_assets.py`, `tests/test_cb_assets.py` |
| CP-005 | Real-data seams for the cards: one read that returns per-course shelf facts (sections done/total, is-new, subject chip, cover artifact) without new invention | cinder | sentinel | CP-001 | the `library.list` handler in `coursebook/domain.py`, `contracts/rpc.v25.json` (additive) |

CP-002 and CP-010/011 run together: the contract names roles, easel paints to roles, and the
contract reviewer checks that every painted surface maps to a role.

### Wave 1: art production, content and the v3 base (parallel lanes, one plugin.js writer)

| Card | Work | Owner | Reviewer | Parents | Writes |
|---|---|---|---|---|---|
| CP-012 | Workshop pack covers (A3) | easel | quill | CP-010 approved style | `assets/art/covers/*`, pack media rows |
| CP-013 | Scene headers (A4) and object kit (A5) | easel | quill | CP-010 | `assets/art/scenes/*`, `assets/art/objects/*` |
| CP-014 | Pack media integration: approved covers into the three bundled packs as role `cover`, re-hash catalogue | lattice | sentinel | CP-012 | `bundled/packs/*`, `catalog/workshop.v1.json` |
| CP-016 | World prompts to the art bible, proven live on two new topics | sable | easel | CP-010, CP-013 | `coursebook/world.py`, prompt tests |
| CP-015 | Four real demo courses made through the product's own create flow | lattice | sentinel | CP-016 | demo profile seed script, run records |
| CP-006 | Mechanical split of `desktop/plugin.js` into ordered segments (D9) | sable | sentinel | GM-012 merged | `desktop/src/*`, `scripts/build_plugin.py` |
| CP-020a | v3 style scope, fonts, materials, ready marker | vellum | quill | CP-002, CP-003, CP-004, CP-011, GM-012 (and CP-006) | `desktop/plugin.js` |
| CP-020b | v3 primitives and the component lab (the product's design-system sheet) | vellum | quill | CP-020a, CP-010, CP-013 | `desktop/plugin.js` |

### Wave 2: screens (one plugin.js writer, or parallel segments with D9)

| Card | Work | Owner | Reviewer | Parents |
|---|---|---|---|---|
| CP-021 | Discover / Workshop v3 (R-DISC): feature banner, rail, collectible grid aligned to the banner, fox point pose, honest metadata | vellum | quill | CP-020b, CP-014 |
| CP-022 | Home v3 (R-HOME): "Your field library", one primary pill, quiet secondary, wooden shelf with four real courses, fox with clock and "New course" tag | vellum | quill | CP-021, CP-005, CP-015 |
| CP-023 | Classroom v3 (R-CLASS): stamp-node stepper, framed scene, dialogue bubble with real Japanese, check card as the one primary, Field Challenge in Game only, evidence tray, restyled tutor rail | vellum | quill | CP-022 |
| CP-024 | Course home and route v3 (R-MAP, F2): map ground as art, route nodes as DOM buttons | vellum | quill | CP-023 |
| CP-025a | v3 adoption on the GM-008 homework surfaces and the GM-010 Game header and completion | vellum | quill | CP-024 |
| CP-025b | v3 adoption on World Studio (GM-004) and Parent Studio (GM-006) | vellum | quill | CP-025a |

Each screen card captures its own stamped matrix with `scripts/cp-capture.mjs` from its own
commit; the stamp makes a stale or faked frame detectable, and the reviewer reproduces at least
three cells live. The final integrated build is re-captured from scratch by GM-016, so no screen
evidence is ever inherited by the release gate.

### Wave 3: the existing gates, extended (one quality bar, no second gate)

| Card | Work | Owner | Reviewer | Parents |
|---|---|---|---|---|
| GM-015 `t_ec0fcc1d` | Independent behavioural and accessibility QA, now including every v3 screen | sentinel | cbqa | existing parents plus CP-015, CP-021 to CP-025b |
| GM-016 `t_11e21405` | Final concept-parity acceptance: side-by-side boards against R-HOME, R-DISC, R-CLASS, R-SYS (lab), R-MAP; v3 rubric; "better than the concept" checklist | cbqa | quill | GM-015 |
| CP-026 | README, demo script and submission screenshots from the accepted v3 build | harbor | sentinel | GM-016 |
| GM-017 `t_cfcb5927` | Integration, v3 audit re-pin, install, sha verify, docs, owner screenshot pack | atlas | sentinel | GM-015, GM-016, CP-026 |

### Parallelism at a glance

- Start together: CP-000, CP-001, CP-002, CP-010 and CP-011, beside the GM chain card vellum is on
  (GM-020, then GM-012): six workers, the dispatcher's `--max 6`. CP-003, CP-004 and CP-005 start
  as soon as their one parent merges.
- Art (easel) runs CP-010, then CP-012 and CP-013 together, in its own lane; it never touches code.
- Backend and content (cinder, sable, lattice) run CP-005, CP-016, CP-014 and CP-015 beside the UI.
- One `desktop/plugin.js` writer at a time: GM-020, GM-012, CP-006, CP-020a, CP-020b, then the screens.
  With D9, the manager reads CP-006's segment map; screen cards whose segments are disjoint are
  unlinked and run in parallel worktrees (CP-021 beside CP-023 is the likely pair), and each merges
  by regenerating the module. CP-022 and CP-024 stay serial because both touch Home and course-home
  code.
- Review trails each card by one step, so a maker never waits idle on a reviewer.

## 8. Card bodies

Each card body below is written to `docs/concept-parity/cards/<CARD>.md` on master before the card
is created, and the card is created with `--body-file` pointing at it. A comment is not a durable
input; the body and the committed spec are.

### 8.0 Common rules (pasted at the top of every CP body)

- Read first, in order: `docs/concept-parity/SPEC-V3.md` (once CP-001 lands), `contracts/cb.tokens.v3.json`
  and `docs/COURSEBOOK-VISUAL-IDENTITY-V3.md` (once CP-002 lands), `docs/EXPERIENCE-QUALITY-BAR.md`,
  `docs/GM-CONCEPT-PARITY-RUBRIC.md` (v3 section), `docs/concept-parity/refs/REFS.md`, this plan.
- Base: work only in the card worktree. Merge every parent branch named in the card before editing
  (`git merge --no-edit <branch>`). If a parent branch is missing, stop and report. Never edit the
  operator checkout, never merge to master, never push.
- Only cards owned by `vellum` may edit `desktop/plugin.js`. Any other card that finds it needs a
  plugin change writes the request into its review summary instead.
- Truth: every visible label is DOM text from real state or the copy deck. No stars, review counts,
  invented XP, invented counts, AI text inside art, or generated screenshots used as UI.
- Evidence: screenshots only through `scripts/cp-capture.mjs` (CP-000), each with its stamp JSON.
  A frame without a stamp, or with a stamp whose plugin sha differs from the commit under review,
  is invalid.
- Commit small, run the named tests, then
  `hermes kanban request-review <CARD_ID> --reviewer <reviewer> --summary "branch; commits; tests; evidence paths; known gaps"`.
  Never call `hermes kanban complete` on your own card.
- Reviewer section: you did not build this. Reproduce the tests and at least three evidence cells
  live, score with the v3 rubric, then `complete` with the scorecard path or `request-changes` naming
  the defect class and the test that closes it. Three change rounds maximum; the fourth escalates
  to `atlas`, who splits the residual.
- Full suite runs in the background with a log (`python3 -m unittest discover -s tests -t . > "${TMPDIR:-/tmp}/<card>-suite.log" 2>&1`),
  never two suites at once, never the audit and the suite at once.

### CP-000 Render-path forensics and the one capture method

Owner `sentinel`, reviewer `cbqa`, branch `wt/cp-000-render`, runtime 90m, skills
`coursebook-desktop-rig`, `inspecting-hermes-desktop-dom`. Parents: none. Must not edit `desktop/plugin.js`.

Mission: explain, with evidence, every recent screenshot that showed plain text on a blank page, and
make that failure impossible to submit again.

Steps:
1. Inventory every frame under `docs/visual-review/gm-002/` and `gm-004/` and classify it from its
   manifest as static render (`scripts/gm002-shot.mjs`, "no backend, no chat, no RPC") or live rig.
2. Build a fresh rig state (new `HERMES_HOME`, userdata, CDP port, isolated backend) from
   `origin/master` `00751f0`; copy `desktop/plugin.js` to every load path and record each sha256.
3. Capture `#/coursebook` live and the same surface through the static renderer. Record console
   errors, `[data-cb-route]` presence, the route marker, computed font families, and whether host CSS
   is present in each.
4. Write `docs/concept-parity/CP-000-RENDER.md`: each cause found, its evidence, and which past
   frames it explains. State plainly how much of the gap is capture method and how much is the v2
   design itself rendering as flat text.
5. Ship `scripts/cp-capture.mjs`. It refuses to capture unless: the module sha in the window equals
   the checkout sha; `[data-cb-route]` exists with no render-error marker; `document.fonts.status`
   is `loaded`; every `img` in the route is decoded with `naturalWidth > 0`; and, once v3 exists,
   `[data-cb-v3-ready]` is set. It crops to `[data-cb-route]`, applies route width through
   `Emulation.setDeviceMetricsOverride`, and writes `<name>.png` plus `<name>.stamp.json`
   (plugin sha, backend `wire_version` and method count, route width, theme, text scale, reduced
   motion, forced colors, fonts loaded, images decoded, time).
6. Measure cold route paint time of the current module three times; record the median as the
   performance baseline for v3.
7. Ship `scripts/cp-sbs.py`: builds an equal-height side-by-side PNG (concept crop left, product
   right) from a refs crop box and a capture.

Tests: `tests/test_cp_capture_stamp.py` (stamp schema; a stale sha is refused; a missing font or
undecoded image is refused, using a recorded fixture page).

Acceptance: the report names a root cause per frame class; a live capture of current master exists
with a valid stamp; the capture script refuses a stale module in a demonstrated run.

### CP-001 Concept parity spec v3

Owner `quill`, reviewer `atlas`, branch `wt/cp-001-spec`, runtime 120m, skills `impeccable`,
`coursebook-desktop-rig`, `design-md`. Parents: none; created blocked until D1 to D5 are answered.

Mission: turn the concept images into numbers and strings a builder can follow and a reviewer can
score without asking anyone.

Deliverables in `docs/concept-parity/`:
- `SPEC-V3.md`: for Home (R-HOME), Discover/Workshop (R-DISC), Classroom (R-CLASS), Course home
  (R-MAP), Design-system lab (R-SYS): a region map in route-relative units at route widths 1049,
  900 and 460; the fox pose per screen and its safe area; the one primary action; navigation model
  per D3; every state with its one next action; and a "better than the concept" list per screen
  (for R-DISC at least: grid aligned to banner edges, no dead zone right of the grid, labelled rail,
  fox inside the safe area, one metadata pattern for every card).
- `COPY.md`: every string on every v3 screen, plain 6th to 8th grade, sourced from the copy deck or
  a named backend field; Japanese lines at L0 carry kana, romaji and furigana per the pack scaffold.
- The honesty table from section 6 of this plan, extended to every element in the five references.
- Icons stay `sdk.Codicon` only: the rail uses Codicon glyphs with visible labels, and medallion and
  stamp-node centres are Codicon glyphs placed on painted blanks. The concept's custom line icons are
  not a second icon set.
- `docs/visual-review/matrix.json` additions for `home.v3`, `discover.v3`, `classroom.v3`,
  `course-home.v3`, `lab.v3` with named states, plus a forced-colors cell for each screen.
- A short owner amendment appended to `docs/EXPERIENCE-QUALITY-BAR.md` recording which v2 rules the
  ratified concepts lift (physical elevation, paper and wood material, custom faces, pills, larger
  radii) and which stay (no glass, no rainbow gradients, no fake data, one primary, Codicon only).
- `GM-CONCEPT-PARITY-RUBRIC.md` v3 section: the nine dimensions plus a tenth, Craft (material
  consistency, illustration consistency, alignment, edge quality at 200% zoom); anchor A3 redefined
  as "a lit paper world with physical objects and contact shadows"; pass rule unchanged (every
  dimension at least 4, all anchors present).

Tests: `tests/test_cp_spec.py` (matrix entries exist for every v3 screen and state; every COPY.md
string id is referenced by SPEC-V3; no banned word list: stars, rating, reviews, learners, mastery).

### CP-002 Visual contract v3

Owner `quill`, reviewer `cbqa`, branch `wt/cp-002-tokens`, runtime 120m, skills `design-md`,
`impeccable`. Parents: none; blocked until D2 and D7.

Deliverables:
- `contracts/cb.tokens.v3.json` with light and dark palettes for these roles: `canvas`,
  `canvas-edge`, `card-stock`, `ink`, `ink-soft`, `rule`, `forest`, `on-forest`, `terracotta`,
  `on-terracotta`, `terracotta-quiet`, `gold`, `sage`, `wood`, `wood-edge`, `plum`, `alert`,
  `focus`. Starting values come from the reference measurements in section 2 (rail `#0d281b`,
  canvas `#f5e3c8`, card stock `#f4ecd9`, concept CTA `#db6c45`). The CTA must reach 4.5:1 for its
  label: either deepen the fill (white on `#b4532f` is 4.98:1) or use ink labels (5.31:1 on
  `#db6c45`). Render both on parchment and pick one in the review.
- Elevation `elev-1`, `elev-2`, `inset-1`, with dark-mode values; radii `0`, `6`, `12`, `999`;
  type families `CB Display` (Fraunces subset) and `CB UI` (Source Sans 3 subset) with a system CJK
  stack for Japanese; six type steps with display as
  `clamp(2.5rem, 1.5rem + 3cqi, 4rem)` measured against the route container, not the window;
  materials (grain tile id and opacity per theme, vignette, wood tile id); motion beats press 120,
  lift 150, route 240, verdict 300, complete 600 ms, ceiling 600 ms, no loops.
- Contrast pairs with required ratios for every text-on-surface combination, including text on
  `forest`, on `card-stock`, on `wood` (labels never sit on wood), and focus ring on every surface.
- `docs/COURSEBOOK-VISUAL-IDENTITY-V3.md`: plain-language rules per role, what each surface may
  use, the dark "night atlas" mode, forced-colors behaviour, and what stays banned.

Tests: `tests/test_tokens_v3_contract.py` (schema, every pair computed and passing, dark and light
role parity, no role missing). These run on the contract file alone, so they pass before any UI.

### CP-003 Gate migration (versioned, not weakened)

Owner `sentinel`, reviewer `cbqa`, branch `wt/cp-003-gates`, runtime 120m. Parent: CP-002.
Must not edit `desktop/plugin.js`.

Mission: let v3 surfaces exist without deleting a single v2 protection.

Steps:
1. Classify every assertion in `test_desktop_tokens.py`, `test_desktop_type_scale.py`,
   `test_desktop_h152_motion.py`, `test_desktop_field_desk.py`, `test_desktop_h150_library_shelf.py`,
   `test_h197_covers.py`, `test_gm_visual_spec.py`, `test_desktop_home_hub.py` as universal,
   v2-material, or superseded-by-v3. Record the table in `docs/concept-parity/GATE-MIGRATION.md`.
2. Scope v2-material assertions to v2 regions (inline style objects outside the v3 stylesheet).
3. Add `tests/test_desktop_tokens_v3.py`: `CB_TOKENS_V3_JSON` equals the contract byte for byte; hex
   appears only in the two token literals; `box-shadow` appears only inside `CB_V3_CSS` and only as
   `var(--cb3-elev-*)`; no `backdrop-filter`, no `blur(`; the only gradient is the named vignette;
   every selector in `CB_V3_CSS` starts with `[data-cb-v3]` except `@font-face`; every font family
   name starts with `CB `; motion durations come only from the motion table.
4. Version the M4 audit: `scripts/m4v-audit.py` claims apply to v2 surfaces; add
   `scripts/v3-audit.py` and `tests/test_v3_visual_audit.py` with v3 claims and the module sha pin.
5. Put `V3_REQUIRED = False` at the top of each new v3 test module. CP-020a flips it to `True` as
   its first commit, watches the tests fail, then makes them pass. That is the TDD hand-off.

Acceptance: full suite green on the branch with `V3_REQUIRED = False`; with a temporary local flip
to `True` the v3 tests fail for the stated reasons (paste the output in the review summary).

### CP-004 Asset pipeline and size budget

Owner `sable`, reviewer `sentinel`, branch `wt/cp-004-assets`, runtime 90m. Parent: CP-002.
Must not edit `desktop/plugin.js` except through the generated segment named below.

Mission: brand assets (fonts, textures, fox, object kit) travel inside the single plugin module;
course and pack art keeps using the existing media route.

Deliverables:
- `assets/` tree: `fonts/`, `material/`, `fox/`, `objects/`, each with a `manifest.json` row per
  file (role, source, licence SPDX, sha256, width, height, bytes, provenance id).
- `scripts/build_cb_assets.py`: converts approved masters to WebP (AVIF where the host decodes
  it), subsets fonts to Latin plus punctuation with fontTools in a private `uv venv`, writes
  `desktop/cb-assets.generated.js` as one frozen `CB_ASSETS` object of data URLs, and prints a
  size report. Deterministic: two runs give identical bytes.
- Font licence check before subsetting: read each font's OFL text for Reserved Font Names. If an
  RFN applies, either ship the unmodified file or rename per OFL; record the decision in
  `docs/THIRD-PARTY.md`.
- Budgets enforced by `tests/test_cb_assets.py`: generated segment at most 2.5 MB; any single
  asset at most 300 KB; `desktop/plugin.js` total at most 4.5 MB; every manifest row has a licence
  and a sha256 that matches the file; no asset path outside `assets/`.
- Course covers, scene headers and world plates are never embedded. They stay pack or world media
  served by `/media/{artifact_id}` and `/artifacts/{handle}`.

### CP-005 Shelf and card facts (backend)

Owner `cinder`, reviewer `sentinel`, branch `wt/cp-005-shelf-facts`, runtime 90m. Parent: CP-001.

Mission: every number or badge on a v3 card comes from one read, so the UI never computes or
invents one.

Deliverables: an additive field set on `library.list` items (or a new `library.cards` method if
the contract owner prefers a new read), frozen in `contracts/rpc.v25.json` with `rpc.v24.json`
byte-identical: `sections_done`, `sections_total`, `checks_recorded`, `is_new` (no attempts yet),
`subject_label`, `cover_artifact_id` (approved world cover, else pack cover, else null),
`last_studied_at`. No rating, no learner count, no percentage. Handler tests for a new course, a
course mid-path, a finished course, a pack-backed course, and a course whose world was rejected.

### CP-006 Mechanical split of desktop/plugin.js (only if D9 is yes)

Owner `sable`, reviewer `sentinel`, branch `wt/cp-006-split`, runtime 90m. Parent: GM-012 merged
to master (no other plugin writer may be running).

Mission: let several UI cards work at once without editing the same file, with zero behaviour
change.

Steps: split `desktop/plugin.js` at its existing top-level banners into ordered files
`desktop/src/NN-<name>.js`; add `scripts/build_plugin.py` that concatenates them in order to
`desktop/plugin.js`; add `tests/test_plugin_build.py` asserting the concatenation is byte-identical
to the committed `desktop/plugin.js`, so a direct edit of the generated file fails the suite.
Acceptance: the first commit's regenerated file has the same sha256 as master's `plugin.js`; full
suite and `node --check` green; `scripts/validate-plugin.sh` 4/4. Update the rule in
`docs/GAME-MODE-CARD-DAG.md`: never two writers on the same segment; the generated file is resolved
at merge by regeneration, never by hand.

### CP-010 Art bible, fox character sheet and pose set (A1)

Owner `easel`, reviewer `quill`, branch `wt/cp-010-fox`, runtime 150m, skills `impeccable`,
`coursebook-desktop-rig`. Parents: none; blocked until D4.

Deliverables:
- `docs/concept-parity/ART-BIBLE.md`: medium (opaque gouache with a dark-brown ink line), light
  (soft, upper left), palette tied to v3 roles, line weight per output size, the fox model sheet
  rules (head about 45 percent of figure height, cream bib and tail tip, dark socks to the elbow,
  dark ear backs, outline `#3a2318`-class brown, never black), forbidden content, prompt
  templates, negative prompts, and the reference-image procedure.
- Fox model sheet first: front, three-quarter, side and back turnaround in one image. Owner
  approves it from the contact sheet before any pose is generated.
- Seven poses (wave, point, clock, read, cheer, think, sleep). Each pose is generated with the
  approved model sheet as `reference_image_urls`, using the provider's returned media URL.
- Cutouts: generate on a flat chroma background and key with ImageMagick; if fur edges fringe,
  use `rembg` in a private venv. Inspect every cutout at 200 percent on parchment and on the dark
  canvas.
- Each pose passes a tesseract text check (no letters), a vision consistency check against the
  model sheet (same markings, proportions, colours), and has a provenance row with provider, model,
  prompt hash, date, sha256 and the text-check result.
- `docs/concept-parity/art/fox-contact-sheet.png` labelled by pose.

Acceptance: the owner approves the model sheet and the pose sheet; the reviewer confirms the seven
poses read as one character at 64 px and at 256 px.

### CP-011 Material textures (A2)

Owner `easel`, reviewer `quill`, branch `wt/cp-011-material`, runtime 90m. Parent: none (uses the
art bible draft from CP-010 when available).

Deliverables: paper grain, parchment vignette, wood plank and card-stock fibre tiles in light and
dark variants, each seamless (3x3 composite proof image), at most 60 KB, plus a texture sheet
rendering every tile behind real body text at 16 px to show legibility is unaffected. Wood is
used only for the shelf plank and the evidence tray; it never sits behind text.

### CP-012 Workshop pack covers (A3)

Owner `easel`, reviewer `quill`, branch `wt/cp-012-covers`, runtime 150m. Parents: CP-010 (model
sheet and art bible approved).

Deliverables: one cover kit (same light, line and paper) for the three bundled packs and any pack
CP-015 exports; masters at 1200x800 with 4:5 and 3:2 crops; each cover passes the anti-generic swap
check in `docs/GM-SUBJECT-WORLDS.md`; textless; provenance rows; a labelled contact sheet for owner
approval. Covers for the four demo courses are not drawn here; they come from the product's own
world pipeline (CP-015 and CP-016), so the shelf shows art the product can make for any course.

### CP-013 Scene headers and object kit (A4, A5)

Owner `easel`, reviewer `quill`, branch `wt/cp-013-scenes`, runtime 150m. Parent: CP-010.

Deliverables: the Discover feature banner ground (lantern district, 4.4:1, quiet field for DOM
title), the cafe interior lesson frame (16:9), the expedition map ground for course home (16:9, no
pins and no numbers, nodes are DOM), and the blank object kit: stamp-node rim, medallion rims for
five real events, passport tray, ticket, brass alarm clock, kraft tag blank. Icons placed in rims
at runtime are `sdk.Codicon`. Every label is DOM over the blank.

### CP-014 Pack media integration

Owner `lattice`, reviewer `sentinel`, branch `wt/cp-014-pack-media`, runtime 60m. Parent: CP-012.

Deliverables: approved covers added to the bundled packs as role `cover` with
`license.per_artifact[]`, manifests and `catalog/workshop.v1.json` re-hashed, Press Plate kept as
the typographic fallback, `tests/test_workshop.py` and pack import tests green.

### CP-015 Four real demo courses made by the product

Owner `lattice`, reviewer `sentinel`, branch `wt/cp-015-demo-courses`, runtime 240m. Parents:
CP-016 merged. Skills `coursebook-course-generation`, `coursebook-desktop-rig`.

Mission: the Home shelf shows four courses that really exist, created the way a user would create
them: Japanese Cafe Basics (L0, ordering at a cafe), Auto Repair Fundamentals, Astronomy, Sourdough.

Steps: on a disposable demo `HERMES_HOME`, run `scripts/reset-demo-data.py`, then for each course
use the live create flow: goal, plan generated and approved, world style board chosen, world
approved, first lesson page rendered. Record job ids, validator verdicts, source counts and image
counts. No QA fixture names on the shelf. Export each course for the demo profile so the shelf can
be rebuilt from scratch with one command (`scripts/seed-demo-shelf.sh`).

Acceptance: four plans approved by the validator with sources; four approved worlds; one rendered
lesson page per course; Auto Repair passes the head-gasket rule (art is orientation only).

### CP-016 World prompts to the v3 art bible

Owner `sable`, reviewer `easel` (art judge; did not write the code), branch `wt/cp-016-world-v3`,
runtime 120m. Parents: CP-010, CP-013.

Mission: covers, heroes and section plates generated at runtime for any new course match the art
bible, not only the curated demo.

Deliverables: `coursebook/world.py` `STYLE_DIRECTIONS` and grammar prompts updated to the art
bible (medium, light, palette, line), the textless negatives kept, the fox reference rule ("no
mascot other than the fox") kept, any new aspect role (for example a 3:2 card crop) added
additively with a contract test. A live proof on two topics that are not in the demo set (one
technical, one creative): style boards and approved world for each, contact sheet attached.
Prompt-hash tests updated; GM-003 and GM-019 fence tests green.

### CP-020a v3 style scope, fonts and materials

Owner `vellum`, reviewer `quill`, branch `wt/cp-020a-scope`, runtime 120m, skills `impeccable`,
`coursebook-desktop-rig`. Parents: CP-002, CP-003, CP-004, CP-011, GM-012 merged to master, and
CP-006 when D9 is yes.

Mission: the Coursebook route can paint a lit paper world. Nothing on a product screen changes
yet except the route ground.

TDD order:
1. First commit flips `V3_REQUIRED = True` in the CP-003 test modules. Run them; paste the failures.
2. Add `CB_TOKENS_V3_JSON` (byte-equal to the contract), `CB_V3_CSS` and a `CbV3Scope` component
   that renders one `jsx('style', { children: CB_V3_CSS })` inside the route root, sets
   `data-cb-v3`, `container-type: inline-size` and `container-name: cb`, writes the v3 custom
   properties for the current light or dark mode, and registers `@font-face` rules from
   `CB_ASSETS` data URLs with `font-display: swap`.
3. After `document.fonts.ready` and the ground textures decode, set `data-cb-v3-ready`. A font or
   texture that fails to load leaves the system stack and flat colour in place, never a blank route.
4. Materials: canvas grain and vignette layers (`aria-hidden`, `pointer-events: none`), hidden under
   `@media (forced-colors: active)`; reduced motion disables every transition and lift.
5. Responsive rules use `@container cb (...)` against the route width. Keep `useCbViewportWidth()`
   only for decisions JavaScript must make.

Tests (fail first, then pass): `test_v3_scope_wraps_route_once`, `test_v3_tokens_match_contract`,
`test_v3_fonts_embedded_from_assets`, `test_v3_textures_hidden_in_forced_colors`,
`test_v3_ready_marker_waits_for_fonts`, plus every CP-003 v3 gate.
Evidence: live stamped captures of the current Home on the new ground at 1049/900/460, light and
dark, and the cold paint time against the CP-000 baseline (must not regress by more than 150 ms).

### CP-020b v3 primitives and the component lab

Owner `vellum`, reviewer `quill`, branch `wt/cp-020b-primitives`, runtime 150m. Parents: CP-020a,
CP-010 (fox approved), CP-013 (object kit).

Primitives, each with every state and a short doc comment naming its tokens:
`PillAction` (primary and quiet; one primary per surface is asserted by test), `ForestRail` and its
narrow form `ForestBand`, `PaperCard`, `CollectibleCard` (cover window, title, subject chip, real
meta row, optional "New" chip), `CoverPlate3` (artifact image or typographic fallback),
`ShelfPlank` (wood tile, front lip, contact shadow, cards bottom-aligned), `StampNode` (done,
current, upcoming, locked; a real button), `Medallion` (one per named real event), `FoxPose`
(pose id, size, `aria-hidden`, safe-area aware), `DialogueBubble` (ruby furigana, romaji line,
optional speaker button), `ChallengeCard`, `EvidenceTray`.

Lab: export the primitives on the module's existing test export object and add
`scripts/cp-lab-frames.py` plus `scripts/cp-lab-shot.mjs`, which render a lab page in Chromium
(every primitive x state x light/dark x 100/200 percent text). The lab is labelled a component
preview, never a live capture, and it is the product version of the R-SYS design-system sheet.

Tests: `test_v3_one_primary_per_surface`, `test_stamp_node_states_are_buttons_with_labels`,
`test_fox_pose_aria_hidden_and_hidden_below_620`, `test_collectible_card_has_no_rating_fields`,
`test_dialogue_bubble_renders_ruby_and_romaji`, `test_primitives_use_only_v3_tokens`.
Evidence: `docs/concept-parity/lab/contact-sheet.png` (owner checkpoint) and a side-by-side of the
lab card anatomy against R-SYS.

### Screen cards (CP-021 to CP-024)

Shared for all four. Owner `vellum`, reviewer `quill`, runtime 150m each, skills `impeccable`,
`coursebook-desktop-rig`. The maker captures the full matrix with `scripts/cp-capture.mjs` from the
card's own commit (eight baseline cells, every named state, forced colors, the 1349 wide cell) and
builds side-by-side boards with `scripts/cp-sbs.py` against the named reference crop. The review
packet is `docs/visual-review/<card>/MANIFEST.md` plus `SCORECARD.md` left blank for the reviewer.
If D9 is yes, each screen card edits only its own segment files and must not edit the primitive
segment; a needed primitive change becomes a small CP-020c card owned by vellum.

CP-021 Discover / Workshop v3 (R-DISC). Branch `wt/cp-021-discover`. Parents: CP-020b, CP-014.
- Heading "Discover your next world"; feature banner uses the CP-013 lantern ground with the real
  featured pack title and outcome as DOM text in the quiet field; one primary on the banner
  (`Preview`).
- Tabs Discover, Library, Provenance kept from H-196 with a visible active state.
- Collectible grid aligned to the banner's edges, column count from route width (4 at 1049 and
  above, 3 at 900, 1 with peek at 460); no dead zone right of the grid; layouts specified for 1, 3,
  7 and 8 packs.
- Card meta is one pattern: subject chip plus real structure ("6 sections") plus trust label. No
  stars, no review counts, no "Life".
- Fox point pose in the safe area at the bottom right, never cropped by the route edge.
- Tests: `test_workshop_v3_no_ratings_or_counts`, `test_workshop_v3_grid_aligned_to_banner`,
  `test_workshop_v3_same_cover_in_store_library_detail`, existing H-196 tests green.

CP-022 Home v3 (R-HOME). Branch `wt/cp-022-home`. Parents: CP-021, CP-005, CP-015.
- "Your field library", "Choose a course or start a new expedition." One filled terracotta pill
  `Start a new course` (opens the existing three-step create flow); `Browse library` is a quiet
  outline pill to Courses.
- Shelf: `ShelfPlank` with up to four real courses standing on it (contact shadows), cover from
  `cover_artifact_id`, meta from CP-005 fields only; `See all` when more than four.
- Fox clock pose standing on the plank's right end. The kraft tag shows "New: <title of the most
  recently created course>" and opens that course, only when that course is less than 14 days old
  and has no attempts; otherwise the tag is not rendered (see O5).
- States: first run (no courses: the start plate on the plank with the fox), loading (plank and
  card silhouettes, no shimmer), error (names the failed read, one retry), offline, overflow.
- Tests: `test_home_v3_one_primary`, `test_home_v3_cards_use_card_facts_only`,
  `test_home_v3_no_course_hero_on_global_home`, `test_home_v3_fox_tag_rule`,
  GM-002 behavioural tests kept green (the composition tests are superseded per CP-003's table).

CP-023 Classroom v3 (R-CLASS). Branch `wt/cp-023-classroom`. Parent: CP-022.
- Stamp-node stepper from the real course outline; current node has the warm halo; every node is
  a button opening its section; locked only where the plan gates it.
- Framed scene: the course world's section plate, else the CP-013 cafe frame for the Japanese pack,
  else a typographic plate. A `DialogueBubble` carries the lesson's real line (kana with furigana,
  romaji under it) and a speaker button when audio exists.
- Check card: the real check prompt and options; choosing an option is the one primary action.
  Feedback is immediate and kind (fox think pose on a wrong answer, cheer pose on a recorded pass).
- Right column: the tutor rail per GM-012's contract; in Game mode a `ChallengeCard` sits at its
  top with XP and level from `engagement.read` and real homework or practice rows. Textbook and
  Guided show no XP.
- `EvidenceTray`: "2 of 5 checks recorded" from evidence; first-try, hinted and answer-shown states
  stay visible.
- Tests: `test_classroom_v3_answer_is_primary`, `test_classroom_v3_no_xp_outside_game`,
  `test_classroom_v3_stepper_matches_outline`, `test_classroom_v3_ruby_on_japanese_line`,
  H-149 and H-178 lesson tests green.

CP-024 Course home v3 (R-MAP, F2). Branch `wt/cp-024-course-home`. Parent: CP-023.
- Hero map from the course world (or the CP-013 map ground for packs) with route anchors stored as
  normalised coordinates in the plate's manifest; nodes are DOM buttons placed on the anchors,
  falling back to the vertical `StampNode` route below 900 or when a plate has no anchors.
- One primary `Continue`; Field Notes and course shelf as the aside; host pet companion per the
  fox and pet rule in SPEC-V3.
- Tests: `test_course_home_v3_nodes_are_dom_buttons`, `test_course_home_v3_anchor_fallback`,
  `test_course_home_v3_one_primary`.

### Review, gates and integration (existing cards retargeted)

No second final gate is created. The existing gate cards are extended so there is one bar.

- CP-025a (vellum, reviewer quill, 150m, parent CP-024): the homework action, sheet and notebook
  list from GM-008 and the Game header, award and completion from GM-010, rebuilt on v3 primitives
  with their existing tests kept green and their matrix cells re-captured.
- CP-025b (vellum, reviewer quill, 150m, parent CP-025a): World Studio (GM-004) and Parent Studio
  (GM-006) on v3 primitives; Parent Studio keeps its adult-only rules and stays free of game chrome.
- GM-015 (sentinel, existing `t_ec0fcc1d`): add CP-015 and CP-021 to CP-025b as parents; add the v3
  behavioural list (keyboard order on the rail and shelf, 200 percent text, forced colors, reduced
  motion, null-runtime render, font-load failure, image-load failure, offline, cold profile).
- GM-016 (cbqa, existing `t_11e21405`): becomes the final concept-parity gate. Side-by-side boards
  for R-HOME, R-DISC, R-CLASS, R-SYS (lab) and R-MAP at equal width; v3 rubric with the Craft
  dimension; the "better than the concept" checklist from SPEC-V3; a five-second first-screen test
  with five fresh agent sessions given only the screenshot. Reviewer `quill`; the owner signs the
  last step.
- CP-026 (harbor, reviewer sentinel, 90m, parent GM-016): README, demo script and submission
  screenshots regenerated from the accepted build with `scripts/cp-capture.mjs`; old Atlas Lamp
  screenshots removed from the README; every claim in the README checked against the build.
- GM-017 (atlas, existing `t_cfcb5927`, add CP-026 as a parent): merge order, v3 audit re-pin, install to
  `~/.hermes/desktop-plugins/coursebook/plugin.js` and the checkout behind `~/.hermes/plugins/coursebook`,
  sha256 verified, `hermes plugins doctor coursebook`, docs, owner screenshot pack.

## 9. Merge and install rules (atlas and the supervisor)

1. A card is merged only after its named reviewer completes it. A board `done` is a branch, not a
   merge; atlas verifies `git merge-base --is-ancestor` on `origin/master` after every push.
2. Merge one card at a time into a detached scratch worktree from `origin/master`, run the v3 audit,
   then the full suite in the background (never both at once), then `scripts/validate-plugin.sh`.
   With D9, conflicts in `desktop/plugin.js` are resolved only by `python3 scripts/build_plugin.py`.
3. After each UI merge: copy `desktop/plugin.js` to `~/.hermes/desktop-plugins/coursebook/plugin.js`,
   fast-forward the operator checkout, verify both sha256 values equal master's, and post the
   card's side-by-side board link to the owner.
4. Never restart the default gateway from a worker. Python-half changes (CP-005, CP-016) are
   recorded as "needs operator gateway restart" with the exact command.

## 10. Dispatch sequence (for the manager or the board supervisor, after approval)

Step 0, now, whatever the approval state (two board edits, no code):

```bash
B="hermes kanban --board coursebook"
# GM-012 waits only on GM-010 today; without this edge it can start while GM-020 (also vellum,
# also desktop/plugin.js) is still running.
$B link t_ff09c89e t_35652a2f
# Hold the final QA gate so it cannot start on a v2-only build. `block` only acts on running or
# ready cards and GM-015 is todo, so park it as scheduled; `unblock` in step 4 re-gates it on its
# parents. Nothing releases a scheduled card automatically.
$B schedule t_ec0fcc1d "Held for concept parity v3; see docs/concept-parity/PLAN.md"
$B show t_ec0fcc1d | sed -n '1,4p'     # expect: status: scheduled
```

Update the supervisor cron job `85d2218453f7` (every 45 m, 67 of 120 runs used, so about 40 h of
runs left, enough to pass the deadline) with `hermes cron edit 85d2218453f7 --prompt "..."`. Keep
its existing protocol and append: merge GM-010 together with GM-020 after their reviews; let GM-012
run; never let two vellum cards run at once unless the manager unlinked them under D9; post each
CP card's side-by-side board in the report; apply the D10 cut line at 2026-11-11 06:00 MST; leave GM-015 scheduled until the manager runs
step 4.

Step 1, toolchain prep from section 4, with its checks. A worker skips a missing `--skill` with
only a log warning (it fails only when every named skill is missing), so verify each one. The
skills table truncates long names unless it is wide, hence `COLUMNS`:

```bash
for p in quill cbqa vellum easel sentinel sable lattice cinder atlas harbor; do
  printf '%-9s ' $p
  list=$(COLUMNS=250 hermes -p $p skills list --enabled-only 2>/dev/null)
  for s in impeccable coursebook-desktop-rig coursebook-course-generation design-md; do
    grep -q -- "$s" <<<"$list" && printf '%s ' "$s" || printf '(no %s) ' "$s"
  done; echo
done
```

Step 2, commit the inputs on master in one manager commit: `docs/concept-parity/refs/*`,
`REFS.md`, `docs/concept-parity/cards/CP-*.md` (bodies from section 8 with the common rules on
top), and the owner's answers to section 3.

Step 3, create the cards with parents at creation, so no worktree card is born ready ahead of its
dependency. If D1, D2, D4 or D7 is still open, add `--initial-status blocked` to the CP-001, CP-002,
CP-010 and CP-011 lines and `$B unblock` each one when its decision is answered (an initial block is
sticky, so the dispatcher never promotes it on its own). Save the block as `cp-create.sh` and run
`bash cp-create.sh` from the repo root (not pasted into an interactive shell, because of `set -e`); it stops
on the first failed create and writes every id to `cp-card-ids.env` for the later steps. The
helper was dry-run against a stub that records argv; `create --json` returns the task with `.id`.

```bash
set -euo pipefail
B="hermes kanban --board coursebook"; D=docs/concept-parity/cards; IDS=cp-card-ids.env
: > "$IDS"
mk() { # VAR "[LABEL] title" owner branch runtime [extra create args...]
  local var="$1" title="$2" owner="$3" branch="$4" rt="$5"; shift 5
  local label="${title#\[}"; label="${label%%\]*}"; local id
  id=$($B create "$title" --body-file "$D/$label.md" --assignee "$owner" --workspace worktree \
        --branch "$branch" --max-runtime "$rt" --max-retries 3 --json "$@" | jq -r .id)
  [[ "$id" == t_* ]] || { echo "create failed: $title" >&2; return 1; }
  printf -v "$var" '%s' "$id"; echo "$var=$id" >> "$IDS"; echo "$var $id $title"
}
GM012=t_35652a2f; GM015=t_ec0fcc1d; GM016=t_11e21405; GM017=t_cfcb5927
RIG="--skill coursebook-desktop-rig"; IMP="--skill impeccable"

# Wave 0
mk CP000 "[CP-000] Render-path forensics and capture method" sentinel wt/cp-000-render 90m $RIG --skill inspecting-hermes-desktop-dom
mk CP001 "[CP-001] Concept parity spec v3" quill wt/cp-001-spec 120m $IMP $RIG --skill design-md
mk CP002 "[CP-002] Visual contract v3" quill wt/cp-002-tokens 120m --skill design-md $IMP
mk CP010 "[CP-010] Art bible, fox model sheet and poses" easel wt/cp-010-fox 150m $IMP $RIG
mk CP011 "[CP-011] Material textures" easel wt/cp-011-material 90m $IMP
mk CP003 "[CP-003] Gate migration v2 to v3" sentinel wt/cp-003-gates 120m --parent $CP002
mk CP004 "[CP-004] Asset pipeline and size budget" sable wt/cp-004-assets 90m --parent $CP002
mk CP005 "[CP-005] Shelf and card facts" cinder wt/cp-005-shelf-facts 90m --parent $CP001

# Wave 1
mk CP012 "[CP-012] Workshop pack covers" easel wt/cp-012-covers 150m --parent $CP010 $IMP
mk CP013 "[CP-013] Scene headers and object kit" easel wt/cp-013-scenes 150m --parent $CP010 $IMP
mk CP014 "[CP-014] Pack media integration" lattice wt/cp-014-pack-media 60m --parent $CP012
mk CP016 "[CP-016] World prompts to the art bible" sable wt/cp-016-world-v3 120m --parent $CP010 --parent $CP013
mk CP015 "[CP-015] Four real demo courses" lattice wt/cp-015-demo-courses 240m --parent $CP016 --skill coursebook-course-generation $RIG
mk CP006 "[CP-006] Split plugin.js into built segments" sable wt/cp-006-split 90m --parent $GM012
mk CP020A "[CP-020a] v3 style scope, fonts and materials" vellum wt/cp-020a-scope 120m --parent $CP002 --parent $CP003 --parent $CP004 --parent $CP011 --parent $GM012 --parent $CP006 $IMP $RIG
mk CP020B "[CP-020b] v3 primitives and component lab" vellum wt/cp-020b-primitives 150m --parent $CP020A --parent $CP010 --parent $CP013 $IMP $RIG

# Wave 2 (serial form; see the D9 note below)
mk CP021 "[CP-021] Discover and Workshop v3" vellum wt/cp-021-discover 150m --parent $CP020B --parent $CP014 $IMP $RIG
mk CP022 "[CP-022] Home v3" vellum wt/cp-022-home 150m --parent $CP021 --parent $CP005 --parent $CP015 $IMP $RIG
mk CP023 "[CP-023] Classroom v3" vellum wt/cp-023-classroom 150m --parent $CP022 $IMP $RIG
mk CP024 "[CP-024] Course home v3" vellum wt/cp-024-course-home 150m --parent $CP023 $IMP $RIG
mk CP025A "[CP-025a] v3 on homework and Game surfaces" vellum wt/cp-025a-adopt 150m --parent $CP024 $IMP $RIG
mk CP025B "[CP-025b] v3 on World Studio and Parent Studio" vellum wt/cp-025b-adopt 150m --parent $CP025A $IMP $RIG

# Wave 3
mk CP026 "[CP-026] README, demo script and submission shots from v3" harbor wt/cp-026-readme 90m --parent $GM016 $RIG
```

If D9 is no, drop the CP-006 line and its `--parent $CP006`. If D9 is yes, after CP-006 merges the
manager reads its segment map and, where segments are disjoint, removes the narrative edges so the
screens run in parallel worktrees (parent first, child second):

```bash
B="hermes kanban --board coursebook"; set -a; . ./cp-card-ids.env; set +a
$B unlink $CP021 $CP022 && $B link $CP020B $CP022     # Home no longer waits for Discover
$B unlink $CP022 $CP023 && $B link $CP020B $CP023     # Classroom runs beside Discover and Home
$B unlink $CP024 $CP025A && $B link $CP021 $CP025A && $B link $CP023 $CP025A && $B link $CP024 $CP025A
$B unlink $CP025A $CP025B && $B link $CP021 $CP025B && $B link $CP023 $CP025B && $B link $CP024 $CP025B
```

Step 4, extend the existing gates (parent first, child second), then release the hold:

```bash
B="hermes kanban --board coursebook"; set -a; . ./cp-card-ids.env; set +a
GM015=t_ec0fcc1d; GM017=t_cfcb5927
for c in $CP015 $CP021 $CP022 $CP023 $CP024 $CP025A $CP025B; do $B link $c $GM015; done
$B link $CP026 $GM017
$B unblock $GM015            # leaves scheduled; re-gated on its parents, so it stays todo
```

Step 5, `$B dispatch --max 6 --json`, then `$B stats` and `$B list --status running`. Expect
CP-000, CP-001, CP-002, CP-010 and CP-011 running beside whichever GM chain card is live, once the
decisions are answered.
Keep the supervisor cron; add the no-agent dispatch watchdog described in
`coursebook-desktop-rig/references/kanban-card-dag.md` only if cards sit ready for more than one tick.

## 11. Schedule shape and the deadline

Computed from the runtime caps along the dependency graph, starting from GM-020 (running since
01:30) and including the gates (GM-015 120 m, GM-016 90 m, CP-026 90 m, GM-017 120 m). A cap is an
upper bound for one run; the 16 finished GM cards took a median of 1.3 h wall time (max 8.4 h),
while review rounds and owner approvals add time the caps do not show.

| Plan | Last screen merged | GM-017 done | Critical path |
|---|---|---|---|
| D9 no, full scope | 23.5 h | 30.5 h | CP-002, CP-003, CP-020a, CP-020b, CP-021 to CP-025b, gates |
| D9 yes, full scope | 18.5 h | 25.5 h | CP-010, CP-013, CP-016, CP-015, CP-022, CP-024, CP-025a, gates |
| D9 no, D10 slice | 16.0 h | 23.0 h | CP-002, CP-003, CP-020a, CP-020b, CP-021, CP-022, CP-023, gates |
| D9 yes, D10 slice | 13.5 h | 20.5 h | CP-010, CP-013, CP-016, CP-015, CP-022, gates |

About 37 h remain at 01:50 MST. Full scope without D9 leaves under 7 h for review rounds and
approvals, which is not enough. With D9 the art and content lane becomes the critical path, so the
fox model sheet approval inside CP-010 and the first live demo world in CP-015 are the two owner
waits that most move the date. The D10 cut line at 06:00 MST on 2026-11-11 keeps at least 9 h for
the gates either way.

## 12. Owner checkpoints (what you will be shown, and when)

1. Now: decisions D1 to D10.
2. Fox model sheet, then the seven-pose sheet (CP-010).
3. Cover kit, scene headers and object kit contact sheets (CP-012, CP-013).
4. The v3 component lab contact sheet, the product version of the design-system panel (CP-020b).
5. One side-by-side board per screen against its concept (CP-021 to CP-025b), posted by the
   supervisor in its report as each card passes review.
6. The final parity pack from GM-016 and the installed build from GM-017.

Every image you are shown is either a labelled art plate or a stamped capture of the running
product. No mockup is ever presented as the product.

## 13. Risks and tradeoffs

1. Art consistency is the biggest risk. Generated poses can drift (markings, proportions, palette).
   Mitigation: one model sheet, reference-image generation, a vision consistency check and owner
   approval. Fallback: commission a human illustrator for the fox master and use generation only
   for covers and scenes. Cost of that option is not measured.
2. Spend: at the caps, the art lane is 78 images (fox 24, textures 16, pack covers 9, scenes 9,
   object kit 20) and the six live worlds are up to 78 more (13 per world: 3 style boards, hero,
   cover, up to 6 sections, 2 optional scenes), so at most 156 generated images in all. The cost per
   image on the current provider is not measured; CP-010 records it from its first batch, and the
   supervisor stops a card that exceeds the D8 cap.
3. The v3 contract reverses earlier research-backed bans (shadow, texture, custom type). The owner
   ratified the concept, and contrast, legibility, one-primary and truth gates all remain. More
   material also means more room for noise, which is why the rubric gains a Craft dimension.
4. Module size and paint time: 1.34 MB today plus up to 2.5 MB of assets. The loader allows 16 MiB;
   older shells were already past their 512 KiB preview limit. CP-000 sets a paint baseline and
   CP-020a may not regress it by more than 150 ms.
5. Single-writer bottleneck on `desktop/plugin.js`: without D9 there are nine serial plugin cards
   (GM-012, CP-020a, CP-020b, CP-021 to CP-024, CP-025a, CP-025b), about 23.5 h of capped runtime
   against about 18.5 h with D9 to the last screen. D9 is a large mechanical change; the byte-identical build test is
   its guard, and it runs only while no other plugin writer is active.
6. Narrow route: the route can be about 400 to 460 px wide inside the Desktop window. The rail
   collapses to a band, the shelf to one card with a peek, the fox hides below 620 px. The concept
   never showed this width; SPEC-V3 must.
7. Dark mode, forced colors and 200 percent text are not in the concepts. The night-atlas palette
   and dark texture variants can look muddy; they have their own contrast pairs and captures.
8. Live generation can fail. CP-015 records validator rejections honestly; the shelf then shows
   fewer courses, never a fake one.
9. The old failure mode (plain text on a blank page) can return through a stale module or the
   wrong capture target. CP-000's stamped capture script is the only accepted evidence path.
10. All worker profiles run `deepseek/deepseek-v4.1-flash-1017`. Visual judgement and art direction
    are the weakest fit for a flash model. Option: pin `easel` runs and the visual-review runs to
    a stronger multimodal model with `--model` and `--provider` on those cards, trial it on CP-010
    and the CP-021 review, and keep it only if it lowers review rounds per merged card.
11. GM-008, GM-010 and GM-012 ship on v2 first and are restyled by CP-023, CP-025a and CP-025b.
    That cost is paid twice, but it keeps the plugin writer busy while the v3 base is built and lets
    the behavioural work merge under its own reviews now.
12. Deadline. Section 11 shows full scope fits only with D9 and few review rounds. D10 makes the
    cut explicit and dated instead of silent; the roadmap cards stay on the board, unlinked from
    the gates.
13. GM-020 can fail its own review. GM-012, and so the whole v3 plugin lane, waits on it; the
    supervisor's existing block-triage rules apply, and CP-000, CP-001, CP-002 and the art lane do
    not depend on it and keep running.

## 14. Open questions

- O1. Will you fund a human illustrator for the fox master if generated poses fail the
  consistency check, and at what cap?
- O2. May progress screenshots be uploaded to a public image host for the chat reports, as the
  concept reviews were, or should reports carry local paths only?
- O3. When the learner has a Hermes pet, may the fox and the pet share one viewport? Recommended:
  the fox guides Home, Discover and Classroom; the pet appears only at the course trailhead and the
  lesson close, never beside the fox.
- O4. Rail destinations: the concept shows Home, Discover, Classroom, Studio, Events. Recommended:
  Home, Courses, Workshop (Discover), Parent Studio, with Settings at the bottom; "Events" has no
  backing and is dropped.
- O5. The fox's "New course" tag: recommended rule is the CP-022 one (most recent course, under 14
  days old, no attempts yet, otherwise hidden).
- O6. Discover has three real packs today against eight cards in the concept. Recommended: lay out
  honestly for 1, 3, 7 and 8 items, and add the four demo courses to the Workshop only if a general
  course export exists by then.

## 15. Execution record

Approved 2026-11-10 02:50 MST and started the same night. Plan and card bodies are committed on
master (`de2d234`), reference pack under `docs/concept-parity/refs/`; the board carries every card
with its body, owner, reviewer, branch and parents.

| Card | Id | Owner | Status at creation | Branch |
|---|---|---|---|---|
| CP-000 | `t_f0be3189` | sentinel | running | `wt/cp-000-render` |
| CP-001 | `t_e4faed02` | quill | running | `wt/cp-001-spec` |
| CP-002 | `t_04aa5eb1` | quill | running | `wt/cp-002-tokens` |
| CP-003 | `t_8682d52f` | sentinel | todo | `wt/cp-003-gates` |
| CP-004 | `t_a2f39669` | sable | todo | `wt/cp-004-assets` |
| CP-005 | `t_4948bedf` | cinder | todo | `wt/cp-005-shelf-facts` |
| CP-006 | `t_02cb9495` | sable | todo | `wt/cp-006-split` |
| CP-010 | `t_ea64d10f` | easel | running | `wt/cp-010-fox` |
| CP-011 | `t_744b5a9d` | easel | running | `wt/cp-011-material` |
| CP-012 | `t_dbe44921` | easel | todo | `wt/cp-012-covers` |
| CP-013 | `t_ee2f8e3c` | easel | todo | `wt/cp-013-scenes` |
| CP-014 | `t_9438c09c` | lattice | todo | `wt/cp-014-pack-media` |
| CP-015 | `t_849e52d2` | lattice | todo | `wt/cp-015-demo-courses` |
| CP-016 | `t_483a0af4` | sable | todo | `wt/cp-016-world-v3` |
| CP-020a | `t_3793dc3d` | vellum | todo | `wt/cp-020a-scope` |
| CP-020b | `t_af9a7522` | vellum | todo | `wt/cp-020b-primitives` |
| CP-021 | `t_2a558085` | vellum | todo | `wt/cp-021-discover` |
| CP-022 | `t_ce7a8931` | vellum | todo | `wt/cp-022-home` |
| CP-023 | `t_047f8993` | vellum | todo | `wt/cp-023-classroom` |
| CP-024 | `t_41d66170` | vellum | todo | `wt/cp-024-course-home` |
| CP-025a | `t_1668762b` | vellum | todo | `wt/cp-025a-adopt` |
| CP-025b | `t_8337be56` | vellum | todo | `wt/cp-025b-adopt` |
| CP-026 | `t_a066bf25` | harbor | todo | `wt/cp-026-readme` |

Board edits made before dispatch (step 0): GM-020 linked as a parent of GM-012, GM-015 parked as
`scheduled` so the QA gate cannot open on a v2-only build. Gates extended: CP-015 and CP-021 to
CP-025b feed GM-015, CP-026 feeds GM-017, then GM-015 was released back to `todo`.

First wave dispatched at 02:54 MST: CP-000 (sentinel), CP-001 and CP-002 (quill), CP-010 and
CP-011 (easel), beside GM-020's review. Toolchain: `impeccable` installed in default, quill, cbqa,
vellum and the new `easel` profile; `coursebook-desktop-rig` and `coursebook-course-generation`
copied into all ten worker profiles at one sha (`2bdc72af...`, `a9e2a858...`).

Blocking issue handed to the manager: GM-010 is `blocked` (needs_input) because its tip is red
through the GM-008 ancestor. Decision taken: merge `wt/gm-020-fix-invariants` into
`wt/gm-010-engagement-ui` once GM-020 passes review, then unblock GM-010 for quill to re-review.
