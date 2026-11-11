# Game-mode visual kit - built-in and user-generated courses

Status: implementation contract for VQ-004. Read with
`docs/launch/VISUAL-QUALITY-PROGRAM.md`, `docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md` sections 4, 6
and 10C, and `docs/launch/UI-DECISIONS.md`.

## 1. Goal

A user-created course that chooses Game mode must use the same visual building as a built-in
course. It must not fall back to flat text panels, Press Plates, or typographic card fields.

The mechanism is a **visual kit** per grammar. The kit is curated once, approved once, and reused
by every course that selects that grammar. Image generation adds subject-specific plates when a
provider is available; it is not a requirement for Game mode.

## 2. Existing seams

- `coursebook/world.py` owns the grammar policy, `world_brief`, prompt construction, the
  `world_concepts` and `world_kit` job stages, and the `world.*` handlers.
- `course_worlds` stores `brief_json`, `concepts_json`, `selected_concept_id`, `style_hash`,
  `kit_hash`, `approved_hash`, and the world state.
- `world_assets` already supports roles `hero`, `cover`, `section`, and `lesson_scene`, with
  `section_key` and `artifact_id`.
- `desktop/src/97-world.js` is World Studio. `desktop/src/70-learning.js` resolves the classroom
  scene from `world.read`; today it uses a section plate.
- `library_item.cover_artifact_id` already uses an approved world cover when one exists.
- `course.mode.set` switches the course only after the world is approved.

The missing pieces are: a curated kit, a kit reference in the brief, `lesson_scene` generation
and resolution, a post-generation quality critic, and a no-provider path.

The current code confirms each gap:

- `coursebook/world.py` `build_kit_prompts` builds only `hero`, `cover`, and `section` prompts; it
  has no `lesson_scene` role.
- `coursebook/world.py` `_missing_kit_roles` requires hero, cover, and sections; it has no
  lesson-scene requirement or fallback rule.
- `coursebook/world.py` `_kit_stage` sets `provider_unavailable` and stops when no image provider
  is configured, instead of using a curated kit.
- `world_assets.textless` is written as true from the prompt. There is no OCR or vision critic,
  so a plate with baked letters can still reach approval.
- `desktop/src/70-learning.js` `classroomSceneFromWorld` returns `artifactId: null` when no
  section plate matches, and the classroom then renders a typographic plate that states the
  course title. That is the flat fallback this program removes for approved Game courses.

## 3. Visual kit registry

Each grammar gets a registry entry under `assets/visual-kits/<grammar>/` with `kit.json`. The
manifest names:

- grammar, kit version, palette, medium, composition, and the art-bible reference;
- style variants for the three concept directions;
- hero, display cover, section, lesson-scene, and collectible plates;
- shared objects, frames, badges, materials, and fox pose references;
- every asset's path, dimensions, sha256, provenance, role, and fallback.

The kit is a **product asset**, not a prompt. It is reviewed once against the visual rubric and
then used by built-in screens and generated courses. A course does not create a new kit.

Curated kit files are registered as content-addressed artifacts with
`source = curated_kit` and `kit_id = <grammar>@<version>` in provenance, so `world_assets`
continues to store `artifact_id` and the renderer keeps one read path.

## 4. World brief and generation

Add optional `visual_kit_id` to `WorldBrief` and `world_brief`. If absent, derive it from the
selected grammar. Store it in `course_worlds.brief_json`; no schema migration is required.

At `world.generate(stage=concepts)`:

- with an image provider: build the three style boards from the kit reference and the course
  motifs;
- without a provider: build three curated kit variants (palette or composition directions);
- run the world quality critic on generated boards; a failed board is not offered.

At `world.generate(stage=kit)`:

- build hero, display cover, one section plate per section (max six), and up to two lesson
  scenes when the brief requests them;
- with a provider: generate from the selected style board and the kit reference;
- without a provider: register the curated kit plates as artifacts and persist them as world
  assets;
- run the critic on every generated plate; retry once; fall back to the curated kit role; if
  there is no approved fallback, keep the world failed and the course in Textbook mode.

`world_assets` already has the `lesson_scene` role. `_missing_kit_roles` continues to require
hero, cover, and every section plate. Lesson scenes are optional; if requested, they must pass
the critic or the kit fallback.

## 5. Lesson scene resolution

`desktop/src/70-learning.js` resolves the classroom scene in this order:

1. `world_assets` role `lesson_scene` whose `section_key` matches the lesson or section;
2. `world_assets` role `section` whose `section_key` matches the section;
3. the grammar kit's lesson-scene background, or the section plate;
4. a textless material field. Never a flat text panel, never a Press Plate.

The scene is a mounted plate with the same mat, rule, and type as the built-in Classroom. A
generated scene is never an instructional media replacement; the lesson text, checks, and
evidence remain DOM.

## 6. World quality critic

The critic is a separate stage after each generated plate. It is not the generator and it is not
the user.

Hard fails:

- any OCR-readable letter, number, word, logo, watermark, or UI chrome;
- a subject-swap test pass: the plate could serve an unrelated course with no motif change;
- a grammar mismatch or a generic fantasy skin;
- a depicted procedure, torque value, measurement, wiring, medication, or hazard presented as
  authority;
- a plate with no quiet field for the real headline and controls.

Soft scores: palette and medium consistency, composition, subject-specific motifs, textless
cleanliness, legibility underneath type. A generated plate must pass the hard checks and the
kit's minimum score before it can enter `world_assets`.

If the critic is unavailable, the generated path is unavailable and the curated kit is used.
Curated kits are approved once and are not re-critiqued per course.

## 7. User-generated lesson flow

1. The user creates a course with `presentation_mode = game`.
2. The backend builds the brief, selects the grammar, and stores the `visual_kit_id`.
3. World Studio shows three directions, generated or curated.
4. The kit job produces hero, display cover, section plates, and optional lesson scenes.
5. The critic checks generated plates; failures fall back to the kit.
6. The user sees an assembled Home, Discover, and Classroom preview with real text and approves
   `Use this world`.
7. `world.approve` stores the approved hash; `course.mode.set` switches the course to Game mode.
8. Lesson generation runs against the approved world. The classroom resolves the lesson scene or
   section plate at read time.

If the user creates a lesson inside an existing Game course, it reuses that course's approved
world. No new world job and no new image spend are required. If the user imports a Textbook course
and switches to Game, the same World Studio flow applies.

If no approved kit exists for the grammar, Game mode is unavailable and the course stays in
Textbook mode. A flat Game fallback is forbidden.

## 8. Contracts and storage

- `world_brief` gains optional `visual_kit_id`; `WorldBrief` reads it and defaults from grammar.
- `world.read` returns optional `kit_id` and per-asset `source` (`curated_kit` or `generated`) so
  the UI can show provenance. If the current `cb.rpc` shape forbids additional response keys, add
  them in the next additive contract revision; the world state and asset ids do not move.
- `world_assets` keeps its current columns. `source` and `kit_id` live in artifact provenance;
  `_asset_views` may expose them read-only.
- `library_item.cover_artifact_id` continues to use the approved world cover; no new field.
- No lesson, attempt, evidence, export, or pack read joins the world tables. World art remains
  orientation only.

## 9. Tests and acceptance

- A game course with a fake provider produces a full kit and an approved world.
- A game course with no provider produces a curated kit and still switches to Game mode.
- A generated plate with OCR text fails the critic and is replaced by the curated fallback.
- A course with two lesson scenes resolves `lesson_scene` before `section`, and a course without
  one resolves the section plate.
- A user-generated lesson in an existing Game course uses the course world with no new world job.
- Home and Discover use the approved display cover, not a Press Plate.
- The classroom never renders a flat text-only scene when an approved plate exists.
- `world.approve` refuses partial worlds and never approves a failed plate.
- The installed plugin, not a proof HTML, is captured with real course data.

## 10. Non-goals

- No per-lesson image generation beyond the two-scene budget.
- No user-drawn or CSS-drawn substitute for a missing plate.
- No generated image on a technical procedure as instruction or measurement.
- No fake XP, ratings, progress, or evidence from the world.
- No change to the Press Plate pack-cover lane.
