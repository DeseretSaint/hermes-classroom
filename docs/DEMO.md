# Demo script (0.1.0 candidate)

Status: not recorded, and not recordable on this host today. Gate 7 is unmet: Sentinel's demo
scenarios (U01-U04) have not passed on commit `e93b8c5`, and recording needs operator approval.

Two surfaces decide it, and they fail for different reasons:

- **The route mounts.** With a reachable backend, `#/coursebook` renders the course library,
  `New course` and Parent Studio on this commit's `desktop/plugin.js`
  (`docs/CB016-RELEASE-VERIFICATION.md` §3b).
- **The chat does not.** This host runs one gateway for profile `default` and refuses a second for
  any isolated home (`Cannot reserve gateway profiles`), so an isolated window shows the session
  list for every route and has no composer. The 8-25 s chat shot needs a bound chat, and a lesson
  binds to a chat. Until that is resolved there is no honest way to record the chat turns.

The build does perform the four flows this file once said were missing. Course creation and pack
export run on this tree: `pack.import` creates a course and enrollment, `pack.export` returns a
hashed archive (`tests/adversarial/evidence/attack-packs.json`, P17, P18, P20), and the last full
mounted-backend run counted 31/31 expectations (`scripts/validate.sh` on `e93b8c5`). Chat binding is
written by `POST /sessions/bind` and read back by `binding.get` in the CB-014 log. Grading commits
exactly one attempt and one transition per submit, and fails closed on an invalid, hung or throwing
grader (`tests/adversarial/evidence/attack-state.json`, S01, S02, S10-S12).

Gate status: NOT MET. Recording starts only after Sentinel passes the demo scenarios on the exact
build being recorded. Nothing is recorded before that, and no recording is labeled as having passed
this gate. Recording and publishing also need DeseretSaint's approval.

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

The 8-25 s chat row is the one this host cannot capture today: a lesson binds to a chat, and no
second gateway can start while profile `default` owns the host gateway. The other rows need the
route that does mount here, but none of them may be recorded before Sentinel passes U01-U04 on this
commit.

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
