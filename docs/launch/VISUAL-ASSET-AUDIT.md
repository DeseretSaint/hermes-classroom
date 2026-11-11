# Visual asset audit - 2026-11-11

Status: first audit for the owner-approved visual quality program.
Read with `docs/launch/VISUAL-QUALITY-PROGRAM.md` and
`docs/launch/GAME-MODE-VISUAL-KIT.md`.

## 1. Lane decision

- **Pack management:** Press Plate, flat printed field. It remains the pack-cover lane.
- **Product surfaces:** Display Plate, painted and textless. Home, Discover, Classroom, Course
  home, and Game mode use this lane.
- No product surface may use a Press Plate as a hero, display cover, collectible, lesson scene, or
  world plate.
- No screen may be mostly DOM text and buttons with a flat card band standing in for
  illustration.

## 2. Current inventory

### Approved and usable

- Fox: eight painted poses (`cheer`, `clock`, `model-sheet`, `point`, `read`, `sleep`, `think`,
  `wave`) at 64, 128, 256, 512 and source size. Good material and scale control.
- Materials: paper grain, parchment vignette, card-stock fibre, and wood plank, light and dark.
- Objects: clock, medallion rim, passport tray, shelf plank, stamp rim, tag, ticket. Painted
  object kit, good for display surfaces.
- Painted cover masters: three masters, `japanese`, `parent`, `technical`, each with 4:5 and 3:2
  crops. These are course-specific masters, not a general display set.
- Bundled pack covers: three packs, each with Press Plate `cover-4x5.png` and `cover-3x2.png`.
  These are the only bundled pack covers in the tree.

### Partial or missing

- `assets/art/scenes/discover-banner.png` is 1024x233. It is a lantern/cafe slice with a large
  blank sky, not a full Discover banner.
- `assets/art/scenes/lesson-cafe.png` is 1024x576. It is a sparse cafe interior, not the full
  classroom scene in the reference.
- `assets/art/scenes/course-map.png` is 1024x576. It is a map fragment, not a full course map
  with trail, buildings, and shelf.
- There is no Home hero plate. Home is composed from DOM, material, fox, and objects.
- There are no display covers for the four Home courses in the proof. The CP-053 worktree's
  `.worktrees/t_5e22c918/design/home-scene.html` uses mismatched existing covers: `Auto Repair
  Fundamentals` with a Japanese cover, `Astronomy` with a parent cover, and so on. The proof is
  not real-data evidence.
- There is no `assets/visual-kits/` registry.
- There is no Design System specimen sheet.
- There are no section plates, collectible display plates, stamps, or challenge-card art for the
  v3 screens.
- There is no Game-mode curated kit. `coursebook/world.py` generates hero, cover, and section
  plates when an image provider exists; it does not generate lesson scenes and has no curated
  fallback. `world_assets.textless` is asserted from the prompt, not verified: there is no OCR or
  vision critic in the code, so a generated plate with baked letters can reach approval.

## 3. Surface matrix

Status values: approved, partial, placeholder, missing, forbidden. "System" means the surface is
composed from the shared kernel and is not scored as a reference frame.

### Home global and Home course

| asset | status | path or gap |
|---|---|---|
| hero scene | partial | DOM composition in `desktop/src/30-home.js`; no kit hero plate |
| display covers x4 | missing | no four-course display set; current proof uses mismatched covers |
| paper/grain | approved | `assets/art/material/paper-grain-*` |
| wood and shelf | approved | `wood-plank-*`, `objects/shelf-plank.png` |
| fox clock | approved | `assets/art/fox/fox-clock.png` |
| tag and clock | approved | `objects/tag.png`, `objects/clock.png` |
| header band | missing | 86px brand, nav, and utility band is not in the Home spec |
| type scale | partial | v3 tokens exist; Home card is still `t_c4bfc678` |

### Discover and Workshop

| asset | status | path or gap |
|---|---|---|
| banner | partial | `scenes/discover-banner.png`, 1024x233, mostly blank |
| collectible display plates x8 | missing | no eight-card display set |
| fox point | approved | `assets/art/fox/fox-point.png` |
| badges | missing | no v3 badge display sheet |
| card anatomy | partial | v3 primitives exist; no approved Discover specimen |

### Classroom

| asset | status | path or gap |
|---|---|---|
| lesson scene | partial | `scenes/lesson-cafe.png`, sparse 1024x576 |
| section plates | missing | no grammar section set |
| stamp stepper | missing | stamps exist as objects, not as the stepper set |
| challenge card | missing | no display plate |
| fox read | approved | `assets/art/fox/fox-read.png` |
| type and focus | partial | shared tokens; no classroom specimen |

### Course home

| asset | status | path or gap |
|---|---|---|
| map base | partial | `scenes/course-map.png`, fragment |
| trail and stops | missing | no trail, stop, or building set |
| shelf | partial | object shelf plank only; no composed shelf |
| fox point | approved | `assets/art/fox/fox-point.png` |

### Design System

| asset | status | path or gap |
|---|---|---|
| specimen sheet | missing | no rendered v3 specimen |
| card anatomy | partial | primitives exist; no approved sheet |
| palette, type, materials | partial | tokens and textures exist; no one sheet |
| pose map and object kit | approved | fox and objects exist; not presented as a kit |

### Parent Studio

System-derived, no parity frame. Current state: no display kit, no composition recipe. Needs the
shared kernel and a system-derived scene, not a reference score.

### Game mode

| asset | status | path or gap |
|---|---|---|
| generated hero, cover, sections | partial | `coursebook/world.py` and `97-world.js`; provider-dependent |
| curated kit | missing | no `assets/visual-kits`; no provider-free path |
| lesson scenes | missing | `world_assets.lesson_scene` exists, but `build_kit_prompts` does not produce one |
| world critic | missing | no post-generation textless or subject-fit check |
| display cover | partial | approved world cover feeds `library_item.cover_artifact_id`; no display plate for built-ins |
| classroom scene resolution | partial | `70-learning.js` uses a section plate; no lesson-scene fallback |

### Homework and print

System-derived. Type and print grammar only; no illustration dependency. Needs a specimen, not a
display plate.

### Studio and Settings

System-derived. Same kernel; no new visual language. Needs a specimen, not a new asset set.

## 4. First display plate list

These are the first assets that unblock a screen card.

### Home

- four display covers at 4:5 (640x800) and 3:2 (1200x800), textless, one per real Home course;
- one field-atlas hero plate, 1344x768, textless, with a quiet field for the title;
- optional alternate crops for the 1049, 900, and 460 widths;
- no baked title, no pack-cover text, no software UI.

### Discover

- one full banner, at least 1344x768 or a 1344x420 band, textless;
- eight collectible display plates at 3:2, textless, one per real collectible;
- badge sheet and card frame specimens.

### Classroom

- one full lesson scene at 1344x768, textless, cafe/lantern district;
- section plates for the lesson sections, 3:2 or 16:9;
- stamp stepper set and challenge-card frame.

### Course home

- one full map base at 1344x768, textless;
- trail, stop, building, and shelf layers;
- no baked labels or numbers.

All plates are textless. All type and controls are DOM. No plate is a screenshot of the product.

## 5. Kit manifest shape

The registry lives at `assets/visual-kits/<grammar>/kit.json`. It is the only manifest format.

```json
{
  "grammar": "field_atlas",
  "label": "Field atlas",
  "version": 1,
  "art_bible": "docs/concept-parity/ART-BIBLE.md",
  "palette": ["paper", "ink", "ochre", "lamp", "field"],
  "medium": "painted gouache on paper",
  "composition": "route through lantern district; quiet left third",
  "roles": {
    "hero": [{"id": "home-hero", "path": "hero/home-hero.png", "size": [1344, 768], "sha256": "...", "source": "curated_kit"}],
    "cover": [{"id": "course-a-4x5", "path": "cover/course-a-4x5.png", "size": [640, 800], "sha256": "...", "source": "curated_kit"}],
    "section": [],
    "lesson_scene": [{"id": "cafe", "path": "lesson-scene/cafe.png", "size": [1344, 768], "sha256": "...", "source": "curated_kit"}],
    "collectible": [],
    "object": [],
    "fox": []
  },
  "fallbacks": {
    "lesson_scene": ["section", "background"],
    "cover": ["course-master", "pack-cover"]
  }
}
```

- `source` is `curated_kit`, `generated`, or `pack_cover`.
- `kit_id` is `<grammar>@<version>`.
- Every asset has a sha256 and provenance. A worker may not add an unlisted path.
- The shape matches the existing `world_assets` roles; no schema migration is needed.

## 6. Card graph

- **VQ-001** this audit. Done when this file and the program docs agree.
- **VQ-002** field-atlas kit and Home display covers. Parent: VQ-001.
- **VQ-003** shared visual kernel and Design System specimens. Parent: VQ-002 and CP-005f.
- **VQ-004** Game-mode world kit backend: curated fallback, lesson scenes, quality critic.
  Parent: VQ-002.
- **VQ-005** Game-mode World Studio and classroom rendering. Parent: VQ-004.
- **VQ-006** real-data installed capture harness. Parent: VQ-001.
- **VQ-007** Discover, Classroom, and Course home display plates. Parent: VQ-002.
- **VQ-008** Curated kits for the remaining seven grammars. Parent: VQ-002. Create after the
  field-atlas kit format is reviewed; this is the provider-free coverage bar for every grammar.
- **Home quality** existing `t_831137dd`, parent VQ-002 and VQ-003.
- Discover, Classroom, and Course home quality cards are created only after VQ-007 and their
  asset sheets are approved.
- Parent Studio, Game, Homework, Studio, and Settings specimens are created after VQ-003.
- Cross-screen cohesion is the final gate.

No screen quality card is created before its display assets are approved.
