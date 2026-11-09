# GM-002 evidence manifest — global Home and course-home split

Branch: `wt/gm-002-home`   Commit: `602b1d6`   Captured: 2026-11-09   Captured by: `vellum`
App build: renderer frames of the shipped `desktop/plugin.js` from this commit
Viewports: 1049 / 900 / 460 · Modes: light, dark · Text scale: 100, 200

## What these frames are

Static renders of the shipped module in Chromium, produced by `scripts/gm002-frames.py` and
`scripts/gm002-shot.mjs` (the same pipeline family as `m2fd-frames.py` / `h196-workshop-frames.py`).
The rows, outline, next step and estimate are the contract's own shapes from the Field Desk render
suite; the components, tokens and layout are the shipped ones. This is a **renderer audit**, not a
live-window capture: no backend, chat or RPC was driven for these PNGs. `home.global` and
`home.course` are the two surfaces this card splits.

**Keyboard focus caveat.** The frame carries the focus *stop* (Tab reaches the third shelf card on
`home.global` and a path checkpoint on `home.course`), but the plugin paints its authored 2px
`--cb-accent` ring from React focus state, which a static document cannot enter. The authored ring
is asserted in `tests/test_desktop_home_hub.py::test_focused_classroom_tab_paints_the_identity_focus_ring`
and on the card overlay via `data-cb-focus-ring`; the PNG alone shows only the UA ring. This is named
here rather than dressed up as an authored ring.

**Live-window status.** The isolated window rig was not driven for this packet; the renderer frames,
the route walkthrough test and the state assertions are the evidence. The card asks for `Home ->
course -> back`; that is proven in
`tests/test_desktop_gm002_home.py::HomeSplitRouteTest.test_home_course_back_walkthrough`.

## home.global — the field library

Concept frame: `home-generic-first-open.png` (invitation band + shelf). Tokens/type from
`refined-system.png`.

| File | Screen | Viewport | Mode | Scale | State | Notes |
|---|---|---|---|---|---|---|
| home.global--1049--light--100--default.png | home.global | 1049 | light | 100 | default | 6 authored cards, one primary, shelf scrolls (1496 px in a 965 px tray) |
| home.global--1049--dark--100--default.png | home.global | 1049 | dark | 100 | default | dark token table |
| home.global--900--light--100--default.png | home.global | 900 | light | 100 | default | first collapse |
| home.global--460--light--100--default.png | home.global | 460 | light | 100 | default | cards stack; no clipped primary |
| home.global--1049--light--200--default.png | home.global | 1049 | light | 200 | default | root 32 px; invitation and actions wrap |
| home.global--460--light--200--default.png | home.global | 460 | light | 200 | default | narrow + 200 % |
| home.global--1049--light--100--focus.png | home.global | 1049 | light | 100 | focus | focus stop on the third card (see caveat) |
| home.global--1049--light--100--reduced-motion.png | home.global | 1049 | light | 100 | reduced-motion | static resting frame |
| home.global--1049--light--100--empty.png | home.global | 1049 | light | 100 | empty | "No courses yet." + one create action |
| home.global--1049--light--100--loading.png | home.global | 1049 | light | 100 | loading | shelf geometry held, restrained loader |
| home.global--1049--light--100--error.png | home.global | 1049 | light | 100 | error | named failed read, not an empty library |
| home.global--1049--light--100--offline.png | home.global | 1049 | light | 100 | offline | offline banner over the last-read shelf |
| home.global--900--light--100--overflow.png | home.global | 900 | light | 100 | overflow | shelf scrolled state (1496 px tray) |

## home.course — the selected course's home

Concept frame: `refined-classroom.png` (three-column body) / `japanese-classroom-reference.png` for
the course-bound hero direction GM-004 will bring.

| File | Screen | Viewport | Mode | Scale | State | Notes |
|---|---|---|---|---|---|---|
| home.course--1049--light--100--default.png | home.course | 1049 | light | 100 | default | trailhead + Continue + path |
| home.course--1049--dark--100--default.png | home.course | 1049 | dark | 100 | default | dark token table |
| home.course--900--light--100--default.png | home.course | 900 | light | 100 | default | first collapse |
| home.course--460--light--100--default.png | home.course | 460 | light | 100 | default | stacked trail |
| home.course--1049--light--200--default.png | home.course | 1049 | light | 200 | default | 200 % text |
| home.course--460--light--200--default.png | home.course | 460 | light | 200 | default | narrow + 200 % |
| home.course--1049--light--100--focus.png | home.course | 1049 | light | 100 | focus | focus stop on a path checkpoint |
| home.course--1049--light--100--reduced-motion.png | home.course | 1049 | light | 100 | reduced-motion | static resting frame |
| home.course--1049--light--100--loading.png | home.course | 1049 | light | 100 | loading | "Reading the trail" plate, geometry held |
| home.course--1049--light--100--error.png | home.course | 1049 | light | 100 | error | named failed read with retry |
| home.course--1049--light--100--no-outline.png | home.course | 1049 | light | 100 | no-outline | trail read failed; Continue keeps the recorded next step |

## Machine-readable companion

- `evidence.json` — painted facts per frame: root font, tokens, primary count/label, card count and
  titles, mode badges, shelf scroll width, path rows, banned vanity words, horizontal overflow.
- `frames.json` — the exact HTML rendered for each frame (regenerate with the scripts).
