# QC — Coursebook launch film

File: `docs/launch/coursebook-demo-90s.mp4`
Measured 2026-11-11 13:26 MST on `origin/master` `7831d31d`. Every number below is pasted from a command
run against the file on disk. This file records measurement; it does not grant approval.

## Files in the take

```
$ ls -1 coursebook-*.mp4
coursebook-demo-90s.mp4
```

One file. `docs/launch/VIDEO-PLAN.md` §1 also lists a 30 s cutdown (`coursebook-launch-30s.mp4`) for quote
posts; it was never produced. **Declared deviation:** there is no cutdown, so this QC covers the hero film
only, and the only demo file that can be posted or linked is `coursebook-demo-90s.mp4`.

## Probe

```
$ ffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,pix_fmt,profile,level -of default=noprint_wrappers=1 coursebook-demo-90s.mp4
index=0
codec_name=h264
profile=High
codec_type=video
width=1920
height=1080
pix_fmt=yuv420p
level=50
r_frame_rate=30/1

$ ffprobe -v error -show_entries format=duration,size,bit_rate -of default=noprint_wrappers=1 coursebook-demo-90s.mp4
duration=51.000000
size=2099849
bit_rate=329388

$ ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 coursebook-demo-90s.mp4
1530

$ ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 coursebook-demo-90s.mp4 | wc -l
0

$ sha256sum coursebook-demo-90s.mp4
3d7a1d8126b58fd475931415cd2c5293c869ac395dc6eab9f1d4e0c741c77aa4  coursebook-demo-90s.mp4
```

| Check | Required | Measured | Verdict |
| --- | --- | --- | --- |
| Duration under 90 s (`VIDEO-PLAN.md` §9.2) | < 90.0 s | **51.000000 s** | PASS |
| Resolution | 1920x1080 | 1920x1080 | PASS |
| Frame rate | 30 fps CFR | `r_frame_rate=30/1`, 1530 frames = 51.0 x 30 | PASS |
| Codec / pixel format | H.264, yuv420p | `h264`, `High`, `yuv420p` | PASS |
| Size | <= 512 MB | 2,099,849 B (2.00 MiB) | PASS |
| Audio stream (§9.1 expects AAC 48 kHz) | a track to measure | zero audio streams | **DECLARED DEVIATION** |
| Loudness -14 LUFS / -1 dBTP (§9.3) | -15.0 <= I <= -13.0, TP <= -1.0 | not measurable: no audio | **DECLARED DEVIATION** |
| sha256 recorded (§9.5) | one digest in this file | `3d7a1d81...77aa4` | PASS |

## Loudness — the command, and its output

The planned loudnorm pass was run against the file as it stands:

```
$ ffmpeg -hide_banner -v error -i coursebook-demo-90s.mp4 -map 0:a -af loudnorm=print_format=json -f null -
Stream map '' matches no streams.
To ignore this, add a trailing '?' to the map.
Failed to set value '0:a' for option 'map': Invalid argument
Error parsing options for output file -.
Error opening output files: Invalid argument
exit=234
```

Without an explicit map, `loudnorm` is a no-op: ffmpeg reports `audio:0KiB` for the whole encode and
prints no loudness JSON, because the file has no audio stream for the filter to read. There is therefore
no LUFS or dBTP figure to report, and none is invented here. This is a declared deviation from
`VIDEO-PLAN.md` §9.1 and §9.3, not a pass: the plan assumed a composed track. `CREDITS.md` §Music gives
the reason (X autoplays muted; no licensed bed could be cleared and credited inside the window).

## Frame provenance — per beat, against the shipped pin

The capture stamps name `tree.commit = 172b61aa` and module `98400108`. The submission pins `7831d31d`,
whose `desktop/plugin.js` is module `71d940ce`:

```
$ git show 7831d31d:desktop/plugin.js | sha256sum
71d940ce0398220fe1d25d1ec39b1e4bdfbc2a1c257eb7eb42292c628ac4d4b8  -
$ git show 172b61aa:desktop/plugin.js | sha256sum
9840010845539c05e571566dbd65d4ceab03bc1119d01c0356f2ff29c6d9c395  -
```

One desktop commit sits between them:

```
$ git log --oneline 172b61aa..7831d31d -- desktop/
468f45c0 D-007 round 2: seat fox/clock on plank two, separate them, ink hero on a 0.60 scrim
```

| Beat | Screen | Capture commit (stamp) | Module | Shot ahead of the pin? | Changed by `468f45c0`? |
| --- | --- | --- | --- | --- | --- |
| 0 | title card, drawn in `ffmpeg` | n/a | n/a | n/a | no |
| 1 | Home | `172b61aa` | `98400108` | yes, one commit | **yes — Home scene only** |
| 2 | Workshop / Discover | `172b61aa` | `98400108` | yes, one commit | no |
| 3 | Course page (plan awaits approval) | `172b61aa` | `98400108` | yes, one commit | no |
| 4 | Lesson (objectives + Japanese cue) | no stamp | `98400108` by build parity | yes, one commit | no |
| 5 | Typed check | no stamp | `98400108` by build parity | yes, one commit | no |
| 6 | end card, drawn in `ffmpeg` | n/a | n/a | n/a | no |

Which screens changed between the two modules: **Home only**. `468f45c0` moves the fox box `left
1088 -> 1110`, `top 526 -> 481` and the clock `top 588 -> 568`, repaints the hero headline from
`--cb3-forest` (measured 4.45:1) to `--cb3-ink` on a 0.60 scrim instead of 0.55, and changes one
`data-cb-home-cover` attribute. Its CSS lives in `76-v3-scope.js` under Home-scoped selectors
(`[data-cb-home-scene-panel]`, `[data-cb-home-hero-band]`, `[data-cb-home-scene-clock]`,
`[data-cb-home-scene-fox]`). No other screen's rules change, so beats 2-5 are pixel-identical to what the
shipped module renders.

**Beat 1 is not.** It renders the pre-`468f45c0` Home, and the difference is visible, not theoretical: at
the pre-fix coordinates the fox box overlaps the clock box by 72 px (fox at 1088, clock right edge at
1160), so in the filmed frame the fox stands in front of the clock and in front of the plank rather than
seated on it. In the shipped module the two clear each other by 11.4 px and their feet land on the
shelf at y=684. That beat therefore shows a Home the repository no longer shipped, and I will not write
the sentence "no beat misrepresents the shipped build" over it. The rest of the packet stands; this one
beat is the owner's call: re-shoot Home on module `71d940ce` and re-encode (new sha, new measurement), or
accept the film with this delta declared here and in `CREDITS.md`.

## Muted comprehension

The film has no audio stream at all, so "muted" is the only way it can be watched. One reviewer (this
session) reviewed every beat as frames extracted from the file itself with sound off (`ffmpeg -ss` at
2, 7, 15, 23, 31, 39, 40, 42 and 43.5 s, covering all seven beats) and wrote one sentence:

> A dark-green product film that shows an installed learning plugin: a library of courses, a shelf of
> lesson packs to install, a course whose plan you approve before lessons start, a lesson that teaches
> one objective at a time with a Japanese example, and a typed answer box that gets checked against the
> lesson — ending on the name Coursebook, the repo and MIT.

That is one sentence of the answer §9 item 6 asks for. **§9 item 6 requires three independent viewers, and
three were not obtained: n=1.** The two remaining reads were not run before this packet was cut, so this
row is PARTIAL, not PASS, and it is not presented as the three-viewer result.

What the beats say on screen (read from extracted frames at 30 fps, times given):

```
0. 0:00-0:04  "A course, not a chat." / "Coursebook for Hermes Desktop"
1. 0:04-0:12  "Your field library." / "Pick a course, or start a new expedition."
2. 0:12-0:20  "Your next world is already on the shelf." / "Packs you can learn from, already on this device."
3. 0:20-0:28  "The plan is the spine." / "Read it, then approve it so lessons can start."
4. 0:28-0:36  "One objective at a time." / "Four objectives, one trail, one next step."
5. 0:36-0:44  "A typed check, graded against the objective." / "Graded against what the lesson asked, not the chat."
6. 0:44-0:51  "Coursebook" / "a local-first study plugin for Hermes Agent" / the repo URL / "MIT" / "captured from the real plugin - build c4fe2d63"
```

## Claim audit — what the frames actually show

Read against the frames, not against the intent:

| Claim | Where | Shown? | Evidence |
| --- | --- | --- | --- |
| "a course, not a chat" | beat 0 | yes | title card |
| library of courses | beat 1 | yes | three course cards under the hero |
| packs on the device | beat 2 | yes | Workshop / Discover, "Packs you can learn from, already on this device." |
| the plan is approved by the reader | beat 3 | yes | "The plan is waiting for you" + "Review and approve the plan" |
| one objective at a time | beat 4 | yes | four objective cards in a row, one lesson step expanded |
| Japanese cue with furigana and romaji | beat 4 | yes | "好きです、付き合ってください。" with reading `suki desu, tsukiatte kudasai` and a note under it |
| a typed check | beat 5 | yes | answer text in the box, "Check answer" |
| **"graded against the objective"** | beat 5 caption | **no** | frames at 39.0, 40.0, 42.0 and 43.5 s all show the same state: answer typed, "Check answer" unpressed, no grade, score or feedback visible anywhere in the take |
| inspectable evidence | not in the film | **no** | no evidence panel appears; the word "Evidence" is a section heading on the course page listing other courses |
| build `c4fe2d63` | end card | yes | matches module `98400108`, which is what the pixels render |

The caption on beat 5 and the phrase "evidence you can inspect" in the drafted X copy both outrun the
pixels. The copy was corrected in `POST.md` §1 to descriptors the frames carry. The film's own beat-5
caption is unchanged (re-rendering changes the sha and is the owner's call) and is recorded here as the
one on-screen overstatement in the take.

## Rejected captures

No rejected-capture files were retained: `docs/launch/captures/freeze/captures-src/` holds only the five
PNGs the film uses, and no superseded frame is tracked in this repository. Earlier drafts of this file
named `05-lesson-body.png`, `06-check.png` and `08-feedback.png` as rejected; those files do not exist on
disk or in any ref, so that paragraph has been removed rather than repeated. What the take does contain is
the beat-5 caption issue in the table above, which is a finding, not a discarded frame.

## Reviewer sign-off

| Role | Name | Verdict | Date |
| --- | --- | --- | --- |
| Cut review | sentinel | pending | — |
| Owner approval before upload | DeseretSaint | pending | — |

The film is **not approved for upload** until DeseretSaint signs the row above. That is
`docs/SUBMISSION.md` §0 and gate 13; this file records the measurement, it does not grant the approval.
