# CP-031c — Parent Studio shipped-string sweep

Card: **CP-031c** (`t_0458a135`), re-swept by **CP-031c-R** (`t_54a44039`) at `a11bc0e4` and re-derived by **CP-031d** (`t_d20f3f5e`) at `14fb14f3`. Docs only; no product string changed.

**Revision swept:** `origin/master` at **`14fb14f3e8c5306f973bf98ba270140ca98f0ac5`** (95-studio.js, 7934 lines, whole file).
**Rows:** 647 inventory rows; 647 distinct literals. Every row cites the line(s)
that carry its words in this revision.

**CP-031d re-derivation (`t_d20f3f5e`):** between `a11bc0e4` and `14fb14f3`, `95-studio.js` moved
exactly once — `54eca355` replaced the template `plan ${row.kind}` at 4666 with the literal
`plan change` — and no other user-facing literal in the file changed. The literal count and the
647-row total are unchanged; the row below already carries the new literal at the same line
(`95-studio.js:4666`), re-derived by the same lexer, not by eye.

**Surface:** the Parent Studio detail page: homework sheets, plan validation, the fine-tune editor, the
approval banner and the lesson-set export gate.

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

### STUDIO_VISUALS (`95-studio.js` from line 25)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| No visuals | `95-studio.js:26` | empty | `GAP-28` |

### STUDIO_NARRATION (`95-studio.js` from line 30)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| No narration | `95-studio.js:31` | empty | `GAP-28` |
| A script I read aloud | `95-studio.js:32` | default | `GAP-28` |

### STUDIO_DIFFICULTIES (`95-studio.js` from line 38)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Too easy | `95-studio.js:39` | default | `GAP-28` |
| About right | `95-studio.js:40` | default | `GAP-28` |
| Too hard | `95-studio.js:41` | default | `GAP-28` |

### STUDIO_TABS (`95-studio.js` from line 50)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Parent guide | `95-studio.js:51`; `95-studio.js:703` | default | `GAP-28` |
| Learner pages | `95-studio.js:52` | default | `GAP-28` |
| Audio & visuals | `95-studio.js:54` | default | `GAP-28` |

### EVIDENCE_TARGET_OPTIONS (`95-studio.js` from line 57)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Tell the difference | `95-studio.js:63` | default | `GAP-28` |

### PLAN_STATE_COPY (`95-studio.js` from line 67)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Plan draft | `95-studio.js:68` | default | `GAP-28` |
| Plan approved | `95-studio.js:69` | default | `GAP-28` |
| Plan superseded | `95-studio.js:70` | default | `GAP-28` |

### APPROVAL_STATE_COPY (`95-studio.js` from line 72)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Lesson set not approved | `95-studio.js:73` | default | `GAP-28` |
| Lesson set approved | `95-studio.js:74` | default | `GAP-28` |
| Changes need review | `95-studio.js:75`; `95-studio.js:3756` | default | `GAP-28` |

### EXPORT_BLOCKED_COPY (`95-studio.js` from line 78)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The generated lesson set has not been approved. Approval is a separate step from approving the plan. | `95-studio.js:79` | default | `GAP-28` |
| Changes need review. The approved lesson set no longer matches the pages shown, so export is blocked until you approve them again. | `95-studio.js:80` | default | `GAP-28` |
| The plan is not approved, so there are no pages to export. | `95-studio.js:81` | default | `GAP-28` |
| No lesson pages have been generated yet. | `95-studio.js:82` | empty | `GAP-28` |

### EXPORT_REFUSAL_COPY (`95-studio.js` from line 85)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The plan is not approved. | `95-studio.js:86` | default | `GAP-28` |
| Approve the exact lesson set first. | `95-studio.js:87` | default | `GAP-28` |
| The pages changed after approval; review and approve them again. | `95-studio.js:88` | default | `GAP-28` |
| There is no generated content to export. | `95-studio.js:89` | default | `GAP-28` |
| This course came from an imported pack. Use Library → Export pack for it. | `95-studio.js:90` | default | `GAP-28` |
| The generated lessons do not meet the pack’s teaching minima yet. | `95-studio.js:91` | default | `GAP-28` |
| The files could not be written. Nothing was exported. | `95-studio.js:92` | error | `GAP-28` |

### PlanStateBadge (`95-studio.js` from line 204)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| No plan yet | `95-studio.js:206`; `95-studio.js:6393` | empty | `GAP-28` |
| {…} · v{…} | `95-studio.js:210`; `95-studio.js:7331` | default | `GAP-28` |

### JobStateText (`95-studio.js` from line 224)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Waiting to start. Nothing is spent until it begins. | `95-studio.js:229` | default | `GAP-28` |
| Stopping. The step already under way finishes, then this stops before the next one. | `95-studio.js:234` | default | `GAP-28` |
| Working on it{…} | `95-studio.js:240` | default | `GAP-28` |
| It stopped early. The work already saved is kept; start the stage again to finish it. | `95-studio.js:249` | default | `GAP-28` |
| Cancelled before it finished. The brief and any work that had already been saved are kept. | `95-studio.js:255` | default | `GAP-28` |
| It stopped before finishing. | `95-studio.js:262` | default | `GAP-28` |
| Technical detail | `95-studio.js:269`; `95-studio.js:4177`; `95-studio.js:4497` | default | `GAP-28` |

### PLAN_WAIT_BAND (`95-studio.js` from line 287)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| One lesson usually takes a few minutes. | `95-studio.js:288` | default | `GAP-28` |
| Short courses usually take a few minutes. | `95-studio.js:289` | default | `GAP-28` |
| A full course takes longer than a short course; the clock counts the real wait. | `95-studio.js:290` | default | `GAP-28` |

### PLAN_STAGE_WORDS (`95-studio.js` from line 294)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Waiting to start | `95-studio.js:295` | default | `GAP-28` |
| Writing the outline | `95-studio.js:296`; `95-studio.js:298` | default | `GAP-28` |
| Researching the goal | `95-studio.js:297` | default | `GAP-28` |
| Checking the outline | `95-studio.js:299` | default | `GAP-28` |
| Ready for your review | `95-studio.js:300` | default | `GAP-28` |

### planWaitBand (`95-studio.js` from line 303)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| A plan usually takes a few minutes. | `95-studio.js:304` | default | `GAP-28` |

### PlanWritingPanel (`95-studio.js` from line 349)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Step {…} of {…} | `95-studio.js:361` | default | `GAP-28` |
| The plan is being written | `95-studio.js:370` | default | `GAP-28` |
| The plan is not running right now | `95-studio.js:370` | default | `GAP-28` |
| Reading the job… | `95-studio.js:378` | default | `GAP-28` |
| {…}s elapsed | `95-studio.js:387` | default | `GAP-28` |

### StudioJobLine (`95-studio.js` from line 474)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| It runs in the background; leaving this page does not stop it. | `95-studio.js:523` | default | `GAP-28` |
| Cancel generation | `95-studio.js:531` | default | `GAP-28` |
| Run this stage again | `95-studio.js:541` | default | `GAP-28` |

### StudioList (`95-studio.js` from line 555)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Parent Studio needs the v6 authoring methods | `95-studio.js:570` | default | `GAP-28` |
| This backend does not list library.list, so no authored course can be read. Update the plugin instead of using a placeholder screen. | `95-studio.js:572` | default | `GAP-28` |
| Open Capabilities | `95-studio.js:573`; `95-studio.js:1763` | default | `GAP-28` |
| Reading your parent courses | `95-studio.js:577` | default | `GAP-28` |
| Your parent courses could not be read | `95-studio.js:581` | error | `GAP-28` |
| Try again | `95-studio.js:583`; `95-studio.js:894`; `95-studio.js:1008`; `95-studio.js:1427`; `95-studio.js:2818`; `95-studio.js:3083`; `95-studio.js:3784`; `95-studio.js:4300`; `95-studio.js:4335`; `95-studio.js:4357`; `95-studio.js:4373`; `95-studio.js:4386`; `95-studio.js:6314`; `95-studio.js:7038`; `95-studio.js:7051`; `95-studio.js:7158` | default | `GAP-28` |
| No lesson plans yet | `95-studio.js:588` | empty | `GAP-28` |
| A lesson plan starts from a short brief: the child’s age and reading level, where you will teach, what you have, | `95-studio.js:590` | default | `GAP-28` |
| what to leave out, and what you want them to be able to do. Coursebook drafts a plan for you to review before any | `95-studio.js:591` | default | `GAP-28` |
| lesson page is written. | `95-studio.js:592` | default | `GAP-28` |
| New lesson plan | `95-studio.js:593`; `95-studio.js:629` | default | `GAP-28` |

### StudioLanding (`95-studio.js` from line 605)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Parent Studio | `95-studio.js:625` | default | `GAP-28` |
| Plans for your child | `95-studio.js:626` | default | `GAP-28` |
| Prepare a lesson for a child. Each brief you write is kept as its own plan, so you can compare versions without losing the first. | `95-studio.js:628` | default | `GAP-28` |
| Lesson plan for a child | `95-studio.js:643` | default | `GAP-28` |
| updated {…} | `95-studio.js:644` | default | `GAP-28` |
| Open plan | `95-studio.js:647` | default | `GAP-28` |

### CB_STUDIO_ENTRANCES (`95-studio.js` from line 670)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| My lesson plans | `95-studio.js:671` | default | `GAP-28` |
| Take-home from a lesson | `95-studio.js:672`; `95-studio.js:918`; `95-studio.js:1289` | default | `GAP-28` |

### CB_TAKEHOME_KINDS (`95-studio.js` from line 678)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Print a take-home pack | `95-studio.js:681` | default | `GAP-28` |
| A parent guide, the learner page and a separate answer guide, bound to this lesson. | `95-studio.js:682` | default | `GAP-28` |
| Prepare an activity plan | `95-studio.js:686` | default | `GAP-28` |
| The same lesson, composed for a short parent-led activity away from the screen. | `95-studio.js:687` | default | `GAP-28` |
| Send with homework | `95-studio.js:691` | default | `GAP-28` |
| One real-world practice task on a single sheet the learner can carry with them. | `95-studio.js:692` | default | `GAP-28` |

### CB_TAKEHOME_AUDIENCES (`95-studio.js` from line 696)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| For me to teach from | `95-studio.js:697` | default | `GAP-28` |
| For the learner to hold | `95-studio.js:698` | default | `GAP-28` |

### CB_TAKEHOME_PAGE_WORD (`95-studio.js` from line 701)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Learner page | `95-studio.js:704` | default | `GAP-28` |
| Answer guide | `95-studio.js:706` | default | `GAP-28` |

### CB_TAKEHOME_PAGE_NOTE (`95-studio.js` from line 714)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The first page of the printed pack. | `95-studio.js:715` | default | `GAP-28` |
| For the adult preparing the lesson. It is not the learner’s page. | `95-studio.js:716` | default | `GAP-28` |
| For the learner. This page carries no answers. | `95-studio.js:717` | default | `GAP-28` |
| Captioned orientation art. It is not the lesson text. | `95-studio.js:718` | default | `GAP-28` |
| Parent only. Keep this page back. | `95-studio.js:719` | default | `GAP-28` |

### CB_TAKEHOME_MODE_WORD (`95-studio.js` from line 729)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Game course | `95-studio.js:730` | default | `GAP-28` |
| Textbook course | `95-studio.js:731` | default | `GAP-28` |

### CB_TAKEHOME_KIND_WORD (`95-studio.js` from line 734)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Take-home pack | `95-studio.js:735` | default | `GAP-28` |
| Activity plan | `95-studio.js:736` | default | `GAP-28` |
| Homework sheet | `95-studio.js:737` | default | `GAP-28` |

### CB_TAKEHOME_BLOCKED_WORD (`95-studio.js` from line 741)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| no generated lesson | `95-studio.js:742` | empty | `GAP-28` |
| The lesson for this objective has not been written yet. | `95-studio.js:742` | default | `GAP-28` |
| A parent-authored plan is not a learner source. | `95-studio.js:743`; `95-studio.js:756` | default | `GAP-28` |
| This procedure has only illustration art, so it cannot print as authority. | `95-studio.js:744` | error | `GAP-28` |

### CB_TAKEHOME_EXPORT_WORD (`95-studio.js` from line 748)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Approve the exact pages above before exporting. | `95-studio.js:749` | default | `GAP-28` |
| The pages changed after approval. Approve the pages you can see again. | `95-studio.js:750` | default | `GAP-28` |
| The preview moved on. Preview the pages again, then approve them. | `95-studio.js:751` | default | `GAP-28` |
| This pack is already exported. The file below is that export. | `95-studio.js:752` | default | `GAP-28` |
| The print font cannot draw every character in this lesson, so no PDF was written. Nothing was corrupted. | `95-studio.js:754` | error | `GAP-28` |
| The PDF renderer failed. The pack is kept; the export did not run. | `95-studio.js:755` | error | `GAP-28` |
| This draft was superseded. Start a fresh draft from the lesson. | `95-studio.js:757` | default | `GAP-28` |

### StudioEntranceTabs (`95-studio.js` from line 767)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Parent Studio sections | `95-studio.js:771` | default | `GAP-28` |

### cbTakeHomeBlockedCopy (`95-studio.js` from line 854)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This lesson cannot be printed yet. | `95-studio.js:855` | error | `GAP-28` |
| This lesson cannot be printed: {…}. | `95-studio.js:856` | error | `GAP-28` |

### TakeHomeShelf (`95-studio.js` from line 885)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading the courses you teach | `95-studio.js:888` | default | `GAP-28` |
| The courses you teach could not be read | `95-studio.js:892` | error | `GAP-28` |
| No learner course to draw from | `95-studio.js:899` | empty | `GAP-28` |
| A take-home pack is printed from a Game or Textbook lesson you already teach. Write or import a learner course first; a parent plan belongs under My lesson plans. | `95-studio.js:901` | default | `GAP-28` |
| Check again | `95-studio.js:902` | default | `GAP-28` |
| Draw a take-home from a course you already teach | `95-studio.js:919` | default | `GAP-28` |
| The source course is not copied, changed or re-approved. The pack binds to this lesson’s version and hash, so printing it never touches the course. | `95-studio.js:921` | default | `GAP-28` |
| Courses you can draw a take-home from | `95-studio.js:925` | default | `GAP-28` |
| Untitled course | `95-studio.js:956` | default | `GAP-28` |
| Choose this course | `95-studio.js:971` | default | `GAP-28` |

### TakeHomeSourcePanel (`95-studio.js` from line 983)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Source lesson | `95-studio.js:996` | default | `GAP-28` |
| Choose a lesson | `95-studio.js:997` | default | `GAP-28` |
| Pick the written lesson to print. The preview is read-only: the course, its plan and its approval are not touched. | `95-studio.js:999` | default | `GAP-28` |
| Back to courses | `95-studio.js:1000` | default | `GAP-28` |
| Reading the lessons in this course | `95-studio.js:1003` | default | `GAP-28` |
| This course’s lessons could not be read | `95-studio.js:1006` | error | `GAP-28` |
| This course has no written lessons yet | `95-studio.js:1012` | default | `GAP-28` |
| A take-home pack prints the lesson as it already exists. Write the lesson in the course first, then come back. | `95-studio.js:1014` | default | `GAP-28` |
| Choose another course | `95-studio.js:1015` | default | `GAP-28` |
| written lesson | `95-studio.js:1025` | default | `GAP-28` |
| written lessons | `95-studio.js:1025` | default | `GAP-28` |
| No child account and no child chat: the adult prepares and prints. | `95-studio.js:1028` | empty | `GAP-28` |
| Evidence target: {…} · {…} | `95-studio.js:1084` | default | `GAP-28` |
| · world plates available | `95-studio.js:1085` | default | `GAP-28` |
| · no world art | `95-studio.js:1085` | default | `GAP-28` |
| Preview this lesson | `95-studio.js:1096` | default | `GAP-28` |
| Not printable yet | `95-studio.js:1096` | default | `GAP-28` |

### TakeHomeProof (`95-studio.js` from line 1118)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Print proof of the pack pages | `95-studio.js:1128` | default | `GAP-28` |
| Print proof | `95-studio.js:1142` | default | `GAP-28` |
| {…} · {…} · {…} pt margins · selectable text | `95-studio.js:1145` | default | `GAP-28` |
| Page {…} of {…} | `95-studio.js:1205` | default | `GAP-28` |
| Text alternative: {…} | `95-studio.js:1225` | default | `GAP-28` |

### TakeHomePackPanel (`95-studio.js` from line 1253)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Back to the lesson list | `95-studio.js:1292` | default | `GAP-28` |
| Evidence target: {…} | `95-studio.js:1301` | default | `GAP-28` |
| Source: {…} · | `95-studio.js:1323` | default | `GAP-28` |
| state {…} | `95-studio.js:1325` | default | `GAP-28` |
| Source content hash: {…} | `95-studio.js:1329` | default | `GAP-28` |
| Printing this pack does not change the course, its plan or its approval. | `95-studio.js:1331` | default | `GAP-28` |
| What to make | `95-studio.js:1335` | default | `GAP-28` |
| What to make from this lesson | `95-studio.js:1338` | default | `GAP-28` |
| Who holds this copy | `95-studio.js:1381`; `95-studio.js:1385` | default | `GAP-28` |
| Composing the pages | `95-studio.js:1420` | default | `GAP-28` |
| Preview the pages | `95-studio.js:1420` | default | `GAP-28` |
| The pages could not be composed | `95-studio.js:1425` | error | `GAP-28` |
| Recorded sources | `95-studio.js:1447` | default | `GAP-28` |
| This lesson records no external sources. | `95-studio.js:1468` | default | `GAP-28` |
| Approval and print | `95-studio.js:1480` | default | `GAP-28` |
| Previewed pages: {…} · preview hash: {…} | `95-studio.js:1483` | default | `GAP-28` |
| Draft {…} · revision {…}. Approval covers exactly the pages above. | `95-studio.js:1488` | default | `GAP-28` |
| {…} on {…} · approval hash: {…} | `95-studio.js:1494` | default | `GAP-28` |
| Saving the draft | `95-studio.js:1502` | default | `GAP-28` |
| Save this draft | `95-studio.js:1502` | default | `GAP-28` |
| Approving the pages | `95-studio.js:1510` | default | `GAP-28` |
| Approve these pages | `95-studio.js:1510` | default | `GAP-28` |
| PDF exported | `95-studio.js:1520` | default | `GAP-28` |
| Printing the PDF | `95-studio.js:1522` | default | `GAP-28` |
| Export the print-ready PDF | `95-studio.js:1523` | default | `GAP-28` |
| Backend reason: {…}. | `95-studio.js:1547`; `95-studio.js:7397` | default | `GAP-28` |
| Exported {…} · artifact {…} | `95-studio.js:1580` | default | `GAP-28` |
| Download the print-ready PDF | `95-studio.js:1590` | default | `GAP-28` |
| The file is recorded; its download link is not available in this host. | `95-studio.js:1593` | error | `GAP-28` |

### TakeHomeStudio (`95-studio.js` from line 1610)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Take-home needs the library methods | `95-studio.js:1760` | default | `GAP-28` |
| This backend does not list library.list, so no source course can be read. Update the plugin instead of using a placeholder screen. | `95-studio.js:1762` | default | `GAP-28` |

### CB_HOMEWORK_STATE_WORD (`95-studio.js` from line 1850)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Planned | `95-studio.js:1851` | default | `GAP-31` → `hw.state.proposed` |
| Done — you recorded it | `95-studio.js:1852` | default | `GAP-31` → `hw.state.self_reported_done` |
| Done — a parent recorded it | `95-studio.js:1853` | default | `GAP-31` → `hw.state.parent_reported_done` |
| Skipped | `95-studio.js:1854` | default | `GAP-31` → `hw.state.skipped` |
| Expired | `95-studio.js:1855` | default | `GAP-31` → `hw.state.expired` |

`Planned`, `Skipped` and `Expired` are single tokens, so the extraction gate never asked for them;
they are rowed by hand under `GAP-31` so the state map is complete by name. The map's sixth contract
value, `assigned`, **has no shipped word** — `GAP-31` leaves that row to the owner, and CP-001g does
not invent it here.

### CB_HOMEWORK_KIND_WORD (`95-studio.js` from line 1858)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Use it for real | `95-studio.js:1859` | default | `GAP-31` |
| Notice it | `95-studio.js:1860` | default | `GAP-31` |
| Label it | `95-studio.js:1861` | default | `GAP-31` |
| Say it aloud | `95-studio.js:1862` | default | `GAP-31` |
| Make it | `95-studio.js:1863` | default | `GAP-31` |
| Tell someone | `95-studio.js:1864` | default | `GAP-31` |

### cbHomeworkExcerpt (`95-studio.js` from line 1994)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Take this with you: {…} | `95-studio.js:1996` | default | `GAP-28` |

### cbHomeworkSheetGuard (`95-studio.js` from line 2021)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This task would print a word a take-home sheet must not carry, so it is not shown. | `95-studio.js:2028` | default | `GAP-31` |
| A field card carries at most three steps, so this task is not shown. | `95-studio.js:2031` | default | `GAP-31` |

### cbPrintHomeworkSheet (`95-studio.js` from line 2040)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Homework sheet for printing | `95-studio.js:2044` | default | `GAP-28` |

### CB_LESSON_PRINT_ROLE_WORD (`95-studio.js` from line 2087)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Your turn | `95-studio.js:2091` | default | `GAP-28` |

### CB_PRINT_FIGURE_OMITTED (`95-studio.js` from line 2176)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Figure not printed - see the lesson screen. | `95-studio.js:2176` | default | `GAP-28` |

### cbPrintMediaOmission (`95-studio.js` from line 2178)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Audio not printed - see the lesson screen. | `95-studio.js:2180` | default | `GAP-28` |

### cbLessonPrintHtml (`95-studio.js` from line 2201)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Answer this on the lesson screen. The answer key is not printed here.{…} | `95-studio.js:2234`; `95-studio.js:2249` | default | `GAP-28` |
| Your turn{…} | `95-studio.js:2247` | default | `GAP-28` |
| <!doctype html> | `95-studio.js:2258` | default | `GAP-28` |
| Coursebook · lesson{…} | `95-studio.js:2268` | default | `GAP-28` |
| Coursebook · printed from this lesson. The answer key is never part of this sheet. | `95-studio.js:2274` | default | `GAP-28` |

### HomeworkSheetCard (`95-studio.js` from line 2317)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Skipped. Nothing is owed and nothing is lost. | `95-studio.js:2346`; `95-studio.js:3035` | default | `GAP-28` |
| This task closed without a report. | `95-studio.js:2348` | default | `GAP-28` |
| A parent recorded this as done{…}. A report, not a verdict. | `95-studio.js:2350` | default | `GAP-28` |
| You recorded this as done{…}. A report, not a verdict. | `95-studio.js:2352` | default | `GAP-28` |
| Done — I will record this myself. | `95-studio.js:2353` | default | `GAP-28` |
| Take-home task: {…} | `95-studio.js:2358` | default | `GAP-28` |
| Coursebook field card | `95-studio.js:2372` | default | `GAP-28` |
| One task | `95-studio.js:2382` | default | `GAP-28` |
| Where and when | `95-studio.js:2425`; `95-studio.js:2854` | default | `GAP-28` |
| Do this | `95-studio.js:2438` | default | `GAP-28` |
| Ticks for this card: {…} | `95-studio.js:2458` | default | `GAP-28` |
| Done when | `95-studio.js:2462` | default | `GAP-28` |
| About {…} minutes · {…} | `95-studio.js:2476` | default | `GAP-28` |
| Source · | `95-studio.js:2502` | default | `GAP-28` |
| Sources · | `95-studio.js:2502` | default | `GAP-28` |
| (accessed {…}) | `95-studio.js:2519` | default | `GAP-28` |

### HomeworkSheetActions (`95-studio.js` from line 2533)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Print the sheet | `95-studio.js:2542` | default | `GAP-28` |
| Saved to the notebook | `95-studio.js:2566` | default | `GAP-28` |
| Save to notebook | `95-studio.js:2566` | default | `GAP-28` |
| Local only. Nothing is sent. | `95-studio.js:2573` | default | `GAP-28` |

### TakeThisWithYou (`95-studio.js` from line 2588)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The lesson for this section is not written yet, so there is no task to take with you. | `95-studio.js:2656` | default | `GAP-28` |
| This is the whole task. It stays in your notebook and on paper; it is not a chat. | `95-studio.js:2682` | default | `GAP-28` |
| Recorded: a parent reported this done. A report, not a mark. | `95-studio.js:2706`; `95-studio.js:3031` | default | `GAP-28` |
| Recorded: you reported this done. A report, not a mark. | `95-studio.js:2707` | default | `GAP-28` |
| Skipped. Nothing is owed, nothing is lost, and no streak breaks. | `95-studio.js:2729` | default | `GAP-28` |
| Saved to the notebook. The task itself stays a homework task, not a note. | `95-studio.js:2753` | default | `GAP-28` |
| The lesson for this section is not written yet. | `95-studio.js:2761` | default | `GAP-28` |
| Take this with you | `95-studio.js:2770`; `95-studio.js:2792`; `95-studio.js:2974` | default | `GAP-28` |
| Take this with you · {…} | `95-studio.js:2792` | default | `GAP-28` |
| Reading this lesson’s task | `95-studio.js:2795` | default | `GAP-28` |
| The task could not be read. | `95-studio.js:2811` | error | `GAP-28` |
| Reason · {…} | `95-studio.js:2813` | default | `GAP-28` |
| {…} There is nothing to take with you from this section yet, and nothing is lost. | `95-studio.js:2827` | default | `GAP-28` |
| Coursebook can write one small task from this lesson — one thing to use where you actually are. Say where and when, in one sentence. | `95-studio.js:2844` | default | `GAP-28` |
| Before dinner at our own table | `95-studio.js:2859` | default | `GAP-28` |
| Writing the task | `95-studio.js:2870` | default | `GAP-28` |
| Show me the task | `95-studio.js:2870` | default | `GAP-28` |
| One task, at most three steps, three to ten minutes. | `95-studio.js:2874` | default | `GAP-28` |
| It opens no chat and sends nothing anywhere. Printing and downloading are local. | `95-studio.js:2880` | loading | `GAP-28` |
| The sheet is open in the print dialog. | `95-studio.js:2897`; `95-studio.js:3188` | default | `GAP-28` |
| This build cannot open a print dialog. | `95-studio.js:2897`; `95-studio.js:3188` | error | `GAP-28` |
| The sheet was saved as a file on this device. | `95-studio.js:2899`; `95-studio.js:3190` | default | `GAP-28` |
| This build cannot save a file. | `95-studio.js:2899`; `95-studio.js:3190` | error | `GAP-28` |
| I did it | `95-studio.js:2911`; `95-studio.js:3162` | default | `GAP-28` |
| Not this one | `95-studio.js:2918` | default | `GAP-28` |
| Only you record it. Nothing here is marked. | `95-studio.js:2922` | default | `GAP-28` |
| This one is closed as skipped. A fresh task can be taken with you from another lesson. | `95-studio.js:2931` | default | `GAP-31` |
| This task already carries a report; it cannot be reported twice. | `95-studio.js:2932` | error | `GAP-31` |

### HomeworkRecord (`95-studio.js` from line 2987)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Recorded: the learner reported this done. A report, not a mark. | `95-studio.js:3032` | default | `GAP-28` |
| Reading this task | `95-studio.js:3065` | default | `GAP-28` |
| This task could not be read. | `95-studio.js:3081` | error | `GAP-28` |
| {…} min | `95-studio.js:3134` | default | `GAP-28` |
| This course | `95-studio.js:3140` | default | `GAP-28` |
| Hide the sheet | `95-studio.js:3150` | default | `GAP-28` |
| Show the sheet | `95-studio.js:3150` | default | `GAP-28` |
| A parent recorded this | `95-studio.js:3161` | default | `GAP-28` |

### HomeworkStudio (`95-studio.js` from line 3274)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Homework needs the homework methods | `95-studio.js:3338` | default | `GAP-28` |
| This backend does not implement homework.read, so no task can be read here. Update the plugin instead of showing a placeholder. | `95-studio.js:3340` | default | `GAP-28` |
| Tasks a learner took with them from a lesson on this device. A parent can record one as done; it is a report, never a mark, and it opens no chat. | `95-studio.js:3366` | default | `GAP-28` |
| The course names could not be read. The tasks below are unchanged. | `95-studio.js:3369` | error | `GAP-28` |
| A lesson title could not be read. The task itself is unchanged. | `95-studio.js:3372` | error | `GAP-28` |
| Homework taken with you | `95-studio.js:3379` | default | `GAP-28` |
| No homework yet | `95-studio.js:3380` | empty | `GAP-28` |
| When a learner takes a task with them from a lesson, it appears here. A task starts on a lesson page, never from this screen. | `95-studio.js:3382` | default | `GAP-28` |

### StudioBriefForm (`95-studio.js` from line 3393)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| A title is required. | `95-studio.js:3405` | default | `GAP-28` |
| Say what you want the child to be able to do. | `95-studio.js:3406` | default | `GAP-28` |
| Pick an age band. | `95-studio.js:3407` | default | `GAP-28` |
| Say the reading level in your own words. | `95-studio.js:3408` | default | `GAP-28` |
| Duration must be between 5 and 600 minutes. | `95-studio.js:3410` | default | `GAP-28` |
| Desired pages must be between 1 and 40. | `95-studio.js:3412` | default | `GAP-28` |
| Acknowledge the provider/egress disclosure before submitting. | `95-studio.js:3413` | default | `GAP-28` |
| Duplicate this brief | `95-studio.js:3448` | default | `GAP-28` |
| Write a lesson brief | `95-studio.js:3448` | default | `GAP-28` |
| Prepare a lesson for a child. You are the operator: Coursebook prepares the material for you to teach, and there is no child chat, no child persona and no grading of the child. Everything here is a plan you review before any page is generated. | `95-studio.js:3451` | default | `GAP-28` |
| From your last reflection: {…} | `95-studio.js:3456` | default | `GAP-28` |
| What and who | `95-studio.js:3462` | default | `GAP-28` |
| How this course appears in your list. | `95-studio.js:3466` | default | `GAP-28` |
| Kitchen fractions for a 9-year-old | `95-studio.js:3472` | default | `GAP-28` |
| What should the child be able to do afterwards? | `95-studio.js:3477` | default | `GAP-28` |
| Concrete beats aspirational. One skill, described as an action you can watch. | `95-studio.js:3478` | default | `GAP-28` |
| Halve and quarter a real object and explain each cut. | `95-studio.js:3484` | default | `GAP-28` |
| Starting point and content prerequisites | `95-studio.js:3489` | default | `GAP-28` |
| What they can already do, and anything they must have read or seen first. | `95-studio.js:3490` | default | `GAP-28` |
| Counts to 100, follows a recipe with help. | `95-studio.js:3496` | default | `GAP-28` |
| Age band | `95-studio.js:3504`; `95-studio.js:3791` | default | `GAP-28` |
| Reading level | `95-studio.js:3511`; `95-studio.js:3792` | default | `GAP-28` |
| Your words are enough: “Year 3, short sentences”. | `95-studio.js:3512` | default | `GAP-28` |
| Year 3, short decodable sentences | `95-studio.js:3518` | default | `GAP-28` |
| Where, how long, with what | `95-studio.js:3524` | default | `GAP-28` |
| Materials you have | `95-studio.js:3563` | default | `GAP-28` |
| One per line. Up to 20. Safety notes are written against this list. | `95-studio.js:3564` | default | `GAP-28` |
| one apple plastic knife measuring cup | `95-studio.js:3570` | default | `GAP-28` |
| A narration script is text you read aloud; it is not an audio file. | `95-studio.js:3586` | default | `GAP-28` |
| Exclusions and supervision | `95-studio.js:3589` | default | `GAP-28` |
| Leave these out | `95-studio.js:3592` | default | `GAP-28` |
| One per line: foods, topics, activities, anything the child must not meet here. | `95-studio.js:3593` | default | `GAP-28` |
| no nuts no timed pressure | `95-studio.js:3599` | empty | `GAP-28` |
| Supervision and safety | `95-studio.js:3604` | default | `GAP-28` |
| Who holds what, what the adult must do, what the child may not do alone. | `95-studio.js:3605` | default | `GAP-28` |
| An adult holds the knife; the child places the pieces. | `95-studio.js:3611` | default | `GAP-28` |
| Before you paste: provider and egress | `95-studio.js:3615` | default | `GAP-28` |
| This brief is sent to the model provider configured for this Hermes profile so the plan can be drafted. Coursebook stores no provider key and sends the brief nowhere else. Anything you paste can appear in the generated pages — do not paste a child’s full name, address, school or anything you would not hand to a provider. | `95-studio.js:3622` | default | `GAP-28` |
| I have read this and want to send this brief to the provider. | `95-studio.js:3628` | default | `GAP-28` |
| Ask for identifying details to be redacted where it is possible. | `95-studio.js:3634` | default | `GAP-28` |
| Before submitting | `95-studio.js:3643` | default | `GAP-28` |
| The brief was not saved, and nothing was started. | `95-studio.js:3653` | default | `GAP-28` |
| Saving the brief | `95-studio.js:3665` | default | `GAP-28` |
| Create the course and start the plan | `95-studio.js:3665` | default | `GAP-28` |
| This backend does not register parent.brief.create. | `95-studio.js:3671` | default | `GAP-28` |

### APPROVAL_INVALIDATION_COPY (`95-studio.js` from line 3742)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| You edited the plan after approving the lesson set. | `95-studio.js:3743` | default | `GAP-38` |
| The generated pages changed after you approved them. | `95-studio.js:3744` | default | `GAP-38` |
| You changed the course title or goal after approving the lesson set. | `95-studio.js:3745` | default | `GAP-38` |
| A newer approval replaced this one. | `95-studio.js:3746` | default | `GAP-38` |

### StudioReviewBanner (`95-studio.js` from line 3750)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The lesson set you approved no longer matches the current pages. | `95-studio.js:3761` | default | `GAP-38` |
| Export is blocked ({…}). | `95-studio.js:3766`; `95-studio.js:7392` | default | `GAP-38` |
| Approve the current lesson set before exporting. | `95-studio.js:3767` | default | `GAP-38` |

### StudioBriefView (`95-studio.js` from line 3774)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading the brief | `95-studio.js:3777` | default | `GAP-28` |
| This course has no parent brief | `95-studio.js:3781` | default | `GAP-28` |
| It was not created by parent.brief.create, or the saved record that stores it is gone. Nothing is reconstructed from a form. | `95-studio.js:3783` | default | `GAP-28` |
| Starting point | `95-studio.js:3790` | default | `GAP-28` |
| {…} minutes | `95-studio.js:3794` | default | `GAP-28` |
| None listed | `95-studio.js:3795`; `95-studio.js:3796` | empty | `GAP-28` |
| Pages / visuals / narration | `95-studio.js:3798` | default | `GAP-28` |
| {…} pages · {…} · {…} | `95-studio.js:3798` | default | `GAP-28` |
| Provider disclosure acknowledged | `95-studio.js:3799` | default | `GAP-28` |
| Redaction requested | `95-studio.js:3800` | default | `GAP-28` |
| You are the operator of this course. Coursebook drafted material for you to teach; the child never chats with it. A brief is immutable once stored — changing the teaching comes from editing the plan, and copying this brief makes a new course. | `95-studio.js:3813` | default | `GAP-28` |
| The brief | `95-studio.js:3815` | default | `GAP-28` |
| A note from your last reflection | `95-studio.js:3833` | default | `GAP-28` |
| It is shown here as a proposal. It is not applied to any brief unless you copy one. | `95-studio.js:3837` | default | `GAP-28` |
| Duplicate brief | `95-studio.js:3845` | default | `GAP-28` |
| Duplicate with the reflection note | `95-studio.js:3850` | default | `GAP-28` |

### PLAN_CHECK_LABELS (`95-studio.js` from line 3868)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| whether each objective matches the goal | `95-studio.js:3869` | default | `GAP-38` |
| whether each claim has a source that was actually read | `95-studio.js:3870` | default | `GAP-38` |
| whether the units, objectives and checks fit together | `95-studio.js:3871` | default | `GAP-38` |
| whether the schedule and time estimates add up | `95-studio.js:3872` | default | `GAP-38` |
| whether the plan follows the recipe and its limits | `95-studio.js:3873` | default | `GAP-38` |

### VALIDATION_OUTCOME_COPY (`95-studio.js` from line 3903)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The validator did not pass this draft. | `95-studio.js:3904`; `95-studio.js:4393` | error | `GAP-32` |
| The author model checked its own work; no independent check was recorded. | `95-studio.js:3905` | default | `GAP-32` |
| A different model checked this draft and passed it. | `95-studio.js:3906` | default | `GAP-32` |
| No validator record was written for this draft. | `95-studio.js:3907` | empty | `GAP-32` |

### VALIDATION_INDEPENDENCE_COPY (`95-studio.js` from line 3910)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The writing model and the checking model were different. | `95-studio.js:3911` | default | `GAP-32` |
| The same model wrote and checked the plan. | `95-studio.js:3912` | default | `GAP-32` |
| The checking model could not be identified. | `95-studio.js:3913` | error | `GAP-32` |

### RESEARCH_STATUS_COPY (`95-studio.js` from line 3916)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Research fetched its sources. | `95-studio.js:3917` | default | `GAP-32` |
| Research returned only part of its sources. | `95-studio.js:3918` | default | `GAP-32` |
| Research was unavailable, so no source could be checked. | `95-studio.js:3919` | error | `GAP-32` |

### PLAN_VALIDATION_LINES (`95-studio.js` from line 3936)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Checked by a second model | `95-studio.js:3937` | default | `GAP-32` |
| Checked by the same model | `95-studio.js:3938` | default | `GAP-32` |
| Checked by a model that could not be identified | `95-studio.js:3939` | error | `GAP-32` |
| No validator record is stored for this version | `95-studio.js:3940` | empty | `GAP-32` |
| The validator refused this version | `95-studio.js:3941` | error | `GAP-32` |
| Edited by you; this version has no validator record | `95-studio.js:3942` | default | `GAP-32` |
| Its validation record covers earlier bytes | `95-studio.js:3943` | default | `GAP-32` |

### PLAN_VALIDATION_SETTINGS_HINT (`95-studio.js` from line 3954)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| To have a different model review plans, set | `95-studio.js:3955` | default | `GAP-32` |
| plugins.entries.coursebook.settings.validator_model (and optionally validator_provider) and | `95-studio.js:3956` | default | `GAP-32` |
| allow it with plugins.entries.coursebook.llm.allow_model_override / allow_provider_override | `95-studio.js:3957` | default | `GAP-32` |
| (with allowed_models / allowed_providers), then read coursebook_status to confirm a | `95-studio.js:3958` | default | `GAP-32` |
| validator route is configured. | `95-studio.js:3959` | default | `GAP-32` |

### PLAN_VALIDATION_CONFIGURE_LINE (`95-studio.js` from line 3961)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| No different checking model is configured here; coursebook_status reports the setting to change. | `95-studio.js:3962` | empty | `GAP-32` |

### planValidationView (`95-studio.js` from line 3991)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This plan version was edited by its owner. Approval is a human review of that outline; nothing here claims a validation pass. | `95-studio.js:4010` | default | `GAP-32` |
| The plan changed after it was validated, so the recorded pass covers different bytes. | `95-studio.js:4026` | default | `GAP-32` |
| The stored record for this version is a refusal; the review panel above explains it. | `95-studio.js:4041` | default | `GAP-32` |
| The stored record passed this version. | `95-studio.js:4064` | default | `GAP-32` |
| The job line for this run is no longer on the page; this comes from the stored record. | `95-studio.js:4065` | default | `GAP-32` |
| The facts were not checked against sources, so this is not factual verification. | `95-studio.js:4079`; `95-studio.js:4137` | default | `GAP-32` |
| No validation record is bound to this exact plan version, so nothing here claims a second model. | `95-studio.js:4096` | empty | `GAP-32` |
| This plan was checked against an earlier version; a carried version is a copy, not a re-check. | `95-studio.js:4098` | default | `GAP-32` |
| The validator passed this draft. | `95-studio.js:4111` | default | `GAP-32` |
| Writing model: {…}. | `95-studio.js:4112` | default | `GAP-32` |
| Checking model: {…}. | `95-studio.js:4115` | default | `GAP-32` |
| The runtime did not report the checking model. | `95-studio.js:4116` | error | `GAP-32` |
| The sources were not checked, so a pass is not factual verification. | `95-studio.js:4118` | default | `GAP-32` |

### PlanValidationLine (`95-studio.js` from line 4147)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Checking model: {…} | `95-studio.js:4162` | default | `GAP-32` |
| Provenance rule: docs/GENERATION.md §1 (validator independence) and | `95-studio.js:4189` | default | `GAP-32` |

### planRejectView (`95-studio.js` from line 4209)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| this course | `95-studio.js:4252` | default | `GAP-32` |
| one lesson | `95-studio.js:4268` | default | `GAP-32` |
| a short course | `95-studio.js:4268` | default | `GAP-32` |
| a full course | `95-studio.js:4268` | default | `GAP-32` |
| the shape you chose | `95-studio.js:4269` | default | `GAP-32` |
| {…} holds {…} to {…} objectives | `95-studio.js:4279` | default | `GAP-32` |
| {…} holds a different number of objectives | `95-studio.js:4280` | default | `GAP-32` |
| The plan had {…} objectives; {…}. | `95-studio.js:4282` | default | `GAP-32` |
| Nothing was approved, and no lesson pages exist. | `95-studio.js:4283`; `95-studio.js:4333` | empty | `GAP-32` |
| One lesson | `95-studio.js:4287` | default | `GAP-32` |
| Short course | `95-studio.js:4287` | default | `GAP-32` |
| Full course | `95-studio.js:4287` | default | `GAP-32` |
| Shapes that hold this plan: {…}. | `95-studio.js:4289` | default | `GAP-32` |
| This goal does not fit {…} | `95-studio.js:4293` | default | `GAP-32` |
| The plan came back with {…} objectives, and {…}. No plan was written, so there is no draft to approve. Your goal and every choice you made are saved; choosing a different shape keeps the goal and changes only how much of it a course covers. | `95-studio.js:4294` | default | `GAP-32` |
| The whole plan: its size fits no legal shape | `95-studio.js:4295` | default | `GAP-32` |
| Choose a different shape | `95-studio.js:4299` | default | `GAP-32` |
| You stopped this run | `95-studio.js:4313` | default | `GAP-32` |
| The run lost its worker | `95-studio.js:4315` | default | `GAP-32` |
| The planning service did not answer | `95-studio.js:4317` | error | `GAP-32` |
| Planning stopped before a plan was written | `95-studio.js:4318` | default | `GAP-32` |
| You stopped this run for {…}. A draft plan had already been written, so it stays here, unapproved; nothing was deleted. | `95-studio.js:4321` | default | `GAP-32` |
| No plan was written for {…}. Your goal and every choice you made are saved with this plan, so running it again repeats the same brief rather than starting over. | `95-studio.js:4322` | empty | `GAP-32` |
| The run stopped before it finished, but a draft plan for {…} had already been written. It stays here, unapproved; running the brief again does not create a second course. | `95-studio.js:4324` | default | `GAP-32` |
| No plan was written for {…}. The brief is saved; running it again sends the same brief and does not create a second course. | `95-studio.js:4325` | empty | `GAP-32` |
| The run, before the plan was approved | `95-studio.js:4326` | default | `GAP-32` |
| The plan, before it was approved | `95-studio.js:4326` | default | `GAP-32` |
| What happened: {…} | `95-studio.js:4328` | default | `GAP-32` |
| No plan record was written for this run. | `95-studio.js:4328` | empty | `GAP-32` |
| The previous attempt stopped early; it is safe to start again. | `95-studio.js:4330` | default | `GAP-32` |
| A draft plan exists and is readable; it is not approved. | `95-studio.js:4332` | default | `GAP-32` |
| The plan came back with nothing to teach | `95-studio.js:4352` | default | `GAP-32` |
| The draft for {…} arrived without any objectives, so there is nothing to approve. The course, its brief and this draft are still saved; nothing was deleted. | `95-studio.js:4353` | default | `GAP-32` |
| The whole plan: no objective was written | `95-studio.js:4354` | default | `GAP-32` |
| Change the goal | `95-studio.js:4356`; `95-studio.js:6503` | default | `GAP-32` |
| The plan could not show where its facts came from | `95-studio.js:4361` | error | `GAP-32` |
| {…} of the draft could not be tied to a source the research pass actually read. This run returned the draft that was already refused instead of starting a new attempt, so nothing about it changed; the draft is saved and nothing was lost. | `95-studio.js:4363` | error | `GAP-32` |
| {…} of the draft could not be tied to a source the research pass actually read. The draft is saved, so nothing is lost. {…} | `95-studio.js:4364-4368` | error | `GAP-32` |
| Adjust this plan | `95-studio.js:4371`; `95-studio.js:4384`; `95-studio.js:6456` | default | `GAP-28` |
| Edit the plan | `95-studio.js:4372`; `95-studio.js:4385` | default | `GAP-32` |
| Run research again | `95-studio.js:4373`; `95-studio.js:4386` | default | `GAP-32` |
| The outline does not fit together yet | `95-studio.js:4376` | default | `GAP-32` |
| The plan was written but failed an outline check{…}. The draft is saved, so you can repair the outline instead of starting over.{…} | `95-studio.js:4377-4381` | error | `GAP-32` |
| Checks that did not clear: {…} | `95-studio.js:4392` | error | `GAP-32` |
| Research status: {…} | `95-studio.js:4395` | default | `GAP-32` |
| No detailed reason was recorded for this refusal. | `95-studio.js:4396` | empty | `GAP-32` |

### PlanRejectPanel (`95-studio.js` from line 4447)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Where: {…} | `95-studio.js:4466` | default | `GAP-28` |
| Your draft is still here. It is not approved, and no lesson will be written from it. | `95-studio.js:4470` | default | `GAP-28` |
| No draft was written, so there is nothing to lose by running the brief again. | `95-studio.js:4471` | empty | `GAP-28` |

### FINE_TUNE_CHIP_COPY (`95-studio.js` from line 4530)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This objective or section was changed by the course author; one revision row records it. | `95-studio.js:4531` | default | `GAP-33` |
| This change is stored and readable, but nobody has approved it. Export and any new check wait for approval. | `95-studio.js:4533` | default | `GAP-33` |
| This change was approved with the lesson set it belongs to. It is still not an independent validation. | `95-studio.js:4535` | default | `GAP-33` |

### FINE_TUNE_SECTION_ACTIONS_GAP (`95-studio.js` from line 4538)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This course serves no authored section identity, so one section cannot be revised or | `95-studio.js:4539` | error | `GAP-33` |
| regenerated from here. `lesson.revise` and `lesson.regenerate` are keyed on the `section_id` | `95-studio.js:4540` | default | `GAP-33` |
| and `page_hash` that `parent.blueprint.read` reports in `sections[]`; a pack-backed course is | `95-studio.js:4541` | default | `GAP-33` |
| composed from its pack and reports none. Nothing here invents a section id or a digest. | `95-studio.js:4542` | default | `GAP-33` |

### FINE_TUNE_EVIDENCE_CONSEQUENCE (`95-studio.js` from line 4544)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Editing this page keeps every stored attempt and the previous page version; the new page is | `95-studio.js:4545` | default | `GAP-33` |
| stored as a revision that nobody has approved, so its check stays closed and export waits. | `95-studio.js:4546` | default | `GAP-33` |

### fineTuneScopeLine (`95-studio.js` from line 4593)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| 1 section: {…} | `95-studio.js:4594` | default | `GAP-33` |

### StudioReviewDiff (`95-studio.js` from line 4602)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Review changes | `95-studio.js:4603`; `95-studio.js:4639`; `95-studio.js:5298` | default | `GAP-33` |
| The pending changes could not be read, so nothing here claims the course has none. | `95-studio.js:4616` | error | `GAP-33` |
| Reading the pending changes. | `95-studio.js:4617` | default | `GAP-33` |
| The approved lesson set matches the pages shown, so export is available. | `95-studio.js:4643` | default | `GAP-33` |
| Export is blocked. The backend’s reason: {…}. | `95-studio.js:4645` | default | `GAP-33` |
| Export is blocked and the backend returned no reason string. | `95-studio.js:4646` | error | `GAP-33` |
| No fine-tune change is waiting for review. | `95-studio.js:4652` | empty | `GAP-33` |
| plan change | `95-studio.js:4666` | default | `GAP-33` |
| Changed: {…} | `95-studio.js:4684` | default | `GAP-33` |
| Now: {…} | `95-studio.js:4689` | default | `GAP-33` |
| Before: {…} | `95-studio.js:4693` | default | `GAP-33` |
| lesson page | `95-studio.js:4711` | default | `GAP-33` |
| {…} — changed: {…} | `95-studio.js:4728` | default | `GAP-33` |
| {…} stored attempt(s) reference this section; the edit was confirmed against that consequence. | `95-studio.js:4734` | default | `GAP-33` |
| page {…}… | `95-studio.js:4739` | default | `GAP-33` |

### StudioFineTunePanel (`95-studio.js` from line 4758)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| That move would put one unit’s objectives behind a later unit, so the stored order was kept. | `95-studio.js:4896` | default | `GAP-33` |
| A later change landed after that revision, so the undo would overwrite it; nothing was written. | `95-studio.js:4899` | default | `GAP-33` |
| That structural change was already undone. | `95-studio.js:4901` | default | `GAP-33` |
| This plan has no structural change to undo. | `95-studio.js:4903` | default | `GAP-33` |
| The plan is not approved, so only a draft edit applies. | `95-studio.js:4905` | default | `GAP-33` |
| The course revision was refreshed; try again. | `95-studio.js:4909` | default | `GAP-33` |
| Order saved. {…} | `95-studio.js:4950-4955` | default | `GAP-33` |
| Undid the last structural change. Stored order: {…} | `95-studio.js:5013` | default | `GAP-33` |
| Nothing changed yet. | `95-studio.js:5128`; `95-studio.js:5993` | empty | `GAP-33` |
| This section has no authored page yet, so there is no page digest to revise. | `95-studio.js:5137` | default | `GAP-33` |
| Use “Regenerate this section” to author it first. | `95-studio.js:5138` | default | `GAP-33` |
| {…} learner attempt(s) already reference this section. | `95-studio.js:5190` | default | `GAP-33` |
| {…} Confirm to store the edit. | `95-studio.js:5191` | default | `GAP-33` |
| Section page saved as a new revision that needs review before export. | `95-studio.js:5206` | default | `GAP-33` |
| Every stored attempt and the previous page version are untouched. | `95-studio.js:5207` | default | `GAP-33` |
| Section metadata saved. The edited objective is recorded as a revision that needs review before export. | `95-studio.js:5211` | default | `GAP-33` |
| Queued regenerating 1 section: {…}. Other sections, their media and every attempt are untouched. | `95-studio.js:5269` | default | `GAP-33` |
| Fine-tune this approved course | `95-studio.js:5288` | default | `GAP-33` |
| Undo last structural change | `95-studio.js:5307` | default | `GAP-33` |
| Reorder or retitle an objective and the change is written to storage as a revision that needs review; | `95-studio.js:5318` | default | `GAP-33` |
| lesson pages, checks and attempts are not rewritten. Every move is sent with the full order, so the | `95-studio.js:5319` | default | `GAP-33` |
| order you see is the order the backend returned. | `95-studio.js:5320` | default | `GAP-33` |
| {…} in stored order | `95-studio.js:5339` | default | `GAP-33` |
| {…}. {…}. Press Alt+ArrowUp or Alt+ArrowDown to move it. | `95-studio.js:5356` | default | `GAP-33` |
| Alt+ArrowUp Alt+ArrowDown | `95-studio.js:5357` | default | `GAP-33` |
| no page yet | `95-studio.js:5387` | empty | `GAP-33` |
| page v{…} | `95-studio.js:5388` | default | `GAP-33` |
| no authored section | `95-studio.js:5394` | empty | `GAP-33` |
| Move up | `95-studio.js:5407` | default | `GAP-33` |
| Move down | `95-studio.js:5415` | default | `GAP-33` |
| Close editor | `95-studio.js:5422` | default | `GAP-33` |
| Edit section | `95-studio.js:5422` | default | `GAP-33` |
| Regenerate this section | `95-studio.js:5434` | default | `GAP-33` |
| {…} title | `95-studio.js:5449`; `95-studio.js:6863` | default | `GAP-33` |
| Stored on the objective. The section page keeps its authored prose; a retitle is a plan revision that needs review. | `95-studio.js:5451` | default | `GAP-33` |
| Section page title | `95-studio.js:5461` | default | `GAP-33` |
| Stored on the authored page through lesson.revise, fenced on the page digest this read served ({…}…). The result is a new page revision that needs review. | `95-studio.js:5464` | default | `GAP-33` |
| This section has no authored page yet, so there is no digest to revise. Regenerate this section to author one. | `95-studio.js:5465` | default | `GAP-33` |
| Evidence target | `95-studio.js:5477` | default | `GAP-33` |
| Assessment criteria | `95-studio.js:5505` | default | `GAP-33` |
| One criterion per line. Saving replaces the objective’s criteria. | `95-studio.js:5507` | default | `GAP-33` |
| This build was not served the objective’s current criteria, so this field starts empty. | `95-studio.js:5508` | default | `GAP-33` |
| Enter the criteria you want stored; leaving it untouched keeps whatever storage holds. | `95-studio.js:5509` | default | `GAP-33` |
| Save section | `95-studio.js:5526` | default | `GAP-33` |
| Unsaved changes | `95-studio.js:5539` | default | `GAP-33` |
| The section’s segment bodies are authored by the lessons job; this editor changes the page title and the objective metadata, and lesson.revise stores a new page revision that needs review before export. | `95-studio.js:5548` | default | `GAP-33` |
| Confirm the evidence consequence | `95-studio.js:5554` | default | `GAP-33` |
| {…} stored attempt(s) reference this section. {…} | `95-studio.js:5560` | default | `GAP-33` |
| Confirm and save | `95-studio.js:5568` | default | `GAP-33` |
| Keep editing | `95-studio.js:5575`; `95-studio.js:5617`; `95-studio.js:7851` | default | `GAP-33` |
| Unsaved section changes | `95-studio.js:5586`; `95-studio.js:7819` | default | `GAP-33` |
| Discard the unsaved changes to this section? | `95-studio.js:5592` | default | `GAP-33` |
| Discard changes | `95-studio.js:5610` | default | `GAP-33` |
| Regenerating this section costs about {…}–{…}, | `95-studio.js:5636` | default | `GAP-33` |
| based on what writing lessons for this course has cost so far. | `95-studio.js:5637` | default | `GAP-33` |
| The price for this section appears here once you queue it. | `95-studio.js:5638` | default | `GAP-33` |
| We work out what one section costs when you queue it — this course has no earlier lesson run to go by yet. | `95-studio.js:5639` | default | `GAP-33` |
| Queue regenerating 1 section | `95-studio.js:5650` | default | `GAP-33` |
| Queued {…} · job {…} | `95-studio.js:5677` | default | `GAP-33` |
| This section costs {…}– | `95-studio.js:5684` | default | `GAP-33` |
| {…} to regenerate. | `95-studio.js:5685` | default | `GAP-33` |
| Not covered — no supporting source: | `95-studio.js:5734` | default | `GAP-33` |
| Scope shortfall — fewer supporting capabilities: | `95-studio.js:5735` | default | `GAP-33` |

### StudioPlanView (`95-studio.js` from line 5748)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The course was updated elsewhere; press Save changes again. | `95-studio.js:6009` | default | `GAP-28` |
| This plan is approved; start a new plan version to change it. | `95-studio.js:6011` | default | `GAP-28` |
| That objective already has content or learning state, so it cannot be removed. | `95-studio.js:6013` | error | `GAP-28` |
| Plan saved{…}. The edit is versioned and marks the lesson set as needing review until it is approved again. | `95-studio.js:6023` | default | `GAP-28` |
| This version changed after it was validated, so approval is withheld. Re-read the plan or run a new version. | `95-studio.js:6046` | default | `GAP-28` |
| This version has no passing validation record, so approval is withheld. Repair the plan above or run a new version. | `95-studio.js:6047` | default | `GAP-28` |
| The plan digest is not available yet. Re-read the plan and try again. | `95-studio.js:6056` | error | `GAP-28` |
| The plan was re-read; press Approve plan again. | `95-studio.js:6072` | default | `GAP-28` |
| The course was updated elsewhere; press Approve plan again. | `95-studio.js:6073` | default | `GAP-28` |
| Plan approved. The outline and activities are now fixed; the generated pages are a separate approval. | `95-studio.js:6078` | default | `GAP-28` |
| {…} The saved choices could not be read, so no plan was started. | `95-studio.js:6123` | error | `GAP-28` |
| {…} Nothing was lost: your goal and choices are still saved. | `95-studio.js:6148` | error | `GAP-28` |
| The course was updated elsewhere; press Start a new plan version again. | `95-studio.js:6174` | default | `GAP-28` |
| A new draft plan version was created. The approved lesson set stops applying until the new plan and its pages are approved. | `95-studio.js:6179` | default | `GAP-28` |
| The saved brief could not be read yet, so this run cannot be repeated. Try again once the plan finishes reading. | `95-studio.js:6239` | error | `GAP-28` |
| {…}{…} The saved draft is unchanged. | `95-studio.js:6255` | default | `GAP-28` |
| The planning service answered with the run that already finished, so nothing new started. The refused draft is unchanged; try again shortly. | `95-studio.js:6262` | error | `GAP-28` |
| A new planning run started from the same brief: research runs again and the draft it writes is a new version. The refused draft stays readable until a new plan replaces it. | `95-studio.js:6268` | error | `GAP-28` |
| Reading the plan | `95-studio.js:6308` | default | `GAP-28` |
| The plan could not be read | `95-studio.js:6312`; `95-studio.js:7036` | error | `GAP-28` |
| Draft plan {…} · version {…} is still stored. | `95-studio.js:6335` | default | `GAP-28` |
| This course has no plan yet | `95-studio.js:6373` | default | `GAP-28` |
| Your goal and the choices you made are saved. Write the plan to pick up where it stopped — you do not need to start a new course. | `95-studio.js:6377` | default | `GAP-28` |
| Writing the plan | `95-studio.js:6384` | default | `GAP-28` |
| Write this course's plan | `95-studio.js:6384` | default | `GAP-28` |
| This course has no plan attached and nothing is stored to resume from; nothing is invented to fill the gap. | `95-studio.js:6395` | default | `GAP-28` |
| No plan is attached to this course, so there is nothing to review. Start a new brief. | `95-studio.js:6396` | empty | `GAP-28` |
| About {…} week{…} | `95-studio.js:6440` | default | `GAP-28` |
| plan {…}… | `95-studio.js:6443` | default | `GAP-28` |
| Edit plan | `95-studio.js:6456` | default | `GAP-28` |
| Save changes | `95-studio.js:6460` | default | `GAP-28` |
| Approve plan | `95-studio.js:6469` | default | `GAP-28` |
| Write unit {…} lessons | `95-studio.js:6479` | default | `GAP-28` |
| Generate missing lessons | `95-studio.js:6481` | default | `GAP-28` |
| Generate lessons | `95-studio.js:6482` | default | `GAP-28` |
| Ask for a change | `95-studio.js:6491` | default | `GAP-28` |
| Start a new plan version | `95-studio.js:6491` | default | `GAP-28` |
| This starts a new course; this one and its evidence stay. | `95-studio.js:6514` | default | `GAP-28` |
| THE GOAL YOU ARE APPROVING | `95-studio.js:6525` | default | `GAP-28` |
| This version cannot be approved: it changed after its validation record was written, so that record covers different bytes. Run a new plan version, or edit the plan to take ownership of it as your own outline. | `95-studio.js:6552` | error | `GAP-28` |
| This version cannot be approved: the validator refused it. Repair it above; approving a refused draft is never offered. | `95-studio.js:6554` | error | `GAP-28` |
| This version was edited by you, so approval is a human review of your own outline; it is not presented as validated. | `95-studio.js:6556` | default | `GAP-28` |
| This version cannot be approved: no passing validation record is stored for it. Edit the plan to own it, or run a new plan version. | `95-studio.js:6558` | error | `GAP-28` |
| Approval is withheld until this version has a validation record: a draft with no record is not approvable. | `95-studio.js:6559` | default | `GAP-28` |
| Approving the plan approves this outline and these activities. It does not approve a single generated page: the lesson set is approved later, by its own hash. | `95-studio.js:6566` | default | `GAP-28` |
| Lessons cannot be generated from this plan version: {…} | `95-studio.js:6580` | error | `GAP-28` |
| The authored outline (its sections and research) belongs to the version that was written with the plan, and this version has changes it does not cover, so Generate lessons is withheld rather than offered as a second failure. Start a new plan version to author an outline that covers every objective. | `95-studio.js:6581` | default | `GAP-28` |
| Re-running generation reuses every lesson already authored at this plan version and only authors what is missing. Nothing is paid for twice. | `95-studio.js:6636` | default | `GAP-28` |
| What this plan does not cover | `95-studio.js:6658` | default | `GAP-28` |
| The plan declares these parts of the goal it will not teach. Read them before you approve: approving this outline approves the course without them. | `95-studio.js:6661` | default | `GAP-28` |
| The plan’s own wording | `95-studio.js:6692` | default | `GAP-28` |
| OUTLINE AND ACTIVITIES ({…}) | `95-studio.js:6705` | default | `GAP-28` |
| UNIT {…} | `95-studio.js:6714` | default | `GAP-28` |
| {…} {…} title | `95-studio.js:6741` | default | `GAP-28` |
| {…} {…} evidence target | `95-studio.js:6766` | default | `GAP-28` |
| Add a {…} | `95-studio.js:6847` | default | `GAP-28` |
| New {…} {…} title | `95-studio.js:6855` | default | `GAP-28` |
| New {…} {…} evidence target | `95-studio.js:6876` | default | `GAP-28` |
| Add objective | `95-studio.js:6907` | default | `GAP-28` |
| Sources and review notes | `95-studio.js:6917` | default | `GAP-28` |
| Sources come from the research that produced this plan. If research was unavailable the plan says so; no citation is invented here. | `95-studio.js:6920` | error | `GAP-28` |
| No source is recorded for this plan | `95-studio.js:6928` | empty | `GAP-28` |
| No source was recorded for this plan. Nothing on this plan is presented as cited, and no excerpt is invented to fill the gap. | `95-studio.js:6930` | empty | `GAP-28` |
| Car activities are passenger-only. The driver never handles material. | `95-studio.js:6938` | default | `GAP-28` |
| A draft plan can be edited freely. An approved plan is changed only by starting a new version, so what you approved stays exact. | `95-studio.js:6943` | default | `GAP-28` |

### LearnerPlanView (`95-studio.js` from line 6962)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The plan's progress could not be read | `95-studio.js:7046` | error | `GAP-28` |
| This backend cannot check whether a plan is being written for this course. | `95-studio.js:7050` | error | `GAP-28` |
| Start the first lesson | `95-studio.js:7080` | default | `GAP-28` |
| Open the first section | `95-studio.js:7088` | default | `GAP-28` |
| The outline is approved. Coursebook writes the lesson pages below; the section list is the approved outline. | `95-studio.js:7097` | default | `GAP-28` |

### StudioBlueprintView (`95-studio.js` from line 7149)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading the pages | `95-studio.js:7152` | default | `GAP-28` |
| The pages could not be read | `95-studio.js:7156` | error | `GAP-28` |
| The parent guide is what you follow while teaching. It can quote the answer guide; the learner pages never do. | `95-studio.js:7166` | default | `GAP-28` |
| These are the learner pages. No answer key is included here — answers live in their own tab and are a different file role. | `95-studio.js:7167` | default | `GAP-28` |
| The answer guide. It is served by course id only, so it is never reachable from a learner’s lesson surface, and export keeps it out of the learner pages. | `95-studio.js:7168` | default | `GAP-28` |
| The narration script you read aloud. It is text, not an audio file, and it is also inside the parent guide. | `95-studio.js:7169` | default | `GAP-28` |
| Every source this plan recorded, with the support verdict it earned. | `95-studio.js:7170` | default | `GAP-28` |
| {…} file{…} in this tab | `95-studio.js:7181` | default | `GAP-28` |
| content hash {…}… | `95-studio.js:7182` | default | `GAP-28` |
| No source is recorded for this course | `95-studio.js:7191` | empty | `GAP-28` |
| No source was recorded for this course. Nothing here is presented as cited, and no excerpt is invented to fill the gap. | `95-studio.js:7193` | empty | `GAP-28` |
| Nothing generated for this tab yet | `95-studio.js:7198` | empty | `GAP-28` |
| This course asked for no narration, or no lesson has been generated yet. | `95-studio.js:7201` | default | `GAP-28` |
| The plan must be approved and its lessons generated before this tab has text. | `95-studio.js:7202` | default | `GAP-28` |
| clipped | `95-studio.js:7223` | default | `GAP-35` → `studio.tab.clipped` |
| sha256 {…} | `95-studio.js:7231` | default | `GAP-35` |
| · the served text was clipped at the tab limit | `95-studio.js:7231` | default | `GAP-35` → `studio.tab.clipped_note` |

### StudioExportPanel (`95-studio.js` from line 7244)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The course was updated elsewhere; press Approve this lesson set again. | `95-studio.js:7284` | default | `GAP-34` |
| Export gate | `95-studio.js:7326` | default | `GAP-34` → `studio.gate.title` |
| Plan | `95-studio.js:7331` | default | `GAP-34` → `studio.gate.row.plan` |
| Lesson set approval | `95-studio.js:7332` | default | `GAP-34` → `studio.gate.row.approval` |
| Approved content hash | `95-studio.js:7334` | default | `GAP-34` |
| Current content hash | `95-studio.js:7338` | default | `GAP-34` |
| Final approval | `95-studio.js:7343` | default | `GAP-34` |
| Approving the plan approved the outline and its activities. This gate is separate: it approves the generated lesson set by its content hash, and any later edit to the plan, the pages or the course title clears it. | `95-studio.js:7347` | default | `GAP-34` |
| Lesson set approved{…}{…}. | `95-studio.js:7352-7354` | default | `GAP-34` |
| There is no approved plan to approve a lesson set for yet. | `95-studio.js:7363` | default | `GAP-34` |
| No generated pages exist yet, so there is nothing to approve. Generate the lessons from the Plan view first. | `95-studio.js:7364` | empty | `GAP-34` |
| This backend does not implement parent.final.approve yet. | `95-studio.js:7369` | default | `GAP-34` |
| Approving the lesson set | `95-studio.js:7378` | default | `GAP-34` |
| Approve this lesson set | `95-studio.js:7378` | default | `GAP-34` |
| Export is available: the approved lesson set matches the pages shown. | `95-studio.js:7384` | default | `GAP-34` |
| Pack archive (parent guide, learner pages, answer guide). | `95-studio.js:7407` | default | `GAP-34` |
| Printable PDF: selectable text, low-ink layout, no color-only answers. | `95-studio.js:7413` | default | `GAP-34` |
| Export the approved files | `95-studio.js:7419` | default | `GAP-34` |
| The pack minima reported these problems: | `95-studio.js:7432` | default | `GAP-34` |
| Exported files | `95-studio.js:7446` | default | `GAP-34` |
| Export {…} · {…} · content hash {…} | `95-studio.js:7449` | default | `GAP-34` |
| The pack carries parent guide, learner pages and answer guide. Narration stays an audio role, so an authored text script is not exported as a narration file: it is the Audio & visuals tab and part of the parent guide. | `95-studio.js:7465` | default | `GAP-34` |
| Exported files never include attempts, notebook notes, reflections, transcripts or provider settings. | `95-studio.js:7467` | default | `GAP-34` |
| Download PDF | `95-studio.js:7499` | default | `GAP-34` |
| Download pack archive | `95-studio.js:7501` | default | `GAP-34` |
| Download export record | `95-studio.js:7502` | default | `GAP-34` |
| Session-bound, expiring link served by this host’s artifact route. A filesystem path never leaves the backend. | `95-studio.js:7510` | default | `GAP-34` |
| Host artifact route. | `95-studio.js:7511` | default | `GAP-34` |

### StudioReflectionView (`95-studio.js` from line 7527)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| A reflection is parent-reported. It is not evidence of learning, it is never graded, and it is excluded from every exported pack. Its only purpose is to seed your next brief. | `95-studio.js:7567` | default | `GAP-28` |
| How did it go? | `95-studio.js:7569` | default | `GAP-28` |
| What would you revisit? | `95-studio.js:7579` | default | `GAP-28` |
| Optional. This note is offered to your next draft as a proposal, never applied silently. | `95-studio.js:7580` | default | `GAP-28` |
| The quarter-to-eighth cut needed a second demonstration. | `95-studio.js:7586` | default | `GAP-28` |
| Offer this note to my next draft. | `95-studio.js:7593` | default | `GAP-28` |
| Record reflection | `95-studio.js:7602` | default | `GAP-28` |
| Start the next brief from this note | `95-studio.js:7608` | default | `GAP-28` |
| Plan hash | `95-studio.js:7621` | default | `GAP-28` |
| REFLECTIONS ({…}) | `95-studio.js:7625` | default | `GAP-28` |
| No reflections recorded for this course yet. | `95-studio.js:7627` | empty | `GAP-28` |
| parent-reported · {…} | `95-studio.js:7640` | default | `GAP-28` |
| for next draft | `95-studio.js:7641` | default | `GAP-28` |

### StudioDetail (`95-studio.js` from line 7659)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| All parent courses | `95-studio.js:7778` | default | `GAP-28` |
| Parent course | `95-studio.js:7785` | default | `GAP-28` |
| Parent preparation | `95-studio.js:7789` | default | `GAP-28` |
| Export ready | `95-studio.js:7793` | default | `GAP-28` |
| Parent view · what your child did and what you observed, never points, levels or rankings. | `95-studio.js:7803` | default | `GAP-28` |
| You are the operator · revision {…} | `95-studio.js:7809` | default | `GAP-28` |
| Studio view | `95-studio.js:7815` | default | `GAP-28` |
| The section editor has unsaved changes. Leaving discards them and leaves storage exactly as it is now. | `95-studio.js:7832` | default | `GAP-28` |
| Discard and leave | `95-studio.js:7845` | default | `GAP-28` |

### Home defaults and ChildSafeLine (`30-home.js` from line 4740)

`ChildSafeLine` and the defaults line render in the take-home pack's Home copy and again on the Home
surface. The Home sweep rows them in §1a-§1c of `CP-031-sweep-game.md`; they are repeated here
because this file's take-home screen renders the same component, and a restyle must not change one
copy and leave the other. `GAP-41` is the defaults line, `GAP-42` is the objective-state vocabulary.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Default view · | `30-home.js:4751` | default | `GAP-41` |
| · This classroom · | `30-home.js:4760` | default | `GAP-41` |
| · Child-safe defaults | `30-home.js:4770` | default | `GAP-41` |
| · Session · {…} min | `30-home.js:4775`; `30-home.js:4802` | default | `GAP-41` |
| Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no streaks · XP is cosmetic Game feedback | `30-home.js:4798` | default | `GAP-41` |
| Open Coursebook settings (accessible name) | `30-home.js:4811` | default | `GAP-41` |

### Rows removed in the a11bc0e4 re-derivation

Two strings rowed at `5d2b303e` do not ship at `a11bc0e4`, and one earlier string stays retired.
Each is shown with the wording that replaced it, so a reviewer reads a re-word, not a silent
deletion.

| retired string | replaced by |
|---|---|
| The plan was written but failed an outline check{…}. The draft is saved, so you can repair the outline instead of starting over. (`5d2b303e`) | The plan was written but failed an outline check{…}. The draft is saved, so you can repair the outline instead of starting over.{…} (`95-studio.js:4377-4381``) |
| This course has no plan attached. Start a new course to generate one; nothing is invented to fill the gap. (`5d2b303e`) | This course has no plan attached and nothing is stored to resume from; nothing is invented to fill the gap. (`95-studio.js:6395`) |
| Research and drafting run in the background; this screen fills itself when the plan is written. Nothing is shown from a template, and there is no progress percentage to show. (retired at `475efefc`) | — the sentence is gone; the writing state is now worded by `PLAN_WAIT_BAND` and `planWaitBand`, rowed above. |

**Offline and overflow evidence:** this file has no `useOnline()` branch, so a failed read names
the error rather than an offline state (`GAP-35`). Its only overflow copy is the tab-limit badge
`clipped` (7223) and `· the served text was clipped at the tab limit` (7231).
