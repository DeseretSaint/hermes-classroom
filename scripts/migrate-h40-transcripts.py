"""Migrate the recorded harness transcripts to the procedure-verification rule.

A procedure objective is measured by a confirmation checklist of the acts, not by a question about
them. The recordings already carry `example_steps` for every procedure lesson; those steps are the
checklist. This rewrites the two transcripts whose procedure checks were quizzes so the end-to-end
harness exercises the capability the product now enforces, instead of failing on a fixture authored
before the rule existed.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/home/deseretsaint/.hermes/cache/scratch/e2e")
TRANSCRIPTS = ROOT / "audit" / "adversarial" / "harness-e2e" / "transcripts"


def dump(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def migrate(path: Path) -> dict[str, int]:
    document = json.loads(path.read_text(encoding="utf-8"))
    shape = document["shape"]
    titles = {
        objective["title"]: objective["evidence_target"] for objective in shape["objectives"]
    }
    changed_checks = 0
    added_items = 0

    for check in shape["check_plan"]:
        objective = shape["objectives"][int(check["objective_ref"]) - 1]
        if objective["evidence_target"] == "procedure" and check["kind"] != "verification":
            check["kind"] = "verification"
            changed_checks += 1

    for title, recording in document["lessons"].items():
        if titles.get(title) != "procedure" or recording.get("items"):
            continue
        steps = [str(step) for step in (recording.get("example_steps") or []) if str(step).strip()]
        if not steps:
            continue
        recording["items"] = [
            {"id": f"step-{index + 1}", "label": step}
            for index, step in enumerate(steps[:5])
        ]
        added_items += len(recording["items"])

    path.write_text(dump(document) + "\n", encoding="utf-8")
    return {"checks": changed_checks, "items": added_items}


if __name__ == "__main__":
    for transcript in sorted(TRANSCRIPTS.glob("*.json")):
        result = migrate(transcript)
        print(f"{transcript.name}: {result['checks']} check kind(s), {result['items']} item(s)")
