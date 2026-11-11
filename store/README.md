# The Coursebook store

The store is **this repository**, not a service. A course pack that is in this tree ships to every
user with the next plugin update, and the plugin's Workshop surface reads it from disk with no
account, no upload and no network call.

Two shelves feed `store/index.json`:

| shelf | path | who writes it |
| --- | --- | --- |
| first-party | `bundled/packs/<slug>/` | the pack builder, with the release |
| community | `store/packs/<pack_id>.zip` | an accepted store pull request |

`store/index.json` is **generated** from those bytes (`python3 scripts/store_index.py`). It never
carries a hash a file does not have, and `--check` fails when it is stale.

## Share a course (the "Share to store" button)

```
python3 scripts/submit-course.py path/to/course.zip --dry-run   # audit + show the card
python3 scripts/submit-course.py path/to/course.zip             # branch, push, open one PR
```

The script audits the archive with the importer's own pre-write gate before a branch exists, places
it at `store/packs/<pack_id>.zip`, regenerates the index, and opens one pull request whose body
carries the pack id, version, objective count, content hash and archive sha256. Those values are read
out of the pack, never typed by hand.

## Accept a submission (one merge)

Read the PR body. The hashes are computed from the submitted bytes; `store/index.json` in the diff is
the generated shelf. Merge to `master` — the pack is then part of the next plugin update and appears
in every user's Workshop.

A duplicate `pack_id`, a zip whose name does not match its own `pack_id`, a stale index, or a pack
that fails the import gate all fail before merge.

## Add a store course to your Coursebook

The Workshop surface lists first-party and community packs together. Adding one runs the same atomic
`pack.import` path a file picker uses, so a store course cannot bypass the import gate; importing the
same release twice returns the course you already have instead of a duplicate.

## What the store is not

No server, no account, no price, no rating, no learner count, no telemetry, no self-update. The
catalogue's editorial fields live in `catalog/workshop.v1.json` for first-party packs; a community
card is derived from the pack's own manifest and the generated index, so no one hand-writes a claim
about a pack.
