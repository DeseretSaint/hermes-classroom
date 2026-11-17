# CP-031c — World Studio shipped-string sweep

Card: **CP-031c** (`t_0458a135`), re-swept by **CP-031c-R** (`t_54a44039`) at `a11bc0e4`, re-derived by **CP-031d** (`t_d20f3f5e`) at `14fb14f3`, and re-swept by **CP-031e** (`t_868205f4`) at `a0925957`. Docs only; no product string changed.

**Revision swept:** `origin/master` at **`a0925957fc43edfb8ce3f7c846c9f49309897c0f`** (97-world.js, 1135 lines, whole file).
**Rows:** 92 inventory rows; 92 distinct literals. Every row cites the line(s)
that carry its words in this revision.

**Surface:** World Studio and the durable-mode chrome the course home paints.

## How this table was filtered

Every literal in the file was lexed by `tests/test_cp_copy_inventory.py::lex_strings` (single
quotes, double quotes and template literals, outside comments and regex literals). The extractor
keeps a literal when it has two or more whitespace-separated tokens and at least two word tokens,
and then drops, by class:

- CSS class lists, declarations, grid templates, lengths, colours and `calc()`/`var(--…)` values;
- dotted method and field names, paths, URLs, MIME types and `SCREAMING_SNAKE` error codes;
- code fragments (`=>`, function text, tags, `\uXXXX` escapes);
- the two named attribute-value allowlist entries `noreferrer noopener` and `noopener noreferrer`.

Template-literal `${…}` expressions are normalised to `{…}` before comparison, so a row reads
`Step {…} of {…}` and the cited line is checked with the same substitution. Single-word controls
(e.g. `Cancel`) are outside this multi-word gate; the ones that carry state are named in `GAPS.md`.
The state column is classified from the literal's own wording (`error`, `empty`, `loading`,
`offline`) and is `default` for a plain label; it is not a call-graph reading.

## Inventory

### CB_WORLD_COPY (`97-world.js` from line 8)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Course world | `97-world.js:9` | default | `GAP-27` |
| Change mode | `97-world.js:13` | default | `GAP-27` |
| Course settings | `97-world.js:14` | default | `GAP-27` |
| World not approved yet | `97-world.js:15` | default | `GAP-27` |
| This course reads as Textbook until its world is approved. Your lessons and plan are unchanged. | `97-world.js:17` | default | `GAP-27` |
| Open World Studio | `97-world.js:18`; `97-world.js:1056` | default | `GAP-27` |
| Use Textbook mode | `97-world.js:19`; `97-world.js:931` | default | `GAP-27` |
| This backend does not report a course world yet. | `97-world.js:20` | default | `GAP-27` |
| The course world could not be read | `97-world.js:21`; `97-world.js:593` | error | `GAP-27` |
| The art for this plate is not available; the text label stands in for it. | `97-world.js:22` | error | `GAP-27` |

### CB_GRAMMAR_NAME (`97-world.js` from line 26)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Field atlas | `97-world.js:27` | default | `GAP-27` |
| Workshop manual | `97-world.js:28` | default | `GAP-27` |
| Kitchen table | `97-world.js:30` | default | `GAP-27` |
| Archive desk | `97-world.js:31` | default | `GAP-27` |
| Studio bench | `97-world.js:32` | default | `GAP-27` |
| Lab bench | `97-world.js:33` | default | `GAP-27` |
| Instrument board | `97-world.js:34` | default | `GAP-27` |

### CB_GRAMMAR_ONE_LINE (`97-world.js` from line 37)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Maps, lanterns and a field notebook — a place to travel through the subject. | `97-world.js:38` | default | `GAP-27` |
| A service bay, tool wall and manual pages — orientation beside the procedure. | `97-world.js:39` | default | `GAP-27` |
| Star charts, instruments and an observation log. | `97-world.js:40` | default | `GAP-27` |
| A work surface, ingredient cards and a recipe board. | `97-world.js:41` | default | `GAP-27` |
| Documents, stamps, maps and index cards. | `97-world.js:42` | default | `GAP-27` |
| Materials, swatches and a sketchbook. | `97-world.js:43` | default | `GAP-27` |
| Glassware, a lab notebook and labelled stations. | `97-world.js:44` | default | `GAP-27` |
| Instruments, graph paper and a blackboard. | `97-world.js:45` | default | `GAP-27` |

### CB_WORLD_STATE_WORD (`97-world.js` from line 48)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Choosing directions | `97-world.js:50` | default | `GAP-27` |
| Three directions | `97-world.js:51` | default | `GAP-27` |
| Direction chosen | `97-world.js:52` | default | `GAP-27` |
| Building the world | `97-world.js:53` | default | `GAP-27` |
| Ready to approve | `97-world.js:54` | default | `GAP-27` |
| Could not finish | `97-world.js:56` | error | `GAP-27` |

### WorldPlate (`97-world.js` from line 143)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Loading the plate | `97-world.js:202` | loading | `GAP-27` |

### ModeBadge (`97-world.js` from line 214)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| · saving | `97-world.js:242` | default | `GAP-27` |

### CourseWorldHero (`97-world.js` from line 251)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This course | `97-world.js:333`; `97-world.js:798` | default | `GAP-27` |
| Review the world | `97-world.js:345` | default | `GAP-27` |

### WorldStudio (`97-world.js` from line 414)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The world job did not finish. | `97-world.js:451` | error | `GAP-27` |
| The world is approved, but the course could not switch to Game mode: | `97-world.js:549` | error | `GAP-27` |
| This backend does not carry the world wire yet | `97-world.js:582` | default | `GAP-27` |
| Your course stays in Textbook mode and no art is generated. | `97-world.js:584` | default | `GAP-27` |
| Keep Textbook | `97-world.js:585`; `97-world.js:1046`; `97-world.js:1127` | default | `GAP-27` |
| Try again | `97-world.js:599`; `97-world.js:964`; `97-world.js:971` | default | `GAP-27` |
| Back to the course | `97-world.js:600` | default | `GAP-27` |
| Reading the course world | `97-world.js:610` | default | `GAP-27` |
| Nothing already saved is lost. | `97-world.js:616` | empty | `GAP-27` |
| Choose the world for this course | `97-world.js:636` | default | `GAP-27` |
| The world is orientation art. Your lessons, checks and evidence are unchanged by it. | `97-world.js:650` | default | `GAP-27` |
| That did not finish | `97-world.js:670` | error | `GAP-27` |
| Game mode is unavailable because image generation is not configured. | `97-world.js:690` | error | `GAP-27` |
| The course stays in Textbook mode and your lessons are unchanged. No fake world is created. | `97-world.js:691` | default | `GAP-27` |
| Some plates are missing | `97-world.js:710` | default | `GAP-27` |
| Missing: {…}. Nothing is approved until every role exists, and no placeholder art is saved. | `97-world.js:711` | default | `GAP-27` |
| Chosen direction | `97-world.js:760` | default | `GAP-27` |
| Use this direction | `97-world.js:767` | default | `GAP-27` |
| The world you would get | `97-world.js:799` | default | `GAP-27` |
| 1 hero · 1 cover · {…} section {…} | `97-world.js:800` | default | `GAP-27` |
| Library cover | `97-world.js:803` | default | `GAP-27` |
| Section card | `97-world.js:810` | default | `GAP-27` |
| Use this world and the course opens on it. This is the final visual approval; you can review it again from Course settings. | `97-world.js:818` | default | `GAP-27` |
| Use this world to approve the kit and switch this course to Game mode. Your lessons, checks and evidence do not change. | `97-world.js:819` | default | `GAP-27` |
| This world is approved. | `97-world.js:839` | default | `GAP-27` |
| Changing it starts a new direction and leaves this approved kit on the course until you approve another. | `97-world.js:840` | default | `GAP-27` |
| Close the direction | `97-world.js:855` | default | `GAP-27` |
| Edit direction | `97-world.js:855` | default | `GAP-27` |
| e.g. calm, practical | `97-world.js:861` | default | `GAP-27` |
| Who it is for | `97-world.js:862` | default | `GAP-27` |
| e.g. adult learner | `97-world.js:862` | default | `GAP-27` |
| Motifs to include | `97-world.js:863` | default | `GAP-27` |
| comma separated | `97-world.js:863`; `97-world.js:864` | default | `GAP-27` |
| Motifs to avoid | `97-world.js:864` | default | `GAP-27` |
| These words steer the next generation only. They never edit a lesson, a check or a source. | `97-world.js:871` | default | `GAP-27` |
| What should change? | `97-world.js:885` | default | `GAP-27` |
| e.g. warmer light, fewer props | `97-world.js:891` | default | `GAP-27` |
| The reason is used as mood text for the next set. It is not shown to the image model as a scene description. | `97-world.js:893` | default | `GAP-27` |
| Try another set | `97-world.js:928` | default | `GAP-27` |
| {…} — you can leave this open or cancel. No lesson is built until the world is approved. | `97-world.js:944` | default | `GAP-27` |
| You can leave this open or cancel. No lesson is built until the world is approved. | `97-world.js:944` | default | `GAP-27` |

### buildWorldPrimary (`97-world.js` from line 962)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Show me three directions | `97-world.js:965`; `97-world.js:972` | default | `GAP-27` |
| Build this world | `97-world.js:967` | default | `GAP-27` |
| Use this world | `97-world.js:968` | default | `GAP-27` |
| Change world | `97-world.js:969` | default | `GAP-27` |
| Retry the missing plates | `97-world.js:970` | default | `GAP-27` |
| Try the directions again | `97-world.js:970` | default | `GAP-27` |

### WorldStudioFrame (`97-world.js` from line 975)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Close the World Studio | `97-world.js:1014` | default | `GAP-27` |

### ModeSwitchDialog (`97-world.js` from line 1035)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Game mode is not available right now | `97-world.js:1044` | error | `GAP-27` |
| Game mode is not available right now because the image provider is not configured. The course stays in Textbook mode and your lessons are unchanged. | `97-world.js:1045` | error | `GAP-27` |
| This course already has a world. | `97-world.js:1049` | default | `GAP-27` |
| Switch to Game mode? The approved world is reused; no art is generated. | `97-world.js:1050` | default | `GAP-27` |
| Switch to Game mode | `97-world.js:1051` | default | `GAP-27` |
| A world is not approved yet. | `97-world.js:1054` | default | `GAP-27` |
| This course has a world in progress. It stays in Textbook mode until you approve the final kit. | `97-world.js:1055` | default | `GAP-27` |
| Game mode is not available yet. Generate a game world? | `97-world.js:1061` | error | `GAP-27` |
| This course was built in Textbook mode. The World Studio shows three art directions, then builds the kit, then asks for your final approval. Your plan, lessons, checks and evidence stay exactly as they are. | `97-world.js:1062` | default | `GAP-27` |


**Offline and overflow evidence:** this file has no `useOnline()` branch and states no offline
sentence. It is not quite free of truncation, though: the direction form sends at most six motifs and
six forbidden items (`direction.include.split(',').slice(0, 6)` / `direction.avoid…`
at `97-world.js:468-469`) and says nothing when the input carried more, so `GAP-35` owns a
`world.plates.overflow` row for that cap. Offline copy is still a `GAP-35` question (`world.offline.*`
is not worded; the owner has not chosen per-surface or shared).
