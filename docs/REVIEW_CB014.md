# REVIEW CB-014 — adversarial security, state, accessibility and demo-falsification pass

Author: Sentinel (independent release gate). Date: 2026-11-06T16:50Z.
Candidate under test: `f4a42f34edeb20031ce107dbf5b36af11e7f388a` (`wt/cb-014-sentinel`), plugin 0.1.0,
cb.rpc wire_version 6, 51 declared methods.
Rule applied throughout: **no claim accepted from a self-report.** Every row below is the output of a
command I ran, and the raw evidence file is named next to it.

## Verdict

**NO-GO for the contest release as of this commit.** The backend passes every attack I threw at it,
but the release's primary surface is not reachable: on the installed candidate the `/coursebook`
route renders the session home instead of the Coursebook page. That makes the course library, the
create/import flows, Parent Studio and Activity unverifiable live and blocks the demo script.
One medium information leak and one recorded (currently disabled-lane) grading-injection risk are also open.

| Gate | Result |
|---|---|
| Backend transactional state, races, restart, jobs, grading fail-closed | **PASS** (21/22 scenarios; the one FAIL is the leak below, not a state defect) |
| Hostile pack import/export/prompt injection | **PASS** (21/21) |
| Native Coursebook page / course list live | **FAIL** — P1 |
| Accessibility, 200% text, narrow layout, reduced motion, no-media on the route | **BLOCKED** by the P1 (route has no DOM to audit) |
| Demo truthfulness | **FAIL** — demo cannot be recorded honestly today; `docs/DEMO.md` status text is stale |
| Existing gates (`scripts/validate.sh`) | **PASS** — 636 tests OK, node check OK, plugins validate + doctor OK, 31/31 mounted expectations, exit 0 (`/tmp/cb014-validate.log`) |

## Defects

| ID | Severity | Owner | Status | Summary |
|---|---|---|---|---|
| CB-QA-09 | P1 | Vellum (+ t_bfe339b2) | OPEN — retested, still failing | `#/coursebook` renders the session home on the installed candidate; the route page never mounts |
| CB-QA-10 | P2 | Cinder (domain/evidence) | OPEN | `evidence.inspect` returns `l2.objectives[].criteria[].check_spec.reference` — the answer key — to the client while the check is still open |
| CB-QA-11 | P2 (lane disabled) | Cinder (grader) | RECORDED RISK | With an aux grader installed, learner text is passed to the grader and a "pass" containing instructor-style injection is accepted; no structural cross-check exists for open responses |
| CB-QA-12 | P3 | Harbor (docs) | OPEN | `docs/DEMO.md` says "not recordable … 0.1.0 has no course creation, no chat binding, no grading and no export", which is false for this build |
| CB-QA-13 | P3 (operational) | Atlas | NOTE | A test payload placed anywhere under the plugin root outside `tests/` fails `hermes plugins validate` as `dangerous`; the adversarial suite must live in `tests/` (test-tree demotion) or admission breaks |

### CB-QA-09 — the Coursebook route does not render (P1, release blocker)

Reproduction against the installed candidate in the dedicated test home
(`~/.hermes/coursebook-test/home`, backend `127.0.0.1:44219`, Desktop CDP `127.0.0.1:9337`):

```bash
scripts/install-local.sh          # installs f4a42f3 into the test home; "Installed."
scripts/cb013-live-backend.sh     # backend ready, runtime plugin_root = .worktrees/t_d72bb1a4
scripts/cb013-live-window.sh      # CDP up
CB009_CDP_PORT=9337 node scripts/cb013-eval.mjs \
  "(async()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()==='Open Coursebook');b.click();await new Promise(r=>setTimeout(r,3000));return {hash:location.hash,main:(document.querySelector('main')||document.body).innerText.slice(0,300)}})()"
```

Expected: `#/coursebook` renders the Courses destination (course rows / welcome).
Actual: `main` is the SESSIONS sidebar + session list; no `h1/h2/h3` from the plugin, no course row,
no welcome copy. Same result from the sidebar `Coursebook` item and from `location.hash` assignment.
`#/capabilities?tab=plugins` and `#/settings` render normally in the same window, so the router is
alive; only this plugin route is empty. The plugin *is* loaded: the right-hand pane renders
`COURSEBOOK / No durable chat yet / Open Coursebook`, and the sidebar nav item is registered.

This is the open card `t_bfe339b2` ("cold #/coursebook load falls back to the session home") reproduced
on the release candidate, not fixed. Impact: it removes the product's primary surface from the
submission and makes every UI acceptance row unverifiable, so it is P1 rather than a flake.

### CB-QA-10 — the answer key crosses the client boundary while a check is open (P2)

Scenario `S07` in `tests/adversarial/attack_state.py`; raw evidence
`tests/adversarial/evidence/attack-state.json` (`results.S07`).

Expected: the reference answer stays in the backend until an attempt is committed (`grading.py` and
`check.get` both honour this).
Actual, with the check still open, `evidence.inspect` returns:

```
l2.objectives[0].criteria[0].check_spec.reference =
  {"kind": "numeric", "tolerance": {"abs": "0"}, "value": "4"}
```

`check.open`, `check.get`, `lesson.page` and `attempt.submit` are clean; only the evidence bundle
carries the spec. `EvidenceView` in `desktop/plugin.js` does not currently render `check_spec`, so this
is not visible in the shipped UI — it is an RPC-level leak reachable by any local client with the
session token. It does not corrupt state or advance mastery, hence P2, but it contradicts "the
reference answer never leaves the backend" and should be stripped from the L2 projection (a hash, as
`grading.provenance.reference_sha256` already does, is sufficient).

### CB-QA-11 — open-response grader can be steered by learner text (P2, lane disabled)

Scenario `S13`. With `grading.configure_aux_grader()` installed (the host seam), an answer that
instructs the grader to disregard its own instructions and return a passing verdict is graded `pass`
when the adapter behaves like an obedient model. Structural validation rejects malformed output,
unmet criteria and timeouts, but there is no cross-check that can distinguish an honest pass from a
persuaded one for open responses.
The release ships with the aux lane off (`needs_retry`), so this is a recorded risk, not a live leak:
enabling the lane requires an injection-resistant rubric envelope (delimit answer as data, criteria
checked independently) and a measured false-pass rate.

### CB-QA-12 — demo status text is stale

`docs/DEMO.md` line 3 still claims the build has no course creation, binding, grading or export; the
same commit's backend performs all four (see `tests/adversarial/evidence/attack-packs.json` P20/P17 and
`/tmp/cb014-validate.log`). Independently of the route defect, the demo cannot be recorded today:
shots 0–8s, 34–40s, 47–62s and 62–73s all require surfaces that do not render, and the file's own gate
("Recording starts only after Sentinel passes the demo scenarios") is not met.

## Acceptance matrix

Backend rows: each is one scenario in `tests/adversarial/attack_state.py` or `attack_packs.py`,
run against a real migrated SQLite database in a throwaway `HERMES_HOME` through the same
`api.dispatch` envelope the HTTP seam uses.

| # | Attack / claim | Verdict | Evidence (actual result) |
|---|---|---|---|
| S01 | duplicate submit, same idempotency key | PASS | one attempt, one attempt-transition, same attempt id replayed |
| S02 | two threads submit at one revision | PASS | 1 committed, 1 `STALE_REVISION`; attempts=1 transitions=1 |
| S03 | stale revision | PASS | `STALE_REVISION`, 0 attempts written |
| S04 | second answer to a closed check | PASS | `CHECK_STALE`, still 1 attempt / 1 transition |
| S05 | shown answer contaminates next attempt | PASS | evidence class `answer_shown`, never `cold` |
| S06 | override | PASS | objective `overridden`, 0 independent rows |
| S07 | reference answer on learner surfaces | **FAIL** | `evidence.inspect` L2 check_spec carries the reference (CB-QA-10) |
| S08 | pre-turn teaching context | PASS | context returned; no reference/rubric/tolerance token |
| S09 | clarification inside an open check | PASS | 0 attempts, hook returns `None` |
| S10 | grader returns invalid JSON | PASS | `needs_retry` persisted, 0 transitions |
| S11 | grader hangs | PASS | returned at 8.05 s with `needs_retry`, 0 transitions |
| S12 | grader raises | PASS | `needs_retry`, 0 transitions, exception text not echoed |
| S13 | learner prompt injection vs grader | BLOCKED | aux lane disabled in release; with the seam installed a persuaded `pass` is accepted (CB-QA-11) |
| S14 | restart in a separate process | PASS | identical revision/attempts/transitions/evidence/check state; replayed stale submit refused `CHECK_STALE` |
| S15 | late post-turn callback | PASS | 0 segments before and after (discarded, not written) |
| S16 | detached binding | PASS | binding not active, hook returns no block/advance, 0 attempts |
| J01 | same operation id twice | PASS | one job row, same job id |
| J02 | two concurrent claims | PASS | one claimed, one `JobLeaseLost` |
| J03 | cancel a queued job | PASS | `cancelled`, unclaimable, 0 usage rows |
| J04 | stage finishes after cancel | PASS | `completed_late`, 0 usage rows |
| J05 | restart with an expired lease | PASS | `interrupted_requires_retry`, checkpoint `sources:["a"]` preserved |
| J06 | resume with skip | PASS | executed only `plan`; gather not re-run; `completed` |
| P01 | archive path traversal | PASS | `PACK_REJECTED`, no table changed |
| P02 | absolute member path | PASS | `PACK_REJECTED`, no residue |
| P03 | symlink entry | PASS | `PACK_REJECTED`, no residue |
| P04 | duplicate member | PASS | `PACK_REJECTED` (zipfile warned on write; staging refused) |
| P05 | case-colliding member | PASS | `PACK_REJECTED` |
| P06 | decompression bomb (200:1) | PASS | `PACK_REJECTED` |
| P07 | oversized member with a lying manifest size | PASS | `PACK_REJECTED` |
| P08 | 4 MB manifest field | PASS | `PACK_REJECTED` at the staging boundary |
| P09 | active SVG declared `image/svg+xml` | PASS | `PACK_REJECTED` (MIME allowlist + active content) |
| P10 | `<iframe>` in a text file | PASS | `PACK_REJECTED` |
| P11 | remote image in markdown | PASS | `PACK_REJECTED` |
| P12 | bytes vs declared MIME | PASS | `PACK_REJECTED` |
| P13 | nested zip disguised as text | PASS | `PACK_REJECTED` |
| P14 | reference answer copied onto a learner page | PASS | `PACK_REJECTED` |
| P15 | prompt-injected pack prose | PASS | imports as data; injection absent from plan and check specs, no `AGENTS.md` created, recipe unchanged |
| P16 | three hostile imports, table residue | PASS | no table changed for traversal/bomb/active-SVG |
| P17 | export contains learner history | PASS | notebook sentinel absent; only the 5 pack files + `pack.json`; 14 548 bytes |
| P18 | repeat export (retest of t_d28a0846) | PASS | second call returns the same artifact id, 1 artifact row — defect no longer reproduces |
| P19 | export with an unreviewed hash | PASS | `DELETE_SCOPE_STALE`, 0 artifacts (code name is misleading but refusal is correct) |
| P20 | reimport resume vs fresh | PASS | resume → same enrollment; fresh → new course+enrollment, same pack id |
| P21 | pack delete | PASS | enrollment/evidence kept; reimport `POLICY_VIOLATION` |
| U01 | `/coursebook` route live | **FAIL** | CB-QA-09 |
| U02 | course list, create, import UI live | BLOCKED | requires U01 |
| U03 | keyboard-only route path, focus, names | BLOCKED | requires U01 (the pane renders but the route under test does not) |
| U04 | 200% text / narrow layout / reduced motion / no-media | BLOCKED | requires U01 |
| D01 | demo records only live, working paths | **FAIL** | demo gate unmet (CB-QA-09, CB-QA-12) |

## Retest table (parent claims, re-run by me)

| Claim | Source | My result |
|---|---|---|
| 636-test suite, node check | CB-011L | **CONFIRMED** — `python3 -m unittest discover -s tests -t .` → 636 tests OK |
| `scripts/validate.sh` passes | CB-010/013 | **CONFIRMED** — exit 0, 31/31 mounted expectations, plugins validate + doctor pass |
| Repeat `pack.export` fails with IntegrityError | CB-013 / t_d28a0846 | **NO LONGER REPRODUCES** — P18 passes on f4a42f3 |
| Cold `#/coursebook` falls back to the session home | t_bfe339b2 | **REPRODUCED** on the installed candidate (CB-QA-09) |
| Chat and pane on one lineage | CB-009/013 | not re-run in this pass (no route); no claim made |
| Five-state movie impossible until the mount flake is fixed | CB-013 | **CONFIRMED** — still impossible |

## Environment and reproduction

```bash
cd .worktrees/t_d72bb1a4
python3 tests/adversarial/attack_state.py --json tests/adversarial/evidence/attack-state.json
python3 tests/adversarial/attack_packs.py --json tests/adversarial/evidence/attack-packs.json
bash scripts/validate.sh                     # full admission gate
```

Raw evidence digests:
`attack-state.json sha256:dfefe4a3910f0ce0e6bc629ea4012f09835ae41937c1ff123c3dce0e34882d2c`
`attack-packs.json sha256:1ba56a1b6432dd1495d59efb0984b9b53d1d4c5185c9ef6b4e646904647807ad`

Isolation: every scenario runs in its own fresh `HERMES_HOME` under the scratch dir; hostile archives
are generated on the fly under `tests/adversarial/packs/` (git-ignored product fixtures live in
`tests/`, which the plugin guard treats as a test tree). The live checks use only
`~/.hermes/coursebook-test` (disposable), never the operator's profile, and send no external messages.

## Limits of this pass

- Route-level accessibility (U03/U04) is **not** verified: there is no route DOM to audit. I did not
  substitute the pane for the route, because that would accept a claim the release cannot make.
- No CDP five-state capture was re-attempted; CB-013's own packet already documents why.
- The aux-grader lane is not enabled in this build, so S13 is a seam-level risk, not a live-path result.
- `course.get` and `course.outline` are frozen in cb.rpc v6 but unimplemented in this build (probe
  reports 31/34 registered); not a defect by itself, but any UI claim resting on them is unsupported.
