# F-01 — light-theme meta text below AA contrast

Follow-up to `audit/A11Y_UX_AUDIT.md` §F-01 (184 failing text nodes, light theme only, 3.47–3.53:1
against a required 4.5:1). Everything below is measured with the Sentinel harness
(`scripts/audit-ux-lib.mjs` `measure()`), not eyeballed.

## What changed

| File | Change |
|---|---|
| `desktop/plugin.js` | All **88** `text-(--ui-text-tertiary)` call sites → `text-(--ui-text-secondary)` (74 % alpha instead of 54 %). The plugin keeps no tertiary text: every one of the 88 was readable copy (meta lines, empty-state explanations, provenance, hashes, timestamps, section labels), none decorative. No raw colour, no `!important`, no host-chrome rule touched. |
| `scripts/audit-ux-lib.mjs` | Additive measurement only: `contrastTotal`, `contrastBySize`, `contrastAll` (the existing `contrast[]` stays capped at 40), and each failing row now carries `tag` / `cls` / `slot` / `parentCls` so a reader can tell plugin-authored copy from host-primitive paint. |
| `scripts/f01-states.mjs` | The seven audited states, induced exactly as `scripts/audit-ux-run.mjs` does (same fault shapes, same real UI actions). |
| `scripts/f01-contrast.mjs` | Runs those states under one theme and records `contrast` per state; `--token=<pct>` applies a **measurement-only** host-token simulation (never shipped). |
| `audit/ux/f01-light-before.json` | Before: master plugin, light. |
| `audit/ux/f01-light-after.json` | After: this branch, light, with the ownership trail. |
| `audit/ux/f01-light-token6{3,6}.json` | Host token simulation at 63 % / 66 % (0 failures). |
| `audit/ux/f01-light-token61.json` | Negative control: 61 % still fails with exactly the same 86 nodes. |
| `audit/ux/f01-dark-after.json` | Dark regression pass after the change (0 failures). |

## Measured before → after, light theme, seven captured states

| State | Before (tertiary 54 %) | After (plugin on secondary) | Host token 63 % | Host token 61 % (control) |
|---|---:|---:|---:|---:|
| lesson-ready | 15 | 7 | **0** | 7 |
| no-courses | 10 | 5 | **0** | 5 |
| no-search-results | 7 | 6 | **0** | 6 |
| backend-off | 3 | 1 | **0** | 1 |
| degraded-db | 5 | 2 | **0** | 2 |
| unsupported-backend | 6 | 5 | **0** | 5 |
| demo-fixture-mode | 81 | 60 | **0** | 60 |
| **total** | **127** | **86** | **0** | **86** |

All failing rows keep the same signature: `fg: color(srgb 0.121569 0.137255 0.156863 / 0.54)`,
3.53:1 over `rgb(254,254,254)` (12 px / 11 px) and 3.47:1 over `rgb(246,246,246)` (9.6 px / 10.4 px).
The before total on this rig is 127; Sentinel's audit headline is 184 for the same defect on its own
window — same foreground, same ratios, same strings, different rig state (row count, pane open).
After the change **no failing node is plugin-authored**.

## Where the remaining 86 nodes come from (host primitives, not plugin copy)

Classification of every remaining failing node by its own class trail
(`audit/ux/f01-light-after.json` → `contrastAll[]`):

| Owner | Nodes | Evidence |
|---|---:|---|
| `Badge` (variant `muted`/`outline`) | 23 | `data-slot="badge"`, `bg-muted text-muted-foreground`; `apps/desktop/src/components/ui/badge.tsx` variants |
| `SegmentedControl` inactive option | 22 | `text-muted-foreground hover:text-foreground`; `apps/desktop/src/components/ui/segmented-control.tsx:52` |
| `Button` variant `text` (`Open`, `Review`, `All courses`) | 20 | host `buttonVariants` base + `text-muted-foreground`; `apps/desktop/src/components/ui/button.tsx:41` |
| `ListRow` caption (`Review 1 objective(s)`, `Start …`) | 18 | `mt-1 text-[length:var(--conversation-caption-font-size)] … text-(--ui-text-tertiary)`; `apps/desktop/src/app/capabilities/primitives.tsx:28` |
| `EmptyState` / `ErrorState` description | 3 | `text-muted-foreground`; `empty-state.tsx:20`, `error-state.tsx:59` |
| unclassified plugin-owned | **0** | — |

`desktop/plugin.js` now contains **0** occurrences of `text-(--ui-text-tertiary)` and **0** of the
host utility `text-muted-foreground`, so every one of those nodes is painted by an SDK primitive's
own class. Two of them (`EmptyState.description` is a `string`, and `SegmentedControl` exposes no
per-option class) have no plugin seam at all; repainting the rest from the plugin would mean
re-specifying host chrome, which the brief forbids.

## The host dependency (option b), quantified

The token is one host declaration, shared by both themes:

```
apps/desktop/src/styles.css:365  --ui-text-secondary: color-mix(in srgb, var(--ui-base) 74%, transparent);
apps/desktop/src/styles.css:366  --ui-text-tertiary:  color-mix(in srgb, var(--ui-base) 54%, transparent);
apps/desktop/src/styles.css:426  --dt-muted-foreground: var(--ui-text-tertiary);
apps/desktop/src/styles.css:133  --color-muted-foreground: var(--dt-muted-foreground);
```

In light mode `--ui-base` is `#1f2328`, so 54 % composites to 3.53:1 over `#fefefe` and 3.47:1 over
`#f6f6f6`. Simulating a higher light-theme alpha in the renderer (measurement only — the plugin
ships no colour):

| Light tertiary alpha | Failing nodes, 7 states | Worst ratio |
|---:|---:|---:|
| 54 % (today) | 86 | 3.47 |
| 61 % (control) | 86 | 3.47 |
| **63 %** | **0** | ≥ 4.5 |
| 66 % | 0 | ≥ 4.5 |
| 74 % (= secondary, currently 0 plugin use) | 0 | ≥ 4.5 |

**Ask for the host token owner:** raise the *light-theme* tertiary from 54 % to 66 % (or introduce a
light-only tertiary step; 63 % is the measured floor, 66 % is the recommendation to keep a real step
below secondary at 74 %). Nothing else in the Desktop changes: dark tertiary stays 54 %, and this
branch's dark pass over the same seven states is 0 failures.

Until that host value moves, F-01 is **not closed**: the plugin-owned share is fixed and proven at 0,
and the residual 86 nodes are addressed by the one-line host change above, not by plugin CSS.

## F-03 — 200 ms transitions (reassigned to the host)

`desktop-input-chrome` is a host class, not a plugin class:

```
apps/desktop/src/styles.css:1547  .desktop-input-chrome { … transition: border-color 200ms ease-out; }
apps/desktop/src/components/ui/control.ts:9   'desktop-input-chrome w-full …'  (host Input/control chrome)
```

Measured in this rig: `document.querySelectorAll('[class*="desktop-input-chrome"]')` inside
`[data-cb-route]` = **0** on the courses/lesson screens, and `desktop/plugin.js` contains **0**
`transition` declarations. The audit's "up to two nodes per page" are host controls, so F-03 is
host-owned like F-05/F-07: changing it means editing host CSS, which is outside this plugin's
surface. One-line host fix if the owner wants it: `transition: border-color 100ms ease-out`.

## F-04 — 9.6 px tag captions (report-only)

Unchanged by this work: 23 of the 86 residual nodes are 9.6 px `Badge` captions (`Casual`,
`Parent preparation`, `recall`, `Needs review`). They are host-painted and still fail until the
token moves; at 200 % text they compute to 19.2 px. Report-only, as scoped.

## Reproduce

```bash
# isolated rig: own home, own userdata, own gateway path (nothing touches the operator's window)
scripts/install-local.sh --source <checkout> --home ~/.hermes/f01-test/home --no-enable
AUDIT_PROXY_PORT=44332 AUDIT_TARGET=http://127.0.0.1:44219 node scripts/audit-ux-proxy.mjs &
COURSEBOOK_TEST_STATE=~/.hermes/f01-test CB013_CDP_PORT=9361 scripts/cb013-live-window.sh
CB015_CDP_PORT=9361 node scripts/audit-ux-bootstrap.mjs
CB015_CDP_PORT=9361 node scripts/f01-contrast.mjs audit/ux/f01-light-after.json after-fix --mode=light
CB015_CDP_PORT=9361 node scripts/f01-contrast.mjs /tmp/t66.json host-token-66 --token=66
```

The userdata `connections.json` must point at the proxy port **before** the window starts — the
running app keeps dialling its launch connection until restarted, which is the §7.3 topology block
in the audit.

Rig note: the audit window on CDP 9351 was not usable for this pass — its renderer sat at 99.5 % CPU
/ ~7 GB and answered no CDP domain (`Runtime.enable` timed out), consistent with audit §F-07
(host tile-memory pressure). This pass therefore ran on its own isolated window.

## Gates

- `python3 -m unittest discover -s tests -t .` → **Ran 664 tests, OK**
- `node --check desktop/plugin.js` → **OK**
- `node scripts/cb015-hygiene.mjs` → **0** violations across 13 rules
