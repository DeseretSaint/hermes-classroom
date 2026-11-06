# CB-005 review packet — Desktop shell: first-run, Library, Courses and the native visual language

Branch `wt/cb-005-vellum`, based on `master` @ `df224b8`.
Owner: Vellum. Single-writer file: `desktop/plugin.js`.

## What ships

| Surface | Implementation | Backend command | Gated on |
|---|---|---|---|
| `/coursebook` route + sidebar row + right pane + palette + keybind + settings page | inherited from CB-003, kept intact | — | plugin registration |
| Destination shell (Courses / Library) | `CoursebookPage` + `SegmentedControl`; destination survives leaving the route | — | health `ready` |
| Backend unavailable | `BackendUnavailable`: enable path, Open Capabilities, Check again, error code | `/health` | — |
| Database not migrated | `DegradedBody`: contract/version rows, Check again, no empty list | `/health` | `db.ready === false` |
| First run / no courses | `FirstRun`: goal line, orientation, real actions only | `library.list` `empty_reason` | kernel merged |
| Create course (3 steps: goal → shape → review) | `CreateCourseFlow`; writes one course + draft plan + enrollment, states plainly that generation is not in this build | `course.create`, `enrollment.create` | `/runtime.implemented_methods` |
| Courses list | `courses` rows from `library.list`: title, recipe badge, next-step label, evidence summary, warning badge + text, provenance | `library.list` | implemented |
| Search / filter / filtered-empty | `SearchField` (debounced 250 ms) + `SegmentedControl`; filtered empty keeps data and offers Clear search / Clear filter | `library.list` | implemented |
| Archive / unarchive | `DropdownMenu` item, revision-fenced | `enrollment.update` | implemented |
| Delete enrollment | typed-scope `ConfirmDialog` fed by a real `dry_run` preview (counts + preserved rows + scope hash) | `enrollment.delete` | implemented |
| Resume lesson | row action resolves `binding.get` by **enrollment id**, then opens only an `active` stored-session binding | `binding.get` | implemented |
| Library | installed packs from the same real rows, grouped by provenance (All / Bundled / Local), master/detail preview of what the backend recorded | `library.list` | implemented |
| Reconnecting | stale read-only rows + explicit line + Retry; request tokens stop an older response overwriting newer intent | — | any failed read after a good one |
| Pane scoping | unchanged from CB-003: stored-session-id only, never the runtime id, never recency | `binding.get` | — |

No transcript, no composer, no second markdown renderer, no second icon set. Components used: `Button`, `Badge`, `SearchField`, `SegmentedControl`, `ListRow`, `Textarea`, `Input`, `EmptyState`, `ErrorState`, `Loader`, `ConfirmDialog`, `DropdownMenu*`, `Codicon`, `PanelEmpty`, `PanelSectionLabel`. Tokens only; no raw hex, gradients, shadows, radii or control padding overrides. No autofocus, no background navigation, no animations beyond the shared `Loader`.

## Gates (run on this branch)

```
bash scripts/test.sh      -> 220 tests OK (includes tests/test_desktop_contracts.py: 6 tests)
node --check desktop/plugin.js -> syntax OK
bash scripts/validate.sh  -> Validation passed (16/16 admission checks, doctor, 9 backend expectations)
```

`scripts/validate.sh` prints the live `/runtime` body from an isolated HERMES_HOME, which is the
proof that this branch's backend *does* publish `implemented_methods`
(`["binding.get", "health.get", "schema.get"]` on the skeleton) and that the Desktop reads it.

## Live verification — real Desktop render, not a mock

Isolated Electron instance (`electron .` against the app's Vite dev server, its **own**
`--user-data-dir` and CDP port 9333), driven over CDP. The operator's packaged window was never
touched, relaunched or killed.

Environment facts established with real output, not assumed:

1. **One gateway per host.** `HERMES_HOME=<scratch> hermes gateway ensure` answers
   `runtime_exited` / `"The host gateway already serves profile 'default' — nothing to start"`.
   A second isolated HERMES_HOME therefore cannot own its own backend; the Desktop talks to the
   host gateway, which serves every profile.
2. **The plugin ships opt-in.** `runtime-loader.ts:931` sets `defaultEnabled: false` for any folder
   carrying `.hermes-package.json`. The plugin is discovered and listed in Capabilities → Plugins as
   **Off**; the earlier attempt misread that as "the loader did not re-register". It was enabled
   with the row's own switch, after which the sidebar row appears with no relaunch.

Captured states (all from the live window; screenshots in `docs/cb005-shots/`):

| Shot | State | How it was reached |
|---|---|---|
| `01-first-run-dark.png` | first-run, empty library, Courses | vellum profile, migrated DB, `library.list` → 0 rows |
| `02-first-run-light.png` | same, light | `data-hermes-mode=light`, same DOM |
| `03-courses-dark.png` | Courses list with a real enrollment row | row created through `course.create` + `enrollment.create` |
| `04-courses-light.png` | same, light | — |
| `05-courses-narrow-dark.png` | 460×900 | `Emulation.setDeviceMetricsOverride` |
| `06-courses-text200-dark.png` | 200 % text | root font-size 16→32 px (tokens are rem-based) |
| `07-library-dark.png` | Library, All/Bundled/Local, provenance rows + Preview | destination switch |
| `08-filtered-empty-dark.png` | "No courses match your search" + **Clear search** | typed a non-matching query |
| `09-backend-unavailable-dark.png` | "Backend off — Coursebook needs its agent plugin", Open Capabilities, Check again, `404: {"detail":"Plugin not found"}` | switched to a profile with no Coursebook backend mount |

The list row was verified at pixel level as well as in the DOM: title, `One-off` recipe badge,
`Plan update` warning badge, `Review and approve the plan`, `0 independent`, and the warning
sentence `A newer plan draft is waiting for review.`

Real `dry_run` scope the delete dialog renders (returned by the product's own handler, not a
fixture): counts for attempts/transitions/notebook entries/lesson runs/artifacts/jobs, the six
`preserved` rows, a `scope_hash`, and a one-sentence summary.

### Data honesty

The enrollment row and the Library rows were created **through the product's own RPC handlers**
(`api.dispatch` → `course.create` / `enrollment.create`) against the real profile SQLite file. The
first-use schema was provisioned with the backend's own documented `ensure_schema()` (v2, 19
tables). Nothing was inserted with SQL and no response was stubbed.

### Two defects found by driving the live UI

1. **FIXED — a search that matches nothing rendered first-run.** `filteredEmpty` considered only
   `data.applied_filter`, so with courses present a non-matching **search** fell through to
   `FirstRun` and told a learner with two courses that they had none. It now counts the query as a
   filter and names the cause ("No courses match your search" / **Clear search**). Pinned by
   `test_filtered_empty_accounts_for_a_search_query`; verified live (clear restores both rows).
2. **FILED — `/runtime` registry drift in the kernel tree.** The CB-008 kernel package's
   `dashboard/plugin_api.py` predates `implemented_methods`, so `backendWire.implemented` is `null`
   and every control gated on `implemented.has(...)` (Create, row Actions, archive/delete) hides,
   while `backendSupports()` treats the same unknown registry as "ask". This branch's backend does
   publish the field (proved by `validate.sh`), so the merged tree lights them up; the stale copy is
   the gap. Not "fixed" by weakening the gate: rendering an action the backend may not implement
   would violate the no-dead-controls rule. Belongs to the CB-024 integration merge, where the
   kernel's `plugin_api.py` must be the merged one.

## Design check against `apps/desktop/DESIGN.md`

- flat grouping, whitespace over dividers; one hairline (`--ui-stroke-tertiary`) per section edge;
- no card-in-card; no boxed search (`SearchField` underline variant); `SegmentedControl` for filter
  and destination choice, not radio piles;
- status is never colour-only: warnings and backend states are text badges plus sentences;
- `Loader` never renders the literal "Loading…";
- `ConfirmDialog` is the only confirmation surface, and its copy separates enrollment deletion from
  pack content and transcripts;
- reduced motion: nothing animated except the shared `Loader`, which owns its own policy;
- narrow layout: the Library list/detail collapses at the app's own `min-[47.5rem]` breakpoint with
  an explicit back control; rows use `ListRow`'s container-query stacking;
- 200 % text: no clipping at 460 px or at doubled root size in the captured states;
- focus: no `autoFocus`, no `focus()` calls, no navigation from background reads. Opening the page
  from the sidebar moves the route but does not move focus into the pane.

## Known gaps — filed, not hidden

1. **No pack catalogue command.** `cb.rpc` v2 has no listing for bundled/local pack *manifests*
   (`library.list` is the enrolment library; `pack.preview` needs a staged upload). The Bundled tab
   therefore shows packs that already produced an enrolment and says so. A `pack.list` in a v3
   amendment plus a handler is the honest fix; escalated to Atlas.
2. **Import / export UI is absent** (`IMPORT_FLOW_WIRED = false`) — it belongs to the pack work
   package (Lattice, `t_27f18c22`) which is editing this same file concurrently.
3. **Plan generation** is not wired; the create flow stops at a draft plan and says so.
4. **Course detail / lesson workspace** (Textbook, Notebook, Quizzes, attempt states) is CB-009
   (`t_61fcfa6e`); row actions that need it are deliberately not rendered.
5. **Reconnecting** is exercised by unit tests and by the request-token design, but was not captured
   as a screenshot: the only reachable transport fault in this environment takes the whole plugin
   host down, which is the Backend-off state instead.

## Hotspot

`desktop/plugin.js`, as recorded in `docs/WORK_PACKAGES.md` §4. Lattice's `t_27f18c22` is running
against the same file. My contributions keep stable ids (`page`, `nav`, `pane`, `open`, `focus`,
`coursebook-settings`) and every new view is namespaced inside them, so a rebase lands by
appending, not rewriting.
