# Engagement integrity audit — H-155

Status: audit record and ship gate. Owner: sentinel (adversarial QA). Date: 2026-11-07.
Base: `master` `c6b658e` (cb.rpc v16 / cb.db v11), plugin `desktop/plugin.js` 18,901 lines,
sha256 `035597017a19b77cae14f65eb37fd90c6868ba6f94dd0fc5d6977dd8d6b97b5d`.
Probe: `tests/test_engagement_integrity.py`, sha256
`1a96f489d578e28ed9fa139c428d37a5219178aab0c8ff363189e6f045697c75`.
Register: this file is not `docs/AUDIT-INDEX.md` evidence until its merge commit exists; the
AUDIT-INDEX row (owner: quill) is added at merge with that hash.
Sources: `docs/ENGAGEMENT-RESEARCH.md`, `docs/EXPERIENCE-QUALITY-BAR.md` §2.4/§3/§4.1/§6,
`docs/EXPERIENCE-REVIEW.md` §3.6/§4/§5 — those three live on `wt/h151-action-type` (`1a01f95`),
not yet merged; they were read from that branch and are cited by section.

**Verdict.** The shipped learner surfaces carry evidence, not theater: no XP, no streak, no league,
no leaderboard, no hearts/energy/gems, no mastery percentage or ring, no lock, no variable reward,
no loss-framed reminder. Two primary progression metrics only — objectives with independent
evidence, and objectives due for review. Six defects exist; four are copy/truth defects on
surfaces the redesign cards already touch (`H-148`, `H-150`, `H-157`) and two are pinned to `H-145`.
None of them is a gamification mechanic. The first slice may ship **only** with the refuse list in
§6 enforced and the fixes in §5 applied by the owning cards.

## 1. What was executed (not just read)

| Check | Command | Result |
|---|---|---|
| Copy scan of every non-comment string literal in the shipping pane | `python3 -m unittest tests.test_engagement_integrity -v` | 9 tests, 8 pass, 1 `expectedFailure` (ENG-D1), 0 failures |
| Pure projections executed through Node against the real `desktop/plugin.js` | same suite (`harness.mjs` written by the test) | path/desk/progress output captured in §4 |
| Banned-vocabulary scan of every local branch ahead of `master` | `git rev-list --count master..<b>` + `git diff <base> <b> -- desktop/plugin.js dashboard catalog coursebook \| grep '^+'` | 1 branch ahead touches UI copy (`wt/h118-review`, 2 commits); its only hits are disclaimer comments. No branch introduces a violation. |
| Dirty in-flight UI work | `git -C <worktree> diff -- desktop/plugin.js \| grep '^+'` | `wt/h145-home-launcher` (53 insertions, uncommitted): no banned vocabulary, one new string `Coursebook`. `wt/h64-controls-r2` (unrelated): one `sdk.Badge` state chip. |
| Extra-surface sweep | `grep -rniE 'xp\|streak\|badge\|mastery\|percent\|ring' coursebook dashboard catalog bundled` | `mastery`/`percent`/`streak`/`XP` appear only in docstrings and disclaimers; `dashboard/` and `catalog/` contain none. |

## 2. The vault/engagement rules, checked

| Rule (research / quality bar §2.4) | Evidence in the build | Verdict |
|---|---|---|
| ≤ 2 primary progression metrics, concrete | Home/path show exactly two: *N of M with independent evidence* (`library.list.evidence_summary.independent`/`total_objectives`, `course.outline.objectives[].independent`) and *N due for review* (`review.queue.total_overdue`, `objectives.state ∈ review_due/needs_review`). Everything else on the surface is a state word, an ordinal, or a real plan fact (session estimate). | PASS |
| Competence: progress shows what the learner can now do | `OBJECTIVE_STATE_COPY` (7 states, contract `objective_state`), `progressStatement()` ("N of M objectives have independent evidence"), `verdictTakeaway()` repeats the graded `observed` criterion — never a compliment generator. | PASS |
| Autonomy: pace, session length, difficulty are the learner's | Create flow dials (recipe, session length), optional placement (H-119), plan review/approve, review actions `Snooze / Stretch / Drop / Resume`. No mandatory daily goal, no appointment timer. | PASS |
| Relatedness: no public ranking; parent sees evidence, not XP | No ranking surface exists (`leaderboard|league|podium` = 0; `rank` appears once, in the disclaimer "there is no marketplace ranking and no verified badge"). Parent view reports `evidence_class`, attempts and state words (H-156 owns the remaining defaults). | PASS |
| Mistakes are review items, never damage | `coursebook/domain.py:2192` — `verdict ∈ (partial, not_yet) → needs_review`; copy "It will come back for review." No lives, no attempt limit, no loss. | PASS |
| No loss-framed reminders | No reminder/notification channel exists: `host.notify` is used only for in-app warnings/errors. Review card H-147 defers cue-based reminders. No "you'll lose", "streak dies", "47 days" strings (`grep` = 0). | PASS |
| No variable rewards / no randomness in rewards | The only randomness in the pane is an idempotency key (`crypto.randomUUID`). Course marks and shelf fingerprints are deterministic hashes. No loot, spin, near-miss or surprise payout. | PASS |

## 3. Surface-by-surface trace (every number, state and gamified-looking visual)

`plugin.js` line numbers are the base commit's. "Backend field" names the contract field or command
the value is read from; nothing in this table is computed by the UI except a count of an array it
was given.

| Surface | String / visual | Backend field | Verdict | Fix |
|---|---|---|---|---|
| Home · Continue plate (`ContinueCard` 2706) | `Section 1 of 4` | `course.outline.objectives[].ordinal`, `outline.total` | pass | — |
| Home · Continue plate | "N of M sections have evidence · D due" (2866) | `evidence_summary.independent`/`total_objectives`; `objectives.state` | **defect ENG-D5** (duplicated in the tally caption two lines later) and **ENG-D4** — the template has no singular branch, so `M=1` renders "1 of 1 sections have evidence" | H-145: keep one statement |
| Home · `DeskFacts` (2691) | `N of M — With evidence`; `D — Due now`; state word | same summary + `objectives.state` | pass | — |
| Home · `DeskProgress` (2660) | 12 segments, per-objective tint, `opacity .32` when `not_started`, `aria-hidden` | `outline.objectives[].state` via `DESK_STATE_TONE` | pass (segment = one objective, never a percentage) | — |
| Home · session estimate | `≈ 6 min` / `Session length not recorded` / `Session length could not be read` | pack manifest `estimated_minutes` (`useSessionEstimate`), three states kept distinct (`deskEstimateState` 2264) | pass | — |
| Shelf row · `CoursePath` (2377, `cbCoursePathSegments` 8973) | four segments; first segment `background: var(--cb-accent); opacity: 1` at **zero evidence** | `evidence_summary.independent`/`total_objectives` | **defect ENG-D1** (P0, Q4): one filled segment of four reads as 25 % reached while the caption says "0 of 4 with evidence" | H-148: no `current`/`done` paint before evidence |
| Shelf row caption | "N of M with evidence · D due" | same | pass (counts, clamped; hostile `999` → `4 of 4`, unreadable → "No sections yet") | — |
| Shelf disclosure (`ShelfDisclosure` 2415) | `· 990ee883` after the title | `cbShelfFingerprint()` = FNV hash of title/recipe/locale/objectives/pack | **defect ENG-D3** (Q11): unexplained raw identifier on a learner row | H-150: drop it, or show the pack version only |
| Courses / All Courses | course title, "N courses shown", filter counts | `library.list` rows, client count of returned rows | pass | — |
| Library · `PackFacts` (3995) | raw `pack_id` chip (4014), `revision 12` (4032), "N objectives · M due" (4037) | `provenance.pack_id`, `revision`, `evidence_summary` | **defect ENG-D3** (pack_id, revision) + **ENG-D4** (plural) | H-150: `pack_id`/`revision` belong in the closed technical details |
| Pack preview (`PackPreview` 1378) | manifest version, locale + `level_label`, file roles, content hash, "N check(s)" (1525) | `manifest.*` fields, `manifest.level_label` | pass for the fields (real manifest); **ENG-D4** for "check(s)" | H-150 |
| Course Detail hero (14657-14668) | `Section N of M`; "N of M — With independent evidence"; `D — Due for review` | `course.outline`, `review.queue.total_overdue` | pass | — |
| Path index (`SectionRow` 12912, `UnitHeading` 12988) | ordinal, state word + icon (`Not started/Started/Complete/Review due/Review needed/Moved on without a grade`), unit sentence "This unit starts after Unit 1. You can still open it." | `objectives.state` verbatim; `units.prerequisite_state` | pass — no node is disabled or locked; no fake checkpoint | — |
| Path state word fidelity | `delayed_evidence` and `independent_evidence` both display **Complete** (`SECTION_STATE_SEMANTIC` 7014) | `objectives.state` | pass with note (§9): the mapping loses the "delayed" distinction on the index; the raw state word is still shown on Evidence and lesson surfaces. Route to H-148 as an improvement, not a violation. | optional H-148 |
| Lesson views (`TextbookBlock`, `GuidedBlock`, `QuestMission` 11088) | `Step 3 of 7`, `Mission`/`Checkpoint` labels, "Missions are the reading path" | `lesson_document` blocks; `block.check_id`; `document` counts | pass | — |
| Field Quest header (11270) | "N missions, C checkpoints" | document block count / `check_id` presence | pass | — |
| Quest checkpoint without a check (11233) | "No check could be attached to this checkpoint, so the mission stays readable and ungated." | `block.check_id` | pass (a checkpoint with no check is disclosed, not gated) | — |
| Check verdict (`AttemptVerdict` 7414, `VERDICT_COPY` 7146) | `Passed` / `Partly there` / `Not yet` / `We could not grade this answer`; `Self-reported pass` | `attempts.verdict`, `attempts.evidence_class` | pass — no XP, no points, no "keep it up" | — |
| Check feedback | "What you showed: …" + "This check is independent evidence for one objective, not mastery of the whole course." | graded `criteria[].observed` | pass | — |
| Try again / retry | "Tick the remaining steps and submit again. This stays your own report." | `attempts.state`, `next_action` | pass (retry is free, unshamed; failure becomes `needs_review`) | — |
| Evidence class chip (`EvidenceClassText` 7185) | `First try, no hints` + "Independent evidence is worth more…"; `Reported by you — not independently verified.` | `attempts.evidence_class` | pass | — |
| Pronunciation studio (`PronunciationStudio` 10066) | `Recogniser confidence 84%`, "N of M words matched", "not verified pronunciation and not a graded score" | `assessment.confidence`, `assessment.words[].match`, `assessment.transcript` | pass with note (§9): the only percentage in the product, a recogniser confidence, explicitly disclaimed | — |
| Evidence tab (`EvidenceView` 13985) | `L3 · current recommendation`, `L2 · objective evidence`, `L1 · attempts and events`, `basis: layer2.independent == false`, "derived from layer 2. Not a persona claim." | `evidence.l1/l2/l3`, `l3.recommendations[].basis` (`coursebook/evidence.py:216-234`) | **defect ENG-D2** (Q11): internal layer names and a raw predicate in learner copy | H-157 (or the Q11 owner): plain words; keep the exact basis in a closed technical panel |
| Evidence tab | `next review <date>`, `interval 7d · step 3`, "Revisable and derived from layer 2…" | `review.queue.items[].due_at/interval_days/step` | pass for the numbers (declared heuristic, contract §review.queue); ENG-D2 for the wording | H-157 |
| Notebook / Quizzes / Plan | saved-moment counts, attempt verdicts, objective states | `notebook.list`, `quizzes.attempts`, `course.outline` | pass | — |
| Sources tab | `source_type`, `support_status`, `published <date>` | `sources[]` rows | pass (support is an assessment, never a "verified" badge) | — |
| Export view (14287) | "N of M lesson page(s) validated", content hash, bytes | `course.export` read: `sections.validated/total`, `content_hash`, `files[].bytes` | pass for the numbers; **ENG-D4** "page(s)" | H-157 |
| Parent Studio (`ParentBriefForm`, plan gates) | reading level, age band, plan `version`, `State: <state> · check: <state>`, approval badges | `parent.brief.create` fields, `plans.version`, `plan state`, `checks.state` | pass — reads evidence, never XP | — |
| Parent reflections | "parent-reported · <date>", "not evidence of learning, never graded" | `reflections.evidence_class = parent_reported` | pass | — |
| Syllabus intake | `${weight}%` / `${weight} points`, "counted from your term start", "N of M items have a decision" (6398) | extracted `assessments[].weight`, `weight_unit`, `due`, `derivation` | pass for the numbers (the syllabus's own grade weight, with derivation); **ENG-D4** for "N of 1 items have a decision" | H-157 / syllabus card |
| First run / cold states | "Nothing here is sample data", "no progress percentage until the plan exists" | `runtime` method registry, job state | pass — no fake tour, no sample course | — |
| Chrome · seal (`SurveyMark` 9027) | decorative `aria-hidden` mark on first-run (1140), shelf cover (2524), Continue plate (2808), Course Detail hero (14713), route header (18230) | none (decorative) | **defect ENG-D6** (Q5): an ornament that needs explaining, on primary surfaces; the review already ordered its retirement | H-145 / H-153 |
| Settings | — | — | n/a — the sheet does not exist yet (H-147); sound/haptics and reduced-motion must ship as opt-in toggles, never as an engagement lever | H-147 |
| Reminders / notifications | — | — | n/a — no channel in this build; any future reminder must reference the cue and carry an opt-out (§7 M5) | future card only |
| Demo pack content (`bundled/`) | teaching text | pack files | pass — no gamification copy | — |

## 4. Reproduced defects

### ENG-D1 — P0, Q4: the shelf path paints progress a zero-evidence course does not have

- Repro: `python3 -m unittest tests.test_engagement_integrity.EngagementIntegrityTest.test_zero_evidence_path_paints_no_reached_segment -v`
- Expected: at `independent = 0`, `total_objectives = 4`, no segment is painted as reached.
- Actual: `cbCoursePathSegments` returns `[{0:"current"},{1:"quiet"},{2:"quiet"},{3:"quiet"}]`; the
  rendered HTML is `background:var(--cb-accent);opacity:1;outline:1px solid var(--cb-accent)` on
  segment 0, while the caption under it reads `0 of 4 with evidence`. One filled segment of four
  reads as 25 % reached.
- Also observed: `independent: 1, total: 4` → segment 0 `done`, segment 1 `current` — i.e. the
  second segment is also painted accent, so one unit of evidence paints 50 % of the bar.
- Fix owner: **H-148** (path and checkpoint truth). Fix: paint `done` only for evidence actually
  held, `due` only when due, and leave every other segment `quiet`/`empty`; the current position is
  already carried by the "Next" row and the caption.
- Status: pinned as `@unittest.expectedFailure`; when H-148 fixes it the test turns green and the
  decorator must be removed.

### ENG-D2 — P1, Q11: internal vocabulary on the Evidence tab

- Evidence: `desktop/plugin.js:13999` `L3 · current recommendation`, `:14022` `L2 · objective
  evidence`, `:14058` `L1 · attempts and events`, `:14009` `basis: ${item.basis}`, `:14015`
  "derived from layer 2. Not a persona claim." `coursebook/evidence.py:216` sets
  `basis = "layer2.independent == false"`, so the learner can literally read
  `basis: layer2.independent == false`.
- Verdict: defect. A learner-facing string may not carry an internal predicate or a layer id
  (quality bar §2.1, gate Q11). The recommendation text itself is evidence-derived and honest.
- Fix owner: **H-157** (Course Detail composition). Fix: replace the three labels with plain words
  ("What to do next", "What the evidence shows", "Your attempts"); move `basis` to the closed
  technical details panel with the other provider/integrity facts.

### ENG-D3 — P2, Q11: raw identifiers on learner rows

- Evidence: `desktop/plugin.js:2468` renders `cbShelfFingerprint(member)` — an 8-hex-digit FNV hash
  (observed value for a parent course: `990ee883`). `PackFacts` prints the raw `pack_id` badge
  (`:4014`) and `revision ${row.revision}` (`:4032`); Course Detail repeats `revision`
  (`:12760`).
- Verdict: defect. These are real backend fields, so Q4 (traceability) is satisfied, but they are
  not learner facts and they are unexplained on a browsing surface (quality bar §2.5). The
  Experience review already classified `revision`/`pack_id` as inspector data.
- Fix owner: **H-150** (Library shelf). Fix: hide the fingerprint; show `pack_id`/`revision` only
  inside the closed "technical details" disclosure with a label that says what they are.

### ENG-D4 — P3, Q11: pluralization in count sentences

- Evidence: `:2866` and `:2873` "1 of 1 sections have evidence"; `:1525` "N check(s)"; `:4037`
  and `:12765` "1 objectives"; `:6398` "1 of 1 items have a decision"; `:14287`
  "1 of 2 lesson page(s) validated".
- Verdict: defect (copy). Does not change a fact, but reads as machine output on a learner surface.
- Fix owners: H-145 (`:2866/:2873`), H-150 (`:1525`, `:4037`), H-157 (`:12765`, `:6398`,
  `:14287`). Fix: one shared `plural(count, one, many)` helper next to `progressStatement` and use
  it for every count sentence.

### ENG-D5 — P3, Q2/Q5: the Continue plate states the same two counts twice

- Evidence: `:2862-2868` plate caption `Course evidence · N of M sections have evidence · D due`
  and `:2871-2875` tally caption `N of M sections with evidence · D due` — same card, same two
  facts, two phrasings, plus the per-objective segments between them.
- Verdict: defect (hierarchy). It is duplicated information, not duplicated metrics; the quality
  bar's one-focal-hierarchy rule and the review's "remove the repeated next-step sentence" both
  apply.
- Fix owner: **H-145**. Fix: keep the tally caption (it sits on the honest record) and reduce the
  plate caption to the course identity or drop it.

### ENG-D6 — P2, Q5: the decorative seal is still on five primary surfaces

- Evidence: `SurveyMark` rendered at `:1140` (first run), `:2524` (shelf cover), `:2808`
  (Continue plate), `:14713` (Course Detail hero), `:18230` (route header). It is `aria-hidden`,
  deterministic per course id, and encodes nothing a learner can name. The Experience review
  (`§3.1`, `§4`) and the owner have rejected it as identity.
- Verdict: defect (Q5, "no unexplained decorative mark"). It invents no fact, so it is not an
  engagement violation — but it is the kind of decoration a gamified redesign would multiply.
- Fix owners: **H-145** (chrome, Continue plate), **H-153** (first run). Fix: remove; use the
  title/locale/level line and the survey-free cover.

## 5. Defect → card map (blocking status)

| Defect | Severity | Owner card | Blocks that card? |
|---|---|---|---|
| ENG-D1 zero-evidence path paint | P0 | H-148 | **Yes** — H-148 exists to fix it; the card cannot claim Q4 without the test green |
| ENG-D2 internal layer vocabulary | P1 | H-157 | Yes for Q11 on the Evidence tab |
| ENG-D3 raw fingerprint / pack id / revision | P2 | H-150 | Yes for Q11 on Library |
| ENG-D4 pluralization | P3 | H-145, H-150, H-157 | No — must be fixed in the card's copy diff |
| ENG-D5 duplicated counts on Continue | P3 | H-145 | Yes for Q2 on Home |
| ENG-D6 seal on primary surfaces | P2 | H-145, H-153 | Yes for Q5 |

Every other card in the slice (H-146, H-147, H-149, H-151, H-152, H-154, H-156) ships with no
engagement defect against this audit's base. They are still bound by §6.

## 6. Refuse list — what reviewers block without discussion

A UI/product card is refused (not "fixed later") if its diff or its rendered surface introduces any
of the following. Each line names the mechanic and the concrete trace that makes it a violation.

1. **XP, points, coins, crowns, gems, currency, a shop.** Any earned number that is not a stored
   evidence/attempt/schedule fact. Trigger strings: `XP`, `xp`, `+N points`, `credits`.
2. **Levels / leagues / promotion / demotion.** `Level` is allowed only as a subject level
   (`reading level`, `level_label` in a pack manifest). A level that grows with time or completed
   lessons is refused.
3. **Streaks, chains, "don't break it", freezes, repair, "days in a row", any per-day counter.**
   The conditional streak is deferred (quality bar §6.2); it is not in the first slice, so no
   streak string, badge or calendar strip may appear.
4. **Leaderboards, ranks, percentiles, public or household comparison, "top learner".** Relatedness
   is a shared parent/learner view of evidence (H-156), never a ranking.
5. **Badges / trophies / certificates as rewards.** The host `sdk.Badge` is allowed only as a text
   chip for a backend enum (evidence class, source type, plan state). An earned badge, an
   attendance trophy, or a badge with a name the learner "unlocks" is refused.
6. **Hearts, lives, energy, attempt limits, pay-to-skip, time gates.** Retry stays free; a failure
   becomes `needs_review` (`coursebook/domain.py:2192`).
7. **Mastery percentages, progress rings, "X% complete", "mastered".** Counts only
   (`N of M with evidence`). A percentage is allowed only for a *recogniser confidence* that is
   labelled as such and disclaimed as not a score.
8. **Fake locks, fake checkpoints, decorative gates.** A checkpoint is the section's own check
   event (`block.check_id`); if no check attaches, the UI says so and leaves the section readable
   (`plugin.js:11233`).
9. **Variable rewards, loot, spin-to-win, near-miss, surprise multiplier, random XP.** Deterministic
   identity marks are fine; a reward with a random magnitude is refused.
10. **Loss-framed or guilt reminders.** "You'll lose", "before it disappears", "we miss you",
    "your streak dies", "last chance", "don't fall behind". The build has no reminder channel; any
    future reminder must reference the cue and carry an opt-out.
11. **Confetti/shake/damage numbers/coin SFX as the only reward.** Motion is feedback on a real
    event (H-152), never the reward itself, and reduced motion must keep the state change.
12. **An analytics dashboard, a "wellness score", or a composite metric.** The measurement plan in
    §7 is read-only, operator-side, and not a visible surface.

## 7. Measurement plan (small, read-only, no new telemetry)

Every measure is derived from rows the product already writes. "Source" is the command or table
that already exists at `cb.rpc v16` / `cb.db v11`; no field, event or dashboard is added, and none
of these numbers is rendered to a learner.

| # | Measure | Definition | Source (existing contract) | Target / reading |
|---|---|---|---|---|
| M1 | **Durable evidence coverage** | share of claimed progress that is evidenced: `Σ objectives.independent / Σ total_objectives` across active enrollments, split by `independent_evidence` vs `delayed_evidence` | `library.list.evidence_summary` (`independent`, `total_objectives`); `course.outline.objectives[].state`; contract `docs/CONTRACTS.md` §631-634 | rising or flat with evidence rising; **never** rising with no evidence change |
| M2 | **Time to first real success** | median time from `enrollments.created_at` to the first `attempts.committed_at` where `verdict='pass'` and `evidence_class='cold'` | `enrollments.created_at`; `attempts.verdict`, `attempts.evidence_class`, `attempts.committed_at`, `attempts.state='committed'` (`contracts/db.v11.json` §attempts) | falling; a pass with `hinted`/`answer_shown` does not count |
| M3 | **Review adherence** | of objectives that became `review_due` in a window, the share that later returned to `independent_evidence`/`delayed_evidence`; snooze/stretch/drop counted separately | `review.queue` (`total_due`, `total_overdue`, `total_scheduled`); layer-1 events `review_snooze`/`review_stretch`/`review_drop`/`review_resume` (`coursebook/review.py`) | adherence up, `review_drop` treated as a signal not a failure |
| M4 | **Pressure / anxiety guardrail** | a 3-question parent/learner interview ("did you feel behind? did you feel you would lose something? did you stop because of the app?") collected **off-product**, recorded as a manual note per release | none in the product by design — no survey, no prompt, no modal | any "yes" blocks a ship until the cause is named; this guardrail is deliberately not instrumented |
| M5 | **Notification opt-out** | precondition, not a metric today: the build has no notification channel. When a reminder channel is proposed, it must ship with an explicit opt-out and a cue-based (not loss-framed) message, and this row becomes "opt-out honoured: 100 % of reminders stop within one tick of the setting" | `host.notify` (transient, in-app) is the only channel; settings sheet is H-147 | 100 % opt-out, verified by a test that sends with the toggle off and asserts nothing is queued |

Guardrail readings that block a ship (from the research, §4 "Guardrails"): evidence coverage falling
while any engagement number rises; review adherence falling after a UI change; any M4 "yes"; any
reminder without an opt-out.

## 8. Accepted with a note (not violations)

- **`Recogniser confidence NN%`** (`plugin.js:10461`): the only percentage a learner can read. It is
  `assessment.confidence` from the deterministic comparison, and the same block says "not verified
  pronunciation and not a graded score". Keep the disclaimer adjacent; do not let it grow into an
  accuracy score or a ring.
- **`N%` / `N points` on the syllabus review** (`:5411-5412`): the syllabus's own grade weight, with
  `derivation` shown; it is a source fact, not learner progress.
- **`Complete` for both `independent_evidence` and `delayed_evidence`** on the path index
  (`:7014`): a simplification, not an invention — both are complete evidence. The full state word
  still appears on Evidence and lesson surfaces. H-148 may restore "Delayed" as an improvement.
- **Host `sdk.Badge` everywhere**: a text chip carrying a backend enum. It is not an award; the
  refuse list forbids giving it a reward meaning.

## 9. What this audit does not prove (Q5/Q12 boundaries)

- It does not prove the first slice looks or feels right. Q5 (authored visual) and Q12 (human proof)
  belong to the human walkthrough on the slice cards; this audit only proves the slice may not
  acquire theater.
- It does not prove the live accessibility of the redesigned screens (H-151/H-152/H-145 own Q9/Q8
  evidence). The copy scan and the state-vocabulary test are static-plus-executed checks, not axe.
- It does not audit the demo profile's seeded data (H-109 owns demo hygiene) or the demo script's
  freshness claims (CB-017/DEMO gate). It does confirm `docs/DEMO.md` already forbids "guaranteed
  mastery" language.
- It does not certify the `dashboard/` operator surface as learner-safe; that surface is not
  reachable from the learner pane and contains no engagement strings.

## 10. Sign-off

As of `master` `c6b658e`, with the checks in §1 executed on that byte-identical plugin:

> **The first slice has no XP, no streak, no leaderboard, no league, no hearts/energy, no variable
> reward, no loss-framed reminder and no fabricated mastery.** Progression is exactly two concrete
> evidence metrics. The defects in §5 are truthfulness and copy defects on surfaces already owned by
> H-148, H-150, H-157, H-145 and H-153, and each card must clear them before requesting review.
> No shipping card may introduce anything on the §6 refuse list; a diff that does is blocked on
> sight.

Re-run before every release:

```
python3 -m unittest tests.test_engagement_integrity -v
```

Expected: `OK (expected failures=1)` — the single expected failure is ENG-D1, owned by H-148.
