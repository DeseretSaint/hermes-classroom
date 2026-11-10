# CP-044 — visual gate record (owner-directed gate, 2026-11-10 18:45)

Run per `docs/concept-parity/VISUAL-GATE.md` against the two live Hermes Desktop windows on this
box, via a copy of `visual/` kept out of the operator checkout
(`~/.hermes/profiles/harbor/cache/scratch/cp044-visual-*`). `node find-cdp.mjs` → ports `9371`,
`9357`; both show a `[data-cb-route="/coursebook"]` page.

**Read this first: this card changes no screen.** `git diff --name-only b09b65f..HEAD -- desktop/
visual/ docs/concept-parity/` is empty — CP-044 touches `coursebook/deadline.py`,
`coursebook/generation.py`, `coursebook/job_service.py`, tests, probes and docs. The gate was run
anyway because the operator made it binding for every review handoff. What follows is what the live
windows actually render, and where it does *not* meet the gate's own scoring rules.

## Numbers

| | port 9371 (narrow pane) | port 9357 (wide pane) |
| --- | --- | --- |
| rendered node **width × height** (CSS px) | **341 × 608** | **1515 × 1889** |
| screenshot pixels | 341 × 608 (dpr 1) | 1517 × 1891 (dpr 0.53) |
| `data-cb-scope` | **light** | **light** |
| `CB Display` loaded | **true** | **true** |
| `CB UI` loaded | **true** | **true** |
| axe **serious/critical** ids | **none** (0 violations, all four routes) | **`color-contrast` ×2, `label-content-name-mismatch` ×3** (5 serious; 1 minor `aria-allowed-role`) |
| pixel diff vs `visual/baselines/*.png` | **not comparable** — `frame size changed` (baseline 1101×1336 → render 341×608; tool reports ratio 1.0) | **not comparable** — `frame size changed` (baseline 1101×1336 → render 1517×1891) |
| similarity vs approved reference (`refs/home.png`) | **0.7519** (RMSE 0.248058; render 505×900 vs ref 1575×900 after equal-height resize) | **0.5256** (RMSE 0.474441; render 722×900) |
| sheet | `narrow-341x608/home-sheet.png` | `wide-1515x1889/home-sheet.png` |

`discover.txt` in the narrow folder is the Courses route against `refs/discover.png`:
similarity 0.6345 (RMSE 0.365451).

## Why these numbers cannot be scored as parity

1. **Neither pane is the reference breakpoint.** The approved references are 1344×768 landscape. The
   narrow window is a 341 px side pane and the wide one is a 1515×1889 tall pane — different
   breakpoints, which the gate's rule 1 says can be correct for their own width but cannot be scored
   as parity. The similarity figures above are therefore advisory only (0.75 / 0.53 against a
   landscape reference, mostly composition-crop difference, not a redesign claim).
2. **No stamp.** Neither page exposes a `plugin_sha256` (the probe for
   `[data-plugin-root]` / `data-cb-plugin` / `data:plugin-sha256` returned null on both ports), so by
   the gate's rule 5 these frames are not evidence *for commit 51d9fb4* — they are evidence of what
   the desktop that was already running renders. The worktree was never loaded into either window.
3. The two windows were launched before this card; nothing here was captured against the branch.

## What is still worth acting on

The wide pane has **5 serious axe violations** (`color-contrast` ×2, `label-content-name-mismatch`
×3) that the narrow pane does not show. Both windows are `light` scope and both load both product
fonts. Since CP-044 touches no markup, this is pre-existing and breakpoint-dependent; it is recorded
here rather than fixed, and tracked as `t_ffa0e5da` (assigned to vellum, the Desktop UI lane). The
narrow pane — the actual Phone/desktop side-pane shape this plugin ships into — is clean: 0
violations, fonts loaded, light scope.

## How this record was produced

```
cd ~/.hermes/profiles/harbor/cache/scratch/cp044-visual-1644/visual
node find-cdp.mjs                     # 9371, 9357
node audit.mjs --port 9371            # frames/, report.json in this copy
cd .. && bash scripts/compare-ref.sh visual/frames/home.png \
  docs/concept-parity/refs/home.png visual/compare home
# repeated in cp044-visual-wide-1644 for --port 9357
```

`report.json` and the frames/sheets from both runs are stored beside this file. The operator
checkout was read, never written: the `visual/` tree and `scripts/compare-ref.sh` were copied out
first.
