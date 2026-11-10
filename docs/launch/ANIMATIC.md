# CP-033 — the flat animatic

Status: **built and cut to the beat grid; it is an animatic, not the film.** No v3 screen exists on
this branch, so every product frame here is a pinned reference plate with a visible placeholder
chip. Nothing in this file is a capture of the build, and nothing here is parity evidence.

Built artefact: `docs/launch/animatic/animatic.mp4`
Spec: `docs/launch/animatic/beats.json` · Build record: `docs/launch/animatic/manifest.json`

## 1. What was actually produced

| Fact | Measured value | How it was measured |
|---|---|---|
| Runtime | **75.000 s** | `ffprobe -show_entries format=duration` on the MP4 |
| Frames | **2250** at 30 fps | `ffprobe -show_entries stream=nb_frames` |
| Picture | 1920×1080, H.264, `yuv420p`, faststart | `ffprobe` stream fields |
| Audio | **none** | no audio stream in the file |
| File | 2,036,868 bytes, sha256 `39e3c88c6972d6e4…` | `manifest.json` `video` block |
| Cut points | 12 shots, all on a beat of the 120 BPM grid (0.5 s per beat, 150 beats) | `beats.json` + `manifest.json` |
| Placeholder frames | 5 of 12 (`S2`, `S3`, `S4a`, `S4b`, `S5b`) — every one carries a chip | frame PNGs, §3 below |

Rebuild, from a clean checkout:

```bash
node scripts/cp-animatic.mjs            # frames + animatic.mp4 + manifest.json
node scripts/cp-animatic.mjs --no-video # frames only
node scripts/cp-animatic.mjs --out /tmp/animatic-check   # rebuild somewhere else and compare
```

Measured on 2026-11-10: a rebuild into a second output directory produced **byte-identical** frames
and MP4 (`cmp` clean on all 12 PNGs and on `animatic.mp4`, same 2,036,868 bytes, same sha256), so the
artefact in this commit is reproducible from the spec, the plates and the two OFL font files.

The renderer reads `contracts/cb.tokens.v3.json` `modes.light` at build time and the product's own
typefaces (`assets/fonts/CBDisplay-VF.woff2`, `assets/fonts/CBUI-VF.woff2`). It draws no product UI:
word cards are editorial type on the contract's paper ground, and plate frames show a pinned
reference PNG inside a mat.

## 2. Frame by frame

| # | In → out (s) | Beats | Frame | Kind | Picture source | Placeholder? |
|---|---|---|---|---|---|---|
| 1 | 0.00 → 3.00 | 0–6 | `S0-hook` | word | type only | no |
| 2 | 3.00 → 9.00 | 6–18 | `S1-problem` | word | type only | no |
| 3 | 9.00 → 15.00 | 18–30 | `S2-reveal` | reveal | `docs/concept-parity/refs/home.png` (`fd75bed3…`) | **yes** |
| 4 | 15.00 → 27.00 | 30–54 | `S3-proof1-shelf` | plate | `home.png` (`fd75bed3…`) | **yes** |
| 5 | 27.00 → 33.00 | 54–66 | `S4a-proof2-answer` | plate | `docs/concept-parity/refs/classroom.png` (`ee0c1a66…`) | **yes** |
| 6 | 33.00 → 39.00 | 66–78 | `S4b-proof2-row` | plate | `classroom.png` (`ee0c1a66…`) | **yes** |
| 7 | 39.00 → 45.00 | 78–90 | `S5a-proof3-close` | word | type only (labelled cut) | no |
| 8 | 45.00 → 51.00 | 90–102 | `S5b-proof3-resume` | plate | `classroom.png` (`ee0c1a66…`) | **yes** |
| 9 | 51.00 → 57.00 | 102–114 | `S6-mechanism` | word | type only | no |
| 10 | 57.00 → 63.00 | 114–126 | `S7a-truth` | struck | type only, three struck concept elements | no |
| 11 | 63.00 → 69.00 | 126–138 | `S7b-truth` | word | type only | no |
| 12 | 69.00 → 75.00 | 138–150 | `S8-end` | end | type only, repo + MIT | no |

Seven plate frames read `PLACEHOLDER · REFERENCE PLATE, NOT THE BUILD` in a chip above the mat, on
screen for the whole beat. A judge who sees this cut can tell from the picture alone that the
product frames are the design target, not the shipped screens.

## 3. Why the plates and not captures

`docs/concept-parity/SPEC-V3.md` §5 defines the v3 screens and the card set that builds them:
Home is CP-022, Discover/Workshop CP-021, Classroom CP-023, Course home CP-024. On this branch,
`desktop/plugin.js` carries no `[data-cb-v3-ready]` marker — the v3 route is not built here, so a
capture door run today would refuse (`--require-v3`) or return a v2 frame labelled as v3.

Two v3 branches exist elsewhere in the repository (`wt/cp-020a-scope`, `wt/cp-020b-primitives`, each
with `data-cb-v3-ready` in the module) but they are not this card's base and this card does not
merge them: the plan's rule is that a card merges the parents named in its own card, and none are.

**What replaces each placeholder on the final take**, shot for shot:

| Placeholder frame | Replacement |
|---|---|
| `S2-reveal`, `S3-proof1-shelf` | `node scripts/cp-capture.mjs --name launch-home-1049 --route-width 1049 --require-v3` on the accepted commit, wide breakpoint |
| `S4a-proof2-answer`, `S4b-proof2-row`, `S5b-proof3-resume` | `cp-capture.mjs` on the Classroom surface, before submit, after the verdict, and after reopen — each with its stamp, each driven by `scripts/cp-demo.mjs` |

A capture only enters the take when its stamp's `plugin_sha256` equals the accepted commit's
`desktop/plugin.js`. A frame whose stamp names a different module is not evidence and is not cut in.

## 4. One real capture exists and is deliberately not used

`docs/concept-parity/captures/home-live-1049-light.png` is a real live frame with a valid stamp. It
is **not** in this animatic, because its stamp records:

- `plugin.window_sha256 = 7802e3ca…` — the v2 `master` module, not this branch;
- `plugin.checkout_path = …/.worktrees/t_f0be3189/desktop/plugin.js` — a different worktree.

By the card's own rule (a stamp whose plugin sha differs from the commit under review is invalid)
that frame cannot stand in for this commit's Home. It is v2, and the v3 Home is what the film is
built to. Using it would put a real screenshot where the video claims v3.

## 5. Sound

The animatic is silent. A flat animatic is judged on whether the beats read with no motion and no
audio; the sound plan for the final take (bed at 120 BPM, three UI effects, optional voice, −14 LUFS,
ducked under the caption) is in `SCRIPT.md` §3. No music or effect is licensed yet, and none is
embedded in this artefact.

## 6. The re-recordable driver

`scripts/cp-demo.mjs` replays `docs/launch/cp-demo.steps.json` over the same CDP connection
`scripts/cp-capture.mjs` uses (default port 9411) and writes a marker log whose ids equal the frame
ids above, so an editor cuts at the log rather than by eye.

```bash
node scripts/cp-demo.mjs --dry-run     # validate the step list, print the timeline, touch nothing
node scripts/cp-demo.mjs               # drive the accepted-commit window, write the marker log
node scripts/cp-demo.mjs --selftest    # drive a local fixture: navigate/click/type/wait/marker
```

Every selector in the step list is an attribute the shipped module actually renders — the test
`tests/test_cp033_launch_film.py::DriverSteps::test_every_selector_is_an_attribute_the_module_actually_renders`
fails if one is renamed. The submit control carries no stable data attribute, so that one click falls
back to the button's own label and accepts both the v2 copy (`Submit answer`) and the v3 deck row
(`Check answer`, `COPY.md` `classroom.check.primary`).

Measured: `--selftest` ran 9 steps in 221 ms against the fixture and printed `selftest ok`, so the
step executor (click by selector, click by label fallback, type, wait-for-selector, hover sweep,
marker, assert) is verified to work. The live take is **not** run in this card: no window is
listening on 9411, and driving the product is the recording card's job.

## 7. Known gaps

| Gap | Status |
|---|---|
| Product frames are reference plates | open until CP-022/CP-023/CP-024 land and the capture door stamps them |
| No motion | by design for an animatic; the film adds 4% camera drift and state transitions |
| No audio | no licensed bed or effects yet |
| Live take not driven | no CDP window on 9411 in this card |
| Vertical / sound-off cutdown | planned at 9:16 from the same beat grid; not built in this card |
| Parity | **not claimed anywhere in this card** |
