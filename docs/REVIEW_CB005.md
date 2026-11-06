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
| Search / filter / filtered-empty | `SearchField` (debounced 250 ms) + `SegmentedControl`; filtered empty keeps data and offers Clear filter | `library.list` | implemented |
| Archive / unarchive | `DropdownMenu` item, revision-fenced | `enrollment.update` | implemented |
| Delete enrollment | typed-scope `ConfirmDialog` fed by a real `dry_run` preview (counts + preserved rows) | `enrollment.delete` | implemented |
| Resume lesson | row action resolves `binding.get` by **enrollment id**, then opens only an `active` stored-session binding | `binding.get` | implemented |
| Library | installed packs from the same real rows, grouped by provenance (All / Bundled / Local), master/detail preview of what the backend recorded | `library.list` | implemented |
| Reconnecting | stale read-only rows + explicit line + Retry; request tokens stop an older response overwriting newer intent | — | any failed read after a good one |
| Pane scoping | unchanged from CB-003: stored-session-id only, never the runtime id, never recency | `binding.get` | — |

No transcript, no composer, no second markdown renderer, no second icon set. Components used: `Button`, `Badge`, `SearchField`, `SegmentedControl`, `ListRow`, `Textarea`, `Input`, `EmptyState`, `ErrorState`, `Loader`, `ConfirmDialog`, `DropdownMenu*`, `Codicon`, `PanelEmpty`, `PanelSectionLabel`. Tokens only; no raw hex, gradients, shadows, radii or control padding overrides. No autofocus, no background navigation, no animations beyond the shared `Loader`.

## Gates (all run on this branch)

```
bash scripts/test.sh      -> 219 tests OK (includes the new tests/test_desktop_contracts.py: 5 tests)
node --check desktop/plugin.js -> syntax OK
bash scripts/validate.sh  -> Validation passed (16/16 admission checks, doctor, 9 backend expectations)
```

`tests/test_desktop_contracts.py` pins the literal enums the module renders against
`contracts/vocabulary.v1.json` (recipes), `contracts/rpc.v2.json` (`course.create` dials,
`library.list` filters) and refuses any control gated on a method the contract does not define.
`tests/test_platform_desktop.py` needed one truthful stub addition (`useRef`) because the module
now uses it; recorded as a cross-owner edit.

## Live verification — what was actually exercised, and what was not

Isolated Desktop instance (own `--user-data-dir`, `HERMES_DESKTOP_DEV_SERVER` + own CDP port) was
launched against the installed app. Two environment limits were hit and are reported rather than
worked around:

1. **One host gateway.** A second `HERMES_HOME` cannot spawn its own gateway while the operator's
   host gateway runs (`hermes gateway run` exits 0: it already serves every profile). The isolated
   window therefore talks to the operator's gateway.
2. The renderer loaded the *previously installed* copy of `desktop/plugin.js`; after the copy was
   reconciled and the renderer reloaded, the disk-plugin loader in that already-booted instance did
   not re-register the plugin, so the sidebar row stayed absent and the route did not resolve. This
   is an app-startup ordering fact, not a plugin error — the module passes the same Node ESM
   registration harness the app's loader uses (`tests/test_platform_desktop.py`), and the
   reconciliation did copy this file byte-identical into `~/.hermes/desktop-plugins/coursebook/`.

Not yet captured, and required before this card is final: a clean-instance screenshot set
(light/dark/narrow/200 %) on a machine whose host gateway can load the kernel. The Desktop had to
be restarted with the new copy for that; that is what the integration card (CB-024 / `t_fdf1950a`)
does when it installs the merged tree.

Run from the integration tree (kernel merged), the expected first screen is Courses → first-run or
the enrolment rows; with the current `master` backend (`library.list` → `NOT_IMPLEMENTED`) the same
code renders the honest "Your courses could not be read" `ErrorState`, which is the state this
branch can genuinely show today.

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
- focus: no `autoFocus`, no `focus()` calls, no navigation from background reads.

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

## Hotspot

`desktop/plugin.js`, as recorded in `docs/WORK_PACKAGES.md` §4. Lattice's `t_27f18c22` is running
against the same file. My contributions keep stable ids (`page`, `nav`, `pane`, `open`, `focus`,
`coursebook-settings`) and every new view is namespaced inside them, so a rebase lands by
appending, not rewriting.
