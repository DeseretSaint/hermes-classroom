# CP-042 — visual gate run (owner-directed, 2026-11-10 18:45 ruling)

The gate in `docs/concept-parity/VISUAL-GATE.md` was run against a live Desktop window driven by
this branch's plugin and this branch's backend. It was **not** run against the operator's app
(`PID 360235`, packaged, no CDP port), and it did **not** attach to another worker's rig
(`coursebook-test-gm010` on 9371, `coursebook-test-cp024` on 9381): those were live and in use.

## Rig (isolated, disposable, reproducible)

```bash
export COURSEBOOK_TEST_HOME=$HOME/.hermes/cp042-visual/home
scripts/install-local.sh                                             # plugin + agent half, SHA-matched
COURSEBOOK_TEST_HOME=$COURSEBOOK_TEST_HOME CB013_PORT=44442 \
  CB013_TOKEN=cp042-visual-token scripts/cb013-live-backend.sh       # backend ready on 44442
COURSEBOOK_TEST_STATE=$HOME/.hermes/cp042-visual CB013_CDP_PORT=9391 \
  scripts/cb013-live-window.sh --restart                             # dev Electron, CDP 9391
cd visual && node find-cdp.mjs                                       # prints 9391 (and the two live rigs)
node audit.mjs --port 9391                                           # frames/, diffs/, report.json
```

`find-cdp.mjs` printed `9381` and `9371` (the two live worker rigs) as well as `9391`; the audit was
bound to `9391` only. The desktop half of a unified package ships opt-in, so the gate run sets
`localStorage['hermes.desktop.pluginDecisions.v2'] = {"coursebook": true}` and restarts the window
(`visual/open-coursebook-route.mjs` is the small driver the rig uses to prime that decision and open
`#/coursebook`; it writes nothing to the app).

Plugin under test: `sha256:45c7d9720115cf513b40883b4810f89b75ea52a744999fac228bd32b59c3028c`
(this branch's `desktop/plugin.js`). Comparison build: `sha256:4087908c1881df93bf0f7e71bbac65c2511aee3f115271f6b3f846091c9d03b7`
(`origin/master`'s `desktop/plugin.js`, installed into the same rig).

## Result — all four routes rendered, three pre-existing failures

| route | rendered (CSS px) | scope | CB Display | CB UI | axe serious/critical | diff vs baseline |
| --- | --- | --- | --- | --- | --- | --- |
| home | 818 × 488 | light | **false** | true | none | 0.00 % |
| courses | 818 × 488 | light | **false** | true | none | 0.00 % |
| workshop | 818 × 488 | light | **false** | true | `label-content-name-mismatch` (1 node) | 0.00 % |
| studio | 818 × 488 | light | **false** | true | none | 0.00 % |

- Frames are captured at 2× device scale (1636 × 976 px) of an 818 × 488 CSS route box. That is
  **not** the approved 1344 × 768 reference geometry: the host sidebar plus a 1440 px window leaves
  an 818 px pane. Per gate rule 1 the composition is scored against the pane's own state and the
  reference comparisons below are advisory, not a parity claim.
- Similarity against the approved references (gate rule 1 caveat applies — different geometry):
  `workshop` → `refs/discover.png` **0.6347**; `home` → `refs/home.png` **0.8013**.
- Sheets: `audit/cp042-shipping/visual-gate/compare/workshop-discover-sheet.png`,
  `…/workshop-discover.txt`; `report.json` and `report-branch.json` are the raw audit output.

## The three failures are pre-existing (reproduced on `origin/master`'s plugin)

The identical audit, same rig, same packs, with `origin/master`'s `desktop/plugin.js` installed,
produced the **same five findings**: `CB Display` unloaded on all four routes, `CB UI` loaded, and
`workshop: label-content-name-mismatch` (serious, 1 node) — see `master/report.json`. Frame diff
against the branch baselines was 0.00 % on every route, because the Discover/store data is served by
the Python half (this branch's linked `coursebook` package), so both plugin builds render the same
pack list.

So this run does **not** claim a clean pixel gate. It records: (a) CP-042 introduces no rendered
regression, and (b) the display-font and Workshop accessible-name failures are live defects on
`master` that a pixel/axe gate catches and the unit suite cannot. They belong to the desktop
surface, not to this pack-metadata card.

## The shipped titles are DOM text (the point this card owns)

The `workshop` route's rendered text titles, read from the live DOM, included all three shipped
courses as real text:

```
Japanese register: affection and closeness
Measuring together: a kitchen lesson
Reading a pack before you install it
```

with no cover image carrying a title (the covers are the deterministic, OCR-verified art from
`tests/test_pack_shipping_labels.py::CoverArtTests`).
