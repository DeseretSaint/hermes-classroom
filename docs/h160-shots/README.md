# H-160 evidence: the two measured H-151 defects

`h160-facts.json` is the unedited output of the H-151 capture script run against this branch's
`desktop/plugin.js` (`sha256 710178571d7a943cfa4e786a03ada9f42b29b59b5968ce33a27567ffeea6e68b`) in the
isolated Electron window — not a fixture, not a hand-written table:

```
# rig: ~/.hermes/coursebook-test-h151 (remote backend 127.0.0.1:44219, dev server 127.0.0.1:5174)
# home/plugins/coursebook -> this worktree; home/desktop-plugins/coursebook/plugin.js copied from it
COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-h151 CB013_CDP_PORT=9371 \
  bash scripts/cb013-live-window.sh --restart
CB009_CDP_PORT=9371 node scripts/h151-action-capture.mjs <out-dir>
```

It is a second bundle rather than an overwrite of `docs/h151-shots/`: those frames are the
`fc16813` before-state that `docs/H151-ACTION-TYPE.md` §2–§5 describes, and replacing them would
delete the only record of the 53 px failure.

## Numbers

| fact | H-151 at `fc16813` | H-160 |
|---|---|---|
| Courses `primaryCount` (1049 / 900 / 460) | 0 / 0 / 0 | **1 / 1 / 1**, label `New course` |
| `text200.routeOverflowX` (section route, 460 px, 32 px root) | **53** | **0** |
| `text200.overflowX` (document) | 0 | 0 |
| `text200.zeroSizedControls` | 0 | 0 |
| `routeOverflowX` on every other measured surface (15 frames) | 0 | 0 |
| reading column `[data-cb-main]` at 460 px, 16 px root | scrolled (790 px breadcrumb) | **0** (185 / 185) |

At a 32 px root the reading column still scrolls sideways by 163 px for tabular evidence rows and
`whitespace-nowrap` chips. That is inside the column's own `overflow: auto`, not route overflow; the
route-level number this card accepts is `0`.

## What was wider than the 215 px pane

1. `COURSEBOOK`, the header wordmark: 28 px + 0.14em tracking = 239 px.
2. `Course`, the page title at the display step: 72 px at a 32 px root ≈ 220 px.
3. the section breadcrumb, the course title inside a host `variant: 'text'` button
   (`shrink-0 whitespace-nowrap`) = 790 px.

Fixes are declared wrapping (`overflowWrap: 'anywhere'` + `minWidth: 0` on the two header tokens; a
`CbAction tertiary` breadcrumb with `whiteSpace: 'normal'`, `flexShrink: 1`, `maxWidth: '100%'`).
No `overflow-x: hidden` was added anywhere.
