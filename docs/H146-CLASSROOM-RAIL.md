# H-146 — the classroom rail, captured live

Evidence for the classroom rail and the selected classroom on `wt/h146-classroom-rail`.
Captured **on top of** `ae2494f` (H-146a's tab focus ring), which is the head this card found when it
started capturing.

| | |
|---|---|
| Branch | `wt/h146-classroom-rail` @ `ae2494f` |
| `desktop/plugin.js` | sha256 `687613abde8d77ab6c1825a92b1bd3e0d0293d71a9f665c38d3bf44fa87bcc66` |
| Clean copy in the rig | `~/.hermes/coursebook-test-h146/home/desktop-plugins/coursebook/plugin.js`, same sha256 (copied from the branch, not reconciled) |
| Rig | isolated Electron window, remote backend `127.0.0.1:44219`, CDP `9364` (`scripts/cb013-live-window.sh`) |
| Frames | `docs/h146-shots/` |
| Facts | `docs/h146-shots/h146-facts.json` (every number below is read from it) |

## What the rail does

`SlotRail` sits above Continue on the Home desk and is **navigation, not a dashboard**
(`desktop/plugin.js`, `hubSlots` + `SlotRail`):

- one slot per `course_id`, built from `library.list` rows; `recipe === 'parent'` rows are dropped, so
  Parent Studio never appears as a learner classroom;
- the slot name is `learner_label` when present, otherwise the course title — nothing is invented;
- duplicate enrollments on one course are disclosed (`This course has N progress records; showing
  the most recent`) instead of being split;
- **≤ 4 classrooms**: text tabs with `aria-current` on exactly one, the current tab carrying a 2 px
  lamp underline and 600 weight; **> 4**: one labelled `<select>`; **1**: a named classroom, not a
  control;
- a switch is shell state only (`onSelect(course_id)`); it re-keys Continue, `course.outline` and
  `lesson.page`, and never touches `?profile=` or the backend. `Showing <name>` states the active
  classroom in words beneath the control;
- no avatars, covers, seals or card grid.

## Capture method

```
CB009_CDP_PORT=9364 node scripts/h146-theme.mjs light        # rig preference, applied by restart
COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-h146 bash scripts/cb013-live-window.sh --restart
CB009_CDP_PORT=9364 CB_H146_TARGET=Japanese node scripts/h146-capture.mjs docs/h146-shots
```

- Widths are calibrated, not merely requested: `Emulation.setDeviceMetricsOverride` is iterated until
  `window.innerWidth` equals 1049 / 900 / 460 exactly (`facts.innerWidth` in every row below).
- 200 % text is asserted, not assumed: the root font is set to 32 px and every 200 % row records
  `rootFont: "32px"`.
- Theme is the plugin's own paint, read from `[data-cb-route][data-cb-scope]` — `dark` and `light`
  rows below come from two window runs, not from a class string this harness injected.
- Keyboard rows are produced by **real `Input.dispatchKeyEvent` Tab presses**, because the tab paints
  its ring on `:focus-visible`: a programmatic `element.focus()` (what the first attempt did) reports
  `outline: none` and is not evidence about a keyboard user.

## Frame table

All frames 1049/900/460 CSS px wide, 900 px tall, root font as stated, plugin sha256
`687613ab…`. "initial" = the first classroom as the rail lists it; "switched" = after clicking the
`Japanese affection and register` classroom.

| Frame | Theme | Viewport | Root font | State | `data-cb-scope` | Rail |
|---|---|---|---|---|---|---|
| `dark-1049-initial.png` | dark | 1049 | 16 px | initial | dark | tabs |
| `dark-1049.png` | dark | 1049 | 16 px | switched | dark | tabs |
| `dark-900-initial.png` | dark | 900 | 16 px | initial | dark | tabs |
| `dark-900.png` | dark | 900 | 16 px | switched | dark | tabs |
| `dark-460-initial.png` | dark | 460 | 16 px | initial | dark | tabs |
| `dark-460.png` | dark | 460 | 16 px | switched | dark | tabs |
| `text200-dark-1049.png` | dark | 1049 | **32 px** | 200 % text, reduced motion | dark | tabs |
| `text200-dark-460.png` | dark | 460 | **32 px** | 200 % text, reduced motion | dark | tabs |
| `focus-dark-1049.png` | dark | 1049 | 16 px | Tab stop on the classroom tab | dark | tabs |
| `light-1049-initial.png` | light | 1049 | 16 px | initial | light | tabs |
| `light-1049.png` | light | 1049 | 16 px | switched | light | tabs |
| `light-900-initial.png` | light | 900 | 16 px | initial | light | tabs |
| `light-900.png` | light | 900 | 16 px | switched | light | tabs |
| `light-460-initial.png` | light | 460 | 16 px | initial | light | tabs |
| `light-460.png` | light | 460 | 16 px | switched | light | tabs |
| `text200-light-1049.png` | light | 1049 | **32 px** | 200 % text, reduced motion | light | tabs |
| `text200-light-460.png` | light | 460 | **32 px** | 200 % text, reduced motion | light | tabs |
| `focus-light-1049.png` | light | 1049 | 16 px | Tab stop on the classroom tab | light | tabs |
| `focus-ring-frame-light.png` (+ `-crop.png`) | light | 519 | 16 px | pixel probe of the focused tab | light | tabs |

The rig holds two classrooms (`H103 live failure check`, `Japanese affection and register — an L0
demonstration classroom`), so `data-cb-slot-rail` is `tabs` in every frame; the `select` (five or
more) and `single` (one classroom) branches are not live in this rig and are **fixture-backed**.

## Measured state (from `h146-facts.json`)

| Measurement | dark 1049 | dark 460 | light 1049 | light 460 | 200 % 460 |
|---|---|---|---|---|---|
| tabs / `aria-current` | 2 / one | 2 / one | 2 / one | 2 / one | 2 / one |
| active classroom, in words | `Showing Japanese affection and register — an L0 demonstration classroom` | same | same | same | same |
| Continue surfaces | 1 | 1 | 1 | 1 | 1 |
| Continue course after switch | `Japanese affection and register — …` | same | same | same | same |
| horizontal overflow (px) | 0 | 0 | 0 | 0 | 0 |
| `h1` count on the route | 1 | 1 | 1 | 1 | 1 |
| parent rows leaked into the desk | no | no | no | no | no |
| covers / avatars / all-courses cards | 0 / 0 / 0 | same | same | same | same |
| tab target height (current / other) | 53 / 44 px | 74 / 44 px | 53 / 44 px | 74 / 44 px | 356 / 146 px |

At 200 % text the rail wraps to several lines (a tab 356 px tall at 460) and the route still reports
`overflow: 0` — the accepted narrow behaviour.

## Q-gate table (H-146: Q1, Q2, Q3, Q7, Q11)

| Gate | Claim on this branch | Evidence |
|---|---|---|
| **Q1 First-screen grasp** | The Home desk states the active classroom in words and offers one Continue that names the course and the next section. | `light-1049-initial.png`: rail + `Showing H103 live failure check` + Continue card titled `H103 live failure check` / `Review and approve the plan`, one `h1`. `facts["light-1049-initial"]`. |
| **Q2 One primary action** | Exactly one Continue surface per screen; a classroom switch re-keys it instead of adding a second CTA. | `continueCards: 1` in all 18 fact rows; `light-1049.png` vs `light-1049-initial.png` show the same single card retitled across the switch. |
| **Q3 Path legibility** | The rail's current classroom is marked (`aria-current`, lamp underline, 600 weight) and the switch moves the current state; the desk below re-reads. | `tabs[].state/current` per row; `dark-1049-initial.png` → `dark-1049.png` show `aria-current` and `Showing …` moving to the Japanese classroom. |
| **Q7 State completeness** | Rail is present in both themes, three widths, and at 200 % text without overflow; selection survives a switch and back. | 18 frames + `overflow: 0`, `rootFont: 32px` in the four 200 % rows. Empty / failed-read / offline / all-archived / selected-slot-deleted are **fixture-backed** (`tests/test_desktop_home_hub.py`) — the rig's backend does not serve those states. |
| **Q11 Copy and truth** | Classroom names come from `learner_label` or the course title; no invented "Learner 1", no debug/test sentence on the desk. | `facts[].tabs[].name` equal the two live course titles; `parentLeak: false` in every row (the check looks for `Parent demo` / `H103 live reject check`). The rig's *data* still contains the H-103 debug course, which is H-109 demo hygiene, not this branch's copy. |

## Focus ring — what the capture actually shows

The keyboard walk, by real Tab presses from the route's skip link, is:

`Skip to course content` → `Home` → `Courses` → `Library` → `Parent Studio` → `All courses` →
classroom tab (6th stop; dark stop list recorded verbatim in `h146-facts.json`).

On the classroom tab stop: `data-cb-focus-ring="visible"`, computed
`outline: solid 1.1156px rgb(44, 74, 140)` (light) / `rgb(168, 192, 242)` (dark) — the accent token in
each theme — with `outline-offset` equal to the width. `focusRingVisible: true` in both modes.

What the pixels show, and what they do not: `focus-ring-frame-light.png` is a full-viewport capture
of the focused tab, and `focus-ring-frame-light-crop.png` is that tab at 1:1 device pixels. A pixel
probe of the crop finds the accent colour on exactly **two rows, 214 device px wide** (the ring's top
and bottom edges, one device pixel thick) and on no column beyond those two rows: the vertical edges
anti-alias into the paper at this window's `devicePixelRatio` of 0.896, and the 2 px ring resolves to
`1.1156px` computed. So the capture shows a **hairline ring, not a closed 2 px rectangle**. The DOM
state and the style are correct and keyboard-reachable; the painted weight is thinner than
`docs/COURSEBOOK-VISUAL-IDENTITY-V2.md` asks for. Logged as a defect on this card (H-146b) rather
than fixed here, because this card carries no product code.

## Live vs fixture-backed

- **Live (this rig, this sha, these frames):** tab rail with two classrooms, `aria-current`, the
  `Showing …` line, one Continue card re-keyed by a switch, both themes, 1049/900/460, 200 % text
  (root font asserted 32 px) with reduced motion, zero horizontal overflow, the Tab order through the
  rail, and the focus-ring state.
- **Fixture-backed, not live here:** the `> 4` labelled select, the single-classroom branch, the
  duplicate-enrollment disclosure, the empty / failed-read / offline / all-archived /
  selected-slot-deleted states, and the parent-only profile — all covered by
  `tests/test_desktop_home_hub.py` (20 tests), none produced by this rig.
- **Not claimed:** that a first-time tester finds Continue in five seconds (Q1 needs a human walk),
  and that the 2 px ring paints at 2 px (see above).

## M4 re-pin

`desktop/plugin.js` moved from `9735300e…` (pin at `428e6ab`) to `687613ab…`, so the M4 digest was
regenerated rather than grandfathered: `python3 scripts/m4v-audit.py` → **15 PASS, 0 not PASS**,
62 frames, `plugin_sha256: 687613abde8d77ab6c1825a92b1bd3e0d0293d71a9f665c38d3bf44fa87bcc66`.
`docs/release-evidence.json`, `README.md` and `docs/M4-VISUAL-MEDIA-AUDIT.md` carry the new pin.
