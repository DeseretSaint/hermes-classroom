# How an update actually reaches a user

Verified on 2026-11-12 against the installed `hermes` (v0.23.1+g1513f54), the code that reads
`plugin-catalog/`, and a live end-to-end install in an isolated `HERMES_HOME`. This is the only
delivery path; anything else is us looking at our own checkout.

## The chain

1. **A commit lands on `DeseretSaint/hermes-classroom` `master`.** We see it immediately; users do not.
2. **A catalog entry pins that exact 40-character SHA**, in `plugin-catalog/coursebook.yaml` of
   `NousResearch/hermes-agent`, submitted as a PR. Rule 2 of the catalog README: branches, tags and
   short SHAs are rejected by the loader; installs check out exactly that commit. Rule 4: every SHA
   bump is a **new PR**, re-reviewed like any other change. There is no self-serve registry and no
   automated ingestion (rule 1).
3. **A maintainer merges the PR.** Presence in `plugin-catalog/` is the trust signal.
4. **The docs deploy publishes the live catalog.** `.github/workflows/deploy-site.yml` runs on pushes
   to `main` that touch `plugin-catalog/**`, and `website/scripts/extract-plugins.py` writes
   `plugin-catalog.json` from `plugin-catalog/*.yaml`. That file is served at
   `https://hermes-agent.nousresearch.com/docs/api/plugin-catalog.json`.
5. **A user's CLI reads the live catalog**, not their checkout's copy: `load_catalog_live()` fetches
   the published JSON and caches it for 6 hours (`LIVE_CATALOG_TTL_SECONDS`). This is why a merged
   entry appears without waiting for a Hermes release.
6. **`hermes plugins install coursebook`** clones the repo and checks out the pinned SHA; the
   installer writes `.hermes-catalog.json` beside the plugin with that SHA.
7. **`hermes plugins update coursebook`** compares the installed SHA to the entry and re-pins. It
   never `git pull`s: a catalog install only moves when the catalog moves. `plugins.auto_apply`
   defaults to **off**; a notice is printed, and the user (or the gateway tick, once opted in) applies it.

## What was actually wrong

Both defects would have kept the plugin from ever reaching a user, and neither was visible from our
own machine, because our desktop plugin is a **symlink** (`~/.hermes/plugins/coursebook →
~/Projects/hermes-classroom`) with no catalog sidecar: we were always looking at the dev checkout.

1. **No entry was reachable.** The entry exists only on `add-coursebook-catalog-entry`, the PR is
   open and unmerged, and the published catalog (2,094 entries, generated 2026-11-12T09:57Z) does not
   contain `coursebook`. `hermes plugins install coursebook` answers *"'coursebook' is not in the
   Hermes plugin catalog"* for every user, on every machine. Verified in an isolated home.
2. **The entry could never pass admission.** The pinned commit shipped
   `visual/node_modules/playwright-core/lib/webp_codec.wasm`. The admission gate
   (`scripts/ci/catalog_validate_pinned_entries.py`) refuses unscannable executable payloads
   (README rule 17), so the PR would have failed CI on the pinned source even after review. 243
   node_modules files were tracked in git although `.gitignore` already listed the directory.
3. **The branch was 2,881 commits behind `main`.** Refreshed onto current `main`; the PR is now
   `MERGEABLE` (blocked only on maintainer review, which is the intended human-merged gate).

## What now runs green

```
python3 scripts/catalog-delivery.py --strict          # pin carries every runtime change on master
GITHUB_WORKSPACE=~/.hermes/hermes-agent \
  CHANGED_FILES=plugin-catalog/coursebook.yaml \
  python3 -I ~/.hermes/hermes-agent/scripts/ci/catalog_validate_pinned_entries.py
```

The second command is the real admission gate, run locally: it clones the pinned commit, runs
`hermes plugins validate --install-deps`, scans the payload and refuses a self-updater. It passed
(`Validation passed.`, exit 0) only after the node_modules removal and the re-pin.

## The release ritual

Every time plugin code merges to `master`:

1. `python3 scripts/catalog-delivery.py` — if it says **FAIL: master ships runtime changes the catalog
   pin does not carry**, the release is not delivered yet.
2. Bump `sha:` in the fork's `plugin-catalog/coursebook.yaml` to the new master head, commit, push the
   PR branch. Bumps are new commits on the same open PR; after merge they are new PRs.
3. Run the admission gate above to green.
4. Update the PR body's pin line and say what the range contains.
5. After the merge, confirm the live catalog: `python3 scripts/catalog-delivery.py` must print
   `live … (matches the entry)`. That is the first moment a user can install it.

## What a user experiences

- **Install:** `hermes plugins install coursebook` → clone at the pin, capability consent, then
  `hermes plugins enable coursebook`.
- **Update:** `hermes plugins update coursebook` when the entry pin moves; or turn on
  `plugins.auto_apply` and let the gateway tick do it. Nothing moves silently without a merged pin.
- **Trust label:** installs at a catalog pin are labelled by tier (`community` today) and skip the
  install-time caution prompt, because the scan ran at admission.

## Facts that look like bugs and are not

- **Our desktop is not on the catalog path.** The symlinked dev install is deliberate for
  development; to exercise what a user gets, use an isolated home:
  `HERMES_HOME=$(mktemp -d) hermes plugins install coursebook`.
- **A docs-only commit does not need a bump.** `scripts/catalog-delivery.py` treats `docs/`,
  `tests/`, `audit/`, `probes/`, `scripts/`, `.github/` and `store/` as non-runtime.
- **An installed copy never moves on its own** unless `plugins.auto_apply` is on; that is the catalog's
  trust model, not a defect.
