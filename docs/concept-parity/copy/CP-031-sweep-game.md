# CP-031c — Game and Home shipped-string sweep

Card: **CP-031c** (`t_0458a135`), re-swept by **CP-031c-R** (`t_54a44039`) at `a11bc0e4`. Docs only; no product string changed.

**Revision swept:** `origin/master` at **`a11bc0e4bdf55683ea3c1660f8031d0f5a5f3ef6`** (30-home.js, 5215 lines, whole file).
**Rows:** 216 inventory rows; 216 distinct literals. Every row cites the line(s)
that carry its words in this revision.

**Surface:** the Home shelf and defaults line, the Game band, the play layer and the field journal.

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

### DESK_PRIMARY_LABEL (`30-home.js` from line 30)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Start a fresh run | `30-home.js:31` | default | `GAP-03` |
| Resume the lesson | `30-home.js:32` | default | `GAP-03` |
| Start the review | `30-home.js:36` | default | `GAP-03` |
| Reconnect the chat | `30-home.js:37` | default | `GAP-03` |
| Review the plan | `30-home.js:38` | default | `GAP-03` |
| Review the pack | `30-home.js:39` | default | `GAP-03` |
| Course complete | `30-home.js:41` | default | `GAP-03` |
| Repair this lesson | `30-home.js:42` | default | `GAP-03` |
| Write the lesson | `30-home.js:45` | default | `GAP-03` |

### CB_HOME_COPY (`30-home.js` from line 87)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| What will you learn next? | `30-home.js:88` | default | `GAP-03` |
| Pick a course, or chart a new one. | `30-home.js:89` | default | `GAP-03` |
| Start a new course | `30-home.js:90`; `30-home.js:175` | default | `GAP-03` |
| Browse the library | `30-home.js:91` | default | `GAP-03` |
| Your courses | `30-home.js:92`; `30-home.js:177` | default | `GAP-03` |
| See all | `30-home.js:93`; `30-home.js:178` | default | `GAP-03` |
| No courses yet. | `30-home.js:94`; `30-home.js:195` | empty | `GAP-03` |
| Start with a goal, or browse a ready-made course. | `30-home.js:95` | default | `GAP-03` |
| Reading your courses… | `30-home.js:96` | default | `GAP-03` |
| Your courses could not be read | `30-home.js:97`; `30-home.js:188` | error | `GAP-03` |
| This backend does not report course mode yet. | `30-home.js:98` | default | `GAP-03` |
| Course mode could not be read. | `30-home.js:99` | error | `GAP-03` |

### CB_HOME_V3_COPY (`30-home.js` from line 170)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Your field library | `30-home.js:171`; `30-home.js:180` | default | `GAP-03` |
| Choose a course or start a new expedition. | `30-home.js:174` | default | `GAP-03` |
| Browse library | `30-home.js:176` | default | `GAP-03` |
| New course | `30-home.js:179`; `30-home.js:2488` | default | `GAP-03` |
| Nothing here yet. Start a course and its first lesson will appear on this shelf. | `30-home.js:181` | empty | `GAP-03` |
| Start your first course | `30-home.js:182` | default | `GAP-03` |
| More courses to the right | `30-home.js:183` | default | `GAP-03` |
| No courses on this shelf | `30-home.js:184` | empty | `GAP-03` |
| Courses you archive move out of this view. | `30-home.js:185` | default | `GAP-03` |
| See archived courses | `30-home.js:186` | default | `GAP-03` |
| Reading your courses. Nothing on the shelf changes while this loads. | `30-home.js:187` | default | `GAP-03` |
| Nothing you saved is lost. Try again. | `30-home.js:189` | empty | `GAP-03` |
| Try again | `30-home.js:190`; `30-home.js:193`; `30-home.js:3667`; `30-home.js:3796`; `30-home.js:3969`; `30-home.js:4927` | default | `GAP-03` |
| You are offline | `30-home.js:191` | offline | `GAP-03` |
| Your shelf is here. New lessons wait until you reconnect. | `30-home.js:192` | default | `GAP-03` |
| Every course here is archived. Unarchive one in Courses to continue it. | `30-home.js:196` | default | `GAP-03` |
| This is a failed read, not an empty library. | `30-home.js:202` | error | `GAP-03` |
| Parent Studio holds your lesson plans. | `30-home.js:203` | default | `GAP-03` |
| This profile has parent-led lesson plans, not a learner course. Start a learner course here, or open Parent Studio. | `30-home.js:205` | default | `GAP-03` |
| Open Parent Studio | `30-home.js:206` | default | `GAP-03` |
| {…} checks recorded | `30-home.js:235` | default | `GAP-03` |

### homeCardFacts (`30-home.js` from line 243)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| {…} of {…} sections done | `30-home.js:257`; `30-home.js:259`; `30-home.js:773` | default | `GAP-03` |

### HomeV3Card (`30-home.js` from line 477)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Untitled course | `30-home.js:194`; `30-home.js:479`; `30-home.js:733`; `30-home.js:1773`; `30-home.js:1972`; `30-home.js:1987` | default | `GAP-03` |
| Open {…} | `30-home.js:503`; `30-home.js:785` | default | `GAP-03` |

### cbShelfEdgeMask (`30-home.js` from line 633)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| linear-gradient(to right, {…}) | `30-home.js:644` | default | `GAP-03` |

### deskEstimateLabel (`30-home.js` from line 1592)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Reading the estimate | `30-home.js:1594` | default | `GAP-03` |
| Session length could not be read | `30-home.js:1595` | error | `GAP-03` |
| ≈ {…} min | `30-home.js:1596` | default | `GAP-03` |
| Session length not recorded | `30-home.js:1597` | default | `GAP-03` |

### buildDeskModel (`30-home.js` from line 1608)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| No next step was recorded for this course. | `30-home.js:1660` | empty | `GAP-03` |
| Open the lesson | `30-home.js:1661` | default | `GAP-03` |

### ShelfMemberOpen (`30-home.js` from line 1771)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Open {…}, updated {…} | `30-home.js:1778` | default | `GAP-03` |
| Open “{…}” | `30-home.js:1787` | default | `GAP-03` |

### ShelfDisclosure (`30-home.js` from line 1801)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| {…} for {…} | `30-home.js:1809` | default | `GAP-03` |
| Can’t open “{…}” from here. | `30-home.js:1864` | default | `GAP-03` |
| Open the Library shelf | `30-home.js:1869` | default | `GAP-03` |
| Open it from the Library shelf. | `30-home.js:1871` | default | `GAP-03` |

### PackShelfRow (`30-home.js` from line 2030)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Untitled pack | `30-home.js:2035` | default | `GAP-03` |
| Preview {…} | `30-home.js:2065`; `30-home.js:2150` | default | `GAP-03` |
| No sections yet | `30-home.js:2110`; `30-home.js:3237` | empty | `GAP-03` |
| Nothing to open yet. Preview it to see the manifest. | `30-home.js:2133` | empty | `GAP-03` |

### DeskFacts (`30-home.js` from line 2193)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| This section | `30-home.js:2196` | default | `GAP-03` |
| {…} of {…} | `30-home.js:2197` | default | `GAP-03` |
| With evidence | `30-home.js:2197` | default | `GAP-03` |
| Due now | `30-home.js:2198` | default | `GAP-03` |

### SlotTab (`30-home.js` from line 2384)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| opacity, transform | `30-home.js:2425`; `30-home.js:2974`; `30-home.js:2975`; `30-home.js:3464`; `30-home.js:3691` | default | `GAP-03` |
| Next step not recorded | `30-home.js:2437` | default | `GAP-03` |
| Last touched {…} | `30-home.js:2441`; `30-home.js:3092` | default | `GAP-03` |
| Nothing touched yet | `30-home.js:2441`; `30-home.js:3092` | empty | `GAP-03` |

### SlotRail (`30-home.js` from line 2456)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Your other classrooms | `30-home.js:2475` | default | `GAP-03` |
| All courses | `30-home.js:2493` | default | `GAP-03` |
| Showing {…} | `30-home.js:2503` | default | `GAP-03` |
| This course has {…} progress records; showing the most recent. | `30-home.js:2510` | default | `GAP-03` |
| Choose a classroom | `30-home.js:2559` | default | `GAP-03` |
| Classroom shelf | `30-home.js:2614` | default | `GAP-03` |

### StudyCompanion (`30-home.js` from line 2795)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Your study companion | `30-home.js:2917`; `30-home.js:2918` | default | `GAP-03` |
| {…} · study companion | `30-home.js:2918` | default | `GAP-03` |

### cbNextStopSentence (`30-home.js` from line 2925)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| is due for another check. Answer it once to bring the evidence up to date. | `30-home.js:2926` | default | `GAP-03` |
| . Pick up where you stopped and finish this section. | `30-home.js:2927` | default | `GAP-03` |
| . Work through this section, then finish its check. | `30-home.js:2928` | default | `GAP-03` |
| . Generate its lesson from the Plan tab, then start it. | `30-home.js:2929` | default | `GAP-03` |
| . Read the recorded plan before the first lesson starts. | `30-home.js:2930` | default | `GAP-03` |
| . Check the imported pack before it becomes a course. | `30-home.js:2931` | default | `GAP-03` |
| . The page could not be written; repair it from the reasons it names. | `30-home.js:2932` | error | `GAP-03` |
| . Every section has evidence and nothing is due. | `30-home.js:2933` | default | `GAP-03` |
| . Open it to see what this course records next. | `30-home.js:2934` | default | `GAP-03` |

### ContinueCard (`30-home.js` from line 2964)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| THE REVIEW IS DUE | `30-home.js:2991` | default | `GAP-03` |
| COURSE COMPLETE | `30-home.js:2993` | default | `GAP-03` |
| THE PAGE COULD NOT BE WRITTEN | `30-home.js:2995` | error | `GAP-03` |
| CONTINUE THE TRAIL | `30-home.js:2996` | default | `GAP-03` |
| Retry reading the session length | `30-home.js:3086` | default | `GAP-03` |
| Open section | `30-home.js:3110` | default | `GAP-03` |
| See the plan | `30-home.js:3117` | default | `GAP-03` |

### cbPathEvidenceCaption (`30-home.js` from line 3235)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| {…} of {…} {…} with evidence{…} | `30-home.js:3243` | default | `GAP-03` |

### PathRouteSegment (`30-home.js` from line 3317)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| M {…} 0 C {…} 42, {…} 58, {…} 100 | `30-home.js:3318` | default | `GAP-03` |
| M {…} 0 L {…} 100 | `30-home.js:3318` | default | `GAP-03` |

### cbPathDetailText (`30-home.js` from line 3404)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Evidence: {…} | `30-home.js:3406` | default | `GAP-03` |
| No committed attempts yet | `30-home.js:3407` | empty | `GAP-03` |
| {…} committed attempt{…} | `30-home.js:3407` | default | `GAP-03` |
| Last opened {…} | `30-home.js:3408` | default | `GAP-03` |
| Not opened yet | `30-home.js:3408` | default | `GAP-03` |

### cbPathRunParts (`30-home.js` from line 3413)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Next: {…} · {…} | `30-home.js:3420` | default | `GAP-03` |

### CheckpointPath (`30-home.js` from line 3635)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The route | `30-home.js:3657`; `30-home.js:3695` | default | `GAP-03` |
| Your path | `30-home.js:3658`; `30-home.js:3696` | default | `GAP-03` |
| {…}{…} The route was not read. Continue still uses the next step this course recorded. | `30-home.js:3665` | default | `GAP-03` |
| This course has no objectives yet, so there is no path to show. Approve its plan to start one. | `30-home.js:3725` | default | `GAP-03` |
| Course route | `30-home.js:3729` | default | `GAP-03` |
| Course end | `30-home.js:3750` | default | `GAP-03` |

### SourcesDrawer (`30-home.js` from line 3762)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Hide sources | `30-home.js:3774` | default | `GAP-03` |
| Show sources | `30-home.js:3774` | default | `GAP-03` |
| Sources for “{…}” | `30-home.js:3778` | default | `GAP-03` |
| Sources for the current section | `30-home.js:3784` | default | `GAP-03` |
| Reading this section’s sources | `30-home.js:3788` | default | `GAP-03` |
| {…}{…} The sources were not read. | `30-home.js:3794` | default | `GAP-03` |
| No sources are recorded for this section yet. | `30-home.js:3800` | empty | `GAP-03` |
| Untitled source | `30-home.js:3810` | default | `GAP-03` |
| status unrecorded | `30-home.js:3811` | default | `GAP-03` |

### FieldNotesLine (`30-home.js` from line 3860)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Field notes · reading | `30-home.js:3866` | default | `GAP-03` |
| Field notes · could not be read | `30-home.js:3867` | error | `GAP-03` |
| Field notes · nothing saved yet | `30-home.js:3868` | default | `GAP-03` |
| Field notes · {…} saved | `30-home.js:3869` | default | `GAP-03` |
| · paused until the desk reconnects | `30-home.js:3883` | default | `GAP-03` |

### FieldNotesStrip (`30-home.js` from line 3890)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Go to the current lesson | `30-home.js:3908` | default | `GAP-03` |
| Field Notes | `30-home.js:3938` | default | `GAP-03` |
| {…} saved{…} | `30-home.js:3942` | default | `GAP-03` |
| All field notes | `30-home.js:3951` | default | `GAP-03` |
| These are the notes last read. A save or an edit is paused until the desk reconnects. | `30-home.js:3958` | default | `GAP-03` |
| {…}{…} Saved moments are still stored; this strip just could not read them. | `30-home.js:3967` | error | `GAP-03` |
| Reading your field notes | `30-home.js:3973` | default | `GAP-03` |
| Save an explanation, visual or quiz moment and it will appear here. | `30-home.js:3980` | default | `GAP-03` |
| Section · {…} | `30-home.js:4045` | default | `GAP-03` |
| saved {…} | `30-home.js:4048` | default | `GAP-03` |
| Open the saved moment “{…}” in Textbook | `30-home.js:4052` | default | `GAP-03` |
| Open in textbook | `30-home.js:4054` | default | `GAP-03` |

### CbGenerationUsage (`30-home.js` from line 4137)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| not recorded | `30-home.js:4143` | default | `GAP-03` |
| This build does not report generation usage. | `30-home.js:4154` | default | `GAP-03` |
| Reading the usage record… | `30-home.js:4159` | default | `GAP-03` |
| No usage total is shown while this read fails. | `30-home.js:4169` | empty | `GAP-03` |
| Read it again | `30-home.js:4171` | default | `GAP-03` |
| Generation calls: {…} | `30-home.js:4179` | default | `GAP-03` |
| Tokens in: {…} · out: {…} | `30-home.js:4183` | default | `GAP-03` |
| Cache read: {…} · cache write: {…} | `30-home.js:4187` | default | `GAP-03` |
| Artifacts generated: {…} | `30-home.js:4191` | default | `GAP-03` |
| Not recorded on every usage row: {…}. | `30-home.js:4200` | default | `GAP-03` |
| A value the backend did not record reads “not recorded”. Nothing on this line is estimated, and no total is added up here. | `30-home.js:4205` | error | `GAP-03` |

### HomeSettingsSheet (`30-home.js` from line 4221)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"]) | `30-home.js:4240` | default | `GAP-03` |
| On this device | `30-home.js:4347` | default | `GAP-03` |
| Close settings | `30-home.js:4355` | default | `GAP-03` |
| Stored for this Hermes profile on this device. Coursebook does not sync these settings to another device. | `30-home.js:4372` | default | `GAP-03` |
| The palette Coursebook paints inside its own surfaces. Hermes chrome keeps the app theme. | `30-home.js:4380` | default | `GAP-03` |
| Reset appearance to System | `30-home.js:4381` | default | `GAP-03` |
| Default view | `30-home.js:4402` | default | `GAP-03` |
| The view a lesson opens in. A single classroom can override it. | `30-home.js:4403` | default | `GAP-03` |
| Reset the default view to Game | `30-home.js:4404` | default | `GAP-03` |
| This classroom · {…} | `30-home.js:4425` | default | `GAP-03` |
| This classroom | `30-home.js:4425` | default | `GAP-03` |
| This classroom keeps its own view. Choosing the home default clears the override. | `30-home.js:4427` | default | `GAP-03` |
| Select a classroom on Home to give it its own view. | `30-home.js:4428` | default | `GAP-03` |
| Clear this classroom’s view override | `30-home.js:4429` | default | `GAP-03` |
| Home default | `30-home.js:4437` | default | `GAP-03` |
| Child-safe defaults | `30-home.js:4457` | default | `GAP-03` |
| For any lesson a child uses. No reminder scheduler, no public ranking, no random rewards and no streaks. XP and levels are cosmetic Game feedback only, and the Game feedback switch below hides them here. | `30-home.js:4459` | default | `GAP-03` |
| Reset the session length to 15 minutes | `30-home.js:4460` | default | `GAP-03` |
| Hidden here | `30-home.js:4482` | default | `GAP-03` |
| Session length | `30-home.js:4515` | default | `GAP-03` |
| A plan the parent writes, not a countdown. No reminder is sent when a session is missed. | `30-home.js:4535` | default | `GAP-03` |
| A short tone when a check is scored. Off by default. | `30-home.js:4549` | default | `GAP-03` |
| Reset sound to off | `30-home.js:4550` | default | `GAP-03` |
| Check cue sound | `30-home.js:4557` | default | `GAP-03` |
| One quiet tone at a verdict, never narration. | `30-home.js:4558` | default | `GAP-03` |
| Study companion | `30-home.js:4569` | default | `GAP-03` |
| The Hermes pet already installed in this profile can stand at the trailhead. Coursebook never draws a different avatar, and the companion is never a progress marker. | `30-home.js:4571` | default | `GAP-03` |
| Reset the study companion to shown | `30-home.js:4572` | default | `GAP-03` |
| Show my study companion | `30-home.js:4579` | default | `GAP-03` |
| Your own Hermes pet beside the trailhead. Off leaves the plate without a companion. | `30-home.js:4580` | default | `GAP-03` |
| Not available on desktop. | `30-home.js:4594` | error | `GAP-03` |
| Haptics are always off on desktop | `30-home.js:4595` | default | `GAP-03` |
| A desktop has no haptic engine, so Coursebook never offers a vibration response. There is nothing here to switch on or off. | `30-home.js:4602` | default | `GAP-03` |
| Reduced motion | `30-home.js:4611` | default | `GAP-03` |
| Follow the system setting, or hold Coursebook to no transitions even when the system allows them. | `30-home.js:4613` | default | `GAP-03` |
| Reset motion to follow the system | `30-home.js:4614` | default | `GAP-03` |
| Game feedback | `30-home.js:4637` | default | `GAP-03` |
| XP, the cosmetic level and the Game progress bar in Game mode, earned by finished checks — never by opening the app or checking in. Play progress only: hiding it never deletes your play history, and no check, source or lesson depends on it. | `30-home.js:4639` | default | `GAP-03` |
| Reset Game feedback to shown | `30-home.js:4640` | default | `GAP-03` |
| Show Game feedback | `30-home.js:4655` | default | `GAP-03` |
| The XP chip, level and progress bar in Game mode. Textbook, Guided and Parent Studio never show them either way. | `30-home.js:4657` | default | `GAP-03` |
| Generation usage | `30-home.js:4670` | default | `GAP-03` |
| What Coursebook’s own generation has used on this profile. A number the backend did not record is shown as not recorded, never as zero. | `30-home.js:4672` | error | `GAP-03` |
| Third-party notices | `30-home.js:4698` | default | `GAP-03` |
| {…} asset sources, with the licence each manifest declares. | `30-home.js:4702` | default | `GAP-03` |
| Open third-party notices | `30-home.js:4713` | default | `GAP-03` |
| View notices | `30-home.js:4717` | default | `GAP-03` |

### HomeDefaultsLine (`30-home.js` from line 4739)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Default view · | `30-home.js:4751` | default | `GAP-41` |
| · This classroom · | `30-home.js:4760` | default | `GAP-41` |
| · Child-safe defaults | `30-home.js:4770` | default | `GAP-41` |
| · Session · {…} min | `30-home.js:4775`; `30-home.js:4802` | default | `GAP-41` |

### ChildSafeLine (`30-home.js` from line 4790)

The same component renders in Parent Studio's take-home pack, where §3.1 of
`CP-031-sweep-parent-studio.md` rows it as well; this section is the Home copy. The Game
band's own vocabulary begins at `CB_GAME_ACTION_WORD`, below.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no streaks · XP is cosmetic Game feedback | `30-home.js:4798` | default | `GAP-41` |
| Open Coursebook settings | `30-home.js:4811` | default | `GAP-41` |

### CB_GAME_ACTION_WORD (`30-home.js` from line 4834)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Lesson step | `30-home.js:4835` | default | `GAP-24` |
| Homework done | `30-home.js:4838` | default | `GAP-24` |
| Came back | `30-home.js:4839` | default | `GAP-24` |

### CB_GAME_PROGRESS_NOTE (`30-home.js` from line 4847)

Every Game card also paints one of the objective-state words (`Not started`, `Independent evidence`,
`Delayed evidence`, `Review due`, `Could not be written`, `Moved on without a grade`) from
`CB_COPY` in `00-header.js`; those rows are in §CB_COPY of `CP-031-sweep-chrome.md`, and `GAP-42`
is the gap that owns them.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Play progress, not evidence. | `30-home.js:4847` | default | `GAP-24` |

### GameHeader (`30-home.js` from line 4878)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The field journal could not be read: {…} Your course is unaffected. | `30-home.js:4924` | error | `GAP-24` |
| Reading the field journal… | `30-home.js:4940` | default | `GAP-24` |
| {…} XP | `30-home.js:4974` | default | `GAP-24` |
| Level {…} | `30-home.js:4982` | default | `GAP-24` |
| · cosmetic | `30-home.js:4984` | default | `GAP-24` |
| Game progress | `30-home.js:5005`; `30-home.js:5016` | default | `GAP-24` |
| {…} of {…} {…} | `30-home.js:5008` | default | `GAP-24` |
| No steps assigned yet | `30-home.js:5009` | empty | `GAP-24` |

### cbGameSectionCards (`30-home.js` from line 5062)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Untitled section | `30-home.js:5066` | default | `GAP-24` |

### GameJournal (`30-home.js` from line 5083)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Field journal | `30-home.js:5090`; `30-home.js:5109` | default | `GAP-24` |
| {…} of {…} sections stamped by recorded evidence. | `30-home.js:5119` | default | `GAP-24` |
| Stamped | `30-home.js:5192` | default | `GAP-42` → `game.journal.stamped` |
| No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page. | `30-home.js:5120` | empty | `GAP-24` |

`Stamped` is the journal's earned word and is a single token, so the extractor never asked for a
row: it is rowed by hand under `GAP-42` so the card's earned state cannot vanish with a restyle.


**Offline and overflow evidence:** Home has an offline state (`CB_HOME_V3_COPY.offlineTitle` /
`offlineBody`, lines 191-193, rendered at 1191). The field journal caps at twelve cards
(`rows.slice(0, 12)` at 5064) and states no overflow sentence (`GAP-35`).
