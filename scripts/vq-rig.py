#!/usr/bin/env python3
"""Small state helpers for `scripts/vq-capture.sh`.

Two things the shell needs and should not do with inline Python:

    python3 scripts/vq-rig.py connection <userdata/connections.json> <port> <token>
    python3 scripts/vq-rig.py game-course <state/library.json>

`connection` writes the remote-connection document the disposable Desktop reads, so the window
talks to the harness's isolated backend and never to the operator's gateway. `game-course` prints
the course id the library report chose, or nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def connection(path: str, port: str, token: str) -> int:
    document = {
        "version": 2,
        "primary": "remote-vq006",
        "launchMode": "primary",
        "lastUsed": "remote-vq006",
        "connections": [
            {"id": "local", "kind": "local", "label": "This device"},
            {
                "id": "remote-vq006",
                "kind": "remote",
                "label": f"127.0.0.1:{port}",
                "url": f"http://127.0.0.1:{port}",
                "authMode": "token",
                "token": {"encoding": "plain", "value": token},
            },
        ],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2) + "\n")
    print(target)
    return 0


def game_course(path: str) -> int:
    target = Path(path)
    if not target.is_file():
        return 0
    report = json.loads(target.read_text())
    chosen = report.get("game_course") or {}
    course_id = chosen.get("course_id") or ""
    if course_id:
        print(course_id)
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    command = sys.argv[1]
    if command == "connection" and len(sys.argv) == 5:
        return connection(sys.argv[2], sys.argv[3], sys.argv[4])
    if command == "game-course" and len(sys.argv) == 3:
        return game_course(sys.argv[2])
    print(f"unknown or incomplete command: {' '.join(sys.argv[1:])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
