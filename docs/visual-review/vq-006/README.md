# VQ-006 capture packet

This directory is written by `scripts/vq-capture.sh` and judged by `scripts/vq-manifest.py`. Do not
hand-edit a frame or a cell record: re-run the command. The program doc is
`docs/launch/VISUAL-QUALITY-PROGRAM.md` §9.

```
<destination>--<width>.png     the route, clipped to [data-cb-route], at the requested route width
<destination>--<width>.json    the cell record: plugin sha, route state, every image and background layer
manifest.json                  the judge's verdict per cell, plus the Press Plate registry
MANIFEST.md                    the same, readable
contact-sheet.png              every captured frame on one labelled sheet
```

## What a cell record proves

- the window read the module named by `window.plugin.sha256` (`readPluginSource`, hashed in-page);
- the route rendered the requested destination, with fonts loaded and v3 primitives mounted;
- for every image in the route: its selector, `currentSrc`, natural size, rendered size, sha256, the
  bundled-asset path when the bytes match `desktop/cb-assets.generated.js`, and whether the row is a
  placeholder or a Press Plate (matched by sha256 against the bundled pack covers);
- the same for every `background-image` layer, plus `background-repeat` and `background-size`, so a
  tiling decoration is distinguishable from an upscaled illustration. A layer that tiles is not held
  to the 2x ratio; no background layer satisfies a display role.

## What this packet is not

- It is not a design fixture, a proof HTML or a component-lab render. The camera refuses those.
- A cell that fails is a finding about the installed product, not a harness bug. The manifest lists
  every reason.
- `manifest.json` separates **passed**, **failed** (a frame exists and the judge refused it) and
  **never captured** (no frame at all). A failed frame is never reported as a missing one.

## 2026-11-11 baseline — captured at `80a81fd7`, plugin `251a3948…`

16 of 24 matrix cells captured (Home, Discover, Course home, Design System × 1344/1049/900/460),
0 pass, 16 failed, 8 never captured. Classroom and World Studio were not captured from this library:
the three bundled packs are the only courses, none of them carries an approved Game world, and the
harness does not fabricate one.

| cell group | result |
|---|---|
| home ×4 | 0 of 4 display covers. At 1049/900/460 the two course covers are the bundled pack Press Plates (`cover-3x2.png` of the Japanese and technical packs); at 1344 the Home scene draws no course cover art. The fox ships at 128 px and renders at 88–220 px, below 2x. The 96×96 night vignette is stretched with `background-size: cover` (ratio 0.07–0.21) |
| discover ×4 | 0 of 8 collectibles; four Press Plates on the surface; the banner is a data-URI 864 px plate under 2x; the same stretched vignette layer |
| course-home ×4 | no image asset at all — DOM type, one inline contour and buttons; the fox role is also absent; the same stretched vignette layer |
| design-system ×4 | the installed plugin mounts no Design System surface (VQ-003 has not landed) |
| classroom, world-studio | never captured — no approved Game world in the seeded library |

The grain and shelf-plank background layers tile (`repeat`, `repeat-x`) and are exempt from the 2x
ratio; only the no-repeat vignette is flagged.

## Driver coverage (not evidence)

All six destination drivers were exercised. Classroom and World Studio were driven on a **copy** of
the preserved GM-004 rig home (worlds staged by `scripts/gm004-stage-worlds.py` behind a documented
synthetic media seam, not model output), only to prove the harness can reach those surfaces:

| destination | control that reached it |
|---|---|
| home | `[data-cb-nav-item="home"]` |
| discover | `[data-cb-nav-item="workshop"]` → `[data-cb-workshop-tab="discover"]` |
| course-home | `[data-cb-home-card-action]` |
| classroom | course home → "Open section" |
| world-studio | course home → `[data-cb-world-change]` ("Review the world"); falls back to the Courses destination → "Open course" when the desk has no world control |
| design-system | none — recorded as `missing_surface` |

Frames from that rig are not in this directory and are not evidence: its world art is a synthetic
tonal swatch stamped as such by `docs/visual-review/gm-004/MANIFEST.md`.
