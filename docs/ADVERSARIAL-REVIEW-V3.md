# Coursebook adversarial review v3 — 2026-11-07

Status: read-only review plus the card set it produced. Review base: `origin/master` `7d0f9cf`
(H-86 on H-84), with H-91 in flight on the two H-85 gate blockers. Nothing here is a release
claim, and no publication gate moved.

## Verdict

**Functionally promising; not yet a professional build.** The v2 visual work is a real
improvement: uppercase labels are gone, body text is readable, contrast is clean, the route is
designed rather than a host form, and the H-86 start plate is the right shape. But one P0 path
still crashes the route (H-91), the static gate missed two acceptance regressions (S08/S09), the
frequency-inventory and reproducibility work is stranded on branches, and several user-facing
reads still turn a failure into a quiet empty state. A judge would notice the crash first, the
duplicate demo data second, and the "why did this not load?" dead ends third.

The standards research is not the gap. The gap is **evidence-to-surface discipline**: every
stored fact has to reach a named, accessible, recoverable state, and every failure has to say
what happened and what to do next.

## What is true on this base

| Item | Evidence |
|---|---|
| Section route crash | H-85 V2-1, reproduced twice in light/dark at 1049/460; `runtime.binding_status` on a null runtime. H-91 `t_2ebaafa6` is fixing it. |
| Library overflow | H-85 V2-2: 19 px at 900, 45 px at 460; header actions clip. H-91 is fixing it. |
| Acceptance drift | `tests/adversarial/attack_state.py` on this tree: **S08 FAIL** (`context_returned=True`, `forbidden_hits=['reference']`) and **S09 FAIL** (clarification now gets the tutor skill context; attempts/revision unchanged). H-102 `t_86021cbf` owns the reconciliation. |
| Unmerged capability work | H-89 `wt/h89-frequency-inventory` @ `149e428` (frequency inventory, 25 tests, 1682 suite) is not on master; H-90 `h90-repro` @ `f0e3d1d` (reproducibility) and H-85 `h85-gate` @ `46c16ed` (gate doc) are local branches. |
| Stale release claims | README still says 1,648 tests, M4 pin `635b7061…`, 2,050 nodes / 5.93:1; H-85 measured 1,673 tests at `7d0f9cf`; H-90 measured `416ff74` / 62/62. `docs/SUBMISSION.md` still carries 685-test / schema-v4 rows. |
| Install drift | `hermes plugins doctor coursebook` warns the installed Desktop copy is stale, and fails copying `.worktrees/*/.chromium/Singleton*` sockets. |

## Findings, ranked

### P0/P1 — must fix before any demo

1. **Section crash.** H-91. A section render with `runtime === null` must be a test, not a
   production error boundary.
2. **Library clipping.** H-91. Header actions must wrap/stack at 900 and 460; route overflow 0.
3. **Acceptance matrix is red and stale.** H-102. S08/S09 were written before the tutor-skill
   context existed; the test must reject the *actual* reference value, not the word "reference",
   and S09 must allow a skill context with zero attempts. The current result is 2 failures in
   22 scenarios, which contradicts the docs' old 22/22 line.
4. **Frequency inventory stranded.** H-101. H-89 is good work but invisible on master; a learner
   still gets no source/licence row. Land it, then expose the facts.

### P2 — a judge notices in the first minute

5. **No stable h1/heading order.** H-92. H-85 found no h1 and a desk AX order of H3 before H2;
   add one h1 per surface, landmarks and a skip link, with AX assertions.
6. **Ten computed type sizes.** H-93. The 4–6 rule is not met; 0.75/0.8/0.8125/0.85/0.875/1rem
   strings are scattered. Tokenize six sizes and a 50–75 ch measure.
7. **Two Parent Studio primaries and a desk stat strip.** H-94. One primary per screen; one
   facts line, not three equal cards.
8. **View switcher disappears.** H-96. Show all three views with a reason when unavailable;
   no 0×0 rail or below-fold combobox as the only path.
9. **Check can render without its question.** H-97. `check.get` has `.catch(() => {})`; a failed
   stimulus read leaves an answer form and a false "shown above" line. Surface Retry.
10. **460 px targets.** H-98. H-80 measured 12 sub-20 px targets and a 16×16 checkbox; audit
    every authored target at 24 px, plus 200 % text.
11. **Duplicate demo rows.** H-99/H-109. Library/Parent Studio currently show repeated courses;
    group by content hash, clean the seed, and add an explicit demo reset.
12. **Bike-repair starter copy.** H-100. `GOAL_PLACEHOLDER` and `TITLE_PLACEHOLDER` still make a
    new learner think the product is for bicycle repair. Replace with a neutral domain gallery.
13. **Cold states unproven.** H-95. H-85 did not reach first-run empty, forced error or loading;
    prove the cold-profile walk and every failure state.

### P3 — product truth and trust

14. **Plan reject is a dead end.** H-103. Turn `rejection_reasons` into plain language and one
    repair action; keep the draft recoverable.
15. **Research unavailable is not a product state.** H-104. Say the profile cannot search, offer
    Check again, and never fabricate sources.
16. **Validator independence is not disclosed.** H-105. `model_assessed` must read as "same
    model", never "independently validated".
17. **Source/provenance panel is too thin.** H-106. Show support status, exact excerpt, modality,
    licence, and the H-89 inventory hash; label model-assessed support.
18. **Pack narration still has no player.** H-107. H-73 froze option (a), but no implementation
    landed; either ship the materialized media segment + player or adopt the honest fallback.
19. **Pronunciation is inert.** H-108. No narration child and no live recording; make the
    unavailable state useful and never fabricate a score.
20. **`single` scope contradicts its copy.** H-112. The UI says one lesson; `SCOPE_EXPECTATIONS`
    allows 4–5 objectives. Reconcile code, blueprint and UI.
21. **Bundled tutor skill is stale.** H-113. The repo skill lacks the no-check procedure path,
    answer-format close and bound-store warning that the user skill already learned.
22. **Silent failures are widespread.** H-114. The `check.get` catch, `useCourseMinutes`,
    `post_llm_call`, import-journal, STT and sources reads need a labelled degradation or a fix.
23. **Install/doctor drift.** H-110. Stale Desktop copy and worktree socket symlinks; a
    professional install should print one exact fix and ignore disposable worktrees.
24. **Security/privacy has residual risk.** H-115. S13/aux grader remains BLOCKED; re-run pack
    attacks, reference-leak probes and egress review on the current tree.
25. **Release docs contradict the tree.** H-111/H-116. Reconcile counts, pins, gates and
    "not shippable" prose; no tag/PR/announcement without the owner's sign-off.

### Upgrades worth building after the defects

26. **Progress and cost.** H-117: stage/elapsed/cancel from the durable job; backend-sourced
    usage only.
27. **Spaced review.** H-118: make the due queue and next review action visible; no fake XP.
28. **Placement.** H-119: optional 3–5 item diagnostic instead of a free-text level guess.
29. **Conversation practice.** H-120: bounded scenario, turn limit, one rubric; backend verdict.
30. **Export/share.** H-121: approved-course export with a hash and privacy preview; import gives
    Resume vs fresh.

## Card set (30 cards)

| Card | Owner | Depends | Purpose |
|---|---|---|---|
| H-92 `t_4a1982cf` | vellum | H-91 | h1/landmarks/skip |
| H-93 `t_cd7f3da6` | vellum | H-92 | type/density |
| H-94 `t_deb0cb35` | vellum | H-93 | one primary/facts line |
| H-95 `t_d8465fd5` | cbqa | H-91 | cold states |
| H-96 `t_581c7874` | vellum | H-95 | view switcher |
| H-97 `t_66312e2b` | vellum | H-96 | check stimulus |
| H-98 `t_6665aa8d` | vellum | H-97 | 460 targets |
| H-99 `t_633b248a` | vellum | H-98 | course shelf/dedupe |
| H-100 `t_9406a6d1` | vellum | H-99 | starter copy |
| H-101 `t_6d9474b5` | atlas | H-91 | land H-89 + source facts |
| H-102 `t_86021cbf` | cbqa | — | S08/S09 acceptance |
| H-103 `t_61462c1a` | vellum | H-100/H-101 | rejection UX |
| H-104 `t_4ca5dd3b` | vellum | H-103 | research unavailable |
| H-105 `t_042a0028` | vellum | H-104 | validator truth |
| H-106 `t_96e05b28` | vellum | H-105 | provenance panel |
| H-107 `t_58acb60e` | cinder | H-106 | pack media playback |
| H-108 `t_20c0760e` | cinder | H-107 | pronunciation states |
| H-109 `t_b9f48420` | lattice | — | demo data hygiene |
| H-110 `t_a7d42b68` | sable | — | install/doctor |
| H-111 `t_e9b90a9a` | harbor | — | release truth |
| H-112 `t_17db986e` | cinder | H-103 | single scope |
| H-113 `t_8a6c3602` | lattice | — | tutor skills |
| H-114 `t_a71e3255` | sentinel | — | silent-failure sweep |
| H-115 `t_6d73e0df` | sentinel | — | security/privacy |
| H-116 `t_b989cc25` | harbor | — | release/marketplace |
| H-117 `t_950a39d4` | vellum | H-108 | progress/cost |
| H-118 `t_ed4c27e5` | vellum | H-117 | spaced review |
| H-119 `t_657ef10d` | vellum | H-118 | placement |
| H-120 `t_5eadfbca` | vellum | H-119 | conversation |
| H-121 `t_04d37587` | vellum | H-120 | export/share |

The first wave is deliberately read-only or file-disjoint: H-102 (tests), H-109 (seed/data),
H-110 (install scripts), H-111 (docs), H-113 (skills), H-114/115/116 (audits). UI cards are
chained behind H-91 and each other because `desktop/plugin.js` has one writer. Do not fan them out
in parallel.

## What I did not prove

- No live cold-profile walk yet (H-95).
- No live Guided/Field Quest capture until H-91 lands.
- No provider-spend generation; plan rejection evidence is from the existing probes.
- H-89/H-90/H-85 branch evidence was read from their handoffs and diffs, not re-run on a merged
  tree; H-111/H-101 must re-derive before calling it release evidence.
- No security claim beyond the existing pack/attack suite; H-115 is a new audit.

## Standard

Use `docs/UX-RESEARCH-STANDARDS.md` as binding. No raw colour outside the token contract, no
uppercase labels, no decorative bars, no nested cards, no second primary, no empty/loading/error
without one next action, and no claim that automation certifies accessibility.
