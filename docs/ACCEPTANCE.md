# ACCEPTANCE — adversarial matrix

Owner: Sentinel. Sources: `UX_SPEC.md` §16 proof suite, `PREBUILD_SPEC.md` §16 gates,
`AUDIT.md` acceptance expansion. Status vocabulary:

- **verified** — an executable probe or test records PASS in this repo today;
- **pending** — requires product code that does not exist in the skeleton yet;
- **blocked** — the runtime topology cannot exercise it here (reason given);
- **failing** — probe/reproduction currently fails (see `DEFECTS.md`).

Evidence lives in `probes/raw/`; probe scripts are `probes/p*.sh`. Owners: Atlas (contracts,
identity, runtime topology), Cinder (learning kernel, grader, DB, jobs), Sable (Desktop
route/panes/media renderer), Sentinel (verification).

## A. Runtime assumptions (probes)

| Item | Probe | Status | Owner | Evidence |
|---|---|---|---|---|
| Runtime/stored ids across create/first turn/resume/tool | p1 | verified | Cinder | `raw/p1/assert.json` |
| Ids across compression | p1 | blocked | Atlas | #44794 warning, `raw/p1/compress.txt` |
| `pre_llm_call` injection replay semantics | p2 | **failing** (CB-QA-01) | Atlas/Cinder | `raw/p2/assert_storage.json` |
| Isolated cwd policy discovery | p3 | verified | Cinder | `raw/p3/assert.json` |
| Course inside a git repo | p3 | **failing constraint** (CB-QA-05) | Cinder | `raw/p3/repo_course.jsonl` |
| Remote Desktop/backend topology | p3 | blocked (no remote backend) | Atlas | — |
| Aux grading latency / invalid JSON / timeout / outage | p4 | verified + caveats (CB-QA-03/04) | Cinder | `raw/p4/assert.json` |
| `jsonschema` missing must fail closed | p4 seam | verified (with package) / hazard recorded | Cinder | `raw/p4/p4_runtime_seam.json` |
| Tool → artifact → `MEDIA:` → renderer | p5 | verified at seam; render blocked | Sable | `raw/p5/p5_media_seam.json` |
| Cron explicit vs omitted delivery | p6 | verified (DST untested) | Cinder/Atlas | `raw/p6/jobs.json` |
| `submit_attempt` authoritative without hook | p7 | verified | Cinder | `raw/p7/assert.json` |
| Hook exception/timeout fail-open | p7 | verified (CB-QA-02) | Atlas/Cinder | `p7_hook_bypass.json` |

## B. UX proof suite (`UX_SPEC.md` §16)

| # | Proof | Status | Depends on |
|---|---|---|---|
| 1 | Fresh profile → sidebar → bundled preview → import → lesson | pending | Sable + Cinder packs |
| 2 | Backend disabled → enable → brief preserved | pending | Sable |
| 3 | New goal → cancel generation → reattach → approve plan | pending | Cinder jobs |
| 4 | Chat answer and pane answer race → one attempt | pending | Cinder `submit_attempt` |
| 5 | Wrong answer → alternate representation → clarification not a retry | pending | Cinder |
| 6 | Grader timeout → needs_retry → override recorded | pending (runtime path verified in p4/p7) | Cinder |
| 7 | Hide/reopen/split pane during attempt → no lost/duplicate submit | pending | Sable + Cinder |
| 8 | Restart at every attempt state → same objective/pending | pending; compression blocked | Cinder/Atlas |
| 9 | Parent edit after approval → reapproval | pending | Cinder parent |
| 10 | Invalid/malicious pack → precise error, no residue | pending | Cinder packs |
| 11 | Offline lesson → cached content; research explains pause | pending | Cinder/Sable |
| 12 | Source stale → impact banner; evidence retained | pending | Cinder |
| 13 | Reimport same pack → resume vs fresh | pending | Cinder packs |
| 14 | Course/chat/pack deletion distinct & recoverable | pending | Cinder |
| 15 | Keyboard-only, text-only, reduced motion, 200 %, narrow | pending | Sable |
| 16 | 50+ objectives / long JP text / many sources stay usable | pending | Sable |
| 17 | Save moment → tag/search → exact section → new run | pending | Cinder + Sable |
| 18 | Past quiz read-only → new version keeps both | pending | Cinder |
| 19 | Jump early/late sections → context-bound runs | pending | Cinder identity |

## C. PREBUILD §16 gates (condensed)

| Gate | Status | Probe / owner |
|---|---|---|
| Duplicate submits/two windows commit once | pending; idempotency seam verified | p7 → Cinder |
| Same key+payload returns original; mismatch/stale conflict | **verified at command level** | p7 |
| Late callback cannot change newer revision | pending (needs revisions in product) | Cinder |
| Restart after every state restores state | pending; compression blocked | Cinder/Atlas |
| Rename/branch/edit/delete/compress/repeat explicit | blocked/pending | Cinder |
| Unrelated sessions get no Coursebook context | pending (hook must scope by binding) | Cinder |
| Wrong/irrelevant answers do not pass | pending | Cinder |
| Flawed question/key/rubric fails closed | verified mechanism; product pending | p4 → Cinder |
| Answer-shown/hint/override evidence classes | pending | Cinder |
| Physical completion self-reported | pending | Cinder |
| Pack/web prompt injection cannot change policy | pending; p2 shows injected text durability | Cinder/Atlas |
| Traversal/bombs/links/SVG/remote images/MIME reject | pending | Cinder packs |
| Offline cached content works; staleness visible | pending | Cinder |
| Rights/ND enforced; exports leak nothing | pending | Cinder |
| Jobs cancel/recover without duplicate artifacts | pending | Cinder |
| Keyboard/text/reduced-motion/no-media complete | pending; p5 proves text fallback data exists | Sable |
| Local/remote explicit, not silently wrong | **verified local**; remote blocked | p3/p5 |
| Fresh install/enable/restart/revoke/uninstall | pending; hot-reload defect CB-QA-07 | Atlas |
| Demo below 90 s, no fake live research | pending (no demo recorded) | Atlas/Sable |
| Catalog PR pinned + form on time | pending | Atlas |

## D. Gate conditions for sign-off

1. No acceptance item may be marked verified from a self-report; each row needs an artifact
   path or a test name.
2. CB-QA-01…03 must be closed or explicitly accepted by Atlas before the grader ships.
3. Compression/restart (CB-QA-06) must be re-run on a restarted gateway before sign-off.
4. Remote topology stays `TOPOLOGY_UNSUPPORTED` until p3/p5 remote halves pass.
