# Coursebook launch film — delegation plan

Status: approved for execution 2026-11-10. Owner: DeseretSaint. Manager: atlas.
Deadline that binds this: **2026-11-11 17:00 EST = 15:00 MST**. Publish target: **12:00 MST**, three hours of buffer.
This plan is written so a worker with no other context can execute a stage without asking a question. Every number, string, path and command below is the decision; there are no options left open.

## 1. What is being made, and why

A 75-second launch film for Coursebook, the Hermes Desktop plugin, that satisfies the hackathon's demo requirement and reads as an official product release rather than a screen recording.

The hackathon rows this film exists to satisfy, taken from the official `hackathon-judge` checklist (not from announcement prose):

- **HACK-02** — post a demo video on X and tag `@NousResearch`.
- **HACK-03** — strictly **under 90 seconds**, showing **the actual plugin working**.
- **HACK-04** — put the catalog-PR link and the X post link into `https://form.typeform.com/to/FwJLvOln`.
- **HACK-05** — 5PM EST, Nov 11 2026.

Two consequences are not negotiable. The pixels come from the real build, captured from the accepted commit; and the film must be legible muted, because X autoplays without sound.

Deliverables:

| File | Spec |
|---|---|
| `docs/launch/coursebook-launch-75s.mp4` | 1920x1080, 30 fps CFR, H.264 High@4.0, yuv420p, AAC LC 192k 48 kHz, ≤89.0 s, ≤512 MB, −14 LUFS / −1 dBTP |
| `docs/launch/coursebook-launch-30s.mp4` | same encode, 30 s cutdown, for quote posts |
| `docs/launch/POST.md` | the exact X copy, the tag, the alt text, the catalog-PR link and the form answers |
| `docs/launch/CREDITS.md` | music licence URL, font licences (OFL), every capture commit sha |
| `docs/launch/QC.md` | the measured ffprobe and loudnorm output, the muted-comprehension result, reviewer sign-off |

## 2. The one claim

**"Turn any topic into a course you can finish."**

It is the product's own promise, it is provable in one screen (a typed topic becomes a real course), and every beat below either shows it happening or is cut. The end card carries the product name, the repo URL and `MIT`.

Register: **crafted film**. Taste and pacing carry it, but the product is always the picture; there are no abstract montages, no stock footage, no fake UI.

## 3. Beat sheet — 75.0 s, hard cuts on the beat

Frame numbers at 30 fps are given so the editor never has to convert.

| # | In | Out | Frames | Picture | On-screen words | Motion | Sound |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 3.5 | 0–105 | Forest ground `#0d281b`, one line, no logo | **You don't need another course.** | Type rises 8 px over 300 ms, holds; cut on the downbeat | Low pad, single piano note on frame 0 |
| 2 | 3.5 | 7.5 | 105–225 | Three flat paper cards stack into frame, each with a line | **A textbook.** / **A flashcard app.** / **A tutor you can't afford.** | Cards land one per beat, 6 px settle | Paper taps, three of them |
| 3 | 7.5 | 11.0 | 225–330 | Same ground, one line, bigger | **One course. Finished.** | Hard cut, no motion | Music drops out, one beat of silence |
| 4 | 11.0 | 14.0 | 330–420 | Real Home v3, full bleed, cropped to the shelf and headline | **Coursebook.** then **Your field library.** | 100→106 % push over 3 s, ease `cubic-bezier(.2,.8,.2,1)` | Hit on frame 330, music returns |
| 5 | 14.0 | 24.0 | 420–720 | Real capture: Home → `Start a new course` → type the topic → plan screen with real sections | **Any topic becomes a real course.** (lower third, first 4 s) | Cursor moves in 12-frame steps; clicks land on beats; push to the plan | Click, keyboard, a single stamp when the plan lands |
| 6 | 24.0 | 38.0 | 720–1140 | Real Classroom: stepper, kana with furigana + romaji, check card, answer, feedback, evidence tray `2 of 5 checks recorded` | **Read it. Hear it. Answer it.** (first 4 s) | Slow push on the line; cut to the check card on the beat; hold the feedback 1.2 s | UI click, soft correct chime |
| 7 | 38.0 | 47.0 | 1140–1410 | Real tutor rail: select a line → ask → cited answer → citation walkthrough | **Ask the lesson. Get the page.** | 100→104 % push; highlight the selected text with a 2 px terracotta underline | Key click, page turn on the citation |
| 8 | 47.0 | 56.0 | 1410–1680 | Real Game mode: XP chip, level, challenge card, completion | **Practice that remembers where you are.** | Cut on the beat; XP chip counts 0→40 in 900 ms, no bounce | Level-up sting, short |
| 9 | 56.0 | 64.0 | 1680–1920 | Real Parent Studio: observation row, evidence, no game chrome | **And a parent sees the work, not the screen time.** | Lateral 40 px pan, hold | Soft paper slide |
| 10 | 64.0 | 70.0 | 1920–2100 | Real Discover grid, real packs, real covers | **Your next world is already on the shelf.** | Grid settles, 100→103 % push | Music builds |
| 11 | 70.0 | 75.0 | 2100–2250 | End card on forest ground: wordmark, repo URL, `MIT`, `Built with Hermes` | **Coursebook** / `github.com/DeseretSaint/hermes-classroom` / **MIT** / *Built with Hermes* | Type only, no motion | Final hit, tail 1.5 s |

Rules for the edit:
- Every cut is a hard cut on a beat. No dissolves except the 6-frame fade at 74.4–75.0 s.
- One message on screen at a time. If two lines are visible, one is a lower third and the other is product UI.
- The product is never redrawn. Every UI pixel is a capture, cropped, never reconstructed.
- No cursor halo, no click ripples, no zoom blur. Motion is push-in only, 3–6 % maximum.
- If a beat's screen is not v3 at picture lock, cut the beat and extend the previous one. Never substitute a v2 screen or a mock.

## 4. Copy deck — exact strings

Only these strings appear. Every one is either product copy or a statement the build can prove.

1. `You don't need another course.`
2. `A textbook.` / `A flashcard app.` / `A tutor you can't afford.`
3. `One course. Finished.`
4. `Coursebook.` / `Your field library.`
5. `Any topic becomes a real course.`
6. `Read it. Hear it. Answer it.`
7. `Ask the lesson. Get the page.`
8. `Practice that remembers where you are.`
9. `And a parent sees the work, not the screen time.`
10. `Your next world is already on the shelf.`
11. `Coursebook` / `github.com/DeseretSaint/hermes-classroom` / `MIT` / `Built with Hermes`

No user counts, no ratings, no "10× faster", no invented numbers. The only numerals are ones visible in the real UI.

## 5. Visual system

Type: **Fraunces** for display (OFL), **Source Sans 3** for UI and captions (OFL), **Noto Serif JP** for kana (OFL). No SF Pro, no Apple marks, no imitation of Apple assets.

Palette, from the v3 contract: ground `#0d281b` forest, canvas `#f5e3c8`, card stock `#f4ecd9`, ink `#1a1713`, terracotta `#b4532f`, gold `#a1741f`, rule `#cdb894`.

Type sizes on a 1920x1080 canvas: display 96–132 px (Fraunces 600, tracking −1.5 %), lower third 44 px Source Sans 3 600, caption 34 px, end-card URL 30 px. Measure caps: display lines at most 18 characters per line.

Safe area: keep all type inside 120 px margins. X's player chrome covers the bottom ~10 %; nothing essential below y = 972.

Captions: the on-screen type is the message, so there is no separate subtitle track. Any product UI that carries meaning must be legible at 100 % on a phone: crop to the region that matters, never show a whole 3440 px desktop shrunk.

## 6. Capture plan

Source of truth is a capture from the accepted commit, not a mock.

- Tool: `scripts/cp-capture.mjs` for stills (it stamps the plugin sha, fonts, route geometry and refuses contaminated frames); `gpu-screen-recorder` for motion clips if a still cannot carry the beat.
- Window: the live Hermes Desktop on profile `default`, CDP port 9411. If the Desktop relaunch gate (CB-017) is still closed at capture time, capture is blocked; use stamped stills from the cards' review packets and mark the take `still-only` in QC. Do not fake a live run.
- Resolution: capture at 2× device pixel ratio, 1920x1080 route width minimum, so a 3–6 % push never softens.
- Naming: `docs/launch/captures/<beat>-<state>-<width>-<theme>.png`, with the stamp JSON beside it.
- Required states, in beat order: `home-1049-light`, `create-topic-light`, `plan-sections-light`, `classroom-line-light`, `classroom-check-light`, `classroom-feedback-light`, `tutor-cited-light`, `game-challenge-light`, `game-complete-light`, `parent-observation-light`, `discover-grid-light`, `endcard` (graphic).
- Every still must show the real v3 scope: `[data-cb-v3-ready]` present, fonts loaded, images decoded. A frame without a stamp is not usable.
- Commit pin: the exact sha is written into `CREDITS.md` and `QC.md`; a later merge invalidates the take.

## 7. Composition plan

Engine: **Remotion**, because it renders deterministically on Linux, is free for an individual, and gives exact frame control.

- Project: `video/` at repo root, `npm i` once, `npx remotion render Hero75 out/coursebook-launch-75s.mp4`.
- Composition `Hero75`: 1920x1080, 30 fps, 2250 frames. `Hero30`: same, 900 frames.
- Structure: `video/src/Hero75.tsx` (sequence), `video/src/beats/B01Hook.tsx` … `B11End.tsx`, `video/src/components/Caption.tsx`, `Push.tsx` (scale-only), `Crop.tsx` (image placement math), `video/src/tokens.ts` (the palette and type above, imported from the same hexes as the contract).
- All motion is transform/opacity only, easing `cubic-bezier(.2,.8,.2,1)`, durations 120/240/300/600 ms — the product's own motion language.
- Images are imported as static assets; no network at render time.
- Fallback if Remotion cannot render on this machine within 45 minutes: `scripts/launch-ffmpeg.sh` using `zoompan` + `drawtext` over the same stills. Same timings, same copy; lower polish accepted, deadline protected.

## 8. Sound plan

- Music: one 75 s bed, 96 BPM, sparse piano/pad, build at 7.5 s, hit at 11.0 s, tail at 70 s. Source must be licensed for commercial use with a URL in `CREDITS.md`: a CC0 track (Pixabay/Free Music Archive) or a bespoke Suno generation on a paid plan. No track without a licence line.
- SFX: 10 cues, each −18 to −12 dBFS under the bed: paper tap ×3, click ×2, keyboard, stamp, correct chime, page turn, level sting.
- No voiceover in the hero cut. The type carries the message; a synthetic voice is the fastest way to make a launch film sound unofficial. A VO variant is optional after the hero ships.
- Mix: music −14 LUFS integrated at the end, true peak ≤ −1 dBTP, SFX peak ≤ −6 dBTP. Measure with `ffmpeg -af loudnorm=print_format=json -f null -` and paste the numbers into `QC.md`.

## 9. Acceptance — measured, not judged by vibe

Automated, in `scripts/launch-qc.sh`:
1. `ffprobe` → `codec_name=h264`, `profile=High`, `width=1920`, `height=1080`, `r_frame_rate=30/1`, `codec_name(a)=aac`, `sample_rate=48000`.
2. `duration` between 74.0 and 89.0 s for the hero, 29.0–31.0 s for the cutdown; file ≤ 512 MB.
3. `loudnorm` → I between −15.0 and −13.0 LUFS, TP ≤ −1.0 dBTP.
4. Black-frame scan → no run longer than 3 frames except the intended 6-frame fade.
5. `sha256sum` of the final mp4 recorded in `QC.md`.

Human, by the reviewer:
6. Muted comprehension: three people (or three fresh agent sessions) watch with sound off and write one sentence on what the product does. All three must say "turns a topic into a course" or equivalent. If not, the hook and beat 5 are wrong.
7. Claim audit: every on-screen string traced to product copy or a visible state; no invented numbers. A single untraceable claim fails the take.
8. Craft read: typography, spacing, contrast, cuts on beats; the film must not read as a tutorial.

## 10. Delegation — cards, owners, inputs, acceptance

| Card | Owner | Reviewer | Runtime | Input | Output | Done when |
|---|---|---|---|---|---|---|
| CP-033 (running) | harbor | quill | 120 m | this plan, SPEC-V3 | `docs/launch/brief.md`, `SCRIPT.md`, `ANIMATIC.md`, `scripts/cp-demo.mjs` | animatic plays end to end from real stills; script table matches this beat sheet |
| CP-033b Capture | harbor | sentinel | 60 m | accepted commit, CP-033 driver | 11 stamped stills + 4 clips in `docs/launch/captures/` | every still has a stamp whose sha equals the pin; no v2 frame |
| CP-033c Compose | harbor | quill | 150 m | CP-033b + animatic | `video/` project, `Hero75.mp4` picture lock | renders 2250 frames; every beat matches section 3; muted comprehension passes |
| CP-033d Sound + export | easel | quill | 90 m | CP-033c | final mp4 + `CREDITS.md` + `QC.md` | section 9 items 1–5 pass, licence URLs present |
| CP-033e Publish packet | atlas | — | 30 m | CP-033d + catalog PR link | `POST.md`, alt text, form answers | owner can post without editing a word |

Dependency order: CP-033 → CP-033b → CP-033c → CP-033d → CP-033e. CP-033b may start only when the screens it needs are on master; if the v3 wave slips, capture the beats that exist and mark the rest `cut` in `ANIMATIC.md`.

## 11. Schedule against the deadline

Assume picture lock at **P** (the moment GM-016 accepts the build). Publish target is 12:00 MST on Nov 11, so P must be ≤ 08:00 MST. If P is later, the cutdown ships first and the hero follows.

- P + 0:00 — capture pass (60 m), parallel with the sound bed search.
- P + 1:00 — compose to picture lock (150 m).
- P + 3:30 — sound and export (90 m).
- P + 5:00 — QC (30 m), then `POST.md` and the owner's X post.
- P + 6:00 — form submitted with the X link and the catalog PR link.

If P is 08:00, that lands at 14:00 — one hour of buffer, which is why the cutdown exists. If P slips past 10:00, ship the 30 s cutdown (beats 1, 3, 4, 5, 6, 11) and publish; do not miss the form.

## 12. Risks and the exact fallback

| Risk | Fallback |
|---|---|
| Remotion cannot render headless within 45 m | `scripts/launch-ffmpeg.sh` with zoompan/drawtext over the same stills |
| Desktop relaunch still closed, no live capture | stamped stills from review packets, `still-only` marked in QC; no live claim in the post |
| Tutor live walkthrough missing (GM-012b gap) | cut beat 7, extend beat 6 by 9 s; never stage a citation |
| A v3 screen not merged at picture lock | cut that beat, extend the previous one; the film gets shorter, never older |
| Music licence unclear | CC0 track with a URL, or a code-composed bed; no unlicensed track |
| Time below 4 h | 30 s cutdown, then publish |

## 13. What the owner decides, and when

Only three things are reserved, and each has a default if the owner is silent:
1. The claim wording — default **"Turn any topic into a course you can finish."**
2. Voiceover — default **none**.
3. Publishing — the X post and the form are the owner's; the packet is prepared, not sent.

Everything else in this plan is delegated and must not come back as a question.
