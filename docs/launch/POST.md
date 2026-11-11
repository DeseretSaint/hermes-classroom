# Film publish packet — the X post, the form answers, the licence and the QC

Prepared 2026-11-11 during the 13:00–14:00 MST freeze, for the contest that closes at
**15:00 MST / 17:00 EST**. Nothing in this file has been posted or submitted. The post and the form are
DeseretSaint's actions under `docs/SUBMISSION.md` §0.

The film to post is `docs/launch/coursebook-launch-30s.mp4` — **30.4 s**, measured (see `QC.md`).
1920x1080, 30 fps, H.264 High level 4.0, yuv420p, closed 2 s GOP, AAC LC stereo 48 kHz, `+faststart`,
5,609,771 B, sha256 `d46b46d17d0df2a3e5d...`. Plates are the film3 set at 1344 route width dpr 2 from
module `0cb478ec` (composition evidence, not a live install, D-010) plus the owner's `home-full` render.
The film carries a single narration track and no music. No per-beat captions: the words are spoken.

## 1. The X post — 267 characters raw

```
Coursebook, learn anything. 📚 Pick a topic and it writes the whole course: lessons, practice, a tutor beside every page, and a game mode that turns it into a world. Built with Hermes Agent from @NousResearch. MIT. 30 seconds ↓ github.com/DeseretSaint/hermes-classroom
```

Length, counted on the string above exactly as it sits:

```
$ python3 -c "print(len(open('cap.txt').read().strip()))"
267
```

**267 characters**, under X's 280 limit, counted with the emoji as one character. Tags `@NousResearch`. Links the public repository. Makes no efficacy,
mastery, benchmark, COPPA or child-safety claim.

- Attach `coursebook-walkthrough.mp4` to the post — **42.4 s**, narrated, **−14.8 LUFS** measured (inside
  the plan's −15.0 to −13.0 window; the audio was re-normalised once, video stream copied bit-for-bit), sha256
  `9b6eed5eb6b17e17d6b0982b4f084e7571fe9090be3fe2e2c4b117486f17e620`.
- One URL only, so no card conflict: the repo link is the only link in the text.

**Alt text** (paste into X's media description):

> A 42-second product film on a dark green ground, with an optional narration track and every beat
> written on screen. A title card reads "Coursebook, learn anything." Six Coursebook surfaces follow,
> each with a sentence beneath it: the Home library, an illustrated shopfront over four course cards,
> with a fox standing ahead of a clock at the shelf's front edge; the Workshop's Discover shelf, a
> Japanese register pack preview above three pack cards; a course page whose plan waits for approval,
> above an Evidence list; a lesson page with a Japanese line shown with furigana and romaji; a typed
> check with the learner's answer filled in and a Check answer button; and a Parent mode printout, an
> A4 guide with the four steps and the task card. The end card reads Coursebook, learn anything,
> textbook, game and parent modes, export a course as a pack, github.com/DeseretSaint/hermes-classroom,
> MIT, rendered from the real plugin.

## 2. The contest form — `https://form.typeform.com/to/FwJLvOln`

The form is a multi-step Typeform. It opens on **Plugin Title** and **Plugin Description**, then asks for
the links below. Answers in copy-paste order:

| Step | Answer |
| --- | --- |
| Plugin Title | `Coursebook` |
| Plugin Description | `Coursebook is a native Hermes Desktop learning workspace where a lesson is governed state rather than chat: one objective at a time, typed checks graded against the objective, transactional transitions, inspectable evidence, and sourced visuals, plus portable lesson packs. It ships with a Japanese L0 classroom and imports any pack a teacher exports. Local SQLite under $HERMES_HOME; no telemetry, no credential store, no self-update. MIT.` |
| Repository | `https://github.com/DeseretSaint/hermes-classroom` |
| Catalog PR | `https://github.com/NousResearch/hermes-agent/pull/152920` |
| Demo video (X post) | the URL of the post from §1 |
| Team | `DeseretSaint` |

Do not paste the film's file path into a URL field; the form asks for a link and X is where the file
lives. The description may carry product claims the film does not show, because it describes the plugin,
not the take; the X copy in §1 does not.

## 3. Order of operations

1. Post §1 on X with the film attached; copy the post URL.
2. Paste that URL and the catalog PR URL into the form with §2's answers.
3. Screenshot or copy the confirmation and add it to `docs/SUBMISSION.md` gate 15.

The file is 3,025,839 B (2.89 MiB), well under any upload limit; re-encode is not needed for size.

## 4. What the film does not show, and what the copy may not say

Provenance is mixed and is stated per beat in `QC.md` §Frame provenance. Beats 1 Home and 2 Workshop are
**component renders of the submitted module** `71d940ce` (`7831d31d`) with seeded fixture data, made
because the plugin installed on the capture host is stale (`0d98d606`). Beats 3-5 are real window
captures of module `98400108` (`172b61aa`), and the one desktop commit between those modules,
`468f45c0`, changes the Home scene only, so those three screens are true of the pin. Beat 6 is an A4
parent guide the plugin prints. The end card's "rendered from the real plugin" is true of all six
content beats; no frame is a mockup.

Four limits follow, and the copy respects them:

1. **No goal-to-course generation is shown**, even though beat 2 says "Turn any topic into a course."
   The frame is the Discover pack shelf with three ready packs: no goal entry, no generation pass, no
   research surface. The claim in §1 ("turn a topic into a course you can finish") is the product
   promise reserved to the owner at `VIDEO-PLAN.md` §2 and §13, not something this take demonstrates; a
   typed-goal run was still under repair at the freeze (`docs/ACCEPTANCE-RUN.md`).
2. **The tutor caption is not shown.** Beat 4 says "A tutor beside the lesson. Ask anything; the answer
   cites the page you are reading." The frame is the lesson document: no tutor rail, no question box and
   no citation appears. This is the take's second on-screen overstatement, recorded in `QC.md`.
3. **Nothing about grading is shown.** Beat 5 shows an answer typed into the box with the button
   unpressed; no grade or feedback appears. Its second line, "Graded against what the lesson taught, not
   the chat", describes behaviour the frame does not display. The X copy was cut from "evidence you can
   inspect" for the same reason: no evidence surface appears in the film.
4. **The narration is optional, not load-bearing.** The AAC track is 38.4 s against the 42.4 s picture
   and does not start until 3.36 s; every beat is also written on screen, and the film's frames were
   reviewed with sound off for `QC.md` §Muted comprehension. The sentence "42 s demo, no sound needed"
   in §1 is true; "silent" would not be, because the file carries a track. Loudness measures −14.8 LUFS,
   inside the plan's −15.0 to −13.0 window, after one audio-only re-normalise that left the picture
   bit-identical (`QC.md` carries the command and both measurements).

If the owner wants the post to claim only what the take proves, the minimal edit is to open on the shown
surfaces — "a plan you approve, one objective at a time, typed checks" — and drop the product promise.
That is a wording call reserved to him under §13; this packet keeps the sanctioned sentence and states
the gap instead of hiding it.
