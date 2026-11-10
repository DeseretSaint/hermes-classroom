# GAPS — every string with no copy-deck row

Card: **CP-031**. This file is a **request to CP-001**, not approved copy. Nothing here may be
implemented until it lands in `docs/concept-parity/COPY.md`; the deck's own rule is that a screen may
not render text with no row (`COPY.md:3-4`).

Each entry names: what the card body or spec asks for, why no row covers it, the proposed row, and
the card that needs it. Rows marked **decision** are not mine to word — they need the owner
(`atlas`) or the deck owner (`CP-001`).

Proposed ids follow the existing `<surface>.<part>` convention. Caps follow the deck's column.

---

## Shell (needed by every screen)

### GAP-01 — the Home settings sheet

SPEC line 320 makes the sheet part of Home. The deck has only the entry label `home.settings` (67).
The shipped sheet renders (`desktop/src/30-home.js:3319, 3343, 3484, 3547, 3508, 3515, 143`):

| proposed id | text | source | cap |
|---|---|---|---|
| `home.settings.appearance` | Appearance | deck | 16 |
| `home.settings.default_view` | Default view | deck | 16 |
| `home.settings.sound` | Sound | deck | 12 |
| `home.settings.reduced_motion` | Reduced motion | deck | 20 |
| `home.settings.companion` | Study companion | deck | 20 |
| `home.settings.companion.show` | Show my study companion | deck | 28 |
| `home.settings.scope` | On this device | deck | 20 |

Needed by: CP-022, CP-020a (the sheet's own restyle).

### GAP-02 — the companion's visible name

SPEC §3.8 requires adjacent visible text; the canvas is `aria-hidden`.

| proposed id | text | source | cap |
|---|---|---|---|
| `companion.line` | {name} · study companion | deck + `pet.info.displayName` | 48 |
| `companion.none` | Your study companion | deck | 24 |

Needed by: CP-022 (trailhead), CP-023 (path stop, lesson close), CP-024 (beside Continue).
When the host has no pet the companion is hidden, so `companion.none` is only the fallback name,
never a placeholder face.

---

## CP-022 — Home

### GAP-03 — the shelf card title

| proposed id | text | source | cap |
|---|---|---|---|
| `home.card.title` | {course title} | `field:library_item.title` | 60 |

Needed by: CP-022. Without it a maker either invents the card's largest string or cites
`course.title`, which is a different surface's row.

### GAP-04 — "See all"

CP-022 line 39 asks for `See all` when more than four courses exist. SPEC line 388 gives overflow's
one next action as "scroll or `Browse library`", and a fifth control in H5 risks the duplicate-CTA
gate. **Decision.**

- Recommended: **no new row.** Drop "See all" from the body; keep `home.overflow.hint` (77) and
  `home.secondary` "Browse library" (66).
- If the owner keeps it: `home.overflow.action` = "See all", deck, cap 12, quiet, opens Courses.

### GAP-05 — the paper tag rule

Three rules exist: deck `home.tag.firstuse` = "New course", first use only (73); SPEC line 401 says
the tag "exists only in first-use and is not a second create control"; CP-022 lines 40–42 say
"New: {title of the most recently created course}", opening that course, under 14 days and no
attempts; PLAN O5 (line 940) recommends the CP-022 rule. **Decision — owner.**

- If the spec stands: no new row; correct CP-022's body.
- If O5 stands: `home.tag.recent` = "New: {course title}", deck + `field:library_item.title`, cap 40,
  and SPEC §5.1 line 401 and §6 must be amended with it.

### GAP-06 — body wording (not a new row)

CP-022 line 35 "Choose a course or start a new expedition." → `home.sub` (64).
CP-022 line 36 "Start a new course" → `home.primary` (65).
No deck change; correct the body before dispatch.

---

## CP-021 — Discover / Workshop

### GAP-07 — the pack card title

| proposed id | text | source | cap |
|---|---|---|---|
| `discover.card.title` | {pack title} | `field:pack.inspect.manifest.title` | 40 |

**The source is the problem, not just the row.** `pack.list.items[]` (`$defs.pack_list_item`,
`contracts/rpc.v24.json`) has no `title`: the list carries `pack_id`, `pack_version`, `source`,
`state`, `recipe`, `license`, `file_count`, `content_hash`, `installed_at`. Rendering a titled grid
therefore needs one `pack.inspect` per card, or a contract addition. **Decision:** CP-001 accepts the
N+1 read, or a CP-005-style forward field `library_item`-equivalent for packs (e.g.
`pack_list_item.title`) is requested from the backend owner.

### GAP-08 / GAP-09 / GAP-10 — body wording (not new rows)

- Line 35 "Discover your next world" → `discover.title` "Discover" (95, cap 16). Correct the body.
- Lines 35–36 "and outcome" → `discover.feature.body` is `pack.inspect.manifest.subtitle` (101). No
  field named outcome exists in `pack-manifest.v2.json`. Correct the body.
- Line 37 "`Preview`" → `discover.feature.primary` "Preview this pack" (102). Correct the body.

---

## CP-023 — Classroom (the worst screen)

### GAP-11 — the stepper node label

| proposed id | text | source | cap |
|---|---|---|---|
| `classroom.step.label` | {section title} | `field:course.outline.objectives[].title` | 40 |

Shared shape with `GAP-19`. Needed by CP-023 and CP-024; CP-001 should name it once and let both
surfaces cite the same row, or add `course.route.node.label` for the map and keep this one local.

### GAP-12 / GAP-13 / GAP-14 — the choice surface words (SPEC line 501)

| proposed id | text | source | cap |
|---|---|---|---|
| `classroom.check.answer_label` | Your answer | deck | 16 |
| `classroom.check.selected` | Selected | deck | 12 |
| `classroom.check.selection_summary` | Selected: {n}. {choice} | `computed` over the picked index + `check.get.stimulus.choices[]` | 60 |
| `classroom.check.selection_none` | Nothing selected yet. | deck | 24 |

### GAP-15 — the answer-region helper lines (SPEC lines 500, 502)

Three rows, one per format. **Decision — deck owner writes the sentence;** a placeholder here would
be the invented copy this card exists to prevent.

| proposed id | format | source | cap |
|---|---|---|---|
| `classroom.check.help.text` | written answer | deck | 60 |
| `classroom.check.help.selection` | choice | deck | 60 |
| `classroom.check.help.verification` | checklist | deck | 60 |

### GAP-16 — the level line

| proposed id | text | source | cap |
|---|---|---|---|
| `classroom.game.level` | {level title} · level {n} | `field:engagement.read.level.title` + `engagement.read.level.level` | 32 |

Shipped v2 reads `Level 1 · Curious · cosmetic` (`desktop/src/30-home.js:3846-3848`). The deck says
XP is "cosmetic" only in the token/`is_cosmetic` field; if the word "cosmetic" is kept it needs its
own row. Needed by CP-023 (Challenge card) and CP-025a (Game band).

### GAP-17 — the evidence-integrity words

| proposed id | text | source | cap |
|---|---|---|---|
| `classroom.evidence.first` | First try, no hints | `field:lesson.page.attempts[].evidence_class` == `independent` | 24 |
| `classroom.evidence.hinted` | Hinted | … == `hinted` | 12 |
| `classroom.evidence.shown` | Answer shown — no longer independent | … == `answer_shown` | 48 |

These are the product's integrity claim (`docs/EXPERIENCE-QUALITY-BAR.md`, and CP-023 lines 45–46).
The enum values are `attempt_summary.evidence_class` and `evidence_event.evidence_class`.
**CP-001 must confirm the enum names** before the rows are written; a row keyed to a guessed enum is
worse than a gap.

### GAP-18 — body contradiction (not a new row)

CP-023 line 40 "choosing an option is the one primary action" contradicts SPEC §3.10 line 290 and
§5.3 line 465 (`Check answer` is the one primary) and the deck (148). Correct the body.

---

## CP-024 — Course home

### GAP-19 — the route node label

| proposed id | text | source | cap |
|---|---|---|---|
| `course.node.label` | {section title} | `field:course.outline.objectives[].title` | 60 |

### GAP-20 — "Field Notes" in the aside

CP-024 line 38 asks for "Field Notes and course shelf as the aside". SPEC M7/M8 are evidence and
other courses; the shipped strip renders `Field Notes` and `All field notes`
(`desktop/src/30-home.js:2984, 2997`). **Decision:** follow the spec (no row; correct the body) or
amend SPEC §5.4 and add:

| proposed id | text | source | cap |
|---|---|---|---|
| `course.notes.title` | Field Notes | deck | 16 |
| `course.notes.action` | All field notes | deck | 20 |

### GAP-21 — body contradiction (not a new row)

CP-024 line 38 "One primary `Continue`" contradicts SPEC line 545 and §3.10 line 291: the primary is
the backend's `library_item.next_step.label` on the filled plate; `course.continue.title` is a
heading. Correct the body.

### GAP-22 — the missing offline state

| proposed id | text | source | cap |
|---|---|---|---|
| `course.offline.title` | You are offline | deck | 20 |
| `course.offline.body` | The route you opened last is still here. Saving waits. | deck | 60 |
| `course.offline.action` | Try again | deck | 12 |

Required by SPEC §3.12 line 325. The body text is a **decision** — it must match the pattern the
three shipped offline rows use (`home.offline.body` 86, `discover.offline.body` 118,
`classroom.offline.body` 172) and state what is preserved.

---

## CP-025a — Homework and Game

### GAP-23 — no homework section

The full source inventory is `CP-025a-homework-game.md`. CP-001 needs a `hw.*` section covering the
action, the sheet, the field card, the four completion sentences and the two lists. The
**load-bearing rows** (a restyle must not paraphrase them) are:

| proposed id | text (as shipped) | source | cap |
|---|---|---|---|
| `hw.action` | Take this with you | deck | 20 |
| `hw.sheet.note` | This is the whole task. It stays in your notebook and on paper; it is not a chat. | deck | 100 |
| `hw.sheet.local` | It opens no chat and sends nothing anywhere. Printing and downloading are local. | deck | 90 |
| `hw.card.where` | Where and when | deck | 16 |
| `hw.card.do` | Do this | deck | 12 |
| `hw.card.done_when` | Done when | deck | 12 |
| `hw.card.source` | Source · / Sources · | deck | 12 |
| `hw.record.done` | I did it | deck | 12 |
| `hw.record.skip` | Not this one | deck | 16 |
| `hw.record.only` | Only you record it. Nothing here is marked. | deck | 44 |
| `hw.completion.learner` | Recorded: you reported this done. A report, not a mark. | deck | 60 |
| `hw.completion.parent` | Recorded: a parent reported this done. A report, not a mark. | deck | 60 |
| `hw.completion.skipped` | Skipped. Nothing is owed, nothing is lost. | deck | 48 |
| `hw.notebook.tab` | Taken with you | deck | 16 |
| `hw.list.title` | Homework taken with you | deck | 28 |
| `hw.list.empty` | No homework yet | deck | 20 |

(+ the form, print, save and studio-record rows in the inventory table; CP-001 should take the whole
table, not only this subset.)

### GAP-24 — no Game section

| proposed id | text | source | cap |
|---|---|---|---|
| `game.band.label` | Game | deck | 8 |
| `game.level` | {level title} · level {n} | `engagement.read.level` | 32 |
| `game.progress` | Game progress | `engagement.read.progress.label` (const) | 16 |
| `game.progress.steps` | {done} of {assigned} steps | `computed` over `progress.completed_steps` / `assigned_steps` | 24 |
| `game.progress.none` | No steps assigned yet | deck | 24 |
| `game.play_only` | Play progress, not evidence. | deck | 28 |
| `game.event.lesson_step` | Lesson step | deck | 14 |
| `game.event.check` | Check | deck | 8 |
| `game.event.review` | Review | deck | 8 |
| `game.event.homework` | Homework done | deck | 16 |
| `game.event.returned` | Came back | deck | 12 |
| `game.journal.title` | Field journal | deck | 16 |
| `game.journal.count` | {earned} of {total} sections stamped by recorded evidence. | `computed` over `course.outline.objectives[].independent` | 60 |
| `game.journal.empty` | No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page. | deck | 100 |
| `game.journal.stamped` | Stamped / `game.journal.not_started` Not started | deck | 8 |

The five `game.event.*` rows map the `recent_events[].action_kind` enum (`lesson_step`,
`check_submitted`, `review`, `homework_completed`, `returned`) — an enum→copy map with no row today.

### GAP-25 — empty vs unavailable, and no offline copy

`homework.list` does not exist in cb.rpc v24, so "No homework yet" can appear while tasks exist.
**Decision:** add `hw.list.unavailable` ("Homework cannot be listed right now." deck, cap 40) and
name which state wins, plus `hw.offline.*` / `game.offline.*` rows for §3.12.

### GAP-26 — card body corruption

`cards/CP-025a.md` lines 38–56 are CP-021's body. Repair before dispatch. Not a copy row; a manager
edit (`hermes kanban edit`).

---

## CP-025b — World Studio and Parent Studio

### GAP-27 — no World Studio section

Full inventory: `CP-025b-studio.md`. Minimum load-bearing rows:

| proposed id | text (as shipped) | source | cap |
|---|---|---|---|
| `world.mode.game` / `world.mode.textbook` | Game / Textbook | `course.mode` read | 12 |
| `world.open_studio` | Open World Studio | deck | 20 |
| `world.review` | Review the world | deck | 20 |
| `world.not_approved` | This course reads as Textbook until its world is approved. Your lessons and plan are unchanged. | deck | 100 |
| `world.unavailable` | Game mode is unavailable because image generation is not configured. | deck | 80 |
| `world.unavailable.keep` | Keep Textbook | deck | 16 |
| `world.no_fake` | The course stays in Textbook mode and your lessons are unchanged. No fake world is created. | deck | 100 |
| `world.missing_plates` | Some plates are missing | deck | 24 |
| `world.missing_plates.body` | Nothing is approved until every role exists, and no placeholder art is saved. | deck | 90 |
| `world.job_failed` | The world job did not finish. | deck | 32 |
| `world.direction.mood` etc. | Mood / Who it is for / Motifs to include / Motifs to avoid | deck | 20 |

The eight world archetype names and descriptions (`97-world.js:27-45`) are a fixed enum→prose map and
need their own table; CP-001 owns that wording, because the descriptions make a claim about what the
art is.

### GAP-28 — no Parent Studio section

| proposed id | text (as shipped) | source | cap |
|---|---|---|---|
| `studio.title` | Parent Studio | deck | 16 |
| `studio.lead` | Plans for your child | deck | 24 |
| `studio.caption` | Prepare a lesson for a child. Each brief you write is kept as its own plan, so you can compare versions without losing the first. | deck | 140 |
| `studio.primary` | New lesson plan | deck | 20 |
| `studio.entrance.plans` | My lesson plans | deck | 20 |
| `studio.entrance.takehome` | Take-home from a lesson | deck | 28 |
| `studio.entrance.homework` | Homework | deck | 12 |
| `studio.child_safe` | Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no XP or streaks | deck | 100 |
| `studio.child_chat` | No child account and no child chat: the adult prepares and prints. | deck | 64 |
| `studio.session` | · Session · {n} min | `computed` | 24 |
| `studio.page.cover` / `.parent_guide` / `.learner_page` / `.answer_guide` | Cover / Parent guide / Learner page / Answer guide | deck | 16 |
| `studio.page.answer_back` | Parent only. Keep this page back. | deck | 32 |
| `studio.pack.draft` / `.approved` / `.exported` / `.superseded` | Draft / Approved / Exported / Superseded | `takehome.read.state` | 12 |
| `studio.pack.approve_hint` | Approve the exact pages above before exporting. | deck | 48 |

(+ the take-home preview, export and source-picker rows in the inventory table.)

### GAP-29 — card body corruption

`cards/CP-025b.md` lines 37–55 are CP-021's body. Repair before dispatch.

---

## Amendment order (what unblocks what)

1. `GAP-01`, `GAP-02` — shell. Needed by every screen; do first.
2. `GAP-03`, `GAP-07`, `GAP-11`, `GAP-19` — the four missing card/node titles, and the one pack-title
   source decision in `GAP-07`.
3. `GAP-12`–`GAP-17` — the Classroom answer surface and integrity words; CP-023 cannot ship without
   them.
4. `GAP-22` — the missing offline state; one row set, three strings.
5. `GAP-23`, `GAP-24`, `GAP-27`, `GAP-28` — the two missing deck sections; CP-025a and CP-025b stay
   blocked until these land.
6. Body corrections and card-body repairs (`GAP-06`, `GAP-08`–`GAP-10`, `GAP-18`, `GAP-21`,
   `GAP-26`, `GAP-29`) are `hermes kanban edit` work on the card bodies, not deck work.

Owner decisions required (not wordable by the deck author alone): `GAP-04`, `GAP-05`, `GAP-07`
(source), `GAP-15` (three sentences), `GAP-17` (enum names), `GAP-20`, `GAP-22` (body text),
`GAP-25` (empty vs unavailable).
