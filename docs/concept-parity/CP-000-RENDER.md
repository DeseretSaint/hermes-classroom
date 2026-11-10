# CP-000 — render-path forensics and the one capture method

Date: 2026-11-10 (MST). Owner: `sentinel`. Branch: `wt/cp-000-render`, base `origin/master`
`de2d234` (concept-parity plan commit; its parent `00751f0` is the GM-006 merge named in the plan).
Reviewer: `cbqa`. Round 2 (see §9 for the review findings this round closes).

## 1. Question

Every recent screenshot that looked like "plain text on a blank page" had to be explained, and the
failure had to become impossible to submit again. This report separates **(a) capture method** from
**(b) the v2 design itself**, with measurements from both render paths, and ships the single capture
door (`scripts/cp-capture.mjs`) that refuses any frame that cannot prove what it shows.

## 2. Frame inventory and classification

The full per-file inventory (md5, bytes, manifest row, classification, reason) is generated and
gated by `scripts/cp-frame-inventory.py` → `docs/concept-parity/frame-inventory.json`.

| Packet | PNG on disk | Manifest rows | Class | Provenance in its own manifest |
|---|---|---|---|---|
| `docs/visual-review/gm-002/` | **32** | 31 | 31 **live rig** + 1 **unverifiable** | "live capture from the isolated Electron window (Page.captureScreenshot)", plugin sha `bca1bcbe…` |
| `docs/visual-review/gm-002/renderer-frames/` | 2 | 24 (frame rows, no per-file rows) | **static render** | "static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)", `plugin_sha256: null` |
| `docs/visual-review/gm-004/` | 42 | 42 | **live rig** | "Page.captureScreenshot from a real, isolated Hermes Desktop window talking to a real `cb.rpc` backend", plugin sha `5918cdff…` |

**The one frame with no manifest row** is
`docs/visual-review/gm-002/home.course--460--light--200--continue.png` (413×900, md5
`39ac247b0a23264e13bcf13d17976ba7`). It has no row in `live-evidence.json`: no module sha, state dir,
captured state or hash record. It is classified **`unverifiable`** in the inventory with that reason
and must not be used as evidence. The two PNG stills under `renderer-frames/` are stills from the
static-render packet (their HTML frames are the 24 rows in `frames.json`; `evidence.json` has no
per-file rows), so they are classified **`static-render`**.

Both packets' manifest-listed root PNGs are live captures. The only static-render frames are under
`gm-002/renderer-frames/`, and that packet records **no plugin sha** anywhere.

## 3. The two paths, measured side by side

Same surface (`#/coursebook`, Home, 1049 px route width, light, 100 % text).

| Fact | Live rig (master module) | Static renderer |
|---|---|---|
| Module proof | window `readPluginSource` sha256 `7802e3ca3dd15cc7a19b61dff632666a14a6b14b23f8a1cf858dc246dbe01f52` (== checkout) | none recorded; `plugin_sha256: null` |
| Host chrome | 289 `[data-slot]` host nodes, `host_shell: true` | 0 host slots, no shell |
| Stylesheets / rules | 18 sheets, 1600 rules (host Tailwind + KaTeX + codicons + product inline) | 1 inline `<style>` block: `html, body { margin: 0; padding: 0; } body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }` |
| Body font | host stack: `"Segoe WPC", "Segoe UI", …, system-ui` | `system-ui, -apple-system, "Segoe UI", sans-serif` (from that inline block) |
| Heading font | `ui-serif, Georgia, "Iowan Old Style", …` | the component's own serif declaration; no host font CSS is loaded |
| Backend | `cb.rpc` wire v24, 93/93 methods implemented | none (no backend, no chat, no RPC) |
| Route images | 0 (`img` count in route) | 0 |
| Fonts settled | `document.fonts.status = loaded` | loaded (nothing to load) |
| Console errors | 0 | n/a |

Raw evidence: `docs/concept-parity/captures/home-live-1049-light.stamp.json` (live) and
`docs/visual-review/gm-002/renderer-frames/frames.json` (the recorded static HTML; `evidence.json`
holds tokens and per-frame assertions but **no** font-family or stylesheet fields — the earlier
round cited the wrong file).

## 4. Root cause per frame class

**Class A — static renders (`gm-002/renderer-frames/`): plain text on a blank page.**
The renderer mounts the shipped component in Node and paints it into a bare HTML document whose only
CSS is the margins + `system-ui` body stack quoted above. There is no host stylesheet, no shell, no
backend and no media route. The result is the component's inline styles on a cream field with system
type: exactly the "formatted text" look. This is a **capture method** failure, not a product render.
These frames were already labelled "supplementary, not evidence" in the GM-002 manifest; CP-000
closes the hole by refusing this path as evidence at all.

**Class B — live v2 rigs (`gm-002/`, `gm-004/`): styled but materially flat.**
The live frames do have chrome, host type, 18 stylesheets and real state. What they *lack* is intrinsic
to v2: `desktop/plugin.js` has **0 `boxShadow`, 0 `@font-face`, 0 `<style>` elements and no
`assets/`**, so every course card is a typographic block and every "cover" is a monogram. Route `img`
count is 0 on Home. The gap here is the **v2 design**, not the capture: no capture method can add
material the module never renders.

**Class C — capture framing and an unpainted emulated viewport.** Two distinct causes, both now
gated:

- *C1, past packets:* full-window screenshots include the host session sidebar, status rails and
  bottom bar. Measured in the live rig, a 1433 px window at ~0.896 zoom gives the route 1196 px with
  the sidebar closed and 813 px with it open; the route pane's own width is what the design must be
  judged at.
- *C2, the CP-000 round-1 frame:* the committed `home-live-1049-light.png` was itself contaminated
  by an L-shaped `#0D1015` band — right band from x≈916 CSS, bottom band from y≈1325 CSS of a
  1049×1462 clip. The bands were **not** host chrome painted over the route: the rig ran a page zoom
  of 89.6 %, and under a non-100 % zoom `Emulation.setDeviceMetricsOverride(width=1153)` produces a
  layout viewport of 1286 CSS px while Chromium paints only the first 1153 CSS px. The route's last
  ~133 px horizontally and ~137 px vertically were never painted, so the document background showed
  through; the host text inside the bottom band (`deseretsaint`, `Off`, `client v0.23.0+1`) is
  compositor surface outside the painted area, not product UI. The stamped `route.width: 1049`
  therefore overstated the painted product surface.

`cp-capture.mjs` now normalises page zoom to 100 % through the host's own zoom bridge, records
`zoom.original_percent / capture_percent / restored_percent`, restores the operator setting, and
crops to `[data-cb-route]` (or, with `--crop-to-content`, to the recorded unoccluded content rect).
The shipped frame now stamps `route.width = content_width = 1049`, `host_overlay_points = 0/384`,
and a pixel check of `host_bg_fraction = 0` (`0` host-background pixels in 116 900 sampled).

**Class D — unverifiable provenance.** No prior packet could answer "which module produced this
frame?" from the frame itself. GM-002 recorded a sha in the manifest but not in the image evidence;
the static packet recorded none; one gm-002 frame has no manifest row at all. `cp-capture.mjs` puts
the sha the **window** read into every stamp, and `scripts/cp-frame-inventory.py` fails when a packet
PNG has neither a manifest row nor an explicit unverifiable entry.

### How much of the gap is capture vs design

- Capture method explains **all** of the no-chrome/no-host-CSS/no-backend class (Class A), the
  full-window framing distortion (C1) and the unpainted-band frame (C2).
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
5. **no host element occludes the route** — a 16×24 hit-test grid inside the route box reports any
   element painted above it. A contaminated clip is refused unless `--crop-to-content` is passed, in
   which case the overlay geometry is recorded and the crop is the unoccluded content rect;
6. **the captured pixels contain no significant share of the document background** when the route
   paints a different colour (`>2 %` of sampled pixels vetoes the frame);
7. the page zoom during capture is 100 % (`zoom_neutral`), so the emulated viewport is fully painted;
8. with `--require-v3`, `[data-cb-v3-ready]` is set **and** `[data-cb-v3-textures="ready"]` — a
   ground whose material tiles settled as `fallback` is flat paper, not v3 evidence;
9. the renderer logged no React duplicate/missing `key` warning; a warning-noisy tree is refused
   even when every visual gate passes, because the console is the only place React says so.

It hard-reloads with `ignoreCache` before probing, normalises and then restores the page zoom,
calibrates the emulated width until the **route** is the requested width, grows the viewport to the
route height, emulates reduced motion / forced colors only on request, crops to the route box, and
writes `<name>.png` plus `<name>.stamp.json` (plugin expected/window sha + loaded path + bytes;
backend `wire_version`, contract method count, implemented count, `plugin_root`; route width/height,
`content_width`, `content_height`, `content_rect`, `host_overlays`, `host_overlay_fraction`,
`html_background`, `background_color`, window width, theme, root font, motion posture,
reduced-motion and forced-colors booleans, fonts status, font faces, image decode counts,
stylesheet/rule counts, host slot count, ancestor chain; zoom original/capture/restored percent;
console error list; capture sha256/bytes/`crop_mode`/clip/`pixel_check`; timestamp).

### Demonstrated refusals (live, not a fixture)

Before the final capture the live rig was serving GM-004's module (`5918cdff…`). Running the tool
against master's checkout produced:

```
REFUSED (home-live-1049-light): stale module: window reads 5918cdffc94b4ac5047421fd2cd44bebfdd329b528685e185c90466d0f4f273b,
expected 7802e3ca3dd15cc7a19b61dff632666a14a6b14b23f8a1cf858dc246dbe01f52
```

The same live run also exercised the new gates on a clean frame (`no_host_overlay`,
`no_unpainted_region`, `zoom_neutral` all true) and recorded the refusal in
`captures/home-live-1049-light.refused.json`. After repointing the rig's plugin symlink at this
worktree, the same command stamped master's `7802e3ca…`; the rig's original symlink target and
`desktop-plugins` copy were restored to `5918cdff…` afterwards.

The fixture suite reproduces every refusal deterministically and adds the contamination class:
`tests/test_cp_capture_stamp.py` (8 tests, OK) covers valid stamp schema, stale sha, unsettled fonts,
undecoded image, a painted render-error branch, a host-occluded route (refused), the same page with
`--crop-to-content` (stamp records `host_overlays`, `content_width` and a clean pixel check), and the
backend block shape (`wire_version` 24, 93/93) against a recorded stub runtime.

## 6. Cold route paint baseline (v3 comparison point)

`scripts/cp-cold-paint.mjs` reloads with an empty cache, waits for a **new document** via
`performance.timeOrigin`, then for a non-zero `[data-cb-route]` box. It reads the module sha through
the same in-window `readPluginSource` door as the capture tool and refuses to report a baseline on a
sha mismatch.

| run | ms |
|---|---|
| 1 | 1777 |
| 2 | 1646 |
| 3 | 1535 |

**Median 1646 ms** (min 1535, max 1777). The record is pinned to: module
`7802e3ca3dd15cc7a19b61dff632666a14a6b14b23f8a1cf858dc246dbe01f52` (= master checkout), state dir
`~/.hermes/coursebook-test-gm004-203620`, backend `cb.rpc` wire v24 with 93/93 implemented
(`plugin_root` `t_1575d158`), theme light, 808.5 × 681.6 px route, page zoom 90 %, host boot + first
RPC paint included. Raw: `docs/concept-parity/captures/cold-paint-baseline.json`.
`tests/test_cp_cold_paint.py` asserts the provenance fields exist and that a mismatched sha exits 2
with `ok: false`. v3 may not regress this beyond noise without a recorded reason.

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
- The capture door sets the rig's page zoom to 100 % for the shot and restores it through
  `window.hermesDesktop.zoom`. The bridge reports an integer `percent`, so the rig is restored to
  its recorded 90 % (not the original fractional 89.64 %); `stamp.zoom` records both values and the
  restoration. This affects the disposable test rig only, never the operator's app.
- No UI/paint change is proposed here. This card may not edit `desktop/plugin.js`; the v3 material
  gap belongs to CP-002/CP-006 and the screen cards.

## 8. Artifacts

- `scripts/cp-capture.mjs` — capture + refusal gates (module sha, route, fonts, images, host
  occlusion, pixel contamination, zoom) + stamp.
- `scripts/cp-cold-paint.mjs` — cold route paint measurement with module/state/backend provenance.
- `scripts/cp-frame-inventory.py` + `docs/concept-parity/frame-inventory.json` — per-file frame
  inventory and the `--check` gate over the review packets.
- `scripts/cp-sbs.py` — equal-height concept/product side-by-side.
- `tests/test_cp_capture_stamp.py` + `tests/fixtures/cp-capture/*.html` — stamp schema, refusal and
  contamination tests.
- `tests/test_cp_cold_paint.py` — baseline provenance and stale-sha refusal.
- `tests/test_cp_frame_inventory.py` — inventory completeness (incl. the unverifiable gm-002 frame).
- `docs/concept-parity/captures/home-live-1049-light.png` + `.stamp.json` — live capture of master's
  module with a valid stamp (route 1049×1166, `content_width` 1049, 0 host-background pixels).
- `docs/concept-parity/captures/home-live-1049-light.refused.json` — the stale-module refusal recorded
  on the live rig before the swap.
- `docs/concept-parity/captures/cold-paint-baseline.json`, `sbs-home-live-1049-light.png`.

## 9. Round-2 closures (review 814)

| Finding | Closure |
|---|---|
| F1 — route crop contained host chrome; `route.width` overstated the painted surface; §4 claimed Class C fixed | Root-caused to the zoom/emulation paint mismatch (§4 C2). Capture normalises zoom to 100 %, adds `host_overlays`, `content_width/height`, `content_rect`, a hit-test occlusion gate and a post-capture pixel veto. Shipped frame: 0 host-bg pixels, `content_width == route.width == 1049`. Fixture `host-overlay.html` covers refuse + `--crop-to-content`. §3/§4 corrected. |
| F2 — inventory missed one gm-002 frame | `scripts/cp-frame-inventory.py` + `frame-inventory.json` + `tests/test_cp_frame_inventory.py`; the frame is named here and classified `unverifiable` with its md5. |
| F3 — static facts cited from `evidence.json`, block mis-described | §3 now cites `renderer-frames/frames.json` and quotes the block including the `body { font-family: system-ui… }` declaration. |
| F4 — cold-paint baseline had no module provenance | `cp-cold-paint.mjs` reads the sha through `readPluginSource`, stamps sha/state dir/backend/theme/route/zoom, and refuses on mismatch; `tests/test_cp_cold_paint.py` covers both paths. Baseline re-measured on master: median 1646 ms. |
| F5 — schema test did not assert the backend block | `test_backend_block_shape_is_stamped` runs the capture against a recorded stub runtime and asserts `wire_version`, contract method count, implemented count and `plugin_root`; `test_valid_fixture_writes_stamp_and_png` asserts the full gate set and pixel-check block. |

## 10. Addressable destinations (CP-038)

The door previously reloaded and only then set `#/coursebook`, so a capture could only ever photograph
Home, and a frame named for another surface was indistinguishable from a Home frame. CP-038 makes a
capture addressable and makes the provenance explicit:

- `--destination home|courses|workshop|studio|#/course/<id>|#/learn/<id>` reaches the surface through
  the product's own control (`[data-cb-nav-item]`, `[data-cb-home-card-action]`,
  `[data-cb-section-row]`) and **refuses** (exit 2, no PNG/stamp) unless the rendered route matches.
  The hash is set before the hard reload and re-asserted if the host restores a session route.
- `--click <selector>` (repeatable) clicks through a state (a selected line, an opened check card)
  after the destination renders; `--scroll <selector|px>` scrolls a region inside the route after the
  viewport is sized and refuses if it would move `[data-cb-route]` out of the crop.
- The stamp now carries `destination{requested,normalized,rendered,rendered_course_home,
  rendered_lesson_view,match,controls}`, `route.destination/course_home/lesson_view/marker_names`,
  `clicks` and `scroll`, so a still cannot lie about where it came from.
- The door also waits for route images to settle (`--image-wait`, 15 s) and every `Runtime.evaluate`
  has a timeout: a dead host bridge produced a silent hang before. The wait is not passive: every
  pending `[data-cb-route] img` is forced to `loading="eager"` and decoded, and a zero-image route is
  accepted only after it is stable for three polls. This is what makes a Workshop frame possible at
  all — its non-hero covers are lazy and sit below the capture viewport, so a passive wait polled
  `{total:3,pending:1}` until it refused.
- `--appearance system|light|dark` drives the product's own settings sheet (open → choose the
  palette → close) and **refuses** unless the route repaints to the requested `data-cb-scope`. The
  palette is a per-profile product setting, not `prefers-color-scheme`; `--color-scheme` remains for
  hosts whose theme does follow the media feature and is refused when it does not. The stamp carries
  `appearance{requested,before,applied,rendered_scope,clicks}` and the gate adds
  `appearance_applied`, so a `-light` still can never be a dark frame.
- A success deletes any stale `<name>.refused.json` from an earlier run, so a packet cannot carry
  both REFUSED and OK for one still.

`tests/test_cp_capture_route.py` covers home unchanged, a non-Home destination, a course
destination, a wrong/unknown destination (exit 2, no frame), a destination control that renders a
different route (the CP-021 defect; exit 2 with `destination.match=false`), click state, scroll,
missing click/scroll selectors, a lazy offscreen image being forced to decode, the appearance
setting producing a real light frame, an unknown appearance, and a success clearing a stale refusal.
