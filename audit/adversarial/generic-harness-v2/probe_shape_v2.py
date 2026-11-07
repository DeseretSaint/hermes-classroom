"""H-30b probe A — the v2 schema/prompt bounds the shipped product actually carries.

Read-only, no DB, no provider. This replaces the H-30 probe for the blueprint contract: the
contract moved (PLAN_SCHEMA v2), so the old probe's `gen.PLAN_SCHEMA` reads were v1-only.

Run from the product checkout:

    PYTHONPATH=. python3 audit/adversarial/generic-harness-v2/probe_shape_v2.py
"""

from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from coursebook import generation as gen
from coursebook import policy as cap


def emit(label: str, value) -> None:
    print(f"{label}: {value}")


def schema_errors(schema: dict, document: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    return [f"/{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


def verdict(schema: dict, document: dict) -> str:
    errors = schema_errors(schema, document)
    return "ACCEPTED" if not errors else "REJECTED — " + " | ".join(errors[:3])


def objective(ordinal: int, unit_ref: int = 1, target: str = "procedure") -> dict:
    return {
        "ordinal": ordinal,
        "unit_ref": unit_ref,
        "title": f"Perform step {ordinal} of the task with the named tool",
        "evidence_target": target,
        "evidence_criteria": [f"Step {ordinal} completed without forcing a part"],
        "support": "unverified",
        "source_ids": [],
    }


def unit(ordinal: int, prereqs: list[int] | None = None, lessons: int = 1) -> dict:
    return {
        "ordinal": ordinal,
        "title": f"Unit {ordinal} of the course",
        "goal": f"Unit {ordinal} makes the next body of work possible",
        "prereq_unit_ordinals": list(prereqs or []),
        "target_lessons": lessons,
    }


def check(ordinal: int, kind: str = "quiz", target: str = "procedure") -> dict:
    return {"objective_ref": ordinal, "kind": kind, "evidence_target": target}


def plan_document(scope: str, units: list[dict], objectives: list[dict], checks: list[dict],
                  recipe: str = "committed", weeks: int = 4) -> dict:
    return {
        "plan_schema": gen.PLAN_SCHEMA_V2_NAME,
        "scope": scope,
        "title": f"A {scope} course on an arbitrary non-Japanese topic",
        "learner_outcome": "The learner can do the task or explain the concept without notes.",
        "delivery": "self_study",
        "time_estimate": {
            "sessions_per_week": 2,
            "minutes_per_session": 60,
            "weeks": weeks,
            "basis": "none",
            "confidence": "low",
            "rationale": "Authored estimate; no benchmark transfer claim.",
            "benchmark": None,
            "attainment_hours": None,
        },
        "units": units,
        "objectives": objectives,
        "check_plan": checks,
        "context_needs": ["the actual equipment or textbook"],
        "source_ids": [],
        "exclusions": ["Does not certify competence; a supervisor checks the first attempt."],
        "spaced_review": recipe != "one_off",
        "evidence_note": None,
    }


def try_rules(document: dict, *, scope: str, recipe: str) -> str:
    try:
        gen.enforce_plan_rules(
            document, recipe=recipe, dials={}, locale="en-US", ledger=[], scope=scope,
        )
    except gen.GenerationRejected as exc:
        return f"REJECTED — {exc}"
    except Exception as exc:  # noqa: BLE001 - a crash is the finding
        return f"{type(exc).__name__} — {exc}"
    return "ACCEPTED"


def prompt_lines(scope: str) -> dict:
    """What the v2 plan request actually tells the model, per scope."""
    from coursebook.research import ResearchRun

    run = ResearchRun(
        status="unavailable", reason="probe", queries=[], sources=[],
    )
    request = gen.build_plan_request(
        goal="an arbitrary non-Japanese goal", recipe="committed", dials={}, locale="en-US",
        research_run=run, scope=scope, level="beginner", subject_domain="repair",
    )
    payload = json.loads(request.input_text)
    return {
        "schema_name": request.schema_name,
        "prompt_version": request.prompt_version,
        "max_tokens": request.max_tokens,
        "rules_objective_count": payload["rules"]["objective_count"],
        "rules_unit_count": payload["rules"]["unit_count"],
        "rules_unit_objective_count": payload["rules"]["unit_objective_count"],
        "schema_objectives_min": request.schema["properties"]["objectives"]["minItems"],
        "schema_objectives_max": request.schema["properties"]["objectives"]["maxItems"],
        "schema_units_min": request.schema["properties"]["units"]["minItems"],
        "schema_units_max": request.schema["properties"]["units"]["maxItems"],
        "instructions_line": next(
            (line for line in request.instructions.splitlines() if "objective" in line.lower()
             and any(word in line.lower() for word in ("produce", "exactly"))),
            "<none>",
        ),
    }


def main() -> None:
    print("## scope contract (v2 blueprint)")
    for scope in ("single", "short", "full"):
        emit(f"SCOPE_EXPECTATIONS[{scope!r}].blueprint_objectives",
             gen.SCOPE_EXPECTATIONS[scope]["blueprint_objectives"])
        emit(f"SCOPE_EXPECTATIONS[{scope!r}].blueprint_units",
             gen.SCOPE_EXPECTATIONS[scope]["blueprint_units"])
        emit(f"prompt[{scope}]", prompt_lines(scope))

    print("\n## legacy v1 bounds (unchanged, for stored documents only)")
    emit("PLAN_SCHEMA.objectives.minItems", gen.PLAN_SCHEMA["properties"]["objectives"]["minItems"])
    emit("PLAN_SCHEMA.objectives.maxItems", gen.PLAN_SCHEMA["properties"]["objectives"]["maxItems"])
    emit("PLAN_SCHEMA has 'units'", "units" in gen.PLAN_SCHEMA["properties"])

    print("\n## v2 artifact validator")
    one = plan_document(
        "single", [unit(1, lessons=1)], [objective(1)], [check(1, "verification")],
        recipe="one_off", weeks=1,
    )
    four = plan_document(
        "short", [unit(1, lessons=2), unit(2, [1], lessons=2)],
        [objective(1), objective(2), objective(3, 2), objective(4, 2)],
        [check(1), check(2), check(3), check(4)],
        weeks=3,
    )
    twelve = plan_document(
        "full", [unit(1, lessons=4), unit(2, [1], lessons=4), unit(3, [2], lessons=4)],
        [objective(i, 1 if i <= 4 else 2 if i <= 8 else 3) for i in range(1, 13)],
        [check(i, kind="quiz") for i in range(1, 13)],
        weeks=6,
    )
    for label, document in (("1-objective single plan", one), ("4-objective short plan", four),
                            ("12-objective full plan", twelve)):
        emit(label, verdict(gen.PLAN_SCHEMA_V2, document))
        emit(f"{label} rule layer", try_rules(
            document, scope=document["scope"],
            recipe="one_off" if document["scope"] == "single" else "committed",
        ))

    print("\n## the measured `full` ceiling (40 objectives, docs/PLAN-CEILING.md)")
    forty_units = [unit(i, [i - 1] if i > 1 else [], lessons=4) for i in range(1, 11)]
    forty = plan_document(
        "full", forty_units,
        [objective(i, (i - 1) // 4 + 1) for i in range(1, 41)],
        [check(i, kind="quiz") for i in range(1, 41)],
        weeks=20,
    )
    emit("40-objective full plan", verdict(gen.PLAN_SCHEMA_V2, forty))
    emit("40-objective full plan rule layer", try_rules(forty, scope="full", recipe="committed"))
    forty_one = plan_document(
        "full", forty_units,
        [objective(i, (i - 1) // 4 + 1) for i in range(1, 42)],
        [check(i, kind="quiz") for i in range(1, 42)],
        weeks=20,
    )
    emit("41-objective full plan (over the declared cap)", verdict(gen.PLAN_SCHEMA_V2, forty_one))

    print("\n## v2 refuses what v1 required")
    padded = plan_document(
        "single", [unit(1, lessons=4)],
        [objective(i) for i in range(1, 5)],
        [check(i, "verification") for i in range(1, 5)],
        recipe="one_off", weeks=1,
    )
    emit("4-objective single plan rule layer", try_rules(padded, scope="single", recipe="one_off"))

    short_bad = plan_document(
        "short", [unit(1, lessons=2)],
        [objective(1, 1, "comprehension"), objective(2, 1, "comprehension")],
        [check(1, kind="quiz", target="comprehension"), check(2, kind="quiz", target="comprehension")],
        weeks=3,
    )
    emit("2-objective short plan rule layer", try_rules(short_bad, scope="short", recipe="committed"))

    print("\n## subject-domain routing (unchanged contract)")
    for label, kwargs in (
        ("non-language topic + locale", dict(
            recipe="committed", evidence_target="comprehension",
            lesson_intent="Explain how a bicycle brake caliper clamps the rim",
            locale="es-MX", subject_domain="music")),
        ("language topic, no locale, no domain", dict(
            recipe="committed", evidence_target="production",
            lesson_intent="Order a meal at a restaurant in Spanish",
            locale=None, subject_domain=None)),
    ):
        decision = cap.plan_lesson_capability(**kwargs)
        emit(label, {"domain": decision.subject_domain, "rubric_profile": decision.rubric_profile})


if __name__ == "__main__":
    main()
