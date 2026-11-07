# H-63R — live arbitrary-topic generation, executed on the real backend

Auditor: Sentinel (cbqa). Date: 2026-11-07. Source: `ea5f15d` on `wt/h63-live-arbitrary-r2`.
Isolated home: `/home/deseretsaint/.hermes/cbqa-h63-live-1794080841/home` (fresh; not the Japanese
demo, not the operator's profile). Provider calls: **live** `nous` via the host-owned
`agent.plugin_llm.PluginLlm`; research: **live** `web_search`/`web_extract` through
`coursebook.research.HermesToolSearch`. No credential was read by the harness and no external
message was sent.

## What was run

For each topic: `course.create` → `enrollment.create` → `jobs.create` (the exact sequence
`desktop/plugin.js::startLearnerPlan` sends), then the **real** `executor.pump_once` (the function
the agent tick calls) under a lease, with the host LLM, host search seam and a cross-model
validator bound through the same `bind_host_llm` / `bind_validator_llm` / `bind_research_seam`
functions `register(ctx)` uses. Job state was polled every 2 s and the wait bounded at 600 s.

| run | transport | goal | terminal state | elapsed | research | validator | verdict |
|---|---|---|---|---|---|---|---|
| `topic1-derailleur` | in-process dispatcher | How does a bicycle derailleur index through its gears? | `completed` | 270.3 s | `ok`, 2 queries, 5+ sources | independent (nous / deepseek-v4.1-flash) | **reject** (3 reasons) |
| `topic2-relative-minor` | in-process dispatcher | Find the relative minor on the circle of fifths | `completed` | 302.3 s | `degraded`, 3 sources, 1 fetch failure | independent | **reject** (4 reasons) |
| `topic3-cancel` | in-process dispatcher | Sharpen a kitchen knife safely with a whetstone | `completed_late` | 244.3 s | `degraded` | independent | reject; cancel honoured only after the running call |
| `topic4-http` | **live HTTP `cb.rpc`** | How does a bicycle derailleur index through its gears? | `completed` | 94.1 s | **`unavailable`** | **unidentified** (no validation call) | **reject** (1 deterministic rule) |

`topic4` was created over HTTP against the isolated `hermes serve --isolated` backend on
`127.0.0.1:44229`, then run by the process already ticking against that home. The agent-side pump
returned `finished: []` — it never got the job. That is the defect below.

## Verdicts

| claim | verdict | evidence |
|---|---|---|
| A non-demo live plan reaches a real terminal state inside the 10-minute bound | **PASS** | all four jobs terminal at 94–302 s; no job was left `running` |
| Live research seam produces fetched sources | **PASS (agent-side)** | `status=ok` (topic1), `degraded` with real fetched excerpts (topic2/3) |
| Independent cross-model validation runs | **PASS** | validator identity `nous / deepseek/deepseek-v4.1-flash`, generator `…-1017`; `independence=independent` |
| Cancellation reaches a terminal state | **PASS, with caveat** | `cancel_requested` at 8.2 s → `completed_late` at 244.3 s; the running provider call is not interrupted |
| A live arbitrary topic becomes an **approvable** plan | **FAIL** | 4/4 rejected; reasons below |
| The run through the real RPC path has the research seam enabled | **FAIL** | `topic4`: research `unavailable`, no validation call |

### Rejection reasons (verbatim, from `evidence.json`)

- topic1: negative evidence criteria that mark a true answer wrong (indexing left open; “no cable
  tension” claims), and `learner_outcome` truncated mid-word (`…do not establish,so`).
- topic2: goal over-promises a general skill while the one objective covers only C major; corrupted
  `parent.reading_level` (`Plain English, short sentences; chart-l批`); `evidence_note` truncated
  (`…excluded as a`); a self-ticked checklist cannot evidence comprehension.
- topic3: cancelled; no approvable artifact.
- topic4: `a one-off brief is not a parent-led lesson` (deterministic rule after two attempts).

## Defects

### D-H63-1 (P1) — the serve process runs the job tick without the host research seam

`job_1a348fd966c541bea02a270f4a591fb6` was created over the **live HTTP** transport. Within
seconds it was `running`, while the agent-side `executor.pump_once(limit=1)` returned
`finished=[]` at 0.0 s. The run recorded `research.status = "unavailable"` (“no source could be
fetched”) and `independence = "unidentified"` (the candidate broke a deterministic rule twice, so
validation never ran). The isolated backend on port 44229 is the only process pointed at this home
and therefore the one that claimed the job. This is the same failure class as the card's original
job: the process the Desktop talks to executes generation without `ctx.dispatch_tool`, so every job
created through the real RPC path gets **zero research support** even though a properly bound agent
tick grounds research. Fix belongs to the executor/job-tick owner: either the serve context must
not start `executor.start_tick`, or the tick must require both `ctx.llm` and a usable research seam
before claiming a job.

### D-H63-2 (P2) — free-prose fields are hard-truncated at JSON-schema `maxLength`

| field | schema cap | observed length | tail |
|---|---|---|---|
| `learner_outcome` (topic1) | 600 | **600** | `…do not establish,so` |
| `evidence_note` (topic2) | 400 | **400** | `…excluded as a` |
| `parent.reading_level` (topic2) | 40 | **40** (42 bytes) | `…chart-l批` |

The provider enforces `maxLength` by cutting the model output; the prompts ask for prose that
reaches the cap, so plans systematically carry mid-word / mid-codepoint artifacts. The independent
validator then correctly refuses them. Two of three fresh plans were rejected partly for this.

### D-H63-3 (P3) — cancel during a running provider call is not an immediate stop

`jobs.cancel` at 8.2 s moved the job to `cancel_requested`; it stayed there while the single plan
stage ran and then closed as `completed_late` at 244.3 s, having authored (and paid for) the whole
plan. This is the documented reconcile-don't-rerun behaviour, but UI copy must not promise an
immediate stop.

## Required fix before H-63 can be green

1. D-H63-1: keep the tick in the agent process, or bind/deny the research + validator seams in
   serve. Prove it by creating a job over HTTP and showing `research.status != "unavailable"` from
   an execution the Desktop backend performed.
2. D-H63-2: make prose length-aware (ask the model for a bounded length, retry on cap, or remove
   the hard `maxLength` truncation) and prove an arbitrary-topic plan reaches `draft`/approval.
3. Then the lesson stage + rendered Desktop lesson capture can be attempted; none was fabricated
   here because no live plan was approvable.

## Reproduce

```bash
# fresh isolated home (disposable)
BASE=~/.hermes/cbqa-h63-live-$(date +%s); mkdir -p "$BASE/home"
COURSEBOOK_TEST_HOME="$BASE/home" bash scripts/install-local.sh \
  --source /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_af57b886
# config.yaml: plugins.entries.coursebook.llm.{allow_model_override,allow_provider_override}=true,
#              allowed_*=["*"], settings.validator_{provider,model}=nous/deepseek/deepseek-v4.1-flash

P=~/.hermes/installs/4d8bf4040d63cdfa/environments/8f3bc04345f24c01aa16ba22c63df51d/venv/bin/python
export HERMES_DISABLE_LAZY_INSTALLS=1 HERMES_HOME="$BASE/home" \
  HERMES_AGENT_ROOT=~/.hermes/hermes-agent \
  COURSEBOOK_SOURCE=/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_af57b886 \
  H63_VALIDATOR_PROVIDER=nous H63_VALIDATOR_MODEL=deepseek/deepseek-v4.1-flash
"$P" audit/adversarial/h63-live-generation/worker.py --tag repro \
  --goal "How does a bicycle derailleur index through its gears?" --title "Bicycle derailleur" \
  --recipe one_off --scope single --subject-domain repair --depth working --max-seconds 600 \
  --result /tmp/h63-repro.json
```

`HERMES_DISABLE_LAZY_INSTALLS=1` is required in this container: without it the venv re-execs into the
dependency-free runtime interpreter and `ruamel` is missing. It only disables lazy installs; the
provider and search calls are still live.

## Files

- `worker.py` — the harness (real loader bindings, real dispatcher, real `pump_once`).
- `http_create.py` — create the same chain over the live HTTP `cb.rpc` transport.
- `build_evidence.py` — assembles `evidence.json` from the per-run captures.
- `evidence/topic*.json` — raw per-run capture (timeline, job view, plan, research ledger, usage).
- `evidence.json` — normalised packet and defect list.
- `shots/` — empty: no lesson page existed to capture; the plan was rejected in every run. The
  Desktop requirement is conditional on an approved plan and is not claimed here.
