# GM-012 — tutor rail evidence

Branch: `wt/gm-012-tutor-ui`. Plugin sha: `e1ead18e161e9fa9ab37925a8f2f67efeb5b70affff729e09f6bf7459a099a6e`.

## What this packet is — and is not

These are **component frames**, not live Desktop captures. `scripts/gm012-rail-render.mjs` renders the
shipped `TutorRail` from `desktop/plugin.js` into standalone HTML with the module's own token styles
(`cbScopeStyle` + `cbHostVars`); `scripts/m4v-audit.mjs` paints each frame in headless Chromium and
records contrast, clipping, horizontal overflow, unnamed controls and target sizes. The rail's own
layout is inline style on the token contract, so hierarchy, type, wrapping and target size are the
shipped component's. Host chrome (sidebar, chat, pane frame) is absent.

The packet does **not** prove a live window. A live attempt was made in a disposable home
(`~/.hermes/coursebook-test-gm012`): the isolated backend (wire v24, plugin_root = this worktree)
served `lesson.page`, `tutor.history` (seeded thread), `tutor.ask`, and `practice.*`; the Electron rig
(window pid recorded in that state's `window.pid`, CDP 9367) painted the shell but never registered the
Coursebook route or sidebar entry — no `[data-cb-route]`, no `codebook` text node — so the pane could
not be driven there. That is recorded as a rig/plugin-load finding, not a route result.

## Frames

32 PNGs: `ask`, `quote`, `practice`, `no-lesson` × light/dark × 1049/900/460 + 460 at 200% root text.
Each is `rail-<surface>--<width>--<mode>.png`; measurements in `audit.json` under the same ids.
At 1049/900 the rail is painted at its 340 px pane width; at 460 it is painted full width and selects
`data-cb-tutor-rail="sheet"`.

Measured on this run: 0 clipped, 0 horizontal overflow, 0 unnamed controls, 0 positive tabindex.
The only contrast row below 4.5 is the **disabled** primary `Ask` (2.43:1), which is an inactive
control (WCAG 1.4.3 exemption); the enabled `Ask`/`Say it` and every body/quiet line pass.

## What the tests prove instead

`tests/test_desktop_gm012_tutor_rail.py` (9 tests) renders the same component through React and scans
the module source: selection arms a quote and never calls `tutor.ask`; the quote chip has a labelled
remove; glossary terms are `<button>`s and prose is not a target; citations are buttons that name a
served block and unknown ids are omitted; the rail never reaches `host.newChat`/`host.openSession`/
`host.composer`; practice marks only learner turns as graded and writes through `practice.*`; the rail
is a sheet under 520 px; every named state paints its own copy; the hint path records `lesson.assist`
and the answer stays withheld.

## Repro

```
python3 scripts/gm012-rail-capture.py
python3 -m unittest tests.test_desktop_gm012_tutor_rail tests.test_m4_visual_audit
```
