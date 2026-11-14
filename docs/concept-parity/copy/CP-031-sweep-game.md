# CP-031b — Game surface shipped-string sweep

Card: **CP-031b** (`t_adc9bdee`). Closes **GAP-30** for the Game surface: the play layer in
`desktop/src/30-home.js:4834-5215` (`CB_GAME_ACTION_WORD` through the end of the file) and the mode
words it shares with the shell (`desktop/src/00-header.js:238`, `CB_PRESENTATION_LABEL`). Docs only;
no product string changed. Row citations were re-derived on the strings at `475efefc`.

The card scoped the Game block by the line numbers of the revision it was cut at. At `475efefc` the
same surfaces are: the `ChildSafeLine` block (`30-home.js:4790`, mounted by `95-studio.js:631`),
which is **not** Game copy — its strings are rowed in `CP-031-sweep-parent-studio.md` §3.1 — and the
Game-visible block that starts at `CB_GAME_ACTION_WORD` (`4834`) and runs to the end of the file
(`5215`). No row is skipped silently.

**Two coverage claims in earlier cuts of this file were false, and are corrected here.** This sweep
used to say the home-route twin of the child-safe line (`30-home.js:4770`, `4775`) "belonged to"
`CP-022-home.md`, and that the objective-state words rendered on every journal card were
"inventoried in" `CP-022-home.md`. Neither is true: `CP-022-home.md` is a gap analysis of the Home
surface, not an inventory of `30-home.js`, and it contains no row for either block (checked by
reading the file, not by trusting the claim). Both are rowed below — §1a and §1c — and recorded as
**GAP-41** and **GAP-42**. A hand-off note to another inventory is only allowed when that inventory
actually carries the strings.

**Surface:** GM-010 Game mode — the header band, the journal of section cards, the objective-state
words each card renders, and the `Game`/`Guided`/`Textbook` mode words. `GAP-24` owns the section;
`GAP-25` owns the offline rows; the third mode word is a new gap (**GAP-36**) because it is not a
`world.read` value.

## 1. The game layer (`30-home.js:4834-5215`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Lesson step / Check / Review / Homework done / Came back (event words) | `30-home.js:4835`, `30-home.js:4838-4839` | default | `GAP-24 game.event.{lesson_step,check,review,homework,returned}` |
| Play progress, not evidence. | `30-home.js:4847` | default | `GAP-24 game.play_only` |
| The field journal could not be read: {error} Your course is unaffected. | `30-home.js:4924` | error | `GAP-24 game.error` |
| Try again | `30-home.js:190` | error | `GAP-24 game.retry` |
| Reading the field journal… | `30-home.js:4940` | loading | `GAP-24 game.loading` |
| Game (band accessible name) | `30-home.js:484` | default | `GAP-24 game.band.label` |
| {n} XP | `30-home.js:4974` | default | `GAP-24 game.xp` (`field:engagement.read.xp_total`) |
| Level {n} | `30-home.js:4982` | default | `GAP-24 game.level` (`field:engagement.read.level.level`) |
| {level title or “Explorer”} | `30-home.js:4983` | empty | `GAP-24 game.level_title` |
| · cosmetic | `30-home.js:4984` | default | `GAP-24 game.level_cosmetic` |
| {progress label or “Game progress”} | `30-home.js:5005`, `30-home.js:5016` | default | `GAP-24 game.progress` |
| {done} of {assigned} step / steps | `30-home.js:353` | default | `GAP-24 game.progress.steps` (`computed:progress_fraction`) |
| No steps assigned yet | `30-home.js:5009` | empty | `GAP-24 game.progress.none` |
| Field journal (heading) | `30-home.js:5090` | default | `GAP-24 game.journal.title` |
| Field journal (region accessible name) | `30-home.js:5090` | default | `GAP-24 game.journal.label` |
| {earned} of {total} sections stamped by recorded evidence. | `30-home.js:5119` | default | `GAP-24 game.journal.count` (`computed:count(objectives[].independent)` over `field:course.outline.objectives[].independent`) |
| No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page. | `30-home.js:5120` | empty | `GAP-24 game.journal.empty` |
| Section {n} / Section (card ordinal label) | `30-home.js:2964` | default / empty | `GAP-24 game.card.section` |
| Untitled section (card title fallback) | `30-home.js:5066` | empty | `GAP-24 game.card.untitled` |
| Stamped | `30-home.js:5192` | default | `GAP-24 game.journal.stamped` |
| Not started (card state fallback) | `00-header.js:65` | empty | `GAP-24 game.journal.not_started` |

## 1a. The Home defaults line the band sits under (`30-home.js:4739-4781`)

`HomeDefaultsLine` names the presentation default, a classroom override, the child-safe floor and
the session length on the Home route. It is not Game copy, and it is not Home-surface coverage that
exists elsewhere either: `CP-022-home.md` carries no inventory row at all (it is a gap analysis, and
it never cites `30-home.js:4739-4781`). Rowed here so CP-001 has the strings, flagged as **GAP-41**
for the Home section to own.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Default view · {mode} | `30-home.js:4751` | default | `GAP-41 home.defaults.mode` |
| {mode label} or “Game” (unknown-mode fallback) | `30-home.js:4752` | empty | `GAP-41 home.defaults.mode_fallback` |
| · This classroom · {mode} (only when the selected classroom overrides the default) | `30-home.js:4760` | default | `GAP-41 home.defaults.override` |
| · Child-safe defaults | `30-home.js:4770` | default | `GAP-41 home.defaults.child_safe` |
| · Session · {n} min | `30-home.js:4775` | default | `GAP-41 home.defaults.session` (`computed:session_minutes`) |

The child-safe and session fragments here are the short Home-route forms. The long form
("Child-safe defaults · no loss-framed reminders, no ranking, …") is a different component at
`30-home.js:4798` and is rowed in the studio sweep §3.1; the two do not share wording and must not be
collapsed into one id.

## 1c. The objective-state words every journal card renders (`00-header.js:64-75`, `30-home.js:5204`)

`CB_COPY.state` (`00-header.js:64-75`) is the enum→copy map over the objective evidence states, and
the Game card renders it directly through `CB_COPY.stateWord(card.state)` (`30-home.js:5204`). It had
no row in any deck file. **GAP-42** owns it; CP-001 authors it with
`GAP-24` because the card cannot render without it.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Not started / Started / Independent evidence / Delayed evidence / Review due / Could not be written / Moved on without a grade (objective-state words, in enum order) | `00-header.js:64-75` | default | `GAP-42 game.state.{not_started,introduced,independent_evidence,delayed_evidence,review_due,needs_review,overridden}` |
| Not started (fallback for a state outside the map) | `00-header.js:65` | empty | `GAP-24 game.journal.not_started` (already rowed in §1) |

## 2. The mode words (`00-header.js:89-200`)

`CB_PRESENTATION_LABEL` is `{ game: 'Game', guided: 'Guided', textbook: 'Textbook' }`
(`00-header.js:180`). Only two of the three are `world.read.presentation_mode` values; `guided` is
the device/create mode and has no deck row and no contract enum — that is **GAP-36**, not a
`GAP-27` row, because a `field:world.read.presentation_mode == guided` claim would be false.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Game / Textbook (durable-mode words) | `30-home.js:105` | default | `GAP-27 world.mode.game` / `world.mode.textbook` |
| Guided (presentation word with no contract enum) | `30-home.js:4657` | default | `GAP-36 game.mode.guided` |

`Guided` also appears as an autonomy option (`00-header.js:112`, `{ id: 'guided', label: 'Guided' }`);
that is a brief/create field, inventoried with the shell create form in `CP-031-sweep-chrome.md`.
The `Guided` presentation word itself is the new gap.

## 3. State coverage for this surface

| state | what renders | deck |
|---|---|---|
| default | band, XP chip, level chip, progress bar, journal cards (section 1), each card's objective-state word (§1c) | GAP-24, GAP-42 |
| loading | `Reading the field journal…` (`30-home.js:3785`) | GAP-24 |
| empty | `No steps assigned yet`, `No section is stamped yet…`, `Untitled section`, `Section`, `Not started` (unknown state, §1c) | GAP-24 |
| error | `The field journal could not be read…` + `Try again` | GAP-24 |
| offline | **no string.** The Game band does not read `useOnline()`; an offline `engagement.read` renders the error line, which names the read rather than the connection. | GAP-25 |
| overflow | **no string.** The band wraps (`30-home.js:3749-3758`) and the journal is capped at 12 cards (`3933`); nothing states that the rest exist. | GAP-35 |
| dialog | none — the play layer opens nothing. | — |

## 4. What CP-031's sample missed (delta for CP-001)

`CP-025a-homework-game.md` sampled the Game band but not the journal. This sweep adds: the five
event words as an explicit map with its enum (`30-home.js:3706-3712`), the journal's counted and
empty states (`3969-3970`), the card state words (`4005, 4026`), the `· cosmetic` qualifier
(`3848`), the XP `{n} XP` shape (`3827`), and the untitled fallbacks. It also separates `Guided` from
the world enum instead of folding it into `GAP-27`.

Round 4 of this sweep's own review corrected two hand-off notes that were false, and rowed what they
had displaced: the Home defaults line (§1a, five strings, **GAP-41**) and the seven objective-state
words of `DESK_STATE_WORD` that every journal card renders (§1c, **GAP-42**). Both blocks had no row
in any deck file, and the note that said otherwise is now gone.

## 5. Row count

§1 carries 21 rows, §1a five and §1c two: **28 inventory rows** for `30-home.js`, plus the two mode
rows in §2. Excluded by class: `data-cb-*` values, RPC method names, CSS strings, ids.
