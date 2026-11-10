# CP-000 — render-path forensics and the one capture method

Date: 2026-11-10 (MST). Owner: `sentinel`. Branch: `wt/cp-000-render`, base `origin/master`
`de2d234` (concept-parity plan commit; its parent `00751f0` is the GM-006 merge named in the plan).
Reviewer: `cbqa`.

## 1. Question

Every recent screenshot that looked like "plain text on a blank page" had to be explained, and the
failure had to become impossible to submit again. This report separates **(a) capture method** from
**(b) the v2 design itself**, with measurements from both render paths, and ships the single capture
door (`scripts/cp-capture.mjs`) that refuses any frame that cannot prove what it shows.

## 2. Frame inventory and classification

| Packet | Frames | Path | Class | Provenance in its own manifest |
|---|---|---|---|---|
| `docs/visual-review/gm-002/` | 31 PNG | live Electron (`scripts/gm002-live-capture.mjs`) | **live rig** | "live capture from the isolated Electron window (Page.captureScreenshot)", plugin sha `bca1bcbe…` |
| `docs/visual-review/gm-002/renderer-frames/` | 2 PNG + 24 recorded frame rows | jsdom → static HTML → headless Chromium (`scripts/gm002-shot.mjs`) | **static render** | "static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)", `plugin_sha256: null` |
| `docs/visual-review/gm-004/` | 42 PNG | live Electron (`scripts/gm004-live-capture.mjs`) | **live rig** | "Page.captureScreenshot from a real, isolated Hermes Desktop window talking to a real `cb.rpc` backend", plugin sha `5918cdff…` |

Both packets' root PNGs are live captures. The only committed frames that are **static renders** are
under `gm-002/renderer-frames/`, and that packet's own `evidence.json` records **no plugin sha**.

## 3. The two paths, measured side by side

Same surface (`#/coursebook`, Home, 1049 px route width, light, 100 % text).

| Fact | Live rig (master module) | Static renderer |
|---|---|---|
| Module proof | window `readPluginSource` sha256 `7802e3ca3dd15cc7a19b61dff632666a14a6b14b23f8a1cf858dc246dbe01f52` (== checkout) | none recorded; `plugin_sha256: null` |
| Host chrome | 349 `[data-slot]` host nodes, `host_shell: true` | 0 host slots, no shell |
| Stylesheets / rules | 18 sheets, 1600 rules (host Tailwind + KaTeX + codicons + product inline) | 1 inline `<style>` block (`html,body` margin only) |
| Body font | host stack: `"Segoe WPC", "Segoe UI", …, system-ui` | `system-ui, -apple-system, "Segoe UI", sans-serif` |
| Heading font | `ui-serif, Georgia, "Iowan Old Style", …` | same CSS declaration, but no host font CSS loaded |
| Backend | `cb.rpc` wire v24, 93/93 methods implemented | none (no backend, no chat, no RPC) |
| Route images | 0 (`img` count in route) | 0 |
| Fonts settled | `document.fonts.status = loaded` | loaded (nothing to load) |
| Console errors | 0 | n/a |

Raw evidence: `docs/concept-parity/captures/home-live-1049-light.stamp.json` (live) and
`docs/visual-review/gm-002/renderer-frames/evidence.json` (static).

## 4. Root cause per frame class

**Class A — static renders (`gm-002/renderer-frames/`): plain text on a blank page.**
The renderer mounts the shipped component in Node and paints it into a bare HTML document. There is
no host stylesheet, no shell, no backend and no media route. The result is the component's inline
styles on a cream field with system type: exactly the "formatted text" look. This is a **capture
method** failure, not a product render. These frames were already labelled "supplementary, not
evidence" in the GM-002 manifest; CP-000 closes the hole by refusing this path as evidence at all.

**Class B — live v2 rigs (`gm-002/`, `gm-004/`): styled but materially flat.**
The live frames do have chrome, host type, 18 stylesheets and real state. What they *lack* is intrinsic
to v2: `desktop/plugin.js` has **0 `boxShadow`, 0 `@font-face`, 0 `<style>` elements and no
`assets/`**, so every course card is a typographic block and every "cover" is a monogram. Route `img`
count is 0 on Home. The gap here is the **v2 design**, not the capture: no capture method can add
material the module never renders.

**Class C — capture framing.** Previous packets shot the **full window**: host status rails, session
sidebar and bottom bar occupy the frame and shrink the route. Measured in the live rig, a 1433 px
window at ~0.896 zoom gives the route 1196 px when the sidebar is closed and 813 px with it open;
the route pane's own width is what the design must be judged at. `cp-capture.mjs` crops to
`[data-cb-route]` and records both `route.width` and `window_width`.

**Class D — unverifiable provenance.** No prior packet could answer "which module produced this
frame?" from the frame itself. GM-002 recorded a sha in the manifest but not in the image evidence;
the static packet recorded none. `cp-capture.mjs` puts the sha the **window** read into every stamp.

### How much of the gap is capture vs design

- Capture method explains **all** of the no-chrome/no-host-CSS/no-backend class (Class A) and the
  framing distortion (Class C).
- The v2 design explains **all** of the missing art, custom type, elevation and material in the live
  frames (Class B). Those live frames render correctly; they simply render a contract that forbids
  the concept's materials (`docs/concept-parity/PLAN.md` §2.1).
- Verifiability (Class D) is a third, separate defect: a frame that cannot prove its module sha is
  not evidence, whichever path produced it.

## 5. The one capture method

`scripts/cp-capture.mjs` is the only evidence door from CP-000 onward. It **refuses** (exit 2,
`<name>.refused.json`, no PNG, no stamp) unless:

1. the plugin source the window reads hashes to the checkout module sha (`--expect-sha` optional);
2. `[data-cb-route]` exists and no `[data-cb-render-error]` / `[data-cb-route-error]` /
   `[data-cb-render-failed]` / `[data-cb-error-page]` marker is present;
3. `document.fonts.status === 'loaded'`;
4. every `img` inside the route is complete with `naturalWidth > 0`;
5. with `--require-v3`, `[data-cb-v3-ready]` is set (inert until v3 lands; it fails today, by design).

It hard-reloads with `ignoreCache` before probing, calibrates the emulated width against the rig's
~0.896 zoom until the **route** is the requested width, grows the viewport to the route height,
emulates reduced motion / forced colors only on request, crops to the route box, and writes
`<name>.png` plus `<name>.stamp.json` (plugin expected/window sha + loaded path + bytes; backend
`wire_version`, contract method count, implemented count, `plugin_root`; route width/height, window
width, theme, root font, motion posture, reduced-motion and forced-colors booleans, fonts status,
font faces, image decode counts, stylesheet/rule counts, host slot count, ancestor chain; console
error list; capture sha256/bytes/clip; timestamp).

### Demonstrated stale-module refusal (live, not a fixture)

Before the final capture the live rig was serving GM-004's module (`5918cdff…`). Running the tool
against master's checkout produced:

```
REFUSED (home-live-1049-light): stale module: window reads 5918cdffc94b4ac5047421fd2cd44bebfdd329b528685e185c90466d0f4f273b,
expected 7802e3ca3dd15cc7a19b61dff632666a14a6b14b23f8a1cf858dc246dbe01f52
```

(after the symlink swap the same run produced a valid stamp; the rig's original plugin, marker and
link target were restored to `5918cdff…` afterwards). The fixture tests reproduce the same refusals
deterministically: `tests/test_cp_capture_stamp.py` (5 tests, OK) covers valid stamp schema, stale
sha, unsettled fonts, undecoded image and a painted render-error branch.

## 6. Cold route paint baseline (v3 comparison point)

`scripts/cp-cold-paint.mjs` (reload with empty cache; waits for a **new document** via
`performance.timeOrigin`, then for a non-zero `[data-cb-route]` box):

| run | ms |
|---|---|
| 1 | 1679 |
| 2 | 1671 |
| 3 | 1792 |

**Median 1679 ms** (min 1671, max 1792), 812.8 × 684.5 px route, host boot + first RPC paint
included. Raw: `docs/concept-parity/captures/cold-paint-baseline.json`. v3 may not regress this
beyond noise without a recorded reason.

## 7. Known limits / disclosure

- A **brand-new** disposable home built from master (`~/.hermes/coursebook-test-cp000-0302`) installs
  cleanly (`install-local.sh` 7/7, plugin copy sha matches) but its Desktop window never leaves the
  host's boot state in this environment: the forced-local gateway child exits (`runtime_exited`),
  the status stack stays on "Backend checking", and no plugin route is contributed. The same result
  follows a clone of the GM-004 state rewritten to a new home/backend/CDP port, so this is a host
  boot fault, not a plugin or state defect. Screenshots taken in that window would be invalid (no
  route to stamp); none were taken.
- The live capture above therefore uses the **preserved GM-004 rig's window/backend** (real session,
  real `cb.rpc`, wire v24 / 93 methods) with the **renderer module swapped to master's
  `7802e3ca…`**, verified in-window by the stamp. The backend `plugin_root` recorded in the stamp is
  the GM-004 checkout (`t_1575d158`); its contract surface is identical to master's (93/93, v24),
  and the renderer under test is master. A future capture on a healthy fresh rig should replace this
  frame; the tool will record the difference.
- No UI/paint change is proposed here. This card may not edit `desktop/plugin.js`; the v3 material
  gap belongs to CP-002/CP-006 and the screen cards.

## 8. Artifacts

- `scripts/cp-capture.mjs` — capture + refusal gates + stamp.
- `scripts/cp-cold-paint.mjs` — cold route paint measurement.
- `scripts/cp-sbs.py` — equal-height concept/product side-by-side.
- `tests/test_cp_capture_stamp.py` + `tests/fixtures/cp-capture/*.html` — stamp schema and refusal tests.
- `docs/concept-parity/captures/home-live-1049-light.png` + `.stamp.json` — live capture of master's
  module with a valid stamp.
- `docs/concept-parity/captures/home-live-1049-light.refused.json` — the stale-module refusal recorded
  on the live rig before the swap.
- `docs/concept-parity/captures/cold-paint-baseline.json`, `sbs-home-live-1049-light.png`.
