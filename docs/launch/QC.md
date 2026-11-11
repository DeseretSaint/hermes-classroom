# QC — Coursebook launch film

File posted: `docs/launch/coursebook-walkthrough.mp4`
Measured 2026-11-11 13:41 MST at `origin/master` `0dbb31a1`. The file was extracted with
`git show origin/master:docs/launch/coursebook-walkthrough.mp4` and every number below is pasted from
a command run against that extraction. Nothing in this file is copied from another document and nothing
is estimated. This file records measurement; it does not grant approval.

## Files in the take

Three films sit at the root of `docs/launch/`; `coursebook-walkthrough.mp4` is the one the post
attaches.

```
$ git ls-tree -r --long origin/master -- docs/launch/ | grep -E 'launch/[^/]*\.mp4$'
100644 blob 546989d57bd033adc8d757412e8130f1d1098904  3203434  docs/launch/coursebook-walkthrough.mp4
100644 blob 10e0627df7ee0bea9ba97b35120318a62bfd8a2d  3029291  docs/launch/coursebook-demo-voiced.mp4
100644 blob 714de92bccda5358ab11fe3de65025b491aabc7f  2099849  docs/launch/coursebook-demo-90s.mp4
```

- `coursebook-walkthrough.mp4` — the posted cut: 51.000000 s, narration track, burned-in type.
- `coursebook-demo-voiced.mp4` — the earlier narration mux over the pre-recapture picture. Superseded
  by the walkthrough; it is not posted and is not measured here.
- `coursebook-demo-90s.mp4` — the silent picture-only master. It is kept as the picture master; its
  loudness row is not applicable rather than passed, because it has no audio stream.

**Declared deviation:** `docs/launch/VIDEO-PLAN.md` §1 also lists a 30 s cutdown
(`coursebook-launch-30s.mp4`) for quote posts; it was never produced. This QC therefore covers one film,
and the only file that can be posted or linked is the walkthrough.

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
duration=43.600000

$ ffprobe -v error -show_entries format=duration,size,bit_rate -of default=noprint_wrappers=1 coursebook-walkthrough.mp4
duration=51.000000
size=3203434
bit_rate=502499

$ ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 coursebook-walkthrough.mp4
1530

$ sha256sum coursebook-walkthrough.mp4
9051c4328b587379ce237fddb1efe035aeaa6b99f26c83542498ae270d7d343a  coursebook-walkthrough.mp4
```

| Check | Required | Measured | Verdict |
| --- | --- | --- | --- |
| Duration under 90 s (`VIDEO-PLAN.md` §9.2) | < 90.0 s | **51.000000 s** | PASS |
| Resolution | 1920x1080 | 1920x1080 | PASS |
| Frame rate | 30 fps CFR | `r_frame_rate=30/1`, 1530 frames = 51.0 x 30 | PASS |
| Codec / pixel format | H.264, yuv420p | `h264`, `High`, `yuv420p` | PASS |
| Size | <= 512 MB | 3,203,434 B (3.06 MiB) | PASS |
| Audio stream (§9.1 expects AAC 48 kHz) | one AAC 48 kHz track | `aac` LC, 2 ch, 48000 Hz | PASS |
| Loudness -14 LUFS (§9.3) | -15.0 <= I <= -13.0 | **-14.90 LUFS** integrated | PASS |
| True peak (§9.3) | TP <= -1.0 dBTP | **-4.45 dBTP** | PASS |
| sha256 recorded (§9.5) | one digest in this file | `9051c432...d343a` | PASS |

## Audio and loudness — the commands and their output

```
$ ffmpeg -hide_banner -nostats -v info -i coursebook-walkthrough.mp4 -map 0:a \
    -af loudnorm=print_format=json -f null -
{
  "input_i" : "-14.90",
  "input_tp" : "-4.45",
  "input_lra" : "6.30",
  "input_thresh" : "-25.63",
  "output_i" : "-21.87",
  "output_tp" : "-8.23",
  "output_lra" : "4.90",
  "output_thresh" : "-32.49",
  "normalization_type" : "dynamic",
  "target_offset" : "-2.13"
}

$ ffmpeg -hide_banner -nostats -v info -i coursebook-walkthrough.mp4 -map 0:a -af ebur128=peak=true -f null -
  Integrated loudness:
    I:         -14.9 LUFS
    Threshold: -25.5 LUFS
  Loudness range:
    LRA:         6.7 LU
  True peak:
    Peak:       -4.5 dBFS
```

`input_i` and `input_tp` are the as-delivered measurements; the `output_*` fields are loudnorm's
prediction for its default target and are not claims about this file. The two integrated readings agree
at -14.9 LUFS; true peak is -4.45 dBTP from loudnorm and -4.5 dBFS from ebur128.

**The audio does not span the picture.** The AAC stream is **43.600000 s** against a **51.000000 s**
video stream, so the last 7.4 s carries no narration by construction. `silencedetect` locates the
boundaries:

```
$ ffmpeg -hide_banner -nostats -v info -i coursebook-walkthrough.mp4 -map 0:a \
    -af silencedetect=noise=-50dB:d=0.5 -f null -
silence_start: 0
silence_end: 3.641333 | silence_duration: 3.641333
silence_start: 43.019188
silence_end: 43.6 | silence_duration: 0.580812
```

Narration begins at 3.64 s — under the Home beat, after the 4 s title card — and ends at 43.02 s, before
the end card. This film is not mute: it is a 51 s cut with **optional narration plus burned-in type**,
and it reads with sound off because every beat carries its message on screen. The phrase "silent by
design" is not true of this file; it is true only of the picture-only master.

The silent master `coursebook-demo-90s.mp4` has zero audio streams, so `VIDEO-PLAN.md` §9.1/§9.3 are
**not applicable** to it — there is no track to normalise and no loudness target to miss.

## Frame provenance — per beat, against the shipped pin

The submission pins `7831d31d`, module `71d940ce`. The walkthrough is built so that the two beats the
Home pass changed are rendered from that pin, and the three it did not change come from captures one
Home pass earlier:

| Beat | Surface | Source | Module | Method |
| --- | --- | --- | --- | --- |
| 0 | title card | drawn in `ffmpeg` | n/a | `build-v2.sh` |
| 1 | Home / field library | `captures/freeze/captures-src/f-home.png` | `71d940ce`, the pin | module render, 1920x1080, seeded enrollments |
| 2 | Workshop / Discover | `captures/freeze/captures-src/f-workshop.png` | `71d940ce`, the pin | module render, 1920x1080 |
| 3 | Course page, plan awaits approval | `captures/freeze/captures-src/course-home-772-light.png` | `98400108` | real window capture |
| 4 | Lesson, objectives + Japanese cue | `captures/freeze/captures-src/04-lesson-top.png` | `98400108` | window capture, no stamp |
| 5 | Typed check | `captures/freeze/captures-src/07-answer.png` | `98400108` | window capture, no stamp |
| 6 | end card | drawn in `ffmpeg` | n/a | `build-v2.sh` |

The two module renders are **component renders of the shipped modules with seeded fixture data, not
screenshots of a running Desktop.** `captures/freeze/captures-src/manifest.json` records why: it was
rendered from checkout `fc6ec7b7` at module `71d940ce`, while the installed plugin on the capture host
was module `0d98d606`, which is stale. The end card says "rendered from the real plugin", which is true
of all five beats; no frame is a mockup.

The capture stamps in `CREDITS.md` name `tree.commit = 172b61aa` and module `98400108`. The one desktop
commit between that build and the submitted pin is:

```
$ git log --oneline 172b61aa..7831d31d -- desktop/
468f45c0 D-007 round 2: seat fox/clock on plank two, separate them, ink hero on a 0.60 scrim
```

`468f45c0` changes the Home screen only — `desktop/src/30-home.js`, Home-scoped rules in
`desktop/src/76-v3-scope.js`, and one `data-cb-home-cover` attribute. Beats 3-5 render code that commit
does not touch, so their pixels are true of the pin. Beat 1 is where the silent cut was one commit
behind; the walkthrough re-renders it from `71d940ce`, so **the posted film does not carry that delta.**
Beat 2 is re-rendered from the pin as well, though nothing in `468f45c0` changed it.

### Beat 1 geometry — the reproducible figures

The pre-fix Home in the silent cut overlapped the two scene boxes by 72 px: fox box left 1088 against
clock box right 1160. The shipped module still overlaps the two **boxes** horizontally by **50 px** —
`CB_HOME_SCENE.clock` is `left: 1042, size: 118` (right edge 1160) and `CB_HOME_SCENE.fox` is
`left: 1110, size: 208` — so "the two clear each other" is not a statement about box geometry.

The commit message and its code comment claim `11.4 px clear of the clock's opaque art`, from the
parenthetical `1099.5 -> 1153.9`. That parenthetical spans **54.4 px**, not 11.4, and the 11.4 px figure
cannot be derived from the diff, the constants, or any artifact in the repository. It is recorded here
as a **commit-message figure**, not a measurement: the clearance is between painted art, and no PNG of
the shipped Home exists in the tree to check it against.

What is verifiable is the seating. `ledge.top = 684` is the plank's top edge; the painted offsets are
4.9 px for the fox and 2.3 px for the clock, so the shipped boxes land the fox's feet on **684.1** and
the clock's base on **683.7**. In the filmed pre-fix Home the same offsets put the feet at **729.1** and
the base at **703.7**, i.e. 45.1 px and 19.7 px *below* the plank top: the group stood in front of the
plank, not on it. The walkthrough's Home is the fixed composition.

## Muted comprehension

`VIDEO-PLAN.md` §9 item 6 asks three people (or three fresh agent sessions) to watch with sound off and
write one sentence; **all three must say "turns a topic into a course" or equivalent.** Two things are
true of this row and both are stated:

1. **n=1.** Three reads were required and one was obtained. The two remaining reads were not run before
   this packet was cut.
2. **The one read does not meet the test as written.** It describes the surfaces without the
   topic-to-course claim:

   > A dark-green product film that shows an installed learning plugin: a library of courses, a shelf of
   > lesson packs to install, a course whose plan you approve before lessons start, a lesson that teaches
   > one objective at a time with a Japanese example, and a typed answer box that gets checked against the
   > lesson — ending on the name Coursebook, the repo and MIT.

   That sentence names the library, the packs, the plan, the lesson and the check. It does not say the
   product turns a topic into a course, and it could not: `POST.md` §4 concedes that no goal-to-course
   generation is shown in the film.

So the row is **PARTIAL for two independent reasons** — it is one sample of three, and the sample it has
misses §9 item 6's pass condition. It is not presented as a pass and it is not evidence that the hook
works. The read was taken against the picture-only master's frames; the posted walkthrough shares beats
0 and 3-6 with that master and differs at 1 and 2 (recapture from the pin) and in carrying narration.

What the beats say on screen, read from extracted frames of the posted file (times at 30 fps):

```
0. 0:00-0:04  "A course, not a chat." / "Coursebook for Hermes Desktop"
1. 0:04-0:12  "Your field library." / "Choose a course or start a new expedition."
2. 0:12-0:20  "Your next world is already on the shelf." / "Packs you can learn from, already on this device."
3. 0:20-0:28  "The plan is the spine." / "Read it, then approve it so lessons can start."
4. 0:28-0:36  "One objective at a time." / "Four objectives, one trail, one next step."
5. 0:36-0:44  "A typed check, graded against the objective." / "Graded against what the lesson asked, not the chat."
6. 0:44-0:51  "Coursebook" / "a local-first study plugin for Hermes Agent" / the repo URL / "MIT" / "rendered from the real plugin"
```

## Claim audit — what the frames actually show

Read against the frames, not against the intent:

| Claim | Where | Shown? | Evidence |
| --- | --- | --- | --- |
| "a course, not a chat" | beat 0 | yes | title card |
| library of courses | beat 1 | yes | four course cards on the shelf: Auto Repair Fundamentals, Japanese Cafe Basics, Astronomy, Sourdough |
| packs on the device | beat 2 | yes | Workshop / Discover, "Packs you can learn from, already on this device." |
| the plan is approved by the reader | beat 3 | yes | "The plan is waiting for you" + "Review and approve the plan" |
| one objective at a time | beat 4 | yes | four objective cards in a row, one lesson step expanded |
| Japanese cue with furigana and romaji | beat 4 | yes | "好きです、付き合ってください。" with reading `suki desu, tsukiatte kudasai` and a note under it |
| a typed check | beat 5 | yes | answer text in the box, "Check answer" |
| **"graded against the objective"** | beat 5 caption | **no** | the FILM-4R review scanned 36-44 s and found no grade; my frame at 39.0 s reproduces that state: answer typed, "Check answer" unpressed, no grade, score, tick, cross or feedback text |
| inspectable evidence | not in the film | **no** | no evidence panel appears; the word "Evidence" is a section heading on the course page listing other courses |
| "rendered from the real plugin" | end card | yes | beats 1-2 are component renders of module `71d940ce`; beats 3-5 are window captures of module `98400108` |

The caption on beat 5 and the phrase "evidence you can inspect" in the drafted X copy both outrun the
pixels. The copy was corrected in `POST.md` §1 to descriptors the frames carry. The film's own beat-5
caption is unchanged (re-rendering changes the sha and is the owner's call) and is recorded here as the
one on-screen overstatement in the take.

## Rejected captures — three PNGs exist in a ref, and one corroborates the beat-5 finding

`docs/launch/captures/freeze/captures-src/` holds only the five PNGs the film uses, and no superseded
frame is present in the working tree. But earlier drafts of this file went further and said
`05-lesson-body.png`, `06-check.png` and `08-feedback.png` "do not exist on disk or in any ref". **That
was wrong.** All three are tracked blobs at `docs/launch/captures/loop/`, added by commit `6b352174`,
reachable from the evidence refs `evidence/acceptance-172b61aa` and `origin/evidence/loop-172b61aa`:

```
$ git ls-tree -r --long 6b352174 -- docs/launch/captures/loop/
100644 blob 9e4e69b67da69bf9e49353f8a2c425aab0c3d276  326516  docs/launch/captures/loop/05-lesson-body.png
100644 blob 3f97fef8232c67f0692c8a6ab43fd05193404331  207621  docs/launch/captures/loop/06-check.png
100644 blob 95abcd4970ff1cf6836b9b3f347b4113d7d1c4f6  217238  docs/launch/captures/loop/08-feedback.png
```

They are not on disk in a clean checkout and they are not frames of this film. They are captures from
the loop evidence run on `172b61aa`, which is a different take.

Materially, `08-feedback.png` shows a **real verdict state** — "Not quite. does not match an accepted
answer", a "Try again" button, and "15 of 15 checks recorded". A grading capture of this build therefore
exists, which corroborates rather than contradicts the beat-5 finding above: the product can show a
grade, and the posted beat does not show one.

## Reviewer sign-off

| Role | Name | Verdict | Date |
| --- | --- | --- | --- |
| Cut review | sentinel | corrections applied in this commit | 2026-11-11 |
| Owner approval before upload | DeseretSaint | pending | — |

The film is **not approved for upload** until DeseretSaint signs the row above. That is
`docs/SUBMISSION.md` §0 and gate 13; this file records the measurement, it does not grant the approval.
