# CP-015g re-run — one-course in-plugin acceptance (attempt on master adca16a6)

Card: `t_ad25d623`. Run started 2026-11-11 09:38 MST on the tree this card found on master.
**Outcome: BLOCKED by the host platform's own in-flight update — no Coursebook verdict.**
Nothing here is a partial green: no plan job was ever created, so the repaired validator seam
was not exercised to a verdict.

## Exact build (recorded, not assumed)

| fact | value |
|---|---|
| worktree HEAD | `adca16a6c33a641e0f5311e9aeab178aa886c29e` (`master`, D1 + D3 rebased into it) |
| branch | `wt/cp015g-rerun` |
| `desktop/plugin.js` in checkout | `0112000c418cfcb6815059020857eaf1b8a7299de3d863be1c3b0431cafa0c86` |
| rig home `…-cp015g-r2/home/desktop-plugins/coursebook/plugin.js` | `0112000c…` (identical) |
| operator `~/.hermes/desktop-plugins/coursebook/plugin.js` | `0112000c…` (identical) |
| backend | `hermes serve --isolated --port 44619` on a fresh home installed from this checkout (`scripts/install-local.sh`); `GET /api/plugins/coursebook/runtime` → 200 |
| window | dev Electron, vite renderer 5174, CDP 9433, 1344×768 |
| rig state | `~/.hermes/coursebook-test-cp015g-r2` (fresh home + fresh userdata) |

The three plugin.js copies are byte-identical, so nothing was tested against a stale module.

## What the run established

### 1. First-run Plugins inventory — REPRODUCED DEFECT (new card filed)

On a **fresh Desktop userdata** (no `hermes.desktop.pluginDecisions.v2`, verified absent from
localStorage), with the package installed and enabled in that home:

```
HERMES_HOME=<rig>/home hermes plugins list   ->  coursebook  enabled  0.1.0  git
window.hermesDesktop.desktopPluginsRoot()     ->  <rig>/home/desktop-plugins
window.hermesDesktop.readDir(root).entries    ->  ["coursebook"]
```

Yet Capabilities → Plugins showed **10 switches** (hermes-security, Rea, Bots, Disk Cleanup,
Kanban, Radio, Security Guidance, Omh, Bot Forge + Auto-update) and **no Coursebook row** —
before boot, after a full app restart, and after scrolling the whole 22 846 px pane (body text
expanded to 112 921 characters). A DOM text scan over the entire document found the string
"Coursebook" only in a chat-session title in the sidebar.

The plugin's own loader contract says a disabled plugin *still inventories* ("A disabled plugin
still inventories (settings shows it, the toggle reactivates via the handle above) —
`apps/desktop/src/contrib/runtime-loader.ts`). It did not inventory at all. Only after writing
`localStorage['hermes.desktop.pluginDecisions.v2'] = {"coursebook":true}` and restarting the app
did the Coursebook nav item and route appear. That decision-key write is the rig shortcut the
first run flagged; this run confirms the buyer-visible screen is still empty.

Filed as its own defect card: fresh-userdata Capabilities → Plugins omits Coursebook.

### 2. Create flow — reached step 2, then the host broke

The visible flow was driven from the Coursebook home:

- `01-create-step1.png` — "Start a new course" opened the goal step.
- Goal typed through the visible textarea:
  *"Set up a small backyard telescope and find and observe the moons of Jupiter on a clear night"*.
- `02-create-step2.png` — **Continue** advanced to step 2 of 3, "What shape should this course
  take?", with the three scope cards (One lesson / Short course / Full course) and the header
  still reading `Default view · Game`. This frame already shows the app's status bar reporting
  **"Backend inference unavailable"** and `# backend v0.23.0 (update…)`.
- The older `data-cb-scope-option` / `data-cb-create-step` markers from the first run no longer
  exist on this build, so the driver was rewritten to locate controls by their visible text.

No review frame exists: the run stopped at step 2 when the host broke.


At this point the host platform was mid-`hermes update`:

```
$ hermes profile list
⚠ A previous `hermes update` pulled new code but did not restart running gateways.
  Gateways may still be serving pre-update modules (mixed sys.modules).
  Run `hermes update` or `hermes gateway restart`.
```

Consequences observed inside the rig, in order:

1. `~/.hermes/hermes-agent/node_modules/electron` disappeared (the rig refused to start with
   "no dev Electron"), so the window was relaunched on
   `apps/desktop/node_modules/electron`, which still existed.
2. The renderer dropped to a blank document (`document.body.innerText === ""`), then to the
   app's own failure shell: **"Hermes couldn't load — Part of the app didn't load; reloading
   usually fixes it. Reload"**; Reload did not recover.
3. The Electron process then exited; CDP 9433 refused.

The vite dev server itself served 200 for `/` and `/src/main.tsx` throughout, so the breakage is
the Electron/renderer side of the operator's platform update, not Coursebook.

No `Create course` press was possible after the breakage (the review screen's controls were
never reachable), so the flow stopped before any plan job existed.

### 3. Spend record — zero

| metric | value |
|---|---|
| queue rows in rig `plugin-data/coursebook/data.db` | courses 0, plans 0, jobs 0 |
| provider calls | **0** |
| output tokens | **0** |
| image spend | 0 vision calls |
| `Try again` presses | 0 |

Nothing was authored, injected or patched; no fixture was used.

## Verdict

- **CP-015g re-run: BLOCKED (environment), not PASS and not RED on the product.** The D1
  validator-repair seam could not be exercised because the visible UI could not reach
  `Create course` while the host was replacing its own runtime.
- **New defect confirmed and filed:** fresh Desktop userdata shows no Coursebook row in
  Capabilities → Plugins although the package is installed, enabled, and its desktop folder is
  visible to the app's own bridge. The plugin only appears after the decision key is written by
  hand — exactly the first-run screen a buyer would see.
- Re-run requirement: after the operator's `hermes update` completes and the desktop app is
  restarted on a settled tree, run this card again unchanged. The rig state
  `~/.hermes/coursebook-test-cp015g-r2` can be reused (nothing was created in it).

## Frames (1344×768, rig window, files on disk)

`00-fresh-capabilities-plugins.png` — fresh-userdata Plugins inventory (no Coursebook row)
`01-create-step1.png` — goal step
`02-create-step2.png` — shape step (One lesson / Short course / Full course), Game default
`05-app-failure-shell.png` — "Hermes couldn't load / Part of the app didn't load" shell

No home, review, lesson, check, export or install frames exist because the product never
produced a plan and the host app stopped loading.

## Drivers (click/read the live DOM only; no backend RPC, no fixture data)

`scripts/cp015g-r2-nav.mjs`, `-start.mjs`, `-create-flow.mjs`, `-inspect.mjs`, `-find.mjs`,
`-plugins.mjs`, `-plugins2.mjs`, `-pane.mjs`, `-scroll.mjs`, `-root.mjs`, `-enable.mjs`,
`-reload.mjs`, `-route.mjs`, `-probe.mjs`, `-ls.mjs`.

Reproduce (after the host update settles):

```
ELECTRON_BIN=~/.hermes/hermes-agent/apps/desktop/node_modules/electron/dist/electron \
CB051_STATE=~/.hermes/coursebook-test-cp015g-r2 CB051_BACKEND_PORT=44619 \
CB051_CDP_PORT=9433 CB051_TOKEN=cb015g-r2-token scripts/rig-private-desktop.sh
CB015_CDP_PORT=9433 CP015G_OUT=docs/concept-parity/demo/cp015g-r2 node scripts/cp015g-r2-create-flow.mjs
```
