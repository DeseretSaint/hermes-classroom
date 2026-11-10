# Visual audit

Render the plugin, diff it, and fail on drift — on the secondary monitor, without touching the
owner's window or focus.

```
cd visual && npm install
node find-cdp.mjs                 # prints the CDP port showing Coursebook
node audit.mjs --write-baseline   # first run, or after an approved visual change
node audit.mjs                    # every later run
```

## It never uses the owner's window

- It opens its own peer window through the host's `openWindow()`.
- It moves that window to the secondary monitor (`--monitor secondary`, default) and records the
  real geometry in `report.json`.
- It hands focus straight back to whatever window was focused before the run, and closes the test
  window at the end. It never calls `bringToFront`, `setViewportSize` or `reload` on a live window.
- `--reuse` attaches to an existing Coursebook page instead of opening one; it still never focuses
  or reloads it.

## What it checks, per route

- screenshots `[data-cb-route]` at 2x into `frames/`,
- diffs against `baselines/<route>.png` with pixelmatch, failing past `--threshold` (0.1%),
- runs axe-core on the same DOM and fails on serious/critical,
- asserts `CB Display` and `CB UI` actually loaded (a fallback face is a defect),
- writes `report.json`.

## Geometry is recorded, not assumed

The host docks the plugin beside chat, so the route can be 341–744px wide even in a wide window.
The report prints `window WxH at X,Y; route WxH scope=...`; a narrow pane is a real finding, and it
cannot be scored as parity with a 1344x768 reference. That gap is CP-048.

The plugin is read from `~/.hermes/desktop-plugins/coursebook/plugin.js` at app start, so a code
change is only visible after the Desktop restarts — CB-017, not a harness bug.
