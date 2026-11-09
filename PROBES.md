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

## Re-run on the release candidate — 2026-11-08 (MST)

The tables below were first measured before the H-208/H-182 union. Gate 6 now rests on this
re-run instead:

| Fact | Value |
|---|---|
| Measured commit | `bc9f6072fc0509f151a00e303243ea6f04b47bad` (`bc9f607`, H-203 merge on the H-209 tree `ab6dc7e`; code tree unchanged, module pin identical) |
| Shipped module | `desktop/plugin.js` sha256 `cd862140f0f03783f098326017db5225bb58b400e3595b321200480aa865c516` |
| Probe plugin | `probes/plugin/__init__.py` sha256 `36411bfe805adb9b273993d2d9d1e971a5b9b256524c030b4137212444610a3d` |
| Host runtime | Hermes Agent v0.23.0+1.gc02e6e0.dirty, local `c02e6e01806d` (the first run was `2bd378ed1b8d`; the host moved, so this is a re-measurement on a newer runtime, not a replay of the old numbers) |
| Profile wiring | `cbqa`; `plugins/coursebook` → this worktree and `plugins/cb-probe` → `probes/plugin`, both `realpath`-resolved and sha256-checked before the run |
| Driver | `bash probes/setup.sh && bash probes/run_all.sh`; finished 2026-11-08 21:43 MST, exit 0, wall 1 m 57 s |

**Assertion files are byte-identical to the previous committed run** except the two that embed
measured wall-clock (`p4/assert.json` latencies, `p7/p7_hook_bypass.json` `timeout_wall_s`).
That is the reproduction claim: the probes did not change their verdicts on this tree.

| # | Probe | Expected | Observed on `bc9f607` | Artifact (sha256) |
|---|---|---|---|---|
| 1 | runtime/stored ids | session id stable across resume; turn id per turn; tool sees session+task, no turn | **PASS**, 8/8 checks (`turns_observed=2`) | `probes/raw/p1/assert.json` `569cce2a…` |
| 1b | compression ids | `post_compaction` fires; ids survive compaction | **PASS** (supplementary, see below) — 34 → 12 messages, `post_compaction` `kind=summarize`, 22 messages removed, `session_id` unchanged and `task_id` still equal to it on the next turn | `probes/raw/p1/compress_long/assert.json` `de9835e7…` |
| 2 | `pre_llm_call` replay | docs: ephemeral, nothing persisted | **FAIL (unchanged)** — sentinel stored in `api_content` (83 chars vs 30-char `content`), and a later process with injection disabled answered `PRESENT` with the sentinel at message indexes `[1,2,3]` | `probes/raw/p2/assert_storage.json` `74dfadd2…`, `turn2.txt` |
| 3 | context discovery | only the course policy loads in an isolated cwd; in-repo parent policy leaks | **PASS** (`isolated=[COURSE]`, `repo_course=[COURSE,REPO]`, `repo_root=[REPO]`, `outside=[]`, `ignore_rules=[]`); **remote BLOCKED** — no remote backend is configured on this host | `probes/raw/p3/assert.json` `421723e2…` |
| 4 | aux grading | fast, fail-closed, outage visible | **PASS with caveats** — p50 1.616 s / p95 3.486 s, all `json`; `timeout=0.001` → `APITimeoutError` after **3.47 s** (timeout is not a wall clock); missing pinned model silently ran `stepfun/step-3.7-flash:free` and returned `pass` in **9.84 s** | `probes/raw/p4/assert.json` `860ad0be…`, `p4_runtime_seam.json` `4e8d197a…` |
| 5 | tool → artifact → `MEDIA:` → renderer | seam parses; gateway does not deliver plugin media; Desktop render unproven | **PASS (seam)** — 70-byte artifact + text alternative, `extract_media` finds the plain-text tag, finds nothing in a JSON tool result, plugin tool not on the auto-append allowlist. **Desktop render BLOCKED** — no renderer contribution in the skeleton and no Electron window was driven; needs a live Desktop session, which this headless host does not provide | `probes/raw/p5/assert.json` `8a866ff1…`, `p5_media_seam.json` `c208040e…` |
| 6 | cron delivery | omitted → local; explicit target stored; duplicates duplicate | **PASS** (`local`, `local`, `telegram:999999999`, second `qa-omit`); jobs created paused and removed after inspection; DST arithmetic untested | `probes/raw/p6/assert.json` `1ce48ca7…`, `jobs.json` |
| 7 | `submit_attempt` authority | idempotent backend door; hook fail-open and mortal | **PASS** — first/duplicate/conflict/stale as specified; `pre_llm_call` raise → turn ran; 32 s sleep with 1 s budget → turn ran in **5 s**; hook **did not fire again** on the next turn; `cbprobe submit` still `committed` while bypassed | `probes/raw/p7/assert.json` `d8b1f9bc…`, `p7_hook_bypass.json` `e70b5a02…` |

**Compression segment now PASS, with its precondition named.** The operator gateway decision
(`t_6a32ffe9`) has landed on this host: `compression.in_place` is `true`, so the #44794
"session rotation did not occur" refusal is gone. The stock p1 transcript (8 messages) still
refuses — `Compression refused (summary would grow the conversation): 8 messages preserved`
(`probes/raw/p1/compress.txt`) — because `compression.protect_last_n=20` leaves almost nothing
compressible. `probes/p1b_compress_long.sh` therefore builds a 34–38 message session and asks
for `/compress`; the committed-script run compacted **34 → 12 messages**, fired
`post_compaction` once (`kind=summarize`, `before_tokens=16080`, `after_tokens=14558`,
`messages_removed=22`), kept `session_id`, and the next turn still had `task_id == session_id`
with a fresh `turn_id` (10/10 checks in `probes/raw/p1/compress_long/assert.json`). Across the
three executions of this procedure the numbers moved (34–38 messages, 22–26 removed) and the
verdict did not: `compress_long.txt`, `events_compress_long.jsonl`,
`events_after_compact.jsonl`.

**Still blocked, and why:** probe 5's Desktop render (no Electron window on this host; a
headless screenshot is not a render result) and probe 3's remote half (no remote backend
configured). Probe 2 stays FAIL: it is a host/doc mismatch, not a Coursebook defect — the
consequence, "treat injection as persistent; never inject secrets", is what the product
depends on.

## Verdict table

Baseline run 2026-11-06. Superseded by the 2026-11-08 re-run above, where probe 1's compression
segment moved to PASS and every other verdict held.

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
