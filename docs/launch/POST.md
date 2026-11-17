# Film publish packet — the X post, the form answers, the licence and the QC

Prepared 2026-11-11 during the 13:00–14:00 MST freeze, for the contest that closes at
**15:00 MST / 17:00 EST**. Nothing in this file has been posted or submitted. The post and the form are
DeseretSaint's actions under `docs/SUBMISSION.md` §0.

The film to post is `docs/launch/coursebook-launch-30s.mp4` — **30.4 s**, measured (see `QC.md`).
1920x1080, 30 fps, H.264 High level 4.0, yuv420p, a keyframe every 2.0 s, AAC LC stereo 48 kHz,
`+faststart`, 5,609,771 B, sha256
`d46b46d17d0df2a3ccd986d2fe0ccc2ed398b564f31754020928742fa8ee1037`. Plates are the film3 set at 1344
route width dpr 2 from module `0cb478ec` (composition evidence, not a live install, D-010) plus the
owner's `home-full` render. The film carries a single narration track and no music. No per-beat captions:
the words are spoken.

Its measured loudness is **-16.4 LUFS**, **1.4 LU under `VIDEO-PLAN.md` §9.3's -15.0 floor**: the posted
file fails that criterion as it stands. The owner decides whether to accept it or spend one audio-only
normalise pass, which would make a new file and a new sha (`QC.md` §"Decision"). Of the other automated §9
rows, items 1, 2, 4 and 5 pass on this blob; item 3 is the loudness row above. Item 6, the muted
comprehension read, is unmeasured on this cut (n=0 of 3, `QC.md` §"Muted comprehension"). Item 7's claim
audit exists only as `QC.md`'s nine-row frame audit, which records what each beat shows but does not trace
every on-screen string to product copy, so no item-7 pass is claimed. Item 8, the craft read, has no
recorded read either.

## 1. The X post — 267 characters raw

```
Coursebook, learn anything. 📚 Pick a topic and it writes the whole course: lessons, practice, a tutor beside every page, and a game mode that turns it into a world. Built with Hermes Agent from @NousResearch. MIT. 30 seconds ↓ github.com/DeseretSaint/hermes-classroom
```

Length, counted on the string above exactly as it sits:

```
$ python3 -c "print(len(open('cap.txt').read().strip()))"
267
```

**267 characters**, under X's 280 limit, counted with the emoji as one character. Weighted the way X
counts a link — the bare URL above is 40 characters and X charges 23 — the same string is **250
weighted** (267 - (40 - 23)). Tags `@NousResearch`. Links the public repository. Makes no efficacy,
mastery, benchmark, COPPA or child-safety claim.

- Attach **`docs/launch/coursebook-launch-30s.mp4`** to the post, and attach no other file — 30.400000 s,
  912 frames, 5,609,771 B, sha256
  `d46b46d17d0df2a3ccd986d2fe0ccc2ed398b564f31754020928742fa8ee1037`. Measured integrated loudness
  **-16.4 LUFS** (LRA 4.6 LU, true peak -4.4 dBFS), which is **1.4 LU under §9.3's -15.0 floor: FAIL**,
  and the owner's call (`QC.md` §"Decision"). No other film file is attached.
- One URL only, so no card conflict: the repo link is the only link in the text.

**Alt text** (paste into X's media description):

> A 30-second product film on a dark green ground, with a spoken narration track and no caption band:
> the on-screen words are the interface's own. It opens on a title card, "Coursebook, learn anything.",
> with "textbook, game and parent modes" beneath it. Six beats follow. The Home field library: a lit
> market street carrying four course cards — Reading a pack before you install it, Japanese: affection
> and register, Parent measurement practice, Technical pack literacy — with a fox standing on a bench at
> the front. A goal card, "What do you want to be able to do?", step 1 of 3, its answer field still empty
> under a greyed example. An approved plan screen, "Plan approved", whose outline lists four activities
> and offers a Generate lessons button. A course page, "Two ways of saying it", listing five missions and
> one checkpoint. A lesson, "Japanese affection and register", with a Field Challenge multiple-choice
> question still unanswered. The Discover shelf, three packs presented over a kitchen scene. The end card
> repeats Coursebook, learn anything, github.com/DeseretSaint/hermes-classroom and MIT.

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
not the take. §1's copy also carries the product promise, and §4 states line by line which of its claims
the take demonstrates and which it does not, so the owner chooses with the gap visible rather than hidden.

## 3. Order of operations

1. Post §1 on X with the film attached; copy the post URL.
2. Paste that URL and the catalog PR URL into the form with §2's answers.
3. Screenshot or copy the confirmation and add it to `docs/SUBMISSION.md` gate 15.

The file is 5,609,771 B (5.35 MiB), well under any upload limit; re-encode is not needed for size.

## 4. What the film does not show, and what the copy may not say

Provenance first, because it bounds everything else. Every content beat is a composed plate, not a
Desktop window capture: the film3 stills at 1344 route width dpr 2 plus the owner's `home-full` render
for the library beat, which is composition evidence (D-010) and not a live install. The cut's history
records it — `080637eb` made the first 30 s cut from module `0d98d606`, and `be8a59d0` (v7) is "owner
Home render as the library beat, X-grade encode". What this pass re-derived is the encode, not the
plates; `QC.md` §Frame provenance states exactly which part of the provenance was carried from gate 13
and not recomputed here.

Five things bound what the copy may say. Four are §1 lines that outrun the take, and the fifth is how the
narration works. All of them are the owner's to accept or cut — the product promise is sanctioned under
`VIDEO-PLAN.md` §2 and §13, and it is not an invention of this packet:

1. **"Pick a topic and it writes the whole course" is not shown happening.** The take does have a goal
   screen — "What do you want to be able to do?", step 1 of 3 — but the field is **empty** (the visible
   text is the greyed placeholder "e.g. Hold a six-minute conversation in Spanish"), no goal is typed or
   submitted, and there is no research or generation pass on screen. The plan that follows is a recorded
   state ("Plan approved · v3 plan …", outline and Generate lessons), and its own footnote reads "No
   source is recorded for this plan." Nothing in the film demonstrates a goal becoming a course.
2. **A lesson and a check are shown; "a tutor beside every page" is not.** The lesson beat is the lesson
   document plus a multiple-choice Field Challenge. No tutor rail, question box or citation appears in any
   beat of this cut.
3. **"a game mode that turns it into a world" is not shown.** The title card and the end card both say
   "textbook, game and parent modes", but the pictures are textbook mode only: no game-mode beat and no
   parent printout appears in this 30 s cut. That is the take's largest on-screen gap and it is stated
   here rather than papered over.
4. **Nothing about grading is shown.** The Field Challenge question is unanswered ("Nothing selected
   yet"), and no grade, verdict, tick or feedback appears. The lesson rail does show a recorded count,
   "2 of 5 checks recorded", which is a stored number, not a demonstrated grade. The X copy does not
   claim grading, and it does not claim "evidence you can inspect": no evidence surface appears.
5. **The words are spoken, not captioned.** There is no per-beat caption band; the on-screen words are
   the interface's own, plus the title and end cards. The narration is a single track, 30.4 s against a
   30.4 s picture, first speech at 0.400417 s, and it is not optional: the narration is what carries the
   product sentence. The film is readable with sound off only at the level of its screens, and no muted
   comprehension read exists for this cut (`QC.md` §Muted comprehension: n=0 of 3), so §1 claims
   nothing about watching it without sound.

The loudness figure belongs in the same honesty list rather than in a footnote: the file measures
**-16.4 LUFS** against §9.3's -15.0 floor, a **FAIL by 1.4 LU**, pasted in `QC.md` §"Audio and
loudness". Posting it as-is puts a film that misses its own loudness criterion in the contest entry, and
the owner is the one who decides that.

If the owner wants the post to claim only what the take proves, the minimal edit is to drop "it writes
the whole course", "a tutor beside every page" and "a game mode" from the §1 string and open on the shown
surfaces — a goal card, an approved plan, one objective at a time, a typed check. That is a wording call
reserved to him under §13; this packet keeps the sanctioned sentence, states the gap, and cannot make the
choice for him.
