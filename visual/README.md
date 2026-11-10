# Visual audit

The feedback loop the build was missing: render the plugin, diff it, and fail on drift.

```
cd visual && npm install
node audit.mjs --port 9337 --write-baseline   # first run: accept current frames
node audit.mjs --port 9337                    # every later run: diff vs baseline
```

It connects to the running Hermes Desktop over CDP (no second browser), opens `#/coursebook`,
clicks each nav destination (Home, Courses, Workshop, Parent Studio), and for each route:

- screenshots the `[data-cb-route]` node at 2x into `frames/`,
- diffs against `baselines/<route>.png` with pixelmatch, failing past `--threshold` (0.1% default),
- runs axe-core on the same DOM and fails on serious/critical violations,
- asserts `CB Display` and `CB UI` actually loaded (a silent system-serif fallback is a defect),
- writes `report.json` and `report.html` (a contact sheet with titles, fonts, axe and diff).

The plugin is read from `~/.hermes/desktop-plugins/coursebook/plugin.js` at app start, so a code
change is only visible after the Desktop restarts — that is CB-017, not a harness bug.
