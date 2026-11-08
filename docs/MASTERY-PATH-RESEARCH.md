# Mastery path, checkpoints and the lesson loop: what the evidence supports

Status: research note, 2026-11-07. Design direction, not a measured outcome claim; none of this
has been tested in Coursebook. Effect sizes are population averages from other settings — they
justify a mechanism, not a promise.

Scope: the owner wants a Duolingo-like path with checkpoints and a game-like home, without
padding or invented progress. This answers what a node should teach, what a checkpoint is for,
how the check/feedback loop runs, and which game mechanics are defensible. It sits under
`docs/UX-RESEARCH-STANDARDS.md` (no invented mastery, XP, streaks or percentages) and extends
`docs/FIELD-DESK-RESEARCH.md`, `docs/DUOLINGO-RESEARCH.md` (the product survey) and
`docs/CURRICULUM-SEQUENCING-RESEARCH.md`.

## 1. What the evidence supports

| Finding | Effect | Source |
|---|---|---|
| Practice testing vs restudying | g = 0.51 (272 effects); g = 0.50 across 222 classroom studies, 48,478 students | [1][2] |
| Same, stricter primary/secondary classroom meta | g = 0.37 | [3] |
| Transfer from testing | d = 0.40; near zero without response congruency or elaborated retrieval | [4] |
| Spacing | positive; optimal gap scales with the retention horizon; g = 0.20 in classrooms | [3][5][6] |
| Interleaving | g = 0.42 overall; math 0.34, paintings 0.67, **words −0.39** | [7] |
| Feedback | d = 0.48 (435 studies); older meta d ≈ 0.38 with about a third of effects negative | [8][9] |
| Mastery learning | 0.52 average (108 evaluations); 0.61 for weaker students, 0.40 for stronger | [10] |
| Self-explanation prompts | g = 0.55 (64 studies) | [11] |
| Metacognitive strategy instruction | g = 0.50 posttest, 0.63 follow-up | [12] |
| Gamification | cognitive 0.49, motivational 0.36, behavioural 0.25 | [13] |
| Tangible rewards for interesting tasks | undermine intrinsic motivation | [14] |

Two framing results do more work than any row. **Performance during practice is a poor proxy for
learning**: what speeds acquisition often reduces retention, and what feels harder often improves
it [15]. And **not every difficulty is desirable** — only when the learner has the prior
knowledge to meet it and gets feedback [16]. That forbids both "fluent means learned" and "hard
for its own sake."

## 2. What a path node should teach

A node is **one capability, stated as an exit performance** — "can order food and ask the price
without English," "can size a breaker for a 20 A circuit" — not a topic heading.

- **The node is the smallest performance that can be checked cold.** Five to fifteen minutes
  without scaffolds; if it does not fit, it is a section.
- **Every node carries five fields**: exit performance; prerequisite edge(s); check family
  (`recall`, `comprehension`, `production`, `discrimination`, `procedure`, `transfer`); the
  misconceptions it must catch; the review obligation it creates. Coursebook stores evidence
  targets per objective already; show the capability, keep the target as the scheduling key.
- **The path is a prerequisite graph rendered as a line, not a difficulty ladder.** Order by
  "what must the learner already be able to do", with a why-now reason per node. Independent
  nodes may branch; a line that hides a real branch misstates the structure.

A node whose check does not resemble its exit performance measures the lesson's prose, not the
capability: the 2026 meta found the testing effect was moderated by format matching between
practice and test, and transfer is weakest to rearranged items and worked examples [3][4].

## 3. What a checkpoint is

A checkpoint is **a scheduled cold retrieval event over prior nodes, taken without scaffolds,
that writes evidence and can reorder the path**. It is not a boss fight, not a content gate, and
not a second final exam. Because retrieval is itself a learning event, a checkpoint is
instruction, not only measurement [1][2].

| Type | Question | When | State written |
|---|---|---|---|
| **Gate check** | Can they do this now, unaided? | End of node, new items | `introduced` → `independent_evidence` |
| **Delayed check** | Does it survive? | 2–7+ days, cold | `delayed_evidence` |
| **Cumulative check** | Can they pick the right move among confusable ones? | Every N nodes, mixed | `transfer` / discrimination evidence |

The delayed check is the one that matters. Same-session success is a weak signal because fluency
during practice predicts retention poorly [15]. A path that celebrates the gate check and never
returns is measuring the wrong moment.

**Pass rule.** Correct on a cold attempt, after the delay, without hints, on an item not seen in
that exact form. Do **not** invent a universal "three in a row" criterion. Kulik's strongest
mastery programmes used high unit-quiz criteria (some 100%) *plus* corrective feedback and more
time; their effects were largest on locally written tests and shrank when feedback was equated
between groups [10]. That supports *mastery plus correction*, not a magic streak length. Define
the criterion per evidence target, store it, and show it as a rule ("two cold passes, one after a
week"), not as science.

**Failure rule.** One miss sets `needs_review` on that node, not a course reset. Two misses
across two *different* check forms trigger re-teaching with a different representation — not the
same explanation louder. A single wrong answer is a provisional misconception, never a diagnosis.

**Do not lock the whole path.** Kulik's self-paced mastery programmes often *reduced completion
rates* [10]. Offer "continue with this unresolved": the flag stays on the path and the review
queue picks it up. Gate only where the next node genuinely depends on this one.

## 4. How checks and feedback should work

The loop: **prompt → attempt → verdict → explanation → a different re-attempt → schedule.**

- **Cold first.** No hint, no answer-shaped context. Failed retrieval still improves later
  learning when feedback follows [17], and corrected errors can beat error-free study [18]. An
  error without correction is practice at being wrong.
- **Closed-form first, deterministic where possible.** Open responses need a typed rubric,
  reference answer, accepted alternatives and adversarial cases. Grader failure is `needs_retry`,
  never mastery.
- **Name the misconception.** Say which rule was misapplied, not "incorrect." Impact is driven by
  feedback's *information content*, and self/praise feedback is the weakest level [8]; Kluger &
  DeNisi's negative third is the same warning [9].
- **Immediate correction for procedures, delayed summary for retention.** Correct at once when a
  procedural error would otherwise be rehearsed (pronunciation, safety, a procedure step); delay
  to end-of-set when the goal is durable retrieval [3]. Never render the answer beside the
  question.
- **Never ask "how well do you know this?" as the primary signal.** Judgements of learning are
  poorly calibrated: participants rated massing as more effective even after their own test
  showed spacing had won [19]. Measure, then tell them.
- **Show a state word, not a score.** `with evidence`, `due now`, `needs review`; a percentage is
  not.

## 5. What should be spaced and interleaved

**Spacing.** The optimal gap is not a constant: roughly 0.24–0.43 of the retention interval at
one week, falling to 0.07–0.08 at one year [6][3]. The learner's answer to "how long do you need
this?" should parameterise the ladder. Coursebook's ladders — recall `(1,3,7,16,35)`,
comprehension `(2,5,12,28)`, transfer `(7,21,45)` — are a reasonable expanding default, labelled
a heuristic, not a forgetting curve (`review.py`). Add two rules: a failed review must not reset
to day 1, and a pass must not jump to the end of the ladder.

**Successive relearning.** Durable retention comes from retrieving to a criterion in *each* of
several spaced sessions, not rereading between them; classroom experiments show benefits on tests
42 and 68 days later [20]. A review is a cold recall event that must be passed, not a page that
must be opened.

**Interleaving — conditionally.** Interleave confusable categories, procedures and mixed problem
types; **block first acquisition**, then interleave. The benefit is strongest where categories
are similar between and dissimilar within, and reversed for words [7]. So: block a new
procedure's first worked examples, then interleave once each can be executed alone; interleave
vocabulary only after items are individually retrievable, by *confusable set* (particles that
occupy the same slot), never at random; mix cumulative checkpoints by confusability, not topic
adjacency.

## 6. Which game mechanics are defensible

The test: **a game element may visualise a real evidence fact, or lower the cost of the next
repetition. If it creates a number the backend does not record, it is fake.**

Defensible:

- **Path position and one next move.** Removes the "which lesson is correct?" cost. Navigation,
  not learning; label it as such.
- **Competence feedback tied to evidence.** "You did this without help," a count of objectives
  with delayed evidence, a streak of *evidence days* — not of app opens.
- **Choice and autonomy.** Which review set, how long the session. The Li et al. gamification
  meta found gains in intrinsic motivation, autonomy and relatedness but **minimal impact on
  competence** [21] — autonomy is the lever, not more points.
- **Implementation intentions.** "Tuesday 19:00, 25 minutes, this node" — d = 0.65 originally,
  about 0.27 after publication-bias correction [22]. Use the conservative number.
- **Competition combined with collaboration.** This moderated behavioural outcomes [13]; a shared
  weekly goal is defensible, a league table is not.

Not defensible:

- XP, coins or levels for attendance, clicks or time: a second progress currency competing with
  the evidence states.
- Default leaderboards or leagues: competition without collaboration, no learning effect.
- Loss-framed streaks. Habit formation took 18–254 days to reach 95% of asymptote in Lally's
  field study, and missing one opportunity did not materially affect it [23]. A broken streak is
  not a learning fact.
- Badges for completion, mastery percentages, "learning style" personalisation [24], and Bloom's
  "2 sigma" [25].

## 7. Caveats to state out loud

- **Heterogeneity is the headline.** Feedback "cannot be understood as a single consistent form
  of treatment" [8]; the same holds for interleaving and spacing.
- **Effects shrink as settings get real.** Testing: 0.51 → 0.50 → 0.37 across meta-analyses;
  spacing: large in lab, 0.20 in classrooms [1][2][3][5].
- **Publication bias is material.** Pan & Rickard's bias-corrected intercepts often indicated no
  positive transfer when moderators were absent [4]; Gollwitzer's 0.65 fell to ~0.27 [22].
- **Mastery learning's 0.52 is inflated by weak comparisons** — local tests, teacher-paced
  delivery, unequal feedback [10].
- **Gamification effects may be novelty effects**; most studies are short [13].
- **The honest product claim** is "this loop uses retrieval, spacing and corrective feedback,"
  not "this raises outcomes by g = 0.4."

## Sources

1. Adesope, Trevisan & Sundararajan (2017), *Review of Educational Research* —
   https://journals.sagepub.com/doi/10.3102/0034654316689306
2. Yang, Luo, Vadillo, Yu & Shanks (2021), *Psychological Bulletin* 147(4) —
   https://psycnet.apa.org/record/2021-24563-001
3. Retrieval/distributed/interleaved practice in authentic classrooms (2026), *Educational
   Psychology Review* 38:137 — https://link.springer.com/article/10.1007/s10648-026-10225-5
4. Pan & Rickard (2018), *Psychological Bulletin* 144(7) —
   https://pubmed.ncbi.nlm.nih.gov/29733621/
5. Cepeda, Pashler, Vul, Wixted & Rohrer (2006), *Psychological Bulletin* 132(3) —
   https://psycnet.apa.org/fulltext/2006-06233-002.html
6. Cepeda, Vul, Rohrer, Wixted & Pashler (2008), "A Temporal Ridgeline of Optimal Retention" —
   https://psycnet.apa.org/record/2008-18156-008
7. Brunmair & Richter (2019), *Psychological Bulletin* 145(11) —
   https://www.psychologie.uni-wuerzburg.de/fileadmin/06020400/2019/Brunmair_Richter_in_press__2019_META-ANALYSIS_OF_INTERLEAVED_LEARNING.pdf
8. Wisniewski, Zierer & Hattie (2020), *Frontiers in Psychology* 10:3087 —
   https://pmc.ncbi.nlm.nih.gov/articles/PMC6987456/
9. Kluger & DeNisi (1996), *Psychological Bulletin* 119(2) —
   https://doi.apa.org/doi/10.1037/0033-2909.119.2.254
10. Kulik, Kulik & Bangert-Drowns (1990), *Review of Educational Research* 60(2) —
    https://www.uky.edu/~gmswan3/575/kulik_kulik_Bangert-Drowns_1990.pdf
11. Bisra, Liu, Nesbit, Salimi & Winne (2018), *Educational Psychology Review* —
    https://link.springer.com/article/10.1007/s10648-018-9434-x
12. de Boer, Donker, Kostons & van der Werf (2018), *Educational Research Review* 24 —
    https://pure.rug.nl/ws/portalfiles/portal/56352857/Long_term_effects_of_metacognitive_strategy_instruction_on_student_academic_performance.pdf
13. Sailer & Homner (2020), *Educational Psychology Review* 32(1) —
    https://link.springer.com/article/10.1007/s10648-019-09498-w
14. Deci, Koestner & Ryan (1999), *Psychological Bulletin* 125(6) —
    https://psycnet.apa.org/record/1999-01567-001
15. Soderstrom & Bjork (2015), *Perspectives on Psychological Science* 10(2) —
    https://journals.sagepub.com/doi/10.1177/1745691615569000
16. Bjork & Bjork (2011), "Creating Desirable Difficulties to Enhance Learning" —
    https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2016/04/EBjork_RBjork_2011.pdf
17. Richland, Kornell & Kao (2009), *JEP: Applied* 15(3) — https://eric.ed.gov/?id=EJ859957
18. Metcalfe (2017), "Learning from Errors," *Annual Review of Psychology* 68 —
    https://www.annualreviews.org/content/journals/10.1146/annurev-psych-010416-044022
19. Kornell & Bjork (2008), "Learning Concepts and Categories" —
    https://web.williams.edu/Psychology/Faculty/Kornell/Publications/Kornell.Bjork.2008a.pdf
20. Dunlosky, Greve, Badali, Wissman & Rawson, "The Promise of Successive Relearning" —
    https://www.unh.edu/teaching-learning-resource-hub/sites/default/files/media/2023-06/itow-successive-relearning-dunlosky-greve-badali-wissman-rawson.pdf
21. Li, Hew & Du (2024), *ETR&D* — https://link.springer.com/article/10.1007/s11423-023-10337-7
22. Gollwitzer & Sheeran (2006), *Advances in Experimental Social Psychology*; 2025
    bias-corrected re-analysis — see `references/learning-science-evidence.md`
23. Lally et al. (2010), *European Journal of Social Psychology* 40(6) —
    https://onlinelibrary.wiley.com/doi/abs/10.1002/ejsp.674
24. Pashler, McDaniel, Rohrer & Bjork (2008), *Psych. Science in the Public Interest* 9(3)
25. VanLehn (2011), *Educational Psychologist* 46(4) — the 2-sigma claim did not replicate
