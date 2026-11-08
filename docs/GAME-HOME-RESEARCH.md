# The hub is not a menu: game-home patterns for an adult learning product

**Baseline.** The vault's research indexes set the constraints: `game=learning` — "the game lives INSIDE the learning task"; 3–8 minute session arcs; progression-as-story ("lantern milestones"); no-penalty retry; feel built from response and polish, not reward volume (`JP-Lingo/game-designer-research.md`, `storyteller-research.md`, `humanifier-research.md`; `JP-Game-OSS-Quality-Stack.md`). Q240 adds SDT (competence, autonomy, relatedness), the PBL fallacy, and "concrete metrics > abstract points" (`UI-UX One-Shot Playbook.md` §Q240).

## 1. What a game hub does

A game home has two jobs, not "reward the player."

**Orientation.** Answer five questions before the click: where am I, what's next, how long, what will it produce, who else is here. Main-menu practice converges here: Continue belongs first once a save exists, and it should say what is being continued — "Continue: Chapter 3" answers the question the player was about to ask [1]. The menu's purpose is throughput, not showcase; every added element is "a tax on the players who are most engaged" [2].

**Momentum.** Games create progress by making the next commitment's shape visible and letting past effort leave a mark. Hades' House: a lost run still banks meta-currency and advances dialogue — "the run ended" and "something persisted" are almost always true in the same death [3]. Celeste stores the last area so chapter select opens exactly there [4]. Slay the Spire shows the act's map from the start, node types legible, so the run's shape is planned before the first fight [5]. None is a points system; all are orientation mechanics that double as motivation.

So a hub motivates by clarifying the next bounded effort and showing what the last one changed, not by adding a reward layer.

## 2. Patterns that transfer

| Pattern | What the games do | Adult-learning translation | Refuse |
|---|---|---|---|
| **One resumed position** | Continue-first; "Continue: Chapter 3" [1]; Celeste's `LastArea` reopens chapter select there [4] | "Resume · Section 4 · ~6 min", section named | "New Game" above resume; a fake "last played" |
| **A small, legible slot** | Hollow Knight's four profiles; a failed Steel Soul run reads `DEFEATED` where the location would be [6]; Hades' four slots [7] | Learner + classroom + teacher as one identity line; chooser only when >1 | A character-select carousel for one adult |
| **A visible route with typed stops** | Spire's DAG: monster/elite/shop/rest/treasure/unknown/boss, partially visible [5]; Celeste: single-screen challenges, checkpoints, optional branches [8] | A course spine with node types (read, practice, checkpoint, review), whole shape visible | Fog-of-war that hides what is assessed |
| **A rest stop that is a real choice** | Spire's campfire: heal or upgrade [5] | A consolidation node: review due items or continue | A grind gate disguised as rest |
| **A hub as a place** | Hades' House: spend, talk, then take the door [3]; hub worlds set mood and clue the levels outside [9] | A threshold with one door, a margin with people and changes | A 3D room, NPC dialogue trees, a mascot |
| **Juice as response** | "Maximum output for minimum input"; sound is the most cost-effective layer; shake with care [10] | 80–150 ms response, focus ring, a route line that draws, soft confirmation when evidence lands | Confetti, screen shake, particles, cartoon sounds |

Two refinements. First, profile slots are an identity contract, not a save file: a game slot answers "whose run is this, where were they, is anything wrong" [6]. A "classroom" is a scope, not a slot; forcing a pick at every launch is an arcade-cabinet tax. Show the current scope; expand only on ambiguity.

Second, the path must be honest about what is known. Spire shows node type, not outcome [5]; Hollow Knight's map is discovered and updates only at rest points [11]. So don't hide the path — show its shape and each stop's type, and withhold only what would spoil the work.

## 3. What does not transfer

**Childish.** Mascots, coins, confetti, "Yay!", character levels, loot, badges, forced daily streaks. Not a taste objection. Age-aware gamification research finds children benefit from storytelling and multisensory feedback, adolescents from competition and peer recognition, and **adults from structure and application relevance** [12]. A child's game optimises for the wrong profile and signals that adults aren't taken seriously.

**Misleading.** The stronger risk is false progress.

- **Invented XP/levels/mastery.** Bogost's charge is that gamification is "exploitationware" — a reward layer substituting for the thing itself [13]. Van Roy and Zaman show that adding game elements as "external, meaningless regulations" is likely to reduce learners' intrinsic motivation [14].
- **The PBL (points/badges/leaderboards) fallacy.** Generic points/badges/leaderboards backfire: LinkedIn retired Top Voice badges when volume beat quality; Disneyland's leaderboard was an "electronic whip"; Habitica collapses under cognitive load (Q240).
- **Streaks as obligation.** Streaks convert motivation into obligation via loss aversion; effects are often misreported, and the experience is "I have to / I can't let it die" (Q240). They can be "highly manipulative," and guilt-marketing — a dying mascot — is the tell [15].
- **Fake structure.** A checkpoint with no evidence, a boss that is a longer quiz, a level that is one lesson, a bar that counts clicks: worse than no game layer, because they teach the learner that the signals are decorative.

Coursebook already has a real progress truth — evidence per section, review due. Any parallel number contradicts it. **One progress truth, and it is evidence.**

## 4. Translating the baseline

**game=learning.** The game lives inside the task, so the home must not become a meta-game. It frames the loop: one objective, a constrained task, immediate feedback, a visible result, a reason to go again. No coins for logging in, no garden, no pet. The fun is the lesson's loop; the home is its threshold.

**3–8 minute arcs.** A run-sized promise, not a course-sized one. Hades' runs are 20–40 minutes [3]; Celeste breaks the climb into single-screen rooms with checkpoints between them [8]. Coursebook should present the next 3–8 minute arc and name its end: "Resume · 6 min · ends at Checkpoint 2" — the equivalent of seeing the boss at the top of the act [5]. Without a named end, "continue" is an open-ended debt.

**Progression-as-story.** Map unlocks to structural milestones, not XP. A section opens the next because of evidence, and the home states the capability concretely: "After this: order food without English." That is the lantern — a place reached, not a number earned. The route is the story; the checkpoint is the chapter break.

**Mistake tolerance.** In Hades, death banks currency and dialogue [3], and God Mode toggles at any time — "if you find you're struggling... or any reason" [16]. Celeste keeps Assist Mode on file select [17]. Coursebook should never show `DEFEATED`, `failed`, or a lost streak: a wrong answer is a review item, not a damaged save. If state fails to read, say so and offer recovery — FieldDesk already does.

**Game feel.** Swink: "realtime control of virtual objects in a simulated space, with interactions emphasised by polish" [18]; Juice It or Lose It: "maximum output for minimum input," sound the cheapest effective layer [10]. A text-first product can't copy physics, but can copy response: immediate press feedback, obvious focus, a route line that draws in 120–200 ms, a page that settles, one optional sound. The register is "well-made instrument," not arcade.

## 5. The Coursebook home: "The Threshold"

The fix is hierarchy, not decoration: recompose the existing Field Desk into three bands, the route line running from button into path. No new backend.

**Band 1 — Threshold (top).** Current course and section, one capability line ("After this you can…"), one primary `Resume`/`Begin`, honest minutes from `useSessionEstimate`, and the run's end: "ends at Checkpoint 2" or "ends with this section." This is Hades' door: one obvious next step, cost and payoff stated.

**Band 2 — Route (center).** A vertical spine of 6–8 visible nodes. Each has a type and state: `read`, `practice`, `checkpoint`, `review`; `settled`, `current`, `open`, `due`. The current node is expanded and connected to the threshold. The whole course shape is visible; only the contents of future checks are withheld. Click a node to open it — no modal. Reuse `PathPreview`'s state model (`DESK_STATE_TONE`) and `aria-current="step"`.

**Band 3 — Margin (right).** Identity and change, not stats: learner · classroom · teacher, "last touched," and a short "since you were here" (new sources, review due, last session's note). Notebook and sources are drawers. Courses/Library/Parent Studio become rooms off the hub, not tabs competing with `Resume`.

**Vertical slice (build first).**
1. `HubFrame`: threshold + spine + margin; a 1px route line spans bands 1–2; serif title, generous space, one accent.
2. Typed nodes from existing data: settled/current/open/due exist; add `checkpoint` only where the outline has a real quiz, `review` from the due count. No invented types.
3. Run line: reuse `useSessionEstimate`; add "ends at …" from the next checkpoint ordinal, or the section end.
4. Identity strip from `currentScope()`; switcher only when >1 profile/classroom. Keep "Progress and personal answers stay on this profile."
5. One motion (route line draws 160 ms), visible focus, `prefers-reduced-motion`; optional sound off. Empty first run: Create / Import / Preview, no carousel.

**Later roadmap.**
- Per-objective `last_opened`, so the route reopens where the learner stopped (Celeste's `LastArea` [4]).
- A "what changed" digest — new sources, review due, teacher note: relatedness without a social feed.
- A review "run": choose a short set, see its shape, end at a rest node (Spire's map logic [5]); still no XP.
- Sound/haptics/transitions auditioned for adult register; never on by default.
- Never: XP, levels, badges, leaderboards, streaks, loot, mascots, "mastery" claims, `DEFEATED`.

**Acceptance test.** A returning learner should answer, in three seconds: where am I, what is next, how long, what will it produce, who else is here. If it can't, it is still a dashboard with a game skin.

## References

[1] h-idris, main menu design — https://h-idris.com/blog/game-main-menu-design.html
[2] Wandr, game menu design — https://www.wandr.studio/blog/game-menu-design
[3] teemo.dev, Hades game overview — https://teemo.dev/game-design/hades/systems/game-overview/
[4] frissyn, Celeste save data (`LastArea`) — https://github.com/frissyn/celeste-saves/blob/master/savedata.md
[5] saschb2b, Slay the Spire map & nodes — https://saschb2b.github.io/game-mechanics/games/slay-the-spire/map-and-nodes
[6] Hollow Knight Wiki, Save Data — https://hollowknight.wiki/w/Save_Data_(Hollow_Knight) ; Steel Soul — https://hollowknight.wiki/w/Steel_Soul_Mode_(Hollow_Knight)
[7] Hades Wiki, Saving your Progress — https://hades.fandom.com/wiki/Saving_your_Progress
[8] Wikipedia, Celeste — https://en.wikipedia.org/wiki/Celeste_(video_game)
[9] WIRED, How Hub Worlds Shape Video Game Design — https://www.wired.com/story/how-hub-worlds-shape-video-game-design/
[10] gdad.wiki, Juice It or Lose It — https://gdad.wiki/wiki/sources/source-juice-it-or-lose-it
[11] datafield.dev, Hollow Knight case study — https://datafield.dev/video-game-design/part-04/chapter-19/case-study-02.html
[12] Kaißer, Kleffmann & Schaaff, age-aware gamification — https://arxiv.org/abs/2512.15630
[13] Bogost, Persuasive Games: Exploitationware — https://www.gamedeveloper.com/design/persuasive-games-exploitationware
[14] Van Roy & Zaman, Why Gamification Fails in Education — https://link.springer.com/chapter/10.1007/978-3-319-51645-5_22
[15] The Age, app streak culture — https://www.theage.com.au/lifestyle/life-and-relationships/it-s-highly-manipulative-the-dark-side-of-app-streak-culture-20240903-p5k7e5.html
[16] Hades Wiki, God Mode — https://hades.fandom.com/wiki/God_Mode
[17] teemo.dev, Celeste Assist Mode reference — https://teemo.dev/game-design/celeste/systems/assist-mode-and-accessibility-reference/
[18] Wikipedia, Game feel — https://en.wikipedia.org/wiki/Game_feel