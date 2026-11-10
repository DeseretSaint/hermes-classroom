#!/usr/bin/env python3
"""CP-036 — synthesise the launch-film music bed and SFX pack.

Deterministic, DAW-free, no third-party samples. Everything here is generated
from oscillators and noise by this file, so the licence line is the repo's own
(CC0 1.0 dedication — see docs/launch/CREDITS.md).

Outputs (48 kHz / 24-bit PCM WAV):
  docs/launch/audio/bed-75s.wav        75.000 s, 96 BPM, sparse piano + pad
  docs/launch/audio/sfx/01-paper-tap-1.wav ... 10-paper-tap-3.wav

Run: python3 scripts/launch-audio.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import wave

import numpy as np

SR = 48000
DUR = 75.0
BPM = 96.0
BEAT = 60.0 / BPM  # 0.625 s

# picture anchors from docs/launch/VIDEO-PLAN.md §3 and §8
BUILD_START = 7.5
SILENCE_END = 8.125          # one beat of silence per §3 beat 3
HIT = 11.0
BUILD_2 = 64.0               # §3 beat 10 "music builds"
FINAL_HIT = 70.0
TAIL_END = 75.0
FADE_START = 74.4            # §3 rule: fade 74.4–75.0 s

# ---------------------------------------------------------------- primitives

def midi_hz(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69.0) / 12.0)


def _env_attack(t: np.ndarray, a: float) -> np.ndarray:
    return 1.0 - np.exp(-t / max(a, 1e-4))


def piano(freq: float, dur: float, seed: int, amp: float = 1.0) -> np.ndarray:
    """Felt-piano-ish additive tone: decaying partials + a soft hammer knock."""
    n = max(int(dur * SR), 8)
    t = np.arange(n) / SR
    out = np.zeros(n)
    # (harmonic ratio, amplitude, decay scale) — rolls off fast: felt, not bright
    partials = [(1, 1.00, 1.00), (2, 0.42, 0.78), (3, 0.20, 0.60),
                (4, 0.10, 0.46), (5, 0.055, 0.36), (6, 0.030, 0.28)]
    for k, (ratio, a, dk) in enumerate(partials):
        f = freq * ratio * (1.0 + 0.00035 * k * k)      # slight inharmonicity
        tau = 2.6 * dk
        out += a * np.sin(2 * np.pi * f * t + 0.37 * k) * np.exp(-t / tau)
    # hammer: 10 ms knock, low-passed noise, very quiet
    hl = min(n, int(0.012 * SR))
    rng = np.random.default_rng(seed)
    nz = rng.standard_normal(hl) * np.exp(-np.arange(hl) / (0.0022 * SR))
    nz = np.convolve(nz, np.ones(6) / 6.0, mode="same") * 0.35
    out[:hl] += nz
    out *= _env_attack(t, 0.004)
    # cosine release on the last 50 ms so notes never click
    rl = min(n, int(0.05 * SR))
    if rl > 2:
        out[-rl:] *= 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rl)))
    peak = np.max(np.abs(out))
    return out / peak * amp if peak > 0 else out


def pad(freqs, dur: float, amp: float = 1.0, attack: float = 1.4,
        release: float = 1.8, seed: int = 0) -> np.ndarray:
    """Soft pad: harmonic-summed sines, two detuned voices, slow tremolo."""
    n = max(int(dur * SR), 8)
    t = np.arange(n) / SR
    out = np.zeros(n)
    rng = np.random.default_rng(seed)
    for f0 in freqs:
        for det in (-0.0012, 0.0012):
            f = f0 * (1.0 + det)
            for h in range(1, 6):
                out += (1.0 / h ** 1.9) * np.sin(
                    2 * np.pi * f * h * t + rng.uniform(0, 2 * np.pi)
                )
    out /= max(len(freqs) * 2, 1)
    out *= _env_attack(t, attack)
    rl = min(n, int(release * SR))
    if rl > 2:
        out[-rl:] *= 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rl)))
    lfo = 1.0 + 0.07 * np.sin(2 * np.pi * 0.13 * t + 0.5)
    out *= lfo
    peak = np.max(np.abs(out))
    return out / peak * amp if peak > 0 else out


def boom(dur: float = 1.6, amp: float = 1.0, seed: int = 7) -> np.ndarray:
    """Sub impact: pitch-swept sine 95→38 Hz plus a short noise transient."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 38.0 + 57.0 * np.exp(-t / 0.09)
    ph = 2 * np.pi * np.cumsum(f) / SR
    out = np.sin(ph) * np.exp(-t / 0.55)
    hl = int(0.035 * SR)
    rng = np.random.default_rng(seed)
    nz = rng.standard_normal(hl) * np.exp(-np.arange(hl) / (0.008 * SR))
    out[:hl] += np.convolve(nz, np.ones(10) / 10.0, mode="same") * 0.5
    out *= _env_attack(np.arange(n) / SR, 0.003)
    peak = np.max(np.abs(out))
    return out / peak * amp if peak > 0 else out


def riser(dur: float, amp: float = 1.0, seed: int = 11) -> np.ndarray:
    """Build: swept tone 70→420 Hz + a band-limited noise swell, exponential ramp.

    The noise is smoothed (moving average) so the build sits in the low mids —
    an unsmoothed/differenced noise reads as a 9 kHz hiss and sounds cheap.
    """
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = t / dur
    f = 70.0 + 350.0 * x ** 1.6
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = 0.62 * np.sin(ph) + 0.26 * np.sin(2 * ph + 0.9) + 0.10 * np.sin(3 * ph + 2.1)
    rng = np.random.default_rng(seed)
    nz = rng.standard_normal(n + 48)
    nz = np.convolve(nz, np.ones(24) / 24.0, mode="same")[:n]
    nz /= max(np.max(np.abs(nz)), 1e-9)
    # a second, quieter voice rising an octave keeps the build legible
    lift = 0.18 * x ** 2 * np.sin(2 * np.pi * np.cumsum(f * 2.0) / SR)
    env = x ** 2.2
    out = (tone + 0.42 * nz + lift) * env
    out *= _env_attack(t, 0.05)
    peak = np.max(np.abs(out))
    return out / peak * amp if peak > 0 else out


def place(buf: np.ndarray, t0: float, sig: np.ndarray, gain: float = 1.0):
    i = int(round(t0 * SR))
    if i >= len(buf):
        return
    if i < 0:
        sig = sig[-i:]
        i = 0
    n = min(len(sig), len(buf) - i)
    if n > 0:
        buf[i:i + n] += sig[:n] * gain


# ---------------------------------------------------------------- harmony

# voicings as MIDI numbers, low → high
VOICING = {
    "Dm": [38, 45, 50, 57, 62, 65, 69],
    "Bb": [34, 41, 46, 53, 58, 62, 65],
    "F":  [29, 36, 41, 48, 53, 57, 60],
    "C":  [36, 43, 48, 55, 60, 64, 67],
    "A":  [33, 40, 45, 52, 57, 61, 64],
}

# section: (start, end, chord) — chord changes land on picture cuts (§3)
SECTIONS = [
    (0.0, 3.5, "Dm"),
    (3.5, 7.5, "Dm"),
    (11.0, 14.0, "Dm"),
    (14.0, 24.0, "Bb"),
    (24.0, 38.0, "Dm"),
    (38.0, 47.0, "Bb"),
    (47.0, 56.0, "Dm"),
    (56.0, 64.0, "C"),
    (64.0, 70.0, "Bb"),
    (70.0, 75.0, "Dm"),
]

# inner chord moves inside the long picture beats, on 2.5 s bars (4 beats)
INNER = {
    14.0: [(14.0, "Bb"), (17.5, "F"), (21.0, "C")],
    24.0: [(24.0, "Dm"), (27.5, "Bb"), (31.0, "F"), (34.5, "C")],
    38.0: [(38.0, "Bb"), (41.0, "F"), (44.0, "C")],
    47.0: [(47.0, "Dm"), (50.0, "Bb"), (53.0, "F")],
    56.0: [(56.0, "C"), (60.0, "Dm")],
    64.0: [(64.0, "Bb"), (67.0, "A")],
}


def chord_at(t: float) -> str:
    # resolve via the flattened inner timeline
    for start, end, name in SECTIONS:
        if start <= t < end:
            moves = INNER.get(start)
            if moves:
                cur = moves[0][1]
                for mt, mn in moves:
                    if t >= mt:
                        cur = mn
                return cur
            return name
    return "Dm"


def inner_timeline():
    out = []
    for start, end, name in SECTIONS:
        moves = INNER.get(start)
        if moves:
            for i, (mt, mn) in enumerate(moves):
                nxt = moves[i + 1][0] if i + 1 < len(moves) else end
                out.append((mt, nxt, mn))
        else:
            out.append((start, end, name))
    return out


# ---------------------------------------------------------------- bed build

def build_bed() -> np.ndarray:
    buf = np.zeros(int(DUR * SR))
    rng = np.random.default_rng(20261110)

    # 1. low drone under beats 1–2, enters at 0 with the single piano note
    place(buf, 0.0, pad([midi_hz(38), midi_hz(45)], 7.9, amp=0.20,
                        attack=1.6, release=0.9, seed=1), 1.0)
    place(buf, 0.0, piano(midi_hz(62), 3.2, seed=101, amp=0.46), 1.0)   # D4 on frame 0

    # 2. beat 2 (3.5–7.5): three card landings, sparse piano under the paper taps
    for i, (tt, m) in enumerate([(3.5, 65), (5.0, 69), (6.5, 62)]):
        place(buf, tt, piano(midi_hz(m), 2.6, seed=110 + i, amp=0.26), 1.0)

    # 3. beat 3: one beat of silence (7.5–8.125), then the build to the hit
    place(buf, SILENCE_END, riser(HIT - SILENCE_END, amp=0.30, seed=21), 1.0)
    # accelerating piano pulse through the build, on 16th→8th grid
    t, step, k = SILENCE_END + 0.3125, 0.3125, 0
    while t < HIT - 0.05:
        place(buf, t, piano(midi_hz([57, 62, 65][k % 3]), 0.9,
                            seed=200 + k, amp=0.10 + 0.16 * (t - SILENCE_END) / 2.875), 1.0)
        k += 1
        step = 0.3125 if k < 5 else 0.625
        t += step

    # 4. hit at 11.0 — impact + full Dm
    place(buf, HIT, boom(1.8, amp=0.62, seed=31), 1.0)
    for m, a in [(38, 0.30), (50, 0.20), (62, 0.30), (69, 0.16)]:
        place(buf, HIT, piano(midi_hz(m), 4.5, seed=300 + m, amp=a), 1.0)
    place(buf, HIT, pad([midi_hz(m) for m in (38, 50, 57, 62)], 6.0,
                        amp=0.16, attack=0.6, release=2.0, seed=32), 1.0)

    # 5. bed through beats 4–10: pad per chord section + sparse piano
    for (t0, t1, name) in inner_timeline():
        v = VOICING[name]
        seg = min(t1 - t0, 6.0)
        place(buf, t0, pad([midi_hz(m) for m in (v[0], v[2], v[4], v[5])],
                           min(t1 - t0 + 1.2, DUR - t0), amp=0.115,
                           attack=0.9, release=1.4, seed=int(t0 * 10) + 5), 1.0)

    # piano figure: one low note + one or two upper notes per chord, 2.5 s grid
    for (t0, t1, name) in inner_timeline():
        v = VOICING[name]
        place(buf, t0, piano(midi_hz(v[1]), min(3.0, t1 - t0 + 1.0),
                            seed=int(t0 * 100) + 1, amp=0.22), 1.0)
        if t1 - t0 > 1.5:
            up = [v[4], v[6], v[3], v[5]]
            for j in range(2 if t1 - t0 < 5 else 3):
                tt = t0 + BEAT * (2 + 2 * j)
                if tt >= t1 - 0.2:
                    break
                place(buf, tt, piano(midi_hz(up[(j + int(t0)) % len(up)]), 2.2,
                                    seed=int(tt * 100) + 9, amp=0.15), 1.0)

    # 6. beat 10 build (64.0 → 70.0) and the final hit
    place(buf, BUILD_2, riser(FINAL_HIT - BUILD_2, amp=0.24, seed=41), 1.0)
    place(buf, FINAL_HIT, boom(2.2, amp=0.55, seed=51), 1.0)
    for m, a in [(38, 0.28), (50, 0.18), (62, 0.28), (65, 0.14), (69, 0.12)]:
        place(buf, FINAL_HIT, piano(midi_hz(m), 5.0, seed=400 + m, amp=a), 1.0)
    place(buf, FINAL_HIT, pad([midi_hz(m) for m in (38, 50, 57, 62, 69)], 5.4,
                              amp=0.15, attack=0.25, release=2.2, seed=52), 1.0)

    # 7. remove DC before the dropout so the silent beat is a true zero
    buf -= np.mean(buf)

    # 7b. §3 beat 3: the bed drops out for exactly one beat, 7.500–8.125 s.
    #    Applied last so no decaying note tail bleeds into the silence.
    d0, d1 = int(7.35 * SR), int(7.45 * SR)
    buf[d0:d1] *= 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, d1 - d0)))
    buf[d1:int(SILENCE_END * SR)] = 0.0

    # 8. tail fade 74.4 → 75.0 (plan §3: no hard cut at the end)
    i0 = int(FADE_START * SR)
    n = len(buf) - i0
    buf[i0:] *= np.linspace(1.0, 0.0, n) ** 1.3

    # 8. top and tail: absolute zero at both ends, no DC, no click
    buf[:int(0.005 * SR)] *= np.linspace(0, 1, int(0.005 * SR))
    fade_in = int(0.005 * SR)
    buf[-fade_in:] *= np.linspace(1, 0, fade_in)

    # 9. headroom: peak -3.0 dBFS, then a gentle tanh safety on the bus
    buf = np.tanh(buf / max(np.max(np.abs(buf)), 1e-9) * 2.2) / 2.2
    buf *= 10 ** (-3.0 / 20) / max(np.max(np.abs(buf)), 1e-9)
    return buf.astype(np.float64)


# ---------------------------------------------------------------- SFX

def sfx_paper_tap(seed: int, tone: float, dur: float = 0.30) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    nz = rng.standard_normal(n) * np.exp(-t / 0.018)
    # band emphasis around 1.4–2.6 kHz through a short resonant ring
    ring = np.sin(2 * np.pi * tone * t) * np.exp(-t / 0.010)
    hp = np.diff(nz, prepend=0.0)
    out = 0.75 * np.convolve(hp, np.ones(4) / 4, mode="same") + 0.45 * ring
    out *= _env_attack(t, 0.0015)
    out[-int(0.05 * SR):] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, int(0.05 * SR))))
    return out / max(np.max(np.abs(out)), 1e-9)


def sfx_click(seed: int, tone: float, dur: float = 0.14) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    tick = rng.standard_normal(n) * np.exp(-t / 0.0018)
    ping = (np.sin(2 * np.pi * tone * t) + 0.4 * np.sin(2 * np.pi * tone * 2.02 * t)) \
        * np.exp(-t / 0.012)
    out = 0.8 * np.diff(tick, prepend=0.0) + 0.5 * ping
    out *= _env_attack(t, 0.0008)
    out[-int(0.03 * SR):] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, int(0.03 * SR))))
    return out / max(np.max(np.abs(out)), 1e-9)


def sfx_keyboard(seed: int = 5, dur: float = 0.55) -> np.ndarray:
    out = np.zeros(int(dur * SR))
    rng = np.random.default_rng(seed)
    for i, t0 in enumerate([0.0, 0.085, 0.155, 0.245, 0.30]):
        n = int(0.09 * SR)
        t = np.arange(n) / SR
        thock = np.sin(2 * np.pi * (150 + rng.uniform(-12, 12)) * t) * np.exp(-t / 0.012)
        clk = np.diff(rng.standard_normal(n), prepend=0.0) * np.exp(-t / 0.0016)
        s = 0.55 * thock + 0.6 * clk
        s *= _env_attack(t, 0.001)
        i0 = int(t0 * SR)
        m = min(n, len(out) - i0)
        out[i0:i0 + m] += s[:m] * (0.75 + 0.25 * (i % 2))
    return out / max(np.max(np.abs(out)), 1e-9)


def sfx_stamp(seed: int = 6, dur: float = 0.45) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    thud = np.sin(2 * np.pi * (78 - 18 * np.clip(t / 0.12, 0, 1)) * t) * np.exp(-t / 0.09)
    smash = np.convolve(rng.standard_normal(n), np.ones(24) / 24, mode="same") \
        * np.exp(-t / 0.022)
    out = 0.9 * thud + 0.7 * smash
    out *= _env_attack(t, 0.0015)
    rl = int(0.06 * SR)
    out[-rl:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, rl)))
    return out / max(np.max(np.abs(out)), 1e-9)


def sfx_chime(seed: int = 8, dur: float = 1.1) -> np.ndarray:
    """Two-note bell, a fourth apart: A5 then D6 — in the bed's key (D minor)."""
    n = int(dur * SR)
    out = np.zeros(n)
    for t0, f, a in [(0.0, 880.0, 1.0), (0.115, 1174.66, 0.78)]:
        m = n - int(t0 * SR)
        t = np.arange(m) / SR
        v = np.zeros(m)
        for h, ha in [(1, 1.0), (2.0, 0.30), (3.01, 0.14), (4.2, 0.06)]:
            v += ha * np.sin(2 * np.pi * f * h * t) * np.exp(-t / (0.42 / h ** 0.4))
        v *= _env_attack(t, 0.0018)
        out[int(t0 * SR):] += v * a
    rl = int(0.08 * SR)
    out[-rl:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, rl)))
    return out / max(np.max(np.abs(out)), 1e-9)


def sfx_page_turn(seed: int = 9, dur: float = 0.6) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    nz = rng.standard_normal(n)
    # paper rustle: noise gated by a fast flutter, then a short high sweep
    flutter = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 17 * t + 0.3))
    env = np.exp(-((t - 0.16) ** 2) / (2 * 0.075 ** 2))
    body = np.convolve(np.diff(nz, prepend=0.0), np.ones(3) / 3, mode="same")
    out = body * flutter * env
    sw = np.sin(2 * np.pi * (500 + 2200 * np.clip(t / dur, 0, 1) ** 2) * t) \
        * np.exp(-((t - 0.30) ** 2) / (2 * 0.055 ** 2)) * 0.18
    out = out + sw
    out *= _env_attack(t, 0.004)
    rl = int(0.09 * SR)
    out[-rl:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, rl)))
    return out / max(np.max(np.abs(out)), 1e-9)


def sfx_level_sting(seed: int = 10, dur: float = 0.9) -> np.ndarray:
    """Three-note rising arpeggio (D5 F5 A5) with a bright, short tail."""
    n = int(dur * SR)
    out = np.zeros(n)
    for t0, m in [(0.0, 74), (0.085, 77), (0.17, 81)]:
        f = midi_hz(m)
        mm = n - int(t0 * SR)
        t = np.arange(mm) / SR
        v = np.zeros(mm)
        for h, ha in [(1, 1.0), (2, 0.5), (3, 0.28), (4, 0.15), (5, 0.08)]:
            v += ha * np.sin(2 * np.pi * f * h * t) * np.exp(-t / (0.30 / h ** 0.5))
        v *= _env_attack(t, 0.002)
        out[int(t0 * SR):] += v
    rl = int(0.06 * SR)
    out[-rl:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, rl)))
    return out / max(np.max(np.abs(out)), 1e-9)


# ---------------------------------------------------------------- io

def normalise(data: np.ndarray, peak_dbfs: float | None):
    data = np.asarray(data, dtype=np.float64)
    if peak_dbfs is not None:
        peak = np.max(np.abs(data))
        if peak > 0:
            data = data * (10 ** (peak_dbfs / 20.0) / peak)
    return np.clip(data, -1.0, 1.0)


def write_wav24(path: str, data: np.ndarray):
    data = np.asarray(data, dtype=np.float64)
    ints = np.round(data * 8388607.0).astype(np.int32)
    raw = np.empty(len(ints) * 3, dtype=np.uint8)
    raw[0::3] = (ints & 0xFF).astype(np.uint8)
    raw[1::3] = ((ints >> 8) & 0xFF).astype(np.uint8)
    raw[2::3] = ((ints >> 16) & 0xFF).astype(np.uint8)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(raw.tobytes())
    return path


def measure(data: np.ndarray):
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data ** 2)))
    return {
        "peak_dbfs": round(20 * math.log10(peak) if peak > 0 else -999.0, 2),
        "rms_dbfs": round(20 * math.log10(rms) if rms > 0 else -999.0, 2),
        "seconds": round(len(data) / SR, 3),
    }


SFX_SPEC = [
    ("01-paper-tap-1", lambda: sfx_paper_tap(201, 1500.0)),
    ("02-paper-tap-2", lambda: sfx_paper_tap(202, 1750.0)),
    ("03-paper-tap-3", lambda: sfx_paper_tap(203, 1320.0)),
    ("04-click-1", lambda: sfx_click(210, 2400.0)),
    ("05-click-2", lambda: sfx_click(211, 1950.0)),
    ("06-keyboard", lambda: sfx_keyboard()),
    ("07-stamp", lambda: sfx_stamp()),
    ("08-correct-chime", lambda: sfx_chime()),
    ("09-page-turn", lambda: sfx_page_turn()),
    ("10-level-sting", lambda: sfx_level_sting()),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/launch/audio")
    args = ap.parse_args()

    bed = normalise(build_bed(), -3.0)
    assert len(bed) == int(DUR * SR), (len(bed), int(DUR * SR))
    bed_path = write_wav24(os.path.join(args.out, "bed-75s.wav"), bed)

    manifest = {"bed": {"path": bed_path, **measure(bed), "bpm": BPM,
                        "sample_rate": SR, "bit_depth": 24}, "sfx": []}
    for name, fn in SFX_SPEC:
        s = normalise(fn(), -18.0)
        p = write_wav24(os.path.join(args.out, "sfx", name + ".wav"), s)
        manifest["sfx"].append({"name": name, "path": p, **measure(s)})

    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
