"""H-30 probe B — does a generated check reach a real verdict?

Runs one recorded non-Japanese scenario through the real product path (the H-09 harness), then
opens the first two generated checks and submits a correct and a wrong answer through
``check.open`` / ``attempt.submit`` — the same RPC the Desktop plugin speaks.

    PYTHONPATH=. python3 audit/adversarial/generic-harness/probe_grading.py <path/to/harness_e2e.py> <home-dir>

Every response is printed; the script never asserts a verdict it did not read.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


def load_harness(path: str):
    spec = importlib.util.spec_from_file_location("harness_e2e_probe", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def show(label: str, value) -> None:
    print(f"{label}: {json.dumps(value, sort_keys=True, default=str)}")


def main() -> None:
    harness_path, home_dir = sys.argv[1], Path(sys.argv[2])
    home = home_dir / "home"
    home.mkdir(parents=True, exist_ok=True)
    harness = load_harness(harness_path)

    name = sys.argv[3] if len(sys.argv) > 3 else "music_short"
    evidence = harness.run_scenario(name, home=home)
    print(f"scenario {name}: {evidence['verdict']}")

    enrollment_id = evidence["steps"]["create"]["enrollment_id"]
    approve_revision = evidence["steps"]["approve"]["revision"]
    show("approve_revision", approve_revision)

    outline = harness._ok("course.outline", {"enrollment_id": enrollment_id})
    objectives = outline["objectives"]
    show("outline_objectives", [(o["ordinal"], o.get("title"), o.get("check_state")) for o in objectives])

    # Correct answer for objective 1 in the recorded music transcript is "7" (perfect fifth).
    # Wrong answer for objective 2 is "D major"; the transcript's reference is "D minor".
    attempts = [
        (objectives[0], {"kind": "selection", "selection": ["7"]}, "correct-answer"),
        (objectives[1], {"kind": "selection", "selection": ["D major"]}, "wrong-answer"),
    ]
    revision = approve_revision
    for objective, answer, label in attempts:
        opened = harness._rpc(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective["objective_id"]},
            expected_revision=revision,
            key=f"h30-open-{objective['ordinal']}",
        )
        show(f"check.open[{label}]", opened)
        if not opened["ok"]:
            continue
        revision = opened["result"]["revision"]
        check_version = opened["result"]["check_version"]
        check_id = opened["result"]["check_id"]
        submitted = harness._rpc(
            "attempt.submit",
            {
                "enrollment_id": enrollment_id,
                "check_id": check_id,
                "check_version": check_version,
                "attempt_nonce": f"h30-nonce-{objective['ordinal']}",
                "answer": answer,
            },
            expected_revision=revision,
            key=f"h30-submit-{objective['ordinal']}",
        )
        show(f"attempt.submit[{label}]", submitted)
        if submitted["ok"]:
            revision = submitted["result"].get("revision", revision)

    # What the kernel actually persisted for those attempts.
    from coursebook import db

    with db.read() as connection:
        rows = connection.execute(
            "SELECT id, check_id, state, verdict, evidence_class, grading_provenance_json"
            " FROM attempts WHERE enrollment_id = ? ORDER BY created_at, id",
            (enrollment_id,),
        ).fetchall()
    show("attempt_rows", [dict(row) for row in rows])


if __name__ == "__main__":
    main()
