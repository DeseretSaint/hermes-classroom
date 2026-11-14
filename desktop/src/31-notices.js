/**
 * ── Third-party notices: the licence screen the settings sheet opens ────────────────────────
 *
 * Coursebook ships third-party typefaces and brand assets. Their manifests declare a licence, and
 * `docs/launch/NOTICES.md` is the machine-generated inventory of those declarations. This surface
 * renders that inventory instead of a second, hand-typed one: the rows below are written by
 * `scripts/build_notices_rows.py` from the same generator, and `tests/test_desktop_notices.py`
 * refuses a row that the generator does not produce.
 *
 * Two honesty rules are load-bearing:
 *
 *   1. The module never guesses a licence. A row the generator could not resolve renders its
 *      licence as `UNKNOWN`, with the generator's own reason in the evidence cell. A blank beats
 *      a lie, and a plausible-looking default is worse than both.
 *   2. The text is DOM text. There is no image, no canvas and no SVG lettering on this surface, so
 *      a reader with their own type size, a screen reader or a text extractor gets every row.
 *
 * The dialog is real: `role="dialog"`, `aria-modal="true"`, a labelled heading, focus moved in on
 * open and returned to the invoking control on close, Tab held inside, and Escape closes it. It is
 * opened from the one Home settings sheet, which is the only settings surface this plugin has.
 */

// BEGIN GENERATED NOTICE ROWS
// Written by scripts/build_notices_rows.py from the same rows as docs/launch/NOTICES.md.
// Do not edit by hand: a licence id typed here is a licence id nobody verified.
const CB_NOTICE_ROWS = Object.freeze([
  {
    "asset_id": "cb.asset.font.display",
    "kind": "font",
    "licence": "OFL-1.1",
    "evidence": "`assets/fonts/licenses/OFL-Fraunces.txt`",
    "commercial_use": "Yes",
    "manifest": "assets/fonts/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.font.ui",
    "kind": "font",
    "licence": "OFL-1.1",
    "evidence": "`assets/fonts/licenses/OFL-SourceSans3.txt`",
    "commercial_use": "Yes",
    "manifest": "assets/fonts/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.cheer.128",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.cheer.256",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.cheer.512",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.cheer.64",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.clock.128",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.clock.256",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.clock.512",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.clock.64",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.point.128",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.point.256",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.point.512",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.point.64",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.read.128",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.read.256",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.read.512",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.read.64",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.sleep.128",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.sleep.256",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.sleep.512",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.sleep.64",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.think.128",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.think.256",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.think.512",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.think.64",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.wave.128",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.wave.256",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.wave.512",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.fox.wave.64",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/fox/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.field-atlas-lesson-room",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.home-ground",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.home-hero",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.japanese-cover-3x2",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.japanese-cover-4x5",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.parent-cover-3x2",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.parent-cover-4x5",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.technical-cover-3x2",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.kit.field_atlas.technical-cover-4x5",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/kit/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.material.grain-night",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.material.grain-paper",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.material.vignette-night",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.material.vignette-parchment",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.material.wood-plank",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.material.wood-plank-night",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.object.clock",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/objects/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.object.medallion-rim",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/objects/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.object.passport-tray",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/objects/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.object.shelf-plank",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/objects/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.object.stamp-rim",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/objects/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.object.tag",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/objects/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.asset.object.ticket",
    "kind": "image",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/objects/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fonts.Fraunces-VF",
    "kind": "master",
    "licence": "OFL-1.1",
    "evidence": "<https://openfontlicense.org/open-font-license-official-text/>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fonts.SourceSans3-VF",
    "kind": "master",
    "licence": "OFL-1.1",
    "evidence": "<https://openfontlicense.org/open-font-license-official-text/>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fox.fox-cheer",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fox.fox-clock",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fox.fox-point",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fox.fox-read",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fox.fox-sleep",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fox.fox-think",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.fox.fox-wave",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.material.grain-night",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.material.grain-paper",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.material.vignette-night",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.material.vignette-parchment",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.material.wood-plank",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.material.wood-plank-night",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.objects.clock",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.objects.medallion-rim",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.objects.passport-tray",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.objects.shelf-plank",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.objects.stamp-rim",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.objects.tag",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "cb.master.objects.ticket",
    "kind": "master",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/masters/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:card-stock-fibre:dark",
    "kind": "card-stock",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:card-stock-fibre:light",
    "kind": "card-stock",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:paper-grain:dark",
    "kind": "canvas",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:paper-grain:light",
    "kind": "canvas",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:parchment-vignette:dark",
    "kind": "canvas",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:parchment-vignette:light",
    "kind": "canvas",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:wood-plank:dark",
    "kind": "wood",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  },
  {
    "asset_id": "material:wood-plank:light",
    "kind": "wood",
    "licence": "CC0-1.0",
    "evidence": "<https://creativecommons.org/publicdomain/zero/1.0/legalcode.en>",
    "commercial_use": "Yes",
    "manifest": "assets/art/material/manifest.json",
    "resolved": true
  }
])
// END GENERATED NOTICE ROWS

const CB_NOTICES_TITLE_ID = 'cb-notices-title'

/**
 * The licence a reader is shown. `resolved` is the generator's verdict on the manifest's claim:
 * a declared id that is not in the generator's registry is unresolved, and the row says so rather
 * than printing an id the inventory could not stand behind.
 */
function cbNoticeLicence(row) {
  if (!row || row.licence === 'UNKNOWN' || row.resolved !== true) return 'UNKNOWN'
  return row.licence
}

/** The commercial-use cell, kept literally as the generator classified it. */
function cbNoticeCommercial(row) {
  const value = row ? row.commercial_use : 'UNKNOWN'
  if (value === 'Yes') return 'Commercial use permitted'
  if (value === 'No') return 'Not for commercial use'
  return 'Commercial use unknown'
}

/**
 * One notice row. Every value comes off the generated row; nothing here derives, rounds or
 * substitutes a licence. `data-cb-notice-licence` carries the shown licence so a test can compare
 * the rendered surface with the generated data row by row.
 */
function NoticeRow({ row }) {
  const licence = cbNoticeLicence(row)
  return jsxs('li', {
    'data-cb-notice-row': row.asset_id,
    'data-cb-notice-licence': licence,
    'data-cb-notice-resolved': row.resolved === true ? 'yes' : 'no',
    style: {
      listStyle: 'none',
      padding: '0.55rem 0',
      borderTop: '1px solid var(--cb-rule)',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.2rem',
      minWidth: 0
    },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          gap: '0.2rem 0.6rem',
          minWidth: 0
        },
        children: [
          jsx('strong', {
            style: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)' },
            children: row.asset_id
          }),
          jsx('span', {
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: row.kind
          }),
          jsx('span', {
            'data-cb-notice-licence-label': '',
            style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: licence === 'UNKNOWN' ? 'var(--cb-coral)' : 'var(--cb-ink)' },
            children: licence
          }),
          jsx('span', {
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: cbNoticeCommercial(row)
          })
        ]
      }),
      jsx('div', {
        style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
        children: row.evidence
      }),
      jsx('div', {
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
        children: row.manifest
      })
    ]
  })
}

/**
 * The notices dialog. Mounted by the settings sheet and rendered only while open, so the trap and
 * the Escape listener exist exactly when the surface does. Focus returns to the invoking control
 * when it closes, which is how a reader who opened it by keyboard gets back to where they were.
 */
function NoticesDialog({ open, onClose, returnFocusRef }) {
  const panelRef = useRef(null)
  // The sheet re-renders while this dialog is open, and an inline onClose changes identity every
  // time. Holding it in a ref keeps the effect keyed to `open` alone, so a parent render cannot
  // re-run open/close focus choreography under the reader.
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return undefined
    // The invoking control is whatever had focus when the dialog opened. `document.activeElement`
    // is `body` for a pointer click in some engines, so the caller's trigger ref is the fallback
    // and the launcher selector is the last resort.
    const previous = typeof document !== 'undefined' ? document.activeElement : null
    const focusables = () => {
      const panel = panelRef.current
      if (!panel || typeof panel.querySelectorAll !== 'function') return []
      return Array.from(
        panel.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
      ).filter((node) => !node.disabled && node.getAttribute('aria-hidden') !== 'true')
    }
    const nodes = focusables()
    if (nodes.length > 0 && typeof nodes[0].focus === 'function') {
      nodes[0].focus({ preventScroll: true })
    }
    const onKeyDown = (event) => {
      if (!event || !event.key) return
      if (event.key === 'Escape' || event.key === 'Esc') {
        if (typeof event.preventDefault === 'function') event.preventDefault()
        if (typeof event.stopPropagation === 'function') event.stopPropagation()
        if (typeof onCloseRef.current === 'function') onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const items = focusables()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      const active = typeof document !== 'undefined' ? document.activeElement : null
      if (event.shiftKey && (active === first || !items.includes(active))) {
        if (typeof event.preventDefault === 'function') event.preventDefault()
        last.focus({ preventScroll: true })
      } else if (!event.shiftKey && (active === last || !items.includes(active))) {
        if (typeof event.preventDefault === 'function') event.preventDefault()
        first.focus({ preventScroll: true })
      }
    }
    if (typeof document !== 'undefined' && document.addEventListener) {
      document.addEventListener('keydown', onKeyDown, true)
    }
    return () => {
      if (typeof document !== 'undefined' && document.removeEventListener) {
        document.removeEventListener('keydown', onKeyDown, true)
      }
      // The launcher is the one control that opens this dialog, so returning focus to it is exact
      // in every engine — including a pointer click, where `document.activeElement` was still the
      // sheet's first control at open time. The captured element and the caller's ref are fallbacks
      // for a future second entry point.
      let target = null
      if (typeof document !== 'undefined' && document.querySelector) {
        target = document.querySelector('[data-cb-notices-open]')
      }
      if (!target && previous && previous.isConnected && previous !== document.body) target = previous
      if (!target && returnFocusRef && returnFocusRef.current) target = returnFocusRef.current
      if (target && target !== document.body && typeof target.focus === 'function') {
        target.focus({ preventScroll: true })
      }
    }
  }, [open, returnFocusRef])

  if (!open) return null

  return jsx('div', {
    'data-cb-notices-backdrop': '',
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 70,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      background: 'color-mix(in srgb, var(--cb-ink) 36%, transparent)'
    },
    onMouseDown: (event) => {
      if (event && event.target === event.currentTarget && typeof onClose === 'function') onClose()
    },
    children: jsxs('section', {
      ref: panelRef,
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': CB_NOTICES_TITLE_ID,
      'data-cb-notices': 'open',
      'data-cb-notice-count': String(CB_NOTICE_ROWS.length),
      style: {
        width: '44rem',
        maxWidth: '100%',
        maxHeight: '100%',
        overflowY: 'auto',
        background: 'var(--cb-paper-raised)',
        color: 'var(--cb-ink)',
        border: '1px solid var(--cb-rule)',
        borderRadius: '0.75rem',
        padding: '1rem 1.25rem 1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.6rem'
      },
      children: [
        jsxs('div', {
          style: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem' },
          children: [
            jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
              children: [
                jsx('h2', {
                  id: CB_NOTICES_TITLE_ID,
                  style: { margin: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.heading, fontWeight: 600, lineHeight: 1.1 },
                  children: 'Third-party notices'
                }),
                jsx('div', {
                  'data-cb-notices-scope': '',
                  style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                  children: `${CB_NOTICE_ROWS.length} asset sources · generated from the committed manifests`
                })
              ]
            }),
            jsx(sdk.Button, {
              size: 'sm',
              variant: 'ghost',
              'data-cb-notices-close': '',
              'aria-label': 'Close third-party notices',
              style: { minHeight: '44px' },
              onClick: onClose,
              children: 'Close'
            })
          ]
        }),
        jsx('p', {
          style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
          children:
            'Every row is one source file the product ships, with the licence its manifest declares and where that licence can be read. A licence id the generator could not verify reads UNKNOWN rather than a guess. Commercial use is a classification of the licence id, not a legal opinion about a particular asset.'
        }),
        jsx('ul', {
          'data-cb-notices-list': '',
          style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', minWidth: 0 },
          children: CB_NOTICE_ROWS.map((row) => jsx(NoticeRow, { row }, row.asset_id))
        })
      ]
    })
  })
}
