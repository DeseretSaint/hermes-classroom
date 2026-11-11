# t_831137dd — Home kit round 2 evidence

Module under test: `desktop/plugin.js` sha256 `71d940ce0398220fe1d25d1ec39b1e4bdfbc2a1c257eb7eb42292c628ac4d4b8`
(`python3 scripts/build_plugin.py --check` matches `desktop/src`).

## What this round changed from `3cdfa1d0`

1. Fox and clock seated ON plank two (top edge y=684): clock `top` 588 -> 568 (painted base 683.7),
   fox `top` 526 -> 481 (painted feet 684.1), both inside the card's +/-2 px.
2. Fox moved right, `left` 1088 -> 1110: opaque fox art now clears the opaque clock art by 11.4 px
   (clock right 1142.5, fox left 1153.9), where round 1 overlapped by 10.6 px.
3. Hero contrast: the question paints `var(--cb3-ink)` (was `var(--cb3-forest)`, which measured
   4.45:1 on the plate) and the panel scrim is `--cb3-canvas` at opacity 0.60 (was 0.55). Measured
   on the committed 1344x768 proof, background pixels >= 6 px from any near-ink pixel: title box
   worst 5.62:1 (ink), subline band worst 5.77:1 (ink); the same pixels give forest 4.94 / 5.08.
4. `data-cb-home-cover` on the narrow hub card no longer says `type` for a painted kit cover.
5. New pins: seating + separation arithmetic, hero ink + scrim floor, and per-course cover mapping
   (technical / japanese / parent / lesson-room) instead of "any approved row".

## Files

- `home-scene-1344-proof.png` — `design/home-scene.html` (generated from the built module by
  `scripts/gen-home-proof.py`) at 1344x768, chromium headless. This is the composition frame.
- `home-1344-light.png` / `.json` — the installed plugin's `[data-cb-route]` box at exactly
  1344x768, light scope, with per-element read-back (module sha, scope, fonts, rects, covers).
- `home-900-light.png` / `.json` — the same camera at 900x768.

## Not passing, stated as such

The installed 1344/900 frames show the plugin's **empty-library Home**, not the shelf: this rig
window issued **no coursebook RPC at all** (zero `performance` entries for the plugin), so it never
saw the three enrolled courses that are in the rig database
(`~/.hermes/coursebook-test-t831137dd/home/plugin-data/coursebook/data.db`, 3 enrollments). The
frames are the right size and scope, but they are not composition evidence. The previous installed
frames (module `3cdfa1d0`) were taken before the plugin was reinstalled into this rig home; after
reinstall the host renders the plugin but does not bind its runtime context. That harness defect is
routed with `t_92878d65`; this card does not fake around it.

## Audit deltas a reader will see, and why they are deliberate

`node scripts/audit-screen.mjs visual/spec/home.json --html design/home-scene.html` on this proof
reports **3 mismatched / 14 out-of-tolerance** (was 39 out of tolerance at `3cdfa1d0`). The three
mismatches are the D-007 trades, not drift:

- fox `box.top` −45 px and fox `box.left` +22 px — the fox moved from the pack's 526/1088 box to
  481/1110 so its painted feet sit on plank two's 684 top edge and its opaque art clears the clock's;
- clock `box.top` −20 px — 588 → 568 for the same seating rule (painted base 683.7);
- `subline` paints `--cb3-ink` (`#1a1713`) where the pack spec says `#5c5347` — ink on the token
  scrim is what holds the hero text at ≥ 4.5:1 over the painted plate.

`visual/spec/home.json` still carries the pre-trade boxes, so the audit stays red on those four
values. The audit is recorded, not gated, under D-007.

## Capture attempt after review round 2 (2026-11-11 12:35–13:15 MST) — still no bound frame

The reviewer asked for one more recapture from a freshly started, freshly seeded rig window. That
was attempted; it did not produce a usable frame, and the reason is now known precisely:

1. **The rig had no backend of its own.** `serve-44219.log` ends with
   `BACKEND_PORT_IN_USE port=44219`. The listener on 44219 was another card's backend:
   `/proc/<pid>/environ` shows `HERMES_HOME=/home/deseretsaint/.hermes/coursebook-test/home` and its
   runtime answers `plugin_root: /home/deseretsaint/Projects/hermes-classroom`. The rig script's
   readiness loop greps the whole appended log, so earlier `HERMES_DASHBOARD_READY` lines in that
   same file satisfied it and the window was pointed at a foreign backend.
2. **Restarted on free ports with its own backend.** State `~/.hermes/coursebook-test-t831137dd`,
   backend 44671, CDP 9481, dev Electron from `apps/desktop`. Verified by direct request:
   `plugin_root` = this worktree, `HERMES_HOME` = the rig home, `wire_version` 26; installed
   `plugin.js` sha256 `71d940ce…` equals the checkout and `home/plugins/coursebook/desktop/plugin.js`.
3. **The window still does not bind that backend.** With the round-2 userdata the app rendered the
   scene at 1344 (`scene:true`, 4 cards, 4 covers, fox and clock present) but the card titles were
   `Read the Night Sky`, `Technical demo: reading a pack…`, `Japanese affection and register — a
   Sample L0 classroom`, `… an L0 demonstration classroom` — courses that live in
   `~/.hermes/coursebook-test/home`, not in this rig's DB (which holds 3: *Japanese register:
   affection and closeness*, *Measuring together: a kitchen lesson*, *Reading a pack before you
   install it*). So that frame photographs a foreign library under this module; it is **not
   shipped as evidence**.
4. **A fresh userdata dir binds the operator's local gateway.** `connections.json` names
   `remote-cp051` at 127.0.0.1:44671 as primary and `lastUsed`, yet the window logs
   `Gateway inaccessible (runtime_exited)` from `ensureLocalGateway` and the sidebar lists the
   operator's own sessions. The renderer also resets any `#/coursebook` hash to `#/`, so the plugin
   route cannot be opened without a connection that serves it.

Net: no frame in this card shows the kit composition under an installed plugin. The composition
evidence remains the generated 1344x768 proof (`home-scene-1344-proof.png`), which
`python3 scripts/gen-home-proof.py --check` ties byte-for-byte to `desktop/plugin.js`
(`71d940ce…`). The ruling that a proof render may substitute for a host frame is the UI director's;
it is raised on the card rather than assumed here.
