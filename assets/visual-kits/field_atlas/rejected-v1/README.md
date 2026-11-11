# field_atlas@1 — rejected evidence

This directory is the record of the kit the owner rejected. It is not a consumer fallback, and no
screen, world job, or downstream card may read it: `kit.json` in the parent directory is
`field_atlas@2`, and its `fallbacks` chain never points here.

## What the owner said

2026-11-11 02:22, reviewing the v1 contact sheet on the secondary screen: below reference quality.
The failure named in the rejection was visible in the work, not only the pixels — the hero prompt
asked for a still life on a bare-paper field, while the field-atlas grammar is a *place*: a street
or cafe of paper lanterns with depth. The covers and the lesson scene were sparse vignettes.

## What survives here

- `contact-sheet.png` — the sheet the owner reviewed, at 1372x2896. **Pinned, not committed**: the
  operator ruled on 2026-11-11 03:22 that rejected raster stays out of the repository, so its sha256
  and size live in `HASHES.md` and the bytes are attached to kanban card `t_902ad79f`.
- `kit.json` — the v1 manifest exactly as it was proposed: 23 role entries, its generation log (9
  attempts / 5 accepted / 4 rejected), its fallbacks, and its own sha256 claims.
- `HASHES.md` — sha256 of everything above and of the omitted sheet, plus where the sheet bytes are.

## What does not

The individual v1 plate bytes were replaced **in place** during the v2 rebuild, so the per-file
sha256 claims in this manifest no longer describe files on disk. That is deliberate rather than
tidy: v1 must not be readable as a fallback, and a directory of plates whose hashes still resolve is
a directory somebody will load. The sheet is what the rejection rested on; the manifest is what was
claimed; both are here. The v1 provider raws are retained under `.vq-raw/field_atlas/` as build
inputs.

## Mutations that must not come back

The v1 review round also closed three contract defects that v2 keeps closed, all enforced by
`scripts/vq002-kit-audit.py --check` and mutation-tested by `scripts/vq002-kit-audit-selftest.sh`:

1. `fallbacks.cover` must lead with `course-master` and end at `background`; a Press Plate pack
   cover is forbidden as a display-cover fallback, in any spelling.
2. Every accepted generation row must carry the `raw_sha256` it consumed and a non-empty `produces`
   list, and every shipped plate must trace to exactly one such row.
3. No fictional proof title may appear in the kit's own manifest or plates.

## Status

`field_atlas@1`: rejected by the owner, superseded by `field_atlas@2`, retained as evidence only.
