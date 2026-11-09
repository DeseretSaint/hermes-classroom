# H-194 live pass — evidence manifest (round 2)

Date: 2026-11-08/09 (America/Denver; facts timestamps are UTC). Base: `wt/h194-ui` @ `58b8c5b`.
Branch: `wt/h194-live`. The UI half (25 H-194 UI tests, 784 desktop tests, `node --check`,
validate-plugin 4/4 on `58b8c5b`) is not redone here; this card only drives the live pass.

## Rig

- Disposable home: `~/.hermes/coursebook-test-h194-1108/home`
- Store: `~/.hermes/coursebook-test-h194-1108/home/plugin-data/coursebook/data.db` (real store, 30 courses)
- Isolated backend: `http://127.0.0.1:44249` (wire 20), running from that home
- Desktop window: dev Electron, CDP `127.0.0.1:9386`, userdata `~/.hermes/coursebook-test-h194-1108/userdata`
- Installed plugin (re-checked this round):
  - `install_check.py --source …/.worktrees/t_07409875 --home …/coursebook-test-h194-1108/home`
    → `Install is current: both halves match this package.`
  - Desktop half `plugin.js` sha256 `f6ce2289dcff5853530ba76e09df636b788b63897fd4af402cdfcb603e82f7f7`
- Theme: `color-scheme: dark`, body background `color(srgb 0.0509804 0.0625882 0.0810196)` (no `data-theme` attribute)
- Viewport for every capture: **1280 × 1200** (`Emulation.setDeviceMetricsOverride`, DPR 1)
- No gateway restart, no merge, no push, `desktop/plugin.js` not edited.

## Exact command lines (this round)

```
# 0 — before the pass: approval active, gate ready
CB013_BASE=http://127.0.0.1:44249 CB013_TOKEN=cb013-test-token \
  H194_STATE=~/.hermes/profiles/sable/cache/scratch/h194-cafe-state.json \
  python3 scripts/h194-live-drive.py status

# 1 — edit phase: objective title + section page title, then reorder
CB013_CDP_PORT=9386 H194_TITLE='Japanese café basics, revised' H194_PHASE=edit \
  node scripts/h194-live.mjs

# 2 — untouched section read + pre-approval parent.export (BEFORE any approve click)
H194_FACTS=audit/h194/live/facts.untouched.json CB013_BASE=http://127.0.0.1:44249 \
  CB013_TOKEN=cb013-test-token H194_STATE=~/.hermes/profiles/sable/cache/scratch/h194-cafe-state.json \
  python3 scripts/h194-live-drive.py continue-untouched

# 3 — approve phase: blocked gate → approve → ready gate
CB013_CDP_PORT=9386 H194_TITLE='Japanese café basics, revised' H194_PHASE=approve \
  H194_BLOCKED_REASON=no_final_approval node scripts/h194-live.mjs

# 4 — parent.export after approval (measured refusal: product defect)
H194_FACTS=audit/h194/live/facts.export.json CB013_BASE=http://127.0.0.1:44249 \
  CB013_TOKEN=cb013-test-token H194_STATE=~/.hermes/profiles/sable/cache/scratch/h194-cafe-state.json \
  python3 scripts/h194-live-drive.py export

# 5 — success path on a course whose approved revision keeps its checks
H194_FACTS=audit/h194/live/facts.export-success.json CB013_BASE=http://127.0.0.1:44249 \
  CB013_TOKEN=cb013-test-token python3 scripts/h194-live-drive.py export-enrollment \
  enr_af2b9cf4832243b1a42542fcad397dfb

# 6 — changes_need_review reachability probe (see "Measured verdict" #3)
H194_FACTS=audit/h194/live/facts.gate-probe.json CB013_BASE=http://127.0.0.1:44249 \
  CB013_TOKEN=cb013-test-token \
  python3 ~/.hermes/profiles/sable/cache/scratch/h194_gate_probe.py
```

## Course driven

`crs_3ea89399cb7b4385a6baba8e02883150` — *Japanese café basics, revised*, plan
`pln_3ce0768a3c99488990c415ddbc87dfe1` **version 11** (approved), enrollment
`enr_e88941f95fd54ff3998e93fd8ec5b4ea`. At the start of the pass the lesson set had an active
approval `apr_2471184cbcdf46f2b484f1e0a303ecaf` and the UI gate read `ready`.

## Order actually run (timestamps from the facts files and the store)

| # | Step | Started (UTC) | Finished (UTC) | Evidence |
|---|---|---|---|---|
| 0 | gate before pass: `ready` | — | — | `status` output, approval `apr_2471…` active |
| 1 | edit objective title + page title, save (`prv_c4512013…` at 00:23:08.973873) | 00:23:04.287 | 00:23:10.933 | `facts.edit.json` |
| 1b | reorder (`prv_4adffcea…` at 00:23:10.034919) — **after** the approval was already superseded at 00:23:08.974173 | — | — | `facts.edit.json.reorder`, store |
| 2 | untouched section `lesson.page` + `lesson.begin` + pre-approval `parent.export` | 00:23:15.170 | 00:23:15.233 | `facts.untouched.json` |
| 3 | approve phase: blocked gate → approve (`apr_00e64bc0…` 00:23:22.909677) → `ready` | 00:23:17.890 | 00:23:24.016 | `facts.approve.json`, `facts.review.json` |
| 4 | `parent.export` after approval — **refused** `no_generated_content` | 00:23:26.142 | 00:23:26.154 | `facts.export.json` |
| 5 | `parent.export` success on `crs_60369f…` (`enr_af2b9c…`) | 00:23:43.883 | 00:23:43.928 | `facts.export-success.json` |
| 6 | `changes_need_review` reachability probe + restore | 00:23:53.892 | 00:23:53.994 | `facts.gate-probe.json` |

Step 2 finished 2.657 s **before** the approve phase started, and the approval row it recorded is
`state: superseded` — the read/refusal happened strictly inside the pre-approval window.

## Artifacts

| File | sha256 | What it shows |
|---|---|---|
| `h194-editor.png` | `a050ff285424f34f9402bb56c132b7929ed145a97d4cf81ba96e00c417127750` | inline editor, objective title **and** page title changed, dirty draft |
| `h194-reorder-confirmed.png` | `0a740fc1ef782f27aa3a69798a7f03f1e758df0437d21d04faf5881d1bd07299` | `Order saved.` notice, stored order adopted, undo token `prv_4adffcea…` |
| `h194-export-blocked.png` | `d4802a0f41d589bb2ee4701dfe81773ae09c6c8fc7f0b08ef2685e8fb56ae841` | Review changes, gate `blocked`, backend reason `no_final_approval` rendered |
| `h194-export-ready.png` | `56d7e4623c06effb351fe9fe7a2a9091557aa604cb9283d0b31d661a42b549a3` | after approve: gate `ready`, export control enabled — for the same bytes the export command then refuses (#4 below) |
| `facts.edit.json` | `94452978d038a760bf0584e22e14c6be74a74ea02d5542edf646810420391f84` | viewport, theme, row match (`1 of 6`), editor fields, save notice, reorder |
| `facts.untouched.json` | `b4e9215419fe1a424fb2b3a2905b0d9b2d76476ddb0ea7167380c83378a06c81` | timestamps, enrollment id, approval state at read, untouched `lesson.page`/`lesson.begin`, pre-approval `parent.export` refusal |
| `facts.approve.json` | `199e3326e6a0769b4a1cf25f61379269acfe1c0dc8df1c683a6379bd156218a2` | review diff, blocked gate, approve result, ready gate |
| `facts.review.json` | `e85be86378b79992a89bd8d258a7ff65bf64f552962d29febf88a000daa8e2d8` | `facts.review` on its own: gate, changed rows, chips, afterApprove |
| `facts.export.json` | `9d14060f67ee8a973098b99e9235eeb9d3609f2bd62115b102e0576b161548cb` | post-approval `parent.export` refusal `no_generated_content` + exact section |
| `facts.export-success.json` | `0b919212664223df7ac779bf858adce75a80714ec07fc47ee779598bd8e91725` | `parent.export` success: `export_id exp_263269f7cef3428eb78805b9d9a0481b`, content hash `sha256:3629c6e3…dd67` |
| `facts.gate-probe.json` | `496d9f5949ee7df6032eae0b66f4da713b3cb3e42f5d13bdb6a74671b79cbd2d` | measured `changes_need_review` on `parent.export`, with current/approved hashes, then success after restore |

## Measured verdict (not softened)

1. **Row selection fixed and loud.** `article[data-cb-course-id]` matched by *containing* title;
   exactly 1 match out of **6** landing rows (`1 of 6`). Both phases assert uniqueness and throw
   otherwise.
2. **The edit phase changes both fields.** Save notice: “Section page saved as a new revision that
   needs review before export.” Objective title → `… (revised)`, page title →
   `… page (revised)`; store revision `prv_c451201323a44465ad89094e51071101` (`objective_edit`)
   and `lrv_cce047da023942248d57c84a196718b7` (`changed_fields: ["title"]`).
3. **`changes_need_review` is unreachable through the H-194 edit path, and that is now measured, not
   inferred.** `lesson.revise` (`coursebook/domain.py:5461`) and `plan.edit`/undo
   (`:5158`, `:5308`) each call `_supersede_active_approval` **inside the same transaction**, so by
   the time the parent can click export there is no active row and the export gate short-circuits at
   `no_final_approval` (`coursebook/pack_flow.py:1259-1267`). Measured: `apr_2471…` was superseded at
   `00:23:08.974173` by the *objective/page-title edit* — the reorder came later, at
   `00:23:10.034919` — and `parent.export` then refused `no_final_approval` with the approval row
   `state: superseded, invalidated_reason: plan_edited` (`facts.untouched.json`).
   `changes_need_review` itself **is** reachable and was measured in `facts.gate-probe.json`: with an
   active approval (`apr_dda27b5d…`) and a changed stored page, `parent.export` refuses
   `POLICY_VIOLATION changes_need_review` with `current_content_hash`/`approved_content_hash`, and
   succeeds again after the page is restored. That probe uses the same direct page mutation as
   `tests/test_parent_studio.py:770`; it is a gate-reachability measurement, not a UI path.
4. **The H-194 product defect is real and measured.** After approval (`apr_00e64bc0…`, gate `ready`),
   `parent.export` still refuses `POLICY_VIOLATION no_generated_content`: “section 'Name one warm and
   one cold thing in the kitchen (revised again) page (revised)' has no check; lessons must validate
   before export.” Cause: `lesson.revise` writes a new `gen_lessons` row and does not copy the
   `gen_lesson_checks` rows, which are keyed by `lesson_id`; `domain._export_status` (`:4522-4532`)
   never performs the check-level validation that `parent_authoring.build_pack` (`~:700`) does, so the
   UI gate and the export command disagree at the same moment (`facts.approve.json.afterApprove`
   `ready` vs `facts.export.json` refusal).
   Follow-up card: **`t_48983869`** (page-title-only revision loses its check / gate order conflict).
5. **The success path is proven end to end.** `parent.export` on `crs_60369f196bb44cf2abfadc54d8a2a477`
   (`enr_af2b9cf4832243b1a42542fcad397dfb`, all sections `validated`, active approval matching the
   content hash) returned `export_id exp_263269f7cef3428eb78805b9d9a0481b`, content hash
   `sha256:3629c6e34505fe17fc090e820a8d2123c88c9200f6aecb0104fcf0d94bc2dd67`, and stored
   `pack` + `pdf` + `export` artifacts whose zip sha256 is
   `7bfdda689753a53366f28a6671bbebf6e3a6e53bda5de28ee2183322d4cb26e4` (8 871 bytes) and pdf sha256
   `d04996a33fa939172547ace5e2dc2ae685cce232aada81255e04c1e09efc4adb` (7 352 bytes).
6. **Untouched-section read works and is timestamped.** `lesson.page` served section
   `obj_2b36ae673495412aaa53db93aee66688` — 6 blocks, `document_state: textbook_only`, document
   `doc_c91a63d03acc00c4c8e8`; `lesson.begin` returned `run_5d244bb8e06a4149a76ee285f01537ba`,
   `needs_fresh_run`, `resume.available: false (no_binding)`. `enrollment_id`, `started_at` and
   `finished_at` are all in the file, and `approval_at_read` is `superseded`, which is the proof it
   ran before the approve click.
7. **No fresh seed was attempted this round.** The prior attempt already measured the host boundary
   failure (`job_33c16da4… HOST_UNAVAILABLE coursebook.plan.generate exceeded its 240s deadline`),
   and the pass only needs a real existing course; re-seeding would not change any conclusion.

## Files changed by this task

- `scripts/h194-live.mjs` — phase split preserved; containing-title row selection with a loud
  uniqueness assertion; page-title edit preserved; approve phase now also writes `facts.review.json`.
- `scripts/h194-live-drive.py` — `continue-untouched` now derives the edited section from
  `facts.edit.json`, records `started_at`/`finished_at`/`enrollment_id`/approval-at-read/export-status-at-read,
  and records a differing gate reason as a measured deviation instead of aborting; `export` records the
  refusal before raising; new `export-enrollment` for the success-path measurement.
- `audit/h194/live/*` — the four frames and the seven fact files above.

`desktop/plugin.js` was not edited; nothing was merged, pushed, or re-pinned, and the gateway was not
restarted.
