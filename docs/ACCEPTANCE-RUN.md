# ACCEPTANCE-RUN - Gate 7 demo scenarios on the frozen tree

Card: `t_720119db`. Owner: Sentinel. Run window: 2026-11-11 13:27-14:20 MST, isolated backend plus a
real Desktop window. This file records what I drove myself on the pinned tree. It does not re-grade the
course-creation leg (`t_ad25d623`, CP-015g), which is cited only where it is the sole measurement.

Round 2 (this revision) answers the round-1 review: the three frames that did not carry their
observable were recaptured scrolled to it, the second attempt's rows are quoted, and every FAIL row now
names the card that owns it.

## Tree, module and backend (recorded from commands, not from a report)

| fact | value | how |
| --- | --- | --- |
| scored tree | `7831d31d98100e034bfb0bcdd5a6569a082e6c79` | `git worktree add --detach ... 7831d31d`; `git rev-parse HEAD` in that tree |
| `desktop/plugin.js` at that tree | `71d940ce0398220fe1d25d1ec39b1e4bdfbc2a1c257eb7eb42292c628ac4d4b8` | `sha256sum tree/desktop/plugin.js` |
| installed Desktop copy | same sha `71d940ce...` | `sha256sum home/desktop-plugins/coursebook/plugin.js` |
| second load path `home/plugins/coursebook/desktop/plugin.js` | same sha `71d940ce...` | `sha256sum` (both copies verified so the window cannot serve a stale module) |
| backend | `hermes serve --isolated --port 44501`, `HERMES_HOME=<rig>/home`, started from the pinned tree | process env read from `/proc/<pid>/environ` |
| `GET /api/plugins/coursebook/runtime` (re-answered live at 14:00 MST) | `wire_contract: cb.rpc`, `wire_version: 26`, `contract_methods: 93`, `implemented_methods: 93`, `plugin_root: .../g7/tree` (the pinned tree) | `curl -H 'Authorization: Bearer <rig token>' .../runtime` -> `runtime-now.json` |
| window | dev Electron 44.9.3 + vite renderer 5174, CDP 9413, `HERMES_HOME=<rig>/home`, remote connection to `127.0.0.1:44501` | `scripts/cb013-live-window.sh` with `COURSEBOOK_TEST_STATE=<rig>` and `CB013_CDP_PORT=9413` |

Operator notes folded in: the operator pinned `origin/master` `7831d31d` (module `71d940ce...`) and later
measured `origin/master` `fc6ec7b7` with the **same** module sha. I scored **`7831d31d`**. No Gate 8c sha
was available to me at run time, and both named commits ship the identical `desktop/plugin.js`.

### Rig disclosures (so no row is read as more than it is)

1. The Desktop half of this home never inventories the installed package on its own. I wrote
   `hermes.desktop.pluginDecisions.v2 = {"coursebook":true}` into the window's localStorage and
   reloaded; that is the documented rig shortcut for defect **`t_244d7ad2`**, not product behaviour.
   Without it the `#/coursebook` route does not register and no scenario can start.
2. The course data is the CP-015 demo shelf copied into a fresh rig home
   (`~/.hermes/coursebook-test-cp015/home` -> `<rig>/home`): four courses authored by the product's own
   create flow plus Sourdough. No row was hand-inserted. The copy is disposable; nothing outside the
   rig was mutated.
3. Two typed attempts were committed on the Sourdough section during round 1 (20:32:30Z and 20:34:10Z).
   Both are quoted in full below. Round 2 added no attempts: every recapture was navigation and scroll
   only, except the single `Try again` press used to drive S3.
4. Round 2 restarted the window on the same home and userdata (`cb013-live-window.sh --restart`, then a
   fresh launch of the same Electron build), so S2 is measured across real process restarts, not a
   reload.
5. Recaptured frames are 1896x1030 (the wider rig window); the two round-1 frames not re-captured are
   941x640/941x662. Each frame's size and sha are listed in the recapture log.

## Scenario table

The carrying frames are committed beside this record in `docs/concept-parity/demo/gate7/`; the sha256
prefixes quoted in the rows are of those committed PNGs.

| # | scenario | step I drove | observable that proved it | carrying frame / response | verdict |
| --- | --- | --- | --- | --- | --- |
| S1a | plan surface | Home -> `Astronomy` -> `Review the plan` -> Plan section | Plan surface renders `Plan draft · v6`, `plan sha256:5d4d68b44aaf...`, the refusal headline **"The planning service did not answer"**, "It stays here, unapproved", `Where: The plan, before it was approved`, "It is not approved, and no lesson will be written from it.", one primary **`Try again`**, and **no approve control** (27 visible controls, `approveish: []`) | `g7-06-plan-surface.png` (sha `ec72d7b3...`, 1896x1030, scrolled to the draft label); DOM quoted | **PASS** (surface is honest about a failed run; nothing unapproved is offered as approved) |
| S1b | approve | not drivable on this home | approved state exists only from an earlier run: `plans` row `93cdc4ea1a52fb49`, course `crs_1ad565b...`, **version 5, state `approved`**, `plan_hash sha256:988fb899...`. The approve **click** was not exercised on this tree | sqlite `plans` query quoted below | **FAIL (not driven)** - no plan on this home can reach an approvable state; card `t_4e993e34`, blocked by `t_3e8b07ba` |
| S1c | lesson | Home -> `Sourdough` -> `Open section` | lesson page renders the objective heading, the typed question ("In your own words, explain what a sourdough starter is ... lactic acid."), `Your answer`, textarea `#cb3-classroom-answer`, disabled `Check answer`, and the no-chat state "This section has no chat yet" -> `Start a fresh run` | `g7-11-check.png` (sha `682fbd3f...`, 1896x1030, scrolled so the no-chat state, question, field and button are all in frame) | **PASS** |
| S1d | check -> feedback | typed a full-sentence answer, `Check answer` (round 1; two attempts total) | verdict element `data-cb3-verdict="not_yet"`; DB: two `attempts` rows, two `transitions` rows, two `evidence` rows (quoted below), each attempt one revision step with `next_action=retry_attempt`; **the graded sentence renders "Not quite. does not match an accepted answer"** with `criteria_json` observed text `"does not match an accepted answer"` (empty subject, no reason) | `g7-16-verdict-frame.png` (sha `74f1cf5e...`, verdict scrolled into view); sqlite rows quoted below | **FAIL (copy)** - behaviour is correct (one attempt -> one transition -> one evidence row per attempt); the learner-facing feedback sentence is broken in shipped product. Card `t_b0599ff2` |
| S2 | resume | stopped the window, relaunched it on the same home/backend (two real restarts), then reopened Home -> Sourdough -> `Open section` | after restart the same section and objective come back (`Explain what a sourdough starter is ... sour taste`), the same typed question, the check in `awaiting_input` with an empty field and disabled `Check answer`, and the rail records `1 of 1 checks recorded` with chip `Hinted` (the latest attempt, `att_ac3bc6f5...`) and `Next up: Review 1 objective(s)`; the DB still holds both committed attempts | `g7-15-resume-restart.png` (sha `151aad80...`, 1896x1030; objective, counter, chip, question, field and button all in one frame) | **PASS** (same objective and same pending question survive a real app restart). Restated below: the round-1 "First try, no hints" snapshot is superseded |
| S3 | rejected plan's repair path | pressed `Try again` on the Astronomy refusal (S1a surface), waited for the job to reach a terminal state | repair run was driven and decided: job `job_b14fffdb5b70436ab60071a211444496` (`kind=plan`, **`state=failed`**, 20:53:37Z -> 20:56:18Z) with `HOST_UNAVAILABLE` / `coursebook.plan.validate failed: APIConnectionError: Connection error.`; plans table unchanged (v6 draft still newest); surface then reads "The planning service did not answer", "Where: The plan, before it was approved", "It is not approved ...", `Try again`, no approve control | `g7-06-plan-surface.png` (post-repair state) plus the `jobs` row quoted below; `t_ad25d623` cited for the validator-seam refusal | **FAIL (repair not completed)** - the affordance, the honest refused state and the retained draft are measured, but the re-plan itself dies at the provider, so no repaired plan exists. Card `t_fe299a64`, blocked by `t_3e8b07ba` |
| S4 | parent-only surface | Home nav -> `Parent Studio` | `h1 "Parent Studio"`; tabs `My lesson plans` / `Take-home from a lesson` / `Homework`; copy is parent-facing ("the child's age and reading level, where you will teach, what you have, what to leave out"); empty state names one next action, primary `New lesson plan`; no child-facing chat or child view anywhere on the surface | `g7-13-parent-studio.png` (sha `fb427148...`, 941x640) | **PASS** |

Count: **4 PASS** (S1a, S1c, S2, S4) and **3 FAIL** (S1b, S1d, S3). No PASS rests on a test suite alone.

## FAIL rows and the cards that own them

| row | failure | card | blocked by |
| --- | --- | --- | --- |
| S1b | approve click cannot be exercised: no plan on the rig can reach an approvable state without the research/validation lane | `t_4e993e34` (CP-G7-03, sable) | `t_3e8b07ba` |
| S1d | graded feedback renders a sentence with an empty subject ("Not quite. does not match an accepted answer") | `t_b0599ff2` (CP-G7-01, sable) | - (product copy defect, open on this tree) |
| S3 | the repair run dies at the provider (`APIConnectionError` at `coursebook.plan.validate`); no repaired plan is produced | `t_fe299a64` (CP-G7-04, sable) | `t_3e8b07ba` |

`t_3e8b07ba` is the measured cause of both S1b and S3: the isolated backend cannot read the research
provider key, so no fresh plan stage can complete. These two rows are not product-behaviour regressions
by themselves; they are gate blockers that must be re-driven once the provider lane is reachable.

### Supervisor note at merge (2026-11-12, trunk `c563a7a9`)

This record and its carrying frames lived only on `wt/gate7-acceptance` (tip `18126291`), and that branch
cannot be merged whole: it still carries `visual/node_modules` and predates its removal at `79d35897`.
The supervisor took only the two commits that add this file and its frames (`d48167b2`, `18126291`) onto
trunk. No measurement here was re-derived or edited; the five quoted frame sha prefixes were re-checked
against the committed PNGs before the merge and match.

The three owning cards above are now **archived duplicates** of live cards: S1b and S3 point at
`t_3e8b07ba` (the provider-key scope defect), S1d at `t_d2cbff9a` (both graded-copy defects). Gate 7
therefore stays `[ ]` on trunk, and the gate row in `docs/SUBMISSION.md` names the live cards.

## Rows that need care

- **S1a headline changed during the run, and that is disclosed.** Round 1 saw the pre-repair aborted-run
  banner "The run lost its worker". The single `Try again` press used for S3 then produced a completed
  refused state, so the recaptured frame carries "The planning service did not answer" instead. Both
  states carry the same claim: the draft is displayed, unapproved, with a named reason, a retry
  affordance and no approve control. Both were observed; neither is inferred.
- **S1b.** The gate wording ("plan -> approve -> lesson -> check -> feedback") assumes a plan that can be
  approved in the same session. On this home none is: Astronomy is a refused draft, and the three other
  courses were approved by earlier runs. Approving a plan is not a local action - the run that produces
  it needs a provider, and research is unavailable to the isolated backend (`t_3e8b07ba`, re-confirmed
  by CP-015g an hour earlier). I will not call the loop green on a state an earlier run produced.
- **S1d.** This is the same copy `docs/launch/QC.md` records as the reason two film captures were
  rejected. It is **still on the pinned tree**, so the product defect is open regardless of what the cut
  shows. Both committed attempts carry the same `criteria_json` observed text, so the defect is not an
  artefact of one answer.
- **S2 restated.** Round 1 quoted `1 of 1 checks recorded` plus `First try, no hints`. That snapshot is
  no longer reproducible because a second (`hinted`) attempt landed at 20:34:10Z. The durable facts now
  measured after a real restart are: same section and objective, same typed question, check in
  `awaiting_input`, `1 of 1 checks recorded`, chip `Hinted`, two committed attempts in the DB. The
  counter counts checks, not attempts.
- **S2 caveat.** The section has no chat binding ("This section has no chat yet"), so the *bound-chat*
  resume (the demo's "same objective, same pending check" beside a live chat) was not part of this
  measurement. What is measured is the durable side: objective, question, attempt count, evidence class
  and next action survive a real window restart. The previous verdict is deliberately not re-rendered;
  the check reopens for a retry, which matches `next_action=retry_attempt`.
- **S3.** The repaired validator seam itself is not in question here: `t_ad25d623` measured it holding on
  the prior tip. What failed on this rig is provider reachability during `plan.validate`.
- **S4 covers the parent-only surface, not its authoring flow.** `New lesson plan` was not pressed.

## Recapture log (round 2)

Window: CDP 9413, viewport 1896x1030. Every step below is navigation/scroll only; no text was typed and
no attempt was submitted. The driver is `node driver.mjs --eval <file> --shot <png>`; each script ends
with the observable scrolled into view and returns its bounding rects as proof.

| frame | script | scroll action proved by the returned rects | sha256 | pixels |
| --- | --- | --- | --- | --- |
| `g7-06-plan-surface.png` | `wide-s1a.js` | draft label at y 301, headline 346, `Try again` 557-601, all inside 1030 | `ec72d7b30588ba0628e0313253315d5d2310568d6d592f6717b2fa62f0f3effc` | 1896x1030 |
| `g7-11-check.png` | `wide-s1c.js` | no-chat heading y 537, question 677-758, field 795-889, `Check answer` 901-949 | `682fbd3f280dd939f2e0930a3fa3b85493262c8acc78189882188deb7c59d513` | 1896x1030 |
| `g7-15-resume-restart.png` | `s2-state.js` after two real restarts | objective y 277, counter/chip 690/717, question 729, field 847, button 953-1001 | `151aad8011a80ebfbbc3fe48ff850a06deccd370b44106e99ec7b1e5d4fed5bf` | 1896x1030 |
| `g7-13-parent-studio.png` | round 1 (`d1-parent-studio.js`) | unchanged; reviewer reproduced | `fb4271486611775fe26b457e0e2be87fd29584dc2b11fb7f3e0096243fb5767c` | 941x640 |
| `g7-16-verdict-frame.png` | round 1 (`a10-verdict-frame.js`) | unchanged; reviewer reproduced | `74f1cf5eb1ecb71002e3d01060dd004b578a377c1965c3e89e2b77475299d34a` | 941x662 |

## Commands quoted

```
# tree and module
git -C <repo> worktree add --detach <rig>/tree 7831d31d
git -C <rig>/tree rev-parse HEAD
7831d31d98100e034bfb0bcdd5a6569a082e6c79
sha256sum <rig>/tree/desktop/plugin.js <rig>/home/desktop-plugins/coursebook/plugin.js <rig>/home/plugins/coursebook/desktop/plugin.js
71d940ce0398220fe1d25d1ec39b1e4bdfbc2a1c257eb7eb42292c628ac4d4b8  (all three identical)

# backend runtime, answered live from the pinned tree
curl -H 'Authorization: Bearer <rig token>' 'http://127.0.0.1:44501/api/plugins/coursebook/runtime?profile='
{"wire_contract":"cb.rpc","wire_version":26,"contract_methods":93,
 "implemented_methods":[ ... 93 entries ... ],
 "plugin_root":".../g7/tree"}

# sqlite: approved plan (earlier run; S1b)
93cdc4ea1a52fb49|crs_1ad565bfb4cf42fcbc82527371ccc64b|5|approved|sha256:988fb899d4a48a6d6a32c621afeb3a1fa4668e5017a45cd38dda6b4bf215cbac

# sqlite: BOTH graded attempts on Sourdough section 1 (S1d), one transition and one evidence row each
att_1f49188c75a74e18b20296ff7924420f|text|not_yet|cold|committed|2026-11-11T20:32:30.313385+00:00
  answer="A sourdough starter is flour and water where wild yeasts and lactic acid bacteria feed on carbohydrates; the bacteria make lactic acid, which gives the bread a sour taste."
  criteria=[{"id":"c1","met":false,"observed":"does not match an accepted answer"}]
  grading={"grader":"deterministic:exact","reference_sha256":"sha256:2621078db2cd41dbfcfb19a9fd94255d499767669e18ef5032c4175ebff8b059"}
att_ac3bc6f596d0430dbc3dffa18ba89a25|text|not_yet|hinted|committed|2026-11-11T20:34:10.235272+00:00
  answer="A starter is flour and water that wild yeast and bacteria ferment, and lactic acid makes it sour."
  criteria=[{"id":"c1","met":false,"observed":"does not match an accepted answer"}]
trn_fbcaf281f69442df8f653e4834c2917e|att_1f49188c...|1|2|retry_attempt|2026-11-11T20:32:30.315853+00:00
trn_7d9c6e504c2e4a1aa14f365aea1c1557|att_ac3bc6f5...|2|3|retry_attempt|2026-11-11T20:34:10.235526+00:00
evd_b8c84e7d17b54fb0b78ac01e2bddb218|objective b7bf6f770ba67f4b|att_1f49188c...|layer 1|attempt|cold|2026-11-11T20:32:30.315987+00:00
evd_b887e00d0bf64dc9925e868d86030514|objective b7bf6f770ba67f4b|att_ac3bc6f5...|layer 1|attempt|hinted|2026-11-11T20:34:10.235573+00:00

# sqlite: the repair run driven for S3
job_b14fffdb5b70436ab60071a211444496|plan|failed|created 2026-11-11T20:53:37Z|updated 2026-11-11T20:56:18Z
  error={"category":"capability","code":"HOST_UNAVAILABLE",
         "details":{"purpose":"coursebook.plan.validate"},
         "message":"coursebook.plan.validate failed: APIConnectionError: Connection error.",
         "retryable":true}
```

## Other defects observed while driving these scenarios

| defect | seen in | card |
| --- | --- | --- |
| course page renders `Session length could not be read` + `Retry` on the primary course surface (two courses, survived a window restart) | round 1, while driving S1a/S1c; not re-observed in the round-2 frames (the Home read showed `Session · 15 min`) | `t_b28115be` (cinder; route to sable if the read is Desktop-side) |

## What this run does not claim

- It does not claim the film is approved, or that any video frame was re-verified (gate 13).
- It does not claim a green plan-approval loop, export, install or pack round-trip on this tree.
- It does not claim keyboard-only, screen-reader or 200 % text results; those rows in
  `docs/ACCEPTANCE.md` are outside this card's scenarios and remain `blocked`/`unmeasured`.
- It does not reuse any hash or verdict from another agent; the CP-015g verdict is cited only where
  the course-creation leg is the subject.

## Gate-7 verdict in one line

Measured on `7831d31d` (module `71d940ce`), backend `cb.rpc` v26 with 93 methods: **4 PASS** (plan
surface honesty, lesson render, app-restart resume, parent-only surface) and **3 FAIL** (approve click
not drivable because no plan can be approved without the research lane, card `t_4e993e34`; graded
feedback copy broken, card `t_b0599ff2`; repair run dies at the provider, card `t_fe299a64`). The gate
row cannot be marked closed on a full five-beat loop until the provider lane is reachable and the copy
is fixed.
