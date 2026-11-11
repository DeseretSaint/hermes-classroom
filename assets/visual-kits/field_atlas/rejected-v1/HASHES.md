# rejected-v1 — provenance of the evidence

`field_atlas@1` was rejected by the owner on 2026-11-11 02:22 as below reference quality. This file
pins what the rejection rested on. It carries hashes, not raster bytes.

## In this directory (committed)

| File | Bytes | sha256 |
|---|---|---|
| `kit.json` — the v1 manifest as proposed (23 role entries, 9 attempts / 5 accepted / 4 rejected) | 38186 | `415cb2ac1b3d913dcae09a745b04d67aa75730c2a43d1d50896d63dc56a36d51` |
| `README.md` — what survives and what the rebuild replaced | — | see `git log` |

## The v1 contact sheet (pinned, not in git)

The sheet the owner reviewed:

- size: 1372x2896, 16-bit sRGB, 7302377 bytes
- sha256: `03eb2c4efa0155c27fe4f7d31cfc81e5569631b678ae20f2cefe44383a4affd9`
- built 2026-11-11 02:37 from the v1 plates

Its bytes are deliberately **not** committed. Operator ruling 2026-11-11 03:22: rejected raster stays
out of the repository. The sheet remains retrievable from three places, in descending order of
durability:

1. attached to kanban card `t_902ad79f` (VQ-002) as `rejected-v1-contact-sheet.png`;
2. backup copy: `~/.hermes/cache/scratch/vq002-kit-backup-0320/field_atlas/rejected-v1/contact-sheet.png`;
3. the operator checkout that produced it.

Verify any recovered copy against the sha256 above before citing it as evidence.

## The v1 plate bytes

Gone. They were replaced in place by v2; only the five accepted v1 provider raws survive as build
inputs under `.vq-raw/field_atlas/` (untracked). The per-file sha256 claims in `kit.json` here
therefore do not resolve on disk, which is intentional: v1 must not be loadable as a fallback.

## The approved v2 sheet

For contrast, the current sheet is `../specimens/contact-sheet.png`, 1440x3817, sha256
`f9e4b606bfd6e81c3e51ba795672bf3b5005073ba02d4fbb13f7d147d56a7bc8`.
