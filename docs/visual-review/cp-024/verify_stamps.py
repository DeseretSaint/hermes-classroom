#!/usr/bin/env python3
"""CP-024 stamp verifier.

Reads every ``*.stamp.json`` in docs/visual-review/cp-024, and checks the packet's own claims:

* the module sha in every stamp is the checkout's ``desktop/plugin.js``;
* each name parses to its claimed route width / theme / text scale, and the probe agrees;
* the root font is checked for EVERY cell, not only the non-100 % ones, and the capture also
  recorded that it *requested* that size (round 3 shipped 14 frames at 32px while every name said
  100 %);
* every frame file exists and its sha256 matches the stamp, and no two cells share a frame hash
  (one still cannot prove two states);
* every capture-door gate is true and the frame is not a refusal;
* the frame is a course home (``data-cb-course-detail``) in the requested route mode;
* the word-wrap probe is empty: no course title is split mid-word.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "visual-review" / "cp-024"
PLUGIN = ROOT / "desktop" / "plugin.js"
NAME = re.compile(r"^course-home--(?P<width>\d+)--(?P<theme>light|dark)--(?P<scale>\d+)--(?P<state>.+)$")


def plugin_sha() -> str:
    return hashlib.sha256(PLUGIN.read_bytes()).hexdigest()


def check_packet(out_dir: Path, sha: str, require: tuple[str, ...] = (), ignore_width: tuple[str, ...] = ()) -> tuple[list[str], list[str]]:
    """Check every stamp in ``out_dir`` against ``sha``; return (names, problems)."""
    stamps = sorted(out_dir.glob("*.stamp.json"))
    problems: list[str] = []
    names: list[str] = []
    frame_hashes: dict[str, str] = {}
    for path in stamps:
        name = path.name[: -len(".stamp.json")]
        names.append(name)
        stamp = json.loads(path.read_text(encoding="utf-8"))
        route = stamp.get("route") or {}
        gates = stamp.get("gates") or {}
        capture = stamp.get("capture") or {}
        match = NAME.match(name)
        if not match:
            problems.append(f"{name}: unparseable cell name")
            continue
        width = int(match.group("width"))
        theme = match.group("theme")
        scale = int(match.group("scale"))
        if (stamp.get("plugin") or {}).get("window_sha256") != sha:
            problems.append(f"{name}: window sha {(stamp.get('plugin') or {}).get('window_sha256')} != {sha}")
        if not gates or not all(bool(value) for value in gates.values()):
            problems.append(f"{name}: gate not all true: {gates}")
        if route.get("theme") != theme:
            problems.append(f"{name}: theme {route.get('theme')} != {theme}")
        if name not in ignore_width and route.get("width") != width:
            problems.append(f"{name}: route width {route.get('width')} != {width}")
        # The scale in the cell name is the ROOT FONT SIZE, and it is asserted for every cell, not
        # only the non-100 % ones: round 3 shot 14 of 15 frames at 32px while every name said
        # 100 %, and the old check skipped exactly those cells.
        expected_root = f"{round(16 * scale / 100)}px"
        if route.get("text_scale_root_px") != expected_root:
            problems.append(
                f"{name}: rendered root font {route.get('text_scale_root_px')} != {expected_root} for {scale}% text"
            )
        requested_root = (capture.get("root_font") or {}).get("requested")
        if requested_root != expected_root:
            problems.append(
                f"{name}: capture requested root font {requested_root!r} != {expected_root} for {scale}% text"
            )
        frame_sha = capture.get("sha256")
        png = (out_dir / name).with_suffix(".png")
        if not png.exists():
            problems.append(f"{name}: frame {png.name} is missing")
        elif frame_sha:
            actual = hashlib.sha256(png.read_bytes()).hexdigest()
            if actual != frame_sha:
                problems.append(f"{name}: frame sha {actual} != stamp {frame_sha}")
        else:
            problems.append(f"{name}: stamp records no frame sha")
        if frame_sha:
            if frame_sha in frame_hashes:
                problems.append(
                    f"{name}: frame is byte-identical to {frame_hashes[frame_sha]} (sha {frame_sha}) — one frame cannot prove two cells"
                )
            else:
                frame_hashes[frame_sha] = name
        if route.get("course_detail") != "overview":
            problems.append(f"{name}: course_detail={route.get('course_detail')!r}, not an overview course home")
        wraps = route.get("word_wraps")
        if wraps is None:
            problems.append(f"{name}: stamp predates the word-wrap probe")
        elif wraps:
            problems.append(f"{name}: a title word was split across lines: {wraps}")

    for required in require:
        if required not in names:
            problems.append(f"missing required cell: {required}")
    return names, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require", action="append", default=[], help="cell name that must exist")
    parser.add_argument("--ignore-width", action="append", default=[], help="cell name exempt from the width check")
    args = parser.parse_args()

    sha = plugin_sha()
    names, problems = check_packet(OUT, sha, tuple(args.require), tuple(args.ignore_width))

    print(f"plugin sha256: {sha}")
    print(f"stamps: {len(names)}")
    for name in names:
        print(f"  {name}")
    if problems:
        print("\nPROBLEMS")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\n0 problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
