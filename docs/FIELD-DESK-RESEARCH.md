# Field Desk: learning-app research and the home redesign

Status: design research supporting the Field Desk home change. It is not a claim of measured
learning outcomes, and it is not a substitute for the product's own audit evidence.

Date: 2026-11-07.

## Question

The first Field Desk was functionally correct but read as a stack of paragraphs. A learner could
not tell what course they were in, what the next move was, or why the side rail existed. The
question for this pass was narrower than the harness work:

> What do the strongest learning products put on the screen first, and which of those patterns can
> Coursebook use without inventing progress data or turning the desk into a vanity dashboard?

## What was surveyed

This was a public product/design survey, not a controlled study. Vendor statements are labelled as
vendor statements.

| Product | What the public material says | What is useful for Coursebook |
|---|---|---|
| **Duolingo** | The home screen is a **path** with one step-by-step route; lessons are ordered and grouped; the current place is explicit. Duolingo's own design post describes the path as a way to remove "which lesson is correct?" uncertainty. [Introducing the new Duolingo learning path](https://blog.duolingo.com/new-duolingo-home-screen-design/) | A route, not a table. The learner should see the current node and the next node, not a catalogue of every unit with equal weight. |
| **Coursera** | Its course dashboard adds a **progress bar per course** and highlights the recommended **next item** with a **Start** action. Coursera reported early data that learners with these features were "over 10 percent more likely" to complete a course; this is a 2016 vendor report, not an independent effect size. [New progress tracking features on Coursera](https://blog.coursera.org/new-progress-tracking-features-on-coursera/) | Put progress and the next action in the same card. A course shelf is useful only when each row has an honest next step. |
| **Brilliant** | Brilliant describes interactive, visual learning: build intuition with visual explanations and hands-on manipulation, keep the simplest version of an idea, and use low-stakes practice. It also says its gamification layer is deliberately limited so the learning content stays central. [About Brilliant](https://brilliant.org/about/) | Visual structure should carry the concept, not decorate it. A path marker, a course cover and a real progress strip are enough; a wall of invented badges is not. |
| **Khan Academy** | Khan's progress reporting uses clear at-a-glance views of mastery goals; the learner/teacher can see where progress is and where support is needed. [Monitor student progress toward mastery](https://www.khanacademy.org/khan-for-educators/khan-for-educators-advanced-course/x2e5750eab575b791:khan-for-educators-advanced/x2e5750eab575b791:using-ka-reports-to-personalize-learning/a/review-student-progress-toward-mastery-a9) | Progress language should name the real evidence state. Coursebook says "with evidence", "due now" and "not started"; it never turns those into a mastery percentage. |

Supporting pattern language from a learning-app UI survey: a home screen should show the next
lesson, the current level, recent progress and a clear way to start; it should not ask the learner
to reconstruct where they were. [Language learning app UI: home screens & lessons](https://gummble.com/categories/language-learning-apps)
This is a design-pattern source, not an outcome study.

## The recurring pattern

Across the four products the same four pieces recur:

1. **Identity** — which course or subject this is.
2. **Position** — where the learner is in the path.
3. **One next move** — the exact section or practice to open, with a primary action.
4. **A navigable context** — the rest of the path and the learner's other courses, always
   secondary to the next move.

The strongest products do not make every course, every module and every statistic equally loud.
They put one action at the top and let the route explain the rest.

## What changed in the Field Desk

### 1. The Continue card is a learning card, not a heading stack

- It names the **course** (with a deterministic initial stamp), then the **section** in a larger
  display size, then the recorded position (`Section 1 of 4`), the recorded estimate (or
  `Session length not recorded`) and the last touch time.
- It adds three counts that the backend actually recorded: **Sections**, **With evidence**, and
  **Due now**. There is no percentage, streak, XP, league or invented goal.
- It adds a segmented progress strip: one segment per objective, painted from that objective's own
  state. A segment is not a fake completion bar; it is a compact view of the real `state` values.
- The primary action is the backend's next step. **Start the lesson** and **Resume the lesson** are
  different states, not two names for the same optimistic button.

### 2. The path is a route

- Each objective is a numbered circular marker, the state word and a state dot.
- The current step gets `aria-current="step"` and a quiet accent tint; the title column wraps so a
  split-screen layout cannot push the state word under the title.
- The path stays on the main reading column. The course shelf is not allowed to outrank it.

### 3. The side rail is intentional

- **Field Notes** is the saved-moment surface for this course; it is a card, not a settings list.
- **All Courses** is a small shelf of the other courses, at most three cards, each with its own
  next step and its real evidence count. The full search/manage surface remains one click away.
- On a wide desk the main column is `minmax(0, 1.2fr)` and the side rail is
  `minmax(19rem, 0.8fr)`. Below the live wide breakpoint the rail stacks after the main column, so
  the next action and path stay first in reading order.

### 4. Resume is honest about a missing chat

`lesson.begin(mode='resume')` can legitimately return `resume.available: false` with
`reason: "no_binding"` even when a lesson run exists. The old UI fell through to
`startLessonChat()`, which opened a fresh draft and unmounted the course page. That looked like
"Resume opened a new session and nothing happened."

The desk now returns a typed `no-binding` result and keeps the learner on the course page; the
course detail opens the section instead of a blank chat. The notice says exactly what is missing
and the section's own `Start a fresh run` control remains available. A saved chat that cannot be
opened is also caught and explained rather than silently ignored.

## What was deliberately not copied

- **No streak, league, XP or level system.** Coursebook has no durable daily-activity contract for
  those claims, and inventing them would violate the product's evidence rules.
- **No mastery percentage or ring.** The real states are `not_started`, introduced, independent
  evidence, delayed evidence, review due and needs review. The desk names those.
- **No decorative illustration pipeline.** Images belong to a lesson's capability policy when they
  carry the teaching; the home cover is a deterministic initial stamp, not generated art.
- **No gradients, shadows or glass.** The Ink & Field Notes token contract forbids gradients and
  the desk test forbids shadows; hierarchy comes from scale, spacing, rules and the accent token.

## Validation performed for this pass

- Rendered the shipped module at the live wide viewport and at an emulated 900 px viewport; no
  horizontal overflow, no path-title/state collision, and the stacked order keeps the Continue card
  and path above the shelf.
- `tests/test_desktop_field_desk.py` and `tests/test_desktop_field_notes.py` cover the wide grid,
  the real stat counts, the course stamp, the path-wrap rule and the no-binding resume fallback.
- The existing token-layer test still refuses raw hex, gradients and shadows in the desk block.

## Deferred, with a reason

- A richer course-cover visual language (per-subject marks) needs a media/capability decision; the
  current stamp is deterministic and safe for every title.
- Micro-transitions are deferred until the shell has a reduced-motion contract; the current shell
  records the preference and ships no transitions.
- A first-run home that demonstrates the loop still needs a real sample-free walkthrough; it must
  not become a fake course.
