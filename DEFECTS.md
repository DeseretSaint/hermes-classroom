# DEFECTS — first adversarial report

Author: Sentinel. Evidence: `PROBES.md`, `probes/raw/`. Severity is release impact for the
contest vertical slice. Owners are the specialists who fix; I do not patch product code.

| ID | Severity | Owner | Summary |
|---|---|---|---|
| CB-QA-01 | High | Atlas (contract) / Cinder | `pre_llm_call` injection is persisted in `api_content` and replayed; docs call it ephemeral |
| CB-QA-02 | High | Atlas (runtime contract) / Cinder | A timed-out `pre_llm_call` stops firing until plugin reload; turns continue (silent gate loss) |
| CB-QA-03 | High | Cinder (grader) | Aux `task=` silently substitutes a different model when the pinned one is unavailable |
| CB-QA-04 | Medium | Cinder | `timeout=` on `ctx.llm` does not bound wall-clock time (up to ~5 s of retries) |
| CB-QA-05 | Medium | Cinder (identity) | A course workspace inside a git repo admits the repo-root `AGENTS.md` into the course system prompt |
| CB-QA-06 | Medium | Atlas | `/compress` cannot rotate or compact local gateway sessions (`in_place` off); post-compaction state unverifiable |
| CB-QA-07 | Low | Atlas | Plugin hot reload can leave `pre_llm_call` unregistered while other hooks fire |
| CB-QA-08 | Info | Sable / Cinder | A plugin tool's `MEDIA:` tag is not auto-delivered by the messaging gateway (allowlist) |
| CB-QA-09 | P1 | Vellum | `#/coursebook` renders the session home on the installed candidate; the route page never mounts. Reproduction: `docs/REVIEW_CB014.md` |
| CB-QA-10 | P2 | Cinder (domain/evidence) | `evidence.inspect` returns `l2.objectives[].criteria[].check_spec.reference` (the answer key) while the check is still open. Evidence: `tests/adversarial/evidence/attack-state.json` (`results.S07`) |
| CB-QA-11 | P2 (lane disabled) | Cinder (grader) | With the aux grader enabled, learner text reaches the grader and a "pass" carrying instructor-style injection is accepted; no structural cross-check exists for open responses. Evidence: `attack-state.json` (`results.S13`, BLOCKED while the lane is disabled) |

Status note (H-11, 2026-11-07). This table is the record of the first report, at the commit it was
written on. One row is no longer true of the current tree: **CB-QA-10 is fixed** — on `master` at
`498b1da` the S07 probe passes (`open_check_reference_leaks=[]`, `secret_present=False`) and
`coursebook/evidence.py` projects criteria through `PUBLIC_CRITERION_FIELDS`. No card claims the fix;
the derivation is recorded in `docs/HARNESS-STATUS.md` §4. Every other row stands as written.

Status note (H-115-D4, 2026-11-07). The H-115 report's coupling finding — `coursebook/db.py`
opens the single-home pinned database through the host-internal
`hermes_cli.sqlite_util.open_db` — is settled as accepted debt with a guard, not a fix: the import
is named and checked (module, attribute, keyword shape) at its one call site, a drift raises
`HostSeamUnavailable` naming the surface and the host build it was verified against, and
`install_check` reports it as `HOST_SEAM_UNAVAILABLE` before a request is made. Host range and the
upgrade procedure are in `docs/ARCHITECTURE.md` §9; the canary is
`tests/test_host_seam_guard.py`. The public seam (option a) remains a host-side change.

---

## CB-QA-01 — injected context persists and replays

**Expected:** docs (`website/docs/developer-guide/plugins/index.md`, "How injection works"):
injected context is ephemeral, appended at API call time only, "nothing is persisted to the
session database".

**Actual:** the user row stores the exact wire bytes in `api_content`:
`"Reply with the single word OK.\n\nCB_INJECTED_SENTINEL[…] end-sentinel"` (83 chars) while
`content` stays 30 chars; a resumed process with injection disabled replays it
(`sentinel_in_earlier_history: true`) and the model answers `PRESENT`.

**Repro:**
```bash
bash probes/p2_injection.sh
python3 probes/scripts/db_inspect.py ~/.hermes/profiles/cbqa/state.db \
  --session <sid> --needle SENT2-…
```

**Impact:** any Coursebook policy delta (or accidental reference-answer hint) injected by
the hook becomes permanent prompt history, replayed on every later turn and through
compaction summaries. Treat injection as durable: public state only, no keys/secrets.

## CB-QA-02 — timed-out hook never fires again

**Expected:** a hook that exceeds `plugins.hook_callback_timeout` is skipped for that call;
the next turn runs the hook again (docs: "logged and skipped, and the turn goes ahead").

**Actual:** with a 1 s callback budget, a 32 s hook was abandoned and the turn proceeded
(~5 s). The **next** turn (control cleared) produced no `pre_llm_call` at all while
`post_llm_call`, `pre_api_request`, etc. still fired. Only `plugins disable/enable` restored
it.

**Repro:** `bash probes/p7_authority.sh`; compare `raw/p7/events_timeout.jsonl` and
`raw/p7/events_after_timeout.jsonl`.

**Impact:** one slow grading attempt silently disables Coursebook's per-turn gate for the
whole gateway process. The backend `submit_attempt` reconciliation is mandatory; a start-of-
session registration check is advisable.

## CB-QA-03 — silent grader model substitution

**Expected:** "provider/aux failures produce visible degraded states… no fabricated…
mastery" (`PREBUILD_SPEC.md` §12); a grader verdict records its model.

**Actual:** with `auxiliary.cb_grader_bad.model = definitely-not-a-model-xyz`, the call
returned `ok:true`, `verdict: pass`, provider `nous`, model **`stepfun/step-3.7-flash:free`**
after 10.4 s (7.5 s and 59.4 s on earlier runs). No error, no notice.

**Repro:** `bash probes/p4_grading.sh` → `raw/p4/p4_outage.json`.

**Impact:** evidence provenance is wrong and a rubric graded by an unplanned model is
recorded as valid. The grader must compare `result.model` with the rubric's pinned model and
fail closed (`needs_retry`) on mismatch, recording the substitution.

## CB-QA-04 — `timeout=` is not a deadline

**Expected:** `timeout` bounds the call.

**Actual:** `timeout=0.001` raised `APITimeoutError` only after 3.41 s (3.4–5.1 s across
runs); `timeout=0.5` after 5.1 s. `timeout=1` succeeded at 1.12 s. Retries are outside the
requested budget.

**Repro:** `raw/p4/p4_timeout.json`; rerun `cbqa cbprobe grade --scenario timeout --timeout 0.001`.

**Impact:** an 8 s internal deadline cannot be implemented by passing `timeout=` alone.
Wrap the call in an outer wall-clock budget and treat overrun as `needs_retry`.

## CB-QA-05 — repo-root policy leaks into a course in a git repo

**Expected:** an isolated course workspace loads only the Coursebook `AGENTS.md`.

**Actual:** in `test-root/repo/course` (inside a git repo) the system prompt contained both
`CB_CTX_REPO` and `CB_CTX_COURSE`; isolated and outside-git cases were clean.

**Repro:** `bash probes/p3_context.sh` → `raw/p3/repo_course.jsonl`.

**Impact:** course governance could be overridden or polluted by repository policy. Creation
must refuse a workspace inside any git root (or prove a sanitizing mechanism). Keep the
prebuild rule "course workspace outside git roots" as an enforced precondition.

## CB-QA-06 — compression cannot be exercised on this topology

**Expected:** compaction updates the binding tip and fires `post_compaction`; resume returns
to the same lesson revision.

**Actual:** `/compress` warns "session rotation did not occur (session_id unchanged) and
in-place mode is off — preserving original transcript instead of overwriting it (#44794)";
on the 01:59 rerun it instead refused: "Compression refused (summary would grow the
conversation): 8 messages preserved". Auto-compaction never fired at 24 KB inputs.
`post_compaction` was never observed in either case.

**Repro:** `raw/p1/compress.txt`.

**Impact:** restart-after-compaction acceptance cannot be signed off yet. Needs a restarted
gateway with `in_place` enabled or a standalone session; keep the item on the gate list.

## CB-QA-07 — hot reload leaves `pre_llm_call` unregistered

**Expected:** `plugins enable` / config change rewires all hooks for new sessions.

**Actual:** after a config-triggered reload, `pre_llm_call` was absent while
`pre_auxiliary_call`, `post_llm_call` and request hooks fired; a disable/enable cycle fixed
it. (Observed twice: before the 01:47 run and after the timeout run.)

**Repro:** `raw/p7/events_after_timeout.jsonl` vs `raw/p7/events_raise.jsonl`.

**Impact:** install/enable instructions must require a restart (or the plugin must verify its
own hook registration at `on_session_start`). Do not rely on hot reload during the demo.

## CB-QA-08 — plugin media is not gateway-delivered

**Expected (some designs assumed):** a tool returning `MEDIA:/path.png` results in a native
attachment on every surface.

**Actual:** gateway auto-append allowlist is `{text_to_speech, text_to_speech_tool,
image_generate}`; `extract_media()` finds nothing inside a JSON tool result. Desktop's
`TOOL_MEDIA_RENDERER_AREA` is the supported, provenance-scoped path.

**Repro:** `raw/p5/p5_media_seam.json`.

**Impact:** do not promise Telegram/Discord media from Coursebook tools in the contest
build. Desktop renderer must claim the exact registered tool names; text fallback must stay
complete (verified).
