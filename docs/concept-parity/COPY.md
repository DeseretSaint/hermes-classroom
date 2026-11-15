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
- Japanese at L0 renders the pack's own line: kana, `romaji` under the line, and the English
  meaning, all read from the pack's section content or the media `text_equivalent`. A romaji-only
  line is not offered.
- `furigana` ruby over kanji is authored by this deck, never read from a field: the pack carries no
  reading. Omit the ruby when the pack carries no reading; never derive one from kana.

Sources, exactly one of these forms per cell:

- `deck` — authored here. `deck (DESTINATIONS)` means the deck owns the string and the nav constant
  in `desktop/plugin.js` must match it.
- `field:<path>` — one backend value rendered verbatim. `<path>` resolves in
  `contracts/rpc.v24.json`: either `$defs.<def>.<field…>` or `<method>.<response field…>`, with
  `[]` for an array step. `pack.inspect.manifest.<field>` resolves in
  `contracts/pack-manifest.v2.json`. The only `field:` names outside the frozen contracts are the
  CP-005 forward fields the closing test allowlists: `library_item.subject_label`,
  `library_item.sections_done`, `library_item.sections_total`, `library_item.is_new`.
- `pack:<repo-relative path>` — the pack's own authored content; the file must exist.
- `art:<manifest path>` — a licence/provenance row (`license.per_artifact[].attribution`), not a
  claim about learning.
- `contract:<path>` — a value CP-002 owns in `contracts/cb.tokens.v3.json`, written as a path into
  that file: `color.<role>`, `type.scale.<step>` or `type.line_height.<step>`. A quoted size cites
  the scale path and, because the row also prints the line-height, that step's line-height path. A
  bare `type.<step>` names no path in the contract and is never written.
- `computed:<rule>` — arithmetic the surface performs on a named field; the rule is stated in
  SPEC-V3.

A cell may name several sources joined by ` + `; the surface renders the first that is present and
omits the row when none is.

---

## 1. Shared shell

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `nav.home` | Home | deck | 12 | rail, tab strip |
| `nav.courses` | Courses | deck (`DESTINATIONS`) | 12 | rail, tab strip |
| `nav.workshop` | Workshop | deck (`DESTINATIONS`) | 12 | rail, tab strip |
| `nav.parent` | Parent Studio | deck (`DESTINATIONS`) | 16 | rail, tab strip |
| `shell.rpc.envelope` | The Coursebook backend answered with something that is not a contract envelope. | deck | 90 | `00-header.js:710` · synthesized envelope, painted by `describeError()` on any surface |
| `shell.rpc.no_answer` | The Coursebook backend did not answer. | deck | 40 | `00-header.js:1058`; `00-header.js:1061` · `describeError()` fallback |

`shell.rpc.*` is the shell's own failure sentence, not a surface's: every route that calls `cb.rpc`
can paint it, and `GAP-39` records that no deck row carried it. The words are kept as shipped —
a malformed answer must stay distinguishable from a timeout and from an offline read.

### 1.1 Create form (shared shell, painted on Home)

`GAP-37` found the create form's whole vocabulary — five recipe cards, four dials and four course
filters — with no row in any card: the CP-031 samples were scoped to the six screens and the create
form fell between them. The `parent` recipe is the only shell pointer into Parent Studio, so a
restyle here changes where a parent is sent.

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `create.recipe.one_off` | One task I need to do now | deck | 28 | `00-header.js:122` · `RECIPE_COPY.one_off.title` |
| `create.recipe.one_off.desc` | A single thing to get right — a repair, a form, a procedure. You practise the task, not a quiz. | deck | 110 | `00-header.js:123` · `RECIPE_COPY.one_off.description` |
| `create.recipe.casual` | A little at a time | deck | 20 | `00-header.js:126` · `RECIPE_COPY.casual.title` |
| `create.recipe.casual.desc` | Short sessions you pick up when you have ten minutes, with no schedule to keep. | deck | 90 | `00-header.js:127` · `RECIPE_COPY.casual.description` |
| `create.recipe.committed` | A steady plan | deck | 16 | `00-header.js:130` · `RECIPE_COPY.committed.title` |
| `create.recipe.committed.desc` | A sequence that builds on itself, with practice you come back to. | deck | 70 | `00-header.js:131` · `RECIPE_COPY.committed.description` |
| `create.recipe.companion` | Alongside something else | deck | 24 | `00-header.js:134` · `RECIPE_COPY.companion.title` |
| `create.recipe.companion.desc` | A subject you keep returning to while you study or work on other things. | deck | 80 | `00-header.js:135` · `RECIPE_COPY.companion.description` |
| `create.recipe.parent` | Preparing for my child | deck | 24 | `00-header.js:138` · `RECIPE_COPY.parent.title` |
| `create.recipe.parent.desc` | You are preparing material for a child. That happens in Parent Studio, not here. | deck | 84 | `00-header.js:139` · the only shell pointer into Parent Studio |
| `create.dial.pace` | Pace | deck | 8 | `00-header.js:144` · `DIALS.pace.label` |
| `create.dial.pace.light` | Light | deck | 8 | `00-header.js:146` · `DIALS.pace.options` |
| `create.dial.pace.steady` | Steady | deck | 8 | `00-header.js:147` · `DIALS.pace.options` |
| `create.dial.pace.intense` | Intense | deck | 8 | `00-header.js:148` · `DIALS.pace.options` |
| `create.dial.depth` | Depth | deck | 8 | `00-header.js:152` · `DIALS.depth.label` |
| `create.dial.depth.survey` | Survey | deck | 8 | `00-header.js:154` · `DIALS.depth.options` |
| `create.dial.depth.working` | Working | deck | 8 | `00-header.js:155` · `DIALS.depth.options` |
| `create.dial.depth.deep` | Deep | deck | 8 | `00-header.js:156` · `DIALS.depth.options` |
| `create.dial.assessment` | Assessment | deck | 12 | `00-header.js:160` · `DIALS.assessment.label` |
| `create.dial.assessment.none` | None | deck | 8 | `00-header.js:162` · `DIALS.assessment.options` |
| `create.dial.assessment.self_check` | Self-check | deck | 12 | `00-header.js:163` · `DIALS.assessment.options` |
| `create.dial.assessment.graded` | Graded | deck | 8 | `00-header.js:164` · `DIALS.assessment.options` |
| `create.dial.autonomy` | Autonomy | deck | 10 | `00-header.js:168` · `DIALS.autonomy.label` |
| `create.dial.autonomy.guided` | Guided | deck | 8 | `00-header.js:170` · `DIALS.autonomy.options` (the autonomy option, not the presentation word) |
| `create.dial.autonomy.balanced` | Balanced | deck | 10 | `00-header.js:171` · `DIALS.autonomy.options` |
| `create.dial.autonomy.independent` | Independent | deck | 14 | `00-header.js:172` · `DIALS.autonomy.options` |
| `create.filter.all` | All | deck | 4 | `00-header.js:177` · `FILTERS` |
| `create.filter.in_progress` | In progress | deck | 14 | `00-header.js:178` · `FILTERS` |
| `create.filter.review_due` | Review due | deck | 12 | `00-header.js:179` · `FILTERS`, reading `CB_COPY.state.review_due` |
| `create.filter.archived` | Archived | deck | 10 | `00-header.js:180` · `FILTERS` |

`studio.presentation.guided` (the `Guided` presentation option at `00-header.js:238`) is **not**
rowed: `GAP-36` asks the owner whether the third presentation view survives, and a `guided` world
contract value does not exist, so the row is stated in the handoff instead of guessed.

---

## 2. Home (`R-HOME`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `home.title` | Your field library | deck | 24 | H2 |
| `home.sub` | Choose a course or start a new expedition. | deck | 48 | H2 |
| `home.primary` | Start a course | deck | 24 | H3 filled |
| `home.secondary` | Browse library | deck | 24 | H3 outline |
| `home.settings` | Settings | deck | 12 | H7 |
| `home.shelf.label` | Your courses | deck | 24 | H4 |
| `home.card.subject` | {subject label} | field:`library_item.subject_label` (CP-005) + field:`world_brief.subject_domain` + field:`library_item.recipe` | 24 | H5 card, line 2 |
| `home.card.meta` | {done} of {total} sections done | field:`library_item.sections_done` + field:`library_item.sections_total` (CP-005), else field:`library_item.evidence_summary.independent` + field:`library_item.evidence_summary.total_objectives` | 32 | H5 card, line 3 |
| `home.card.practice` | {n} checks recorded | field:`library_item.checks_recorded` (CP-005), used only when field:`library_item.sections_total` is 0 — an all-practice course has no section denominator; renders `1 check recorded` for one | 32 | H5 card, line 3 when the course has no evidence-bearing section |
| `home.card.new` | New | field:`library_item.is_new` (CP-005), else field:`library_item.evidence_summary.independent` | 4 | H5 card chip |
| `home.card.next` | {next step} | field:`library_item.next_step.label` | 40 | H5 card, quiet action |
| `home.card.untitled` | Untitled course | deck | 16 | H5 card, title line when the course row carries no title yet |
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
| `home.defaults.view` | Default view · {mode} | deck | 32 | `30-home.js:4751` · `HomeDefaultsLine`, above the Game band |
| `home.defaults.classroom` | · This classroom · {mode} | deck | 40 | `30-home.js:4760` · only when this classroom overrides the default |
| `home.defaults.childsafe` | · Child-safe defaults | deck | 28 | `30-home.js:4770` · the short form, above the band |
| `home.defaults.session` | · Session · {n} min | deck | 24 | `30-home.js:4775` · the configured session length |
| `home.defaults.childsafe_long` | Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no streaks · XP is cosmetic Game feedback | deck | 140 | `30-home.js:4798` · `ChildSafeLine`, the long form; it does not share wording with the short one |

`GAP-41` records why this block is `home.*` and not `game.*`: it is Home chrome that sits above the
Game band, it was wrongly assigned to `CP-022-home.md` (which carries no rows), and the short and
long child-safe forms are two different sentences, so collapsing them would lose one.

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
| `discover.feature.body` | {pack subtitle} | field:`pack.inspect.manifest.subtitle` | 140 | D4 quiet field |
| `discover.feature.primary` | Preview this pack | deck | 24 | D4 filled |
| `discover.shelf.title` | All packs | deck | 20 | D6 |
| `discover.shelf.count` | {n} packs | field:`pack.list.total` (filter `installed`) | 16 | D6 right |
| `discover.card.meta` | {n} sections | computed:`sum(objectives[].sections[])` over field:`pack.inspect.manifest.objectives[].sections[]`, else field:`library_item.sections_total` (CP-005) | 24 | D7 card, line 3 |
| `discover.card.trust.integrity` | Files checked | field:`pack.inspect.trust.labels` contains `integrity_verified` | 20 | D7 card chip |
| `discover.card.trust.checks` | Automated checks passed | field:`pack.inspect.trust.labels` contains `automated_checks_passed` | 28 | D7 card chip |
| `discover.card.trust.human` | Human review recorded | field:`pack.inspect.trust.labels` contains `human_review_recorded` | 28 | D7 card chip |
| `discover.card.trust.model` | Support assessed by a model | field:`pack.inspect.trust.labels` contains `model_assessed_support` | 32 | D7 card chip |
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
| `discover.rejected.banner` | {pack title} did not pass its checks. | field:`pack.inspect.manifest.title` + field:`pack.inspect.trust.labels` | 56 | D9 |
| `discover.rejected.title` | This pack did not pass its checks | deck | 36 | D4 quiet field |
| `discover.rejected.body` | Open Provenance to see what was recorded for each file. | deck | 60 | D4 quiet field |
| `discover.rejected.action` | Open Provenance | deck | 20 | D4 quiet |

---

## 4. Classroom (`R-CLASS`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `classroom.back` | Back to {course title} | field:`library_item.title` | 48 | C2 |
| `classroom.title` | {course title} | field:`library_item.title` | 60 | C4 |
| `classroom.section` | {section title} | field:`lesson.page.section.title` | 60 | C4 |
| `classroom.stepper.label` | This section | deck | 16 | C3 (screen-reader group name) |
| `classroom.step.current` | Now | deck | 8 | C3 current stamp label |
| `classroom.step.done` | Done | deck | 8 | C3 completed stamp label |
| `classroom.step.next` | Next | deck | 8 | C3 upcoming stamp label |
| `classroom.step.locked` | Opens after the check | deck | 24 | C3, only where the plan gates it |
| `classroom.scene.credit` | {art credit} | art:`license.per_artifact[].attribution` | 40 | C5 mat, micro |
| `classroom.line.jp` | 好きです。付き合ってください。 | pack:`bundled/packs/japanese-affection-context-l0/content/section-01-two-ways.md#dialogue-b` | 80 | C6 |
| `classroom.line.furigana` | 好(す)き です。付(つ)き合(あ)ってください。 | deck (ruby over kanji; omit when the pack carries no reading) | 80 | C6 over the line |
| `classroom.line.romaji` | suki desu. tsukiatte kudasai. | pack:`bundled/packs/japanese-affection-context-l0/content/section-01-two-ways.md#dialogue-b` + pack:`bundled/packs/japanese-affection-context-l0/pack.json#files[].text_equivalent` | 80 | C6 under the line |
| `classroom.line.en` | I like you. Please go out with me. | pack:`bundled/packs/japanese-affection-context-l0/content/section-01-two-ways.md#dialogue-b` + pack:`bundled/packs/japanese-affection-context-l0/pack.json#files[].text_equivalent` | 80 | C6 under romaji |
| `classroom.line.play` | Play the line | deck | 16 | C6 quiet action |
| `classroom.check.question` | {check prompt} | field:`check.get.stimulus.prompt` | 120 | C7 |
| `classroom.check.option` | {choice text} | field:`check.get.stimulus.choices[]` (`selection` format) | 60 | C7 radio row, 2–8 |
| `classroom.check.item` | {item label} | field:`check.get.stimulus.items[].label` (`verification` format) | 60 | C7 checklist row, 1–24 |
| `classroom.check.primary` | Check answer | deck | 16 | C7 filled, all three formats |
| `classroom.check.edit` | Edit answer | deck | 16 | C7 quiet, `text` format |
| `classroom.check.clear_choice` | Clear choice | deck | 16 | C7 quiet, `selection` format |
| `classroom.check.clear_ticks` | Clear ticks | deck | 16 | C7 quiet, `verification` format |
| `classroom.check.correct` | That is right. {why} | deck + field:`attempt.submit.criteria[].observed` | 120 | C7 verdict |
| `classroom.check.wrong` | Not quite. {why} | deck + field:`attempt.submit.criteria[].observed` | 120 | C7 verdict |
| `classroom.check.retry` | Try again | deck | 12 | C7 primary after a wrong verdict |
| `classroom.check.next` | Next section | deck | 16 | C7 primary after a correct verdict |
| `classroom.check.choices` | Choices | deck | 16 | C7 group name, `selection` format |
| `classroom.check.checklist` | Checklist | deck | 16 | C7 group name, `verification` format |
| `classroom.check.answers` | Answers | deck | 16 | C7 group name, `text` format |
| `classroom.check.criteria` | Grading criteria | deck | 24 | C7 verdict criteria group name |
| `classroom.check.hint` | Ask for a hint | deck | 24 | C7 quiet action, beside the check |
| `classroom.check.hint_pending` | Asking the tutor for a hint. | deck | 32 | C7 quiet status while the assist is recorded |
| `classroom.check.hint_recorded` | Hint recorded. The tutor has answered in the tutor panel. | deck + field:`lesson.assist.evidence_class` | 64 | C7 quiet status after the hint |
| `classroom.check.hint_failed` | The hint could not be recorded. Try again. | deck | 48 | C7 quiet status on a refused assist |
| `classroom.practice.expressions` | Expressions to practise | deck | 32 | C8 tutor rail group name |
| `classroom.practice.transcript` | Practice transcript | deck | 28 | C8 tutor rail transcript group name |
| `classroom.evidence.title` | Evidence | deck | 12 | C8, C9 |
| `classroom.evidence.count` | {n} of {total} checks recorded | computed:`count(attempt_count > 0)` over field:`lesson.page.checks[]`, total = that array's length | 32 | C8 |
| `classroom.evidence.empty` | No checks recorded yet. | deck | 28 | C8 empty |
| `classroom.aside.next` | Next up: {next section} | field:`library_item.next_step.label` | 48 | C8 |
| `classroom.aside.tutor` | Ask the tutor | deck | 16 | C8 quiet action |
| `classroom.nochat.title` | This section has no chat yet | deck | 32 | C7 region |
| `classroom.nochat.body` | Start a fresh run to open a chat for this section. | deck | 60 | C7 region |
| `classroom.nochat.action` | Start a fresh run | deck | 20 | C7 filled |
| `classroom.complete.title` | Section finished | deck | 20 | C7 region |
| `classroom.complete.body` | Your check is recorded. | deck | 28 | C7 region |
| `classroom.complete.body.unrecorded` | Your check passed, but nothing was recorded for it, so it does not count toward your evidence yet. | deck | 100 | C7 region |
| `classroom.complete.action` | Back to the path | deck | 20 | C7 filled |
| `classroom.loading` | Opening this section. | deck | 24 | C4 |
| `classroom.error.title` | This section could not be read | deck | 32 | C7 region |
| `classroom.error.body` | Your attempt is unchanged. Try again. | deck | 44 | C7 region |
| `classroom.error.action` | Try again | deck | 12 | C7 quiet |
| `classroom.offline.title` | You are offline | deck | 20 | C7 region |
| `classroom.offline.body` | The page you opened last is still here. Checking an answer waits. | deck | 70 | C7 region |
| `classroom.offline.action` | Try again | deck | 12 | C7 quiet |
| `classroom.game.xp` | {n} XP | field:`engagement.read.xp_total`, Game mode only | 12 | C11 chip |
| `classroom.challenge.title` | Field Challenge | deck, Game mode only | 24 | C11 |
| `classroom.challenge.primary` | Try it yourself | deck | 20 | C11 filled, Game mode only |
| `classroom.tutor.no_chat_return` | This lesson has no chat to return to yet. | deck | 48 | `00-header.js:867` · the bound-lesson tutor path |
| `classroom.tutor.not_connected` | This lesson is not connected to a chat right now. | deck | 56 | `00-header.js:870` · no live chat for the section |
| `classroom.tutor.update_app` | Update Hermes Desktop to resume a bound lesson. | deck | 52 | `00-header.js:873` · host too old to resume |
| `classroom.tutor.open_failed` | The saved lesson chat could not be opened from this desktop. The section is still available to read. | deck | 110 | `00-header.js:883` · chat open refused, section still readable |
| `classroom.tutor.title` | Coursebook lesson | deck | 20 | `00-header.js:937` · the chat's own name |
| `classroom.tutor.bind_failed` | {code}: {message} | deck | 120 | `00-header.js:961` · the bind refused, the backend's own words kept |
| `classroom.tutor.no_course` | No course was read for this action. | deck | 40 | `00-header.js:984` · no course in context |
| `classroom.tutor.no_objective` | This course has no current objective yet; approve the plan first. | deck | 72 | `00-header.js:987` · no objective to open |
| `classroom.tutor.resumed` | Resumed the bound lesson chat. | deck | 36 | `00-header.js:1024` · resumed |
| `classroom.tutor.no_saved_chat` | There is no saved lesson chat for this section yet. Read the section below, then start a new lesson when you are ready. | deck | 130 | `00-header.js:1033` · no saved chat |
| `classroom.tutor.ready` | The lesson is ready. Your section is open below. The chat becomes this lesson’s chat when you send your first message. | deck | 140 | `00-header.js:1053` · lesson opened |

`classroom.tutor.*` is the one family `GAP-40` exists for: `CP-031b` correctly did not row these
(it is the Classroom/course-detail tutor path, not one of the four swept surfaces), and §5 of the
chrome sweep used to say `CP-023-classroom.md` inventoried them. It does not — `CP-023` carries the
deck's own no-chat state, whose wording differs. These rows are the shipped wording; whether the
code moves to the deck's `classroom.nochat.*` wording instead is a CP-023 question, recorded in the
handoff.

**Worked L0 example.** The four `classroom.line.*` rows above show one real line from the bundled
pack `bundled/packs/japanese-affection-context-l0/content/section-01-two-ways.md` (Dialogue B),
whose kana, romaji and English meaning are the pack's own; the narration file's `text_equivalent`
in the same pack repeats them. The kana and the romaji are read, not re-authored here.
`好(す)き` is the ruby form of 好き; that reading is authored by this deck because the pack carries
no ruby, and the ruby is omitted for any pack that carries no reading. The screen renders the
lesson's authored line; this example is the fixture that proves the three scaffolds fit.

---

## 5. Course home (`R-MAP`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `course.back` | Back to {parent} | deck (destination label) | 32 | M2 |
| `course.title` | {course title} | field:`library_item.title` | 60 | M3 |
| `course.subject` | {subject label} | field:`library_item.subject_label` (CP-005) | 24 | M3 |
| `course.hero.credit` | {art credit} | art:`license.per_artifact[].attribution` | 40 | M4 mat, micro |
| `course.route.label` | Your route | deck | 16 | M5 (screen-reader group name) |
| `course.node.current` | You are here | deck | 16 | M5 current node |
| `course.node.done` | Done | deck | 8 | M5 completed node |
| `course.node.next` | Next | deck | 8 | M5 next node |
| `course.node.locked` | Opens after the section before it | deck | 36 | M5, only where the plan gates it |
| `course.continue.title` | Continue | deck | 12 | M6 heading |
| `course.next.label` | {next step} | field:`library_item.next_step.label` | 48 | M6 filled plate |
| `course.evidence.title` | Evidence | deck | 12 | M7 |
| `course.evidence.count` | {n} of {total} sections have evidence | field:`library_item.sections_done` + field:`library_item.sections_total` (CP-005) | 44 | M7 |
| `course.others.title` | Your other courses | deck | 24 | M8 |
| `course.others.row` | {title} · {next step} | field:`library_item.title` + field:`library_item.next_step.label` | 60 | M8 rows |
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
| `course.end.practice` | {n} checks recorded | field:`library_item.checks_recorded` (CP-005), used only when field:`library_item.sections_total` is 0; renders `1 check recorded` for one | 28 | M6, the close of a course whose objectives are all practice |
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
| `lab.palette.role` | {role name} | contract:`color.role` key in `contracts/cb.tokens.v3.json` | 20 | S8 |
| `lab.palette.ratio` | {ratio}:1 | computed:`contrast(pair)` from the contract's two role values | 10 | S8 |
| `lab.type.micro` | Caption · 12/16.2 · 4 of 5 checks recorded | contract:`type.scale.caption` + contract:`type.line_height.caption` | 48 | S9 |
| `lab.type.label` | Meta · 14/19.6 · Check answer | contract:`type.scale.meta` + contract:`type.line_height.meta` | 48 | S9 |
| `lab.type.body` | Body · 16/24 · A sentence of real lesson text. | contract:`type.scale.body` + contract:`type.line_height.body` | 56 | S9 |
| `lab.type.lead` | Lead · 20/27 · A sentence that opens the lesson. | contract:`type.scale.lead` + contract:`type.line_height.lead` | 56 | S9 |
| `lab.type.title` | Heading · 29.69/34.14 · Japanese Lantern District | contract:`type.scale.heading` + contract:`type.line_height.heading` | 52 | S9 |
| `lab.type.display` | Display · 55.47/56.58 · Your field library | contract:`type.scale.display` + contract:`type.line_height.display` | 48 | S9 |
| `lab.type.section` | Section · Your route | deck (v2 lab) | 20 | v2 lab only |
| `lab.material.grain` | Paper grain | deck | 16 | S10 |
| `lab.material.wood` | Wood ledge | deck | 16 | S10 |
| `lab.material.elevation` | Elevation | deck | 16 | S10 |
| `lab.material.radius` | Radius | deck | 16 | S10 |
| `lab.motion.static` | Motion off: poses hold still. | deck | 36 | S? reduced-motion state |
| `lab.forced` | System colours. | deck | 20 | S? forced-colors state |
| `lab.text200` | Text at 200%. | deck | 20 | S? text-200 state |

---

## 7. Homework (`R-WORK`)

The take-home surfaces (the classroom's homework sheet, the Notebook's own actions and the Parent
Studio sheet) read these. `GAP-31` found the two enum→copy maps and the three sheet guards with no
row anywhere; the words are shipped at `desktop/src/95-studio.js`, which is why each row's Where
cell carries that citation rather than a v3 region code.

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `hw.state.proposed` | Planned | `field:`homework.read.task.state`` == `proposed` | 12 | `95-studio.js:1851` · `CB_HOMEWORK_STATE_WORD` |
| `hw.state.self_reported_done` | Done — you recorded it | `field:`homework.read.task.state`` == `self_reported_done` | 24 | `95-studio.js:1852` · `CB_HOMEWORK_STATE_WORD` |
| `hw.state.parent_reported_done` | Done — a parent recorded it | `field:`homework.read.task.state`` == `parent_reported_done` | 28 | `95-studio.js:1853` · `CB_HOMEWORK_STATE_WORD` |
| `hw.state.skipped` | Skipped | `field:`homework.read.task.state`` == `skipped` | 12 | `95-studio.js:1854` · `CB_HOMEWORK_STATE_WORD` |
| `hw.state.expired` | Expired | `field:`homework.read.task.state`` == `expired` | 12 | `95-studio.js:1855` · `CB_HOMEWORK_STATE_WORD` |
| `hw.state.skipped_note` | This one is closed as skipped. A fresh task can be taken with you from another lesson. | deck | 96 | `95-studio.js:2931` · the skipped sheet's own line |
| `hw.kind.real_world_use` | Use it for real | `field:`homework.read.task.task_kind`` == `real_world_use` | 16 | `95-studio.js:1859` · `CB_HOMEWORK_KIND_WORD` |
| `hw.kind.observe` | Notice it | `field:`homework.read.task.task_kind`` == `observe` | 12 | `95-studio.js:1860` · `CB_HOMEWORK_KIND_WORD` |
| `hw.kind.label` | Label it | `field:`homework.read.task.task_kind`` == `label` | 12 | `95-studio.js:1861` · `CB_HOMEWORK_KIND_WORD` |
| `hw.kind.practice` | Say it aloud | `field:`homework.read.task.task_kind`` == `practice` | 16 | `95-studio.js:1862` · `CB_HOMEWORK_KIND_WORD` |
| `hw.kind.make` | Make it | `field:`homework.read.task.task_kind`` == `make` | 12 | `95-studio.js:1863` · `CB_HOMEWORK_KIND_WORD` |
| `hw.kind.teach_back` | Tell someone | `field:`homework.read.task.task_kind`` == `teach_back` | 16 | `95-studio.js:1864` · `CB_HOMEWORK_KIND_WORD` |
| `hw.sheet.guard.word` | This task would print a word a take-home sheet must not carry, so it is not shown. | deck | 94 | `95-studio.js:2028` · sheet guard, refusal not truncation |
| `hw.sheet.guard.steps` | A field card carries at most three steps, so this task is not shown. | deck | 72 | `95-studio.js:2031` · sheet guard, refusal not truncation |
| `hw.record.already_reported` | This task already carries a report; it cannot be reported twice. | deck | 70 | `95-studio.js:2932` · the second report is refused |

`hw.state.assigned` is **not** rowed here. `GAP-31` asks the owner to choose its word (the shipped
map has none for `assigned`); the proposed row is stated in the handoff for CP-001g, not guessed.

---

## 8. Game (`R-PLAY`)

The field journal on the Home route renders one state word per card from `CB_COPY.state`, and
`Game` is the only surface that prints five of these seven words. One map, one wording: a second
literal for any of them on a rendered surface is refused by
`tests/test_desktop_learner_copy.py`, so these rows are the map's own words, not a Game re-voice.

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `game.state.not_started` | Not started | deck | 12 | `00-header.js:65` · `CB_COPY.state` |
| `game.state.introduced` | Started | deck | 12 | `00-header.js:66` · `CB_COPY.state` |
| `game.state.independent_evidence` | Independent evidence | deck | 24 | `00-header.js:60` · `CB_COPY.state` |
| `game.state.delayed_evidence` | Delayed evidence | deck | 20 | `00-header.js:68` · `CB_COPY.state` |
| `game.state.review_due` | Review due | deck | 12 | `00-header.js:69` · `CB_COPY.state` |
| `game.state.needs_review` | Could not be written | deck | 20 | `00-header.js:73` · `CB_COPY.state` |
| `game.state.overridden` | Moved on without a grade | deck | 28 | `00-header.js:74` · `CB_COPY.state` |
| `game.state.unknown` | State not recorded | deck | 20 | `00-header.js:98` · `CB_COPY.stateWord` fallback |
| `game.journal.stamped` | Stamped | deck | 12 | `30-home.js:5192` · journal card, earned state |
| `game.journal.overflow` | The journal stops at {shown} cards. The rest are on the course page. | deck | 72 | `30-home.js:5064` · new sentence; `rows.slice(0, 12)` truncates with no words today |

---

## 9. World Studio (`R-WORLD`)

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `world.plates.overflow` | Only the first six motifs and the first six to avoid are kept. | deck | 72 | `97-world.js:468-469` · new sentence; both direction lists are sliced at six with no words today |

---

## 10. Parent Studio (`R-STUDIO`)

The Parent Studio detail page is the largest shipped surface with no deck section. These rows cover
the approval-invalidation banner and the plan-check reasons (`GAP-38`), the fine-tune editor and its
two dialogs (`GAP-33`), the lesson-set export gate (`GAP-34`), the tab-limit overflow note
(`GAP-35`) and the shell's contract-envelope error where a Studio read paints it (`GAP-39`).
`GAP-32`'s independence family is **not** rowed: the owner must choose whether it survives as one
family or collapses to a badge plus two claims, so the rows are stated in the handoff instead.

| id | Text | Source | Cap | Where |
|---|---|---|---|---|
| `studio.banner.title` | Changes need review | deck | 24 | `95-studio.js:3756` · `StudioReviewBanner`, derived from the approval row |
| `studio.banner.reason.plan_edited` | You edited the plan after approving the lesson set. | `field:`parent.blueprint.read.approval.invalidated_reason`` == `plan_edited` | 60 | `95-studio.js:3743` · `APPROVAL_INVALIDATION_COPY` |
| `studio.banner.reason.content_changed` | The generated pages changed after you approved them. | `field:`parent.blueprint.read.approval.invalidated_reason`` == `content_changed` | 60 | `95-studio.js:3744` · `APPROVAL_INVALIDATION_COPY` |
| `studio.banner.reason.course_edited` | You changed the course title or goal after approving the lesson set. | `field:`parent.blueprint.read.approval.invalidated_reason`` == `course_edited` | 80 | `95-studio.js:3745` · `APPROVAL_INVALIDATION_COPY` |
| `studio.banner.reason.replaced` | A newer approval replaced this one. | `field:`parent.blueprint.read.approval.invalidated_reason`` == `replaced` | 40 | `95-studio.js:3746` · `APPROVAL_INVALIDATION_COPY` |
| `studio.banner.reason.unknown` | The lesson set you approved no longer matches the current pages. | deck | 70 | `95-studio.js:3761` · unknown-reason fallback |
| `studio.banner.export_approve` | Approve the current lesson set before exporting. | deck | 60 | `95-studio.js:3767` · no blocked reason yet |
| `studio.review.blocked` | Export is blocked ({reason}). | deck + field:`parent.blueprint.read.export.blocked_reason` | 60 | `95-studio.js:3766`; `95-studio.js:7392` · one sentence, two renderings |
| `studio.review.blocked_unknown` | Export is blocked and the backend returned no reason string. | deck | 60 | `95-studio.js:4646` · the honest no-reason branch |
| `studio.check.alignment` | whether each objective matches the goal | deck | 50 | `95-studio.js:3869` · `PLAN_CHECK_LABELS` |
| `studio.check.sources` | whether each claim has a source that was actually read | deck | 60 | `95-studio.js:3870` · `PLAN_CHECK_LABELS` |
| `studio.check.structure` | whether the units, objectives and checks fit together | deck | 60 | `95-studio.js:3871` · `PLAN_CHECK_LABELS` |
| `studio.check.schedule` | whether the schedule and time estimates add up | deck | 50 | `95-studio.js:3872` · `PLAN_CHECK_LABELS` |
| `studio.check.policy` | whether the plan follows the recipe and its limits | deck | 50 | `95-studio.js:3873` · `PLAN_CHECK_LABELS` |
| `studio.revision.chip.edited` | Edited | deck | 12 | `95-studio.js:4525` · `FINE_TUNE_CHIP.edited` |
| `studio.revision.chip.needs_review` | Could not be written | deck | 24 | `95-studio.js:4526` reads `CB_COPY.state.needs_review` · the word ships at `00-header.js:73` |
| `studio.revision.chip.approved` | Approved | deck | 12 | `95-studio.js:4527` · `FINE_TUNE_CHIP.approved` |
| `studio.revision.edited_note` | This objective or section was changed by the course author; one revision row records it. | deck | 96 | `95-studio.js:4531` · `FINE_TUNE_CHIP_COPY` |
| `studio.revision.needs_review_note` | This change is stored and readable, but nobody has approved it. Export and any new check wait for approval. | deck | 120 | `95-studio.js:4532-4533` · `FINE_TUNE_CHIP_COPY` |
| `studio.revision.approved_note` | This change was approved with the lesson set it belongs to. It is still not an independent validation. | deck | 120 | `95-studio.js:4534-4535` · `FINE_TUNE_CHIP_COPY` |
| `studio.finetune.no_section` | This course serves no authored section identity, so one section cannot be revised or regenerated from here. `lesson.revise` and `lesson.regenerate` are keyed on the `section_id` and `page_hash` that `parent.blueprint.read` reports in `sections[]`; a pack-backed course is composed from its pack and reports none. Nothing here invents a section id or a digest. | deck | 400 | `95-studio.js:4539-4542` · `FINE_TUNE_SECTION_ACTIONS_GAP`; the method names are shipped and are flagged in the handoff |
| `studio.finetune.scope` | 1 section: {title} | deck | 60 | `95-studio.js:4594` · `fineTuneScopeLine` |
| `studio.review.title` | Review changes | deck | 16 | `95-studio.js:4603` · review tab |
| `studio.review.error` | The pending changes could not be read, so nothing here claims the course has none. | deck | 88 | `95-studio.js:4616` · review read failure |
| `studio.review.loading` | Reading the pending changes. | deck | 32 | `95-studio.js:4617` · review read in flight |
| `studio.review.clean` | The approved lesson set matches the pages shown, so export is available. | deck | 80 | `95-studio.js:4643` · review clean state |
| `studio.review.empty` | No fine-tune change is waiting for review. | deck | 48 | `95-studio.js:4652` · review empty state |
| `studio.review.order` | plan {id} | deck | 24 | `95-studio.js:4666` · review diff header |
| `studio.review.changed` | Changed: {change} | deck | 40 | `95-studio.js:4684` · review diff row |
| `studio.review.now` | Now: {value} | deck | 28 | `95-studio.js:4689` · review diff row |
| `studio.review.before` | Before: {value} | deck | 32 | `95-studio.js:4693` · review diff row |
| `studio.review.row.lesson_page` | lesson page | deck | 16 | `95-studio.js:4711` · review row kind |
| `studio.review.row.changed` | {path} — changed: {change} | deck | 80 | `95-studio.js:4728` · review row |
| `studio.review.row.page` | page {n}… | deck | 16 | `95-studio.js:4739` · review row page marker |
| `studio.review.row.consequence` | {n} stored attempt(s) reference this section; the edit was confirmed against that consequence. | deck | 160 | `95-studio.js:4734` · stored-revision review row |
| `studio.finetune.move.blocked` | That move would put one unit’s objectives behind a later unit, so the stored order was kept. | deck | 110 | `95-studio.js:4896` · `prerequisite_order_conflict` |
| `studio.finetune.undo.stale` | A later change landed after that revision, so the undo would overwrite it; nothing was written. | deck | 110 | `95-studio.js:4899` · stale undo refused |
| `studio.finetune.undo.done` | That structural change was already undone. | deck | 48 | `95-studio.js:4901` · undo already applied |
| `studio.finetune.undo.none` | This plan has no structural change to undo. | deck | 52 | `95-studio.js:4903` · nothing to undo |
| `studio.finetune.undo.draft` | The plan is not approved, so only a draft edit applies. | deck | 60 | `95-studio.js:4905` · draft-only undo |
| `studio.finetune.stale` | The course revision was refreshed; try again. | deck | 52 | `95-studio.js:4909` · stale revision |
| `studio.finetune.order_saved` | Order saved. {detail} | deck | 60 | `95-studio.js:4950-4955` · order written |
| `studio.finetune.undone` | Undid the last structural change. Stored order: {order} | deck | 72 | `95-studio.js:5013` · undo written |
| `studio.finetune.no_changes` | Nothing changed yet. | deck | 20 | `95-studio.js:5128` · editor untouched |
| `studio.finetune.no_page` | This section has no authored page yet, so there is no page digest to revise. | deck | 88 | `95-studio.js:5137` · no authored page |
| `studio.finetune.no_page_short` | Use “Regenerate this section” to author it first. | deck | 60 | `95-studio.js:5138` · the same state, short form |
| `studio.finetune.consequence_error` | {n} learner attempt(s) already reference this section. {consequence} Confirm to store the edit. | deck | 160 | `95-studio.js:5190-5191` · refusal toast, first rendering |
| `studio.finetune.saved_page` | Section page saved as a new revision that needs review before export. | deck | 76 | `95-studio.js:5206` · saved page |
| `studio.finetune.saved_page_note` | Every stored attempt and the previous page version are untouched. | deck | 72 | `95-studio.js:5207` · saved page, second line |
| `studio.finetune.saved_meta` | Section metadata saved. The edited objective is recorded as a revision that needs review before export. | deck | 120 | `95-studio.js:5211` · saved metadata |
| `studio.finetune.queued` | Queued regenerating 1 section: {section}. Other sections, their media and every attempt are untouched. | deck | 130 | `95-studio.js:5269` · regeneration queued |
| `studio.finetune.title` | Fine-tune this approved course | deck | 32 | `95-studio.js:5288` · section heading |
| `studio.finetune.undo` | Undo last structural change | deck | 32 | `95-studio.js:5307` · quiet action |
| `studio.finetune.note` | Reorder or retitle an objective and the change is written to storage as a revision that needs review; lesson pages, checks and attempts are not rewritten. Every move is sent with the full order, so the order you see is the order the backend returned. | deck | 260 | `95-studio.js:5318-5320` · editor note |
| `studio.finetune.order_label` | {n} in stored order | deck | 24 | `95-studio.js:5339` · order label |
| `studio.finetune.move_label` | {title}. {note}. Press Alt+ArrowUp or Alt+ArrowDown to move it. | deck | 96 | `95-studio.js:5356` · row action label |
| `studio.finetune.shortcut` | Alt+ArrowUp Alt+ArrowDown | deck | 28 | `95-studio.js:5357` · key hint |
| `studio.finetune.page.none` | no page yet | deck | 16 | `95-studio.js:5387` · page marker |
| `studio.finetune.page.version` | page v{n} | deck | 16 | `95-studio.js:5388` · page marker |
| `studio.finetune.no_authored_section` | no authored section | deck | 24 | `95-studio.js:5394` · section marker |
| `studio.finetune.move.up` | Move up | deck | 12 | `95-studio.js:5407` · reorder action |
| `studio.finetune.move.down` | Move down | deck | 12 | `95-studio.js:5415` · reorder action |
| `studio.finetune.edit` | Edit section | deck | 16 | `95-studio.js:5422` · editor open |
| `studio.finetune.close` | Close editor | deck | 16 | `95-studio.js:5422` · editor close |
| `studio.finetune.regenerate` | Regenerate this section | deck | 24 | `95-studio.js:5434` · regenerate open |
| `studio.finetune.field.objective_title` | {name} title | deck | 40 | `95-studio.js:5449` · objective title field |
| `studio.finetune.field.objective_title_note` | Stored on the objective. The section page keeps its authored prose; a retitle is a plan revision that needs review. | deck | 140 | `95-studio.js:5451` · objective title note |
| `studio.finetune.field.title` | Section page title | deck | 24 | `95-studio.js:5461` · page title field |
| `studio.finetune.field.title_note` | Stored on the authored page through lesson.revise, fenced on the page digest this read served ({digest}…). The result is a new page revision that needs review. | deck | 170 | `95-studio.js:5464` · page title note |
| `studio.finetune.field.title_no_page` | This section has no authored page yet, so there is no digest to revise. Regenerate this section to author one. | deck | 120 | `95-studio.js:5465` · page title field, no page |
| `studio.finetune.field.evidence_target` | Evidence target | deck | 20 | `95-studio.js:5477` · evidence field |
| `studio.finetune.field.criteria` | Assessment criteria | deck | 24 | `95-studio.js:5505` · criteria field |
| `studio.finetune.field.criteria_note` | One criterion per line. Saving replaces the objective’s criteria. | deck | 80 | `95-studio.js:5507` · criteria note |
| `studio.finetune.field.criteria_unserved` | This build was not served the objective’s current criteria, so this field starts empty. | deck | 96 | `95-studio.js:5508` · unserved criteria |
| `studio.finetune.field.criteria_keep` | Enter the criteria you want stored; leaving it untouched keeps whatever storage holds. | deck | 110 | `95-studio.js:5509` · unserved criteria, instruction |
| `studio.finetune.save` | Save section | deck | 16 | `95-studio.js:5526` · editor primary |
| `studio.finetune.unsaved_title` | Unsaved changes | deck | 20 | `95-studio.js:5539` · editor status line |
| `studio.finetune.editor_note` | The section’s segment bodies are authored by the lessons job; this editor changes the page title and the objective metadata, and lesson.revise stores a new page revision that needs review before export. | deck | 240 | `95-studio.js:5548` · editor note |
| `studio.finetune.confirm` | Confirm the evidence consequence | deck | 40 | `95-studio.js:5554` · first dialog, title |
| `studio.finetune.consequence_dialog` | {n} stored attempt(s) reference this section. {consequence} | deck | 120 | `95-studio.js:5560` · in-panel consequence, second rendering |
| `studio.finetune.confirm_action` | Confirm and save | deck | 20 | `95-studio.js:5568` · first dialog, primary |
| `studio.finetune.keep_editing` | Keep editing | deck | 16 | `95-studio.js:5575` · first dialog, quiet |
| `studio.dialog.unsaved_title` | Unsaved section changes | deck | 24 | `95-studio.js:5586` · second `role="alertdialog"` |
| `studio.dialog.unsaved_body` | Discard the unsaved changes to this section? | deck | 44 | `95-studio.js:5592` · second dialog, body |
| `studio.dialog.discard` | Discard changes | deck | 16 | `95-studio.js:5610` · second dialog, confirm |
| `studio.dialog.keep` | Keep editing | deck | 16 | `95-studio.js:5617` · second dialog, quiet |
| `studio.regen.estimate` | Regenerating this section costs about {low}–{high}, based on what writing lessons for this course has cost so far. The price for this section appears here once you queue it. | deck | 180 | `95-studio.js:5636-5638` · cost preflight; the arithmetic is SPEC-V3 §5.6 |
| `studio.regen.no_estimate` | We work out what one section costs when you queue it — this course has no earlier lesson run to go by yet. | deck | 120 | `95-studio.js:5639` · cost preflight, no history |
| `studio.regen.queue` | Queue regenerating 1 section | deck | 32 | `95-studio.js:5650` · preflight primary |
| `studio.regen.queued` | Queued {section} · job {job} | deck | 60 | `95-studio.js:5677` · queued result |
| `studio.regen.price` | This section costs {low}–{high} to regenerate. | deck + field:`lesson.regenerate.preflight.minimum_cost_usd` + field:`lesson.regenerate.preflight.maximum_cost_usd` | 48 | `95-studio.js:5684-5685` · the queued job's own price |
| `studio.tab.clipped` | clipped | deck | 8 | `95-studio.js:7223` · tab-limit badge |
| `studio.tab.clipped_note` | · the served text was clipped at the tab limit | deck | 56 | `95-studio.js:7231` · tab-limit note |
| `studio.gate.stale` | The course was updated elsewhere; press Approve this lesson set again. | deck | 72 | `95-studio.js:7284` · approve refused on a stale revision |
| `studio.gate.title` | Export gate | deck | 16 | `95-studio.js:7326` · gate heading |
| `studio.gate.row.plan` | Plan | deck | 8 | `95-studio.js:7331` · gate table row label |
| `studio.gate.row.approval` | Lesson set approval | deck | 24 | `95-studio.js:7332` · gate table row label |
| `studio.gate.row.approved_hash` | Approved content hash | deck | 24 | `95-studio.js:7334` · gate table row label |
| `studio.gate.row.current_hash` | Current content hash | deck | 24 | `95-studio.js:7338` · gate table row label |
| `studio.gate.row.final` | Final approval | deck | 20 | `95-studio.js:7343` · gate table row label |
| `studio.gate.note` | Approving the plan approved the outline and its activities. This gate is separate: it approves the generated lesson set by its content hash, and any later edit to the plan, the pages or the course title clears it. | deck | 240 | `95-studio.js:7347` · gate note |
| `studio.gate.approved_line` | Lesson set approved{when}{note} | deck + field:`parent.blueprint.read.approval.state` | 96 | `95-studio.js:7352-7354` · approval record, computed |
| `studio.gate.no_plan` | There is no approved plan to approve a lesson set for yet. | deck | 64 | `95-studio.js:7363` · no plan |
| `studio.gate.no_pages` | No generated pages exist yet, so there is nothing to approve. Generate the lessons from the Plan view first. | deck | 120 | `95-studio.js:7364` · no pages |
| `studio.gate.unsupported` | This backend does not implement parent.final.approve yet. | deck | 60 | `95-studio.js:7369` · backend without the method |
| `studio.gate.approving` | Approving the lesson set | deck | 28 | `95-studio.js:7378` · approve in flight |
| `studio.gate.approve` | Approve this lesson set | deck | 24 | `95-studio.js:7378` · gate primary |
| `studio.gate.available` | Export is available: the approved lesson set matches the pages shown. | deck | 76 | `95-studio.js:7384` · gate open |
| `studio.gate.backend_reason` | Backend reason: {reason}. | deck + field:`parent.blueprint.read.export.blocked_reason` | 60 | `95-studio.js:7397` · the backend's own word, verbatim |
| `studio.gate.format.archive` | Pack archive (parent guide, learner pages, answer guide). | deck | 64 | `95-studio.js:7407` · format note |
| `studio.gate.format.pdf` | Printable PDF: selectable text, low-ink layout, no color-only answers. | deck | 76 | `95-studio.js:7413` · format note |
| `studio.gate.export` | Export the approved files | deck | 28 | `95-studio.js:7419` · gate primary |
| `studio.gate.minima` | The pack minima reported these problems: | deck | 44 | `95-studio.js:7432` · minima refusal |
| `studio.gate.files` | Exported files | deck | 16 | `95-studio.js:7446` · artifact list heading |
| `studio.gate.export_line` | Export {export_id} · {when} · content hash {hash} | deck | 96 | `95-studio.js:7449` · artifact row, computed |
| `studio.gate.pack_note` | The pack carries parent guide, learner pages and answer guide. Narration stays an audio role, so an authored text script is not exported as a narration file: it is the Audio & visuals tab and part of the parent guide. | deck | 240 | `95-studio.js:7465` · pack note |
| `studio.gate.privacy_note` | Exported files never include attempts, notebook notes, reflections, transcripts or provider settings. | deck | 110 | `95-studio.js:7467` · privacy note |
| `studio.gate.download.pdf` | Download PDF | deck | 16 | `95-studio.js:7499` · download action |
| `studio.gate.download.archive` | Download pack archive | deck | 24 | `95-studio.js:7501` · download action |
| `studio.gate.download.record` | Download export record | deck | 24 | `95-studio.js:7502` · download action |
| `studio.gate.artifact_note` | Session-bound, expiring link served by this host’s artifact route. A filesystem path never leaves the backend. | deck | 130 | `95-studio.js:7510` · artifact note |
| `studio.gate.artifact_short` | Host artifact route. | deck | 24 | `95-studio.js:7511` · artifact note, short form |

---

## 11. Words this deck does not use


The v2 honesty rules stay. No string claims a public score, a ranking, a crowd opinion, a
competence state, or a count of people. Where a concept showed one of those, the row above
replaces it with a recorded fact or drops it: a card says how many sections are done, a pack says
which checks it passed, and a lesson says how many checks are recorded. The specific words the
screens may not render, in any form, are the ones for public scores, score marks, crowd opinion, a
headcount of people, and a competence percentage. `docs/EXPERIENCE-QUALITY-BAR.md` §2.5 is the
rule; this deck is its wording.
