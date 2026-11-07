# M1 narrow width — host decision: side rails leave the grid below the dock floor

Card: `t_eb497e0f`. Raised by the artifact review of `t_0a030589`
(`audit/visual/m1-guided-authoring/evidence.json`).

## The finding, restated precisely

The original 460 px frames were captured with `Emulation.setDeviceMetricsOverride`.
That changes `innerWidth` but does **not** deliver a media-query change to the
host's narrow atom (`$narrowViewport`, `matchMedia('(max-width: 639.98px)')`), so
the host never entered its narrow mode: a wide layout was measured inside a
narrow viewport. The numbers in the report are real, but they describe a state a
user cannot reach by resizing the window.

Re-measured on a **real** 460 × 1000 window (compositor resize, so the breakpoint
engages), the defect is still there and is worse than "22vw":

| pane | width at 460 px |
|---|---|
| `grp-sessions` (minimized rail) | 28 |
| `grp-main` — the Coursebook route | **101** |
| `grp-review` — the plugin's `coursebook:pane` (declared `width: '340px'`) | 331 |

The row spends the fixed rail's declared width first and the flex main zone
absorbs the remainder, which then bottoms out at the workspace pane's `22vw`
floor. The plugin's own companion pane is what starves the route.

## Decision

**A fixed-width side rail leaves the grid below the host's dock floor and is
revealed as an edge overlay — whether or not the pane opted into `collapsible`.**

The host already owns this policy: `SIDEBAR_DOCK_MIN_WIDTH_PX = 640` is the
width below which docking "stops paying for itself", and `collapsible` panes
already leave the grid there. The gap is that `collapsible` is an **opt-in**, and
a plugin that declares `width: '340px'` never opted in — it cannot, because it
does not know the window width and the breakpoint is a host property.

Rejected alternatives:

- **Collapse the chat zone only.** Same rule, narrower scope: it leaves the next
  width-declaring plugin pane to reproduce the bug. The host should not special-case
  one pane id.
- **Enforce a minimum route width.** At 460 px the fixed rail (340) plus any
  usable main floor (≥ 320) exceeds the window. A minimum does not create space;
  it overflows the row or clips the rail. Rejected on arithmetic.
- **Move the pane to a sheet at narrow widths.** This is what the chosen rule
  produces in effect (the overlay is a sheet over the layout), but implemented
  through the mechanism the host already has rather than a second one.
- **Change `desktop/plugin.js` to shrink or hide its own pane.** Out of scope by
  the card, and wrong in principle: the plugin would be guessing at host width.

## Implementation

`narrowLeavesGrid(chrome)` in
`apps/desktop/src/components/pane-shell/tree/renderer/track-model.ts`:

```
collapsible            → leaves the grid
placement main/floating → stays
otherwise              → leaves the grid iff it declares a horizontal `width`
```

Wired through the three places that already tested `narrow && collapsible`
(`tree-split` `paneGone`, `tree-group` `paneShown`, `store` `shownPanesInGroup`)
and through `NarrowOverlays`' reveal list, so a pane the host collapses is always
reachable. A height-only deck (the terminal) is a column track and is unaffected.

Host repo: `DeseretSaint/hermes-agent`, branch `wt/host-narrow-rail`, commit
`5900b6e7a0` (not pushed). `host-narrow-rail.patch` in this directory is the
canonical diff `94ade5ab22..5900b6e7a0` (six files, including the test) and
`git apply --check` passes on a clean worktree at `94ade5ab22`.
`host-narrow-rail.installed-checkout.patch` is the same change rebased onto the
installed checkout (`2bd378ed1b`), which is what the capture applied; the two
differ only in `tree-group.tsx` context line numbers.

Tests, run in the installed checkout with this patch applied (the same tree the
frames were captured from — the fork has no `node_modules`, so it cannot run
them itself): `npx vitest run src/components/pane-shell` → 52 files / 258 tests
passed, including 7 new `narrow-rail-collapse` tests; `npx tsc -p tsconfig.json
--noEmit` → exit 0.

## Evidence after the change

Real 460 × 1000 window, lesson document open, chat rail collapsed out of the grid:

| frame | routeWidth | viewWidth | horizontalOverflow |
|---|---|---|---|
| 07-textbook-dark-460px | 432 | 384 | false |
| 08-textbook-light-460px | 432 | 384 | false |
| 09-textbook-dark-460px-200pct | 404 | 308 | false |
| 10-guided-dark-460px | 432 | 392 | false |
| 11-guided-light-460px | 432 | 392 | false |
| 12-guided-dark-460px-200pct | 404 | 308 | false |
| 14-chat-overlay-dark-460px | 432 | 384 | false |

The route now takes the whole window minus the 28 px minimized terminal rail
(56 px at 200 % text, because that rail is sized in rem). At 200 % the lesson
body wraps and stays fully visible; the companion chat is one edge-reveal away
and slides over the lesson at its declared 340 px.

## Residuals

1. The host change is **not installed**. It was applied to
   `~/.hermes/hermes-agent` for the duration of the capture and reverted
   afterwards (the checkout's five files were restored to their pre-task
   sha256). Until `wt/host-narrow-rail` is merged and installed, the shipped app
   still shows the 101 px route at 460 px.
2. At 200 % text the plugin's own header tab strip truncates its third label
   ("Parent Stu…"). That is plugin-side label truncation inside a 432 px page,
   not host width allocation, and it does not clip lesson content. It belongs to
   the plugin's 200 % typography pass, not to this card.
3. The lesson in these frames is the pre-existing demo course served by the
   isolated backend; no provider was called and no spend occurred.
