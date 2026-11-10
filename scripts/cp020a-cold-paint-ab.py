#!/usr/bin/env python3
"""Merge the two CP-020a cold-paint phase records into one like-for-like evidence file.

Usage:
    python3 scripts/cp020a-cold-paint-ab.py \
        --baseline <baseline.json> --candidate <candidate.json> \
        --baseline-v3-scope false --candidate-v3-scope true \
        --out docs/concept-parity/captures/cp020a2-cold-paint-ab.json

Both inputs must be real `scripts/cp-cold-paint.mjs` records captured under the SAME
`--emulate WxH` in the SAME window session, each pinned to its own module sha. The merge refuses
(exit 1) when the route widths differ by more than 2 px: a timing at another route width is not a
comparison, which is exactly the round-1 defect this file exists to answer.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--baseline-v3-scope", choices=["true", "false"], required=True)
    parser.add_argument("--candidate-v3-scope", choices=["true", "false"], required=True)
    parser.add_argument("--budget", type=int, default=150)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    baseline = json.loads(Path(args.baseline).read_text())
    candidate = json.loads(Path(args.candidate).read_text())

    def samples(record):
        return [s["ms"] for s in record.get("samples", []) if isinstance(s.get("ms"), (int, float))]

    base_ms = samples(baseline)
    cand_ms = samples(candidate)
    if not base_ms or not cand_ms:
        print("cp020a-cold-paint-ab: a phase recorded no samples", file=sys.stderr)
        return 1

    base_width = baseline.get("geometry", {}).get("route_width")
    cand_width = candidate.get("geometry", {}).get("route_width")
    like_for_like = (
        baseline.get("ok") is True
        and candidate.get("ok") is True
        and isinstance(base_width, (int, float))
        and isinstance(cand_width, (int, float))
        and abs(base_width - cand_width) <= 2
    )
    delta = statistics.median(cand_ms) - statistics.median(base_ms)
    within_budget = delta <= args.budget

    record = {
        "tool": "cp-cold-paint.mjs x2 (one window, one emulated geometry, one module swap + relaunch per phase)",
        "ok": like_for_like and within_budget,
        "like_for_like": like_for_like,
        "method": (
            "Round 1 compared a 266 px route in a 512x735 window against an 809 px route in a "
            "1045x735 window. Both phases here run in the same window under "
            f"--emulate {baseline.get('emulation')}, and each phase's route width is recorded. The "
            "module under test is swapped in the linked package (home/plugins/coursebook) AND the "
            "desktop copy, then the window is relaunched, because the renderer reads the linked "
            "package's desktop/plugin.js rather than the desktop-plugins copy (proved by a DOM "
            "marker check: the pre-v3 module paints no [data-cb-v3])."
        ),
        "emulation": baseline.get("emulation"),
        "route_widths": {"baseline": base_width, "candidate": cand_width},
        "module_marker": {
            "[data-cb-v3] on baseline": args.baseline_v3_scope == "true",
            "[data-cb-v3] on candidate": args.candidate_v3_scope == "true",
        },
        "budget_ms": args.budget,
        "baseline": {
            "window_sha256": baseline["plugin"]["window_sha256"],
            "loaded_path": baseline["plugin"]["loaded_path"],
            "samples_ms": base_ms,
            "median_ms": baseline["median_ms"],
            "window_width": baseline.get("window_width"),
            "window_height": baseline.get("window_height"),
            "zoom_percent": baseline.get("zoom_percent"),
        },
        "candidate": {
            "window_sha256": candidate["plugin"]["window_sha256"],
            "loaded_path": candidate["plugin"]["loaded_path"],
            "samples_ms": cand_ms,
            "median_ms": candidate["median_ms"],
            "window_width": candidate.get("window_width"),
            "window_height": candidate.get("window_height"),
            "zoom_percent": candidate.get("zoom_percent"),
        },
        "delta_ms": delta,
        "verdict": (
            f"candidate median {statistics.median(cand_ms)} ms vs baseline {statistics.median(base_ms)} ms "
            f"at the same {base_width} px route (delta {delta:+.0f} ms, budget +{args.budget} ms)"
            if like_for_like
            else "NOT COMPARABLE: route widths differ by more than 2 px or a phase failed"
        ),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("ok", "like_for_like", "route_widths", "delta_ms", "verdict")}, indent=2))
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
