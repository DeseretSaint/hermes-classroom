# CP-031b — Homework surface shipped-string sweep

Card: **CP-031b** (`t_adc9bdee`). Closes **GAP-30** for the Homework surface: the Notebook's
"Taken with you" list in `desktop/src/90-course.js`, plus a pointer to the lesson-side and
studio-side homework strings that live in `desktop/src/95-studio.js` (swept in
`CP-031-sweep-parent-studio.md` §6, the same source file, so they are not duplicated here).
Docs only; no product string changed.

Row citations in this file were re-derived on the strings at `475efefc`: each `file:line` is the
line that carries the row's own words today. Section headings keep a coarse range as navigation;
the row citation is the authoritative anchor.

**Range, and why it is wider than the card's slice.** The card named `90-course.js:880-1000`. That
slice starts after the list's own search field (`868`, `871`) and stops before the row actions, the
technical-detail disclosure, the edit form and the remove dialog (`1007-1124`) — all rendered by the
same component, `NotebookView` (`90-course.js:735-1133`). A deck authored from the 880-1000 slice
alone would silently lose "Remove from notebook", "Save changes" and the only dialog on this
surface. This sweep therefore covers **all of `NotebookView`, `735-1133`**, and says so instead of
inheriting the card's boundary. Lines `735-867` carry no prose literal (checked by re-lex): the
component's only strings are the ones below.

**Surface:** GM-008 Homework — the one-page sheet, the record, the two lists, and the notebook row's
own actions and dialog. `GAP-23` owns the section; `GAP-25` owns offline; `GAP-31` is new and owns
the enum→copy maps and the sheet guards; the notebook row's action/edit/dialog family is named in
`GAP-23` as part of the same `hw.*` section.

## 1. The Notebook list (`90-course.js:868-1000`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Search the notebook (accessible name) | `90-course.js:950` | default | `GAP-23 hw.notebook.search_label` |
| Search notes and excerpts (placeholder) | `90-course.js:953` | default | `GAP-23 hw.notebook.search_placeholder` |
| Filter by tag (accessible name) | `90-course.js:963` | default | `GAP-23 hw.notebook.filter_label` |
| All tags (select placeholder and first option) | `90-course.js:965` · `90-course.js:883, 890` | default / empty | `GAP-23 hw.notebook.all_tags` |
| Recently saved / Oldest first (order) | `90-course.js:983-984` | default | `GAP-23 hw.notebook.order.*` |
| Removed from the notebook. The lesson and any media it referenced are untouched. | `90-course.js:998` | default | `GAP-23 hw.notebook.removed` |
| Undo (restores as a new entry) | `90-course.js:1000` | default | `GAP-23 hw.notebook.undo` |
| Taken with you (section label) | `90-course.js:1010` | default | `GAP-23 hw.notebook.tab` |
| No homework yet | `90-course.js:1016` | empty | `GAP-23 hw.list.empty` |
| A task you take with you from a lesson is listed here. | `90-course.js:1017` | empty | `GAP-23 hw.list.empty_body` |
| Nothing saved yet / No saved moment matches | `90-course.js:1025` | empty | `GAP-23 hw.notebook.empty` |
| Save an explanation, visual or quiz moment and it will appear here. | `90-course.js:1028` | empty | `GAP-23 hw.notebook.empty_body` |
| Your saved moments are still here; this search or tag just excludes them. | `90-course.js:1029` | empty | `GAP-23 hw.notebook.filtered_empty` |
| Go to the current lesson | `90-course.js:1036` | empty | `GAP-23 hw.notebook.go_to_lesson` |
| Clear search and tag | `90-course.js:1046` | empty | `GAP-23 hw.notebook.clear_filters` |
| This lesson (section-title fallback) | `90-course.js:1076` | empty | `GAP-23 hw.notebook.lesson_fallback` |
| Course · {title} | `90-course.js:1079` | default | `GAP-23 hw.notebook.course_line` |

## 1b. The notebook row: actions, technical detail, edit form, remove dialog (`90-course.js:1007-1124`)

This is the same list's second half, and the only dialog on the surface. None of it had a row before:
it is the block the card's `880-1000` boundary excluded.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Open in textbook | `90-course.js:1089` | default | `GAP-23 hw.notebook.action.open` |
| Play/view media (label is fixed; `aria-expanded` carries open/closed) | `90-course.js:1097` | default | `GAP-23 hw.notebook.action.media` |
| Edit note and tags | `90-course.js:1110` | default | `GAP-23 hw.notebook.action.edit` |
| Remove from notebook | `90-course.js:1117` | default | `GAP-23 hw.notebook.action.remove` |
| Technical detail (disclosure summary) | `90-course.js:1129` | default | `GAP-23 hw.notebook.detail.summary` |
| Section id · {objective id or “not recorded”} | `90-course.js:1135` | default / empty | `GAP-23 hw.notebook.detail.section` |
| Saved from · {kind or “not recorded”} | `90-course.js:1137` | default / empty | `GAP-23 hw.notebook.detail.kind` |
| Source · {source ids, comma separated} | `90-course.js:1140` | default | `GAP-23 hw.notebook.detail.source` |
| Tags · {tags, comma separated} | `90-course.js:1144` | default | `GAP-23 hw.notebook.detail.tags` |
| Saved {when} | `90-course.js:1146` | default | `GAP-23 hw.notebook.detail.saved_at` (`computed:whenLabel(created_at)`) |
| Your note | `90-course.js:1158` | default | `GAP-23 hw.notebook.edit.note_label` |
| Tags (comma separated) | `90-course.js:1169` | default | `GAP-23 hw.notebook.edit.tags_label` |
| Save changes | `90-course.js:1179` | default | `GAP-23 hw.notebook.edit.save` |
| Cancel | `90-course.js:1187` | default | `GAP-23 hw.notebook.edit.cancel` |
| Remove this moment from the notebook? (dialog title) | `90-course.js:1203` | dialog | `GAP-23 hw.notebook.remove_title` |
| Only the notebook entry is removed. The lesson, its attempts and any media it referenced are kept. (dialog body) | `90-course.js:1205` | dialog | `GAP-23 hw.notebook.remove_body` |
| Remove entry (dialog confirm) | `90-course.js:1206` | dialog | `GAP-23 hw.notebook.remove_confirm` |

The dialog carries no dismiss label of its own: `FocusReturningDialog` (`1120-1128`) renders the
host's close control, so only the confirm label is ours. The remove notice (`916`) and the undo
control (`918`) are the post-dialog state and are rowed in §1.

## 2. The rest of the surface lives in `95-studio.js`

The lesson-side action (`Take this with you`), the one-page sheet, the field card, the record and the
studio's own homework tab are all authored in `desktop/src/95-studio.js`. They are inventoried
row-by-row in `CP-031-sweep-parent-studio.md` §6 with `file:line` citations:

- §6.1 state and kind maps — `95-studio.js:1640-1655` → **GAP-31**
- §6.2 the sheet and its print path — `95-studio.js:1779-2164`
- §6.3 Take this with you — `95-studio.js:2164-2559`
- §6.4 the record, list and studio tab — `95-studio.js:2559-2940`

This file is therefore the Notebook half of the same surface, not a second inventory of the same
strings.

## 3. State coverage for this surface

| state | what renders | deck |
|---|---|---|
| default | the sheet, card, record, both lists and the notebook row's four actions | GAP-23 |
| loading | `Reading this lesson's task`, `Reading this task`, `Writing the task` | GAP-23 |
| empty | `No homework yet`, `Nothing saved yet`, `No saved moment matches`, `This lesson`, and the two `not recorded` fallbacks (§1b) | GAP-23 |
| error | `The task could not be read.`, `This task could not be read.`, `The course names could not be read…`, `A lesson title could not be read…`, `Removed from the notebook…` | GAP-23, GAP-31 |
| refusal | the two sheet guards (`95-studio.js:1818, 1821`) and `This task already carries a report…` (`2507`) | GAP-31 |
| offline | **no homework string.** `90-course.js` and the homework block in `95-studio.js` never read `useOnline()`; a failed read says the task could not be read, not that the device is offline. | GAP-25 |
| overflow | **no string.** The sheet is capped at three steps, and the two guards *refuse* an over-long card (`1818, 1821`) rather than truncating it. The notebook list has no count line or truncated-page notice either. | GAP-31 |
| dialog | `Remove this moment from the notebook?` + body + `Remove entry` (`90-course.js:1121-1124`); the print dialog is the host's, not ours (`95-studio.js:2473, 2749`) | GAP-23 |

## 4. What CP-031's sample missed (delta for CP-001)

`CP-025a-homework-game.md` sampled the sheet and the action. This sweep adds: the Notebook list in
`90-course.js` (15 strings, none of which had a row), the two sheet guards as **refusals**, the
already-reported refusal, the five state words and six kind words as an explicit enum map, the
"already read" error pair in the studio list (`95-studio.js:2916, 2919`), and the compact `Skip`
variant (`2732`).

Round 4 of this sweep's own review added the rest of `NotebookView` (§1b): the search field's
accessible name and placeholder, the four row actions, the technical-detail line family, the edit
form's two labels and two buttons, and the remove dialog's title, body and confirm — 17 strings that
the card's `880-1000` boundary excluded even though they render a few lines past it.

## 5. Row count

§1 carries 17 rows and §1b carries 17: **34 inventory rows** for `90-course.js`, plus the
`95-studio.js` rows carried in the studio sweep. Every row cites the line that actually renders the
words it quotes.
