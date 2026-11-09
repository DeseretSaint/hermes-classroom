# Release evidence — what is measured, on which commit, and what is branch-only

Status: the H-203 truth pass, re-derived on the settled `master`
`ab6dc7e3e769dcfa8c8ce5bb2b9425dffb3de815` (the H-209 tree: H-208's H-183/H-189/H-192c/H-199
integration with H-206 and the H-182/D1-D3 renderer work, the H-182/D8 residual learner copy, the
H-182/D6 reaper/pump store scope, the validator-reject fix, and the private test `node_modules`
isolation). Every number below was produced by a command in this pass on that commit unless a row
names another commit. Machine-readable copy: `docs/release-evidence.json`, checked against the
documents by `python3 scripts/check-docs-truth.py`.

**This is not a green release.** The suite passes, but no demo is recorded, no license exists, no
live Desktop window has driven this exact commit, and the operator publication gate in
`docs/SUBMISSION.md` §0 is closed. No tag, catalog pull request or announcement was made.

## Measured on `ab6dc7e`

| Fact | Value | Command |
| --- | --- | --- |
| Suite | `Ran 2724 tests in 533.270s`, `OK` | `python3 -m unittest discover -s tests -t .` |
| `cb.rpc` | v20, 73 declared methods | `contracts/rpc.v20.json` (`coursebook/contracts.py:51` `WIRE_CONTRACT_VERSION = 20`) |
| Handlers | 73, asserted by the registry; `METHOD_HANDLERS` after importing every registering module | `coursebook/api.py`, registry test in the suite |
| `cb.db` | v12, `DB_SCHEMA_VERSION = 12`, migrations `0001`-`0012` | `coursebook/db.py:230`, `contracts/db.v12.json` |
| Shipped module | `desktop/plugin.js` sha256 `cd862140f0f03783f098326017db5225bb58b400e3595b321200480aa865c516` | `sha256sum desktop/plugin.js` |
| M4 audit | 62 frames, 15/15 claims PASS, 2,120 measured text nodes over 56 non-forced frames, worst authored contrast 5.93:1, 0 unnamed of 298 AX controls, 0 px overflow | `python3 scripts/m4v-audit.py` → `audit/visual/m4-visual/audit.json` |
| Adversarial state matrix | `SUMMARY total=23 fail=0 pass=23`; S13 BLOCKED because the auxiliary grader lane is disabled in this release | `python3 tests/adversarial/attack_state.py` |

The `audit.json` carries `plugin_sha256` equal to the shipped module's hash, which is what makes the
M4 row a claim about this commit rather than a stale pin. Regenerating the audit on this tree
(`python3 scripts/m4v-audit.py`) rewrote only `generated_at` and the recorded branch name — every
measurement and every committed screenshot was reproduced unchanged, which is the evidence that the
`cd862140` pin is the module the numbers describe.

Two measurements moved on the settled tree and are recorded as measured rather than carried forward:
the text-node count is **2,120** over the 56 non-forced frames (the H-183/H-189 learner-copy sweep and
the H-182/D8 objective copy reduced painted prose on those surfaces), and `C-08` now measures **0**
animated nodes in the four reduced-motion frames against **70** in the full-motion frames (H-152's
transitions are real, and the preference suppresses them). The AX control count (298 over the 32
frames with an accessibility tree), the worst authored contrast (5.93:1), and the overflow/clipping
counts (0) are unchanged. A prior record quoting 2,416 text nodes describes the `eed7dc7` slice, not
this tree.

## Reproducibility

`python3 scripts/m4v-repro-check.py` runs the whole audit twice in isolated scratch/out trees (separate
render pass, browser and screenshots) and fails on any difference except `generated_at`. The
reproducibility result is recorded in `docs/M4-VISUAL-MEDIA-AUDIT.md` and in `m4_repro` in
`docs/release-evidence.json`, pinned to the module it was run at. A reproducibility result is only a
claim about the module its `plugin_sha256` line names.

## What this pass did not measure

- No live Desktop window and no mounted backend trace on `ab6dc7e`; `scripts/validate.sh` step 5 was
  not run here (it needs a mounted backend and an isolated home).
- `bash scripts/validate-plugin.sh` (the export admission gate) **was** re-run here on the merged
  commit: 4/4 checks PASS on a `git archive` export of 2742 files (admission and security scan,
  `node --check`, 26 desktop contract tests, `hermes plugins doctor`).
- No provider-spend generation, no demo capture, no recording.
- The adversarial matrix was re-run here and is green (23/23 PASS, S13 BLOCKED by design).
- The catalog entry was not re-validated in this pass; the last recorded validation is the H-193
  record. It is a docs pass, and the catalog pin is untouched.

## Keeping this honest

`python3 scripts/check-docs-truth.py` fails when: the recorded plugin hash is not the hash of
`desktop/plugin.js` at the recorded commit; the recorded RPC method count or schema version disagrees
with the contract and `coursebook/db.py`; a document stops quoting the recorded values or still
carries a retired one (`1648`, `1682 tests`, `2,050 text nodes`, `635b7061`, `80725f6`); a cited
40-hex commit does not exist; a historical pin is attributed to the wrong commit; or the suite no
longer reports the recorded test count. `--skip-tests` runs everything except the suite.
