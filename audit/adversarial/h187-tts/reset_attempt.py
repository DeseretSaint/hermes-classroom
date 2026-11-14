#!/usr/bin/env python3
"""Reset the single coarse capture attempt so one coherent run record can be produced.

The prior run DID generate a real artifact (art_5d6c...), but the evidence script crashed on a
wrong column name right after the write, so that attempt has no dispatch envelope or served-page
record. This removes exactly that artifact row + object and puts the lesson's media item back to
its pre-capture placeholder so the capture script can run once, start to finish.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ce380228")
sys.path.insert(0, str(REPO))

from coursebook import db  # noqa: E402

with db.read() as connection:
    rows = connection.execute("SELECT id, path, content_hash FROM artifacts").fetchall()
    lesson = connection.execute("SELECT media_json FROM gen_lessons WHERE id = 'gen_lang_1'").fetchone()

items = json.loads(lesson["media_json"])
for item in items:
    for key in ("artifact_id", "content_hash", "mime", "label", "reason"):
        item.pop(key, None)
    item["degraded"] = True
    item["reason"] = "not generated yet; this task declares the requirement and does not produce bytes"

with db.transaction() as write:
    for row in rows:
        write.execute("DELETE FROM artifacts WHERE id = ?", (row["id"],))
    write.execute(
        "UPDATE gen_lessons SET media_json = ? WHERE id = 'gen_lang_1'",
        (json.dumps(items, ensure_ascii=False, sort_keys=True),),
    )

for row in rows:
    Path(row["path"]).unlink(missing_ok=True)

print(json.dumps({"removed_rows": [dict(r) for r in rows], "media_json": items}, indent=2, ensure_ascii=False))
