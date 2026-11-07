# Demo script (0.1.0 candidate)

Status: measured on the pane-reveal build `5b0f124`, not recordable. Sentinel re-ran the gate on
`2026-11-07` in a fresh isolated rig at `5b0f124630fab9154aef9be5751919eeb8911255` (the merge of
`13d4a75`, t_d587a007): home `~/.hermes/coursebook-demo-gate-5b0f124/home`, backend
`hermes serve --isolated` on `127.0.0.1:44317` serving that worktree, Desktop window on CDP 9377.
The backend reported `cb.rpc` v7 with `contract_problems: []` and `plugin_root` = that worktree; the
installed `desktop/plugin.js` sha256 is
`c151974a7de0fed2662e977a001127327b3c3cf96d19a54cd49b819433f935fc`, the file in that commit.

D1's product half is fixed on `5b0f124`. `13d4a75` adds `revealCoursebookPane()` in
`desktop/plugin.js`, which feature-detects `host.revealPane` and fronts the `coursebook:pane`
contribution after `host.newChat` (fresh start) and after `host.openSession` (bound resume). Measured
on the rig: a section "Start a fresh run" now leaves the route for `#/`, opens a chat **and** reveals
the Coursebook pane beside it; `paneVisibility('coursebook:pane').get()` returned `true` and the still
`audit/demo-gate-5b0f124/shots/u08-fresh-start.png` shows the chat column and the Coursebook pane
together. That is the 8-25 s surface, and it is no longer the blocker it was on `29bede7`.

U01 and U03 pass on `5b0f124`: the `#/coursebook` route mounts from a real sidebar click (U01), and
the route is reachable and operable by keyboard with visible focus and named controls (U03: 5 tabs to
"Open Coursebook", Enter mounts the route, 18 in-route stops all `:focus-visible` and named). U04
holds at 1440 px with 100% and 200% text (document overflow 0, 0 unnamed controls, 0 clipped nodes,
reduced-motion max transition and animation 0 s). Raw captures: `audit/demo-gate-5b0f124/`.

The demo is still not recordable, and the remaining blocker is reachability on the rig rather than the
route or the pane. The isolated backend has no inference provider: the shell reports
`Backend: inference unavailable` and a fresh thread stays on `Waking up default…`. With no first turn
there is no durable stored session id, so no active chat binding can be created, `Submit answer` stays
disabled (the section states "This section's chat binding is detached"), and the notebook has no
teaching segments to save ("Segments appear here after a teaching turn in the bound chat"). Therefore
the 8-25 s graded attempt, the 25-34 s evidence transition, the 34-40 s notebook save and the 40-47 s
bound restart/resume cannot be driven on this rig, and the 73-82 s narration line still has no asset
because the named Japanese pack declares "No audio is bundled". Separately, the Library empty state
still says this build has no pack import (`desktop/plugin.js:2271`) while import works (D2).

Gate status: NOT MET on `5b0f124`. D1's product half is fixed, but U01-U04 and the four learning shots
have not been measured on the exact build that would be recorded in the default profile, and the
shots above remain undrivable until a profile with inference plus an active binding is in place.
Recording starts only after Sentinel passes U01-U04 on the exact build being recorded, and the shots
themselves must be drivable; both are re-run after that profile is chosen. Nothing is recorded before
that, and no recording is labeled as having passed this gate. Recording and publishing also need
DeseretSaint's approval.

The one operator action that remains is profile choice and inference: this host runs one gateway,
owned by profile `default`, and a second gateway is refused. To record chat and pane together, install
the recorded commit into that profile and restart its gateway
(`scripts/install-local.sh --home ~/.hermes/profiles/default`, then `hermes gateway restart`), so the
chat runs on a profile that can actually answer. Until then the pane surface is proven but the chat
beside it is not.

## Rules

- One continuous run on one machine, at a comfortable desktop width, with the real Hermes chat
  and the Coursebook pane visible together for the learning shots.
- The first shot is the course library, not Settings. Installation is not shown.
- Every shot shows a state change or an artifact. No panel tour, no feature grid.
- Cuts are allowed only to hide waiting. A cut is labeled on screen for its duration, and the
  state before and after must be identical to what the backend reports.
- Cached output is never presented as live generation. Reopening a lesson that already has its
  visual and audio must be shown as a reopen, and the narration says so.
- If a flow fails on recording day, cut the shot and remove the claim it carried. Do not
  substitute a prerecorded simulation for a live path.

## Composition (86 seconds)

Times are targets. Total must stay under 90 seconds.

| Time | Surface | Action | Narration | Live or precomputed | Gate |
| --- | --- | --- | --- | --- | --- |
| 0-8s | Coursebook sidebar, library, Japanese pack preview, enroll | Preview a bundled Japanese pack, then create a fresh course from it | "A prepared classroom, ready to learn from. Fresh progress, nothing imported from its author." | Live | Pack import and course creation |
| 8-25s | Chat and pane side by side | Ask a normal question; the pane shows the current objective and a typed check; submit a wrong answer; specific retry appears | "Chat answers. Coursebook asks what the lesson asks, and grades the attempt against the objective." | Live | Chat binding, attempt submit, grading |
| 25-34s | Pane, evidence strip | Submit a correct new attempt; exactly one transition fires; the evidence row appears | "One correct attempt, one permitted transition, one durable record." | Live | Transition and evidence |
| 34-40s | Notebook, textbook section | Save the explanation to the notebook, reopen the exact section | "The explanation goes back to the page it came from." | Live | Notebook and source anchor |
| 40-47s | Pane after restart | Restart the gateway or the app, return, show the identical pending objective and check | "Restart. Same objective, same pending check." | Live, with a labeled cut if the restart is slow | Resume |
| 47-62s | Parent Studio review, export preview | Review already-generated pages, approve, show the parent guide and learner page | "The parent reviews what was generated, then approves it. Nothing is produced for a child before that approval." | Generation precomputed and disclosed; approval and export live | Parent Studio |
| 62-73s | Export preview | Export the pack; show the file list, rights and the no-upload statement | "The pack carries teaching material, not the learner's history, and it uploads nothing." | Live | Pack export |
| 73-82s | Lesson media | Show the sourced visual and audio, then the text alternative and the next review date | "A sourced visual, spoken, with the text right here. The next review is scheduled." | Media precomputed and disclosed; navigation live | Media, scheduling |
| 82-86s | Closing card | Static end card | "A chat answers. Coursebook makes the next step depend on what you did." | Static | None |

The route and the pane surface mount on `5b0f124` (U01, U03), so no row is excluded for an unmounted
surface. The rows that cannot be captured today are 8-25 s, 25-34 s, 34-40 s and 40-47 s: the chat on
the isolated rig cannot answer (`Backend: inference unavailable`, `Waking up default…`), so there is no
first turn, no stored session id, no active binding, a disabled Submit and no teaching segment to save.
The 73-82 s row has a visual and a text alternative but no audio in the named pack. Those rows stay in
the script as targets, not as shots that can be captured today. A partial cut that drops them is a
different video with different claims, not this script.

## Precomputed and live split

Two things are generated before recording, because doing them live would waste the 90 seconds:

1. The Parent Studio pages. Generation runs on the same build, before recording, through the same
   backend path. The recording shows the review and approval, and the narration states that
   generation happened beforehand. On-screen caption for the duration of the shot: "pages
   generated earlier in this build".
2. The lesson visual and audio for the media shot. They are cached artifacts of the same build.
   The shot is presented as reopening a lesson, never as generating on camera. On-screen caption:
   "cached artifact from this build".

Everything else is live: enrollment, the chat turn, the wrong attempt, the correct attempt, the
transition, the notebook save, the restart, the parent approval, the export and the review
schedule.

The disclosure line is part of the video, not only the description. A judge should be able to
tell which seconds were generated earlier without reading the post.

## Narration discipline

- Say "generated earlier in this build" wherever the precomputed caption is on screen.
- Never say "2 sigma", "guaranteed mastery", "proven to improve learning", "COPPA compliant" or
  "child safe". None of those is true of this product.
- Describe the mechanism, not the outcome: transition, evidence, approval, allowlist.
- Keep each line under about four seconds of speech.

## Capture checklist

| Item | Requirement | Owner |
| --- | --- | --- |
| Build under test | Sentinel demo scenarios passed on the exact commit being recorded | Sentinel |
| Resolution | Desktop window at a width where chat and pane are both legible | Harbor |
| Audio | Narration recorded separately and aligned; no music over narration | Harbor |
| Timer | Every segment timed, total under 90 seconds | Harbor |
| Captions | The two precomputed captions rendered and readable at 1080p | Harbor |
| Claims audit | One pass against this file and `docs/PRIVACY_EGRESS.md` for any sentence that overclaims | Atlas |
| Approval | DeseretSaint approves the cut before upload | DeseretSaint |

## What cannot be claimed from this script

Recorded, this script proves a governed loop on one prepared pack. It does not prove learning
efficacy, does not prove behavior with other packs, and does not prove a public community index.
Those are not in the video and not in the submission text.

## Product-line measurement on the post-0.1.0 tree (not a recording)

This section records what the visual build measured. It does not replace the script above and it
does not change the gate.

- The script and every verdict above were measured on `5b0f124`, the pane-reveal build. That record
  stands as written. This tree (M0-M4, `docs/PRODUCT-LINE-RELEASE-NOTES.md`) was **not** recorded,
  and the demo gate remains **NOT MET**.
- **No video exists.** No shot in this file was captured as video on any commit, and no frame below
  is presented as a recording.

What exists is a still-frame audit of the shipped Desktop module, run by M4-QA at `2b37b5b`:
62 painted frames over Textbook, Guided, Field Quest, Field Desk, Procedure, text-only and
media-unavailable, at light/dark, 1280 and 460 CSS px, 100 % and 200 % text, forced colors and
reduced motion. The host transport was stubbed (it served the real M0 PNG and MP3 and a deterministic
schematic); the module, the paint, the layout and the Chromium accessibility tree were real. Every
number is in `audit/visual/m4-visual/audit.json`; the report is `docs/M4-VISUAL-MEDIA-AUDIT.md`.

| Script row | Product-line still frames available | What they can and cannot carry |
| --- | --- | --- |
| 0-8 s library, pack preview, enroll | Field Desk first-run/empty and backend-off frames (`audit/visual/m2-field-desk/`) | First-run state and real actions. No import run on this tree. |
| 8-25 s chat and pane, wrong answer, retry | None | Requires a bound chat and a live grader. Nothing in the visual build produces this shot. |
| 25-34 s correct attempt, transition, evidence | None | Same; a still of a view cannot show a transition. |
| 34-40 s notebook save, reopen the exact section | Field Notes live frames: save dialog, search, return to the exact block (`audit/visual/m2-field-notes/live-evidence.json`) | The save/search/exact-block behaviour is live-proven on an isolated backend, but not inside the demo's bound-chat loop. Do not splice these into the 34-40 s row. |
| 40-47 s restart, identical pending objective | None | Resume depends on a binding that no isolated rig here can create. |
| 47-62 s Parent Studio review and approve | Not measured in the product line | The 0.1.0 rows in this file are the only record. |
| 62-73 s export file list and rights | Not measured in the product line | Same. |
| 73-82 s media, text alternative | Textbook light/dark, 460 px, 200 % and text-only frames with the real generated PNG and the real MP3, each with caption and text equivalent (`audit/visual/m4-visual/`) | A **still** proves the image renders, the transcript is present and no audio autoplays. It cannot prove audible playback, and it cannot be narrated as "spoken". The named Japanese pack still declares "No audio is bundled", so the shot as scripted still needs a generated narration artifact — provider spend this card did not authorise. |
| 82-86 s closing card | None | Static end card; nothing to measure. |

The visual build does not unblock recording. The preconditions in this file are unchanged: Sentinel
passes U01-U04 on the exact build being recorded, every shot is drivable on that build, and
DeseretSaint approves the cut. No catalog submission, tag or pull request was made from this branch.

