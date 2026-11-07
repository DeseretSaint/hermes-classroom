# Coursebook Desktop — adversarial UI/UX audit, round 3 (H-80)

**Verdict.** Coursebook now looks like a *designed* product at the individual-card level, and the
copy is far better than a dev shell: empty states explain themselves, the plan view warns that
estimates are not promises, the check copy says "first try, no hints". What still breaks the
hackathon read is not styling — it is **density, duplication, and machine language**. Three
screens (Library, Parent Studio, All Courses) are walls of identical rows; section headers print
raw enums (`not_started · production`, `missing`); and a judge's first 3 seconds at 1049 px hit a
426 px-wide pane set in 13 px body text under 9.9 px labels. Contrast is clean and nothing
overflows at 460 px, so this is a *hierarchy and data-hygiene* problem, not a colour problem.

**Scope.** Coursebook route and pane only (`[data-cb-route]`). Host chrome not assessed and not
proposed for change. Read-only: no product, contract, or test file was edited.

## Method

| item | value |
|---|---|
| rig | `HERMES_HOME=/home/deseretsaint/.hermes/coursebook-test-h64/home` |
| CDP | `127.0.0.1:9338`, single page `http://127.0.0.1:5174/#/coursebook` |
| window | 1049 × 1149 CSS px (host zoom 0.896, dpr 0.896) |
| plugin sha256 | `d61bc03b804c0d996dd4fc84eab5478c87e9aa44131e37fa85829b265ca80790` (installed copy) |
| repo copy sha256 | `c01eebc942baaef738e1716093004d6332109203467368973d2a98a1d2a73008` (7-line diff; installed copy is what was measured) |
| widths | live 1049, then `Emulation.setDeviceMetricsOverride` at 900 and 460 CSS px |
| theme | **dark only** — the host theme toggle lives outside `#/coursebook`; `data-cb-scope` stayed `dark` in every capture |
| capture | `Page.captureScreenshot` + `measure()` (contrast, clipping, overflow, tap targets, headings) per width |
| evidence | `audit/ux/round3/*.png` + `audit/ux/round3/captures.json` (17 surfaces × 3 widths = 51 frames) |

`captures.json` carries, per surface: route/destination, visible headings, first 2 000 chars of
pane text, the visible control list, the three screenshot paths, and the measured metrics.

## Evidence map

| # | surface | shot prefix | route / view | visible heading | primary action |
|---|---|---|---|---|---|
| 01 | Field Desk home | `01-field-desk` | `#/coursebook`, dest `courses` | H3 *Greet café staff and open the interaction politely* | **Start the lesson** |
| 02 | All courses | `02-all-courses` | dest `courses`, list | none as H1; rows are H3 | *Open* per row |
| 03 | All courses, no results | `03-all-courses-empty-search` | same | none | **Clear search** |
| 04 | Library | `04-library` | dest `library` | **none (0 headings)** | *Preview* / *Import pack* |
| 05 | Import pack | `05-library-import-pack` | dialog over Library | *Import a pack* | **Choose folder…** |
| 06 | College syllabus intake | `06-library-syllabus-intake` | dialog over Library | *Use my college syllabus* | **Choose a syllabus file** |
| 07 | Parent Studio | `07-parent-studio` | dest `studio` | **none (0 headings)** | *Open plan* |
| 08 | New course step 1 | `08-new-course-step1` | inline step | H2 *What do you want to make?* | **Continue** (disabled) |
| 09 | New course step 1 selected | `09-new-course-step1-selected` | inline step | H2 *What do you want to make?* | **Continue** |
| 10 | New course step 2 | `10-new-course-step2` | inline step | H2 *What should it cover?* | **Continue** |
| 11 | Plan review / approval | `11-plan-review` | dest `courses`, plan draft | H2/H3 *Find relative minors on the circle of fifths* | **Review and approve the plan** |
| 12 | Course detail overview | `12-course-detail` | dest `courses` | H2/H3 *Order coffee in Japanese* | **Start lesson** |
| 14 | Notebook view | `14-tab-notebook` | via `View` combobox | H2 *Order coffee in Japanese* | *Go to the current lesson* |
| 15 | Quizzes view | `15-tab-quizzes` | via `View` combobox | H2 *Order coffee in Japanese* | filters only |
| 16 | Plan view | `16-tab-plan` | via `View` combobox | H2 *Order coffee in Japanese* | **Open the first section** |
| 19 | Section page, Textbook only | `19-section-textbook` | Japanese-affection legacy lesson | H2 lesson title | **Start a fresh run** |
| 22 | Section page, second visit | `22-section-legacy` | identical render | H2 lesson title | **Start a fresh run** |

Guided and Field Quest were **reached live** at 15:44 MST on the Order-coffee section and their
text was read directly (Guided: `Step 1 of 5 … Back / Continue`; Field Quest:
`FIELD QUEST · 0 independent · 0 due · 5 missions, 1 checkpoint`). On every later visit to the same
section the switcher offered *Textbook* only, so no clean screenshot of those two views exists.
That intermittency is finding **F3**, not a capture failure to hide.

## Findings, ranked

Legend: **[V]** visually wrong, **[F]** functionally broken, **[V+F]** both. Every line cites the
shot in `audit/ux/round3/` and the selector or text that proves it.

### P0 — kills the demo

**F1 [V+F] Library and Parent Studio are walls of the same row.** `04-library-live.png`,
`07-parent-studio-live.png`. Library pane text repeats *Kitchen fractions for a 9-year-old* 14× and
*Authored here* 15×, with 20 `Preview` buttons; Parent Studio repeats *Kitchen fractions for a
9-year-old · Lesson plan for a child · updated 1 d ago · Open plan* 14× verbatim. All Courses
(`02-all-courses-live.png`) shows the Japanese-affection course 3× each flagged `Source stale`.
First-3-seconds read: "the database is broken". Root cause is stored data (duplicate courses and
plans in `plugin-data/coursebook/data.db`, 12+ `Kitchen fractions` rows), but the UI has no
collapsing, grouping, or "N similar" affordance, so the defect is visible as a design failure.
Gate: a clean rig must render ≤1 row per course before any judge sees it.

**F2 [V+F] The `View` tab rail renders at 0 × 0 — Notebook / Quizzes / Plan / Evidence / Sources /
Export are invisible.** `12-course-detail-live.png`. DOM probe re-run at three widths on the
Order-coffee detail page — 1049, 900 and ~460 CSS px — returns the identical result:
`Overview=0x0 · Notebook=0x0 · Quizzes=0x0 · Plan=0x0 · Evidence=0x0 · Sources=0x0 · Export=0x0`
while a second copy of the same control measures `176x30` / `144x30` / `176x30`. The only visible
entry point is a *combobox* labelled `View · Overview` (at 1049 px: `@313,627`; at 900 px it sits
`@307,1511`, i.e. 1 500 px down the page and well below the fold). So every secondary surface is
either invisible or a dropdown below the fold — a judge will never find Notebook or Quizzes.
Either render the rail or delete the dead buttons.

### P1 — a judge notices these in the first minute

**F3 [F] The lesson-view switcher appears and disappears with no explanation.**
`19-section-textbook-live.png`. Same section, same session: at 15:44 the header read
`Lesson view · Textbook · Guided · Field Quest`; from 15:50 onward the same page reads
`View · Textbook` and offers no Guided or Field Quest. Nothing on screen says why a view vanished.
A demo that says "all three views" and then shows one is worse than a demo that says "this lesson
has a textbook view only".

**F4 [V] Raw machine enums and debug tokens are printed as UI.** Text dumps for `19`/`22`:
`COURSEBOOK · Greet café staff … · not_started · production · last opened 4 hr ago`, plus chips
reading `missing`, `needs_review`, `model_assessed`. `missing` also appears inline next to the
view row. These are contract vocabulary, not learner vocabulary, and they are the last thing
between Coursebook and "looks shipped".

**F5 [V] There is no H1 anywhere, and three screens have no heading element at all.**
Heading arrays in `captures.json`: Library `[]`, Parent Studio `[]`, All courses `[]`; Field Desk
has a single H3; course pages repeat the same string as H2 *and* H3
(`12-course-detail`: `H2:Order coffee in Japanese || H3:Order coffee in Japanese`). The screen
title on All courses / Library / Parent Studio is 11 px nav-level text, so a screen reader and a
skimming judge both lack an anchor.

**F6 [V] The type scale is a size too small for a 426 px pane.** Computed styles on the live pane:
masthead 24.8 px/600, primary button 13.12 px/650, body 13.12 px, secondary meta 11.52 px, nav
labels 11 px, all-caps eyebrow labels 9.92 px (`NEXT ·`, `SECTIONS`, `WITH EVIDENCE`). Contrast is
fine (0 failures measured at both widths) — the problem is that everything under the eyebrow tier
sits below comfortable reading size, so the pane reads as dense and administrative.

### P2 — real, but survivable

**F7 [V] A disabled primary button still looks enabled.** `08-new-course-step1-live.png`.
`[data-cb-slot=button][data-variant=default]` with text *Continue*: `disabled=true`,
`opacity: 0.5`, `background-color: rgb(74, 132, 254)`. At 50 % opacity a saturated blue button
over `--cb-paper:#0f141a` still reads as the thing to press.

**F8 [V] Library duplicates its own calls to action.** `04-library-live.png`: *Use my college
syllabus* and *Import pack* appear in the hero card and again in the toolbar (*Use my college
syllabus* / *Import a pack*), with two different labels for the same action (*Import pack* vs
*Import a pack*). Below it, *What we check / what we do not check* is a disclosure with no affordance.

**F9 [V+F] Transient generation reads as breakage.** At 15:44 the Order-coffee section read
`The check could not be opened.` and `This section has no teaching content yet.` with no spinner,
progress, or ETA — then later rendered a full lesson (`Example · Two phrases you will hear`,
`Explain · Why register matters`). `16-tab-plan-live.png` does carry the right sentence
("Research and drafting may take several minutes"), but the section page itself gives the judge an
error sentence with no recovery path.

**F10 [V] Tap targets below 20 px at 460 px.** `10-new-course-step2-w460.png`:
`Light 44×19`, `Steady 54×19`, `Intense 56×19`, `Survey 54×19` (12 sub-20 px targets on that
screen); `06-library-syllabus-intake-w460.png`: a 16 × 16 checkbox labelled *Acknowledge that the
extracted text goes to your model provider*.

### P3 — polish

**F11 [V] The first form a new user sees is a bike repair.** `10-new-course-step2-live.png`: the
course-name field's placeholder is *Bike tube replacement*, and the helper text lists
"Replace the tube on my road bike", "bike repair, Spanish, statistics". It is only placeholder
copy (the field value is empty), but it sets the tone of the product to bicycle maintenance.

**F12 [V] Jargon density.** `0 of 4 objectives have independent evidence`, `Say or write it`,
`evidence target`, `Source stale`, `Challenge out`. The vocabulary is internally consistent and
each term is defined somewhere, but a first-time judge meets four undefined terms above the fold.

## What is visually wrong vs what is functionally broken

* **Functionally broken (must fix):** F2 (0 × 0 view rail), F3 (views vanish), F9 (empty section
  state for a lesson that exists), F1's data half (duplicate courses/plans in the store).
* **Visually wrong (design fixes):** F4, F5, F6, F7, F8, F10, F11, F12 and F1's presentation half.
* **Working well and worth protecting:** zero horizontal overflow at 460 px, zero contrast failures
  in the route at 1049 and 460, zero clipped text, honest empty states ("No courses match your
  search · Your courses are still here"), the plan view's "estimates are planning aids, not
  promises", and the Field Quest line "Counts describe evidence the backend already recorded; they
  are not a score."

## Three signature visual moves

1. **Make the course a field card, not a row.** Every course gets a 16:9 cover block on
   `--cb-paper-raised` carrying its two-letter mark (the `OC` / `JA` / `FR` monogram already
   exists), the one-line objective in 17 px, and progress as a 4-segment path with the current
   segment filled in the accent. Library, All Courses and Parent Studio then read as a shelf of
   distinct objects instead of 14 identical text rows, and duplicate data becomes visually obvious
   instead of visually fatal.
2. **One evidence ladder, drawn once.** Replace `not_started · production · 0 of 4 objectives have
   independent evidence` with a single three-rung ladder per section — *Not started → Practised →
   On your own* — filled by state colour with the raw value in a tooltip. Same information, no
   enums on the surface, and the learner can see what "independent evidence" means without a
   glossary.
3. **A real segmented view switch with previews.** Replace the 0 × 0 tab rail and the bare
   `View · Textbook` combobox with three always-visible segments — *Textbook / Guided / Field
   Quest* — each with a 24 px mini-thumbnail of its layout shape; disabled segments stay visible
   and say why ("needs a sequenced lesson"). That turns the strongest idea in the product into
   something a judge can see in three seconds.

*No host-chrome change is proposed; all three moves live inside `[data-cb-route]`.*
