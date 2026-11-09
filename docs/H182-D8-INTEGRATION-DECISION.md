# H-182 / D8 — integration decision for the acceptance tree

Status: decided, implementation in progress. Written by Atlas on 2026-11-08 against local
master `7e15963` and integration branch `scratch/int-d8-land`. Nothing here is pushed,
merged to master, recorded or published.

## The question

H-182 walked tree `300d00b` (plugin module `6f444dcb`) cold and found that the acceptance
tree is not the union of the completed UI cards: `git merge-base --is-ancestor <commit> HEAD`
is false for H-183 `0b01f33`, H-189 `82200c2`, H-199 `9596045`, H-192c `8204311` and
H-194e `aaaff15`. Either those branches must enter the acceptance tree and the gate re-run
on the integrated commit, or the final gate has to be re-scoped.

**Decision: integrate H-183, H-189 and H-199. They are part of the shipped product and
the gate must see them. H-192c is held for rework and does not enter as committed. H-194e
needs no merge because its content is already on master. The final acceptance gate is
re-scoped to run on the integrated commit; `300d00b` is not a demo or publication base.**

## Measured, per card

| card | commit | ancestor of `7e15963` | content on master / integrated tree | ruling |
|---|---|---|---|---|
| H-194e | `aaaff15` | no | present | no merge |
| H-183 | `0b01f33` | no | absent | merge |
| H-189 | `82200c2` | no | absent | merge |
| H-199 | `9596045` | no | absent | merge |
| H-192c | `8204311` | no | absent | held |

### H-194e — ancestry is a false negative

`aaaff15` and master's `7e15963` carry the same subject ("H-194e: a page revision keeps its
check…"), so the work was re-landed rather than merged. File-level comparison:

```
git diff aaaff15 7e15963 -- coursebook/pack_flow.py        # identical
git diff aaaff15 7e15963 -- coursebook/parent_authoring.py # identical
git diff --numstat aaaff15 7e15963 -- coursebook/domain.py docs/CONTRACTS.md
#   11  0  coursebook/domain.py
#    8  0  docs/CONTRACTS.md
```

Additions only, no deletions: master is the branch plus later work. `tests/test_h194_fine_tune.py`
is likewise a superset and green — `python3 -m unittest tests.test_h194_fine_tune` →
`Ran 16 tests … OK`. H-194e is in the acceptance tree; no cherry-pick.

### H-183, H-189, H-199 — merged

All three are clean alone (H-199: 9/9 on `9596045`; H-189: 13/13 on `82200c2`). They are on
`scratch/int-d8-land`:

```
d4960cc Merge branch 'wt/h199-lesson-liveness' into scratch/int-d8-land
4793488 Merge H-183: learner truth sweep (M4 pin re-rendered after integration)
c036412 Merge H-189: living home (route settle, authored node list, one notes line)
c69bcb8 Restore CheckpointDetailRow for H-189's route node detail rows
```

Content now measurable on the branch: `This lesson page is not written yet`,
`Details and job state`, `Record revision`, `The backend did not record a next step` all
resolve, and `tests/test_desktop_h183_copy_inventory.py`,
`tests/test_desktop_h189_living_home.py`, `tests/test_h199_lesson_deadline.py` exist and run.

One real conflict had to be resolved by hand: `desktop/plugin.js` (H-183's `PathStop` list vs
H-189's inline route node renderer). Resolution kept both route hooks (`useCbSelectionSettle`
from H-189, `useStudyCompanion` gate from H-183), kept H-183's run line **and** H-189's
hierarchy caption, took H-189's inline node list as the superseding surface, and restored
`CheckpointDetailRow`, which was dropped with `PathStop` and without which route render threw
`ReferenceError`. `audit/visual/m4-visual/audit.json` was re-rendered rather than hand-merged.

### H-192c — held, not merged

`8204311` is not gate-clean on its own branch, so merging it would put a known-red contract
into the acceptance tree:

```
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
ModelOutputInvalid: plan validation violates its schema at claim_verdicts: [] is too short
```

and 299 existing tests fail (146 failures + 153 errors) on a tree carrying it; the failure
reproduces at `8204311` directly (`tests.test_syllabus_import.CompanionCourseTest`). Cause is
contract-vs-fixture: H-192b/H-192c narrow each validation pass to its own criteria batch and
claim labels with `minItems == maxItems`, while every recorded/scripted validator still answers
the wide ten-criterion schema with an empty claim set. That is rework, not a merge artefact —
tracked as `t_69ab60f9` (cinder), with the fixture-alignment repair prototyped on
`wt/h192c-integrated` @ `b304e16`.

## State of the integrated tree (not green yet)

`git status` clean at `c69bcb8`; full `./scripts/validate.sh` went from 126 failing cases on the
naive union to **2**, both in `tests/test_desktop_h148_path_truth.py`:

- `test_the_trail_has_place_labels_one_halo_and_only_real_gates`
  (`data-cb-path-place="start"` absent from the rendered route)
- `test_current_and_next_carry_one_honest_detail_line_and_future_stays_collapsed`
  (`<details` present in a route that should show only current + next detail)

Both pass on `wt/h189-living-home` alone, so the loss is in the union. Also outstanding on that
branch: the M4 `plugin_sha256` pin, which must be re-rendered (`python3 scripts/m4v-audit.py`,
`python3 scripts/m4v-repro-check.py`), never hand-edited. Both items are `t_e0db4a27` (sable).

## Re-scoped gate

1. The acceptance gate runs on the tip of `scratch/int-d8-land`, not on `300d00b`.
2. It re-runs only when that tip passes `./scripts/validate.sh`, the H-40 replay packet and the
   M4 repro byte-compare.
3. H-182's cold walk is re-walked on that commit. Mechanical gates passing on `300d00b` say
   nothing about the integrated tree.
4. No demo recording, no catalogue pin, no publication from `300d00b` or from the integration
   branch while it is red. Recording stays operator-gated (DeseretSaint) and post-gate.
5. Integration order is unchanged: H-192c rework lands after the union is green, then the gate.

## Learner-surface copy still open

H-183's inventory rule covers the default Home / lesson / section / check / first-run / error
sentences. The cold walk's remaining strings sit on authoring surfaces and are not repaired by
H-183; they are routed to a triage card rather than silently declared fixed:

- `desktop/plugin.js:24691` — `State: ${objective.state} · check: ${objective.check_state}` in the
  plan/blueprint editor
- `desktop/plugin.js:19888` — `Source type not recorded`
- `desktop/plugin.js:2641` — `Session length could not be read` (red/Retry on first classroom arrival)

Reproduce the D8 measurement:

```
git merge-base --is-ancestor 0b01f33 HEAD; git merge-base --is-ancestor 82200c2 HEAD
git merge-base --is-ancestor 9596045 HEAD; git merge-base --is-ancestor aaaff15 HEAD
python3 -m unittest tests.test_desktop_h148_path_truth   # 2 failures at c69bcb8
```

## D8 resolution on `scratch/int-d8-land` (`t_e0db4a27`)

`t_e0db4a27` closed both open items. The failing-count went from **2 to 0** in
`tests/test_desktop_h148_path_truth.py` (15/15 OK) and the M4 claim set from **1 FAIL to 0**
(15/15 PASS).

### The path: the assertions describe the shipped trail, not a dropped shape

H-189 branched at `82200c2`, which does **not** contain H-177 (`0f8fbb4`,
`test_desktop_h177_trail`). On master the shipped `CheckpointPath` is `PathPlace` + `PathStop`:
two route SVG halves per stop, `Start` and `Course end` place labels, one halo on the current
stop, one gate diamond per real `check_state`, and one detail line inside the current and next
rows. The union kept H-189's inline node list, which predates that surface, and with it the
repeated `<details>` disclosure H-177 had removed.

Resolution: **restore the shipped trail and fold H-189's additions into it** rather than
rewriting the assertions. `PathStop` now also carries H-189's current-stop pulse
(`data-cb-path-pulse`, the finite four-leg cycle), and `CheckpointPath` keeps H-189's
`useCbSelectionSettle` arrival on the route beat and its single caption line. The inline node
list and the `CheckpointDetailRow` helper it served are gone; nothing else read them.

### The M4 pin, and one real defect the re-render found

`python3 scripts/m4v-audit.py` re-rendered the pin from the branch bytes, never hand-edited:
`plugin_sha256` moved from `ec03f7bc...` to `c7a6e938...`. The first fresh render failed
**C-03** (`No clipped text ...`, 10 clipped nodes): a 56 px classroom cover drew its title on
one `white-space: nowrap` + ellipsis line, so `scrollWidth` exceeded `clientWidth`. The same 10
clipped nodes measure on `c69bcb8` before the path reconciliation, so the defect came from
H-189's cover, not from the path: H-189's own audit pin was stale and never measured it. Fix:
the cover title and subject wrap (`overflowWrap: anywhere`) and the frame grows from a
`minHeight`, so no cover text is truncated. The re-rendered audit is 15/15 PASS and
`scripts/m4v-repro-check.py` reports two independent runs producing identical `audit.json`
(62 frames) and 62 identical screenshots.

### Gate status at the tip

`./scripts/validate.sh` passes from the top of the branch (full unit discovery, ESM parse,
catalog admission, plugin validate + doctor on the export, 31/31 mounted backend expectations).
Nothing was pushed and master was not advanced.

