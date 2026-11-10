# Launch film — audio mix notes (CP-036)

Input to CP-033d. The bed and the ten SFX are picture-locked to `docs/launch/VIDEO-PLAN.md` §3, so the
sound stage is a mix, not a search. Everything below is measured, not estimated; regenerate the pack with
`python3 scripts/launch-audio.py` and re-check with `python3 scripts/launch-audio-verify.py`.

## The pack

| Asset | Spec | Measured |
|---|---|---|
| `bed-75s.wav` | 48 kHz, 24-bit, mono, 75.000 s, 96 BPM | 75.000000 s, peak −3.00 dBFS, RMS −16.92 dBFS, **−18.37 LUFS** integrated, true peak −3.00 dBTP, LRA 6.20 LU |
| 10 × `sfx/*.wav` | 48 kHz, 24-bit, mono, peak −18.00 dBFS each | verified per file, `docs/launch/audio/manifest.json` |

Bed headroom is deliberate: it ships 4.4 dB under programme level. Crest factor (peak − RMS) is **13.92 dB**;
peak-to-loudness (peak − integrated LUFS) is 15.4 dB, which is the number the gain-staging argument uses.
The mix stage owns the loudness decision (see "Gain staging").

## Cue list

Times are seconds from 00:00.000 and the frame at 30 fps CFR; both are exact in the bed/edit. "Trim" is the
gain applied to the delivered file (`0 dB` = the file's own −18.00 dBFS peak), giving the level at use.
Every cue lands on a hard cut or a beat named in §3 — none is placed by ear.

| # | Time | Frame | Cue | Plan §3 beat | Trim | Level at use |
|---|---|---|---|---|---|---|
| B1 | 0.000 | 0 | Bed: low pad + single piano note (D4) | 1 — "single piano note on frame 0" | — | bed body ≈ −18 LUFS |
| B2 | 3.500 | 105 | Bed: piano F4 under card 1 | 2 — cards land one per beat | — | — |
| 1 | 3.500 | 105 | `01-paper-tap-1` | 2 — "paper taps, three of them" | 0 dB | −18.0 dBFS |
| B3 | 5.000 | 150 | Bed: piano A4 under card 2 | 2 | — | — |
| 2 | 5.000 | 150 | `02-paper-tap-2` | 2 | 0 dB | −18.0 dBFS |
| B4 | 6.500 | 195 | Bed: piano D4 under card 3 | 2 | — | — |
| 3 | 6.500 | 195 | `03-paper-tap-3` | 2 | 0 dB | −18.0 dBFS |
| B5 | 7.400–8.125 | 222–244 | Bed: fade-out 7.400→**7.500**, then **digital silence** 7.500–8.125, one beat | 3 — "music drops out, one beat of silence" | — | −∞ (measured −999 dB) from 7.499958 s |
| B6 | 8.125–11.000 | 244–330 | Bed: build (swept tone 70→420 Hz, band-limited swell, accelerating piano) | 3/§8 — "build at 7.5 s" | — | RMS −17.12 over 8.125–11.000; −13.52 over the last 100 ms |
| B7 | 11.000 | 330 | Bed: **hit** — sub impact + full Dm | 4 — "hit on frame 330, music returns" | — | RMS −8.46 over 11.000–11.500 |
| 4 | 15.000 | 450 | `04-click-1` | 5 — `Start a new course` click | +1 dB | −17.0 dBFS |
| 5 | 16.000 | 480 | `06-keyboard` | 5 — typing the topic (re-place at 17.100 if typing runs longer) | 0 dB | −18.0 dBFS |
| 6 | 19.500 | 585 | `05-click-2` | 5 — generate/confirm click | +1 dB | −17.0 dBFS |
| 7 | 23.500 | 705 | `07-stamp` | 5 — "a single stamp when the plan lands" | +3 dB | −15.0 dBFS |
| 8 | 31.000 | 930 | `04-click-1` (reuse, second placement) | 6 — "UI click", answer the check card | +1 dB | −17.0 dBFS |
| 9 | 32.200 | 966 | `08-correct-chime` | 6 — "soft correct chime"; feedback holds 1.2 s to 33.400 | +4 dB | −14.0 dBFS |
| 10 | 41.500 | 1245 | `06-keyboard` (reuse) | 7 — "key click", ask about the selected line | 0 dB | −18.0 dBFS |
| 11 | 44.500 | 1335 | `09-page-turn` | 7 — "page turn on the citation" | +1 dB | −17.0 dBFS |
| 12 | 47.000 | 1410 | `10-level-sting` | 8 — "level-up sting, short", on the cut as the XP chip counts 0→40 | +3 dB | −15.0 dBFS |
| 13 | 56.000 | 1680 | `09-page-turn` (reuse, low) | 9 — "soft paper slide" as Parent Studio pans in | 0 dB | −18.0 dBFS |
| B8 | 64.000–70.000 | 1920–2100 | Bed: second build | 10 — "music builds" | — | RMS −17.40 over 64.000–70.000; −15.36 over the last 200 ms |
| B9 | 70.000 | 2100 | Bed: **final hit** + ring through the end card | 11 — "final hit, tail 1.5 s" (see conflict 3) | — | RMS −8.87 over 70.000–70.500; −17.79 over 74.000–74.200 |
| B10 | 74.400–75.000 | 2232–2250 | Bed: tail fade to zero | 11 / §3 rule — "fade 74.4–75.0 s" | — | RMS −49.06 over the last 100 ms (74.900–75.000) |

Ten files, **thirteen** SFX placements (three files are reused, marked above). The §3 sound column names
eleven sounds; the pack is the ten-file set the card asks for, and the card/tap repeats cover the rest.

## Levels

- **Delivered:** every SFX file peaks at −18.00 dBFS; the bed peaks at −3.00 dBFS. Nothing clips
  (0 samples above −0.01 dBFS), no DC offset, first and last sample are zero.
- **At use:** SFX sit between −18 and −14 dBFS peak, inside plan §8's "−18 to −12 dBFS under the bed",
  and 11 dB below plan §8's −6 dBTP SFX ceiling.
- **Programme:** the finished film is normalised by CP-033d to −14 LUFS integrated, true peak ≤ −1 dBTP
  (plan §9 item 3). This pack is an input, not the finished mix.

## Gain staging for CP-033d

The bed measures **−18.37 LUFS / −3.00 dBTP**. To reach the −14 LUFS programme target by fader alone you
would add 4.37 dB and put the true peak at +1.37 dBTP — a fail. Peak-to-loudness is 15.4 dB because the bed
is sparse piano, so:

1. Bed gain **+4.4 dB**.
2. Then a true-peak limiter:
   `alimiter=limit=0.84:attack=5:release=50:level=disabled` (0.84 ≈ −1.5 dBTP).
   **`level=disabled` is mandatory.** `alimiter`'s `level` option defaults to *enabled*, which re-normalises
   the output back to 0 dBFS: without the flag this chain measures **−12.65 LUFS / 0.00 dBTP** (and
   **−13.10 LUFS / 0.00 dBTP** with the older `limit=0.891`) — **1.5 dB louder than intended** at the
   published limit (1.0 dB at the older one: −13.10 vs −14.11) and at full scale, a fail of the §9 item 3
   true-peak gate with no headroom for anything summed later. The +4.4 dB above is the bed gain stage; it is
   not the size of the error. Do not "clean up" the
   chain by dropping the flag. (The `−14.11 LUFS / −1.00 dBTP` pair sometimes quoted for this chain belongs to
   `limit=0.891` **with** `level=disabled` — the round-1 setting — not to the no-flag case.)
3. Place the SFX after the limiter so their transients are not squashed; they are already 15 dB down.
4. **Re-measure the finished programme, not just the bed.** `limit=0.84` leaves 0.5 dB under the ceiling for
   the SFX sum and the AAC encode, which is not a guarantee — run `loudnorm=print_format=json` on the completed
   mix and paste the numbers into `QC.md`. If TP still lands above −1.0 dBTP, limit the finished programme
   again; do not lower the bed under the SFX.

Verified end to end on the delivered bed — this is the exact command `launch-audio-verify.py` executes:

```
ffmpeg -i docs/launch/audio/bed-75s.wav \
  -af "volume=4.4dB,alimiter=limit=0.84:attack=5:release=50:level=disabled,loudnorm=print_format=json" -f null -
# -> input_i -14.16 LUFS   input_tp -1.51 dBTP
#    gate (plan §9 item 3): I -15.0..-13.0 LUFS, TP <= -1.0 dBTP
```

Do not compress the bed to chase loudness in this pack — re-run the generator instead if a different crest
is wanted.

## Ducking rule

**Music ducks −6 dB under any voice.** The hero cut has **no voiceover** (plan §8, §13), so ducking is
**not engaged** in this mix and the bed runs at full level for all 75 s apart from the scored drop-out at
7.500–8.125 s.

If the optional VO variant is cut later, apply it exactly like this:

- Sidechain the music bus from the VO bus: **−6 dB** reduction, **80 ms** attack, **400 ms** release,
  **10 dB** max reduction (the −6 dB static value plus 4 dB of headroom for peaks).
- Keep the bed's drop-out at 7.500–8.125 s — a VO does not replace the written beat of silence.
- SFX are **not** ducked (they are the product's own sound), but they must stay 6 dB below the VO.
- Re-measure the programme: −14 LUFS integrated, TP ≤ −1 dBTP, and the VO must read at least 6 LU below
  the bed peak at every syllable.

## Three plan conflicts, resolved here (do not "fix" them in the mix)

1. **Silence vs build at 7.5 s.** §3 beat 3 says "music drops out, one beat of silence"; §8 and this card
   say "build at 7.5 s". Both are kept: the bed is **digital silence 7.500–8.125 s** and the build occupies
   **8.125–11.000 s**. The drop-out is a measured −999 dB, not a quiet pad.
   *Exact boundaries, measured on the delivered file:* the fade runs 7.400→7.500 (the last 100 ms before the
   cut), the last non-zero sample is at **7.499937 s**, and the exact-zero run is **7.499958–8.125000 s =
   0.6250 s = exactly one beat at 96 BPM**. The music is therefore audible — 17.8 dB down and decaying, but
   present — right up to the 7.500 cut (last frame 7.467–7.500 s measures −34.8 dBFS RMS against a −16.9 dBFS
   bed body), instead of going silent 150 ms early. No frame of the drop-out is dead before its cut.
2. **The fade length at the end.** §3 says "6-frame fade at 74.4–75.0 s"; 6 frames at 30 fps is 0.2 s but the
   stated range is 0.6 s. The bed fades across the **whole stated range, 74.400–75.000**, because a 0.2 s fade
   would leave the score at full level to 74.8 s and then cut. If the editor wants 6 frames instead, that
   is a picture decision, not an audio one.
3. **"Tail 1.5 s" vs a 5 s end card.** §3 beat 11 calls the final hit "final hit, tail 1.5 s", but beat 11 is
   itself 5 s long (70.0–75.0) and §8 / this card say "tail at 70 s". A 1.5 s tail would leave **3.5 s of
   silence under the end card**, which is dead air on a static type-only card with no motion to carry it.
   Kept: the final hit rings through the end card and is faded out by the planned 74.400–75.000 fade —
   measured −8.9 dBFS RMS at the hit, −17.8 dBFS at 74.0–74.2, −49 dB in the last 100 ms. That is the plan's
   audible intent (the hit carries the card, the film ends on a fade, not a cut) with no untracked silence.
   If the editor wants a literal 1.5 s tail, say so and the final hit is regenerated short; do not cut the
   file at 71.5 s.

## Tempo and grid

96 BPM gives a 0.625 s beat (120 beats in 75 s). The picture cuts (3.5, 7.5, 11.0, 14.0 …) are **not**
multiples of 0.625 s, so the score is built the way film music is built: the rhythmic pulse is anchored on
beat 0 at t = 0.000 (the single piano note on frame 0), while structural events — the drop-out, the build,
both impacts — are locked to the **exact frame times**, not to the grid. Harmony changes on the cuts. Do not
time-shift the bed to "straighten" the grid; it would move the hit off frame 330.

## Source search (why this pack is synthesised)

The card allows a CC0 library track **or** a code-composed bed. A search of Pixabay's CC0/royalty-free
catalogue (query: "CC0 96 BPM sparse piano ambient, commercial use") returned only catalogue listing pages;
no candidate could be verified as a specific, URL-citable track **and** cut to the 7.500 / 11.000 / 70.000
anchors without time-stretching — and a stretched track is a derived work with a weaker licence line than an
owned composition. The card's 30-minute escape hatch was taken: the bed is composed and rendered by
`scripts/launch-audio.py`, owns its licence outright, and hits the anchors to the frame. Licence:
CC0 1.0, https://creativecommons.org/publicdomain/zero/1.0/ — see `docs/launch/CREDITS.md`.

## Reproduce / verify

```
python3 scripts/launch-audio.py        # writes docs/launch/audio/{bed-75s.wav,sfx/*.wav,manifest.json}
python3 scripts/launch-audio-verify.py # asserts the spec below, exits non-zero on any miss
ffprobe -v error -show_entries stream=sample_rate,bits_per_sample,duration \
        -of csv=p=0 docs/launch/audio/bed-75s.wav
```

Verified on this branch: bed 75.000000 s / 48 kHz / 24-bit, peak −3.00 dBFS, RMS −16.92 dBFS, crest 13.92 dB;
10 SFX at −18.000 dBFS peak; exact zero 7.499958–8.125000 s (one beat, starting on the 7.500 cut); hit at
11.000 s is 7.9 dB above the pre-hit window; final hit at 70.000 s is 7.5 dB above it; the last 100 ms of the
tail measure −49 dB. The published CP-033d chain measures I −14.16 LUFS / TP −1.51 dBTP on the bed.
