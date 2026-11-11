# SCORECARD — CP-021 Discover / Workshop v3 (R-DISC)

Left blank for the independent reviewer. The maker must not fill this block.

```text
Card: CP-021            Branch: wt/cp-021-discover  Commit: ______________
Maker (did not review): vellum   Reviewer: quill   Date: __________
Loop: 1 / 2 / 3
Screens submitted: Discover / Workshop (route 1049, 900, 460, 1349; light, dark, forced colours)
Concept frames used: R-DISC docs/concept-parity/refs/discover.png (sha256 f9ce940f…)
Evidence: docs/visual-review/cp-021/MANIFEST.md   Captures: 6 / 6 required cells
```

## Dimensions

| # | Dimension | Score 1–5 | Evidence (one sentence; required below 5) |
|---|---|---|---|
| 1 | Focal hierarchy | | |
| 2 | Composition | | |
| 3 | Type | | |
| 4 | Palette and texture | | |
| 5 | Illustration | | |
| 6 | Card / game system | | |
| 7 | State coverage | | |
| 8 | Responsiveness | | |
| 9 | Truth | | |

## Composition anchors (per screen)

| Screen | A1 Threshold | A2 Anchored asymmetry | A3 Material surface | A4 Subject mark | A5 Quiet field |
|---|---|---|---|---|---|
| Discover | | | | | |

## Verdict

```text
All nine dimensions >= 4?          YES / NO
All anchors present per screen?    YES / NO
Verdict:                           PASS / REQUEST CHANGES
Smallest fix if not passing: __________________________________________
Remaining differences even on pass: ___________________________________
Reviewer signature (profile): ______________
```

A `PASS` with any dimension at 3, any missing anchor, or any missing required capture is void.
Maximum three loops; a fourth failure goes to the manager to split the screen.

## Reviewer checklist for this card (not scores — reproduce or refute)

- [ ] `node scripts/cp-capture.mjs … --destination workshop --require-v3` reproduces at least three
      of the six cells, and each stamp's `route.destination` reads `workshop` and `plugin.window_sha256`
      equals the module at the commit under review.
- [ ] `test_workshop_v3_no_ratings_or_counts`, `test_workshop_v3_grid_aligned_to_banner`,
      `test_workshop_v3_same_cover_in_store_library_detail` and `tests.test_workshop` pass on the
      reviewer's own run.
- [ ] The grid's left and right edges equal the feature plate's edges at 1049/900/460/1349 (measured
      with CDP, not by eye).
- [ ] A frame exists for route 1049 dark, 1049 light, 460 dark and the 1349 wide cell.
- [ ] The manifest's known gaps (heading ruling, banner ground, compact rows vs the card body's
      "peek", the CoverPlate3 mid-word break) are judged against SPEC-V3, not against the card text.
