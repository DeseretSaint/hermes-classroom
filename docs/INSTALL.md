# Installing Coursebook (0.1.0)

This guide covers the two install paths that exist today: a linked development install from a local
checkout, and a scripted single-home install that does the same thing plus enable and verification.
Catalog install is not available yet. Every command below was executed on the CB-014 candidate
(`97fff42`) in a throwaway `HERMES_HOME`, and the observed result is stated next to it.

Read the status table in `README.md` before installing. The package installs and its backend
answers. The Desktop page mounts whenever the window reaches a gateway-backed backend, so course
library, course creation, Parent Studio and Activity are reachable in that window; a window on an
isolated home with no gateway shows the session home for every hash, which Atlas reclassified
P3-operational as a host binding rather than a plugin defect (`docs/REVIEW_CB017-FINAL.md` §3.1).
That sentence replaces an earlier claim on this page that the page "does not mount on this
candidate (CB-QA-09)" — true of the CB-014 candidate it was measured on, not of this tree.

Installing this tree does **not** install a product. What is build-complete, what is proven only on
a branch, and what is fixture-only: `docs/HARNESS-STATUS.md`.

## Requirements

- Hermes Agent 0.23.0 or newer. Verified against the installed Hermes on this machine, stable.
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
  restart the gateway, then enable the Desktop half in Capabilities → Plugins
  hermes plugins doctor coursebook
```

The script symlinks the checkout rather than copying it, because a linked package is watched:
editing `desktop/plugin.js` re-syncs the Desktop copy and hot-reloads it. A copied install only
picks up changes on rescan, update or restart.

It refuses to run outside a Coursebook checkout and refuses to replace an existing real directory.
Both refusals are errors, not prompts. It does not enable anything.

## 3. Enable the agent half

```
hermes plugins enable coursebook
hermes gateway restart
```

Observed: `✓ Plugin coursebook enabled.` followed by `Restart the gateway for the plugin to take
effect:`. The flag lives in `config.yaml` under `plugins.enabled`.

## 4. Enable the Desktop half

In the Desktop app: Capabilities, Plugins, Coursebook, on. The two halves are separate on purpose.
If only the Desktop half is on, the pane shows "Coursebook needs its agent plugin" and offers the
enable path; it never renders an empty course list as if you had no courses.

On this candidate the sidebar item, pane and settings page register, but `#/coursebook` renders the
session home instead of the Coursebook page (CB-QA-09, `docs/REVIEW_CB014.md`). That is a known
defect of this build, not an install failure.

## 5. Or: one scripted install into a dedicated home

`scripts/install-local.sh` links the agent half, materializes the Desktop copy with its
`.hermes-package.json` marker, writes the single-home flag, enables the plugin in that home and runs
the admission gates. It defaults to `~/.hermes/coursebook-test/home`, never the root profile:

```
bash scripts/install-local.sh --home /tmp/coursebook-home
```

Observed output, abbreviated to the lines that carry meaning:

```
source : /path/to/hermes-classroom (97fff42)
home   : /tmp/coursebook-home

== 1/6 agent half: link the package ==
/path/to/hermes-classroom

== 2/6 desktop half: materialize the app root copy ==
marker: /tmp/coursebook-home/desktop-plugins/coursebook/.hermes-package.json

== 3/6 single-home flag for an isolated backend ==
wrote /tmp/coursebook-home/coursebook-single-home.env
start the backend with it:  set -a; . /tmp/coursebook-home/coursebook-single-home.env; HERMES_HOME=/tmp/coursebook-home hermes serve --isolated --port 44219

== 4/6 enable the agent half in this home ==
✓ Plugin coursebook enabled.
Restart the gateway for the plugin to take effect:
  hermes gateway restart

== 5/6 discover it in this home ==
discovered: coursebook

== 6/6 admission gates ==
Validation passed.
  manifest: coursebook 0.1.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 1 tool(s), 3 hook(s)

Installed.
```

Exit codes: `0` installed and verified, `1` refused (not a checkout, a real directory in the way, a
gate failed), `2` bad usage.

## 6. Verify

```
bash scripts/validate-plugin.sh
```

Observed on `bc4b2f9`: `Release gate passed: 3/3 checks on
bc4b2f963fda82238d2047cb928b177f9e18c3fb (444 files).` The gate runs `hermes plugins validate`,
`node --check desktop/plugin.js` and `python3 -m unittest tests.test_desktop_contracts` against a
`git archive` export of `HEAD`, then removes the export.

It exports first because the validator reads every directory it is given. Run from the checkout
root, `hermes plugins validate .` walks `.worktrees/` (one worktree per kanban task, gitignored) and
reports `dangerous` for fixtures and review notes that belong to other commits and to no version of
this package. That is a false red, and it can hide a real one. The script refuses to run when
tracked files differ from `HEAD`, because a release gate pins a commit; `--worktree` gates local
edits instead, and `--ref <commit>` gates another commit.

```
bash scripts/test.sh
```

Observed on the CB-017 release commit (`29bede7`): `Ran 685 tests in 72.181s`, `OK`, then
`desktop/plugin.js: syntax OK` (`scripts/validate.sh`); `scripts/test.sh` runs the same suite plus
the syntax check.

```
bash scripts/validate.sh
```

Observed on the CB-017 release commit (`29bede7`): 685 tests OK, `desktop/plugin.js: syntax OK`,
`hermes plugins validate` on an export of the tracked tree passes all 16 admission checks with one
warning (private core imports, see below), `hermes plugins doctor .` reports `1 tool(s), 3 hook(s)`,
the mounted backend trace passes all 31 expectations against an isolated `HERMES_HOME`, and the
script ends `Validation passed.` with exit 0. `scripts/validate-plugin.sh` on the same commit
reports `Release gate passed: 3/3 checks on 29bede7643403cd9d608499232125e6347c680dd (802 files).`
The verbatim output and the clean-export install are in `docs/CB017-RELEASE-VERIFICATION.md` §1 and
§1.1.

```
hermes plugins doctor coursebook
```

Observed:

```
Plugin Doctor:
/path/to/hermes-classroom
  manifest: coursebook 0.1.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 1 tool(s), 3 hook(s)
```

`plugins validate` prints one warning rather than an error: `coursebook/db.py` opens SQLite through
`hermes_cli.sqlite_util.open_db`, and the `probes/scripts/` harnesses import `hermes_bootstrap` and
`agent.plugin_llm` helpers. Those are private core surfaces, they can break on a Hermes upgrade, and
they are listed here rather than hidden. Catalog rule 9 treats them as a warning, not a rejection.

## 7. What a correct first run looks like

Ask the agent to run `coursebook_status`. On a home whose backend has served `/health` at least
once (opening the pane does that), the observed shape is:

| Field | Value | Meaning |
| --- | --- | --- |
| `plugin_version` | `0.1.0` | The package on disk is the one that answered |
| `contract_version` | `7` | `cb.rpc` v7 is loaded |
| `db.ready` | `true` | The store is provisioned and migrated |
| `db.schema_version` | `4` | Migrations `0001`-`0004` applied |
| `implemented_methods` | 52 names | Every method `cb.rpc` v7 declares has a handler |
| `contracts` | 7 entries | Each frozen contract with its version and hash |

The pane reports the same health block: backend `cb.rpc v7`, plugin 0.1.0, database ready at schema
v4, and `Courses: none yet` until you create or import one. With no chat bound to an enrollment it
offers `Open Coursebook` and says no durable chat is bound yet.

Provisioning is deliberate and narrow: `GET /health` (and `health.get` over RPC) creates the store
and applies migrations on first contact. Enabling the plugin, loading it, and the three chat hooks do
not create anything (CB-014-R1). So on a brand-new home, `coursebook_status` asked **before** any
health check reports `db.ready: false` and `schema_version: null`; that is an unprovisioned profile,
not a broken install. Open the pane, or call `health.get`, once and it reports ready at v4.

The route mount depends on the window reaching a backend, which is why the demo gate stays open:
on this host an isolated home cannot start a gateway, and a shell with no gateway renders the
session list for every route. See `docs/CB016-RELEASE-VERIFICATION.md` §3 for the two conditions
that were captured. Nothing above depends on the route rendering.

## 8. Development loop

Because the package is linked, edits to `desktop/plugin.js` reload in the Desktop app. Python changes
are picked up by the gateway, which needs a restart to re-import the backend.

Run `bash scripts/validate.sh` before proposing a merge. It is the pre-merge gate and covers tests,
module syntax, catalog admission, runtime registration and the mounted backend trace. Its admission
step validates an export of the tracked working tree (`scripts/lib/gate-export.sh`), not the
checkout root, so the gitignored `.worktrees/` tree is never scanned and an uncommitted edit to a
tracked file still fails that step. `bash scripts/validate-plugin.sh` is the release gate for a
pinned commit (see section 6).

## 9. Uninstall and revoke

```
bash scripts/uninstall-local.sh --home /tmp/coursebook-home
```

Observed on a scripted install:

```
== 1/4 remove the credential copy ==
no credential copy at /tmp/coursebook-home/auth.json

== 2/4 disable ==
⊘ Plugin coursebook disabled.

== 3/4 remove the package ==
unlinked /tmp/coursebook-home/plugins/coursebook (the checkout it pointed at is untouched)
removed the Desktop app-root copy /tmp/coursebook-home/desktop-plugins/coursebook

== 4/4 verify the home no longer lists it, and holds no credential copy ==
unlisted
no credential copy remains

Plugin data under /tmp/coursebook-home/plugin-data/coursebook was kept.
Deleting the whole disposable home is the operator's call, not this script's.
```

The script refuses to guess which home to tear down, refuses the machine-level `~/.hermes`, and
deletes exactly the credential copy rather than a tree. A linked dev install can be removed by hand:

```
hermes plugins disable coursebook
rm "$HERMES_HOME/plugins/coursebook"
hermes gateway restart
```

The `rm` removes the symlink only; the checkout stays intact. Coursebook state is **not** deleted by
either path: it lives at `$HERMES_HOME/plugin-data/coursebook/data.db` and survives package removal.
Delete that directory yourself if you want the courses gone; deleting an enrollment from inside the
app is the scoped, previewed data deletion (`enrollment.delete`).

## 10. Troubleshooting

| Symptom | Meaning | Fix |
| --- | --- | --- |
| `run this from the coursebook checkout (plugin.yaml not found)` | `install-dev.sh` was run outside the repository root | `cd` to the checkout, rerun |
| `$TARGET already exists and is not a symlink; refusing to replace it.` | A real directory already occupies the plugin slot | Inspect and remove that directory yourself; the script will not do it |
| Pane says "Coursebook needs its agent plugin" | Desktop half is on, backend half is not enabled or the gateway has not restarted | `hermes plugins enable coursebook`, `hermes gateway restart` |
| `#/coursebook` shows the session list instead of Coursebook | The window has no gateway: on an isolated home the gateway cannot start (one gateway per host) and the shell then renders the session list for every route | Check the window log for `Gateway inaccessible (runtime_exited)`; point the window at a backend that can serve the session. Evidence: `docs/CB016-RELEASE-VERIFICATION.md` §3 |
| `VALIDATION_FAILED` naming a method as "not one of [...]" | The method is not in `cb.rpc` v7. Unknown methods are refused before any handler runs | Use one of the 52 declared methods; the error lists them |
| `NOT_IMPLEMENTED` from an RPC call | A method declared in `cb.rpc` has no handler in this process. Not expected when all 52 are mounted | Check `/runtime` for the mounted list; a partial install or a stale gateway is the usual cause |
| `db.ready: false` in the status tool | Either the store is unprovisioned (no `/health` call yet) or a migration did not complete | Call `health.get` once; if it stays false, check the gateway log for the migration error |
| `hermes plugins validate` fails the capability probe | `jsonschema` is missing from the Hermes interpreter | `hermes plugins validate . --install-deps` |
| `security scan — dangerous` naming a file you never wrote, e.g. `REVIEW_CB003.md:32` | Someone ran `hermes plugins validate` at the checkout root, so the validator read the gitignored `.worktrees/` tree of other kanban tasks | Run `bash scripts/validate.sh` or `bash scripts/validate-plugin.sh`, which validate an export and never scan the checkout root |
| `tracked files differ from HEAD; commit them, or run --worktree` | The release gate pins a commit; uncommitted edits are not in the export | Commit, or run `bash scripts/validate-plugin.sh --worktree` to gate the local edits |
| `scratch dir … is inside the checkout` | `TMPDIR` points into the repository | Point `TMPDIR` outside the checkout, or unset it; the export must not be scanned by itself |
| `hermes plugins doctor` reports a hook or tool mismatch | `plugin.yaml` declarations drifted from `register()` | Fix the declaration or the registration; admission compares the two |

If the pane cannot reach the backend at all, it shows the error code with a Check again button.
Those codes come from `contracts/errors.v2.json`; they are contract values, not prose.

## 11. What this install does not give you

A working Desktop page. The backend, pack pipeline and Parent Studio authoring are implemented and
tested, but the route does not mount (CB-QA-09), image and speech generation and reminders are
absent, and research runs only inside plan jobs. See the status table in `README.md` for the full,
row-by-row state of this build.
