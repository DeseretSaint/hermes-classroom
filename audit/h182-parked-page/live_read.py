"""Read the live H-182/D3 rows through the real RPC against a *copy* of that store.

Read-only evidence for t_3a3c6ea1. The source profile is never opened for writing: its two files
are copied into scratch, and every command runs with ``db.use_store_scope`` pinned to the copy.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from coursebook import api, db, domain  # noqa: F401 - importing domain registers the handlers

SOURCE = Path.home() / ".hermes/coursebook-test-h182d3/home/plugin-data/coursebook"
COPY = Path("/home/deseretsaint/.hermes/profiles/cinder/cache/scratch/t3a3-live/plugin-data/coursebook")

ENROLLMENT = "enr_1690af0794f9426cba6486bf5b765236"
COURSE = "crs_b06a829852714f21a9ddba63ddfeb2fa"
OBJECTIVE = "9e23789eee08e7ca"


def request(method: str, payload: dict) -> dict:
    return {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"op-{method.replace('.', '-')}-evidence",
        "payload": payload,
    }


def main() -> None:
    if COPY.parent.parent.exists():
        shutil.rmtree(COPY.parent.parent)
    COPY.mkdir(parents=True)
    for name in ("data.db", "data.db-wal", "data.db-shm"):
        source = SOURCE / name
        if source.exists():
            shutil.copy2(source, COPY / name)

    with db.use_store_scope(COPY):
        page = api.dispatch(request("lesson.page", {"enrollment_id": ENROLLMENT, "objective_id": OBJECTIVE}))
        book = api.dispatch(request("parent.blueprint.read", {"course_id": COURSE}))

    result = page["result"] if page["ok"] else None
    if result is None:
        print("lesson.page FAILED:", json.dumps(page.get("error"), indent=1))
        return
    document = result["document"]
    print("lesson.page ok:", page["ok"])
    print("  document.state     :", document["state"])
    print("  document.blocks    :", len(document["blocks"]))
    print("  document.check_id  :", document["check_id"])
    print("  document.view_note :", document["view_note"])
    print("  provenance         :", json.dumps(result["provenance"]))
    print("  section            :", json.dumps(result["section"], ensure_ascii=False))
    print()
    print("parent.blueprint.read ok:", book["ok"])
    blueprint = book["result"]
    for role in ("learner_pages", "parent_guide", "answers", "narration"):
        for item in blueprint["tabs"].get(role, []):
            print(f"  {role:13s} {item['title']}  ({item['bytes']} B)")
    print("  sections:")
    for row in blueprint["sections"]:
        print("   ", json.dumps(row, ensure_ascii=False))
    print("  export:", json.dumps(blueprint["export"]))


if __name__ == "__main__":
    main()
