# QC — Coursebook launch film

File posted: `docs/launch/coursebook-launch-30s.mp4`

Measured 2026-11-16 against the blob at `origin/master` `8b502714`
(`8b5027144502163865304f00ff6c0a5dc9947d79`). The file was extracted with
`git show origin/master:docs/launch/coursebook-launch-30s.mp4`, and every number in the film-of-record
block below is pasted from a command run against that extraction: `ffprobe`, `ffmpeg -count_frames`,
`ffmpeg -af ebur128=peak=true`, `ffmpeg -vf blackframe` and `sha256sum`. Nothing in that block is copied
from another document and nothing is estimated. This file records measurement; it does not grant
approval.

**The film of record changed at `4c2a89b3`** ("Submission: point the packet and gate 13 at the 30 s cut
that actually gets posted", 2026-11-11 14:29 MST). This file had not followed: until this pass it named
the 42.4 s walkthrough as the posted file, and its 30 s section measured a 32.3 s blob that is not in the
tree. The walkthrough material below is now marked **superseded history**. Where history and the
film-of-record block disagree, the block governs.

## Film of record — the 30 s cut, `d46b46d1…1037`

| Property | Value | Source |
| --- | --- | --- |
| sha256 | `d46b46d17d0df2a3ccd986d2fe0ccc2ed398b564f31754020928742fa8ee1037` | `sha256sum` on the extraction |
| Duration | 30.400000 s, inside §9.2's 29.0-31.0 s cutdown window | `format=duration` |
| Frames | 912 = 30.4 x 30, CFR 30/1 | `-count_frames nb_read_frames` |
| Picture | 1920x1080, h264 High level 4.0, yuv420p | `stream=codec_name,width,height,profile,level` |
| Keyframes | 16, one every 2.000 s from 0.000 to 30.000 | `frame=key_frame,pts_time` |
| Container | `moov` before `mdat` (`+faststart`) | atom scan of the first 4 KiB |
| Audio | AAC LC, 48 kHz, stereo, stream duration 30.400000 s | `select_streams a` |
| Integrated loudness | **-16.4 LUFS**, LRA 4.6 LU, true peak -4.4 dBFS | `ebur128=peak=true` |
| Loudness verdict, §9.3 window -15.0 to -13.0 LUFS | **FAIL — 1.4 LU under the floor** | measured above |
| Size | 5,609,771 B (5.35 MiB) | `format=size` |
| End card | present, names Coursebook, the repo and MIT | frames 27.166-30.400 s |

Loudness note: this is the criterion the posted file actually misses. `VIDEO-PLAN.md` §9.3 requires
**-15.0 to -13.0 LUFS** integrated; the shipped 30 s cut measures **-16.4 LUFS**, 1.4 LU below the floor,
with true peak -4.4 dBFS (the -1.0 dBTP ceiling passes with 3.4 dB of headroom). No normalise pass is
applied here. Re-encoding is the owner's call, and doing it would replace this file and this sha — see
§"Decision".

The earlier record in this file reported "-15.1 / -15.12 LUFS" and "-14.8 LUFS" for other blobs. Those
figures belong to the v3 walkthrough and to the walkthrough as it now stands (-14.8 then, **-14.9** when
re-measured this pass, which is measurement noise on the same track), and "-15.4 LUFS" belonged to the
32.3 s first 30 s cut. None of them describes the file that ships; they are kept only in §"Superseded
history".

## Decision — recorded, not taken here

Both calls belong to DeseretSaint. This measurement pass records the state; it does not rule on either.

1. **Which file is posted.** The answer on record is the **30 s cut**. `4c2a89b3` moved
   `docs/SUBMISSION.md` gate 13 and the head of `docs/launch/POST.md` to
   `coursebook-launch-30s.mp4`; this pass finished that switch in `POST.md` §1 and §4 and in this file.
   The walkthrough was the film of record before that commit and is not now. If the owner reverses the
   decision, gate 13, `POST.md` §1 and this file move together — the packet must never again name two
   films at once.
2. **Whether -16.4 LUFS is accepted for posting.** Open. Two paths, both the owner's:
   - **Post at -16.4.** Then this FAIL stands in the record and gate 13 states it. Nothing else changes.
   - **One audio-only normalise pass** (`-c:v copy` plus a loudness filter on the audio stream), which
     leaves the picture bit-identical but produces a **new file, a new sha256 and a new measurement**.
     That is a new artifact, not an edit to this one, and it needs its own card; this pass does not run
     it and does not accept the current loudness on the owner's behalf.

## Files in the take

Four films sit at the root of `docs/launch/`, and `coursebook-launch-30s.mp4` is the one the post
attaches. Re-run against master for this pass:

```
$ git ls-tree -r --long origin/master -- docs/launch/ | grep -E 'launch/[^/]*\.mp4$'
100644 blob 714de92bccda5358ab11fe3de65025b491aabc7f 2099849  docs/launch/coursebook-demo-90s.mp4
100644 blob 10e0627df7ee0bea9ba97b35120318a62bfd8a2d 3029291  docs/launch/coursebook-demo-voiced.mp4
100644 blob f7e4f178f545facbb00b6268dc5d0c036593a474 5609771  docs/launch/coursebook-launch-30s.mp4
100644 blob 6fff18970cdb46917282b1da3261312ad3c0eddd 3025839  docs/launch/coursebook-walkthrough.mp4
```

- `coursebook-launch-30s.mp4` — **the posted cut and the film of record**: 30.400000 s, 5,609,771 B,
  sha256 `d46b46d1…1037`. Measured above.
- `coursebook-walkthrough.mp4` — the previous film of record: 42.400000 s, 3,025,839 B, sha256
  `9b6eed5e…e620`. In the tree, **not posted**, superseded as film of record at `4c2a89b3`. Measured
  this pass: -14.9 LUFS integrated, LRA 5.7 LU, true peak -4.2 dBFS; 1272 frames.
- `coursebook-demo-voiced.mp4` — 51.000000 s, video + AAC: an earlier narration mux over the
  pre-recapture picture. Superseded; not posted; loudness not measured this pass.
- `coursebook-demo-90s.mp4` — 51.000000 s, **video only, no audio stream**: the silent picture master.
  `VIDEO-PLAN.md` §9.1/§9.3 are **not applicable** to it rather than passed — there is no track to
  normalise and no loudness target to miss.

The earlier version of this section was a pasted `ls-tree` of a superseded tree (it listed the
walkthrough at 9,557,524 B and said "three films sit at the root"), and it closed by claiming the 30 s
cut "was never produced". Both statements were false against master: four films are at the root, and
`coursebook-launch-30s.mp4` has been in the tree since `080637eb` (2026-11-11 14:05 MST) and is the file
gate 13 now names.

## Probe

```
$ ffprobe -v error -show_entries stream=index,codec_type,codec_name,profile,level,width,height,pix_fmt,r_frame_rate,sample_rate,channels,duration -of default=noprint_wrappers=1 coursebook-launch-30s.mp4
index=0
codec_name=h264
profile=High
codec_type=video
width=1920
height=1080
pix_fmt=yuv420p
level=40
r_frame_rate=30/1
duration=30.400000
index=1
codec_name=aac
profile=LC
codec_type=audio
sample_rate=48000
channels=2
r_frame_rate=0/0
duration=30.400000

$ ffprobe -v error -show_entries format=duration,size,bit_rate -of default=noprint_wrappers=1 coursebook-launch-30s.mp4
duration=30.400000
size=5609771
bit_rate=1476255

$ ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 coursebook-launch-30s.mp4
912

$ ffprobe -v error -select_streams v:0 -show_entries frame=key_frame,pts_time -of csv=p=0 coursebook-launch-30s.mp4 | grep '^1'
1,0.000000
1,2.000000
1,4.000000
1,6.000000
1,8.000000
1,10.000000
1,12.000000
1,14.000000
1,16.000000
1,18.000000
1,20.000000
1,22.000000
1,24.000000
1,26.000000
1,28.000000
1,30.000000

$ sha256sum coursebook-launch-30s.mp4
d46b46d17d0df2a3ccd986d2fe0ccc2ed398b564f31754020928742fa8ee1037  coursebook-launch-30s.mp4
```

## Check table — VIDEO-PLAN.md §9 against the shipped blob

| Check | Required | Measured | Verdict |
| --- | --- | --- | --- |
| Duration, cutdown (§9.2) | 29.0-31.0 s | **30.400000 s** | PASS |
| Resolution (§9.1) | 1920x1080 | 1920x1080 | PASS |
| Frame rate (§9.1) | 30 fps CFR | `r_frame_rate=30/1`, 912 frames = 30.4 x 30 | PASS |
| Codec / pixel format (§9.1) | H.264, yuv420p | `h264`, `High`, level 4.0, `yuv420p` | PASS |
| Size (§9.2) | <= 512 MB | 5,609,771 B (5.35 MiB) | PASS |
| Audio stream (§9.1) | AAC 48 kHz | `aac` LC, 2 ch, 48000 Hz | PASS |
| Integrated loudness (§9.3) | -15.0 <= I <= -13.0 | **-16.4 LUFS** | **FAIL — 1.4 LU below the floor** |
| True peak (§9.3) | TP <= -1.0 dBTP | **-4.4 dBFS** | PASS |
| Black runs (§9.4) | no run > 3 frames | 3 black frames, 0.000-0.067 s, head only | PASS (at the limit) |
| sha256 recorded (§9.5) | one digest in this file | `d46b46d1…1037` | PASS |

The black-frame row is the exact count, not a scan summary:

```
$ ffmpeg -hide_banner -nostats -v info -i coursebook-launch-30s.mp4 -vf blackframe=amount=98:threshold=32 -an -f null -
[Parsed_blackframe_0 @ …] frame:0 pblack:100 pts:0 t:0.000000 type:I last_keyframe:0
[Parsed_blackframe_0 @ …] frame:1 pblack:100 pts:512 t:0.033333 type:P last_keyframe:0
[Parsed_blackframe_0 @ …] frame:2 pblack:98 pts:1024 t:0.066667 type:B last_keyframe:0
```

## Audio and loudness — the command and its output

```
$ ffmpeg -hide_banner -nostats -v info -i coursebook-launch-30s.mp4 -map 0:a -af ebur128=peak=true -f null -
  Integrated loudness:
    I:         -16.4 LUFS
    Threshold: -27.1 LUFS

  Loudness range:
    LRA:         4.6 LU
    Threshold: -37.2 LUFS
    LRA low:   -20.1 LUFS
    LRA high:  -15.5 LUFS

  True peak:
    Peak:       -4.4 dBFS
```

File sha256 for that run: `d46b46d17d0df2a3ccd986d2fe0ccc2ed398b564f31754020928742fa8ee1037`.

`VIDEO-PLAN.md` §9.3 requires -15.0 to -13.0 integrated, so **the loudness row fails by 1.4 LU**. This is
a real miss, not measurement noise: the same command on the same file twice returns the same -16.4, and
the walkthrough blob measured beside it returns -14.9, so the tool and the extraction are behaving. A
corrective `loudnorm=I=-14` pass would change the file's sha and is **not applied here**; re-encoding is
the owner's call and this file records what would ship.

**The narration starts at 0.400417 s and runs to the end of the picture.** The audio stream is the same
length as the video (30.400000 s), and `silencedetect` finds only sentence pauses after the opening
0.4 s:

```
$ ffmpeg -hide_banner -nostats -v info -i coursebook-launch-30s.mp4 -map 0:a \
    -af silencedetect=noise=-50dB:d=0.5 -f null -
silence_start: 3.754896
silence_end: 4.279333 | silence_duration: 0.524438
silence_start: 7.089542
silence_end: 7.632667 | silence_duration: 0.543125
silence_start: 11.369958
silence_end: 11.944646 | silence_duration: 0.574688
silence_start: 17.175104
silence_end: 17.713313 | silence_duration: 0.538208
silence_start: 23.381604
silence_end: 23.92 | silence_duration: 0.538396
silence_start: 27.571021
silence_end: 28.369125 | silence_duration: 0.798104
```

The film is **not mute** and it is **not music-led**: the audio is a single narration track, and the git
history records the bed being removed (`38da44a9`, "30 s cut v4: mascot removed, music bed removed,
narration only"). There is **no per-beat caption band**; the on-screen text is interface and card copy
(`6229cd31`, "30 s cut v6: no per-beat captions, title and end cards only").

## What the posted film shows

Read from frames extracted from the shipped blob, on a 1 s grid plus a scene-change scan
(`select='gt(scene,0.02)'`). Cut points are the scan's; beat times are approximate to the frame.

| Beat | From | To | Surface |
| --- | --- | --- | --- |
| title card | 0.000 | 2.333 | "Coursebook, learn anything." plus "textbook, game and parent modes" |
| Home | 2.333 | 6.367 | "Your field library", four course cards over the market-street scene, fox on the bench |
| goal | 6.367 | 10.433 | "What do you want to be able to do?", step 1 of 3, empty field, example starts |
| plan | 10.433 | 14.467 | "Plan approved · v3 plan …", four outline items, "Generate lessons" |
| course page and lesson | 14.467 | 22.567 | "Two ways of saying it" section list, then the Japanese affection and register lesson with a Field Challenge |
| Discover | 22.567 | 26.633 | "Discover", three packs on the shelf |
| end card | 26.633 | 30.400 | Coursebook, learn anything, repo URL, MIT |

Claim audit, against the frames rather than against intent:

| On-screen claim | Beat | Shown? | Evidence |
| --- | --- | --- | --- |
| "Coursebook, learn anything." / "textbook, game and parent modes" | title, end card | cards assert it | the pictures are textbook-mode screens: no game-mode beat and no parent printout appears in this cut |
| "Your field library." / "Choose a course or start a new expedition." | Home | yes | four course cards (Reading a pack before you install it, Japanese: affection and register, Parent measurement practice, Technical pack literacy) |
| "What do you want to be able to do?" / step 1 of 3 | goal | yes | the field is **empty**; the visible text is the placeholder "e.g. Hold a six-minute conversation in Spanish" |
| "Plan approved · v3 plan sha256:bbbb…" + four outline items + "Generate lessons" | plan | yes, as a state | one outline item reads "No check yet"; the screen's own footnote reads "No source is recorded for this plan." |
| "Two ways of saying it" + "Progress not recorded" | course page | yes | section list, five missions, one checkpoint |
| "Japanese affection and register" + Field Challenge multiple choice + "Nothing selected yet" | lesson | yes | the question is unanswered; no grade, verdict or feedback appears |
| "2 of 5 checks recorded" / "Hinted" | lesson | yes | lesson rail, as a recorded count |
| "Discover": three packs | Discover | yes | Japanese: the two ways to say it, Measuring at the kitchen table, What a pack manifest declares |
| repo URL + MIT | end card | yes | drawn card |

Five things the film does **not** show, which `POST.md` §4 therefore records as limits rather than as
demonstrated claims: a goal being typed and a course generated from it (the goal screen is empty and the
plan is a recorded state); a tutor rail (none appears); grading (the check is unanswered); a game-mode
beat; and a parent printout. The last two are named on the title and end cards and have no beat in this
cut.

## Muted comprehension

`VIDEO-PLAN.md` §9 item 6 asks three people (or three fresh agent sessions) to watch with sound off and
write one sentence; all three must say "turns a topic into a course" or equivalent.

**For this cut the answer is n=0 of 3.** No muted read exists against
`d46b46d17d0df2a3ccd986d2fe0ccc2ed398b564f31754020928742fa8ee1037`. The one read on record in earlier
drafts of this file was written against the silent master's frames, a different cut, and it named the
surfaces rather than the topic-to-course claim, so it fails §9 item 6 on its own terms. The row is
**unmeasured on this cut**, and the only read that exists belongs to another film and does not pass. It
is not presented as a pass and not evidence that the hook works.

## Frame provenance

Every content beat is a composed still, not a Desktop window capture — composition evidence (D-010), not
a live install. The still set is recorded in gate 13 of `docs/SUBMISSION.md`: six film3 plates at 1344
route width, device pixel ratio 2, from module `0cb478ec`, plus the owner's `home-full` render for the
library beat. The cut's own history confirms the last of it: `be8a59d0` is "30 s cut v7: owner Home render
as the library beat, X-grade encode", and the first version came from module `0d98d606` (`080637eb`).

What this pass re-derived is the file: duration, frames, streams, keyframe spacing, black runs, loudness
and sha, all pasted above. What it did **not** re-derive is the plate provenance: no capture was re-run,
and module `0cb478ec` is not a git object in this repository, so that hash is carried from the gate text
written in `4c2a89b3` and was not recomputed here. If the owner wants provenance attested as well as the
encode, that is a capture pass, not a docs pass.

## Superseded history — not the posted film

Nothing in this section certifies the post. It is kept because the packet's earlier claims are visible
here, with their real blob sizes, so a reviewer can see what changed and when.

### The walkthrough, as it stands in master (`9b6eed5e…e620`)

`docs/launch/coursebook-walkthrough.mp4`: 42.400000 s, 1272 frames, 1920x1080 h264 High, AAC LC 48 kHz
stereo with a 38.400000 s stream, 3,025,839 B, sha256
`9b6eed5eb6b17e17d6b0982b4f084e7571fe9090be3fe2e2c4b117486f17e620`. Measured this pass: **-14.9 LUFS**,
LRA 5.7 LU, true peak -4.2 dBFS — inside §9.3's window. It is not posted: gate 13 and `POST.md` name the
30 s cut. The earlier header of this file ("File posted: …coursebook-walkthrough.mp4") and its
film-of-record block were correct for the packet before `4c2a89b3` and are wrong after it.

### The v3 walkthrough (`69303767…e08fa`) — not in master's tree

51.000000 s, 1530 frames, 9,557,524 B, sha256
`693037676af045f2319278dbcd545f4bbbb6b928a0fe41be12fdacec151e08fa`, **-15.1 LUFS** measured this pass,
which failed §9.3 by 0.1 LU. It is blob `17b742c2`, present in master's history at `61786bd3` and
`53ffb7d1` but not in master's tree. That blob is why the old §"Files in the take" block listed the
walkthrough at 9,557,524 B: it was a pasted `ls-tree` of that tree, not of master.

### The first 30 s cut (`60049942…d880`) — not in master's tree

The old §"30 s launch cut (film3)" measured this blob: 32.300000 s, 4,870,583 B, sha256
`60049942b4251f29a82c5c541c25c8f09afbc93b280fb477bc867783df06d880`, **-15.4 LUFS** re-measured this
pass. It was blob `3bb70564` at `080637eb` and was replaced by four later versions
(`38da44a9`, `64e3d2e2`, `6229cd31`, `be8a59d0`), the last of which is the 30.4 s file that ships. The
section's numbers were therefore correct for a file that no longer exists and wrong for the one gate 13
names.

The walkthrough's per-beat provenance, beat-1 geometry findings, rejected-capture note and 51 s claim
audit that earlier drafts of this file carried were measurements of the v3/v5 walkthroughs. They are not
reproduced here because they describe frames the posted film does not contain; the full text is in the
history of this file at `25ce8c8f` and `451d41e1` if the owner wants it restored as a separate record.

## Reviewer sign-off

| Role | Name | Verdict | Date |
| --- | --- | --- | --- |
| Cut review | sentinel | pending — re-derive the shas, durations, frame counts and both `ebur128` figures | — |
| Owner approval before upload | DeseretSaint | pending | — |

The film is **not approved for upload** until DeseretSaint signs the row above. That is
`docs/SUBMISSION.md` §0 and gate 13; this file records the measurement, it does not grant the approval.
The **loudness FAIL of 1.4 LU** and the three product claims the cut does not demonstrate (generation,
tutor, game mode) are the owner's to accept or repair before posting.
