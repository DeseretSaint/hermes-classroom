# Credits and provenance — Coursebook launch film

Every product pixel in `coursebook-demo-90s.mp4` is a crop of a real window running the installed Coursebook
plugin. Nothing is redrawn, mocked, or generated. The film was composed with `ffmpeg` from five PNG
captures; the build script is `build-final-film.sh` in the capture directory.

## Capture provenance

- **Build:** `c4fe2d63` on `DeseretSaint/hermes-classroom`, the tree `docs/SUBMISSION.md` records as the
  measured release candidate before the Gate 8c pin.
- **Plugin module:** `98400108` — `python3 scripts/build_plugin.py --check` on that tree reports
  `desktop/plugin.js matches desktop/src (9840010845539c05e571566dbd65d4ceab03bc1119d01c0356f2ff29c6d9c395)`.
- **Capture window:** 1344–1833 px wide, light theme, the installed plugin driven by the VQ capture rig.
- **Date:** 2026-11-11, 12:26–12:50 MST.

| Beats | File | sha256 |
| --- | --- | --- |
| 1 | `captures-src/home-1833-light.png` | `77bfb00627822aa730a676cb3761cd9dd139793962bea8334a8d86e8a804f852` |
| 2 | `captures-src/workshop-1833-light.png` | `148b3e02ab41262e88f3d0f348dc508f750106bcdf38afa43232a1f308309938` |
| 3 | `captures-src/course-home-772-light.png` | `737ea36be20193366ff4c86d1f75a7bbf4ca9a6c4686be4f3677ac70d3e23964` |
| 4 | `captures-src/04-lesson-top.png` | `6d881493924355305636a7be1136460fe3de3b09cdf5620e7e9064f61e2431ea` |
| 5 | `captures-src/07-answer.png` | `20c0078c23af637e94bc100eebf278f95c8562ef1091456db9c2a61078541ea1` |

Each crop removes the host window's right rail and status strip. No pixel inside the plugin surface is
retouched.

## Type

Text in the film is drawn with **Liberation Sans** (Regular and Bold), the metric-compatible open
release of Arial.

- Licence: **SIL Open Font License 1.1**
- Source: <https://github.com/liberationfonts/liberation-fonts>
- Licence text: <https://github.com/liberationfonts/liberation-fonts/blob/main/LICENSE>
- Installed at `/usr/share/fonts/liberation/` (distribution package `ttf-liberation`).

## Music and sound

**None.** The film has no audio stream at all — `ffprobe -select_streams a` reports zero streams. This is
deliberate: X autoplays muted, every beat is written on screen, and a licensed track could not be
cleared and credited inside the submission window. No sound effect, no bed, no narration.

## Illustration and course art

The lesson illustration, the Home hero plate, the course covers and the fox are part of the packaged
`field_atlas@2` kit shipped in `desktop/src`, authored for this project and covered by the repository
MIT licence. They are not third-party stock.

## Tooling

| Tool | Version | Use |
| --- | --- | --- |
| `ffmpeg` / `ffprobe` | system build, Omarchy 7.2.15 | crops, type, encode, measurement |
| `python3` | 3.14 | sha256, build script generation |
