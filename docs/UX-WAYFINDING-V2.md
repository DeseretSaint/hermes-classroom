# H-86 — first-run wayfinding: make every next step obvious

Status: implemented on `h86-wayfinding` (base `origin/master` 36f9a1d, H-84 landed).
Scope: desktop presentation only. No backend, RPC, grading, pack-policy, permission or publication
change. Stored fields (`evidence_class`, binding status, plan state) are untouched.

## What changed, and why it needed no explanation

| Surface | Before | After | Why |
|---|---|---|---|
| First-run plate | eyebrow `New course`, heading `Learn something specific.`, promise about research, primary + secondary rows in arbitrary order | heading **What do you want to be able to do?**, support line **Name one goal, review the plan, then learn. Nothing is created until you approve the plan.**, one filled **Start with a goal** with `Next you choose how big the course is.`, then a 3-row numbered path | the question is the task; the numbers carry the sequence, so no tour and no current-step marker before a course exists |
| Plate frame | lamp top rule, `sdk.Button` with bespoke inline styling | flat field: 1px rule, 44px lamp primary, `h1`, seal | one product action primitive, one focal hierarchy |
| Alternate entries | `Use a course someone already made` + hint | **Use a course I already have** + hint; **Use my college syllabus** + `Your syllabus sets the scope. Coursebook writes its own lessons alongside it…` | each entry says what it opens, not what the product is |
| Route header | title + a second line of prose per destination (`Pick up where you left off, or open another course.`) | seal + **Coursebook** only | a sentence that explains the UI is removed; the screen below names the action |
| Destination navigation | host `SegmentedControl`, active state = fill | `CbDestinationNav`: **Courses / Library / Parent Studio** with `aria-current="page"`, 600 weight and a 2px lamp underline | selected state readable without colour; present on every top-level screen |
| New course (header) | `default` (filled) button, shown even on course detail | `secondary`, hidden on course detail and while the start plate is up | never a second competing primary |
| New course flow header | `STEP 1 OF 3` uppercase label, one heading | numbered spine `1 Size · 2 Goal · 3 Review` with `aria-current="step"`, `Step 1 of 3`, heading, and one line: `Next: name the goal and the course.` (`Next: review what will be created.`, `Create the course, then review the draft plan.`) | the step and the next decision are both on screen from layout and words |
| Step 1 | scope cards, `Selected`/`Choose` | scope **section rows** (unchanged rows), selected state in words, intro `Pick how much course you want. Nothing is created yet, and you can go back at any point.` | decision, not decoration |
| Step 2 | `How will you use it?`, name field unmarked | `What kind of course is this?` (recipe titles/descriptions state the kind of course), `Name this course (required)` | no internal enum, no unmarked requirement |
| Step 3 | paragraph about `course.create` + `enrolment` + job + model drafting | `Create course writes the course and one draft plan. The plan then opens here for you to approve, and no lesson is written until you do.` | names the real next action; never implies lessons exist |
| After create | result screen + `Open in Courses` (filled) beside the plan's own `Approve plan` | result copy `…Approve the plan to start the first lesson; no lesson is written before that.`; `Open in Courses` secondary, `Create another` text | one primary — the plan approval the learner came for |
| Section with no chat | sentence only when a runtime read answered; primary `Start the lesson` **plus** tertiary `Start a fresh run instead` | `This section has no lesson chat yet. Start one and send the first message to begin.` shown whenever nothing is bound; exactly one button, **Start a fresh run** | one run, one button; the sentence survives a failed runtime read |
| Desk / overview / course detail | `Start the lesson` | **Start a fresh run** (resume keeps `Resume the lesson`) | the Continue card and the section page name the same next action |

Banned copy audit: `Learn more`, `Get started`, `Click here`, `durable chat`, `chat binding`,
`session id`, `projection`, `evidence target`, `not_started`, `in_progress`, `needs_review`,
`model_assessed`, `one_off`, `self_check` and `companion` do not appear in `FIRST_RUN_COPY`,
`CREATE_RESULT_COPY`, `CREATE_STEP_SPINE` or the section sentence
(`tests/test_desktop_h86_wayfinding.py::LessonStartTest::test_learner_copy_has_no_internal_vocabulary`).
Machine words remain in source comments and the settings diagnostics, where they are the honest
subject.

## Standards

`docs/UX-RESEARCH-STANDARDS.md`, as written:

- **No dedicated onboarding.** One inline start plate that leads to the first real course. No modal,
  no deck of cards, no coach marks, no theme picker, no sample course
  (`test_no_onboarding_by_overlay`, `test_the_path_is_three_numbered_rows_not_an_onboarding_flow`).
- **One primary action per screen.** The static render of the plate has exactly one
  `data-variant="default"` control; the section action block has exactly one button.
- **No decorative kicker/eyebrow.** The plate opens on the heading; the header subtitle is gone.
- **Navigation visible**, `aria-current` plus a non-colour cue.
- **New Course is a novice wizard**: one thing per step, Back without data loss, conditional step
  indicator, labels above fields, examples as placeholders, 44px primary.
- **Empty/error states keep one next action.** The desk error keeps `Try again` + `Open
  Capabilities`; the section read error keeps `Try again` + `Open Capabilities`; neither renders an
  empty course.
- **WCAG**: focus comes from the host button primitives (focus-visible ring unchanged); the new
  local controls are native `<button>`s inside a `<nav>`; nothing is colour-only; text sizes are
  >= 0.75rem with body at 1rem; the path numbers use tabular numerals.
  Intentional deviation: the plate is a flat lamp field with top and side 1px rules, not a card in a
  card (owner: DeseretSaint, the lamp field is the established surface for the one primary action).

## Verification actually run

- `node --check desktop/plugin.js` — OK.
- `python3 -m unittest discover -s tests -t .` — **Ran 1673 tests, OK (skipped=1)**, including the
  new `tests/test_desktop_h86_wayfinding.py` (12 tests) and the updated `test_desktop_h28_copy.py`
  (start plate, path rows, spine, step-next lines) and `test_desktop_field_desk.py`
  (`Start a fresh run`).
- `python3 scripts/m4v-audit.py` — regenerated, **15 PASS, 0 not PASS**, new
  `plugin_sha256 2f806531aa840e53ecd0418ea13906d88e39909e4c858ed6f1b5e6f9af6b8240`
  (`audit/visual/m4-visual/audit.json` committed with it).
- `bash scripts/validate-plugin.sh` — run on committed HEAD (see the commit note; the gate refuses a
  dirty tree by design).

## Live capture: what was and was not obtained

`scripts/h86-capture.mjs` is the reproducible walk (start plate, New Course 1–3, desk, Library,
Parent Studio, section with no chat; measures `routeWidth`, `overflowX`, `h1`, primary buttons,
`aria-current` and the section action count at 1049/900/460).

It was run against the running isolated window on CDP 9337. That window kept serving the **pre-H-86**
module: its desk primary still read `Start the lesson`, no `[data-cb-nav-item]` existed and no
create spine rendered, even after copying the committed file into both plugin directories and
reloading with `ignoreCache`. The captures from that run were therefore **discarded** — they are not
evidence for this change and are not committed. The reload path that makes the host re-read the
plugin module could not be re-established inside this card's runtime, so:

- **No live CDP capture of the H-86 composition exists yet.** The route width measurements from the
  discarded run are still informative about the environment: route 406px at 1049, 256px at 900,
  214px at 460 — which is why every new row wraps and the spine collapses to `1 Size` etc. rather
  than a table.
- H-85 owns the final capture sweep on a committed sha and must treat the start plate, the three
  New Course steps and the no-chat section as **unverified live** until then.
- The first-run **empty** state and the forced **error** state were not reached live at all (the rig
  profile has a course, and no fault injection was wired in this run).

Everything above that claims behaviour is backed by the static render tests, the source guards, the
M4 harness and the suite — no screenshot is cited that was not produced by the new module.
