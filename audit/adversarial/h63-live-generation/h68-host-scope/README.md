# H-68 live RPC-path evidence — copied from kanban, not a reproduction

**What this directory is.** Byte-for-byte copies of the four attachment files H-68
(`t_f178ba3d`, done 2026-11-07 14:25) left on the coursebook board. They are placed here
by H-166 (`t_cd419083`) so the live arbitrary-topic run is reachable from the tree instead
of only from `~/.hermes/kanban/boards/coursebook/attachments/t_f178ba3d/`.

| file | sha256 | what it records |
|---|---|---|
| `EVIDENCE.md` | `989f1439…` | H-68's own report: repro, root cause, host fix `c02e6e0180`, test counts, live acceptance, limits |
| `probe-fixed.json` | `69c004a2…` | post-fix probe worker: `web_search` ok (3 results), `web_extract` ok (1 document, 4523 chars), `get_provider_env(FIRECRAWL_API_KEY)` → `non_empty: false` (keyless route) |
| `research-run.json` | `26c349f0…` | research ledger `114a08e40b09c49a`: `status: "ok"`, 2 queries, 4 fetched sources, `failures: []` |
| `plan-job.json` | `28e21960…` | job `job_18e2916bd1684036b1ee0df26c8e950c`: `completed` at 21:18:22Z, created 21:15:37Z (**165 s**); plan `752bb7935176cbdc` at `draft`, `approved_at: null`, `generation_state: needs_review` |

**What this is not.** These are transcripts of one run, not a reproduction: nothing here
re-runs, and no gate in this repository reads them. `EVIDENCE.md` also cites
`audit/h68/create-h68.json` and `audit/h68/validation-records.json`, which were written under
the host-side rig and were **not** attached to the card — that absence is the point of the
"no validation record" half of the P0-7 basis, not an oversight in this copy.

**Host fix.** `EVIDENCE.md` names host commit `c02e6e0180` on
`~/.hermes/hermes-agent` branch `wt/h68-serve-secret-scope`. Verified 2026-11-08: that commit
exists in the host repo and is contained by **no** remote ref (`0` of `2842` refs under
`refs/remotes`), so it is a source backup, not a merged or pushed line. The host repository is
not this repository and is not vendored here.

**No secrets.** The four files contain key *names* (`FIRECRAWL_API_KEY`) and env-var names
(`HERMES_DASHBOARD_SESSION_TOKEN`) but no values; nothing was redacted.
