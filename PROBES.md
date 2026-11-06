# PROBES — Coursebook runtime probe report

Author: Sentinel. Runtime: Hermes Agent v0.23.0 (`2bd378ed1b8d`, 2026-11-05), Python 3.14.9,
model `deepseek/deepseek-v4.1-flash-1017` (provider `nous`), profile `cbqa`, local
multiplexing gateway. Harness: `probes/`, raw evidence: `probes/raw/`. Reproduce with
`bash probes/setup.sh && bash probes/run_all.sh`.

Every claim below is backed by a recorded artifact; commands are in the per-probe scripts.
No operator course was read or written and no external message was sent (cron probe jobs
were created **paused**, inspected, then removed; `profile/cbqa/cron/jobs.json` ends at
`{"jobs": []}`).

**Reproducibility:** the whole suite was executed end-to-end at 2026-11-06 02:03 MST after
the last script edit — `probes/raw/RUN.log` (full stdout of every probe),
`probes/raw/VERDICTS.txt` (machine-readable `RESULT` lines), exit 0. Timings vary between
runs; each table below cites the 02:03 run and gives the observed spread where it matters to
the decision.

## Verdict table

| # | Probe | Verdict | Decisive evidence |
|---|---|---|---|
| 1 | runtime/stored ids | **PASS** (compression **BLOCKED**) | `probes/raw/p1/assert.json`, `events.jsonl` |
| 2 | `pre_llm_call` injection replay | **FAIL** | `raw/p2/assert_storage.json`, `events_turn2.jsonl` |
| 3 | context discovery | **PASS**, remote **BLOCKED** | `raw/p3/assert.json`, `* .jsonl` |
| 4 | aux grading latency/timeout/JSON/outage | **PASS** with 3 contract caveats | `raw/p4/assert.json`, `raw/p4/p4_runtime_seam.json` |
| 5 | tool → artifact → `MEDIA:` → renderer | **PASS** (seam); Desktop render **BLOCKED** | `raw/p5/p5_media_seam.json` |
| 6 | cron delivery targets | **PASS** (DST untested) | `raw/p6/jobs.json`, `assert.json` |
| 7 | `submit_attempt` authoritative without hook | **PASS** | `raw/p7/assert.json`, `p7_hook_bypass.json` |

---

## 1. Runtime / stored ids — PASS (compression BLOCKED)

Two turns in one session, the second resumed in a new process, plus one tool call
(`cb_probe_ids`):

- `session_id` is stable across resume and equals `task_id` in every hook; it is the stored
  id (`local-<sha256>`), not a per-process handle.
- `turn_id` is **per turn**: `<session_id>:<session_id>:<8 hex>`, and every `api_request_id`
  is `<turn_id>:api:<N>`. `on_session_start` fires once, on the first turn.
- Plugin **tools receive `session_id` and `task_id` but no `turn_id`** — a tool cannot
  fence a callback by turn without an extra record.
- In the gateway, `os.getcwd()` = `/home/deseretsaint/.hermes/hermes-agent` and
  `HERMES_HOME` env = the default home, while `get_hermes_home()` resolves the active
  profile and `resolve_agent_cwd()` resolves the session's course dir. Any Coursebook code
  that uses `os.getcwd()`/`os.environ` for workspace or DB paths is wrong on this topology.

**Compression segment: BLOCKED.** `/compress` on a resumed local session returned, across
runs, either the runtime warning

```
Manual /compress: session rotation did not occur (session_id unchanged) and in-place mode
is off — preserving original transcript instead of overwriting it (#44794).
```

or a refusal (`Compression refused (summary would grow the conversation): 8 messages
preserved`). Auto-compaction never fired at 24 KB inputs with `compression.threshold`
lowered. The `post_compaction` hook and post-compaction id behaviour therefore remain
unverified; doing so needs a restarted/standalone gateway or `in_place` enabled. See
`raw/p1/compress.txt`.

## 2. `pre_llm_call` injection replay — FAIL (docs contradict persistence)

Docs (`website/docs/developer-guide/plugins/index.md` §pre_llm_call context injection) say
injected context is "Ephemeral — … nothing is persisted to the session database". On this
runtime it is **stored and replayed**:

- Turn 1 (fresh process, sentinel injected): the stored user row has
  `content` = `"Reply with the single word OK."` (30 chars) but
  `api_content` = `"… \n\nCB_INJECTED_SENTINEL[SENT2-…] end-sentinel"` (83 chars).
- Turn 2 in a **new process** with injection **disabled**: `pre_api_request` reports
  `sentinel_in_earlier_history: true`, `sentinel_message_indexes: [1,2,3]`, and the model
  answered `PRESENT`.

Consequence for Coursebook: any policy delta injected by `pre_llm_call` (including a
grading hint or a reference answer) becomes part of the durable, replayed prompt. Treat
injection as persistent and never inject secrets/keys; scope every delta to public state.

## 3. Context discovery — PASS (with a hard placement constraint); remote BLOCKED

System-prompt captures from `pre_api_request` for the same turn in four cwds:

| cwd | AGENTS policies present | Result |
|---|---|---|
| `test-root/isolated_course` (outside git) | `CB_CTX_COURSE` only | PASS |
| `test-root/repo/course` (inside a git repo) | `CB_CTX_REPO` **and** `CB_CTX_COURSE` | parent policy leaks |
| `test-root/repo` | `CB_CTX_REPO` | as expected |
| `test-root/outside` (no AGENTS) | none | PASS |
| isolated + `--ignore-rules` | none | PASS (escape hatch works) |

Decision input: a course workspace **must be created outside any git root** and the
creation path must verify that (walk up for `.git`/`AGENTS.md`), otherwise repo-level
policy is admitted into the course system prompt. Remote Desktop/backend topology is
**BLOCKED** — no remote backend is configured here; the local gateway's filesystem is
shared with the session, but that proves nothing for remote.

## 4. Owned aux structured grading — PASS with three caveats

Samples via `ctx.llm.complete_structured(task="cb_grader")` with an owned schema
(`verdict` + `criteria`):

| Scenario | Observed | Meaning |
|---|---|---|
| realistic rubric, n=5 | p50 **2.21 s**, p95 **4.27 s**, all `content_type=json` | an 8 s deadline has ~1.9× headroom at p95 (other runs: p50 1.42–1.87 s / p95 2.24–4.46 s) |
| `timeout=0.001` | `ok:false`, `APITimeoutError`, wall **3.41 s** | client timeout does **not** bound wall clock (retries); 3.4–5.1 s across runs |
| `timeout=1` | succeeded in 1.12 s | a 1 s budget is not reliable |
| non-JSON text (seam) | `content_type="text"`, `parsed=None` | caller can detect; do not accept |
| schema violation, `jsonschema` importable | `ValueError: … 'fail' is not one of ['pass']` | **fails closed** |
| schema violation, `jsonschema` absent (simulated) | `content_type="json"`, parsed accepted | the spec's hazard is real; hard-require the dep |
| pinned aux model unavailable | silently ran `stepfun/step-3.7-flash:free`, returned `pass`, **10.36 s** | model substitution is undetected by the call (7.5–59.4 s across runs) |

`hermes_bootstrap` makes `jsonschema 4.26.0` importable in the real gateway process; a bare
interpreter (tests, scripts) sees none — so validation availability depends on the import
path, not the manifest.

**Decision — grader body (Cinder):** `complete_structured` is fast enough, but the body must
(1) treat `content_type != "json"`, schema failure, and any exception as `needs_retry`
(never a pass); (2) import and use `jsonschema` itself, refusing to grade if it is missing;
(3) record `result.provider`/`result.model` on the verdict and **refuse a verdict whose
model differs from the rubric's pinned model**; (4) enforce an outer wall-clock deadline
≤ 8 s because `timeout=` can overrun (3.4 s observed for a 1 ms budget). Its own
`auxiliary.cb_grader` slot needs no `llm.task_override` consent; only reusing Hermes built-in
tasks would.

## 5. Tool → artifact → `MEDIA:` → renderer — seam PASS, Desktop render BLOCKED

- The owned tool returns `{"MEDIA": "MEDIA:/…/cli_p5.png", "text_fallback": "…/cli_p5.md",
  "sha256": …}`; both files exist (70-byte PNG + complete text alternative).
- `extract_media()` finds the path when it appears in plain assistant text
  (`raw/p5/p5_media_seam.json` → `extract_media_plain_text`).
- It finds **nothing** in a JSON tool result (`extract_media_from_json_tool_result: []`),
  and gateway auto-append is allowlisted to `text_to_speech`, `text_to_speech_tool`,
  `image_generate` — a Coursebook tool's `MEDIA:` is **not** delivered by messaging
  gateways automatically.
- The Desktop contract (`apps/desktop/src/lib/tool-media-renderers.ts`) is provenance
  scoped: a renderer claims exact tool names, and claims on tools the package did not
  register are refused; the built-in player is the fallback. The skeleton registers no
  renderer yet, and no Electron session was driven here.

**Decision — renderer (Sable):** shipping a renderer is supported once Coursebook's tool
names are frozen; declare them exactly in `data.tools`. Do not promise gateway media
delivery (Telegram etc.) from a plugin tool. End-to-end render stays BLOCKED until an
Electron run is recorded.

## 6. Cron delivery targets — PASS (DST untested)

Jobs created paused, inspected in `profile/cron/jobs.json`, then removed:

- no `--deliver` → stored `"deliver": "local"` (never Telegram, never `origin`);
- `--deliver local` → `"local"`;
- `--deliver telegram:999999999` → stored verbatim, `origin: null` (no send occurred: paused);
- creating the same `--name` twice produced **two jobs** with different random ids.

**Decision:** Coursebook must implement list-by-namespaced-name → reuse itself; cron has no
idempotency key. Timezone/DST arithmetic was not exercised and must be tested separately
before enabling delivery.

## 7. `submit_attempt` authoritative without the chat hook — PASS

A minimal backend command (`probes/plugin`, SQLite `BEGIN IMMEDIATE`) called from a
**process with no agent and no hook**:

| Call | Result |
|---|---|
| key k1, payload A, rev 1 | `committed` |
| key k1, payload A, rev 1 (new process) | `duplicate`, original verdict returned |
| key k1, payload B | `conflict` |
| key k2, rev 9 (current 1) | `stale`, `http 409`, no attempt created |

Hook behaviour on this runtime:

- `pre_llm_call` raising → the turn still ran (`RAISEOK`) — **fail-open**.
- `pre_llm_call` sleeping 32 s with a 1 s callback budget → the turn ran in 3–5 s; the hook
  was abandoned, no policy applied.
- **After a timed-out `pre_llm_call`, the hook did not fire again** on the next turn (other
  hooks still fired); only a plugin reload brought it back. A single slow grade silently
  disables the gate for the gateway process.
- `cbprobe submit` still committed after both failures (`submit_after_bypass: committed`).

**Decision:** the backend command is the door. `pre_llm_call` is an optimisation that can
disappear; every subsequent Coursebook action must reconcile pending attempts and refuse
advancement, exactly as `PREBUILD_SPEC.md` §8 requires.

---

## Cross-cutting hazards recorded for the contract owner

1. Plugin hot reload (`config set`, `plugins enable`) can leave `pre_llm_call` unregistered
   while other hooks still fire (`raw/p7/events_after_timeout.jsonl`, then a reload fixes it).
   Require a restart after enabling Coursebook, or verify registration at session start.
2. `task=` aux routing falls back silently to another provider/model. Pin and verify.
3. `timeout=` is not a wall-clock deadline.
4. `api_content` persistence makes injected context permanent history.
