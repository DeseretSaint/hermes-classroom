# Film publish packet — the X post, the form answers, the licence and the QC

Prepared 2026-11-11 during the 13:00–14:00 MST freeze, for the contest that closes at
**15:00 MST / 17:00 EST**. Nothing in this file has been posted or submitted. The post and the form are
DeseretSaint's actions under `docs/SUBMISSION.md` §0.

The film is `docs/launch/coursebook-demo-90s.mp4` — **51.0 s**, measured, not estimated
(`QC.md` carries the command output). It is silent by design; every beat carries its message as
on-screen type so the file reads with sound off, which is how X autoplays.

## 1. The X post — 271 characters raw, 254 weighted

```
Coursebook: turn a topic into a course you can finish. A Hermes Desktop plugin — a plan you approve, one objective at a time, typed checks, packs already on the device. MIT. 51 s silent demo. Built with @NousResearch Hermes Agent.
github.com/DeseretSaint/hermes-classroom
```

Length, counted on the string above exactly as it sits inside the fence:

```
$ printf '%s' '<the two lines above>' > post.txt && wc -m post.txt
271
$ awk '{print length($0)}' post.txt
230
40
```

271 characters including the line break (230 + 40 + one line break); X's weighted count is **254**, because the bare URL is charged
23 regardless of its 40 rendered characters. Both are under X's 280 limit, with the line break counted.
Tags `@NousResearch`. Links the public repository. Makes no efficacy, mastery, benchmark, COPPA or
child-safety claim.

- Attach `coursebook-demo-90s.mp4` to the post.
- One URL only, so no card conflict: the repo link is the only link in the text.

**Alt text** (paste into X's media description):

> A 51-second silent product film on a dark green ground. A title card reads "A course, not a chat." Then
> five real Coursebook screens appear one at a time, each with a sentence beneath it: the Home library, an
> illustrated shopfront over three course cards, with a fox standing in front of a clock on the shelf; the
> Workshop's Discover shelf, a Japanese register pack preview above three pack cards; a course page titled
> Read the Night Sky whose plan waits for approval, above an Evidence list; a lesson with four objectives
> in a row and a Japanese line shown with furigana and romaji; and a typed check with the learner's answer
> filled in and a Check answer button. The end card reads Coursebook, a local-first study plugin for
> Hermes Agent, github.com/DeseretSaint/hermes-classroom, MIT, captured from the real plugin - build
> c4fe2d63.

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

The file is 2.00 MB, well under any upload limit; re-encode is not needed for size.

## 4. What the film does not show, and what the copy may not say

The frames are captures of a real installed plugin at tree `172b61aa`, module `98400108`. The submission
pins `7831d31d`, module `71d940ce`; the single desktop commit between them is `468f45c0`, which changed
the Home scene only. `QC.md` §Frame provenance measures that per beat and records the Home delta as a
declared deviation.

Two limits follow, and the copy respects both:

1. **No goal-to-course generation is shown.** The film shows a course that already exists, its plan, a
   lesson and a check. The claim in §1 ("turn a topic into a course you can finish") is the product
   promise reserved to the owner at `VIDEO-PLAN.md` §2 and §13, not something this take demonstrates; a
   typed-goal run was still under repair at the freeze (`docs/ACCEPTANCE-RUN.md`).
2. **Nothing about grading is shown.** Beat 5 shows an answer typed into the box with the button
   unpressed; no grade or feedback appears. The film's own caption says "graded against the objective",
   which is the take's one on-screen overstatement, recorded in `QC.md`. The X copy was cut from
   "evidence you can inspect" for the same reason: no evidence surface appears in the film.

If the owner wants the post to claim only what the take proves, the minimal edit is to open on the shown
surfaces — "a plan you approve, one objective at a time, typed checks" — and drop the product promise.
That is a wording call reserved to him under §13; this packet keeps the sanctioned sentence and states
the gap instead of hiding it.
