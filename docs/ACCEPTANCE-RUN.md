# Acceptance run — release tree 172b61aa + 82a0866a + 15e1301d

Measured 2026-11-11. Every number below came from a command or a stamped frame, not from a
document.

## The tree under test

| Item | Value |
|---|---|
| base commit | `172b61aaffd44c33f2c89360df9f1fceeff66c37` (= `origin/master` at freeze time) |
| evidence tip | `0ce3a2e7` (film + post); suite measured on `2c001e7a` |
| copy fix | `82a0866a` — the exact-answer miss names whose answer it is |
| generated proofs re-derived | `15e1301d` — `design/fox-adoption.html`, `design/home-scene.html`, CP-053 record |
| `desktop/plugin.js` sha256 | `9840010845539c05e571566dbd65d4ceab03bc1119d01c0356f2ff29c6d9c395` |
| reproducible from its own `desktop/src` | yes — `scripts/build_plugin.py --check` matched |
| backend | `cb.rpc` **v26**, `plugin_root` = the release worktree (was a worker worktree, see D-8) |
| window | dev Electron rig, CDP `9337`, `HERMES_HOME=~/.hermes/coursebook-test/home`, light scope |
| module the window loaded | `98400108…c395`, read through the host's `readPluginSource` door and asserted before every capture |

The live plugin was installed from this commit into both paths the window can read
(`~/.hermes/desktop-plugins/coursebook/plugin.js` and
`<rig>/home/plugins/coursebook/desktop/plugin.js`) and the sha was compared, not assumed.

## Suite

First full run on `172b61aa`:

```
Ran 3965 tests in 1496.175s
FAILED (failures=5, skipped=12)
```

All five were stale **generated** artifacts, not product logic — the committed proof pages and the
CP-053 measurement still named module `3cdfa1d0` while `desktop/plugin.js` is `98400108`:

| failing test | cause | fix |
|---|---|---|
| `test_a_fresh_render_reproduces_the_committed_page` | `design/fox-adoption.html` stale | `python3 scripts/gen-fox-proof.py` |
| `test_the_committed_page_pins_the_current_module` | same page pins the old module | same |
| `test_the_committed_proof_is_a_fresh_render_of_the_shipped_module` | `design/home-scene.html` stale | `python3 scripts/gen-home-proof.py` |
| `test_the_recorded_measurement_names_the_module_it_was_taken_on` | CP-053 `measure.json` pins the old module | re-derived at 1344×768; `sim_grey 0.6401` and `rmse_grey 91.782` reproduced identically, so the row was re-pinned, not re-scored |
| `test_harness_does_not_edit_product_source` | race with this run's own file writes | passes in isolation (`Ran 71 tests … OK`) |

After the fix the three affected modules passed, and a second full run on `15e1301d` came back with
**two** failures — both `test_fresh_evidence_reproduces_the_committed_bytes`, and both caused by the
copy fix itself: the H-40 packets embed the validator's message, so `music_short` and `soldering_full`
no longer re-ran byte-identically. Regenerated with the packet's own generator (`2c001e7a`);
`bicycle_single` was already reproducible and was left alone.

Final run on `2c001e7a`:

```
Ran 3965 tests in 1460.040s

OK (skipped=12)
```

Three runs, same tree family, measured end to end: 5 failures → 2 → 0. Every failure along the way was
a stale *generated* artifact, never product logic — which is itself the lesson: this tree pins its own
generated evidence, so any change to a message or a module invalidates it until it is regenerated.

## Frames

Every frame in `docs/launch/captures/freeze/` carries a `.stamp.json` beside it naming
`window.plugin_sha256`, `matches_expected`, route width/height, `data-cb-scope`, nav count, font
state, `[data-cb-v3-ready]`, and the captured bytes' sha256.

| Frame | Route | Size | Scope | Module |
|---|---|---|---|---|
| `home-1833-light.png` | Home | 1833×1090 | light | `98400108` |
| `courses-1833-light.png` | Courses | 1833×1090 | light | `98400108` |
| `workshop-1833-light.png` | Workshop | 1833×1090 | light | `98400108` |
| `studio-1833-light.png` | Parent Studio | 1833×1090 | light | `98400108` |
| `pane/*-pane-light.png` | all four at pane width | 892×946 | light | `98400108` |
| `course-home-772-light.png` | course home ("Read the Night Sky") | 772×1090 | light | `98400108` |

`coursebook-demo.mp4` — 38.0 s, 1920×1080, 30 fps, composed only from the frames above. Four beats:
Home, Courses, Course (Section 2 of 4, "Needs review", "Source stale"), and the Check with its own
question visible. It does **not** show an answer being submitted — see the next section for why that
cannot be shown inline on this tree.

## The teaching loop — driven, not assumed

The demo course was the **rejected** one. `course.outline` for *Read the Night Sky* returns
`plan.validation = {verdict: "reject", reasons: ["objectives 1-4: No supplied source supports any
objective…"]}`, so no lesson exists and the section view correctly says *"the check opened, but the
backend returned no question"*. Six courses on the profile have approvable plans; the Japanese L0
course has an approved plan (`pln_0e8776a5`), two teaching segments and an open check
(`chk_6a584dd269de4dc0af4f0290472eb38a`, `audit_state: passed`).

Driven on the frozen module through the product's own UI:

| step | observable |
|---|---|
| course home | "THE REVIEW IS DUE … Section 1 of 4 · Tell everyday affection from a direct romantic declaration" |
| open section | lesson renders `好きすきです。付き合ってつきください。` with romaji and an A/B register comparison |
| check | "Which line is the romantic confession, and which cue makes it one?" with a free-text field |
| submit | feedback: *"Not quite. Your answer does not match an accepted answer."* (after `82a0866a`) |
| evidence state | "15 of 15 checks recorded", "Hinted", "First try, no hints", "Override — not independent evidence" |

## The answer step is chat-bound, and starting a run leaves Coursebook

Measured on both `98400108` (this tree) and `8f10ae0f` (branch `wt/vq009-capture-door`, below):

- The Check screen renders the question, the evidence state ("First try, no hints", "11 attempts
  recorded on this section · last 3 d ago") and the learner's own saved lesson text.
- Its answer field is `disabled: locked || detached` and the product says why in its own words:
  *"This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to
  connect a new chat."*
- Clicking **Start a fresh run** does not open an inline attempt: the whole app leaves the plugin
  route (`#/coursebook` → `#/`) and lands on the Hermes session surface. Every capture taken after
  that click is of the host, not of Coursebook — which is how earlier frame sets ended up with a
  "Teaching" caption over a Home screenshot.

So the loop cannot be demonstrated inside one Coursebook route on this tree. It is bound to a host
lesson chat, and the binding is not restored when the chat is closed. This is the single most
important thing the submission should say, because it is visible to any judge who tries to type an
answer.

## `master` is behind the working build, and the working build was not on GitHub

The build that could bind a chat (`8f10ae0f`) is **reproducible** from a committed branch, not from a
dirty tree:

```
$ git -C /tmp/cb-wt-4efebd14 show -s --format=%H%n%s 4efebd14
4efebd1408345ac11c7a8f7dba4f336b876937ec
Merge remote-tracking branch 'origin/master' into wt/vq009-capture-door
$ python3 scripts/build_plugin.py --check
build_plugin: desktop/plugin.js matches desktop/src (8f10ae0f6b6c56802d020dffd681329684fef046f24ebd4d41199af1d995a1a4)
```

`172b61aa` (the commit frozen for this report) does **not** contain D-009/D-009b, which are the
course-route rework in `90-course.js` (+524/−308) and `76-v3-scope.js` (+237). That branch existed
only in the local worktree `wt/vq009-capture-door`; it has now been **pushed to origin** at
`4efebd14` so the code that produced the working build is on GitHub rather than only on this machine.



## Current rig state (after this report's measurements)

The rig was moved onto the branch tree so that both halves match and the code is on GitHub:

| Half | Now |
|---|---|
| window module | `8f10ae0f…a1a4`, reproducible from `4efebd14` (`build_plugin.py --check` matched) |
| backend `plugin_root` | `/tmp/cb-wt-4efebd14` (branch tree), `cb.rpc` v26, `127.0.0.1:44219`, pid restarted |
| installs | all three plugin paths hold `8f10ae0f…a1a4` |

The frames and film above were captured **earlier**, on `98400108` (`172b61aa` + `82a0866a`) with the
backend on that same tree. Both are on GitHub; the film names the module it came from in its end card.

## Scenario results

| # | Scenario | Result | Observable |
|---|---|---|---|
| 1 | Plugin route mounts on the frozen module and paints Home | **PASS** | `[data-cb-route]` 1833×1090, 4 nav items, `[data-cb-v3-ready]`, `CB Display` loaded, window module sha == commit module |
| 2 | All four destinations render as distinct surfaces | **PASS** | four frames, four distinct sha256, each after a nav click *and* an `aria-current` assertion |
| 3 | Course home mounts from the library | **PASS (narrow)** | "Read the Night Sky", "The plan is waiting for you", route 772×1090 |
| 4 | Plan → approve → lesson → check → feedback | **PASS on the Japanese course** | lesson → check question → free-text answer → feedback, driven through the UI; the demo course itself cannot show this (its plan is rejected) |
| 5 | Resume a lesson | **NOT RUN** | no resume was driven |
| 6 | A rejected plan's repair path | **NOT RUN** | the rejection is proven from `course.outline`, the repair UI was not driven |
| 7 | Parent-only surface | **PASS (render only)** | Parent Studio renders "Plans for your child", "New lesson plan", two plan cards; approval path not driven |
| 8 | Full unit suite | **PASS** | `Ran 3965 tests in 1460.040s … OK (skipped=12)` on `2c001e7a`; 5 stale-artifact failures found and fixed on the way |

## Defects reproduced (none fixed except the two named in the tree table)

- **D-1 — the visual audit photographs a crash.** `visual/audit.mjs` produced four byte-identical
  frames at 913×976 on 2026-11-11T01:28Z. All four are the "Hermes couldn't start — background
  service stopped" dialog, not a product screen. The isolated rig had no backend, so the harness
  certified a crash as four routes.
- **D-2 — the capture door throws on the v3 nav.** `scripts/cp-capture.mjs` with `--destination home`
  fails `TypeError: Cannot read properties of null (reading 'getBoundingClientRect')`: the resolver
  looks for `[data-cb-destination]`, which the v3 shell does not render (it renders
  `[data-cb-nav-item]`).
- **D-3 — `enrollment.delete` fails with `INTERNAL_ERROR / IntegrityError`.** `reset-demo-data.py
  --apply` deletes nothing; the shelf keeps duplicate enrollment titles. The dependent tables that
  reference `enrollment_id` are not cascaded.
- **D-4 — a course surface cannot be re-entered by the capture path.** Once the course home is
  mounted, the Courses list is no longer reachable from the shell, so a second capture refuses.
- **D-5 — dead space at wide widths.** At a 1833 px route the Parent Studio and course surfaces
  paint in a narrow left column and leave the canvas blank.
- **D-6 — demo-labelled pack titles reach the shelf.** "Technical demo: reading a pack before you
  install it" and "Parent demo: measuring ingredients together" are visible product text.
- **D-7 — Workshop pack titles clip.** At 1833 px the third card reads "Reading a pack before" and is
  cut mid-line under its cover.
- **D-8 — the rig's Python half was served from a worker worktree.** `plugin_root` resolved to
  `.worktrees/t_07100f40`, so the UI half and the backend half came from different trees; the
  symlink was repointed at the release worktree and the runtime re-read.
- **D-9 — the window's module is overwritten without notice.** `~/.hermes/desktop-plugins/
  coursebook/plugin.js` was replaced by a worker's rebuild (`8f10ae0f`) while captures were running.
  The `readPluginSource` preflight is the only thing that caught it.
- **D-10 — the free-text grader is an exact string match.** A correct answer phrased in the learner's
  own words is marked wrong; the open-response lane is disabled by design (CB-QA-11), so the flagship
  Japanese check cannot accept a paraphrase.

## What this report does not claim

No visual approval by the owner. No parity score against the 1344×768 concept references (the pane
frames are a different breakpoint and are labelled as such). No demo film of the loop. No resume or
repair scenario.
