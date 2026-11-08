# Duolingo as a learning app: clarity, engagement, and what Coursebook should take

Status: public product research, 2026-11-07. Vendor claims are labelled; independent evidence is
labelled. Not a controlled study; no claim of measured outcomes. Supports
`docs/UX-RESEARCH-STANDARDS.md` and `docs/FIELD-DESK-RESEARCH.md` without overriding them.

## Verdict

Duolingo is self-explanatory because it **removes decisions**, not because it explains itself: one
route, one lit node, one button per lesson, onboarding that ends in real work. Its engagement is a
separate stack — streak, XP, leagues, energy — tuned for retention and revenue. Coursebook should
take the first and reject the second.

## 1. What the app is

Course → sections → units → short lessons, grouped around communication goals [1][3]. A lesson is a
bounded set — 12–15 exercises in Duolingo's 2021 structure [10]. Duolingo's own assessment paper
describes units ending in a checkpoint used as learner review and internal measurement [10]. Home is
one vertical route with a labelled current circle [1]. Two progress languages sit on top: path
position and the 0–160 Score [4].

## 2. Clarity mechanics

**One route, one lit node.** Duolingo's stated reason for the 2022 redesign: learners were "not sure
whether they're using Duolingo the 'correct' or 'best' way"; the path makes each step "truly the best
step" [1]. The product answers "what now?" before the learner asks.

**Written state.** The current node is singled out; completed and locked nodes look different [1][3].
Duolingo's few states let shape and colour carry it; Coursebook has six evidence states and cannot
copy that compression without lying. Rule: every marker carries its state word;
the current marker carries `Next`; the legend is the explanation.

**Onboarding ends in work.** A teardown of the December 2024 flow records: language
first (the one question you cannot get wrong), a mascot-voiced exchange, self-assessed level,
motivation, a daily goal framed as a routine (`Casual` … `Intense`), the self-assessment reflected
back as a placement, then a real lesson — before account creation [9]. The teardown estimates real
Spanish inside ninety seconds [9]. Activation onboarding, not a tour.

**Invariant lesson shell.** Stimulus, response, and a check button at the bottom. Duolingo's own
method page captions its screenshots "Check buttons are at the bottom of all screens" [2]. The label
changes; the position does not. Learn the shell once; spend attention on the language.

**Feedback closes the loop.** Correct: confirmation plus the answer in context — "Correct! Meaning:
I live in Mexico" [9]. Wrong: the correct answer is shown; the first wrong attempt is soft, with no
penalty; missed items replay at the end [9]. That is retrieval practice with immediate corrective
feedback [17].

**Bounded units and a real checkpoint.** The path is chunked with a visible end; the checkpoint is a
genuine stop-and-check, not a badge [1][10].

**A number with a meaning.** The Score is bounded, CEFR-mapped, and translated into capabilities —
"order food", "tell stories" [4]. Validity is separate; the pattern — abstract mark plus a plain-language
table — is its best answer to "what does this mean?"

## 3. Engagement mechanics

**Streak.** Duolingo describes it as loss aversion: the longer it grows, the more the learner
practices to protect it [7]. Vendor data: learners who reach a 7-day streak are 3.6 times more likely
to complete the course, and separating the streak from the daily goal raised Day-14 retention by
3.3% [6][7]. Correlational, vendor-reported: retention, not learning.

**XP and leagues.** XP for lessons, stories, practice and challenges; weekly leaderboards
promote the top earners and demote the bottom across ten leagues, Bronze to Diamond [3][8].
Independent interviews and nine years of forum data document learners fixating on rewards and
drifting from the learning [14].

**Delight.** Characters, silly sentences, sound and animation are stated design principles;
Duolingo says funny content is more memorable [2].

**What the stack optimizes.** Duolingo's own half-life regression paper reports the model improved
daily student engagement by 12% in an operational study [11]. Engagement is the target variable. The
efficacy literature is thinner than the marketing: a key peer-reviewed study is Duolingo-authored
and assessed only reading and listening [12], and an independent systematic review found the
2012–2020 literature mostly design-focused, quantitative, and non-probability sampled [13].

## 4. What does not transfer

| Mechanic | Why it works there | Why not here |
|---|---|---|
| Streak | Daily habit, notifications, loss aversion [7] | No daily contract or push channel; review dues are per objective. |
| XP, levels, crowns, Legendary | Scalar reward on a fixed curriculum with known difficulty [1][3] | The contract is evidence states; a level is an invented mastery claim. |
| Leagues, leaderboards | A large cohort and public profiles make ranking meaningful [8] | A classroom is a handful of learners; ranking children is a safeguarding risk. |
| Hearts, Energy, gems, shop | Freemium conversion surface [5] | No paywall or right to restrict access. Duolingo says Energy helps completion [5]; Class Central documents users calling it punishment, and its author reports doing fewer lessons per session [15]. |
| Adaptive difficulty ("Birdbrain") | A calibrated item bank and millions of responses [18] | Coursebook generates courses and has no item calibration; claiming adaptivity would be fake personalization. |
| Mascot and characters | A decade-long brand asset pipeline [2] | Ink & Field Notes is a surveyed document, not a cartoon. |
| Fully linear lock | Removes choice for a mass-market self-learner [1] | A parent must be able to open any section; recommend, don't imprison. |

## 5. What Coursebook should borrow

### 5.1 Home and path

- **Top bar:** active classroom and learner, course title, one `Switch` control.
- **Continue plate:** seal, course title, section title, three recorded facts (`Section 2 of 4`,
  `3 of 7 checks with evidence`, `20 min recorded estimate`); one primary (`Start Section 2`/
  `Resume`), one secondary (`Open course`), one tertiary (`Why this is next`).
- **Route:** vertical sections; current expands to checks, others one row. Each row: state word
  (`Not started`, `Reading`, `With evidence`, `Review due`) plus marker; current gets `Next` and
  `aria-current="step"`. Future sections are tappable, not locked.
- **Rail:** Field Notes (max 3), then at most two courses with their own next step. The rail
  never outranks the route.

Duolingo has three node states; Coursebook has six. Do not reduce them: write them, and show detail
only for the current section.

### 5.2 First run

Three screens, then a real course: (1) `What do you want to learn?`; (2) `Have you studied this
before?` — `New to it`, `Some of it`, `Confident` — changing the starting section; (3) `How long is a
good session?` — 15 / 25 / 40 minutes — changing the section size. Then generate. No tour, no sample
course. The first real check is the onboarding; returning learners see the Continue plate.

### 5.3 Lesson loop

Header (`Section`, mode, `Check 3 of 7`, exit), one stimulus, one response, one footer. Footer: one
primary `Check`, becoming `Continue`; Enter does the same; `Skip for now` is tertiary. Feedback:
`Correct` plus the answer in context plus one line of why; `Not quite` plus the correct answer plus
one line of why plus `Continue`. Never colour alone. End: `You finished Section 2`, `5 of 7 checks
with evidence`, `2 checks to review`, one next action. No XP, no random reward, no confetti.

### 5.4 Checkpoint

Assemble a `Checkpoint` from the section's own checks. It writes evidence and does not lock the next
section. Copy: `Show what you know`, `Checkpoint · 6 checks`, not `Exam`. A miss routes to specific
`Review due` objectives — Duolingo's review-and-measurement job [10], without the gate.

### 5.5 Progress and the seal

Counts and states, never a percentage: `3 of 7 checks with evidence`, not `43%`. The strip is
painted from real states; a one-line collapsible legend is the explanation, not a modal.

The seal is deterministic and `aria-hidden` [19], which is why it reads as a badge. Give it a job:
course cover, completion plate, Library row, always beside the title. If a sentence is needed, put
it in the course About/Details — "The mark is generated from the course title; it is not a grade."
No tooltip on a decorative mark. Duolingo's Score works because it is bounded and translated into
capabilities [4]; the seal must mean something or stop looking meaningful.

### 5.6 Fun

Duolingo's fun is characters, sound, silly sentences, animation [2]. Coursebook's is a well-written
scenario, a real field note, an earned ending. One motion effect, at most one sound cue;
no emoji, no cartoon. Fun from the loop and the voice.

## 6. Reject

No streak or daily goal; no XP, levels, crowns or leagues; no hearts, energy, gems or shop; no
mastery percentage; no adaptive-difficulty claim without an item bank; no guilt or shaming copy [16];
no lock on future sections; no mascot.

## 7. Verify

1. **Five seconds:** a cold user can name the next action; at ten, say which course and section
they're in.
2. **First run:** first real check under 90 seconds; zero modals.
3. **Path:** five users; "what happens if you tap Section 3?" must answer "it opens".
4. **Honesty grep:** no `%`, `streak`, `XP`, `level`, `mastered`, or `league`; every number traces
to a backend field.

## Sources

Accessed 2026-11-07.

1. Duolingo, "Introducing the new Duolingo learning path," 2022.
   https://blog.duolingo.com/new-duolingo-home-screen-design/ — vendor.
2. Duolingo, "The Duolingo Method," 2023. https://blog.duolingo.com/duolingo-teaching-method/ —
   vendor.
3. Duolingo, "Duolingo 101."
   https://blog.duolingo.com/duolingo-101-how-to-learn-a-language-on-duolingo/ — vendor.
4. Duolingo, "How the Duolingo Score tracks your learning progress."
   https://blog.duolingo.com/duolingo-score/ — vendor.
5. Duolingo, "Why Duolingo switched to Energy," 2025.
   https://blog.duolingo.com/duolingo-energy/ — vendor.
6. Duolingo, "Improving the streak." https://blog.duolingo.com/improving-the-streak/ — vendor.
7. Duolingo, "The habit-building research behind your Duolingo streak."
   https://blog.duolingo.com/how-duolingo-streak-builds-habit/ — vendor.
8. Duolingo Help Center, "What are leaderboards and leagues?"
   https://www.duolingo.com/help/leaderboards-and-league — vendor.
9. Botsi, "Duolingo onboarding flow: full teardown (Dec 2024)."
   https://www.botsi.com/resources/flows/apps/duolingo-2024-12 — independent teardown.
10. Portnoff et al., "Methods for Language Learning Assessment at Scale: Duolingo Case Study," EDM
    2021. https://research.duolingo.com/papers/portnoff.edm21.pdf — Duolingo researchers.
11. Settles and Meeder, "A Trainable Spaced Repetition Model for Language Learning," ACL 2016.
    https://research.duolingo.com/papers/settles.acl16.pdf — Duolingo researchers.
12. Jiang et al., "Evaluating the reading and listening outcomes of beginning-level Duolingo
    courses," Foreign Language Annals, 2021. https://onlinelibrary.wiley.com/doi/full/10.1111/flan.12600
    — peer-reviewed, Duolingo-authored; reading/listening only.
13. Shortt et al., "Gamification in mobile-assisted language learning: a systematic review of
    Duolingo literature," Computer Assisted Language Learning 36(3), 2023.
    https://eric.ed.gov/?id=EJ1386218 — independent.
14. Mogavi et al., "When Gamification Spoils Your Learning," L@S 2022.
    https://ar5iv.labs.arxiv.org/html/2203.16175 — independent.
15. Class Central, "Duolingo Breaks Hearts for Energy, Drains Free Learning," 2025.
    https://www.classcentral.com/report/duolingo-breaks-hearts-for-energy/ — independent.
16. Growth.Design, "Duolingo's User Retention: 8 Tactics Tested On 300 Million Users."
    https://growth.design/case-studies/duolingo-user-retention — independent; shaming microcopy.
17. Roediger and Karpicke, "Test-Enhanced Learning," Psychological Science 17(3), 2006.
    https://journals.sagepub.com/doi/10.1111/j.1467-9280.2006.01693.x — peer-reviewed.
18. Duolingo, "Introducing Birdbrain."
    https://blog.duolingo.com/learning-how-to-help-you-learn-introducing-birdbrain/ — vendor.
19. Coursebook internal: `docs/UX-RESEARCH-STANDARDS.md`, `docs/FIELD-DESK-RESEARCH.md`,
    `docs/COURSEBOOK-VISUAL-IDENTITY-V2.md`, `desktop/plugin.js` (`SurveyMark`, `aria-hidden`).
