# Sources

This course teaches the Coursebook pack contract as it is implemented in this repository.
Nothing is quoted from an external work, and no third-party text or media is bundled.

- `contracts/pack-manifest.v1.json` and `contracts/pack-manifest.v2.json` — the manifest contracts
  whose fields this pack names: `content_hash`, `files[]`, `objectives[]`, `media[]`, `license`.
- `contracts/vocabulary.v1.json` — `pack_trust_label`, the four separate trust facts this pack
  explains, and `evidence_target`.
- `docs/CONTRACTS.md` — the version history and the rule that v1 documents do not inherit v2 fields.
- `coursebook/archive.py` — the import reading order: manifest, then declared bytes, then structure.

These are repository files, read locally. They are cited here by path rather than bundled into the
pack, so the pack stays small and cannot go stale by quoting a copy.
