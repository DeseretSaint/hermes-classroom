# Credits and provenance — Coursebook launch film

Every product pixel in `coursebook-demo-90s.mp4` is a crop of a real window running the installed Coursebook
plugin. Nothing is redrawn, mocked, or generated. The film was composed with `ffmpeg` from five PNG
captures; the build script is `build-final-film.sh` in the capture directory.

Composition: `ffmpeg n9.0.2`, GPL build (`--enable-gpl --enable-libx264`), x264, on Omarchy 7.2.15.
The film carries no third-party footage, no music and no stock imagery.

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

| Beat | File | sha256 | Stamp | `tree.commit` | module | `captured_at` |
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

Caption on the end card reads `captured from the real plugin - build c4fe2d63`; both trees carry the
same module digest, so the card is true of the pixels.

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
Beats 2-5 render from code this commit does not change. Beat 1 renders the pre-`468f45c0` Home; the
delta and its visible effect are measured per beat in `QC.md` and declared there.

## Type

Text in the film is drawn with **Liberation Sans** (Regular and Bold), the metric-compatible open
release of Arial.

- Licence: **SIL Open Font License 1.1**
- Source: <https://github.com/liberationfonts/liberation-fonts>
- Licence text: <https://github.com/liberationfonts/liberation-fonts/blob/main/LICENSE>
- Installed at `/usr/share/fonts/liberation/` (distribution package `ttf-liberation`).

## Music and sound

**None.** The film has no audio stream at all — `ffprobe -select_streams a` reports zero streams
(`QC.md` pastes the command). This is deliberate: X autoplays muted, every beat is written on screen, and
a licensed track could not be cleared and credited inside the submission window. No sound effect, no bed,
no narration. There is no track, so there is no track licence to carry.

## Illustration and course art

The lesson illustration, the Home hero plate, the course covers and the fox are part of the packaged
`field_atlas@2` kit shipped in `desktop/src`, authored for this project and covered by the repository
MIT licence. They are not third-party stock.

## Tooling licences

| Tool | Version | Licence | Use |
| --- | --- | --- | --- |
| `ffmpeg` / `ffprobe` | n9.0.2, GPL build | LGPL-2.1-or-later plus `--enable-gpl` components (x264: GPL-2.0-or-later) | crops, type, encode, measurement |
| `python3` | 3.14 | PSF-2.0 | sha256, build-script generation |
