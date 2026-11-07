"""H-30b — end-to-end generic-harness re-audit after blueprint v2.

Three non-Japanese briefs run through the **real** product path in a throwaway ``HERMES_HOME``:

* ``course.create`` / ``enrollment.create`` / ``jobs.create`` (cb.rpc v11, the wire the Desktop
  plugin speaks),
* ``generation.run_plan_job`` (research -> plan -> deterministic rules -> independent validation),
* ``plan.approve`` (H-12 fail-closed),
* ``generation.run_unit_sections_job`` and ``generation.run_lesson_job`` per unit,
* ``course.outline``, ``lesson.page``, ``check.open`` and ``attempt.submit``.

What is **FAKE** and labelled so: the model. Every response is produced by ``ScriptedLLM`` below,
deterministically, from the request the pipeline actually sent. No provider is called and no spend
occurs. The research fetch is an in-memory recorded page, not the live web.

What is **real**: every schema, rule, transaction, approval check, projection, check payload,
grading lane and verdict under test. The script reports what it read; it never asserts a verdict
it did not observe.

Run from the product checkout:

    PYTHONPATH=. python3 audit/adversarial/generic-harness-v2/generic_v2_e2e.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from coursebook import generation as gen
from coursebook import rubrics

HERE = Path(__file__).resolve().parent
OUT = HERE / "evidence"
NOW = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)

#: Answer the fake lesson plants for a quiz objective. The harness submits this string.
def quiz_answer(ordinal: int) -> str:
    return f"the verified answer for step {ordinal}"


def _shorten(text: str) -> str:
    """A strictly shorter prefix of ``text`` at a word boundary: drops detail, adds no claim."""
    words = text.split()
    keep = max(2, (len(words) * 2) // 3)
    candidate = " ".join(words[:keep])
    if len(candidate) >= len(text):
        candidate = " ".join(words[: max(1, keep - 1)])
    return candidate


class RecordedSearch:
    """One in-memory page through the real search seam (not the live web)."""

    def __init__(self) -> None:
        self.url = "https://example.invalid/recorded-page"
        self.queries: list[str] = []
        self.fetches: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        return [{"url": self.url, "title": "Recorded page", "description": "recorded result"}][:limit]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.fetches.append(url)
        return {
            "url": self.url,
            "title": "Recorded page",
            "publisher": "Recorded publisher",
            "published_at": None,
            "content": "A recorded page used only to make the research seam return a source. "
                       "It states the general procedure in plain words and nothing else.",
        }


#: Per-scope shape the scripted model is asked to produce. These are the *contract* shapes, not
#: a claim that a live model chooses them; ``probe_shape_v2.py`` and ``docs/PLAN-CEILING.md``
#: carry the request/schema evidence and the one real measurement.
SHAPES = {
    "single": {"units": 1, "objectives": 1, "weeks": 1, "sessions": 1},
    "short": {"units": 2, "objectives": 4, "weeks": 3, "sessions": 2},
    "full": {"units": 6, "objectives": 24, "weeks": 12, "sessions": 2},
}

TOPICS = {
    "single": ["Replace the rear inner tube and verify the brakes"],
    "short": [
        "Hold a knife safely and cut an onion evenly",
        "Control pan heat and judge when oil is ready",
        "Season a dish by tasting as you go",
        "Plan and repeat a weeknight dinner",
    ],
    "full": [
        "Index an array and explain its constant-time access",
        "Resize a dynamic array and state the amortised cost",
        "Implement a stack and use it to reverse a sequence",
        "Implement a queue and explain FIFO order",
        "Traverse a linked list and insert at the head",
        "Remove a node from a singly linked list safely",
        "Insert and search in a binary search tree",
        "Traverse a tree in order and state the output order",
        "Explain hash collisions and a collision strategy",
        "Measure a hash table's load factor",
        "Represent a graph as an adjacency list",
        "Breadth-first traverse a small graph",
        "Depth-first traverse a small graph",
        "Choose a structure for a stated access pattern",
        "Explain why a balanced tree bounds search cost",
        "Implement a priority queue over a heap",
        "Explain the cost of extracting the minimum",
        "Trace insertion sort on six numbers",
        "Trace merge sort and count its comparisons",
        "State when a linear search is the honest choice",
        "Compare two structures on memory and speed",
        "Design a small index for a text search task",
        "Explain a cache's eviction effect on lookups",
        "Justify one structure for a final project",
    ],
}

TARGETS = ("recall", "comprehension", "discrimination", "transfer")


class ScriptedLLM:
    """Deterministic fake model. Records every real request it was sent."""

    def __init__(self, *, drop_unit_section: int | None = None, validation: str = "pass") -> None:
        self.requests: list = []
        self.drop_unit_section = drop_unit_section
        self.validation_mode = validation

    # ── plan ────────────────────────────────────────────────────────────────
    def _plan(self, payload: dict) -> dict:
        if not payload.get("plan_schema"):
            return self._plan_v1(payload)
        scope = str(payload["scope"])
        shape = SHAPES[scope]
        recipe = str(payload["recipe"])
        units_n = shape["units"]
        objectives_n = shape["objectives"]
        per_unit = objectives_n // units_n
        unit_objs: list[dict] = []
        objectives: list[dict] = []
        checks: list[dict] = []
        topics = TOPICS[scope]
        target_cycle = ("procedure",) if scope == "single" else TARGETS
        for unit_ordinal in range(1, units_n + 1):
            unit_objs.append({
                "ordinal": unit_ordinal,
                "title": f"Unit {unit_ordinal}: {topics[unit_ordinal - 1][:60]}",
                "goal": f"Unit {unit_ordinal} makes the next body of work possible",
                "prereq_unit_ordinals": [unit_ordinal - 1] if unit_ordinal > 1 else [],
                "target_lessons": per_unit,
            })
            for index in range(per_unit):
                ordinal = (unit_ordinal - 1) * per_unit + index + 1
                target = target_cycle[(ordinal - 1) % len(target_cycle)]
                objectives.append({
                    "ordinal": ordinal,
                    "unit_ref": unit_ordinal,
                    "title": topics[ordinal - 1],
                    "evidence_target": target,
                    "evidence_criteria": [
                        f"States or performs step {ordinal} without notes",
                        f"Names the condition that would make step {ordinal} unsafe",
                    ],
                    "support": "unverified",
                    "source_ids": [],
                })
                checks.append({
                    "objective_ref": ordinal,
                    "kind": "verification" if recipe == "one_off" else "quiz",
                    "evidence_target": target,
                })
        return {
            "plan_schema": gen.PLAN_SCHEMA_V2_NAME,
            "scope": scope,
            "title": f"{scope.title()} course on an arbitrary non-Japanese topic",
            "learner_outcome": "The learner can do the task or explain the concept without notes.",
            "delivery": "self_study",
            "time_estimate": {
                "sessions_per_week": shape["sessions"],
                "minutes_per_session": 60,
                "weeks": shape["weeks"],
                "basis": "none",
                "confidence": "low",
                "rationale": "Authored estimate; no benchmark transfer claim.",
                "benchmark": None,
                "attainment_hours": None,
            },
            "units": unit_objs,
            "objectives": objectives,
            "check_plan": checks,
            "context_needs": ["the actual equipment or textbook"],
            "source_ids": [],
            "exclusions": ["Does not certify competence; a supervisor checks the first attempt."],
            "spaced_review": recipe != "one_off",
            "evidence_note": None,
        }

    # ── legacy v1 plan (unscoped brief; stored-document path) ───────────────
    def _plan_v1(self, payload: dict) -> dict:
        recipe = str(payload["recipe"])
        topics = [
            "Read the dial and set the tool to the stated value",
            "Hold the work steady and make the first pass",
            "Check the result against the stated criterion",
            "Repeat the task without notes and state the limit",
        ]
        objectives = [
            {
                "ordinal": index + 1,
                "title": topic,
                "evidence_target": "comprehension",
                "evidence_criteria": [f"Explains step {index + 1} accurately"],
                "support": "unverified",
                "source_ids": [],
            }
            for index, topic in enumerate(topics)
        ]
        sections = [
            {
                "ordinal": index + 1,
                "title": topic,
                "lesson_intent": f"Teach and then check: {topic}",
                "media_need": {
                    "construct": "",
                    "image": {"level": "none", "role": "none"},
                    "audio": {"level": "none", "role": "none"},
                },
                "objective_refs": [index + 1],
                "context_needs": [],
                "source_ids": [],
            }
            for index, topic in enumerate(topics)
        ]
        checks = [
            {
                "objective_ref": index + 1,
                "kind": "quiz",
                "evidence_target": "comprehension",
                "count": 1,
                "independent_evidence": False,
            }
            for index in range(len(topics))
        ]
        return {
            "title": "A legacy unscoped course on an arbitrary topic",
            "learner_outcome": "The learner can explain each step without notes and name its limit.",
            "delivery": "self_study",
            "time_estimate": {
                "sessions_per_week": 2,
                "minutes_per_session": 45,
                "weeks": 2,
                "basis": "none",
                "confidence": "low",
                "rationale": "Authored estimate; no benchmark transfer claim.",
                "benchmark": None,
                "attainment_hours": None,
            },
            "objectives": objectives,
            "sections": sections,
            "check_plan": checks,
            "context_needs": ["the actual equipment or textbook"],
            "source_ids": [],
            "exclusions": ["Does not certify competence."],
            "spaced_review": recipe == "committed",
            "evidence_note": None,
        }

    # ── unit sections ───────────────────────────────────────────────────────
    def _unit_sections(self, payload: dict) -> dict:
        unit = payload["unit"]
        sections = []
        for index, objective in enumerate(payload["objectives"]):
            if self.drop_unit_section == int(unit["ordinal"]) and index == len(payload["objectives"]) - 1:
                continue  # simulate one required step that cannot be authored
            sections.append({
                "ordinal": int(objective["ordinal"]),
                "unit_ref": int(unit["ordinal"]),
                "role": "owner",
                "primary_objective_ref": int(objective["ordinal"]),
                "reinforces": [],
                "title": objective["title"],
                "lesson_intent": f"Teach and then verify: {objective['title']}",
                "context_needs": [],
                "source_ids": [],
                "media_need": {
                    "construct": "",
                    "image": {"level": "none", "role": "none"},
                    "audio": {"level": "none", "role": "none"},
                },
            })
        return {"unit_ref": int(unit["ordinal"]), "sections": sections}

    # ── lesson ──────────────────────────────────────────────────────────────
    def _lesson(self, payload: dict) -> dict:
        section = payload["section"]
        objective = payload["objective"]
        ordinal = int(objective["ordinal"])
        target = str(objective["evidence_target"])
        recipe = str(payload["recipe"])
        capability = payload["capability_policy"]
        profile = rubrics.resolve_profile(str(capability["rubric_profile"]), target)
        entry = rubrics.RUBRICS[profile]
        rubric = [
            {"criterion": criterion.label, "weight": 1.0,
             "description": criterion.observation}
            for criterion in entry.criteria
        ]

        first = (
            f"Work through {section['title']} slowly, with the real material in front of you. "
            "Stop if a part binds or the result looks unsafe."
        )
        second = (
            "Say the step out loud before you do it, then check the result against the "
            "criterion your supervisor gave you."
        )
        explanation = (
            "This lesson teaches one step and then asks you to show it. "
            "The check is the evidence."
        )
        if recipe == "one_off":
            check = {
                "kind": "verification",
                "stimulus": {
                    "prompt": "Tick each step only after you have done it.",
                    "format": "verification",
                    "choices": [],
                    "items": [
                        {"id": "item_1", "label": "Read the step and gathered the tool"},
                        {"id": "item_2", "label": "Performed the step without forcing a part"},
                        {"id": "item_3", "label": "Checked the result by hand"},
                    ],
                },
                "learner_instructions": "Tick only what you actually did.",
                "evidence_target": target,
                "accepted_answers": ["all listed steps ticked honestly"],
                "accepted_alternatives": [],
                "rubric": rubric,
                "reference_answer": "Every listed step completed and checked by hand",
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "none"},
                "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
            }
        else:
            check = {
                "kind": "quiz",
                "stimulus": {
                    "prompt": f"What is the verified answer for step {ordinal}?",
                    "format": "text",
                    "choices": [],
                    "items": [],
                },
                "learner_instructions": "Answer in one short sentence, without notes.",
                "evidence_target": target,
                "accepted_answers": [quiz_answer(ordinal)],
                "accepted_alternatives": [],
                "rubric": rubric,
                "reference_answer": quiz_answer(ordinal),
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "none"},
                "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
            }
        return {
            "section_title": section["title"],
            "segments": [
                {"kind": "model", "heading": "The step", "body": first, "short": _shorten(first)},
                {"kind": "guided", "heading": "Do it", "body": second, "short": _shorten(second)},
            ],
            "worked_example": {
                "prompt": f"An example of {section['title']}",
                "steps": ["Read the step", "Do it slowly", "Check the result"],
                "answer": "The step is done and checked",
                "short": "The step is done and checked",
            },
            "learner_explanation": explanation,
            "learner_explanation_short": _shorten(explanation),
            "check": check,
            "sources": [],
            "media": [],
            "parent_notes": None,
            "supervision_notes": [],
        }

    # ── validation ──────────────────────────────────────────────────────────
    def _validation(self, payload: dict, *, lesson: bool) -> dict:
        if self.validation_mode == "reject":
            verdict = "reject"
            criteria_verdict = {"objective_alignment": "fail"}
        else:
            verdict = "pass"
            criteria_verdict = {}
        criteria = [
            {"id": criterion, "verdict": criteria_verdict.get(criterion, "pass"),
             "reason": f"{criterion} checked against the artifact"}
            for criterion in gen.VALIDATION_CRITERIA
        ]
        return {
            "verdict": verdict,
            "criteria": criteria,
            "rejections": (
                [{"item": "plan", "criterion": "objective_alignment",
                  "reason": "scripted rejection for the fail-closed approval probe"}]
                if verdict == "reject" else []
            ),
            "claim_verdicts": [],
        }

    def __call__(self, request):
        self.requests.append(request)
        payload = json.loads(request.input_text)
        if request.purpose == "coursebook.plan.generate":
            document = self._plan(payload)
        elif request.purpose == "coursebook.plan.validate":
            document = self._validation(payload, lesson=False)
        elif request.purpose == "coursebook.unit_sections.generate":
            document = self._unit_sections(payload)
        elif request.purpose == "coursebook.unit_sections.validate":
            document = self._validation(payload, lesson=False)
        elif request.purpose == "coursebook.lesson.generate":
            document = self._lesson(payload)
        elif request.purpose == "coursebook.lesson.validate":
            document = self._validation(payload, lesson=True)
        else:
            raise AssertionError(f"unexpected provider call {request.purpose!r}")
        text = json.dumps(document, ensure_ascii=False)
        return gen.LLMResponse(
            text=text, parsed=document, provider="fake", model="scripted-h30b",
            input_tokens=len(request.input_text) // 4,
            output_tokens=len(text) // 4,
            cost_usd=0.0,
        )


def _rpc(method: str, payload: dict | None = None, *, key: str | None = None,
         expected_revision: int | None = None) -> dict:
    from coursebook import api

    body = {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"op-h30b-{method.replace('.', '-')}-{os.urandom(3).hex()}",
        "payload": payload or {},
    }
    if key:
        body["idempotency_key"] = key
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    return api.dispatch(body)


def _ok(method: str, payload: dict | None = None, **kwargs) -> dict:
    response = _rpc(method, payload, **kwargs)
    if not response["ok"]:
        raise RuntimeError(f"{method} failed: {json.dumps(response['error'])}")
    return response["result"]


BRIEFS = {
    "single": {
        "title": "Replace a bicycle inner tube",
        "goal": "Walk me through replacing the inner tube on my road bike and checking the brakes "
                "before I ride it today.",
        "recipe": "one_off",
        "scope": "single",
        "locale": "en-US",
        "level": "beginner",
        "subject_domain": "repair",
    },
    "short": {
        "title": "Three weeks of practical weeknight cooking",
        "goal": "Three weeks of practical weeknight cooking: knife skills, pan heat, seasoning "
                "and a repeatable dinner plan I can cook without a recipe.",
        "recipe": "committed",
        "scope": "short",
        "locale": "en-US",
        "level": "beginner",
        "subject_domain": "general",
    },
    "full": {
        "title": "Introduction to data structures",
        "goal": "A first-year college introduction to data structures: arrays, lists, stacks, "
                "queues, trees, hashing and graphs, with assessments and prerequisites.",
        "recipe": "committed",
        "scope": "full",
        "locale": "en-US",
        "level": "beginner",
        "subject_domain": "general",
    },
}

DIALS = {"pace": "steady", "depth": "working", "assessment": "graded", "autonomy": "guided"}
BUDGET = gen.CostBudget(max_calls=400, max_cost_usd=100.0, source="caller")


def run_scenario(name: str, *, home: Path) -> dict:
    from coursebook import db, domain  # noqa: F401 - binds the RPC handlers
    from coursebook import pack_flow  # noqa: F401

    os.environ["HERMES_HOME"] = str(home)
    db.migrate()
    with db.read() as connection:
        gen.ensure_schema(connection)

    brief = BRIEFS[name]
    llm = ScriptedLLM()
    search = RecordedSearch()
    evidence: dict = {
        "scenario": {"name": name, **brief},
        "labels": {
            "model": "FAKE — deterministic ScriptedLLM, no provider call",
            "research": "RECORDED in-memory page through the real search seam",
            "provider_calls": 0,
            "provider_spend_usd": 0.0,
        },
        "steps": {},
        "observations": {},
    }

    created = _ok("course.create", {**brief, "dials": DIALS}, key=f"h30b-{name}-create")
    course_id = created["course_id"]
    enrollment = _ok("enrollment.create", {"course_id": course_id, "learner_label": brief["title"]},
                     key=f"h30b-{name}-enroll")
    enrollment_id = enrollment["enrollment_id"]

    plan_brief = {
        "stage": "plan", "course_id": course_id, "enrollment_id": enrollment_id,
        "goal": brief["goal"], "recipe": brief["recipe"], "dials": DIALS,
        "locale": brief["locale"], "level": brief["level"],
        "subject_domain": brief["subject_domain"], "scope": brief["scope"],
    }
    job = _ok("jobs.create", {"kind": "plan", "brief": plan_brief}, key=f"h30b-{name}-plan-job")
    connection = db.connect()
    try:
        plan_result = gen.run_plan_job(
            connection, {"job_id": job["job_id"], "brief": plan_brief}, llm, search, now=NOW,
        )
    finally:
        connection.close()

    plan_request = next(r for r in llm.requests if r.purpose == "coursebook.plan.generate")
    plan_id = plan_result["plan_id"]
    evidence["steps"]["plan_job"] = {
        "result": plan_result,
        "request": {
            "prompt_version": plan_request.prompt_version,
            "schema_name": plan_request.schema_name,
            "max_tokens": plan_request.max_tokens,
            "objective_count_rule": json.loads(plan_request.input_text)["rules"]["objective_count"],
            "unit_count_rule": json.loads(plan_request.input_text)["rules"]["unit_count"],
        },
        "research": {"status": plan_result["research"]["status"],
                     "queries": len(search.queries), "fetches": len(search.fetches)},
    }

    with db.read() as connection:
        plan_row = dict(connection.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone())
        document_row = dict(connection.execute(
            "SELECT document_json, generation_state, validation_id FROM gen_plan_documents"
            " WHERE plan_id = ?", (plan_id,)).fetchone())
    evidence["steps"]["stored_plan"] = {
        "state_before_approval": plan_row["state"],
        "generation_state": document_row["generation_state"],
        "validation_id_present": bool(document_row["validation_id"]),
        "document": json.loads(document_row["document_json"])["plan"],
    }

    # H-12 fail-closed: a stale hash must be refused and must not approve.
    tampered = _rpc("plan.approve", {
        "enrollment_id": enrollment_id, "plan_id": plan_id,
        "plan_hash": "sha256:" + "0" * 64,
    }, key=f"h30b-{name}-approve-wrong", expected_revision=0)
    evidence["steps"]["approve_wrong_hash"] = {
        "ok": tampered["ok"],
        "error_code": (tampered.get("error") or {}).get("code"),
        "state_after": _plan_state(plan_id),
    }

    book = _ok("parent.blueprint.read", {"course_id": course_id})
    approval = _ok("plan.approve", {
        "enrollment_id": enrollment_id, "plan_id": plan_id,
        "plan_hash": book["plan"]["plan_hash"],
    }, expected_revision=0, key=f"h30b-{name}-approve")
    evidence["steps"]["approve"] = {
        "plan_hash": approval["plan_hash"],
        "revision": approval["revision"],
        "state_after": _plan_state(plan_id),
        "approval_provenance": book["plan"].get("validation_source"),
    }

    units = [int(unit["ordinal"]) for unit in evidence["steps"]["stored_plan"]["document"]["units"]]
    evidence["steps"]["unit_stages"] = []
    for ordinal in units:
        unit_brief = {"stage": "unit_sections", "plan_id": plan_id, "enrollment_id": enrollment_id,
                      "unit_ordinal": ordinal}
        unit_job = _ok("jobs.create", {"kind": "plan", "brief": unit_brief},
                       key=f"h30b-{name}-unit-{ordinal}")
        jobs_before = _job_count()
        connection = db.connect()
        try:
            unit_result = gen.run_unit_sections_job(
                connection, {"job_id": unit_job["job_id"], "brief": unit_brief}, llm,
                plan_id=plan_id, unit_ordinal=ordinal, now=NOW, budget=BUDGET,
            )
        finally:
            connection.close()
        jobs_after = _job_count()
        evidence["steps"]["unit_stages"].append({
            "unit_ordinal": ordinal,
            "result": unit_result,
            "jobs_before_run": jobs_before,
            "jobs_after_run": jobs_after,
            "chained_a_job": jobs_after > jobs_before,
            "offered_next_unit_ordinal": unit_result.get("next_unit_ordinal"),
        })

    evidence["steps"]["lesson_stages"] = []
    for ordinal in units:
        lesson_brief = {"stage": "lessons", "plan_id": plan_id, "enrollment_id": enrollment_id,
                        "unit_ordinal": ordinal}
        lesson_job = _ok("jobs.create", {"kind": "plan", "brief": lesson_brief},
                         key=f"h30b-{name}-lessons-{ordinal}")
        jobs_before = _job_count()
        connection = db.connect()
        try:
            lesson_result = gen.run_lesson_job(
                connection, {"job_id": lesson_job["job_id"], "brief": lesson_brief}, llm,
                plan_id=plan_id, unit_ordinal=ordinal, now=NOW, budget=BUDGET,
            )
        finally:
            connection.close()
        jobs_after = _job_count()
        evidence["steps"]["lesson_stages"].append({
            "unit_ordinal": ordinal,
            "result": lesson_result,
            "jobs_before_run": jobs_before,
            "jobs_after_run": jobs_after,
            "chained_a_job": jobs_after > jobs_before,
        })

    outline = _ok("course.outline", {"enrollment_id": enrollment_id})
    evidence["steps"]["outline"] = outline

    # Grading through the real RPC: one correct answer, one wrong answer where a quiz exists.
    revision = approval["revision"]
    objectives = outline["objectives"]
    grading_rows = []
    attempts = []
    if brief["recipe"] == "one_off":
        attempts.append((objectives[0], {"kind": "selection",
                                         "selection": ["item_1", "item_2", "item_3"]}, "correct"))
    else:
        attempts.append((objectives[0], {"kind": "text", "text": quiz_answer(1)}, "correct"))
        attempts.append((objectives[1], {"kind": "text", "text": "a deliberately wrong answer"},
                         "wrong"))
    for objective, answer, label in attempts:
        opened = _rpc("check.open", {
            "enrollment_id": enrollment_id, "objective_id": objective["objective_id"],
        }, expected_revision=revision, key=f"h30b-{name}-open-{objective['ordinal']}")
        if not opened["ok"]:
            grading_rows.append({"label": label, "open": opened})
            continue
        revision = opened["result"]["revision"]
        submitted = _rpc("attempt.submit", {
            "enrollment_id": enrollment_id,
            "check_id": opened["result"]["check_id"],
            "check_version": opened["result"]["check_version"],
            "attempt_nonce": f"h30b-nonce-{label}-{objective['ordinal']}",
            "answer": answer,
        }, expected_revision=revision, key=f"h30b-{name}-submit-{label}-{objective['ordinal']}")
        if submitted["ok"]:
            revision = submitted["result"]["revision"]
        grading_rows.append({"label": label, "open": opened, "submit": submitted})
    evidence["steps"]["grading"] = grading_rows

    with db.read() as connection:
        check_rows = [dict(row) for row in connection.execute(
            "SELECT id, objective_id, state, version, audit_state,"
            " stimulus_json, reference_json FROM checks ORDER BY created_at, id").fetchall()]
        attempt_rows = [dict(row) for row in connection.execute(
            "SELECT id, check_id, state, verdict, evidence_class, grading_provenance_json"
            " FROM attempts ORDER BY created_at, id").fetchall()]
        lesson_rows = [dict(row) for row in connection.execute(
            "SELECT id, section_id, state FROM gen_lessons ORDER BY created_at, id").fetchall()]
        units_rows = [dict(row) for row in connection.execute(
            "SELECT ordinal, title, prereq_unit_ordinals_json, target_lessons FROM plan_units"
            " ORDER BY ordinal").fetchall()]
        section_rows = [dict(row) for row in connection.execute(
            "SELECT ordinal, section_role, objective_refs_json FROM gen_plan_sections"
            " ORDER BY ordinal").fetchall()]
    evidence["observations"] = {
        "schema_name": plan_request.schema_name,
        "prompt_version": plan_request.prompt_version,
        "plan_scope": plan_result["scope"],
        "validation_verdict": plan_result["validation_verdict"],
        "plan_state_before_approval": evidence["steps"]["stored_plan"]["state_before_approval"],
        "plan_state_after_approval": _plan_state(plan_id),
        "units": len(units_rows),
        "objectives": len(objectives),
        "checks": len(check_rows),
        "lessons": len(lesson_rows),
        "sections": len(section_rows),
        "outline_units": len(outline["plan"]["units"]),
        "outline_unit_states": [
            {"ordinal": unit["ordinal"], "prereq_unit_ordinals": unit["prereq_unit_ordinals"],
             "prerequisite_state": unit["prerequisite_state"], "unmet": len(unit["unmet"]),
             "objectives": len(unit["objectives"])}
            for unit in outline["plan"]["units"]
        ],
        "unit_rows": units_rows,
        "section_rows": section_rows,
        "check_lanes": [
            {"objective_id": row["objective_id"],
             "reference_kind": (json.loads(row["reference_json"]).get("kind")
                                if row["reference_json"] else None),
             "stimulus_format": (json.loads(row["stimulus_json"]).get("format")
                                 if row["stimulus_json"] else None),
             "state": row["state"]}
            for row in check_rows
        ],
        "attempt_rows": attempt_rows,
    }
    return evidence


def _plan_state(plan_id: str) -> str:
    from coursebook import db

    with db.read() as connection:
        return str(connection.execute("SELECT state FROM plans WHERE id = ?", (plan_id,)).fetchone()[0])


def _job_count() -> int:
    from coursebook import db

    with db.read() as connection:
        return int(connection.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"])


def run_fail_closed_probe(home: Path) -> dict:
    """A plan whose independent validation fails must not be approvable."""
    from coursebook import db, domain  # noqa: F401
    from coursebook import pack_flow  # noqa: F401

    os.environ["HERMES_HOME"] = str(home)
    db.migrate()
    with db.read() as connection:
        gen.ensure_schema(connection)
    brief = dict(BRIEFS["short"])
    llm = ScriptedLLM(validation="reject")
    search = RecordedSearch()
    created = _ok("course.create", {**brief, "dials": DIALS}, key="h30b-reject-create")
    enrollment = _ok("enrollment.create",
                     {"course_id": created["course_id"], "learner_label": "rejected"},
                     key="h30b-reject-enroll")
    plan_brief = {
        "stage": "plan", "course_id": created["course_id"],
        "enrollment_id": enrollment["enrollment_id"], "goal": brief["goal"],
        "recipe": brief["recipe"], "dials": DIALS, "locale": brief["locale"],
        "level": brief["level"], "subject_domain": brief["subject_domain"],
        "scope": brief["scope"],
    }
    job = _ok("jobs.create", {"kind": "plan", "brief": plan_brief}, key="h30b-reject-job")
    connection = db.connect()
    try:
        result = gen.run_plan_job(connection, {"job_id": job["job_id"], "brief": plan_brief},
                                  llm, search, now=NOW)
    finally:
        connection.close()
    book = _ok("parent.blueprint.read", {"course_id": created["course_id"]})
    attempt = _rpc("plan.approve", {
        "enrollment_id": enrollment["enrollment_id"], "plan_id": result["plan_id"],
        "plan_hash": book["plan"]["plan_hash"],
    }, expected_revision=0, key="h30b-reject-approve")
    return {
        "plan_result_status": result["status"],
        "validation_verdict": result["validation_verdict"],
        "plan_state": _plan_state(result["plan_id"]),
        "approve_ok": attempt["ok"],
        "approve_error": attempt.get("error"),
    }


def run_missing_section_probe(home: Path) -> dict:
    """A required step that cannot be authored is refused and never served as a promise."""
    from coursebook import db, domain  # noqa: F401
    from coursebook import pack_flow  # noqa: F401

    os.environ["HERMES_HOME"] = str(home)
    db.migrate()
    with db.read() as connection:
        gen.ensure_schema(connection)
    brief = dict(BRIEFS["short"])
    llm = ScriptedLLM(drop_unit_section=2)
    search = RecordedSearch()
    created = _ok("course.create", {**brief, "dials": DIALS}, key="h30b-miss-create")
    enrollment = _ok("enrollment.create",
                     {"course_id": created["course_id"], "learner_label": "missing"},
                     key="h30b-miss-enroll")
    plan_brief = {
        "stage": "plan", "course_id": created["course_id"],
        "enrollment_id": enrollment["enrollment_id"], "goal": brief["goal"],
        "recipe": brief["recipe"], "dials": DIALS, "locale": brief["locale"],
        "level": brief["level"], "subject_domain": brief["subject_domain"],
        "scope": brief["scope"],
    }
    job = _ok("jobs.create", {"kind": "plan", "brief": plan_brief}, key="h30b-miss-job")
    connection = db.connect()
    try:
        result = gen.run_plan_job(connection, {"job_id": job["job_id"], "brief": plan_brief},
                                  llm, search, now=NOW)
    finally:
        connection.close()
    book = _ok("parent.blueprint.read", {"course_id": created["course_id"]})
    _ok("plan.approve", {
        "enrollment_id": enrollment["enrollment_id"], "plan_id": result["plan_id"],
        "plan_hash": book["plan"]["plan_hash"],
    }, expected_revision=0, key="h30b-miss-approve")

    unit_brief = {"stage": "unit_sections", "plan_id": result["plan_id"],
                  "enrollment_id": enrollment["enrollment_id"], "unit_ordinal": 2}
    unit_job = _ok("jobs.create", {"kind": "plan", "brief": unit_brief}, key="h30b-miss-unit")
    connection = db.connect()
    try:
        unit_result = gen.run_unit_sections_job(
            connection, {"job_id": unit_job["job_id"], "brief": unit_brief},
            llm, plan_id=result["plan_id"], unit_ordinal=2, now=NOW, budget=BUDGET,
        )
    except Exception as exc:  # noqa: BLE001 - a refusal is evidence too
        unit_result = {"refused": True, "type": type(exc).__name__, "message": str(exc)}
    finally:
        connection.close()

    with db.read() as connection:
        sections = int(connection.execute(
            "SELECT COUNT(*) AS n FROM gen_plan_sections WHERE plan_id = ?",
            (result["plan_id"],)).fetchone()["n"])
        lessons = int(connection.execute(
            "SELECT COUNT(*) AS n FROM gen_lessons WHERE plan_id = ?",
            (result["plan_id"],)).fetchone()["n"])
        checks = int(connection.execute(
            "SELECT COUNT(*) AS n FROM checks").fetchone()["n"])

    lesson_brief = {"stage": "lessons", "plan_id": result["plan_id"],
                    "enrollment_id": enrollment["enrollment_id"], "unit_ordinal": 2}
    lesson_job = _ok("jobs.create", {"kind": "plan", "brief": lesson_brief},
                     key="h30b-miss-lessons")
    connection = db.connect()
    try:
        gen.run_lesson_job(connection, {"job_id": lesson_job["job_id"], "brief": lesson_brief},
                           llm, plan_id=result["plan_id"], unit_ordinal=2, now=NOW,
                           budget=BUDGET)
    except Exception as exc:  # noqa: BLE001 - the refusal is the evidence
        lesson_refusal = {"type": type(exc).__name__, "message": str(exc)}
    else:
        lesson_refusal = None
    finally:
        connection.close()

    outline = _ok("course.outline", {"enrollment_id": enrollment["enrollment_id"]})
    unit_two = next(u for u in outline["plan"]["units"] if int(u["ordinal"]) == 2)
    target_objective = unit_two["objectives"][-1]
    page = _rpc("lesson.page", {"enrollment_id": enrollment["enrollment_id"],
                                "objective_id": target_objective["objective_id"]})
    return {
        "unit_sections_result": unit_result,
        "lesson_job_refusal": lesson_refusal,
        "sections_after_refusal": sections,
        "lessons_after_refusal": lessons,
        "checks_after_refusal": checks,
        "outline_objective": {key: target_objective.get(key)
                              for key in ("ordinal", "title", "state", "check_state")},
        "lesson_page_ok": page["ok"],
        "lesson_page_result": page.get("result"),
        "lesson_page_error": page.get("error"),
    }


def run_legacy_probe(home: Path) -> dict:
    """An unscoped (legacy v1) brief still projects one implicit unit and grades."""
    from coursebook import db, domain  # noqa: F401
    from coursebook import pack_flow  # noqa: F401

    os.environ["HERMES_HOME"] = str(home)
    db.migrate()
    with db.read() as connection:
        gen.ensure_schema(connection)
    brief = {
        "title": "Legacy unscoped arbitrary topic",
        "goal": "Teach me a short arbitrary non-Japanese task in four steps.",
        "recipe": "committed",
        "locale": "en-US",
        "level": "beginner",
        "subject_domain": "general",
    }
    llm = ScriptedLLM()
    search = RecordedSearch()
    created = _ok("course.create", {**brief, "dials": DIALS}, key="h30b-legacy-create")
    enrollment = _ok("enrollment.create",
                     {"course_id": created["course_id"], "learner_label": "legacy"},
                     key="h30b-legacy-enroll")
    plan_brief = {
        "stage": "plan", "course_id": created["course_id"],
        "enrollment_id": enrollment["enrollment_id"], "goal": brief["goal"],
        "recipe": brief["recipe"], "dials": DIALS, "locale": brief["locale"],
        "level": brief["level"], "subject_domain": brief["subject_domain"],
    }
    job = _ok("jobs.create", {"kind": "plan", "brief": plan_brief}, key="h30b-legacy-job")
    connection = db.connect()
    try:
        result = gen.run_plan_job(connection, {"job_id": job["job_id"], "brief": plan_brief},
                                  llm, search, now=NOW)
    finally:
        connection.close()
    plan_request = next(r for r in llm.requests if r.purpose == "coursebook.plan.generate")
    book = _ok("parent.blueprint.read", {"course_id": created["course_id"]})
    approval = _ok("plan.approve", {
        "enrollment_id": enrollment["enrollment_id"], "plan_id": result["plan_id"],
        "plan_hash": book["plan"]["plan_hash"],
    }, expected_revision=0, key="h30b-legacy-approve")
    lesson_brief = {"stage": "lessons", "plan_id": result["plan_id"],
                    "enrollment_id": enrollment["enrollment_id"]}
    lesson_job = _ok("jobs.create", {"kind": "plan", "brief": lesson_brief},
                     key="h30b-legacy-lessons")
    connection = db.connect()
    try:
        lesson_result = gen.run_lesson_job(
            connection, {"job_id": lesson_job["job_id"], "brief": lesson_brief}, llm,
            plan_id=result["plan_id"], now=NOW, budget=BUDGET,
        )
    finally:
        connection.close()
    outline = _ok("course.outline", {"enrollment_id": enrollment["enrollment_id"]})
    revision = approval["revision"]
    opened = _ok("check.open", {
        "enrollment_id": enrollment["enrollment_id"],
        "objective_id": outline["objectives"][0]["objective_id"],
    }, expected_revision=revision, key="h30b-legacy-open")
    submitted = _ok("attempt.submit", {
        "enrollment_id": enrollment["enrollment_id"],
        "check_id": opened["check_id"], "check_version": opened["check_version"],
        "attempt_nonce": "h30b-legacy-nonce",
        "answer": {"kind": "text", "text": quiz_answer(1)},
    }, expected_revision=opened["revision"], key="h30b-legacy-submit")
    with db.read() as connection:
        unit_rows = int(connection.execute(
            "SELECT COUNT(*) AS n FROM plan_units WHERE plan_id = ?",
            (result["plan_id"],)).fetchone()["n"])
        hash_now = gen.plan_content_hash(connection, result["plan_id"])
    return {
        "schema_name": plan_request.schema_name,
        "prompt_version": plan_request.prompt_version,
        "plan_schema_field": result.get("plan_schema"),
        "validation_verdict": result["validation_verdict"],
        "plan_units_rows": unit_rows,
        "plan_content_hash_at_validation": result.get("plan_content_hash"),
        "plan_content_hash_after_approval_and_lessons": hash_now,
        "hash_unchanged": result.get("plan_content_hash") == hash_now,
        "outline_units": outline["plan"]["units"],
        "objectives": len(outline["objectives"]),
        "lessons_authored": len(lesson_result["lessons"]),
        "lessons_needing_review": lesson_result["needs_review"],
        "grading": {"verdict": submitted["verdict"],
                    "next_action": submitted["next_action"],
                    "evidence_class": submitted["evidence_class"]},
    }


def _json_dump(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str)


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names = argv[1:] or ["single", "short", "full"]
    summary: dict[str, str] = {}
    for name in names:
        work = Path(tempfile.mkdtemp(prefix=f"coursebook-h30b-{name}-"))
        previous = os.environ.get("HERMES_HOME")
        try:
            evidence = run_scenario(name, home=work / "home")
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
            shutil.rmtree(work, ignore_errors=True)
        (OUT / f"{name}.json").write_text(_json_dump(evidence) + "\n", encoding="utf-8")
        obs = evidence["observations"]
        summary[name] = (
            f"schema={obs['schema_name']} units={obs['units']} objectives={obs['objectives']} "
            f"checks={obs['checks']} lessons={obs['lessons']} validation={obs['validation_verdict']}"
        )
        print(f"{name}: {summary[name]}")
        for row in obs["check_lanes"]:
            print(f"  check lane: {row}")
        for row in evidence["steps"]["grading"]:
            submit = row.get("submit") or {}
            result = submit.get("result") if submit.get("ok") else submit.get("error")
            print(f"  grading[{row['label']}]: {json.dumps(result, default=str)[:400]}")

    # The two adversarial probes share a home each.
    for label, runner in (("fail_closed_approval", run_fail_closed_probe),
                          ("missing_required_step", run_missing_section_probe),
                          ("legacy_projection", run_legacy_probe)):
        work = Path(tempfile.mkdtemp(prefix=f"coursebook-h30b-{label}-"))
        previous = os.environ.get("HERMES_HOME")
        try:
            result = runner(work / "home")
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
            shutil.rmtree(work, ignore_errors=True)
        (OUT / f"{label}.json").write_text(_json_dump(result) + "\n", encoding="utf-8")
        print(f"{label}: {json.dumps(result, default=str)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
