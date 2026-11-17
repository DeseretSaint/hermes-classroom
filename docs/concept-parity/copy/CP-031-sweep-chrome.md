# CP-031c — Shared chrome shipped-string sweep

Card: **CP-031c** (`t_0458a135`), re-swept by **CP-031c-R** (`t_54a44039`) at `a11bc0e4`, re-derived by **CP-031d** (`t_d20f3f5e`) at `14fb14f3`, and re-swept by **CP-031e** (`t_868205f4`) at `a0925957`. Docs only; no product string changed.

**Revision swept:** `origin/master` at **`a0925957fc43edfb8ce3f7c846c9f49309897c0f`** (00-header.js, 1226 lines, whole file).
**Rows:** 52 inventory rows — the 51 multi-word literals the lexer extracts from this revision,
plus the single-token state word `Started`, rowed by hand (CP-001g, `t_4d6d5b56`) because a
one-word state word is exactly the family member that can vanish between sweeps. Every row cites the
line(s) that carry its words in this revision.

**CP-031e re-derivation (`t_868205f4`):** between `14fb14f3` and `a0925957` only `00-header.js`
moved (`ab62cbd7` → `b4b8bd87`); the four other segment blobs are byte-identical, so their rows and
citations were re-checked rather than rewritten. The move is `525aa8ba`'s health work: a net twelve
added lines across 1076–1111 introducing the pure `healthStatus(result)` helper and a `failed`
state. Re-running this repo's lexer at the new revision gives 0 missing rows, 0 miscited rows, 0
out-of-file citations, and no citation at or above line 1076, so no stored line number moved. The
helper adds no row to *this* file: its return values (`'ready'`, `'failed'`, `'degraded'`) are
single tokens the multi-word gate drops, and the rest of the block is comments. The `failed` state's
learner-visible wording is real, but it ships in `desktop/src/10-primitives.js` (`backendCopy`,
`MigrationFailedBody`) — a file no CP-031c sweep covers — so it is rowed in `GAP-43` instead of
being silently attributed here.

**Surface:** the rail, route title, learner vocabulary, create form, settings sheet, tutor path and the
shell's error sentences.

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

### CB_COPY (`00-header.js` from line 59)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Independent evidence | `00-header.js:60` | default | `GAP-42` → `game.state.independent_evidence` |
| Not started | `00-header.js:65` | default | `GAP-42` → `game.state.not_started` |
| Started | `00-header.js:66` | default | `GAP-42` → `game.state.introduced` |
| Delayed evidence | `00-header.js:68` | default | `GAP-42` → `game.state.delayed_evidence` |
| Review due | `00-header.js:69` | default | `GAP-42` → `game.state.review_due` |
| Could not be written | `00-header.js:73` | error | `GAP-42` → `game.state.needs_review` |
| Moved on without a grade | `00-header.js:74` | default | `GAP-42` → `game.state.overridden` |
| No check yet | `00-header.js:77` | empty | `GAP-42` |
| Check open | `00-header.js:78` | default | `GAP-42` |
| Check closed | `00-header.js:79` | default | `GAP-42` |
| Check replaced | `00-header.js:80` | default | `GAP-42` |
| {…} {…} of {…} | `00-header.js:92` | default | `GAP-42` |
| State not recorded | `00-header.js:98` | default | `GAP-42` → `game.state.unknown` |
| Check state not recorded | `00-header.js:102` | default | `GAP-42` |

`Started` had no row at all before CP-001g: the extractor drops single-token literals, so the only
one of the seven state words that never gained a sweep row was the one that says a section has been
introduced. It is rowed here by hand (`GAP-42`) so the family is complete by name, not only by
extraction.

### RECIPE_COPY (`00-header.js` from line 120)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| One task I need to do now | `00-header.js:122` | default | `GAP-37` |
| A single thing to get right — a repair, a form, a procedure. You practise the task, not a quiz. | `00-header.js:123` | default | `GAP-37` |
| A little at a time | `00-header.js:126` | default | `GAP-37` |
| Short sessions you pick up when you have ten minutes, with no schedule to keep. | `00-header.js:127` | default | `GAP-37` |
| A steady plan | `00-header.js:130` | default | `GAP-37` |
| A sequence that builds on itself, with practice you come back to. | `00-header.js:131` | default | `GAP-37` |
| Alongside something else | `00-header.js:134` | default | `GAP-37` |
| A subject you keep returning to while you study or work on other things. | `00-header.js:135` | default | `GAP-37` |
| Preparing for my child | `00-header.js:138` | default | `GAP-37` |
| You are preparing material for a child. That happens in Parent Studio, not here. | `00-header.js:139` | default | `GAP-37` |

### FILTERS (`00-header.js` from line 176)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| In progress | `00-header.js:178` | default | `GAP-37` |

### DESTINATIONS (`00-header.js` from line 187)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Parent Studio | `00-header.js:193` | default | `GAP-37` |

### CB_REDUCED_MOTION_OPTIONS (`00-header.js` from line 239)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Follow system | `00-header.js:240` | default | `GAP-37` |
| Reduce motion | `00-header.js:241` | default | `GAP-37` |

### CB_CHILD_SAFE_RULES (`00-header.js` from line 251)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Loss-framed reminders | `00-header.js:252` | default | `GAP-37` |
| Public leaderboard | `00-header.js:253` | default | `GAP-37` |
| Loot or random rewards | `00-header.js:254` | default | `GAP-37` |
| XP and levels | `00-header.js:256` | default | `GAP-37` |
| Game only | `00-header.js:256` | default | `GAP-37` |

### CB_SESSION_OPTIONS (`00-header.js` from line 258)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| 10 min | `00-header.js:259` | default | `GAP-37` |
| 15 min | `00-header.js:260` | default | `GAP-37` |
| 20 min | `00-header.js:261` | default | `GAP-37` |
| 30 min | `00-header.js:262` | default | `GAP-37` |

### IMPORT_FLOW_WIRED (`00-header.js` from line 486)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| profile routes could not be read | `00-header.js:514` | error | `GAP-30` |

### requireContext (`00-header.js` from line 633)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Coursebook is not registered | `00-header.js:634`; `00-header.js:1065`; `00-header.js:1070` | default | `GAP-30` |

### transportFailure (`00-header.js` from line 650)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The Coursebook backend answered with something that is not a contract envelope. | `00-header.js:710` | default | `GAP-39` |

### currentSessionIds (`00-header.js` from line 828)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| loadBinding needs exactly one of storedSessionId or enrollmentId | `00-header.js:838` | default | `GAP-40` |

### revealCoursebookPane (`00-header.js` from line 849)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This lesson has no chat to return to yet. | `00-header.js:867` | default | `GAP-40` |
| This lesson is not connected to a chat right now. | `00-header.js:870` | default | `GAP-40` |
| Update Hermes Desktop to resume a bound lesson. | `00-header.js:873` | default | `GAP-40` |
| The saved lesson chat could not be opened from this desktop. The section is still available to read. | `00-header.js:883` | error | `GAP-40` |

### openArmedLessonChat (`00-header.js` from line 909)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Coursebook lesson | `00-header.js:937` | default | `GAP-40` |
| No course was read for this action. | `00-header.js:984` | empty | `GAP-40` |
| This course has no current objective yet; approve the plan first. | `00-header.js:987` | default | `GAP-40` |
| Resumed the bound lesson chat. | `00-header.js:1024` | default | `GAP-40` |
| There is no saved lesson chat for this section yet. Read the section below, then start a new lesson when you are ready. | `00-header.js:1033` | default | `GAP-40` |
| The lesson is ready. Your section is open below. The chat becomes this lesson’s chat when you send your first message. | `00-header.js:1053` | default | `GAP-40` |

### describeError (`00-header.js` from line 1057)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The Coursebook backend did not answer. | `00-header.js:1058`; `00-header.js:1061` | error | `GAP-40` |


**Offline and overflow evidence:** this file has no `useOnline()` branch and no truncating list,
so it authors no offline sentence and no overflow copy. The shell's offline lines live in the route
files (`32-desk.js:352`, `98-page.js:632`, `10-primitives.js:273`; `GAP-35`).
