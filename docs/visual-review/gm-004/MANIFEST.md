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
| evidence JSON | `live-evidence.json` (one row per frame: md5, bytes, width, root font, scope, mode row, world, sections, overflow) |

Reproduce:

```bash
S=$HOME/.hermes/coursebook-test-gm004-203620
ln -sfn "$PWD" "$S/home/plugins/coursebook"
cp desktop/plugin.js "$S/home/desktop-plugins/coursebook/plugin.js"
COURSEBOOK_TEST_HOME="$S/home" CB013_PORT=44291 bash scripts/cb013-live-backend.sh
rm -f "$S"/userdata/Singleton*
COURSEBOOK_TEST_STATE="$S" CB013_CDP_PORT=9471 bash scripts/cb013-live-window.sh --restart
CB015_CDP_PORT=9471 CB013_PORT=44291 COURSEBOOK_TEST_STATE="$S" \
  node scripts/gm004-live-capture.mjs
```

The window is the dev Electron app on the Vite renderer (`npm run dev:renderer`, port 5174).
`spawn` order matters: backend, Vite, then the window, or Electron fails to load the dev URL.

## Frames (34)

All widths are measured `window.innerWidth` (the rig needs an iterative
`Emulation.setDeviceMetricsOverride` because this Electron build reports a zoomed width).
At 200% text `document.documentElement` font-size is `32px`; every other frame is `16px`.

### Home — `[data-cb-home]` list

| frame | width | theme | zoom | shows |
| --- | --- | --- | --- | --- |
| `home--1049--dark` | 1049 | dark | 100% | six course cards with per-card mode badges (Game / Textbook) |
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
- `head_gasket` → `workshop_manual--authored`, state `approved`, mode `game`
- `sample_classroom` → `concepts_ready` (three authored boards, not approved)

`staged-worlds.json` is the `world.read` projection for each course, captured through the same
dispatcher. Staging used unique operation ids per call (`job_service.create` dedupes by operation
id, which otherwise leaves the kit job stuck in `kit_generating`).

### Why there is no head-gasket course-home frame

*Replace a head gasket* is staged and **approved** (`workshop_manual--authored`, see
`staged-worlds.json`), but the course has no enrollment and `enrollment.create` is frozen in
`cb.rpc` with **no handler in this build** (`NOT_IMPLEMENTED`). A course home cannot be opened for
it, so no frame is claimed. The Japanese course home carries the approved-world visual evidence;
the head-gasket world is proven at the RPC boundary only.

## Notes for the reviewer

- The Japanese course moved from Textbook (earlier packet) to an approved Game world for this
  packet, so `course-textbook--*` frames are now the *Order coffee* course. The German/Japanese
  identity of every world frame is recorded in `live-evidence.json` (`course` field).
- `overflow=false` and correct `rootFont` on all 34 rows; no frame is clipped horizontally.
- `create-mode--1049--*` and `--460--*` were captured from a fresh create flow (goal typed, then
  Continue); the mode control is the authored Game/Textbook choice, no world generation.
- Frames were recaptured in one session against the final plugin pin; `live-evidence.json`
  carries a single `plugin_sha256`.
