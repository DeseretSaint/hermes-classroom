# H-150 — Library shelf, live rig evidence

Evidence card: `t_618af304` (H-150b). Implementation: `wt/h150-library-shelf` @
`a52e295` (rebased onto `origin/master` `428e6ab`). **No product code was edited by that card.**

> **H-150c (`t_35a40588`) fixes both findings below.** The branch tip is now `a9a75bf4…`; the
> product change, its gates and the re-measured frames are in
> [H-150c — the fix](#h-150c--the-fix-product) at the end of this document. Everything between
> "Verdict up front" and that section is the H-150b measurement at `a52e295`, kept as the record of
> what failed.

## Verdict up front

- **The capture is live.** Every PNG below is a renderer frame from the isolated Hermes Desktop
  window over CDP (`Page.captureScreenshot`), against the running Coursebook backend. No fixture
  HTML, stub SDK or hand-built DOM was rendered.
- **Frames were taken at `desktop/plugin.js` sha256
  `930c770e4f2df5b240475fa0d17b4ecf0d07ed1e309b3e14d888c993826b97fe`**, which equals the branch's
  file at `a52e295`:
  `sha256sum desktop/plugin.js` and
  `sha256sum ~/.hermes/coursebook-test-h150-2345/home/desktop-plugins/coursebook/plugin.js`
  return the same value. The window was restarted after that copy; it was not page-reloaded.
  (H-150c re-captured the shelf, ring and overlay frames at `a9a75bf4…` — see the last section.)
- **Overlay focus retention fails as measured.** After Enter or Space opens the preview,
  `document.activeElement` is `body` at both 1049 and 460 px; at 460 the list is hidden and the
  preview is open, so focus is not inside the preview either.
- **The focus ring still fails as a visible ring.** The inline `outline: 2px solid var(--cb-accent)`
  is present and computed (`solid 1.1156px rgb(44, 74, 140)`, offset `1.1156px`,
  `:focus-visible` true), but only the **top and bottom** strokes paint. The left and right strokes
  are clipped by the `MAIN.overflow-auto` container, which is exactly as wide as the row.

## What the shelf does

The Library destination is one shelf over the enrollments on this profile:

- one page `h1` — **Library** — in the route shell; the plate below it is **Packs on this profile**
  and carries the single lead ("Every pack installed on this profile…"); the destination word is
  not repeated as a second plate label;
- three filters — **All packs / Bundled / From someone else** — each with its own empty state
  ("No bundled pack on this profile", "No pack from someone else on this profile");
- one row per pack, with title, provenance badge, section count, the next-step line, a
  state-painted path and a single **Preview** button;
- a **whole-row target**: an absolutely positioned `RowButton` (`aria-label="Preview <title>"`,
  `aria-pressed`) covers the row (`inset: 0`), takes Enter and Space, and opens the preview; the
  row content is inert and the explicit Preview button sits above the overlay;
- a selected row paints `data-cb-pack-selected` plus the word **Selected** with a check icon — the
  cue is text, not colour alone;
- the preview (`data-cb-pack-preview`) carries one primary (Resume lesson / Open course) and one
  secondary (Archive), with pack identifiers under a **closed** `Technical details` disclosure;
- an empty pack names "No sections yet" once and keeps Preview (the manifest is inspectable).

## Rig provenance

| Item | Value |
| --- | --- |
| State dir | `/home/deseretsaint/.hermes/coursebook-test-h150-2345` |
| Window | Electron `--remote-debugging-port=9362`, pid `1070480`, page `http://127.0.0.1:5174/#/coursebook` |
| Plugin deployed to rig | `…/home/desktop-plugins/coursebook/plugin.js`, sha256 `930c770e…` |
| Branch | `wt/h150-library-shelf` @ `a52e295` (base `428e6ab`) |
| Product file | `desktop/plugin.js`, sha256 `930c770e…` |
| Harnesses | `scripts/h150-capture.mjs` (content/geometry, patched only to verify navigation), `scripts/h150-focus-probe.mjs` (focus) |
| Data | live `library.list` response: two local packs (2 and 4 sections) |

An earlier pass in this same session was **discarded**: it ran at the pre-rebase plugin
(`2affbbb…`) while H-150a concurrently rewrote the branch, and its first (light) pass raced the
route remount and captured **Home** instead of Library. The harness now retries navigation until
`data-cb-destination === "library"` and throws if a frame is about to be taken anywhere else; all
15 fact snapshots in `audit/ux/h150-shots/h150-facts.json` carry
`"destination": "library"`.

The earlier committed frames under `docs/h150-shots/` are superseded by this pass.

## Frames

Image files are device pixels; this Electron build applies page zoom ≈ 0.897, so a 1049 CSS-px
viewport captures as 941 px and a 460 CSS-px viewport as 413 px. `innerWidth` and root font were
read from the DOM at capture time.

| Frame | innerWidth | Root font | Theme | State | Shows |
| --- | ---: | ---: | --- | --- | --- |
| `light-1049.png` | 1049 | 16 px | light | Library / All packs, no selection | one h1, plate + one lead, filters, two rows |
| `light-900.png` | 900 | 16 px | light | same | reflow at 900 |
| `light-460.png` | 460 | 16 px | light | same | narrow split: route column 215 px beside the chat workspace |
| `dark-1049.png` | 1049 | 16 px | dark | same | dark tokens on the same shelf |
| `dark-900.png` | 900 | 16 px | dark | same | dark at 900 |
| `dark-460.png` | 460 | 16 px | dark | same | dark at 460 |
| `text200-light-460.png` | 460 | **32 px** | light | Library, preview open | 200 % text; preview is below the fold at this height |
| `text200-measured-light-460-full.png` | 460 | **32 px** | light | Library, no selection, row scrolled to top | 200 % text on the shelf itself |
| `focus-ring-light-1049-full.png` | 1049 | 16 px | light | row 0 focused | focus indicator (top/bottom strokes only) |
| `focus-ring-light-1049-blurred.png` | 1049 | 16 px | light | same row, blurred | A/B control for the accent-pixel count |
| `focus-ring-light-1049-zoom.png` | – | – | light | derived 4× crop of the full frame | the painted strokes |
| `focus-ring-light-460-full.png` | 460 | 16 px | light | row 0 focused | narrow focus indicator |
| `focus-ring-light-460-blurred.png` | 460 | 16 px | light | same row, blurred | A/B control |
| `focus-ring-light-460-zoom.png` | – | – | light | derived 4× crop | narrow strokes |
| `focus-ring-clip-control-520.png` | 520 | 16 px | light | row button with a 6 px test outline | only top/bottom strokes (clip control) |
| `focus-ring-renderer-control-520.png` | 520 | 16 px | light | fixed div with the same 6 px outline | full rectangle (renderer control) |
| `overlay-open-enter-1049.png` | 1049 | 16 px | light | Enter on row 0 | preview open beside the list; focus fell to `body` |
| `overlay-open-space-1049.png` | 1049 | 16 px | light | Space on row 1 | Japanese pack preview; focus fell to `body` |
| `overlay-open-space-460.png` | 460 | 16 px | light | Space on row 0 | list hidden, preview shown; focus fell to `body` |

The two `-zoom.png` files are nearest-neighbour 4× crops of the named full frames, not separate
captures: `focus-ring-light-1049-zoom.png` is `359×190+214+333` of
`focus-ring-light-1049-full.png`, and `focus-ring-light-460-zoom.png` is `180×251+1+421` of
`focus-ring-light-460-full.png` (crop boxes derived from the row rects in the probe JSON).

## Measured geometry

From `audit/ux/h150-shots/h150-facts.json` and `h150-focus-facts.json`:

- 1049 px: route column `x=237 w=407`; row `x=248 w=384 h=196`; the row overlay measures
  `384 × 195` (`inset: 0`), so the target covers the row; each row has 2 buttons (overlay +
  Preview).
- 460 px: route column `w=215` (the host keeps the chat workspace beside the route); row
  `x=11 w=185 h=264`; overlay `185 × 263`.
- `document.documentElement.scrollWidth - clientWidth = 0` at 1049, 900 and 460; no page-level
  horizontal overflow in any frame.

## Finding 1 — overlay focus retention: fails

Driven with real CDP key events (`Input.dispatchKeyEvent`), not JS-synthesised events.

| Step | activeElement | visible | preview open | list row visible |
| --- | --- | --- | --- | --- |
| 1049, before Enter | `button[aria-label="Preview Parent demo: measuring ingredients together"]` | yes | no | yes |
| 1049, after Enter | `body` | – | yes | yes |
| 1049, after Space (row 1) | `body` | – | yes | yes |
| 460, before Space | `button[aria-label="Preview Parent demo: measuring ingredients together"]` | yes | no | yes |
| 460, after Space | `body` | – | yes | **no** |

At 460 the selected row's list container is hidden (`narrowDetailOnly`), so the focused element is
removed from view and focus falls to `body`; nothing inside `data-cb-pack-preview` receives focus.
`overlay-open-space-460.png` is the frame for that state. This is reported as a **product defect**;
the implementation is not changed by this evidence card. The fix belongs to a product card
(focus the preview heading/back action when the list is hidden, and retain focus on the row when
the preview opens beside it).

## Finding 2 — focus ring: declared but not a visible ring

Measured on the focused row overlay:

- `activeElement` is the row's `button[aria-label="Preview …"]`; inline style is
  `outline: 2px solid var(--cb-accent); outline-offset: 2px`;
- computed: `outline-style: solid`, `outline-width: 1.1156px`, `outline-color: rgb(44, 74, 140)`,
  `outline-offset: 1.1156px`, `:focus-visible` = `true`.

What actually paints (exact `#2C4A8C` pixel counts, 1049 full frame):

| Frame | Accent pixels | Where |
| --- | ---: | --- |
| focused | 1174 | two 1-px rows at `y=341` and `y=519`, `x=224…564` (341 px wide) + progress bar |
| blurred | 492 | progress bar only |
| difference | **682** | exactly `2 × 341` — top and bottom strokes, no sides |

At 460 the same difference is `544 − 222 = 322 = 2 × 161`. Sampling the row's mid-height
(`y=430`, 1049) across `x=216…228` and `x=560…569` returns the background `rgb(247,241,228)`:
there is no left or right stroke. The 4× crops show the two blue rules at the row's top and bottom
edges and no vertical edges.

Cause, measured: the row's nearest clipping ancestor is
`MAIN.min-h-0.flex-1.overflow-auto`, whose box is the same width as the row (251 CSS px at the
moment of measurement). The 2 px/2 px-offset outline lies outside that box, so the side strokes are
clipped; the top and bottom strokes survive but are trimmed to the container width. A control
6 px `!important` outline on the same button painted only `225 × 185` device px — row width by row
height plus the two strokes — while a fixed-position `200 × 100` div with the same 6 px outline
painted 2,780 red pixels. The clipping is the scroll container, not the renderer. The two controls
are `focus-ring-clip-control-520.png` (6 px outline on the row button: only top/bottom strokes,
bbox `225×185`) and `focus-ring-renderer-control-520.png` (same 6 px outline on a fixed div: full
rectangle, 2,780 red pixels); both were taken at `innerWidth 520`.

**Verdict: still failing.** The computed outline exists, but what a keyboard user sees is two
accent rules at the row edges, not an enclosing ring. A negative `outline-offset` (inset ring) or
row padding inside the scroll container would be needed; that is a product change for a product
card.

### Why the committed harness printed `outline: none`

`scripts/h150-capture.mjs` measures its final focus sample at 460 px while a preview selection is
open. The list is hidden in that state, so `button.focus()` is a no-op on a `display: none`
element and the computed style is read from an unfocused (hidden) button. The probe moves the
measurement to a visible row and blurs it for the A/B control. The `outline: none 2.2312px` line in
`h150-facts.json` is a measurement artifact, not the product's focus behaviour.

## Finding 3 — 200 % text at the narrow split

`document.documentElement.style.setProperty('font-size','32px','important')` was set before
capture and read back: **root font 32 px, body 26 px** (`text200-measured-light-460`). At
`innerWidth 460` the route column is 215 px and the page has no horizontal scroll
(`scrollWidth = clientWidth = 460`). In that column the route heading clips ("Librar…"), the pack
title wraps mid-word (`Paren / t / demo: / meas / uring / ingre…`), and the metadata runs below the
fold. This is recorded as measured; it is a consequence of the host's 215 px route column at 460,
not of a 460 px-wide route. The 200 % evidence is therefore honest but limited: it proves the root
font assertion and the wrap/clip behaviour, not a full-width 460 layout.

## Content checks (live, from `h150-facts.json`)

- `h1` count 1, text **Library**; the word Library occurs once outside the nav (`plateLabels: 1`);
  the lead sentence occurs once (`leadCount: 1`).
- 2 rows: "Parent demo: measuring ingredients together" (local pack, 2 sections) and "Japanese
  affection and register — an L0 demonstration classroom" (local pack, 4 sections).
- Each row has 2 buttons (whole-row overlay + Preview); the overlay's `aria-pressed` flips, and the
  selected cue text is exactly **"Selected"**.
- Clicking a row opens `data-cb-pack-preview` with one primary ("Resume lesson" for the parent
  pack, "Open course" for the Japanese pack) and one secondary ("Archive"); "All packs" clears it.
- Enter and Space open the same preview (`afterKeyboardEnter`, `afterKeyboardSpace`:
  `previewPanel: true`, `selectedCount: 1`, cue "Selected").
- `Technical details` is closed by default (`open: false`); opening it reveals Pack ID, Pack
  version and Record revision. Learner text never contains `revision N` or `pack_<hex>`
  (`rawRevision: false`, `rawPackId: false`).
- The Bundled filter is a live empty state: "No bundled pack on this profile" (this profile has no
  bundled pack). "From someone else" returns both rows because both are `local` provenance, which
  is in that bucket by definition.
- No empty pack exists on this profile, so "No sections yet" count is 0; the empty-pack row is not
  claimed as captured.

## Reproduce

```bash
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_b171870c
sha256sum desktop/plugin.js    # 930c770e… at a52e295, a9a75bf4… at the H-150c tip
cp desktop/plugin.js ~/.hermes/coursebook-test-h150-2345/home/desktop-plugins/coursebook/plugin.js
COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-h150-2345 CB013_CDP_PORT=9362 \
  bash scripts/cb013-live-window.sh --restart
CB009_CDP_PORT=9362 node scripts/h150-capture.mjs audit/ux/h150-shots
CB009_CDP_PORT=9362 node scripts/h150-focus-probe.mjs audit/ux/h150-shots
```

## H-150c — the fix (product)

Product card `t_35a40588`, on the same branch. Product file `desktop/plugin.js` sha256
`a9a75bf4b5916ed31d9b7113fd62970198b457990c9f49352ccfc1194d71ecba`, byte-identical to the copy in
`~/.hermes/coursebook-test-h150-2345/home/desktop-plugins/coursebook/plugin.js`; the isolated window
was **restarted** after that copy (not reloaded). Every number below is from that window.

### What changed

- **The layout rule is one measured decision, not a window media query.** `PackShelfSplit` stacks the
  list and the preview at every width and, when the route column is under
  `CB_SHELF_COMPACT_WIDTH` (400 px), replaces the list with the preview once a pack is open. Route
  columns measured on this rig: 958 px in a 1600 px window, 407 at 1049, 257 at 900, 215 at 460.
  Measured in the deck, the emitted `47.5rem` rules are `.min-[47.5rem]:flex-row`, `:w-52` and
  `:gap-5` — there is no `.min-[47.5rem]:flex` and no `:w-72`, so the shelf's `hidden
  min-[47.5rem]:flex` list never un-hid and its intended 18rem column never applied. The shelf asked
  for a split the deck cannot draw.
- **Focus has one target per state.** `shelfFocusTarget(compact, detailOpen)` returns `'list'` when
  the row is still on screen and `'detail'` when it is not, so the pane the user can see is the pane
  that keeps focus. `LibraryView` stores that as a request object (`{target, key}`) and
  `PackShelfSplit` applies it after render; Enter and Space both go through the one `openPack`, so
  the two keys cannot diverge. `All packs` (the preview's back control) gained a
  `data-cb-pack-back` handle and returns focus to the row it came from.
- **The ring is inset.** `outline: 2px solid var(--cb-accent)` with `outline-offset: -2px` (the
  H-146a identity ring, unchanged colour and width) draws inside the row, so the `MAIN.overflow-auto`
  box that clipped the left and right strokes no longer can. Ring state still follows
  `:focus-visible`; a pointer press paints nothing.
- **Focus restored by script announces itself.** This Electron build moves `activeElement` without
  firing `focusin`, so React's `onFocus` does not run for a script focus; the split dispatches one
  `focusin` when, and only when, it actually moved focus, so a retained row paints its ring.

### Finding 1 — re-measured: passes

Real CDP key events, one press each (`keyDown` + `keyUp`), `document.activeElement` read after the
key:

| Window | Route | Shelf | Enter | Space | In scrollport | Page overflow |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1600 | 958 | stacked | row `Preview Parent demo…`, `:focus-visible` true | same | yes | 0 |
| 1049 | 407 | stacked | row `Preview Parent demo…`, `:focus-visible` true | same | yes | 0 |
| 900 | 257 | one-pane | preview `All packs` | same | yes | 0 |
| 460 | 215 | one-pane | preview `All packs` | same | yes | 0 |

`h150-focus-facts.json` (the repo probe) reads `wideAfterEnter`/`wideAfterSpace` as the row button
with `isBody: false`, and `narrowAfterSpace` as `insidePreview: true`, `visible: true`,
`isBody: false`, `previewPanel: true`. `h150c-focus-facts.json` carries the full per-width table
(`enter`/`space` → `isBody`, `isRowAction`, `insidePreview`, `listPaneDisplay`, `ring.state`).
After Enter at 460 the active element sits at `top 597, bottom 621` inside a scrollport of
`247…984` — visible, not merely present.

**A single Space press does not dismiss the preview it just opened.** The keydown opens it and moves
focus to `All packs`; the matching keyup does not activate that control (`space-keyup` measurement:
`afterDown` and `afterUp` both `previewOpen: true`, focus `All packs`).

### Finding 2 — re-measured: passes

Focused and blurred full frames per width are diffed; the changed pixel box is compared with the row
box measured in the DOM and the changed pixels are binned into the four edge bands of that box.

| Window | Computed outline | Diff box vs row box (device px) | Edge bands (px) | Painted side rows |
| ---: | --- | --- | --- | --- |
| 1600 | `solid 1.1156px rgb(44,74,140)`, offset `-1.1156px` | `270,290 427×135` vs `270,290 428×136` | 439 / 439 / 147 / 147 | left 135, right 135 |
| 1049 | same | `222,343 338×175` vs `222,342 338×176` | 350 / 350 / 187 / 187 | left 175, right 175 |
| 900 | same | `222,493 204×214` vs `222,491 204×216` | 216 / 216 / 226 / 226 | left 214, right 214 |
| 460 | same | `10,536 165×236` vs `10,536 166×237` | 177 / 177 / 248 / 248 | left 236, right 236 |

`middle` is 0 at every width: the only thing that changed between the focused and the blurred frame
is the ring itself. The left and right strokes are painted for the row's full height, so the ring
encloses the row on all four sides. `h150c-ring-facts.json` holds the numbers;
`h150c-ring-{1600,1049,900,460}.png` are the diff-box crops and
`h150c-ring-{focused,blurred}-<width>-full.png` the A/B frames.

### Harness correction (measurement, not product)

`scripts/h150-capture.mjs` and `scripts/h150-focus-probe.mjs` sent `rawKeyDown` **and** `keyDown`
for one press, which the renderer delivers as two keydowns. That was harmless while focus stayed put;
with the fix it made the 460 px Space sample read `previewPanel: false`, because the second press
activated the `All packs` control focus had just moved to. Both scripts now send one `keyDown` +
one `keyUp`. Re-run under the corrected harness, the same shelf reads `narrowAfterSpace:
insidePreview: true, previewPanel: true`.

`h150-focus-probe.mjs` also now establishes keyboard modality (one Tab) and announces the script
focus with one `focusin` before sampling the ring. The ring is the H-146a `:focus-visible` identity,
so a script focus straight after the harness's own click on `All packs` inherits that pointer
modality, the engine answers `:focus-visible` false, and the sample reads `outline: none` — a
measurement artifact, not a missing ring (the product repaints on the next keyboard stop).

### Content checks — unchanged

`h150-facts.json`, re-captured at `a9a75bf4…`: one `h1` (Library) with `plateLabels: 1` and
`leadCount: 1`; 2 rows, 2 buttons each; Enter and Space both open a preview with exactly one primary
(`Resume lesson` / `Open course`) and one secondary (`Archive`); the selected cue is the word
**Selected**; `Technical details` is closed by default and the raw pack id and record revision never
reach learner text; the Bundled filter is the live empty state; page overflow is 0 at 1049, 900 and
460.

### Frames re-captured at this sha

`focus-ring-light-1049{,-full,-blurred}.png`, `focus-ring-light-460{,-full,-blurred}.png`,
`overlay-open-enter-1049.png`, `overlay-open-space-1049.png`, `overlay-open-space-460.png`,
`text200-measured-light-460{,-full}.png` and the `light-*` / `dark-*` shelf frames now show the fixed
state; the older rows in the Frames table above describe what those files showed at `a52e295`. New
`h150c-*` frames:

| Frame | Shows |
| --- | --- |
| `h150c-focus-ring-<1600,1049,900,460>.png` (+ `-full`) | the focused row, inset ring |
| `h150c-focus-blurred-<width>.png` | the same row blurred — the A/B control |
| `h150c-ring-focused-<width>-full.png` / `h150c-ring-blurred-<width>-full.png` | full-viewport A/B pair |
| `h150c-ring-<width>.png` | crop at the diff's own box: the enclosing ring |
| `h150c-open-enter-<width>.png` / `h150c-open-space-<width>.png` | where focus lands after each key |
| `h150c-text200-open-460.png` | 200 % text (root 32 px), 460 px window, focus inside the preview |

### Layout consequence to review

At a 900 px window the route column is 257 px; the shelf is now one pane there (preview replaces the
list once a pack is open) instead of stacking both. At 1049 (407 px) and 1600 (958 px) the row stays
on screen and keeps focus. No other surface or harness behaviour changed.

