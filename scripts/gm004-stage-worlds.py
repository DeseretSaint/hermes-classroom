"""Stage the GM-004 visual-review worlds through the real handlers.

This is the staging run behind every `course-world--*` / `studio-concepts--*` frame in
`docs/visual-review/gm-004/`. It does not touch the Desktop and it does not draw anything:
it drives `world.generate` / `world.approve` / `course.mode.set` / `enrollment.create`
through `coursebook.api.dispatch`, and binds a deterministic, provider-shaped media seam in
this process only.

The seam returns flat tonal swatch PNGs keyed off the style palette words. They carry no
scene, no text and no numbers, and the MANIFEST labels every frame that shows them as
"synthetic tonal swatch — not model output". The live model provider is unavailable here
(`provider_unavailable`, `missing_roles: style_board:*`), so no generated art exists and
none is claimed.

Run against the preserved rig state (see MANIFEST.md "Reproduce"):

    HERMES_HOME="$HOME/.hermes/coursebook-test-gm004-203620/home" \
    GM004_WORKTREE="$PWD" \
      python3 scripts/gm004-stage-worlds.py

It is idempotent: a course whose world is already approved is reported and left alone, and
a course that already has an active enrollment is not enrolled twice.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
import zlib

HOME = os.environ["HERMES_HOME"]

COLORS = {
    "steel grey": (96, 104, 112), "oil-dark ink": (42, 40, 36), "safety ochre": (196, 138, 46),
    "parchment": (222, 208, 184), "warm parchment": (231, 214, 186), "honey ochre": (206, 160, 74),
    "midnight ink": (30, 36, 46), "slate": (88, 98, 108), "lantern amber": (208, 148, 62),
    "moss": (94, 108, 78), "forest ink": (40, 52, 44), "rice paper": (236, 228, 210),
    "indigo": (58, 70, 104), "clay": (170, 112, 84),
}
FALLBACK = (128, 118, 102)

#: The rig's three staged courses, found by title. `approve` false keeps a course at
#: `concepts_ready`, which is the state the World Studio frames need.
COURSES = (
    ("japanese_demo", "Japanese affection and register — an L0 demonstration classroom", True),
    ("head_gasket", "Replace a head gasket", True),
    ("sample_classroom", "Japanese affection and register — a Sample L0 classroom", False),
)


def png(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> bytes:
    rows = []
    for y in range(height):
        t = y / max(1, height - 1)
        row = bytes(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) * width
        rows.append(b"\x00" + row)
    raw = zlib.compress(b"".join(rows), 6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


class SwatchSeam:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def image(self, prompt: str, *, aspect_ratio: str = "landscape") -> tuple[bytes, str]:
        self.calls.append(prompt)
        low = prompt.lower()
        colors = [COLORS[name] for name in COLORS if name in low]
        top = colors[0] if colors else FALLBACK
        bottom = colors[1] if len(colors) > 1 else tuple(max(0, c - 40) for c in top)
        wide = "portrait" not in aspect_ratio
        return png(320 if wide else 240, 180 if wide else 320, top, bottom), "image/png"


os.environ.setdefault("HERMES_COURSEBOOK_SINGLE_HOME", "1")
sys.path.insert(0, os.environ.get("GM004_WORKTREE", os.getcwd()))

from coursebook import api, db, domain, executor, world  # noqa: E402

db.ensure_schema()
seam = SwatchSeam()
world.bind_media(seam)
# This process is not the plugin's register path, so bind both handler families explicitly.
domain.ensure_registered()
world.ensure_registered()


def call(method: str, payload: dict, rev=None):
    stamp = time.time_ns()
    body = {
        "contract": api.RPC_CONTRACT, "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method, "operation_id": f"gm004-stage-{method.replace('.', '-')}-{stamp}",
        "idempotency_key": f"gm004-stage-{method.replace('.', '-')}-{payload.get('course_id', '')}-{payload.get('stage', '')}-{stamp}",
        "payload": payload,
    }
    if rev is not None:
        body["expected_revision"] = rev
    response = api.dispatch(body)
    if not response.get("ok"):
        raise SystemExit(f"{method} failed: {response.get('error')}")
    return response


def newest_course(title: str) -> str:
    """The visible course for a rig title: prefer a course the library already lists."""
    with db.read() as connection:
        row = connection.execute(
            "SELECT c.id AS id FROM courses c"
            " LEFT JOIN enrollments e ON e.course_id = c.id AND e.status = 'active'"
            " WHERE c.title = ? AND c.status != 'deleted'"
            " ORDER BY (e.id IS NULL) ASC, e.updated_at DESC, c.rowid DESC LIMIT 1",
            (title,),
        ).fetchone()
    if row is None:
        raise SystemExit(f"no course titled {title!r} in {HOME} — the rig state dir is required")
    return row["id"]


def ensure_enrollment(course_id: str) -> str:
    """A course only reaches the Desktop library through an enrollment; create it honestly."""
    with db.read() as connection:
        row = connection.execute(
            "SELECT id FROM enrollments WHERE course_id = ? AND status = 'active' LIMIT 1",
            (course_id,),
        ).fetchone()
    if row is not None:
        return f"existing:{row['id']}"
    created = call("enrollment.create", {"course_id": course_id})["result"]
    return f"created:{created['enrollment_id']}"


def settle(course_id: str) -> dict:
    """Pump the real queue until this course's world leaves a *_generating state."""
    for _ in range(40):
        read = call("world.read", {"course_id": course_id})["result"]
        state = (read["world"] or {}).get("state", "not_requested")
        if state not in ("concepts_generating", "kit_generating"):
            return read
        executor.pump_once(limit=1)
    return call("world.read", {"course_id": course_id})["result"]


def stage(course_id: str, label: str, approve: bool) -> None:
    read = call("world.read", {"course_id": course_id})["result"]
    if read["world"] and read["world"]["state"] == "approved":
        print(f"{label}: already approved")
        return
    revision = read["revision"]
    state = (read["world"] or {}).get("state", "not_requested")
    if state in ("failed", "unavailable", "not_requested"):
        call("world.generate", {"course_id": course_id, "stage": "concepts"}, revision)
        read = settle(course_id)
        revision, state = read["revision"], read["world"]["state"]
    board = (read["world"].get("concepts") or [None])[0]
    if state in ("concepts_ready", "failed"):
        if not approve:
            print(json.dumps({"course": label, "state": state,
                              "concepts": len(read["world"].get("concepts") or []),
                              "provider_calls": len(seam.calls)}))
            return
        if board is None:
            raise SystemExit(f"{label}: no concept board to select from (state {state})")
        call("world.approve", {
            "course_id": course_id, "world_id": read["world"]["world_id"],
            "stage": "style", "approved_hash": board["style_hash"],
        }, revision)
        read = call("world.read", {"course_id": course_id})["result"]
        revision, state = read["revision"], read["world"]["state"]
    if state == "style_selected":
        call("world.generate", {
            "course_id": course_id, "stage": "kit", "style_id": board["style_id"],
        }, revision)
        read = settle(course_id)
        revision, state = read["revision"], read["world"]["state"]
    if state in ("kit_generating", "kit_ready"):
        read = settle(course_id)
        revision, state = read["revision"], read["world"]["state"]
    if state == "kit_ready":
        call("world.approve", {
            "course_id": course_id, "world_id": read["world"]["world_id"],
            "stage": "final", "approved_hash": read["world"]["kit_hash"],
        }, revision)
        read = call("world.read", {"course_id": course_id})["result"]
        revision = read["revision"]
    if read["presentation_mode"] != "game":
        call("course.mode.set", {"course_id": course_id, "mode": "game"}, revision)
    final = call("world.read", {"course_id": course_id})["result"]
    print(json.dumps({
        "course": label,
        "mode": final["presentation_mode"],
        "state": final["world"]["state"],
        "grammar": (final["world"]["selected_concept_id"] or "").split("--")[-1],
        "style": final["world"]["selected_concept_id"],
        "assets": [a["role"] + ":" + str(a.get("section_key") or "") for a in final["world"]["assets"]],
        "provider_calls": len(seam.calls),
        "fallback": final["fallback"],
    }))


for label, title, approve in COURSES:
    course_id = newest_course(title)
    enrollment = "not_required" if not approve else ensure_enrollment(course_id)
    print(json.dumps({"course": label, "course_id": course_id, "enrollment": enrollment}))
    stage(course_id, label, approve)
