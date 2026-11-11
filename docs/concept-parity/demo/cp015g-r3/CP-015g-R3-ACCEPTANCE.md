# CP-015g re-run — one-course in-plugin acceptance (run 2, repaired validator seam)

Card: `t_ad25d623`. Run started 2026-11-11 11:26 MST on a **settled host** (previous attempt was
blocked by the platform's own in-flight upgrade). Branch `wt/cp015g-rerun`, local only.

**Outcome in one line:** the plan stage reached a **named, actionable product refusal**
(`source_support`, stage `plan`) with **no unhandled non-JSON validation stop** — the D1 seam held —
but the green path (lesson → check → export → install) was **not reached**, because research was
unavailable to this isolated backend, so the product correctly refused to approve an unsourced plan.
No approve control was offered and nothing unapproved was approved.

## Exact build (recorded, not assumed)

| fact | value |
|---|---|
| worktree HEAD | `0390cd517bbc7fb2c110a2b85cf36ec830305bec` (merge of `origin/master` `279ab6ed` into `wt/cp015g-rerun`) |
| master tip tested | `279ab6ed` (2 commits past `adca16a6`; those two touch only `docs/launch/*`, plugin.js identical) |
| D1 repair in this tree | `VALIDATION_REPAIR_PROMPT_SUFFIX = ".validate-repair"`, `VALIDATION_OUTPUT_TOKENS = 12000`, `gen_validation_records` write path — present in `coursebook/generation.py` |
| `desktop/plugin.js` in checkout | `0112000c418cfcb6815059020857eaf1b8a7299de3d863be1c3b0431cafa0c86` |
| rig home `…-cp015g-r3/home/desktop-plugins/coursebook/plugin.js` | `0112000c…` (**identical** to checkout) |
| operator `~/.hermes/desktop-plugins/coursebook/plugin.js` | `1d23b78cb19f887bc7cce25e4d8b494c032a071ace4e4db24addba97c50a9e0b` — **DIFFERENT** (4 143 063 B vs 3 107 065 B, mtime 11:29). The run measured the checkout module, **not** the operator's installed copy |
| backend | `hermes serve --isolated --port 44619`, `HERMES_HOME=…-cp015g-r3/home` installed from this worktree; `GET /api/plugins/coursebook/runtime` → 200, `wire_version: 26`, `plugin_root: …/.worktrees/t_ad25d623` |
| window | dev Electron `v44.9.3`, vite renderer 5174, CDP 9433, viewport 1344×900 |
| rig state | `~/.hermes/coursebook-test-cp015g-r3` (fresh home; fresh userdata for the first-run check) |

The three plugin paths **do differ**: the checkout/rig pair is byte-identical, the operator copy is
not. That operator copy was not the subject of this card (the card names the released module of the
checkout), but it is recorded here so nobody assumes identity.

## 1. First-run Capabilities → Plugins — defect re-confirmed (`t_244d7ad2` still open)

Clean measurement on a **truly fresh Desktop userdata** (`userdata-fresh3`, `connections.json` only,
no `hermes.desktop.pluginDecisions.v2`; LevelDB contains **0** occurrences of the key):

| t (s) | decisions | plugin switches | Coursebook row |
|---|---|---|---|
| 0 (first paint) | absent | 0 (pane not mounted) | no |
| +0 … +60 | absent | 10 | **no** |

The 10 switches are Auto-update, 2× NousResearch, Bots, Disk Cleanup, Kanban, Radio, one unnamed
Bundled row, rlaope, BkashJEE. An element-level scan for "coursebook" among all switch ancestors
found nothing; the only "Coursebook" strings in the document are chat-session titles in the sidebar
(x≈38, x<392). The plugin is installed and enabled in that home
(`hermes plugins list` → `coursebook enabled 0.1.0`), and the app's own bridge lists the package
folder. It still does not inventory on first run.

Frame: `00-fresh-capabilities-plugins.png` (fully loaded pane; the Coursebook route only appears
after the decision key is written, which is the documented rig shortcut, not product behaviour).

> Measurement note: an intermediate profile (`userdata-fresh2`) ended with
> `{"coursebook":true}` after an automation click inside the pane. I treated that as my own click
> landing on a switch, not as product behaviour, and re-ran the check cleanly without touching any
> switch (`userdata-fresh3` above). No claim here rests on the fresh2 trace.

## 2. Create flow, driven only through the visible UI

Home → **Start a new course** → goal typed in the visible textarea:

> "Learn to greet people and introduce yourself in Japanese before a first trip to Japan"

→ **Continue** → shape step: **Short course** selected (card body click), presentation **Game**
already selected → **Continue** → trailhead review (Short course · 3–6 sections · Game mode ·
Working research depth) → **Create course**.

Frames: `02-create-goal.png`, `03-create-shape.png`, `04-create-review.png`, `05-after-create.png`.

Course row written by the product: `crs_4d57fcfe7b5b44f9ad822876366543bd`, scope `short`,
`presentation_mode=game`, plan job created in the same transaction.

## 3. Plan stage — two jobs, one provider blip, one verdict

### Job 1 — `job_f91f44e3e4074ca18b49b6116ec46b31`

Failed with a **transport** error, not a validator parse error:

```json
{"category":"capability","code":"HOST_UNAVAILABLE",
 "details":{"purpose":"coursebook.plan.validate"},
 "message":"coursebook.plan.validate failed: APIConnectionError: Connection error.",
 "retryable":true}
```

Four calls completed before it (2 × `plan.generate` 8037/5692, 2 × `plan.validate` 106/2145 output
tokens). The backend log names the cause:

```
agent.auxiliary_client: Auxiliary cb_validate: main provider nous is unavailable and no
fallback_chain / fallback_providers is configured — refusing to guess another logged-in provider.
```

The product surface said **"The planning service did not answer"**, kept the authored draft, and
offered **Try again**. A zero-cost provider liveness probe (`GET /v1/models`, 3/3 `200` in
0.24–0.36 s) showed the endpoint healthy, so this was a transient blip.

### Job 2 — `job_9e8bf482679c455ca4eb89574df24c27` (the one allowed `Try again` press)

Completed. Five calls, **none at the 12 000 cap**:
`plan.generate` 5013 / 6301; `plan.validate` 115 / 2098 / 2718 output tokens.

Final state (`checkpoint_json`):

```json
{"generation_state":"needs_review","validation_verdict":"reject",
 "outcome":"rejected","objectives":4,"units":2,
 "rejection_reasons":["objectives 1-4: No source ledger entry supports any Japanese form,
   time-of-day mapping, politeness rule, or self-introduction order, so the content must not
   be presented as validated."],
 "validation":{"outcome":"rejected","verdict":"reject","calls":3,
   "research_status":"unavailable","shape_violations":0}}
```

Plan `pln_17fc78ad20014b83860b54ad57a08993`, draft v1 `plan sha256:27b70458feb2…`.

**The visible panel (frame `07-plan-verdict-panel.png`):**

> **The plan could not show where its facts came from**
> One part of the draft could not be tied to a source the research pass actually read. The draft is
> saved, so nothing is lost. Trying again runs the research pass again and writes a new plan version;
> if the sources still do not cover it, this same check refuses the new attempt.
> **Where:** objectives 1-4: whether each claim has a source that was actually read
> Your draft is still here. It is not approved, and no lesson will be written from it.
> **[Try again]**

No Approve control exists on that surface (`[data-cb-route] button` texts: Home, Courses, Workshop,
Parent Studio, All courses, Open the plan, Overview, Learn, Notebook, Evidence, Attempts, Plan,
Sources, Export, Try again). The Sources panel states "No source is recorded for this plan".

**Why research was unavailable** (environment, not the validator): the isolated backend cannot read
the web-search credential —

```
plugins.web.perplexity.provider: Perplexity search error: Hermes could not read this profile's
PERPLEXITY_API_KEY (an internal profile-scoping bug on the multiplexed gateway, not your
configuration). Run `hermes gateway restart`; if it keeps happening, report it with
`hermes debug share`.
```

so `research_status: unavailable` → empty source ledger → `source_support` fail → refusal.

## 4. The validator seam itself — what this card exists to measure

* No `VALIDATION_FAILED` in either job; the completed job's `error_json` is `{}`.
* `gen_validation_records` holds **one** row for the plan — `parse_outcome: parsed`,
  `attempt_index: 2`, `pass_index: -1`, `repair_attempted: 0`, full `criteria_json` with 11 criteria
  (all pass except `source_support: fail` and `factual_correctness: unknown`).
* Because the validator's answers parsed, the **repair branch was not exercised in this run** (no
  unreadable answer occurred). What is proven here is the card's acceptance condition: the stage
  reached a real verdict without an unhandled non-JSON stop.

## 5. Spend

| metric | value |
|---|---|
| plan authoring jobs | 2 (one failed on a provider transport error, one completed) |
| `Try again` presses | **1** |
| provider calls | 9 (4 in job 1, 5 in job 2) |
| output tokens | 32 225 total — generate 25 043, validate 7 182 |
| calls at the 12 000 cap | 0 |
| image/vision spend | 3 vision checks, one per captured frame |
| attempts / evidence / lessons / checks / packs | 0 / 0 / 0 / 0 / 0 |

Full call table: `provider-calls.json`; job rows: `jobs.json`.

## 6. Board counts (rig DB, after the run)

| table | rows |
|---|---|
| courses | 1 |
| plans | 1 |
| objectives | 4 |
| plan_units | 2 |
| gen_lessons | 0 |
| checks | 0 |
| packs | 0 |
| jobs | 2 |
| attempts | 0 |
| evidence | 0 |
| world_assets | 0 |
| gen_validation_records | 1 |

## 7. Verdict against this card's acceptance

| acceptance item | result |
|---|---|
| course with objectives, lessons, ≥1 check, installed pack — **or** a named, actionable refusal with the stage | **Named refusal at stage `plan`**: `source_support`, reason quoted above, product surface names the failing criterion and the draft is retained. Objectives exist (4); lessons/checks/pack do **not** |
| no unhandled non-JSON validation stop | **PASS** — validator answered, parsed, verdict recorded; job completed |
| review packet, frames, job table, board counts, local commit | this file + frames + JSON + local commit |
| fresh-userdata Capabilities → Plugins shows Coursebook? | **NO** — defect re-confirmed on a clean profile at t+60 s |

**Not proven / not attempted, stated plainly:**
* No lesson-player frame, no check frame, no export/import/install frame. They are unreachable while
  the plan is refused, and only one `Try again` was permitted.
* The D1 *repair* path (unreadable answer re-asked inside the stage) was not triggered this run.
* The green course path remains unmeasured on master; the blocker is the isolated backend's
  unreadable web-search credential, not the validator.

## Frames (1344×900, rig window)

| file | what it shows | sha256 |
|---|---|---|
| `00-fresh-firstpaint.png` | fresh userdata first paint | `0ed4a31d…` |
| `00-fresh-capabilities-plugins.png` | fresh userdata, Capabilities → Plugins, 10 switches, **no Coursebook** | `cc680a10…` |
| `02-create-goal.png` | goal step, typed goal | `e1e26d51…` |
| `03-create-shape.png` | shape step, Short course + Game selected | `16406ef2…` |
| `04-create-review.png` | trailhead review | `8dc17c45…` |
| `05-after-create.png` | plan job running after Create course | `01b7e947…` |
| `06-plan-stage.png` | job 1 failure surface ("The planning service did not answer", Try again) | `7bb59d6d…` |
| `07-plan-verdict-panel.png` | **validator refusal panel** — source_support, not approved, no Approve control | `86fe2a55…` |

## Repro

```bash
# rig (isolated backend + window), from this worktree
CB051_STATE=~/.hermes/coursebook-test-cp015g-r3 CB051_BACKEND_PORT=44619 \
CB051_CDP_PORT=9433 CB051_TOKEN=cb015g-r3-token \
ELECTRON_BIN=~/.hermes/hermes-agent/apps/desktop/node_modules/electron/dist/electron \
  scripts/rig-private-desktop.sh

# visible create flow (goal → Short course → Game → Create course)
CB015_CDP_PORT=9433 node scripts/cp015g-r3-create-1.mjs
CB015_CDP_PORT=9433 node scripts/cp015g-r3-create-2.mjs
# follow the job and read the verdict
CB015_CDP_PORT=9433 node scripts/cp015g-r3-verdict-frame.mjs
# first-run plugin inventory on a fresh userdata
CB015_CDP_PORT=9433 node scripts/cp015g-r3-fresh-timeline.mjs

# evidence
sqlite3 ~/.hermes/coursebook-test-cp015g-r3/home/plugin-data/coursebook/data.db \
  "select id,kind,state,error_json from jobs; select * from gen_validation_records;"
```
