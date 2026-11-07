"""Author one lesson through the real pipeline into a disposable rig home, then read it back.

This probe is the on-disk half of M1-U2:

* goal -> bounded research -> plan -> independent validation -> approved plan -> lesson author ->
  independent lesson validation, executed by ``coursebook.generation`` against a real migrated
  plugin database in a disposable ``HERMES_HOME``, driven through the shipped commands
  (``enrollment.create``, ``plan.approve``) rather than by writing rows by hand;
* the model and search seams are the **deterministic offline adapters** the test suite uses
  (``tests.test_generation.FakeLLM`` / ``FakeSearch``), so no provider is called and no spend is
  recorded. Nothing here claims a provider-authored lesson;
* the objective is then read through ``api.dispatch``, the same dispatcher the plugin route uses,
  so the ``lesson.page.document`` captured is the output of the shipped handler.

usage: M1U_RIG=<rig dir> python3 scripts/m1u-guided-probe.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
RIG = Path(os.environ["M1U_RIG"])
os.environ["HERMES_HOME"] = str(RIG / "home")
os.environ["HERMES_COURSEBOOK_SINGLE_HOME"] = "1"
sys.path.insert(0, str(REPO))

from coursebook import api, db, domain, generation as gen  # noqa: E402
from tests.kernel_support import request  # noqa: E402
from tests.test_generation import (  # noqa: E402
    FakeLLM,
    FakeSearch,
    lesson_from_request,
    plan_from_fixture,
    plan_job,
    validation_from_fixture,
)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


def dispatch(
    method: str, payload: dict[str, Any], *, expected_revision: int | None = None
) -> dict[str, Any]:
    response = api.dispatch(request(method, payload, expected_revision=expected_revision))
    if not response.get("ok"):
        raise SystemExit(f"{method} failed: {response.get('error')}")
    return response["result"]


def objective_for_check(check_id: str) -> dict[str, Any] | None:
    with db.read() as connection:
        row = connection.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
        if row is None:
            return None
        objective = connection.execute(
            "SELECT * FROM objectives WHERE id = ?", (row["objective_id"],)
        ).fetchone()
    return dict(objective) if objective is not None else None


def main() -> None:
    db.migrate()
    llm = FakeLLM(
        {
            "coursebook.plan.generate": plan_from_fixture(),
            "coursebook.plan.validate": validation_from_fixture(),
            "coursebook.lesson.generate": lesson_from_request(),
            "coursebook.lesson.validate": validation_from_fixture(),
        }
    )
    with db.transaction() as connection:
        plan_result = gen.run_plan_job(
            connection, plan_job(job_id="job-m1u-plan"), llm, FakeSearch(), now=NOW
        )
    plan_id = plan_result["plan_id"]
    course_id = plan_result["course_id"]

    enrollment_id = dispatch(
        "enrollment.create", {"course_id": course_id, "learner_label": "Learner"}
    )["enrollment_id"]
    dispatch(
        "plan.approve",
        {
            "enrollment_id": enrollment_id,
            "plan_id": plan_id,
            "plan_hash": domain.plan_hash(plan_id),
        },
        expected_revision=0,
    )
    with db.transaction() as connection:
        lesson_result = gen.run_lesson_job(
            connection,
            {"job_id": "job-m1u-lesson", "kind": "plan", "brief": {"plan_id": plan_id}},
            llm,
            now=NOW,
            budget=gen.CostBudget(max_calls=32),
        )

    objective = None
    for item in lesson_result["lessons"]:
        objective = objective_for_check(item["check_id"])
        if objective is not None:
            break
    if objective is None:
        raise SystemExit("no objective found for the authored lessons")

    page = dispatch(
        "lesson.page", {"enrollment_id": enrollment_id, "objective_id": objective["id"]}
    )
    document = page["document"]
    evidence = {
        "rig_home": str(RIG / "home"),
        "plugin_root": str((RIG / "home" / "plugins" / "coursebook").resolve()),
        "authoring": {
            "adapter": "tests.test_generation.FakeLLM / FakeSearch (deterministic, offline)",
            "provider_call": False,
            "spend": "none: no provider was called and no cost was recorded",
            "plan_id": plan_id,
            "plan_validation": plan_result["validation_verdict"],
            "lesson_states": [item["state"] for item in lesson_result["lessons"]],
            "lesson_validations": [item["validation_verdict"] for item in lesson_result["lessons"]],
            "prompt_version": gen.LESSON_PROMPT_VERSION,
        },
        "lesson_page": {
            "enrollment_id": enrollment_id,
            "objective_id": objective["id"],
            "state": document["state"],
            "views": document["views"],
            "view_note": document["view_note"],
            "block_roles": [block["role"] for block in document["blocks"]],
            "block_shorts": [block["short"] for block in document["blocks"]],
            "block_headlines": [block["headline"] for block in document["blocks"]],
            "check_id": document["check_id"],
            "blocks_claiming_the_check": [
                index for index, block in enumerate(document["blocks"]) if block["check_id"]
            ],
            "content_hash": document["content_hash"],
            "segment_kinds": [segment["kind"] for segment in page["segments"]],
        },
    }
    target = REPO / "audit" / "visual" / "m1-guided-authoring" / "pipeline-evidence.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
