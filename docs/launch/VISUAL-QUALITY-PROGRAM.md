# Visual quality program - Coursebook

Status: owner-approved 2026-11-11.
Scope: every Coursebook surface, including user-generated lessons that choose Game mode.
Read with: `docs/launch/UI-PROGRAM.md`, `docs/launch/UI-DECISIONS.md`,
`docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`, `docs/concept-parity/ART-BIBLE.md`,
`docs/ART-DIRECTION-COVERS.md`, and `docs/GM-CONCEPT-PARITY-RUBRIC.md`.

## 1. Decision

The product has two visual lanes and must keep them separate:

- **Press Plate** is the procedural, flat printed field used for pack management. It stays as the
  pack cover lane. It is not a product-surface illustration.
- **Display Plate** is the painted, textless art used on product surfaces: Home, Discover,
  Classroom, Course home, and Game mode. It is a separate asset type from a pack cover.

No product surface may use a Press Plate as its hero, display cover, collectible, lesson scene, or
world plate. No screen may be mostly DOM text and buttons with a flat card band standing in for
illustration.

The visual building is **kit-first and generation-optional**:

1. Every visual grammar has a curated kit of textless display plates, materials, frames, objects,
   and a fox pose map.
2. Built-in screens and user-generated Game courses use the same kit registry.
3. Image generation adds subject-specific plates when a provider is available. It never replaces
   the kit and never becomes a requirement for Game mode.
4. If generation is unavailable or fails the quality critic, the curated kit is the fallback. If
   no approved kit exists for the course's grammar, Game mode is unavailable; the course stays in
   Textbook mode. There is no flat Game fallback.

## 2. Surfaces and required assets

| surface | reference | kit and assets | acceptance |
|---|---|---|---|
| Home (global and course) | `docs/concept-parity/refs/home.png` | field-atlas hero, four display covers, paper/grain, wood planks, shelf, fox clock pose, tag, clock | one Home writer; covers are display plates; header band present; 1344x768 |
| Discover / Workshop | `docs/concept-parity/refs/discover.png` | field-atlas banner, eight collectible display plates, fox point pose, badges | banner and cards are painted plates, not typographic plates |
| Classroom lesson | `docs/concept-parity/refs/classroom.png` | field-atlas lesson scene, section plates, stamp stepper, challenge card, fox read pose | lesson scene is a display plate; fallback is the section plate, never flat text |
| Course home | `docs/concept-parity/refs/map.png` | course-map base, trail, buildings, shelf, fox | map and shelf are plates; no plain course card list |
| Design System | `docs/concept-parity/refs/system.png` | card anatomy, badges, palette, pose map, materials, object kit | specimen sheet is the source of truth |
| Parent Studio | system-derived | same kit, no parity frame | composed from the system, not scored as a reference frame |
| Game mode | `docs/GM-CONCEPT-PARITY-RUBRIC.md` | approved world kit, XP chip, challenge card, lesson scene | world approved; no fake XP outside Game |
| Homework and print | system-derived | type and print grammar, no illustration dependency | selectable text, no color-only answers |
| Settings and Studio | system-derived | same kit | no new visual language |

## 3. Visual kernel and kit registry

Create `assets/visual-kits/<grammar>/` for each policy grammar:

```
kit.json                 grammar, version, palette, medium, composition, roles, hashes
hero/                    hero plates and crops
cover/                   display-cover plates, 4:5 and 3:2
section/                 section or chapter plates
lesson-scene/            optional lesson scenes, max two per course
collectible/             Discover collectible plates
objects/                 clock, tag, stamp, badge, shelf, frame
fox/                     pose references and crops
specimens/               Design System specimens
```

The registry is a manifest, not a directory convention only. `kit.json` names every asset, size,
sha256, provenance, grammar, role, and fallback. A screen card reads the manifest; it does not
invent a path.

The shared visual kernel is the material and type layer used by every kit:

- paper grain, parchment vignette, wood plank, shelf plank, card stock;
- the six-step v3 type scale and the display/heading roles;
- card anatomy: cover window, title, subject chip, meta row, progress bar;
- badges, stamps, tags, seals, and the object kit;
- the painted A1 fox pose map, scale, and safe areas;
- focus, motion, reduced-motion, and contrast rules.

The Design System screen is the specimen sheet for this kernel. It is built before any screen
card that consumes it.

## 4. Screen recipe and gates

Each screen has a scene recipe, not a box list:

- paper and ground;
- scene plate or system-derived composition;
- architecture and props;
- collectible or card band;
- character;
- chrome and header;
- type and labels;
- depth, shadow, texture, safe areas;
- states: default, hover, focus-visible, loading, empty, reduced motion.

Gates for every built-in screen:

- **Gate -1 Lane.** Owner approves the lane and the display-plate list.
- **Gate 0 Asset sheet.** Every hero, cover, collectible, section, lesson scene, object, and
  character pose exists at 2x, is textless, has provenance, and is approved. No card starts on a
  missing or placeholder asset.
- **Gate 1 Scene recipe.** Director approves the layer stack, composition, focal point, and asset
  paths.
- **Gate 2 Mechanical.** 1344x768 plus 1049/900/460; computed styles; `currentSrc` sha256; natural
  size at least 2x rendered; both fonts; contrast; axe; states.
- **Gate 3 Region critic.** Independent vision reviewer scores 600x600 crops at 2x for scene,
  cards, fox, type, and material; returns a delta list.
- **Gate 4 Director and owner.** Rubric average at least 4; hard floors on composition,
  illustration, material, and character; masked SSIM for reference screens; anti-cheat clean.
- **Gate 5 Installed capture.** Build, install, relaunch, and capture the installed plugin with
  real course data. A proof HTML alone is not evidence. The one command and its refusal rules are
  in §9.
- **Gate 6 Cross-screen cohesion.** A contact sheet of every screen; same palette, card anatomy,
  type, fox scale, and motion. A screen that passes alone but breaks the set fails.

Objective anti-flat tripwires, recorded per scene region: painted coverage, flat-fill ratio,
unique colours and edge density, number of real assets, text-area-to-art ratio, and CSS shapes
standing in for art. They force review; they do not replace the rubric.

## 5. Roles and models

- **Scene builder:** a strong vision model, Sonnet 5.5 or Opus, for hero scenes and composition.
- **Integrator:** the cheap model for wiring, tests, and mechanical changes.
- **Director:** Opus at high reasoning, writes the scene recipe and the verdict.
- **Region critic:** independent vision model, JSON scores only.
- **Verifier:** atlas or cbqa, fresh run, never the writer.
- **Owner:** approves the lane, the kit asset sheets, and the final installed screen.

No same-model self-review. No cheap model is asked to invent the visual language.

## 6. Self-generated lessons in Game mode

A user-generated lesson that chooses Game mode uses the same visual building:

1. `course.create` records `presentation_mode = game`; `world_job_on_create` queues the world.
2. The backend builds a typed `world_brief` from the approved plan and selects a grammar.
3. The user chooses one of three style directions. With a provider, the directions are generated
   from the kit reference. Without a provider, they are curated kit variants.
4. The kit job produces hero, cover, section plates, and up to two lesson scenes. It uses the kit
   as the style reference. Every generated plate passes the world quality critic before approval.
5. The user sees an assembled Home, Discover, and Classroom preview with real text and presses
   `Use this world`. `world.approve` stores the assets and `course.mode.set` switches the mode.
6. The lesson generation job runs against the approved world. Classroom resolves the
   `lesson_scene` for the lesson, then the section plate, then the kit background. It never falls
   back to flat text panels.
7. Home and Discover use the approved world cover as the display cover; pack management continues
   to use the Press Plate.

If generation is unavailable, the curated kit provides the world and Game mode remains available.
If no approved kit exists for the grammar, Game mode is unavailable and the course stays in
Textbook mode. A partial world is never approved.

The full contract is in `docs/launch/GAME-MODE-VISUAL-KIT.md`.

## 7. Sequence

1. **VQ-001** visual contract, lane, and plugin asset audit.
2. **VQ-002** field-atlas kit and Home display covers.
3. **VQ-003** shared visual kernel and Design System specimens.
4. **VQ-004** Game-mode world kit backend: curated fallback, lesson scenes, and the world quality
   critic.
5. **VQ-005** Game-mode World Studio and classroom rendering: preview, lesson-scene resolution,
   and display covers.
6. **VQ-006** real-data installed capture harness.
7. **VQ-007** Discover, Classroom, and Course home display plates.
8. **VQ-008** Curated kits for the remaining seven grammars. This is the provider-free coverage
   bar for every self-generated Game course.
9. **Home quality** (existing `t_831137dd`) amended to use display covers, the header band, and
   the asset preflight.
10. **Discover**, **Classroom**, **Course home** quality cards, created only after their asset
    sheets are approved.
11. **Parent Studio, Game, Homework, Studio, Settings** system-derived cards.
12. **Cross-screen cohesion** and final installed capture.

The sequence is asset first, screen second. No screen card starts before its kit and asset sheet
are approved.

## 8. Acceptance

The program is complete only when:

- every surface in section 2 is installed with real data;
- no product surface uses a Press Plate as illustration;
- Home, Discover, Classroom, and Course home each have a scene plate, display covers or
  collectibles, and a passing rubric;
- a user-created Game course can choose a grammar, receive a curated or generated world, approve
  it, and open a lesson with a lesson scene, with no provider required for the curated path;
- the world quality critic rejects text-bearing, generic, or unsafe plates;
- the cross-screen contact sheet passes;
- the owner approves the installed result.

## 9. Gate 5 harness — the one capture command

Every screen card captures through `scripts/vq-capture.sh`. There is no second door: a frame from a
proof HTML, a component-lab render harness, a design fixture or a starter template is not evidence,
and the judge refuses it.

```bash
scripts/vq-capture.sh
#   --state <dir>        disposable rig (default ~/.hermes/coursebook-test-vq006)
#   --out <dir>          capture output (default docs/visual-review/vq-006)
#   --widths "1344 1049 900 460"
#   --destinations "home discover course-home classroom world-studio design-system"
#   --game-course crs_…  the user-created Game course to capture
#   --reuse              drive an already-running rig instead of building one
#   --allow-no-game      report a missing Game course instead of stopping before capture
#   --keep-window        leave the rig running for a follow-up run
```

What it does, in order:

1. installs the current checkout into a private `HERMES_HOME` (`scripts/install-local.sh`), starts
   an isolated backend on that home, and launches one dev-Electron window with its own CDP port and
   `connections.json` — the operator's window, profile and gateway are never touched;
2. seeds the real library: the three bundled packs through the product's own grant → preview →
   import path (`scripts/vq-library.py` → `scripts/seed-demo-course.py`), then reads `world.read` for
   every library item and requires one course whose stored `presentation_mode` is `game` with an
   approved world. It does not create a Game course and never photographs a Textbook course as Game;
3. captures Home, Discover, Classroom, Course home, World Studio and the Design System at the
   1344x768 window and the 1049, 900 and 460 route widths, one PNG and one JSON cell per cell;
4. writes `manifest.json`, `MANIFEST.md` and `contact-sheet.png` beside the frames, and prints the
   absolute output directory and a short manifest;
5. exits non-zero when a cell fails.

The judge is `scripts/vq-manifest.py`; the camera is `scripts/vq-capture.mjs`. A cell fails when:

- the page is not live (a `file:` URL, a proof fixture script, a `[data-cb-proof]` marker);
- the requested destination did not render, the route has a render-error marker, fonts did not
  load, or the installed plugin has no such surface (the Design System on a build that never mounted
  one, for example);
- a required display role is missing: four Home display covers, eight Discover collectibles, a
  Classroom lesson scene, a Course-map plate, a World plate, a Design System specimen;
- an image is a placeholder (incomplete, no natural size, empty `currentSrc`, a known blank name);
- an image is below 2x its rendered size;
- an image is a data URI unless it is a hashed bundled brand asset from
  `desktop/cb-assets.generated.js` (the fox, materials and object kit ship that way by contract);
- an image's bytes match a bundled pack cover, which proves a Press Plate is standing in as
  product-surface illustration;
- a `background-image` layer breaks any of the rules above. Layers are judged with the same
  classification as an `<img>`, so an asset cannot escape by being delivered as CSS; the exceptions
  are stated, not silent. The 2x rule is applied per axis: an axis is exempt only when the layer
  both repeats on it and paints it at the file's own size (`background-size: auto` or a length), so a
  `repeat` + `auto` grain tile is decoration, while `cover`, `contain` and percentage sizes are
  judged on the axes they stretch even when the layer also repeats. A record with no repeat mode
  exempts nothing. No background layer satisfies a display role (a role is a placement the surface
  must render as an image);
- the PNG on disk does not hash to the sha256 the cell record claims.

`manifest.json` separates three states, and `summary.ok` is false if any is non-zero: **passed**
(judged, no finding), **failed** (a frame was captured and the judge refused it), and **never
captured** (no cell record at all — nothing to judge). A failed frame is never counted as missing.

Each cell record carries, for every image in the route: `selector`, `currentSrc`, natural width and
height, rendered width and height, `sha256`, the resolved bundled-asset path when one exists, and
whether the row is a placeholder or a Press Plate. Background-image layers are recorded and judged
the same way, with `background-repeat` and `background-size` alongside, and the manifest prints which
axes the 2x rule covered for each layer (`x`, `y`, or none when it tiles at natural size), so a tiling
layer is distinguishable from an upscaled one. A screen card reads the manifest; it does not need a
browser of its own.

**Measured on `80a81fd7`, plugin sha `251a3948…`, 2026-11-11** (16 of 24 matrix cells captured, 0
pass, 16 captured and failed, 8 never captured — classroom ×4 and world-studio ×4): no Home cell has a
display cover (0 of 4). At 1049/900/460 the two course covers are the bundled pack Press Plates
(`cover-3x2.png` of the Japanese and technical packs); at 1344 the Home scene draws no course cover
art at all. The fox ships at 128 px and is rendered at 220 px on the wide Home, below 2x. Discover
has 0 of 8 collectibles, its banner is a data-URI 864 px plate under 2x, and three Press Plates sit
on the surface. On the twelve cells that paint the night background, the vignette layer is a 96×96
asset stretched with `background-size: cover` across the route (ratio 0.07–0.21, below 2x on every
one); the grain and shelf-plank layers tile and are exempt from the ratio rule. Course home is DOM
type, one inline contour and buttons with no image asset. The Design System surface is not mounted,
and no course in the seeded library has an approved Game world, so Classroom and World Studio were
never captured. Every one of those is a Gate 0/2 gap the harness is supposed to expose, not a harness
failure to hide.

