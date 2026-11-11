# GM-002 — first-screen comprehension script

Read this while the `home.global--1049--light--100--default.png` frame is open. A person who has
never seen Coursebook should answer each question from the screen alone, without instruction. Every
answer below is a fact the frame actually paints; if the reader needs a second sentence of
explanation, the screen is the thing to fix.

| # | Ask | The reader should say | Where the screen says it |
|---|---|---|---|
| 1 | What is this screen for? | "It's my course library — I pick what to learn." | `Your field library` / `Choose a course or start a new expedition.` |
| 2 | What is the first thing I can do? | "Start a new course." | the only filled button in the invitation band |
| 3 | What if I don't want to write one? | "Browse the library." | `Browse library` beside the primary |
| 4 | What are those objects along the shelf? | "Courses I already have." | `Your courses`, six titled cards, each with its real next step. A Game/Textbook badge appears only when `world.read` reports a mode; this rig reports none and the page says so instead of inventing one. |
| 5 | Where is my lesson / Continue? | "Not here — open a course." | no Continue plate exists on this screen; the card is the door |
| 6 | How do I see everything? | "See all." | the quiet link beside `Your courses` |
| 7 | If nothing is here? | "No courses yet — start one or browse." | empty state keeps the same two actions |

## Walkthrough script (Home -> course -> back)

1. Home paints the invitation band, one primary, the shelf and `See all`. No Continue, no course
   hero, no Japanese scene.
2. Activate any card (click, or Tab to it and press Enter). The route now paints the **course home**:
   the trailhead, the course title, the current objective, `Continue`, and the path. The shelf is
   gone; the header offers `Back to Home`.
3. Activate `Back to Home` (or press `Home` in the section nav). The library is back, the Continue
   plate is gone, and the course that was open is still the selected shelf item.

This is asserted end to end in
`tests/test_desktop_gm002_home.py::HomeSplitRouteTest.test_home_course_back_walkthrough`.

## What fails the script

- Any Continue/Resume control on the library Home.
- A second create control on the shelf or in the header of Home.
- A star, review count, "recently played", streak, level or XP anywhere on Home.
- A failed read painted as "No courses yet." instead of a named error with a retry.
- A mode badge whose value was not read from `world.read`.
