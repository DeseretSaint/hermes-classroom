# CP-025b — World Studio and Parent Studio copy and state inventory

Card body: `docs/concept-parity/cards/CP-025b.md`.
Spec: `SPEC-V3.md` has **no** section for these surfaces. §5 ends at the design-system lab.
Deck: `COPY.md` has **no** section for these surfaces.

Deck rows used: **0**. Not one string on either surface has a row, although the shell rows still
apply wherever the rail or a back path is painted.

## What this card actually says

CP-025b's real "This card" section is two lines (lines 34–35):

> World Studio (GM-004) and Parent Studio (GM-006) on v3 primitives; Parent Studio keeps its
> adult-only rules and stays free of game chrome.

Lines 37–55 of the body are a **copy of CP-021's body** (Discover strings, the capture paragraph,
CP-021's ownership block). Line 61 carries the real ownership block. This is `GAP-29`: repair before
dispatch or the maker restyles Discover.

"Keeps its adult-only rules" is itself a copy constraint with no deck rows: the shipped surface
states it twice ("No child account and no child chat: the adult prepares and prints." at
`desktop/src/95-studio.js:840`, and the child-safe line below). A rebuild must not soften either.

## World Studio (GM-004) — strings the shipped surface renders

### Mode chrome and the course-home plate

| string | source | deck |
|---|---|---|
| Course world / World / Game / Textbook (mode labels) | `desktop/src/97-world.js:9-12` | — |
| Change mode | `97-world.js:13` | — |
| Course settings | `97-world.js:14` | — |
| World not approved yet | `97-world.js:15` | — |
| This course reads as Textbook until its world is approved. Your lessons and plan are unchanged. | `97-world.js:17` | — |
| Open World Studio | `97-world.js:18` | — |
| Use Textbook mode | `97-world.js:19, 897` | — |
| This backend does not report a course world yet. | `97-world.js:20` | — |
| The course world could not be read | `97-world.js:21, 598` | — |
| The art for this plate is not available; the text label stands in for it. | `97-world.js:22` | — |
| Loading the plate | `97-world.js:202` | — |
| · saving | `97-world.js:238` | — |
| This course | `97-world.js:335, 774` | — |
| Review the world | `97-world.js:349` | — |
| Section | `97-world.js:379` | — |

### World states

| string | source | deck |
|---|---|---|
| Not started / Choosing directions / Three directions / Direction chosen / Building the world / Ready to approve / Approved / Could not finish / Unavailable | `97-world.js:49-57` | — |
| Queued | `97-world.js:498` | — |
| Working on the world (+ "{stage} — you can leave this open or cancel. No lesson is built until the world is approved.") | `97-world.js:909-910` | — |
| Working… | `97-world.js:929` | — |
| The world job did not finish. | `97-world.js:455` | — |
| That did not finish | `97-world.js:665` | — |
| Some plates are missing / Missing: {roles}. Nothing is approved until every role exists, and no placeholder art is saved. | `97-world.js:687-688` | — |
| Reading the course world / Nothing already saved is lost. | `97-world.js:614-615` | — |

### World archetypes (a fixed enum → name + description map)

| string | source | deck |
|---|---|---|
| Field atlas / Workshop manual / Observatory / Kitchen table / Archive desk / Studio bench / Lab bench / Instrument board | `97-world.js:27-34` | — |
| Maps, lanterns and a field notebook — a place to travel through the subject. … Instruments, graph paper and a blackboard. (eight one-line descriptions) | `97-world.js:38-45` | — |

### The Studio

| string | source | deck |
|---|---|---|
| Choose the world for this course | `97-world.js:642` | — |
| The world is orientation art. Your lessons, checks and evidence are unchanged by it. | `97-world.js:646` | — |
| Direction / Chosen direction | `97-world.js:707, 736` | — |
| Show me three directions / Build this world / Use this world / Change world / Try another set / Try again | `97-world.js:894, 930-938` | — |
| Use this direction | `97-world.js:745` | — |
| The world you would get | `97-world.js:773` | — |
| 1 hero · 1 cover · {n} section card(s) | `97-world.js:775` | — |
| Library cover / Section card | `97-world.js:778, 785` | — |
| Use this world and the course opens on it…. / Use this world to approve the kit and switch this course to Game mode…. | `97-world.js:793-794` | — |
| This world is approved. | `97-world.js:805` | — |
| Changing it starts a new direction and leaves this approved kit on the course until you approve another. | `97-world.js:806` | — |
| Edit direction / Close the direction | `97-world.js:821` | — |
| Mood / Who it is for / Motifs to include / Motifs to avoid | `97-world.js:827-830` | — |
| e.g. calm, practical / e.g. adult learner / comma separated / comma separated | `97-world.js:827-830` | — |
| These words steer the next generation only. They never edit a lesson, a check or a source. | `97-world.js:837` | — |
| What should change? | `97-world.js:851` | — |
| e.g. warmer light, fewer props | `97-world.js:857` | — |
| The reason is used as mood text for the next set. It is not shown to the image model as a scene description. | `97-world.js:859` | — |
| Game mode is unavailable because image generation is not configured. / The course stays in Textbook mode and your lessons are unchanged. No fake world is created. | `97-world.js:676-677` | — |
| Game mode is not available right now / …because the image provider is not configured…. | `97-world.js:1005-1006` | — |
| Keep Textbook / Cancel / Close / Retry the missing plates | `97-world.js:589, 898, 983, 936, 1089-1090` | — |
| This course already has a world. / Switch to Game mode? The approved world is reused; no art is generated. / Switch to Game mode | `97-world.js:1010-1012` | — |
| A world is not approved yet. / This course has a world in progress. It stays in Textbook mode until you approve the final kit. / Open World Studio | `97-world.js:1015-1017` | — |
| Game mode is not available yet. Generate a game world? / This course was built in Textbook mode. The World Studio shows three art directions, then builds the kit, then asks for your final approval. Your plan, lessons, checks and evidence stay exactly as they are. / Studio | `97-world.js:1022-1024` | — |
| The world is approved, but the course could not switch to Game mode: {reason} | `97-world.js:553` | — |
| This backend does not carry the world wire yet / Your course stays in Textbook mode and no art is generated. | `97-world.js:587-588` | — |
| Back to the course | `97-world.js:602` | — |

### World Studio states

| state | what renders | deck |
|---|---|---|
| default (course home plate) | mode label + `Open World Studio` / `Review the world` | — |
| loading | `Reading the course world` + `Nothing already saved is lost.` | — |
| error | `The course world could not be read` + `Try again` + `Back to the course` | — |
| unavailable (no provider) | `Game mode is unavailable…` + `Keep Textbook` | — |
| missing plates | `Some plates are missing` + the role list + `Retry the missing plates` | — |
| job failed | `The world job did not finish.` / `That did not finish` | — |
| **offline** | **no string exists** | — |
| overflow | no copy | — |

## Parent Studio (GM-006) — strings the shipped surface renders

### Landing and plans

| string | source | deck |
|---|---|---|
| Parent Studio (surface label) | `desktop/src/95-studio.js:474` | — |
| Plans for your child | `95-studio.js:475` | — |
| Prepare a lesson for a child. Each brief you write is kept as its own plan, so you can compare versions without losing the first. | `95-studio.js:477` | — |
| New lesson plan | `95-studio.js:443, 478` | — |
| No lesson plans yet | `95-studio.js:438` | — |
| A lesson plan starts from a short brief: the child's age and reading level, where you will teach, what you have, what to leave out, and what you want them to be able to do. Coursebook drafts a plan for you to review before any lesson page is written. | `95-studio.js:440-442` | — |
| Lesson plan for a child | `95-studio.js:492` | — |
| updated {when} | `95-studio.js:492` area (`whenLabel`) | — |
| Open plan | `95-studio.js:496` | — |
| My lesson plans / Take-home from a lesson / Homework (entrances) | `95-studio.js:520-523` | — |
| Reading your parent courses / Your parent courses could not be read / Try again | `95-studio.js:427-433` | — |
| Parent Studio needs the v6 authoring methods / Open Capabilities | `95-studio.js:420-423` | — |
| Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no XP or streaks | `desktop/src/30-home.js:3670` | — |
| · Session · {n} min | `30-home.js:3674` | — |
| Settings / Open Coursebook settings | `30-home.js:3683-3687` | — |
| No child account and no child chat: the adult prepares and prints. | `95-studio.js:840` | — |

### Take-home pack

| string | source | deck |
|---|---|---|
| Print a take-home pack | `95-studio.js:530` | — |
| A parent guide, the learner page and a separate answer guide, bound to this lesson. | `95-studio.js:531` | — |
| Prepare an activity plan | `95-studio.js:535` | — |
| Send with homework | `95-studio.js:540` | — |
| One real-world practice task on a single sheet the learner can carry with them. | `95-studio.js:541` | — |
| For me to teach from / For the learner to hold | `95-studio.js:546-547` | — |
| Cover / Parent guide / Learner page / Plate / Answer guide (page roles) | `95-studio.js:551-555` | — |
| The first page of the printed pack. / For the adult preparing the lesson. It is not the learner's page. / For the learner. This page carries no answers. / Captioned orientation art. It is not the lesson text. / Parent only. Keep this page back. | `95-studio.js:564-568` | — |
| Draft / Approved / Exported / Superseded (pack states) | `95-studio.js:572-575` | — |
| Game course / Textbook course (source modes) | `95-studio.js:579-580` | — |
| Take-home pack / Activity plan / Homework sheet (pack kinds) | `95-studio.js:584-586` | — |
| Course / Take-home | `95-studio.js:629, 633` | — |
| Approve the exact pages above before exporting. | `95-studio.js:598` | — |
| The pages changed after approval. Approve the pages you can see again. | `95-studio.js:599` | — |
| The preview moved on. Preview the pages again, then approve them. | `95-studio.js:600` | — |
| This pack is already exported. The file below is that export. | `95-studio.js:601` | — |
| The PDF renderer failed. The pack is kept; the export did not run. | `95-studio.js:604` | — |
| A parent-authored plan is not a learner source. | `95-studio.js:592, 605` | — |
| This draft was superseded. Start a fresh draft from the lesson. | `95-studio.js:606` | — |
| This lesson cannot be printed yet. / This lesson cannot be printed: {reason}. | `95-studio.js:667-668` | — |
| This procedure has only illustration art, so it cannot print as authority. | `95-studio.js:593` | — |
| no generated lesson / The lesson for this objective has not been written yet. | `95-studio.js:591` | — |
| Reading the courses you teach / The courses you teach could not be read / Try again | `95-studio.js:700-706` | — |
| No learner course to draw from / A take-home pack is printed from a Game or Textbook lesson you already teach. Write or import a learner course first; a parent plan belongs under My lesson plans. / Check again | `95-studio.js:711-714` | — |

### Parent Studio states

| state | what renders | deck |
|---|---|---|
| default | landing + the three entrances | — |
| empty | `No lesson plans yet` + the brief explanation + `New lesson plan` | — |
| loading | `Reading your parent courses` / `Reading the courses you teach` | — |
| error | `… could not be read` + `Try again` | — |
| no source | `No learner course to draw from` + `Check again` | — |
| pack blocked | `This lesson cannot be printed yet.` or `… : {reason}.` | — |
| leave guard | `data-cb-studio-leave-discard` dialog (`95-studio.js:6803-6834`) — copy not extracted here | — |
| **offline** | **no string exists** | — |
| overflow | no copy | — |

## GAPS

- **GAP-27 — the deck has no World Studio section.** Every string above is unsourced, including the
  eight world archetype names and their descriptions (a fixed enum → prose map, `97-world.js:27-45`)
  and the three mode dialogs (`97-world.js:1005-1024`). A v3 restyle will re-word the mode rules,
  which are the product's honesty claims ("No fake world is created", "your lessons are unchanged").
- **GAP-28 — the deck has no Parent Studio section.** Every string above is unsourced, including the
  adult-only claims (`95-studio.js:840`, `30-home.js:3670`) and the take-home page-role descriptions
  (`95-studio.js:564-568`). The card body's own rule — "Parent Studio keeps its adult-only rules and
  stays free of game chrome" — has no row a reviewer can check against.
- **GAP-29 — the card body is corrupted.** `cards/CP-025b.md` lines 37–55 are CP-021's body; the real
  ownership block is line 61.
- Both surfaces also have **no offline copy**, which §3.12 requires of every v3 screen.

## What CP-025b needs before it can start

1. `COPY.md` sections for World Studio and Parent Studio, built from the tables above, each with a
   source form (`deck`, `field:world.read.*`, `field:takehome.*`, `field:parent.*`).
2. A repaired card body (`GAP-29`).
3. The adult-only rules named as explicit rows, so the reviewer has something to assert.
4. v3 primitives, owned by CP-020b; label-shape changes are a CP-020c request.
