# Credits

Every asset in the launch film, with the licence line that clears it for commercial use.
Picture assets (still captures, fonts, end-card) are filled in at picture lock by CP-033c/CP-033d;
this file records the audio pack now, before picture lock, so the sound stage is a mix and not a search.

## Music

| Asset | File | Source | Licence |
|---|---|---|---|
| Launch bed, 96 BPM, 75 s | `docs/launch/audio/bed-75s.wav` | Original composition, synthesised from oscillators and noise by `scripts/launch-audio.py` (this repo). No third-party samples, loops, or model-generated audio. | CC0 1.0 Universal — https://creativecommons.org/publicdomain/zero/1.0/ . Rights holder: DeseretSaint. Commercial use, modification and redistribution permitted; no attribution required (credited here anyway). |

**Licence URL:** https://creativecommons.org/publicdomain/zero/1.0/
**Reproducible from:** `scripts/launch-audio.py` at the CP-036 commit on `wt/cp-036-audio`.
**Why not a library track:** the card allows a CC0 track or a code-composed bed. No Pixabay/Free Music
Archive track could place a build at exactly 7.500 s, a hit at exactly 11.000 s and a tail at 70.000 s
without time-stretching, which would (a) defeat the picture lock and (b) create a derived work whose
licence line is weaker than an owned composition. See `mix-notes.md` §"Source search".

## Sound effects

All ten are synthesised by the same script. Same licence: original work, CC0 1.0
(https://creativecommons.org/publicdomain/zero/1.0/), no third-party samples.

| # | File | Source | Licence |
|---|---|---|---|
| 1 | `sfx/01-paper-tap-1.wav` | `scripts/launch-audio.py` — band-limited noise burst + 1.50 kHz ring | CC0 1.0 (URL above) |
| 2 | `sfx/02-paper-tap-2.wav` | same, 1.75 kHz ring | CC0 1.0 |
| 3 | `sfx/03-paper-tap-3.wav` | same, 1.32 kHz ring | CC0 1.0 |
| 4 | `sfx/04-click-1.wav` | UI click — 1.8 ms noise transient + 2.40 kHz resonance | CC0 1.0 |
| 5 | `sfx/05-click-2.wav` | UI click, 1.95 kHz variant | CC0 1.0 |
| 6 | `sfx/06-keyboard.wav` | five mechanical key hits (150 Hz thock + click) over 0.55 s | CC0 1.0 |
| 7 | `sfx/07-stamp.wav` | stamp thud, 78→60 Hz sweep + paper smash | CC0 1.0 |
| 8 | `sfx/08-correct-chime.wav` | two-note bell, A5 → D6 (in the bed's key) | CC0 1.0 |
| 9 | `sfx/09-page-turn.wav` | flutter-gated noise + 500→2700 Hz paper sweep | CC0 1.0 |
| 10 | `sfx/10-level-sting.wav` | rising D5–F5–A5 arpeggio, 0.9 s | CC0 1.0 |

## Fonts

Per plan §5, the film uses **Fraunces**, **Source Sans 3** and **Noto Serif JP**, all SIL Open Font
License 1.1 (https://openfontlicense.org/). Font files are placed and their exact versions recorded by
CP-033c at picture lock; nothing is bundled in this audio commit.

## Capture commits

Filled in by CP-033c/CP-033d at picture lock: the exact `sha` of the accepted build for every still,
matching the `stamp` JSON beside each capture. Not claimed here — no capture exists yet.

## Tools

`ffmpeg`/`ffprobe` (LGPL/GPL build, used as an external binary, not linked) for measurement;
`numpy` for synthesis. No paid generation service was used, so there is no per-generation terms page
to cite for the audio.
