# Acceptance run — frozen tree 172b61aa

Measured 2026-11-11 between 14:20 and 16:45 EST. Every number below came from a command or a
stamped frame, not from a document.

## The tree under test

| Item | Value |
|---|---|
| commit | `172b61aaffd44c33f2c89360df9f1fceeff66c37` (= `origin/master` at freeze time) |
| `desktop/plugin.js` sha256 | `9840010845539c05e571566dbd65d4ceab03bc1119d01c0356f2ff29c6d9c395` |
| reproducible from its own `desktop/src` | yes — `scripts/build_plugin.py --check` matched (`03d2859e` for the earlier local D-009, `98400108` for this tree) |
| backend | isolated `cb.rpc` **v26** on `127.0.0.1:44219` (`scripts/cb013-live-backend.sh`) |
| window | dev Electron rig, CDP `127.0.0.1:9337`, `HERMES_HOME=~/.hermes/coursebook-test/home` |
| module the window actually loaded | `98400108…c395` — read through the host's own `readPluginSource` IPC door, equal to the commit's module |

The live plugin was installed from this commit into both paths the window can read
(`~/.hermes/desktop-plugins/coursebook/plugin.js` and
`<rig>/home/plugins/coursebook/desktop/plugin.js`) and the sha was compared, not assumed.

## Frames

Every frame in `docs/launch/captures/freeze/` carries a `.stamp.json` beside it naming
`window.plugin_sha256`, `matches_expected`, route width/height, `data-cb-scope`, nav count, font
state, `[data-cb-v3-ready]`, and the captured bytes' sha256.

| Frame | Route | Size | Scope | Module |
|---|---|---|---|---|
| `home-1833-light.png` | Home | 1833×1090 | light | `98400108` |
| `courses-1833-light.png` | Courses | 1833×1090 | light | `98400108` |
| `workshop-1833-light.png` | Workshop | 1833×1090 | light | `98400108` |
| `studio-1833-light.png` | Parent Studio | 1833×1090 | light | `98400108` |
| `pane/*-pane-light.png` | all four at pane width | 892×946 | light | `98400108` |
| `course-home-772-light.png` | course home ("Read the Night Sky") | 772×1090 | light | `98400108` |

`coursebook-demo.mp4` — 52.0 s, 1920×1080, 30 fps, composed only from the frames above.

## Scenario results

| # | Scenario | Result | Observable |
|---|---|---|---|
| 1 | Plugin route mounts on the frozen module and paints Home | **PASS** | `[data-cb-route]` 1833×1090, 4 nav items, `[data-cb-v3-ready]`, `CB Display` loaded, window module sha == commit module |
| 2 | All four destinations render as distinct surfaces | **PASS** | four frames, four distinct sha256, each after a nav click *and* an `aria-current` assertion |
| 3 | Course home mounts from the library | **PASS (narrow)** | "Read the Night Sky", "The plan is waiting for you / Read it, then approve it so lessons can start", route 772×1090 — pane width, not reference canvas |
| 4 | Plan → approve → lesson → check → feedback loop | **NOT RUN** | the capture door cannot re-enter a course surface once mounted (`no course card` on the second pass); see defect D-4 |
| 5 | Resume a lesson | **NOT RUN** | same entry defect; no lesson was started in this run |
| 6 | A rejected plan's repair path | **NOT RUN** | same |
| 7 | Parent-only surface | **PASS (render only)** | Parent Studio renders plans ("Plans for your child", "New lesson plan", two plan cards); the approval path was not driven |
| 8 | Full unit suite on this commit | **NOT MEASURED** | the suite started at 14:33 on this tree and had not printed `Ran N tests` before this report was written; no green suite is claimed for `172b61aa` |

Scenarios 4, 5 and 6 are the ones `docs/ACCEPTANCE.md` asks a demo to carry, and they are **not**
covered. Gate 7 stays open on this report.

## Defects found while measuring (each reproduced, none fixed)

- **D-1 — the visual audit photographs a crash.** `visual/audit.mjs` produced four byte-identical
  frames at 913×976 on 2026-11-11T01:28Z. All four are the "Hermes couldn't start — background
  service stopped" dialog, not a product screen. The isolated rig has no backend, so the harness
  certified a crash as four routes.
- **D-2 — the capture door throws on the v3 nav.** `scripts/cp-capture.mjs` with
  `--destination home` fails `TypeError: Cannot read properties of null (reading
  'getBoundingClientRect')`: the destination resolver looks for a `[data-cb-destination]` control
  that the v3 shell does not render (it renders `[data-cb-nav-item]`). This is the "capture door is
  the open gate" line in `172b61aa`'s own message, reproduced.
- **D-3 — `enrollment.delete` fails with `INTERNAL_ERROR / IntegrityError`.** Re-running
  `scripts/reset-demo-data.py --apply` deletes nothing; the demo shelf keeps duplicate enrollment
  titles ("Japanese affection and register — a Sample L0 classroom" beside "— an L0 demonstration
  classroom"). The 14 dependent tables that reference `enrollment_id` are not cascaded.
- **D-4 — a course surface cannot be re-entered by the capture path.** Once the course home is
  mounted, the Courses list is no longer reachable from the shell, so a second capture of the same
  course refuses. Deep screens stay effectively unmeasurable by script.
- **D-5 — dead space at wide widths.** At a 1833 px route the Parent Studio and course surfaces
  paint in a narrow left column and leave the rest of the canvas blank; the film was therefore
  composed from 892 px pane frames.
- **D-6 — demo-labelled pack titles reach the shelf.** "Technical demo: reading a pack before you
  install it" and "Parent demo: measuring ingredients together" are visible product text.
- **D-7 — Workshop pack titles clip.** At 1833 px the third card reads "Reading a pack before" and
  is cut mid-line under its cover.

## What this report does not claim

No green suite. No parity score against the 1344×768 concept references (the pane frames are a
different breakpoint and are labelled as such). No lesson, check, feedback, resume or repair
scenario. No visual approval by the owner.
