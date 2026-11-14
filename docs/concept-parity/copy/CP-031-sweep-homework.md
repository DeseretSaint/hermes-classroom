# CP-031c — Homework (classroom and notebook) shipped-string sweep

Card: **CP-031c** (`t_0458a135`), re-swept by **CP-031c-R** (`t_54a44039`) at `e6fe4f71`. Docs only; no product string changed.

**Revision swept:** `origin/master` at **`e6fe4f7119ad97d85eee2406890e0ea1a72fb2af`** (90-course.js, 5088 lines, whole file).
**Rows:** 331 inventory rows; 331 distinct literals. Every row cites the line(s)
that carry its words in this revision.

**Surface:** the course-detail classroom, the textbook index and the whole Notebook component.

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

### COURSE_PRIMARY_FALLBACK_LABEL (`90-course.js` from line 39)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Open the lesson | `90-course.js:39` | default | `GAP-23` |

### OverviewView (`90-course.js` from line 64)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This course | `90-course.js:107`; `90-course.js:724`; `90-course.js:4534` | default | `GAP-23` |
| No objective recorded yet | `90-course.js:156`; `90-course.js:4182` | empty | `GAP-23` |
| Next: {…} | `90-course.js:171` | default | `GAP-23` |
| The backend did not return a next step for this course. | `90-course.js:171` | error | `GAP-23` |
| Read this section | `90-course.js:191` | default | `GAP-23` |
| Course sections | `90-course.js:211` | default | `GAP-23` |
| Recent evidence | `90-course.js:222` | default | `GAP-23` |
| {…} {…} due for review. | `90-course.js:223`; `90-course.js:739`; `90-course.js:4703` | default | `GAP-23` |
| No attempt has been recorded on this course yet. | `90-course.js:255` | empty | `GAP-23` |
| Start with the oldest: {…} | `90-course.js:263` | default | `GAP-23` |
| Course details | `90-course.js:277` | default | `GAP-23` |
| How you will use it | `90-course.js:283` | default | `GAP-23` |
| Not recorded | `90-course.js:284` | default | `GAP-23` |
| {…} independent | `90-course.js:292`; `90-course.js:5057` | default | `GAP-23` |
| Where it came from | `90-course.js:296` | default | `GAP-23` |
| authored on this profile | `90-course.js:298` | default | `GAP-23` |
| Exporting the pack is a Library action; it never includes your answers or notes. | `90-course.js:301` | default | `GAP-23` |

### CourseIdentity (`90-course.js` from line 378)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Next · | `90-course.js:420` | default | `GAP-23` |

### SectionRow (`90-course.js` from line 441)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Last opened {…} | `90-course.js:444` | default | `GAP-23` |

### UnitHeading (`90-course.js` from line 517)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Unit {…} | `90-course.js:546` | default | `GAP-23` |
| This unit starts after Unit {…}. You can still open it. | `90-course.js:564` | default | `GAP-23` |

### TextbookIndexDetails (`90-course.js` from line 577)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| this section has evidence held without help. | `90-course.js:580` | default | `GAP-23` |
| the section the course points to now. | `90-course.js:581` | default | `GAP-23` |
| evidence is scheduled to come back. | `90-course.js:582` | default | `GAP-23` |
| no attempt recorded yet. | `90-course.js:583` | empty | `GAP-23` |
| What the states and check types mean | `90-course.js:591` | default | `GAP-23` |
| Check types in this course | `90-course.js:619` | default | `GAP-23` |
| {…} — the backend calls this “{…}”. | `90-course.js:626` | default | `GAP-23` |

### TextbookView (`90-course.js` from line 641)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| 66 characters per line. Evidence is named, never estimated. | `90-course.js:751` | default | `GAP-23` |
| This build can name the current section and every section with scheduled evidence. The complete | `90-course.js:759` | default | `GAP-23` |
| section list needs course.outline; rows light up here automatically once that command is registered. | `90-course.js:760` | default | `GAP-23` |
| No sections yet | `90-course.js:764` | empty | `GAP-23` |
| A section appears once the course has an approved plan with objectives. Approve the plan first. | `90-course.js:765` | default | `GAP-23` |
| Also recorded on this course | `90-course.js:796` | default | `GAP-23` |
| Jumping backward never erases later evidence: each section keeps its own lesson runs, attempts and notebook saves. | `90-course.js:809` | default | `GAP-23` |

### NotebookView (`90-course.js` from line 817)

`NotebookView` is `90-course.js:817-1215` — the **whole** component. The card's
`880-1000` slice stopped before its own action row, edit form and only dialog; every one of
them is rowed here because they render directly under the saved-moment list. §1b is this
section.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Search the notebook | `90-course.js:950` | default | `GAP-23` |
| Search notes and excerpts | `90-course.js:953` | default | `GAP-23` |
| Filter by tag | `90-course.js:963` | default | `GAP-23` |
| All tags | `90-course.js:965`; `90-course.js:972` | default | `GAP-23` |
| Recently saved | `90-course.js:983` | default | `GAP-23` |
| Oldest first | `90-course.js:984` | default | `GAP-23` |
| Removed from the notebook. The lesson and any media it referenced are untouched. | `90-course.js:998` | default | `GAP-23` |
| Undo (restores as a new entry) | `90-course.js:1000` | default | `GAP-23` |
| Taken with you | `90-course.js:1010` | default | `GAP-23` |
| No homework yet | `90-course.js:1016` | empty | `GAP-23` |
| A task you take with you from a lesson is listed here. | `90-course.js:1017` | default | `GAP-23` |
| Nothing saved yet | `90-course.js:1025` | empty | `GAP-23` |
| No saved moment matches | `90-course.js:1025` | empty | `GAP-23` |
| Save an explanation, visual or quiz moment and it will appear here. | `90-course.js:1028` | default | `GAP-23` |
| Your saved moments are still here; this search or tag just excludes them. | `90-course.js:1029` | default | `GAP-23` |
| Go to the current lesson | `90-course.js:1036` | default | `GAP-23` |
| Clear search and tag | `90-course.js:1046` | default | `GAP-23` |
| This lesson | `90-course.js:1076`; `90-course.js:1077` | default | `GAP-23` |
| Course · {…} | `90-course.js:1079` | default | `GAP-23` |
| Open in textbook | `90-course.js:1089` | default | `GAP-23` |
| Play/view media | `90-course.js:1097` | default | `GAP-23` |
| Edit note and tags | `90-course.js:1110` | default | `GAP-23` |
| Remove from notebook | `90-course.js:1117` | default | `GAP-23` |
| Technical detail | `90-course.js:1129`; `90-course.js:1630`; `90-course.js:1978`; `90-course.js:2112` | default | `GAP-23` |
| Section id · {…} | `90-course.js:1135` | default | `GAP-23` |
| Saved from · {…} | `90-course.js:1137` | default | `GAP-23` |
| Source · {…} | `90-course.js:1140` | default | `GAP-23` |
| Tags · {…} | `90-course.js:1144` | default | `GAP-23` |
| Saved {…} | `90-course.js:1146` | default | `GAP-23` |
| Your note | `90-course.js:1158` | default | `GAP-23` |
| Tags (comma separated) | `90-course.js:1169` | default | `GAP-23` |
| Save changes | `90-course.js:1179` | default | `GAP-23` |
| Cancel | `90-course.js:1187` | default | `GAP-23` |
| Remove this moment from the notebook? | `90-course.js:1203` | default | `GAP-23` |
| Only the notebook entry is removed. The lesson, its attempts and any media it referenced are kept. | `90-course.js:1205` | default | `GAP-23` |
| Remove entry | `90-course.js:1206` | default | `GAP-23` |

### QuizzesView (`90-course.js` from line 1216)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| A new audited version of this check is open. The original attempt stays inspectable. | `90-course.js:1247` | default | `GAP-23` |
| Write at least a sentence explaining the dispute. | `90-course.js:1256` | default | `GAP-23` |
| Dispute recorded. The original verdict is unchanged and the history is append-only. | `90-course.js:1266` | default | `GAP-23` |
| All results | `90-course.js:1279` | default | `GAP-23` |
| Partly there | `90-course.js:1281` | default | `GAP-23` |
| Not yet | `90-course.js:1282` | empty | `GAP-23` |
| Could not be graded | `90-course.js:1283` | error | `GAP-23` |
| All assistance | `90-course.js:1291` | default | `GAP-23` |
| First try | `90-course.js:1292` | default | `GAP-23` |
| Answer shown | `90-course.js:1294` | default | `GAP-23` |
| No quiz attempts yet | `90-course.js:1308` | empty | `GAP-23` |
| No attempt matches | `90-course.js:1308` | empty | `GAP-23` |
| Answers you give in a lesson are recorded here with their original feedback. | `90-course.js:1311` | default | `GAP-23` |
| Your attempts are still here; these filters just exclude them. | `90-course.js:1312` | default | `GAP-23` |
| Clear filters | `90-course.js:1323` | default | `GAP-23` |
| Open attempt | `90-course.js:1349` | default | `GAP-23` |
| Reviewing is read-only. Nothing here consumes a retry or changes the old grade. | `90-course.js:1360` | default | `GAP-23` |
| No criterion detail was stored for this attempt. | `90-course.js:1375` | empty | `GAP-23` |
| not recorded | `90-course.js:1381`; `90-course.js:2091`; `90-course.js:2403` | default | `GAP-23` |
| Check version | `90-course.js:1383` | default | `GAP-23` |
| Dispute history | `90-course.js:1394` | default | `GAP-23` |
| Review lesson | `90-course.js:1412` | default | `GAP-23` |
| Try a new version | `90-course.js:1419` | default | `GAP-23` |
| Quiz moment | `90-course.js:1428` | default | `GAP-23` |
| Save to notebook | `90-course.js:1434` | default | `GAP-23` |
| Dispute this grade | `90-course.js:1446` | default | `GAP-23` |
| What did the grader get wrong? | `90-course.js:1453` | default | `GAP-23` |
| Record dispute | `90-course.js:1460` | default | `GAP-23` |
| A dispute never overwrites the original verdict; a re-grade would be a new operation. | `90-course.js:1463` | default | `GAP-23` |

### PlanView (`90-course.js` from line 1493)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| No different item is ready for this objective yet. Open the section to review this item. | `90-course.js:1514` | empty | `GAP-23` |
| Estimated sessions are planning aids, not promises. Only a cold independent result moves an objective to independent evidence. | `90-course.js:1530` | default | `GAP-23` |
| No objectives to show | `90-course.js:1535` | empty | `GAP-23` |
| The plan is not approved, or this build cannot read the objective list. | `90-course.js:1536` | error | `GAP-23` |
| next review {…} | `90-course.js:1558` | default | `GAP-23` |
| interval {…}d · step {…} | `90-course.js:1559` | default | `GAP-23` |
| Open section | `90-course.js:1571`; `90-course.js:3858` | default | `GAP-23` |
| Challenge out | `90-course.js:1573` | default | `GAP-23` |
| This build cannot edit evidence criteria, attempt counts or settings yet. Nothing is filled in to hide that. | `90-course.js:1585` | error | `GAP-23` |

### EvidenceView (`90-course.js` from line 1592)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading the evidence layers | `90-course.js:1594` | default | `GAP-23` |
| What to do next | `90-course.js:1607` | default | `GAP-23` |
| Nothing is suggested yet, because no evidence has been recorded. | `90-course.js:1609` | empty | `GAP-23` |
| It changes when new evidence is recorded, and it describes that evidence rather than judging you. Updated {…}. | `90-course.js:1621` | default | `GAP-23` |
| basis: {…} | `90-course.js:1637` | default | `GAP-23` |
| What the evidence shows | `90-course.js:1652` | default | `GAP-23` |
| No objective in your plan has evidence yet. | `90-course.js:1654` | empty | `GAP-23` |
| no cold result | `90-course.js:1667` | empty | `GAP-23` |
| Your attempts | `90-course.js:1689` | default | `GAP-23` |

### SOURCE_SUPPORT_CLASS (`90-course.js` from line 1754)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| A model read this source and rated how it bears on the claim. That is an assessment, not a document proof. | `90-course.js:1757` | default | `GAP-23` |
| The model found this source at odds with a claim. A person has to settle the disagreement. | `90-course.js:1761` | default | `GAP-23` |
| Not assessed | `90-course.js:1764` | default | `GAP-23` |
| Nothing has checked this source against a claim, so it is listed as provenance only. | `90-course.js:1765` | empty | `GAP-23` |
| Source changed | `90-course.js:1768` | default | `GAP-23` |
| The stored words changed after this course used them. Dependent checks wait for review rather than grading against old text. | `90-course.js:1769` | default | `GAP-23` |
| Source unreachable | `90-course.js:1772` | default | `GAP-23` |
| The last re-fetch failed. The stored evidence is kept, and reuse triggers review. | `90-course.js:1773` | error | `GAP-23` |
| Publisher’s own document | `90-course.js:1776` | default | `GAP-23` |
| This is the publisher’s own documentation, which is provenance for the text — not a check that any claim is true. | `90-course.js:1777` | default | `GAP-23` |

### SOURCE_ASSESSMENT_WORDS (`90-course.js` from line 1781)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| the model judged that this source supports the claim | `90-course.js:1782` | default | `GAP-23` |
| the model judged that this source only partly supports the claim | `90-course.js:1783` | default | `GAP-23` |
| the model could not verify the claim from this source | `90-course.js:1784` | error | `GAP-23` |
| the model judged that this source contradicts the claim | `90-course.js:1785` | default | `GAP-23` |

### SOURCE_TYPE_WORDS (`90-course.js` from line 1788)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Web page | `90-course.js:1794` | default | `GAP-23` |

### sourceSupportModel (`90-course.js` from line 1797)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Status unrecorded | `90-course.js:1800` | default | `GAP-23` |
| The backend did not record how this source bears on the claim. | `90-course.js:1801` | error | `GAP-23` |

### sourceTypeLabel (`90-course.js` from line 1815)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Source type not recorded | `90-course.js:1816` | default | `GAP-23` |

### SourceExcerpt (`90-course.js` from line 1828)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The recorded research snapshot could not be read, so this source’s excerpt is unknown — not absent. Nothing here is presented as a quote. | `90-course.js:1837` | error | `GAP-23` |
| No excerpt is stored for this source. It is listed as provenance only, so no claim on this course is presented as supported by it. | `90-course.js:1838` | empty | `GAP-23` |
| Exact excerpt ({…} characters) | `90-course.js:1848` | default | `GAP-23` |
| These are the words the research step stored when it fetched the page. They are shown as stored; reading them is not a re-fetch and proves nothing beyond what they say. | `90-course.js:1871` | default | `GAP-23` |

### SourceProvenanceCard (`90-course.js` from line 1880)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Published by {…} | `90-course.js:1890` | default | `GAP-23` |
| Publisher not recorded | `90-course.js:1890` | default | `GAP-23` |
| Published {…} | `90-course.js:1892` | default | `GAP-23` |
| Fetched {…} | `90-course.js:1893` | default | `GAP-23` |
| {…} claim{…} cite it | `90-course.js:1896` | default | `GAP-23` |
| Source id: {…}. | `90-course.js:1899` | default | `GAP-23` |
| Support class: {…}. | `90-course.js:1900` | default | `GAP-23` |
| Model assessment: {…}. | `90-course.js:1901` | default | `GAP-23` |
| Model assessment: none recorded. | `90-course.js:1901` | default | `GAP-23` |
| Excerpt state: {…}. | `90-course.js:1902` | default | `GAP-23` |
| Content hash: {…}. | `90-course.js:1903` | default | `GAP-23` |
| Modality: {…}. Licence: {…}. | `90-course.js:1904` | default | `GAP-23` |
| Untitled source | `90-course.js:1918` | default | `GAP-23` |
| the model’s verdict | `90-course.js:1926` | default | `GAP-23` |
| Support basis: {…}, because a model read it. {…} | `90-course.js:1939` | default | `GAP-23` |
| Support basis: {…} | `90-course.js:1940` | default | `GAP-23` |
| Open source | `90-course.js:1958` | default | `GAP-23` |
| Rights: {…} | `90-course.js:1969` | default | `GAP-23` |
| · Modality: {…} | `90-course.js:1970` | default | `GAP-23` |
| · Modality: not recorded | `90-course.js:1970` | default | `GAP-23` |
| . A title and a URL are not a licence. | `90-course.js:1971` | default | `GAP-23` |

### SourceProvenancePanel (`90-course.js` from line 1994)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading this course’s sources | `90-course.js:2013` | default | `GAP-23` |
| The sources could not be read | `90-course.js:2017` | error | `GAP-23` |
| {…}{…} Nothing is shown from a cached list. | `90-course.js:2018` | default | `GAP-23` |
| Try again | `90-course.js:2019`; `90-course.js:2279`; `90-course.js:2558`; `90-course.js:4220`; `90-course.js:4919` | default | `GAP-23` |
| No source has been read yet | `90-course.js:2027` | empty | `GAP-23` |
| A source list is read with this course’s lesson page. Until that read runs, nothing is presented as cited. | `90-course.js:2029` | default | `GAP-23` |
| No source is recorded | `90-course.js:2037` | empty | `GAP-23` |
| No source is recorded for this course. Nothing on it is presented as cited, and no excerpt is invented to fill the gap. | `90-course.js:2040` | empty | `GAP-23` |

### ProvenanceInventoryRow (`90-course.js` from line 2069)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Not applicable | `90-course.js:2078` | default | `GAP-23` |
| No vocabulary inventory applies: this course does not declare a language domain. | `90-course.js:2081` | empty | `GAP-23` |
| No word list is verified for this plan{…}. No word list or coverage claim is shown. | `90-course.js:2082` | empty | `GAP-23` |
| Word list recorded | `90-course.js:2099` | default | `GAP-23` |
| Vocabulary source {…} · {…} · {…} · band {…} (ranks {…}–{…}) · {…} | `90-course.js:2101` | default | `GAP-23` |
| {…} vocabulary item{…} named from this band. The plan may only use words this declared list contains. | `90-course.js:2107` | default | `GAP-23` |
| Inventory id: {…}. Rows hash: {…}. | `90-course.js:2116` | default | `GAP-23` |
| Licence URL: {…}. | `90-course.js:2117` | default | `GAP-23` |

### SourcesView (`90-course.js` from line 2127)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Each row is one recorded source. The support class is what the backend stored; the excerpt is the text it fetched. A support verdict came from a model unless it says otherwise, and a listed source is not itself a citation. | `90-course.js:2138` | default | `GAP-23` |

### COURSE_EXPORT_BLOCKED_COPY (`90-course.js` from line 2152)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The plan is not approved yet. Approve the plan before packaging this course: an unapproved plan is not a published design. | `90-course.js:2154` | default | `GAP-23` |
| At least one lesson page has not passed validation, so it cannot be packaged. Regenerate or fix the page first; a page no validator cleared is not content to hand to someone else. | `90-course.js:2156` | error | `GAP-23` |
| This course has no lesson pages yet. Generate the lessons before packaging it. | `90-course.js:2158` | default | `GAP-23` |
| The lesson text changed after it was approved. Review the pages again before packaging them. | `90-course.js:2160` | default | `GAP-23` |
| The generated lessons do not meet the pack’s teaching minima yet, so the archive would not import. Fix the lesson content first. | `90-course.js:2162` | default | `GAP-23` |
| The archive could not be written. Nothing was exported and nothing was sent anywhere. | `90-course.js:2164` | error | `GAP-23` |
| This course came from a pack. Its file list and licence belong to that pack, so re-export it from the pack surface — this course cannot export its own copy. | `90-course.js:2166` | error | `GAP-23` |

### COURSE_EXPORT_PRIVATE_ROWS (`90-course.js` from line 2177)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Attempts, answers and grades | `90-course.js:2178` | default | `GAP-23` |
| learner evidence, never read | `90-course.js:2178` | default | `GAP-23` |
| Notebook notes and saved excerpts | `90-course.js:2179` | default | `GAP-23` |
| personal prose, never read | `90-course.js:2179` | default | `GAP-23` |
| Parent observations and chat transcripts | `90-course.js:2180` | default | `GAP-23` |
| teaching history, never read | `90-course.js:2180` | default | `GAP-23` |
| Provider settings, bindings and enrollment id | `90-course.js:2181` | default | `GAP-23` |
| local state, never read | `90-course.js:2181` | default | `GAP-23` |

### COURSE_EXPORT_REPAIR (`90-course.js` from line 2190)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Review and approve the plan | `90-course.js:2191` | default | `GAP-23` |
| Generate the lessons | `90-course.js:2192` | default | `GAP-23` |
| Open the plan to fix the pages | `90-course.js:2193` | default | `GAP-23` |
| Review and re-approve the lesson set | `90-course.js:2194` | default | `GAP-23` |
| Open the plan to fix the lessons | `90-course.js:2195` | default | `GAP-23` |
| Export the pack from Library | `90-course.js:2196` | default | `GAP-23` |

### CourseExportView (`90-course.js` from line 2215)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The lesson text changed since this page was read, so nothing was exported. The review was refreshed; export again only if the new file list is the one you want. | `90-course.js:2241` | default | `GAP-23` |
| The backend exported a different content hash than the one reviewed. Nothing here should be handed on. | `90-course.js:2250` | default | `GAP-23` |
| This backend build does not publish the course export commands, so there is no export action here. Nothing is offered that would produce a file the backend did not write. | `90-course.js:2269` | error | `GAP-23` |
| Reading what an export would contain | `90-course.js:2273` | default | `GAP-23` |
| The export review could not be read | `90-course.js:2277` | error | `GAP-23` |
| This course cannot be packaged yet | `90-course.js:2292` | error | `GAP-23` |
| The backend gave no reason, so no export is offered. | `90-course.js:2298` | error | `GAP-23` |
| {…} of {…} validated. | `90-course.js:2311` | default | `GAP-23` |
| Check again | `90-course.js:2326`; `90-course.js:2329` | default | `GAP-23` |
| Nothing was exported: a refused review writes no archive and sends nothing anywhere. | `90-course.js:2332` | error | `GAP-23` |
| Export this course | `90-course.js:2342` | default | `GAP-23` |
| Review what goes with the course, what stays behind, and the exact text hash before anything is packaged. | `90-course.js:2343` | default | `GAP-23` |
| GOES IN THE ARCHIVE | `90-course.js:2345` | default | `GAP-23` |
| {…}: this course’s own lesson text and its guides, and nothing else. | `90-course.js:2349` | default | `GAP-23` |
| STAYS ON THIS PROFILE | `90-course.js:2374` | default | `GAP-23` |
| There is no option here to add learner history to a course archive. The backend builds the archive from | `90-course.js:2385` | default | `GAP-23` |
| the lesson rows only, so notes and answers are absent by construction, not by a setting this page forgot. | `90-course.js:2386` | default | `GAP-23` |
| Content hash | `90-course.js:2394`; `90-course.js:2436` | default | `GAP-23` |
| version {…} · {…} | `90-course.js:2403` | default | `GAP-23` |
| I reviewed these files, the licence and the rights statement; package exactly this text. | `90-course.js:2418` | default | `GAP-23` |
| Export these files | `90-course.js:2426` | default | `GAP-23` |
| Matches the reviewed hash | `90-course.js:2439` | default | `GAP-23` |
| {…} v{…} | `90-course.js:2442` | default | `GAP-23` |
| Pack manifest hash | `90-course.js:2445` | default | `GAP-23` |
| Archive bytes | `90-course.js:2450` | default | `GAP-23` |
| Archive file hash | `90-course.js:2455` | default | `GAP-23` |
| Download archive | `90-course.js:2467` | default | `GAP-23` |
| The download link is the host route the backend named; the session is checked there and the | `90-course.js:2474` | default | `GAP-23` |
| handle expires. The file is byte-identical to the hash above. | `90-course.js:2475` | default | `GAP-23` |
| The archive travels: open Library → Import pack on another profile, review the same hash, then | `90-course.js:2481` | default | `GAP-23` |
| resume an existing classroom for this pack or start a fresh enrollment. The pack identity (id and | `90-course.js:2482` | default | `GAP-23` |
| hash above) is the shared course; the enrollment identity is created by the profile that imports it. | `90-course.js:2483` | default | `GAP-23` |

### lessonHeroPlan (`90-course.js` from line 2498)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Back to sections | `90-course.js:2503` | default | `GAP-23` |
| Why this is next | `90-course.js:2504`; `90-course.js:2510`; `90-course.js:4570` | default | `GAP-23` |
| Start the lesson | `90-course.js:2508` | default | `GAP-23` |
| Open the textbook | `90-course.js:2509` | default | `GAP-23` |

### CB3_COURSE_COPY (`90-course.js` from line 2536)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Back to | `90-course.js:2537` | default | `GAP-23` |
| Your route | `90-course.js:2538` | default | `GAP-23` |
| You are here | `90-course.js:2539` | default | `GAP-23` |
| Opens after the section before it | `90-course.js:2542` | default | `GAP-23` |
| Your other courses | `90-course.js:2545` | default | `GAP-23` |
| No scene yet | `90-course.js:2546` | empty | `GAP-23` |
| The lesson works without art. | `90-course.js:2547` | default | `GAP-23` |
| Painting the scene. | `90-course.js:2548` | default | `GAP-23` |
| This scene was not approved | `90-course.js:2549` | default | `GAP-23` |
| Open World Studio | `90-course.js:2550` | default | `GAP-23` |
| The plan is waiting for you | `90-course.js:2551` | default | `GAP-23` |
| Read it, then approve it so lessons can start. | `90-course.js:2552` | default | `GAP-23` |
| Course complete | `90-course.js:2553` | default | `GAP-23` |
| Every section has evidence. | `90-course.js:2554` | default | `GAP-23` |
| Opening this course. | `90-course.js:2555` | default | `GAP-23` |
| This course could not be read | `90-course.js:2556` | error | `GAP-23` |
| The route shows what was saved last. Try again. | `90-course.js:2557` | default | `GAP-23` |

### cb3CourseEvidenceLine (`90-course.js` from line 2562)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| {…} of {…} sections have evidence | `90-course.js:2566` | default | `GAP-23` |

### REVIEW_SCHEDULE_COPY (`90-course.js` from line 3638)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Start the interval again from today. | `90-course.js:3639` | default | `GAP-23` |
| Wait one interval longer before this returns. | `90-course.js:3640` | default | `GAP-23` |
| Take it out of the review queue. The evidence stays. | `90-course.js:3641` | default | `GAP-23` |
| Put this section back in the review queue. | `90-course.js:3642` | default | `GAP-23` |

### reviewDueLabel (`90-course.js` from line 3651)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| no due date recorded | `90-course.js:3652` | empty | `GAP-23` |

### reviewBacklogNotice (`90-course.js` from line 3714)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Showing {…} of {…} due sections. One more returns as you clear these. | `90-course.js:3717` | default | `GAP-23` |
| Showing {…} of {…} due sections. The other {…} return as you clear these. | `90-course.js:3719` | default | `GAP-23` |

### ReviewDuePanel (`90-course.js` from line 3726)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The backend did not answer the review action, so nothing here changed. | `90-course.js:3768` | error | `GAP-23` |
| Untitled section | `90-course.js:3820` | default | `GAP-23` |
| section {…}: {…} | `90-course.js:3821` | default | `GAP-23` |
| {…} · dropped {…} | `90-course.js:3823` | default | `GAP-23` |
| {…} · due {…} | `90-course.js:3824` | default | `GAP-23` |
| Open {…} | `90-course.js:3855`; `90-course.js:3856` | default | `GAP-23` |
| You took this out of the queue. Resume puts it back. | `90-course.js:3869` | default | `GAP-23` |
| Decide when this comes back. | `90-course.js:3870` | default | `GAP-23` |
| {…} review of {…} | `90-course.js:3881` | default | `GAP-23` |
| {…} recorded. | `90-course.js:3899` | default | `GAP-23` |
| State now {…}; | `90-course.js:3900` | default | `GAP-23` |
| next due {…}; | `90-course.js:3901` | default | `GAP-23` |
| recorded {…}. | `90-course.js:3902` | default | `GAP-23` |
| {…} The queue is unchanged; read it again before retrying. | `90-course.js:3919` | default | `GAP-23` |
| Read the queue again | `90-course.js:3926` | default | `GAP-23` |

### CourseDetail (`90-course.js` from line 3941)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This course has no current objective yet; approve the plan first. | `90-course.js:4081` | default | `GAP-23` |
| A new lesson chat is open. Send the first message to connect it to this lesson. | `90-course.js:4103` | default | `GAP-23` |
| Open the lesson chat | `90-course.js:4107` | default | `GAP-23` |
| Start anyway | `90-course.js:4120`; `90-course.js:4996` | default | `GAP-23` |
| The saved plan could not be read yet, so this page cannot be written from here. Open Plan to start it. | `90-course.js:4152` | error | `GAP-23` |
| This page could not be written again. The plan and every page already written are unchanged. | `90-course.js:4169` | error | `GAP-23` |
| Writing this page again. Pages already written for this plan are kept. | `90-course.js:4174` | default | `GAP-23` |
| The notebook could not be read | `90-course.js:4218` | error | `GAP-23` |
| This build cannot name the authored section for this objective, so it cannot repair it from here. | `90-course.js:4292` | error | `GAP-23` |
| The repair could not be queued. | `90-course.js:4308` | error | `GAP-23` |
| Queued one new page for this section. Other sections, their media and every attempt are untouched. | `90-course.js:4313` | default | `GAP-23` |
| In this course | `90-course.js:4369` | default | `GAP-23` |
| {…} of {…} | `90-course.js:4373` | default | `GAP-23` |
| With independent evidence | `90-course.js:4373` | default | `GAP-23` |
| Due for review | `90-course.js:4375` | default | `GAP-23` |
| All courses | `90-course.js:4503` | default | `GAP-23` |
| Course surfaces | `90-course.js:4638` | default | `GAP-23` |
| More · {…} | `90-course.js:4650` | default | `GAP-23` |
| You are reading {…} from More. Overview, Learn, Notebook and Evidence stay one click away above. | `90-course.js:4680` | default | `GAP-23` |
| Nothing is due for review right now. | `90-course.js:4704` | empty | `GAP-23` |
| {…} {…} out of the queue. | `90-course.js:4706` | default | `GAP-23` |
| See what is due | `90-course.js:4715` | default | `GAP-23` |

### SnapshotLossNotice (`90-course.js` from line 4760)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| {…} teaching {…} could not be saved to this lesson. The chat has them; this page does not. | `90-course.js:4774` | error | `GAP-23` |
| Last recorded {…}. | `90-course.js:4779` | default | `GAP-23` |
| Coursebook could not check whether any teaching turn was lost. | `90-course.js:4789` | error | `GAP-23` |

### LessonPaneBody (`90-course.js` from line 4800)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Focused the bound lesson chat. | `90-course.js:4865` | default | `GAP-23` |
| A new lesson run is ready. Its chat connects when you send your first message. | `90-course.js:4893` | default | `GAP-23` |
| This Desktop build cannot open a new chat; start one from the sidebar. | `90-course.js:4894` | error | `GAP-23` |
| Abandoned from the Coursebook pane. | `90-course.js:4904` | default | `GAP-23` |
| Binding abandoned. Start a new governed run when you are ready. | `90-course.js:4910` | default | `GAP-23` |
| Cannot read this lesson | `90-course.js:4917` | error | `GAP-23` |
| The course list could not be read. | `90-course.js:4918` | error | `GAP-23` |
| Bound, but not listed | `90-course.js:4925` | default | `GAP-23` |
| This chat is connected to a course the library did not return. Nothing is guessed: reopen Coursebook to check it. | `90-course.js:4927` | error | `GAP-23` |
| Open Coursebook | `90-course.js:4928`; `90-course.js:4968` | default | `GAP-23` |
| binding {…} | `90-course.js:4945` | default | `GAP-23` |
| This chat is not part of a lesson yet. Open Coursebook and start a lesson; the first message in its new chat connects it. | `90-course.js:4961` | default | `GAP-23` |
| Current check | `90-course.js:4976` | default | `GAP-23` |
| The lesson page could not be read. | `90-course.js:4980` | error | `GAP-23` |
| No check could be opened. | `90-course.js:5002` | empty | `GAP-23` |
| Opening the current check | `90-course.js:5005` | default | `GAP-23` |
| Open lesson chat | `90-course.js:5032` | default | `GAP-23` |
| Continue lesson | `90-course.js:5040` | default | `GAP-23` |
| Full course | `90-course.js:5042` | default | `GAP-23` |
| {…} due for review | `90-course.js:5052` | default | `GAP-23` |
| Nothing due | `90-course.js:5053` | empty | `GAP-23` |
| Review is unavailable right now | `90-course.js:5054` | error | `GAP-23` |
| {…} sources | `90-course.js:5059` | default | `GAP-23` |
| This lesson has no durable chat to continue yet. | `90-course.js:5072` | default | `GAP-23` |
| This lesson is not connected to its chat right now. Open it from the course page first. | `90-course.js:5073` | default | `GAP-23` |
| Opening the lesson chat failed: {…} | `90-course.js:5078` | error | `GAP-23` |
| Continue the lesson. | `90-course.js:5083` | default | `GAP-23` |
| Asked the lesson chat to continue. | `90-course.js:5084` | default | `GAP-23` |
| The lesson chat is not on screen, so nothing was sent. Open it and continue there. | `90-course.js:5085` | default | `GAP-23` |
| This Desktop build cannot send a message; open the lesson chat and continue there. | `90-course.js:5087` | error | `GAP-23` |


**Offline and overflow evidence:** this file adds no offline sentence — a failed read renders a
named error with a retry, not an offline state (`GAP-35`) — and no list here states an overflow
rule; the notebook renders every saved moment.
