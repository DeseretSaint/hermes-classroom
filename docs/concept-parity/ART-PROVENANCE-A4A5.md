# A4 scenes and A5 object kit — provenance

Card: CP-013 (`wt/cp-013-scenes`). Owner `easel`, reviewer `quill`.
Machine records: `audit/cp013-scenes/provenance.json` (prompts, media URLs, hashes, OCR),
`audit/cp013-scenes/prompts.json` (prompt text, verbatim, and the rejected rounds),
`audit/cp013-scenes/art-audit.json` (measured plate facts).
Style authority: `docs/concept-parity/ART-BIBLE.md` §9 (A4) and §10 (A5).

Every hash below was printed by `scripts/cp013-provenance.py` from the file on disk; no value here
is typed from memory. If a file changes, the script and `tests/test_cp013_scene_objects.py` fail
together.

## Verdict up front

Ten plates shipped: three scene plates and seven object blanks. Every one passes a tesseract
`--psm 3` text check (empty output), carries no pure black (the plate step lifts the black point
into a warm umber band), and — for the two rims — carries a measured blank centre for the runtime
`sdk.Codicon`. Three rounds were discarded before shipping: two banner rounds, one passport-tray
round. Their bytes are deleted, as `PLAN.md` §5 requires; their hashes, media URLs and rejection
reasons are kept in `prompts.json`.

## How each plate was made

1. Text prompt from the `ART-BIBLE.md` §9/§10 templates, recorded verbatim in `prompts.json`.
2. Generated through the host image tool (`image_generate`), which answers through the nous image
   gateway and serves the media from `v3b.fal.media`.
3. Scenes: cropped to their shipping aspect at the vertical offset the quiet-field probe measured
   (`scripts/cp013-quiet-probe.py`), then one deterministic print-safety lift (`+level 4%,100%`) so
   no pixel in a shipped plate is pure black.
4. Objects: the same chroma key as A1 (`scripts/cp010-fox-prep.py`'s recipe: sample the file's own
   corner colour, `-fuzz 30%`, trim, pad square), one colour temper (`-modulate 92,72,100`) so the
   kit sits in the same muted family as the fox, then export at 256 px RGBA.
5. Checks: `scripts/cp013-art-audit.py` (aspect, pure-black share, darkest-tint warmth, quiet-field
   detail and ink contrast, alpha and centre probes), tesseract, and a vision pass against the
   reference crops.

## Rows

| plate | prompt | prompt_hash (16) | asset sha256 (16) | bytes | OCR | round |
|---|---|---|---|---|---|---|
| `discover-banner` | A4-banner-r3 | `d98614f55105ca8c` | `5ef48e588928384f` | 261941 | no text | 3 |
| `lesson-cafe` | A4-cafe | `0b9fb47cd5dbae35` | `6c3e4f692055b4f7` | 866917 | no text | 1 |
| `course-map` | A4-map | `c6f4347737a2188f` | `6daf97d9b8be5ae3` | 949513 | no text | 1 |
| `stamp-rim` | A5-stamp-rim | `af1338393a7f42d4` | `ddca1f614e31412e` | 94090 | no text | 1 |
| `medallion-rim` | A5-medallion-rim | `f28fb6d1571ba328` | `2ebe695ae90b8ed9` | 78693 | no text | 1 |
| `clock` | A5-clock | `85c025416a546cb4` | `e734ab1231be48cd` | 88280 | no text | 1 |
| `tag` | A5-tag | `8001f94b974ed37d` | `0f53b618b8e6efe3` | 66938 | no text | 1 |
| `ticket` | A5-ticket | `6c5e6b8d1fec7861` | `2851526d3e2471ed` | 52202 | no text | 1 |
| `passport-tray` | A5-passport-tray-r2 | `b3019a1d2010c092` | `22def4d61f8ad143` | 64517 | no text | 2 |
| `shelf-plank` | A5-shelf-plank | `d1918ebee4a01da0` | `1e996a6a272ae017` | 66048 | no text | 1 |

Full prompt hashes, provider media URLs, raw-input hashes and byte counts are in
`provenance.json`. Media URLs are the provider's returned URLs; no plate was re-hosted.

| plate | provider media URL |
|---|---|
| `discover-banner` | `https://v3b.fal.media/files/b/0ab1ed0e/wlc4cUboeU9AvSr27IYsK_FW8iDjfQ.png` |
| `lesson-cafe` | `https://v3b.fal.media/files/b/0ab1ecf7/6qH3m5cDMTuHd-ZsKj11G_A938Nki5.png` |
| `course-map` | `https://v3b.fal.media/files/b/0ab1ecf7/rsfnzMpKMmpXR9LZsrVgH_jwo19DD2.png` |
| `stamp-rim` | `https://v3b.fal.media/files/b/0ab1ecf8/8dYXzlqQu2gJlb8QPGLco_Ts4iyRiA.png` |
| `medallion-rim` | `https://v3b.fal.media/files/b/0ab1ecf8/ELIesa8CJXblpDqVabtnI_GtHWgMq9.png` |
| `clock` | `https://v3b.fal.media/files/b/0ab1ecf8/j7PqHrNn4p4ZpN4NA8M6D_GtPIkaxL.png` |
| `tag` | `https://v3b.fal.media/files/b/0ab1ecf8/tzAc1aE1MoujqbY4kpth1_cwISStgb.png` |
| `ticket` | `https://v3b.fal.media/files/b/0ab1ecf9/6xF6AF5kcp7MRoQi7uycp_rWIQaZev.png` |
| `passport-tray` | `https://v3b.fal.media/files/b/0ab1ed0e/b3Pjsj2zNLGXn2Cye3Znx_3x1EDwjM.png` |
| `shelf-plank` | `https://v3b.fal.media/files/b/0ab1ecf9/y2qAhByYzMalzbm2MV8ao_y1GIwNX0.png` |

## Rejected rounds

| id | plate | round | media URL | reason |
|---|---|---|---|---|
| `A4-banner-r1` | `discover-banner` | 1 | `https://v3b.fal.media/files/b/0ab1ecf4/YDm4izHsyXubKwJpknf9e_lCOy3FTh.png` | Bloom around the lit lantern and a vertical sky gradient, both banned by `ART-BIBLE.md` §1; the deep shadows measured `#2A2A35`, a cool blue-grey outside the pigment table. |
| `A4-banner-r2` | `discover-banner` | 2 | `https://v3b.fal.media/files/b/0ab1ecff/qAsJP8m3UCZkwvritrqOD_6jZKVVih.png` | Quiet field fine, but 2.11 % of the plate was pure black and the foliage still carried cool shade. Regenerated under the strict warm-pigment rule. |
| `A5-passport-tray-r1` | `passport-tray` | 1 | `https://v3b.fal.media/files/b/0ab1ecf9/sVWxJESuDEPlCpqMQ91lL_3TUmk1fs.png` | 5.24 % of opaque pixels near black: the tray's inner shadow was painted black rather than a darker tint of the wood pigment. |

## Measured facts

- **Quiet field.** The banner's reserved field (left 40 %, SPEC-V3 D5) measures 5.93 detail energy,
  median luminance 247 with p05 193, so `ink` clears 16.67:1 at the median and 9.92:1 at the darkest
  5 %. The course-home plate's upper-left third (SPEC-V3 M4) measures 8.68 detail, ink 14.31:1 /
  13.27:1. The cafe frame carries no reserved field: the dialogue, not the art, holds the type.
- **Pure black.** 0.000 % on all three scenes and ≤ 0.010 % on the two rims; every other object is
  0.000 %. The darkest 5 % of each scene is a warm family (`#200e0d`, `#2a2b1f`, `#221a1f`), never
  neutral black.
- **Aspect.** `discover-banner` is 1024×233 (4.395:1, the nearest whole pixel to 4.4:1); the cafe
  and the map are 1024×576 (16:9). The cafe master is cropped mechanically to the 3:1 lesson frame
  at render time (SPEC-V3 §3.3), never stretched.
- **Cutout.** Every object is 256×256 RGBA with a transparent margin. The rims' centres measure
  11.67 and 11.22 detail energy — a blank, not a glyph — so a 20 px `sdk.Codicon` can sit there.
- **Text.** tesseract 5.5.3 at `--psm 3` returned an empty string for all ten recorded raws. On the
  shipped plates, after the print-safety lift, the cafe frame yields single-glyph contour noise
  (`W`, `U`, `I`) — the documented criterion is therefore *no token of two or more characters at 70
  confidence or above*, which no plate reaches. `tests/test_cp013_scene_objects.py` enforces that
  criterion on the shipped files.

## A5 medallions: five real events, one blank

The medallion is one painted rim. What differs per event is the `sdk.Codicon` glyph and the DOM
label, both added at runtime; painting five different rims would be decoration a learner cannot
name, which `COURSEBOOK-VISUAL-IDENTITY-V3.md` §10 removes. The five events are the five recorded
action kinds the product actually has (`coursebook/gm_contract.py::EngagementAction`) plus the
course-end state:

| event | source of truth | glyph | label id | status |
|---|---|---|---|---|
| first lesson step | `lesson_step` | `play` | none yet | **blocked on a copy id** — CP-001's deck carries no label for it; no medallion renders until the id exists |
| first check | `check_submitted` | `check` | `lab.medal.first_check` | ready |
| first review | `review` | `book` | `lab.medal.first_review` | ready |
| first take-home | `homework_completed` | `arrow-left` (take-home pack) | `lab.medal.first_takehome` | ready |
| course complete | course-end state | `shield` | `lab.medal.course_complete` | ready |

## Pipeline

The painted blanks are the object kit's masters: `scripts/build_cb_assets.py` now reads
`assets/art/objects/<name>.png` first and only falls back to the procedural SVG when no painted
master exists. `--write-masters` never overwrites a painted master. The shipped
`assets/objects/<name>.webp` (+ AVIF where the WebP passes 8 KB) is an encode of that PNG, and the
manifest row carries `source: generated:audit/cp013-scenes/provenance.json#<plate>` and the master's
sha256.

Scenes are **not** embedded. They stay where `PLAN.md` §5 and `assets/README.md` put them:
`assets/art/scenes/` masters, served as pack or world media on the media route.

## Known gaps

1. **No model id in the provenance row.** The host `image_generate` tool returns the media URL and
   nothing else. The row says so rather than guessing an id (same gap as A1).
2. **The first-lesson-step medallion has no copy id.** Five blanks are delivered as one rim plus
   five event mappings; the fifth label is CP-001's to author. Until it exists, that event has no
   medallion — it is not rendered with an invented word.
3. **The banner's quiet field is measured, not certified.** 5.93 detail energy and 9.92:1 worst-case
   ink contrast are pixel facts; whether the composition reads well at 226 px is the contact sheet
   and the reviewer's eye.
4. **A sports-pitch-like rectangle appears in the map's meadow.** It carries no letters and no
   markings beyond field lines; it is recorded here because a reviewer should decide whether it is a
   wanted motif, not discover it later.
5. **No human illustrator, native-art review or professional colour check exists**, and none is
   claimed. A matching hash is not a rights verdict and not a quality verdict.
