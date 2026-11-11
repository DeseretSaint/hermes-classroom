# Credits and provenance — Coursebook launch film

Every product pixel in the posted film, `coursebook-walkthrough.mp4`, renders shipped Coursebook code.
Nothing is redrawn, mocked, or invented. The film was composed with `ffmpeg` from six source images;
the build script is `captures/freeze/build-v4.sh`, and the narration track was muxed onto it afterwards
(`QC.md` records the delivered file's measurements).

Composition: `ffmpeg n9.0.2`, GPL build (`--enable-gpl --enable-libx264`), x264, on Omarchy 7.2.15.
The film carries no third-party footage, no music and no stock imagery.

## The posted take — six sources, three methods

| Beat | Source | Module | Method |
| --- | --- | --- | --- |
| 1 Home | `captures/freeze/captures-src/f-home.png` | `71d940ce`, the pin | **component render** with seeded fixture data (four enrollments), 1920x1080, Chromium |
| 2 Workshop / Discover | `captures/freeze/captures-src/f-workshop.png` | `71d940ce`, the pin | **component render** with fixture data, 1920x1080, Chromium |
| 3 Course page | `captures/freeze/captures-src/course-home-772-light.png` | `98400108` | real window capture |
| 4 Lesson | `captures/freeze/captures-src/04-lesson-top.png` | `98400108` | real window capture, no stamp |
| 5 Typed check | `captures/freeze/captures-src/07-answer.png` | `98400108` | real window capture, no stamp |
| 6 Parent mode | `captures/freeze/captures-src/parent-guide.png` | current product output | an A4 parent guide the plugin prints, reproduced as a printout |

The two Home-side beats are **not screenshots of a running Desktop.** They were rendered from checkout
`fc6ec7b7` at module `71d940ce` because the plugin installed on the capture host was stale module
`0d98d606`; `captures/freeze/captures-src/manifest.json` records the checkout, the module digest, the
commands and the fixtures. The end card's claim — "rendered from the real plugin" — is true of all five
beats under that definition.

The earlier silent cut `coursebook-demo-90s.mp4` used window captures at module `98400108` for all five
beats; its Home frame pre-dates the seating fix. That file is kept only as the picture-only master, and
the stamp table below describes its captures.

## Capture build — what the stamps say, per file

The capture rig writes a `.stamp.json` beside every capture it takes. The three stamps that exist all
name the same tree and module:

- `tree.commit = 172b61aaffd44c33f2c89360df9f1fceeff66c37`
- `module_sha256_expected = 9840010845539c05e571566dbd65d4ceab03bc1119d01c0356f2ff29c6d9c395`
- `window.plugin_sha256` equals that same digest and `window.matches_expected = true` — the loaded
  `plugin.js` at `~/.hermes/desktop-plugins/coursebook/plugin.js` hashed to the expected module.

Independently re-derived:

```
$ git show 172b61aa:desktop/plugin.js | sha256sum
9840010845539c05e571566dbd65d4ceab03bc1119d01c0356f2ff29c6d9c395  -
```

| Silent-cut beat | File | sha256 | Stamp | `tree.commit` | module | `captured_at` |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `captures-src/home-1833-light.png` | `77bfb00627822aa730a676cb3761cd9dd139793962bea8334a8d86e8a804f852` | `freeze/home-1833-light.stamp.json` | `172b61aa` | `98400108` | 2026-11-11T19:26:45.228Z |
| 2 | `captures-src/workshop-1833-light.png` | `148b3e02ab41262e88f3d0f348dc508f750106bcdf38afa43232a1f308309938` | `freeze/workshop-1833-light.stamp.json` | `172b61aa` | `98400108` | 2026-11-11T19:27:04.373Z |
| 3 | `captures-src/course-home-772-light.png` | `737ea36be20193366ff4c86d1f75a7bbf4ca9a6c4686be4f3677ac70d3e23964` | `freeze/course-home-772-light.stamp.json` | `172b61aa` | `98400108` | 2026-11-11T19:29:03.265Z |
| 4 | `captures-src/04-lesson-top.png` | `6d881493924355305636a7be1136460fe3de3b09cdf5620e7e9064f61e2431ea` | **none** | not recorded | `98400108` by build parity only | not recorded |
| 5 | `captures-src/07-answer.png` | `20c0078c23af637e94bc100eebf278f95c8562ef1091456db9c2a61078541ea1` | **none** | not recorded | `98400108` by build parity only | not recorded |

Two provenance gaps are stated rather than papered over.

1. **Beats 4 and 5 have no stamp.** No `04-lesson-top.stamp.json` or `07-answer.stamp.json` exists on
   disk or in any ref (no file-name match, and neither sha256 appears outside this table). Their build
   attribution rests on `6281e4ce`, the commit that added them, which records them as captures of
   `c4fe2d63` (module `98400108`); `git show c4fe2d63:desktop/plugin.js | sha256sum` returns the
   same digest. That is corroboration, not a stamp.
2. **The stamp files are not tracked.** `git ls-tree origin/master -- docs/launch/captures/freeze/`
   lists only `build-final-film.sh` and the PNGs; the `*.stamp.json` files live in the working tree.
   Commit them with the next capture so provenance is inspectable from a clone.

Caption on the end card of the posted film reads `rendered from the real plugin`; the silent cut's card
carried `captured from the real plugin - build c4fe2d63`. Both are accurate descriptions of how their
own pixels were made.

Capture window: 772-1833 px wide (source PNGs `773x1092` and `1834x1092`), light theme, the installed
plugin driven by the capture rig, 2026-11-11 12:26-12:31 MST.

Each crop removes the host window's right rail and status strip. No pixel inside the plugin surface is
retouched.

## Module delta against the shipped pin

The capture build `172b61aa` (module `98400108`) is an ancestor of the shipped pin `7831d31d` (module
`71d940ce`). Exactly one desktop commit separates them:

```
$ git log --oneline 172b61aa..7831d31d -- desktop/
468f45c0 D-007 round 2: seat fox/clock on plank two, separate them, ink hero on a 0.60 scrim

$ git diff --stat 172b61aa 7831d31d -- desktop/
 desktop/plugin.js          | 25 +++++++++++++++----------
 desktop/src/30-home.js     | 10 +++++++---
 desktop/src/76-v3-scope.js | 15 +++++++-------
 3 files changed, 30 insertions(+), 20 deletions(-)
```

`468f45c0` touches the **Home screen only**: the `CB_HOME_SCENE` seating of the fox and clock, the
Home-scoped CSS in `76-v3-scope.js` (`[data-cb-home-scene-panel]`, `[data-cb-home-hero-band]`,
`[data-cb-home-scene-clock]`, `[data-cb-home-scene-fox]`), and one `data-cb-home-cover` attribute.
Beats 3-5 render from code this commit does not change, so their pixels are true of the pin. Beat 1 is
the one screen the commit changes, and the posted walkthrough re-renders it from `71d940ce`; the delta
is no longer in the delivered film. `QC.md` §Beat 1 geometry records the seating arithmetic and states
which clearance figure is a commit-message claim rather than a measurement.

## Type

Text in the film is drawn with **Liberation Sans** (Regular and Bold), the metric-compatible open
release of Arial.

- Licence: **SIL Open Font License 1.1**
- Source: <https://github.com/liberationfonts/liberation-fonts>
- Licence text: <https://github.com/liberationfonts/liberation-fonts/blob/main/LICENSE>
- Installed at `/usr/share/fonts/liberation/` (distribution package `ttf-liberation`).

## Narration and sound

**No music.** There is no bed, no sound effect and no stock audio, so there is no third-party track
licence to carry.

The posted film does carry a **narration track**: AAC LC, 48 kHz, stereo, 38.400000 s against the
42.400000 s picture, integrated **−14.8 LUFS** and true peak −4.2 dBTP (`QC.md` pastes the commands and
outputs; the loudness figure misses the plan's −15.0 floor and is recorded there as a fail). The track
starts at 3.36 s, so the title card is clear. It is an optional aid, not the carrier of the message:
every beat is written on screen and the film is reviewed with sound off.

The narration is synthesised speech. `docs/launch/QC.md` at `61771289` records it as synthesised with
OpenAI TTS, slowed to 0.88 and delayed 3.6 s; the synthesis step is not in this repository, and no human
recording is used. The picture-only master `coursebook-demo-90s.mp4` has no audio stream at all — for it,
`ffprobe -select_streams a` reports zero streams and the loudness rows are not applicable.

## Illustration and course art

The lesson illustration, the Home hero plate, the course covers and the fox are part of the packaged
`field_atlas@2` kit shipped in `desktop/src`, authored for this project and covered by the repository
MIT licence. They are not third-party stock.

## Tooling licences

| Tool | Version | Licence | Use |
| --- | --- | --- | --- |
| `ffmpeg` / `ffprobe` | n9.0.2, GPL build | LGPL-2.1-or-later plus `--enable-gpl` components (x264: GPL-2.0-or-later) | crops, type, encode, measurement |
| `python3` | 3.14 | PSF-2.0 | sha256, build-script generation |
