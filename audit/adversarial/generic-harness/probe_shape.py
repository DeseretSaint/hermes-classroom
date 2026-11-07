"""H-30 probe A — deterministic shape and routing gates (read-only, no DB, no provider).

Run from a product checkout:

    PYTHONPATH=. python3 audit/adversarial/generic-harness/probe_shape.py <transcript-plan.json>

It answers, without a model:
  * what objective bounds the plan schema and the plan prompt actually carry per scope;
  * whether a one-objective plan and a twelve-objective plan survive the artifact validator;
  * whether the capability policy routes a non-language topic with a locale, and a language
    topic without a locale, to the right production lane.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from coursebook import generation as gen
from coursebook import policy as cap


def emit(label: str, value) -> None:
    print(f"{label}: {value}")


def plan_from(path: str) -> dict:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return document["transcript"]["plan"]


def reshape(plan: dict, count: int) -> dict:
    """Clone a recorded plan with exactly ``count`` objectives and sections."""
    clone = json.loads(json.dumps(plan))
    source_objectives = list(clone["objectives"])
    source_sections = list(clone["sections"])
    while len(clone["objectives"]) < count:
        template = json.loads(json.dumps(
            source_objectives[len(clone["objectives"]) % len(source_objectives)]
        ))
        template["ordinal"] = len(clone["objectives"]) + 1
        template["title"] = f"{template['title']} (copy {template['ordinal']})"
        clone["objectives"].append(template)
        section = json.loads(json.dumps(
            source_sections[len(clone["sections"]) % len(source_sections)]
        ))
        section["ordinal"] = len(clone["sections"]) + 1
        section["objective_refs"] = [template["ordinal"]]
        clone["sections"].append(section)
    clone["objectives"] = clone["objectives"][:count]
    clone["sections"] = clone["sections"][:count]
    clone["check_plan"] = [
        {
            "objective_ref": i,
            "kind": "verification",
            "evidence_target": clone["objectives"][i - 1]["evidence_target"],
            "count": 1,
            "independent_evidence": False,
        }
        for i in range(1, count + 1)
    ]
    # The rule layer is under test, not the ledger: drop recorded placeholders so the
    # provenance rule does not mask the count question.
    clone["source_ids"] = []
    for section in clone["sections"]:
        section["source_ids"] = []
    for objective in clone["objectives"]:
        objective["source_ids"] = []
        objective["support"] = "unverified"
    return clone


def schema_errors(plan: dict) -> list[str]:
    validator = Draft202012Validator(gen.PLAN_SCHEMA)
    errors = sorted(validator.iter_errors(plan), key=lambda e: list(e.absolute_path))
    return [f"/{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


def schema_verdict(plan: dict) -> str:
    errors = schema_errors(plan)
    if not errors:
        return "ACCEPTED"
    return "REJECTED — " + " | ".join(errors[:3])


def prompt_bounds(scope: str | None, recipe: str) -> str:
    text = gen._plan_instructions(
        recipe=recipe, dials={}, locale="en-US", research_status="available",
        level="beginner", subject_domain="repair", scope=scope,
    )
    for line in text.splitlines():
        if line.startswith("Produce ") and "objectives" in line:
            return line
    return "<no objective-count line>"


def main() -> None:
    plan = plan_from(sys.argv[1])

    print("## scope contract")
    for scope in ("single", "short", "full"):
        emit(f"SCOPE_EXPECTATIONS[{scope!r}]", gen.SCOPE_EXPECTATIONS[scope])
    emit("PLAN_SCHEMA.objectives.minItems", gen.PLAN_SCHEMA["properties"]["objectives"]["minItems"])
    emit("PLAN_SCHEMA.objectives.maxItems", gen.PLAN_SCHEMA["properties"]["objectives"]["maxItems"])
    emit("PLAN_SCHEMA.check_plan.objective_ref.maximum",
         gen.CHECK_PLAN_SCHEMA["properties"]["objective_ref"]["maximum"])
    emit("PLAN_SCHEMA has 'units'", "units" in gen.PLAN_SCHEMA["properties"])
    emit("PLAN_SCHEMA has 'plan_schema'", "plan_schema" in gen.PLAN_SCHEMA["properties"])
    for scope in ("single", "short", "full"):
        emit(f"prompt[{scope}]", prompt_bounds(scope, "committed"))
    emit("prompt[unscoped]", prompt_bounds(None, "committed"))

    print("\n## artifact validator")
    for count in (1, 4, 8, 12):
        emit(f"{count}-objective plan", schema_verdict(reshape(plan, count)))

    print("\n## rule layer (does it enforce the count itself?)")
    for count, scope in ((1, "single"), (12, "full")):
        candidate = reshape(plan, count)
        try:
            gen.enforce_plan_rules(
                candidate, recipe="one_off", dials={}, locale="en-US",
                ledger=[], scope=scope,
            )
        except gen.GenerationRejected as exc:
            emit(f"enforce_plan_rules[{count}, {scope}]", f"REJECTED — {exc}")
        except Exception as exc:  # noqa: BLE001 - a rule crash is the finding
            emit(f"enforce_plan_rules[{count}, {scope}]", f"{type(exc).__name__} — {exc}")
        else:
            emit(f"enforce_plan_rules[{count}, {scope}]", "ACCEPTED")

    print("\n## subject-domain routing")
    emit("normalise(None, None)", cap.normalise_subject_domain(None, None))
    emit("normalise(None, 'es-MX')", cap.normalise_subject_domain(None, "es-MX"))
    emit("normalise('music', 'es-MX')", cap.normalise_subject_domain("music", "es-MX"))
    emit("normalise('language', None)", cap.normalise_subject_domain("language", None))
    emit("normalise('technical_procedure', 'ja-JP')",
         cap.normalise_subject_domain("technical_procedure", "ja-JP"))

    cases = [
        ("non-language topic + locale", dict(
            recipe="committed", evidence_target="comprehension",
            lesson_intent="Explain how a bicycle brake caliper clamps the rim",
            locale="es-MX", subject_domain="music")),
        ("language topic, no locale, no domain", dict(
            recipe="committed", evidence_target="production",
            lesson_intent="Order a meal at a restaurant in Spanish",
            locale=None, subject_domain=None)),
        ("language topic + locale", dict(
            recipe="committed", evidence_target="production",
            lesson_intent="Order a meal at a restaurant in Spanish",
            locale="es-MX", subject_domain=None)),
        ("technical procedure + locale", dict(
            recipe="committed", evidence_target="procedure",
            lesson_intent="Replace the brake pads on a bicycle",
            locale="es-MX", subject_domain="technical_procedure")),
        ("language, pronunciation earned", dict(
            recipe="committed", evidence_target="production",
            lesson_intent="Pronounce 'la cuenta, por favor' with the stress on the right syllable",
            locale="es-MX", subject_domain="language")),
        ("technical, labelled diagram earned", dict(
            recipe="committed", evidence_target="discrimination",
            lesson_intent="Identify the labelled parts of a bicycle brake caliper",
            locale="en-US", subject_domain="technical_procedure")),
    ]
    for name, kwargs in cases:
        decision = cap.plan_lesson_capability(**kwargs)
        emit(name, {
            "domain": decision.subject_domain,
            "image": decision.image, "image_role": decision.image_role,
            "audio": decision.audio, "audio_role": decision.audio_role,
            "rubric_profile": decision.rubric_profile,
        })

    print("\n## media declaration authority (illustration vs schematic)")
    for role, construct in (("illustration", "grip"), ("schematic", "wiring"),
                            ("schematic", "grip")):
        try:
            declared = cap.plan_lesson_capability(
                recipe="committed", evidence_target="procedure",
                lesson_intent="Replace the handlebar grips",
                locale="en-US", subject_domain="technical_procedure",
                media_need={"image": {"level": "required", "role": role},
                            "audio": {"level": "none", "role": "none"},
                            "construct": construct},
            )
        except cap.CapabilityPolicyError as exc:
            emit(f"{role} ({construct}) on a technical procedure", f"REFUSED — {exc}")
        else:
            emit(f"{role} ({construct}) on a technical procedure", {
                "image": declared.image, "role": declared.image_role,
                "reason": declared.reasons[1]})


if __name__ == "__main__":
    main()
