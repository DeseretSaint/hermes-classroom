# Demo script (0.1.0 candidate)

Status: measured, not recordable. Sentinel ran the demo gate on the release commit
`29bede7643403cd9d608499232125e6347c680dd` (`origin/master`) on 2026-11-07, in a fresh isolated rig:
home `~/.hermes/coursebook-demo-gate-29bede7/home`, backend `127.0.0.1:44297` serving that worktree,
Desktop window on CDP 9367. The backend reported `cb.rpc` v7, 52/52 implemented,
`contract_problems: []`, and the installed `desktop/plugin.js` sha256 is
`c59ebc3c937385f1119787a5522acda09fb852f8180c06e3d3f4615e3c8281fb`, the file in that commit.

The four scenarios U01-U04 pass on that commit: the `#/coursebook` route mounts from a real sidebar
click (U01); a bundled Japanese pack previews, imports and creates a course and enrollment through
the UI (U02); the route is reachable and operable by keyboard with visible focus and named controls
(U03); and 200% text, 460 px narrow, reduced motion and no-media all hold, with 8 clipped nodes only
at 460 px plus 200% (U04). Raw captures: `audit/demo-gate/`.

The demo is still not recordable, and the blocker is now the lesson surface rather than the route.
On `29bede7`, every lesson-start action ("Resume lesson" on the card or overview, "Start a fresh
run" in the textbook) moves the window to `#/`, unmounts `[data-cb-route]`, and opens no chat and no
Coursebook pane. That is the 8-25 s, 25-34 s, 34-40 s and 40-47 s surface, so those shots cannot be
driven, and D1 in `docs/REVIEW_CB017-demo-gate.md` is a P1 on the recorded build. Separately, the
Japanese pack the script names states "No audio is bundled", so the 73-82 s narration line "spoken"
has no asset on this pack. The Library empty state also still says this build has no pack import
(`desktop/plugin.js:2271`) while import works (D2).

Gate status: NOT MET on `29bede7`. Recording starts only after Sentinel passes U01-U04 on the exact
build being recorded, and the shots themselves must be drivable; both are re-run after D1 is fixed.
Nothing is recorded before that, and no recording is labeled as having passed this gate. Recording
and publishing also need DeseretSaint's approval.

The one operator action left, beyond the D1 fix, is profile choice: this host runs one gateway,
owned by profile `default`, and a second gateway is refused. To record chat and pane together,
install the recorded commit into that profile and restart its gateway
(`scripts/install-local.sh --home ~/.hermes/profiles/default`, then `hermes gateway restart`).

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

The route itself mounts on `29bede7` (U01), so no row is excluded for an unmounted surface. The rows
that cannot be captured today are 8-25 s, 25-34 s, 34-40 s and 40-47 s: starting a lesson leaves the
route for `#/` (D1), so the chat-and-pane, attempt, notebook and restart shots have no surface to
show. The 73-82 s row has a visual and a text alternative but no audio in the named pack. Those rows
stay in the script as targets, not as shots that can be captured today. A partial cut that drops them
is a different video with different claims, not this script.

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
