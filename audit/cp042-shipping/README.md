# CP-042 — shipped pack evidence

Card: CP-042, branch `wt/cp-042-pack-shipping`. Owner `cbqa`, reviewer `atlas`.

Ruling applied (owner, 2026-11-10): the three packs under `bundled/packs/` are real store
courses a user adds to a library from Discover. No user-visible string is labelled demo, sample
or fixture, and each pack declares a redistribution licence.

## What is recorded here

| file | produced by | what it proves |
| --- | --- | --- |
| `manifest-validation.json` | `coursebook.packs.load_manifest` + `validate_manifest` + `validate_minima` on all three dirs | each shipped manifest validates, and the identity/licence actually in the file |
| `install-proof.json` | a fresh `HERMES_HOME` (`db.migrate()`), then `workshop.catalog_view()`, `workshop.install()` for each pack, `library.list`, `lesson.page` through `coursebook.api.dispatch` | Discover lists three courses with the new titles and `CC-BY-4.0`/`allowed`; each install lands in the library and its lesson page opens |

Commands:

```bash
python3 bundled/packs/build_bundled_packs.py            # regenerate, deterministic
python3 -m unittest tests.test_pack_shipping_labels     # the label/licence gate
python3 -m unittest discover -s tests -t .              # full suite
```

## Determinism

Two consecutive builder runs over the same tree produced byte-identical files:

```
DETERMINISTIC_RUNS_IDENTICAL
TREE_UNCHANGED_BY_REBUILD
```

`find bundled/packs -type f | sort | xargs sha256sum` was compared before and after each run.

## Install proof, actual output

`workshop.catalog_view()` (the Discover read behind `GET /workshop/catalog`) returned
`count: 3`, `refused: []`, with:

| pack_id | title | licence | redistribution |
| --- | --- | --- | --- |
| `japanese-affection-context-l0` | Japanese register: affection and closeness | CC-BY-4.0 | allowed |
| `parent-measurement-practice` | Measuring together: a kitchen lesson | CC-BY-4.0 | allowed |
| `technical-pack-literacy` | Reading a pack before you install it | CC-BY-4.0 | allowed |

`workshop.install(pack_id)` created one course per pack (`imported: true`), and
`library.list` returned `total: 3`; for each course `lesson.page` answered `ok: true` with a
textbook document whose `section_title` is the pack's first objective (for example
"Read what a pack manifest declares", "Read the marks on a measuring jug",
"Tell everyday affection from a direct romantic declaration"). Full JSON:
`install-proof.json`.

## No stamped live frame on this card

`scripts/cp-capture.mjs` needs a live Electron window mirrored over CDP
(`--cdp-port`, default 9411) plus a live backend URL and bearer token. In this worker session no
CDP listener existed on 9411 (or 9222/44311); the only Hermes Desktop process is the operator's
own app, started without `--remote-debugging-port`. The script was not pointed at the operator's
live app and no frame is claimed. The install proof above is backend JSON, not a screenshot.
