# Work packages, branch map and file ownership

Frozen at CB-001. Two people never own the same file. If a package needs a change in a file owned
by someone else, it changes the **contract** through Atlas or asks that owner; it does not edit.

## 1. Branch and worktree map

| Card | Branch | Worktree | Owner | Phase |
|---|---|---|---|---|
| CB-001 | `wt/cb-001-atlas` | `.worktrees/t_950798bc` | Atlas | contracts + skeleton (this commit) |
| CB-002 | `wt/cb-002-cinder` | `.worktrees/<task>` | Cinder | backend kernel |
| CB-003 | `wt/cb-003-sable` | `.worktrees/<task>` | Sable | platform skeleton |
| CB-004 | `wt/cb-004-lattice` | `.worktrees/<task>` | Lattice | packs + demo fixtures |
| CB-005 | `wt/cb-005-vellum` | `.worktrees/<task>` | Vellum | Desktop shell |
| CB-006 | `wt/cb-006-sentinel` | `.worktrees/<task>` | Sentinel | probes + acceptance matrix |
| CB-007 | `wt/cb-007-harbor` | `.worktrees/<task>` | Harbor | release skeleton |

Base is `master`. Every branch starts from the CB-001 commit so contracts are present.

## 2. Merge order

```
CB-001  (contracts + skeleton)
   ├── CB-006  probes may START immediately (own files, no overlap) and publish PROBES.md
   ├── CB-003  platform skeleton        ← merged second
   ├── CB-002  backend kernel           ← merged third
   ├── CB-004  packs                    ← merged fourth
   ├── CB-005  Desktop shell            ← merged fifth, AFTER CB-003
   └── CB-007  release skeleton         ← merged last
```

Rationale: CB-003 proves the two halves talk before anyone builds state on top of them; CB-002 owns
the tables every later package writes; CB-004 needs the DB but not the UI; CB-005 extends the single
Desktop module CB-003 creates; CB-007 documents what actually shipped, not what was planned.

## 3. File ownership matrix

| Path | Owner | Others may |
|---|---|---|
| `contracts/**` | **Atlas** | read only |
| `coursebook/contracts.py` | **Atlas** | read only |
| `docs/CONTRACTS.md`, `docs/ARCHITECTURE.md`, `docs/WORK_PACKAGES.md` | **Atlas** | read only |
| `tests/test_contracts.py`, `scripts/test.sh` | **Atlas** | read only |
| `plugin.yaml`, `__init__.py` | **Sable** | request a change via Atlas |
| `coursebook/api.py`, `coursebook/tools.py` | **Sable** | extend `METHOD_HANDLERS` only through `register_handler` |
| `dashboard/manifest.json`, `dashboard/plugin_api.py` | **Sable** | read only |
| `coursebook/db.py`, `coursebook/migrations/**` | **Cinder** | read only |
| `coursebook/domain.py`, `coursebook/grading.py`, `coursebook/validators.py` | **Cinder** | read only |
| `coursebook/packs.py`, `coursebook/archive.py`, `bundled/packs/**` | **Lattice** | read only |
| `desktop/plugin.js` | **Sable → Vellum** (see hotspot) | one writer per phase |
| `probes/**`, `PROBES.md`, `docs/ACCEPTANCE.md`, `tests/test_acceptance_*.py` | **Sentinel** | read only |
| `README.md`, `docs/INSTALL.md`, `docs/PRIVACY_EGRESS.md`, `docs/DEMO.md`, `docs/SUBMISSION.md`, `catalog/**` | **Harbor** | read only |
| `scripts/validate.sh`, `scripts/install-dev.sh` | **Sable** | read only |
| `coursebook/hooks.py` | **Cinder** (grading gate body) + **Sable** (binding validation) | coalesce before merge |
| `coursebook/jobs.py` | **Cinder** | read only |
| `tests/test_rpc.py` | **Sable** | append cases |
| `tests/test_jobs.py` | **Cinder** | append cases |

`coursebook/hooks.py` is the one shared Python file: it is small and the two bodies are
non-overlapping, but the owners **must** land them in one commit or coordinate in the card thread
before merging. That is recorded here so it is not discovered mid-merge.

## 4. Hotspot: `desktop/plugin.js`

`desktop/plugin.js` is a **hotspot**, not a normal file. A runtime plugin is a single ESM module
(`apps/desktop/src/contrib/runtime-loader.ts` refuses relative imports), so the entire Desktop half —
route, pane, four destinations, every view, every state — is one file.

Rules:

1. **CB-003 (Sable) lands first**: registration bootstrap, `ctx.rest` client, scope handling,
   route/nav/pane/palette/settings registration, health states.
2. **CB-005 (Vellum) starts after CB-003 is merged** and owns the file until its phase lands.
3. Later feature packages (packs, parent, media) add their view inside the file **in their own
   merge**, rebasing on `master` first, and re-run `bash scripts/validate.sh`.
4. If CB-005 and a later package ever need the file at the same time, the later one splits its work
   by *contribution id* and lands after, never concurrently. If collisions continue, Atlas
   decomposes the file into generated sections — not into modules, which do not load.

Keep contributions namespaced and independent (`id: 'library'`, `id: 'parent'`, …) so additions do
not renumber or rewrite each other.

## 5. Definition of merge-ready (every package)

* `bash scripts/validate.sh` passes locally, including `hermes plugins validate .`.
* New behaviour has a test that fails without the change; no test asserts on a mock of the thing
  under test.
* No file outside the package's ownership column is modified.
* Every new backend command is registered with `api.register_handler` and is already in `cb.rpc`.
  If it is not in the contract, the contract change comes first.
* No new enum, error code, table or payload field outside `contracts/`.
* No dead control in the UI: a button either does its job or is absent.
* Review packet in the card: commit hash, test output, validate output, screenshots where relevant.

## 6. Commands

```bash
# all local checks (unit tests, ESM parse, admission, runtime contracts)
bash scripts/validate.sh

# fast loop
bash scripts/test.sh

# individual gates
python3 -m unittest discover -s tests -t . -v
node --check desktop/plugin.js
hermes plugins validate .
hermes plugins doctor .

# live development (symlink, then enable both halves)
bash scripts/install-dev.sh
hermes plugins enable coursebook
```

Requires: `python3` with `jsonschema` (declared in `plugin.yaml`), `node` for the ESM syntax check,
and a Hermes install that provides `hermes plugins`.

## 7. Package acceptance summary

| Package | Done means |
|---|---|
| CB-002 | one transition per answer; duplicate/late callbacks ignored; restart recovery; conflict shapes; evidence classes; notebook isolation — proven by tests, no network inside a transaction |
| CB-003 | clean install/enable/disable/re-enable; route and pane render with the real SDK; backend health visible; runtime vs stored ids explicit; probe findings recorded |
| CB-004 | import/export/reimport roundtrip preserves teaching content and excludes private data; traversal/symlink/bomb/active-content/bad-MIME rejected; answer key never on a learner page |
| CB-005 | real render in light/dark/narrow/200% text; no focus theft; every empty/error state has an honest action; design checked against `apps/desktop/DESIGN.md` |
| CB-006 | seven probes with PASS/FAIL/BLOCKED and exact evidence; acceptance matrix mapped to cards; defects filed with owners |
| CB-007 | every command runnable from a clean checkout or marked TODO; privacy/egress and limitations explicit; catalog fields validated |
