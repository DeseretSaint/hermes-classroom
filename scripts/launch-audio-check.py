"""Objective checks on the generated bed: envelope, anchors, spectrum, DC, clipping."""
import wave
import numpy as np

SR = 48000
P = "docs/launch/audio/bed-75s.wav"
with wave.open(P, "rb") as w:
    assert w.getnchannels() == 1 and w.getsampwidth() == 3 and w.getframerate() == SR
    n = w.getnframes()
    raw = np.frombuffer(w.readframes(n), dtype=np.uint8).reshape(-1, 3).astype(np.int32)
x = (raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)).astype(np.int64)
x = np.where(x >= 1 << 23, x - (1 << 24), x) / 8388608.0

print(f"frames={n} seconds={n/SR:.6f} peak={20*np.log10(np.max(np.abs(x))):.2f} dBFS")
print(f"dc={np.mean(x):.6f} clipped_samples={int(np.sum(np.abs(x) > 0.9999))}")
print(f"first_sample={x[0]:.6f} last_sample={x[-1]:.6f}")

def win_rms(t0, t1):
    a, b = int(t0 * SR), int(t1 * SR)
    seg = x[a:b]
    r = np.sqrt(np.mean(seg ** 2))
    return 20 * np.log10(r) if r > 0 else -999.0

print("\n-- RMS per 1.0 s window --")
for t in np.arange(0, 75, 1.0):
    print(f"{t:5.1f}s {win_rms(t, t+1):7.2f} dB")

print("\n-- anchors --")
print(f"silence 7.625-8.100  {win_rms(7.625, 8.100):7.2f} dB   (expect <= -60)")
print(f"pre-hit 10.00-10.50  {win_rms(10.0, 10.5):7.2f} dB")
print(f"hit     11.00-11.50  {win_rms(11.0, 11.5):7.2f} dB   (expect > pre-hit)")
print(f"build   64.00-66.00  {win_rms(64.0, 66.0):7.2f} dB")
print(f"final   70.00-70.50  {win_rms(70.0, 70.5):7.2f} dB")
print(f"tail    74.90-75.00  {win_rms(74.9, 75.0):7.2f} dB   (expect <= -40)")

# spectral centroid over time, coarse
def centroid(t0, t1):
    seg = x[int(t0*SR):int(t1*SR)]
    seg = seg * np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg))
    f = np.fft.rfftfreq(len(seg), 1/SR)
    return float(np.sum(f*spec)/max(np.sum(spec), 1e-12))

print("\n-- spectral centroid (Hz) --")
for a, b, lab in [(0,3,"drone"),(3.5,7.5,"cards"),(8.2,11,"build"),
                  (11,14,"hit"),(24,38,"classroom"),(56,64,"parent"),
                  (64,70,"build2"),(70,75,"tail")]:
    print(f"{lab:10s} {a:5.1f}-{b:5.1f}  {centroid(a,b):7.0f}")
