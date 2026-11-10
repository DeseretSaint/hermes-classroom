# COPY — every string on the v3 screens

Card: CP-001. This is the copy deck for v3. It is the only source of product wording; a screen may
not render text that has no row here, and a row that no screen uses is removed rather than kept.

Binding rules:

- Plain language, 6th–8th grade. Short sentences. Sentence case. No exclamation marks.
- No internal names: never show a code value such as `needs_review`, `resume_lesson`,
  `resolve_review_due`, `review_due`, `single_home_host`, `runtime`, `binding`, `projection`.
  Those are field names, not words a person reads.
- `{braces}` mark a value the surface fills from the named field. A missing value takes the row's
  "when empty" wording; it never renders a zero, a dash pile or an empty box.
- Counts are real. A count the backend does not record is not rendered at all.
- Every string is at most the char cap shown; a longer value clamps with an ellipsis at a word
  boundary and keeps its `title` attribute.
- Japanese at L0 renders three scaffolds together: kana, `furigana` ruby over kanji, `romaji`
  under the line, plus the English meaning. A romaji-only line is not offered.

Sources: `deck` = authored here; `field:<path>` = a backend value rendered verbatim; `art` = a
provenance row for the plate, not a claim about learning.

---

## 1. Shared shell

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `nav.home` | Home | deck | 12 | rail, tab strip |
| `nav.courses` | Courses | deck (`DESTINATIONS`) | 12 | rail, tab strip |
| `nav.workshop` | Workshop | deck (`DESTINATIONS`) | 12 | rail, tab strip |
| `nav.parent` | Parent Studio | field (`DESTINATIONS`) | 16 | rail, tab strip |

---

## 2. Home (`R-HOME`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `home.title` | Your field library | deck | 24 | H2 |
| `home.sub` | Pick a course, or start a new one. | deck | 48 | H2 |
| `home.primary` | Start a course | deck | 24 | H3 filled |
| `home.secondary` | Browse library | deck | 24 | H3 outline |
| `home.settings` | Settings | deck | 12 | H7 |
| `home.shelf.label` | Your courses | deck | 24 | H4 |
| `home.card.subject` | {subject label} | field:`library_item.subject_label` (CP-005) or `world_brief.subject_domain` or `recipe` | 24 | H5 card, line 2 |
| `home.card.meta` | {done} of {total} sections done | field:`sections_done`,`sections_total` (CP-005), else `evidence_summary.independent`,`total_objectives` | 32 | H5 card, line 3 |
| `home.card.new` | New | field:`is_new` (CP-005), else `evidence_summary.independent == 0` | 4 | H5 card chip |
| `home.card.next` | {next step} | field:`next_step.label` | 40 | H5 card, quiet action |
| `home.tag.firstuse` | New course | deck | 14 | H6 paper tag, first use only |
| `home.firstuse.title` | Your field library | deck | 24 | H2, first use |
| `home.firstuse.sub` | Nothing here yet. Start a course and its first lesson will appear on this shelf. | deck | 84 | H2, first use |
| `home.firstuse.primary` | Start your first course | deck | 24 | H3, first use |
| `home.overflow.hint` | More courses to the right | deck | 28 | H5 mask, wide and mid only |
| `home.empty.title` | No courses on this shelf | deck | 28 | H2 |
| `home.empty.body` | Courses you archive move out of this view. | deck | 56 | H2 |
| `home.empty.action` | See archived courses | deck | 28 | H3 quiet |
| `home.loading` | Reading your courses. Nothing on the shelf changes while this loads. | deck | 74 | H2 |
| `home.error.title` | Your courses could not be read | deck | 32 | H2 |
| `home.error.body` | Nothing you saved is lost. Try again. | deck | 44 | H2 |
| `home.error.action` | Try again | deck | 12 | H3 quiet |
| `home.offline.title` | You are offline | deck | 20 | H2 |
| `home.offline.body` | Your shelf is here. New lessons wait until you reconnect. | deck | 60 | H2 |
| `home.offline.action` | Try again | deck | 12 | H3 quiet |

---

## 3. Discover / Workshop (`R-DISC`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `discover.title` | Discover | deck | 16 | D2 |
| `discover.sub` | Packs you can learn from, already on this device. | deck | 56 | D2 |
| `discover.tab.discover` | Discover | deck | 12 | D3 |
| `discover.tab.library` | Library | deck | 12 | D3 |
| `discover.tab.provenance` | Provenance | deck | 12 | D3 |
| `discover.feature.title` | {pack title} | field:`pack.inspect.manifest.title` | 40 | D4 quiet field |
| `discover.feature.body` | {pack description} | field:`pack.inspect.manifest.description` | 140 | D4 quiet field |
| `discover.feature.primary` | Preview this pack | deck | 24 | D4 filled |
| `discover.shelf.title` | All packs | deck | 20 | D6 |
| `discover.shelf.count` | {n} packs | field: count of `workshop.list` rows | 16 | D6 right |
| `discover.card.meta` | {n} sections | field:`pack.inspect.manifest.sections` length, else CP-005 `sections_total` | 24 | D7 card, line 3 |
| `discover.card.trust.integrity` | Files checked | field:`pack.inspect.trust.labels` contains `integrity_verified` | 20 | D7 card chip |
| `discover.card.trust.checks` | Automated checks passed | field:`…labels` contains `automated_checks_passed` | 28 | D7 card chip |
| `discover.card.trust.human` | Human review recorded | field:`…labels` contains `human_review_recorded` | 28 | D7 card chip |
| `discover.card.trust.model` | Support assessed by a model | field:`…labels` contains `model_assessed_support` | 32 | D7 card chip |
| `discover.empty.title` | No packs on this device | deck | 28 | D4 quiet field |
| `discover.empty.body` | A pack file you add shows up here. | deck | 44 | D4 quiet field |
| `discover.empty.action` | Import a pack | deck | 20 | D4 quiet |
| `discover.loading` | Reading your workshop. | deck | 28 | D2 |
| `discover.error.title` | The workshop could not be read | deck | 32 | D2 |
| `discover.error.body` | Packs you already have are unchanged. Try again. | deck | 52 | D2 |
| `discover.error.action` | Try again | deck | 12 | D9 quiet |
| `discover.offline.title` | You are offline | deck | 20 | D2 |
| `discover.offline.body` | Packs already on this device still list. The rest waits. | deck | 60 | D2 |
| `discover.offline.action` | Try again | deck | 12 | D9 quiet |
| `discover.rejected.banner` | {pack title} did not pass its checks. | field: title + `trust.labels` | 56 | D9 |
| `discover.rejected.title` | This pack did not pass its checks | deck | 36 | D4 quiet field |
| `discover.rejected.body` | Open Provenance to see what was recorded for each file. | deck | 60 | D4 quiet field |
| `discover.rejected.action` | Open Provenance | deck | 20 | D4 quiet |

---

## 4. Classroom (`R-CLASS`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `classroom.back` | Back to {course title} | field:`library_item.title` | 48 | C2 |
| `classroom.title` | {course title} | field:`library_item.title` | 60 | C4 |
| `classroom.section` | {section title} | field: current objective title | 60 | C4 |
| `classroom.stepper.label` | This section | deck | 16 | C3 (screen-reader group name) |
| `classroom.step.current` | Now | deck | 8 | C3 current stamp label |
| `classroom.step.done` | Done | deck | 8 | C3 completed stamp label |
| `classroom.step.next` | Next | deck | 8 | C3 upcoming stamp label |
| `classroom.step.locked` | Opens after the check | deck | 24 | C3, only where the plan gates it |
| `classroom.scene.credit` | {art credit} | art: asset provenance row | 40 | C5 mat, micro |
| `classroom.line.jp` | 好きです。付き合ってください。 | field:`lesson_block` kana line | 80 | C6 |
| `classroom.line.furigana` | 好(す)き です。付(つ)き合(あ)ってください。 | field:`lesson_block` reading (ruby) | 80 | C6 over the line |
| `classroom.line.romaji` | suki desu. tsukiatte kudasai. | field:`lesson_block` romaji | 80 | C6 under the line |
| `classroom.line.en` | I like you. Please go out with me. | field:`lesson_block` English meaning | 80 | C6 under romaji |
| `classroom.line.play` | Play the line | deck | 16 | C6 quiet action |
| `classroom.check.question` | {check prompt} | field:`lesson.page` check prompt | 120 | C7 |
| `classroom.check.option` | {option text} | field:`lesson.page` check option | 60 | C7, 3 targets |
| `classroom.check.primary` | Check answer | deck | 16 | C7 filled |
| `classroom.check.correct` | That is right. {why} | field: check explanation, prefixed `deck` | 120 | C7 verdict |
| `classroom.check.wrong` | Not quite. {why} | field: check explanation, prefixed `deck` | 120 | C7 verdict |
| `classroom.check.retry` | Try again | deck | 12 | C7 primary after a wrong verdict |
| `classroom.check.next` | Next section | deck | 16 | C7 primary after a correct verdict |
| `classroom.evidence.title` | Evidence | deck | 12 | C8, C9 |
| `classroom.evidence.count` | {n} of {total} checks recorded | field: recorded checks, plan total | 32 | C8 |
| `classroom.evidence.empty` | No checks recorded yet. | deck | 28 | C8 empty |
| `classroom.aside.next` | Next up: {next section} | field:`next_step.label` | 48 | C8 |
| `classroom.aside.tutor` | Ask the tutor | deck | 16 | C8 quiet action |
| `classroom.nochat.title` | This section has no chat yet | deck | 32 | C7 region |
| `classroom.nochat.body` | Start a fresh run to open a chat for this section. | deck | 60 | C7 region |
| `classroom.nochat.action` | Start a fresh run | deck | 20 | C7 filled |
| `classroom.complete.title` | Section finished | deck | 20 | C7 region |
| `classroom.complete.body` | Your check is recorded. | deck | 28 | C7 region |
| `classroom.complete.action` | Back to the path | deck | 20 | C7 filled |
| `classroom.loading` | Opening this section. | deck | 24 | C4 |
| `classroom.error.title` | This section could not be read | deck | 32 | C7 region |
| `classroom.error.body` | Your attempt is unchanged. Try again. | deck | 44 | C7 region |
| `classroom.error.action` | Try again | deck | 12 | C7 quiet |
| `classroom.offline.title` | You are offline | deck | 20 | C7 region |
| `classroom.offline.body` | The page you opened last is still here. Checking an answer waits. | deck | 70 | C7 region |
| `classroom.offline.action` | Try again | deck | 12 | C7 quiet |
| `classroom.game.xp` | {n} XP | field:`engagement.read.xp_total`, Game mode only | 12 | C11 chip |
| `classroom.challenge.title` | Field Challenge | field: the check's own title, Game mode only | 24 | C11 |
| `classroom.challenge.primary` | Try it yourself | deck | 20 | C11 filled, Game mode only |

**Worked L0 example.** The four `classroom.line.*` rows above show one real line from the bundled
pack `bundled/packs/japanese-affection-context-l0/content/section-01-two-ways.md` (Dialogue B).
The shot renders whatever `lesson_block` carries; this example is the fixture that proves the
three scaffolds fit. `好(す)き` is the ruby form of 好き; the kana, the romaji and the meaning are
the pack's own, not re-authored here.

---

## 5. Course home (`R-MAP`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `course.back` | Back to {parent} | field: destination label | 32 | M2 |
| `course.title` | {course title} | field:`library_item.title` | 60 | M3 |
| `course.subject` | {subject label} | field:`subject_label` (CP-005) | 24 | M3 |
| `course.hero.credit` | {art credit} | art: asset provenance row | 40 | M4 mat, micro |
| `course.route.label` | Your route | deck | 16 | M5 (screen-reader group name) |
| `course.node.current` | You are here | deck | 16 | M5 current node |
| `course.node.done` | Done | deck | 8 | M5 completed node |
| `course.node.next` | Next | deck | 8 | M5 next node |
| `course.node.locked` | Opens after the section before it | deck | 36 | M5, only where the plan gates it |
| `course.continue.title` | Continue | deck | 12 | M6 heading |
| `course.next.label` | {next step} | field:`next_step.label` | 48 | M6 filled plate |
| `course.evidence.title` | Evidence | deck | 12 | M7 |
| `course.evidence.count` | {n} of {total} sections have evidence | field:`sections_done`,`sections_total` | 44 | M7 |
| `course.others.title` | Your other courses | deck | 24 | M8 |
| `course.others.row` | {title} · {next step} | field:`library_item.title`, `next_step.label` | 60 | M8 rows |
| `course.plan.review.title` | The plan is waiting for you | deck | 32 | M6 |
| `course.plan.review.body` | Read it, then approve it so lessons can start. | deck | 52 | M6 |
| `course.plan.review.action` | Review the plan | deck | 20 | M6 filled |
| `course.noworld.title` | No scene yet | deck | 20 | M4 |
| `course.noworld.body` | The lesson works without art. | deck | 36 | M4 |
| `course.world.running` | Painting the scene. | deck | 24 | M4 |
| `course.world.rejected.title` | This scene was not approved | deck | 32 | M4 |
| `course.world.rejected.action` | Open World Studio | deck | 20 | M4 quiet |
| `course.end.title` | Course complete | deck | 20 | M6 |
| `course.end.body` | Every section has evidence. | deck | 28 | M6 |
| `course.end.action` | Review the plan | deck | 20 | M6 filled |
| `course.loading` | Opening this course. | deck | 24 | M3 |
| `course.error.title` | This course could not be read | deck | 32 | M3 |
| `course.error.body` | The route shows what was saved last. Try again. | deck | 56 | M3 |
| `course.error.action` | Try again | deck | 12 | M6 quiet |

---

## 6. Design-system lab (`R-SYS`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `lab.title` | Design system | deck | 20 | S2 |
| `lab.sub` | The parts every screen uses, with the values they read. | deck | 60 | S2 |
| `lab.readonly` | Read-only sheet. Values come from the token contract. | deck | 60 | S2 |
| `lab.back` | Back | deck | 8 | S2 top-left |
| `lab.section.fox` | Fox poses | deck | 16 | S3 |
| `lab.section.card` | Card anatomy | deck | 16 | S3 |
| `lab.section.medals` | Medallions | deck | 16 | S3 |
| `lab.section.palette` | Palette | deck | 16 | S4 |
| `lab.section.type` | Type | deck | 16 | S4 |
| `lab.section.materials` | Materials | deck | 16 | S4 |
| `lab.pose.wave` | Waving | deck | 12 | S5 specimen name |
| `lab.pose.point` | Pointing | deck | 12 | S5 |
| `lab.pose.clock` | Clock | deck | 12 | S5 |
| `lab.pose.read` | Reading | deck | 12 | S5 |
| `lab.pose.cheer` | Cheering | deck | 12 | S5 |
| `lab.pose.think` | Thinking | deck | 12 | S5 |
| `lab.pose.sleep` | Sleeping | deck | 12 | S5 |
| `lab.anatomy.plate` | 01 Art plate | deck | 20 | S6 callout |
| `lab.anatomy.title` | 02 Title | deck | 20 | S6 |
| `lab.anatomy.subject` | 03 Subject | deck | 20 | S6 |
| `lab.anatomy.evidence` | 04 Evidence line | deck | 24 | S6 |
| `lab.anatomy.next` | 05 Next step | deck | 20 | S6 |
| `lab.anatomy.cover` | 06 Cover mark | deck | 20 | S6 |
| `lab.medal.first_check` | First check | deck | 16 | S7 |
| `lab.medal.first_review` | First review | deck | 16 | S7 |
| `lab.medal.first_takehome` | First take-home | deck | 20 | S7 |
| `lab.medal.course_complete` | Course complete | deck | 20 | S7 |
| `lab.palette.role` | {role name} | field:`contracts/cb.tokens.v3.json` role key | 20 | S8 |
| `lab.palette.ratio` | {ratio}:1 | field: computed from the contract pair | 10 | S8 |
| `lab.type.display` | Display · 56/60 · Your field library | field: contract size + this sample | 48 | S9 |
| `lab.type.title` | Title · 32/40 · Japanese Lantern District | field: contract size + this sample | 48 | S9 |
| `lab.type.section` | Section · 24/32 · Your route | field: contract size + this sample | 48 | S9 |
| `lab.type.body` | Body · 16/26 · A sentence of real lesson text. | field: contract size + this sample | 56 | S9 |
| `lab.type.label` | Label · 14/20 · Check answer | field: contract size + this sample | 48 | S9 |
| `lab.type.micro` | Micro · 12/16 · 4 of 5 checks recorded | field: contract size + this sample | 48 | S9 |
| `lab.material.grain` | Paper grain | deck | 16 | S10 |
| `lab.material.wood` | Wood ledge | deck | 16 | S10 |
| `lab.material.elevation` | Elevation | deck | 16 | S10 |
| `lab.material.radius` | Radius | deck | 16 | S10 |
| `lab.motion.static` | Motion off: poses hold still. | deck | 36 | S? reduced-motion state |
| `lab.forced` | System colours. | deck | 20 | S? forced-colors state |
| `lab.text200` | Text at 200%. | deck | 20 | S? text-200 state |

---

## 7. Words this deck does not use

The v2 honesty rules stay. No string claims a public score, a ranking, a crowd opinion, a
competence state, or a count of people. Where a concept showed one of those, the row above
replaces it with a recorded fact or drops it: a card says how many sections are done, a pack says
which checks it passed, and a lesson says how many checks are recorded. The specific words the
screens may not render, in any form, are the ones for public scores, score marks, crowd opinion, a
headcount of people, and a competence percentage. `docs/EXPERIENCE-QUALITY-BAR.md` §2.5 is the
rule; this deck is its wording.
