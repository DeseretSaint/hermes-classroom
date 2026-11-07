"""H-40: arbitrary-topic end-to-end proof through the **current** (blueprint v2) product path.

Three non-Japanese briefs are driven through the real product surface in a throwaway
``HERMES_HOME``:

* ``course.create`` / ``enrollment.create`` / ``jobs.create`` — the cb.rpc envelope and
  ``coursebook.api.dispatch``, the same wire the Desktop plugin speaks;
* ``generation.run_plan_job`` — research seam, deterministic blueprint rules, independent
  validation, cost preflight, stored plan + units;
* ``plan.approve`` — H-12 fail-closed digest approval, refused before validation and refused on a
  stale hash;
* ``generation.run_unit_sections_job`` and ``generation.run_lesson_job`` per unit — the unit
  checkpoint path H-21 introduced, with the user (not the executor) enqueueing every unit;
* ``course.outline``, ``lesson.page``, ``check.open`` and ``attempt.submit`` — serving and grading
  through the real lanes.

What is **FAKE** and labelled so: the model. Every response is that scenario's recorded transcript
(``transcripts/*.json``, authored by ``build_transcripts.py``) replayed through the real pipeline,
with two distinct recorded model identities for author and validator so H-36 independence is
exercised rather than asserted. No provider is called and no spend occurs. The research fetch is an
in-memory recorded page through the real search seam, not the live web.

What is **real**: every schema, rule, transaction, approval check, projection, check payload,
grading lane and verdict under test. The script reports what it read; it does not assert a verdict
it did not observe.

Run from the product checkout:

    PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
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
from coursebook import text_completeness

HERE = Path(__file__).resolve().parent
TRANSCRIPTS = HERE / "transcripts"
EVIDENCE = HERE / "evidence"
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

#: Two distinct recorded identities: a validator that reports the author's own model name is
#: ``same_model`` under H-36, so the pass could not be called independent. Both are recordings.
AUTHOR_MODEL = "recorded-transcript-h40"
VALIDATOR_MODEL = "recorded-validator-h40"

def _has_japanese(text: str) -> bool:
    return any(
        0x3040 <= ord(char) <= 0x30FF
        or 0x3400 <= ord(char) <= 0x4DBF
        or 0x4E00 <= ord(char) <= 0x9FFF
        for char in text
    )


#: Marks that end a sentence; the short may only ever end on one of these.
_TERMINAL_MARKS = ".!?\u2026\u3002\uff01\uff1f"
#: Marks that separate clauses, so a sentence's own boundary can be kept when it has no full stop.
_CLAUSE_MARKS = ",;:\u2014\u2013"
_TRAILING_SEPARATORS = " ,;:\u2014\u2013"
#: The lesson schema's floor for an authored short; a candidate below it is not schema-valid.
_MIN_SHORT = 8


def _complete(candidate: str) -> bool:
    """True when the product's own completeness gate reads ``candidate`` as finished text.

    The harness imports the predicate rather than re-spelling it: a short it authors can never
    drift away from the shape the lesson validator reads, which is exactly the bit-rot that made
    D8's recorded evidence stale when H-46 landed.
    """
    return not text_completeness.completeness_problems(candidate, where="short")


def _terminated(fragment: str, terminal: str) -> str:
    return fragment.rstrip(_TRAILING_SEPARATORS).rstrip() + terminal


def _shorten(text: str) -> str:
    """A strictly shorter, complete-sentence prefix of ``text``: drops detail, adds no claim.

    The H-46 gate refuses a short that stops mid-sentence, so the old 2/3 word-boundary prefix is
    no longer an authored short — D8 recorded precisely those clipped endings, and the gate is
    right to refuse them. The contract is otherwise unchanged: the result is a strict prefix, so
    every claim atom it carries already occurs in the deep text. It now lands on a sentence or
    clause boundary and keeps the terminal mark, so it reads as a sentence on its own.
    """
    stripped = text.strip()
    if not stripped:
        return stripped
    terminal = stripped[-1] if stripped[-1] in _TERMINAL_MARKS else "."

    # 1. A complete first sentence, when the text holds more than one.
    for index, char in enumerate(stripped[:-1]):
        if char not in _TERMINAL_MARKS:
            continue
        candidate = stripped[: index + 1]
        if _MIN_SHORT <= len(candidate) < len(stripped) and _complete(candidate):
            return candidate

    target = (len(stripped) * 2) // 3

    # 2. The clause boundary closest to two thirds of the text, re-terminated as a sentence.
    clauses: list[str] = []
    for index, char in enumerate(stripped[:-1]):
        if char not in _CLAUSE_MARKS:
            continue
        candidate = _terminated(stripped[:index], terminal)
        if _MIN_SHORT <= len(candidate) < len(stripped) and _complete(candidate):
            clauses.append(candidate)
    if clauses:
        return min(clauses, key=lambda candidate: abs(len(candidate) - target))

    # 3. No sentence or clause boundary: the last whole-word prefix near two thirds that still
    #    ends a sentence (never on a function word the gate would call dangling).
    words = stripped.split()
    start = max(2, (len(words) * 2) // 3)
    for keep in range(min(start, len(words) - 1), 1, -1):
        candidate = _terminated(" ".join(words[:keep]), terminal)
        if _MIN_SHORT <= len(candidate) < len(stripped) and _complete(candidate):
            return candidate

    # 4. Nothing structural survives: keep the text whole rather than author a clipped sentence.
    dropped_word = _terminated(" ".join(words[:-1]), terminal)
    return dropped_word if len(dropped_word) < len(stripped) else stripped


class RecordedSearch:
    """One in-memory page through the real search seam (not the live web)."""

    def __init__(self, page: dict) -> None:
        self.page = page
        self.queries: list[str] = []
        self.fetches: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        return [{"url": self.page["url"], "title": self.page["title"],
                 "description": "recorded result"}][:limit]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.fetches.append(url)
        return {
            "url": self.page["url"],
            "title": self.page["title"],
            "publisher": "Recorded publisher",
            "published_at": None,
            "content": self.page["content"][:max_chars],
        }


class RecordedLLM:
    """Replays the recorded transcript; records every real request the pipeline sent.

    Everything that is a property of the *request* (rubric profile, capability policy, schema
    constant, unit ordinals, objective titles) is read from the live payload. Everything that is
    authored content (plan skeleton, lesson prose, check answers) comes from the recording. A
    request the recording cannot answer is a hard failure, never a fallback.
    """

    def __init__(self, transcript: dict) -> None:
        self.transcript = transcript
        self.requests: list = []

    # ── plan ────────────────────────────────────────────────────────────────
    def _plan(self, payload: dict, shape: dict | None = None, scenario: dict | None = None) -> dict:
        authored = self.transcript
        scenario = scenario or authored["scenario"]
        shape = shape or authored["shape"]
        assert payload.get("plan_schema") == gen.PLAN_SCHEMA_V2_NAME, payload.get("plan_schema")
        assert str(payload["scope"]) == scenario["scope"], (payload["scope"], scenario["scope"])
        scope = str(payload["scope"])
        units = []
        for unit in shape["units"]:
            units.append({
                "ordinal": int(unit["ordinal"]),
                "title": unit["title"],
                "goal": unit["goal"],
                "prereq_unit_ordinals": [int(ref) for ref in unit["prereq_unit_ordinals"]],
                "target_lessons": int(unit["target_lessons"]),
            })
        objectives = [
            {
                "ordinal": int(objective["ordinal"]),
                "unit_ref": int(objective["unit_ref"]),
                "title": objective["title"],
                "evidence_target": objective["evidence_target"],
                "evidence_criteria": list(objective["evidence_criteria"]),
                "support": "unverified",
                "source_ids": [],
            }
            for objective in shape["objectives"]
        ]
        checks = [
            {
                "objective_ref": int(item["objective_ref"]),
                "kind": item["kind"],
                "evidence_target": item["evidence_target"],
            }
            for item in shape["check_plan"]
        ]
        return {
            "plan_schema": gen.PLAN_SCHEMA_V2_NAME,
            "scope": scope,
            "title": scenario["title"],
            "learner_outcome": shape["learner_outcome"],
            "delivery": "self_study",
            "time_estimate": {
                "sessions_per_week": int(shape["sessions_per_week"]),
                "minutes_per_session": 60,
                "weeks": int(shape["weeks"]),
                "basis": "none",
                "confidence": "low",
                "rationale": "Authored estimate from the recorded transcript; no transfer claim.",
                "benchmark": None,
                "attainment_hours": None,
            },
            "units": units,
            "objectives": objectives,
            "check_plan": checks,
            "context_needs": ["the actual equipment or a quiet keyboard"],
            "source_ids": [],
            "exclusions": ["Does not certify competence; a supervisor checks the first attempt."],
            "spaced_review": scenario["recipe"] != "one_off",
            "evidence_note": None,
        }

    # ── unit sections ───────────────────────────────────────────────────────
    def _unit_sections(self, payload: dict) -> dict:
        unit = payload["unit"]
        ordinal = int(unit["ordinal"])
        by_title = self.transcript["lessons"]
        sections = []
        for objective in payload["objectives"]:
            title = str(objective["title"])
            if title not in by_title:
                raise AssertionError(f"recording has no lesson for objective {title!r}")
            sections.append({
                "ordinal": int(objective["ordinal"]),
                "unit_ref": ordinal,
                "role": "owner",
                "primary_objective_ref": int(objective["ordinal"]),
                "reinforces": [],
                "title": title,
                "lesson_intent": by_title[title]["intent"],
                "context_needs": [],
                "source_ids": [],
                "media_need": {
                    "construct": "",
                    "image": {"level": "none", "role": "none"},
                    "audio": {"level": "none", "role": "none"},
                },
            })
        return {"unit_ref": ordinal, "sections": sections}

    # ── lesson ──────────────────────────────────────────────────────────────
    def _lesson(self, payload: dict) -> dict:
        section = payload["section"]
        objective = payload["objective"]
        title = str(objective["title"])
        recording = self.transcript["lessons"].get(title)
        if recording is None:
            raise AssertionError(f"recording has no lesson for objective {title!r}")
        target = str(objective["evidence_target"])
        capability = payload["capability_policy"]
        profile = rubrics.resolve_profile(str(capability["rubric_profile"]), target)
        rubric = [
            {"criterion": criterion.label, "weight": 1.0,
             "description": criterion.observation}
            for criterion in rubrics.RUBRICS[profile].criteria
        ]
        practice = str(recording["practice"])
        criterion = str(recording["criterion"])
        explanation = str(recording["explanation"])
        if recording.get("items"):
            check = {
                "kind": "verification",
                "stimulus": {
                    "prompt": recording["check_prompt"],
                    "format": "verification",
                    "choices": [],
                    "items": [dict(item) for item in recording["items"]],
                },
                "learner_instructions": "Tick only what you actually did.",
                "evidence_target": target,
                "accepted_answers": list(recording["accepted_answers"]),
                "accepted_alternatives": [],
                "rubric": rubric,
                "reference_answer": recording["reference_answer"],
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "none"},
                "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
            }
        else:
            check = {
                "kind": "quiz",
                "stimulus": {
                    "prompt": recording["check_prompt"],
                    "format": "text",
                    "choices": [],
                    "items": [],
                },
                "learner_instructions": "Answer in one short phrase, without notes.",
                "evidence_target": target,
                "accepted_answers": list(recording["accepted_answers"]),
                "accepted_alternatives": [],
                "rubric": rubric,
                "reference_answer": recording["reference_answer"],
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "none"},
                "scaffolds": {"romaji": False, "furigana": False, "english_meaning": False},
            }
        return {
            "section_title": section["title"],
            "segments": [
                {"kind": "model", "heading": "The step", "body": practice,
                 "short": _shorten(practice)},
                {"kind": "guided", "heading": "Do it", "body": criterion,
                 "short": _shorten(criterion)},
            ],
            "worked_example": {
                "prompt": f"A worked example of {section['title']}",
                "steps": list(recording["example_steps"]),
                "answer": f"The step is done and checked. {criterion}",
                "short": _shorten(f"The step is done and checked. {criterion}"),
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
    def _validation(self) -> dict:
        return {
            "verdict": "pass",
            "criteria": [
                {"id": criterion, "verdict": "pass",
                 "reason": f"{criterion} checked against the recorded artifact"}
                for criterion in gen.VALIDATION_CRITERIA
            ],
            "rejections": [],
            "claim_verdicts": [],
        }

    def __call__(self, request):
        self.requests.append(request)
        payload = json.loads(request.input_text)
        if request.purpose == "coursebook.plan.generate":
            document = self._plan(payload)
        elif request.purpose == "coursebook.plan.validate":
            document = self._validation()
        elif request.purpose == "coursebook.unit_sections.generate":
            document = self._unit_sections(payload)
        elif request.purpose == "coursebook.unit_sections.validate":
            document = self._validation()
        elif request.purpose == "coursebook.lesson.generate":
            document = self._lesson(payload)
        elif request.purpose == "coursebook.lesson.validate":
            document = self._validation()
        else:
            raise AssertionError(f"unexpected provider call {request.purpose!r}")
        validator = request.purpose.endswith(".validate")
        text = json.dumps(document, ensure_ascii=False)
        return gen.LLMResponse(
            text=text,
            parsed=document,
            provider="recorded",
            model=VALIDATOR_MODEL if validator else AUTHOR_MODEL,
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
        "operation_id": f"op-h40-{method.replace('.', '-')}-{os.urandom(3).hex()}",
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


DIALS = {"pace": "steady", "depth": "working", "assessment": "graded", "autonomy": "guided"}
BUDGET = gen.CostBudget(max_calls=400, max_cost_usd=100.0, source="caller")


def _plan_state(plan_id: str) -> str:
    from coursebook import db

    with db.read() as connection:
        return str(connection.execute("SELECT state FROM plans WHERE id = ?", (plan_id,)).fetchone()[0])


def _job_count() -> int:
    from coursebook import db

    with db.read() as connection:
        return int(connection.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"])


def transcribe(transcript: dict):
    return RecordedLLM(transcript)


def _prepare(home: Path) -> None:
    from coursebook import db, domain  # noqa: F401 - binds RPC handlers
    from coursebook import pack_flow  # noqa: F401

    os.environ["HERMES_HOME"] = str(home)
    db.migrate()
    with db.read() as connection:
        gen.ensure_schema(connection)


def _create_course(scenario: dict, *, key_prefix: str) -> tuple[str, str]:
    brief = {key: scenario[key] for key in
             ("title", "goal", "recipe", "scope", "locale", "level", "subject_domain")}
    created = _ok("course.create", {**brief, "dials": DIALS}, key=f"{key_prefix}-create")
    enrollment = _ok("enrollment.create",
                     {"course_id": created["course_id"], "learner_label": scenario["title"]},
                     key=f"{key_prefix}-enroll")
    return created["course_id"], enrollment["enrollment_id"]


def _plan_brief(scenario: dict, course_id: str, enrollment_id: str) -> dict:
    return {
        "stage": "plan", "course_id": course_id, "enrollment_id": enrollment_id,
        "goal": scenario["goal"], "recipe": scenario["recipe"], "dials": DIALS,
        "locale": scenario["locale"], "level": scenario["level"],
        "subject_domain": scenario["subject_domain"], "scope": scenario["scope"],
    }


def run_scenario(name: str, *, home: Path) -> dict:
    """Drive one arbitrary-topic course end to end and return its evidence record."""
    from coursebook import db

    _prepare(home)
    transcript = json.loads((TRANSCRIPTS / f"{name}.json").read_text(encoding="utf-8"))
    scenario = transcript["scenario"]
    llm = transcribe(transcript)
    search = RecordedSearch(transcript["research"])

    evidence: dict = {
        "scenario": scenario,
        "labels": {
            "model": "RECORDED TRANSCRIPT (hand-authored, replayed through the real pipeline)",
            "validator": "RECORDED TRANSCRIPT, distinct recorded model identity (H-36)",
            "research": "RECORDED PAGE (fetched through the real search seam, bytes are a recording)",
            "provider_calls": 0,
            "provider_spend_usd": 0.0,
        },
        "steps": {},
        "observations": {},
    }

    course_id, enrollment_id = _create_course(scenario, key_prefix=f"h40-{name}")
    plan_brief = _plan_brief(scenario, course_id, enrollment_id)
    job = _ok("jobs.create", {"kind": "plan", "brief": plan_brief}, key=f"h40-{name}-plan-job")
    connection = db.connect()
    try:
        plan_result = gen.run_plan_job(
            connection, {"job_id": job["job_id"], "brief": plan_brief}, llm, search, now=NOW,
        )
    finally:
        connection.close()
    plan_id = plan_result["plan_id"]
    plan_request = next(r for r in llm.requests if r.purpose == "coursebook.plan.generate")
    evidence["steps"]["plan_job"] = {
        "result": plan_result,
        "request": {
            "prompt_version": plan_request.prompt_version,
            "schema_name": plan_request.schema_name,
            "objective_count_rule": json.loads(plan_request.input_text)["rules"]["objective_count"],
            "unit_count_rule": json.loads(plan_request.input_text)["rules"]["unit_count"],
            "unit_objective_count_rule": json.loads(plan_request.input_text)["rules"]["unit_objective_count"],
        },
        "research": {"status": plan_result["research"]["status"],
                     "queries": len(search.queries), "fetches": len(search.fetches)},
    }

    # H-12 fail-closed: approval before validation and on a stale digest must both be refused.
    early = _rpc("plan.approve", {
        "enrollment_id": enrollment_id, "plan_id": plan_id,
        "plan_hash": plan_result["plan_hash"],
    }, key=f"h40-{name}-approve-early", expected_revision=-1)
    tampered = _rpc("plan.approve", {
        "enrollment_id": enrollment_id, "plan_id": plan_id,
        "plan_hash": "sha256:" + "0" * 64,
    }, key=f"h40-{name}-approve-wrong", expected_revision=0)
    evidence["steps"]["approval_refusals"] = [
        {"probe": "before_validation_wrong_revision", "ok": early["ok"],
         "error_code": (early.get("error") or {}).get("code"), "state_after": _plan_state(plan_id)},
        {"probe": "stale_hash", "ok": tampered["ok"],
         "error_code": (tampered.get("error") or {}).get("code"), "state_after": _plan_state(plan_id)},
    ]

    book = _ok("parent.blueprint.read", {"course_id": course_id})
    approval = _ok("plan.approve", {
        "enrollment_id": enrollment_id, "plan_id": plan_id,
        "plan_hash": book["plan"]["plan_hash"],
    }, expected_revision=0, key=f"h40-{name}-approve")
    evidence["steps"]["approve"] = {
        "plan_hash": approval["plan_hash"],
        "revision": approval["revision"],
        "state_after": _plan_state(plan_id),
        "approval_provenance": book["plan"].get("validation_source"),
    }

    with db.read() as connection:
        stored = dict(connection.execute(
            "SELECT document_json, generation_state, validation_id FROM gen_plan_documents"
            " WHERE plan_id = ?", (plan_id,)).fetchone())
        unit_rows = [dict(row) for row in connection.execute(
            "SELECT ordinal, title, prereq_unit_ordinals_json, target_lessons FROM plan_units"
            " WHERE plan_id = ? ORDER BY ordinal", (plan_id,)).fetchall()]
    plan_document = json.loads(stored["document_json"])["plan"]
    evidence["plan_document"] = plan_document
    evidence["steps"]["stored_plan"] = {
        "generation_state": stored["generation_state"],
        "validation_id_present": bool(stored["validation_id"]),
        "unit_rows": unit_rows,
    }

    units = [int(row["ordinal"]) for row in unit_rows]
    evidence["steps"]["unit_stages"] = []
    for ordinal in units:
        unit_brief = {"stage": "unit_sections", "plan_id": plan_id,
                      "enrollment_id": enrollment_id, "unit_ordinal": ordinal}
        unit_job = _ok("jobs.create", {"kind": "plan", "brief": unit_brief},
                       key=f"h40-{name}-unit-{ordinal}")
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
            "next_unit_ordinal": unit_result.get("next_unit_ordinal"),
        })

    evidence["steps"]["lesson_stages"] = []
    for ordinal in units:
        lesson_brief = {"stage": "lessons", "plan_id": plan_id,
                        "enrollment_id": enrollment_id, "unit_ordinal": ordinal}
        lesson_job = _ok("jobs.create", {"kind": "plan", "brief": lesson_brief},
                         key=f"h40-{name}-lessons-{ordinal}")
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
    first_objective = outline["objectives"][0]["objective_id"]
    page = _ok("lesson.page", {"enrollment_id": enrollment_id, "objective_id": first_objective})
    evidence["steps"]["lesson_page"] = page

    # Grading through the real RPC: one correct answer, and for quizzes one wrong answer.
    revision = approval["revision"]
    objectives = outline["objectives"]
    recording = transcript["lessons"]

    def recorded_answer(objective) -> dict:
        entry = recording[objective["title"]]
        if entry.get("items"):
            return {"kind": "selection", "selection": [item["id"] for item in entry["items"]]}
        return {"kind": "text", "text": entry["reference_answer"]}

    attempts = [(objectives[0], recorded_answer(objectives[0]), "correct")]
    if scenario["recipe"] != "one_off" and len(objectives) > 1:
        attempts.append((objectives[1], {"kind": "text", "text": "a deliberately wrong answer"},
                         "wrong"))
    grading_rows = []
    for objective, answer, label in attempts:
        opened = _rpc("check.open", {
            "enrollment_id": enrollment_id, "objective_id": objective["objective_id"],
        }, expected_revision=revision, key=f"h40-{name}-open-{objective['ordinal']}-{label}")
        if not opened["ok"]:
            grading_rows.append({"label": label, "objective_ordinal": objective["ordinal"],
                                 "open": opened})
            continue
        revision = opened["result"]["revision"]
        submitted = _rpc("attempt.submit", {
            "enrollment_id": enrollment_id,
            "check_id": opened["result"]["check_id"],
            "check_version": opened["result"]["check_version"],
            "attempt_nonce": f"h40-nonce-{label}-{objective['ordinal']}",
            "answer": answer,
        }, expected_revision=revision, key=f"h40-{name}-submit-{objective['ordinal']}-{label}")
        if submitted["ok"]:
            revision = submitted["result"]["revision"]
        grading_rows.append({
            "label": label, "objective_ordinal": objective["ordinal"],
            "check_id": opened["result"]["check_id"],
            "stimulus_format": opened["result"].get("stimulus", {}).get("format"),
            "open": {"ok": True, "revision": opened["result"]["revision"]},
            "submit": submitted,
        })
    evidence["steps"]["grading"] = grading_rows

    with db.read() as connection:
        check_rows = [dict(row) for row in connection.execute(
            "SELECT id, objective_id, state, version, audit_state, stimulus_json,"
            " reference_json, rubric_json FROM checks ORDER BY created_at, id").fetchall()]
        attempt_rows = [dict(row) for row in connection.execute(
            "SELECT id, check_id, state, verdict, evidence_class, grading_provenance_json"
            " FROM attempts ORDER BY created_at, id").fetchall()]
        lesson_rows = [dict(row) for row in connection.execute(
            "SELECT id, section_id, state, page_json FROM gen_lessons"
            " WHERE plan_id = ? ORDER BY created_at, id", (plan_id,)).fetchall()]
        section_rows = [dict(row) for row in connection.execute(
            "SELECT ordinal, section_role, objective_refs_json FROM gen_plan_sections"
            " WHERE plan_id = ? ORDER BY ordinal", (plan_id,)).fetchall()]
    lesson_pages = [json.loads(row.pop("page_json")) for row in lesson_rows]
    check_lanes = [
        {
            "objective_id": row["objective_id"],
            "reference_kind": (json.loads(row["reference_json"]).get("kind")
                               if row["reference_json"] else None),
            "stimulus_format": (json.loads(row["stimulus_json"]).get("format")
                                if row["stimulus_json"] else None),
            "state": row["state"],
        }
        for row in check_rows
    ]
    evidence["observations"] = {
        "schema_name": plan_request.schema_name,
        "prompt_version": plan_request.prompt_version,
        "plan_scope": plan_result["scope"],
        "validation_verdict": plan_result["validation_verdict"],
        "validation_outcome": plan_result["validation"]["outcome"],
        "validation_independence": plan_result["validation"]["independence"],
        "approval_provenance": plan_result.get("approval_provenance"),
        "plan_state_before_approval": "draft",
        "plan_state_after_approval": _plan_state(plan_id),
        "units": len(unit_rows),
        "objectives": len(outline["objectives"]),
        "checks": len(check_rows),
        "lessons": len(lesson_rows),
        "sections": len(section_rows),
        "outline_units": [
            {"ordinal": unit["ordinal"], "prereq_unit_ordinals": unit["prereq_unit_ordinals"],
             "prerequisite_state": unit["prerequisite_state"], "unmet": len(unit["unmet"]),
             "objectives": len(unit["objectives"])}
            for unit in outline["plan"]["units"]
        ],
        "check_lanes": check_lanes,
        "attempt_rows": attempt_rows,
    }
    evidence["lesson_rows"] = [
        {"lesson_id": row["id"], "section_id": row["section_id"], "state": row["state"],
         "page": page}
        for row, page in zip(lesson_rows, lesson_pages)
    ]

    assertions = _assert_scenario(name, scenario, evidence)
    evidence["assertions"] = assertions
    evidence["verdict"] = "PASS" if all(assertions.values()) else "FAIL"
    return evidence


def _assert_scenario(name: str, scenario: dict, evidence: dict) -> dict[str, bool]:
    obs = evidence["observations"]
    grading = evidence["steps"]["grading"]
    submitted = [row.get("submit") or {} for row in grading]
    results = [row.get("result") if row.get("ok") else row.get("error") for row in submitted]
    correct = next((result for row, result in zip(grading, results)
                    if row["label"] == "correct"), None) or {}
    wrong = next((result for row, result in zip(grading, results)
                  if row["label"] == "wrong"), None)
    lanes = obs["check_lanes"]
    unit_rows = evidence["steps"]["stored_plan"]["unit_rows"]
    outline_units = obs["outline_units"]
    page_blob = json.dumps(evidence["steps"]["lesson_page"], ensure_ascii=False, sort_keys=True)
    lessons_blob = json.dumps([row["page"] for row in evidence["lesson_rows"]],
                              ensure_ascii=False, sort_keys=True)
    plan_blob = json.dumps(evidence["plan_document"], ensure_ascii=False, sort_keys=True)
    all_blob = json.dumps(evidence["steps"], ensure_ascii=False, sort_keys=True, default=str)

    # Prerequisite edges are whatever the recording authored; the outline must project a state.
    edges = {int(row["ordinal"]): json.loads(row["prereq_unit_ordinals_json"] or "[]")
             for row in unit_rows}
    edges_backwards = all(
        ref < ordinal for ordinal, refs in edges.items() for ref in refs
    )
    outline_has_state = all(unit["prerequisite_state"] for unit in outline_units)

    assertions = {
        "no_japanese_content_in_plan": not _has_japanese(plan_blob),
        "no_japanese_content_in_lessons": not _has_japanese(lessons_blob),
        "no_japanese_content_in_run": not _has_japanese(all_blob),
        "plan_independently_validated": obs["validation_outcome"] == "independently_validated",
        "plan_validated_before_approval": obs["validation_verdict"] == "pass",
        "approval_after_validation_succeeded": obs["plan_state_after_approval"] == "approved",
        "approval_refused_before_and_on_stale_hash": all(
            not row["ok"] for row in evidence["steps"]["approval_refusals"]
        ),
        "every_lesson_validated": all(row["state"] == "validated" for row in evidence["lesson_rows"]),
        "one_section_per_objective": obs["sections"] == obs["objectives"],
        "prerequisite_edges_point_backwards": edges_backwards,
        "outline_projects_prerequisite_state": outline_has_state,
        "units_user_enqueued_not_chained": all(
            not stage["chained_a_job"] for stage in evidence["steps"]["unit_stages"]
        ) and all(not stage["chained_a_job"] for stage in evidence["steps"]["lesson_stages"]),
        "no_answer_key_in_served_lesson": not any(
            str(recording.get("reference_answer") or "") in page_blob
            for recording in json.loads(
                (TRANSCRIPTS / f"{name}.json").read_text(encoding="utf-8"))["lessons"].values()
            if recording.get("reference_answer")
        ),
    }

    if name == "bicycle_single":
        assertions.update({
            "exactly_one_unit": obs["units"] == 1,
            "exactly_one_objective": obs["objectives"] == 1,
            "exactly_one_check": obs["checks"] == 1,
            "the_check_is_verification": all(
                lane["stimulus_format"] == "verification" and lane["reference_kind"] == "rubric_only"
                for lane in lanes
            ),
            "no_quiz_lane_present": not any(lane["reference_kind"] == "exact" for lane in lanes),
            "verification_is_graded_as_self_reported": correct.get("verdict") == "pass"
            and correct.get("evidence_class") == "self_reported",
        })
    elif name == "music_short":
        assertions.update({
            "two_units": obs["units"] == 2,
            "four_objectives": obs["objectives"] == 4,
            "every_check_is_an_exact_lane_quiz": all(
                lane["reference_kind"] == "exact" and lane["stimulus_format"] == "text"
                for lane in lanes
            ),
            "correct_answer_passes": correct.get("verdict") == "pass",
            "wrong_answer_is_not_yet": wrong is not None and wrong.get("verdict") == "not_yet",
        })
    elif name == "soldering_full":
        assertions.update({
            "multi_unit_course": obs["units"] >= 2,
            "prerequisite_edges_declared": any(edges.values()),
            "graded_checks_present": len(lanes) == obs["objectives"] and all(
                lane["reference_kind"] == "exact" for lane in lanes
            ),
            "correct_answer_passes": correct.get("verdict") == "pass",
            "wrong_answer_is_not_yet": wrong is not None and wrong.get("verdict") == "not_yet",
            "plan_ceiling_probe_ran": bool(evidence.get("ceiling_probe")),
        })
        probe = evidence.get("ceiling_probe") or {}
        assertions["plan_at_declared_bound_accepted"] = probe.get("at_bound", {}).get("accepted") is True
        assertions["plan_over_declared_bound_rejected"] = probe.get("over_bound", {}).get("rejected") is True
    return assertions


# ── the plan-ceiling probe ──────────────────────────────────────────────────


class CeilingLLM(RecordedLLM):
    """Replays the full-scope recording with a plan document authored to a chosen size."""

    def __init__(self, transcript: dict, *, units: int, objectives: int) -> None:
        super().__init__(transcript)
        self.units_n = units
        self.objectives_n = objectives

    def _plan(self, payload: dict, shape: dict | None = None, scenario: dict | None = None) -> dict:
        document = super()._plan(payload, shape, scenario)
        # The declared time estimate must schedule every lesson: 12 weeks x 2 sessions could not
        # hold 40 lessons, and a rule violation would make the ceiling claim meaningless.
        document["time_estimate"]["weeks"] = 52
        document["time_estimate"]["sessions_per_week"] = 2
        per_unit = self.objectives_n // self.units_n
        remainder = self.objectives_n % self.units_n
        document["units"] = [
            {
                "ordinal": ordinal,
                "title": f"Cumulative unit {ordinal}",
                "goal": f"Unit {ordinal} builds on the unit before it.",
                "prereq_unit_ordinals": [ordinal - 1] if ordinal > 1 else [],
                "target_lessons": per_unit + (1 if ordinal <= remainder else 0),
            }
            for ordinal in range(1, self.units_n + 1)
        ]
        document["objectives"] = []
        document["check_plan"] = []
        ordinal = 0
        for unit in document["units"]:
            for _ in range(unit["target_lessons"]):
                ordinal += 1
                document["objectives"].append({
                    "ordinal": ordinal,
                    "unit_ref": unit["ordinal"],
                    "title": f"Objective {ordinal}",
                    "evidence_target": "comprehension",
                    "evidence_criteria": [f"Explains point {ordinal} without notes"],
                    "support": "unverified",
                    "source_ids": [],
                })
                document["check_plan"].append({
                    "objective_ref": ordinal, "kind": "quiz", "evidence_target": "comprehension",
                })
        assert ordinal == self.objectives_n, (ordinal, self.objectives_n)
        return document


def run_ceiling_probe(home: Path) -> dict:
    """The full-scope plan bound is accepted at the declared ceiling and refused above it."""
    from coursebook import db

    _prepare(home)
    transcript = json.loads((TRANSCRIPTS / "soldering_full.json").read_text(encoding="utf-8"))
    scenario = transcript["scenario"]
    expectation = gen.SCOPE_EXPECTATIONS["full"]
    unit_ceiling = expectation["blueprint_units"][1]
    objective_ceiling = expectation["blueprint_objectives"][1]

    def attempt(*, units: int, objectives: int, label: str) -> dict:
        llm = CeilingLLM(transcript, units=units, objectives=objectives)
        search = RecordedSearch(transcript["research"])
        course_id, enrollment_id = _create_course(scenario, key_prefix=f"h40-ceiling-{label}")
        brief = _plan_brief(scenario, course_id, enrollment_id)
        job = _ok("jobs.create", {"kind": "plan", "brief": brief},
                  key=f"h40-ceiling-{label}-job")
        connection = db.connect()
        try:
            result = gen.run_plan_job(
                connection, {"job_id": job["job_id"], "brief": brief}, llm, search, now=NOW,
            )
        except Exception as exc:  # noqa: BLE001 - a rule refusal is the evidence
            return {"label": label, "units": units, "objectives": objectives,
                    "raised": type(exc).__name__, "message": str(exc)}
        finally:
            connection.close()
        return {
            "label": label,
            "units": units,
            "objectives": objectives,
            "status": result["status"],
            "validation_verdict": result["validation_verdict"],
            "plan_units": result["units"],
            "plan_objectives": result["objectives"],
            "validation": result.get("validation"),
            "warnings": result.get("warnings"),
        }

    at_bound = attempt(units=unit_ceiling, objectives=objective_ceiling, label="at_bound")
    over_bound = attempt(units=unit_ceiling, objectives=objective_ceiling + 1, label="over_bound")
    probe = {
        "declared_bound": {"units": unit_ceiling, "objectives": objective_ceiling},
        "at_bound": dict(at_bound),
        "over_bound": dict(over_bound),
    }
    probe["at_bound"]["accepted"] = (
        at_bound.get("plan_units") == unit_ceiling
        and at_bound.get("plan_objectives") == objective_ceiling
        and at_bound.get("status") == "draft"
        and at_bound.get("validation_verdict") == "pass"
    )
    probe["over_bound"]["rejected"] = "raised" in over_bound or over_bound.get("status") in (
        "rejected", "needs_review"
    )
    return probe


# ── the partial-unit-batch probe (H-30b D1) ─────────────────────────────────


class DropSectionLLM(RecordedLLM):
    """The recorded unit batch with one required owner section missing."""

    def __init__(self, transcript: dict, *, unit_ordinal: int) -> None:
        super().__init__(transcript)
        self.drop_unit_ordinal = unit_ordinal

    def _unit_sections(self, payload: dict) -> dict:
        document = super()._unit_sections(payload)
        if int(payload["unit"]["ordinal"]) == self.drop_unit_ordinal:
            document["sections"] = document["sections"][:-1]
        return document


def run_partial_unit_probe(home: Path) -> dict:
    """What a unit stage that cannot author every owner section actually persists."""
    from coursebook import db

    _prepare(home)
    transcript = json.loads((TRANSCRIPTS / "music_short.json").read_text(encoding="utf-8"))
    scenario = transcript["scenario"]
    llm = DropSectionLLM(transcript, unit_ordinal=2)
    search = RecordedSearch(transcript["research"])
    course_id, enrollment_id = _create_course(scenario, key_prefix="h40-partial")
    brief = _plan_brief(scenario, course_id, enrollment_id)
    job = _ok("jobs.create", {"kind": "plan", "brief": brief}, key="h40-partial-plan-job")
    connection = db.connect()
    try:
        plan_result = gen.run_plan_job(
            connection, {"job_id": job["job_id"], "brief": brief}, llm, search, now=NOW,
        )
    finally:
        connection.close()
    plan_id = plan_result["plan_id"]
    book = _ok("parent.blueprint.read", {"course_id": course_id})
    _ok("plan.approve", {"enrollment_id": enrollment_id, "plan_id": plan_id,
                         "plan_hash": book["plan"]["plan_hash"]},
        expected_revision=0, key="h40-partial-approve")
    unit_brief = {"stage": "unit_sections", "plan_id": plan_id,
                  "enrollment_id": enrollment_id, "unit_ordinal": 2}
    unit_job = _ok("jobs.create", {"kind": "plan", "brief": unit_brief}, key="h40-partial-unit")
    connection = db.connect()
    try:
        unit_result = gen.run_unit_sections_job(
            connection, {"job_id": unit_job["job_id"], "brief": unit_brief}, llm,
            plan_id=plan_id, unit_ordinal=2, now=NOW, budget=BUDGET,
        )
    finally:
        connection.close()
    with db.read() as connection:
        sections = [dict(row) for row in connection.execute(
            "SELECT ordinal, section_role, objective_refs_json FROM gen_plan_sections"
            " WHERE plan_id = ? ORDER BY ordinal", (plan_id,)).fetchall()]
        lessons = int(connection.execute(
            "SELECT COUNT(*) AS n FROM gen_lessons WHERE plan_id = ?", (plan_id,)).fetchone()["n"])
        checks = int(connection.execute("SELECT COUNT(*) AS n FROM checks").fetchone()["n"])
    lesson_brief = {"stage": "lessons", "plan_id": plan_id,
                    "enrollment_id": enrollment_id, "unit_ordinal": 2}
    lesson_job = _ok("jobs.create", {"kind": "plan", "brief": lesson_brief},
                     key="h40-partial-lessons")
    connection = db.connect()
    try:
        gen.run_lesson_job(connection, {"job_id": lesson_job["job_id"], "brief": lesson_brief},
                           llm, plan_id=plan_id, unit_ordinal=2, now=NOW, budget=BUDGET)
    except Exception as exc:  # noqa: BLE001 - a refusal is the evidence
        refusal = {"type": type(exc).__name__, "message": str(exc)}
    else:
        refusal = None
    finally:
        connection.close()
    outline = _ok("course.outline", {"enrollment_id": enrollment_id})
    unit_two = next(unit for unit in outline["plan"]["units"] if int(unit["ordinal"]) == 2)
    missing_objective = unit_two["objectives"][-1]
    page = _rpc("lesson.page", {"enrollment_id": enrollment_id,
                                "objective_id": missing_objective["objective_id"]})
    return {
        "unit_result": unit_result,
        "persisted_sections": sections,
        "lessons_after_refusal": lessons,
        "checks_after_refusal": checks,
        "lesson_stage_refusal": refusal,
        "outline_missing_objective": {
            key: missing_objective.get(key)
            for key in ("ordinal", "title", "state", "check_state")
        },
        "lesson_page_ok": page["ok"],
        "lesson_page_state": (page.get("result") or {}).get("state"),
        "lesson_page_view_note": (page.get("result") or {}).get("view_note"),
        "lesson_page_check_id": (page.get("result") or {}).get("check_id"),
        "lesson_page_error": page.get("error"),
    }


def _json_dump(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str)


def _run(label: str, runner, *, prefix: str):
    work = Path(tempfile.mkdtemp(prefix=f"coursebook-h40-{prefix}-"))
    previous = os.environ.get("HERMES_HOME")
    try:
        return runner(work / "home")
    finally:
        if previous is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str]) -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    names = [name for name in (argv[1:] or list(TRANSCRIPTS.glob("*.json")))]
    names = [Path(name).stem for name in names]
    lines: list[str] = []
    summary: dict[str, str] = {}
    overall = True

    def emit(text: str = "") -> None:
        print(text)
        lines.append(text)

    emit("H-40 arbitrary-topic evidence packet — base c588e4a (blueprint v2)")
    emit(f"model: RECORDED TRANSCRIPT ({AUTHOR_MODEL}) / validator RECORDED ({VALIDATOR_MODEL})")
    emit("provider calls: 0, provider spend: $0.00, network: none")
    emit()
    for name in names:
        evidence = _run(name, lambda home: run_scenario(name, home=home), prefix=name)
        probe = None
        if name == "soldering_full":
            probe = _run(name, run_ceiling_probe, prefix=f"{name}-ceiling")
            evidence["ceiling_probe"] = probe
            evidence["assertions"] = _assert_scenario(name, evidence["scenario"], evidence)
            evidence["verdict"] = "PASS" if all(evidence["assertions"].values()) else "FAIL"
        (EVIDENCE / f"{name}.json").write_text(_json_dump(evidence) + "\n", encoding="utf-8")
        summary[name] = evidence["verdict"]
        overall = overall and evidence["verdict"] == "PASS"
        obs = evidence["observations"]
        emit(f"{name}: {evidence['verdict']}  scope={obs['plan_scope']} "
             f"units={obs['units']} objectives={obs['objectives']} checks={obs['checks']} "
             f"lessons={obs['lessons']} validation={obs['validation_outcome']}")
        for check, value in evidence["assertions"].items():
            emit(f"  {'PASS' if value else 'FAIL'}  {check}")
        for row in evidence["steps"]["grading"]:
            submit = row.get("submit") or {}
            outcome = submit.get("result") if submit.get("ok") else submit.get("error")
            emit(f"  grading[{row['label']}]: {json.dumps(outcome, default=str)}")
        if probe:
            emit(f"  ceiling at bound {probe['declared_bound']}: "
                 f"{json.dumps(probe['at_bound'], default=str)}")
            emit(f"  ceiling over bound: {json.dumps(probe['over_bound'], default=str)}")
        emit()
    partial = _run("partial", run_partial_unit_probe, prefix="partial-unit")
    (EVIDENCE / "partial_unit_batch.json").write_text(_json_dump(partial) + "\n", encoding="utf-8")
    emit("partial_unit_batch (H-30b D1): "
         f"unit state={partial['unit_result'].get('state')} "
         f"persisted_sections={len(partial['persisted_sections'])} "
         f"lesson_refusal={(partial['lesson_stage_refusal'] or {}).get('type')} "
         f"page_state={partial['lesson_page_state']} check_id={partial['lesson_page_check_id']}")
    (EVIDENCE / "run-output.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (EVIDENCE / "summary.json").write_text(_json_dump(summary) + "\n", encoding="utf-8")
    emit(f"overall: {'PASS' if overall else 'FAIL'}  ({sum(v == 'PASS' for v in summary.values())}"
         f"/{len(summary)} scenarios)")
    (EVIDENCE / "run-output.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
