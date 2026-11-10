# Catalog draft

`coursebook.yaml` is the draft entry this repository keeps under review. The catalog lives in the
`hermes-agent` repository and is merged by a Nous maintainer through a pull request. The submitted
entry is `plugin-catalog/coursebook.yaml` in `NousResearch/hermes-agent#152920`, an open draft pull
request; until that merges, the catalog `hermes-agent` ships does not resolve `coursebook`. That
pull request is authoritative where the two differ: it pins a later commit on `master` and points
`docs_url` at the README's `#install-locally` heading, while this review copy still pins `61cdb03`.

## Pin policy

The `sha` field pins one commit. The catalog installs exactly that commit, and the entry's page
renders the README from that same commit. A draft pin cannot be final: feature work lands after
it. The rule is:

1. Merge every code change first.
2. Write the release commit.
3. Set `sha` to that commit and `version` to the matching label in the same change.
4. Open the catalog PR. Never amend the pinned commit afterwards.

## Validate

From a `hermes-agent` checkout:

```
python3 scripts/validate_plugin_catalog.py /path/to/hermes-classroom/catalog/coursebook.yaml
```

The validator checks the structural contract: required keys, name pattern, https repo, 40 hex
sha, tier and category enum, `requires_hermes` comparator syntax, image host rules and the shape
of `capabilities`. It does not check that the capabilities match reality; `hermes plugins
validate .` at the plugin root does that.

## Field notes

- `readme: true` requires the repository to be on github.com or gitlab.com and requires
  `README.md` at the pinned commit.
- `platforms: []` means all platforms.
- `tier: community` is the only value an author can propose. Nous maintainers set `official` and
  `verified`.
- The description carries the disclosure lines that a reviewer and an installing user need. Keep
  them in the same field when the text is updated at release.

Open items for the release entry, owner Harbor:

- Replace the placeholder pin.
- Replace the skeleton description with the release description, keeping the disclosure lines.
- Add `image` and up to six `screenshots` on a GitHub raw host, pinned to the same commit.
- Point `docs_url` at the pinned documentation.
