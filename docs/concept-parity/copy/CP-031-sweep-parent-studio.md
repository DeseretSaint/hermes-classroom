# CP-031b — Parent Studio (and its take-home pack) shipped-string sweep

Card: **CP-031b** (`t_adc9bdee`), follow-up to CP-031. Closes **GAP-30**: this is the literal-by-literal
sweep of `desktop/src/95-studio.js` (all 6931 lines), not the named-region sample in
`CP-025b-studio.md`. Docs only; no product string changed.

Row citations in this file were re-derived on the strings at `475efefc`: each `file:line` is the
line that carries the row's own words today. Section headings keep a coarse range as navigation;
the row citation is the authoritative anchor.

**Surface:** Parent Studio (GM-006) and the take-home pack it prints (GM-005). Every string below is
rendered by `desktop/src/95-studio.js` unless the `source` cell says otherwise. `Copy id` names the
proposed deck row; `GAP-28` owns the section, and a new gap id is named where the row is a category
the deck (and CP-031's sample) never inventoried at all.

## How this file was produced

1. The whole file was lexed (comments, strings and regex literals separated) and every literal was
   reviewed; the candidate list is not a keyword grep.
2. Every row cites `file:line`. A row that lists several lines renders the same words from each; the
   shipped code repeats labels per branch.
3. Strings that are **not** user-visible are excluded and named here so nothing is dropped silently:
   RPC method names (`jobs.get`, `takehome.preview`, …), storage keys (`homework-index.v1`),
   `data-*`/`id` attribute values, DOM ids (`cb-finetune-title-*`), CSS class strings, MIME types,
   filenames, and the **left-hand keys** of the enum→copy maps (`no_generated_lesson`, `completed`) —
   the map's rendered value is rowed, its key is a contract token. Keycap names (`ArrowUp`) are
   excluded; the visible shortcut hint (`Alt+ArrowUp Alt+ArrowDown`, `95-studio.js:4780`) is included.
4. Backend-supplied text is marked `field:` only where the row is the surface's own wording; a
   message rendered verbatim from the backend is tagged `(backend text)` and is a *source*, not a
   deck row.

States: default, loading, empty, error, offline, overflow, dialog, refusal.

## 1. Shared option maps (the studio's own enums → copy)

These maps are the parent's vocabulary for a brief. All are `default` state, all unsourced today.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Home / Classroom / Outdoors / Car / Library / Community / Other (setting options) | `95-studio.js:18-19`, `95-studio.js:22` | default | `GAP-28 studio.setting.{home,classroom,outdoors,car,library,community,other}` |
| No visuals / Diagrams / Illustrations | `95-studio.js:26-28` | default | `GAP-28 studio.visual.{none,diagrams,illustrations}` |
| No narration / A script I read aloud | `95-studio.js:31-32` | default | `GAP-28 studio.narration.{none,script}` |
| 3-5 / 5-7 / 7-9 / 8-10 / 10-12 / 12-14 / 14-16 / 16+ (age bands) | `95-studio.js:34` | default | `GAP-28 studio.age_band.*` |
| Too easy / About right / Too hard (difficulty) | `95-studio.js:39-41` | default | `GAP-28 studio.difficulty.{easy,about_right,too_hard}` |
| Brief / Plan / Pages / Export / Reflection (studio views) | `95-studio.js:48` | default | `GAP-28 studio.view.*` |
| Parent guide / Learner pages / Answers / Audio & visuals / Sources (page tabs) | `95-studio.js:51-52`, `95-studio.js:54` | default | `GAP-28 studio.tab.*` |
| Recall / Comprehension / Production / Tell the difference / Procedure / Transfer (evidence targets) | `95-studio.js:58-60`, `95-studio.js:63-65` | default | `GAP-28 studio.target.*` |
| Plan draft / Plan approved / Plan superseded | `95-studio.js:68-70` | default | `GAP-28 studio.plan_state.*` |
| Lesson set not approved / Lesson set approved / Changes need review | `95-studio.js:73-75` · `95-studio.js:72-76, 3269` | default | `GAP-28 studio.lesson_state.*` |
| The generated lesson set has not been approved. Approval is a separate step from approving the plan. | `95-studio.js:79` | refusal | `GAP-28 studio.blocked.no_final_approval` |
| Changes need review. The approved lesson set no longer matches the pages shown, so export is blocked until you approve them again. | `95-studio.js:80` | refusal | `GAP-28 studio.blocked.changes_need_review` |
| The plan is not approved, so there are no pages to export. | `95-studio.js:81` | refusal | `GAP-28 studio.blocked.plan_not_approved` |
| No lesson pages have been generated yet. | `95-studio.js:82` | refusal | `GAP-28 studio.blocked.no_generated_content` |
| The plan is not approved. | `95-studio.js:86` | refusal | `GAP-28 studio.refusal.plan_not_approved` |
| Approve the exact lesson set first. | `95-studio.js:87` | refusal | `GAP-28 studio.refusal.no_final_approval` |
| The pages changed after approval; review and approve them again. | `95-studio.js:88` | refusal | `GAP-28 studio.refusal.changes_need_review` |
| There is no generated content to export. | `95-studio.js:89` | refusal | `GAP-28 studio.refusal.no_generated_content` |
| This course came from an imported pack. Use Library → Export pack for it. | `95-studio.js:90` | refusal | `GAP-28 studio.refusal.course_pack_backed` |
| The generated lessons do not meet the pack’s teaching minima yet. | `95-studio.js:91` | refusal | `GAP-28 studio.refusal.minima` |
| The files could not be written. Nothing was exported. | `95-studio.js:92` | refusal | `GAP-28 studio.refusal.write_failed` |

## 2. Editor fields, badges and the job line (`95-studio.js:155-402`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| No plan yet | `95-studio.js:206` | empty | `GAP-28 studio.plan.none` |
| {plan state} · v{n} | `95-studio.js:210` | default | `GAP-28 studio.plan.version` (`computed:plan_version`) |
| Waiting to start. Nothing is spent until it begins. | `95-studio.js:229` | loading | `GAP-28 studio.job.queued` |
| Stopping. The step already under way finishes, then this stops before the next one. | `95-studio.js:234` | loading | `GAP-28 studio.job.stopping` |
| Working on it — {progress message} | `95-studio.js:240` | loading | `GAP-28 studio.job.running` |
| Finished — {progress message} | `95-studio.js:244` | default | `GAP-28 studio.job.finished` |
| It stopped early. The work already saved is kept; start the stage again to finish it. | `95-studio.js:249` | error | `GAP-28 studio.job.interrupted` |
| Cancelled before it finished. The brief and any work that had already been saved are kept. | `95-studio.js:255` | error | `GAP-28 studio.job.cancelled` |
| It stopped before finishing. | `95-studio.js:262` | error | `GAP-28 studio.job.failed` |
| Technical detail | `95-studio.js:269` | error | `GAP-28 studio.job.technical` |
| It runs in the background; leaving this page does not stop it. | `95-studio.js:523` | loading | `GAP-28 studio.job.background` |
| Cancelling / Cancel generation | `95-studio.js:531` | loading | `GAP-28 studio.job.cancel` |
| Starting / Run this stage again | `95-studio.js:541` | error | `GAP-28 studio.job.retry` |

## 3. Landing, entrances and the shared pack words (`95-studio.js:405-610`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Parent Studio needs the v6 authoring methods | `95-studio.js:570` | error | `GAP-28 studio.unsupported.title` |
| This backend does not list library.list, so no authored course can be read. Update the plugin instead of using a placeholder screen. | `95-studio.js:572` | error | `GAP-28 studio.unsupported.body` |
| Open Capabilities | `95-studio.js:573` | error | `GAP-28 studio.unsupported.action` |
| Reading your parent courses | `95-studio.js:577` | loading | `GAP-28 studio.list.loading` |
| Your parent courses could not be read | `95-studio.js:581` | error | `GAP-28 studio.list.error` |
| Try again | `95-studio.js:583` · `95-studio.js:433, 706, 820, 1217, 2394, 2655, 3297, 5542, 6058, 6161` | error | `GAP-28 studio.retry` |
| No lesson plans yet | `95-studio.js:588` | empty | `GAP-28 studio.plans.empty` |
| A lesson plan starts from a short brief: the child’s age and reading level, where you will teach, what you have, what to leave out, and what you want them to be able to do. Coursebook drafts a plan for you to review before any lesson page is written. | `95-studio.js:590-592` | empty | `GAP-28 studio.plans.empty_body` |
| New lesson plan | `95-studio.js:593` · `95-studio.js:443, 478` | default | `GAP-28 studio.primary` |
| Parent Studio | `95-studio.js:625` | default | `GAP-28 studio.title` |
| Plans for your child | `95-studio.js:626` | default | `GAP-28 studio.lead` |
| Prepare a lesson for a child. Each brief you write is kept as its own plan, so you can compare versions without losing the first. | `95-studio.js:628` | default | `GAP-28 studio.caption` |
| Lesson plan for a child | `95-studio.js:643` | default | `GAP-28 studio.plan.card_title` |
| updated {when} | `95-studio.js:644` | default | `GAP-28 studio.plan.updated` (`computed:updated_at`) |
| Open plan | `95-studio.js:647` | default | `GAP-28 studio.plan.open` |
| My lesson plans / Take-home from a lesson / Homework | `95-studio.js:671-672`, `95-studio.js:674` | default | `GAP-28 studio.entrance.*` |
| Print a take-home pack | `95-studio.js:681` | default | `GAP-28 studio.takehome.print_pack` |
| A parent guide, the learner page and a separate answer guide, bound to this lesson. | `95-studio.js:682` | default | `GAP-28 studio.takehome.print_pack.hint` |
| Prepare an activity plan | `95-studio.js:686` | default | `GAP-28 studio.takehome.activity_plan` |
| The same lesson, composed for a short parent-led activity away from the screen. | `95-studio.js:687` | default | `GAP-28 studio.takehome.activity_plan.hint` |
| Send with homework | `95-studio.js:691` | default | `GAP-28 studio.takehome.homework_sheet` |
| One real-world practice task on a single sheet the learner can carry with them. | `95-studio.js:692` | default | `GAP-28 studio.takehome.homework_sheet.hint` |
| For me to teach from / For the learner to hold | `95-studio.js:697-698` | default | `GAP-28 studio.takehome.audience.*` |
| Cover / Parent guide / Learner page / Plate / Answer guide | `95-studio.js:51`, `95-studio.js:704`, `95-studio.js:706` | default | `GAP-28 studio.page.*` |
| The first page of the printed pack. | `95-studio.js:715` | default | `GAP-28 studio.page.cover.note` |
| For the adult preparing the lesson. It is not the learner’s page. | `95-studio.js:716` | default | `GAP-28 studio.page.parent_guide.note` |
| For the learner. This page carries no answers. | `95-studio.js:717` | default | `GAP-28 studio.page.learner_page.note` |
| Captioned orientation art. It is not the lesson text. | `95-studio.js:718` | default | `GAP-28 studio.page.plate.note` |
| Parent only. Keep this page back. | `95-studio.js:719` | default | `GAP-28 studio.page.answer_guide.note` |
| Draft / Approved / Exported / Superseded (shipped pack-state words) | `95-studio.js:724-726` | default | `GAP-28 studio.pack.*` |
| Game course / Textbook course | `95-studio.js:730-731` | default | `GAP-28 studio.mode.game` / `studio.mode.textbook` |
| Take-home pack / Activity plan / Homework sheet | `95-studio.js:735-737` | default | `GAP-28 studio.kind.*` |
| The lesson for this objective has not been written yet. | `95-studio.js:742` | refusal | `GAP-28 studio.blocked.no_generated_lesson` |
| A parent-authored plan is not a learner source. | `95-studio.js:743` · `95-studio.js:592, 605` | refusal | `GAP-28 studio.blocked.parent_only_course` |
| This procedure has only illustration art, so it cannot print as authority. | `95-studio.js:744` | refusal | `GAP-28 studio.blocked.ai_art_as_procedure` |
| Approve the exact pages above before exporting. | `95-studio.js:749` | refusal | `GAP-28 studio.export_refusal.pack_not_approved` |
| The pages changed after approval. Approve the pages you can see again. | `95-studio.js:750` | refusal | `GAP-28 studio.export_refusal.approval_stale` |
| The preview moved on. Preview the pages again, then approve them. | `95-studio.js:751` | refusal | `GAP-28 studio.export_refusal.preview_hash_mismatch` |
| This pack is already exported. The file below is that export. | `95-studio.js:752` | refusal | `GAP-28 studio.export_refusal.already_exported` |
| The print font cannot draw every character in this lesson, so no PDF was written. Nothing was corrupted. | `95-studio.js:754` | refusal | `GAP-28 studio.print_font` |
| The PDF renderer failed. The pack is kept; the export did not run. | `95-studio.js:755` | refusal | `GAP-28 studio.export_refusal.renderer_failed` |
| This draft was superseded. Start a fresh draft from the lesson. | `95-studio.js:757` | refusal | `GAP-28 studio.export_refusal.superseded` |
| Course / Take-home (source modes) | `95-studio.js:672` | default | `GAP-28 studio.takehome.source_mode.*` |
| This lesson cannot be printed yet. | `95-studio.js:855` | refusal | `GAP-28 studio.pack.blocked_title` |
| This lesson cannot be printed: {reason}. | `95-studio.js:856` | refusal | `GAP-28 studio.pack.blocked_body` |

### 3.1 The child-safe defaults line (`30-home.js:4790-4803`, mounted at `95-studio.js:631`)

`ChildSafeLine` is defined in `30-home.js` but the Parent Studio landing is the surface that renders
it (`95-studio.js:631`), so its strings are Parent Studio copy and were only in CP-025b's **sample**
until now. The home route's twin line is rendered by the Home route itself, and its strings are rowed
in `CP-031-sweep-game.md` §1a as `GAP-41 home.defaults.*` — the words are at `30-home.js:4751-4752`,
`4760-4761`, `4770` and `4775`, not in `CP-022-home.md`, which carries no inventory row at all. Only
the Parent Studio instance is rowed here.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no streaks · XP is cosmetic Game feedback | `30-home.js:4798` | default | `GAP-28 studio.child_safe` |
| · Session · {n} min | `30-home.js:4775` | default | `GAP-28 studio.child_safe.session` (`computed:sessionMinutes`) |
| Open Coursebook settings (accessible name) | `30-home.js:4811` | default | `GAP-28 studio.child_safe.settings_label` |
| Settings | `95-studio.js:555` | default | `GAP-28 studio.child_safe.settings` |

## 4. Take-home shelf and source picker (`95-studio.js:697-930`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading the courses you teach | `95-studio.js:888` | loading | `GAP-28 studio.shelf.loading` |
| The courses you teach could not be read | `95-studio.js:892` | error | `GAP-28 studio.shelf.error` |
| No learner course to draw from | `95-studio.js:899` | empty | `GAP-28 studio.shelf.empty_title` |
| A take-home pack is printed from a Game or Textbook lesson you already teach. Write or import a learner course first; a parent plan belongs under My lesson plans. | `95-studio.js:901` | empty | `GAP-28 studio.shelf.empty_body` |
| Check again | `95-studio.js:902` | empty | `GAP-28 studio.shelf.recheck` |
| Take-home from a lesson / Draw a take-home from a course you already teach | `95-studio.js:672`, `95-studio.js:919` | default | `GAP-28 studio.shelf.title` / `studio.shelf.lead` |
| The source course is not copied, changed or re-approved. The pack binds to this lesson’s version and hash, so printing it never touches the course. | `95-studio.js:921` | default | `GAP-28 studio.shelf.note` |
| Courses you can draw a take-home from (accessible name) | `95-studio.js:925` | default | `GAP-28 studio.shelf.group_label` |
| Untitled course | `95-studio.js:956` | empty | `GAP-28 studio.shelf.untitled` |
| Bundled / Imported / Written here (provenance words) | `95-studio.js:554` | default | `GAP-28 studio.provenance.*` |
| Learner course (fallback learner label) | `95-studio.js:962` | empty | `GAP-28 studio.shelf.learner_course` |
| Choose this course | `95-studio.js:971` | default | `GAP-28 studio.shelf.choose_course` |
| Source lesson / Choose a lesson | `95-studio.js:996-997` | default | `GAP-28 studio.source.title` / `studio.source.choose` |
| Pick the written lesson to print. The preview is read-only: the course, its plan and its approval are not touched. | `95-studio.js:999` | default | `GAP-28 studio.source.note` |
| Back to courses | `95-studio.js:1000` | default | `GAP-28 studio.source.back` |
| Reading the lessons in this course | `95-studio.js:1003` | loading | `GAP-28 studio.source.loading` |
| This course’s lessons could not be read | `95-studio.js:1006` | error | `GAP-28 studio.source.error` |
| This course has no written lessons yet | `95-studio.js:1012` | empty | `GAP-28 studio.source.empty_title` |
| A take-home pack prints the lesson as it already exists. Write the lesson in the course first, then come back. | `95-studio.js:1014` | empty | `GAP-28 studio.source.empty_body` |
| Choose another course | `95-studio.js:1015` | empty | `GAP-28 studio.source.choose_other` |
| written lesson / written lessons (row state words) | `95-studio.js:1025` | default | `GAP-28 studio.source.lesson_word` |
| No child account and no child chat: the adult prepares and prints. | `95-studio.js:1028` | default | `GAP-28 studio.child_chat` |
| {n}. {objective title} (source row label) | `95-studio.js:1079` | default | `GAP-28 studio.source.row` (`computed:objective_ordinal_title`) |
| Evidence target: {target} · {lesson state} | `95-studio.js:1084` | default | `GAP-28 studio.source.evidence` |
| · world plates available / · no world art | `95-studio.js:1085` | default | `GAP-28 studio.source.plates` / `studio.source.no_plates` |
| Preview this lesson / Not printable yet | `95-studio.js:1096` | default / refusal | `GAP-28 studio.source.preview` / `studio.source.not_printable` |
| Print proof of the pack pages (accessible name) | `95-studio.js:1128` | default | `GAP-28 studio.proof.label` |
| A4 / Letter (print profiles) | `95-studio.js:1122` | default | `GAP-28 studio.print_profile.a4` / `studio.print_profile.letter` |
| Print proof | `95-studio.js:1142` | default | `GAP-28 studio.proof.title` |
| {n} pages · {paper} · {m} pt margins · selectable text | `95-studio.js:1145`, `95-studio.js:3798` | default | `GAP-28 studio.proof.meta` (`computed:proof_meta` over `plural(list.length, 'page', 'pages')`, `paper`, `margin`) |
| Page {n} of {m} | `95-studio.js:1205` | default | `GAP-28 studio.proof.page` (`computed:proof_page`) |
| Text alternative: {alt} | `95-studio.js:1225` | default | `GAP-28 studio.proof.alt` |

## 5. Take-home pack panel (`95-studio.js:1066-1400`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Take-home from a lesson / Take-home | `95-studio.js:672` | default | `GAP-28 studio.pack.title` |
| Back to the lesson list | `95-studio.js:1292` | default | `GAP-28 studio.pack.back` |
| Evidence target: {target} · Lesson | `95-studio.js:5477` | default | `GAP-28 studio.pack.evidence` |
| Source: {course} · lesson v{n} · state {state} | `95-studio.js:1324` | default | `GAP-28 studio.pack.source_line` |
| Source content hash: {hash or —} | `95-studio.js:1329` | default | `GAP-28 studio.pack.source_hash` |
| Printing this pack does not change the course, its plan or its approval. | `95-studio.js:1331` | default | `GAP-28 studio.pack.readonly` |
| What to make | `95-studio.js:1335` | default | `GAP-28 studio.pack.kind_label` |
| What to make from this lesson (accessible name) | `95-studio.js:1338` | default | `GAP-28 studio.pack.kind_group` |
| Who holds this copy | `95-studio.js:1381` | default | `GAP-28 studio.pack.audience_label` |
| Composing the pages / Preview the pages | `95-studio.js:1420` | loading / default | `GAP-28 studio.pack.preview` |
| The pages could not be composed | `95-studio.js:1425` | error | `GAP-28 studio.pack.preview_error` |
| Recorded sources | `95-studio.js:1447` | default | `GAP-28 studio.pack.sources` |
| {title} · {url} · {support status} (source row) | `95-studio.js:1458` | default | `GAP-28 studio.pack.source_row` (`field:takehome.preview.sources`) |
| This lesson records no external sources. | `95-studio.js:1468` | empty | `GAP-28 studio.pack.sources_empty` |
| Approval and print | `95-studio.js:1480` | default | `GAP-28 studio.pack.approval_title` |
| Previewed pages: {n} · preview hash: {hash} | `95-studio.js:1483` | default | `GAP-28 studio.previewed` |
| Draft {pack id} · revision {n}. Approval covers exactly the pages above. | `95-studio.js:1488` | default | `GAP-28 studio.pack.draft` |
| {state word} on {date} · approval hash: {hash} | `95-studio.js:1494` | default | `GAP-28 studio.pack.state_line` |
| Saving the draft / Save this draft | `95-studio.js:1502` | loading / default | `GAP-28 studio.save_draft` |
| Approving the pages / Approve these pages | `95-studio.js:1510` | loading / default | `GAP-28 studio.approve` |
| PDF exported / Printing the PDF / Export the print-ready PDF | `95-studio.js:1520`, `95-studio.js:1522-1523` | loading / default | `GAP-28 studio.export_pdf` |
| Backend reason: {reason or “none reported”}. | `95-studio.js:1547` | refusal | `GAP-28 studio.pack.backend_reason` |
| Exported {when} · artifact {id} | `95-studio.js:1580` | default | `GAP-28 studio.pack.exported_line` |
| take-home-pack.pdf (download name) | `95-studio.js:1588` | default | `GAP-28 studio.pack.filename` |
| Download the print-ready PDF | `95-studio.js:1590` | default | `GAP-28 studio.pack.download` |
| The file is recorded; its download link is not available in this host. | `95-studio.js:1593` | error | `GAP-28 studio.pack.no_download` |
| Take-home needs the library methods | `95-studio.js:1760` | error | `GAP-28 studio.takehome.unsupported_title` |
| This backend does not list library.list, so no source course can be read. Update the plugin instead of using a placeholder screen. | `95-studio.js:1762` | error | `GAP-28 studio.takehome.unsupported_body` |

## 6. Homework — the sheet, the card and the record (`95-studio.js:1677-2940`)

This is the GM-008 surface inside the studio file. `GAP-23` already proposes the load-bearing rows;
the sweep adds every remaining literal. Two whole enum→copy maps (`CB_HOMEWORK_STATE_WORD`,
`CB_HOMEWORK_KIND_WORD`) and the sheet's two guard sentences had no gap at all — see **GAP-31**.

### 6.1 The homework state and kind maps

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Planned / Done — you recorded it / Done — a parent recorded it / Skipped / Expired | `95-studio.js:1852-1853` | default | `GAP-31 hw.state.{proposed,self_reported_done,parent_reported_done,skipped,expired}` |
| Use it for real / Notice it / Label it / Say it aloud / Make it / Tell someone | `95-studio.js:1859-1864` | default | `GAP-31 hw.kind.{real_world_use,observe,label,practice,make,teach_back}` |

### 6.2 The sheet and its print path (`95-studio.js:1779-2164`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Take this with you: {task title or “one task”} (accessible name) | `95-studio.js:2770` · `95-studio.js:1786, 1940` | default | `GAP-23 hw.sheet.accessible_name` |
| This task would print a word a take-home sheet must not carry, so it is not shown. | `95-studio.js:2028` | refusal | `GAP-31 hw.sheet.guard.word` |
| A field card carries at most three steps, so this task is not shown. | `95-studio.js:2031` | refusal | `GAP-31 hw.sheet.guard.steps` |
| Homework sheet for printing (print document title) | `95-studio.js:2044` | default | `GAP-23 hw.sheet.print_title` |
| homework-sheet.html (download name) | `95-studio.js:2288` | default | `GAP-23 hw.sheet.filename` |
| Skipped. Nothing is owed and nothing is lost. | `95-studio.js:2346` · `95-studio.js:1929, 2607` | empty | `GAP-23 hw.completion.skipped` |
| This task closed without a report. | `95-studio.js:2348` | empty | `GAP-23 hw.record.closed_no_report` |
| A parent recorded this as done{ on {date}}. A report, not a verdict. | `95-studio.js:2350-2352` | default | `GAP-23 hw.completion.parent_card` |
| You recorded this as done{ on {date}}. A report, not a verdict. | `95-studio.js:2350-2352` | default | `GAP-23 hw.completion.learner_card` |
| Done — I will record this myself. | `95-studio.js:2353` | default | `GAP-23 hw.record.self_pending` |
| Take-home task: {title} / Coursebook field card / One task | `95-studio.js:2358`, `95-studio.js:2382` | default | `GAP-23 hw.card.title` / `hw.card.masthead` / `hw.card.one_task` |
| Where and when / Do this / Done when | `95-studio.js:2425`, `95-studio.js:2438`, `95-studio.js:2462` · `95-studio.js:2007, 2020, 2044` | default | `GAP-23 hw.card.where` / `hw.card.do` / `hw.card.done_when` |
| Ticks for this card: {ticks} | `95-studio.js:2458` | default | `GAP-23 hw.card.ticks` |
| About {n} minutes · {kind word or “Away from the screen”} | `95-studio.js:2476` | default | `GAP-23 hw.card.minutes` (`computed:estimated_minutes`) |
| Source · / Sources · | `95-studio.js:2502` | default | `GAP-23 hw.card.source` |
| (accessed {date}) | `95-studio.js:2519` | default | `GAP-23 hw.card.accessed` |
| Print the sheet | `95-studio.js:2542` | default | `GAP-23 hw.action.print` |
| Download | `95-studio.js:1590` | default | `GAP-23 hw.action.download` |
| Saved to the notebook / Save to notebook | `95-studio.js:2566` | default | `GAP-23 hw.action.save` |
| Local only. Nothing is sent. | `95-studio.js:2573` | default | `GAP-23 hw.sheet.local` |

### 6.3 Take this with you — the lesson-side flow (`95-studio.js:2164-2559`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The lesson for this section is not written yet, so there is no task to take with you. | `95-studio.js:2656` | empty | `GAP-23 hw.action.no_source_lesson` |
| This is the whole task. It stays in your notebook and on paper; it is not a chat. | `95-studio.js:2682` | default | `GAP-23 hw.sheet.note` |
| Recorded: a parent reported this done. A report, not a mark. | `95-studio.js:2706` · `95-studio.js:2282, 2603` | default | `GAP-23 hw.completion.parent` |
| Recorded: you reported this done. A report, not a mark. | `95-studio.js:2707` | default | `GAP-23 hw.completion.learner` |
| Recorded: the learner reported this done. A report, not a mark. | `95-studio.js:3032` | default | `GAP-23 hw.completion.learner_reported` |
| Skipped. Nothing is owed, nothing is lost, and no streak breaks. | `95-studio.js:2729` | default | `GAP-31 hw.completion.skipped_streak` |
| Saved to the notebook. The task itself stays a homework task, not a note. | `95-studio.js:2753` | default | `GAP-23 hw.action.saved` |
| The lesson for this section is not written yet. | `95-studio.js:2761` | empty | `GAP-23 hw.action.no_source_lesson_title` |
| Take this with you / Take this with you · {section title} (accessible name) | `95-studio.js:2770`, `95-studio.js:2792` · `95-studio.js:2346, 2368, 2546` | default | `GAP-23 hw.action` |
| Reading this lesson’s task | `95-studio.js:2795` | loading | `GAP-23 hw.action.loading` |
| The task could not be read. | `95-studio.js:2811` | error | `GAP-23 hw.action.error` |
| Reason · {code} | `95-studio.js:2813` | error | `GAP-23 hw.action.reason` |
| Coursebook can write one small task from this lesson — one thing to use where you actually are. Say where and when, in one sentence. | `95-studio.js:2844` | empty | `GAP-23 hw.action.empty_body` |
| Where and when / Before dinner at our own table (placeholder) | `95-studio.js:2425`, `95-studio.js:2859` · `95-studio.js:2430, 2435` | default | `GAP-23 hw.action.where` / `hw.action.where_placeholder` |
| Writing the task / Show me the task | `95-studio.js:2870` | loading / default | `GAP-23 hw.action.write` |
| One task, at most three steps, three to ten minutes. | `95-studio.js:2874` | default | `GAP-23 hw.action.limits` |
| It opens no chat and sends nothing anywhere. Printing and downloading are local. | `95-studio.js:2880` | default | `GAP-23 hw.sheet.local` |
| The sheet is open in the print dialog. / This build cannot open a print dialog. | `95-studio.js:2897` | default / error | `GAP-23 hw.print.opened` / `hw.print.unavailable` |
| The sheet was saved as a file on this device. / This build cannot save a file. | `95-studio.js:2899` | default / error | `GAP-23 hw.download.saved` / `hw.download.unavailable` |
| Recording / I did it | `95-studio.js:2911` | loading / default | `GAP-23 hw.record.done` |
| Skipping / Not this one (and the compact `Skip`) | `95-studio.js:2918` | loading / default | `GAP-23 hw.record.skip` |
| Only you record it. Nothing here is marked. | `95-studio.js:2922` | default | `GAP-23 hw.record.only` |
| This one is closed as skipped. A fresh task can be taken with you from another lesson. | `95-studio.js:2931` | empty | `GAP-23 hw.record.closed_skipped` |
| This task already carries a report; it cannot be reported twice. | `95-studio.js:2932` | refusal | `GAP-31 hw.record.already_reported` |
| There is nothing to take with you from this section yet, and nothing is lost. | `95-studio.js:2827` | empty | `GAP-23 hw.action.blocked_body` |

The two completion handlers are separate components and word the learner differently: the
lesson-side flow (`2600-2604`) says “the learner reported”, the task card (`2280-2284`) says “you
reported”. Same fact, two sentences — the deck needs both, so no row may cite both lines.

### 6.4 The record, the list and the studio tab (`95-studio.js:2559-2940`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading this task | `95-studio.js:3065` | loading | `GAP-23 hw.record.loading` |
| This task could not be read. | `95-studio.js:3081` | error | `GAP-23 hw.record.error` |
| This course | `95-studio.js:3140` | default | `GAP-23 hw.record.course_fallback` |
| Hide the sheet / Show the sheet | `95-studio.js:3150` | default | `GAP-23 hw.record.sheet_toggle` |
| A parent recorded this | `95-studio.js:3161` | default | `GAP-23 hw.record.parent_done` |
| Homework needs the homework methods | `95-studio.js:3338` | error | `GAP-23 hw.unsupported_title` |
| This backend does not implement homework.read, so no task can be read here. Update the plugin instead of showing a placeholder. | `95-studio.js:3340` | error | `GAP-23 hw.unsupported_body` |
| Tasks a learner took with them from a lesson on this device. A parent can record one as done; it is a report, never a mark, and it opens no chat. | `95-studio.js:3366` | default | `GAP-23 hw.studio.caption` |
| The course names could not be read. The tasks below are unchanged. | `95-studio.js:3369` | error | `GAP-31 hw.list.courses_error` |
| A lesson title could not be read. The task itself is unchanged. | `95-studio.js:3372` | error | `GAP-31 hw.list.lesson_title_error` |
| Homework taken with you | `95-studio.js:3379` | default | `GAP-23 hw.list.title` |
| No homework yet | `95-studio.js:3380` | empty | `GAP-23 hw.list.empty` |
| When a learner takes a task with them from a lesson, it appears here. A task starts on a lesson page, never from this screen. | `95-studio.js:3382` | empty | `GAP-23 hw.list.empty_body` |
## 7. Write-a-brief form and the stored brief (`95-studio.js:2940-3400`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| A title is required. | `95-studio.js:3405` | error | `GAP-28 studio.form.err.title` |
| Say what you want the child to be able to do. | `95-studio.js:3406` | error | `GAP-28 studio.form.err.goal` |
| Pick an age band. | `95-studio.js:3407` | error | `GAP-28 studio.form.err.age` |
| Say the reading level in your own words. | `95-studio.js:3408` | error | `GAP-28 studio.form.err.reading` |
| Duration must be between 5 and 600 minutes. | `95-studio.js:3410` | error | `GAP-28 studio.form.err.duration` |
| Desired pages must be between 1 and 40. | `95-studio.js:3412` | error | `GAP-28 studio.form.err.pages` |
| Acknowledge the provider/egress disclosure before submitting. | `95-studio.js:3413` | error | `GAP-28 studio.form.err.egress` |
| Duplicate this brief / Write a lesson brief | `95-studio.js:3448` | default | `GAP-28 studio.brief.title` / `studio.brief.duplicate` |
| Prepare a lesson for a child. You are the operator: Coursebook prepares the material for you to teach, and there is no child chat, no child persona and no grading of the child. Everything here is a plan you review before any page is generated. | `95-studio.js:3451` | default | `GAP-28 studio.operator` |
| From your last reflection: {note} | `95-studio.js:3456` | default | `GAP-28 studio.brief.from_reflection` |
| What and who | `95-studio.js:3462` | default | `GAP-28 studio.brief.section.what` |
| Title | `95-studio.js:983` | default | `GAP-28 studio.brief.field.title` |
| How this course appears in your list. | `95-studio.js:3466` | default | `GAP-28 studio.brief.field.title_hint` |
| Kitchen fractions for a 9-year-old (placeholder) | `95-studio.js:3472` | default | `GAP-28 studio.brief.field.title_placeholder` |
| What should the child be able to do afterwards? | `95-studio.js:3477` | default | `GAP-28 studio.brief.field.goal` |
| Concrete beats aspirational. One skill, described as an action you can watch. | `95-studio.js:3478` | default | `GAP-28 studio.brief.field.goal_hint` |
| Halve and quarter a real object and explain each cut. (placeholder) | `95-studio.js:3484` | default | `GAP-28 studio.brief.field.goal_placeholder` |
| Starting point and content prerequisites | `95-studio.js:3489` | default | `GAP-28 studio.brief.field.start` |
| What they can already do, and anything they must have read or seen first. | `95-studio.js:3490` | default | `GAP-28 studio.brief.field.start_hint` |
| Counts to 100, follows a recipe with help. (placeholder) | `95-studio.js:3496` | default | `GAP-28 studio.brief.field.start_placeholder` |
| Age band | `95-studio.js:3504` | default | `GAP-28 studio.brief.field.age` |
| Reading level | `95-studio.js:3511` | default | `GAP-28 studio.brief.field.reading` |
| Your words are enough: “Year 3, short sentences”. | `95-studio.js:3512` | default | `GAP-28 studio.brief.field.reading_hint` |
| Year 3, short decodable sentences (placeholder) | `95-studio.js:3518` | default | `GAP-28 studio.brief.field.reading_placeholder` |
| Where, how long, with what | `95-studio.js:3524` | default | `GAP-28 studio.brief.section.where` |
| Setting / Minutes / Pages | `95-studio.js:555` | default | `GAP-28 studio.brief.field.setting` / `field.minutes` / `field.pages` |
| Materials you have | `95-studio.js:3563` | default | `GAP-28 studio.brief.field.materials` |
| One per line. Up to 20. Safety notes are written against this list. | `95-studio.js:3564` | default | `GAP-28 studio.brief.field.materials_hint` |
| one apple / plastic knife / measuring cup (placeholder) | `95-studio.js:3570` | default | `GAP-28 studio.brief.field.materials_placeholder` |
| Visuals / Narration | `95-studio.js:2185` | default | `GAP-28 studio.brief.field.visuals` / `field.narration` |
| A narration script is text you read aloud; it is not an audio file. | `95-studio.js:3586` | default | `GAP-28 studio.brief.field.narration_hint` |
| Exclusions and supervision | `95-studio.js:3589` | default | `GAP-28 studio.brief.section.exclusions` |
| Leave these out | `95-studio.js:3592` | default | `GAP-28 studio.brief.field.exclusions` |
| One per line: foods, topics, activities, anything the child must not meet here. | `95-studio.js:3593` | default | `GAP-28 studio.brief.field.exclusions_hint` |
| no nuts / no timed pressure (placeholder) | `95-studio.js:3599` | default | `GAP-28 studio.brief.field.exclusions_placeholder` |
| Supervision and safety | `95-studio.js:3604` | default | `GAP-28 studio.brief.field.supervision` |
| Who holds what, what the adult must do, what the child may not do alone. | `95-studio.js:3605` | default | `GAP-28 studio.brief.field.supervision_hint` |
| An adult holds the knife; the child places the pieces. (placeholder) | `95-studio.js:3611` | default | `GAP-28 studio.brief.field.supervision_placeholder` |
| Before you paste: provider and egress | `95-studio.js:3615` | default | `GAP-28 studio.brief.egress.title` |
| This brief is sent to the model provider configured for this Hermes profile so the plan can be drafted. Coursebook stores no provider key and sends the brief nowhere else. Anything you paste can appear in the generated pages — do not paste a child’s full name, address, school or anything you would not hand to a provider. | `95-studio.js:3622` | default | `GAP-28 studio.brief.egress.body` |
| I have read this and want to send this brief to the provider. | `95-studio.js:3628` | default | `GAP-28 studio.brief.egress.ack` |
| Ask for identifying details to be redacted where it is possible. | `95-studio.js:3634` | default | `GAP-28 studio.brief.egress.redact` |
| Before submitting | `95-studio.js:3643` | default | `GAP-28 studio.brief.review` |
| The brief was not saved, and nothing was started. | `95-studio.js:3653` | error | `GAP-28 studio.brief.not_saved` |
| Saving the brief / Create the course and start the plan | `95-studio.js:3665` | loading / default | `GAP-28 studio.brief.submit` |
| Cancel | `95-studio.js:255` | default | `GAP-28 studio.cancel` |
| This backend does not register parent.brief.create. | `95-studio.js:3671` | error | `GAP-28 studio.brief.unsupported` |
| Reading the brief | `95-studio.js:3777` | loading | `GAP-28 studio.brief.reading` |
| This course has no parent brief | `95-studio.js:3781` | empty | `GAP-28 studio.brief.none_title` |
| It was not created by parent.brief.create, or the saved record that stores it is gone. Nothing is reconstructed from a form. | `95-studio.js:3783` | empty | `GAP-28 studio.brief.none_body` |
| Goal / Starting point / Age band / Reading level / Setting / Duration / Materials / Exclusions / Supervision / Pages / visuals / narration / Provider disclosure acknowledged / Redaction requested (brief facts) | `95-studio.js:31`, `95-studio.js:3395-3396`, `95-studio.js:3410`, `95-studio.js:3504`, `95-studio.js:3511`, `95-studio.js:3604`, `95-studio.js:3790`, `95-studio.js:3799-3800` | default | `GAP-28 studio.brief.fact.*` |
| None listed | `95-studio.js:3795` · `95-studio.js:3308, 3309` | empty | `GAP-28 studio.brief.fact.none` |
| You are the operator of this course. Coursebook drafted material for you to teach; the child never chats with it. A brief is immutable once stored — changing the teaching comes from editing the plan, and copying this brief makes a new course. | `95-studio.js:3813` | default | `GAP-28 studio.operator.course` |
| The brief / Plan / Job / Submitted | `95-studio.js:3815`, `95-studio.js:3825` | default | `GAP-28 studio.brief.meta.*` |
| A note from your last reflection | `95-studio.js:3833` | default | `GAP-28 studio.brief.reflection_note` |
| It is shown here as a proposal. It is not applied to any brief unless you copy one. | `95-studio.js:3837` | default | `GAP-28 studio.brief.reflection_note_hint` |
| Duplicate brief / Duplicate with the reflection note | `95-studio.js:3845`, `95-studio.js:3850` · `95-studio.js:3358, 3363` | default | `GAP-28 studio.brief.duplicate.*` |

### 7.1 The approval banner on a superseded lesson set (`95-studio.js:3255-3284`)

`StudioReviewBanner` renders whenever the stored approval row is `superseded`. Its reason sentence is
`APPROVAL_INVALIDATION_COPY[approval.invalidated_reason]` — four reasons plus a fallback — and the
second line is the export status. Nothing here is local state: the banner is derived from the
approval row. New gap: **GAP-38**, because neither CP-025b nor CP-031's first cut had a row for any
of these sentences, and "Changes need review" with no cause is exactly what a restyle can produce.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Changes need review (banner heading — same words as `72-76`, rendered again by the banner) | `95-studio.js:75` | refusal | `GAP-28 studio.lesson_state.changes_need_review` |
| You edited the plan after approving the lesson set. | `95-studio.js:3743` | refusal | `GAP-38 studio.banner.reason.plan_edited` |
| The generated pages changed after you approved them. | `95-studio.js:3744` | refusal | `GAP-38 studio.banner.reason.content_changed` |
| You changed the course title or goal after approving the lesson set. | `95-studio.js:3745` | refusal | `GAP-38 studio.banner.reason.course_edited` |
| A newer approval replaced this one. | `95-studio.js:3746` | refusal | `GAP-38 studio.banner.reason.replaced` |
| The lesson set you approved no longer matches the current pages. | `95-studio.js:3761` | refusal | `GAP-38 studio.banner.reason.unknown` |
| Approve the current lesson set before exporting. | `95-studio.js:3767` | refusal | `GAP-38 studio.banner.export_approve` |

The banner's `EXPORT_BLOCKED_COPY[reason]` branch (`3279`) renders the same sentence as the export
gate, so both lines are cited on the one `GAP-34` row in §11; the fallback (`3280`) is the banner's
own wording and is a `GAP-38` row here. `3280` is what a parent reads when the approval is
superseded and the export record names no blocked reason, so it cannot be dropped as a duplicate of
the ready-state line.

### 7.2 The plan-check reason labels (`95-studio.js:3381-3400`)

`{reasons}` in "Checks that did not clear: {reasons}" (§8, `3849`) is built by `planCheckLabel()`
from five frozen sentences. The first cut rowed only `structure`, so the deck could word the frame
and not the reasons. New gap: **GAP-38** — author the five as one family.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| whether each objective matches the goal | `95-studio.js:3869` | default | `GAP-38 studio.check.alignment` |
| whether each claim has a source that was actually read | `95-studio.js:3870` | default | `GAP-38 studio.check.sources` |
| whether the units, objectives and checks fit together | `95-studio.js:3871` | default | `GAP-38 studio.check.structure` |
| whether the schedule and time estimates add up | `95-studio.js:3872` | default | `GAP-38 studio.check.schedule` |
| whether the plan follows the recipe and its limits | `95-studio.js:3873` | default | `GAP-38 studio.check.policy` |

`planCheckLabel()` (`3390-3400`) also falls back for unrecognised check text; that fallback is
`GAP-28 studio.reject.checks`'s companion and carries no new sentence.

## 8. Plan validation, refusal and the review diff (`95-studio.js:3390-4200`)

This block is where the product states whether a second model checked the plan. `GAP-28` covers the
section, but the *verdict* family is firmware-level copy — a restyle that paraphrases it can turn
`model_assessed` into a claim of independent validation. New: **GAP-32**.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The validator did not pass this draft. | `95-studio.js:3904` · `95-studio.js:3417, 3850` | refusal | `GAP-32 studio.verify.rejected` |
| The author model checked its own work; no independent check was recorded. | `95-studio.js:3905` | default | `GAP-32 studio.verify.same_model` |
| A different model checked this draft and passed it. | `95-studio.js:3906` | default | `GAP-32 studio.verify.independent` |
| No validator record was written for this draft. | `95-studio.js:3907` | default | `GAP-32 studio.verify.no_record` |
| The writing model and the checking model were different. | `95-studio.js:3911` | default | `GAP-32 studio.verify.models_differ` |
| The same model wrote and checked the plan. | `95-studio.js:3912` | default | `GAP-32 studio.verify.models_same` |
| The checking model could not be identified. | `95-studio.js:3913` | default | `GAP-32 studio.verify.models_unknown` |
| Research fetched its sources. / Research returned only part of its sources. / Research was unavailable, so no source could be checked. | `95-studio.js:3917-3919` | default / error | `GAP-32 studio.verify.research.*` |
| Checked by a second model / Checked by the same model / Checked by a model that could not be identified | `95-studio.js:3937-3939` | default | `GAP-32 studio.verify.badge.*` |
| No validator record is stored for this version / The validator refused this version / Edited by you; this version has no validator record / Its validation record covers earlier bytes | `95-studio.js:3940-3943` | default / refusal | `GAP-32 studio.verify.state.*` |
| To have a different model review plans, set plugins.entries.coursebook.settings.validator_model (and optionally validator_provider) and allow it with plugins.entries.coursebook.llm.allow_model_override / allow_provider_override (with allowed_models / allowed_providers), then read coursebook_status to confirm the validator route is configured. | `95-studio.js:3957` | empty | `GAP-32 studio.verify.configure` |
| No different checking model is configured here; coursebook_status reports the setting to change. | `95-studio.js:3962` | empty | `GAP-32 studio.verify.not_configured` |
| This plan version was edited by its owner. Approval is a human review of that outline; nothing here claims a validation pass. | `95-studio.js:4010` | default | `GAP-32 studio.verify.owner_edited` |
| The plan changed after it was validated, so the recorded pass covers different bytes. | `95-studio.js:4026` | refusal | `GAP-32 studio.verify.stale` |
| The stored record for this version is a refusal; the review panel above explains it. | `95-studio.js:4041` | refusal | `GAP-32 studio.verify.refusal_record` |
| The stored record passed this version. | `95-studio.js:4064` | default | `GAP-32 studio.verify.passed_record` |
| The job line for this run is no longer on the page; this comes from the stored record. | `95-studio.js:4065` | default | `GAP-32 studio.verify.stored_record` |
| The facts were not checked against sources, so this is not factual verification. | `95-studio.js:4079` · `95-studio.js:3592, 3650` | default | `GAP-32 studio.verify.not_factual` |
| No validation record is bound to this exact plan version, so nothing here claims a second model. | `95-studio.js:4096` | default | `GAP-32 studio.verify.no_binding` |
| This plan was checked against an earlier version; a carried version is a copy, not a re-check. | `95-studio.js:4098` | default | `GAP-32 studio.verify.carried` |
| The validator passed this draft. | `95-studio.js:4111` | default | `GAP-32 studio.verify.passed` |
| Writing model: {model}. / Checking model: {model}. / The runtime did not report the checking model. | `95-studio.js:4112`, `95-studio.js:4115-4162` | default | `GAP-32 studio.verify.model_line` |
| The sources were not checked, so a pass is not factual verification. | `95-studio.js:4118` | default | `GAP-32 studio.verify.sources_unchecked` |
| Checking model: {model} (validation line) | `95-studio.js:4115-4162` | default | `GAP-32 studio.verify.checking_model` |
| Technical detail | `95-studio.js:269` · `95-studio.js:269, 3690, 3921` | error | `GAP-28 studio.job.technical` |
| Provenance rule: docs/GENERATION.md §1 (validator independence) and docs/HARNESS-STATUS.md. | `95-studio.js:4189` | default | `GAP-32 studio.verify.provenance_rule` |
| You stopped this run / The run lost its worker / The planning service did not answer / Planning stopped before a plan was written | `95-studio.js:4313`, `95-studio.js:4315`, `95-studio.js:4317-4318` | error | `GAP-28 studio.reject.cause.*` |
| You stopped this run for {goal}. A draft plan had already been written, so it stays here, unapproved; nothing was deleted. | `95-studio.js:4321` | error | `GAP-28 studio.reject.cancelled_kept` |
| No plan was written for {goal}. Your goal and every choice you made are saved with this plan, so running it again repeats the same brief rather than starting over. | `95-studio.js:4322` | error | `GAP-28 studio.reject.cancelled_none` |
| The run stopped before it finished, but a draft plan for {goal} had already been written. It stays here, unapproved; running the brief again does not create a second course. | `95-studio.js:4324` | error | `GAP-28 studio.reject.failed_kept` |
| No plan was written for {goal}. The brief is saved; running it again sends the same brief and does not create a second course. | `95-studio.js:4325` | error | `GAP-28 studio.reject.failed_none` |
| The run, before the plan was approved / The plan, before it was approved | `95-studio.js:4326` | error | `GAP-28 studio.reject.subject` |
| What happened: {plain reason} / No plan record was written for this run. | `95-studio.js:4328` | error | `GAP-28 studio.reject.what_happened` |
| The previous attempt stopped early; it is safe to start again. | `95-studio.js:4330` | error | `GAP-28 studio.reject.safe_retry` |
| A draft plan exists and is readable; it is not approved. | `95-studio.js:4332` | error | `GAP-28 studio.reject.draft_exists` |
| Nothing was approved, and no lesson pages exist. | `95-studio.js:4283` | error | `GAP-28 studio.reject.nothing_approved` |
| The plan came back with nothing to teach | `95-studio.js:4352` | refusal | `GAP-28 studio.reject.empty_title` |
| The draft for {goal} arrived without any objectives, so there is nothing to approve. The course, its brief and this draft are still saved; nothing was deleted. | `95-studio.js:4353` | refusal | `GAP-28 studio.reject.empty_body` |
| The whole plan: no objective was written | `95-studio.js:4354` | refusal | `GAP-28 studio.reject.empty_detail` |
| Change the goal / Try again | `95-studio.js:583`, `95-studio.js:4356` · `95-studio.js:3817-3818, 3832` | refusal | `GAP-28 studio.reject.change_goal` / `studio.reject.retry` |
| The plan could not show where its facts came from | `95-studio.js:4361` | refusal | `GAP-28 studio.reject.unsourced_title` |
| Edit the plan / Run research again | `95-studio.js:4372-4373` · `95-studio.js:3833-3834, 3842-3843` | refusal | `GAP-28 studio.reject.edit` / `studio.reject.research` |
| One part / {n} parts of the draft could not be tied to a source the research pass actually read. The draft is saved, so nothing is lost. {Trying again runs the research pass again… / Run research again to start a new attempt…} | `95-studio.js:4363-4364` | refusal | `GAP-28 studio.reject.unsourced_body` |
| The outline does not fit together yet | `95-studio.js:4376` | refusal | `GAP-28 studio.reject.outline_title` |
| The plan was written but failed an outline check{: why}. The draft is saved, so you can repair the outline instead of starting over. | `95-studio.js:4377` | refusal | `GAP-28 studio.reject.outline_body` |
| Checks that did not clear: {reasons} | `95-studio.js:4392` | refusal | `GAP-28 studio.reject.checks` (each reason comes from §7.2, `GAP-38 studio.check.*`) |
| Research status: {plain reason} / No detailed reason was recorded for this refusal. | `95-studio.js:4395` | refusal | `GAP-28 studio.reject.research_status` |
| Where: {surface} | `95-studio.js:4466` | refusal | `GAP-28 studio.reject.where` |
| Your draft is still here. It is not approved, and no lesson will be written from it. | `95-studio.js:4470` | refusal | `GAP-28 studio.reject.kept` |
| No draft was written, so there is nothing to lose by running the brief again. | `95-studio.js:4471` | refusal | `GAP-28 studio.reject.none` |
| Starting | `95-studio.js:541` | loading | `GAP-28 studio.job.starting` |
| Edited / Needs review / Approved (revision states) | `95-studio.js:724` | default | `GAP-33 studio.revision.*` |
| This objective or section was changed by the course author; one revision row records it. | `95-studio.js:4531` | default | `GAP-33 studio.revision.edited_note` |
| This change is stored and readable, but nobody has approved it. Export and any new check wait for approval. | `95-studio.js:4533` | default | `GAP-33 studio.revision.needs_review_note` |
| This change was approved with the lesson set it belongs to. It is still not an independent validation. | `95-studio.js:4535` | default | `GAP-33 studio.revision.approved_note` |
| This course serves no authored section identity, so one section cannot be revised or regenerated from here. `lesson.revise` and `lesson.regenerate` are keyed on the `section_id` and `page_hash` that `parent.blueprint.read` reports in `sections[]`; a pack-backed course is composed from its pack and reports none. Nothing here invents a section id or a digest. | `95-studio.js:4540-4541` | refusal | `GAP-33 studio.finetune.no_section` |
| Editing this page keeps every stored attempt and the previous page version; the new page is stored as a revision that nobody has approved, so its check stays closed and export waits. | `95-studio.js:4545-4546` | default | `GAP-33 studio.finetune.consequence` |
| Review changes | `95-studio.js:4603` · `95-studio.js:4027, 4063, 4721` | default | `GAP-33 studio.review.title` |
| The pending changes could not be read, so nothing here claims the course has none. | `95-studio.js:4616` | error | `GAP-33 studio.review.error` |
| Reading the pending changes. | `95-studio.js:4617` | loading | `GAP-33 studio.review.loading` |
| The approved lesson set matches the pages shown, so export is available. | `95-studio.js:4643` | default | `GAP-33 studio.review.clean` |
| Export is blocked. The backend’s reason: {reason}. | `95-studio.js:4645` | refusal | `GAP-33 studio.review.blocked` |
| Export is blocked and the backend returned no reason string. | `95-studio.js:4646` | refusal | `GAP-33 studio.review.blocked_unknown` |
| No fine-tune change is waiting for review. | `95-studio.js:4652` | empty | `GAP-33 studio.review.empty` |
| plan {kind} / page {hash prefix}… / lesson page (diff row labels) | `95-studio.js:4711` | default | `GAP-33 studio.review.row.*` |
| Changed: {fields or “no named field”} | `95-studio.js:4684` · `95-studio.js:4108, 4152` | default | `GAP-33 studio.review.changed` |
| Now: {order} / Before: {order} | `95-studio.js:4689` · `95-studio.js:4113, 4117` | default | `GAP-33 studio.review.order` |
## 9. Fine-tune panel — reorder, edit, regenerate (`95-studio.js:4200-5140`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| That move would put one unit’s objectives behind a later unit, so the stored order was kept. | `95-studio.js:4896` | refusal | `GAP-33 studio.finetune.err.order` |
| A later change landed after that revision, so the undo would overwrite it; nothing was written. | `95-studio.js:4899` | refusal | `GAP-33 studio.finetune.err.undo_stale` |
| That structural change was already undone. | `95-studio.js:4901` | refusal | `GAP-33 studio.finetune.err.undone` |
| This plan has no structural change to undo. | `95-studio.js:4903` | refusal | `GAP-33 studio.finetune.err.nothing_to_undo` |
| The plan is not approved, so only a draft edit applies. | `95-studio.js:4905` | refusal | `GAP-33 studio.finetune.err.draft_only` |
| The course revision was refreshed; try again. | `95-studio.js:4909` | error | `GAP-33 studio.finetune.err.revision` |
| Order saved. {n}. {title} · {n}. {title} … | `95-studio.js:4950` | default | `GAP-33 studio.finetune.order_saved` |
| Undid the last structural change. Stored order: {order} | `95-studio.js:5013` | default | `GAP-33 studio.finetune.undone` |
| Nothing changed yet. | `95-studio.js:5128` · `95-studio.js:4551, 5306` | empty | `GAP-33 studio.finetune.no_changes` |
| This section has no authored page yet, so there is no page digest to revise. Use “Regenerate this section” to author it first. | `95-studio.js:5137-5138` | refusal | `GAP-33 studio.finetune.no_page` |
| Section page saved as a new revision that needs review before export. Every stored attempt and the previous page version are untouched. | `95-studio.js:5206-5207` | default | `GAP-33 studio.finetune.saved_page` |
| Section metadata saved. The edited objective is recorded as a revision that needs review before export. | `95-studio.js:5211` | default | `GAP-33 studio.finetune.saved_meta` |
| Queued regenerating 1 section: {title}. Other sections, their media and every attempt are untouched. | `95-studio.js:5269` | default | `GAP-33 studio.finetune.queued` |
| Fine-tune this approved course | `95-studio.js:5288` | default | `GAP-33 studio.finetune.title` |
| Undoing / Undo last structural change | `95-studio.js:5307` | loading / default | `GAP-33 studio.finetune.undo` |
| Reorder or retitle an objective and the change is written to storage as a revision that needs review; lesson pages, checks and attempts are not rewritten. Every move is sent with the full order, so the order you see is the order the backend returned. | `95-studio.js:5318-5320` | default | `GAP-33 studio.finetune.note` |
| {section plural} in stored order (accessible name) | `95-studio.js:5339` | default | `GAP-33 studio.finetune.order_label` |
| {n}. {title}. Press Alt+ArrowUp or Alt+ArrowDown to move it. (accessible name) | `95-studio.js:5356` | default | `GAP-33 studio.finetune.move_label` |
| Alt+ArrowUp Alt+ArrowDown (shortcut hint) | `95-studio.js:5357` | default | `GAP-33 studio.finetune.shortcut` |
| no page yet / no authored section | `95-studio.js:5387`, `95-studio.js:5394` · `95-studio.js:4810, 4817` | empty | `GAP-33 studio.finetune.no_page_short` |
| page v{n} | `95-studio.js:5388` | default | `GAP-33 studio.finetune.page_version` |
| Move up / Move down | `95-studio.js:5407`, `95-studio.js:5415` · `95-studio.js:4830, 4838` | default | `GAP-33 studio.finetune.move.*` |
| Close editor / Edit section | `95-studio.js:5422` | default | `GAP-33 studio.finetune.edit` |
| Regenerate this section | `95-studio.js:5434` | default | `GAP-33 studio.finetune.regenerate` |
| {section singular} title (accessible name and placeholder) | `95-studio.js:6741`, `95-studio.js:6863` | default | `GAP-33 studio.finetune.field.objective_title` |
| Stored on the objective. The section page keeps its authored prose; a retitle is a plan revision that needs review. | `95-studio.js:5451` | default | `GAP-33 studio.finetune.field.objective_title_hint` |
| Section page title | `95-studio.js:5461` | default | `GAP-33 studio.finetune.field.page_title` |
| Stored on the authored page through lesson.revise, fenced on the page digest this read served ({hash}…). The result is a new page revision that needs review. | `95-studio.js:5464` | default | `GAP-33 studio.finetune.field.page_title_hint` |
| This section has no authored page yet, so there is no digest to revise. Regenerate this section to author one. | `95-studio.js:5465` | refusal | `GAP-33 studio.finetune.no_digest` |
| Evidence target | `95-studio.js:5477` | default | `GAP-33 studio.finetune.field.target` |
| Assessment criteria | `95-studio.js:5505` | default | `GAP-33 studio.finetune.field.criteria` |
| One criterion per line. Saving replaces the objective’s criteria. | `95-studio.js:5507` | default | `GAP-33 studio.finetune.field.criteria_hint` |
| This build was not served the objective’s current criteria, so this field starts empty. Enter the criteria you want stored; leaving it untouched keeps whatever storage holds. | `95-studio.js:5508-5509` | empty | `GAP-33 studio.finetune.field.criteria_empty` |
| Saving / Save section | `95-studio.js:5526` | loading / default | `GAP-33 studio.finetune.save` |
| Unsaved changes | `95-studio.js:5539` | dialog | `GAP-33 studio.finetune.unsaved_title` |
| The section’s segment bodies are authored by the lessons job; this editor changes the page title and the objective metadata, and lesson.revise stores a new page revision that needs review before export. | `95-studio.js:5548` | default | `GAP-33 studio.finetune.editor_note` |
| Confirm the evidence consequence (accessible name) | `95-studio.js:5554` | dialog | `GAP-33 studio.finetune.consequence_label` |
| {n} stored attempt(s) reference this section. Editing this page keeps every stored attempt and the previous page version; the new page is stored as a revision that nobody has approved, so its check stays closed and export waits. | `95-studio.js:4545` | dialog | `GAP-33 studio.finetune.consequence_dialog` |
| {n} learner attempt(s) already reference this section. Editing this page keeps every stored attempt and the previous page version; the new page is stored as a revision that nobody has approved, so its check stays closed and export waits. Confirm to store the edit. | `95-studio.js:5190` | error | `GAP-33 studio.finetune.consequence_error` |
| {n} stored attempt(s) reference this section; the edit was confirmed against that consequence. | `95-studio.js:4734` | default | `GAP-33 studio.finetune.consequence_review` |
| Saving / Confirm and save / Keep editing | `95-studio.js:5568`, `95-studio.js:5575` | loading / dialog | `GAP-33 studio.finetune.confirm` |
| Unsaved section changes (in-panel dialog accessible name) | `95-studio.js:5586` | dialog | `GAP-33 studio.dialog.unsaved_title` |
| Discard the unsaved changes to this section? | `95-studio.js:5592` | dialog | `GAP-33 studio.dialog.unsaved_body` |
| Discard changes / Keep editing | `95-studio.js:5575`, `95-studio.js:5610` · `95-studio.js:5033, 5040` | dialog | `GAP-33 studio.dialog.discard` / `studio.dialog.keep` |

| Queueing / Queue regenerating 1 section | `95-studio.js:5650` | loading / dialog | `GAP-33 studio.regen.queue` |
| Queued {scope} · job {id} | `95-studio.js:5677` | default | `GAP-33 studio.regen.queued` |
| Preflight: {min}–{max} · {min calls}–{max calls} call(s) | `95-studio.js:58` | default | `GAP-33 studio.regen.preflight` |
| 1 section: {title or “untitled”} | `95-studio.js:4594` | default | `GAP-33 studio.finetune.scope` |
| lesson page (diff kind word) | `95-studio.js:4711` | default | `GAP-33 studio.review.row.lesson_page` |

## 10. The plan view — outline, approval gates, editing (`95-studio.js:5137-5988`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The course was updated elsewhere; press Save changes again. | `95-studio.js:6009` | error | `GAP-28 studio.plan.err.stale_save` |
| This plan is approved; start a new plan version to change it. | `95-studio.js:6011` | refusal | `GAP-28 studio.plan.err.approved_edit` |
| That objective already has content or learning state, so it cannot be removed. | `95-studio.js:6013` | refusal | `GAP-28 studio.plan.err.remove_has_state` |
| Plan saved{ as version {n}}. The edit is versioned and marks the lesson set as needing review until it is approved again. | `95-studio.js:6023` | default | `GAP-28 studio.plan.saved` |
| This version changed after it was validated, so approval is withheld. Re-read the plan or run a new version. | `95-studio.js:6046` | refusal | `GAP-28 studio.plan.withheld.changed` |
| This version has no passing validation record, so approval is withheld. Repair the plan above or run a new version. | `95-studio.js:6047` | refusal | `GAP-28 studio.plan.withheld.no_record` |
| The plan digest is not available yet. Re-read the plan and try again. | `95-studio.js:6056` | error | `GAP-28 studio.plan.err.no_digest` |
| The plan was re-read; press Approve plan again. / The course was updated elsewhere; press Approve plan again. | `95-studio.js:6072-6073` | error | `GAP-28 studio.plan.err.stale_approve` |
| Plan approved. The outline and activities are now fixed; the generated pages are a separate approval. | `95-studio.js:6078` | default | `GAP-28 studio.plan.approved` |
| The course was updated elsewhere; press Start a new plan version again. | `95-studio.js:6174` | error | `GAP-28 studio.plan.err.stale_replan` |
| A new draft plan version was created. The approved lesson set stops applying until the new plan and its pages are approved. | `95-studio.js:6179` | default | `GAP-28 studio.plan.replanned` |

| The saved brief could not be read yet, so this run cannot be repeated. Try again once the plan finishes reading. | `95-studio.js:6239` | error | `GAP-28 studio.plan.err.no_brief` |
| {code: }{backend text} The saved draft is unchanged. | `95-studio.js:6255` | error | `GAP-28 studio.plan.retry_failed` (`(backend text)` = `describeError(response.error)`; the frame is ours, the detail is the backend’s) |
| The planning service answered with the run that already finished, so nothing new started. The refused draft is unchanged; try again shortly. | `95-studio.js:6262` | error | `GAP-28 studio.plan.retry_dup` |
| A new planning run started from the same brief: research runs again and the draft it writes is a new version. The refused draft stays readable until a new plan replaces it. | `95-studio.js:6268` | default | `GAP-28 studio.plan.retry_started` |
| Reading the plan | `95-studio.js:6308` | loading | `GAP-28 studio.plan.loading` |
| The plan could not be read | `95-studio.js:6312` · `95-studio.js:5540, 6056` | error | `GAP-28 studio.plan.error` |
| Draft plan {id} · version {n} is still stored. | `95-studio.js:6335` | error | `GAP-28 studio.plan.draft_stored` |
| The plan is being written / No plan yet | `95-studio.js:206`, `95-studio.js:370` | loading / empty | `GAP-28 studio.plan.writing` / `studio.plan.none` |

| This course has no plan attached and nothing is stored to resume from; nothing is invented to fill the gap. | `95-studio.js:6395` | empty | `GAP-28 studio.plan.none_body` |
| No plan is attached to this course, so there is nothing to review. Start a new brief. | `95-studio.js:6396` | empty | `GAP-28 studio.plan.none_review` |
| plan {hash prefix}… | `95-studio.js:6443` | default | `GAP-28 studio.plan.digest` |
| Edit plan / Saving / Save changes | `95-studio.js:6456`, `95-studio.js:6460` | default / loading | `GAP-28 studio.plan.edit` |
| Approve plan | `95-studio.js:6469` | default | `GAP-28 studio.plan.approve` |
| Generate missing lessons / Generate lessons | `95-studio.js:6481-6482` | default | `GAP-28 studio.plan.generate` |
| Start a new plan version | `95-studio.js:6491` | default | `GAP-28 studio.plan.replan` |
| This version cannot be approved: it changed after its validation record was written, so that record covers different bytes. Run a new plan version, or edit the plan to take ownership of it as your own outline. | `95-studio.js:6552` | refusal | `GAP-28 studio.plan.cannot_approve.changed` |
| This version cannot be approved: the validator refused it. Repair it above; approving a refused draft is never offered. | `95-studio.js:6554` | refusal | `GAP-28 studio.plan.cannot_approve.refused` |
| This version was edited by you, so approval is a human review of your own outline; it is not presented as validated. | `95-studio.js:6556` | refusal | `GAP-28 studio.plan.cannot_approve.owner` |
| This version cannot be approved: no passing validation record is stored for it. Edit the plan to own it, or run a new plan version. | `95-studio.js:6558` | refusal | `GAP-28 studio.plan.cannot_approve.no_record` |
| Approval is withheld until this version has a validation record: a draft with no record is not approvable. | `95-studio.js:6559` | refusal | `GAP-28 studio.plan.cannot_approve.withheld` |
| Approving the plan approves this outline and these activities. It does not approve a single generated page: the lesson set is approved later, by its own hash. | `95-studio.js:6566` | default | `GAP-28 studio.plan.approve_hint` |
| Lessons cannot be generated from this plan version: {gap} | `95-studio.js:6580` | refusal | `GAP-28 studio.plan.generate_blocked` |
| The authored outline (its sections and research) belongs to the version that was written with the plan, and this version has changes it does not cover, so Generate lessons is withheld rather than offered as a second failure. Start a new plan version to author an outline that covers every objective. | `95-studio.js:6581` | refusal | `GAP-28 studio.plan.generate_blocked_body` |
| Re-running generation reuses every lesson already authored at this plan version and only authors what is missing. Nothing is paid for twice. | `95-studio.js:6636` | default | `GAP-28 studio.plan.generate_hint` |
| OUTLINE AND ACTIVITIES ({n}) | `95-studio.js:6705` | default | `GAP-28 studio.plan.outline_title` |
| Objective {n} title / Objective {n} evidence target (accessible names) | `95-studio.js:983`, `95-studio.js:6766` | default | `GAP-28 studio.plan.objective_label` |
| Up / Down / Keep / Remove (row controls) | `95-studio.js:5794` | default | `GAP-28 studio.plan.row.*` |
| Add objective | `95-studio.js:6907` | default | `GAP-28 studio.plan.add` |
| Add objective | `95-studio.js:6907` | default | `GAP-28 studio.plan.add_control` |
| New objective {n} title / New objective {n} evidence target (accessible names) | `95-studio.js:6766` | default | `GAP-28 studio.plan.new_objective_label` |
| State not recorded | `00-header.js:98` | default | `GAP-28 studio.plan.state_unrecorded` |
| Sources and review notes | `95-studio.js:6917` | default | `GAP-28 studio.plan.sources_title` |
| Sources come from the research that produced this plan. If research was unavailable the plan says so; no citation is invented here. | `95-studio.js:6920` | default | `GAP-28 studio.plan.sources_note` |
| No source is recorded for this plan / No source was recorded for this plan. Nothing on this plan is presented as cited, and no excerpt is invented to fill the gap. | `95-studio.js:6928`, `95-studio.js:6930` | empty | `GAP-28 studio.plan.sources_empty` |
| Car activities are passenger-only. The driver never handles material. | `95-studio.js:6938` | default | `GAP-28 studio.plan.car_rule` |
| A draft plan can be edited freely. An approved plan is changed only by starting a new version, so what you approved stays exact. | `95-studio.js:6943` | default | `GAP-28 studio.plan.edit_rule` |
## 11. Learner plan, page tabs and export gate (`95-studio.js:5988-6662`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Start the first lesson / Open the first section | `95-studio.js:7080`, `95-studio.js:7088` · `95-studio.js:6087, 6095` | default | `GAP-28 studio.learner.start` |
| The outline is approved. Coursebook writes the lesson pages below; the section list is the approved outline. | `95-studio.js:7097` | default | `GAP-28 studio.learner.outline_note` |
| Reading the pages | `95-studio.js:7152` | loading | `GAP-28 studio.pages.loading` |
| The pages could not be read | `95-studio.js:7156` | error | `GAP-28 studio.pages.error` |
| The parent guide is what you follow while teaching. It can quote the answer guide; the learner pages never do. | `95-studio.js:7166` | default | `GAP-28 studio.tab.parent_guide.note` |
| These are the learner pages. No answer key is included here — answers live in their own tab and are a different file role. | `95-studio.js:7167` | default | `GAP-28 studio.tab.learner_pages.note` |
| The answer guide. It is served by course id only, so it is never reachable from a learner’s lesson surface, and export keeps it out of the learner pages. | `95-studio.js:7168` | default | `GAP-28 studio.tab.answers.note` |
| The narration script you read aloud. It is text, not an audio file, and it is also inside the parent guide. | `95-studio.js:7169` | default | `GAP-28 studio.tab.narration.note` |
| Every source this plan recorded, with the support verdict it earned. | `95-studio.js:7170` | default | `GAP-28 studio.tab.sources.note` |
| Tab (tab-list label) | `95-studio.js:767` | default | `GAP-28 studio.tabs.label` |
| {n} file{s} in this tab | `95-studio.js:7181` | default | `GAP-28 studio.tabs.file_count` |
| content hash {prefix}… | `95-studio.js:7182` | default | `GAP-28 studio.pages.content_hash` |
| sha256 {hash} | `95-studio.js:7231` | default | `GAP-28 studio.pages.sha256` |
| clipped (tab-limit badge) | `95-studio.js:7223-7231` | overflow | `GAP-35 studio.pages.clipped` |
| · the served text was clipped at the tab limit | `95-studio.js:7231` | overflow | `GAP-35 studio.pages.overflow` |
| No source is recorded for this course / No source was recorded for this course. Nothing here is presented as cited, and no excerpt is invented to fill the gap. | `95-studio.js:7191`, `95-studio.js:7193` | empty | `GAP-28 studio.pages.sources_empty` |
| Nothing generated for this tab yet | `95-studio.js:7198` | empty | `GAP-28 studio.pages.empty` |
| This course asked for no narration, or no lesson has been generated yet. | `95-studio.js:7201` | empty | `GAP-28 studio.pages.empty_narration` |
| The plan must be approved and its lessons generated before this tab has text. | `95-studio.js:7202` | empty | `GAP-28 studio.pages.empty_prereq` |
| The course was updated elsewhere; press Approve this lesson set again. | `95-studio.js:7284` | error | `GAP-34 studio.gate.err.stale` |
| Export gate | `95-studio.js:7326` | default | `GAP-34 studio.gate.title` |
| Plan / Lesson set approval / Approved content hash / Current content hash / Final approval (gate rows) | `95-studio.js:7332`, `95-studio.js:7334`, `95-studio.js:7338`, `95-studio.js:7343` | default | `GAP-34 studio.gate.row.*` |
| Approving the plan approved the outline and its activities. This gate is separate: it approves the generated lesson set by its content hash, and any later edit to the plan, the pages or the course title clears it. | `95-studio.js:7347` | default | `GAP-34 studio.gate.note` |
| Lesson set approved{ on {date}}{ for content hash {hash}}. | `95-studio.js:74` | default | `GAP-34 studio.gate.approved_line` |
| There is no approved plan to approve a lesson set for yet. | `95-studio.js:7363` | empty | `GAP-34 studio.gate.no_plan` |
| No generated pages exist yet, so there is nothing to approve. Generate the lessons from the Plan view first. | `95-studio.js:7364` | empty | `GAP-34 studio.gate.no_pages` |
| This backend does not implement parent.final.approve yet. | `95-studio.js:7369` | error | `GAP-34 studio.gate.unsupported` |
| Approving the lesson set / Approve this lesson set | `95-studio.js:7378` | loading / default | `GAP-34 studio.gate.approve` |
| Export is available: the approved lesson set matches the pages shown. | `95-studio.js:7384` | default | `GAP-34 studio.gate.available` |
| Export is blocked ({reason}). | `95-studio.js:3766` · `95-studio.js:3279, 6395` | refusal | `GAP-34 studio.gate.blocked` |
| Backend reason: {reason or “none reported”}. | `95-studio.js:1547` | refusal | `GAP-34 studio.gate.backend_reason` |
| Formats | `95-studio.js:7245` | default | `GAP-34 studio.gate.formats` |
| Pack archive (parent guide, learner pages, answer guide). | `95-studio.js:7407` | default | `GAP-34 studio.gate.format.archive` |
| Printable PDF: selectable text, low-ink layout, no color-only answers. | `95-studio.js:7413` | default | `GAP-34 studio.gate.format.pdf` |
| Exporting / Export the approved files | `95-studio.js:7419` | loading / default | `GAP-34 studio.gate.export` |
| The pack minima reported these problems: | `95-studio.js:7432` | refusal | `GAP-34 studio.gate.minima` |
| Exported files | `95-studio.js:7446` | default | `GAP-34 studio.gate.files` |
| Export {id} · {date} · content hash {hash} | `95-studio.js:7449` | default | `GAP-34 studio.gate.export_line` |
| The pack carries parent guide, learner pages and answer guide. Narration stays an audio role, so an authored text script is not exported as a narration file: it is the Audio & visuals tab and part of the parent guide. | `95-studio.js:7465` | default | `GAP-34 studio.gate.pack_note` |
| Exported files never include attempts, notebook notes, reflections, transcripts or provider settings. | `95-studio.js:7467` | default | `GAP-34 studio.gate.privacy_note` |
| parent-lesson-pack.pdf / parent-lesson-pack.zip / parent-export.json (download names) | `95-studio.js:7492`, `95-studio.js:7494-7495` | default | `GAP-34 studio.gate.filename.*` |
| Download PDF / Download pack archive / Download export record | `95-studio.js:7499`, `95-studio.js:7501-7502` | default | `GAP-34 studio.gate.download.*` |
| Session-bound, expiring link served by this host’s artifact route. A filesystem path never leaves the backend. / Host artifact route. | `95-studio.js:7510-7511` | default | `GAP-34 studio.gate.artifact_note` |
| A reflection is parent-reported. It is not evidence of learning, it is never graded, and it is excluded from every exported pack. Its only purpose is to seed your next brief. | `95-studio.js:7567` | default | `GAP-28 studio.reflection.note` |
| How did it go? | `95-studio.js:7569` | default | `GAP-28 studio.reflection.how` |
| Difficulty | `95-studio.js:7528` | default | `GAP-28 studio.reflection.difficulty` |
| What would you revisit? | `95-studio.js:7579` | default | `GAP-28 studio.reflection.revisit` |
| Optional. This note is offered to your next draft as a proposal, never applied silently. | `95-studio.js:7580` | default | `GAP-28 studio.reflection.revisit_hint` |
| The quarter-to-eighth cut needed a second demonstration. (placeholder) | `95-studio.js:7586` | default | `GAP-28 studio.reflection.revisit_placeholder` |
| Offer this note to my next draft. | `95-studio.js:7593` | default | `GAP-28 studio.reflection.offer` |
| Saving / Record reflection | `95-studio.js:7602` | loading / default | `GAP-28 studio.reflection.record` |
| Start the next brief from this note | `95-studio.js:7608` | default | `GAP-28 studio.reflection.start_next` |
| Recorded / When / Plan hash / for next draft | `95-studio.js:1447`, `95-studio.js:7621`, `95-studio.js:7641` | default | `GAP-28 studio.reflection.meta.*` |
| REFLECTIONS ({n}) | `95-studio.js:7625` | default | `GAP-28 studio.reflection.title` |
| No reflections recorded for this course yet. | `95-studio.js:7627` | empty | `GAP-28 studio.reflection.empty` |
| parent-reported · {date} | `95-studio.js:7640` | default | `GAP-28 studio.reflection.parent_reported` |

## 12. Detail chrome, dialogs and the wordmark (`95-studio.js:6662-6931`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| All parent courses | `95-studio.js:7778` | default | `GAP-28 studio.all_courses` |
| Parent course (fallback title) | `95-studio.js:7785` | empty | `GAP-28 studio.detail.fallback_title` |
| Parent preparation | `95-studio.js:7789` | default | `GAP-28 studio.preparation` |
| Export ready | `95-studio.js:7793` | default | `GAP-28 studio.export_ready` |
| Parent view · what your child did and what you observed, never points, levels or rankings. | `95-studio.js:7803` | default | `GAP-28 studio.parent_view` |
| You are the operator · revision {n} | `95-studio.js:7809` | default | `GAP-28 studio.revision` (`computed:revision`) |
| Studio view | `95-studio.js:7815` | default | `GAP-28 studio.view` |
| Unsaved section changes (leave-guard accessible name) | `95-studio.js:5586` | dialog | `GAP-28 studio.leave.title` |
| The section editor has unsaved changes. Leaving discards them and leaves storage exactly as it is now. | `95-studio.js:7832` | dialog | `GAP-28 studio.leave.body` |
| Discard and leave / Keep editing | `95-studio.js:5575`, `95-studio.js:7845` · `95-studio.js:6842, 6848` | dialog | `GAP-28 studio.leave.discard` / `studio.leave.keep` |
| Coursebook (wordmark) | `95-studio.js:591` | default | `GAP-01` (shell wordmark row; cited, not new) |

## 13. State coverage for this surface

| state | what actually renders | deck |
|---|---|---|
| default | landing, brief, plan, pages, export and reflection views (sections 3–12) | GAP-28 |
| loading | every `Reading …` line plus the job line (`95-studio.js:229-244, 427, 700, 815, 1210, 3290, 5536, 6155, 6379`) | GAP-28 |
| empty | `No lesson plans yet`, `No learner course to draw from`, `No homework yet`, `No source is recorded…`, `No reflections recorded…`, `This lesson records no external sources.` | GAP-28 |
| error | the `could not be read` family and the job-failure family (`95-studio.js:249-262, 431, 704, 818, 1215, 2387, 2653, 3850, 5332, 5540, 6159`) | GAP-28 |
| refusal | the export/approval/blocked families (section 1, 5, 7, 10, 11) | GAP-28, GAP-32–34 |
| dialog | **two** dialogs, not one: the in-panel unsaved-changes dialog (`95-studio.js:5009-5040`) and the leave guard (`95-studio.js:6822-6848`) | GAP-33, GAP-28 |
| overflow | only Parent Studio has words: the `clipped` badge (`95-studio.js:6226`) and `· the served text was clipped at the tab limit` (`6234`) | GAP-35 |
| offline | **no studio string exists.** The shell's offline line (`32-desk.js:352`, `98-page.js:650`) is mounted by those routes, not by this surface; `95-studio.js` never reads `useOnline()`. | GAP-35 |

## 14. What CP-031's sample missed (delta for CP-001)

`CP-025b-studio.md` covered the named regions. This sweep adds, beyond them:

1. **The fine-tune editor and its dialogs** — 60+ strings from `95-studio.js:4200-5140`, including the
   second unsaved-changes dialog (`5009-5040`) that CP-025b did not extract, the cost preflight
   sentence, and the undo messages.
2. **The export gate** — `95-studio.js:6329-6514`, the second approval gate and the three formats.
3. **The plan view's approval-withholding family** — `95-studio.js:5356-5694`.
4. **The validation/independence family** — `95-studio.js:3417-3703`; these are the words that say
   whether a second model checked the plan, and CP-025b did not list them.
5. **The homework state and kind enum maps** — `95-studio.js:1640-1655`, plus the sheet guard
   (`1818, 1821`) and the already-reported refusal (`2507`).
6. **The take-home shelf and proof chrome** — `95-studio.js:700-1040`.
7. **The brief form's 30 field labels, hints and placeholders** — `95-studio.js:2940-3220`.
8. **The reflection flow** — `95-studio.js:6542-6644`.
9. **The approval-invalidation banner and the plan-check reason labels** — `95-studio.js:3255-3284`
   and `3381-3400`, both `GAP-38`. CP-031's first cut (and the samples) rowed neither, so the deck
   could word "Changes need review" and "Checks that did not clear:" and neither the cause nor the
   five reasons.
10. **The child-safe defaults line as Parent Studio renders it** — `30-home.js:3655-3691`, mounted at
    `95-studio.js:480` (§3.1). It existed only in CP-025b's sample.
11. **The print-proof meta line** (`95-studio.js:957`), **the plan-in-progress body** (`5572`), and
    **the second "Add objective" control** (`5933`) — composed or differently-worded strings that a
    label-only sweep loses.

## 15. Row count

Tables above: the surface's complete visible-string inventory for `95-studio.js`, with the four
non-visible literal classes named in "How this file was produced". The closing test
(`tests/test_cp_copy_inventory.py`) asserts this file exists, cites `95-studio.js`, and keeps at
least the row floor; a row with no `file:line` fails review.

## Rows removed in the 475efefc re-derivation

These strings were listed by an earlier cut of this sweep and no longer ship at this revision.
Each is removed with its reason rather than re-anchored to a neighbouring line.

- `Estimated {low}–{high} for one section ({calls} call(s) at {per-call} per call, derived from this course’s last recorded lessons preflight{ · budget: {budget}}). The exact preflight is returned with the queued job.` — the per-call arithmetic left the screen; the shipped line is now "Regenerating this section costs about {low}–{high}, based on what writing lessons for this course has cost so far." at 95-studio.js:5636, which this sweep already rows.
- `The backend sizes this one-section run when you confirm; no recorded preflight is readable for this course yet.` — reworded to "We work out what one section costs when you queue it — this course has no earlier lesson run to go by yet." at 95-studio.js:5639, which this sweep already rows.
- `The create form is not reachable from this surface. Open Courses and start a new course with this goal.` — the plan surface no longer renders this sentence; the create form is its own route (50-create.js) and the string does not ship.
- `Research and drafting run in the background; this screen fills itself when the plan is written. Nothing is shown from a template, and there is no progress percentage to show.` — reworded on the create route to "Research and drafting may take several minutes…" (50-create.js:144-150); the Studio sentence no longer ships.
