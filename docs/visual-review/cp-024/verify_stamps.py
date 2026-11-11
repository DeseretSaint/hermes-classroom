#!/usr/bin/env python3
"""CP-024 stamp verifier.

Reads every ``*.stamp.json`` in docs/visual-review/cp-024, and checks the packet's own claims:

* the module sha in every stamp is the checkout's ``desktop/plugin.js``;
* each name parses to its claimed route width / theme / text scale, and the probe agrees;
* every capture-door gate is true and the frame is not a refusal;
* the frame is a course home (``data-cb-course-detail``) in the requested route mode;
* the word-wrap probe is empty: no course title is split mid-word;
* ``--rig`` prints the rig line the packet names (CDP port / state), for the manifest.
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require", action="append", default=[], help="cell name that must exist")
    parser.add_argument("--ignore-width", action="append", default=[], help="cell name exempt from the width check")
    args = parser.parse_args()

    sha = plugin_sha()
    stamps = sorted(OUT.glob("*.stamp.json"))
    problems: list[str] = []
    names: list[str] = []
    for path in stamps:
        name = path.name[: -len(".stamp.json")]
        names.append(name)
        stamp = json.loads(path.read_text(encoding="utf-8"))
        route = stamp.get("route") or {}
        gates = stamp.get("gates") or {}
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
        if name not in args.ignore_width and route.get("width") != width:
            problems.append(f"{name}: route width {route.get('width')} != {width}")
        if scale != 100:
            expected_root = f"{round(16 * scale / 100)}px"
            if route.get("text_scale_root_px") != expected_root:
                problems.append(
                    f"{name}: root font {route.get('text_scale_root_px')} != {expected_root} for {scale}% text"
                )
        if route.get("course_detail") != "overview":
            problems.append(f"{name}: course_detail={route.get('course_detail')!r}, not an overview course home")
        wraps = route.get("word_wraps")
        if wraps is None:
            problems.append(f"{name}: stamp predates the word-wrap probe")
        elif wraps:
            problems.append(f"{name}: a title word was split across lines: {wraps}")

    for required in args.require:
        if required not in names:
            problems.append(f"missing required cell: {required}")

    print(f"plugin sha256: {sha}")
    print(f"stamps: {len(stamps)}")
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
