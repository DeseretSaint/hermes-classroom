# Coursebook quality bar

**Status:** binding, 2026-11-07. Applies to every worker who ships a Coursebook surface: design,
Desktop UI, backend-visible states, copy, game mechanics, demo data and release evidence.
**Authority:** where this file and a visual idea conflict, this file wins; a written owner override
wins over both. The four design laws outrank taste.

## The bar in one sentence

A cold user can tell, within three seconds, where they are, what the one next move is, and that
nothing is pretending — and the loop feels designed for this subject, not reskinned from a generic
quiz. Artifacts can be *"technically correct and visually polished yet land wrong for a real
person"* (`~/Obsidian/personal-vault/JP-Lingo/humanifier-research.md:6`).

`docs/ADVERSARIAL-REVIEW-V3.md:22` requires every stored fact to reach a named, accessible,
recoverable state, and every failure to say what happened and what to do next. An honest but inert
path is not a learning product.

## 1. What high quality means

### Visually

- **One focal hierarchy per frame.** Squint: primary, secondary, groups still name themselves in
  order. Two dominant elements, or "balanced symmetry", is a defect (`CRAFT-LENS.md:8`).
- **One type system, six sizes maximum per route.** Body-first ramp; line-height inverse to size
  (display ~1.12, body ~1.5); measure 50–75ch (66 ideal, 80 cap); sizes from tokens.
- **Flat and warm, two hues plus coral.** Paper, ink, one lamp field, 1px rules; no gradient,
  shadow, glass or glow. Hierarchy comes from scale, space, weight and one accent; every hue sits
  beside its word.
- **The path is a route, not a card grid.** Ordered nodes, one current, one visible next, a state
  word on every node. Duolingo sells *"a clear path to follow"* for learners unsure they were using
  it the "correct" way.
- **Target-language legibility outranks brand voice.** Japanese reading may use a CJK serif, but
  labels and small text use a legible CJK gothic (`JP-Game-OSS-Quality-Stack.md:18-21`).

### Functionally

- **Every stored fact reaches a named, accessible, recoverable state.** A count, due item, failed
  read or detached chat gets a surface, a word and a way forward.
- **One primary action per screen; every control works or is absent.** A failed read is never an
  empty course, and no dead button, 0×0 rail, duplicate row or unexplained disabled control ships.
- **Profile slots are explicit and isolated.** The active slot is named in text wherever an action
  can be taken; switching is deliberate; each slot shows only its own state.

### Interactively

- **Feedback in the next painted frame.** Press, submit, open and retry acknowledge before the work
  finishes: 100–200ms feedback, 200–300ms enter/exit, transform and opacity only.
- **A checkpoint is a real commit, and retry is free.** Pending, failed, retry, accepted and "needs
  review" are distinct visible states; a wrong answer gets the model, the reason and the next
  attempt — never a buzzer, lost heart or shaming line (`humanifier-research.md:9,22`).
- **Keyboard, focus, screen reader and reduced motion are complete paths.** Reduced motion keeps
  meaning: opacity may remain; position and scale go. Nothing steals focus or navigates on its own.

### In content

- **Plain words at an 8th-grade level for chrome, instructions and errors.** Not for subject
  material or the target language; never flatten a lesson to hit a readability score.
- **No internal vocabulary; every row says one thing.** `not_started`, `model_assessed`, `pack_id`,
  `binding` are contract words. One next step, or one metadata cluster, not both; numbers appear
  only when they change a decision, and limitations stay visible in place.

## 2. The game layer: mechanics we build from

The baseline is not "add points". It is the vault's game research under one hard constraint: **the
game lives inside the learning task** (`game-designer-research.md:117`). No economy, shop, energy or
meta-game beside the lesson.

| Mechanic | What it means in Coursebook | Source |
|---|---|---|
| Self-determination | Competence: the path shows what you can now do. Autonomy: the learner sets pace. Relatedness: a shared parent/learner view, not a public league. One or two metrics; concrete counts beat points. | Q240:1308,1332 |
| Streaks, if used | Loss-aversion shifts motivation to obligation. Ship only with a durable daily fact, a freeze/repair path and "total practice days"; never punish a break. | Q240:1328 |
| Progression as story | Unlocks are path milestones ("the next lantern"), not XP thresholds. A session is a 3–8 minute arc: enter, teach, check, settle, exit; one checkpoint, an explicit end. | `storyteller-research.md:9,12` |
| Show, don't tell; choice gates learning | The path and checkpoint embody the idea; no copy names the theme. Choice must change what is practised; cosmetic choice is slop. | `storyteller-research.md:7-8` |
| Feel beats | The unit is the beat, not the screen: pre-turn gather, preview, attention cue, post-turn settle, progress-readout feel. Design before and after the answer. | `game-designer-research.md:43` |
| Juice, transitions, audio | The biggest quality levers, but semantic and low-stim: one authored transition per commit; audio only when it carries teaching. No shake, damage numbers or coin SFX. | `JP-Game-OSS-Quality-Stack.md:6-16` |
| Anti-generic test | "Could this be reskinned to medieval Europe? If yes, redesign." | `game-designer-research.md:119` |
| Mistake tolerance + human check | Free retry, no shaming; one persistent teaching voice with a bounded arc, not a mascot; warmth over threat. Five lenses (kid, parent, native, cultural, tone); verdict SHIP/FIX/BLOCK. | `humanifier-research.md:9,22,27`; `storyteller-research.md:10-11` |

**UI never invents a learning mechanic**: the game designer owns mechanics, the UI renders backend
facts (`ui-ux-research.md:18`). **No bespoke progress tables**: mechanics write only existing events
(`game-designer-research.md:72,120`).

## 3. Ten hard gates

Done means every gate passes on the shipped module, not on a concept plate.

| # | Gate | Pass condition | Proof |
|---|---|---|---|
| G1 | Focal hierarchy | One primary; squint names primary → secondary → groups; no second filled button | Default-variant count + screenshot |
| G2 | Type and measure | ≤6 sizes/route; label ≥0.75rem; body ~1.5; measure ≤66ch | Token test; computed probe |
| G3 | Token purity | No hex outside literal; no gradient/shadow/backdrop; one radius family; 1px rules | Token test + grep |
| G4 | States | First-run, empty, filtered, loading, backend-off, stale, error, offline, detached, profile switch each have WHY + one next action | Route × state captures, 1049/900/460, both themes |
| G5 | Copy truth | Banned-token grep empty; counts match fields; no invented %/ring/XP | Copy test + field trace |
| G6 | Engagement | ≤2 metrics; every node/badge/checkpoint traces; streak has freeze + total days | Field trace + copy audit |
| G7 | Accessibility | axe `wcag22aa` clean; keyboard/focus/SR; 24px floor, 44px field; no colour-only | axe JSON + manual pass |
| G8 | Responsive | Zero overflow/clipping at 1049/900/460 + 200%; no 0×0; every surface one click | Overflow captures |
| G9 | Feedback | INP ≤200ms; next-frame press; skeleton matches, 200ms; no blank spinner | Trace + screenshot pair |
| G10 | Evidence | sha + command + artifact + date; shipped module; cold-profile walk | Bundle; reviewer reproduces one gate |

## 4. Contradictions in the current product — and the ruling

| Contradiction | Where | Ruling |
|---|---|---|
| The repo bans XP, streaks, leagues and levels "ever"; the owner's baseline is game research with streaks and progression | `COURSEBOOK-VISUAL-IDENTITY-V2.md:885`; `FIELD-DESK-RESEARCH.md:91`; Q240 | The ban was against fabricated facts, not motivation. SDT-backed mechanics are allowed when the fact exists: ≤2 metrics, no public league, streak only with freeze + total days + no loss framing. |
| Owner wants a Duolingo-like game; the constraint is "game = learning" | `game-designer-research.md:117` | No currency, shop, energy, loot or XP economy. The path, checkpoint and evidence are the game. |
| 4–6 type sizes vs eight identity roles and ten computed sizes in the build | Playbook Q1; `COURSEBOOK-VISUAL-IDENTITY-V2.md:189`; `ADVERSARIAL-REVIEW-V3.md:56` | A per-route budget, not a token census. Roles may reuse a step; label floor 0.75rem, not 0.6875rem. |
| No card rows, nested cards or hero-metric strips vs card walls and three count blocks in the build | `UX-RESEARCH-STANDARDS.md:64,68`; `UX-AUDIT-ROUND3.md` F1; `ADVERSARIAL-REVIEW-V3.md:57` | Rows on rules, one featured element, one line of labelled facts. Cards only for the ≤3 shelf, never nested; one row per course. |
| "No motion by default" vs "motion must read as the intended physical act" | `COURSEBOOK-VISUAL-IDENTITY-V2.md:226`; `CRAFT-LENS.md:7` | No decorative motion; every state change gets next-frame feedback and one authored functional beat, semantic and low-stim. |
| 6th–8th-grade copy vs college-level and Japanese content | `UX-RESEARCH-STANDARDS.md:72` | The rule governs chrome, instructions and errors only; subject content keeps its register. |
| Profile slots are new; the build exposes `profile` only as internal scope | `desktop/plugin.js:442-455`; `docs/PRIVACY_EGRESS.md:84-91` | The slot is a data boundary: visible as text, explicit switching, that slot's own loading/home/empty state. No cross-slot cache, no auto-switch. |

## 5. Refuse list

| Refuse | Replace with |
|---|---|
| Bolted-on PBL: points, badges, leaderboards or quests with no SDT job | The path, real checkpoints, ≤2 honest metrics. Cite "PBL backfires", not "90% fail". |
| Opaque leaderboard, public rank, controlling competition | A private, opt-in parent/learner summary, not a ladder. |
| Streak shaming or a streak with no durable daily fact | Freeze/repair + total practice days + a neutral break message. |
| Cosmetic branching, fake choice, a stereotyped cultural reskin | Choice that changes practice; Japanese examples, names and sources. |
| Screen shake, damage numbers, coin SFX, confetti per answer | One semantic transition per commit; celebrate milestones only. |
| Cliffhanger, forced session, infinite feed | Explicit session end, 3–8 minute arc. |
| Gradient/glass/glow/shadow; card grid, nested cards, three stat cards | Weight, scale, space, one accent; rows on rules, one line of facts. |
| Raw enums, "Something went wrong", "Learn more", "Get started" | The state word and the next action. |
| Blank-screen spinner, mismatched skeleton, unexplained disabled control | Labelled loader, shape-matched skeleton, a reason and a path. |
| Hover-only, colour-only or unlabelled controls; mascot with no job; duplicate demo rows | Visible/keyboard-reachable, word + shape; functional delight; one row per course. |

## 6. Review checklist

**Before build**
- [ ] One page grammar named, one primary action, one session arc.
- [ ] One signature structural move; any game mechanic has an SDT job and a backend fact.
- [ ] Failure and empty states designed before the happy path.

**Per screen**
- [ ] Squint test names primary → secondary → groups; one `h1`, landmarks, skip link.
- [ ] One primary; every row says one thing; no duplicates; a failed read is never empty.
- [ ] No raw enum, API noun or placeholder; colour redundant; both themes hold contrast.
- [ ] Focus visible at 2px/2px; targets 24px minimum, 44px field/touch; 460 and 200% clean.
- [ ] Pre-answer and post-answer beats exist; retry is free and unshamed; reduced motion holds.

**Before ship**
- [ ] G1–G10 pass on the shipped sha; evidence bundle complete.
- [ ] Game audit: ≤2 metrics, every metric traceable, streak conditions met, anti-generic test passed.
- [ ] Demo data deduplicated; HUMAN-CHECK verdict is SHIP.

**Reviewer**
- [ ] Blind pass: artifact + acceptance criteria only; any four-design-law breach is a blocker.
- [ ] Two rounds maximum; then the owner adjudicates.

## 7. How a worker is held to it

Done means **ten gates + evidence bundle + cold walk + human-check**. Not "tests pass", not "looks
plausible"; a missing screenshot is a missing gate.

Severity: blocker / should-fix / nit (`CRAFT-LENS.md`). Blocker = hard-law breach, primary-path gate
failure, fabricated fact, silent failure, crash, clipped control, second primary, or shaming retry.

**The product tells the truth, shows the way, teaches inside the game, and respects the person
using it — on every screen, in every state, at every width.**

## Sources

- `~/Obsidian/dm-vault/knowledge/UI-UX-ONE-SHOT-PLAYBOOK.md` (Q1, Q2, Q8, Q11, Q12, Q18, Q19, Q21), `UI-UX-BUILD-AND-AUDIT-DIGEST.md`, `~/Obsidian/dm-vault/ops/reviews/CRAFT-LENS.md`.
- `~/Obsidian/personal-vault/Design & Render One-Shot Quality — Baseline, Evidence, Gates (2026-09-12).md`; `UI-UX One-Shot Playbook.md` Q240 (L1307–1334).
- `~/Obsidian/personal-vault/JP-Lingo/`: `game-designer-research.md`, `storyteller-research.md`, `humanifier-research.md`, `ui-ux-research.md`; `JP-Game-OSS-Quality-Stack.md`.
- `docs/UX-RESEARCH-STANDARDS.md`, `docs/COURSEBOOK-VISUAL-IDENTITY-V2.md`, `docs/FIELD-DESK-RESEARCH.md`, `docs/ADVERSARIAL-REVIEW-V3.md`, `docs/UX-AUDIT-ROUND3.md`, `docs/UX-SIMPLIFICATION-V2.md`.
- Duolingo: https://blog.duolingo.com/new-duolingo-home-screen-design/ · W3C SC 2.5.8: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
