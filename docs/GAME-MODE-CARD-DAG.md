# Game Mode card DAG

This is the execution graph created from the owner-authorized plan on 2026-11-09. The
authoritative product plan is `docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`; the pre-build critique is
`docs/GAME-MODE-ADVERSARIAL-REVIEW.md`.

## Rules for every card

- Work in the card's worktree; never edit the operator checkout.
- Merge every parent branch named in the card before editing. Do not start from a stale `HEAD`.
- Commit small, run the named tests, capture screenshots and print proofs.
- **Do not call `hermes kanban complete`.** Submit `hermes kanban request-review` to the named
  reviewer. The maker never certifies its own visual or behavioral output.
- A reviewer rejection returns the card to the maker with concrete changes. Up to three visual
  loops are allowed before the manager splits or escalates the card.
- No generated screenshot as UI; no AI text in an image; no fake ratings, progress or evidence.
- No publication, catalog submission or external send.

## Graph

| Card | Work | Owner | Reviewer | Parents | Branch |
|---|---|---|---|---|---|
| GM-001 | Contract freeze: modes, worlds, take-home, homework, engagement, tutor | cinder | sentinel | — | `wt/gm-001-contract` |
| GM-013 | Visual direction, concept-parity rubric, print/art spec | quill | atlas | GM-001 | `wt/gm-013-visual-spec` |
| GM-002 | Global Home launcher and course-home split | vellum | quill | GM-001, GM-013 | `wt/gm-002-home` |
| GM-003 | WorldPolicy, textless prompts, world media job/cache | sable | sentinel | GM-001 | `wt/gm-003-world` |
| GM-005 | Parent Studio source picker and take-home pack backend | lattice | sentinel | GM-001 | `wt/gm-005-takehome` |
| GM-007 | Homework generator, policy and Japanese fixtures | lattice | cbqa | GM-005 | `wt/gm-007-homework` |
| GM-009 | Game engagement store and XP rules | cinder | sentinel | GM-001 | `wt/gm-009-engagement` |
| GM-004 | World Studio and course world surface | vellum | quill | GM-002, GM-003 | `wt/gm-004-world-ui` |
| GM-006 | Parent Studio take-home surfaces | vellum | quill | GM-004, GM-005 | `wt/gm-006-parent-ui` |
| GM-014 | Homework/print content fixtures and print proof | harbor | cbqa | GM-007 | `wt/gm-014-content-print` |
| GM-008 | Homework and adult take-home UI | vellum | quill | GM-006, GM-007, GM-014 | `wt/gm-008-homework-ui` |
| GM-011 | Tutor.ask backend and practice integration | cinder | sentinel | GM-009 | `wt/gm-011-tutor` |
| GM-010 | Game engagement UI | vellum | quill | GM-008, GM-009 | `wt/gm-010-engagement-ui` |
| GM-012 | Tutor rail UI, selection, glossary and practice | vellum | quill | GM-010, GM-011 | `wt/gm-012-tutor-ui` |
| GM-015 | Independent behavioral QA and adversarial review | sentinel | cbqa | all implementation cards | `wt/gm-015-qa` |
| GM-016 | Final visual parity acceptance | cbqa | quill | GM-015 | `wt/gm-016-visual` |
| GM-017 | Integration, merge, docs and handoff | atlas | sentinel | GM-015, GM-016 | `wt/gm-017-integration` |

## Why this order

- The contract card freezes additive names before six backend cards and five UI cards collide.
- Visual direction is a parent of Home because the approved Home concept, palette, type and
  textless-art rules must exist before the first screen is judged.
- The UI cards share `desktop/plugin.js`; they are serialized by their parent chain:
  Home -> World Studio -> Parent Studio -> Homework -> Game engagement -> Tutor rail.
- Parent, homework, engagement and tutor backends are independent after the contract, so they can
  run in parallel, but each has one named reviewer.
- The visual reviewer is separate from every maker. The final visual card is not written by the
  UI maker. The final integration card is not written by the QA reviewer.
- A green test suite alone does not close a visual card. A pack proof alone does not close a
  content card. Every close is a named review.
