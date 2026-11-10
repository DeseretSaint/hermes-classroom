# GM-015 behavioural probe harness

Runnable probes for the GM-015 behavioural list: keyboard order, 200% text, forced colours,
reduced motion, null runtime, font failure, image failure, offline and cold profile.

This folder is the instrument only. It does not run the GM-015 gate, score any screen or claim
parity. A probe reports **PASS** only from a measurement; a probe that cannot be measured honestly
reports **SKIP** with the reason, never PASS.

Every probe is runnable from the repo root:

```bash
python3 docs/concept-parity/gate/qa/probe.py
```

## What runs

Default mode is a **component preview**: the harness esbuild-bundles the shipped
`desktop/plugin.js` with React 19 and a harness-owned `@hermes/plugin-sdk` stub, mounts the real
`CoursebookHome`, `TutorRail`, `LessonDocumentView` and the plugin's own `register()` page in
headless Chromium, then measures the resulting DOM with real key events and CDP media emulation.
It is **not** a live Desktop capture: there is no host window chrome, no gateway and no backend.
`--live` is the separate path that measures the route already on screen in a running Desktop.

Requirements (discovered automatically, override with env vars):

| Tool | Discovery | Override |
| --- | --- | --- |
| node | `node` on `PATH` | — |
| react / react-dom / scheduler | `$HERMES_DESKTOP_APP/node_modules`, `~/.hermes/hermes-agent`, `~/.hermes/hermes-agent/apps/desktop` | `HERMES_DESKTOP_APP` |
| esbuild | that `node_modules/.bin/esbuild` | `ESBUILD_BIN` |
| Chromium | `chromium` on `PATH` | `CHROME_BIN` |
| host CSS (optional) | `<desktop app>/dist/assets/main-*.css` | — |

When the host CSS file is found, the frames load it, and the JSON report records its path and
sha256. Without it the preview still renders; the report says `host_css: null`.

## Probes

| Id | Fixture | What it asserts | Invocation |
| --- | --- | --- | --- |
| `module.load` | shelf | The shipped module exports the `coursebook` plugin with `register()` and >100 exports, with no boot or console error. | `probe.py --only module.load` |
| `runtime.null` | page | `register()` and the page render complete with `ctx.rest` rejecting: no uncaught error, no raw `undefined`/`NaN`, and a named state is on screen ("Backend off", "Try again", …). | `probe.py --only runtime.null` |
| `profile.cold` | cold | An empty library paints the invitation + `empty` shelf, exactly one primary action, zero course cards, and no course-home/Continue plate. | `probe.py --only profile.cold` |
| `keyboard.shelf` | shelf | Tab visits every visible shelf control in DOM order (`[data-cb-home]`), Shift+Tab walks the reverse order, and every stop has an accessible name. | `probe.py --only keyboard.shelf` |
| `keyboard.tutor_rail` | tutor | The same assertion over `[data-cb-tutor-rail]`: every visible control, DOM order forward, reverse backward, every stop named. | `probe.py --only keyboard.tutor_rail` |
| `text.200.shelf` | shelf | Root font 32px at 1049 and 460: no horizontal page overflow, no clipped text, and only deliberate scrollers (`overflow: auto/scroll`) may hide content. Intentional `-webkit-line-clamp` is exempt and reported. | `probe.py --only text.200.shelf` |
| `text.200.tutor_rail` | tutor | The same measurement over `[data-cb-route]` and `[data-cb-tutor-rail]`. | `probe.py --only text.200.tutor_rail` |
| `colors.forced.shelf` | shelf | With `forced-colors: active` observed: every text run keeps a non-transparent system colour and `forced-color-adjust` not `none`; the first Tab stop paints an outline or border. | `probe.py --only colors.forced.shelf` |
| `colors.forced.tutor_rail` | tutor | The same assertion over the rail. | `probe.py --only colors.forced.tutor_rail` |
| `motion.reduced.shelf` | shelf | With `prefers-reduced-motion: reduce` emulated **before mount**: no element animates or transitions longer than 10ms, and nothing loops infinitely. | `probe.py --only motion.reduced.shelf` |
| `motion.reduced.tutor_rail` | tutor | The same assertion over the rail. | `probe.py --only motion.reduced.tutor_rail` |
| `image.fail` | lesson | A real `<img>` rendered from a served artifact is pointed at a dead URL; the image is named, keeps a non-zero box, and the media caption + text equivalent stay on screen. | `probe.py --only image.fail` |
| `font.fail` | — | With font URLs blocked, every text run keeps a non-transparent colour and non-zero box. The shipped module currently authors no `@font-face` (type is OS stacks), so this probe reports **SKIP** with that reason and starts measuring automatically when a build adds a loadable face. | `probe.py --only font.fail` |
| `offline` | shelf | With CDP network emulation offline, the route still paints text, keeps its DOM and raises no uncaught error. | `probe.py --only offline` |

### Live mode

`--live` attaches to a running Desktop window's CDP port and measures the route that is already on
screen (no navigation, no window mutation beyond the emulation the probe sets):

```bash
python3 docs/concept-parity/gate/qa/probe.py --live --port 9337
python3 docs/concept-parity/gate/qa/probe.py --live --port 9337 --only motion.reduced.live_route
```

Live probes: `keyboard.live_route`, `text.200.live_route`, `colors.forced.live_route`,
`motion.reduced.live_route`, `image.fail.live_route`, `offline.live_route`. They assert the same
facts against `[data-cb-route]`; a route that is not on screen makes the probe FAIL with
"selector not found" rather than pretending to pass. The window must be the disposable QA rig, not
the operator's main app.

## Output modes

Human summary (one block per probe, with the exact command that produced it):

```bash
python3 docs/concept-parity/gate/qa/probe.py
```

Machine-readable report for the GM-015 reviewer to attach:

```bash
python3 docs/concept-parity/gate/qa/probe.py --json \\
  --out docs/concept-parity/gate/qa/results/gm015-probes.json
```

```json
{
  "tool": "gm015-behavioural-probes",
  "mode": "renderer",
  "plugin": {"path": "…/desktop/plugin.js", "sha256": "…"},
  "git_head": "…",
  "environment": {"renderer": "…", "host_css": {"path": "…", "sha256": "…"}},
  "probes": [
    {"id": "keyboard.shelf", "status": "PASS", "command": "…", "detail": {"expected": [], "forward": [], "…": "…"}}
  ],
  "summary": {"total": 14, "PASS": 13, "FAIL": 0, "SKIP": 1},
  "verdict": "PASS"
}
```

Exit code is `0` when no probe FAILs (PASS + SKIP), `1` when any probe FAILs. `--only <id>` may be
repeated; `--list` prints the catalogue; `--keep` leaves the renderer workspace on disk for
inspection.

`verdict` is the harness's own result, not a GM-015 parity verdict. GM-015 still has to interpret
FAIL/SKIP detail, run the live path and judge the screens.

## Honesty rules encoded here

- A selector that is missing is a **failure**, not a skip: if `[data-cb-tutor-rail]` disappears, the
  keyboard probe fails rather than reporting an empty pass.
- `text.200` distinguishes a deliberate horizontal scroller from a clipping container. The shelf row
  scrolls by design; a `container-overflow` is only reported when the overflow style is
  `hidden`/`clip`.
- The image probe exercises a **real plugin-rendered image**: the preview host serves a small SVG
  data URL for `/media/<artifact>`, the probe then points it at a dead URL. It is not a synthetic
  `<img>` injected by the harness.
- The font probe is a genuine SKIP today. It is not silently green: the report names why it cannot
  measure and what would turn it on.
- Reduced motion is emulated before the page loads, because the product decides motion in React
  state from `matchMedia`, not from a CSS media query. Emulating after mount would test nothing.
- Host CSS is optional and recorded by sha. A missing file does not turn the probes green or red;
  it changes what layout is measured, and the report says which stylesheet was in effect.

## Non-vacuity check (already run)

The probes are not stubs. A throwaway copy of `plugin.js` was mutated (product file untouched) and
three probes turned FAIL on the mutated module while the clean module passed:

| Mutation | Probe that failed |
| --- | --- |
| empty shelf marker forced to `ready` | `profile.cold` |
| shelf row `overflowX: auto` → `hidden` | `text.200.shelf` (container-overflow 545px) |
| `forcedColorAdjust: none` on the Home question | `colors.forced.shelf` |

The mutation script lives outside the repo (scratch) and is not a product or gate artifact.

## Limits the reviewer must keep in mind

- This is a **component preview**, not the Desktop window. It cannot prove host chrome, the session
  rail, real course data, gateway lifecycle or the operator's theme. `--live` covers those on the
  rig; neither mode replaces the visual acceptance gate.
- No backend is mounted, so surfaces that require live data render their named empty/error states.
  That is exactly what the cold and null-runtime probes assert.
- `image.fail` proves the *failed-image* path; it does not prove that a real pack cover loads in a
  real course (that is the live path and the visual packet).
- `font.fail` is SKIP until the module ships a loadable face.
- The harness writes only under this folder in the repo; scratch work goes to the worker's scratch
  directory and is removed unless `--keep` is passed.
