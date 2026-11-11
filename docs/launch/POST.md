# Film publish packet — the X post, the form answers, the licence and the QC

Prepared 2026-11-11 13:50 MST by the release director for the contest that closes at
**15:00 MST / 17:00 EST**. Nothing in this file has been posted or submitted. The post and the form are
DeseretSaint's actions under `docs/SUBMISSION.md` §0.

The film is `docs/launch/coursebook-demo-90s.mp4` — **47.0 s**, measured, not estimated
(`QC.md` carries the command output). It is silent by design; every beat carries its message as
on-screen type so the file reads with sound off, which is how X autoplays.

## 1. The X post — 258 characters, one URL

```
Coursebook: turn a topic into a course you can finish. A Hermes Desktop plugin — one objective at a
time, typed checks, evidence you can inspect. MIT. 47 s demo, no sound needed. Built with
@NousResearch Hermes Agent.
github.com/DeseretSaint/hermes-classroom
```

- Length: **258 characters** counted on the string above (X counts the bare URL as 23 regardless of its
  rendered length, so the effective count is lower).
- Tags `@NousResearch`. Links the public repository. Makes no efficacy, mastery, benchmark, COPPA or
  child-safety claim.
- Attach `coursebook-demo-90s.mp4` to the post.

**Alt text** (paste into X's media description):

> A 47-second silent product film on a dark green ground. Five real Coursebook screens appear one at a
> time with a sentence under each: the Home library with an illustrated course shelf and a fox on a
> plank; the Courses list with per-course progress; a course page whose plan waits for approval; a
> lesson with four objectives down the left and a Japanese register cue with furigana and romaji; and a
> typed check with the answer filled in. The end card reads Coursebook, a local-first study plugin for
> Hermes Agent, github.com/DeseretSaint/hermes-classroom, MIT.

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
lives.

## 3. Order of operations

1. Post §1 on X with the film attached; copy the post URL.
2. Paste that URL and the catalog PR URL into the form with §2's answers.
3. Screenshot or copy the confirmation and add it to `docs/SUBMISSION.md` gate 15.

If X rejects the upload for size, the file is 1.94 MB — well under any limit; re-encode is not needed.

## 4. What the film does not claim

The frames are captures of a real installed plugin, at build `c4fe2d63`, module `98400108`. The release
pin moves with Gate 8c, and the delta is UI copy and composition, not the surfaces shown. The film does
not show course generation from a typed goal, because that path was still under repair at the freeze
(`docs/ACCEPTANCE-RUN.md`); the post therefore says what the product is, not what the take proves about
generation.
