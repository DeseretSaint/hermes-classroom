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
| GM-001 | Contract freeze: modes, worlds, take-home, homework, engagement, tutor | cinder | cbqa | — | `wt/gm-001-contract` |
| GM-013 | Visual direction, concept-parity rubric, print/art spec | quill | atlas | — | `wt/gm-013-visual-spec` |
| GM-002 | Global Home launcher and course-home split | vellum | quill | GM-001, GM-013 | `wt/gm-002-home` |
| GM-003 | WorldPolicy, textless prompts, world media job/cache | sable | sentinel | — | `wt/gm-003-world` |
| GM-005 | Parent Studio source picker and take-home pack backend | lattice | sentinel | — | `wt/gm-005-takehome` |
| GM-007 | Homework generator, policy and Japanese fixtures | lattice | cbqa | GM-005 | `wt/gm-007-homework` |
| GM-009 | Game engagement store and XP rules | cinder | sentinel | — | `wt/gm-009-engagement` |
| GM-004 | World Studio and course world surface | vellum | quill | GM-002, GM-003 | `wt/gm-004-world-ui` |
| GM-006 | Parent Studio take-home surfaces | vellum | quill | GM-004, GM-005 | `wt/gm-006-parent-ui` |
| GM-014 | Homework/print content fixtures and print proof | harbor | cbqa | — | `wt/gm-014-content-print` |
| GM-008 | Homework and adult take-home UI | vellum | quill | GM-006, GM-007, GM-014 | `wt/gm-008-homework-ui` |
| GM-011 | Tutor.ask backend and practice integration | cinder | sentinel | GM-009 | `wt/gm-011-tutor` |
| GM-010 | Game engagement UI | vellum | quill | GM-008, GM-009 | `wt/gm-010-engagement-ui` |
| GM-012 | Tutor rail UI, selection, glossary and practice | vellum | quill | GM-010, GM-011 | `wt/gm-012-tutor-ui` |
| GM-015 | Independent behavioral QA and adversarial review | sentinel | cbqa | all implementation cards | `wt/gm-015-qa` |
| GM-016 | Final visual parity acceptance | cbqa | quill | GM-015 | `wt/gm-016-visual` |
| GM-017 | Integration, merge, docs and handoff | atlas | sentinel | GM-015, GM-016 | `wt/gm-017-integration` |

The contract branch `wt/gm-001-contract` was merged into `master` after the contract tests passed;
GM-005 and GM-009 were released to run against that merged contract while the independent review
of GM-001 continued. If the review rejects the contract, the affected cards return to the contract
card; no worker is allowed to patch around a rejected contract.

## Parallelism and file ownership

The board can run six workers. Independent cards start together; only real file or state overlap
is serialized.

- **Concurrent now:** GM-001 contract review (cbqa), GM-013 visual spec (quill), GM-003 world
  backend (sable), GM-005 take-home backend (lattice), GM-009 engagement backend (cinder), and
  GM-014 print/content proof (harbor).
- **Backend parallel wave:** GM-003, GM-005, GM-009, GM-014 and GM-007 (after GM-005) own
  different modules. They may run together; they must not edit each other's files.
- **Single writer:** every card that changes `desktop/plugin.js` is Vellum-only and runs in the
  serial chain Home -> World Studio -> Parent Studio -> Homework -> Engagement -> Tutor rail.
  Two UI cards never run concurrently, even if their product areas are independent.
- **Migration and contract:** only GM-001 owns migration 0013 and the frozen contract manifest.
  A later card that needs a schema change must return to a contract card; it must not edit the
  migration concurrently.
- **QA/final:** GM-015 and GM-016 wait for all implementation parents; they are review gates, not
  parallel writers. GM-017 integrates only after both pass.
- If two cards unexpectedly need the same file, the second one stops and asks the manager to
  split or serialize; it does not merge into a moving branch.

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

## Created card IDs

Created on board `coursebook` on 2026-11-09. These are the board handles for the graph above.

| Card | Board id | Status at creation |
|---|---|---|
| GM-001 | `t_ee0345b5` | running |
| GM-013 | `t_e00442ed` | todo (GM-001 running) |
| GM-002 | `t_5e7e8e08` | todo (GM-001 running) |
| GM-003 | `t_8a98eff8` | todo (GM-001 running) |
| GM-005 | `t_417a76e7` | todo (GM-001 running) |
| GM-007 | `t_958daca7` | todo (GM-001 running) |
| GM-009 | `t_971b7a47` | todo (GM-001 running) |
| GM-004 | `t_af131c02` | todo (GM-001 running) |
| GM-006 | `t_1b360207` | todo (GM-001 running) |
| GM-014 | `t_a5058d1f` | todo (GM-001 running) |
| GM-008 | `t_69a789eb` | todo (GM-001 running) |
| GM-011 | `t_28a67930` | todo (GM-001 running) |
| GM-010 | `t_ebf058fa` | todo (GM-001 running) |
| GM-012 | `t_35652a2f` | todo (GM-001 running) |
| GM-015 | `t_ec0fcc1d` | todo (GM-001 running) |
| GM-016 | `t_11e21405` | todo (GM-001 running) |
| GM-017 | `t_cfcb5927` | todo (GM-001 running) |
