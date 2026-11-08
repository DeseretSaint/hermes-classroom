# Coursebook experience research: adversarial review and card set

Status: review record, 2026-11-07. Inputs: eight independent research briefs plus the existing
repository standards and the owner's vault baseline. This document records what survived, what did
not, and what becomes a card. It does not claim any recommendation was tested in Coursebook.

Owner clarification applied throughout: the Hollow Knight reference is a **home/launcher** concept
only: open Coursebook, Continue, choose the classroom/save, change a few settings, start learning.
It is not an RPG world map, open exploration, avatar system or game engine. The path is a linear,
Duolingo-like route of lessons and checkpoints.

## 1. Inputs

| Input | File | Evidence note |
|---|---|---|
| Duolingo product survey | `docs/DUOLINGO-RESEARCH.md` | 19 sources; vendor claims and independent evidence labelled. No learning-outcome claim. |
| Game-home patterns | `docs/GAME-HOME-RESEARCH.md` | 18 external sources plus the vault indexes. The vault's canonical `~/projects/*/FINDINGS` trees are not present on this machine; the index claims were treated as baseline, not re-read primary files. |
| Mastery-path evidence | `docs/MASTERY-PATH-RESEARCH.md` | 25 peer-reviewed sources; effect sizes are population averages and carry explicit caveats. |
| Visual/interaction craft | `docs/CRAFT-CHANNELS-RESEARCH.md` | 24 public design sources; duration values are proposed thresholds, not measurements. |
| Engagement evidence | `docs/ENGAGEMENT-RESEARCH.md` | 31 sources; peer-reviewed unless marked vendor/book. |
| Home-hub architecture | `docs/HOME-HUB-ARCHITECTURE.md` | Design only. No contract, schema or code change. Uses existing course + enrollment rows. |
| Current-product audit | this review, §4 | Read-only audit of the current Desktop surfaces; line references at `origin/master` `14a6443`; supplied screenshot predates H-144. |
| Quality standard | `docs/EXPERIENCE-QUALITY-BAR.md` | Binding interim standard; this review applies its §4.1 recommendation rubric. |

The eight research agents were independent. Two were explicitly steered to the owner's vault
baseline: `JP-Lingo/game-designer-research.md`, `storyteller-research.md`,
`humanifier-research.md`, `JP-Game-OSS-Quality-Stack.md` and `UI-UX One-Shot Playbook.md` Q240.
Those files are a research index, not full primary studies; the cards below do not cite them as
proof of an effect.

## 2. Verdict summary

- **ADOPT**: the recommendation is specific, honest, compatible with the existing evidence model
  and likely to improve the first-time learning loop. It gets a card.
- **ADAPT**: the useful core survives, but the literal recommendation would add a fake entity,
  a second product, a child-game costume, or a mechanic the backend cannot support. It gets a
  smaller card.
- **DEFER**: useful later, but not in the first vertical slice, or it needs a contract/item bank
  that does not exist. No card now; the trigger is recorded.
- **REJECT**: it conflicts with the owner's direction, the evidence model, or the product's truth
  rules. No card; removal is folded into an adopted card where relevant.

The main adversarial finding is that **the briefs agree on the loop and disagree on the costume**.
Every serious input says the same thing: one next move, one route, one real check, one honest
result. The disagreements are about seals, profile slots, streaks, world maps and game juice.
Those are exactly where a low-quality build would spend its effort.

## 3. Recommendation review

### 3.1 Duolingo: clarity is decision removal

| Recommendation | Verdict | Reasoning | Card |
|---|---|---|---|
| Continue-first home with the active classroom named | ADAPT | Take the hierarchy; a platform "profile" rail would invent an entity. Use the existing course + enrollment pair. | H-145, H-146 |
| Continue plate with course, section, real counts, one primary | ADOPT | Directly fixes the current desk's equal-weight blocks and duplicate next-step statements. Remove the seal from the plate; keep the title/source identity. | H-145 |
| Vertical route with a state word on every node; future sections tappable | ADOPT | Matches the existing six evidence states and the no-lock rule. Do not reduce six states to Duolingo's three. | H-148 |
| Field Notes / small course rail as secondary context | ADAPT | Keep only what already exists and never let it outrank Continue. No new dashboard. | H-145, H-146 |
| Three-question first run that ends in real work | ADAPT | Keep at most three questions only if each changes the generated course; no tour, no sample lie. The owner wants the deep end, not a slideshow. | H-153 |
| Invariant lesson shell: one stimulus, one response, one footer | ADOPT | The strongest transferable pattern. It is the lesson player, not another card. | H-149 |
| Corrective feedback with the answer and one line of why | ADOPT | Required by the mastery evidence and the existing check contract. | H-149 |
| Checkpoint assembled from the section's own checks, no lock | ADOPT | Aligns with "checkpoint = check event" and no path lock. Do not draw a cumulative checkpoint the backend cannot record. | H-148, H-154 |
| Counts and state words, never a percentage | ADOPT | Existing truth model; the current path has a real zero-evidence fill defect. | H-148 |
| Give the seal a job or explain it | REJECT as stated | The owner has now twice said the seal is confusing. A mark that needs an explanation is not an identity. Retire it from chrome, first-run and pack rows; use title/source/cover identity instead. A tooltip does not rescue it. | H-145, H-153 |
| Fun from scenario, field note, earned ending; one motion/sound | ADAPT | Keep the writing and one functional beat. No mascot, emoji, confetti or reward economy. | H-149, H-152 |
| Reject streak/XP/levels/leagues/hearts/energy/adaptive claims/mascots/full lock | ADOPT | The evidence is strong enough to refuse them in the first slice. A conditional streak is not needed to make the loop good. | H-155 |

### 3.2 Game home: a launcher, not a world

| Recommendation | Verdict | Reasoning | Card |
|---|---|---|---|
| Continue-first "Continue: Chapter 3" with a named end | ADOPT | This is the owner's actual Hollow Knight reference: a home where Continue is the first decision and the next session has a shape. | H-145 |
| Small legible classroom/save slot; chooser only when >1 | ADAPT | Use `learner_label` + course title as the slot; one slot per course. Do not invent "Learner 1", avatars or a character carousel. True multi-learner is a data-model card later. | H-146 |
| Visible route with typed stops (read/practice/checkpoint/review) | ADAPT | Use only types the backend can prove. Do not invent a node type to make the route look game-like. | H-148 |
| Rest stop as a real choice | DEFER | A review-or-continue choice is useful later; the first slice has no separate review run. | — |
| Hub as a place (mood, greeting, threshold) | ADAPT | Mood can come from the classroom identity and the Continue surface. No 3D room, NPCs, mascot or hub world. | H-145 |
| Juice as response: 80–150 ms press, route line, soft confirmation | ADOPT | The current product has almost no temporal feedback. One functional beat per event is the missing layer. | H-152 |
| Profile slots are an identity contract, not a save file | ADAPT | The lesson is "name the current scope and make switching deliberate", not "add profiles". The architecture shows `learner_label` exists; true per-learner evidence does not. | H-146 |
| The Threshold: threshold + route + margin | ADAPT | Recompose the home into a launcher and a route. The margin must not become a stats dashboard; settings live behind one control. | H-145, H-147 |
| Per-objective last opened; "what changed"; review run; sound/haptics later | DEFER | Good roadmap; none is needed to prove the first loop, and several need backend reads. | — |
| Never XP/levels/badges/leaderboards/streaks/loot/mascots/DEFEATED | ADOPT | One progress truth: evidence. | H-155 |

### 3.3 Mastery path: the learning evidence

| Recommendation | Verdict | Reasoning | Card |
|---|---|---|---|
| A node is one capability stated as an exit performance, with prerequisites, check family and misconceptions | ADOPT | This is the difference between a course and a topic list. It should govern generation, not be a decorative badge. | H-154 |
| Checkpoints are gate, delayed and cumulative checks; delayed is the real signal | ADAPT | Gate + delayed are compatible with the existing evidence states. Cumulative checks need unit-scoped checks that do not exist; do not draw them yet. | H-154, H-148 |
| No universal three-in-a-row pass rule; define criterion per target | ADOPT | Prevents fake mastery rules. | H-154 |
| Feedback loop: cold attempt → verdict → explanation → different re-attempt → schedule | ADOPT | This is the lesson player's core interaction, not an optional copy change. | H-149 |
| Spacing: failed review must not reset to day 1; pass must not jump to the end | ADOPT | The existing ladders are defensible; the reset/jump rules are concrete fixes. | H-154 |
| Interleaving: block first acquisition, interleave confusable categories later; words are negative | ADAPT | Use in generation policy; do not random-mix vocabulary in the name of "interleaving". | H-154 |
| Defensible mechanics: path position, competence feedback, autonomy, implementation intentions, cooperative goals | ADOPT | Keep the first four as design constraints; cooperative/social is not in the slice. | H-155 |
| Not defensible: XP/coins/levels, default leaderboards, loss-framed streaks, badges, mastery percentages, learning styles, 2-sigma | ADOPT | Refuse list; audit for these strings and visuals. | H-155 |
| Show a state word, not a score | ADOPT | Existing evidence vocabulary is enough. | H-148 |
| Do not lock the whole path; offer "continue with this unresolved" | ADOPT | Matches the product's parent/learner needs and the completion evidence. | H-148, H-154 |

### 3.4 Craft: the missing temporal layer

| Recommendation | Verdict | Reasoning | Card |
|---|---|---|---|
| One object owns the first viewport; one focal hierarchy | ADOPT | The home and lesson both currently scatter attention. | H-151 |
| Path perspective 56/40/28, 44/32/24 at 460; current ring/halo | ADAPT | Good spatial hierarchy; map to tokens and validate at 460/200%. Do not copy the exact pixel values blindly. | H-148 |
| Depth by overlap, one overlap per screen | REJECT for the slice | Adds composition risk without improving comprehension; the current flat system is not the bottleneck. | — |
| Squint and greyscale review | ADOPT | Cheap, effective review gate. | H-151, H-155 |
| Illustration must encode identity, position or state; delete redundant pictures | ADOPT | Directly answers the seal problem and avoids decorative art. | H-145, H-153 |
| Plate-scale marks only; no per-row ornament | ADOPT | Pack rows and course rows should be text/identity first. | H-145, H-150 |
| One mark grammar including the seal | REJECT the seal; ADAPT the rest | Keep route/gate/horizon marks only if they encode real state. The seal is retired from primary surfaces. | H-145, H-148 |
| Codicon only, 16/20 px; no coloured icon tiles | ADOPT | Replaces the current thin icon language without adding an asset pipeline. | H-151 |
| Motion ladder and reduced-motion equivalents | ADOPT | The module has one transition and zero keyframes; this is the missing feel layer. | H-152 |
| Sound off by default, three state one-shots; haptics desktop no-op | DEFER | Optional later; do not make the first slice depend on audio or pretend desktop haptics exist. | — |
| Eight control states, next-frame feedback | ADOPT | Needed for clickable rows and lesson controls. | H-151, H-152 |
| Seven-beat aliveness kit | ADAPT | Keep route settle, tick commit, press, verdict, completion. Drop seal draw, beacon loop and decoration. | H-152 |
| Slop ledger and computed-style tests | ADOPT | Fold into the quality bar and review gates. | H-155 |
| React/Desktop contract: tokens, one motion source, CbPressable | ADAPT | Use the contract for the core surfaces; migrate only call sites the cards touch, not all 200+ blindly. | H-151, H-152 |

### 3.5 Current product audit

| Recommendation | Verdict | Reasoning | Card |
|---|---|---|---|
| Replace route-header seal with a Coursebook wordmark; real page h1 | ADOPT | The 24 px seal reads as an avatar/refresh glyph; the product name is absent. | H-145 |
| Remove blank 16:9 covers from all browsing surfaces, not just Library | ADOPT | H-144 fixed Library only; All Courses and the desk shelf still use `CourseCover`. | H-150 |
| Make `CoursePath` truthful: no accent fill at zero evidence, one segment per objective | ADOPT | A blue first segment at zero evidence is invented 25% progress. This is a P0 truth defect. | H-148 |
| Rebuild Library header: one h1, one lead, correct filters, trust below list | ADOPT | Three "Library" labels and a lead that contradicts the source badge. | H-150 |
| Make the pack row one whole-row target with visible selection | ADOPT | Current title is dead; only the small Preview button works. | H-150 |
| PackFacts is a preview, not an inspector; technical details closed | ADOPT | `revision 12` and `pack_id` are not learner facts. | H-150 |
| Navigation Home / Courses / Library / Parent Studio; active profile chip | ADAPT | Add Home as the launcher and move the all-courses catalog behind Courses. Do not invent a profile chip; use the classroom name and switch. | H-145, H-146 |
| Page h1 at display size; PlateHead at heading; remove duplicate titles | ADOPT | Current h1 is 1rem while a section h2 is 1.5rem. | H-151 |
| One Coursebook action primitive; stop host-blue primary | ADOPT | 211 host buttons and only three token-styled primaries. | H-151 |
| Learner-copy pass: remove design notes, raw revisions, pack IDs, "1 objectives" | ADOPT | The UI explains its implementation instead of the learner's task. | H-150, H-153 |
| Simplify ContinueCard: one primary, one tertiary, remove repeated next-step sentence; move seal | ADAPT | One primary and one secondary; drop the seal rather than moving it. Keep "Why this is next" only if it has real evidence. | H-145 |
| Apply the measured route gutter; stop unused `routePad` | ADOPT | The reading column is squeezed when the route is narrow. | H-145 |
| Ship a small motion contract | ADOPT | Same as craft; no seal draw. | H-152 |
| De-duplicate PathPreview and OverviewView; one evidence count | ADOPT | The same count is printed twice and every node has equal weight. | H-148 |
| Field Quest: title as h2; counts as caption; one-line mission brief | ADOPT | Counts are not the hero; full prose belongs in Textbook. | H-157 |
| Reduce Course Detail's eight peer tabs to four primary | ADAPT | Good later; keep Plan/Sources/Export under More. Do not do it in the first slice. | H-157 |
| Rebuild first-run and empty states as one plate | ADAPT | One plate, one primary, one secondary; remove the progress paragraph and support note from the learner surface. Keep necessary setup questions. | H-153 |
| Clean demo profile | COVERED | H-109 owns demo-data hygiene; do not create a duplicate. Verify its seed in the live profile before the demo. | H-109 |

### 3.6 Engagement and architecture

| Recommendation | Verdict | Reasoning | Card |
|---|---|---|---|
| Evidence-backed momentum; progress is a measurement, not a prize | ADOPT | The product already has the right truth; the UI must express it. | H-148, H-155 |
| Sell the next capability, not the next reward | ADOPT | Use exit-performance copy in Continue and path. | H-145, H-148 |
| Cue-based habit/reminders; implementation intentions | DEFER | No notification channel in this slice; do not fake a reminder. | — |
| Difficulty as the game / 80–85% success | DEFER | Requires an item bank/placement; H-119 owns optional placement. Do not claim adaptivity. | H-119 |
| People in the loop, not on a podium | DEFER | Parent/learner co-view is a later slice; no public ranking. | H-156 |
| Fun through fiction/voice, not pressure | ADAPT | Scenario voice and earned end; no mascot or narrative economy. | H-149 |
| Adult vs parent/child defaults | ADOPT | Parent Studio stays separate; no loss-framed child defaults; parent view reports evidence, not XP. | H-156 |
| Metrics: durable learning, evidence coverage, guardrails | ADOPT | Make it an audit/measurement card, not a visible dashboard. | H-155 |
| A classroom slot is course + active enrollment | ADOPT | Do not invent a new profile entity. | H-146 |
| One slot per course; disclose duplicate enrollments | ADOPT | Course-scoped evidence would make two slots look like two learners. | H-146 |
| Continue reads the selected slot's next step | ADOPT | One primary action, no N Continue cards. | H-145, H-146 |
| Checkpoints are check events, not save points | ADOPT | No fake milestones. | H-148, H-154 |
| Slice 1 has no contract/schema change | ADOPT | Keeps the first build honest and small. | H-146 |
| Rename classroom, authored-course fork, true multi-learner | DEFER | Each is a separate data/contract card with real migration risk. | — |
| Home is a launcher, not a fourth destination conflict | ADOPT | Make Home the first destination; Courses is the catalog. Do not add both a Home and a Courses home. | H-145 |
| Home settings: appearance, default view, sound/haptics, reduced motion, per-classroom override | ADOPT | Direct owner request; a compact sheet, not a settings page. | H-147 |

## 4. What fails scrutiny

| Rejected or deferred item | Why | Disposition |
|---|---|---|
| Seal as app logo / brand mark | Owner has asked what it means; it is decorative, `aria-hidden`, and used for five different jobs. | Removed from chrome, first-run and pack rows in H-145/H-153; no seal-draw motion. |
| RPG world map / open exploration / 3D hub / avatars / currencies / game engine | Owner explicitly said Hollow Knight was only a home-page reference. | No card. H-145 is a launcher, not a world. |
| XP, levels, crowns, leagues, hearts, energy, gems, shop | No contract; invented progress; freemium/dark-pattern risk. | Refused in H-155; no card. |
| Default leaderboards, public child ranking, variable loot | Harmful and unsafe; no learning evidence. | Refused in H-155/H-156. |
| Loss-framed streak as the primary loop | Evidence supports loss aversion but not learning; would shift motivation to obligation. | Deferred; no streak in slice 1. Conditional later only with durable daily fact, freeze and total days. |
| Mastery percentage / ring / adaptive difficulty claim | No calibrated item bank; would be a false claim. | Refused; placement H-119 if needed. |
| Cumulative checkpoint drawn in UI | Backend cannot record unit-scoped checks. | Deferred; no fake node. |
| Duolingo 3-screen onboarding as a tour | Owner wants immediate work; standards reject tours. | ADAPT: at most three setup questions only if each changes the course. |
| Profile slots as new learner entities | Evidence is course-scoped; two enrollments would show identical progress. | ADAPT: classroom = course + enrollment; true multi-learner deferred. |
| Seal on Continue plate | The brief suggests it; the owner rejects it. | Removed. |
| Decorative overlap / plate depth / hover lift / seal draw / beacon loop | Adds craft risk without comprehension; current flatness is not the bottleneck. | Deferred/rejected. |
| Sound/haptics in first slice | No sound contract, desktop haptics are a no-op, and audio can be annoying. | Deferred; optional later. |
| Full Course Detail tab restructure | Large surface change; not needed to prove the home/path/lesson loop. | Deferred to H-157 after slice 1. |
| "What changed" digest, review run, per-objective last_opened | Good roadmap; needs reads that are not in the first slice. | Deferred; no card. |
| Test fixtures in the demo profile | Makes the product look like QA. H-109 owns it. | Covered by H-109; verify live seed before demo. |

## 5. Card set

Every ADOPT/ADAPT recommendation above maps to one of these cards. Cards are grouped by the
smallest deliverable that can be built and reviewed without inventing a second product. UI cards
touch `desktop/plugin.js` and therefore run one at a time; the backend/spec and audit cards are
disjoint and can run in parallel.

| Card | Title | Owner | Priority | Depends | Why it exists |
|---|---|---|---|---|---|
| H-145 `t_244cc1ed` | Home launcher: wordmark, h1, Continue-first shell | vellum | P0 | — | The owner's home; removes seal chrome; fixes page hierarchy and app identity. |
| H-146 `t_007fb434` | Classroom rail and selected classroom | vellum | P0 | H-145 | Continue/switch without inventing profiles; one slot per course. |
| H-147 `t_6ed659d2` | Home settings and default learning view | vellum | P1 | H-145, H-146 | Direct owner request: appearance, Game/Guided/Textbook default, sound/haptics, reduced motion, per-classroom override. |
| H-148 `t_0c5a84a4` | Path and checkpoint truth | vellum | P0 | H-146 | Linear route; real evidence states; no fake checkpoint/lock/percentage; fixes zero-evidence fill. |
| H-149 `t_19e116bd` | Lesson player: one concept, one check, one close | vellum | P0 | H-148 | The core learning loop, not a document. |
| H-150 `t_b171870c` | Library shelf hierarchy and whole-row action | vellum | P1 | H-145 | Finish the H-144 direction across Library; remove covers and inspector facts. |
| H-151 `t_26625a60` | Coursebook action and type system | vellum | P1 | H-145 | Replace host-blue/default buttons; one h1 hierarchy; six type sizes. |
| H-152 `t_1a0483ef` | Motion and feedback contract | vellum | P1 | H-148, H-149 | Make press, route, verdict and completion feel causal; no seal draw. |
| H-153 `t_38328bdc` | First-run start plate and cold states | vellum | P1 | H-145 | One honest start; no seal, no tour, no test inventory. |
| H-154 `t_27f1cbb4` | Mastery path and checkpoint policy | atlas | P1 | — | Capability nodes, prerequisites, gate/delayed checks; no fake cumulative check. |
| H-155 `t_e5842655` | Engagement integrity audit | sentinel | P0 | — | Refuse XP/streak/leaderboard/mastery theater; audit every surface. |
| H-156 `t_1589e6f8` | Parent and child defaults | vellum | P2 | H-147 | Parent Studio stays separate; child defaults do not use loss pressure. |
| H-157 `t_821f0924` | Course Detail and Field Quest composition | vellum | P2 | H-148 | Counts as caption, one-line missions, four primary tabs. |

**Already covered; do not duplicate:**

- H-144: Library pack rows, no seal/monogram/cover.
- H-95: cold states and 460 walk; H-153 may refine first-run but must not reopen the full cold-state audit.
- H-92/H-93/H-94: h1/type/one primary; H-151 continues the type/action work.
- H-96/H-97/H-103/H-105: view switcher, check stimulus, plan rejection, validator truth.
- H-109: demo-data hygiene.
- H-121: export/share.
- H-119: optional placement, not adaptive difficulty.

## 6. Gate mapping

Each card must name the quality gates it advances and supply the evidence in
`docs/EXPERIENCE-QUALITY-BAR.md` §8:

- H-145: Q1, Q2, Q3, Q5, Q7, Q12.
- H-146: Q1, Q2, Q3, Q7, Q11.
- H-147: Q1, Q7, Q8, Q9, Q11.
- H-148: Q3, Q4, Q5, Q6, Q7.
- H-149: Q1, Q2, Q6, Q8, Q12.
- H-150: Q1, Q2, Q3, Q5, Q11.
- H-151: Q2, Q5, Q9.
- H-152: Q8, Q9, Q10.
- H-153: Q1, Q2, Q5, Q7, Q11.
- H-154: Q4, Q6, Q11.
- H-155: Q4, Q5, Q11, Q12.
- H-156: Q7, Q9, Q11.
- H-157: Q1, Q2, Q5, Q6.

No card is "done" on source tests alone. A card that cannot show the required screenshots and a
human walkthrough remains open.

## 7. What this review does not prove

- It does not prove that any of these changes make Coursebook learn better. The mastery evidence
  supports mechanisms, not this implementation.
- It does not prove the current audit's 460/focus/motion claims live; the audit was read-only and
  the screenshot predates H-144.
- It does not prove the vault's `FINDINGS` files exist here; `~/projects/*` is empty. The indexes
  and external sources are the basis.
- It does not authorize a publication, marketplace submission or demo claim. The publication gate
  remains untouched.
