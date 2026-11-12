# Trunk reconciliation: `d009-course-scene` against `origin/master`

Measured 2026-11-12. Base of both lines: `715d2eac`. Master tip read as
`76cf276f` ("Merge UI-K13 follow-up (21adf23a)"). Decision-line tip: `071c8197`
(branch `d009-course-scene`, the operator checkout's detached HEAD).

Card: `t_676a2fa4`. This document is analysis only; the one thing it authorises landing is recorded
in §6, and the narrow landing is already committed as `8c8369d4` on `wt/trunk-frame-rig`.

---

## 0. Correction to the card's measurement

The card says `git cherry origin/master 071c8197` gives "41 non-equivalent commits, 1 equivalent".
That is not what the command returns:

```
$ git rev-list --count 715d2eac..071c8197        -> 42
$ git rev-list --merges --count 715d2eac..071c8197 -> 1   (f5159691)
$ git cherry origin/master 071c8197 | grep -c '^+'  -> 41
$ git cherry origin/master 071c8197 | grep -c '^-'  -> 0
```

There is **no equivalent commit**. `git cherry` reports 41 `+` and zero `-`; the 42nd commit in the
range is the merge `f5159691` ("Merge UI-K7 …"), which `git cherry` skips because it carries no patch
of its own. So the true finding is stronger than the card states: **none of the 41 patches is on
master by patch-id.**

## 1. What master actually is

Master is the wave-2 backend line plus UI-K13. Its first-parent history since the base is 148 commits,
mostly merges of `wt/w2-*` and `wt/ui-k13-master`, plus evidence re-derivations. The decision line is a
design/UI line off the same base and was never merged back. The two lines touched the same files
heavily and independently:

```
$ git diff --stat origin/master 071c8197 -- desktop/src
 90-course.js    |  ...  95-studio.js | ...  96-workshop.js | ...  99-tutor.js | ...
```

The splits are in different places, not just different content: master carries wave-2 backend work
(cb.rpc v27, lesson truth, plan truth, source ledger, figures/print, repair verdict) that the decision
line does not have, and the decision line carries the D-009b/D-010/D-011/D-012 route work that master
does not have. A merge of the line into master is therefore a real conflict resolution, not a
fast-forward, which is why §7 proposes an order instead of a merge.

### 1a. The decision register is not keyed uniquely

Both lines hold `docs/launch/UI-DECISIONS.md`, and **`D-009` means two different rulings**:

| id | master | `d009-course-scene` |
|---|---|---|
| D-009 | "wave 1 landed the kit on four surfaces; the capture door is the open gate" | "the approved plate is the page, not an inserted image" (owner ruling 2026-11-11) |
| D-010 | absent | "a module-rendered proof stands in for a host frame" (owner ruling ~13:05) |
| D-011 | absent | "a game view is an environment, not an image above text" (owner ruling 13:30) |
| D-012 | absent | Courses / Create / Parent Studio open in one destination shell |

`D-007` appears **twice in both files** with different text ("the approved field_atlas@2 kit goes
live" and "the approved kit is the live product lane"). That duplication predates the split and is a
shared defect, but it means the file cannot be merged by id: landing the line's decisions as written
would produce two `D-009` sections with contradictory meanings. Whoever lands §7 must first allocate a
fresh number for the line's D-009 (D-013 is the next free id) and de-duplicate D-007. That allocation
is an owner-visible decision and is not made here.

### 1b. The operator's installed app has never shown these decisions

`~/.hermes/desktop-plugins/coursebook/plugin.js`, mtime 2026-11-12 05:59:43, sha256
`0b76b2878bac…` — byte-identical to the reproducible build of `origin/master` at `76cf276f`
(`python3 scripts/build_plugin.py` on a clean master worktree produces that hash).

So the window the owner has been reviewing is master's build. Since master does not carry D-009b,
D-011, D-012 or the UI-K7 route work (§2), **nothing the owner approved on that line is in the app he
is looking at.** Every composition review done in a window since 2026-11-11 has been a review of the
pre-decision UI. That is consistent with the reason the frame rig exists at all.

## 2. Method, and what it can and cannot prove

Each of the 41 commits was measured per file, not judged by subject line:

1. Tokens *introduced* by the commit in a file = identifiers (≥8 chars), quoted literals (≥20 chars),
   and `--cb3-*` / `data-cb-*` / `.cb3-*` custom properties that were not in the file at the base.
2. `tip%` = share of those tokens still present in the same file at `071c8197`. Low `tip%` means a
   later commit on the line rewrote the work, i.e. the commit is superseded.
3. `master%` = share present in the same file at `origin/master`.

`desktop/plugin.js` and `desktop/cb-assets.generated.js` are excluded: they are build products of the
files above and comparing them compares the build, not the change. Binary captures, `audit/` and
`.coursebook/` are treated as evidence artefacts, not code.

**Limit, stated plainly.** Token presence is lexical. A behaviour that master reached by a different
route, under different names, reads as "absent". Nothing in the 41 commits reads as absorbed
(`master%` ≤ 0.14 everywhere, and those residues are generic identifiers like `plural` and
`workshopFactRows` that exist on both sides). I corroborated the largest claims structurally rather
than lexically:

* `CbDestinationShell` — 0 occurrences on master (`85-v3-primitives.js`, `95-studio.js`); it is the
  D-012 shell. D-012 is genuinely absent.
* `weekLabel` / `restated` — 0 occurrences in master's `62-syllabus-surfaces.js`; master's
  `SyllabusWeekRow` still renders `Week ${ordinal.text}` next to `label.text`, i.e. the UI-K14a
  "Week 1 Week 1" defect is live on master.
* `data-cb-courses-head` — 0 on master.
* A real frame of master's `CourseHomeV3` (§5) shows the 3:1 plate insert and the disc rail, which
  are exactly what D-009 and D-009b replaced.

## 3. Dispositions

`must-land` = the final content of the line is not on master and encodes an owner ruling or a product
surface master does not have. `superseded` = a later commit on the same line replaced it; the pointer
is the replacement. `on-master` = already present by content.

There are **no `on-master` dispositions**. Three commits are `superseded`. Thirty-eight are
`must-land`, six of which are already landed in `8c8369d4` (§6).

| # | commit | subject | disposition |
|---|---|---|---|
| 1 | `b38f2b18` | D-009: the approved plate is the course home's page | must-land — D-009 ruling; `90-course.js`, `76-v3-scope.js`, `UI-DECISIONS.md`, `test_cp_024` |
| 2 | `fd1f5769` | D-009b: the course route is a paper column of ink | must-land — D-009b ruling; the disc rail master still ships |
| 3 | `843a9d9f` | D-009b: re-pin proof pages and CP-053 measurement | must-land for `design/*.html`; `docs/concept-parity/cp053/measure.json` superseded by `bca99073` |
| 4 | `260eeb5f` | D-009b: re-run the M4 visual audit | **superseded** — evidence only (`audit/visual/m4-visual/audit.json`); re-derived by `bca99073` and re-run per build on master (`945f6e12`, `618ac5c6`) |
| 5 | `70cdb6b6` | D-010: a module-rendered proof stands in for a host frame | must-land — owner ruling; the rule that governs every review |
| 6 | `085f8b0a` | A frame of the module, not a window + the fleet rule | **landed** in `8c8369d4` |
| 7 | `d92bc52d` | Record the limit the module frame does not cover | **landed** in `8c8369d4` |
| 8 | `84b6d972` | cb-frame: lesson surfaces from the pack's own content | **landed** in `8c8369d4` |
| 9 | `ed15ab54` | Every Field Quest mission is imaged | must-land — `80-components.js`; revised by #10 |
| 10 | `50db59fb` | …(clean stacked layout) | must-land — the final layout |
| 11 | `4b517752` | D-011: a game view is an environment | must-land — D-011 ruling |
| 12 | `2da8195d` | D-011: the Home heading sits on paper | must-land — `76-v3-scope.js`, `design/home-scene.html` |
| 13 | `fded9458` | film3: an admissible still set with provenance | must-land for `scripts/film3-manifest.py`; the 22 captures are stale evidence, re-render after landing |
| 14 | `e461d0de` | Land the film gap audit | must-land — `docs/launch/FILM-GAP-ANALYSIS.md`, absent on master |
| 15 | `619a96b7` | film3: crop the Discover frame | **superseded** — evidence only; `manifest.json` replaced by `0af546c8`'s re-render |
| 16 | `ba650253` | D-009/UI-K7: the lesson room is the page | must-land — `70-learning.js`, `76-v3-scope.js`, `80-components.js`, two tests |
| 17 | `89c1d0a7` | film chat instruction | must-land — `docs/launch/FILM-CHAT-PROMPT.md`, absent on master |
| 18 | `c7749155` | D-011: covers take a per-course crop and zoom | must-land |
| 19 | `54d81ecb` | D-011: the Home heading is a left-anchored label | must-land — revised by `94ab0073`, `48540a49` |
| 20 | `adaa34e4` | cb-frame: paint the frame body with the deck canvas | **landed** in `8c8369d4` |
| 21 | `924df968` | D-009/UI-K7 round 2 | must-land — paper evidence card, contained aside, rust primary |
| 22 | `94ab0073` | Home: the owner's five removals | must-land — owner decision, `30-home.js` + `design/home-scene.html` |
| 23 | `0af546c8` | cb-frame: absolute html path + merged rows | **landed** in `8c8369d4` |
| 24 | `2744475c` | classroom: the scene is not a rounded card | must-land — `76-v3-scope.js`; `border-radius: 0` absent on master |
| 25 | `a2c09d79` | Wiring ledger + store import door | must-land — `docs/launch/WIRING-LEDGER.md` absent on master |
| 26 | `d67f9282` | cb-frame: photograph every route destination | **landed** in `8c8369d4` (incl. the four 99-tutor exports it needs) |
| 27 | `d8831f17` | game ledger writer; destination frames render again | must-land — `coursebook/domain.py`, `coursebook/engagement.py`, `test_game_engagement.py` |
| 28 | `ce5a73bd` | Courses speaks the v3 system | **superseded** by `3cf18d3e` — the D-012 shell replaced the `data-cb-courses-head` h2 with `CbDestinationShell` |
| 29 | `1f2637db` | Create speaks the v3 system; frame page rhythm | **landed** for `scripts/cb-frame-render.mjs` + `cb-frame.py`; `50-create.js` must-land |
| 30 | `7decfebd` | One destination shell; Parent Studio moves onto it | must-land — `85-v3-primitives.js` |
| 31 | `3cf18d3e` | D-012: Courses, Create, Parent Studio in one shell | must-land — D-012 ruling |
| 32 | `c7a3e705` | UI-K14a: the syllabus week row names the week once | must-land — **see §4**; this was reported fixed and never reached master |
| 33 | `ebcc64a8` | Rows, not bands: cover thumbnails, one next step | must-land — `coursebook/domain.py`, `20-packs.js`, `95-studio.js` |
| 34 | `9a0a8757` | Four backend doors get a control | must-land — review actions, syllabus removal, pronunciation disputes, usage; two new tests |
| 35 | `9f1a6e28` | One primary, one shell for intake | must-land — `62-syllabus-surfaces.js`, `80-components.js` |
| 36 | `2117c775` | Homework and take-home wear the shell | must-land |
| 37 | `8fc27a82` | The parent brief is a paper form | must-land — `95-studio.js` |
| 38 | `bca99073` | The sheets are flat paper; proof re-pinned | must-land |
| 39 | `48540a49` | The shelf has two panes; companion on the floor | must-land |
| 40 | `ce7e7725` | The empty profile speaks at display size | must-land |
| 41 | `071c8197` | The shelf names only courses the packs actually carry | must-land |
| — | `f5159691` | Merge UI-K7 with the Home label and fox placement | merge only — no disposition of its own |

## 4. Two defects this reconciliation surfaced

**UI-K14a is not fixed on master.** Card `t_f015ea64` completed on 2026-11-11 claiming the
"Week 1 Week 1" defect was fixed at `c7a3e705`. `c7a3e705` exists only on `d009-course-scene`; master's
`SyllabusWeekRow` has no `weekLabel`, no `restated` regex, and still renders the ordinal heading and
`label.text` independently. The completion was true of the checked-out branch and false of the tree
that ships. Any card that reports a commit sha must name the branch that sha is merged into.

**Gate 5's evidence lives on an unmerged line.** Card `t_10bd16ac` completed at `c303a7d5` — also on
this line, 43 commits ahead of master — so the "Gate 5 reaches 5/5 with 16 installed cells captured"
result was measured with the frame rig, which master did not have. With the rig now on trunk (§6),
that measurement is reproducible on master; without it, it was not.

## 5. Evidence: what a frame of master's course home looks like

`python3 scripts/cb-frame.py --component course-home --width 1344` on a clean `origin/master`
worktree (`8c8369d4` adds nothing visual; this is the same render before and after) writes a frame
whose manifest carries:

```json
"module_sha256": "0b76b2878bac73173aaa936c6a7c29ede52644c834ee0ecfae8eff98ac2557a1",
"installed_module_sha256": "0b76b2878bac73173aaa936c6a7c29ede52644c834ee0ecfae8eff98ac2557a1",
"installed_matches_branch": true,
"frame_height": 1169
```

The image shows the 3:1 plate insert inside a page, the vertical rail of objective discs with the
`H` Codicon stand-in glyph, the fox seated bottom-right — i.e. the layout D-009 and D-009b were
issued to replace. It is a genuine render of master, so it is also the first artefact on trunk that
lets a reviewer say *what master is* without opening a window.

## 6. What landed, and why only this

Commit `8c8369d4` on `wt/trunk-frame-rig`, branched from `origin/master` at `76cf276f`:

| file | provenance |
|---|---|
| `scripts/cb-frame.py` | blob `c3333cc55a6d`, identical to `071c8197` |
| `scripts/cb-frame-render.mjs` | blob `38179a781825`, identical to `071c8197` |
| `scripts/cb_frame_fixtures.py` | blob `26c9a4630914`, identical to `071c8197` |
| `tests/test_cb_frame_destinations.py` | blob `14903b56223b`, identical to `071c8197` |
| `docs/launch/VISUAL-REVIEW-RULE.md` | the rule, its known limit, and (added here) the three checkout requirements that were implicit |
| `desktop/src/99-tutor.js` | **the only product-code change**: 4 export names |
| `desktop/plugin.js` | rebuilt from that one edit |

Byte identity was checked with `git hash-object` against `git rev-parse 071c8197:<path>`, not by eye.
Taking the files at the *tip* rather than replaying `085f8b0a`…`0af546c8` folds five in-line
refinements into one landing without carrying their conflicts.

**The `design/*.html` hypothesis in the card is wrong.** `cb-frame.py` reads no `design/*.html`; it
writes its own staging HTML into the output directory. `design/home-scene.html` and
`design/fox-adoption.html` already exist on master (different content, produced by
`scripts/gen-home-proof.py`, which master has). Nothing was taken for them.

**`scripts/vq-capture.*` needed nothing.** `vq-capture.mjs` and `vq-capture.sh` are byte-identical on
both lines already.

**One real dependency, four names wide.** `tests.test_cb_frame_destinations` asserts that every
surface the destination registry mounts is exported by the shipped module. Master *defines* all four —
`CourseDetail` in `90-course.js`, `StudioList`/`StudioDetail`/`StudioBriefForm` in `95-studio.js` —
but `99-tutor.js` does not export them, so `courses-detail` and the three `studio-*` frames could not
mount the shipped component and the test failed. Adding the four names is additive, changes no route
or behaviour, and is the minimum that makes the registry honest. Without it the cherry-pick is not
possible; with it, it is — so the card's option 3 (refuse and propose dependencies) does not apply.

### Acceptance, measured on `wt/trunk-frame-rig` at `8c8369d4`

```
$ python3 scripts/cb-frame.py --preflight
branch plugin.js   d6d85566fde0a4b79b9c0a04e965ec39e0458e9b227fc448727671258f33ddd5
installed plugin   0b76b2878bac73173aaa936c6a7c29ede52644c834ee0ecfae8eff98ac2557a1
src builds clean   True
REFUSE a window review: the installed module is not this checkout's build.
-> exit 1   (correct: the four-name export edit moved the module hash)
```

`--preflight` asserts a *host* fact (installed file == this checkout's build), not a code fact. On
unmodified `origin/master` it exits **0**, because master's build is what was installed at 05:59. On
the landing branch it exits 1 until the new build is installed. Verified both ways:

* unmodified `origin/master` → exit 0, `0b76b2878bac` on both sides;
* `8c8369d4` with `desktop/plugin.js` temporarily installed → exit **0**, then the operator's
  original file restored and re-verified at `0b76b2878bac`. The operator's install was not left
  changed.

After merging, the supervisor must run:

```
python3 scripts/build_plugin.py
cp desktop/plugin.js ~/.hermes/desktop-plugins/coursebook/plugin.js   # then restart the app
python3 scripts/cb-frame.py --preflight        # now exits 0
```

The frame capture itself does not depend on the install:

```
$ python3 scripts/cb-frame.py --component course-home --width 1344 900
-> exit 0, two frames written, each manifest carrying module_sha256,
   installed_module_sha256, installed_matches_branch
```

`--width` is `nargs='+'`, so `1344 900` is **two widths, not width and height**; the rig has no height
flag and sizes the frame to its content (`frame_height`). Both frames are valid; if a 1344×900 crop was
intended, that is a rig feature that does not exist yet and is not invented here.

## 7. Dependency order for the rest of the line

Do not merge `d009-course-scene` wholesale. Land in this order, each as its own reviewed branch off
master, because each later step compiles against the earlier one:

1. **Docs and decisions** — `UI-DECISIONS.md` (§1a: renumber the line's D-009 to D-013, de-duplicate
   D-007 first), `VISUAL-REVIEW-RULE.md` (done), `WIRING-LEDGER.md`, `FILM-GAP-ANALYSIS.md`,
   `FILM-CHAT-PROMPT.md`. Zero code conflict; gets the rulings on trunk.
2. **Frame rig** — done in `8c8369d4`. Unblocks reproduction of every later visual claim.
3. **Token/CSS layer** — `76-v3-scope.js` from D-009/D-009b/D-011 (`b38f2b18`, `fd1f5769`,
   `2da8195d`, `2744475c`). Master has diverged here, so this is a real three-way merge; it is the
   gate for every route change below.
4. **Primitives and shell** — `85-v3-primitives.js` `CbDestinationShell` (`7decfebd`), then D-012's
   route adoption (`3cf18d3e`), then the surface rewrites built on the shell (`ebcc64a8`,
   `9f1a6e28`, `2117c775`, `8fc27a82`, `bca99073`, `48540a49`, `ce7e7725`, `071c8197`).
5. **Learning surfaces** — `70-learning.js`/`80-components.js` mission imaging and the UI-K7 lesson
   room (`ed15ab54`, `50db59fb`, `ba650253`, `924df968`), with `4b517752`'s game-view ruling.
6. **Backend seams** — `d8831f17` (game ledger writer) and `ebcc64a8`'s `domain.py` change, then
   `9a0a8757`'s four doors, then `c7a3e705` (UI-K14a). Last, because they add controls that call
   routes which must already exist.
7. **Evidence regeneration** — re-run every proof, `m4v-audit`, CP-053 measurement and the film3
   stills **after** step 6, so the committed evidence names the merged module. The 22 film3 captures
   and the M4 audit on the line are stale by construction (they name a module master never built).

Per-file conflict risk, from `git diff --stat origin/master 071c8197`: `90-course.js`, `95-studio.js`,
`96-workshop.js`, `99-tutor.js` are the four files both lines rewrote most; schedule steps 3–4 and 5–6
so no two branches are open on the same file at once. `99-tutor.js` in particular will conflict on the
export block for every remaining step — that is the hotspot, and `8c8369d4` is the first change to it.

## 8. What is still not true after this landing

* Master still ships the pre-D-009 course home, the disc rail, the rounded classroom card, no
  destination shell, and the UI-K14a double week label. Only the *instrument* is now on trunk.
* The owner's installed build is unchanged and still master's. He is still looking at the pre-decision
  UI until step 3–4 of §7 lands and he reinstalls.
* `D-009` remains ambiguous across the two files until §1a is resolved by the owner.
