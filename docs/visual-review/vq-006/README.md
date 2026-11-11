# VQ-006 capture packet

This directory is written by `scripts/vq-capture.sh` and judged by `scripts/vq-manifest.py`. Do not
hand-edit a frame or a cell record: re-run the command. The program doc is
`docs/launch/VISUAL-QUALITY-PROGRAM.md` §9.

```
<destination>--<width>.png     the route, clipped to [data-cb-route], at the requested route width
<destination>--<width>.json    the cell record: run id, plugin sha, route state, every image and layer
evidence/<sha256>.<ext>        the inventoried bytes for rows that can satisfy a required display role
manifest.json                  the judge's verdict per cell, plus the Press Plate registry
MANIFEST.md                    the same, readable
contact-sheet.png              every captured frame on one labelled sheet
```

## What a cell record proves

- the window read the module named by `window.plugin.sha256` (`readPluginSource`, hashed in-page),
  on a live `http(s)` page, including when the destination was refused as `missing_surface`;
- the route rendered the requested destination, with fonts loaded and v3 primitives mounted;
- **required display roles are backed by bytes**: for every image row that could satisfy one, the
  packet holds its inventoried bytes under `evidence/`, and the record points at them as
  `evidence/<row sha256>.<raster ext>`. The judge treats that path as untrusted: anything else —
  absolute, `..`, another directory, a name that is not the row's own sha256 — is refused, as are
  bytes identical to the cell screenshot. It re-hashes the file against the row's `sha256` and reads
  the raster header, so the declared natural size has to match the file, and one asset cannot count
  twice toward a role. A required-role row without that backing is refused;
- for every image in the route: its selector, `currentSrc`, natural size, rendered size, sha256, the
  bundled-asset path when the bytes match `desktop/cb-assets.generated.js`, and whether the row is a
  placeholder or a Press Plate (matched by sha256 against the bundled pack covers);
- the same for every `background-image` layer, plus `background-repeat` and `background-size`, so a
  tiling decoration is distinguishable from an upscaled illustration. The 2x rule is applied per
  axis: an axis is exempt only when the layer repeats on it and paints it at the file's own size
  (`auto` or a length), so a `repeat` + `auto` grain tile is decoration, a `repeat-x` + `auto 100%`
  plank is judged on height only, and a `repeat` + `cover` layer is still an upscale. No background
  layer satisfies a display role.

The record alone is not proof of every number in it. `rendered` geometry, `kind`, `complete`, the
background `repeat`/`size` and the screenshot clip are camera-asserted: they describe what the live
DOM measured, and a record edited after capture can still lie about them. The screenshot bytes and
the required-role evidence above are the parts the judge re-verifies from files.

## What this packet is not

- It is not a design fixture, a proof HTML or a component-lab render. The camera refuses those.
- A cell that fails is a finding about the installed product, not a harness bug. The manifest lists
  every reason.
- `manifest.json` separates **passed**, **failed** (a frame exists and the judge refused it) and
  **never captured** (no frame at all). A failed frame is never reported as a missing one.

## 2026-11-11 baseline — captured at `a78ce220`, plugin `251a3948…`

16 of 24 matrix cells captured (Home, Discover, Course home, Design System × 1344/1049/900/460),
0 pass, 16 failed, 8 never captured. Classroom and World Studio were not captured from this library:
the three bundled packs are the only courses, none of them carries an approved Game world, and the
harness does not fabricate one.

This packet predates the `evidence/` directory and the `run.id` field. Its captured cells already
fail the 2x/Press-Plate/required-role rules, so no required-role row is asked for backing and the
verdicts are unchanged; `manifest.json` reports `Capture run: unrecorded`. A re-capture with the
current harness writes `evidence/` and one run id for the set.

| cell group | result |
|---|---|
| home ×4 | 0 of 4 display covers. At 1049/900/460 the two course covers are the bundled pack Press Plates (`cover-3x2.png` of the Japanese and technical packs); at 1344 the Home scene draws no course cover art. The fox ships at 128 px and renders at 128–220 px, below 2x. The 96×96 night vignette is stretched with `background-size: cover` (ratio 0.07–0.21) |
| discover ×4 | 0 of 8 collectibles; four Press Plates on the surface; the banner is a data-URI 864 px plate under 2x; the fox renders at 88 px at 900; the same stretched vignette layer |
| course-home ×4 | no image asset at all — DOM type, one inline contour and buttons; the fox role is also absent; the same stretched vignette layer |
| design-system ×4 | the installed plugin mounts no Design System surface (VQ-003 has not landed) |
| classroom, world-studio | never captured — no approved Game world in the seeded library |

The grain background layer tiles at its own 96 px (`repeat` + `auto`) and is exempt from the 2x
ratio; the five `repeat-x` + `auto 100%` shelf planks are judged on height only (256 px of source for
12–34 px of paint, a downscale that passes); only the `cover` vignette is flagged, on both axes.

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
