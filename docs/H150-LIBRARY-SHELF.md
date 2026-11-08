# H-150 — Library shelf, live rig evidence

Evidence card: `t_618af304` (H-150b). Implementation: `wt/h150-library-shelf` @
`a52e295` (rebased onto `origin/master` `428e6ab`). **No product code was edited by this card.**

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
sha256sum desktop/plugin.js    # 930c770e…
cp desktop/plugin.js ~/.hermes/coursebook-test-h150-2345/home/desktop-plugins/coursebook/plugin.js
COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-h150-2345 CB013_CDP_PORT=9362 \
  bash scripts/cb013-live-window.sh --restart
CB009_CDP_PORT=9362 node scripts/h150-capture.mjs audit/ux/h150-shots
CB009_CDP_PORT=9362 node scripts/h150-focus-probe.mjs audit/ux/h150-shots
```
