#!/usr/bin/env python3
"""Prove the M4-V visual audit is reproducible: run it twice, compare the measurements.

The audit is only evidence if the same `desktop/plugin.js` produces the same numbers twice. This
script runs `scripts/m4v-audit.py` twice in isolated scratch/out directories (separate render pass,
separate browser, separate screenshots) and fails when anything except `generated_at` differs.

    python3 scripts/m4v-repro-check.py            # two full runs (~2 min)
    python3 scripts/m4v-repro-check.py --keep     # leave the two output dirs for inspection

Exit codes: 0 identical, 1 drifted (with the first differing paths printed), 2 the audit itself
failed to run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "scripts" / "m4v-audit.py"
# The one field that is allowed to move between runs: the wall clock of the run itself.
VOLATILE = {"generated_at"}


def run_once(workdir: Path) -> tuple[dict, dict[str, str], str]:
    """Run the audit into `workdir/out` with its own scratch tree; return audit + png hashes."""
    out = workdir / "out"
    scratch = workdir / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["TMPDIR"] = str(scratch)
    env["M4V_OUT"] = str(out)
    env.pop("M4V_SKIP_RENDER", None)
    result = subprocess.run([sys.executable, str(AUDIT)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise SystemExit(f"audit run failed ({result.returncode}):\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(out.glob("*.png"))
    }
    return audit, hashes, result.stdout


def first_difference(left: Any, right: Any, path: str = "") -> str | None:
    if type(left) is not type(right):
        return f"{path or '<root>'}: {type(left).__name__} vs {type(right).__name__}"
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                return f"{path}.{key}: present in only one run"
            found = first_difference(left[key], right[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}: {len(left)} vs {len(right)} entries"
        for index, (first, second) in enumerate(zip(left, right)):
            found = first_difference(first, second, f"{path}[{index}]")
            if found:
                return found
        return None
    if left != right:
        return f"{path}: {left!r} vs {right!r}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="keep the two output directories")
    args = parser.parse_args()

    base = Path(tempfile.mkdtemp(prefix="cb-m4v-repro-"))
    try:
        first = base / "run-a"
        second = base / "run-b"
        for path in (first, second):
            path.mkdir(parents=True, exist_ok=True)

        print(f"run A → {first}")
        audit_a, png_a, _ = run_once(first)
        print(f"run B → {second}")
        audit_b, png_b, _ = run_once(second)

        stripped_a = {key: value for key, value in audit_a.items() if key not in VOLATILE}
        stripped_b = {key: value for key, value in audit_b.items() if key not in VOLATILE}
        drift = first_difference(stripped_a, stripped_b)

        png_drift = sorted(name for name in set(png_a) | set(png_b) if png_a.get(name) != png_b.get(name))

        if drift or png_drift:
            print("FAIL: the audit is not reproducible")
            if drift:
                print(f"  first JSON difference: {drift}")
            if png_drift:
                print(f"  {len(png_drift)} screenshots differ: {', '.join(png_drift[:8])}")
            return 1

        frames = len(audit_a.get("frames") or [])
        print(f"PASS: two independent runs produced identical audit.json ({frames} frames, "
              f"modulo generated_at) and {len(png_a)} identical screenshots")
        print(f"  plugin_sha256: {audit_a.get('summary', {}).get('plugin_sha256')}")
        print(f"  reference_time: {audit_a.get('reference_time')}")
        return 0
    finally:
        if args.keep:
            print(f"kept: {base}")
        else:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
