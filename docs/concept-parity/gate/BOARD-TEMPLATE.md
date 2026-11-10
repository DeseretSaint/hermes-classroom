# BOARD-TEMPLATE — the side-by-side boards GM-016 scores

Card: CP-028. Five boards, one per ratified frame, each **equal width**, each built from a
route-clipped capture whose `.stamp.json` names the commit. Nothing here scores a screen; this is
the recipe and the rectangles.

Read `RUBRIC-V3.md` §1 first. A board built from an unstamped or pre-card capture is refused, not
scored.

---

## 1. Why this is not `cp-sbs.py` alone

`scripts/cp-sbs.py` scales both sides to the **shorter side's height**
(`target_height = min(concept.height, product.height)`). Two inputs only come out at equal width when
their aspect ratios already match. The concept frames are 1344×768 (1.75:1); a v3 route capture is
route-clipped and as tall as the route it holds (roughly 1049×600–1200). Piped straight in, the
product side comes out narrower than the concept side — the legacy
`docs/concept-parity/captures/sbs-home-live-1049-light.png` is 1344 wide on the left and 691 on the
right, and it also includes host chrome.

`docs/concept-parity/gate/board.py` fixes exactly that and nothing else: it crops the concept to the
rectangle below, crops the product to the **same aspect ratio** from the top of its route box, and
hands the pair to `scripts/cp-sbs.py`. Because the aspects are equal, cp-sbs's equal-height scaling
is an equal-width scaling. The tool asserts the two sides afterwards and refuses if they differ by
more than 1 px.

---

## 2. Crop rectangles (concept native pixels, 1344×768)

| Board | Screen (matrix id) | Frame | Region compared | `--crop x,y,w,h` | Aspect |
|---|---|---|---|---|---|
| B-HOME | `home.v3` (CP-022) | `refs/home.png` | threshold band + action pair + wooden shelf + lower ledge with fox and clock | `104,60,1240,708` | 1.751 |
| B-DISC | `discover.v3` (CP-021) | `refs/discover.png` | forest rail + feature banner + grid on one column track + fox at the grid foot | `220,96,1124,616` | 1.825 |
| B-CLASS | `classroom.v3` (CP-023) | `refs/classroom.png` | stamp stepper + framed scene + dialogue + check card + aside + evidence tray | `156,200,1188,568` | 2.092 |
| B-SYS | `lab.v3` (CP-020b) | `refs/system.png` | fox specimens + card anatomy + medallion row + palette + type + materials | `160,100,1138,640` | 1.778 |
| B-MAP | `course-home.v3` (CP-024) | `refs/map.png` | painted route field with hero plate + Continue aside + other-course shelf | `150,150,1090,550` | 1.982 |

Rules the rectangles encode, taken from SPEC §2 anchors and §5 region maps:

- every crop starts inside the content area (left ≥ 104) or at the rail only when the rail is part of
  the compared region (B-DISC starts at 220, i.e. **inside** the grid's left edge, so the rail is
  not compared there — the rail is compared on the product side by the shell check, not by pixels);
- the crop includes every region named in that screen's §5 region map, including the fox box where
  the frame has one;
- the crop never includes the frame's outer parchment border, so a difference in edge vignette is
  not mistaken for layout.

`R-SYS` is the lab sheet; `R-BOARD` is **not** a board source (it is a four-panel contact sheet whose
Home panel is unratified, REFS.md), and an archivist/heirloom panel is not scored in this gate.

---

## 3. Capture the product side (one capture per screen)

```bash
node scripts/cp-capture.mjs --name home-v3-1049-light \
  --out docs/concept-parity/captures --cdp-port 9411 \
  --state "$COURSEBOOK_TEST_STATE" --plugin desktop/plugin.js \
  --backend-url "$CB_BACKEND_URL" --token "$CB013_TOKEN" \
  --route-width 1049 --require-v3
```

- `--require-v3` is mandatory: it refuses unless `[data-cb-v3-ready]` is present, which is the only
  proof the v3 surface is the one on screen.
- The script clips to `[data-cb-route]` (stamp `crop_mode: "route"`), hard-reloads with an empty
  cache, refuses a stale module sha, and writes `<name>.stamp.json` beside the PNG. That stamp is the
  sha authority for the board.
- 1049 is the scoring width. 900 and 460 are scored from the matrix cells directly (RUBRIC §2.8);
  a board is built at 1049 only, because the concept frames are wide frames.
- If the host paints chrome over the route, `--crop-to-content` is allowed **and** the stamp's
  overlay geometry is recorded; a board built from a contaminated clip without that flag is refused.
- `node scripts/cp-capture.mjs --help` prints this usage; run it before a capture to confirm the
  flags exist in the checkout under review.

---

## 4. Build the board

One command per screen, run from the repo root:

```bash
python3 docs/concept-parity/gate/board.py --screen R-HOME \
  --product docs/concept-parity/captures/home-v3-1049-light.png \
  --out docs/concept-parity/gate/boards/board-home-v3-1049-light.png

python3 docs/concept-parity/gate/board.py --screen R-DISC \
  --product docs/concept-parity/captures/discover-v3-1049-light.png \
  --out docs/concept-parity/gate/boards/board-discover-v3-1049-light.png

python3 docs/concept-parity/gate/board.py --screen R-CLASS \
  --product docs/concept-parity/captures/classroom-v3-1049-light.png \
  --out docs/concept-parity/gate/boards/board-classroom-v3-1049-light.png

python3 docs/concept-parity/gate/board.py --screen R-SYS \
  --product docs/concept-parity/captures/lab-v3-1049-light.png \
  --out docs/concept-parity/gate/boards/board-lab-v3-1049-light.png

python3 docs/concept-parity/gate/board.py --screen R-MAP \
  --product docs/concept-parity/captures/course-home-v3-1049-light.png \
  --out docs/concept-parity/gate/boards/board-course-home-v3-1049-light.png
```

Expected output shape (verified below with a synthetic capture): the plan JSON, the delegated
`cp-sbs.py` argv, then `wrote <out> (<w>x<h>, left=1049 right=1049)` and
`equal width verified (1 px rounding)`.

Options: `--width 1049` (each side), `--gap 24`, `--background 247,241,228` (the concept paper).
`--dry-run` prints the plan and argv and writes nothing. `--product-box x,y,w,h` supplies the route
box in CSS px only when a capture has no stamp; `--allow-unstamped` exists only for a mechanics dry
run and prints a warning — never use it for a board that will be scored.

### Refusals you should expect rather than work around

| Refusal | Meaning | Fix |
|---|---|---|
| `REFUSED: ... has no .stamp.json` | the product side is not a capture-door frame | re-capture with `scripts/cp-capture.mjs` |
| `REFUSED: <screen> needs N CSS px of route height` | the route is shorter than the crop needs at 1049 | capture the screen at 1049 with the route tall enough (scroll position top); do **not** pad or upscale |
| `REFUSED: board sides are unequal` | aspect fix failed | report it as a tool defect; do not hand-stitch a board |

A hand-composited board, a board with burned-in labels, or a board whose two sides come from
different commits is not evidence (RUBRIC-V3 E1–E5).

---

## 5. What the reviewer verifies on the board

1. **Equal width** — both sides measure the same width within 1 px; the PNG's own metadata line
   records `left=` / `right=`.
2. **Same region** — the left side is the crop rectangle above; the right side is the top of the
   route box with the same aspect. If the product's compared region sits lower in the route than the
   concept crop does, that is stated in the scorecard's `remaining differences`, not cropped away
   silently.
3. **Same commit** — the stamp's `plugin.window_sha256` equals `git show <commit>:desktop/plugin.js |
   sha256sum`.
4. **No labels in the pixels** — the board carries no captions. Every label in a review packet is
   real DOM text in the capture or an explicit caption outside the image.
5. **Both themes only where the gate asks** — the board is a 1049 light frame. Dark, 900, 460,
   200 %, focus, reduced-motion and forced-colors are scored from the matrix cells, not from boards.

---

## 6. Verified invocations (CP-028)

Run in the CP-028 worktree on `wt/cp-028-gate`:

- `python3 docs/concept-parity/gate/board.py --help` → exit 0, usage printed.
- `python3 scripts/cp-sbs.py --help` → exit 0, usage printed.
- `python3 docs/concept-parity/gate/board.py --screen R-HOME ... --dry-run --allow-unstamped` →
  exit 0, plan JSON + delegated argv, nothing written.
- All five boards built from a **synthetic 1049×820 route image** (`--allow-unstamped`), each
  asserting equal sides: R-HOME 1049/1049, R-DISC 1049/1049, R-CLASS 1050/1049, R-SYS 1049/1049,
  R-MAP 1048/1049 (1 px rounding, accepted by the tool and by this template). Output went to
  `$HERMES_SCRATCH/cp028/`, not to the repo: a synthetic frame is a wiring test, not a capture and
  not evidence.
- `node scripts/cp-capture.mjs --help` → usage printed (the capture itself needs the live rig and is
  GM-016's run, not this card's).

The five real boards do not exist yet because the v3 screens do not exist yet. This card ships the
instrument; GM-016 runs §3→§4 once the last screen merges.
