# GM-012 — live select → ask → cited answer → citation walkthrough

**Outcome: live capture not produced.** No frame in this directory is a valid,
stamped live frame, so this card ships none. What follows is the record of the
attempt: the rig that ran, the steps that did happen in a real window, the two
distinct walls that stopped the packet, and exactly what is not measured.

Captured at `dbc8fe1` on branch `wt/t_ef904ef4` (the reviewed GM-012a tip).
`sha256(desktop/plugin.js)` = `4d34c7a09a6e6f4ba0d8c9796f41a27bd88ca107c6e91761fdf828060b5c34e4`.

## Gate results at this sha

| Gate | Result |
| --- | --- |
| `python3 -m unittest tests.test_desktop_gm012_tutor_rail` | **OK — Ran 10 tests in 0.919s** |
| Frame stamp sha == `sha256(desktop/plugin.js)` | **Not achievable — see "Why no frame ships"** |
| "What this packet does not measure" section | present, below |

The earlier packet said "9 tests". At `dbc8fe1` the module's rail test file runs
**10** tests. The count above is the one this run executed.

## The rig that ran (fresh state, not the stale one)

The carried-over GM-012 state was not reused. Its `connections.json` primary was
`127.0.0.1:44292` while the card's backend served elsewhere, which is the failure
mode the card warned about. A new state was built with ports provisioned to match
before anything launched:

```
state      ~/.hermes/coursebook-test-gm012b
home       ~/.hermes/coursebook-test-gm012b/home
userdata   ~/.hermes/coursebook-test-gm012b/userdata   (connections.json primary 127-0-0-1-44391)
backend    127.0.0.1:44391   (hermes serve --isolated --skip-build, pid 3985053)
window     CDP 127.0.0.1:9391 (Electron dev build, pid 3985681)
```

Install: `COURSEBOOK_TEST_HOME=…/home scripts/install-local.sh --source <worktree>` —
validation passed, 2 tools / 3 hooks registered, installed Desktop copy sha-matched.

Backend identity, read from the running process:

```json
{"wire_version": 24, "plugin_root": "/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ef904ef4"}
```

Both load paths hashed before the window launched: checkout `desktop/plugin.js`
and `home/desktop-plugins/coursebook/plugin.js` are both
`4d34c7a0…c34e4`; `home/plugins/coursebook` is a symlink to this worktree.

The boot-time disk scan again did not produce a nav entry. The plugin record was
present but `status: "disabled"` (the unified agent-plugin root ships the Desktop
half opt-in). Enabling it through the store (`setPluginEnabled('coursebook', true)`)
moved the record to `status: "loaded"`, and `#/coursebook` then painted
`[data-cb-route="/coursebook"]`. **That is a rig action, not a user action, and it
is disclosed here rather than presented as normal first-run behaviour.**

## What the live window actually showed

Session: `20261110_071352_9abc64`, backend `127.0.0.1:44391`, wire v24.

1. **Course seeded through the product's own import path** —
   `python3 scripts/seed-demo-course.py --base-url http://127.0.0.1:44391 --token … --mode fresh`
   returned `course_id crs_67aa6159…`, `enrollment_id enr_0e7e984f…`. The shelf then
   rendered the course; no database write was used.
2. **Start a fresh run** clicked on the course home armed the pending binding. The
   Coursebook chat pane rendered the armed state before any message was sent:
   `Lesson run ready: Tell everyday affection from a direct romantic declaration`.
3. **First chat message sent.** The chat took a durable id (`#/20261110_071352_9abc64`),
   the pane bound to the enrollment, and the shipped `TutorRail` mounted:
   `[data-cb-tutor-pane="enr_0e7e984f…"]`, pane text `This lesson is bound to this chat.`
4. **The open-check withhold line rendered live**, verbatim from the rail:
   `A check is open. The tutor helps you work it out; it does not show the answer or record a verdict.`
5. **The rail's own Ask button was pressed** — not a seeded `tutor.ask`, not a
   `PluginLlm` call. The composer input was filled
   (`Which phrase is polite for a first confession?`), the button was enabled
   (`disabled: false`), and clicking it produced:

   > `The tutor is unavailable. The lesson is still readable.` + a `Retry` control

   No answer, no citation buttons, no citation walk. This is the `ctx.llm` gap the
   card's rig notes predict: `hermes serve` never binds it, so the rail's ask path
   has no host model. The fallback (`scripts/gm012-seed-tutor.py` through
   `PluginLlm`) was **not** used, because it would not exercise this button and
   would make the packet's central claim false.

## Why no frame ships

The card's rule is that a frame is valid only if its stamp's plugin sha equals
`sha256(desktop/plugin.js)` at the captured commit. Three real window screenshots
were taken (armed pane; bound rail; Ask pressed) and then stamped by reading the
module through the host's own door, `window.hermesDesktop.readPluginSource(path)`.
The door returned **1,510,286 characters** hashing to
`1ece52dc3df86e33a7f13bbc40d3ee4140c4f5c4beb899dfe017f4e470f4b41e`, while the file
on disk at that same path is **1,476,713 bytes** hashing to `4d34c7a0…c34e4`.

That difference is the runtime loader's bare-specifier rewrite (it replaces imports
with shim blobs before evaluating). The text the renderer evaluates is therefore
**never** byte-identical to the module on disk, so no window-read hash can satisfy
the gate. Rather than ship frames whose stamp contradicts the commit, the three
PNGs were deleted. No `.png` remains in this directory and no stamp claims one.

Two consequences worth recording for whoever owns CP-000:

- `scripts/cp-capture.mjs` (the card's named capture door) **does not exist at
  `dbc8fe1`** or on `master`. It exists only on the unmerged CP-000 branch
  (`77d1731`). That script would also have refused here: it crops to
  `[data-cb-route]` and requires that route present, while the tutor rail is a
  **chat-pane** surface and no route is mounted once the chat opens.
- Its sha check as written (`readPluginSource` text vs the checkout file) cannot
  pass against this host for the rewrite reason above. The stamp needs a
  different identity anchor — the plugin record's registered id/version plus the
  on-disk file hash, or a loader-exposed source digest — before any CP packet can
  satisfy "stamp sha == commit sha".

## What this packet does not measure

- **No selection → quote chip.** The lesson body was never on screen together with
  the rail. `TutorRailPane` mounts as the Coursebook **chat pane**; opening a
  section navigates the main pane to `#/coursebook` and removes the chat that owns
  the rail. Nothing in this run selected text in a lesson body, so the quote chip
  and its labelled remove were **not** captured live and are not evidenced here.
- **No cited answer, no citation buttons, no citation walk.** The ask failed at the
  host-LLM seam before retrieval ran. Nothing here shows `tutor.ask` producing
  citations, and no citation click was performed.
- **No reload persistence.** `tutor.history` was never exercised, because there was
  no thread to survive a reload.
- **The withholding claim is partial.** The rail's static copy asserting that an
  open check withholds the answer rendered live, but that is the surface's own
  statement — not a measured refusal of a real answer, since no answer was ever
  produced.
- **Nothing about the a11y stage's limits is re-measured here.** This card adds no
  contrast, target-size, focus-order or reduced-motion measurement; the existing
  32-frame component packet under `docs/visual-review/gm-012/` is untouched and
  still says what it says (and still carries its stale "9 tests" line, which is
  outside this card's scope to edit).
- **Host chrome is present in any screenshot that was taken.** They were full-window
  `Page.captureScreenshot` frames, not crops, and they were discarded.
- **One rig action is not a user flow:** the plugin had to be enabled through the
  desktop plugin store because the unified root ships the Desktop half inert.

## Exact commands that failed or were refused

```
# the ask, from the rail's own button, live:
fill "Which phrase is polite for a first confession?" -> click [button] "Ask"
result: "The tutor is unavailable. The lesson is still readable." (Retry)

# the card's named capture door:
node scripts/cp-capture.mjs ...
=> scripts/cp-capture.mjs: No such file or directory (absent at dbc8fe1)

# identity check through the host's own read door:
window.hermesDesktop.readPluginSource("…/desktop-plugins/coursebook/plugin.js")
=> 1510286 chars, sha256 1ece52dc…  vs file 1476713 bytes, sha256 4d34c7a0…
```

## Reproduction

```
COURSEBOOK_TEST_HOME=~/.hermes/coursebook-test-gm012b/home \
  scripts/install-local.sh --source <this worktree>
COURSEBOOK_TEST_HOME=~/.hermes/coursebook-test-gm012b/home \
  CB013_PORT=44391 CB013_TOKEN=<token> scripts/cb013-live-backend.sh
COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-gm012b \
  CB013_CDP_PORT=9391 scripts/cb013-live-window.sh --restart
python3 scripts/seed-demo-course.py --base-url http://127.0.0.1:44391 --token <token> --mode fresh
python3 -m unittest tests.test_desktop_gm012_tutor_rail   # Ran 10 tests, OK
```

The window remains at `CDP 9391` / backend `44391` at `~/.hermes/coursebook-test-gm012b`;
nothing was pushed, merged, published or recorded.
