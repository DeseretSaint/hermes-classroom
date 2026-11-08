# Release evidence — what is measured, on which commit, and what is branch-only

Status: the H-116 truth pass, re-derived on the merged release candidate `master`
`c6b658ea923f1fe14f1e342e9fb816097e3727ea` (H-120a `wt/h120a-contracts` @ `28b5346` merged onto
`origin/master` `14a6443`). Every
number below was produced by a command in this pass on that commit unless a row names another
commit. Machine-readable copy: `docs/release-evidence.json`, checked against the documents by
`python3 scripts/check-docs-truth.py`.

**This is not a green release.** The suite passes and the pane crash and library clipping that
blocked H-85 are fixed here, but no demo is recorded, no license exists, no live Desktop window has
driven this exact commit, and the operator publication gate in `docs/SUBMISSION.md` §0 is closed.
No tag, catalog pull request or announcement was made.

## Measured on `c6b658e`

| Fact | Value | Command |
| --- | --- | --- |
| Suite | `Ran 1984 tests in 310.621s`, `OK (skipped=1)` | `python3 -m unittest discover -s tests -t .` |
| `cb.rpc` | v16, 68 declared methods | `contracts/rpc.v16.json` (`$defs.method.enum` length) |
| Handlers | 68, asserted by the registry test inside the suite | registry test in the suite |
| `cb.db` | v11, `DB_SCHEMA_VERSION = 11`, migrations `0001`-`0011` | `coursebook/db.py`, `contracts/db.v11.json` |
| Shipped module | `desktop/plugin.js` sha256 `9735300e197a0c6a1fb85ba7f15ec40b156283394a795399b9b9e2ba49f25547` | `sha256sum desktop/plugin.js` |
| M4 audit | 62 frames, 15/15 claims PASS, 2,282 measured text nodes over 56 non-forced frames, worst authored contrast 5.93:1, 0 unnamed of 364 AX controls, 0 px overflow | `audit/visual/m4-visual/audit.json` |
| M4 reproducibility | `PASS: two independent runs produced identical audit.json (62 frames, modulo generated_at) and 62 identical screenshots`, `plugin_sha256: 9735300e…` | `python3 scripts/m4v-repro-check.py` |
| Adversarial state matrix | `SUMMARY total=23 fail=0 pass=23`; S13 BLOCKED because the auxiliary grader lane is disabled in this release | `python3 tests/adversarial/attack_state.py` |
| Catalog validity | `OK: 1 file(s) valid` | `python3 ~/.hermes/hermes-agent/scripts/validate_plugin_catalog.py catalog/coursebook.yaml` |

The `audit.json` carries `plugin_sha256` equal to the shipped module's hash, which is what makes the
M4 row a claim about this commit rather than a stale pin. The 2,282 text-node count is the sum over
the 56 non-forced-colour frames; the six forced-colours frames repeat the same content and are
counted in `C-09` instead (2,602 text nodes over all 62 frames). The previous record quoted 2,266
because it was measured on the `71fc4c3f` module at `b33a42f`; the audit was regenerated on this
tree after the P0 react-key sweep and H-144 moved the rendered text nodes, and the value here is
re-derived from `audit/visual/m4-visual/audit.json` rather than carried forward.

## Branch-only evidence (not release evidence)

| Work | Commit | What it proves | Relationship to this candidate |
| --- | --- | --- | --- |
| H-85 final gate | branch `h85-gate` `46c16ed` | FAIL verdict on `7d0f9cf`: P0 `Cannot read properties of null (reading 'binding_status')` in the course → section path, and Library header clipping at 900 and 460 px | The defects are fixed here by H-91 (`670de1b`, merged through `494a540`); the gate itself was not re-run on `c6b658e` |
| H-90 reproducibility fix | branch `h90-repro` `f0e3d1d` (base `36f9a1d`, plugin `416ff74`) | Paint stage waits for media metadata and image decode before each capture; 62/62 reproducible | The script half is portable; its regenerated pixels describe `416ff74`, not this module |
| H-89 frequency inventory | `wt/h89-frequency-inventory` `149e428`, landed as `53fe8c9` | Source-audited frequency inventory seam and vocabulary sequencing; 25 tests | Merged into this candidate; its branch suite count (1,682) is not this tree's count |

The rule is the same one H-111 applied: a count measured on an unmerged branch is not a count for
this tree. `README.md` and `docs/M4-VISUAL-MEDIA-AUDIT.md` name these commits as branch or historical
evidence and do not cite their numbers as current.

## What this pass did not measure

- No live Desktop window and no mounted backend trace on `c6b658e`; `scripts/validate.sh` step 5 was
  not run here (it needs a mounted backend and an isolated home).
- `bash scripts/validate-plugin.sh` (the export admission gate) and `hermes plugins doctor` were not
  re-run in this docs pass. Rows that cite them cite the `29bede7` record or mark the gap.
- `scripts/m4v-repro-check.py` was run here: two independent runs at `9735300e` produced identical
  `audit.json` (modulo `generated_at`) and 62 identical screenshots; the verbatim output is in
  `docs/M4-VISUAL-MEDIA-AUDIT.md`.
- No provider-spend generation, no demo capture, no recording.
- The adversarial matrix was re-run here and is green (23/23 PASS, S13 BLOCKED by design); S08 and
  S09, which failed on `7d0f9cf` under H-111's measurement, pass on this candidate.

## Keeping this honest

`python3 scripts/check-docs-truth.py` fails when: the recorded plugin hash is not the hash of
`desktop/plugin.js` at the recorded commit; the recorded RPC method count or schema version disagrees
with the contract and `coursebook/db.py`; a document stops quoting the recorded values or still
carries a retired one (`1648`, `1682 tests`, `2,050 text nodes`, `635b7061`, `80725f6`); a cited
40-hex commit does not exist; a historical pin is attributed to the wrong commit; or the suite no
longer reports the recorded test count. `--skip-tests` runs everything except the suite.
