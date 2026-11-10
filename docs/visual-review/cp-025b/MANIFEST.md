# CP-025b review packet — World Studio and Parent Studio on the v3 primitives

Packet for reviewer `quill`. Status: **implementation and test evidence only. No capture frames
in this packet.** The last step (rebase onto the merged v3 primitives, the eight-cell capture
matrix and the scorecard) is deferred under the owner's 2026-11-10 partial-build ruling, which
told this card to start on `wt/cp-020b-primitives` at `556a6fb`, build its segment, tests and data
wiring now, and expect the final 10% to be finished after CP-020b merges. A frame set captured
from a branch the manager will rebase is not evidence of the tree that ships, so no frame was
faked, re-used or relabelled.

## What this card changed

| file | change |
| --- | --- |
| `desktop/src/97-world.js` | World Studio, its frame, the mode badge, world plates, the Textbook→Game dialog and the course-world hero now paint from `contracts/cb.tokens.v3.json` only. All 13 `CbAction`s became `PillAction` (`primary`/`quiet`); `sdk.Button`, `sdk.EmptyState`, `sdk.ErrorState` and `sdk.Loader` are gone from the surface; the error state's 2 px left bar, the provider and partial 3 px top bars, the uppercase kicker above the `h2` and the 2 px radii are gone. |
| `desktop/src/95-studio.js` | Parent Studio paints from the same contract (no `--cb-` v2 token, no `CB_TYPE`/`CB_SANS`/`CB_SERIF`). The three entrances are an authored v3 tab strip (`role="tab"`, `aria-selected`, 3 px terracotta marker) instead of the host `sdk.SegmentedControl`; the view switcher is route-relative tabs (was a window `min-[47.5rem]` breakpoint); the take-home "who holds this copy" choice is a labelled radio group; the leave-guard and plan-reject left bars became paper cards; the take-home proof no longer encodes page role as a 3 px left border. |
| `tests/test_cp_025b_v3_studio.py` | 17 new tests: token/type/paint gates on both segments, no decorative bars or kickers, one primary per World Studio state (rendered), the concept boards as paper cards, the brief never rendered as UI copy, the entrance tabs and view switcher, no game chrome in Parent Studio, and the adult-only copy. |
| `audit/visual/m4-visual/audit.json` | regenerated with `python3 scripts/m4v-audit.py` because the shipped module sha changed (the pin is a sha, not a claim about which surface moved). |

## Not changed, by file ownership

`desktop/plugin.js` is generated (`python3 scripts/build_plugin.py`) and was not hand-edited.
`desktop/src/75-tokens.js`, `10-primitives.js`, `80-components.js`, `30-home.js`, `70-learning.js`,
`90-course.js` and `96-workshop.js` were not edited. Primitive and token needs found here are
reported, not made:

1. `PlateHead`, `CourseCover`, `ChildSafeLine` (30-* and 80-*) still paint v2 tokens. Parent Studio's
   head, plan rows and child-safe line therefore keep the v2 paint inside a v3 field. Converting
   them is a primitives/component card, not this one.
2. There is no v3 `Input`/`Select` primitive. World Studio's direction fields and the view picker's
   narrow fallback still use `sdk.Input` / `sdk.Select`; the v3 contract needs a field primitive
   (inset-1, rule, focus ring) before those can be authored.
3. `sdk.Badge` remains in Parent Studio's status rows (plan state, approval state, export ready).
   A v3 chip primitive would replace them, but a badge is not the banned host-blue control this
   card was told to remove.

## Evidence produced in this run

| check | result |
| --- | --- |
| `python3 scripts/build_plugin.py` | wrote `desktop/plugin.js` from 20 segments; sha in the card summary |
| `python3 -m unittest tests.test_cp_025b_v3_studio` | 17 tests, OK |
| `python3 -m unittest tests.test_plugin_build tests.test_desktop_tokens tests.test_desktop_tokens_v3 tests.test_v3_primitives tests.test_v3_scope` | OK |
| `python3 -m unittest tests.test_desktop_gm004_world tests.test_desktop_h94_single_primary tests.test_desktop_gm006_parent_takehome tests.test_desktop_h156_parent_child tests.test_desktop_contracts tests.test_desktop_h194_fine_tune_ui` | OK — every GM-004 world marker, the H-94 one-primary count and the H-156 adult-only copy still hold |
| `python3 scripts/m4v-audit.py` | regenerated `audit/visual/m4-visual/audit.json` against the new module sha |

## The cells this card still owes (deferred)

The matrix has no `cp-025b` entry in `scripts/cp-matrix/`, and the v3 rubric's frame table names no
`world.studio`/`parent.studio` concept frame (its rows are `home.global`, `home.course`, `world.studio`
via F4/F3, `course.world`, `parent.source-picker`, `parent.takehome.preview`, `parent.export.approval`
— all through `docs/concept-parity/refs/`). So the capture set has to be authored by the manager
from the merged branch, against F3/F4 crops, once, on the tree that ships:

```
# from the rebased card worktree, with a fresh rig whose plugin_root is that worktree
S=$HOME/.hermes/coursebook-test-cp025b
ln -sfn "$PWD" "$S/home/plugins/coursebook"
cp desktop/plugin.js "$S/home/desktop-plugins/coursebook/plugin.js"
COURSEBOOK_TEST_HOME="$S/home" CB013_PORT=44341 bash scripts/cb013-live-backend.sh
rm -f "$S"/userdata/Singleton*
COURSEBOOK_TEST_STATE="$S" CB013_CDP_PORT=9451 bash scripts/cb013-live-window.sh --restart

# eight baseline cells each for world.studio and parent.studio: 1049/900/460 × light/dark,
# plus the 1349 wide cell, forced colours and 200% text, every named state below
CB015_CDP_PORT=9451 CB013_PORT=44341 COURSEBOOK_TEST_STATE="$S" \
  node scripts/cp-capture.mjs --name world-studio-1049-light --out docs/visual-review/cp-025b \
    --cdp-port 9451 --state "$S" --plugin desktop/plugin.js \
    --backend-url http://127.0.0.1:44341 --token "$CB013_TOKEN" --route-width 1049 --require-v3
python3 scripts/cp-sbs.py --ref docs/concept-parity/refs/system.png ...   # then the F3 crop
```

Named states to capture, one cell each: World Studio `not_requested`, `concepts_ready`,
`style_selected`, `kit_ready`, `failed` (partial), `approved`, plus the mode dialog; Parent Studio
`plans` (landing), `takehome` (shelf + source panel), `homework`, and the studio view switcher at
900 (tabs) and 460 (Select fallback). Each frame's `.stamp.json` must name the merged commit's
plugin sha; a frame whose stamp sha differs is invalid.

## Known gaps the reviewer should weigh

- No live pixel evidence in this packet. The reviewer cannot score the Craft and Composition
  dimensions from it; that is the deferral, not a claim.
- Parent Studio's remaining v2 paint (head, plan rows, badges) will read as a seam at 200% text until
  the primitives listed above land.
- `sdk.Select`'s own chrome is host-styled; only its trigger and layout are ours.
