# GAPS — every string with no copy-deck row

Card: **CP-031**. This file is a **request to CP-001**, not approved copy. Nothing here may be
implemented until it lands in `docs/concept-parity/COPY.md`; the deck's own rule is that a screen may
not render text with no row (`COPY.md:3-4`).

Each entry names: what the card body or spec asks for, why no row covers it, the proposed row, and
the card that needs it. Rows marked **decision** are not mine to word — they need the owner
(`atlas`) or the deck owner (`CP-001`).

**Inventory revision (CP-031d, card `t_d20f3f5e`, re-deriving CP-031c-R `t_54a44039`):** every
sweep row and every line citation in this file is re-derived from `origin/master` at
**`14fb14f3e8c5306f973bf98ba270140ca98f0ac5`**. The line numbers below are that revision's. The gate
in `tests/test_cp_copy_inventory.py` keys its
required rows on `(file, exact string)`, so a required row is located in the shipped file at test
time instead of being trusted to a stored line number; it also re-extracts the literal population
from the five segment files, so a re-authored file fails the gate instead of quietly rotating the
citations.

The swept revision is pinned on **content**, not only on a commit id: `00-header.js` `ab62cbd7`,
`30-home.js` `9877b940`, `90-course.js` `a47e7fe2`, `95-studio.js` `77d8b2ec`, `97-world.js`
`00d46dcf`. `test_the_swept_sha_still_describes_master` compares each of those five blobs at the
swept sha and at `origin/master`: master moving without touching them is harmless, and master
moving one of them fails the gate naming the file, so the next author re-sweeps rather than
rotating citations. CP-031c swept the same five files at `5d2b303e`; CP-031c-R re-derived that
row set at `a11bc0e4`; CP-031d re-derived it again at `14fb14f3`, where `95-studio.js` had moved
by exactly one literal (`plan change`, `95-studio.js:4666`) and no row total changed. The two
literals CP-031c re-worded are listed at the end of `CP-031-sweep-parent-studio.md`.

Proposed ids follow the existing `<surface>.<part>` convention. Caps follow the deck's column.
A `source` cell is written in the deck's own grammar — `deck`, `field:`, `computed:`, `pack:`,
`art:` or `host:` — and `tests/test_cp_copy_inventory.py` resolves every `field:` path against the
frozen contracts and every `== <value>` predicate against its enum.

---

## Shell (needed by every screen)

### GAP-01 — the Home settings sheet

SPEC line 320 makes the sheet part of Home. The deck has only the entry label `home.settings` (67).
The shipped sheet renders (`desktop/src/30-home.js:4221-4649`):

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
| `companion.line` | {name} · study companion | deck + `host:pet.info.displayName` | 48 |
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
| `classroom.check.selection_summary` | Selected: {n}. {choice} | `computed:selection_summary` over `field:check.get.stimulus.choices[]` | 60 |
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
| `classroom.game.level` | {level title} · level {n} | `field:engagement.read.level.title` + `field:engagement.read.level.level` | 32 |

Shipped v2 reads `Level 1 · Curious · cosmetic` (`desktop/src/30-home.js:4978-4984`). The deck says
XP is "cosmetic" only in the token/`is_cosmetic` field; if the word "cosmetic" is kept it needs its
own row. Needed by CP-023 (Challenge card) and CP-025a (Game band).

### GAP-17 — the evidence-integrity words

`lesson.page.attempts[]` is `$defs.attempt_summary`, whose `evidence_class` is
`contracts/vocabulary.v1.json:20`:

```
cold | hinted | answer_shown | self_reported | parent_reported | override
```

The vocabulary's own rule is that **only `cold` counts as independent evidence** and `override`
grants access, never mastery. `lesson.page.response.attempts[]` items are `$defs.attempt_summary`
(`contracts/rpc.v24.json:2451-2456`), so the value path is that definition's `evidence_class`.
All six values can reach a Classroom attempt row, so all six need a row — the first three from
`docs/EXPERIENCE-QUALITY-BAR.md`, the last three marked **decision** because the honesty claim
must not be worded by a maker.

| proposed id | text | source | cap |
|---|---|---|---|
| `classroom.evidence.first` | First try, no hints | `field:attempt_summary.evidence_class` == `cold` | 24 |
| `classroom.evidence.hinted` | Hinted | `field:attempt_summary.evidence_class` == `hinted` | 12 |
| `classroom.evidence.shown` | Answer shown — no longer independent | `field:attempt_summary.evidence_class` == `answer_shown` | 48 |
| `classroom.evidence.reported` | Self-reported — not an independent check | `field:attempt_summary.evidence_class` == `self_reported` | 48 |
| `classroom.evidence.parent` | Reported by a parent — a report, not a mark | `field:attempt_summary.evidence_class` == `parent_reported` | 52 |
| `classroom.evidence.overridden` | Opened by an override — no evidence recorded | `field:attempt_summary.evidence_class` == `override` | 52 |

These are the product's integrity claim (`docs/EXPERIENCE-QUALITY-BAR.md`, and CP-023 lines 45–46).
A surface that receives one of the last three must never render it as `cold`; if CP-001 declines
the three proposals, they become a **blocked** gap for CP-023, not an implicit fallback.

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
(`desktop/src/30-home.js:3938, 3951`). **Decision:** follow the spec (no row; correct the body) or
amend SPEC §5.4 and add:

| proposed id | text | source | cap |
|---|---|---|---|
| `course.notes.title` | Field Notes | deck | 16 |
| `course.notes.action` | All field notes | deck | 20 |

### GAP-21 — a hard-code rule, not a body defect (no new row)

CP-024 line 38 says "One primary `Continue`". SPEC line 545 and §3.10 line 291 say the primary is
the backend's `library_item.next_step.label` on the filled plate, and SPEC's own default next action
is written `Continue <section>` (the backend's own label) — so a plate that reads "Continue" is not
a contradiction. The defect only appears if a maker **hard-codes** the word `Continue` instead of
rendering `course.next.label` (`field:library_item.next_step.label`, 202): a learner whose backend
offers "Resume section 3" would lose the real next step. No deck change; the maker must not
hard-code the label.

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

**The notebook row's own family** (`desktop/src/90-course.js:950-1215`, swept as §1b of
`CP-031-sweep-homework.md`): `hw.notebook.action.{open,media,edit,remove}`, the technical-detail lines
`hw.notebook.detail.{summary,section,kind,source,tags,saved_at}`, the edit form
`hw.notebook.edit.{note_label,tags_label,save,cancel}`, and the only dialog on the surface
`hw.notebook.remove_{title,body,confirm}`. The card's `883-1003` slice excluded this block; it renders
directly under the list. `hw.notebook.search_label` / `.search_placeholder` (`950`, `953`) are the
same exclusion on the other side of the slice. These ids belong to `GAP-23` — a Homework section
authored without them would ship a list whose buttons have no deck words.

### GAP-24 — no Game section

| proposed id | text | source | cap |
|---|---|---|---|
| `game.band.label` | Game | deck | 8 |
| `game.level` | {level title} · level {n} | `field:engagement.read.level` | 32 |
| `game.progress` | Game progress | `field:engagement.read.progress.label` | 16 |
| `game.progress.steps` | {done} of {assigned} steps | `computed:progress_fraction` over `field:engagement.read.progress.completed_steps` + `field:engagement.read.progress.assigned_steps` | 24 |
| `game.progress.none` | No steps assigned yet | deck | 24 |
| `game.play_only` | Play progress, not evidence. | deck | 28 |
| `game.event.lesson_step` | Lesson step | deck | 14 |
| `game.event.check` | Check | deck | 8 |
| `game.event.review` | Review | deck | 8 |
| `game.event.homework` | Homework done | deck | 16 |
| `game.event.returned` | Came back | deck | 12 |
| `game.journal.title` | Field journal | deck | 16 |
| `game.journal.count` | {earned} of {total} sections stamped by recorded evidence. | `computed:count(objectives[].independent)` over `field:course.outline.objectives[].independent` | 60 |
| `game.journal.empty` | No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page. | deck | 100 |
| `game.journal.stamped` | Stamped | deck | 8 |
| `game.journal.not_started` | Not started | deck | 12 |

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
| `world.mode.game` | Game | `field:world.read.presentation_mode` == `game` | 12 |
| `world.mode.textbook` | Textbook | `field:world.read.presentation_mode` == `textbook` | 12 |
| `world.open_studio` | Open World Studio | deck | 20 |
| `world.review` | Review the world | deck | 20 |
| `world.not_approved` | This course reads as Textbook until its world is approved. Your lessons and plan are unchanged. | deck | 100 |
| `world.unavailable` | Game mode is unavailable because image generation is not configured. | deck | 80 |
| `world.unavailable.keep` | Keep Textbook | deck | 16 |
| `world.no_fake` | The course stays in Textbook mode and your lessons are unchanged. No fake world is created. | deck | 100 |
| `world.missing_plates` | Some plates are missing | deck | 24 |
| `world.missing_plates.body` | Nothing is approved until every role exists, and no placeholder art is saved. | deck | 90 |
| `world.job_failed` | The world job did not finish. | deck | 32 |
| `world.direction.mood` | Mood | deck | 20 |
| `world.direction.audience` | Who it is for | deck | 20 |
| `world.direction.include` | Motifs to include | deck | 20 |
| `world.direction.avoid` | Motifs to avoid | deck | 20 |

The eight world archetype names and descriptions (`97-world.js:27-45``) are a fixed enum→prose map and
need their own table; CP-001 owns that wording, because the descriptions make a claim about what the
art is.

`world.read.presentation_mode` is the read; `course.mode.set` is the setter and is never a render
source. A stored NULL reads as Textbook (`world.read` response description, `contracts/rpc.v24.json`).

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
| `studio.operator` | You are the operator: Coursebook prepares the material for you to teach, and there is no child chat, no child persona and no grading of the child. | deck | 160 |
| `studio.session` | · Session · {n} min | `computed:session_minutes` | 24 |
| `studio.view` | Studio view | deck | 16 |
| `studio.view.brief` | Brief | deck | 12 |
| `studio.view.plan` | Plan | deck | 12 |
| `studio.view.pages` | Pages | deck | 12 |
| `studio.view.export` | Export | deck | 12 |
| `studio.view.reflection` | Reflection | deck | 12 |
| `studio.all_courses` | All parent courses | deck | 20 |
| `studio.preparation` | Parent preparation | deck | 20 |
| `studio.export_ready` | Export ready | deck | 16 |
| `studio.parent_view` | Parent view · what your child did and what you observed, never points, levels or rankings. | deck | 110 |
| `studio.revision` | You are the operator · revision {n} | `computed:revision` | 40 |
| `studio.page.cover` | Cover | deck | 16 |
| `studio.page.parent_guide` | Parent guide | deck | 16 |
| `studio.page.learner_page` | Learner page | deck | 16 |
| `studio.page.answer_guide` | Answer guide | deck | 16 |
| `studio.page.answer_back` | Parent only. Keep this page back. | deck | 32 |
| `studio.approve` | Approve these pages | deck | 24 |
| `studio.approve_hint` | Approve the exact pages above before exporting. | deck | 48 |
| `studio.export_pdf` | Export the print-ready PDF | deck | 32 |
| `studio.save_draft` | Save this draft | deck | 20 |
| `studio.previewed` | Previewed pages: {n} · preview hash: {hash} | `computed:preview_summary` | 80 |
| `studio.pack.draft` | Draft | `field:takehome.read.pack.state` == `draft` | 12 |
| `studio.pack.previewed` | Previewed | `field:takehome.read.pack.state` == `previewed` | 12 |
| `studio.pack.approved` | Approved | `field:takehome.read.pack.state` == `approved` | 12 |
| `studio.pack.exported` | Exported | `field:takehome.read.pack.state` == `exported` | 12 |
| `studio.pack.superseded` | Superseded | `field:takehome.read.pack.state` == `superseded` | 12 |
| `studio.refusal.pack_not_approved` | The plan is not approved. | deck | 40 |
| `studio.refusal.course_pack_backed` | This course came from an imported pack. Use Library → Export pack for it. | deck | 80 |
| `studio.refusal.minima` | The generated lessons do not meet the pack's teaching minima yet. | deck | 80 |
| `studio.refusal.write_failed` | The files could not be written. Nothing was exported. | deck | 60 |
| `studio.print_font` | The print font cannot draw every character in this lesson, so no PDF was written. Nothing was corrupted. | deck | 120 |
| `studio.leave.title` | Unsaved section changes | deck | 24 |
| `studio.leave.body` | The section editor has unsaved changes. Leaving discards them and leaves storage exactly as it is now. | deck | 120 |
| `studio.leave.discard` | Discard and leave | deck | 20 |
| `studio.leave.keep` | Keep editing | deck | 16 |

(+ the take-home preview, export, source-picker and detail-chrome rows in the inventory table.)

### GAP-29 — card body corruption

`cards/CP-025b.md` lines 37–55 are CP-021's body. Repair before dispatch.

### GAP-30 — the shipped-string inventories are a partial sample — **CLOSED** by CP-031b, re-derived by CP-031c

`CP-025a-homework-game.md` and `CP-025b-studio.md` cite the visible strings of the v2 surfaces they
replace, but a literal-by-literal sweep was outstanding. **CP-031b (`t_adc9bdee`) performed it**;
**CP-031c (`t_0458a135`) re-derived it whole-file at `5d2b303e`, and CP-031c-R (`t_54a44039`)
re-swept and re-anchored it at `a11bc0e4`, and CP-031d (`t_d20f3f5e`) re-derived it at
`14fb14f3`.** The complete inventories are:

| file | in-scope source | rows |
|---|---|---|
| `CP-031-sweep-chrome.md` | `desktop/src/00-header.js` (all 1214 lines; rail, route title, learner vocabulary, create form, settings sheet, tutor path, shell errors) | 52 |
| `CP-031-sweep-homework.md` | `desktop/src/90-course.js` (all 5496 lines; the whole `NotebookView` plus the classroom, textbook, quiz, plan, evidence and export surfaces) | 331 |
| `CP-031-sweep-game.md` | `desktop/src/30-home.js` (all 5215 lines; Home shelf, the defaults line, `ChildSafeLine`, the Game band, its play layer and the field journal) | 216 |
| `CP-031-sweep-parent-studio.md` | `desktop/src/95-studio.js` (all 7934 lines; Parent Studio, the plan shape and outline repair, the fine-tune block, the take-home pack and the homework surface hosted in the same file; §3.1 rows the Home twin of `ChildSafeLine` in `30-home.js`) | 647 |
| `CP-031-sweep-world.md` | `desktop/src/97-world.js` (all 1135 lines) | 92 |

Each sweep is generated from a literal lexer and covers the **whole** file, not a slice. The
population is every multi-word user-facing literal: strings outside comments and regex literals,
with two or more whitespace-separated tokens and at least two word tokens, after dropping CSS
class lists/declarations/grid templates/lengths/colours, dotted method and field names, paths,
URLs, MIME types, `SCREAMING_SNAKE` codes and code fragments. Template-literal `${…}` expressions
are normalised to `{…}`. The only allowlist entries are `noreferrer noopener` and
`noopener noreferrer`. Single-word controls are outside this multi-word gate; the ones that carry
state are named in the gap tables below.

`tests/test_cp_copy_inventory.py` proves the closure in both directions: it re-extracts the
population from each segment file at test time and fails with the missing set if any literal has no
row, and it checks that every row cites a line that actually carries its words. The tables in
`CP-025a-homework-game.md` and `CP-025b-studio.md` stay as the **sample** they are; neither is the
complete source, and both now point here. The sweep also closes the scope decision: a full sweep was
funded, so CP-001 authors `hw.*` / `game.*` / `world.*` / `studio.*` from the sweep files, not from
the samples. **No string was changed by the sweep.**

The sweep found twelve categories the samples had no gap for at all: `GAP-31` (homework enum maps and
sheet guards), `GAP-32` (plan-validation independence words), `GAP-33` (fine-tune editor, second
dialog and regenerate preflight), `GAP-34` (the export gate and its formats), `GAP-35` (offline and
overflow), `GAP-36` (the `Guided` presentation word), plus `GAP-37` (the create-form vocabulary that
neither sample owned), `GAP-38` (the approval-invalidation banner and the plan-check reason labels),
`GAP-39` (the shell's contract-envelope error and the `describeError()` fallback behind every failed
read), `GAP-40` (the classroom tutor path the chrome sweep used to say CP-023 carried), `GAP-41` (the
Home defaults line a sweep note wrongly assigned to `CP-022-home.md`) and `GAP-42` (the
objective-state words every Game card renders, likewise wrongly assigned). The last five were added
when review of this sweep's own cuts — and, for the last two, a re-lex before the fifth review —
found strings the sweep had displaced rather than rowed. The figure is a record of what a complete
sweep finds, not of what one pass found.

Two rules are worth stating because each round found the same defect: **a "belongs to another
inventory" note is only allowed after that inventory has been read and found to carry the
strings**, and **a row may only cite a line that carries its own wording**. Rounds 3 and 4 of this
sweep's review removed three such notes (`00-header.js` tutor path, the `30-home.js` defaults line,
`DESK_STATE_WORD`) and each had been displacing a real block. A note of that shape is a coverage
claim, and it is checked like one.

### GAP-31 — the homework enum→copy maps and the sheet guards have no rows

`CB_HOMEWORK_STATE_WORD` (`desktop/src/95-studio.js:1850-1856`) and `CB_HOMEWORK_KIND_WORD`
(`1858-1865`) are enum→copy maps that a v3 restyle can silently shrink. The state map is **not
complete against the contract**: `homework.read` returns `task.state` over
`{proposed, assigned, self_reported_done, parent_reported_done, skipped, expired}`
(`$defs.homework_task.properties.state`), and the shipped map has only five words — `assigned` has
none. The two sheet guards (`2028, 2031`) are refusals, not truncation, and the already-reported
refusal (`2932`) is a third.

| proposed id | text (as shipped) | source | cap |
|---|---|---|---|
| `hw.state.proposed` | Planned | `field:homework.read.task.state` == `proposed` | 12 |
| `hw.state.assigned` | *(no shipped word — decision: "Assigned")* | `field:homework.read.task.state` == `assigned` | 12 |
| `hw.state.self_reported_done` | Done — you recorded it | `field:homework.read.task.state` == `self_reported_done` | 24 |
| `hw.state.parent_reported_done` | Done — a parent recorded it | `field:homework.read.task.state` == `parent_reported_done` | 24 |
| `hw.state.skipped` | Skipped | `field:homework.read.task.state` == `skipped` | 12 |
| `hw.state.expired` | Expired | `field:homework.read.task.state` == `expired` | 12 |
| `hw.kind.real_world_use` | Use it for real | `field:homework.read.task.task_kind` == `real_world_use` | 16 |
| `hw.kind.observe` | Notice it | `field:homework.read.task.task_kind` == `observe` | 12 |
| `hw.kind.label` | Label it | `field:homework.read.task.task_kind` == `label` | 12 |
| `hw.kind.practice` | Say it aloud | `field:homework.read.task.task_kind` == `practice` | 16 |
| `hw.kind.make` | Make it | `field:homework.read.task.task_kind` == `make` | 12 |
| `hw.kind.teach_back` | Tell someone | `field:homework.read.task.task_kind` == `teach_back` | 16 |
| `hw.sheet.guard.word` | This task would print a word a take-home sheet must not carry, so it is not shown. | deck | 100 |
| `hw.sheet.guard.steps` | A field card carries at most three steps, so this task is not shown. | deck | 80 |
| `hw.record.already_reported` | This task already carries a report; it cannot be reported twice. | deck | 70 |

**Decision for CP-001:** word `assigned` ("Assigned" is the proposal) rather than folding it into
`Planned`; the two states differ (a task the backend assigned is not one the learner proposed).

**Status (CP-001g, `t_4d6d5b56`):** rowed as `hw.*` in `COPY.md` §7 — five state words, six task kinds, both sheet guards and the second-report refusal. `hw.state.assigned` is deliberately absent: the owner has not chosen the word, and the proposed row is stated in the handoff rather than printed here.

### GAP-32 — the plan-validation independence words have no rows

`desktop/src/95-studio.js:3901-4446` states, in about 30 sentences, whether a second model checked
the plan, whether the sources were checked, and whether a pass is factual verification. These are
the product's honesty claims: a restyle that paraphrases "The author model checked its own work"
into "Checked" turns a `model_assessed` draft into an advertisement for an independent validator.
`GAP-28` owns the section; this gap exists so the family is authored as a unit and reviewed as one.

Proposed ids: `studio.verify.{rejected, same_model, independent, no_record, models_differ,
models_same, models_unknown, research_fetched, research_partial, research_unavailable, badge.*,
state.*, configure, not_configured, owner_edited, stale, refusal_record, passed_record,
stored_record, not_factual, no_binding, carried, passed, model_line, sources_unchecked,
checking_model, provenance_rule}` — one row per sentence, source `deck` except the two model-name
lines, which are `computed:model_identity` over the stored validation record.

**Decision:** whether the v3 surface keeps the full family or collapses it to a badge plus one
sentence. Collapsing is allowed only if the independent/same-model distinction and "not factual
verification" both survive somewhere on the surface.

**Status (CP-001g, `t_4d6d5b56`):** not rowed. The keep-or-collapse decision is open, so `studio.verify.*` is stated as a question in the handoff; a family authored either way would pre-empt the answer.

### GAP-33 — the fine-tune editor and its second dialog have no rows

`desktop/src/95-studio.js:4524-5714` is the H-194 fine-tune block. CP-025b extracted the leave guard
(`7818-7859`) but not this block, which contains a **second** `role="alertdialog"` for unsaved
section changes (`5583-5600`), the per-section edit form (`5445-5608`), the reorder/undo messages
(`5293-5428`, `4950`), and the one-section regeneration cost preflight (`4855-4888`, `5628-5688`).

Proposed ids: `studio.finetune.*` (title, note, order_label, move_label, shortcut, move.up/down,
edit, regenerate, field.*, save, unsaved_title, editor_note, consequence_label, consequence_dialog,
consequence_error, consequence_review,
confirm, saved_page, saved_meta, queued, undo, undone, order_saved, scope, no_changes, no_page,
no_page_short,
no_digest, err.*), `studio.dialog.*` (unsaved_title, unsaved_body, discard, keep), `studio.regen.*`
(estimate, no_estimate, queue, queued, preflight), `studio.revision.*` (edited, needs_review,
approved, edited_note, needs_review_note, approved_note), `studio.review.*` (title, loading, error,
clean, blocked, blocked_unknown, empty, changed, order, row.*).

The cost preflight sentence carries a number from the backend, so its source cell is
`computed:regen_preflight`; the two dialogs are `deck` rows with the same body shape as the leave
guard, and the second one must not be dropped because the first exists.

The evidence-consequence sentence is shipped in **three** renderings that do not share wording and
must be authored separately, not collapsed into one `{consequence}` placeholder: the in-panel
dialog (`5560`, "…reference this section. {consequence}"), the refusal toast after a
`lesson.revise` that needs confirmation (`5190-5191`, "…**learner** attempt(s) **already** reference
this section. {consequence} **Confirm to store the edit.**"), and the review row for a stored
revision (`4734`, "…reference this section**; the edit was confirmed against that consequence.**").
The sweep rows them as `consequence_dialog`, `consequence_error` and `consequence_review`.

**Status (CP-001g, `t_4d6d5b56`):** rowed as `studio.finetune.*`, `studio.dialog.*`, `studio.regen.*`, `studio.revision.*` and `studio.review.*` in `COPY.md` §10, including both `role="alertdialog"` blocks and the three consequence renderings as three rows.

### GAP-34 — the lesson-set export gate has no rows

The gate at `desktop/src/95-studio.js:7244-7526` is the **second** approval in the product. CP-025b
has the export *refusals* but neither the gate table (`Plan / Lesson set approval / Approved content
hash / Current content hash / Final approval`), the two formats, the artifact notes, nor the
download names.

Proposed ids: `studio.gate.{title, row.*, note, approved_line, no_plan, no_pages, unsupported,
approve, available, blocked, backend_reason, formats, minima, export, files, export_line, pack_note,
privacy_note, filename.*, download.*, artifact_note}` plus `studio.gate.format.{archive,pdf}`.
Source is `deck` except `approved_line` and `export_line`, which are `computed:` over the approval
and export records.

**Status (CP-001g, `t_4d6d5b56`):** rowed as `studio.gate.*` in `COPY.md` §10, with `studio.review.blocked` carrying the shared blocked sentence at both renderings.

### GAP-35 — offline and overflow on the four surfaces

CP-025a/CP-025b said "no offline copy" and "overflow: no copy". The sweep makes that precise:

- **Offline:** the shell has one sentence per route (`30-home.js:191-193`` rendered at `1191`, `32-desk.js:352`,
  `98-page.js:632`, `10-primitives.js:273`), and **none of the four surfaces mounts it** —
  `95-studio.js`, `97-world.js` and the Game block in `30-home.js` never call `useOnline()`.
  A failed read says "could not be read", which misnames the cause. Proposed: `hw.offline.*`,
  `game.offline.*`, `world.offline.*`, `studio.offline.*` — one sentence each, in the shipped
  shell's voice ("… is paused until the connection returns"), source `deck`.
- **Overflow:** only one surface has words — the tab-limit `clipped` badge (`95-studio.js:7223`)
  and `· the served text was clipped at the tab limit` (`7231`), both Parent Studio. The Game
  journal silently caps at 12 cards (`30-home.js:5064`), the homework card refuses rather than
  truncates, and World Studio has none. Proposed: `game.journal.overflow`,
  `world.plates.overflow`; `hw.card.overflow` is **not** needed — the sheet guard is the honest
  state and already has a row (`GAP-31`).

**Decision:** whether the four offline sentences are surface-specific or one shared
`shell.offline.surface` row. The shipped code has four different sentences for four routes, so one
shared row would be a rewrite, not a restyle.

**Status (CP-001g, `t_4d6d5b56`):** the overflow rows are authored (`game.journal.overflow`, `world.plates.overflow`, `studio.tab.clipped` + `studio.tab.clipped_note`). The four offline sentences are **not** rowed: the per-surface-or-shared decision is the owner's, and the proposal is in the handoff.

### GAP-36 — the `Guided` presentation word has no contract enum and no row

`CB_PRESENTATION_LABEL` (`00-header.js:238`) offers `Game / Guided / Textbook`, and `guided` is a
stored presentation option (`00-header.js:234`) as well as an autonomy option (`00-header.js:170`). The world contract's `presentation_mode` enum is
`{game, textbook}` (`contracts/rpc.v24.json`, `$defs.course_world.properties.presentation_mode`);
`guided` is **not** a world value. A deck row for "Guided" must therefore not cite
`field:world.read.presentation_mode` — that claim would be false and the inventory gate rejects it.
It is not a `game.*` word either: it labels a lesson view, not the play layer.

| proposed id | text (as shipped) | source | cap |
|---|---|---|---|
| `studio.presentation.guided` | Guided | deck | 12 |

**Decision for CP-001/atlas:** word it as a device view (`studio.presentation.guided`) or drop the
third option from the shell. It is not a `world.*` row and it is not a `game.*` row.

**Status (CP-001g, `t_4d6d5b56`):** not rowed. `studio.presentation.guided` stays out pending the owner's word; note that `create.dial.autonomy.guided` is the autonomy option, a different row, and is rowed under `GAP-37`.

### GAP-37 — the create-form recipe and dial vocabulary has no rows

`desktop/src/00-header.js:120-240` holds `RECIPE_COPY`, `DIALS` and `FILTERS`: five recipe cards
(title + description), four dials with their options, and four course filters. No card inventories
them and no deck section owns them. The `parent` card is the only shell pointer into Parent Studio
("That happens in Parent Studio, not here"), so a restyle there changes where a parent is sent.

Proposed ids: `create.recipe.{one_off,casual,committed,companion,parent}` plus `.desc` for each;
`create.dial.{pace,depth,assessment,autonomy}` plus `create.dial.pace.{light,steady,intense}`,
`create.dial.depth.{survey,working,deep}`, `create.dial.assessment.{none,self_check,graded}`,
`create.dial.autonomy.{guided,balanced,independent}`; `create.filter.{all,in_progress,review_due,
archived}`. All source `deck`.

Needed by: CP-022 (the Home create form) and CP-025b (the parent door). This is a new gap because
the CP-031 samples were scoped to the six screens and the create form's vocabulary fell between
them.

**Status (CP-001g, `t_4d6d5b56`):** rowed as `create.recipe.*` (ten rows, title plus description), `create.dial.*` (four dials and twelve options) and `create.filter.*` (four) in `COPY.md` §1.1.

### GAP-38 — the approval-invalidation banner and the plan-check reason labels have no rows

Two enum→copy families on the Parent Studio detail page had no row in any inventory. Both are
visible without opening a disclosure, and both are the kind of copy a restyle paraphrases into a
misleading claim.

1. **The approval-invalidation banner.** `APPROVAL_INVALIDATION_COPY`
   (`desktop/src/95-studio.js:3742-3747`) is the reason sentence inside `StudioReviewBanner`
   (`3750-3770`), which renders only when the stored approval row is `superseded` — it is derived
   from the approval row, never from local state. It has four reasons and two fallbacks (`3760` for
   an unknown reason, `3766` for the export line). A restyle that drops a reason leaves a parent
   with "Changes need review" and no cause, and one that rewords `content_changed` can imply the
   pages are wrong rather than that the approval no longer covers them.
2. **The plan-check reason labels.** `PLAN_CHECK_LABELS` (`3868-3875`) is the five-sentence
   vocabulary `planCheckLabel()` (`3877-3886`) feeds into "Checks that did not clear: {reasons}"
   (`4392`, rowed under `GAP-28`). Only `structure` had a row, so the deck could word the frame and
   none of the reasons a parent is actually shown.

| proposed id | text (as shipped) | source | cap |
|---|---|---|---|
| `studio.banner.title` | Changes need review | deck | 24 |
| `studio.banner.reason.plan_edited` | You edited the plan after approving the lesson set. | `field:parent.blueprint.read.approval.invalidated_reason` == `plan_edited` | 60 |
| `studio.banner.reason.content_changed` | The generated pages changed after you approved them. | `field:parent.blueprint.read.approval.invalidated_reason` == `content_changed` | 60 |
| `studio.banner.reason.course_edited` | You changed the course title or goal after approving the lesson set. | `field:parent.blueprint.read.approval.invalidated_reason` == `course_edited` | 80 |
| `studio.banner.reason.replaced` | A newer approval replaced this one. | `field:parent.blueprint.read.approval.invalidated_reason` == `replaced` | 40 |
| `studio.banner.reason.unknown` | The lesson set you approved no longer matches the current pages. | deck | 70 |
| `studio.banner.export_approve` | Approve the current lesson set before exporting. | deck | 60 |
| `studio.check.alignment` | whether each objective matches the goal | deck | 50 |
| `studio.check.sources` | whether each claim has a source that was actually read | deck | 60 |
| `studio.check.structure` | whether the units, objectives and checks fit together | deck | 60 |
| `studio.check.schedule` | whether the schedule and time estimates add up | deck | 50 |
| `studio.check.policy` | whether the plan follows the recipe and its limits | deck | 50 |

`studio.review.blocked` / `studio.review.blocked_unknown` (`GAP-33`) are the export-status sentences
in the same banner; `3766` renders `Export is blocked ({reason}).`, the same words as the gate at
`7392` (`GAP-34`), so it is cited on that row rather than duplicated here.

**Decision for CP-001:** whether the banner keeps all six sentences or collapses to the reason plus
a disclosure. If it collapses, every reason must still be reachable, and the check labels must stay
one sentence per check — the reason list is the only place the product says which check failed.

**Status (CP-001g, `t_4d6d5b56`):** rowed as `studio.banner.*` (title, four reasons, the unknown fallback, the export line) and `studio.check.*` (all five plan-check labels) in `COPY.md` §10.

### GAP-39 — the shell's contract-envelope error sentence has no row

`desktop/src/00-header.js:702-716` synthesizes an `INTERNAL_ERROR` envelope when the backend answers
with something that is not a contract envelope, and the message field of that envelope is rendered
by `describeError()` wherever a surface shows a failed read. Every surface that calls `cb.rpc` can
show it, including all four this card covers — so a learner can read "not a contract envelope",
which is product-internal vocabulary. It is also a claim: it says the answer was malformed, so a
restyle must not soften it into "something went wrong".

| proposed id | text (as shipped) | source | cap |
|---|---|---|---|
| `shell.rpc.envelope` | The Coursebook backend answered with something that is not a contract envelope. | deck | 90 |
| `shell.rpc.no_answer` | The Coursebook backend did not answer. | deck | 40 |

The second row is the same defect on the other branch: `describeError()` (`00-header.js:1057-1062``)
falls back to that sentence whenever the error object carries no `message` and no string — so a
failed read on any surface can print it, and `95-studio.js` calls the helper 20 times. It is a
synthesized answer, not the backend's, so it must not read as if the backend said it.

**Decision for CP-001:** keep this diagnostic sentence (honest, but internal) or replace it with a
plain failure line plus the code. If it is replaced, a malformed answer must stay distinguishable
from a timeout and from an offline read (`GAP-35`).

**Status (CP-001g, `t_4d6d5b56`):** rowed as `shell.rpc.envelope` and `shell.rpc.no_answer` in `COPY.md` §1, kept as shipped.

---

### GAP-40 — the classroom tutor path claims coverage it does not have

`desktop/src/00-header.js:836-1055` (the `loadBinding` / `resumeBoundSession` / `beginLessonFor`
block) returns a family of learner-visible sentences: `This lesson has no chat to return to yet.`
(`867`), `This lesson is not connected to a chat right now.` (`870`), `Update Hermes Desktop to
resume a bound lesson.` (`873`), `The saved lesson chat could not be opened from this desktop. The
section is still available to read.` (`883`), `Coursebook lesson` (`937`), `{code}: {backend message |
this chat could not be bound.}` (`961`), `No course was read for this action.` (`984`), `This course
has no current objective yet; approve the plan first.` (`987`), `Resumed the bound lesson chat.`
(`1024`), `There is no saved lesson chat for this section yet. …` (`1033`), `The lesson is ready.
Your section is open below. …` (`1053`).

These sit on the Classroom/course-detail tutor path, so CP-031b correctly did not row them — but
until this card the sweep's §5 said they were "inventoried by `CP-023-classroom.md`", and they are
not. `CP-023-classroom.md` records the deck's own no-chat state (`classroom.nochat.title/body/action`,
deck `161-163`: "This section has no chat yet" / "Start a fresh run to open a chat for this
section."), whose wording is not the shipped wording; no other inventory in this directory names any
of the sentences above. Leaving the claim in place would let CP-001 believe the tutor path is
covered.

**Minimum:** CP-023's owner (or CP-001 when it revises the Classroom section) copies the block into
an inventory and decides whether the deck's `nochat.*` rows are restated to match the shipped
sentences or the code is changed to emit the deck's wording. Not blocking for CP-025a/CP-025b, which
do not paint this path.

**Status (CP-001g, `t_4d6d5b56`):** rowed as `classroom.tutor.*` (eleven rows) in `COPY.md` §4, with the shipped wording kept. Whether the code adopts the deck's `classroom.nochat.*` wording instead is still a CP-023 question, recorded in the handoff.

---

### GAP-41 — the Home defaults line claims coverage `CP-022-home.md` does not have

`HomeDefaultsLine` (`desktop/src/30-home.js:4739-4784`) paints, above the Game band:

| shipped string | line |
|---|---|
| `Default view · ` + the mode label, falling back to `Game` | `4751` |
| `· This classroom · ` + the mode label, only when the selected classroom overrides the default | `4760` |
| `· Child-safe defaults` | `4770` |
| `· Session · ` + `{n} min` | `4775` |

The Game sweep's first cuts said the home-route twin of the child-safe line — the words are at
`4770` and `4775` — "belonged to `CP-022-home.md`". It does not. `CP-022-home.md` is a gap analysis of the Home surface: it names
`30-home.js` in two notes only — the settings sheet's shipped source lines and the companion
fallback — and it cites the defaults line (`4751-4775`) nowhere. It also has no
row for any string, so nothing in it could carry this block. The two forms also do not share wording
with the long ChildSafeLine sentence at `4798` ("Child-safe defaults · no loss-framed reminders, no
ranking, no random rewards, no XP or streaks"), so collapsing them would lose one of the two.

**Minimum:** CP-022's owner rows the block (it is Home chrome, not Game copy, which is why it is
`home.*` and not `game.*`) or CP-001 authors `home.defaults.*` from §1a of
`CP-031-sweep-game.md`. Not blocking for CP-025a/CP-025b.

**Status (CP-001g, `t_4d6d5b56`):** rowed as `home.defaults.*` (five rows: view, classroom, short child-safe, session, long child-safe) in `COPY.md` §2.

### GAP-42 — the objective-state words every Game card renders have no row

`CB_COPY.state` (`desktop/src/00-header.js:63-72`) maps seven evidence states to the learner's
words, and the Game journal card renders it through `CB_COPY.stateWord(card.state)`
(`desktop/src/30-home.js:5204`), with `Stamped` as the earned-word at `5192`:

`not_started` → *Not started*, `introduced` → *Started*, `independent_evidence` → *Independent
evidence*, `delayed_evidence` → *Delayed evidence*, `review_due` → *Review due*, `needs_review` →
*Could not be written*, `overridden` → *Moved on without a grade*.

No deck file in this directory carries any of those seven words as a row; the Game sweep used to say
they were "inventoried in `CP-022-home.md`", which is false on the same reading as `GAP-41`. The map
is also the only place the Game surface says *Independent evidence* at all, and `GAP-17` already owns
the integrity words for the same states on the Classroom surface — the two must be authored against
one decision, not two. `CB_COPY` is the one learner-vocabulary map: a second literal anywhere on a
rendered surface is refused by `tests/test_desktop_learner_copy.py`, so these rows must be authored
here rather than copied onto a Game surface.

**Minimum:** CP-001 authors `game.state.*` (or extends `GAP-17`'s family) with all seven values, and
decides whether *Independent evidence* / *Delayed evidence* are the same words the Classroom uses.
Not blocking for CP-025a/CP-025b, which do not paint the journal.

**Status (CP-001g, `t_4d6d5b56`):** rowed as `game.state.*` in `COPY.md` §8 — all seven values plus the `State not recorded` fallback — and `game.journal.stamped` for the earned word.

---

## Amendment order (what unblocks what)

1. `GAP-01`, `GAP-02` — shell. Needed by every screen; do first.
2. `GAP-03`, `GAP-07`, `GAP-11`, `GAP-19` — the four missing card/node titles, and the one pack-title
   source decision in `GAP-07`.
3. `GAP-12`–`GAP-17` — the Classroom answer surface and integrity words; CP-023 cannot ship without
   them. `GAP-17` needs all six `evidence_class` values, not three.
4. `GAP-22` — the missing offline state; one row set, three strings.
5. `GAP-23`, `GAP-24`, `GAP-27`, `GAP-28` — the two missing deck sections; CP-025a and CP-025b stay
   blocked until these land. `GAP-30` is **closed**: author from the `CP-031-sweep-*.md` files, not
   from the sample tables.
6. `GAP-31`–`GAP-42` — the categories the sweep found with no gap. `GAP-31` (homework maps) blocks
   CP-025a for the same reason `GAP-23` does; `GAP-32`–`GAP-34` block CP-025b's fine-tune, validation
   and export surfaces; `GAP-35` is the §3.12 offline/overflow obligation for all four surfaces;
   `GAP-36` is a shell decision that must land before the mode words are restyled; `GAP-37` is the
   create-form vocabulary CP-022 and CP-025b both read; `GAP-38` is the banner and check-reason
   family CP-025b's detail section needs alongside `GAP-28`; `GAP-39` is the shell error sentence
   every surface can paint; `GAP-41` (Home defaults line) and `GAP-42` (Game objective-state words)
   are blocks the sample shelves and this sweep's own notes had wrongly assigned to
   `CP-022-home.md`, so neither is a CP-025a/CP-025b blocker but both are deck debt.
7. Body corrections and card-body repairs (`GAP-06`, `GAP-08`–`GAP-10`, `GAP-18`, `GAP-21`,
   `GAP-26`, `GAP-29`) are `hermes kanban edit` work on the card bodies, not deck work.

Owner decisions required (not wordable by the deck author alone): `GAP-04`, `GAP-05`, `GAP-07`
(source), `GAP-15` (three sentences), `GAP-17` (the three non-cold integrity words), `GAP-20`,
`GAP-22` (body text), `GAP-25` (empty vs unavailable), `GAP-31` (the `assigned` word), `GAP-32`
(keep or collapse the independence family), `GAP-35` (per-surface or shared offline), `GAP-36`
(the `Guided` word).
