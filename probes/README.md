# Coursebook runtime probes — evidence pack

Owner: Sentinel (adversarial QA). Everything here is test-only; it never touches an
operator course and never sends an external message.

## What is here

| Path | Purpose |
|---|---|
| `setup.sh` | Creates the dedicated `cbqa` profile, an isolated test root, AGENTS fixtures, and links both the Coursebook skeleton and the probe plugin into that profile. |
| `p1_ids.sh` … `p7_authority.sh` | One script per probe from `PREBUILD_SPEC.md` §14. Each writes raw evidence under `raw/` and prints `RESULT probe=<name> PASS|FAIL|BLOCKED <detail>`. |
| `run_all.sh` | Runs all seven and writes `raw/RUN.log` + `raw/VERDICTS.txt`. |
| `plugin/` | `cb-probe`: a Hermes plugin that logs hook payloads and registers test tools (ids, media artifact, structured grading, idempotent submit). Control file: `<profile>/test-root/control.json`. |
| `scripts/` | Assertions and seam checks (runtime validation, media extraction, DB inspection, log summaries). |

## Run it

```bash
bash probes/setup.sh          # idempotent; creates/refreshes the cbqa profile
bash probes/run_all.sh        # ~3 minutes, several real aux-LLM calls
```

The probes use the live Hermes gateway served for the `cbqa` profile. Plugin code runs in
the **gateway process**, so `os.getcwd()`/`os.environ` there describe the gateway, not the
session — the probe plugin resolves `get_hermes_home()` and `resolve_agent_cwd()` instead,
and the findings below depend on that distinction.

## Verdicts (see `../PROBES.md` for the report and `../DEFECTS.md` for defects)

```
p1  PASS      ids across create/first turn/resume/tool context
p1  BLOCKED   compression ids (gateway /compress cannot rotate or compact in place)
p2  FAIL      pre_llm_call injection is persisted in api_content and replayed
p3  PASS      isolated/outside/ignore-rules clean; in-repo parent policy leaks (constraint)
p4  PASS      grading latency + fail-closed validation; outage substitutes a different model
p5  PASS      artifact + text fallback + MEDIA seam; Desktop render is BLOCKED (no renderer yet)
p6  PASS      omitted delivery = local; explicit target stored; duplicate names duplicate
p7  PASS      submit_attempt authoritative with no hook; hook fails open and a timed-out hook dies
```

## Non-goals / limits

- No Electron window is driven, so `TOOL_MEDIA_RENDERER_AREA` rendering is verified at the
  host contract seam only (`p5` reports BLOCKED for the render step).
- No remote backend is configured; the remote half of probe 3 and probe 5 is BLOCKED.
- The operator's gateway is shared and long-lived. Where a probe needs a restart
  (compression/rotation, hook-timeout config reload) it says so instead of restarting it.
