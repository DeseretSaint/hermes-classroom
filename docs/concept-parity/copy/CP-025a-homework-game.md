# CP-025a — Homework and Game surfaces copy and state inventory

Card body: `docs/concept-parity/cards/CP-025a.md`.
Spec: `SPEC-V3.md` has **no** section for these surfaces. §5 ends at the design-system lab.
Deck: `COPY.md` has **no** section for these surfaces. Its sections are shell, Home, Discover,
Classroom, Course home, Lab (§1–§6, lines 48–271).

Deck rows used: **2** (`classroom.game.xp` line 174 for the band's XP figure; `home.settings` line 67
for the sheet that hosts the Game switch). Everything else is unsourced.

## What this card actually says

CP-025a's "This card" section is two lines long (lines 34–36):

> the homework action, sheet and notebook list from GM-008 and the Game header, award and completion
> from GM-010, rebuilt on v3 primitives with their existing tests kept green and their matrix cells
> re-captured.

Everything from line 38 to line 56 of the card body is a **copy of CP-021's body** (the Discover
string list, the shared capture paragraph and CP-021's file-ownership block). A maker reading CP-025a
sees "Heading \"Discover your next world\"" and a file-ownership line naming `96-workshop.js`. The
real ownership block at line 60 is correct. This is `GAP-26`: the body must be repaired before
dispatch, or the maker will work on the wrong screen.

Because the body names no strings, the inventory below is the **shipped v2 inventory** of the two
surfaces it names, taken from `desktop/src`. Every row is a deck gap; the proposal set is `GAP-23`
and `GAP-24` in `GAPS.md`.

**These tables are a partial sample.** They cover the homework action, sheet, field card, recording
and the two lists, plus the Game band and field journal, but not every literal in
`95-studio.js:1900-2950` and `30-home.js:3650-4100`; `GAP-30` records the incomplete sweep and the
follow-up. Do not author a `hw.*` / `game.*` deck section as if this file were the whole source.

## Homework (GM-008) — strings the shipped surface renders

### The lesson action and the sheet

| string | source | deck |
|---|---|---|
| Take this with you (footer action, panel title) | `desktop/src/95-studio.js:2346, 2368, 2538, 2546` | — |
| Take this with you · {section title} (accessible name) | `95-studio.js:2368` | — |
| Reading this lesson's task | `95-studio.js:2371` | — |
| The task could not be read. | `95-studio.js:2387, 2653` | — |
| Reason · {error code} | `95-studio.js:2389, 2751` | — |
| Try again | `95-studio.js:2394, 2655` | — |
| The lesson for this section is not written yet. | `95-studio.js:2337` | — |
| There is nothing to take with you from this section yet, and nothing is lost. | `95-studio.js:2403` | — |
| Where and when (field label) | `95-studio.js:2430` | — |
| Before dinner at our own table (placeholder) | `95-studio.js:2435` | — |
| One task, at most three steps, three to ten minutes. | `95-studio.js:2450` | — |
| It opens no chat and sends nothing anywhere. Printing and downloading are local. | `95-studio.js:2456` | — |
| Show me the task / Writing the task | `95-studio.js:2446` | — |
| This is the whole task. It stays in your notebook and on paper; it is not a chat. | `95-studio.js:2258` | — |
| The sheet is open in the print dialog. / This build cannot open a print dialog. | `95-studio.js:2473, 2749` | — |
| The sheet was saved as a file on this device. / This build cannot save a file. | `95-studio.js:2475, 2751` | — |
| The lesson for this section is not written yet, so there is no task to take with you. | `95-studio.js:2232` | — |

### The field card

| string | source | deck |
|---|---|---|
| Coursebook field card | `95-studio.js:1954` | — |
| One task | `95-studio.js:1964` | — |
| Where and when | `95-studio.js:2007` | — |
| Do this | `95-studio.js:2020` | — |
| Done when | `95-studio.js:2044` | — |
| Ticks for this card: {…} | `95-studio.js:2040` | — |
| Source · / Sources · / (accessed {date}) | `95-studio.js:2084, 2096` | — |
| {task title} | `$defs.homework_task.title` (`rpc.v24.json`) | — |
| {target.display} / {target.romaji} / {target.meaning} | `$defs.homework_task.target` | — |
| {steps[]} | `$defs.homework_task.steps` (max 3, 200 chars) | — |
| {success_criterion} | `$defs.homework_task.success_criterion` | — |
| {n} min | `95-studio.js:2695`, `homework_task.estimated_minutes` | — |

### Recording, skipping, saving

| string | source | deck |
|---|---|---|
| I did it | `95-studio.js:2486, 2723` | — |
| Not this one / Skip | `95-studio.js:2493, 2732` | — |
| Recording / Skipping | `95-studio.js:2486, 2493, 2720, 2732` | — |
| Only you record it. Nothing here is marked. | `95-studio.js:2497` | — |
| A parent recorded this | `95-studio.js:2722` | — |
| Recorded: you reported this done. A report, not a mark. | `95-studio.js:2283` | — |
| Recorded: a parent reported this done. A report, not a mark. | `95-studio.js:2282, 2603, 2604` | — |
| You recorded this as done…. A report, not a verdict. | `95-studio.js:1935` | — |
| A parent recorded this as done…. A report, not a verdict. | `95-studio.js:1933` | — |
| Done — I will record this myself. | `95-studio.js:1936` | — |
| Skipped. Nothing is owed, nothing is lost. | `95-studio.js:2305, 2607` | — |
| Skipped. Nothing is owed and nothing is lost. | `95-studio.js:1929` | — |
| This task closed without a report. | `95-studio.js:1931` | — |
| This one is closed as skipped. A fresh task can be taken with you from another lesson. | `95-studio.js:2506` | — |
| This task already carries a report; it cannot be reported twice. | `95-studio.js:2507` | — |
| Save to notebook / Saved to the notebook | `95-studio.js:2144` | — |
| Saved to the notebook. The task itself stays a homework task, not a note. | `95-studio.js:2329` | — |
| Local only. Nothing is sent. | `95-studio.js:2149` | — |
| Print the sheet / Download | `95-studio.js:2123, 2136` | — |
| Hide the sheet / Show the sheet | `95-studio.js:2711` | — |

### The notebook list and the Parent Studio list

| string | source | deck |
|---|---|---|
| Taken with you (notebook tab) | `desktop/src/90-course.js:928` | — |
| Homework taken with you (Parent Studio list) | `95-studio.js:2926` | — |
| No homework yet | `95-studio.js:2927` | — |
| Tasks a learner took with them from a lesson on this device. A parent can record one as done; it is a report, never a mark, and it opens no chat. | `95-studio.js:2913` | — |
| The course names could not be read. The tasks below are unchanged. | `95-studio.js:2916` | — |
| A lesson title could not be read. The task itself is unchanged. | `95-studio.js:2919` | — |
| Reading this task | `95-studio.js:2637` | — |
| This course | `95-studio.js:2701` | — |
| Homework needs the homework methods (+ body) | `95-studio.js:2886-2888` | — |

### Homework states

| state | what renders | deck |
|---|---|---|
| closed | `Take this with you` | — |
| loading | `Reading this lesson's task` | — |
| form | `Where and when` + placeholder + helper + `Show me the task` | — |
| proposed | the field card + `I did it` / `Not this one` / `Save to notebook` | — |
| reported | `Recorded: … A report, not a mark.` | — |
| skipped | `Skipped. Nothing is owed…` / `This one is closed as skipped…` | — |
| error | `The task could not be read.` + `Reason · {code}` + `Try again` | — |
| blocked (no lesson) | `The lesson for this section is not written yet…` | — |
| empty (list) | `No homework yet` | — |
| **offline** | **nothing in the source; no string exists** | — |

## Game (GM-010) — strings the shipped surface renders

| string | source | deck |
|---|---|---|
| Game (band accessible name) | `desktop/src/30-home.js:3803` | — |
| {n} XP | `30-home.js:3810` | `classroom.game.xp` (174) — **the only deck row this card can use** |
| Level {n} | `30-home.js:3846` | — |
| {level title} (fallback `Explorer`) | `30-home.js:3847`, `engagement.read.level.title` | — |
| · cosmetic | `30-home.js:3848` | — |
| Game progress | `30-home.js:3868, 3879`; `engagement.read.progress.label` is `const "Game progress"` | — |
| {done} of {assigned} steps / {done} of {assigned} step | `30-home.js:3871` | — |
| No steps assigned yet | `30-home.js:3872` | — |
| {pct}% (bar value) | `30-home.js:3895` | — |
| Play progress, not evidence. | `30-home.js:3719` | — |
| Lesson step / Check / Review / Homework done / Came back | `30-home.js:3707-3711`, labels for `recent_events[].action_kind` enum (`lesson_step`, `check_submitted`, `review`, `homework_completed`, `returned`) | — |
| Field journal | `30-home.js:3948, 3964` | — |
| {earned} of {cards} sections stamped by recorded evidence. | `30-home.js:3969` | — |
| No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page. | `30-home.js:3970` | — |
| Section {n} / Section | `30-home.js:4005` | — |
| {section title} (fallback `Untitled section`) | `30-home.js:3935`, `outline_objective.title` | — |
| Stamped / Not started | `30-home.js:4026` | — |
| Reading the field journal… | `30-home.js:3785` | — |
| The field journal could not be read: {error} Your course is unaffected. | `30-home.js:3768` | — |
| Try again | `30-home.js:3771` | — |
| Show Game feedback (settings switch) | `30-home.js:3567` area; measured label in `docs/visual-review/gm-010/MANIFEST.md` | — |

### Game states

| state | what renders | deck |
|---|---|---|
| ready | band (XP chip, level, progress bar) + field journal | — |
| loading | `Reading the field journal…` | — |
| error | `The field journal could not be read: …` + `Try again` | — |
| feedback off | band absent (`game: null`); no copy | — |
| no steps | `No steps assigned yet` | — |
| no stamps | `No section is stamped yet…` | — |
| **award** | no surface copy of its own: `engagement.award` returns points/level and the band updates | — |
| **completion** | **no completion sentence exists in the source**; completion is the stamp plus the band's progress | — |
| **offline** | **no string exists** | — |
| overflow | no copy; the band wraps | — |

## GAPS

- **GAP-23 — the deck has no homework section at all.** Every string in the tables above is
  unsourced. Two of them are load-bearing claims: the completion sentence ("A report, not a mark")
  and the sheet guarantee ("It opens no chat and sends nothing anywhere"). A maker restyling these
  surfaces must not paraphrase them, and has no row to cite.
- **GAP-24 — the deck has no Game section at all.** Only `classroom.game.xp` (174) exists, and it is
  written for the Classroom lesson chip. The Course-home band and the field journal have no rows,
  including the enum→label map (`lesson_step` → "Lesson step" etc.) that a rebuild will re-invent.
- **GAP-25 — no honest empty state for the two lists.** `homework.list` does not exist in cb.rpc v24
  (`docs/visual-review/gm-008/MANIFEST.md`, "Known gaps"); the notebook and Parent Studio lists
  enumerate through `homework.read` per known task. So "No homework yet" can be rendered when tasks
  exist but cannot be listed. The deck needs an "unavailable", not-empty state, and the card body
  needs to name which state wins. Also: there is no offline copy on either surface, which §3.12
  requires of every v3 screen.
- **GAP-26 — the card body is corrupted.** `cards/CP-025a.md` lines 38–56 are CP-021's body
  (Discover strings, the four-screen capture paragraph, CP-021's file-ownership block naming
  `96-workshop.js`). The real ownership block is at line 60. Repair before dispatch, or the maker
  works on Discover.

## What CP-025a needs before it can start

1. A `COPY.md` section for homework and one for the Game layer, with the strings above (or a v3
   re-wording of them) and a source form each.
2. A decision on the two lists' empty vs unavailable state (`GAP-25`).
3. A repaired card body (`GAP-26`).
4. v3 primitives for these surfaces, which CP-020b owns; any label that changes shape there is a
   CP-020c request, not an edit in this card.
