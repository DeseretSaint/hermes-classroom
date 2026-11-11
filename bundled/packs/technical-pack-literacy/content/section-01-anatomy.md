# Anatomy of a pack

A Coursebook pack is a directory (or a zip of one) whose root carries `pack.json` — the **manifest**.
Everything else is content the manifest names. Read the manifest before you read the lessons: it is
the only file that says what this pack contains and what it claims.

Six fields decide what you are holding.

- `contract` and `contract_version` — which manifest contract the pack speaks. A v1 document may not
  carry `media[]` links; a v2 document may. A build that speaks only v1 refuses a v2 pack instead of
  guessing what its extra fields mean.
- `pack_id` and `pack_version` — the pack's identity. `pack_id` names the pack; `pack_version` is one
  immutable release of it. Two packs with the same id and different versions are two releases, not
  two packs.
- `content_hash` — a sha256 over the manifest's own content description. It makes the manifest
  self-checking: re-reading the pack must reproduce this value.
- `files[]` — every file the pack ships, each with a `path`, `mime`, `bytes` and `sha256`. This list
  is the allowlist. A file on disk that the manifest does not name is not part of the pack; a file
  the manifest names must match its declared size and hash or the import is refused.
- `objectives[]` — the sections a learner works through, each with its own `sections[]` and, where
  the pack grades anything, a `checks[]` record.
- `license` and `attribution` — who made it and under what terms. A pack can honestly say
  `unspecified` and `local_only`; it may not pretend to a redistribution right it does not have.

The order matters. Hashes and structure are checked **before** any teaching text is read, so a
malformed manifest is refused with no course residue rather than half-imported.
