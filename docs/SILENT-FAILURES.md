# SILENT FAILURES — every swallowed failure that can become a user-visible fact

**Task:** H-114 · **Author:** Sentinel (adversarial QA) · **Date:** 2026-11-07
**Tree:** `hermes-classroom` @ `48be4af` (audited), line numbers re-verified at `71c03f2` — the only
files that moved were `coursebook/install_check.py` and `docs/INSTALL.md`, so every reference below
still resolves. `desktop/plugin.js` blob `bc7a411`.
**Scope:** read-only audit. No product code was edited. Probes ran against throwaway
`HERMES_HOME` profiles; the operator's coursebook store was never opened.

This document inventories every broad `except` / `.catch` in the shipped Coursebook plugin whose
handler changes something the learner or parent can see, and separates three classes:

| class | meaning |
| --- | --- |
| **SILENT FALSEHOOD** | the failure is rendered as a *different, confident fact* ("not recorded", "cannot import", "Failed", "no sources"). The user cannot tell a failure from a real state. |
| **SILENT DATA LOSS / INTEGRITY** | the failure removes or fails to record durable evidence, or opens a gate that exists to protect evidence. |
| **SAFE DEGRADATION (LABELLED)** | the failure is rendered with a visible label that names the degradation and, where relevant, the next action. Acceptable — listed in §5 with the exact copy so the label is not taken on trust. |

**Totals:** 26 findings. 25 are defects — 11 silent falsehoods, 7 silent data-loss/integrity, 7
unlabelled omissions — and 1 is a labelled degradation with a residual diagnostic gap (F25). Every
labelled-safe handler is listed in §5 with the exact copy it shows, so no "acceptable" label is
asserted without a visible label or a named next action.

---

## 1. How this was verified

Static inventory: an AST pass over `coursebook/*.py` (71 broad handlers) plus a line scan of
`desktop/plugin.js` (48 `catch` sites), then a read of each handler *and* the code that renders its
return value. A finding only enters this report if the handler's output reaches a surface a user
reads.

Executed probes (all printed real output, no mocks of the product's own logic — only of the failing
seam):

* `probe_h114_backend.py` — 11 probes against the real migrations, real handlers and a real
  `cb.db`, each forcing one failure inside a fresh throwaway profile.
* `probe_h114_js.py` — mounts the **shipped, unmodified** `desktop/plugin.js` under jsdom with a
  stub plugin SDK and a `ctx.rest` whose `check.get` throws, then records the rendered text.

Both scripts live beside this task's workspace
(`~/.hermes/kanban/boards/coursebook/workspaces/t_a71e3255/`). Re-run:

```
cd /home/deseretsaint/Projects/hermes-classroom
python3 <workspace>/probe_h114_backend.py     # 11 probes, writes probe-results.json
python3 <workspace>/probe_h114_js.py          # renders the check card with a dead stimulus read
```

Findings marked **[EXECUTED]** were reproduced in this run. Findings marked **[STATIC]** are proven
by reading the handler *and* the exact rendering path; they are labelled as such because forcing
them needs a live Desktop window (the hook/`ctx.rest` failure is not reachable from a headless
harness). No claim in this document rests on "the code looks reasonable".

---

## 2. Findings, worst first

### F1 — Stale-source grading gate is fail-open when a dependency table cannot be read
* **SILENT DATA LOSS / INTEGRITY · severity: critical · [EXECUTED]**
* `coursebook/sources.py:123` (`_sections_citing`: `except Exception: return []`) feeding
  `coursebook/sources.py:167` (`impact`: `except Exception: lessons = []`) and
  `coursebook/sources.py:339-355` (`check_staleness` → `assert_check_current`).
* `impact()` is the only thing that decides whether a stale/unreachable source touches a check's
  objective. If the `gen_plan_sections` read fails for any reason, the objective list comes back
  empty, `check_staleness` answers `None`, and `assert_check_current` lets `attempt.submit` grade
  the answer. The learner's answer is then committed as evidence against content the ledger has
  already marked `stale`/`unreachable`.
* **Proof (P1):** baseline — stale source citing the objective ⇒ `CHECK_STALE` refusal; same store
  with `gen_plan_sections` returning a `DatabaseError` ⇒ `impact.objective_ids=[]`,
  `check_staleness=None`, **gate PASSED grading (FAIL-OPEN)**.
* **Risk statement:** any corrupt page, locked table or schema drift silently converts "refuse to
  grade stale content" into "grade it". This is the exact integrity control `AUDIT.md` R6 claims.
* Fix card: **H-123**.

### F2 — A failed stimulus read renders a check with no question and claims the question is above
* **SILENT FALSEHOOD · severity: high · [EXECUTED]**
* `desktop/plugin.js:6670` (`rpc('check.get', …).catch(() => {})`) with the answer-only fallback at
  `desktop/plugin.js:7113` and the copy at `desktop/plugin.js:7427`.
* `check.open` returns identity only; the prompt/choices/checklist come from `check.get`. On any
  failure of that second read the card renders with **no stimulus at all** and tells the learner
  *"The question and any choices are shown above; this field records what you answered."*
* **Proof (P-JS):** rendered extraction, real module, `check.get` throwing:
  `…Check v1 discrimination Your answer The question and any choices are shown above; this field
  records what you answered…` — and no error element anywhere in the tree.
* **Risk statement:** a learner answers a question that is not on screen; a checklist check
  silently degrades to a free-text box (its items never load, so `checklistItems` returns `[]`).
  Graded evidence is then produced without the served stimulus.
* Existing card already owns this: **H-97** (`t_66312e2b`) — see the board comment with this
  reproduction.

### F3 — `post_llm_call` swallows a snapshot failure, so the tutor turn never enters the lesson
* **SILENT DATA LOSS · severity: high · [EXECUTED]**
* `coursebook/hooks.py:210` (`except Exception: return None`) around
  `coursebook/turn.py:558` `record_assistant_snapshot`.
* The snapshot is what writes `lesson_segments` (`kind='teaching'`) — the durable record the
  textbook/guided views read. A read-only-database window, a busy lock, or a revision that moved
  between the two reads loses the turn; the hook returns `None` and Hermes never sees an error.
* **Proof (P10):** baseline segment count 1 after a normal turn; with the snapshot write raising,
  `post_llm_call` returned `None` and the segment count stayed 1 — the second teaching turn is
  missing from the lesson page with no marker.
* **Risk statement:** the lesson silently loses the explanation the learner was just given. The
  transcript survives in chat, but the lesson's own record — the evidence a parent or reviewer
  reads — is incomplete and looks complete.
* Fix card: **H-124**.
* **FIXED (H-124, `t_e3f0d994`).** `post_llm_call` retries the snapshot write once; if it still
  fails, the loss is written to the `hook_errors` table (`cb.db` v10,
  `0010_hook_errors.sql`) as `kind='snapshot_write_failed'` with the session id, run, nonce,
  detail and attempt count. The hook still returns `None` and never fails the turn. The pane reads
  the per-run count from the `binding.get` response it already requests
  (`binding.snapshot_failures = {recorded, last_at}`, `null` when the count cannot be read). When
  even that row cannot be written, the hook logs at ERROR with
  `coursebook_event="snapshot_write_failed"`, `recorded=False` — stated, never implied. Guard:
  `tests/test_hook_snapshot_loss.py`; schema guard:
  `tests/test_contracts.py::DbV10AmendmentTest`.

### F4 — A finished pack import is journaled as "interrupted", and the UI says the worker died
* **SILENT FALSEHOOD (with retry cost) · severity: high · [EXECUTED]**
* `coursebook/pack_flow.py:466` (`_import_job_finish`: `except Exception: pass`) and
  `coursebook/pack_flow.py:1843` (`recover_interrupted_imports` relabels every `state='running'`
  import at startup); rendering at `desktop/plugin.js:14322`
  (*"Interrupted: the worker stopped mid-job. Its checkpoint was kept; run the stage again to
  finish it."*).
* A `jobs` write that fails after a *successful* import (lock contention at the moment the import
  commits) leaves the row `running`; the next process start marks it `interrupted_requires_retry`.
* **Proof (P3):** before finish `running`; after a successful import `running`; after startup
  reconciliation `interrupted_requires_retry` (`recovered=['job_…']`).
* **Risk statement:** the user is told their completed import died and invited to run it again —
  the one action most likely to duplicate a course. `pack_import` also swallows the journal when
  `_import_job_start` fails (`pack_flow.py:448`: `return None`), in which case the import exists but
  no job row does, so job history and progress are silent about it.
* Fix card: **H-125**.

### F5 — A failed estimate read is rendered as "Session length not recorded"
* **SILENT FALSEHOOD · severity: high · [STATIC]**
* `desktop/plugin.js:3084` (`.catch(() => … status: 'none', minutes: null …)`) →
  `desktop/plugin.js:2100` `deskEstimateLabel` → `'Session length not recorded'`.
* `useCourseMinutes` reads the pack manifest or `parent.brief.get`. A backend failure is
  indistinguishable from a backend that answered "this course has no recorded estimate": the Field
  Desk prints *"Session length not recorded"* and `data-cb-continue-minutes` carries that string.
  The doc comment on the same function (`plugin.js:2094`) claims the value is *"either recorded by
  the backend or said to be missing"* — a third case exists and is unrepresented.
* **Risk statement:** a parent planning a lesson is told the author never estimated it when the
  backend simply failed to answer. There is no retry affordance.
* Fix card: **H-126**.

### F6 — A failed intake probe is rendered as a capability wall
* **SILENT FALSEHOOD · severity: high · [STATIC]**
* `desktop/plugin.js:1184` (`usePackIntake` catch → `status: 'unsupported'`) → copy at
  `desktop/plugin.js:1529`: *"This backend build cannot receive a local pack … this profile's
  backend does not, so no picker is shown and nothing here pretends to import."*
* Any transport error, timeout or 500 on `GET /packs/intake` produces the same state as a backend
  that genuinely lacks `grant_local_file`.
* **Risk statement:** the user is told the product cannot import packs and stops trying; there is no
  "could not check" state, no retry, and the copy explicitly asserts the backend lacks the door.
* Fix card: **H-127**.

### F7 — `store_exists()` answers "no store" when the store root cannot be resolved
* **SILENT DATA LOSS / INTEGRITY · severity: high · [EXECUTED]**
* `coursebook/db.py:302` (`except Exception: return False`).
* Two consumers take `False` as the strongest possible statement: the chat lifecycle hooks treat the
  chat as *not Coursebook use* (`coursebook/lesson_skills.py:114`, `coursebook/hooks.py` governed
  check) and `health` reads it as *nothing provisioned yet*.
* **Proof (P7):** `store_root()` raising ⇒ `store_exists() -> False`. Nothing distinguishes this from
  an empty install.
* **Risk statement:** a real, populated store that temporarily cannot be resolved is reported as
  "this chat is not a lesson", so a bound lesson turn loses its tutor skill and its usage
  attribution, silently. The docstring claims the opposite ("a store that exists but cannot be read
  stays a hard failure"); the code cannot tell the two apart because the failure is in resolution.
* Fix card: **H-128**.

### F8 — A cancel request that cannot be read is reported as "not cancelled"
* **SILENT DATA LOSS (spend) · severity: high · [EXECUTED]**
* `coursebook/generation.py:848` (`_job_cancel_probe.probe`: `except Exception: return False`).
* The probe is consulted at every provider/research boundary (H-66). If the job store read fails,
  the probe answers "keep going" and the job continues spending on a cancel the user already asked
  for.
* **Proof (P6):** with `job_service.is_cancel_requested` raising, `probe() -> False`.
* **Risk statement:** the UI shows `cancel_requested`/`cancelling` (*"the job stops before its next
  step"*, `plugin.js:14306`) while the job keeps calling the provider. Unbounded spend on a cancel.
* Fix card: **H-129**.

### F9 — The job pump silently skips a queued job it cannot parse, forever
* **SILENT FALSEHOOD · severity: medium · [EXECUTED]**
* `coursebook/job_service.py:762` (`run_pending`: `except Exception: continue`).
* The resolver runs `_load(row['brief_json'])`; a corrupt/legacy brief raises and the loop moves on
  without writing anything to the row.
* **Proof (P5):** `run_pending -> []`, row still `state='queued'`, `error_json='{}'` — the UI renders
  *"Queued. The job runner picks it up on its next tick; nothing is spent until it starts."*
  (`plugin.js:14300`) indefinitely.
* **Risk statement:** a permanent, invisible stall. The user waits, the queue never drains, no
  diagnostic exists, and the same row is skipped on every tick.
* Fix card: **H-130**.

### F10 — A failed recovery checkpoint is dropped to `{}`
* **SILENT DATA LOSS · severity: medium · [EXECUTED]**
* `coursebook/job_service.py:723` (`_stage_checkpoint`: `except Exception: return {}`).
* A failed long job is supposed to persist `exc.to_checkpoint()` so a retry resumes instead of
  re-authoring (sections completed, usage, budget). If serialising it raises, the job fails with an
  empty checkpoint and the next attempt starts from zero cost.
* **Proof (P4):** `_stage_checkpoint -> {}`.
* Fix card: **H-130** (same lifecycle card).

### F11 — `health.get` swallows the migration error and the pane guesses "not migrated yet"
* **SILENT FALSEHOOD (diagnosis) · severity: medium · [EXECUTED]**
* `coursebook/api.py:77` (`except Exception: pass` around `db.ensure_schema()`) →
  `coursebook/db.py:447` `health()` returns only `{ready, schema_version}` →
  `desktop/plugin.js:900` `'Database not migrated'` and `plugin.js:934-964` (*"The course database is
  not migrated yet … this profile has no course tables"*).
* **Proof (P8):** with `ensure_schema` raising `OperationalError('disk I/O error')`,
  `_health_get` returned HTTP 0 with `db={ready: True}` and body keys
  `['backend','contract_version','db','plugin_version']` — the failure left **no trace at all** in the
  response. A store whose migration actually failed is then reported as a store that has not been
  migrated, which is a different and actionable-wrong statement.
* Fix card: **H-131**.

### F12 — Tombstone sync failure leaves a deleted pack looking installed
* **SILENT FALSEHOOD (library state) · severity: medium · [EXECUTED]**
* `coursebook/pack_flow.py:1806` (`sync_tombstones`: `except Exception: return []`).
* `pack.delete` (kernel) freezes the pack row and keeps evidence; this function is the only writer
  that mirrors that state into the library index. If the `packs` read fails at startup, nothing is
  written and the index keeps `state='installed'`.
* **Proof (P11):** `sync_tombstones()` returns `[]` both when there is nothing to do and when the
  read raises — the two are indistinguishable to the caller and to the user.
* **Risk statement:** a pack the user deleted still appears in the library and can still be picked
  for a new course; the import path then refuses (frozen) — a contradiction the user has to debug.
* Fix card: **H-132**.

### F13 — A startup import recovery that fails leaves the job spinning as "Working"
* **SILENT FALSEHOOD · severity: medium · [EXECUTED path]**
* `coursebook/pack_flow.py:1843` (`recover_interrupted_imports`: `except Exception: return recovered`)
  — only the staging reconcile result is returned, interrupted jobs stay `running`.
* Rendering: `plugin.js:14312` `Working…` for a `running` job with no lease.
* **Risk statement:** the same class as F4 but from the other direction: a process that died mid-import
  is not reclaimed, so the pane shows live work that no worker owns. The docstring claims *"The UI
  shows them through jobs.list so a user is told rather than left guessing"*.
* Fix card: **H-125**.

### F14 — An unreadable skill lookup erases the tutor/coach line entirely
* **SILENT OMISSION · severity: medium · [STATIC]**
* `desktop/plugin.js:16823` (`.catch(() => setSkillNote(null))`) with rendering at
  `plugin.js:16932-16944`.
* `lesson_skills.skill_for_session` already answers honestly (`reason='unreadable'`,
  `coursebook/lesson_skills.py:134`), but the pane treats any non-`skill` answer as "say nothing".
* **Risk statement:** the user cannot tell "this chat has no tutor skill because it is unrelated"
  from "Coursebook could not read the store". The line is the only place the lesson's instruction is
  made visible before the next message.
* Fix card: **H-133**.

### F15 — A failed grading-lane probe drops the "open lane unconfigured" warning
* **SILENT FALSEHOOD (grading provenance) · severity: medium · [STATIC]**
* `desktop/plugin.js:7156` (`catch (err) { /* read-only lane probe must never replace the verdict */ }`)
  with the flag at `plugin.js:7105/7513`.
* The probe reads `quiz.history` to learn whether the attempt was graded by the open (unconfigured)
  lane. When the read fails the warning is simply absent, so the verdict renders as a normal graded
  attempt.
* **Risk statement:** the surface that exists to disclose a weaker grading path fails closed *toward
  the user's confidence*, not toward disclosure.
* Fix card: **H-133**.

### F16 — Syllabus "cancel" tells the user nothing more was sent while the parse job runs
* **SILENT FALSEHOOD · severity: medium · [STATIC]**
* `desktop/plugin.js:6021` (`rpc('jobs.cancel', …).catch(() => null)`) → `plugin.js:6096`
  `'Cancelled. Nothing further was sent.'`
* The comment above it states the intent ("a real cancel is sent when the backend has already minted
  the parse job"), but the promise is never awaited and its failure discarded; `onCancel` runs
  synchronously right after.
* **Risk statement:** a refused or failed `jobs.cancel` (stale job id, backend down) still renders the
  cancelled state. The user is told work stopped while the backend keeps parsing and may create a
  course from it.
* Fix card: **H-134**.

### F17 — Single-home pin silently disabled when the host module is missing
* **SILENT DATA LOSS / WRONG HOME · severity: medium · [STATIC]**
* `coursebook/db.py:117` (`single_home_pin`: `except Exception: return None`).
* `None` is the ordinary answer for "not a single-home host" and the fallback for "could not resolve
  the launch home". With the flag set but `hermes_constants` unimportable, storage resolves to the
  ambient profile — the root profile that H-69 showed reads the wrong store.
* **Risk statement:** reads/writes land in a different home than the one the process declared, with
  no diagnostic. Either the pin is required (and a miss must fail closed) or it is not (and the flag
  is noise).
* Related existing card: **H-110** (install/doctor); board comment added.

### F18 — A failed job poll is rendered as "Failed."
* **SILENT FALSEHOOD (job state) · severity: medium · [STATIC]**
* `desktop/plugin.js:14357` (`setJob({state: 'unknown', error})` and keeps polling) →
  `JobStateText` has no `unknown` branch (`plugin.js:14290-14340`) so it falls through to
  `Failed (code).`
* **Risk statement:** a transient read error on a healthy job tells the user their generation
  failed. The retry affordance (`retryable`) is not offered for `unknown`, so the honest recovery is
  hidden too.
* Related existing card: **H-117** (job progress honesty); board comment added.

### F19 — A reduced-motion read failure defaults to full motion
* **UNLABELLED A11Y REGRESSION · severity: medium · [STATIC]**
* `desktop/plugin.js:7965-7968` (`useCbMotion`: `catch { /* assume the default, motion-on posture */ }
  … return 'full'`).
* Every animation gate in the pane keys off this value. A host whose `matchMedia` throws gets the
  motion-on path, contradicting the user's OS preference.
* **Risk statement:** a user who set "reduce motion" gets animation with no way to know the
  preference was not read. Fail-safe direction should be `reduced`.
* Related existing card: **H-98** (a11y sweep); board comment added.

### F20 — `impact()` shortens the dependent-lesson list on any read error
* **SILENT FALSEHOOD · severity: medium · [EXECUTED]**
* `coursebook/sources.py:167` (`impact`: `except Exception: lessons = []`).
* **Proof (P2):** healthy `lesson_ids=['les_h114_1']`; with `gen_lessons` unreadable
  `lesson_ids=[]` while `objective_ids` still resolved.
* **Risk statement:** the review list a human uses to decide what to re-audit after a source change
  under-reports. Same root cause as F1; fix in the same card (**H-123**).

### F21 — Post-tool usage attribution silently dropped
* **SILENT OMISSION · severity: low-medium · [STATIC]**
* `coursebook/hooks.py:269` (`post_tool_call`: `except Exception: return None`).
* **Risk statement:** `usage.summary` (`coursebook/domain.py:2024`) sums only rows that exist, so a
  store hiccup makes token totals and `calls` silently low. No surface renders `usage.summary`
  today, so this is metering debt rather than a visible falsehood — recorded so it is not mistaken
  for a working meter when H-117 starts rendering cost. Folded into **H-130** as a note.

### F22 — `STARTUP_RECONCILIATION` is computed and never read
* **SILENT OMISSION · severity: low · [STATIC]**
* `coursebook/hooks.py:304` computes it; the only other reference is a comment in
  `coursebook/job_service.py:910`. A reconciliation error (returned as `{error, message}`) is
  therefore never surfaced or logged by the plugin.
* **Risk statement:** orphaned artifact staging and cancelled-job reconciliation can fail at load
  with no trace outside the returned dict nobody reads. Folded into **H-131**.

### F23 — `_library_unit_label` returns `None` on any read error
* **SILENT OMISSION · severity: low · [STATIC]**
* `coursebook/domain.py:2197` (`except Exception: return None`) — the library row renders with no
  unit label, identical to a course that has no units.
* **Risk statement:** a v2 course whose `plan_units` read fails looks like a legacy v1 plan. Low
  impact (label only), no card; noted here so the next library work does not mistake silence for
  data.

### F24 — DOCX relationship scan skips an unreadable `.rels` part
* **SECURITY-ADJACENT FAIL-OPEN · severity: low · [STATIC]**
* `coursebook/syllabus.py:236` (`except Exception: continue`) — the loop that refuses
  `TargetMode="External"` silently skips a member it cannot read.
* **Risk statement:** the guard exists to refuse a syllabus that references external targets; a
  corrupt/unreadable `.rels` member bypasses it for that part instead of refusing the document.
  Consistency with the surrounding code (which refuses `external_relationship`) says this branch
  should refuse too.
* No card of its own: appended to **H-127** as a second, cheap hardening item.

### F25 — `stt` collapses every inference failure into one opaque reason
* **SAFE DEGRADATION (LABELLED), residual diagnostic gap · severity: low · [EXECUTED]**
* `coursebook/stt.py:230` raises `SttUnavailable('transcription_failed')` for any
  `WhisperModel.transcribe` exception; the exception type is logged at WARNING only.
* The learner-facing copy is honest
  (`plugin.js:9031` *"The recogniser could not transcribe this take. Nothing was recorded as
  evidence."*) and practice-only is stated, so this is **not** a falsehood. The gap is that
  dependency/model/decode/inference failures all reach the operator as four coarsely distinct codes.
* Evidence: `described() = available True, reason None` on this machine.
* Related existing card: **H-108**; board comment added (no new card).

### F26 — `profileRoutes` failure drops the connection id for RPC
* **SILENT ROUTING RISK · severity: low-medium · [STATIC]**
* `desktop/plugin.js:17238` (`.catch(() => { profileRouteCache = [] })`) and
  `plugin.js:424-433` (`currentScope().connectionId` becomes `null`).
* **Risk statement:** every RPC then travels without a `connectionId` and relies on the host's
  ambient connection. With one connection that is harmless; on a multi-connection install it is a
  route to the wrong backend for reads and writes. No label, no retry. Appended to **H-110** and
  **H-132** context (routing + library state); see board comments.

---

## 3. Findings by class

| class | findings |
| --- | --- |
| SILENT FALSEHOOD | F2, F4, F5, F6, F9, F11, F12, F13, F15, F16, F18 |
| SILENT DATA LOSS / INTEGRITY | F1, F3, F7, F8, F10, F17, F20 |
| SILENT OMISSION (unlabelled decrease) | F14, F19, F21, F22, F23, F24, F26 |
| SAFE DEGRADATION, residual gap | F25 |

---

## 4. Prioritized fix order

1. **F1** stale-source gate fail-open — integrity of every graded attempt (H-123, cinder, P0).
2. **F2** check without its question — every lesson turn (H-97 existing, vellum, P0).
3. **F3** lost teaching snapshot — durable lesson record (H-124, sable, P0).
4. **F4/F13** import journal lie — duplicate-course risk (H-125, cinder, P1).
5. **F7** unreadable store reported as absent (H-128, cinder, P1).
6. **F8** cancel ignored on read failure — unbounded spend (H-129, cinder, P1).
7. **F9/F10** queue stall + dropped checkpoint (H-130, cinder, P1).
8. **F6** false capability wall (H-127, sable, P1).
9. **F5** false estimate label (H-126, vellum, P1).
10. **F11/F22** health without a diagnostic (H-131, sable, P2).
11. **F12** deleted pack still installed (H-132, lattice, P2).
12. **F14/F15** pane reads that vanish (H-133, vellum, P2).
13. **F16** cancel not confirmed (H-134, vellum, P2).
14. **F17/F26/F19** follow-ups attached to H-110, H-98, H-117.

---

## 5. Safe degradations — acceptable because they carry a visible label

Each entry states the exact copy the user sees, so "acceptable" is not an assumption.

| site | handler | visible label (quoted from the shipped file) |
| --- | --- | --- |
| `coursebook/artifacts.py:794` | media generation failure → `degraded=True, reason=…` | `plugin.js:9713` *"Media is degraded: {reason}"*; text equivalent kept |
| `coursebook/media.py:453` | per-item media failure | same `degraded`/`reason` note above, item-scoped |
| `desktop/plugin.js:8988` | artifact preview transport error | *"This media could not be previewed (…); the text equivalent remains."* |
| `desktop/plugin.js:16997` | binding read failure | *"Cannot read this chat's binding"* + code + message |
| `desktop/plugin.js:9144` | pronunciation status transport error | *"Practice only, not graded. The recogniser status could not be read (…)."* |
| `coursebook/stt.py:98-230` | recogniser unavailable | *"Practice only, not graded. Recording stays off because …"* + reason copy map |
| `desktop/plugin.js:1463-1887` | pack choose/preview/import/export failures | `setError({message: describeError(...)})` rendered as an error state |
| `coursebook/research.py:730-786` | per-URL research failure | appended to `failures[]`/`entry.error` and returned in the run result |
| `desktop/plugin.js:3083` (opening of `FieldDesk` docs) | page read failure | error + `stale: true`, previous data kept |

Two of these still deserve a next action and are therefore *not* marked acceptable-and-done:
`artifacts.py:794` and `media.py:453` carry `degraded` but the lesson body does not repeat the reason
next to the missing audio (only the media frame does); noted for H-107's owner.

---

## 6. What this audit did NOT prove

* The JS findings other than F2 were not executed against a live Desktop window: they need a host
  whose `ctx.rest`/`matchMedia`/`profileRoutes` fails, which this headless run cannot create. They
  were confirmed by reading the handler and its exact rendering branch, and are labelled [STATIC].
* No real provider outage, real disk-full or real OS-level lock was induced; failures were forced at
  the seam (`mock` on the innermost collaborator only), never by mocking coursebook's own logic.
* `usage.summary` has no rendering surface today, so F21 is metering debt, not a visible defect.
* The a11y items here are *honesty* items; the full keyboard/200 %/screen-reader gate remains H-85/H-98.
