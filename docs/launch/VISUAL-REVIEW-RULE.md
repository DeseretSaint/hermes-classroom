# Visual review: frame the module, or prove the window is current

Owner directive, 2026-11-11. Applies to every session and every card on the `coursebook` board.

**The failure this fixes.** Three Hermes Desktop windows were open on the secondary monitor for
review while the module under review was something else. A window holds whatever
`~/.hermes/desktop-plugins/coursebook/plugin.js` the app loaded **when it started**; workers reinstall
that file from their own worktrees all day. Observed the same day: a window opened at 12:23, installs
at 12:24 and 12:35, then the branch build again at 13:00. Every review of that window was a review of
a build nobody was working on — the loop the owner flagged, and hours of it.

**1. Composition and code review use the module frame.** No window, no backend, no install step:

```
python3 scripts/cb-frame.py --list
python3 scripts/cb-frame.py --component course-home --width 1344 900
python3 scripts/cb-frame.py --component home --width 1344     # loading beat; use gen-home-proof.py
                                                              # when Home needs the fixture library
python3 scripts/cb-frame.py --component lesson-textbook --width 1344
python3 scripts/cb-frame.py --component lesson-guided --width 1344
python3 scripts/cb-frame.py --component lesson-section --width 1344
```

The lesson components render a document built from the bundled L0 pack's own section markdown and
its objective check - not invented prose - so a lesson frame shows the product holding real course
content. The frame omits the app shell (route mount, nav chrome, centring): it is the component in
the route scope, which is what composition review needs and what the shell must not change.

It stages the built `desktop/plugin.js` with the host's React and a stub SDK, renders the real
component inside `CbV3Scope`, and screenshots at the reference width. Each run writes
`frame-<component>-<width>.json` with `module_sha256`, `installed_module_sha256`,
`installed_matches_branch`, the two font states and the frame height. **A review summary quotes those
fields.** A frame without them is not evidence.

**2. A window review requires a passing preflight.** `python3 scripts/cb-frame.py --preflight`
exits 1 when the installed module is not this checkout's build, and says how to fix it
(`cp desktop/plugin.js ~/.hermes/desktop-plugins/coursebook/plugin.js`, then restart). Exit 0 covers
only a window started *after* that install.

**3. Close the window you opened.** A leftover review window is a stale surface the next run mistakes
for current work. Every stray Hermes window on the secondary monitor is stale by definition.

**4. When the host cannot be trusted**, a module-rendered frame may stand as the composition
evidence — owner ruling **D-010** (`docs/launch/UI-DECISIONS.md`). It may not be described as a live
install; the release docs name the frame's provenance.

The board supervisor (`85d2218453f7`, every 10m) carries this rule in its prompt, so every card it
dispatches inherits it.

## Requirements on a checkout

`scripts/cb-frame.py` needs three things that are not in git:

* `python3 scripts/build_plugin.py` once, so `desktop/plugin.js` matches `desktop/src` (the rig
  renders the built module, never the sources);
* `visual/node_modules` with `playwright` — `npm --prefix visual ci` in a fresh worktree, or a
  symlink to a checkout that has it. Without it the shot step fails with
  `Cannot find module 'playwright'` and no frame is written;
* the host's React (`react`, `react-dom`, `scheduler`) beside `~/.hermes/hermes-agent`, where
  `tests.test_desktop_lesson_views._desktop_node_modules()` looks for it.

A missing precondition exits non-zero and says which one; it never writes a frame it could not make.

## Known limit, stated rather than papered over

`readWindowPlugin` in `scripts/vq-capture.mjs` hashes the plugin **file** through the window's
bridge, and every cell reloads the document first — but neither proves the module the renderer
actually evaluated, because the main process may serve the plugin text it read at launch. So a live
capture can still be one build behind while reporting a current file sha.

The durable fix is a build stamp: `scripts/build_plugin.py` writes the segment hash into the module,
the module sets it on `globalThis` at import, and the capture asserts it against the file before
navigating. It is deliberately not done today: it changes `desktop/plugin.js`, which re-pins the M4
audit, both generated proof pages and the CP-053 measurement — an hour of mechanical churn against a
submission deadline. Until then: composition review goes through `cb-frame.py`, and a live capture
that matters is taken with a window started after the install it is claiming.
