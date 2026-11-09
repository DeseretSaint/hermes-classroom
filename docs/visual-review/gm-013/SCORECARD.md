# SCORECARD — GM-013 (self-consistency check of the instrument)

This card ships no product screen. This scorecard is a **self-consistency check of the rubric**:
can a reviewer score the reference material from the spec without asking a question, and does a
competent reviewer reach the same verdict twice? It is not a product review and it cannot close any
UI card.

```text
Card: GM-013            Branch: wt/gm-013-visual-spec  Commit: see branch tip
Maker (did not review): quill        Reviewer: atlas (pending)      Date: —
Loop: 1
Screens submitted: reference plates (4) + anti-generic swap instrument + print specimen (5 pages)
Concept frames used: F1, F2, F3, F4 (comparison frames, not reproductions)
Evidence: docs/visual-review/gm-013/MANIFEST.md
```

## Dimensions (reference material)

| # | Dimension | Self-check | Why |
|---|---|---|---|
| 1 | Focal hierarchy | n-a (reference) | a plate has no action; scored only on a screen |
| 2 | Composition | 5 | each plate centres one subject mass with ≥35% quiet paper |
| 3 | Type | n-a | no type inside a plate; captions are the sheet's, not the plate's |
| 4 | Palette and texture | 5 | eight tokens, no state hue, no gradient, hard edges |
| 5 | Illustration | 5 | ≥2 plan motifs per world, one kit, textless |
| 6 | Card / game system | n-a | no cards in this card |
| 7 | State coverage | n-a | no screens; the print specimen covers 5 page roles |
| 8 | Responsiveness | 4 | plates are 640×360 masters; regraded at 16:9 and 3:2 crops, not at 460 px UI |
| 9 | Truth | 5 | host-composed, no model call, manifest hash per file, no invented rating |

## Composition anchors

| Screen | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|
| reference plates | n-a | n-a | yes | yes | yes |
| print specimen | yes | yes (aside column on page 1) | yes | yes (plate page 2/5) | yes |

## Verdict

```text
All scored dimensions >= 4?        YES
All anchors present per screen?    YES
Verdict:                           instrument usable; atlas to review
Remaining differences even on pass: the plates are reference, not shipped art; GM-004 must
                                    produce its own subject-specific kit and its own provenance.
```

**The point of this file** is that the nine dimensions are answerable from
`docs/GM-VISUAL-SPEC.md` alone, and that a dimension can legitimately be `n-a` for an artifact that
is not a screen. If a future reviewer cannot reproduce a score here, the rubric is defective.
