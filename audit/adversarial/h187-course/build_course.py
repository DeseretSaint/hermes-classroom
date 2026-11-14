#!/usr/bin/env python3
"""H-187 course preparation: two hand-authored courses with explicit media requirements.

This does NOT generate media. It builds real course/plan/section/lesson rows in a real,
migrated SQLite store through the product's public commands (course.create, enrollment.create,
domain.record_objective, plan.approve) and the product schema, then serves each page through
``lesson.page`` and records what each page says.

The lesson prose is authored here (a preparation script), not by a model authoring pass. The
gen_lessons rows carry state ``model_assessed`` only because that is the state the media caller
(``media.generate_for_lessons``) and ``lesson.page`` admit; ``validation_id`` is NULL and the
served provenance says "model assessed, not independently validated: treat this page as a
proposal." No live model call, no validation claim and no media bytes are produced here.

Two courses, not one: the capability policy decides audio from a language plan and a schematic
from a non-language plan, and one plan carries one domain. A mixed-domain single course is not a
shape this product can author; the pair is the deliverable.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ac36aad4")
HOME = Path.home() / ".hermes" / "h187-course" / "home"
EVIDENCE = REPO / "audit" / "adversarial" / "h187-course"

os.environ["HERMES_HOME"] = str(HOME)
sys.path.insert(0, str(REPO))

from coursebook import api, artifacts, contracts, db, domain, generation, media, policy  # noqa: E402

CONTRACT = "cb.rpc"
VERSION = contracts.WIRE_CONTRACT_VERSION


def request(method: str, payload: dict, *, expected_revision=None, key: str | None = None) -> dict:
    body = {
        "contract": CONTRACT,
        "contract_version": VERSION,
        "method": method,
        "operation_id": f"h187prep-{method.replace('.', '-')}",
        "payload": payload,
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    if key:
        body["idempotency_key"] = key
    response = api.dispatch(body)
    if not response.get("ok"):
        raise RuntimeError(f"{method} refused: {json.dumps(response.get('error'))}")
    return response["result"]


MEDIA_SPECS = {}


def lesson_page(section_title, intent, segments, example, explanation, explanation_short,
                media_items, lang=None, direction=None):
    page = {
        "section_title": section_title,
        "lesson_intent": intent,
        "segments": segments,
        "worked_example": example,
        "learner_explanation": explanation,
        "learner_explanation_short": explanation_short,
        "sources": [],
        "media": media_items,
        "parent_notes": None,
        "supervision_notes": [],
    }
    if lang:
        page["lang"] = lang
        page["direction"] = direction or "ltr"
    return page


AUDIO_SPEC = {
    "kind": "audio",
    "role": "narration",
    "purpose": "Hear こんにちは said clearly",
    "spec": "A clear, unhurried pronunciation of the Japanese daytime greeting こんにちは "
            "(konnichiwa) by a standard-Japanese voice, one item only.",
    "text_equivalent": "こんにちは (konnichiwa) — the standard daytime greeting, hello / good afternoon.",
    "transcript": "こんにちは",
    "language": "ja-JP",
    "voice": "default",
    "degraded": True,
    "reason": "not generated yet; this task declares the requirement and does not produce bytes",
}

SCHEMATIC_SPEC = {
    "kind": "visual",
    "role": "schematic",
    "purpose": "See the four-bolt cross pattern in order",
    "spec": "A four-row table of the cross-pattern wheel-bolt order, no torque values.",
    "text_equivalent": "Four steps: 1 front-left bolt, 2 rear-right bolt, 3 front-right bolt, "
                       "4 rear-left bolt.",
    "facts": {
        "rows": [
            {"label": "Step 1", "value": "Front-left bolt"},
            {"label": "Step 2", "value": "Rear-right bolt"},
            {"label": "Step 3", "value": "Front-right bolt"},
            {"label": "Step 4", "value": "Rear-left bolt"},
        ]
    },
    "technical": True,
    "degraded": True,
    "reason": "not generated yet; this task declares the requirement and does not produce bytes",
}

ILLUSTRATION_SPEC = {
    "kind": "visual",
    "role": "illustration",
    "purpose": "See the bench layout before starting",
    "spec": "An editorial illustration of a bicycle wheel clamped upright in a workshop stand, "
            "a torque wrench laid beside it on the bench; no text labels, no measurement claims.",
    "text_equivalent": "A workshop bench: the bicycle wheel is clamped upright in the stand and "
                       "the torque wrench lies beside it.",
    "technical": False,
    "degraded": True,
    "reason": "not generated yet; this task declares the requirement and does not produce bytes",
}


COURSES = [
    {
        "key": "lang",
        "title": "Bike-shop Japanese: greet and say it aloud",
        "goal": "Greet a bike-shop worker in polite Japanese and say the greeting aloud from a "
                "clear pronunciation model.",
        "recipe": "committed",
        "locale": "ja",
        "level": "L0",
        "subject_domain": "language",
        "scope": "single",
        "dials": {"pace": "light", "depth": "working", "assessment": "none", "autonomy": "guided"},
        "lessons": [
            {
                "ordinal": 1,
                "objective_title": "Greet shop staff with こんにちは and say it aloud",
                "evidence_target": "production",
                "section_title": "Greet the staff with こんにちは",
                "lesson_intent": "Say the Japanese daytime greeting こんにちは aloud from a clear "
                                 "pronunciation model.",
                "media_need": {
                    "construct": "pronounce the greeting こんにちは aloud from a clear model",
                    "image": {"level": "none", "role": "none"},
                    "audio": {"level": "required", "role": "pronunciation_reference"},
                },
                "media": [AUDIO_SPEC],
                "page": lesson_page(
                    section_title="Greet the staff with こんにちは",
                    intent="Say the Japanese daytime greeting こんにちは aloud from a clear "
                           "pronunciation model.",
                    segments=[
                        {
                            "kind": "model",
                            "heading": "The greeting in kana and romaji",
                            "body": "こんにちは (konnichiwa) is the standard daytime greeting in "
                                    "Japanese. It is written こ・ん・に・ち・は; in this fixed "
                                    "greeting the final は is pronounced wa. Say it evenly: "
                                    "ko-n-ni-chi-wa.",
                            "short": "こんにちは (konnichiwa) is the daytime greeting; the final は "
                                     "is pronounced wa here.",
                        },
                        {
                            "kind": "explain",
                            "heading": "When to say it",
                            "body": "Say it when you enter a shop or meet someone during the day. "
                                    "It opens the interaction; it is neither a request nor a "
                                    "farewell.",
                            "short": "Use it on entering or meeting someone in the daytime: it "
                                     "opens the interaction.",
                        },
                        {
                            "kind": "guided",
                            "heading": "Say it back",
                            "body": "Play the pronunciation reference and repeat こんにちは three "
                                    "times, matching the rhythm ko-n-ni-chi-wa. The recording is "
                                    "the model; your own saying is the practice, and this page "
                                    "does not assess pronunciation.",
                            "short": "Play the reference, then repeat こんにちは three times at the "
                                     "same rhythm.",
                        },
                    ],
                    example={
                        "prompt": "A staff member looks up as you enter the shop. What do you say?",
                        "steps": [
                            "Choose the daytime greeting rather than a request or a farewell",
                            "Form the five sounds ko-n-ni-chi-wa",
                            "Say it once, clearly, as you enter",
                        ],
                        "answer": "こんにちは (konnichiwa)",
                        "short": "Enter, then say konnichiwa once, clearly.",
                    },
                    explanation="こんにちは (konnichiwa) is the standard daytime greeting. The final "
                                "は in this fixed greeting is pronounced wa. Romaji is a scaffold "
                                "while you learn the sounds, not a second answer.",
                    explanation_short="こんにちは is the daytime greeting; は sounds as wa here.",
                    media_items=[AUDIO_SPEC],
                    lang="ja",
                ),
            }
        ],
    },
    {
        "key": "tech",
        "title": "Workshop procedure: torque a wheel in a cross pattern",
        "goal": "Tighten a bicycle wheel's four bolts in the safe cross sequence, checking the "
                "order before applying force.",
        "recipe": "committed",
        "locale": None,
        "level": None,
        "subject_domain": "technical_procedure",
        "scope": "single",
        "dials": {"pace": "light", "depth": "working", "assessment": "none", "autonomy": "guided"},
        "lessons": [
            {
                "ordinal": 1,
                "objective_title": "Tighten the four wheel bolts in the cross sequence",
                "evidence_target": "procedure",
                "section_title": "Torque the four wheel bolts in the cross pattern",
                "lesson_intent": "Follow the four-step cross pattern that tightens opposite wheel "
                                 "bolts in turn.",
                "media_need": {
                    "construct": "a labelled sequence showing the four wheel bolts and the "
                                 "cross-pattern tightening order",
                    "image": {"level": "required", "role": "schematic"},
                    "audio": {"level": "none", "role": "none"},
                },
                "media": [SCHEMATIC_SPEC],
                "page": lesson_page(
                    section_title="Torque the four wheel bolts in the cross pattern",
                    intent="Follow the four-step cross pattern that tightens opposite wheel bolts "
                           "in turn.",
                    segments=[
                        {
                            "kind": "model",
                            "heading": "The cross pattern",
                            "body": "Work in opposite pairs: front-left first, then rear-right, "
                                    "then front-right, then rear-left. The schematic lists the same "
                                    "four steps in the same order.",
                            "short": "Tighten front-left, rear-right, front-right, rear-left.",
                        },
                        {
                            "kind": "explain",
                            "heading": "Why opposite pairs",
                            "body": "Alternating opposite bolts distributes the load across the "
                                    "wheel instead of drawing one side down first. Follow the order "
                                    "the schematic shows rather than working around the rim.",
                            "short": "Opposite pairs spread the load instead of pulling one side "
                                     "down first.",
                        },
                        {
                            "kind": "guided",
                            "heading": "Follow the sequence at the wheel",
                            "body": "Before applying force, point to each bolt in the schematic "
                                    "order and name it. Stop if a bolt will not seat by hand: that "
                                    "is a condition to check, not a reason to force it.",
                            "short": "Point to each bolt in schematic order and name it before "
                                     "tightening; stop if a bolt will not seat by hand.",
                        },
                    ],
                    example={
                        "prompt": "You have tightened the front-left bolt. Which bolt is next?",
                        "steps": [
                            "Read the schematic order: front-left is step 1",
                            "The next step is the opposite bolt",
                            "Name it: rear-right",
                        ],
                        "answer": "the rear-right bolt",
                        "short": "After front-left, the opposite bolt: rear-right.",
                    },
                    explanation="The order is the evidence here: front-left, rear-right, "
                                "front-right, rear-left. The schematic restates exactly those four "
                                "rows and adds no torque figure.",
                    explanation_short="Follow the four schematic rows in order, opposite pairs.",
                    media_items=[SCHEMATIC_SPEC],
                ),
            },
            {
                "ordinal": 2,
                "objective_title": "Recognise the workshop bench layout before starting",
                "evidence_target": "comprehension",
                "section_title": "Before you start: the bench layout",
                "lesson_intent": "Recognise the wheel stand and the torque wrench on the bench "
                                 "before the procedure begins.",
                "media_need": {
                    "construct": "a workshop scene showing the bicycle wheel clamped in the stand "
                                 "beside the torque wrench",
                    "image": {"level": "optional", "role": "illustration"},
                    "audio": {"level": "none", "role": "none"},
                },
                "media": [ILLUSTRATION_SPEC],
                "page": lesson_page(
                    section_title="Before you start: the bench layout",
                    intent="Recognise the wheel stand and the torque wrench on the bench before "
                           "the procedure begins.",
                    segments=[
                        {
                            "kind": "model",
                            "heading": "The bench, described",
                            "body": "The wheel is clamped upright in the stand. The torque wrench "
                                    "lies on the bench beside it, within reach and not on the "
                                    "floor.",
                            "short": "Wheel clamped in the stand; torque wrench on the bench "
                                     "beside it.",
                        },
                        {
                            "kind": "explain",
                            "heading": "Why the layout matters",
                            "body": "A clamped wheel stays still while both hands work, and a "
                                    "wrench within reach is not left on the floor where it can be "
                                    "kicked or lost.",
                            "short": "A clamped wheel stays still; a wrench in reach is not left on "
                                     "the floor.",
                        },
                        {
                            "kind": "guided",
                            "heading": "Check your own bench",
                            "body": "Look at the illustration, then at your own bench: is the wheel "
                                    "clamped, and is the wrench beside it? Name anything that is "
                                    "not in place before you start.",
                            "short": "Compare your bench to the illustration and name anything out "
                                     "of place.",
                        },
                    ],
                    example={
                        "prompt": "Where should the torque wrench be before you start?",
                        "steps": [
                            "Look at the bench, not the floor",
                            "Find the tool within reach of the clamped wheel",
                        ],
                        "answer": "on the bench beside the clamped wheel",
                        "short": "On the bench beside the clamped wheel.",
                    },
                    explanation="The illustration is context, not evidence: it shows the layout the "
                                "procedure assumes. It carries no measurements and no torque "
                                "values.",
                    explanation_short="The illustration shows layout only: wheel clamped, wrench "
                                      "beside it.",
                    media_items=[ILLUSTRATION_SPEC],
                ),
            },
        ],
    },
]


def capability_for(course: dict, lesson: dict):
    section = {"lesson_intent": lesson["lesson_intent"], "media_need": lesson["media_need"]}
    objective = {"evidence_target": lesson["evidence_target"]}
    plan = {"subject_domain": course["subject_domain"]}
    capability = policy.plan_lesson_capability(
        recipe=course["recipe"],
        evidence_target=lesson["evidence_target"],
        lesson_intent=lesson["lesson_intent"],
        locale=course["locale"],
        level=course["level"],
        subject_domain=course["subject_domain"],
        media_need=lesson["media_need"],
    )
    problems = policy.media_policy_problems(capability, lesson["media"])
    problems += policy.missing_required_media(capability, lesson["media"])
    for item in lesson["media"]:
        problems += artifacts.media_problems(generation._media_spec_from_lesson_item(item))
    return capability, problems


def main() -> int:
    if HOME.exists():
        shutil.rmtree(HOME)
    HOME.mkdir(parents=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    db.migrate()
    with db.transaction() as connection:
        generation.ensure_schema(connection)

    out = {
        "schema_version": db.applied_schema_version(),
        "wire_contract_version": VERSION,
        "hermes_home": str(HOME),
        "authored_by": "audit/adversarial/h187-course/build_course.py (preparation script; no live model call)",
        "media_bytes_generated": 0,
        "courses": [],
    }

    for spec in COURSES:
        payload = {
            "title": spec["title"],
            "recipe": spec["recipe"],
            "goal": spec["goal"],
            "dials": spec["dials"],
            "scope": spec["scope"],
        }
        if spec["locale"]:
            payload["locale"] = spec["locale"]
        if spec["level"]:
            payload["level"] = spec["level"]
        if spec["subject_domain"]:
            payload["subject_domain"] = spec["subject_domain"]
        created = request("course.create", payload, key=f"h187prep-{spec['key']}-course")
        course_id, plan_id = created["course_id"], created["plan_id"]
        enrolled = request(
            "enrollment.create",
            {"course_id": course_id, "learner_label": spec["title"]},
            key=f"h187prep-{spec['key']}-enroll",
        )
        enrollment_id = enrolled["enrollment_id"]

        objectives = []
        for lesson in spec["lessons"]:
            capability, problems = capability_for(spec, lesson)
            if problems:
                raise RuntimeError(f"{spec['key']} lesson {lesson['ordinal']} media policy: {problems}")
            oid = domain.record_objective(
                plan_id,
                title=lesson["objective_title"],
                evidence_target=lesson["evidence_target"],
                criteria=[],
                ordinal=lesson["ordinal"],
            )
            objectives.append({"lesson": lesson, "objective_id": oid, "capability": capability})

        plan_hash = domain.plan_hash(plan_id)
        approved = request(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": plan_hash},
            expected_revision=enrolled["revision"],
            key=f"h187prep-{spec['key']}-approve",
        )

        digest = artifacts.spec_hash({"course_id": course_id, "plan_hash": plan_hash})
        now = domain._now()
        document = {
            "plan_schema": "coursebook.plan.v1",
            "plan": {
                "plan_schema": "coursebook.plan.v1",
                "state": "approved",
                "title": spec["title"],
                "goal": spec["goal"],
                "objectives": [
                    {"ordinal": item["lesson"]["ordinal"], "title": item["lesson"]["objective_title"],
                     "evidence_target": item["lesson"]["evidence_target"]}
                    for item in objectives
                ],
            },
            "research": {"status": "unavailable", "sources": [], "queries": [], "failures": []},
            "recipe": spec["recipe"],
            "dials": spec["dials"],
            "locale": spec["locale"],
            "level": spec["level"],
            "subject_domain": spec["subject_domain"],
            "scope": spec["scope"],
            "manual_authoring": True,
            "generation": None,
        }
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
                " document_json, research_json, generation_state, validation_id, result_json, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,NULL,?,?)",
                (
                    f"gendoc_{spec['key']}", plan_id, course_id, f"manual-prep-{spec['key']}", digest,
                    json.dumps(document, ensure_ascii=False, sort_keys=True),
                    json.dumps(document["research"], sort_keys=True), "draft",
                    json.dumps({"manual_authoring": True, "validation_verdict": "not_validated"}),
                    now,
                ),
            )
            for item in objectives:
                lesson = item["lesson"]
                section_id = f"sec_{spec['key']}_{lesson['ordinal']}"
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
                    " media_need_json, objective_refs_json, context_needs_json, source_ids_json)"
                    " VALUES (?,?,?,?,?,?,?,?, '[]', '[]')",
                    (
                        section_id, plan_id, lesson["ordinal"], digest, lesson["section_title"],
                        lesson["lesson_intent"], json.dumps(lesson["media_need"], sort_keys=True),
                        json.dumps([lesson["ordinal"]]),
                    ),
                )
                lesson_id = f"gen_{spec['key']}_{lesson['ordinal']}"
                connection.execute(
                    "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                    " page_json, media_json, parent_notes_json, rejection_reasons_json, validation_id,"
                    " policy_json, created_at, updated_at) VALUES (?,?,?,?,1,'model_assessed',?,?,"
                    " '{}', '[]', NULL, ?, ?, ?)",
                    (
                        lesson_id, plan_id, section_id, digest,
                        json.dumps(lesson["page"], ensure_ascii=False, sort_keys=True),
                        json.dumps(lesson["media"], ensure_ascii=False, sort_keys=True),
                        json.dumps(item["capability"].to_dict(), sort_keys=True), now, now,
                    ),
                )
                item["section_id"] = section_id
                item["lesson_id"] = lesson_id

        out["courses"].append(
            {
                "key": spec["key"],
                "course_id": course_id,
                "plan_id": plan_id,
                "plan_hash": approved["plan_hash"],
                "generation_digest": digest,
                "enrollment_id": enrollment_id,
                "title": spec["title"],
                "recipe": spec["recipe"],
                "locale": spec["locale"],
                "level": spec["level"],
                "subject_domain": spec["subject_domain"],
                "lessons": [
                    {
                        "ordinal": item["lesson"]["ordinal"],
                        "objective_id": item["objective_id"],
                        "section_id": item["section_id"],
                        "lesson_id": item["lesson_id"],
                        "media_need": item["lesson"]["media_need"],
                        "media_specs": item["lesson"]["media"],
                        "capability": item["capability"].to_dict(),
                    }
                    for item in objectives
                ],
            }
        )

    # ── read back through the product surface ──────────────────────────────
    for course in out["courses"]:
        listing = request(
            "library.list",
            {"filter": "all", "limit": 50, "sort": "recent"},
        )
        course["in_library"] = any(
            item.get("course_id") == course["course_id"] or item.get("id") == course["course_id"]
            for item in listing.get("items") or []
        ) or any(
            (item.get("course") or {}).get("course_id") == course["course_id"]
            for item in listing.get("items") or []
        )
        for lesson in course["lessons"]:
            page = request(
                "lesson.page",
                {"enrollment_id": course["enrollment_id"], "objective_id": lesson["objective_id"]},
            )
            document = page.get("document") or {}
            lesson["served"] = {
                "objective_title": (page.get("section") or {}).get("title"),
                "document_id": document.get("document_id"),
                "content_hash": document.get("content_hash"),
                "state": document.get("state"),
                "check_id": document.get("check_id"),
                "provenance": document.get("provenance") or page.get("provenance"),
                "blocks": [
                    {
                        "id": block.get("id"),
                        "role": block.get("role"),
                        "headline": block.get("headline"),
                        "media": [
                            {"kind": m.get("kind"), "role": m.get("role"),
                             "purpose": m.get("purpose"), "artifact_id": m.get("artifact_id")}
                            for m in block.get("media") or []
                        ],
                    }
                    for block in document.get("blocks") or []
                ],
            }
            # The exact placement each downstream artifact must land on.
            lesson["placement"] = [
                {
                    "block_id": block["id"],
                    "block_role": block["role"],
                    "media_index_in_block": index,
                    "media": child,
                }
                for block in lesson["served"]["blocks"]
                for index, child in enumerate(block["media"])
            ]

    EVIDENCE.joinpath("course_facts.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(
        {
            "home": str(HOME),
            "courses": [
                {
                    "course_id": c["course_id"],
                    "title": c["title"],
                    "enrollment_id": c["enrollment_id"],
                    "in_library": c["in_library"],
                    "lessons": [
                        {
                            "lesson_id": l["lesson_id"],
                            "objective_id": l["objective_id"],
                            "served_state": l["served"]["state"],
                            "placement": l["placement"],
                        }
                        for l in c["lessons"]
                    ],
                }
                for c in out["courses"]
            ],
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
