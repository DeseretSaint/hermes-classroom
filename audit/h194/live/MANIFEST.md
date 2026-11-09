# H-194 live pass — evidence manifest

Date: 2026-11-08 (America/Denver). Base: `wt/h194-ui` @ `58b8c5b`.

## Rig

- Disposable home: `~/.hermes/coursebook-test-h194-1108/home`
- Store: `~/.hermes/coursebook-test-h194-1108/home/plugin-data/coursebook/data.db` (real store; 30 courses)
- Isolated backend: `http://127.0.0.1:44249` (wire 20), restarted from the h194-1108 home
- Desktop window: dev Electron, CDP `127.0.0.1:9386`, userdata `~/.hermes/coursebook-test-h194-1108/userdata`
- Installed plugin: agent half symlink → `.worktrees/t_07409875` (58b8c5b); Desktop half refreshed from that tree
  - `desktop/plugin.js` sha256 `f6ce2289dcff5853530ba76e09df636b788b63897fd4af402cdfcb603e82f7f7`
  - installer check after refresh: both halves match, `Install is current`
- Theme: `color-scheme: dark`, body background `color(srgb 0.0509804 0.0625882 0.0810196)` (no `data-theme` attribute)
- Viewport for every capture: **1280 × 1200** (`Emulation.setDeviceMetricsOverride`, DPR 1)

## Course driven

`crs_3ea89399cb7b4385a6baba8e02883150` — *Japanese café basics, revised*, plan `pln_3ce0768a3c99488990c415ddbc87dfe1` v9 (approved), enrollment `enr_e88941f95fd54ff3998e93fd8ec5b4ea`.
The enrollment was archived (hidden from the Parent Studio landing); it was unarchived through `enrollment.update` (revision 17 → 18) so a real plan could be opened. `parent.final.approve` was then called once (the same command the UI approve button calls) to give the course an active lesson-set approval, because its earlier approval had been superseded by a prior edit.

## Exact command lines

```
python3 coursebook/install_check.py --source .worktrees/t_07409875 \
  --home ~/.hermes/coursebook-test-h194-1108/home --refresh-desktop --force

COURSEBOOK_TEST_HOME=$HOME/.hermes/coursebook-test-h194-1108/home CB013_PORT=44249 \
  bash scripts/cb013-live-backend.sh
COURSEBOOK_TEST_STATE=$HOME/.hermes/coursebook-test-h194-1108 CB013_CDP_PORT=9386 \
  bash scripts/cb013-live-window.sh --restart

CB013_BASE=http://127.0.0.1:44249 CB013_TOKEN=cb013-test-token \
  H194_STATE=<cafe-state.json> python3 scripts/h194-live-drive.py preapprove
CB013_BASE=http://127.0.0.1:44249 CB013_TOKEN=cb013-test-token \
  H194_STATE=<cafe-state.json> python3 scripts/h194-live-drive.py export

CB013_CDP_PORT=9386 H194_TITLE='Japanese café basics, revised' H194_PHASE=edit \
  node scripts/h194-live.mjs

CB013_CDP_PORT=9386 H194_TITLE='Japanese café basics, revised' H194_PHASE=approve \
  H194_BLOCKED_REASON=no_final_approval node scripts/h194-live.mjs

H194_FACTS=audit/h194/live/facts.untouched.json CB013_BASE=http://127.0.0.1:44249 \
  CB013_TOKEN=cb013-test-token H194_STATE=<cafe-state.json> \
  python3 scripts/h194-live-drive.py continue-untouched
```

## Artifacts

| File | sha256 | What it shows |
|---|---|---|
| `h194-editor.png` | `af60210d71809be413284e1b6de8707cfb72d7b6651c608a41aab4eb691d8e07` | inline editor with both the objective title and the section page-title changed, dirty draft |
| `h194-reorder-confirmed.png` | `5d5e997d73e39a6a8469afd2fe809292c4bcc84f488b07d362faa0bfb19a302f` | `Order saved.` notice, stored order adopted on screen, undo token |
| `h194-export-blocked.png` | `88834c916d80abac39b7ec6749a0d5534d6d3582631ce95958f2d69b11a057be` | Review changes, export gate `blocked`, backend reason rendered |
| `h194-export-ready.png` | `7c61f5d89d1fad7b46640ec096041ded0d1d00499e3c72d7715744160c8524f1` | after approve: gate `ready`, export control enabled |
| `facts.edit.json` | `4d40243d7e74ad3c150eb8f9dc3df49446c84d854a10cf9085b1182eca56b6af` | viewport, theme, row match, editor fields, save notice, reorder |
| `facts.approve.json` | `c9e9400abb270852636ef3433d9163d8c508d7ed0b6d30434bd55979a4347cc2` | `facts.review` (gate, changed rows, chips), approve result |
| `facts.untouched.json` | `c16876c6f3becd6ba63cf66f6c1e1f30e113d57d8fdd6e26fe19688d5ffb292f` | untouched section `lesson.page` + `lesson.begin`, export refusal |

## Measured verdict (not softened)

- **Row selection fixed.** The landing is matched by *containing* title inside `article[data-cb-course-id]` and fails unless exactly one row matches; it matched 1 of 5, course `crs_3ea89399cb7b4385a6baba8e02883150`.
- **The edit phase carries the page-title field.** Save notice: “Section page saved as a new revision that needs review before export.” The first row's page title became `… page (revised)`.
- **Reorder is stored.** `Order saved.` with `data-cb-finetune-order` rotating `obj_49f2…` ahead of `obj_2b36…`, undo token `prv_2f43b5…`.
- **Untouched section read works.** `lesson.page` served section 2 (`Sort picture cards into warm and cold`, document `doc_65456785c9cdd6edc043`); `lesson.begin` returned `run_a5c71388b85f4e38a8fad79a87f30cf7`, `needs_fresh_run`, `resume.reason=no_binding`.
- **Export gate before approval refused, but the measured reason is `no_final_approval`, not `changes_need_review`.** The reorder goes through `plan.edit`, which supersedes the active `final_approvals` row (`invalidated_reason: plan_edited`), so the gate short-circuits at “no active approval”. `changes_need_review` in this domain is emitted only when an active approval's content hash differs — e.g. a page-title-only revision with no plan edit.
- **Export after approval does not succeed on this store state.** The gate reached `ready` in the UI and `parent.final.approve` returned active, but the recomputed export refuses with `POLICY_VIOLATION` / `no_generated_content`: “section 'Name one warm and one cold thing in the kitchen (revised again) page (revised)' has no check; lessons must validate before export.” The page-title revision therefore is *not exportable* with this backend — the UI gate and the export command disagree.
- A fresh pipeline seed was attempted first and failed at the host boundary: `plan` job `job_33c16da4…` → `HOST_UNAVAILABLE`, “coursebook.plan.generate exceeded its 240s deadline”. That is why a pre-existing real course was used.

## Files changed by this task

- `scripts/h194-live.mjs` — `H194_PHASE` split, containing-title row selection with a loud uniqueness assertion, page-title edit field, exact blocked-reason assertion (`H194_BLOCKED_REASON`), theme/viewport facts.
- `scripts/h194-live-drive.py` — `continue-untouched`, `export`, `preapprove`; `parent.export` payload corrected to `{enrollment_id}` only; facts written even when the gate reason differs.
- `audit/h194/live/*` — the four frames and three fact files above.

`desktop/plugin.js` was not edited; nothing was merged, pushed, or re-pinned, and the gateway was not restarted.
