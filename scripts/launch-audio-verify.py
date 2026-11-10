#!/usr/bin/env python3
"""CP-036 acceptance check for the launch-film audio pack.

Asserts exactly what the card's "done when" says, plus the picture anchors, so
CP-033d can run one command instead of trusting prose. Exit code 0 = pass.

  python3 scripts/launch-audio-verify.py [--dir docs/launch/audio]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import wave

import numpy as np

SR = 48000
DUR = 75.0
BPM = 96.0
SILENCE = (7.500, 8.125)
HIT = 11.0
FINAL_HIT = 70.0
FADE_START = 74.40
SFX_FILES = [
    "01-paper-tap-1", "02-paper-tap-2", "03-paper-tap-3",
    "04-click-1", "05-click-2", "06-keyboard", "07-stamp",
    "08-correct-chime", "09-page-turn", "10-level-sting",
]

fails: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str):
    if not cond:
        fails.append(msg)
    return cond


def read_wav24(path: str) -> tuple[np.ndarray, dict]:
    with wave.open(path, "rb") as w:
        meta = {
            "channels": w.getnchannels(),
            "sampwidth": w.getsampwidth(),
            "rate": w.getframerate(),
            "frames": w.getnframes(),
        }
        raw = np.frombuffer(w.readframes(meta["frames"]), dtype=np.uint8)
    if meta["sampwidth"] != 3:
        return np.zeros(0), meta
    b = raw.reshape(-1, 3).astype(np.int32)
    x = (b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)).astype(np.int64)
    x = np.where(x >= 1 << 23, x - (1 << 24), x) / 8388608.0
    return x.astype(np.float64), meta


def db(x: float) -> float:
    return 20.0 * math.log10(x) if x > 0 else -999.0


def rms_db(seg: np.ndarray) -> float:
    if len(seg) == 0:
        return -999.0
    return db(float(np.sqrt(np.mean(seg ** 2))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="docs/launch/audio")
    ap.add_argument("--credits", default="docs/launch/CREDITS.md")
    ap.add_argument("--mixnotes", default="docs/launch/audio/mix-notes.md")
    a = ap.parse_args()

    bed_path = os.path.join(a.dir, "bed-75s.wav")
    print(f"== bed: {bed_path}")
    if not check(os.path.exists(bed_path), f"missing {bed_path}"):
        print("\n".join(fails))
        return 1
    bed, meta = read_wav24(bed_path)
    check(meta["rate"] == SR, f"bed sample rate {meta['rate']} != {SR}")
    check(meta["sampwidth"] == 3, f"bed bit depth {meta['sampwidth']*8} != 24")
    check(meta["channels"] == 1, f"bed channels {meta['channels']} != 1")
    secs = meta["frames"] / meta["rate"]
    check(abs(secs - DUR) < 1e-6, f"bed duration {secs:.6f} != {DUR}")
    print(f"   {secs:.6f} s / {meta['rate']} Hz / {meta['sampwidth']*8}-bit / {meta['channels']} ch")

    peak = float(np.max(np.abs(bed)))
    print(f"   peak {db(peak):.2f} dBFS, rms {rms_db(bed):.2f} dBFS")
    check(db(peak) < -0.5, f"bed peaks at {db(peak):.2f} dBFS — leave headroom")
    check(int(np.sum(np.abs(bed) > 0.9999)) == 0, "bed has clipped samples")
    check(abs(bed[0]) < 1e-6 and abs(bed[-1]) < 1e-6, "bed does not start/end at zero")

    def w(t0, t1):
        return bed[int(t0 * SR):int(t1 * SR)]

    sil = rms_db(w(SILENCE[0], SILENCE[1]))
    pre = rms_db(w(HIT - 1.0, HIT - 0.5))
    hit = rms_db(w(HIT, HIT + 0.5))
    fin = rms_db(w(FINAL_HIT, FINAL_HIT + 0.5))
    tail = rms_db(w(74.90, 75.00))
    print(f"\n== anchors")
    print(f"   drop-out {SILENCE[0]:.3f}-{SILENCE[1]:.3f}s  {sil:7.2f} dB   (must be <= -60)")
    print(f"   pre-hit {HIT-1.0:.2f}-{HIT-0.5:.2f}s   {pre:7.2f} dB")
    print(f"   hit     {HIT:.2f}-{HIT+0.5:.2f}s   {hit:7.2f} dB   (must exceed pre-hit by >= 5 dB)")
    print(f"   final   {FINAL_HIT:.2f}-{FINAL_HIT+0.5:.2f}s {fin:7.2f} dB   (must exceed pre-hit by >= 5 dB)")
    print(f"   tail    74.90-75.00s    {tail:7.2f} dB   (must be <= -40)")
    check(sil <= -60, f"drop-out is not silent ({sil:.2f} dB)")
    check(hit - pre >= 5.0, f"hit is only {hit-pre:.2f} dB over pre-hit")
    check(fin - pre >= 5.0, f"final hit is only {fin-pre:.2f} dB over pre-hit")
    check(tail <= -40, f"tail does not fade ({tail:.2f} dB in last 100 ms)")
    # the fade must start at 74.4, not earlier: level at 74.2 should still be audible
    check(rms_db(w(74.0, 74.2)) > -35.0, "tail fades too early (before 74.4 s)")

    # the beat grid: 96 BPM = 0.625 s, 120 beats in 75 s
    check(abs(60.0 / BPM * 120 - DUR) < 1e-9, "96 BPM does not divide 75 s evenly")
    print(f"   grid: {60.0/BPM:.4f} s/beat, 120 beats, build 8.125-11.000, fade {FADE_START:.2f}-75.00")

    print(f"\n== sfx ({len(SFX_FILES)} expected)")
    peaks = []
    for name in SFX_FILES:
        p = os.path.join(a.dir, "sfx", name + ".wav")
        if not check(os.path.exists(p), f"missing sfx {p}"):
            continue
        x, m = read_wav24(p)
        check(m["rate"] == SR, f"{name}: rate {m['rate']}")
        check(m["sampwidth"] == 3, f"{name}: depth {m['sampwidth']*8}")
        pk = db(float(np.max(np.abs(x))))
        peaks.append(pk)
        dur = m["frames"] / m["rate"]
        ok = abs(pk - (-18.0)) < 0.1
        check(ok, f"{name}: peak {pk:.2f} dBFS != -18.0")
        print(f"   {name:18s} {dur:5.3f} s  peak {pk:7.2f} dBFS  {'ok' if ok else 'FAIL'}")
    check(len(peaks) == 10, f"expected 10 sfx, got {len(peaks)}")

    man_path = os.path.join(a.dir, "manifest.json")
    if check(os.path.exists(man_path), "missing manifest.json"):
        with open(man_path) as f:
            man = json.load(f)
        check(len(man.get("sfx", [])) == 10, "manifest does not list 10 sfx")
        check(abs(man["bed"]["seconds"] - DUR) < 1e-6, "manifest bed seconds wrong")
        check(man["bed"]["bpm"] == BPM, "manifest bpm wrong")

    print("\n== documents")
    credits = open(a.credits).read() if os.path.exists(a.credits) else ""
    check(bool(credits), f"missing {a.credits}")
    check("creativecommons.org/publicdomain/zero/1.0" in credits,
          "CREDITS.md has no citable licence URL")
    check("bed-75s.wav" in credits, "CREDITS.md does not name the bed")
    for name in SFX_FILES:
        check(name in credits, f"CREDITS.md has no licence row for {name}")

    mix = open(a.mixnotes).read() if os.path.exists(a.mixnotes) else ""
    check(bool(mix), f"missing {a.mixnotes}")
    low = mix.lower()
    check("duck" in low and "6 db" in low, "mix-notes has no ducking rule (-6 dB under voice)")
    # every SFX file must appear in the cue list
    for name in SFX_FILES:
        check(name in mix, f"mix-notes has no cue for {name}")
    # cue rows must carry a timecode and a trim
    rows = [ln for ln in mix.splitlines()
            if ln.startswith("|") and re.search(r"\d+\.\d{3}", ln) and "`" in ln]
    check(len(rows) >= 14, f"only {len(rows)} timed cue rows in mix-notes (expect >= 14)")
    print(f"   cue rows with a timecode: {len(rows)}")
    print(f"   licence URL present: {'yes' if 'creativecommons.org' in credits else 'no'}")

    print()
    if fails:
        print(f"FAIL ({len(fails)})")
        for f_ in fails:
            print("  - " + f_)
        return 1
    print("PASS — bed 75.000 s, 10 SFX at -18 dBFS, anchors and licences verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
