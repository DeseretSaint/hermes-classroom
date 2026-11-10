# GM-006 — Parent Studio take-home evidence

Card: GM-006 (Parent Studio take-home surfaces). Branch `wt/gm-006-parent-ui`, worktree
`/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_1b360207`. Parents only: no child
account, no child chat, no learner answer key on the learner page, no XP/stars/scores.

## What the live window proved

An isolated Hermes Desktop window (state `~/.hermes/coursebook-test-gm006`, CDP 9342) connected to
an isolated `hermes serve` backend at `http://127.0.0.1:44309` speaking **cb.rpc v24**. Every frame
below is a real `Page.captureScreenshot` after driving the shipped UI; the pack was previewed,
drafted, approved and exported through the module's own controls. Nothing was rendered from a
fixture.

The run is pinned to `desktop/plugin.js` sha256
`7802e3ca3dd15cc7a19b61dff632666a14a6b14b23f8a1cf858dc246dbe01f52`
(`live-evidence.json` → `plugin_sha256`). Reproduce with
`CB015_CDP_PORT=9342 node scripts/gm006-live-capture.mjs` against a running rig.

| File | Viewport | Pack state | Proof pages | md5 |
|---|---|---|---|---|
| `studio-plans--1049--dark.png` | 1049 px | — | 0 | `7732db115e889f4dd371a1e3a124db87` |
| `takehome-shelf--1049--dark.png` | 1049 px | — | 0 | `530cbcaf85a2dffb6aed3ef6ef5fddc1` |
| `takehome-source-game--1049--dark.png` | 1049 px | — | 0 | `23071e8e00d2635843b45cbb37a10c08` |
| `takehome-source-textbook--1049--dark.png` | 1049 px | — | 0 | `0977f6dd346156f624baad0248452a58` |
| `takehome-pack--1049--dark.png` | 1049 px | none | 0 | `898e99882a24fcbec43bb3c8fdd90f74` |
| `takehome-proof--1049--dark.png` | 1049 px | none | 4 | `24652dfb8f9bd6ee86caaa1cc985cedd` |
| `takehome-print-proof--1049--dark.png` | 1049 px | none | 4 | `3677484fadc8e483b56eeae138c9b073` |
| `takehome-proof-learner_page--1049--dark.png` | 1049 px | none | 4 | `2c2d1cc1f3c9e6d01ee05927c66e2372` |
| `takehome-proof-answer_guide--1049--dark.png` | 1049 px | none | 4 | `f4f8e37eac7cf929ac4c385b341b0b56` |
| `takehome-proof--900--dark.png` | 900 px | none | 4 | `40d5c382580a70532fee315115565e0a` |
| `takehome-proof--460--dark.png` | 460 px | none | 4 | `5ab2912d93d4588c684a4b4662cfae72` |
| `takehome-proof--460--dark--200.png` | 460 px, 200% text | none | 4 | `2751874b842b4e07eab3e6893a484331` |
| `takehome-approved--1049--dark.png` | 1049 px | approved | 4 | `d6b8fd1c6e583c17f3e89dd9000e7780` |
| `takehome-exported--1049--dark.png` | 1049 px | exported | 4 | `e652cfba4353d5e5be2e3e6182ba0e6a` |

`live-evidence.json` records each frame's measured `innerWidth`, `rootFont`, `overflow` (all
`false`), proof page roles (`cover,parent_guide,learner_page,answer_guide`), source mode badge
(`game`, `textbook`) and export artifact id. The 460 px and 200% measurements are calibrated
iteratively against `window.innerWidth`, not assumed.

### Print proof

`takehome-print-proof.pdf` is the PDF the exported pack actually minted (fetched through the
session-bound artifact route named by `artifact.get`):

| Property | Value |
|---|---|
| Pages | 4 (`pdfinfo`) |
| Page box | 612 × 792 pt (Letter), 56 pt margins |
| Bytes | 16,820 |
| sha256 | `fbfbc886930104e87aa06e9cce47bc1a5401154aabdc3c46116567916f0f280f` |
| Tagged | yes |
| Text | selectable; `pdftotext` shows the cover, parent guide, learner page and answer guide |

The learner page text (`Section 1: the sear`, *Why the sear matters*, *Your turn*) is present and
the answer marker/rubric are not; the answer guide is the last sheet and carries
`Answer guide - parent only`. Frames `takehome-proof-learner_page` and
`takehome-proof-answer_guide` show both sheets as distinct visual objects (field edge vs plum
dashed rule), not thumbnails.

## Tests

```
python3 -m unittest tests.test_desktop_gm006_parent_takehome tests.test_platform_desktop
```

covers the five card-named tests plus the regression pins added here:

- `test_parent_source_picker_opens_game_and_textbook` — Game and Textbook sources both open,
  parent plans excluded from the shelf, mode badges and blocked-lesson copy.
- `test_takehome_learner_page_has_no_answer_key` — the learner page and learner copy carry
  neither the answer marker nor the rubric; the answer guide is the parent-only last sheet.
- `test_takehome_print_proof_is_real_pages` — four DOM page sheets, selectable text, no `<img>`,
  no thumbnail; plus `test_textbook_course_without_world_art_still_prints` and
  `test_a_captioned_world_plate_is_a_plate_not_lesson_prose`.
- `test_parent_pack_does_not_mutate_source` — full preview→create→approve→export leaves
  courses/plans/objectives/lessons/checks/attempts/evidence byte-identical.
- `test_parent_pack_no_xp_or_rating` — no XP, rating, stars, mastery or leaderboard in pack JSON,
  printed pages or the composed surface.
- `test_exported_pack_resolves_a_download_handle` — approve advances one revision, export the
  next, and `artifact.get` answers a session-bound PDF handle.
- `test_artifact_get_reads_a_versioned_source_id` — a legacy/deduped artifact row whose
  provenance names `<lesson_id>:v<n>` still returns a contract-valid read.

## Known gaps (honest)

- The palette command `coursebook.takehome` is registered (and pinned in
  `tests/test_platform_desktop.py`), but the live capture drove the in-route tab, not the palette
  widget.
- Both live source courses have no world art. The live proof is the "no world art prints cleanly"
  path; the captioned-plate rendering is proven by the render test above, not by live art.
- The export link is the backend's relative artifact route. The isolated capture resolved it
  against `window.hermesDesktop.getConnection().baseUrl` and carried the rig token because the
  renderer in this rig is the Vite dev origin; clicking the raw href in a production shell is the
  host route's job.
- The proof captures are the **parent** audience (the complete pack). The learner audience copy is
  proven in the render test, not in a live frame.
- Frames are dark mode only; the plugin palette is the host session's appearance.

## The one backend change

`coursebook/takehome.py` now binds the export artifact's provenance to the lesson **id**, keeping
the exact `<lesson_id>:v<n>` in `notes`, and `coursebook/domain.py` normalizes a legacy/deduped
`source_ids` entry at the `artifact.get` boundary. Before this, `artifact.get` refused the
take-home PDF with `INTERNAL_ERROR` (identifier pattern forbids `:`), so the Download control never
appeared. No pack format, pack page composition, state machine or contract changed.
