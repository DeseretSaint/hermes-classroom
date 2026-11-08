# The story gaps this pass could not close

Every entry below was produced by a command on 2026-11-08 in this worktree
(`wt/h181-story`, base `f65154c`) or against a live rig, and every entry is still open. Nothing here
is a limitation of the wording: the README, the catalog entry and `docs/HACKATHON-DEMO.md` are
written to the truth as it stands, and these are the rows where the truth is not good enough yet.

## G1 — No license (owner decision, gate 9)

`ls LICENSE*` → no such file. The decision is `t_6f2d2080`, assigned to Atlas and **blocked on the
owner**: MIT, Apache-2.0, or ship without. This pass did **not** add a license and did **not** pick
one. The catalog entry keeps the open license row and says so; `docs/SUBMISSION.md` gate 9 stays
`[ ] owner decision`. Nothing in the README or the listing claims a license or a redistribution right.

## G2 — The demo profile is polluted, and there is no one-command reset that clears it

`~/.hermes/coursebook-test/home/plugin-data/coursebook/data.db` holds, among others:

| Row | Rows | Why it cannot appear on camera |
| --- | --- | --- |
| `H103 live reject check`, `H103 live failure check` | 2 | debug fixtures |
| `Parent demo: measuring ingredients together` | 1 | labelled "demo" |
| `Japanese affection and register — an L0 demonstration classroom` | 3 | "demonstration" + debug level in the title |
| `Kitchen fractions for a 9-year-old` | 13 | a parent-mode stress fixture, repeated |

`scripts/reset-demo-data.py` collapses duplicate **enrollments** through `library.list` /
`enrollment.delete`; it does not remove debug-authored courses, and it is a dry-run operator script,
not a reset button. There is no script that produces "exactly one Sample classroom and nothing else"
in one command. Building that is a separate card (it owns the seed path, not the story).

## G3 — The bundled demo pack imports 0 checks, so the ledger beat cannot be shot

The clean copy of the Sample classroom home was re-seeded through the product path on this pass:

```
python3 scripts/seed-demo-course.py --base-url http://127.0.0.1:44791 --token ***
already seeded: japanese-affection-context-l0
  enr_1eaf2f5f18e347568120f6529f3857a8  Japanese affection and register — a Sample L0 classroom
```

Then, from that home:

```
sqlite3 plugin-data/coursebook/data.db "select count(*) from checks"      -> 0
sqlite3 plugin-data/coursebook/data.db "select count(*) from objectives"  -> 4
sqlite3 plugin-data/coursebook/data.db "select count(*) from attempts"    -> 0
sqlite3 plugin-data/coursebook/data.db "select count(*) from transitions" -> 0
```

`bundled/packs/japanese-affection-context-l0/pack.json` declares its checks; import materializes the
objectives and **zero checks**. No check means no attempt, no verdict, no transition and no evidence
row — that is segments 5–9 of the 88-second script. This is a pack/import defect, not a wording
problem, and it is not on this card's surface to fix.

## G4 — Package hygiene: the doctor invocation, not (only) the package

The functional audit's finding reproduces exactly:

```
$ hermes plugins doctor coursebook          # from the checkout root
  ERROR: .../coursebook holds no plugin manifest (plugin.yaml, plugin.yml, plugin.json),
  and 'coursebook' is not an installed plugin id. Point Doctor at a plugin directory.
  registrations: 0 tool(s), 0 hook(s)
```

The bare id is resolved as the `./coursebook` **Python package directory**, which has no manifest.
Pointed at the package root it passes:

```
$ hermes plugins doctor .
  manifest: coursebook 0.1.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 2 tool(s), 3 hook(s)
```

So "0 registrations" is an invocation trap, and every install/verify doc that tells a reader to run
`hermes plugins doctor coursebook` steers them into it. `scripts/install-local.sh` runs the gates on
an export and reports `registrations: 1 tool(s), 3 hook(s)`; this pass measured 2 tools at the
package root. The two counts differ because the export is narrower than the checkout, and neither is
zero. **Fix owed:** docs say `doctor .`; the audit's `.chromium/SingletonLock` failure did not
reproduce here because there is no `.chromium` directory in this worktree
(`find … -maxdepth 3 -name .chromium` → empty).

## G5 — The screenshot set is not captured, so the listing shows the pinned 0.1.0 frames

Required: Home trailhead, path, lesson/check, integrity chip, export/handoff, at 1280×1049 and 460,
each labelled with its commit and live/rendered. Not produced. The blockers are G2 + G3 plus the one
gateway (CB-QA-09): a clean rig was built for this pass
(`~/.hermes/coursebook-test-h181`, backend `127.0.0.1:44791`, `cb.rpc` v17, 68 methods, plugin root
= the H-176 worktree) and its Coursebook API answers
`{"backend_package":"coursebook_plugin_backend", …, "wire_version":17}`, but the Desktop shell on
that home stays on **`Backend: checking`** and never renders the route, so no frame can be taken.

The listing therefore keeps the 0.1.0 asset set, repaired to a commit that exists (G6). Those frames
are real captures, not renders, but two of them are visibly imperfect and must be replaced when G2/G3
close: `readme-overview-light.png` shows the debug course title `…— an L0 demonstration classroom`
and a developer status strip with an IP address and a username. That is disclosed here rather than
cropped out.

## G6 — The catalog pin is still 126 commits behind, and the final commit is not named

`catalog/coursebook.yaml` pins `1ba8ec6`. `git rev-list --count 1ba8ec6..origin/master` → **126**.
The entry cannot be re-pinned to "the final commit" because no final commit exists: this branch is
unpushed, H-176 (`2b0324e`) and the H-186 demo pack (`1c223cc`) are unmerged, and publication is
gated by `docs/SUBMISSION.md` §0. Re-pinning today would pin a commit that is not on the remote —
the exact defect being repaired. What this pass did fix: `image` and all six `screenshots` pointed at
`f5b8463…`, which is **404** on the remote; they now point at the pinned commit, where every file
exists (see G7 for the check).

## G7 — Asset URL check at the pin

`curl -I` against `raw.githubusercontent.com/DeseretSaint/hermes-classroom/1ba8ec62…/docs/assets/<file>`:

| File | HTTP | Used by |
| --- | --- | --- |
| `readme-overview-light.png` | 200 | catalog `image`, README cover |
| `readme-overview-dark.png` | 200 | catalog screenshot 1 |
| `readme-library-dark.png` | 200 | catalog screenshot 2 |
| `readme-textbook-dark.png` | 200 | catalog screenshot 3 |
| `readme-lesson-pane-dark.png` | 200 | catalog screenshot 4 |
| `readme-notebook-dark.png` | 200 | catalog screenshot 5 |
| `readme-parent-studio-dark.png` | 200 | catalog screenshot 6 |
| `readme-quiz-in-progress.png` | 200 | not used |
| `readme-quiz-results.png` | 200 | not used |

The old pin `f5b8463…` returns **404** for the same path — that is the defect this pass repaired.

## G8 — The judge scan test has no independent human reader in this run

Required: a reader who has not seen the repo, ten seconds, three answers. This run has no human
available (headless kanban worker), and an agent that has read the repository is not an independent
reader. What is recorded instead, in `docs/JUDGE-SCAN.md`: the exact text a reader sees in the first
ten seconds, and whether each of the three questions is answerable from that text alone with the
sentence that answers it. The human test stays open, and this file says so rather than presenting a
proxy as a user test.

## Nothing here weakens a claim

No entry above was resolved by deleting or softening a limitation. The README keeps "not a green
release", the open gates, the absent demo and the absent license below the fold; the catalog keeps
its open rows; the demo page says nothing is recorded.
