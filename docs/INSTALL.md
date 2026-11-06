# Installing Coursebook (0.1.0 skeleton)

This guide covers the only install path that exists today: a linked development install from a
local checkout. Catalog install is not available yet. Every command below was executed on the
baseline commit and the observed result is stated next to it.

## Requirements

- Hermes Agent 0.23.0 or newer. Verified against Hermes Agent v0.23.0 (2026.9.24), stable.
- Hermes Desktop, for the pane. The backend half works without it.
- Python 3.11 or newer on the interpreter Hermes runs. `scripts/test.sh` honours
  `COURSEBOOK_PYTHON` if you need to point it elsewhere.
- Node.js for `node --check` only. No bundler, no build step, no npm install.

One declared Python dependency: `jsonschema>=4.0,<5`. Hermes never auto-installs a plugin
dependency. If the capability probe fails on import, run:

```
hermes plugins validate . --install-deps
```

That is the same command catalog CI runs.

## 1. Get the source

The public repository is TODO (owner: DeseretSaint; pushing requires operator approval). Until it
exists, use a local checkout:

```
cd /path/to/hermes-classroom
git log -1 --format=%H
```

Record that commit. It is the build you are installing.

## 2. Link the package into Hermes

```
bash scripts/install-dev.sh
```

Observed output:

```
linked $HERMES_HOME/plugins/coursebook -> /path/to/hermes-classroom

next:
  hermes plugins enable coursebook   # backend half (imports plugin_api.py)
  restart the gateway, then enable the Desktop half in Capabilities -> Plugins
  hermes plugins doctor coursebook
```

The script symlinks the checkout rather than copying it, because a linked package is watched:
editing `desktop/plugin.js` re-syncs the Desktop copy and hot-reloads it. A copied install only
picks up changes on rescan, update or restart.

It refuses to run outside a Coursebook checkout and refuses to replace an existing real
directory. Both refusals are errors, not prompts.

## 3. Enable the agent half

```
hermes plugins enable coursebook
hermes gateway restart
```

Observed: `Plugin coursebook enabled.` followed by a restart instruction. The flag lives in
`config.yaml` under `plugins.enabled`.

## 4. Enable the Desktop half

In the Desktop app: Capabilities, Plugins, Coursebook, on. The two halves are separate on
purpose. If only the Desktop half is on, the pane shows "Coursebook needs its agent plugin" and
offers the enable path; it never renders an empty course list as if you had no courses.

## 5. Verify

```
bash scripts/test.sh
```

Observed on the baseline: `Ran 46 tests ... OK`, then `desktop/plugin.js: syntax OK`.

```
bash scripts/validate.sh
```

Observed on the baseline: 46 tests OK, syntax OK, `hermes plugins validate .` passes all 16
checks with no schema errors, `hermes plugins doctor .` reports `1 tool(s), 3 hook(s)` and
`Validation passed.`

```
hermes plugins doctor coursebook
```

Observed: manifest `coursebook 0.1.0 (standalone)`, runtime discovery, manifest parsing, import
and registration OK.

## 6. What a correct first run looks like

The pane shows, and only shows:

| Row | Value | Meaning |
| --- | --- | --- |
| Backend | `cb.rpc v1`, plugin 0.1.0 | The contract is loaded and the backend answered |
| Database | `not migrated` | No migration has shipped yet, so no course data can be stored |
| Courses | `none yet` | No courses exist in this build, and none are simulated |

`Database: not migrated` is the expected state for 0.1.0, not a broken install. It becomes a
schema version once the backend kernel work package lands migrations.

Ask the agent to run `coursebook_status` to see the same block as JSON:
`plugin_version`, `contract_version`, `db.ready` (false today), and the contract inventory.

## 7. Development loop

Because the package is linked, edits to `desktop/plugin.js` reload in the Desktop app. Python
changes are picked up by the gateway, which needs a restart to re-import the backend.

Run `bash scripts/validate.sh` before proposing a merge. It is the admission gate and covers
tests, module syntax, catalog admission and runtime registration.

## 8. Uninstall and revoke

```
hermes plugins disable coursebook
rm "$HERMES_HOME/plugins/coursebook"
hermes gateway restart
```

The `rm` removes the symlink only; the checkout stays intact. Verified in an isolated
`HERMES_HOME`. If you installed by copy rather than link, remove the copied directory instead,
or use `hermes plugins remove coursebook`, which is TODO to verify for a symlinked dev install
(owner: Harbor). Nothing is written to `$HERMES_HOME/plugin-data/coursebook` in 0.1.0, so there
is no data directory to delete. That changes when migrations land.

## 9. Troubleshooting

| Symptom | Meaning | Fix |
| --- | --- | --- |
| `run this from the coursebook checkout (plugin.yaml not found)` | `install-dev.sh` was run outside the repository root | `cd` to the checkout, rerun |
| `$TARGET already exists and is not a symlink; refusing to replace it.` | A real directory already occupies the plugin slot | Inspect and remove that directory yourself; the script will not do it |
| Pane says "Coursebook needs its agent plugin" | Desktop half is on, backend half is not enabled or the gateway has not restarted | `hermes plugins enable coursebook`, `hermes gateway restart` |
| `NOT_IMPLEMENTED` from any RPC call | The method is frozen in `contracts/rpc.v1.json` but has no handler in this build | Expected in 0.1.0. Nothing is broken |
| `Database: not migrated` | No schema exists yet | Expected in 0.1.0 |
| `hermes plugins validate` fails the capability probe | `jsonschema` is missing from the Hermes interpreter | `hermes plugins validate . --install-deps` |
| `hermes plugins doctor` reports a hook or tool mismatch | `plugin.yaml` declarations drifted from `register()` | Fix the declaration or the registration; admission compares the two |

If the pane cannot reach the backend at all, it shows the error code with a Check again button.
Those codes come from `contracts/errors.v1.json`; they are contract values, not prose.

## 10. What this install does not give you

A course app. See the status table in `README.md` and section 6 of `docs/ARCHITECTURE.md`. The
install is real; the feature set is a skeleton.
