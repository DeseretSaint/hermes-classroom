# CP-031b — World Studio and the Game/Textbook mode chrome shipped-string sweep

Card: **CP-031b** (`t_adc9bdee`). Closes **GAP-30** for `desktop/src/97-world.js` (all 1097 lines).
Docs only; no product string changed.

Row citations in this file were re-derived on the strings at `475efefc`: each `file:line` is the
line that carries the row's own words today. Section headings keep a coarse range as navigation;
the row citation is the authoritative anchor.

**Surface:** World Studio (GM-004) and the durable-mode chrome the course home paints. `GAP-27` owns
the section; new gap ids are named where a category had no gap at all.

Same extraction method as `CP-031-sweep-parent-studio.md`: the whole file was lexed and every
literal reviewed; non-visible literals (RPC method names, `data-cb-*` values, grid-template strings,
ids, `HOST_UNAVAILABLE` and other error codes) are excluded by class, not by guess.

## 1. Mode chrome and the course-home plate (`97-world.js:9-22`, `202-379`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Course world | `97-world.js:9` | default | `GAP-27 world.label` |
| World / Game / Textbook (mode words) | `97-world.js:12` | default | `GAP-27 world.mode.*` |
| Change mode | `97-world.js:13` | default | `GAP-27 world.change_mode` |
| Course settings | `97-world.js:14` | default | `GAP-27 world.course_settings` |
| World not approved yet | `97-world.js:15` | empty | `GAP-27 world.not_approved.badge` |
| This course reads as Textbook until its world is approved. Your lessons and plan are unchanged. | `97-world.js:17` | empty | `GAP-27 world.not_approved` |
| Open World Studio | `97-world.js:18` · `97-world.js:18, 1017` | default | `GAP-27 world.open_studio` |
| Use Textbook mode | `97-world.js:19` · `97-world.js:19, 897` | default | `GAP-27 world.use_textbook` |
| This backend does not report a course world yet. | `97-world.js:20` · `97-world.js:20, 587` | error | `GAP-27 world.no_wire` |
| The course world could not be read | `97-world.js:21` · `97-world.js:21, 598` | error | `GAP-27 world.read_error` |
| The art for this plate is not available; the text label stands in for it. | `97-world.js:22` | error | `GAP-27 world.plate_missing_art` |
| Loading the plate | `97-world.js:202` | loading | `GAP-27 world.plate.loading` |
| · saving | `97-world.js:242` | loading | `GAP-27 world.mode.saving` |
| This course (title fallback) | `97-world.js:333` · `97-world.js:335, 774` | empty | `GAP-27 world.title_fallback` |
| Review the world | `97-world.js:345` | default | `GAP-27 world.review` |
| Section (plate fallback label) | `97-world.js:73` | empty | `GAP-27 world.section_fallback` |

## 2. World state words (`97-world.js:49-57`)

An enum→copy map with no deck rows. The contract's `world.read` states are reflected one-for-one.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Not started / Choosing directions / Three directions / Direction chosen / Building the world / Ready to approve / Approved / Could not finish / Unavailable | `97-world.js:48-57` | default | `GAP-27 world.state.{not_requested,concepts_generating,concepts_ready,style_selected,kit_generating,kit_ready,approved,failed,unavailable}` |

The map is complete against the contract: `course_world.state` declares exactly those nine values
(`contracts/rpc.v24.json`, `$defs.course_world.properties.state`), and each has a shipped word.

## 3. World archetypes — a fixed enum → name + description map (`97-world.js:27-45`)

The eight archetypes are a closed backend enum; the name and the one-line description are product
copy, and the description makes a claim about what the art is.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Field atlas / Workshop manual / Observatory / Kitchen table / Archive desk / Studio bench / Lab bench / Instrument board | `97-world.js:27-34` | default | `GAP-27 world.archetype.{field_atlas,workshop_manual,observatory,kitchen_table,archive_desk,studio_bench,lab_bench,instrument_board}` |
| Maps, lanterns and a field notebook — a place to travel through the subject. | `97-world.js:38` | default | `GAP-27 world.archetype.field_atlas.desc` |
| A service bay, tool wall and manual pages — orientation beside the procedure. | `97-world.js:39` | default | `GAP-27 world.archetype.workshop_manual.desc` |
| Star charts, instruments and an observation log. | `97-world.js:40` | default | `GAP-27 world.archetype.observatory.desc` |
| A work surface, ingredient cards and a recipe board. | `97-world.js:41` | default | `GAP-27 world.archetype.kitchen_table.desc` |
| Documents, stamps, maps and index cards. | `97-world.js:42` | default | `GAP-27 world.archetype.archive_desk.desc` |
| Materials, swatches and a sketchbook. | `97-world.js:43` | default | `GAP-27 world.archetype.studio_bench.desc` |
| Glassware, a lab notebook and labelled stations. | `97-world.js:44` | default | `GAP-27 world.archetype.lab_bench.desc` |
| Instruments, graph paper and a blackboard. | `97-world.js:45` | default | `GAP-27 world.archetype.instrument_board.desc` |

## 4. World Studio — progress, failure and the direction editor (`97-world.js:443-940`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Queued | `97-world.js:494` | loading | `GAP-27 world.job.queued` |
| The world job did not finish. | `97-world.js:451` | error | `GAP-27 world.job_failed` |
| That did not finish | `97-world.js:670` | error | `GAP-27 world.job_failed_title` |
| Reading the course world / Nothing already saved is lost. | `97-world.js:610`, `97-world.js:616` | loading | `GAP-27 world.reading` |
| Choose the world for this course | `97-world.js:636` | default | `GAP-27 world.choose` |
| The world is orientation art. Your lessons, checks and evidence are unchanged by it. | `97-world.js:650` | default | `GAP-27 world.orientation_note` |
| Some plates are missing | `97-world.js:710` | error | `GAP-27 world.missing_plates` |
| Missing: {roles}. Nothing is approved until every role exists, and no placeholder art is saved. | `97-world.js:711` | error | `GAP-27 world.missing_plates.body` |
| Direction / Chosen direction | `97-world.js:52`, `97-world.js:760` | default | `GAP-27 world.direction.*` |
| Use this direction | `97-world.js:767` | default | `GAP-27 world.direction.use` |
| The world you would get | `97-world.js:799` | default | `GAP-27 world.kit.preview_title` |
| 1 hero · 1 cover · {n} section card(s) | `97-world.js:249`, `97-world.js:800` | default | `GAP-27 world.kit.plate_count` (`computed:section_plates`) |
| Library cover / Section card (plate captions) | `97-world.js:803`, `97-world.js:810` · `97-world.js:778, 785` | empty | `GAP-27 world.plate.cover_caption` / `world.plate.section_caption` |
| Use this world and the course opens on it. This is the final visual approval; you can review it again from Course settings. | `97-world.js:818` | default | `GAP-27 world.kit.use_game` |
| Use this world to approve the kit and switch this course to Game mode. Your lessons, checks and evidence do not change. | `97-world.js:819` | default | `GAP-27 world.kit.use_switch` |
| This world is approved. | `97-world.js:839` | default | `GAP-27 world.approved` |
| Changing it starts a new direction and leaves this approved kit on the course until you approve another. | `97-world.js:840` | default | `GAP-27 world.approved.change_note` |
| Edit direction / Close the direction | `97-world.js:855` | default | `GAP-27 world.direction.edit` / `world.direction.close` |
| Mood / Who it is for / Motifs to include / Motifs to avoid | `97-world.js:861-864` | default | `GAP-27 world.direction.*` |
| e.g. calm, practical / e.g. adult learner / comma separated (×2) (placeholders) | `97-world.js:861-863` | default | `GAP-27 world.direction.placeholder.*` |
| These words steer the next generation only. They never edit a lesson, a check or a source. | `97-world.js:871` | default | `GAP-27 world.direction.scope_note` |
| What should change? | `97-world.js:885` | default | `GAP-27 world.reroll.title` |
| e.g. warmer light, fewer props (placeholder) | `97-world.js:891` | default | `GAP-27 world.reroll.placeholder` |
| The reason is used as mood text for the next set. It is not shown to the image model as a scene description. | `97-world.js:893` | default | `GAP-27 world.reroll.note` |
| Working… (loader label) | `97-world.js:963` | loading | `GAP-27 world.working_title` |
| {stage} — you can leave this open or cancel. No lesson is built until the world is approved. | `97-world.js:944` | loading | `GAP-27 world.working_body` |
| Working… | `97-world.js:963` | loading | `GAP-27 world.buttons.working` |
| Try again / Show me three directions / Build this world / Use this world / Change world / Retry the missing plates / Try the directions again (primary actions) | `97-world.js:599`, `97-world.js:965`, `97-world.js:967-970` | default / error | `GAP-27 world.buttons.*` |
| Try another set | `97-world.js:928` | default | `GAP-27 world.buttons.try_another` |
| Use Textbook mode / Cancel / Close / Keep Textbook | `97-world.js:19`, `97-world.js:585` | default | `GAP-27 world.buttons.*` |
| Close the World Studio (accessible name) | `97-world.js:1014` | dialog | `GAP-27 world.close_label` |

## 5. Mode dialogs and the unavailable family (`97-world.js:553-1024`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The world is approved, but the course could not switch to Game mode: {reason} | `97-world.js:549` | error | `GAP-27 world.mode_switch_failed` |
| This backend does not carry the world wire yet / Your course stays in Textbook mode and no art is generated. | `97-world.js:582`, `97-world.js:584` | error | `GAP-27 world.no_wire` / `world.no_wire.body` |
| Game mode is unavailable because image generation is not configured. | `97-world.js:690` | error | `GAP-27 world.unavailable` |
| The course stays in Textbook mode and your lessons are unchanged. No fake world is created. | `97-world.js:691` | error | `GAP-27 world.no_fake` |
| Back to the course | `97-world.js:600` | error | `GAP-27 world.back` |
| Game mode is not available right now | `97-world.js:1044` | dialog | `GAP-27 world.dialog.unavailable.title` |
| Game mode is not available right now because the image provider is not configured. The course stays in Textbook mode and your lessons are unchanged. | `97-world.js:1045` | dialog | `GAP-27 world.dialog.unavailable.body` |
| This course already has a world. | `97-world.js:1049` | dialog | `GAP-27 world.dialog.has_world.title` |
| Switch to Game mode? The approved world is reused; no art is generated. | `97-world.js:1050` | dialog | `GAP-27 world.dialog.has_world.body` |
| Switch to Game mode | `97-world.js:1051` | dialog | `GAP-27 world.dialog.has_world.confirm` |
| A world is not approved yet. | `97-world.js:1054` | dialog | `GAP-27 world.dialog.unapproved.title` |
| This course has a world in progress. It stays in Textbook mode until you approve the final kit. | `97-world.js:1055` | dialog | `GAP-27 world.dialog.unapproved.body` |
| Game mode is not available yet. Generate a game world? | `97-world.js:1061` | dialog | `GAP-27 world.dialog.generate.title` |
| This course was built in Textbook mode. The World Studio shows three art directions, then builds the kit, then asks for your final approval. Your plan, lessons, checks and evidence stay exactly as they are. | `97-world.js:1062` | dialog | `GAP-27 world.dialog.generate.body` |
| Studio | `97-world.js:1` | dialog | `GAP-27 world.dialog.generate.confirm` |

## 6. State coverage for this surface

| state | what renders | deck |
|---|---|---|
| default | mode plate, direction editor, kit preview, approved panel (sections 1, 4) | GAP-27 |
| loading | `Loading the plate`, `Reading the course world`, `Queued`, `Working on the world`, `Working…`, `· saving` | GAP-27 |
| empty | `World not approved yet`, `This course`, `Section`, plate fallbacks | GAP-27 |
| error | `could not be read`, `did not finish`, `Some plates are missing`, `no wire`, `could not switch` | GAP-27 |
| dialog | five mode dialogs at `97-world.js:1005-1024` plus the studio frame (`980`) | GAP-27 |
| overflow | **no string.** Grids wrap; nothing states a clipped or truncated state (`97-world.js:301, 367, 700, 762, 782, 825` are layout only). | GAP-35 |
| offline | **no string.** `97-world.js` never reads `useOnline()`; a failed read renders `The course world could not be read` even when the cause is a connection. | GAP-35 |

## 7. What CP-031's sample missed (delta for CP-001)

`CP-025b-studio.md` listed the mode chrome, archetypes, direction editor and the three mode dialogs.
This sweep adds: the nine world state words as a map (`49-57`), the plate chrome and captions
(`202, 238, 335, 349, 379, 773-785`), the primary-action labels (`929-938`), the loader body
(`909-910`), the approved/change panel (`805-806`), and the mode-switch failure (`553`). It also
records two states the sample called "no copy" with the exact evidence: no overflow string, no
offline read.

## 8. Row count

Tables above: the complete visible-string inventory for `desktop/src/97-world.js`. Non-visible
literal classes excluded by the same rule as the studio file (method names, `data-cb-*`, CSS
layout strings, ids, error codes).
