# GM-002 evidence manifest — global Home and course-home split

Branch: `wt/gm-002-home`   Commit: `aaba9ca`   Captured: 2026-11-09   Captured by: `vellum`
App build: the isolated Desktop window from `scripts/cb013-live-window.sh` with
`desktop/plugin.js` copied from this commit (`plugin_sha256` in `live-evidence.json`).
Viewports: 1049 / 900 / 460 CSS px · Modes: light, dark · Text scale: 100, 200

Every frame below was captured at `plugin_sha256`
`a6476fb19c71ded960c9a70027b8330b162a8550a79aa4e8fcd7cca918c45c3b`, the module at `aaba9ca`.
This packet is the round-3 recapture: the shelf card now owns its title (the paper cover prints
only the monogram and subject, so no card repeats its heading), the `overflow` cell is taken with
the shelf tray actually scrolled to its end, and global Home carries `--full` cells at 200 % text
where the pane scrolls. The frames are committed separately from the implementation; the plugin
sha pins the exact module that was driven.

The operator's installed Desktop plugin was **not** modified: the rig is a separate
`COURSEBOOK_TEST_STATE` home with its own userdata and its own backend
(`scripts/cb013-live-backend.sh`, port 44279). No merge and no install happened while this packet
was under review.

## What these frames are

Real captures from the running app: `Page.captureScreenshot` against the isolated Electron window,
after driving the actual route (`#/coursebook`), the actual backend (`cb.rpc`) and the actual
settings sheet. The DOM facts recorded next to each file in `live-evidence.json` come from the same
page that was shot (active element, outline, root font, scope mode, card count, overflow).

Repeatable: `scripts/gm002-live-capture.mjs --phase base|loading|error|offline|full|empty`
(environment in the script header). `scripts/gm002-live-proxy.mjs` is the failure switch for the two
RPC-error states.

Viewport calibration: this Electron build runs the page at ≈0.896 zoom, so `Emulation` width is
calibrated until `window.innerWidth` is exactly the named CSS width. `live-evidence.json` records
the measured `innerWidth` for every frame. Full-page cells grow the emulated viewport until the
shell's scrolling pane (`main#cb-main-content`) fits in one frame; `documentElement` never scrolls
here, so measuring it was what produced a cut-off "full" shot in the previous packet.

## Fault switches (README §1 rule 5)

| State | Switch | Why it is honest |
|---|---|---|
| loading | `GM002_PROXY_MODE=slow` pass-through proxy in front of the backend (3 s on `library.list` / `course.outline`) | the plugin's own loading branch paints while a real request is in flight; nothing is faked |
| error | `GM002_PROXY_MODE=library-error` / `outline-error`: HTTP 200 with the contract's `ok:false, error:{code,message}` envelope | a real RPC-level failed read, not a transport drop (an HTTP 500 makes the shell show its CONNECT screen, which would prove nothing) |
| offline | `Network.emulateNetworkConditions {offline:true}` | sets the real `navigator.onLine` and fires the real `offline` event the page listens to |
| empty | migrated-but-empty Coursebook database (0 enrollments, 0 courses) | a real empty library, not a fabricated `items: []` response |
| plan-in-review | no switch | the second shelf card is a real draft course whose recorded next step is "Review and approve the plan" |

## home.global — the field library

Concept frame: `home-generic-first-open.png` (invitation band + shelf). Tokens/type from
`refined-system.png`. All facts below are recorded in `live-evidence.json`.

| File | Viewport | Mode | Scale | State | Painted facts |
|---|---|---|---|---|---|
| home.global--1049--light--100--default.png | 1049 | light | 100 | default | 6 cards; one filled `--cb-lamp` create action; shelf scrolls horizontally |
| home.global--1049--dark--100--default.png | 1049 | dark | 100 | default | same composition on the dark token table |
| home.global--900--light--100--default.png | 900 | light | 100 | default | first collapse; no page overflow |
| home.global--460--light--100--default.png | 460 | light | 100 | default | cards stack; no page overflow |
| home.global--1049--light--200--default.png | 1049 | light | 200 | default | root 32 px; invitation and actions wrap |
| home.global--1049--light--200--full.png | 1049 | light | 200 | full | full pane capture: content 1106 px inside a 1498 px viewport (`captured_height`/`content_height` in evidence) |
| home.global--460--light--200--default.png | 460 | light | 200 | default | narrow + 200 % |
| home.global--460--light--200--full.png | 460 | light | 200 | full | full pane capture: content 3400 px inside a 3972 px viewport; shelf and `See all` both in frame |
| home.global--1049--light--100--focus.png | 1049 | light | 100 | focus | Tab reaches the primary "Start a new course"; authored 2 px `--cb-accent` ring (`data-cb-focus-ring="visible"`) |
| home.global--1049--light--100--reduced-motion.png | 1049 | light | 100 | reduced-motion | reduced-motion setting + emulated media; static frame |
| home.global--1049--light--100--overflow.png | 1049 | light | 100 | overflow | shelf tray scrolled to its end (`scrollLeft` 557.8 of 1496 px, 938 px client); trailing card cut at the right edge; the document itself does not overflow |
| home.global--1049--light--100--loading.png | 1049 | light | 100 | loading | proxy switch; loader + "Nothing already saved is lost while this read is in flight." |
| home.global--1049--light--100--error.png | 1049 | light | 100 | error | "Your courses could not be read" + Try again; explicitly not an empty library |
| home.global--1049--light--100--offline.png | 1049 | light | 100 | offline | "Offline. Lessons, notes and review keep working…" over the last-read shelf |
| home.global--1049--light--100--empty.png | 1049 | light | 100 | empty | "No courses yet."; exactly one create action; Browse the library |

## home.course — the selected course's home

Concept frame: `refined-classroom.png` for composition; `japanese-classroom-reference.png` is the
course-bound direction GM-004 brings.

| File | Viewport | Mode | Scale | State | Painted facts |
|---|---|---|---|---|---|
| home.course--1049--light--100--default.png | 1049 | light | 100 | default | `data-cb-course-home`; trailhead + Continue plate + path |
| home.course--1049--dark--100--default.png | 1049 | dark | 100 | default | dark token table |
| home.course--900--light--100--default.png | 900 | light | 100 | default | first collapse |
| home.course--460--light--100--default.png | 460 | light | 100 | default | stacked trail |
| home.course--1049--light--200--default.png | 1049 | light | 200 | default | 200 % text |
| home.course--460--light--200--default.png | 460 | light | 200 | default | narrow + 200 % |
| home.course--460--light--100--full.png | 460 | light | 100 | full | full document capture (`captured_height` in evidence) |
| home.course--460--light--200--full.png | 460 | light | 200 | full | full document capture at 200 % |
| home.course--900--light--100--full.png | 900 | light | 100 | full | full document capture |
| home.course--1049--light--100--focus.png | 1049 | light | 100 | focus | Tab reaches the course primary; authored 2 px accent ring |
| home.course--1049--light--100--reduced-motion.png | 1049 | light | 100 | reduced-motion | reduced motion; static frame |
| home.course--1049--light--100--plan-in-review.png | 1049 | light | 100 | plan-in-review | real draft course; "Review and approve the plan" is the recorded next step |
| home.course--1049--light--100--no-world.png | 1049 | light | 100 | no-world | no course in this rig carries a world yet; the badge is honest, no mode is invented |
| home.course--1049--light--100--loading.png | 1049 | light | 100 | loading | proxy switch; "Reading the trail…" with course identity already painted |
| home.course--1049--light--100--error.png | 1049 | light | 100 | error | proxy switch on `course.outline`; "The route was not read. Continue still uses the next step this course recorded." |
| home.course--460--light--200--continue.png | 460 | light | 200 | narrow check (supplementary) | Continue plate measured after `scrollIntoView`: width 400 ≤ 460, `clippedX:false`, `textOverflow:false` (`scripts/gm002-narrow-probe.mjs`) |

## Not in this packet (named, not hidden)

- `home.course` `world-running`, `world-partial`, `world-stale`: GM-004 scope (no course in this
  rig carries a world yet, so there is no live state to paint).
- `home.course` `course-end`: not producible honestly here. Every enrollment in the rig still has
  objectives without independent evidence; a capture would require fabricating progress, which this
  card refuses. It is deferred with that reason, not mislabelled as GM-004 art scope.
- The five world cells and the `course-end` arithmetic are in `../MATRIX.md`; this card supplies
  every cell its own scope can produce and names the deferral.

## Machine-readable companion

- `live-evidence.json` — per-frame painted facts plus the plugin sha256, backend port, state dir and
  reason each frame is the state it claims to be.

## Supplementary, not evidence

`renderer-frames/` keeps the earlier jsdom→static-HTML→Chromium frames and their `evidence.json`
for history. They are **not** evidence for this card; every claim above is supported by the live
captures, not by them.
