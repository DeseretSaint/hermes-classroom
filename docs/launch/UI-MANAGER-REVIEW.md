# Adversarial review — Opus UI manager prompt

Verdict: the prompt is well-intentioned and wrong in three structural ways. It withholds the
context the manager needs, it decomposes a tightly coupled visual task into parallel writers, and it
reduces acceptance to one gameable number. The published evidence says that combination fails most
of the time.

## What the evidence actually says

1. **Multi-agent decomposition is for breadth, not for tightly coupled work.** Anthropic's own
   postmortem on Claude Research reports a 90.2% gain over a single agent on breadth-first research,
   and then says plainly: domains "that require all agents to share the same context or involve many
   dependencies between agents are not a good fit for multi-agent systems today. For instance, most
   coding tasks involve fewer truly parallelizable tasks than research."
   (https://www.anthropic.com/research/multi-agent-research-system)

2. **Vague delegation is the named failure.** The same post: each subagent needs "an objective, an
   output format, guidance on the tools and sources to use, and clear task boundaries. Without
   detailed task descriptions, agents duplicate work, leave gaps, or fail to find necessary
   information." It also recommends artifact handoffs to avoid the "game of telephone."

3. **Parallel writers conflict on implicit decisions.** Cognition's context-engineering post shows
   two subagents building a Flappy Bird clone that disagree on style and movement, and concludes:
   share full context, and keep writes single-threaded. Their follow-up narrows the working pattern
   to "multiple agents contribute intelligence while writes stay single-threaded."
   (https://cognition.com/blog/dont-build-multi-agents, https://cognition.com/blog/multi-agents-working)

4. **Invert the manager.** Anthropic's advisor strategy has the cheap model drive end-to-end and
   consult the strong model at decision points. Measured: Sonnet + Opus advisor +2.7 points on
   SWE-bench Multilingual with 11.9% lower cost per task; Haiku + Opus advisor scored 41.2% on
   BrowseComp versus 19.7% solo at 85% less cost than Sonnet.
   (https://claude.com/resources/articles/the-advisor-strategy)

5. **Multi-agent systems fail about two-thirds of the time, mostly on specification and
   verification.** MAST annotates 1,600+ traces across seven frameworks into 14 failure modes;
   ~66% of runs fail. (https://arxiv.org/abs/2503.13657, https://sky.cs.berkeley.edu/project/mast/)

6. **One visual number is not fidelity.** Design2Code benchmarks 484 real pages with automatic
   metrics and human evaluation; the automatic scores rank systems, but models still lag on recall of
   elements — whole regions go missing while the pixel score stays respectable.
   (https://arxiv.org/abs/2403.03163)

## Findings against the current prompt

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| 1 | Fatal | "Do not open `desktop/src/*.js`" leaves the manager unable to write precise cards or judge a gate failure. It will delegate by adjective. | Anthropic §2 | Give a generated context pack (≈200 lines: token rules, scene contract, current DOM snapshot) and allow three named files. |
| 2 | Fatal | The manager runs no tools at all. It never sees the live DOM or the capture, so it reviews worker self-reports. | Advisor strategy; MAST verification failures | Allow read-only inspection: screenshot, `report.json`, DOM excerpt. Never writes. |
| 3 | High | Four cards in parallel on one screen. UI is a shared visual language; parallel writers make conflicting implicit decisions. | Cognition; Anthropic §1 | One writer at a time on the scene file; cards are phases of one lane, not a wave. |
| 4 | High | "Similarity ≥ 0.90" is the acceptance. The metric is grey RMSE; it rewards copying large blocks and hides missing elements. | Design2Code | Five-dimension rubric (composition, material, type, illustration, states) + element checklist; similarity is a ≥0.85 guardrail. |
| 5 | High | No context-handoff contract. Each card body is prose, so workers re-discover and diverge. | Anthropic §2 | Mandatory context pack per card: exact files, prior attempt, screenshots, acceptance, boundaries. |
| 6 | Medium | No anti-duplication rule. | Anthropic §2 (duplicate searches) | One card per file; board check before create; parent links for dependencies. |
| 7 | Medium | Fable is pinned on implementation cards. The frontier model should be consulted on the decision, not writing CSS. | Advisor evidence | Fable/Opus as advisor at gates; DeepSeek writes. |
| 8 | Medium | No cost telemetry or gain-based stop. | Anthropic (15× tokens) | Cap advisor calls per screen; stop when a pass gains <0.02 similarity or <0.5 rubric point. |
| 9 | Medium | "No copy changes" can stall a worker matching a reference label. | — | Placeholder allowlist: the six visible strings may be placeholders; anything else is recorded for the owner. |
| 10 | Medium | Acceptance at 1344×768 ignores the 560 px tab the owner actually sees. | Measured today | Dual acceptance: pane composition and full-window parity, or an explicit shipping surface. |
| 11 | Low | Verifier is a cheap model with no rubric. | MAST | Give the verifier the same context pack and rubric; disputes escalate to the advisor. |
| 12 | Low | "Three passes" without a per-pass delta requirement invites grinding. | — | Every pass must name its top three deltas and the expected gain before running. |

## The corrected operating model

Not a manager dispatching four writers. One lane, one writer, the strong model as an advisor at four
gates:

1. **Composition spec** — the advisor writes the scene spec (grid, layers, card geometry, type
   scale, materials, states) from the reference. No code.
2. **First capture critique** — the writer implements; the advisor reviews the frame and returns a
   delta list.
3. **Material and type review** — a second capture after fixes; the advisor checks the tokens,
   textures and typography against the reference.
4. **Parity verdict** — rubric scores, element checklist, gates, and a go/no-go to the owner.

Between gates the advisor is silent and the writer runs on DeepSeek. That is the advisor pattern
with the cost curve measured by Anthropic, and it keeps the writes single-threaded as Cognition
requires.

## Revised prompt

The paste-ready rewrite is `docs/launch/OPUS-UI-MANAGER-PROMPT-V2.md`.
