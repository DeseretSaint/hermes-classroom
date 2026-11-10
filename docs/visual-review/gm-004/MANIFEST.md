# GM-004 live evidence MANIFEST

Packet for reviewer `quill`. Every frame here is a `Page.captureScreenshot` from a real,
isolated Hermes Desktop window talking to a real `cb.rpc` backend. Nothing is a rendering of a
mock, a fixture, or a static HTML shell.

## Rig

| thing | value |
| --- | --- |
| state dir | `~/.hermes/coursebook-test-gm004-203620` |
| backend | `127.0.0.1:44291` (`scripts/cb013-live-backend.sh`, `HERMES_COURSEBOOK_SINGLE_HOME=1`) |
| window CDP | `127.0.0.1:9471` (`scripts/cb013-live-window.sh`) |
| plugin pin | `desktop/plugin.js` sha256 `5918cdffc94b4ac5047421fd2cd44bebfdd329b528685e185c90466d0f4f273b` |
| capture script | `scripts/gm004-live-capture.mjs` |
| staging script | `scripts/gm004-stage-worlds.py` (world.generate/approve/mode.set/enrollment.create through the real dispatcher, deterministic swatch seam) |
| projection script | `scripts/gm004-record-worlds.py` (writes `staged-worlds.json`) |
| evidence JSON | `live-evidence.json` (one row per frame: md5, bytes, width, root font, scope, mode row, world, sections, overflow) |

Reproduce:

```bash
S=$HOME/.hermes/coursebook-test-gm004-203620
ln -sfn "$PWD" "$S/home/plugins/coursebook"
cp desktop/plugin.js "$S/home/desktop-plugins/coursebook/plugin.js"
COURSEBOOK_TEST_HOME="$S/home" CB013_PORT=44291 bash scripts/cb013-live-backend.sh
rm -f "$S"/userdata/Singleton*
COURSEBOOK_TEST_STATE="$S" CB013_CDP_PORT=9471 bash scripts/cb013-live-window.sh --restart
# 1. stage the worlds through the real handlers (idempotent)
HERMES_HOME="$S/home" GM004_WORKTREE="$PWD" python3 scripts/gm004-stage-worlds.py
HERMES_HOME="$S/home" GM004_WORKTREE="$PWD" python3 scripts/gm004-record-worlds.py
# 2. capture the matrix from the live window
CB015_CDP_PORT=9471 CB013_PORT=44291 COURSEBOOK_TEST_STATE="$S" \
  node scripts/gm004-live-capture.mjs
```

`scripts/gm004-stage-worlds.py` finds the three courses **by title** in the rig state dir, enrolls
an approved course that has no active enrollment (`enrollment.create`), stages `concepts` →
style approval → `kit` → final approval → `course.mode.set(game)`, and is idempotent (an already
approved world is reported and left alone). It does not create courses: the three courses
themselves were created earlier in this rig through the Desktop create flow and the demo seed.
**`course-world--*`, `course-world-headgasket--*` and `studio-concepts--*` therefore require the
preserved state dir** above; on a fresh state dir the staging script exits with
`no course titled … in … — the rig state dir is required`. The other surfaces (`home--*`,
`course-textbook--*`, `mode-dialog--*`, `create-mode--*`) only need a library with courses; the
rig's `coursebook-demo-seed.json` provides them, but those frames are not claimed to be
regenerable from a bare state dir either.

The window is the dev Electron app on the Vite renderer (`npm run dev:renderer`, port 5174).
`spawn` order matters: backend, Vite, then the window, or Electron fails to load the dev URL.

## Frames (42)

All widths are measured `window.innerWidth` (the rig needs an iterative
`Emulation.setDeviceMetricsOverride` because this Electron build reports a zoomed width).
At 200% text `document.documentElement` font-size is `32px`; every other frame is `16px`.

### Home — `[data-cb-home]` list

| frame | width | theme | zoom | shows |
| --- | --- | --- | --- | --- |
| `home--1049--dark` | 1049 | dark | 100% | six course cards with per-card mode badges; *Replace a head gasket* is first (newest enrollment) with a Game badge |
| `home--1049--light` | 1049 | light | 100% | same surface, light tokens |

### Approved Game world course home — Japanese demo, `field_atlas`

Course: *Japanese affection and register — an L0 demonstration classroom*.

| frame | width | theme | zoom |
| --- | --- | --- | --- |
| `course-world--1049--dark` | 1049 | dark | 100% |
| `course-world--900--dark` | 900 | dark | 100% |
| `course-world--460--dark` | 460 | dark | 100% |
| `course-world--460--dark--200` | 460 | dark | 200% |
| `course-world--1049--light` | 1049 | light | 100% |
| `course-world--900--light` | 900 | light | 100% |
| `course-world--460--light` | 460 | light | 100% |
| `course-world--460--light--200` | 460 | light | 200% |

Each row records `modeRow=game`, `modeBadge=game`, `world=game`, `hero=true`, `sections=4`,
`overflow=false`.

### Approved Game world course home — head gasket, `workshop_manual`

Course: *Replace a head gasket* (technical procedure; its approved kit has a cover and a hero
and no section plates, so `sections=0` on every row while `hero=true`).

| frame | width | theme | zoom |
| --- | --- | --- | --- |
| `course-world-headgasket--1049--dark` | 1049 | dark | 100% |
| `course-world-headgasket--900--dark` | 900 | dark | 100% |
| `course-world-headgasket--460--dark` | 460 | dark | 100% |
| `course-world-headgasket--460--dark--200` | 460 | dark | 200% |
| `course-world-headgasket--1049--light` | 1049 | light | 100% |
| `course-world-headgasket--900--light` | 900 | light | 100% |
| `course-world-headgasket--460--light` | 460 | light | 100% |
| `course-world-headgasket--460--light--200` | 460 | light | 200% |

Each row records `modeRow=game`, `modeBadge=game`, `world=game`, `hero=true`, `sections=0`,
`overflow=false`. The DOM carries the real recorded plate: the hero `img` has
`naturalWidth=320, naturalHeight=180, complete=true, opacity=1` and its pixels run
`rgb(95,103,111)` → `rgb(42,40,36)` top to bottom — the `workshop_manual` steel-grey →
oil-dark swatch, not a placeholder.

### Textbook course home — *Order coffee and ask for the bill in Kyoto, politely*

No world surface, Textbook badge, mode row, and the Textbook→Game prompt behind `Change mode`.

| frame | width | theme | zoom |
| --- | --- | --- | --- |
| `course-textbook--1049--dark` | 1049 | dark | 100% |
| `course-textbook--900--dark` | 900 | dark | 100% |
| `course-textbook--460--dark` | 460 | dark | 100% |
| `course-textbook--460--dark--200` | 460 | dark | 200% |
| `course-textbook--1049--light` | 1049 | light | 100% |
| `course-textbook--900--light` | 900 | light | 100% |
| `course-textbook--460--light` | 460 | light | 100% |
| `course-textbook--460--light--200` | 460 | light | 200% |

`world=null` on every row: a Textbook course has no world surface.

### Textbook→Game prompt — `Game mode is not available yet. Generate a game world?`

| frame | width | theme | zoom |
| --- | --- | --- | --- |
| `mode-dialog--1049--dark` | 1049 | dark | 100% |
| `mode-dialog--460--dark` | 460 | dark | 100% |
| `mode-dialog--1049--light` | 1049 | light | 100% |
| `mode-dialog--460--light` | 460 | light | 100% |

Each row records `dialog=generate`.

### World Studio — three authored directions

Course: *Japanese affection and register — a Sample L0 classroom*, world at `concepts_ready`.

| frame | width | theme | zoom |
| --- | --- | --- | --- |
| `studio-concepts--1049--dark` | 1049 | dark | 100% |
| `studio-concepts--900--dark` | 900 | dark | 100% |
| `studio-concepts--460--dark` | 460 | dark | 100% |
| `studio-concepts--460--dark--200` | 460 | dark | 200% |
| `studio-concepts--1049--light` | 1049 | light | 100% |
| `studio-concepts--900--light` | 900 | light | 100% |
| `studio-concepts--460--light` | 460 | light | 100% |
| `studio-concepts--460--light--200` | 460 | light | 200% |

Each row records `studio=concepts_ready`, `concepts=3`.

### Create — mode choice on the shape step

| frame | width | theme | zoom |
| --- | --- | --- | --- |
| `create-mode--1049--dark` | 1049 | dark | 100% |
| `create-mode--460--dark` | 460 | dark | 100% |
| `create-mode--1049--light` | 1049 | light | 100% |
| `create-mode--460--light` | 460 | light | 100% |

Each row records `createMode=game` (Game is the default; Textbook is the explicit choice).

## World staging — declared deterministic seam

The live model provider is **not available** in this environment (`world.generate` concepts with
the real provider returns `provider_unavailable`, `missing_roles: style_board:*`). **Live provider
capture not produced.**

To exercise the approved-world layout honestly, the three worlds were staged through the **real
handlers** (`world.generate`, `world.approve`, `course.mode.set`, `world.read`) with a
deterministic, provider-shaped media seam bound in the staging process. The seam returns flat
tonal swatch PNGs derived from the style palette words — **no scene, no text, no numbers**. The
frames that use them show recorded art plates and real DOM labels; they are labelled here as
seam swatches, never as generated art:

- `japanese_demo` → `field_atlas--authored`, state `approved`, mode `game`
- `head_gasket` → `workshop_manual--authored`, state `approved`, mode `game`, enrolled via
  `enrollment.create` so its course home is reachable in the library
- `sample_classroom` → `concepts_ready` (three authored boards, not approved)

`staged-worlds.json` is the `world.read` projection for each course, captured through the same
dispatcher. Staging used unique operation ids per call (`job_service.create` dedupes by operation
id, which otherwise leaves the kit job stuck in `kit_generating`).

### The head-gasket course home

*Replace a head gasket* is staged and **approved** (`workshop_manual--authored`). Because
`enrollment.create` **is** implemented in this build (`coursebook/domain.py` registers the
handler; `contracts/rpc.v24.json` declares it) and `library.list` lists any enrolled,
non-archived course — including a draft one — the course reaches the Desktop library. The
staging script's `ensure_enrollment()` step creates that enrollment through the real dispatcher
(`existing:enr_29d642c2…` on re-run) and `staged-worlds.json` now records the live
`library.list` row for it (`enrollment_status=active`, `course_status=draft`). That is what the
eight `course-world-headgasket--*` frames show.

An earlier revision of this packet claimed `enrollment.create` was frozen with no handler; that
was wrong — it was a staging-process registration gap (`world.ensure_registered()` alone does not
register the domain handlers), not a contract fact, and it is corrected here.

## Notes for the reviewer

- The Japanese course moved from Textbook (earlier packet) to an approved Game world for this
  packet, so `course-textbook--*` frames are now the *Order coffee* course. The identity of every world frame is recorded in `live-evidence.json` (`course` field).
- `overflow=false` and correct `rootFont` on all 42 rows; no frame is clipped horizontally.
- At 460 / 200% the surfaces scroll vertically; those frames show the top of the surface at true
  200% text, which is where reflow defects appear. Horizontal overflow is false on every row.
- `create-mode--1049--*` and `--460--*` were captured from a fresh create flow (goal typed, then
  Continue); the mode control is the authored Game/Textbook choice, no world generation.
- Frames were recaptured in one session against the final plugin pin; `live-evidence.json`
  carries a single `plugin_sha256`.
