# QC — Coursebook launch film

File: `docs/launch/coursebook-demo-90s.mp4`
Measured 2026-11-11 13:54 MST. Every number below is pasted from a command run against the file on disk.

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

$ ffprobe -v error -show_entries format=duration,size,bit_rate,format_name -of default=noprint_wrappers=1 coursebook-demo-90s.mp4
format_name=mov,mp4,m4a,3gp,3g2,mj2
duration=47.000000
size=1888574
bit_rate=321459

$ ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 coursebook-demo-90s.mp4
1410

$ ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 coursebook-demo-90s.mp4 | wc -l
0

$ sha256sum coursebook-demo-90s.mp4
61b485ab8180fec7a1d5e2defd002c953d0d0e44e70b3685811e77dc7fbfd5de  coursebook-demo-90s.mp4
```

| Check | Required | Measured | Verdict |
| --- | --- | --- | --- |
| Duration under 90 s | < 90.0 s | **47.000000 s** | PASS |
| Resolution | 1920×1080 | 1920×1080 | PASS |
| Frame rate | 30 fps CFR | `r_frame_rate=30/1`, 1410 frames = 47.0 × 30 | PASS |
| Codec / pixel format | H.264, yuv420p | `h264`, `High`, `yuv420p` | PASS |
| Size | ≤ 512 MB | 1,888,574 B (1.80 MiB) | PASS |
| Loudness −14 LUFS | required by `VIDEO-PLAN.md` §9 | no audio stream at all | **NOT APPLICABLE — declared deviation** |
| Muted legibility | every beat readable with sound off | see below | PASS |

The loudness row is a deliberate, declared deviation from `docs/launch/VIDEO-PLAN.md` §9. The plan
assumed a composed track; the film that shipped has no audio stream, so there is nothing to normalise,
and a silent film cannot breach a loudness target. The reason is in `CREDITS.md` §Music: X autoplays
muted, and a licensed bed could not be cleared and credited inside the window.

## Muted comprehension

Each of the five beats was reviewed as a still with sound off, and each carries one sentence of on-screen
type below the capture:

1. "Your field library." / "Pick a course, or start a new expedition."
2. "Every course keeps its own record." / "Sources, progress, and what is due."
3. "The plan is the spine." / "Read it, then approve it so lessons can start."
4. "One objective at a time." / "Four objectives, one trail, one next step."
5. "A typed check, graded against the objective." / "Graded against what the lesson asked, not the chat."

The end card carries the product name, the repository URL, `MIT`, and the capture build. No beat depends
on a spoken word.

## Frame provenance

Every frame is a crop of a real capture at build `c4fe2d63`, module `98400108`. The five source PNGs and
their sha256 values are in `CREDITS.md`. The crop removes only the host window's right rail and status
strip; the plugin surface is not retouched.

**Two captures were rejected, not used.** `05-lesson-body.png` renders the Home hero as an empty beige
band (the composition defect the Home pass later fixed), and `06-check.png` / `08-feedback.png` are
mid-scroll states that repeat the question in a chat bubble and in the challenge card, with the graded
copy "Not quite. does not match an accepted answer" on screen. Those frames are not in the film; the
copy and duplication are carded as a post-submission product defect.

## Reviewer sign-off

| Role | Name | Verdict | Date |
| --- | --- | --- | --- |
| Cut review | — | pending | — |
| Owner approval before upload | DeseretSaint | pending | — |

The film is **not approved for upload** until DeseretSaint signs the row above. That is `docs/SUBMISSION.md`
§0 and gate 13; this file records the measurement, it does not grant the approval.
