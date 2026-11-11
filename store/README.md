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
the generated shelf. The `store` workflow runs two checks and nothing else:

- `python3 scripts/store_index.py --check` — the index matches the files;
- `python3 scripts/store_verify.py` — every community pack passes the importer's own pre-write gate,
  including the presentation rules that make a Game course import with its world kit and art.

Green checks plus one Merge is the whole acceptance. The pack is then part of the next plugin update
and appears in every user's Workshop.

## Identity without configuration

The submit script asks for nothing. A course exported from Coursebook already carries a pack id
derived from its own course id. When that id is already on a shelf with different bytes, the script
namespaces it with eight hex of its own content hash and re-gates the rewritten archive:
`spanish-basics` becomes `spanish-basics-98ff9171`. Identical bytes again returns
`already_present`, and nothing is written.

Refusals (exit code 3, one JSON line) come from the same gate the importer uses: a corrupt or
truncated archive, a non-`.zip`, an undeclared or missing member, a bad content hash, a missing
teaching minimum, or a presentation block the importer cannot reconstruct.

## What travels with a Game course

A v3 pack carries `presentation.mode`, the approved world's identity and every plate, plus a
section's generated visual/narration through `media[]` with a text equivalent and a per-artifact
licence. Import restores the mode, an approved world re-keyed to the importing course's objectives,
the plate bytes (hash-identical), and the media segments. The store card carries the mode, so a Game
course is visibly a Game course before anyone adds it.

## Add a store course to your Coursebook

The Workshop surface lists first-party and community packs together. Adding one runs the same atomic
`pack.import` path a file picker uses, so a store course cannot bypass the import gate; importing the
same release twice returns the course you already have instead of a duplicate.

## What the store is not

No server, no account, no price, no rating, no learner count, no telemetry, no self-update. The
catalogue's editorial fields live in `catalog/workshop.v1.json` for first-party packs; a community
card is derived from the pack's own manifest and the generated index, so no one hand-writes a claim
about a pack.
