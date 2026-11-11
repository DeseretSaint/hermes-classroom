# QC — Coursebook launch film

File posted: `docs/launch/coursebook-walkthrough.mp4`
Measured 2026-11-11 13:55 MST at `origin/master` `61786bd3`. The file was extracted with
`git show origin/master:docs/launch/coursebook-walkthrough.mp4` and every number below is pasted from a
command run against that extraction. Nothing here is copied from another document and nothing is
estimated. This file records measurement; it does not grant approval.

The cut on master has changed three times in the last twenty minutes (`0dbb31a1` and `468d2ce9` carry
earlier renders of this same path). This measurement describes the blob at `61786bd3`, sha
`69303767…e08fa`. If the post attaches a different digest, this QC does not cover it.

### Drift since this measurement — the gate certifies one digest, not a path

`origin/master` moved again after this measurement. `53ffb7d1` ("Walkthrough v5: slide transitions,
blurred stills behind the cards, plain-language captions") replaces the film with a **42.400000 s**
cut: 3,025,052 B, sha256
`0775f33f0df59aa3d6c2e7c9b144045fbaa62e40d5c77db09777c83254376fda`, AAC stream 38.400000 s,
integrated −15.1 LUFS (ebur128). That is a **different duration** as well as a different digest, so
every "51.0 s" figure in this packet and in `POST.md` describes the cut measured here, not v5.

This QC and gate 13 therefore certify **sha `69303767…e08fa` and nothing else**. If the file attached to
the post hashes differently — v5 included — gate 13 is uncovered until someone measures that blob and
re-issues the row. That is the whole point of naming a digest: a path can be overwritten, a sha cannot.
The film was still being re-cut when this packet was committed, and the owner has not ruled on v5.

## Files in the take

Three films sit at the root of `docs/launch/`; `coursebook-walkthrough.mp4` is the one the post
attaches.

```
$ git ls-tree -r --long origin/master -- docs/launch/ | grep -E 'launch/[^/]*\.mp4$'
100644 blob 17b742c26e33e74e3dcd895578bfd0db2f9be8e9  9557524  docs/launch/coursebook-walkthrough.mp4
100644 blob 10e0627df7ee0bea9ba97b35120318a62bfd8a2d  3029291  docs/launch/coursebook-demo-voiced.mp4
100644 blob 714de92bccda5358ab11fe3de65025b491aabc7f  2099849  docs/launch/coursebook-demo-90s.mp4
```

- `coursebook-walkthrough.mp4` — the posted cut: 51.000000 s, narration track, burned-in type.
- `coursebook-demo-voiced.mp4` — an earlier narration mux over the pre-recapture picture. Superseded;
  not posted, not measured here.
- `coursebook-demo-90s.mp4` — the silent picture-only master. Kept as the picture master; its loudness
  row is not applicable rather than passed, because it has no audio stream.

**Declared deviation:** `docs/launch/VIDEO-PLAN.md` §1 lists a 30 s cutdown
(`coursebook-launch-30s.mp4`) for quote posts; it was never produced. This QC covers one film, and the
only file that can be posted or linked is the walkthrough.

## Probe

```
$ ffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,pix_fmt,profile,level,sample_rate,channels,duration -of default=noprint_wrappers=1 coursebook-walkthrough.mp4
index=0
codec_name=h264
profile=High
codec_type=video
width=1920
height=1080
pix_fmt=yuv420p
level=50
r_frame_rate=30/1
duration=51.000000
index=1
codec_name=aac
profile=LC
codec_type=audio
sample_rate=48000
channels=2
r_frame_rate=0/0
duration=50.700000

$ ffprobe -v error -show_entries format=duration,size,bit_rate -of default=noprint_wrappers=1 coursebook-walkthrough.mp4
duration=51.000000
size=9557524
bit_rate=1499219

$ ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 coursebook-walkthrough.mp4
1530

$ sha256sum coursebook-walkthrough.mp4
693037676af045f2319278dbcd545f4bbbb6b928a0fe41be12fdacec151e08fa  coursebook-walkthrough.mp4
```

| Check | Required | Measured | Verdict |
| --- | --- | --- | --- |
| Duration under 90 s (`VIDEO-PLAN.md` §9.2) | < 90.0 s | **51.000000 s** | PASS |
| Resolution | 1920x1080 | 1920x1080 | PASS |
| Frame rate | 30 fps CFR | `r_frame_rate=30/1`, 1530 frames = 51.0 x 30 | PASS |
| Codec / pixel format | H.264, yuv420p | `h264`, `High`, `yuv420p` | PASS |
| Size | <= 512 MB | 9,557,524 B (9.11 MiB) | PASS |
| Audio stream (§9.1 expects AAC 48 kHz) | one AAC 48 kHz track | `aac` LC, 2 ch, 48000 Hz | PASS |
| Loudness (§9.3) | -15.0 <= I <= -13.0 | **-15.12 LUFS** integrated | **FAIL — 0.12 LU below the band** |
| True peak (§9.3) | TP <= -1.0 dBTP | **-4.48 dBTP** | PASS |
| sha256 recorded (§9.5) | one digest in this file | `69303767…e08fa` | PASS |

## Audio and loudness — the commands and their output

```
$ ffmpeg -hide_banner -nostats -v info -i coursebook-walkthrough.mp4 -map 0:a \
    -af loudnorm=print_format=json -f null -
{
  "input_i" : "-15.12",
  "input_tp" : "-4.48",
  "input_lra" : "5.70",
  "input_thresh" : "-25.84",
  "output_i" : "-22.52",
  "output_tp" : "-5.81",
  "output_lra" : "5.10",
  "output_thresh" : "-33.20",
  "normalization_type" : "dynamic",
  "target_offset" : "-1.48"
}

$ ffmpeg -hide_banner -nostats -v info -i coursebook-walkthrough.mp4 -map 0:a -af ebur128=peak=true -f null -
  Integrated loudness:
    I:         -15.1 LUFS
    Threshold: -25.8 LUFS
  Loudness range:
    LRA:         6.0 LU
  True peak:
    Peak:       -4.5 dBFS
```

`input_i` and `input_tp` are the delivered measurements; the `output_*` fields are loudnorm's prediction
for its default target and are not claims about this file. Both tools agree: **-15.12 / -15.1 LUFS**.
`VIDEO-PLAN.md` §9.3 requires -15.0 to -13.0 integrated, so **the loudness row fails, marginally** —
0.12 LU outside the floor. The true peak passes with 3.5 dB of headroom. A corrective
`loudnorm=I=-14` pass would change the file's sha and is **not** applied here: re-encoding is the
owner's call and this file records what would ship.

**The audio starts late and ends before the picture.** The AAC stream is **50.700000 s** against the
**51.000000 s** video, and `silencedetect` puts the first speech at 3.36 s:

```
$ ffmpeg -hide_banner -nostats -v info -i coursebook-walkthrough.mp4 -map 0:a \
    -af silencedetect=noise=-50dB:d=0.5 -f null -
silence_start: 0
silence_end: 3.356937 | silence_duration: 3.356937
silence_start: 8.354854
silence_end: 8.953625 | silence_duration: 0.598771
silence_start: 29.750896
silence_end: 30.278854 | silence_duration: 0.527958
silence_start: 35.751896
silence_end: 36.353167 | silence_duration: 0.601271
silence_start: 45.697437
silence_end: 46.281625 | silence_duration: 0.584187
```

The gaps are natural pauses between sentences; the track begins under the Home card, after the 3.5 s
title card. The film is **not mute**: it is a 51 s cut with optional narration plus burned-in type, and
it is legible with sound off because every beat is written on screen. "Silent by design" is true only
of the picture-only master, not of the posted file.

The silent master `coursebook-demo-90s.mp4` has zero audio streams, so `VIDEO-PLAN.md` §9.1/§9.3 are
**not applicable** to it — there is no track to normalise and no loudness target to miss.

## Frame provenance — per beat, against the shipped pin

The submission pins `7831d31d`, module `71d940ce`. The Home-side beats are rendered from that pin; the
three screens the Home pass did not touch come from captures one Home pass earlier.

| Beat | Time | Surface | Source | Module | Method |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.0-3.5 | title card | drawn in `ffmpeg` | n/a | `build-v4.sh` |
| 1 | 3.5-10.5 | Home / field library | `captures-src/f-home.png` | `71d940ce`, the pin | module render, seeded enrollments |
| 2 | 10.5-17.5 | Workshop / Discover | `captures-src/f-workshop.png` | `71d940ce`, the pin | module render |
| 3 | 17.5-24.5 | Course page, plan awaits approval | `captures-src/course-home-772-light.png` | `98400108` | real window capture |
| 4 | 24.5-31.5 | Lesson | `captures-src/04-lesson-top.png` | `98400108` | window capture, no stamp |
| 5 | 31.5-38.0 | Typed check | `captures-src/07-answer.png` | `98400108` | window capture, no stamp |
| 6 | 38.0-44.0 | Parent mode printout | `captures-src/parent-guide.png` | product printout | an A4 parent guide the plugin generates |
| 7 | 44.0-51.0 | end card | drawn in `ffmpeg` | n/a | `build-v4.sh` |

The two module renders are **component renders of the shipped modules with seeded fixture data, not
screenshots of a running Desktop.** `captures/freeze/captures-src/manifest.json` records why: they were
rendered from checkout `fc6ec7b7` at module `71d940ce`, while the plugin installed on the capture host
was stale module `0d98d606`. The end card's "rendered from the real plugin" is true of all six content
beats under that definition; no frame is a mockup.

The capture stamps in `CREDITS.md` name `tree.commit = 172b61aa` and module `98400108`. The one desktop
commit between that build and the submitted pin is:

```
$ git log --oneline 172b61aa..7831d31d -- desktop/
468f45c0 D-007 round 2: seat fox/clock on plank two, separate them, ink hero on a 0.60 scrim
```

`468f45c0` changes the Home screen only — `desktop/src/30-home.js`, Home-scoped rules in
`desktop/src/76-v3-scope.js`, and one `data-cb-home-cover` attribute. Beats 3-5 render code that commit
does not touch, so their pixels are true of the pin. Beats 1-2 are rendered from the pin itself, so the
posted film does not carry the Home seating delta that the silent cut carried.

### Beat 1 geometry — the reproducible figures

The pre-fix Home in the silent cut overlapped the two scene boxes by 72 px: fox box left 1088 against
clock box right 1160. The shipped module still overlaps the two **boxes** horizontally by **50 px** —
`CB_HOME_SCENE.clock` is `left: 1042, size: 118` (right edge 1160) and `CB_HOME_SCENE.fox` is
`left: 1110, size: 208` — so "the two clear each other" is not a statement about box geometry.

The commit message and its code comment claim `11.4 px clear of the clock's opaque art`, from the
parenthetical `1099.5 -> 1153.9`. That parenthetical spans **54.4 px**, not 11.4, and the figure cannot
be derived from the diff, the constants, or any artifact in the repository. It is recorded here as a
**commit-message figure**, not a measurement: the clearance is between painted art, and no PNG of the
shipped Home exists in the tree to check it against.

What is verifiable is the seating. `ledge.top = 684` is the plank's top edge; the painted offsets are
4.9 px for the fox and 2.3 px for the clock, so the shipped boxes land the fox's feet on **684.1** and
the clock's base on **683.7**. In the filmed pre-fix Home the same offsets put the feet at **729.1** and
the base at **703.7**, i.e. 45.1 px and 19.7 px *below* the plank top: the group stood in front of the
plank, not on it. In the posted film the fox stands ahead of the clock at the shelf's front edge, which
is what the alt text now says.

## Muted comprehension

`VIDEO-PLAN.md` §9 item 6 asks three people (or three fresh agent sessions) to watch with sound off and
write one sentence; **all three must say "turns a topic into a course" or equivalent.** Three things are
true of this row and all are stated:

1. **The one read on record is against a different cut.** The sentence below was written against the
   silent master's frames, before the recapture and before the v3 re-edit. Against the posted
   `61786bd3` blob there is **no muted read at all: n=0 of 3.**
2. **That one read misses the criterion as written.** It names the surfaces, not the topic-to-course
   claim:

   > A dark-green product film that shows an installed learning plugin: a library of courses, a shelf of
   > lesson packs to install, a course whose plan you approve before lessons start, a lesson that teaches
   > one objective at a time with a Japanese example, and a typed answer box that gets checked against the
   > lesson — ending on the name Coursebook, the repo and MIT.

3. **The posted cut now says the claim itself.** Beat 2's on-screen line is "Turn any topic into a
   course." A future muted read may therefore return the right sentence because the card tells the
   viewer to say it, not because the film showed generation. `POST.md` §4 records that no generation is
   shown; that tension is the take's, and it is not resolved by a favourable reader.

So the row is **PARTIAL**: n=0 of 3 on this cut, and the only read in existence was taken on another cut
and failed §9 item 6. It is not presented as a pass and it is not evidence that the hook works.

## Claim audit — what the frames actually show

Read against frames extracted from the posted file, not against intent:

| On-screen claim | Beat | Shown? | Evidence |
| --- | --- | --- | --- |
| "Coursebook, learn anything." / "textbook, game and parent modes" | 0 | card asserts it | title card; the film shows a lesson and a parent printout, **no game-mode beat** |
| "Your field library." / "Every course keeps its own sources and progress." | 1 | partly | four course cards (Auto Repair Fundamentals, Japanese Cafe Basics, Astronomy, Sourdough); no sources or progress indicator is legible in the crop |
| **"Turn any topic into a course." / "Generated inside Hermes, with real research behind it."** | 2 | **no** | the frame is the Discover pack shelf with three ready packs; no goal entry, no generation, no research surface |
| "A plan before a lesson." / "Read it, approve it, and the course begins." | 3 | yes | "The plan is waiting for you" + "Review and approve the plan" |
| **"A tutor beside the lesson." / "Ask anything; the answer cites the page you are reading."** | 4 | **no** | the frame is the lesson document; no tutor rail, no question box, no citation appears |
| "A check you have to type." | 5 | yes | answer text in the field |
| "Graded against what the lesson taught, not the chat." | 5 | **no** | "Check answer" is unpressed; no grade, score, tick, cross or feedback appears at 35 s |
| "Parent mode." / "Printables and activities, ready to hand over." | 6 | yes | an A4 parent guide is the frame |
| "export a course as a pack; a storefront is on the way" | 7 | not a frame claim | future tense on the card; export/import is proven by gate 4, no storefront exists |
| "rendered from the real plugin" | 7 | yes | beats 1-2 are module renders; 3-5 window captures; 6 a product printout |

Two captions outrun their pictures: **beat 2's topic-to-course generation** and **beat 4's citing
tutor**. Beat 5's second line states a grading behaviour the frame does not display. All three are
recorded here as the take's on-screen overstatements; changing them means a new render and a new sha,
which is the owner's call and is not done in this packet.

## Rejected captures — three PNGs exist in a ref, and one corroborates the beat-5 finding

`docs/launch/captures/freeze/captures-src/` holds only the PNGs the film uses, and no superseded frame is
present in the working tree. But earlier drafts of this file said `05-lesson-body.png`, `06-check.png`
and `08-feedback.png` "do not exist on disk or in any ref". **That was wrong.** All three are tracked
blobs at `docs/launch/captures/loop/`, added by commit `6b352174`, reachable from the evidence refs
`evidence/acceptance-172b61aa` and `origin/evidence/loop-172b61aa`:

```
$ git ls-tree -r --long 6b352174 -- docs/launch/captures/loop/
100644 blob 9e4e69b67da69bf9e49353f8a2c425aab0c3d276  326516  docs/launch/captures/loop/05-lesson-body.png
100644 blob 3f97fef8232c67f0692c8a6ab43fd05193404331  207621  docs/launch/captures/loop/06-check.png
100644 blob 95abcd4970ff1cf6836b9b3f347b4113d7d1c4f6  217238  docs/launch/captures/loop/08-feedback.png
```

They are not on disk in a clean checkout and they are not frames of this film. They are captures from
the loop evidence run on `172b61aa`, which is a different take.

Materially, `08-feedback.png` shows a **real verdict state** — "Not quite. does not match an accepted
answer", a "Try again" button, and "15 of 15 checks recorded". A grading capture of this build exists,
which corroborates rather than contradicts the beat-5 finding above: the product can show a grade, and
the posted beat does not show one.

## Reviewer sign-off

| Role | Name | Verdict | Date |
| --- | --- | --- | --- |
| Cut review | sentinel | corrections applied; v3 cut not yet reviewed | 2026-11-11 |
| Owner approval before upload | DeseretSaint | pending | — |

The film is **not approved for upload** until DeseretSaint signs the row above. That is
`docs/SUBMISSION.md` §0 and gate 13; this file records the measurement, it does not grant the approval.
The loudness FAIL and the two caption overstatements are the owner's to accept or repair before posting.
