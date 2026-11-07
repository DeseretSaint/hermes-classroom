# CB-017 demo gate — U01-U04 on the release commit `29bede7`

Author: Sentinel. Measured in this run on this machine against the commit the demo would be recorded
on. Every verdict below is read from a live renderer (CDP) or a live backend read; raw captures are
in `audit/demo-gate/`. No recording exists and none is claimed.

Commit measured: `29bede7643403cd9d608499232125e6347c680dd` (`origin/master`, CB-017 merged, row-9
tail included). `git rev-parse HEAD` in the measuring worktree returns that sha.

## 1. Rig

| Item | Value |
| --- | --- |
| Worktree | `/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_7f53677c` at `29bede7` |
| Install | `scripts/install-local.sh --home ~/.hermes/coursebook-demo-gate-29bede7/home --source <worktree>` (fresh home, `Installed.`; 1 tool, 3 hooks) |
| Backend | `hermes serve --isolated --port 44297`, `HERMES_HOME=<fresh home>`, `HERMES_COURSEBOOK_SINGLE_HOME=1` |
| Backend proof | `GET /api/plugins/coursebook/runtime` → `plugin_root` = this worktree, `wire_version` 7, 52 implemented, `contract_problems: []` |
| Desktop half | installed `desktop-plugins/coursebook/plugin.js` sha256 `c59ebc3c937385f1119787a5522acda09fb852f8180c06e3d3f4615e3c8281fb` = the file in this commit |
| Window | Electron `--remote-debugging-port=9367`, own userdata, remote connection `127.0.0.1:44297` |
| Operator gateway | not touched. The window's shell still tries to dial the host's local gateway and logs `Gateway inaccessible (runtime_exited)`; that is host-owned noise, not this plugin |

The earlier rig (`coursebook-test-t_fc758da8`, backend 44251, CDP 9347) serves Atlas's review branch
`t_c9baab37`, not `29bede7`, so it was not used for the gate verdict.

## 2. Four scenarios

| id | scenario | verdict | flow driven | observable |
| --- | --- | --- | --- | --- |
| U01 | `/coursebook` route live | **PASS** | sidebar "Coursebook" clicked at its geometry; pointer click, no hash injection | `location.hash` `#/coursebook`; `[data-cb-route]` present after 50 ms, `data-cb-destination="courses"`; empty state "Your courses will appear here." matches `library.list` → `total: 0, empty_reason: no_courses`. One console error: React "Each child in a list should have a unique key prop" (`FirstRun`) |
| U02 | course list, create, import UI live | **PASS** | Library → "Import pack" → "Choose folder…" (OS folder chooser, driven on this host with `wtype`) → "Review" the Japanese pack → "Continue" → "Import and start learning" → "Back to the library" → "Courses" → "Open" | preview rendered the pack with "Hashes match the manifest: yes", content hash `sha256:638ce371db6bf2340a7b6a37a75a9762e0e9e6c3f723e55b0a0a5103a8376d7f`; result screen "Pack imported", course `crs_f8284b1d8e4240c6a9316150590b4bad`, enrollment `enr_1851453223f54e9e99a81fc92ab8788d`; `library.list` returns that row and `course.get` returns the course; Courses list renders the card with "Resume lesson"/"Open" |
| U03 | keyboard-only route path, focus, names | **PASS** | Tab from the shell home to "Open Coursebook" (5 stops), Enter mounts the route; each route stop reached with real CDP Tab events; first route control activated with Enter | `#/coursebook` mounted after Enter; every one of 18 route tab stops had `:focus-visible` true and a non-empty accessible name; AX tree 145 named interactive controls, 0 unnamed inside the route (1 unnamed host-shell button outside it). Harness note: CDP Enter needs `text: "\r"`; without it Chromium fires no click (test artifact, reproduced on a plain button) |
| U04 | 200% text / narrow / reduced motion / no-media | **PASS with one note** | viewport + root font-size emulation on the mounted route; `prefers-reduced-motion: reduce` emulated; blocked media URLs | 1440 at 16 px: overflowX 0, 0 clipped nodes, 0 unnamed. 1440 at 32 px (200%): overflowX 0, 0 clipped, 0 unnamed. 460 px at 16 px: overflowX 0, 0 clipped. 460 px at 32 px: overflowX 0 but **8 clipped nodes** (minor, note D3). Reduced motion: longest transition 0 ms, longest animation 0 ms. No-media: the route's DOM carries text content independent of images; the Japanese pack declares "No audio is bundled" |

A scenario that could not be driven is not reported as a pass. U01-U04 were all drivable; the demo
*shots* below were not, and that is the gate outcome.

## 3. Demo shots against this build

The U-scenarios pass, but the demo is not recordable on `29bede7` because the learning shots cannot
be driven. Measured, not inferred:

| DEMO.md time | shot | drivable on `29bede7`? | evidence |
| --- | --- | --- | --- |
| 0-8s | library, Japanese pack preview, enroll | **yes** | U02 import run; course + enrollment created |
| 8-25s | chat and pane side by side, wrong answer, retry | **no** | "Resume lesson" on the opened course moves the window to `#/` and the route unmounts; no chat opens and no pane appears (`audit/demo-gate/u05-resume-trace.json`: 12 samples over 6 s, all `mounted: false`) |
| 25-34s | correct attempt, one transition, evidence row | **no** | same ejection: there is no attempt surface to submit from |
| 34-40s | notebook save, reopen section | **no** | same ejection; notebook action lives in the route that just disappeared |
| 40-47s | restart, identical pending objective | **no** | depends on 8-34 |
| 47-62s | Parent Studio review, approve | not measured | needs generated pages on this fresh profile; generation was not run (see §4) |
| 62-73s | export file list, rights, no-upload | not measured | depends on 47-62 |
| 73-82s | sourced visual, **audio**, text alternative | **no audio asset** | the bundled Japanese pack's own preview states "No audio is bundled, so no listening evidence is claimed and no voice is certified" |

The in-route lesson surface itself does render (`Textbook` → `Open this section`: full L0 lesson text
with romaji, a textarea, "Submit answer"). But it shows "This section's chat binding is detached.
Submit stays disabled until it is reconciled", and every start action ("Resume lesson", "Start a
fresh run", "Resume this section") ejects to `#/`. That is the demo blocker.

## 4. Defects found in this pass

| id | severity | statement | evidence |
| --- | --- | --- | --- |
| D1 | **P1, demo-blocking** | Starting or resuming a lesson from the Coursebook UI leaves `#/coursebook` for `#/`; `[data-cb-route]` unmounts, no chat session opens and no Coursebook pane is present. Reproduced 3×: course card "Resume lesson", overview "Resume lesson", textbook "Start a fresh run". | `audit/demo-gate/u05-resume-trace.json`, `u05c-attempt.json`, `u02l-lesson.json` |
| D2 | P2, truthful copy | Library empty state says "importing one needs the backend's pack import command, which this build does not have" (`desktop/plugin.js:2271`), while the header "Import pack" imports successfully on this same build (`pack.import` implemented, `runtime` 52/52). A judge reading the library would be told a capability is missing that is present. | `audit/demo-gate/u02a-library.json` vs `u02i-import-done.json` |
| D3 | P3, layout | At 460 px width with 200% text, 8 nodes clip inside the route (no horizontal document overflow). | `audit/demo-gate/u04-layout.json` |
| D4 | P3, console | React key warning on the route's empty state (`FirstRun`); it is the only console error observed on the route. | `u01-route.json`, `u02a-library.json` |

## 5. Verdict

**The four demo scenarios U01-U04 pass on `29bede7643403cd9d608499232125e6347c680dd`; the DEMO
gate is NOT MET for recording**, because D1 makes the demo's 8-34 s surface undrivable on this
build and the 73-82 s shot has no audio asset in the pack the script names. U01-U04 alone cannot
carry a recording that the script's own shots contradict.

Recording does not become possible until D1 is fixed on a new commit **and U01-U04 are re-run on
that commit**. Nothing here authorises a recording, and no recording is claimed to exist.

The one operator action that remains, separate from D1, is gateway/profile choice: this host runs one
gateway, owned by profile `default`, and `hermes gateway run --force` refuses a second one. To
record with the live chat plus the Coursebook pane in one window, Coursebook from the recorded
commit must be installed into `default` and that gateway restarted:

```
scripts/install-local.sh --home ~/.hermes/profiles/default
hermes gateway restart
```

The alternative, recording from this isolated rig, gives a window that reaches the backend remotely
(proven here on 44297) but its chat is still the host's, so the pair is only honest when both halves
run on the same profile. That choice is DeseretSaint's, not the gate's.

## 6. Re-measurement on the pane-reveal build `5b0f124` (supersedes §2-§5 for this commit)

Author: Sentinel. Fresh isolated rig, this run, this machine. The §1-§5 measurement stays as the
record for `29bede7`; this section is the status on the build that carries the D1 fix.

| Item | Value |
| --- | --- |
| Commit | `5b0f124630fab9154aef9be5751919eeb8911255` (`origin/master`), merging `13d4a75` (t_d587a007) |
| Worktree | `.worktrees/t_3589acce` (`wt/cb017-demo-gate-5b0f124`) |
| Install | `scripts/install-local.sh --home ~/.hermes/coursebook-demo-gate-5b0f124/home --source <worktree>` (fresh home) |
| Backend | `hermes serve --isolated --port 44317`, `HERMES_HOME` = fresh home, `HERMES_COURSEBOOK_SINGLE_HOME=1` |
| Backend proof | `GET /api/plugins/coursebook/runtime` → `plugin_root` = this worktree, `wire_version` 7, `contract_problems: []` |
| Desktop half | `desktop-plugins/coursebook/plugin.js` sha256 `c151974a7de0fed2662e977a001127327b3c3cf96d19a54cd49b819433f935fc` = the file in this commit |
| Window | Electron `--remote-debugging-port=9377`, own userdata, remote connection `127.0.0.1:44317` |
| Artifacts | `audit/demo-gate-5b0f124/` |

Rig note, stated so the measurement can be reproduced: in remote mode the Desktop shell resolves
desktop plugins through `GET /api/desktop-plugins/root`, which `hermes serve` does not mount, so the
shell's plugin roster was empty until the rig's own persisted enable decision
(`hermes.desktop.pluginDecisions.v2 = {"coursebook":true}` in that userdata's localStorage) was set.
That is a rig-setup step, not a product change. The course was created through the same
grant → preview → import path a learner uses (`scripts/seed-demo-course.py`): course
`crs_407fde6a258640aebce9475254904c2e`, enrollment `enr_c9011c8809ef457195a443cc3c5501ef`.

### D1 on this commit — fixed

`13d4a75` adds `revealCoursebookPane()` (feature-detects `host.revealPane`, calls it with
`coursebook:pane`) after `host.newChat` and after `host.openSession`. Measured: section
"Start a fresh run" leaves the route for `#/`, opens a chat, and reveals the pane;
`paneVisibility('coursebook:pane').get()` = `true` across 14 samples over 9.8 s, and
`shots/u08-fresh-start.png` shows the chat column and the Coursebook pane side by side
("No durable chat yet"). That is the product half of D1 closed on `5b0f124`.

### Scenario verdicts on `5b0f124`

| id | verdict | evidence |
| --- | --- | --- |
| U01 | **PASS** | sidebar "Coursebook" pointer click → `#/coursebook`, `[data-cb-destination="courses"]`, course card rendered (`u01-route.json`) |
| U02 | not re-driven this pass | prior pass on `29bede7` (`u02*`); this pass created the course via the same backend grant/preview/import path and the UI renders it (`u01-route.json`) |
| U03 | **PASS** | keyboard-only: 5 tabs to "Open Coursebook", Enter mounts the route; 18 in-route stops all `:focus-visible` and named; AX 154 named, 1 unnamed outside the route (`u03-keyboard.json`) |
| U04 | **PASS at 1440 (100%/200%) and reduced motion; narrow rows not conclusively re-measured** | 1440/16 and 1440/32: overflowX 0, 0 unnamed, 0 clipped, max transition/animation 0 s with `prefers-reduced-motion: reduce` (`u04-layout.json`). The 460 px rows aborted when the Vite dev server failed a dynamic module import (`/src/main.tsx`) and the renderer dropped the route; those rows are reported as not measured, not as a pass |

### Demo-shot verdicts on `5b0f124`

The pane surface is drivable; the chat beside it is not, because this rig has no inference provider.

| shot | verdict | evidence |
| --- | --- | --- |
| 0-8s library / pack / enroll | **yes** | U01 run; course + enrollment from the real import path |
| 8-25s chat + pane, typed check, graded attempt | **no** | chat + pane appear together (`u08-fresh-start.json`, `shots/u08-fresh-start.png`) but the shell reports `Backend: inference unavailable` and the thread stays on `Waking up default…`; with no first turn there is no stored session id, so `Submit answer` is disabled ("This section's chat binding is detached", `u09-u10-notebook-quiz.json`) |
| 25-34s correct attempt → transition → evidence | **no** | same: no bound chat, no attempt can be submitted (`u09-u10-notebook-quiz.json`) |
| 34-40s notebook save / reopen | **no** | section states "No teaching segments yet. Segments appear here after a teaching turn in the bound chat", so there is nothing to save (`u09-u10-notebook-quiz.json`) |
| 40-47s restart → identical pending objective | **no** | depends on an active binding; none can exist on this rig |
| 47-62s Parent Studio | not measured | needs generated pages and approval; not run this pass |
| 62-73s export | not measured | depends on 47-62 |
| 73-82s media / audio | **no audio asset** | the named pack declares "No audio is bundled" |

### Verdict for this section

**D1's product half is fixed on `5b0f124`; the DEMO gate remains NOT MET.** The route and the pane
surface pass, but the four learning shots are still undrivable, now because the isolated rig cannot
run inference and therefore cannot create the binding those shots require. No recording exists and
none is claimed.

### What remains for t_6a32ffe9

1. Run the same U01-U04 on the exact build installed in the default profile (the profile that owns
   the gateway), with inference available, so the chat half is real.
2. Create one active binding through the product path (fresh start + first chat turn), then drive the
   8-25 s, 25-34 s, 34-40 s and 40-47 s shots on the bound-resume path and capture DOM text,
   `paneVisibility('coursebook:pane').get()` and stills for each.
3. Re-confirm the 73-82 s row's audio asset or cut the "spoken" claim.
4. Only then update the gate to MET; recording and publishing still need DeseretSaint's approval.


## H-72 addendum — the 73-82 s audio row (2026-11-07)

Item 3 of "What remains" is done, and the two `73-82s … no audio asset` rows above are historical:
they describe the pack as it stood before H-72. The bundled Japanese pack now declares
`content/narration-polite-confession.mp3` as a `role: narration`, `audio/mpeg` file with a
Japanese/romaji/English text equivalent and an Apache-2.0 per-artifact licence, and
`bundled/packs/build_demo_packs.py` regenerates the manifest and `content_hash` from the real bytes.

The "spoken" claim was cut rather than kept. Import materializes a pack's *section text* into lesson
segments and creates no artifact or media segment for a `visual`/`narration` file, so this build has
no route that plays pack-bundled audio inside a lesson. The demo row in `docs/DEMO.md` is now the
still-and-text shot; it claims no audible playback and no listening evidence.
`docs/REVIEW_H72.md` records the tool, the voice, the licence and the exact commands.
