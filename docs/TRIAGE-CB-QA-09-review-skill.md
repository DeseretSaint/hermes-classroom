# Triage: review-lane worker dies when the assignee disables `sdlc-review`

Card: `t_0fc8035f` (filed by Sentinel from `t_edfe245a`). Triage by Atlas, 2026-11-06.
Verdicts on `t_80b6b5cd` are untouched; its evidence is unmodified.

## Verdict in one paragraph

Real defect, real impact, wrong owner for the hackathon build. The failure is in the **Hermes
host**, not in the Coursebook plugin: a review-lane card assigned to a profile that lists
`sdlc-review` under `skills.disabled` spawns a managed worker that raises before its first model
turn and exits 1. Severity is **High for board operation, out of scope for the plugin artifact**
(the plugin ships no code on this path, and the environment fix already restores the lanes). It is
routed as an **upstream defect report** against `NousResearch/hermes-agent`, with the environment
workaround as the release-gate condition. It is not a plugin release blocker and no specialist
work-package changes because of it.

## Evidence (all re-verified on this host, not taken from the report)

Host under test: `/home/deseretsaint/.hermes/hermes-agent` at `2bd378ed1b` (branch `HEAD`,
209 commits behind `origin/HEAD` `90d6b98fd8`).

1. **The crash path exists as described.**
   - `gateway/session_kanban.py:45-48` — on a review-lane run the admission policy appends
     `sdlc-review` to the task's skills unconditionally.
   - `gateway/session_kanban.py:386-388` — `build_preloaded_skills_prompt(...)` returns
     `missing` and no `loaded`, so the turn runner raises `ValueError('kanban_skills_unavailable')`
     before `agent.run_conversation`.
   - `agent/skill_commands.py:953-980` — that helper hard-codes `disabled_as_missing=True`, so an
     **operator-disabled** skill is indistinguishable from a **missing** one at the call site.
   - `hermes_cli/kanban_db_dispatch.py:2146-2149` — the dispatcher applies the same unconditional
     force-load when it claims a review card.
2. **The failure happened eight times, with tracebacks, not just exit codes.**
   `/home/deseretsaint/.hermes/profiles/{cbqa,atlas,harbor}/logs/managed-worker.log` each contain
   `session_kanban.py", line 388 ... ValueError: kanban_skills_unavailable` for pids
   1289899/1292020/1415911/1418563 (cbqa), 1152139/1154487 (atlas), 1105765/1109647 (harbor).
3. **The board DB agrees.** `task_runs` 8, 9 (`t_3eb83beb`/harbor), 12, 13
   (`t_cd2a83f7`/atlas), 29, 30, 39, 40 (`t_80b6b5cd`/cbqa) are `status=crashed`,
   `outcome=crashed`, error `pid N exited with code 1 [managed worker lost...]`; each run's
   `worker_result` has `exit_code: 1` and empty `last_output` (died before the first model turn).
4. **"Owner refused" is a mislabel.** Every one of those eight runs carries exactly one
   `owner_admitted` event and one `worker_bound` event: the owner admitted the request and the
   worker was bound, then died in-process. The user-facing string is
   `hermes_cli/kanban_worker_client.py:188-190`, which prints
   `Kanban owner refused: {exc}` for **any** `KeyError`/`ValueError`/`OSError` raised anywhere in
   the submit path. (The card cited line 149; the live file is 189 — line drift only.)
5. **Untested assumption upstream.** No test in `tests/` asserts behaviour for a force-loaded
   review skill that the assignee has disabled; `grep -rn kanban_skills_unavailable tests/`
   returns nothing.
6. **Still broken upstream.** `git show origin/HEAD:gateway/session_kanban.py` contains the same
   unguarded force-load (`:45-48`) and the same raise (`:385-388`). This is not a stale local
   checkout.
7. **Only one profile is still exposed.** `grep -n sdlc-review ~/.hermes/profiles/*/config.yaml`
   matches exactly one file: `profiles/sentinel/config.yaml:121`.
8. **Consequence of the loop.** No `kanban` block exists in the operating profiles' config, so
   `failure_limit` is the default 2 (`hermes_cli/config_defaults.py`,
   `review_dispatch: True`). Each affected card burned two attempts and auto-blocked; all four
   recovered to `done` only after Sentinel's config remediation.

## Ask 1 — severity and ownership

| Question | Ruling |
|---|---|
| Is it a Coursebook defect? | No. No file under the plugin, no contract, no hook, no schema is involved. |
| Is it in hackathon build scope? | No build work. It is an **environment/release-gate** item and an **upstream report**. |
| Severity for board operation | **High** — silent crash loop, misleading diagnostics, burns `failure_limit`, blocks the automated review lane for any affected profile. |
| Severity for the shipped plugin | **None** — the artifact does not contain the failing code. |
| Owner | Upstream `NousResearch/hermes-agent` (gateway/kanban). Local fork `Projects/hermes-fork` is older and carries the same code; patching it would not fix the running host, which is `~/.hermes/hermes-agent`. |

Release-gate condition (operator, before demo): no profile that can receive a review card may list
`sdlc-review` under `skills.disabled`, **or** `kanban.review_dispatch` must be false and every
review done by hand. Verified today: only `sentinel` violates the first condition.

## Ask 2 — fix direction

Ruling: **gate, then diagnose. Do not degrade a force-loaded review skill to a logged omission as
the primary fix.**

`sdlc-review` is not decoration; it carries the approve/`request changes` discipline and the
"never complete your own review" rule. A review-lane worker that silently loses it still has the
whole `kanban` toolset, so it could close a card it was supposed to review. That is an integrity
regression worse than a crash. Degrading is only correct where no review lane should exist at all
(`review_dispatch: false`), and in that case the dispatcher should not claim the card.

Ordered fix set (for the upstream report):

1. **Primary — refuse to spawn, with a reason.** Before the force-load at
   `kanban_db_dispatch.py:2146-2149` and `session_kanban.py:45-48`, resolve whether the *assignee*
   can load `sdlc-review` (i.e. consult that profile's `skills.disabled`). If it cannot: do not
   spawn; record a typed failure such as `review_skill_disabled:<profile>` and block the card once,
   naming the profile and both remedies (enable the skill, or set `kanban.review_dispatch: false`).
   One clear block instead of a crash loop that eats `failure_limit`.
2. **Secondary — make the error say what happened.** `build_preloaded_skills_prompt` already
   separates `disabled` from `missing` when `disabled_as_missing=False`; the kanban turn runner
   should surface that distinction (or raise a typed error carrying it). `kanban_skills_unavailable`
   is a config-level condition being reported as an execution crash.
3. **Diagnostics — stop calling it a refusal.** `kanban_worker_client.py:188-190` should print
   "owner refused" only for refusal-shaped errors (no admission, stale claim, profile mismatch);
   every other exception should print its own message. As long as this branch stays this wide, a
   local config error is reported to the operator as a permission problem.

Rejected as a fix: "catch and continue without the review skill". Also rejected: blanket
`review_dispatch: false` as anything other than a demo-day workaround, because it removes the
review lane rather than repairing it.

Optional local mitigation, if the operator wants the fork patched before the demo: implement (2)
and (3) only, as a diagnostic improvement, and leave (1) as the upstream structural fix. A local
patch is not required for the demo once the config gate above is satisfied.

## Ask 3 — `sentinel` and `sdlc-review`

**Yes.** `sdlc-review` should be removed from `skills.disabled` in
`profiles/sentinel/config.yaml:121`. Sentinel receives review cards; a reviewer profile that cannot
load the review protocol is misconfigured, not hardened.

- This requires the operator: Sentinel cannot self-edit that file, and Atlas will not edit another
  profile's config without direction. I did **not** modify it.
- The report's claim that Sentinel's config is "protected from agent self-edit" is **unverified**.
  The file is mode `0600`, owned by the same user as the other profiles, with no `chattr` flag; I
  found no protection mechanism and did not test an agent's write attempt. Treat the constraint as
  a convention (agents should not edit it), not an enforced barrier.
- Interim, controlled by Atlas: no review lane is routed to `sentinel` until the entry is removed.
  Reviewer routing is mine, so this holds without touching the config.

## What this card does not do

- No plugin source, contract, test or catalog change.
- No row added to `DEFECTS.md`: that ledger is Sentinel's artifact and is already merged; this
  card's disposition lives here so a later editor does not carry a merge conflict over it. If the
  release record needs the row, it is `CB-QA-09 | Environment (out of plugin scope) | Upstream
  Hermes host | review lane crashes when the assignee disables sdlc-review`, pointing at this file.
- No edit to `t_80b6b5cd` or its evidence, and no verdict change anywhere.
- No upstream publish: the report draft in `docs/UPSTREAM-REPORT-kanban-review-skill.md` is
  operator-gated.
