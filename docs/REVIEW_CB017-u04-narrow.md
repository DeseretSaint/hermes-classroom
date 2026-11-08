# CB-017 / U04 — narrow width on a built (stable) rig at `a8d0f32`

Author: Sentinel. Evidence-only pass: no product code, no `desktop/plugin.js` edit, no contract
change, no chart or demo claim. U04 only — the chat-dependent demo shots are out of scope here and
are not claimed.

This closes the open measurement on `t_6a32ffe9`: on the `5b0f124` rig U04's 460 px rows never
completed because the **Vite dev server** failed a dynamic import (`Failed to fetch dynamically
imported module /src/main.tsx`) and the renderer dropped the route. That was a rig failure, not a
product finding. This pass serves a **production build over a static host**, so no module request
can 404 mid-pass, and all four rows completed.

## 1. Rig

| Item | Value |
| --- | --- |
| Commit | `a8d0f32fa52bb8a81d27b1abcbd89f8c12cec66d` (`master`; `catalog: pin the entry to the docs commit on the merged release candidate`) |
| Worktree | `/home/deseretsaint/.hermes/kanban/boards/coursebook/workspaces/t_ab48e16d/src` (`git worktree add --detach <path> a8d0f32…`) |
| Package `desktop/plugin.js` | sha256 `71fc4c3f57c8b296dbe7d50694151055f6ca7fc00ae4b01b0e90b91f2c5981a5` (matches the card's pin) |
| Installed Desktop copy | `~/.hermes/coursebook-u04-a8d0f32/home/desktop-plugins/coursebook/plugin.js`, same sha256 `71fc4c3f…c5981a5` |
| Home | `~/.hermes/coursebook-u04-a8d0f32/home` — fresh, disposable; operator profile and gateway untouched |
| Install | `scripts/install-local.sh --home ~/.hermes/coursebook-u04-a8d0f32/home --source <worktree>` → `Installed.` (1 tool, 3 hooks) |
| Backend | `HERMES_HOME=<rig home> HERMES_DESKTOP_DEV_SERVER=http://127.0.0.1:51817 HERMES_DASHBOARD_SESSION_TOKEN=<rig token> hermes serve --isolated --port 44617 --skip-build` (log `serve-44617.log`, `HERMES_DASHBOARD_READY port=44617`) |
| Backend proof | `GET /api/plugins/coursebook/runtime` → `plugin_root` = this worktree, `wire_version` 14, `contract_methods` 64, 64 implemented, `contract_problems: []` |
| Window | Electron from `~/.hermes/hermes-agent/apps/desktop`, own userdata `~/.hermes/coursebook-u04-a8d0f32/userdata`, CDP `127.0.0.1:9481`, remote connection `127.0.0.1:44617` |
| Course on the route | seeded through the learner path (`scripts/seed-demo-course.py` → grant/preview/import), course `crs_47e370abfecb4982bb26403e26733282`, enrollment `enr_54b31b3a8c5b44bba00852138d1274a1`, pack content hash `sha256:447aace8…983856` |
| Plugin decision | rig setup, documented: `localStorage['hermes.desktop.pluginDecisions.v2'] = {"coursebook":true}` in that userdata (remote mode's plugin roster is empty because `hermes serve` does not mount `GET /api/desktop-plugins/root`, the `t_3589acce` finding). Not a product change |

## 2. Serve path (the point of this card)

**Built bundle served as static files, not the Vite dev server.**

- Host build used: `~/.hermes/hermes-agent/apps/desktop/dist` (`hermes-build.json` `stampClock`
  `2026-11-07T04:46:42.412Z`, `outputHash` `760120a3f906449c06afb049e4839b075dd2a702362520155428afe98b6e0db9`).
- Static host: `python3 -m http.server 51817 --bind 127.0.0.1 --directory ~/.hermes/hermes-agent/apps/desktop/dist`
  (log `static-51817.log`; `GET /index.html` → 200).
- Window: launched **without** a Vite process, with `HERMES_DESKTOP_DEV_SERVER=http://127.0.0.1:51817`
  so the built renderer loads from the static root. The only entries under `dist/assets` are
  fingerprint-named build chunks; there is no `/src/main.tsx` request in this path at all.
- Why this makes the 460 rows trustworthy: the `5b0f124` abort was a dev-server module-graph failure.
  In this run all four rows, the reduced-motion pass and the screenshots completed with the renderer
  alive afterwards (`GET :9481/json` still returned the page target), and `consoleErrors` was `[]`.

## 3. U04 results

Measured live through CDP on the mounted route, launched by a **real pointer click** on the shell's
own "Coursebook" sidebar item (not hash injection): `#/coursebook`, `[data-cb-route="/coursebook"]`,
`[data-cb-destination="courses"]`.

| row | viewport | root font | route width | horizontal overflow (px) | unnamed controls | clipped nodes | focus: stops / named / `:focus-visible` / visible ring |
| --- | --- | --- | --- | --- | --- | --- | --- |
| desktop-100 | 1440×900 | 16 px | 1180 px | **0** | **0** | **0** | 10 / 10 / 10 / 10 |
| desktop-text-200 | 1440×900 | 32 px (200%) | 1180 px | **0** | **0** | **0** | 14 / 14 / 14 / 14 |
| narrow-460 | 460×900 | 16 px | 460 px | **0** | **0** | **0** | 18 / 18 / 18 / 18 |
| narrow-text-200 | 460×900 | 32 px (200%) | 460 px | **0** | **0** | **4** (note U04-D1) | 18 / 18 / 18 / 18 |

- **200% text:** root font size emulated to `32px`; the route reflows with **0 px document
  overflow** at both widths and 0 unnamed controls. At 460 px / 200% **4 nodes** exceed their own
  client width by 3–5 px (details below). No horizontal scrollbar appears at any row.
- **Reduced motion:** with `Emulation.setEmulatedMedia {prefers-reduced-motion: reduce}`
  (`mediaMatchesReduce: true`), across 125 route nodes the longest `transition-duration` is
  **0.00001 s** and the longest `animation-duration` is **0.00001 s**; no named animation is
  running. That is the "0 s" claim, measured, with the 10 µs Chromium floor stated rather than
  rounded away.
- **Focus visibility:** every route stop reached by real CDP `Tab` key events (not `element.focus()`)
  matched `:focus-visible`, had a non-empty accessible name, and painted a visible ring
  (`outline-width ≠ 0px` or a non-`none` box-shadow). Stop counts differ per viewport because the
  shell's tab order and the route's responsive layout differ; the sweep reports only stops that are
  inside `[data-cb-route]`. At 1440/16 the first sweep's tab budget was exhausted before entering
  the route, so that row's sweep was re-run with a 420-tab budget (`u04-focus-1440-16.json`).
- **No-media fallback:** not re-measured in this pass (out of this card's acceptance list; the
  `29bede7` pass measured it and the route carries no `img` in this build). Not claimed.

### Note U04-D1 (P3, layout) — 460 px at 200% text

Four route nodes clip by 3–5 px inside their own box; the document itself does **not** overflow:

| node | client / scroll px | text |
| --- | --- | --- |
| `div` | 93 / 98 | `0` + `With evidence` (stat pair) |
| `span` | 93 / 98 | `With evidence` |
| `span` | 20 / 23 | `Tell everyday affection from a direct romantic declaration` |
| `span` | 20 / 23 | `Recall the intimate declaration in a new context` |

All four sit under a parent with `text-overflow: clip`; the 20 px spans are the objectives list
inside a clamped column. The stat pair overflows by 5 px, so part of "With evidence" is clipped at
this width and root size. Minor, but it is a real clip and is reported, not normalised. It is
smaller than the `29bede7` reading (8 clipped nodes) and it is the only defect this pass found.

## 4. Host-rail caveat (`t_eb497e0f`) — stated, not attributed here

`t_eb497e0f` (M1 narrow width) is a **host** defect: the shipped host gives the Coursebook route
about **101 px** at a 460 px window with the chat rail docked. This card measures the **module's own**
narrow behaviour, so the route is given the full 460 px (`routeWidth: 460`) under device-metrics
emulation, with the shell sidebar collapsed by the host's responsive rules. Nothing in this table
says the shipped host renders the route at 460 px usable; the M1 finding stands and this pass neither
fixes nor contradicts it. The measured 0 px overflow is the route's own layout at 460 px, not a claim
about the docked-rail host state.

## 5. Measurement command

Rig helpers are the repo's own CDP harness (`scripts/cb015-lib.mjs`, plus `press()` from
`audit/demo-gate-5b0f124/lib.mjs`). The probe lives outside the repo so the commit stays docs-only:

```
RIG=~/.hermes/coursebook-u04-a8d0f32 CB015_CDP_PORT=9481 node ~/.hermes/coursebook-u04-a8d0f32/u04-fast.mjs
```

Core measurement, per row (`u04-fast.mjs`, `measure()`):

```js
const root = document.querySelector('[data-cb-route]')
const controls = [...root.querySelectorAll('button, a[href], input, select, textarea, [role=tab], [role=button], [role=checkbox], [role=radio], [role=link]')]
  .filter(el => el.getClientRects().length > 0)
const unnamed = controls.filter(el => !(el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.value || '').trim())
const clipped = [...root.querySelectorAll('*')].filter(el => el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1)
return { overflowX: document.documentElement.scrollWidth - innerWidth, controls: controls.length,
         unnamedControls: unnamed.length, clippedNodes: clipped.length }
```

Rows are driven with `Emulation.setDeviceMetricsOverride` (1440×900 / 460×900) and
`document.documentElement.style.fontSize = '16px' | '32px'`; focus is measured with real
`Input.dispatchKeyEvent` Tab presses; reduced motion with
`Emulation.setEmulatedMedia` + `getComputedStyle(...).transitionDuration/animationDuration`.

Raw captures: `~/.hermes/coursebook-u04-a8d0f32/u04-fast.json`, `u04-focus-1440-16.json`,
`shots/u04-{desktop-1440-16,desktop-1440-32,narrow-460-16,narrow-460-32}.png`, window log
`window-9481.log`, backend log `serve-44617.log`.

## 6. Verdict

**U04 PASSES on the built rig at `a8d0f32` / plugin `71fc4c3f…c5981a5`, with one P3 note.** All four
rows completed without a renderer crash: horizontal overflow 0 everywhere, 0 unnamed controls
everywhere, 18/18 route stops named, `:focus-visible` and visibly ringed at every viewport, and
reduced-motion transition/animation durations effectively 0 s. At 460 px with 200% text, 4 nodes clip
3–5 px inside their own boxes (U04-D1), and the document still does not scroll horizontally.

This document is evidence for U04 only. It does not assert the demo gate is MET, does not claim any
chat-dependent shot, and authorises no recording, push, tag, publish or catalog change.
