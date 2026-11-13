"""Blueprint v2 fixtures shared by the unit-stage tests and the scoped plan test.

Every document is hand-built here, never copied from a provider. The rules pass because the
fields are honest (no invented URL, no sourced claim without a ledger row), not because the
builder bypasses a check.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence

from coursebook import generation as gen

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def media_none() -> dict[str, Any]:
    return {
        "construct": "",
        "image": {"level": "none", "role": "none"},
        "audio": {"level": "none", "role": "none"},
    }


def blueprint_plan(
    *,
    scope: str = "single",
    units: int = 1,
    objectives_per_unit: int = 1,
    recipe: str = "casual",
    check_kind: str | None = None,
    reviews: Sequence[int] = (),
    spaced_review: bool | None = None,
) -> dict[str, Any]:
    """A schema-valid ``coursebook.plan.v2`` document.

    ``reviews`` is the per-unit review section count (one entry per unit). ``target_lessons`` is
    the unit's objective count plus its review count, which is what the unit stage must author.
    """
    if check_kind is None:
        check_kind = "verification" if recipe == "one_off" else "quiz"
    if spaced_review is None:
        spaced_review = recipe == "committed"
    if spaced_review and not reviews:
        # S3: a spaced-review course schedules at least one review per unit. The plan rule
        # requires one per SPACED_REVIEW_EVERY owners; one per unit is the simplest fixture that
        # satisfies it without changing any unit's owner count.
        reviews = tuple(1 for _ in range(units))
    unit_rows: list[dict[str, Any]] = []
    objective_rows: list[dict[str, Any]] = []
    check_rows: list[dict[str, Any]] = []
    target = "procedure" if recipe == "one_off" else "comprehension"
    ordinal = 1
    for unit_ordinal in range(1, units + 1):
        review_count = int(reviews[unit_ordinal - 1]) if unit_ordinal - 1 < len(reviews) else 0
        unit_rows.append(
            {
                "ordinal": unit_ordinal,
                "title": f"Unit {unit_ordinal}: a distinct phase",
                "goal": f"Unit {unit_ordinal} makes the next part of the goal possible.",
                "prereq_unit_ordinals": [unit_ordinal - 1] if unit_ordinal > 1 else [],
                "target_lessons": objectives_per_unit + review_count,
            }
        )
        for _ in range(objectives_per_unit):
            objective_rows.append(
                {
                    "ordinal": ordinal,
                    "unit_ref": unit_ordinal,
                    "title": f"Objective {ordinal}: do the observable thing",
                    # A one-off brief is one verifiable task, and its check is a verification
                    # checklist; the evidence target has to be the act itself, not a quiz about
                    # it (the plan rule compares the two).
                    "evidence_target": target,
                    "evidence_criteria": [
                        "Shows the behaviour in a fresh example without prompting"
                    ],
                    "support": "unverified",
                }
            )
            check_rows.append(
                {
                    "objective_ref": ordinal,
                    "kind": check_kind,
                    "evidence_target": target,
                }
            )
            ordinal += 1
    weeks = {"single": 1, "short": 8, "full": 24}.get(scope, 24)
    plan: dict[str, Any] = {
        "plan_schema": gen.PLAN_SCHEMA_V2_NAME,
        "scope": scope,
        "title": "A scoped course",
        "learner_outcome": "The learner can do the thing this course is about.",
        # H-195: a plan states its arc and its starting assumptions.
        "through_line": (
            "Each unit adds one observable move, and every later unit uses the move the previous "
            "unit taught."
        ),
        "prerequisite_assumptions": [
            "The learner can read the course's own language of delivery.",
            "No prior knowledge of the subject is assumed.",
        ],
        "delivery": "self_study",
        "time_estimate": {
            "sessions_per_week": 2,
            "minutes_per_session": 45,
            "weeks": weeks,
            "basis": "none",
            "confidence": "low",
            "rationale": "A planning estimate, not an attainment claim.",
        },
        "units": unit_rows,
        "objectives": objective_rows,
        "check_plan": check_rows,
        "context_needs": ["romaji scaffold while the learner reads kana"],
        "source_ids": [],
        "exclusions": ["Nothing beyond the stated learner outcome is claimed"],
        "spaced_review": spaced_review,
    }
    if recipe in ("casual", "one_off"):
        plan["evidence_note"] = (
            "A casual/one-off course: checks are self-reported and never independent evidence."
        )
    if scope == "full":
        # S1: a full course ends on its exit performance. The fixture's last owner section owns
        # the final objective, so that objective carries the procedure family and its check the
        # verification kind a procedure needs.
        final = plan["objectives"][-1]
        final["evidence_target"] = "procedure"
        for item in plan["check_plan"]:
            if int(item["objective_ref"]) == int(final["ordinal"]):
                item["evidence_target"] = "procedure"
                item["kind"] = "verification"
    return plan


def unit_sections_document(
    *,
    unit: dict[str, Any],
    objectives: Sequence[dict[str, Any]],
    reviews: int = 0,
) -> dict[str, Any]:
    """A schema-valid unit-sections document for one unit."""
    sections: list[dict[str, Any]] = []
    for index, objective in enumerate(objectives, start=1):
        sections.append(
            {
                "ordinal": index,
                "unit_ref": int(unit["ordinal"]),
                "role": "owner",
                "primary_objective_ref": int(objective["ordinal"]),
                "reinforces": [],
                "title": f"Lesson {objective['ordinal']}: the observable thing",
                "lesson_intent": (
                    "Carry the construct the objective names so a cold attempt can show it."
                ),
                "context_needs": ["a quiet place to answer"],
                "source_ids": [],
                "media_need": media_none(),
            }
        )
    for extra in range(1, reviews + 1):
        # CP-015f: one owner check serves one review section, so no objective may appear in two
        # reviews. The objectives are split across the reviews, each landing in exactly one, so a
        # fixture batch is always one the rule gate accepts (and `reviews > objectives` is empty
        # by construction, which is the honest shape of an impossible unit).
        start = (extra - 1) * len(objectives) // reviews
        end = extra * len(objectives) // reviews
        refs = [int(obj["ordinal"]) for obj in objectives[start:end]]
        sections.append(
            {
                "ordinal": len(sections) + 1,
                "unit_ref": int(unit["ordinal"]),
                "role": "review",
                "primary_objective_ref": None,
                "reinforces": refs,
                "title": f"Review {extra}: retrieval of earlier work",
                "lesson_intent": (
                    "Retrieve the earlier objective with its existing check, without reteaching."
                ),
                "context_needs": ["a quiet place to answer"],
                "source_ids": [],
                "media_need": media_none(),
            }
        )
    return {"unit_ref": int(unit["ordinal"]), "sections": sections}


def response(payload: dict, *, model: str = "fake-model") -> gen.LLMResponse:
    return gen.LLMResponse(
        text=json.dumps(payload, ensure_ascii=False),
        parsed=payload,
        provider="fake",
        model=model,
        input_tokens=120,
        output_tokens=240,
    )


def narrowed_validation_answer(request: gen.LLMRequest, document: dict[str, Any]) -> dict[str, Any]:
    """Align a fixture's validation answer with the schema the pass was actually handed.

    H-192b/H-192c split plan validation into bounded passes and narrow both ``criteria`` and
    ``claim_verdicts`` to exactly the batch in the request (``minItems == maxItems``). A fixture
    authored against the wide ten-criterion schema is therefore not a legal answer to a narrowed
    pass: it returns ten criteria where five were asked for, and no claim verdict where one per
    label is required. This derives both id sets from the request schema, keeps any verdict the
    fixture already carries for an id in the batch, and fills the rest from the request's own
    vocabulary — the same thing the live validator is told to do.
    """
    properties = (request.schema or {}).get("properties", {})
    aligned = json.loads(json.dumps(document))

    criteria_enum = (
        (((properties.get("criteria") or {}).get("items") or {})
         .get("properties", {}).get("id", {})).get("enum")
        or []
    )
    if criteria_enum:
        by_id = {
            entry.get("id"): entry
            for entry in aligned.get("criteria") or []
            if isinstance(entry, dict)
        }
        aligned["criteria"] = [
            by_id.get(criterion)
            or {
                "id": criterion,
                "verdict": "pass",
                "reason": "nothing in the artifact contradicts this criterion",
            }
            for criterion in criteria_enum
        ]
        rejections = aligned.get("rejections")
        if isinstance(rejections, list):
            # A rejection names a criterion, and the pass narrowed that vocabulary too: a batch
            # may only reject inside its own batch.
            aligned["rejections"] = [
                entry
                for entry in rejections
                if not isinstance(entry, dict) or entry.get("criterion") in criteria_enum
            ]
        # ``t_0affea08``: a pass owns only its own five criteria, so its declared verdict has to
        # be re-derived after narrowing. A fixture that rejects a pass-2 criterion leaves pass 1
        # with every own criterion ``pass`` and no rejection; carrying its ``reject`` over would
        # answer pass 1 incoherently — a verdict naming nothing it judged, which
        # ``_parse_validation_answer`` now types as VALIDATION_FAILED. The live validator answers
        # each pass on its own batch, so this is the same derivation it is told to make; the
        # refusing pass keeps its ``reject`` and the merge still makes the review a refusal.
        if str(aligned.get("verdict")) != "pass":
            grounded = any(
                isinstance(entry, dict) and str(entry.get("verdict")) != "pass"
                for entry in aligned["criteria"]
            ) or bool(aligned["rejections"])
            if not grounded:
                aligned["verdict"] = "pass"

    claim_enum = (
        (((properties.get("claim_verdicts") or {}).get("items") or {})
         .get("properties", {}).get("item", {})).get("enum")
        or []
    )
    if claim_enum:
        by_item = {
            entry.get("item"): entry
            for entry in aligned.get("claim_verdicts") or []
            if isinstance(entry, dict)
        }
        aligned["claim_verdicts"] = [
            by_item.get(label)
            or {"item": label, "support": "unverified", "reason": "not assessed by this fixture"}
            for label in claim_enum
        ]
    elif "claim_verdicts" in aligned:
        # The pass schema carries no claim_verdicts and is additionalProperties: False.
        aligned.pop("claim_verdicts")
    return aligned


def validation_responder(responder, document: dict[str, Any], *, model: str | None = None):
    """Wrap a constant validation document in a responder aligned to the pass it answers.

    H-192b/H-192c narrow each plan-validation pass to its own criteria and claim batch, so a
    constant answer authored against the wide schema is not schema-valid for a narrowed pass.
    This keeps the call sites' model naming while answering the request that was actually made.
    """

    def build(request: gen.LLMRequest):
        aligned = narrowed_validation_answer(request, document)
        return responder(aligned, model=model) if model else responder(aligned)

    return build


def validation_pass() -> dict[str, Any]:
    return {
        "verdict": "pass",
        "criteria": [
            {
                "id": name,
                "verdict": "pass",
                "reason": "nothing in the artifact contradicts this criterion",
            }
            for name in gen.VALIDATION_CRITERIA
        ],
        "rejections": [],
    }


def validation_answer(request: gen.LLMRequest) -> dict[str, Any]:
    """Answer exactly the pass handed in (H-192 splits large plans into bounded passes).

    A claim-only pass has no criteria in its narrowed schema, so the ten-criterion document is not
    a legal answer for it; this derives the claim set from the request like the live validator.
    A criteria pass may also own a claim batch, so the criteria answer is aligned to whatever the
    schema narrowed to rather than assumed wide.
    """
    properties = (request.schema or {}).get("properties", {})
    if "criteria" in properties:
        return narrowed_validation_answer(request, validation_pass())
    labels = (
        ((properties.get("claim_verdicts") or {}).get("items") or {})
        .get("properties", {})
        .get("item", {})
        .get("enum")
        or []
    )
    return {
        "claim_verdicts": [
            {"item": label, "support": "unverified", "reason": "not assessed by this fixture"}
            for label in labels
        ]
    }
